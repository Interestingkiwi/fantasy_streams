import os
import json
import logging
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
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
        return obj.decode('utf-8', 'ignore')

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
    if 'yahoo_token' in session:
        return redirect(url_for('home'))
    return render_template('index.html')

@app.route('/home')
def home():
    if 'yahoo_token' not in session:
        return redirect(url_for('index'))
    return render_template('home.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    session['league_id'] = data.get('league_id')
    session['consumer_key'] = os.environ.get("YAHOO_CONSUMER_KEY")
    session['consumer_secret'] = os.environ.get("YAHOO_CONSUMER_SECRET")

    if not all([session['league_id'], session['consumer_key'], session['consumer_secret']]):
        if not session['consumer_key'] or not session['consumer_secret']:
            logging.error("YAHOO_CONSUMER_KEY or YAHOO_CONSUMER_SECRET environment variables not set on the server.")
            return jsonify({"error": "Server is not configured correctly. Missing API credentials."}), 500
        return jsonify({"error": "League ID is required."}), 400

    redirect_uri = url_for('callback', _external=True, _scheme='https')
    yahoo = OAuth2Session(session['consumer_key'], redirect_uri=redirect_uri)
    authorization_url, state = yahoo.authorization_url(authorization_base_url)
    session['oauth_state'] = state
    return jsonify({'auth_url': authorization_url})

@app.route('/callback')
def callback():
    if 'error' in request.args:
        error_msg = request.args.get('error_description', 'An unknown error occurred.')
        logging.error(f"Yahoo OAuth Error: {request.args.get('error')} - {error_msg}")
        return f'<h1>Error: {error_msg}</h1><p>Please try logging in again.</p>', 400

    if request.args.get('state') != session.get('oauth_state'):
        return '<h1>Error: State mismatch. Please try logging in again.</h1>', 400

    redirect_uri = url_for('callback', _external=True, _scheme='https')
    yahoo = OAuth2Session(session['consumer_key'], state=session.get('oauth_state'), redirect_uri=redirect_uri)

    try:
        token = yahoo.fetch_token(
            token_url,
            client_secret=session['consumer_secret'],
            code=request.args.get('code')
        )
        session['yahoo_token'] = token
    except Exception as e:
        logging.error(f"Error fetching token in callback: {e}", exc_info=True)
        return '<h1>Error: Could not fetch access token from Yahoo.</h1>', 500

    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/query', methods=['POST'])
def handle_query():
    if 'yahoo_token' not in session:
        return jsonify({"error": "User not authenticated. Please log in again."}), 401

    try:
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
        return jsonify({"error": "Could not connect to Yahoo API. Your session may have expired."}), 500

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
        logging.error("yfpy triggered a SystemExit, likely due to an auth issue.")
        return jsonify({"error": "Authentication failed with yfpy. Your session may be invalid."}), 401
    except Exception as e:
        logging.error(f"Error executing query '{query_str}': {e}", exc_info=True)
        if 'token_expired' in str(e).lower():
             return jsonify({"error": f"Your session has expired. Please log out and log in again."}), 401
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

@app.route('/pages/<path:page_name>')
def serve_page(page_name):
    """Renders a page from the templates/pages directory."""
    try:
        return render_template(f"pages/{page_name}")
    except Exception:
        return "Page not found", 404

# --- Placeholder API Routes to prevent 404 errors ---
@app.route('/api/get_league_timestamp')
def get_league_timestamp():
    return jsonify({'timestamp': int(time.time())})

@app.route('/api/matchups')
def get_matchups():
    # Return some sample data
    return jsonify([
        {'week': 1, 'team1': 'Team A', 'team2': 'Team B'},
        {'week': 1, 'team1': 'Team C', 'team2': 'Team D'},
        {'week': 2, 'team1': 'Team A', 'team2': 'Team C'},
    ])

@app.route('/api/db')
def get_db_content():
    return jsonify({'error': 'Database inspection is not implemented yet.'})

@app.route('/api/download_db')
def download_db():
     return jsonify({'error': 'Database download is not implemented yet.'})


if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    app.run(debug=True, port=5001)
