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
# Ensure the directory exists, especially for local/staging runs
if not os.path.exists(DATABASE_DIR):
    os.makedirs(DATABASE_DIR)

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
# The 'yahoo-oauth' library requires a file to read credentials from.
YAHOO_CREDENTIALS_FILE = 'private.json'
private_content = os.environ.get('YAHOO_PRIVATE_JSON')
if private_content:
    print("YAHOO_PRIVATE_JSON environment variable found. Writing to file.")
    with open(YAHOO_CREDENTIALS_FILE, 'w') as f:
        f.write(private_content)
else:
    print("YAHOO_PRIVATE_JSON not found. Assuming local private.json file exists for development.")


# --- Centralized Authentication Helper ---

def get_and_validate_token():
    """
    Single source of truth for getting a valid token.
    Retrieves from session, validates guid, and refreshes if needed.
    Returns a complete, valid token dictionary, or None.
    """
    if 'yahoo_token_data' not in session:
        print("[DEBUG] get_and_validate_token: No token data found in session.")
        return None

    token_data = session['yahoo_token_data']

    # This logic remains as a fallback, but the main fix is in /callback
    guid_added = False
    if 'guid' not in token_data and 'xoauth_yahoo_guid' in token_data:
        token_data['guid'] = token_data['xoauth_yahoo_guid']
        guid_added = True

    # Check for expiration and refresh if needed.
    expires_in = token_data.get('expires_in', 3600)
    token_time = token_data.get('token_time', 0)
    refreshed = False
    if time.time() > token_time + expires_in - 300:  # 5-minute buffer
        try:
            original_guid = token_data.get('guid')
            oauth_for_refresh = OAuth2(None, None, from_file=YAHOO_CREDENTIALS_FILE, **token_data)
            oauth_for_refresh.refresh_access_token()

            token_data = oauth_for_refresh.token_data
            if original_guid and 'guid' not in token_data:
                token_data['guid'] = original_guid

            refreshed = True
        except Exception as e:
            print(f"[DEBUG] FAILED to refresh access token: {e}")
            session.clear()
            return None

    if guid_added or refreshed:
        session['yahoo_token_data'] = token_data
        session.modified = True

    return session['yahoo_token_data']


def get_authenticated_oauth_client():
    """
    Uses the centralized helper to get a valid token and returns an
    authenticated OAuth2 client object.
    """
    token_data = get_and_validate_token()
    if not token_data:
        return None, (jsonify({"error": "Authentication required. Please log in again."}), 401)

    return OAuth2(None, None, from_file=YAHOO_CREDENTIALS_FILE, **token_data), None

# --- Static Frontend Routes ---
@app.route("/")
def serve_index():
    """Serves the frontend's index.html file."""
    return send_from_directory(app.static_folder, 'index.html')

@app.route("/home")
def serve_home():
    """Serves the new home.html file."""
    return send_from_directory(app.static_folder, 'home.html')


# --- API & OAuth Routes ---

@app.route("/login")
def login():
    """
    Initiates the Yahoo login process.
    """
    if not os.path.exists(YAHOO_CREDENTIALS_FILE):
        return "OAuth credentials not configured on the server.", 500
    try:
        with open(YAHOO_CREDENTIALS_FILE) as f:
            creds = json.load(f)
        consumer_key = creds.get('consumer_key')
        redirect_uri = url_for('callback', _external=True)
        params = {
            'client_id': consumer_key,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'language': 'en-us',
            'scope': 'openid fspt-w'  # Request OpenID Connect and Fantasy Sports Write permissions
        }
        auth_url = f"https://api.login.yahoo.com/oauth2/request_auth?{urlencode(params)}"
        return redirect(auth_url)
    except Exception as e:
        print(f"Error during login initiation: {e}")
        return "Failed to start login process.", 500

