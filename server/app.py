from flask import Flask, jsonify, redirect, request, session, send_from_directory, url_for
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
import os
import json
import time
from urllib.parse import urlencode
import requests
from requests.auth import HTTPBasicAuth
from werkzeug.middleware.proxy_fix import ProxyFix
import subprocess
import atexit
import sqlite3

# --- App Initialization ---

# Initialize the Flask application to serve static files from the 'client' directory
app = Flask(__name__, static_folder='../client', static_url_path='')

# Add ProxyFix middleware to trust headers from Render's proxy.
# This is crucial for OAuth redirects to work correctly in production.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Set a secret key for session management from environment variables
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

# --- Database Path Configuration ---
# Use the DATABASE_DIR from environment variables if it exists (for production on Render).
# Otherwise, fall back to a local directory within the project (for staging/local).
DATABASE_DIR = os.environ.get('DATABASE_DIR', os.path.join(os.getcwd(), 'server', 'tasks'))
TASKS_DIR = os.path.join(os.getcwd(), 'server', 'tasks')

# Ensure the directories exist
if not os.path.exists(DATABASE_DIR):
    os.makedirs(DATABASE_DIR)
if not os.path.exists(TASKS_DIR):
    os.makedirs(TASKS_DIR)

# Keep track of background processes
background_processes = {}

def cleanup_processes():
    for league_id, process in background_processes.items():
        if process.poll() is None:  # Check if the process is still running
            print(f"Terminating background process for league {league_id}")
            process.terminate()
            process.wait()

atexit.register(cleanup_processes)


# --- Credential Handling for Render ---

# This block writes the environment variable to a file on the fly.
# The 'yahoo-oauth' and 'yfpy' libraries require a file to read credentials from.
# We write it to the /tasks directory where the background script will run.
YAHOO_CREDENTIALS_FILE = os.path.join(TASKS_DIR, 'private.json')
private_content = os.environ.get('YAHOO_PRIVATE_JSON')
if private_content:
    print(f"YAHOO_PRIVATE_JSON environment variable found. Writing to {YAHOO_CREDENTIALS_FILE}.")
    with open(YAHOO_CREDENTIALS_FILE, 'w') as f:
        f.write(private_content)
else:
    # Also write a local copy for the main app if not on Render
    if not os.path.exists('private.json'):
         print("YAHOO_PRIVATE_JSON not found. Assuming local private.json file exists for development.")

# --- Centralized Authentication Helper ---
def get_and_validate_token():
    """
    Retrieves token from session, ensures GUID is present, and refreshes if needed.
    Returns a complete, valid token dictionary, or None.
    """
    if 'yahoo_token_data' not in session:
        return None

    token_data = session['yahoo_token_data']

    # Ensure GUID is present (essential for yfpy)
    if 'guid' not in token_data:
        if 'xoauth_yahoo_guid' in token_data:
            token_data['guid'] = token_data['xoauth_yahoo_guid']
            session.modified = True
        else:
            # If no guid is found at all, we might need to fetch it, but for now, we rely on the callback.
            print("[WARNING] GUID not found in token data during validation.")

    # Refresh token if it's expired or about to expire
    expires_in = token_data.get('expires_in', 3600)
    token_time = token_data.get('token_time', 0)
    if time.time() > token_time + expires_in - 300: # 5-minute buffer
        try:
            print("Token is expiring. Attempting to refresh.")
            # Use a throwaway OAuth2 object to perform the refresh
            # It needs the original token data to know which refresh_token to use
            creds_file_for_main_app = 'private.json' if os.path.exists('private.json') else YAHOO_CREDENTIALS_FILE
            oauth_for_refresh = OAuth2(None, None, from_file=creds_file_for_main_app, **token_data)
            oauth_for_refresh.refresh_access_token()

            # The library updates its internal token_data, which we can now use
            token_data = oauth_for_refresh.token_data
            session['yahoo_token_data'] = token_data
            session.modified = True
            print("Token refreshed and session updated successfully.")
        except Exception as e:
            print(f"FAILED to refresh access token: {e}")
            session.clear() # Clear session on failure to force re-login
            return None

    return token_data

def get_authenticated_oauth_client():
    """
    Uses the centralized helper to get a valid token and returns an
    authenticated OAuth2 client object for use by the main app.
    """
    token_data = get_and_validate_token()
    if not token_data:
        return None, (jsonify({"error": "Authentication required. Please log in again."}), 401)

    # The main app uses the local private.json or the one in /tasks
    creds_file_for_main_app = 'private.json' if os.path.exists('private.json') else YAHOO_CREDENTIALS_FILE
    return OAuth2(None, None, from_file=creds_file_for_main_app, **token_data), None

# --- Static Frontend Routes ---
@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route("/home")
def serve_home():
    return send_from_directory(app.static_folder, 'home.html')

