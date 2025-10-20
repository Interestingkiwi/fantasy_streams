import sqlite3
import json
import os
import logging # Import the logging module
from datetime import datetime, timedelta
from .optimization_logic import find_optimal_lineup

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [lineup_generator] - %(message)s')

def get_db_connections(league_db_path):
    """Establishes and returns connections to the league and projections databases."""
    proj_db_path = os.path.join('server', 'projections.db')

    if not os.path.exists(league_db_path):
        logging.error(f"League database not found at {league_db_path}")
        raise FileNotFoundError(f"League database not found at {league_db_path}")
    if not os.path.exists(proj_db_path):
        logging.error(f"Projections database not found at {proj_db_path}")
        raise FileNotFoundError(f"Projections database not found at {proj_db_path}")

    league_conn = sqlite3.connect(league_db_path)
    league_conn.row_factory = sqlite3.Row
    proj_conn = sqlite3.connect(proj_db_path)
    proj_conn.row_factory = sqlite3.Row

    logging.info("Successfully established database connections.")
    return league_conn, proj_conn

def calculate_marginal_value(player_projections_json, category_weights):
    """Calculates a single 'marginal_value' for a player."""
    if not player_projections_json or not category_weights:
        return 0

    try:
        projections = json.loads(player_projections_json)
        value = 0
        for category, weight in category_weights.items():
            value += float(projections.get(category, 0)) * float(weight)
        return value
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logging.warning(f"Could not calculate marginal value. Projections: {player_projections_json}, Error: {e}")
        return 0


def generate_weekly_lineups(league_db_path, team_id, week_info):
    """
    Generates and stores the optimal lineup for each day of a given fantasy week.
    """
    logging.info(f"--- Starting lineup generation for team_id: {team_id}, week: {week_info['week_num']} ---")
    league_conn, proj_conn = None, None
    try:
        league_conn, proj_conn = get_db_connections(league_db_path)
        league_cur = league_conn.cursor()
        proj_cur = proj_conn.cursor()

        logging.info("Step 1: Ensuring 'optimal_lineups' table exists.")
        league_cur.execute('''
            CREATE TABLE IF NOT EXISTS optimal_lineups (
                lineup_date TEXT NOT NULL,
                team_id TEXT NOT NULL,
                player_id INTEGER NOT NULL,
                player_name TEXT,
                played_position TEXT,
                status TEXT,
                marginal_value REAL,
                PRIMARY KEY (lineup_date, team_id, player_id)
            )
        ''')

        logging.info("Step 2: Fetching league settings (stat weights and lineup).")
        league_cur.execute("SELECT settings_json FROM settings WHERE setting_name = 'stat_weights'")
        weights_row = league_cur.fetchone()
        category_weights = json.loads(weights_row['settings_json']) if weights_row else {}
        if not category_weights:
            logging.warning("Stat weights not found or empty in settings table!")
        else:
            logging.info(f"Found {len(category_weights)} stat weights.")

        league_cur.execute("SELECT position, count FROM lineup_settings")
        lineup_settings_rows = league_cur.fetchall()
        lineup_slots = {row['position']: row['count'] for row in lineup_settings_rows if row['position'] not in ('BN', 'IR', 'IR+')}
        if not lineup_slots:
            logging.error("FATAL: Lineup settings not found or empty in lineup_settings table!")
            return
        else:
            logging.info(f"Found lineup slots: {lineup_slots}")


        logging.info(f"Step 3: Fetching full team roster for team_id: {team_id}")
        league_cur.execute("SELECT player_id FROM rosters WHERE team_id = ?", (team_id,))
        player_ids = [row['player_id'] for row in league_cur.fetchall()]
        logging.info(f"Found {len(player_ids)} players on roster: {player_ids}")

        roster_players = []
        for pid in player_ids:
            league_cur.execute("SELECT status FROM rostered_players WHERE player_id = ?", (pid,))
            rostered_player_info = league_cur.fetchone()
            if rostered_player_info and rostered_player_info['status'] in ('IR', 'IR+'):
                logging.info(f"Player {pid} is on IR/IR+, skipping.")
                continue

            proj_cur.execute('''
                SELECT p.name, p.team, p.positions, p.per_game_projections, s.schedule
                FROM joined_player_stats p
                LEFT JOIN team_schedules s ON p.team = s.team_abbr
                WHERE p.player_id = ?
            ''', (pid,))
            player_data = proj_cur.fetchone()

            if player_data:
                player = dict(player_data)
                player['player_id'] = pid
                player['marginal_value'] = calculate_marginal_value(player.get('per_game_projections'), category_weights)

                try:
                    player['schedule'] = json.loads(player.get('schedule', '[]'))
                    roster_players.append(player)
                except json.JSONDecodeError:
                    logging.warning(f"Could not decode schedule JSON for player {pid}. Skipping.")
            else:
                logging.warning(f"No data found in projections.db for player_id {pid}.")

        logging.info(f"Successfully enriched data for {len(roster_players)} active players.")

        logging.info("Step 4: Iterating through week and running optimization.")
        start_date = datetime.strptime(week_info['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(week_info['end_date'], '%Y-%m-%d').date()

        logging.info(f"Clearing old lineup data for week {week_info['week_num']}...")
        league_cur.execute("DELETE FROM optimal_lineups WHERE team_id = ? AND lineup_date BETWEEN ? AND ?",
                           (team_id, week_info['start_date'], week_info['end_date']))

        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            players_playing_today = [p for p in roster_players if date_str in p.get('schedule', [])]

            logging.info(f"Processing date: {date_str}. Found {len(players_playing_today)} players playing.")

            if players_playing_today:
                logging.info(f"--- Calling find_optimal_lineup for {date_str} ---")
                optimal_roster, benched_players = find_optimal_lineup(players_playing_today, lineup_slots, category_weights)
                logging.info(f"--- Optimization complete for {date_str}. Active: {len(optimal_roster)}, Benched: {len(benched_players)} ---")

                for player, position in optimal_roster:
                    league_cur.execute('''
                        INSERT OR REPLACE INTO optimal_lineups (lineup_date, team_id, player_id, player_name, played_position, status, marginal_value)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (date_str, team_id, player['player_id'], player['name'], position, 'ACTIVE', player['marginal_value']))

                for player in benched_players:
                    league_cur.execute('''
                        INSERT OR REPLACE INTO optimal_lineups (lineup_date, team_id, player_id, player_name, played_position, status, marginal_value)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (date_str, team_id, player['player_id'], player['name'], 'BN', 'BENCH', player['marginal_value']))

            current_date += timedelta(days=1)

        league_conn.commit()
        logging.info(f"--- Successfully generated and stored lineups for team {team_id} for week {week_info['week_num']} ---")

    except Exception as e:
        logging.error(f"An unexpected error occurred in generate_weekly_lineups: {e}", exc_info=True)
    finally:
        if league_conn:
            league_conn.close()
        if proj_conn:
            proj_conn.close()
        logging.info("Database connections closed.")
