import os
import json
import logging
from flask import Flask, render_template, request, jsonify
from yfpy.query import YahooFantasySportsQuery
from yfpy.models import Model

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Flask App and yfpy Initialization ---
app = Flask(__name__)
yq = None

def init_yfpy():
    """
    Initializes the yfpy query object by reading credentials from
    environment variables and creating the necessary auth file for yfpy.
    """
    global yq
    try:
        league_id = os.environ.get("LEAGUE_ID")
        if not league_id:
            logging.error("FATAL: LEAGUE_ID environment variable not set.")
            return

        private_json_content = os.environ.get("PRIVATE_JSON_CONTENT")
        if not private_json_content:
            logging.error("FATAL: PRIVATE_JSON_CONTENT environment variable not set.")
            logging.error("Please run a yfpy script locally once to generate the private.json file, then copy its content to this environment variable on your hosting provider.")
            return

        # yfpy needs to read from a file, so we create one at runtime in an 'auth' directory.
        auth_dir = os.path.join(os.path.dirname(__file__), "auth")
        os.makedirs(auth_dir, exist_ok=True)
        private_json_path = os.path.join(auth_dir, "private.json")

        with open(private_json_path, "w") as f:
            f.write(private_json_content)

        logging.info("Successfully created auth/private.json for yfpy.")

        # Initialize the query object, pointing to the directory with the auth file.
        # This assumes you are in an NHL league ('nhl'). Change 'game_code' if necessary.
        yq = YahooFantasySportsQuery(auth_dir, league_id, game_code="nhl")
        logging.info(f"Successfully connected to Yahoo Fantasy API for league {league_id}.")

    except Exception as e:
        logging.critical(f"Failed to initialize YahooFantasySportsQuery: {e}", exc_info=True)
        yq = None # Ensure yq is None if initialization fails

def model_to_dict(obj):
    """
    Recursively converts yfpy Model objects and lists of them into dictionaries
    so they can be easily serialized to JSON.
    """
    if isinstance(obj, list):
        return [model_to_dict(i) for i in obj]
    if not isinstance(obj, Model):
        return obj

    # Convert a single yfpy Model object to a dictionary
    result = {}
    for key in dir(obj):
        # Exclude private attributes and methods
        if not key.startswith('_') and not callable(getattr(obj, key)):
            value = getattr(obj, key)
            result[key] = model_to_dict(value)
    return result

# Initialize yfpy right when the application starts
init_yfpy()

@app.route('/')
def index():
    """Renders the main web page."""
    return render_template('index.html')

@app.route('/query', methods=['POST'])
def handle_query():
    """
    Handles the API request from the frontend, executes the yfpy query,
    and returns the result as JSON.
    """
    if not yq:
        return jsonify({"error": "Yahoo API connection is not initialized. Check server logs for errors."}), 500

    data = request.get_json()
    query_str = data.get('query')

    if not query_str:
        return jsonify({"error": "No query was provided."}), 400

    logging.info(f"Executing query: {query_str}")

    try:
        # WARNING: Using eval() with user input is a security risk.
        # This tool is intended for personal use where the user is trusted.
        # The scope is limited to just the 'yq' object for a small layer of safety.
        result = eval(query_str, {"yq": yq})

        # Convert the result (which could be yfpy model objects) to a dictionary
        dict_result = model_to_dict(result)

        # Convert the dictionary to a nicely formatted JSON string
        json_result = json.dumps(dict_result, indent=2)

        return jsonify({"result": json_result})

    except Exception as e:
        logging.error(f"Error executing query '{query_str}': {e}", exc_info=True)
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    # This block is for local development.
    # To run locally:
    # 1. Set the LEAGUE_ID and PRIVATE_JSON_CONTENT environment variables.
    # 2. Run `python app.py`
    app.run(debug=True, port=5001)