# --- API & OAuth Routes ---
@app.route("/login")
def login():
    creds_file_for_main_app = 'private.json' if os.path.exists('private.json') else YAHOO_CREDENTIALS_FILE
    if not os.path.exists(creds_file_for_main_app):
        return "OAuth credentials not configured on the server.", 500
    try:
        with open(creds_file_for_main_app) as f:
            creds = json.load(f)
        consumer_key = creds.get('consumer_key')
        redirect_uri = url_for('callback', _external=True)
        params = {
            'client_id': consumer_key, 'redirect_uri': redirect_uri,
            'response_type': 'code', 'language': 'en-us',
            'scope': 'fspt-w' # Only need fantasy sports write permissions
        }
        auth_url = f"https://api.login.yahoo.com/oauth2/request_auth?{urlencode(params)}"
        return redirect(auth_url)
    except Exception as e:
        print(f"Error during login initiation: {e}")
        return "Failed to start login process.", 500

@app.route("/callback")
def callback():
    code = request.args.get('code')
    if not code:
        return "Authorization code not found in callback.", 400
    try:
        creds_file_for_main_app = 'private.json' if os.path.exists('private.json') else YAHOO_CREDENTIALS_FILE
        redirect_uri = url_for('callback', _external=True)
        with open(creds_file_for_main_app) as f:
            creds = json.load(f)
        consumer_key, consumer_secret = creds.get('consumer_key'), creds.get('consumer_secret')

        token_url = 'https://api.login.yahoo.com/oauth2/get_token'
        payload = {
            'client_id': consumer_key, 'client_secret': consumer_secret,
            'redirect_uri': redirect_uri, 'code': code, 'grant_type': 'authorization_code'
        }
        auth = HTTPBasicAuth(consumer_key, consumer_secret)
        response = requests.post(token_url, data=payload, auth=auth)
        response.raise_for_status()
        token_data = response.json()

        if 'access_token' not in token_data:
            return "Failed to retrieve access token from Yahoo.", 500

        # Add the guid if it exists in the response
        if 'xoauth_yahoo_guid' in token_data:
            token_data['guid'] = token_data['xoauth_yahoo_guid']

        token_data['token_time'] = time.time()
        session['yahoo_token_data'] = token_data
        session.permanent = True
        print("Successfully stored token data in session.")

    except requests.exceptions.RequestException as e:
        print(f"Error during token exchange: {e.response.text if e.response else e}")
        return "Authentication failed.", 400
    except Exception as e:
        print(f"Error in callback: {e}")
        return "Authentication failed.", 500

    return redirect(url_for('serve_index'))


@app.route("/api/user")
def get_user():
    if 'yahoo_token_data' in session:
        return jsonify({"loggedIn": True})
    return jsonify({"loggedIn": False})

@app.route("/api/leagues")
def get_leagues():
    oauth, error = get_authenticated_oauth_client()
    if error: return error
    try:
        gm = yfa.Game(oauth, 'nhl')
        leagues_data = gm.league_ids(year=2025)
        leagues_list = [{'league_id': lid, 'name': gm.to_league(lid).settings()['name']} for lid in leagues_data]
        print(f"--- Final result: Returning {len(leagues_list)} league(s) to the frontend. ---")
        return jsonify(leagues_list)
    except Exception as e:
        print(f"Error fetching leagues from Yahoo API: {e}")
        # Check for specific auth error messages
        if 'token' in str(e).lower():
             session.clear()
             return jsonify({"error": "Authentication error. Please log in again.", "reauth": True}), 401
        return jsonify({"error": "Failed to fetch data from Yahoo API."}), 500

def _start_db_process(league_id):
    """Writes the token to a file and starts the background DB process."""
    token_data = get_and_validate_token()
    if not token_data:
        print("[ERROR] _start_db_process: User token not found in session.")
        return False, "User token not found in session."

    # Write the current user's token to token_cache.json in the tasks directory
    token_cache_path = os.path.join(TASKS_DIR, 'token_cache.json')
    try:
        with open(token_cache_path, 'w') as f:
            json.dump(token_data, f)
        print(f"Successfully wrote user token to {token_cache_path}")
    except Exception as e:
        print(f"[ERROR] Failed to write token cache file: {e}")
        return False, "Failed to prepare authentication for background process."

    if league_id in background_processes and background_processes[league_id].poll() is None:
        return True, "already_running"

    script_path = os.path.join('server', 'tasks', 'db_initializer.py')
    # The Popen command will execute from the project root, but the script itself
    # needs to know where its files are. We set the working directory to TASKS_DIR.
    process = subprocess.Popen(['python', script_path, str(league_id)], cwd=TASKS_DIR)
    background_processes[league_id] = process
    session['current_league_id'] = league_id
    return True, "started"

