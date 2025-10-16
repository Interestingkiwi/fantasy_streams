import os
import json
import logging
from flask import Flask, render_template, request, jsonify, session, redirect
from yfpy.query import YahooFantasySportsQuery
from yahoo_oauth.oauth import OAuth2

# --- Flask App Configuration ---
app = Flask(__name__)
# A secret key is required for Flask to securely manage user sessions.
# On Render, set this as an environment variable for security.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a-strong-dev-secret-key")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# This global object will temporarily store the OAuth handler between auth steps.
# In a multi-user app, this would be handled differently, but it's fine for a personal tool.
oauth_handler = None

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
    Renders the main page. It will show the login form or the query terminal
    based on whether the user is authenticated in their session.
    """
    is_authenticated = 'yahoo_token' in session
    return render_template('index.html', is_authenticated=is_authenticated)

@app.route('/login', methods=['POST'])
def login():
    """
    Step 1 of Auth: Takes credentials from the user, generates an auth URL for Yahoo,
    and returns it to the frontend.
    """
    global oauth_handler
    data = request.get_json()
    session['league_id'] = data.get('league_id')
    session['consumer_key'] = data.get('consumer_key')
    session['consumer_secret'] = data.get('consumer_secret')

    if not all([session['league_id'], session['consumer_key'], session['consumer_secret']]):
        return jsonify({"error": "League ID, Consumer Key, and Consumer Secret are all required."}), 400

    try:
        # We set store_file=False because we don't want to save private.json on the server.
        # We will manage the token within the user's session instead.
        oauth_handler = OAuth2(session['consumer_key'], session['consumer_secret'], store_file=False)
        auth_url = oauth_handler.get_authorization_url()
        return jsonify({"auth_url": auth_url})
    except Exception as e:
        logging.error(f"Error during auth URL generation: {e}", exc_info=True)
        return jsonify({"error": "Failed to generate authentication URL. Please check your Consumer Key/Secret."}), 500

@app.route('/verify', methods=['POST'])
def verify():
    """
    Step 2 of Auth: Takes the verifier code from the user, fetches the access token from Yahoo,
    and stores the token securely in the user's session.
    """
    global oauth_handler
    data = request.get_json()
    verifier = data.get('verifier')

    if not oauth_handler:
         return jsonify({"error": "Authentication process not started. Please login first."}), 400
    if not verifier:
        return jsonify({"error": "Verifier code is required."}), 400

    try:
        token_json = oauth_handler.get_access_token(verifier)
        session['yahoo_token'] = token_json
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Error getting access token: {e}", exc_info=True)
        return jsonify({"error": "Failed to get access token. The verifier code may have been incorrect or expired."}), 500

@app.route('/logout')
def logout():
    """ Clears the session to log the user out and redirects to the main page. """
    session.clear()
    return redirect('/')

@app.route('/query', methods=['POST'])
def handle_query():
    """
    Handles API requests from the terminal. It re-initializes the yfpy query object
    using credentials from the session for each request.
    """
    # Check if user is authenticated
    if 'yahoo_token' not in session:
        return jsonify({"error": "User not authenticated. Please log in again."}), 401

    # Re-create the query object on-the-fly using session credentials
    try:
        yq = YahooFantasySportsQuery(
            int(session['league_id']),
            game_code="nhl",
            yahoo_consumer_key=session['consumer_key'],
            yahoo_consumer_secret=session['consumer_secret'],
            yahoo_access_token_json=session['yahoo_token']
        )
    except Exception as e:
        logging.error(f"Failed to re-initialize yfpy from session: {e}", exc_info=True)
        return jsonify({"error": "Could not connect to Yahoo API using stored credentials. You may need to log out and log in again."}), 500

    data = request.get_json()
    query_str = data.get('query')

    if not query_str:
        return jsonify({"error": "No query was provided."}), 400

    logging.info(f"Executing query: {query_str}")

    try:
        result = eval(query_str, {"yq": yq})
        dict_result = model_to_dict(result)
        json_result = json.dumps(dict_result, indent=2)
        return jsonify({"result": json_result})
    except Exception as e:
        logging.error(f"Error executing query '{query_str}': {e}", exc_info=True)
        # Check if token may have expired.
        if 'token_expired' in str(e).lower():
             return jsonify({"error": f"Your session has expired. Please log out and log in again."}), 401
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
