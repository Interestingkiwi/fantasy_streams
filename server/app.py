import os
import json
import sqlite3
import threading
from flask import Flask, redirect, request, session, url_for, jsonify, send_from_directory, send_file
from yfpy.query import YahooFantasySportsQuery
from yfpy.models import League
from datetime import date
import logging
import unicodedata
import re
from datetime import datetime, timedelta

# --- Configuration ---
YAHOO_CONSUMER_KEY = os.environ.get("YAHOO_CONSUMER_KEY", "YOUR_YAHOO_CONSUMER_KEY")
YAHOO_CONSUMER_SECRET = os.environ.get("YAHOO_CONSUMER_SECRET", "YOUR_YAHOO_CONSUMER_SECRET")

# --- App Initialization ---
# The static_folder is now relative to the server directory
app = Flask(__name__, static_folder='../client')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_super_secret_key_for_dev")
logging.basicConfig(level=logging.INFO)

league_initialization_status = {}

# --- Database Fetcher Class (Adapted from your queries.py) ---
class YahooDataFetcher:
    """
    Handles fetching data from Yahoo Fantasy API and populating a SQLite database.
    """
    def __init__(self, con, league_id, auth_dir='.'):
        self.con = con
        self.league_id = league_id
        # Use the root project directory for authentication credentials
        self.auth_dir = auth_dir
        self.yq = YahooFantasySportsQuery(self.auth_dir, league_id)
        self.num_teams = 0
        self.start_date = None
        self.end_date = None
        self.league_key = None
        self.playoff_start_week = None

    def fetch_all_data(self):
        """
        Fetches all necessary league data and stores it in the database.
        This is a long-running task.
        """
        try:
            logging.info(f"[{self.league_id}] Starting full data fetch.")
            self._fetch_and_store_league_metadata()
            self._fetch_and_store_teams()
            self._fetch_player_id()
            self._fetch_league_scoring_settings()
            self._fetch_and_store_fantasy_weeks()
            self._fetch_league_matchups()
            self._fetch_current_rosters()
            logging.info(f"[{self.league_id}] Full data fetch completed successfully.")
            return "complete"
        except Exception as e:
            logging.error(f"[{self.league_id}] Error during data fetch: {e}", exc_info=True)
            return "error"

    def _execute_and_commit(self, sql, params=(), many=False):
        try:
            cursor = self.con.cursor()
            if many:
                cursor.executemany(sql, params)
            else:
                cursor.execute(sql, params)
            self.con.commit()
        except Exception as e:
            logging.error(f"[{self.league_id}] Database error on query '{sql[:50]}...': {e}")
            self.con.rollback()
            raise

    def _fetch_and_store_league_metadata(self):
        logging.info(f"[{self.league_id}] Fetching league metadata...")
        meta = self.yq.get_league_metadata()
        self.num_teams = meta.num_teams
        self.start_date = meta.start_date
        self.end_date = meta.end_date
        self.league_key = meta.league_key
        sql = "INSERT OR IGNORE INTO league (league_id, name, num_teams, start_date, end_date) VALUES (?, ?, ?, ?, ?)"
        self._execute_and_commit(sql, (self.league_id, meta.name, self.num_teams, self.start_date, self.end_date))
        logging.info(f"[{self.league_id}] Stored metadata for league: {meta.name}")

    def _fetch_and_store_teams(self):
        logging.info(f"[{self.league_id}] Fetching teams...")
        teams = self.yq.get_league_teams()
        teams_to_insert = []
        for team in teams:
            manager_name = team.managers[0].nickname if team.managers else "N/A"
            teams_to_insert.append((team.team_id, team.name, manager_name))
        sql = "INSERT OR IGNORE INTO teams (team_id, name, manager_nickname) VALUES (?, ?, ?)"
        self._execute_and_commit(sql, teams_to_insert, many=True)
        logging.info(f"[{self.league_id}] Stored {len(teams_to_insert)} teams.")

    def _fetch_player_id(self):
        logging.info(f"[{self.league_id}] Fetching all league players...")
        players = self.yq.get_league_players()
        players_to_insert = []
        TEAM_TRICODE_MAP = {"TB": "TBL", "NJ": "NJD", "SJ": "SJS", "LA": "LAK", "MON": "MTL", "WAS": "WSH"}
        for player in players:
            player_name = player.name.full
            nfkd_form = unicodedata.normalize('NFKD', player_name.lower())
            ascii_name = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
            player_name_normalized = re.sub(r'[^a-z0-9]', '', ascii_name)
            player_team_abbr = player.editorial_team_abbr.upper()
            player_team = TEAM_TRICODE_MAP.get(player_team_abbr, player_team_abbr)
            players_to_insert.append((player.player_id, player_name, player_team, player_name_normalized))
        sql = "INSERT OR IGNORE INTO players (player_id, player_name, player_team, player_name_normalized) VALUES (?, ?, ?, ?)"
        self._execute_and_commit(sql, players_to_insert, many=True)
        logging.info(f"[{self.league_id}] Stored {len(players_to_insert)} players.")

    def _fetch_league_scoring_settings(self):
        logging.info(f"[{self.league_id}] Fetching scoring settings...")
        settings = self.yq.get_league_settings()
        self.playoff_start_week = settings.playoff_start_week
        scoring_to_insert = []
        for stat_item in settings.stat_categories:
            scoring_to_insert.append((stat_item.stat_id, stat_item.display_name, stat_item.group))
        sql = "INSERT OR IGNORE INTO scoring (stat_id, category, scoring_group) VALUES (?, ?, ?)"
        self._execute_and_commit(sql, scoring_to_insert, many=True)
        logging.info(f"[{self.league_id}] Stored {len(scoring_to_insert)} scoring categories.")

    def _fetch_and_store_fantasy_weeks(self):
        logging.info(f"[{self.league_id}] Fetching fantasy weeks...")
        game_id = self.league_key.split('.')[1]
        weeks = self.yq.get_game_weeks_by_game_id(game_id)
        weeks_to_insert = []
        for week in weeks:
            weeks_to_insert.append((week.week_num, week.start_date, week.end_date))
        sql = "INSERT OR IGNORE INTO weeks (week_num, start_date, end_date) VALUES (?, ?, ?)"
        self._execute_and_commit(sql, weeks_to_insert, many=True)
        logging.info(f"[{self.league_id}] Stored {len(weeks_to_insert)} weeks.")

    def _fetch_league_matchups(self):
        if not self.playoff_start_week:
            logging.warning(f"[{self.league_id}] Playoff start week not set. Cannot fetch matchups.")
            return
        logging.info(f"[{self.league_id}] Fetching matchups...")
        matchups_to_insert = []
        for week_num in range(1, self.playoff_start_week):
            matchups = self.yq.get_league_matchups_by_week(week_num)
            for matchup in matchups:
                if len(matchup.teams) == 2:
                    team1_name = matchup.teams[0].name
                    team2_name = matchup.teams[1].name
                    matchups_to_insert.append((week_num, team1_name, team2_name))
        sql = "INSERT OR IGNORE INTO matchups (week, team1, team2) VALUES (?, ?, ?)"
        self._execute_and_commit(sql, matchups_to_insert, many=True)
        logging.info(f"[{self.league_id}] Stored {len(matchups_to_insert)} matchups.")

    def _fetch_current_rosters(self):
        logging.info(f"[{self.league_id}] Fetching current rosters...")
        self._execute_and_commit("DELETE FROM rosters")
        rosters_to_insert = []
        MAX_PLAYERS = 19
        today_str = date.today().isoformat()
        for team_id in range(1, self.num_teams + 1):
            players = self.yq.get_team_roster_by_date(team_id, today_str)
            player_ids = [p.player_id for p in players][:MAX_PLAYERS]
            padded_ids = player_ids + ([None] * (MAX_PLAYERS - len(player_ids)))
            rosters_to_insert.append([team_id] + padded_ids)
        sql = "INSERT INTO rosters (team_id, p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12, p13, p14, p15, p16, p17, p18, p19) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        self._execute_and_commit(sql, rosters_to_insert, many=True)
        logging.info(f"[{self.league_id}] Stored rosters for {len(rosters_to_insert)} teams.")


