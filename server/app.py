from flask import Flask, jsonify, redirect, request, session, send_from_directory
from requests_oauthlib import OAuth2Session
import os
import json

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
    yahoo = OAuth2Session(YAHOO_CLIENT_ID, state=session.get('oauth_state'))
    token = yahoo.fetch_token(TOKEN_URL, client_secret=YAHOO_CLIENT_SECRET,
                              authorization_response=request.url)

    session['oauth_token'] = token
    # Redirect user back to the correct frontend URL's root
    return redirect(FRONTEND_URL)

@app.route("/api/user")
def get_user():
    """A sample API endpoint to check for an active session."""
    if 'oauth_token' in session:
        return jsonify({"loggedIn": True})
    else:
        return jsonify({"loggedIn": False})


@app.route("/logout")
def logout():
    """Logs the user out by clearing the session."""
    session.clear()
    return jsonify({"message": "Successfully logged out."})

# This allows the script to be run directly for local testing
if __name__ == "__main__":
    # When running locally, it will default to staging URLs
    # You can set environment variables locally to test production settings
    app.run(debug=True, port=5000)
