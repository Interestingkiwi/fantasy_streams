from flask import Flask, jsonify, redirect, request, session, send_from_directory
from requests_oauthlib import OAuth2Session
from yfpy.query import YahooFantasySportsQuery
import os
import json
import time

# Initialize the Flask application to serve static files from the 'client' directory
app = Flask(__name__, static_folder='../client', static_url_path='')

# You must set a secret key for session management
# Render will need a secure, randomly generated key.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

# --- OAuth Configuration from Environment Variables ---
YAHOO_CLIENT_ID = os.environ.get("YAHOO_CLIENT_ID")
YAHOO_CLIENT_SECRET = os.environ.get("YAHOO_CLIENT_SECRET")

# --- Environment-Specific Redirects ---
# Set an environment variable in Render to 'production' or 'staging'
if os.environ.get("FLASK_ENV") == "production":
    # Production URLs
    REDIRECT_URI = "https://fantasystreams.app/callback"
    FRONTEND_URL = "https://fantasystreams.app"
else:
    # Staging (or local development) URLs
    REDIRECT_URI = "https://fantasy-optimizer-stg.onrender.com/callback"
    FRONTEND_URL = "https://fantasy-optimizer-stg.onrender.com"


# Yahoo's OAuth endpoints
AUTHORIZATION_BASE_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"

# --- Static Frontend Route ---
@app.route("/")
def serve_index():
    """Serves the frontend's index.html file."""
    return send_from_directory(app.static_folder, 'index.html')


# --- API & OAuth Routes ---
@app.route("/login")
def login():
    """Redirects the user to Yahoo's authorization page."""
    if not YAHOO_CLIENT_ID or not YAHOO_CLIENT_SECRET:
        return "OAuth credentials not configured on the server.", 500

    yahoo = OAuth2Session(YAHOO_CLIENT_ID, redirect_uri=REDIRECT_URI)
    authorization_url, state = yahoo.authorization_url(AUTHORIZATION_BASE_URL)

    session['oauth_state'] = state
    return redirect(authorization_url)

@app.route("/callback")
def callback():
    """Handles the callback from Yahoo after authorization."""
    yahoo = OAuth2Session(YAHOO_CLIENT_ID, state=session.get('oauth_state'), redirect_uri=REDIRECT_URI)
    token = yahoo.fetch_token(TOKEN_URL, client_secret=YAHOO_CLIENT_SECRET,
                              authorization_response=request.url)

    session['oauth_token'] = token
    session['yahoo_guid'] = token.get('xoauth_yahoo_guid')

    # Redirect user back to the correct frontend URL's root
    return redirect(FRONTEND_URL)

@app.route("/api/user")
def get_user():
    """A sample API endpoint to check for an active session."""
    if 'oauth_token' in session:
        return jsonify({"loggedIn": True})
    else:
        return jsonify({"loggedIn": False})

@app.route("/api/leagues")
def get_leagues():
    """Fetches and processes the user's fantasy leagues for the 2025 season."""
    if 'oauth_token' not in session:
        return jsonify({"error": "User not authenticated"}), 401

    try:
        # Prepare the token for yfpy
        token_data = session['oauth_token'].copy()
        token_data['token_time'] = time.time()
        token_data['consumer_key'] = YAHOO_CLIENT_ID
        token_data['consumer_secret'] = YAHOO_CLIENT_SECRET
        token_data['guid'] = session.get('yahoo_guid')
        access_token_json = json.dumps(token_data)

        teams_2025 = []
        game_keys = set()
        game_key_to_code = {}

        # Iterate through known sports to find all user teams
        for sport in ['nhl']:
            yq = YahooFantasySportsQuery(
                None,  # league_id
                sport,  # game_code
                yahoo_access_token_json=access_token_json
            )

            # 1. Get all of the user's teams for the current sport
            user_games_data = yq.get_user_teams()

            if isinstance(user_games_data, list):
                # Iterate through each Game object returned by the API
                for game in user_games_data:
                    # THE FIX IS HERE: Access data using dictionary keys from the internal 'extracted_data' attribute
                    game_data = game.extracted_data
                    if game_data and 'teams' in game_data and 'team' in game_data['teams']:

                        teams_in_game = game_data['teams']['team']
                        if not isinstance(teams_in_game, list):
                            teams_in_game = [teams_in_game]

                        for team_data in teams_in_game:
                            season_value = game_data.get('season')
                            if str(season_value) == '2025':
                                print(f"SUCCESS: Matched team '{team_data.get('name')}' in season '2025'")

                                team_key_parts = team_data.get('team_key', '').split('.')
                                if len(team_key_parts) > 4:
                                    game_key = team_key_parts[0]
                                    league_id = team_key_parts[2]
                                    team_num = team_key_parts[4]

                                    teams_2025.append({
                                        "team_key": team_data.get('team_key'),
                                        "team_name": team_data.get('name'),
                                        "game_key": game_key,
                                        "league_id": league_id,
                                        "team_num": team_num
                                    })
                                    game_keys.add(game_key)
                                    game_key_to_code[game_key] = sport

        # 2. Get league names for all unique game keys found
        league_names = {}
        for game_key in game_keys:
            sport_code = game_key_to_code.get(game_key)
            if not sport_code:
                continue

            # Initialize the query with the correct sport code context
            yq_league = YahooFantasySportsQuery(
                None,
                sport_code,
                yahoo_access_token_json=access_token_json
            )
            leagues_data = yq_league.get_user_leagues_by_game_key(game_key)
            if leagues_data and hasattr(leagues_data, 'leagues'):
                for league in leagues_data.leagues:
                    league_names[league.league_id] = league.name

        # 3. Combine the data
        for team in teams_2025:
            team['league_name'] = league_names.get(team['league_id'], 'Unknown League')

        print(f"--- Final result: Returning {len(teams_2025)} team(s) to the frontend. ---")
        return jsonify(teams_2025)

    except Exception as e:
        # Log the actual error on the server for debugging
        print(f"Error fetching leagues from Yahoo API: {e}")
        return jsonify({"error": "Failed to fetch data from Yahoo API."}), 500


@app.route("/logout")
def logout():
    """Logs the out by clearing the session."""
    session.clear()
    return jsonify({"message": "Successfully logged out."})

# This allows the script to be run directly for local testing
if __name__ == "__main__":
    # When running locally, it will default to staging URLs
    # You can set environment variables locally to test production settings
    app.run(debug=True, port=5000)