# --- Helper Functions ---
def get_db_path(league_id):
    """Constructs the path for a league's database in the root directory."""
    return f"yahoo-nhl-{league_id}-custom.db"

def get_db_connection(league_id):
    """Returns a connection to the specified league's database."""
    db_path = get_db_path(league_id)
    return sqlite3.connect(db_path, check_same_thread=False)

def create_database(league_id):
    """Creates a new SQLite database for a league using the schema."""
    db_path = get_db_path(league_id)
    if os.path.exists(db_path):
        logging.info(f"Database for league {league_id} already exists.")
        return
    logging.info(f"Creating new database for league {league_id}...")
    try:
        # Path to schema is now inside the server/tasks folder
        with open("server/tasks/schema.sql", "r") as f:
            schema = f.read()
        con = sqlite3.connect(db_path)
        con.executescript(schema)
        con.commit()
        con.close()
        logging.info(f"Database created successfully: {db_path}")
    except Exception as e:
        logging.error(f"Failed to create database for league {league_id}: {e}")

def initialize_league_data_background(league_id, auth_dir):
    """
    Background task to create and populate the database for a league.
    Updates the global status dictionary.
    """
    global league_initialization_status
    try:
        create_database(league_id)
        con = get_db_connection(league_id)
        fetcher = YahooDataFetcher(con, league_id, auth_dir=auth_dir)
        status = fetcher.fetch_all_data()
        league_initialization_status[league_id] = {'status': status}
        con.close()
    except Exception as e:
        logging.error(f"Background initialization for league {league_id} failed: {e}")
        league_initialization_status[league_id] = {'status': 'error', 'message': str(e)}

