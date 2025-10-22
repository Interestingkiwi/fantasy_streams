from gevent import monkey
monkey.patch_all()

"""
Main run app for Fantasystreams.app

Author: Jason Druckenmiller
Date: 10/16/2025
Updated: 10/22/2025
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
from datetime import date, timedelta, datetime
import shutil
from collections import defaultdict, Counter
import itertools
import copy

# --- Flask App Configuration ---
# Assume a 'data' directory exists for storing database files
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

SERVER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'server')
TEST_DB_FILENAME = 'yahoo-22705-Albany Hockey Hooligans Test.db'
TEST_DB_PATH = os.path.join(SERVER_DIR, TEST_DB_FILENAME)

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


def get_db_connection_for_league(league_id):
    """Finds and connects to the league's database. Uses a test DB if configured."""
    if session.get('use_test_db'):
        logging.info(f"Using test database: {TEST_DB_PATH}")
        if not os.path.exists(TEST_DB_PATH):
            return None, f"Test database '{TEST_DB_FILENAME}' not found in 'server' directory."
        try:
            # Render has an ephemeral filesystem. The test DB in the repo (`server/`) is read-only.
            # It's safer to copy it to the writable `data` dir to connect.
            writable_test_db_path = os.path.join(DATA_DIR, f"temp_{TEST_DB_FILENAME}")
            shutil.copy2(TEST_DB_PATH, writable_test_db_path)
            conn = sqlite3.connect(writable_test_db_path)
            conn.row_factory = sqlite3.Row
            logging.info(f"Successfully connected to temporary copy of test DB.")
            return conn, None
        except Exception as e:
            logging.error(f"Error connecting to test DB at {TEST_DB_PATH}: {e}")
            return None, "Could not connect to the test database."

    # Original logic if not using test DB
    if not league_id:
        return None, "League ID not found in session."

    db_filename = None
    for filename in os.listdir(DATA_DIR):
        if filename.startswith(f"yahoo-{league_id}-") and filename.endswith(".db"):
            db_filename = filename
            break

    if not db_filename:
        return None, "Database file not found. Please initialize it on the 'League Database' page."

    db_path = os.path.join(DATA_DIR, db_filename)
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn, None
    except Exception as e:
        logging.error(f"Error connecting to DB at {db_path}: {e}")
        return None, "Could not connect to the database."


def decode_dict_values(data):
    """Recursively decodes byte strings in a dictionary or list of dictionaries."""
    if isinstance(data, list):
        return [decode_dict_values(item) for item in data]
    if isinstance(data, dict):
        return {k: v.decode('utf-8') if isinstance(v, bytes) else v for k, v in data.items()}
    return data


def get_optimal_lineup(players, lineup_settings):
    """
    Calculates the optimal lineup using a three-pass greedy algorithm that prioritizes
    maximizing player starts and then optimizing for the best rank.
    """
    ranked_players = sorted(
        [p for p in players if 'total_rank' in p and p['total_rank'] is not None],
        key=lambda p: p['total_rank']
    )

    lineup = {pos: [] for pos in lineup_settings}
    player_pool = list(ranked_players)
    assigned_player_names = set()

    def assign_player(player, pos, current_lineup, assigned_set):
        current_lineup[pos].append(player)
        assigned_set.add(player['player_name_normalized'])
        return True

    # --- Pass 1: Place players with only one eligible position ---
    single_pos_players = sorted(
        [p for p in player_pool if len(p['eligible_positions'].split(',')) == 1],
        key=lambda p: p['total_rank']
    )
    for player in single_pos_players:
        pos = player['eligible_positions'].strip()
        if pos in lineup and len(lineup[pos]) < lineup_settings.get(pos, 0):
            assign_player(player, pos, lineup, assigned_player_names)

    player_pool = [p for p in player_pool if p['player_name_normalized'] not in assigned_player_names]

    # --- Pass 2: Place multi-position players using a scarcity-aware algorithm ---
    player_pool.sort(key=lambda p: p['total_rank'])
    for player in player_pool:
        eligible_positions = [pos.strip() for pos in player['eligible_positions'].split(',')]
        available_slots_for_player = [
            pos for pos in eligible_positions if pos in lineup and len(lineup[pos]) < lineup_settings.get(pos, 0)
        ]

        if not available_slots_for_player: continue

        slot_scarcity = {}
        for slot in available_slots_for_player:
            scarcity_count = sum(1 for other in player_pool if other != player and slot in [p.strip() for p in other['eligible_positions'].split(',')])
            slot_scarcity[slot] = scarcity_count

        best_pos = min(slot_scarcity, key=slot_scarcity.get)
        assign_player(player, best_pos, lineup, assigned_player_names)

    player_pool = [p for p in player_pool if p['player_name_normalized'] not in assigned_player_names]

    # --- Pass 3: Upgrade Pass ---
    # Try to swap in benched players if they are better than a starter.
    for benched_player in player_pool: # player_pool now contains only benched players
        for pos in [p.strip() for p in benched_player['eligible_positions'].split(',')]:
            if pos not in lineup: continue

            # Find the worst-ranked starter in this position
            if not lineup[pos]: continue # Should not happen if lineup is full, but a safeguard

            worst_starter_in_pos = max(lineup[pos], key=lambda p: p['total_rank'])

            # If the benched player is better, try to make a swap
            if benched_player['total_rank'] < worst_starter_in_pos['total_rank']:
                # The simple swap: benched player takes the starter's spot
                lineup[pos].remove(worst_starter_in_pos)
                lineup[pos].append(benched_player)

                # Now, try to re-slot the benched starter (worst_starter_in_pos)
                # This makes the algorithm more robust.
                is_re_slotted = False
                for other_pos in [p.strip() for p in worst_starter_in_pos['eligible_positions'].split(',')]:
                    if other_pos in lineup and len(lineup[other_pos]) < lineup_settings.get(other_pos, 0):
                        lineup[other_pos].append(worst_starter_in_pos)
                        is_re_slotted = True
                        break # Re-slotted successfully

                # If the bumped starter couldn't be re-slotted, they go to the bench.
                # The lineup is still better overall because of the initial upgrade.
                break # Move to the next benched player

    return lineup