@app.route("/api/initialize_league", methods=['POST'])
def initialize_league():
    league_id = request.json.get('league_id')
    if not league_id:
        return jsonify({"error": "League ID is required"}), 400

    db_filename = f"yahoo-nhl-{league_id}-custom.db"
    db_path = os.path.join(DATABASE_DIR, db_filename)

    if os.path.exists(db_path):
        session['current_league_id'] = league_id
        return jsonify({"status": "exists", "message": "Database already exists."})

    success, status = _start_db_process(league_id)
    if not success:
        return jsonify({"error": status}), 500
    if status == "already_running":
        return jsonify({"status": "initializing", "message": "Database initialization is already in progress."})

    return jsonify({"status": "initializing", "message": "Initializing league database, this may take a few minutes."})


@app.route("/api/league_status/<league_id>")
def league_status(league_id):
    db_filename = f"yahoo-nhl-{league_id}-custom.db"
    db_path = os.path.join(DATABASE_DIR, db_filename)
    process = background_processes.get(league_id)

    if os.path.exists(db_path):
        # If the file exists, the process is done. Clean it up if it's still tracked.
        if league_id in background_processes:
             if process.poll() is not None:
                  del background_processes[league_id]
        timestamp = os.path.getmtime(db_path)
        return jsonify({"status": "complete", "timestamp": timestamp})

    if process and process.poll() is None:
        return jsonify({"status": "initializing"})
    elif process and process.poll() is not None:
        # The process finished but the file doesn't exist = error
        del background_processes[league_id]
        return jsonify({"status": "error", "message": "Database initialization failed."})

    # No process and no file
    return jsonify({"status": "not_found"})

@app.route("/api/get_league_timestamp")
def get_league_timestamp():
    league_id = session.get('current_league_id')
    if not league_id: return jsonify({"error": "No league selected"}), 400
    db_path = os.path.join(DATABASE_DIR, f"yahoo-nhl-{league_id}-custom.db")
    if os.path.exists(db_path):
        return jsonify({"timestamp": os.path.getmtime(db_path)})
    return jsonify({"error": "Database not found"}), 404

@app.route("/api/get_current_league_id")
def get_current_league_id():
    league_id = session.get('current_league_id')
    if league_id: return jsonify({"league_id": league_id})
    return jsonify({"error": "No league selected in session"}), 400

@app.route("/api/refresh_league", methods=['POST'])
def refresh_league():
    league_id = session.get('current_league_id')
    if not league_id: return jsonify({"error": "No league selected in session"}), 400
    success, status = _start_db_process(league_id)
    if not success: return jsonify({"error": status}), 500
    if status == "already_running":
        return jsonify({"status": "refreshing", "message": "A refresh is already in progress."})
    return jsonify({"status": "refreshing", "message": "Refreshing league database, this may take a few minutes."})

@app.route("/api/matchups")
def get_matchups():
    league_id = session.get('current_league_id')
    if not league_id: return jsonify({"error": "No league selected"}), 400
    db_path = os.path.join(DATABASE_DIR, f"yahoo-nhl-{league_id}-custom.db")
    if not os.path.exists(db_path): return jsonify({"error": "Database not found"}), 404
    try:
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT week, team1, team2 FROM matchups").fetchall()
        con.close()
        return jsonify([dict(row) for row in rows])
    except Exception as e:
        print(f"Error fetching matchups from database: {e}")
        return jsonify({"error": "Failed to fetch matchups."}), 500

@app.route("/api/download_db")
def download_db():
    if os.environ.get("FLASK_ENV") != "development":
        return jsonify({"error": "Feature only available in development."}), 403
    league_id = session.get('current_league_id')
    if not league_id: return jsonify({"error": "No league selected"}), 400
    db_path = os.path.join(DATABASE_DIR, f"yahoo-nhl-{league_id}-custom.db")
    if not os.path.exists(db_path): return jsonify({"error": "Database not found"}), 404
    return send_from_directory(DATABASE_DIR, f"yahoo-nhl-{league_id}-custom.db", as_attachment=True)

@app.route("/api/db")
def get_db_data():
    if os.environ.get("FLASK_ENV") != "development":
        return jsonify({"error": "Feature only available in development."}), 403
    league_id = session.get('current_league_id')
    if not league_id: return jsonify({"error": "No league selected"}), 400
    db_path = os.path.join(DATABASE_DIR, f"yahoo-nhl-{league_id}-custom.db")
    if not os.path.exists(db_path): return jsonify({"error": "Database not found"}), 404
    try:
        con = sqlite3.connect(db_path)
        cursor = con.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        db_data = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            headers = [d[1] for d in cursor.fetchall()]
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            db_data[table] = [headers] + rows
        con.close()
        return jsonify(db_data)
    except Exception as e:
        print(f"Error fetching db data: {e}")
        return jsonify({"error": "Failed to fetch data from the database."}), 500

@app.route("/logout")
def logout():
    session.clear()
    return jsonify({"message": "Successfully logged out."})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