# --- Authentication Routes ---
@app.route('/login')
def login():
    """Redirects user to Yahoo for authentication."""
    # The auth_dir is the project root, where private.json will be stored.
    auth_dir = '.'
    # The league_id is not required for the initial authentication query.
    # Removing league_id=None resolves the TypeError.
    query = YahooFantasySportsQuery(
        auth_dir,
        consumer_key=YAHOO_CONSUMER_KEY,
        consumer_secret=YAHOO_CONSUMER_SECRET
    )
    return redirect(query.login())

@app.route('/logout')
def logout():
    """Clears the session and token file."""
    session.clear()
    token_file = 'private.json'
    if os.path.exists(token_file):
        os.remove(token_file)
    return redirect(url_for('index'))

# --- API Routes ---
@app.route('/api/user')
def user_status():
    """Checks if the user is logged in by looking for private.json in the root."""
    token_file = 'private.json'
    if os.path.exists(token_file):
        return jsonify({'loggedIn': True})
    return jsonify({'loggedIn': False})

@app.route('/api/leagues')
def get_leagues():
    """Fetches the user's fantasy leagues for the current year."""
    token_file = 'private.json'
    if not os.path.exists(token_file):
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        auth_dir = '.'
        query = YahooFantasySportsQuery(auth_dir)
        leagues = query.get_leagues_by_game_code('nhl', 2025)
        leagues_data = [{'league_id': l.league_id, 'name': l.name} for l in leagues]
        return jsonify(leagues_data)
    except Exception as e:
        logging.error(f"Error fetching leagues: {e}")
        return jsonify({'error': 'Failed to fetch leagues from Yahoo. Your token might be expired.'}), 500

@app.route('/api/initialize_league', methods=['POST'])
def initialize_league():
    """Initializes a league's database in the background."""
    global league_initialization_status
    data = request.get_json()
    league_id = data.get('league_id')
    if not league_id:
        return jsonify({'error': 'League ID is required'}), 400

    session['league_id'] = league_id
    db_path = get_db_path(league_id)

    if os.path.exists(db_path):
        return jsonify({'status': 'exists', 'message': 'League database already exists.'})

    auth_dir = '.'
    league_initialization_status[league_id] = {'status': 'initializing'}
    thread = threading.Thread(target=initialize_league_data_background, args=(league_id, auth_dir))
    thread.start()

    return jsonify({'status': 'initializing', 'message': 'League initialization started.'})

@app.route('/api/league_status/<league_id>')
def get_league_status(league_id):
    """Polls for the status of league database initialization."""
    status_info = league_initialization_status.get(league_id, {'status': 'unknown'})
    return jsonify(status_info)

@app.route('/api/get_current_league_id')
def get_current_league_id():
    """Returns the league_id stored in the session."""
    league_id = session.get('league_id')
    if not league_id:
        return jsonify({'error': 'No league selected'}), 404
    return jsonify({'league_id': league_id})

@app.route('/api/matchups')
def get_matchups():
    league_id = session.get('league_id')
    if not league_id:
        return jsonify({"error": "No league selected"}), 400
    try:
        con = get_db_connection(league_id)
        cur = con.cursor()
        cur.execute("SELECT week, team1, team2 FROM matchups ORDER BY week")
        rows = cur.fetchall()
        con.close()
        matchups = [{"week": r[0], "team1": r[1], "team2": r[2]} for r in rows]
        return jsonify(matchups)
    except Exception as e:
        logging.error(f"Error fetching matchups for league {league_id}: {e}")
        return jsonify({"error": "Could not fetch matchup data"}), 500

@app.route('/api/download_db')
def download_db():
    """Allows downloading the league's database file."""
    league_id = session.get('league_id')
    if not league_id:
        return "No league selected.", 400
    db_path = get_db_path(league_id)
    if not os.path.exists(db_path):
        return "Database not found.", 404
    return send_file(db_path, as_attachment=True)

# --- Frontend Serving Routes ---
# Note: The paths for send_from_directory are now relative to the server folder
@app.route('/')
def index():
    """Serves the main login page from the client folder."""
    return send_from_directory('../client', 'index.html')

@app.route('/home')
def home():
    """Serves the main application page after a league is selected."""
    if 'league_id' not in session:
        return redirect(url_for('index'))
    return send_from_directory('../client', 'home.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serves other static files from the client directory."""
    # This is a general catch-all, be careful with production security
    return send_from_directory('../client', path)

# --- Main Execution ---
if __name__ == '__main__':
    app.run(debug=True, port=5001)
