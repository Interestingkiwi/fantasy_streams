"""
Lineup generator for FantasyStreams

Author: Jason Druckenmiller
Date: 10/20/2025
Updated: 10/20/2025
"""


import sqlite3
import json
import os
from datetime import datetime, timedelta
from .optimization_logic import find_optimal_lineup

def get_db_connections(league_db_path):
    """Establishes and returns connections to the league and projections databases."""
    proj_db_path = os.path.join('server', 'projections.db')

    if not os.path.exists(league_db_path):
        raise FileNotFoundError(f"League database not found at {league_db_path}")
    if not os.path.exists(proj_db_path):
        raise FileNotFoundError(f"Projections database not found at {proj_db_path}")

    league_conn = sqlite3.connect(league_db_path)
    league_conn.row_factory = sqlite3.Row
    proj_conn = sqlite3.connect(proj_db_path)
    proj_conn.row_factory = sqlite3.Row

    return league_conn, proj_conn

def calculate_marginal_value(player_projections_json, category_weights):
    """Calculates a single 'marginal_value' for a player."""
    if not player_projections_json or not category_weights:
        return 0

    projections = json.loads(player_projections_json)
    value = 0
    for category, weight in category_weights.items():
        try:
            value += float(projections.get(category, 0)) * float(weight)
        except (ValueError, TypeError):
            continue
    return value

def generate_weekly_lineups(league_db_path, team_id, week_info):
    """
    Generates and stores the optimal lineup for each day of a given fantasy week.
    This is the main orchestrator function.
    """
    league_conn, proj_conn = None, None
    try:
        league_conn, proj_conn = get_db_connections(league_db_path)
        league_cur = league_conn.cursor()
        proj_cur = proj_conn.cursor()

        # Step 1: Create table if it doesn't exist to store results
        league_cur.execute('''
            CREATE TABLE IF NOT EXISTS optimal_lineups (
                lineup_date TEXT NOT NULL,
                team_id TEXT NOT NULL,
                player_id INTEGER NOT NULL,
                player_name TEXT,
                played_position TEXT,
                status TEXT, -- 'ACTIVE' or 'BENCH'
                marginal_value REAL,
                PRIMARY KEY (lineup_date, team_id, player_id)
            )
        ''')

        # Step 2: Get league settings (weights and roster spots)
        league_cur.execute("SELECT settings_json FROM settings WHERE setting_name = 'stat_weights'")
        weights_row = league_cur.fetchone()
        category_weights = json.loads(weights_row['settings_json']) if weights_row else {}

        league_cur.execute("SELECT position, count FROM lineup_settings")
        lineup_settings_rows = league_cur.fetchall()
        lineup_slots = {row['position']: row['count'] for row in lineup_settings_rows if row['position'] not in ('BN', 'IR', 'IR+')}

        # Step 3: Get the full team roster and enrich with data
        league_cur.execute("SELECT player_id FROM rosters WHERE team_id = ?", (team_id,))
        player_ids = [row['player_id'] for row in league_cur.fetchall()]

        roster_players = []
        for pid in player_ids:
            # Check player's injury status from the league DB
            league_cur.execute("SELECT status FROM rostered_players WHERE player_id = ?", (pid,))
            rostered_player_info = league_cur.fetchone()
            # Skip players on IR/IR+ designated slots
            if rostered_player_info and rostered_player_info['status'] in ('IR', 'IR+'):
                continue

            # Get player stats and schedule from projections DB
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
                player['schedule'] = json.loads(player.get('schedule', '[]'))
                roster_players.append(player)

        # Step 4: Iterate through each day of the week and run optimization
        start_date = datetime.strptime(week_info['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(week_info['end_date'], '%Y-%m-%d').date()

        # Clear any old data for this week before generating new data
        league_cur.execute("DELETE FROM optimal_lineups WHERE team_id = ? AND lineup_date BETWEEN ? AND ?",
                           (team_id, week_info['start_date'], week_info['end_date']))

        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')

            # Filter for players playing on the current day
            players_playing_today = [p for p in roster_players if date_str in p['schedule']]

            if players_playing_today:
                optimal_roster, benched_players = find_optimal_lineup(players_playing_today, lineup_slots, category_weights)

                # Store active players
                for player, position in optimal_roster:
                    league_cur.execute('''
                        INSERT OR REPLACE INTO optimal_lineups (lineup_date, team_id, player_id, player_name, played_position, status, marginal_value)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (date_str, team_id, player['player_id'], player['name'], position, 'ACTIVE', player['marginal_value']))

                # Store benched players
                for player in benched_players:
                    league_cur.execute('''
                        INSERT OR REPLACE INTO optimal_lineups (lineup_date, team_id, player_id, player_name, played_position, status, marginal_value)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (date_str, team_id, player['player_id'], player['name'], 'BN', 'BENCH', player['marginal_value']))

            current_date += timedelta(days=1)

        league_conn.commit()
        print(f"Successfully generated lineups for team {team_id} for week {week_info['week_num']}.")

    except Exception as e:
        print(f"An error occurred in generate_weekly_lineups: {e}")
    finally:
        if league_conn:
            league_conn.close()
        if proj_conn:
            proj_conn.close()
