from gevent import monkey
monkey.patch_all()

"""
Main run app for Fantasystreams.app

Author: Jason Druckenmiller
Date: 10/16/2025
Updated: 10/18/2025
"""

import os
import json
import logging
import sqlite3
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from yfpy.query import YahooFantasySportsQuery
import yahoo_fantasy_api as yfa
from yahoo_oauth import OAuth2
from requests_oauthlib import OAuth2Session
import time
import re
import db_builder
import uuid

# --- Flask App Configuration ---
# Assume a 'data' directory exists for storing database files
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a-strong-dev-secret-key-for-local-testing")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Yahoo OAuth2 Settings ---
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

def get_yfpy_instance():
    """Helper function to get an authenticated yfpy instance."""
    if 'yahoo_token' not in session:
        return None

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
    try:
        yq = YahooFantasySportsQuery(
            session['league_id'],
            game_code="nhl",
            yahoo_access_token_json=auth_data
        )
        return yq
    except Exception as e:
        logging.error(f"Failed to init yfpy: {e}", exc_info=True)
        return None

def get_yfa_lg_instance():
    """Helper function to get an authenticated yfa league instance."""
    if 'yahoo_token' not in session:
        return None

    token = session['yahoo_token']
    consumer_key = session.get('consumer_key')
    consumer_secret = session.get('consumer_secret')
    league_id = session.get('league_id')

    if not all([token, consumer_key, consumer_secret, league_id]):
        logging.error("YFA instance requires token and credentials in session.")
        return None

    # yahoo_oauth library requires a file, so we create a temporary one.
    creds = {
        "consumer_key": consumer_key,
        "consumer_secret": consumer_secret,
        "access_token": token.get('access_token'),
        "refresh_token": token.get('refresh_token'),
        "token_type": token.get('token_type', 'bearer'),
        "token_time": token.get('expires_at', time.time() + token.get('expires_in', 3600)),
        "xoauth_yahoo_guid": token.get('xoauth_yahoo_guid')
    }

    temp_dir = os.path.join(DATA_DIR, 'temp_creds')
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}.json")

    try:
        with open(temp_file_path, 'w') as f:
            json.dump(creds, f)

        sc = OAuth2(None, None, from_file=temp_file_path)
        if not sc.token_is_valid():
            logging.info("YFA token expired, refreshing...")
            sc.refresh_access_token()
            with open(temp_file_path, 'r') as f:
                new_creds = json.load(f)

            session['yahoo_token']['access_token'] = new_creds.get('access_token')
            session['yahoo_token']['refresh_token'] = new_creds.get('refresh_token')
            session['yahoo_token']['expires_at'] = new_creds.get('token_time')
            session.modified = True
            logging.info("Session token updated after YFA refresh.")

        gm = yfa.Game(sc, 'nhl')
        lg = gm.to_league(f"nhl.l.{league_id}")
        return lg
    except Exception as e:
        logging.error(f"Failed to init yfa: {e}", exc_info=True)
        return None
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


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
            logging.error("YAHOO_CONSUMER_KEY or YAHOO_CONSUMER_SECRET not set.")
            return jsonify({"error": "Server is not configured correctly."}), 500
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
        return f'<h1>Error: {error_msg}</h1>', 400

    if request.args.get('state') != session.get('oauth_state'):
        return '<h1>Error: State mismatch.</h1>', 400

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
        logging.error(f"Error fetching token: {e}", exc_info=True)
        return '<h1>Error: Could not fetch access token.</h1>', 500

    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/query', methods=['POST'])
def handle_query():
    yq = get_yfpy_instance()
    if not yq:
        return jsonify({"error": "Could not connect to Yahoo API. Your session may have expired."}), 401

    query_str = request.get_json().get('query')
    if not query_str:
        return jsonify({"error": "No query provided."}), 400

    logging.info(f"Executing query: {query_str}")
    try:
        result = eval(query_str, {"yq": yq})
        dict_result = model_to_dict(result)
        json_result = json.dumps(dict_result, indent=2)
        return jsonify({"result": json_result})
    except Exception as e:
        logging.error(f"Query error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/yfa_query', methods=['POST'])
def handle_yfa_query():
    lg = get_yfa_lg_instance()
    if not lg:
        return jsonify({"error": "Could not connect to Yahoo API. Your session may have expired."}), 401

    query_str = request.get_json().get('query')
    if not query_str:
        return jsonify({"error": "No query provided."}), 400

    logging.info(f"Executing YFA query: {query_str}")
    try:
        result = eval(query_str, {"lg": lg})
        pretty_result = json.dumps(result, indent=2)
        return jsonify({"result": pretty_result})
    except Exception as e:
        logging.error(f"YFA Query error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/update_db', methods=['POST'])
def update_db_route():
    yq = get_yfpy_instance()
    lg = get_yfa_lg_instance()
    if not yq or not lg:
        return jsonify({"error": "Authentication failed. Please log in again."}), 401

    league_id = session.get('league_id')
    if not league_id:
        return jsonify({'success': False, 'error': 'League ID not found in session.'}), 400

    data = request.get_json() or {}
    capture_lineups = data.get('capture_lineups', False)

    result = db_builder.update_league_db(yq, lg, league_id, DATA_DIR, capture_lineups=capture_lineups)

    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 500

@app.route('/api/download_db')
def download_db():
    league_id = session.get('league_id')
    if not league_id:
        return jsonify({'error': 'Not logged in or session expired.'}), 401

    db_filename = None
    for filename in os.listdir(DATA_DIR):
        if filename.startswith(f"yahoo-{league_id}-") and filename.endswith(".db"):
            db_filename = filename
            break

    if not db_filename:
        return jsonify({'error': 'Database file not found. Please create it on the "League Database" page first.'}), 404

    try:
        return send_from_directory(DATA_DIR, db_filename, as_attachment=True)
    except Exception as e:
        logging.error(f"Error sending database file: {e}", exc_info=True)
        return jsonify({'error': 'An error occurred while trying to download the file.'}), 500

@app.route('/pages/<path:page_name>')
def serve_page(page_name):
    return render_template(f"pages/{page_name}")

@app.route('/api/db_status')
def db_status():
    league_id = session.get('league_id')
    if not league_id:
        return jsonify({'db_exists': False, 'error': 'Not logged in.'})

    db_path = None
    league_name = "[Unknown]"
    timestamp = None
    db_exists = False

    for filename in os.listdir(DATA_DIR):
        if filename.startswith(f"yahoo-{league_id}-") and filename.endswith(".db"):
            db_path = os.path.join(DATA_DIR, filename)
            db_exists = True
            break

    if db_exists:
        try:
            match = re.search(f"yahoo-{league_id}-(.*)\\.db", filename)
            if match:
                league_name = match.group(1)
            timestamp = os.path.getmtime(db_path)
        except Exception as e:
            logging.error(f"Could not parse DB file info: {e}")
            return jsonify({'db_exists': False, 'error': 'Could not read database file details.'})

    return jsonify({
        'db_exists': db_exists,
        'league_name': league_name,
        'timestamp': int(timestamp) if timestamp else None
    })

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    app.run(debug=True, port=5001)
