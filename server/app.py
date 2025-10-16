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


# --- Helper function to get an authenticated API object ---

def get_authenticated_oauth_client():
    """
    Checks for a token in the session, refreshes it if needed,
    and returns an authenticated OAuth2 object.
    """
    token_data = session.get('yahoo_token_data')
    if not token_data:
        return None, (jsonify({"error": "User not authenticated"}), 401)

    # Manually check if the token is expired or close to expiring
    expires_in = token_data.get('expires_in', 3600)
    token_time = token_data.get('token_time', 0)

    # Refresh if less than 5 minutes remain
    if time.time() > token_time + expires_in - 300:
        print("Token expired or nearing expiration, attempting to refresh...")
        try:
            # Create the client with the expired token data to access the refresh method
            oauth = OAuth2(None, None, from_file=YAHOO_CREDENTIALS_FILE, **token_data)
            oauth.refresh_access_token()

            # The library updates its internal token_data upon refresh
            session['yahoo_token_data'] = oauth.token_data
            print("Successfully refreshed access token and updated session.")
            return oauth, None
        except Exception as e:
            print(f"Failed to refresh access token: {e}")
            session.clear()
            return None, (jsonify({"error": "Failed to refresh token, please log in again."}), 401)

    # If token is valid, just return a new client instance with it
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
    Initiates the Yahoo login process by manually constructing the authorization
    URL and redirecting the user to Yahoo's auth page.
    """
    if not os.path.exists(YAHOO_CREDENTIALS_FILE):
        return "OAuth credentials not configured on the server. Set YAHOO_PRIVATE_JSON env var.", 500

    try:
        with open(YAHOO_CREDENTIALS_FILE) as f:
            creds = json.load(f)
        consumer_key = creds.get('consumer_key')

        # Use url_for to generate the correct callback URL, respecting proxy headers
        redirect_uri = url_for('callback', _external=True)

        params = {
            'client_id': consumer_key,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'language': 'en-us'
        }
        auth_url = f"https://api.login.yahoo.com/oauth2/request_auth?{urlencode(params)}"
        return redirect(auth_url)

    except Exception as e:
        print(f"Error during login initiation: {e}")
        return "Failed to start login process. Check server logs.", 500

@app.route("/callback")
def callback():
    """
    Handles the callback from Yahoo, manually exchanging the code for a token.
    """
    code = request.args.get('code')
    if not code:
        return "Authorization code not found in callback.", 400

    try:
        redirect_uri = url_for('callback', _external=True)
        with open(YAHOO_CREDENTIALS_FILE) as f:
            creds = json.load(f)
        consumer_key = creds.get('consumer_key')
        consumer_secret = creds.get('consumer_secret')

        token_url = 'https://api.login.yahoo.com/oauth2/get_token'
        payload = {
            'client_id': consumer_key,
            'client_secret': consumer_secret,
            'redirect_uri': redirect_uri,
            'code': code,
            'grant_type': 'authorization_code'
        }
        auth = HTTPBasicAuth(consumer_key, consumer_secret)

        response = requests.post(token_url, data=payload, auth=auth)
        response.raise_for_status()
        token_data = response.json()

        if 'access_token' not in token_data:
            return "Failed to retrieve access token from Yahoo.", 500

        # Ensure the 'guid' field is present for yfpy compatibility
        if 'guid' not in token_data and 'xoauth_yahoo_guid' in token_data:
            token_data['guid'] = token_data['xoauth_yahoo_guid']

        # Store the entire token dictionary and set the session to be permanent
        token_data['token_time'] = time.time()
        session['yahoo_token_data'] = token_data
        session.permanent = True # This respects the app.permanent_session_lifetime
        print("Successfully stored token data in session.")

    except requests.exceptions.RequestException as e:
        print(f"Error during token exchange: {e.response.text if e.response else e}")
        return "Authentication failed: Could not exchange code for token.", 400
    except Exception as e:
        print(f"Error in callback: {e}")
        return "Authentication failed due to an unexpected server error.", 500

    # Redirect to the main frontend page after successful login
    return redirect(url_for('serve_index'))


@app.route("/api/user")
def get_user():
    """Checks if the user has a valid token in their session."""
    if 'yahoo_token_data' in session:
        return jsonify({"loggedIn": True})
    return jsonify({"loggedIn": False})

@app.route("/api/leagues")
def get_leagues():
    """
    Fetches the user's fantasy leagues for the 2025 season using yfa.
    """
    oauth, error = get_authenticated_oauth_client()
    if error:
        return error

    try:
        # The 'yfa.Game' object is the entry point for the yahoo_fantasy_api library
        gm = yfa.Game(oauth, 'nhl')

        # The library uses the integer year to find game keys
        leagues_data = gm.league_ids(year=2025)

        leagues_list = []
        for league_id in leagues_data:
            try:
                lg = gm.to_league(league_id)
                lg_settings = lg.settings()
                league_name = lg_settings['name']
                league_id_only = lg_settings['league_id']
                leagues_list.append({
                                    'league_id': league_id_only,
                                    'name': league_name
                                })
            except Exception as e:
                print(f"Could not fetch info for league {league_id}: {e}")
                continue # Skip leagues that fail, but continue with others

        print(f"--- Final result: Returning {len(leagues_list)} league(s) to the frontend. ---")
        return jsonify(leagues_list)

    except Exception as e:
        print(f"Error fetching leagues from Yahoo API: {e}")
        return jsonify({"error": "Failed to fetch data from Yahoo API."}), 500

@app.route("/api/initialize_league", methods=['POST'])
def initialize_league():
    league_id = request.json.get('league_id')
    if not league_id:
        return jsonify({"error": "League ID is required"}), 400

    db_filename = f"yahoo-nhl-{league_id}-custom.db"
    db_path = os.path.join(DATABASE_DIR, db_filename) # Use the configured directory

    if os.path.exists(db_path):
        session['current_league_id'] = league_id
        return jsonify({"status": "exists", "message": "Database already exists."})

    # Check if a process for this league is already running
    if league_id in background_processes and background_processes[league_id].poll() is None:
        return jsonify({"status": "initializing", "message": "Database initialization is already in progress."})

    # Write the combined credentials and token to private.json for the subprocess to use.
    try:
        creds = json.loads(private_content) if private_content else {}
        token_data = session.get('yahoo_token_data')
        if not token_data:
            return jsonify({"status": "error", "message": "User not authenticated, cannot initialize."}), 401

        # Ensure the 'guid' field is present for yfpy compatibility, just in case.
        if 'guid' not in token_data and 'xoauth_yahoo_guid' in token_data:
            token_data['guid'] = token_data['xoauth_yahoo_guid']
            session['yahoo_token_data'] = token_data # Update session as well

        # Merge them. Token data from session takes precedence.
        combined_auth = {**creds, **token_data}

        with open(YAHOO_CREDENTIALS_FILE, 'w') as f:
            json.dump(combined_auth, f)

    except Exception as e:
        print(f"Error creating combined auth file for subprocess: {e}")
        return jsonify({"status": "error", "message": "Failed to prepare authentication for background task."}), 500

    # Run the db_initializer.py script as a background process
    script_path = os.path.join('server', 'tasks', 'db_initializer.py')

    # Pass credentials AND the database directory to the subprocess environment
    proc_env = os.environ.copy()
    proc_env['DATABASE_DIR'] = DATABASE_DIR # Pass the directory to the subprocess

    process = subprocess.Popen(['python', script_path, str(league_id)], env=proc_env)
    background_processes[league_id] = process

    session['current_league_id'] = league_id

    return jsonify({"status": "initializing", "message": "Initializing league database, this may take a few minutes."})

@app.route("/api/league_status/<league_id>")
def league_status(league_id):
    db_filename = f"yahoo-nhl-{league_id}-custom.db"
    db_path = os.path.join(DATABASE_DIR, db_filename)

    process = background_processes.get(league_id)

    if os.path.exists(db_path):
        if process:
            # If the file exists and the process is done, it's complete.
            if process.poll() is not None:
                del background_processes[league_id] # Clean up
                timestamp = os.path.getmtime(db_path)
                return jsonify({"status": "complete", "timestamp": timestamp})
        else: # Process not found, but file exists.
             timestamp = os.path.getmtime(db_path)
             return jsonify({"status": "complete", "timestamp": timestamp})


    if process and process.poll() is None:
        return jsonify({"status": "initializing"})
    elif process and process.poll() is not None: # Process finished but file not found
        del background_processes[league_id] # Clean up
        return jsonify({"status": "error", "message": "Database initialization failed."})

    return jsonify({"status": "not_found"})

@app.route("/api/get_league_timestamp")
def get_league_timestamp():
    league_id = session.get('current_league_id')
    if not league_id:
        return jsonify({"error": "No league selected"}), 400

    db_filename = f"yahoo-nhl-{league_id}-custom.db"
    db_path = os.path.join(DATABASE_DIR, db_filename)

    if os.path.exists(db_path):
        timestamp = os.path.getmtime(db_path)
        return jsonify({"timestamp": timestamp})
    else:
        return jsonify({"error": "Database not found"}), 404

@app.route("/api/get_current_league_id")
def get_current_league_id():
    """Gets the currently selected league ID from the session."""
    league_id = session.get('current_league_id')
    if league_id:
        return jsonify({"league_id": league_id})
    return jsonify({"error": "No league selected in session"}), 400

@app.route("/api/refresh_league", methods=['POST'])
def refresh_league():
    """Triggers a background process to update the database for the current league."""
    league_id = session.get('current_league_id')
    if not league_id:
        return jsonify({"error": "No league selected in session"}), 400

    # Check if a process for this league is already running
    if league_id in background_processes and background_processes[league_id].poll() is None:
        return jsonify({"status": "refreshing", "message": "A refresh is already in progress."})

    # Write the combined credentials and token to private.json for the subprocess to use.
    try:
        creds = json.loads(private_content) if private_content else {}
        token_data = session.get('yahoo_token_data')
        if not token_data:
            return jsonify({"status": "error", "message": "User not authenticated, cannot refresh."}), 401

        # Ensure the 'guid' field is present for yfpy compatibility, just in case.
        if 'guid' not in token_data and 'xoauth_yahoo_guid' in token_data:
            token_data['guid'] = token_data['xoauth_yahoo_guid']
            session['yahoo_token_data'] = token_data # Update session as well

        # Merge them. Token data from session takes precedence.
        combined_auth = {**creds, **token_data}

        with open(YAHOO_CREDENTIALS_FILE, 'w') as f:
            json.dump(combined_auth, f)

    except Exception as e:
        print(f"Error creating combined auth file for subprocess: {e}")
        return jsonify({"status": "error", "message": "Failed to prepare authentication for background task."}), 500


    # Run the db_initializer.py script, which will now handle updates.
    script_path = os.path.join('server', 'tasks', 'db_initializer.py')

    # Pass credentials and DB directory to the subprocess environment
    proc_env = os.environ.copy()
    proc_env['DATABASE_DIR'] = DATABASE_DIR

    process = subprocess.Popen(['python', script_path, str(league_id)], env=proc_env)
    background_processes[league_id] = process

    return jsonify({"status": "refreshing", "message": "Refreshing league database, this may take a few minutes."})

@app.route("/api/matchups")
def get_matchups():
    """Fetches the matchups for the current league from its database."""
    league_id = session.get('current_league_id')
    if not league_id:
        return jsonify({"error": "No league selected"}), 400

    db_filename = f"yahoo-nhl-{league_id}-custom.db"
    db_path = os.path.join(DATABASE_DIR, db_filename)

    if not os.path.exists(db_path):
        return jsonify({"error": "Database not found for this league"}), 404

    try:
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row # This allows accessing columns by name
        cursor = con.cursor()
        cursor.execute("SELECT week, team1, team2 FROM matchups")
        rows = cursor.fetchall()
        con.close()

        # Convert rows to a list of dictionaries
        matchups = [dict(row) for row in rows]

        return jsonify(matchups)

    except Exception as e:
        print(f"Error fetching matchups from database: {e}")
        return jsonify({"error": "Failed to fetch matchups from the database."}), 500

@app.route("/api/download_db")
def download_db():
    """Downloads the current league's database file."""
    if os.environ.get("FLASK_ENV") != "development":
        return jsonify({"error": "This feature is only available in development mode."}), 403

    league_id = session.get('current_league_id')
    if not league_id:
        return jsonify({"error": "No league selected"}), 400

    db_filename = f"yahoo-nhl-{league_id}-custom.db"
    db_path = os.path.join(DATABASE_DIR, db_filename)

    if not os.path.exists(db_path):
        return jsonify({"error": "Database not found for this league"}), 404

    return send_from_directory(DATABASE_DIR, db_filename, as_attachment=True)


@app.route("/api/db")
def get_db_data():
    """Fetches all tables and their content from the database."""
    if os.environ.get("FLASK_ENV") != "development":
        return jsonify({"error": "This feature is only available in development mode."}), 403

    league_id = session.get('current_league_id')
    if not league_id:
        return jsonify({"error": "No league selected"}), 400

    db_filename = f"yahoo-nhl-{league_id}-custom.db"
    db_path = os.path.join(DATABASE_DIR, db_filename)

    if not os.path.exists(db_path):
        return jsonify({"error": "Database not found for this league"}), 404

    try:
        con = sqlite3.connect(db_path)
        cursor = con.cursor()

        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        db_data = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            headers = [description[1] for description in cursor.fetchall()]

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
    """Logs the user out by clearing their session."""
    session.clear()
    return jsonify({"message": "Successfully logged out."})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
