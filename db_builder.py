import os
import sqlite3
import re
import logging
import time

def _create_tables(cursor):
    """
    Creates all necessary tables in the database if they don't already exist.

    Args:
        cursor: A sqlite3 cursor object.
    """
    logging.info("Creating database tables if they don't exist...")
    # Table for basic league information
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS league_info (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    # Table for teams
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            team_id TEXT PRIMARY KEY,
            name TEXT,
            manager_nickname TEXT
        )
    ''')
    # --- Add other CREATE TABLE statements for future queries here ---


def _update_league_info(yq, cursor, league_id, league_name):
    """
    Fetches league metadata and updates the league_info table.

    Args:
        yq: An authenticated yfpy query object.
        cursor: A sqlite3 cursor object.
        league_id: The ID of the league.
        league_name: The sanitized name of the league.
    """
    logging.info("Updating league_info table...")
    cursor.execute("INSERT OR REPLACE INTO league_info (key, value) VALUES (?, ?)",
                   ('league_id', league_id))
    cursor.execute("INSERT OR REPLACE INTO league_info (key, value) VALUES (?, ?)",
                   ('league_name', league_name))


def _update_teams_info(yq, cursor):
    """
    Fetches team data and updates the teams table.

    Args:
        yq: An authenticated yfpy query object.
        cursor: A sqlite3 cursor object.
    """
    logging.info("Updating teams table...")
    try:
        teams = yq.get_league_teams()

        teams_data_to_insert = []
        for team in teams:
            # Extract team data.
            team_id = team.team_id
            team_name = team.name

            manager_nickname = None  # Default to None
            if team.managers and team.managers[0].nickname:
                manager_nickname = team.managers[0].nickname

            teams_data_to_insert.append((team_id, team_name, manager_nickname))

        sql = "INSERT OR IGNORE INTO teams (team_id, name, manager_nickname) VALUES (?, ?, ?)"
        cursor.executemany(sql, teams_data_to_insert)
        logging.info(f"Successfully inserted or ignored data for {len(teams_data_to_insert)} teams.")
    except Exception as e:
        logging.error(f"Failed to update teams info: {e}", exc_info=True)


def update_league_db(yq, league_id, data_dir):
    """
    Creates or updates the league-specific SQLite database by calling
    individual query and update functions.

    Args:
        yq: An authenticated yfpy.query.YahooFantasySportsQuery object.
        league_id: The ID of the fantasy league.
        data_dir: The directory where the database file should be stored.

    Returns:
        A dictionary with the success status and database info, or an error message.
    """
    try:
        logging.info(f"Starting DB update for league {league_id}...")

        # First, get league metadata to determine the correct filename
        logging.info("Fetching league metadata to determine filename...")
        league_metadata = yq.get_league_metadata()

        # FIX: Decode league_metadata.name to a string before using it with re.sub
        league_name_str = league_metadata.name
        if isinstance(league_name_str, bytes):
            league_name_str = league_name_str.decode('utf-8', 'ignore')

        sanitized_name = re.sub(r'[\\/*?:"<>|]', "", league_name_str)

        # Clean up any old database files for this league ID
        for f in os.listdir(data_dir):
            if f.startswith(f"yahoo-{league_id}-") and f.endswith(".db"):
                logging.info(f"Removing old database file: {f}")
                os.remove(os.path.join(data_dir, f))

        db_filename = f"yahoo-{league_id}-{sanitized_name}.db"
        db_path = os.path.join(data_dir, db_filename)

        logging.info(f"Connecting to database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # --- Call functions to build/update the database ---
        _create_tables(cursor)
        _update_league_info(yq, cursor, league_id, sanitized_name)
        _update_teams_info(yq, cursor)
        # --- As you add more queries, you will call their functions here ---

        conn.commit()
        conn.close()

        timestamp = os.path.getmtime(db_path)
        logging.info(f"Database for '{sanitized_name}' updated successfully.")

        return {
            'success': True,
            'league_name': sanitized_name,
            'timestamp': int(timestamp)
        }

    except Exception as e:
        logging.error(f"Database update process failed: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}