@app.route("/callback")
def callback():
    """
    Handles the callback from Yahoo, exchanging the code for a token AND fetching the user's GUID.
    """
    code = request.args.get('code')
    if not code:
        return "Authorization code not found in callback.", 400
    try:
        # --- Step 1: Exchange authorization code for access token ---
        redirect_uri = url_for('callback', _external=True)
        with open(YAHOO_CREDENTIALS_FILE) as f:
            creds = json.load(f)
        consumer_key = creds.get('consumer_key')
        consumer_secret = creds.get('consumer_secret')
        token_url = 'https://api.login.yahoo.com/oauth2/get_token'
        payload = {
            'client_id': consumer_key, 'client_secret': consumer_secret,
            'redirect_uri': redirect_uri, 'code': code,
            'grant_type': 'authorization_code'
        }
        auth = HTTPBasicAuth(consumer_key, consumer_secret)
        response = requests.post(token_url, data=payload, auth=auth)
        response.raise_for_status()
        token_data = response.json()

        if 'access_token' not in token_data:
            return "Failed to retrieve access token from Yahoo.", 500

        # --- Step 2: Use the access token to fetch the User GUID ---
        userinfo_url = 'https://api.login.yahoo.com/openid/v1/userinfo'
        headers = {'Authorization': f'Bearer {token_data["access_token"]}'}
        userinfo_response = requests.get(userinfo_url, headers=headers)
        userinfo_response.raise_for_status()
        userinfo_data = userinfo_response.json()

        # The 'sub' field in the OIDC response is the user's unique ID (guid)
        if 'sub' in userinfo_data:
            token_data['guid'] = userinfo_data['sub']
            print(f"[SUCCESS] Fetched and added guid to token data: {userinfo_data['sub']}")
        else:
            print("[WARNING] Could not find 'sub' (guid) in userinfo response.")
            # Fallback for older API versions, just in case
            if 'xoauth_yahoo_guid' in token_data:
                 token_data['guid'] = token_data['xoauth_yahoo_guid']

        # --- Step 3: Store the complete token in the session ---
        token_data['token_time'] = time.time()
        session['yahoo_token_data'] = token_data
        session.permanent = True
        print("Successfully stored complete token data in session.")

    except requests.exceptions.RequestException as e:
        print(f"Error during token exchange/userinfo fetch: {e.response.text if e.response else e}")
        return "Authentication failed.", 400
    except Exception as e:
        print(f"Error in callback: {e}")
        return "Authentication failed.", 500

    return redirect(url_for('serve_index'))


@app.route("/api/user")
def get_user():
    """Checks if the user has a valid token in their session."""
    if 'yahoo_token_data' in session:
        return jsonify({"loggedIn": True})
    return jsonify({"loggedIn": False})

@app.route("/api/leagues")
def get_leagues():
    """ Fetches the user's fantasy leagues."""
    oauth, error = get_authenticated_oauth_client()
    if error: return error
    try:
        gm = yfa.Game(oauth, 'nhl')
        leagues_data = gm.league_ids(year=2025)
        leagues_list = []
        for league_id in leagues_data:
            try:
                lg = gm.to_league(league_id)
                settings = lg.settings()
                leagues_list.append({'league_id': settings['league_id'], 'name': settings['name']})
            except Exception as e:
                print(f"Could not fetch info for league {league_id}: {e}")
        print(f"--- Final result: Returning {len(leagues_list)} league(s) to the frontend. ---")
        return jsonify(leagues_list)
    except Exception as e:
        print(f"Error fetching leagues from Yahoo API: {e}")
        return jsonify({"error": "Failed to fetch data from Yahoo API."}), 500

def _start_db_process(league_id):
    """Helper to create auth env var and start the background DB process."""
    token_data = get_and_validate_token()
    if not token_data:
        print("[ERROR] _start_db_process: User token not found in session for background process.")
        return False, "User token not found in session."

    with open(YAHOO_CREDENTIALS_FILE, 'r') as f:
        creds = json.load(f)
    full_auth_data = {**token_data, **creds}

    print(f"[DEBUG] START_DB_PROCESS: Final auth data being sent. Keys: {list(full_auth_data.keys())}")

    auth_data_string = json.dumps(full_auth_data)

    if league_id in background_processes and background_processes[league_id].poll() is None:
        return True, "already_running"

    script_path = os.path.join('server', 'tasks', 'db_initializer.py')
    proc_env = os.environ.copy()
    proc_env['DATABASE_DIR'] = DATABASE_DIR
    proc_env['YAHOO_FULL_AUTH'] = auth_data_string

    process = subprocess.Popen(['python', script_path, str(league_id)], env=proc_env)
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
        if process and process.poll() is not None:
            del background_processes[league_id]
        timestamp = os.path.getmtime(db_path)
        return jsonify({"status": "complete", "timestamp": timestamp})

    if process and process.poll() is None:
        return jsonify({"status": "initializing"})
    elif process and process.poll() is not None:
        del background_processes[league_id]
        return jsonify({"status": "error", "message": "Database initialization failed."})

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
