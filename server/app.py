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

# --- App Initialization ---

# Initialize the Flask application to serve static files from the 'client' directory
app = Flask(__name__, static_folder='../client', static_url_path='')

# Add ProxyFix middleware to trust headers from Render's proxy.
# This is crucial for OAuth redirects to work correctly in production.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Set a secret key for session management from environment variables
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

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

# --- Static Frontend Route ---
@app.route("/")
def serve_index():
    """Serves the frontend's index.html file."""
    return send_from_directory(app.static_folder, 'index.html')

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
#                leagues_list.append({
#                    'league_id': league_id,
#                    'name': lg.settings().get('name', 'Unknown League')
#                })
                lg_settings = lg.settings()
                print(lg_settings)
                league_name = lg_settings['name']
                league_id = lg_settings['league_id']
                print(league_name)
                print(league_id)
                leagues_list.append({
                                    'league_id': league_id,
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


@app.route("/logout")
def logout():
    """Logs the user out by clearing their session."""
    session.clear()
    return jsonify({"message": "Successfully logged out."})

# This allows the script to be run directly for local testing
if __name__ == "__main__":
    app.run(debug=True, port=5000)