def _get_ranked_roster_for_week(cursor, team_id, week_num):
    """
    Internal helper to fetch a team's full roster for a week and enrich it
    with game schedules and player performance ranks.
    """
    # Get week dates
    cursor.execute("SELECT start_date, end_date FROM weeks WHERE week_num = ?", (week_num,))
    week_dates = cursor.fetchone()
    if not week_dates:
        return [] # Or raise an error
    start_date = datetime.strptime(week_dates['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(week_dates['end_date'], '%Y-%m-%d').date()

    # Get roster and player info, including player_id
    cursor.execute("""
        SELECT
            p.player_id,
            p.player_name,
            p.player_team as team,
            p.player_name_normalized,
            rp.eligible_positions
        FROM rosters_tall r
        JOIN rostered_players rp ON r.player_id = rp.player_id
        JOIN players p ON rp.player_id = p.player_id
        WHERE r.team_id = ?
    """, (team_id,))
    players_raw = cursor.fetchall()
    players = decode_dict_values([dict(row) for row in players_raw])

    # Get scoring categories
    cursor.execute("SELECT category FROM scoring")
    scoring_categories = [row['category'] for row in cursor.fetchall()]
    cat_rank_columns = [f"{cat}_cat_rank" for cat in scoring_categories]

    # Get schedules
    for player in players:
        cursor.execute("SELECT schedule_json FROM team_schedules WHERE team_tricode = ?", (player['team'],))
        schedule_row = cursor.fetchone()
        player['game_dates_this_week'] = []
        if schedule_row and schedule_row['schedule_json']:
            schedule = json.loads(schedule_row['schedule_json'])
            for game_date_str in schedule:
                game_date = datetime.strptime(game_date_str, '%Y-%m-%d').date()
                if start_date <= game_date <= end_date:
                    player['game_dates_this_week'].append(game_date_str)

    # Filter out IR players
    active_players = [p for p in players if not any(pos.strip().startswith('IR') for pos in p['eligible_positions'].split(','))]
    normalized_names = [p['player_name_normalized'] for p in active_players]

    # Get player stats and calculate total rank
    if normalized_names:
        placeholders = ','.join('?' for _ in normalized_names)
        query = f"""
            SELECT player_name_normalized, {', '.join(cat_rank_columns)}
            FROM joined_player_stats
            WHERE player_name_normalized IN ({placeholders})
        """
        cursor.execute(query, normalized_names)
        player_stats = {row['player_name_normalized']: dict(row) for row in cursor.fetchall()}

        for player in active_players:
            stats = player_stats.get(player['player_name_normalized'])
            if stats:
                total_rank = sum(stats.get(col, 0) or 0 for col in cat_rank_columns)
                player['total_rank'] = round(total_rank, 2)
            else:
                # Use None for JSON compatibility if a player has no stats
                player['total_rank'] = None

    return active_players


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


@app.route('/api/matchup_page_data')
def matchup_page_data():
    league_id = session.get('league_id')
    conn, error_msg = get_db_connection_for_league(league_id)

    if not conn:
        return jsonify({'db_exists': False, 'error': error_msg})

    try:
        cursor = conn.cursor()

        # Fetch weeks
        cursor.execute("SELECT week_num, start_date, end_date FROM weeks ORDER BY week_num")
        weeks = decode_dict_values([dict(row) for row in cursor.fetchall()])

        # Fetch teams
        cursor.execute("SELECT team_id, name FROM teams ORDER BY name")
        teams = decode_dict_values([dict(row) for row in cursor.fetchall()])

        # Fetch matchups
        cursor.execute("SELECT week, team1, team2 FROM matchups")
        matchups = decode_dict_values([dict(row) for row in cursor.fetchall()])

        # Fetch scoring categories, ordered by group (offense, then goalie) then ID
        cursor.execute("SELECT category, stat_id, scoring_group FROM scoring ORDER BY scoring_group DESC, stat_id")
        scoring_categories = decode_dict_values([dict(row) for row in cursor.fetchall()])

        # Determine current week
        today = date.today().isoformat()
        cursor.execute("SELECT week_num FROM weeks WHERE start_date <= ? AND end_date >= ?", (today, today))
        current_week_row = cursor.fetchone()
        current_week = current_week_row['week_num'] if current_week_row else (weeks[0]['week_num'] if weeks else 1)

        return jsonify({
            'db_exists': True,
            'weeks': weeks,
            'teams': teams,
            'matchups': matchups,
            'scoring_categories': scoring_categories,
            'current_week': current_week
        })

    except Exception as e:
        logging.error(f"Error fetching matchup page data: {e}", exc_info=True)
        return jsonify({'db_exists': False, 'error': f"An error occurred: {e}"}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/matchup_team_stats', methods=['POST'])
def get_matchup_stats():
    league_id = session.get('league_id')
    data = request.get_json()
    week_num = data.get('week')
    team1_name = data.get('team1_name')
    team2_name = data.get('team2_name')

    conn, error_msg = get_db_connection_for_league(league_id)
    if not conn:
        return jsonify({'error': error_msg}), 404

    try:
        cursor = conn.cursor()

        # Get team IDs from names
        cursor.execute("SELECT team_id FROM teams WHERE CAST(name AS TEXT) = ?", (team1_name,))
        team1_id_row = cursor.fetchone()
        if not team1_id_row: return jsonify({'error': f'Team not found: {team1_name}'}), 404
        team1_id = team1_id_row['team_id']

        cursor.execute("SELECT team_id FROM teams WHERE CAST(name AS TEXT) = ?", (team2_name,))
        team2_id_row = cursor.fetchone()
        if not team2_id_row: return jsonify({'error': f'Team not found: {team2_name}'}), 404
        team2_id = team2_id_row['team_id']

        # Get week start/end dates
        cursor.execute("SELECT start_date, end_date FROM weeks WHERE week_num = ?", (week_num,))
        week_dates = cursor.fetchone()
        if not week_dates: return jsonify({'error': f'Week not found: {week_num}'}), 404
        start_date_str = week_dates['start_date']
        end_date_str = week_dates['end_date']

        # Get official scoring categories
        cursor.execute("SELECT category FROM scoring")
        scoring_categories = [row['category'] for row in cursor.fetchall()]

        # **FIX**: Ensure all necessary sub-categories for calculations are included
        required_cats = {'SV', 'SA', 'GA', 'TOI/G'}
        all_categories_to_fetch = list(set(scoring_categories) | required_cats)


        cursor.execute("SELECT position, position_count FROM lineup_settings WHERE position NOT IN ('BN', 'IR', 'IR+')")
        lineup_settings = {row['position']: row['position_count'] for row in cursor.fetchall()}


        # --- Calculate Live Stats ---
        cursor.execute("""
            SELECT team_id, category, SUM(stat_value) as total
            FROM daily_player_stats
            WHERE date_ >= ? AND date_ <= ? AND (team_id = ? OR team_id = ?)
            GROUP BY team_id, category
        """, (start_date_str, end_date_str, team1_id, team2_id))

        live_stats_raw = cursor.fetchall()
        live_stats_decoded = decode_dict_values([dict(row) for row in live_stats_raw])

        stats = {
            'team1': {'live': {cat: 0 for cat in all_categories_to_fetch}, 'row': {}},
            'team2': {'live': {cat: 0 for cat in all_categories_to_fetch}, 'row': {}}
        }

        for row in live_stats_decoded:
            team_key = 'team1' if str(row['team_id']) == str(team1_id) else 'team2'
            if row['category'] in all_categories_to_fetch:
                stats[team_key]['live'][row['category']] = row.get('total', 0)

        # --- Calculate ROW (Rest of Week) Stats ---
        # 1. Initialize ROW with live stats
        stats['team1']['row'] = copy.deepcopy(stats['team1']['live'])
        stats['team2']['row'] = copy.deepcopy(stats['team2']['live'])

        # 2. Get the ranked rosters for the entire week for both teams
        team1_ranked_roster = _get_ranked_roster_for_week(cursor, team1_id, week_num)
        team2_ranked_roster = _get_ranked_roster_for_week(cursor, team2_id, week_num)

        # 3. Determine date range for projection
        today = date.today()
        start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        projection_start_date = max(today, start_date_obj)

        # 4. Loop through remaining days and add projections
        current_date = projection_start_date
        while current_date <= end_date_obj:
            current_date_str = current_date.strftime('%Y-%m-%d')

            # Get players playing today for each team
            team1_players_today = [p for p in team1_ranked_roster if current_date_str in p.get('game_dates_this_week', [])]
            team2_players_today = [p for p in team2_ranked_roster if current_date_str in p.get('game_dates_this_week', [])]

            # Generate optimal lineup for each team
            team1_lineup = get_optimal_lineup(team1_players_today, lineup_settings)
            team2_lineup = get_optimal_lineup(team2_players_today, lineup_settings)

            # Flatten the lineup dictionaries to get a list of player_ids
            team1_starters = [player['player_id'] for pos_players in team1_lineup.values() for player in pos_players]
            team2_starters = [player['player_id'] for pos_players in team2_lineup.values() for player in pos_players]
            all_starters_today = team1_starters + team2_starters

            if all_starters_today:
                # Fetch their average stats from joined_player_stats
                placeholders = ','.join('?' for _ in all_starters_today)
                query = f"""
                    SELECT player_id, {', '.join(all_categories_to_fetch)}
                    FROM joined_player_stats
                    WHERE player_id IN ({placeholders})
                """
                cursor.execute(query, tuple(all_starters_today))
                player_stats_raw = cursor.fetchall()
                player_avg_stats = {row['player_id']: dict(row) for row in player_stats_raw}

                # Add projected stats to the ROW totals
                for player_id in team1_starters:
                    if player_id in player_avg_stats:
                        for category in all_categories_to_fetch:
                            stat_val = player_avg_stats[player_id].get(category) or 0
                            stats['team1']['row'][category] += stat_val

                for player_id in team2_starters:
                    if player_id in player_avg_stats:
                        for category in all_categories_to_fetch:
                            stat_val = player_avg_stats[player_id].get(category) or 0
                            stats['team2']['row'][category] += stat_val

            current_date += timedelta(days=1)

        return jsonify(stats)

    except Exception as e:
        logging.error(f"Error fetching matchup stats: {e}", exc_info=True)
        return jsonify({'error': f"An error occurred: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/lineup_page_data')
def lineup_page_data():
    league_id = session.get('league_id')
    conn, error_msg = get_db_connection_for_league(league_id)

    if not conn:
        return jsonify({'db_exists': False, 'error': error_msg})

    try:
        cursor = conn.cursor()

        # Fetch weeks
        cursor.execute("SELECT week_num, start_date, end_date FROM weeks ORDER BY week_num")
        weeks = decode_dict_values([dict(row) for row in cursor.fetchall()])

        # Fetch teams
        cursor.execute("SELECT team_id, name FROM teams ORDER BY name")
        teams = decode_dict_values([dict(row) for row in cursor.fetchall()])

        # Determine current week
        today = date.today().isoformat()
        cursor.execute("SELECT week_num FROM weeks WHERE start_date <= ? AND end_date >= ?", (today, today))
        current_week_row = cursor.fetchone()
        current_week = current_week_row['week_num'] if current_week_row else (weeks[0]['week_num'] if weeks else 1)

        return jsonify({
            'db_exists': True,
            'weeks': weeks,
            'teams': teams,
            'current_week': current_week
        })

    except Exception as e:
        logging.error(f"Error fetching lineup page data: {e}", exc_info=True)
        return jsonify({'db_exists': False, 'error': f"An error occurred: {e}"}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/roster_data', methods=['POST'])
def get_roster_data():
    league_id = session.get('league_id')
    data = request.get_json()
    week_num = data.get('week')
    team_name = data.get('team_name')

    conn, error_msg = get_db_connection_for_league(league_id)
    if not conn:
        return jsonify({'error': error_msg}), 404

    try:
        cursor = conn.cursor()

        # Get team ID
        cursor.execute("SELECT team_id FROM teams WHERE CAST(name AS TEXT) = ?", (team_name,))
        team_id_row = cursor.fetchone()
        if not team_id_row:
            return jsonify({'error': f'Team not found: {team_name}'}), 404
        team_id = team_id_row['team_id']

        # Get week dates
        cursor.execute("SELECT start_date, end_date FROM weeks WHERE week_num = ?", (week_num,))
        week_dates = cursor.fetchone()
        if not week_dates:
            return jsonify({'error': f'Week not found: {week_num}'}), 404
        start_date = datetime.strptime(week_dates['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(week_dates['end_date'], '%Y-%m-%d').date()

        # Get next week's dates for the 'Next Week' column
        cursor.execute("SELECT start_date, end_date FROM weeks WHERE week_num = ?", (int(week_num) + 1,))
        week_dates_next = cursor.fetchone()
        if not week_dates_next:
            start_date_next, end_date_next = None, None
        else:
            start_date_next = datetime.strptime(week_dates_next['start_date'], '%Y-%m-%d').date()
            end_date_next = datetime.strptime(week_dates_next['end_date'], '%Y-%m-%d').date()

        # Use the helper to get the ranked roster of active players
        active_players = _get_ranked_roster_for_week(cursor, team_id, week_num)

        # Get the full player list for display, including IR players
        cursor.execute("""
            SELECT p.player_name, p.player_team as team, rp.eligible_positions, p.player_name_normalized
            FROM rosters_tall r
            JOIN rostered_players rp ON r.player_id = rp.player_id
            JOIN players p ON rp.player_id = p.player_id
            WHERE r.team_id = ?
        """, (team_id,))
        all_players_raw = cursor.fetchall()
        all_players = decode_dict_values([dict(row) for row in all_players_raw])

        # Get scoring categories to fetch rank columns
        cursor.execute("SELECT category FROM scoring")
        scoring_categories = [row['category'] for row in cursor.fetchall()]
        cat_rank_columns = [f"{cat}_cat_rank" for cat in scoring_categories]

        # Get player stats for all players to populate rank columns
        all_normalized_names = [p['player_name_normalized'] for p in all_players]
        player_stats = {}
        if all_normalized_names:
            placeholders = ','.join('?' for _ in all_normalized_names)
            query = f"""
                SELECT player_name_normalized, {', '.join(cat_rank_columns)}
                FROM joined_player_stats WHERE player_name_normalized IN ({placeholders})
            """
            cursor.execute(query, all_normalized_names)
            player_stats = {row['player_name_normalized']: dict(row) for row in cursor.fetchall()}

        # Augment the full player list with all necessary data
        active_player_map = {p['player_name']: p for p in active_players}
        for player in all_players:
            # Add ranks and this week's schedule from the active player data
            if player['player_name'] in active_player_map:
                source = active_player_map[player['player_name']]
                player['total_rank'] = source.get('total_rank')
                player['game_dates_this_week'] = source.get('game_dates_this_week', [])
                player['games_this_week'] = [datetime.strptime(d, '%Y-%m-%d').strftime('%a') for d in player['game_dates_this_week']]
            else: # Handle IR players
                player['games_this_week'] = []
                player['game_dates_this_week'] = []

            # Add category ranks for all players (active and inactive)
            p_stats = player_stats.get(player['player_name_normalized'])
            if p_stats:
                for cat in scoring_categories:
                    rank_key = f"{cat}_cat_rank"
                    player[rank_key] = round(p_stats.get(rank_key), 2) if p_stats.get(rank_key) is not None else None

            # **FIX**: Calculate and add 'games_next_week'
            player['games_next_week'] = []
            if start_date_next and end_date_next:
                cursor.execute("SELECT schedule_json FROM team_schedules WHERE team_tricode = ?", (player['team'],))
                schedule_row = cursor.fetchone()
                if schedule_row and schedule_row['schedule_json']:
                    schedule = json.loads(schedule_row['schedule_json'])
                    for game_date_str in schedule:
                        game_date = datetime.strptime(game_date_str, '%Y-%m-%d').date()
                        if start_date_next <= game_date <= end_date_next:
                            player['games_next_week'].append(game_date.strftime('%a'))

        # Get lineup settings
        cursor.execute("SELECT position, position_count FROM lineup_settings WHERE position NOT IN ('BN', 'IR', 'IR+')")
        lineup_settings = {row['position']: row['position_count'] for row in cursor.fetchall()}

        # --- Calculate optimal lineup and starts for each day ---
        daily_optimal_lineups = {}
        player_starts_counter = Counter()

        current_date = start_date
        while current_date <= end_date:
            day_str = current_date.strftime('%Y-%m-%d')
            players_playing_today = [
                p for p in active_players if day_str in p.get('game_dates_this_week', [])
            ]

            if players_playing_today:
                optimal_lineup_for_day = get_optimal_lineup(players_playing_today, lineup_settings)
                display_date = current_date.strftime('%A, %b %d')
                daily_optimal_lineups[display_date] = optimal_lineup_for_day

                for pos_players in optimal_lineup_for_day.values():
                    for player in pos_players:
                        player_starts_counter[player['player_name']] += 1

            current_date += timedelta(days=1)

        # Add starts count to the final player list
        for player in all_players:
            player['starts_this_week'] = player_starts_counter.get(player['player_name'], 0)

        return jsonify({
            'players': all_players,
            'daily_optimal_lineups': daily_optimal_lineups,
            'scoring_categories': scoring_categories,
            'lineup_settings': lineup_settings
        })

    except Exception as e:
        logging.error(f"Error fetching roster data: {e}", exc_info=True)
        return jsonify({'error': f"An error occurred: {e}"}), 500
    finally:
        if conn:
            conn.close()


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
    if session.get('use_test_db'):
        logging.info(f"Downloading test database: {TEST_DB_FILENAME}")
        if not os.path.exists(TEST_DB_PATH):
            return jsonify({'error': 'Test database file not found in /server directory.'}), 404
        return send_from_directory(SERVER_DIR, TEST_DB_FILENAME, as_attachment=True)

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

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    if request.method == 'GET':
        return jsonify({
            'use_test_db': session.get('use_test_db', False),
            'test_db_exists': os.path.exists(TEST_DB_PATH)
        })
    elif request.method == 'POST':
        data = request.get_json()
        use_test_db = data.get('use_test_db', False)
        session['use_test_db'] = use_test_db
        logging.info(f"Test DB mode set to: {use_test_db}")
        return jsonify({'success': True, 'use_test_db': use_test_db})

@app.route('/pages/<path:page_name>')
def serve_page(page_name):
    return render_template(f"pages/{page_name}")

@app.route('/api/db_status')
def db_status():
    if session.get('use_test_db'):
        db_exists = os.path.exists(TEST_DB_PATH)
        timestamp = os.path.getmtime(TEST_DB_PATH) if db_exists else None
        return jsonify({
            'db_exists': db_exists,
            'league_name': f"TEST DB: {TEST_DB_FILENAME}",
            'timestamp': int(timestamp) if timestamp else None,
            'is_test_db': True
        })

    league_id = session.get('league_id')
    if not league_id:
        return jsonify({'db_exists': False, 'error': 'Not logged in.', 'is_test_db': False})

    db_path = None
    league_name = "[Unknown]"
    timestamp = None
    db_exists = False
    db_filename = None

    for filename in os.listdir(DATA_DIR):
        if filename.startswith(f"yahoo-{league_id}-") and filename.endswith(".db"):
            db_path = os.path.join(DATA_DIR, filename)
            db_exists = True
            db_filename = filename
            break

    if db_exists:
        try:
            match = re.search(f"yahoo-{league_id}-(.*)\\.db", db_filename)
            if match:
                league_name = match.group(1)
            timestamp = os.path.getmtime(db_path)
        except Exception as e:
            logging.error(f"Could not parse DB file info: {e}")
            return jsonify({'db_exists': False, 'error': 'Could not read database file details.', 'is_test_db': False})

    return jsonify({
        'db_exists': db_exists,
        'league_name': league_name,
        'timestamp': int(timestamp) if timestamp else None,
        'is_test_db': False
    })

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    app.run(debug=True, port=5001)
