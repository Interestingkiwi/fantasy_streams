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
    Recursively converts yfpy model objects, lists, and bytes into a structure
    that can be easily serialized to JSON.
    """
    if isinstance(obj, list):
        return [model_to_dict(i) for i in obj]

    if isinstance(obj, bytes):
        # Decode using utf-8, ignoring any errors.
        return obj.decode('utf-8', 'ignore')

    # Check if it's a yfpy model object that needs to be converted to a dict.
    if not hasattr(obj, '__module__') or not obj.__module__.startswith('yfpy.'):
         return obj # Return primitive types as is.

    result = {}
    for key in dir(obj):
        if not key.startswith('_') and not callable(getattr(obj, key)):
            value = getattr(obj, key)
            result[key] = model_to_dict(value)
    return result

@app.route('/')
def index():
    """
    Renders the login page if the user is not authenticated, otherwise
    redirects them to the main home page.
    """
    if 'yahoo_token' in session:
        return redirect(url_for('home'))
    return render_template('index.html')

@app.route('/home')
def home():
    """ Renders the main application page if authenticated, otherwise redirects to login. """
    if 'yahoo_token' not in session:
        return redirect(url_for('index'))
    return render_template('home.html')

@app.route('/login', methods=['POST'])
def login():
    """
    Starts the OAuth2 login process. It generates Yahoo's authorization URL
    and sends it to the frontend to redirect the user.
    """
    data = request.get_json()
    session['league_id'] = data.get('league_id')

    # Get credentials from environment variables instead of user input
    session['consumer_key'] = os.environ.get("YAHOO_CONSUMER_KEY")
    session['consumer_secret'] = os.environ.get("YAHOO_CONSUMER_SECRET")

    if not all([session['league_id'], session['consumer_key'], session['consumer_secret']]):
        # Provide a more specific error if the env vars are missing
        if not session['consumer_key'] or not session['consumer_secret']:
            logging.error("YAHOO_CONSUMER_KEY or YAHOO_CONSUMER_SECRET environment variables not set on the server.")
            return jsonify({"error": "Server is not configured correctly. Missing API credentials."}), 500
        return jsonify({"error": "League ID is required."}), 400

    # The Redirect URI must match exactly what you've configured in your Yahoo App settings.
    # We construct it dynamically to work in both local dev and on Render.
    redirect_uri = url_for('callback', _external=True, _scheme='https')

    yahoo = OAuth2Session(session['consumer_key'], redirect_uri=redirect_uri)
    authorization_url, state = yahoo.authorization_url(authorization_base_url)

    session['oauth_state'] = state
    return jsonify({'auth_url': authorization_url})

@app.route('/callback')
def callback():
    """
    This is the endpoint Yahoo redirects the user to after they authorize the app.
    It exchanges the authorization code from Yahoo for a permanent access token.
    """
    if 'error' in request.args:
        error_msg = request.args.get('error_description', 'An unknown error occurred during Yahoo authentication.')
        logging.error(f"Yahoo OAuth Error: {request.args.get('error')} - {error_msg}")
        return f'<h1>Error: {error_msg}</h1><p>Please try logging in again.</p>', 400

    if request.args.get('state') != session.get('oauth_state'):
        return '<h1>Error: State mismatch. Please try logging in again.</h1>', 400

    redirect_uri = url_for('callback', _external=True, _scheme='https')
    yahoo = OAuth2Session(session['consumer_key'], state=session.get('oauth_state'), redirect_uri=redirect_uri)

    try:
        # The 'code' is the authorization code from Yahoo
        token = yahoo.fetch_token(
            token_url,
            client_secret=session['consumer_secret'],
            code=request.args.get('code')
        )
        session['yahoo_token'] = token
    except Exception as e:
        logging.error(f"Error fetching token in callback: {e}", exc_info=True)
        return '<h1>Error: Could not fetch access token from Yahoo. Please try again.</h1>', 500

    return redirect(url_for('home'))

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
