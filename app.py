import os
import json
import logging
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from yfpy.query import YahooFantasySportsQuery
from requests_oauthlib import OAuth2Session
import time

# --- Flask App Configuration ---
app = Flask(__name__)
# A secret key is required for Flask to securely manage user sessions.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a-strong-dev-secret-key-for-local-testing")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Yahoo OAuth2 Settings ---
# These are the standard URLs for Yahoo's OAuth2 implementation
authorization_base_url = 'https://api.login.yahoo.com/oauth2/request_auth'
token_url = 'https://api.login.yahoo.com/oauth2/get_token'

def model_to_dict(obj):
    """
    Recursively converts yfpy model objects and lists of them into dictionaries
    so they can be easily serialized to JSON.
    """
    if isinstance(obj, list):
        return [model_to_dict(i) for i in obj]

    if not hasattr(obj, '__module__') or not obj.__module__.startswith('yfpy.'):
         return obj

    result = {}
    for key in dir(obj):
        if not key.startswith('_') and not callable(getattr(obj, key)):
            value = getattr(obj, key)
            result[key] = model_to_dict(value)
    return result

@app.route('/')
def index():
    """
    Renders the main page, showing either the login form or the query terminal
    based on whether the user is authenticated.
    """
    is_authenticated = 'yahoo_token' in session
    return render_template('index.html', is_authenticated=is_authenticated)

@app.route('/login', methods=['POST'])
def login():
    """
    Starts the manual OAuth2 login process. It generates Yahoo's authorization URL
    and sends it back to the frontend for the user to visit manually.
    """
    data = request.get_json()
    session['league_id'] = data.get('league_id')
    session['consumer_key'] = data.get('consumer_key')
    session['consumer_secret'] = data.get('consumer_secret')

    if not all([session['league_id'], session['consumer_key'], session['consumer_secret']]):
        return jsonify({"error": "League ID, Consumer Key, and Consumer Secret are all required."}), 400

    redirect_uri = url_for('callback', _external=True, _scheme='https')

    yahoo = OAuth2Session(session['consumer_key'], redirect_uri=redirect_uri)
    authorization_url, state = yahoo.authorization_url(authorization_base_url)

    session['oauth_state'] = state
    return jsonify({'auth_url': authorization_url})

@app.route('/callback')
def callback():
    """
    This is a simple page that the user is redirected to by Yahoo.
    Its only purpose is to contain the verifier code in its URL.
    The user will copy the URL of this page and paste it back into the app.
    """
    return "<h1>Verification successful!</h1><p>Please copy the full URL from your browser's address bar and paste it back into the yfpy Web Terminal.</p>"

@app.route('/verify', methods=['POST'])
def verify():
    """
    Receives the full redirect URL (containing the verifier code) from the user,
    and exchanges it for a permanent access token.
    """
    redirected_url = request.get_json().get('redirected_url')
    if not redirected_url:
        return jsonify({"error": "The redirected URL from Yahoo is required."}), 400

    # Recreate the session object to ensure state and redirect URI match
    redirect_uri = url_for('callback', _external=True, _scheme='https')
    yahoo = OAuth2Session(session['consumer_key'], state=session.get('oauth_state'), redirect_uri=redirect_uri)

    try:
        token = yahoo.fetch_token(
            token_url,
            client_secret=session['consumer_secret'],
            authorization_response=redirected_url
        )
        session['yahoo_token'] = token
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Error fetching token with verifier URL: {e}", exc_info=True)
        return jsonify({"error": "Could not verify the URL. It might be invalid, expired, or used already. Please try generating a new auth URL."}), 500


@app.route('/logout')
def logout():
    """ Clears the session to log the user out. """
    session.clear()
    return redirect('/')

@app.route('/query', methods=['POST'])
def handle_query():
    """
    Executes a yfpy query using the credentials stored in the user's session.
    """
    if 'yahoo_token' not in session:
        return jsonify({"error": "User not authenticated. Please log in again."}), 401

    try:
        # Manually construct the auth dictionary in the exact format yfpy expects,
        # translating from the standard OAuth2 session token.
        token = session['yahoo_token']
        auth_data = {
            'consumer_key': session['consumer_key'],
            'consumer_secret': session['consumer_secret'],
            'access_token': token.get('access_token'),
            'refresh_token': token.get('refresh_token'),
            'token_type': token.get('token_type', 'bearer'),
            'token_time': token.get('expires_at', time.time() + token.get('expires_in', 3600)),
            'guid': token.get('xoauth_yahoo_guid')
        }

        yq = YahooFantasySportsQuery(
            int(session['league_id']),
            game_code="nhl",
            yahoo_access_token_json=auth_data
        )
    except Exception as e:
        logging.error(f"Failed to re-initialize yfpy from session: {e}", exc_info=True)
        return jsonify({"error": "Could not connect to Yahoo API. Your session may have expired. Please log out and log in again."}), 500

    query_str = request.get_json().get('query')
    if not query_str:
        return jsonify({"error": "No query was provided."}), 400

    logging.info(f"Executing query: {query_str}")
    try:
        result = eval(query_str, {"yq": yq})
        dict_result = model_to_dict(result)
        json_result = json.dumps(dict_result, indent=2)
        return jsonify({"result": json_result})
    except SystemExit:
        # Catch the SystemExit from yfpy and return a user-friendly error
        logging.error("yfpy triggered a SystemExit, likely due to an auth issue.")
        return jsonify({"error": "Authentication failed with yfpy. Your session may be invalid. Please log out and log in again."}), 401
    except Exception as e:
        logging.error(f"Error executing query '{query_str}': {e}", exc_info=True)
        if 'token_expired' in str(e).lower():
             return jsonify({"error": f"Your session has expired. Please log out and log in again."}), 401
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    # Make sure to set FLASK_SECRET_KEY in your environment for local testing
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' # Allows http for local dev
    app.run(debug=True, port=5001)
