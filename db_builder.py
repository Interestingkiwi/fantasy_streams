"""
Queries to create and update fantasystreams.app db

Author: Jason Druckenmiller
Date: 10/17/2025
Updated: 10/18/2025
"""

import os
import sqlite3
import re
import logging
import time
import unicodedata
from datetime import date, timedelta


def _create_tables(cursor):
    """
    Creates all necessary tables in the database if they don't already exist.

    Args:
        cursor: A sqlite3 cursor object.
    """
    logging.info("Creating database tables if they don't exist...")

    #league_info
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS league_info (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    #teams
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            team_id TEXT PRIMARY KEY,
            name TEXT,
            manager_nickname TEXT
        )
    ''')
    #daily_lineups_dump
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_lineups_dump (
          lineup_id INTEGER PRIMARY KEY AUTOINCREMENT,
          date_ TEXT NOT NULL,
          team_id INTEGER NOT NULL,
          c1 TEXT,
          c2 TEXT,
          l1 TEXT,
          l2 TEXT,
          r1 TEXT,
          r2 TEXT,
          d1 TEXT,
          d2 TEXT,
          d3 TEXT,
          d4 TEXT,
          g1 TEXT,
          g2 TEXT,
          b1 TEXT,
          b2 TEXT,
          b3 TEXT,
          b4 TEXT,
          b5 TEXT,
          b6 TEXT,
          b7 TEXT,
          b8 TEXT,
          b9 TEXT,
          b10 TEXT,
          b11 TEXT,
          b12 TEXT,
          b13 TEXT,
          b14 TEXT,
          b15 TEXT,
          b16 TEXT,
          b17 TEXT,
          b18 TEXT,
          b19 TEXT,
          i1 TEXT,
          i2 TEXT,
          i3 TEXT,
          i4 TEXT,
          i5 TEXT
        )
    ''')
    #players - being created externally to save individual league builds
#    cursor.execute('''
#        CREATE TABLE IF NOT EXISTS players (
#            player_id TEXT NOT NULL UNIQUE,
#            player_name TEXT NOT NULL,
#            player_team TEXT,
#            player_name_normalized TEXT NOT NULL
#        )
#    ''')
    #scoring
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scoring (
            stat_id INTEGER NOT NULL UNIQUE,
            category TEXT NOT NULL,
            scoring_group TEXT NOT NULL
        )
    ''')
    #weeks
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weeks (
            week_num INTEGER NOT NULL UNIQUE,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL
        )
    ''')
    #matchups
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matchups (
            week INTEGER NOT NULL,
            team1 TEXT NOT NULL,
            team2 TEXT NOT NULL
        )
    ''')
    #rosters
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rosters (
            team_id INTEGER NOT NULL UNIQUE,
            p1 INTEGER,
            p2 INTEGER,
            p3 INTEGER,
            p4 INTEGER,
            p5 INTEGER,
            p6 INTEGER,
            p7 INTEGER,
            p8 INTEGER,
            p9 INTEGER,
            p10 INTEGER,
            p11 INTEGER,
            p12 INTEGER,
            p13 INTEGER,
            p14 INTEGER,
            p15 INTEGER,
            p16 INTEGER,
            p17 INTEGER,
            p18 INTEGER,
            p19 INTEGER,
            p20 INTEGER,
            p21 INTEGER,
            p22 INTEGER,
            p23 INTEGER,
            p24 INTEGER,
            p25 INTEGER,
            p26 INTEGER,
            p27 INTEGER,
            p28 INTEGER,
            p29 INTEGER
        )
    ''')
    #free_agents
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS free_agents (
            player_id TEXT PRIMARY KEY,
            status TEXT
        )
    ''')
    #waiver_players
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS waiver_players (
            player_id TEXT PRIMARY KEY,
            status TEXT
        )
    ''')
    #rostered_players
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rostered_players (
            player_id TEXT PRIMARY KEY,
            status TEXT
        )
    ''')


def _update_league_info(yq, cursor, league_id, league_name, league_metadata):
    """
    Fetches league metadata and updates the league_info table.

    Args:
        yq: An authenticated yfpy query object.
        cursor: A sqlite3 cursor object.
        league_id: The ID of the league.
        league_name: The sanitized name of the league.
        league_metadata: The fetched league metadata object from yfpy.
    """
    logging.info("Updating league_info table...")
    # Extract data from the metadata object
    num_teams = league_metadata.num_teams
    start_date = league_metadata.start_date
    end_date = league_metadata.end_date

    cursor.execute("INSERT OR REPLACE INTO league_info (key, value) VALUES (?, ?)",
                   ('league_id', league_id))
    cursor.execute("INSERT OR REPLACE INTO league_info (key, value) VALUES (?, ?)",
                   ('league_name', league_name))
    cursor.execute("INSERT OR REPLACE INTO league_info (key, value) VALUES (?, ?)",
                   ('num_teams', num_teams))
    cursor.execute("INSERT OR REPLACE INTO league_info (key, value) VALUES (?, ?)",
                   ('start_date', start_date))
    cursor.execute("INSERT OR REPLACE INTO league_info (key, value) VALUES (?, ?)",
                   ('end_date', end_date))


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


def _update_daily_lineups(yq, cursor, conn, num_teams, start_date):
    """
    Iterates through a teams lineup for every day of the season and writes
    player name, and stats to their assigned position in the daily lineup
    table. Repeats for each team in the league.

    Args:
        yq: An authenticated yfpy query object.
        cursor: A sqlite3 cursor object.
    """
    try:
        cursor.execute("SELECT MAX(date_) FROM daily_lineups_dump")
        last_fetch_date_str = cursor.fetchone()[0]

        start_date_for_fetch = start_date
        if last_fetch_date_str:
            last_fetch_date = date.fromisoformat(last_fetch_date_str)
            start_date_for_fetch = (last_fetch_date + timedelta(days=1)).isoformat()
            logging.info(f"Found existing lineup data. Resuming fetch from {start_date_for_fetch}.")
        else:
            logging.info(f"No existing lineup data found. Performing initial fetch from league start date: {start_date_for_fetch}.")


        team_id = 1
        stop_date = date.today().isoformat()
        lineup_data_to_insert = []

        if start_date_for_fetch >= stop_date:
            logging.info("Daily lineups are already up to date.")
            return

        while team_id <= num_teams:
            current_date = start_date_for_fetch
            while current_date < stop_date:
                logging.info(f"Fetching daily lineups for team {team_id}, for {current_date}...")
                players = yq.get_team_roster_player_info_by_date(team_id,current_date)
                c = 0
                lw = 0
                rw = 0
                d = 0
                g = 0
                bn = 0
                ir = 0
                lineup_data_raw = []
                for player in players:
                    player_id = player.player_id
                    player_name = player.name.full
                    pos = player.selected_position.position
                    if pos == "C":
                        pos = 'c'+str(c+1)
                        c += 1
                    elif pos == "LW":
                        pos = 'l'+str(lw+1)
                        lw += 1
                    elif pos == "RW":
                        pos = 'r'+str(rw+1)
                        rw += 1
                    elif pos == "D":
                        pos = 'd'+str(d+1)
                        d += 1
                    elif pos == "G":
                        pos = 'g'+str(g+1)
                        g += 1
                    elif pos == "BN":
                        pos = 'b'+str(bn+1)
                        bn += 1
                    elif pos == "IR" or pos == "IR+":
                        pos = 'i'+str(ir+1)
                        ir += 1
                    player_stats = []
                    if player.player_stats and player.player_stats.stats:
                        stats_list = player.player_stats.stats
                        stats_dict = {
                            stat_item.stat_id: stat_item.value
                            for stat_item in stats_list
                        }
                        for stat_id, stat_value in stats_dict.items():
                            player_stats.append((stat_id, stat_value))
                    #add all stat pulls here too
                    player_data_string = f"ID: {player_id}, Name: {player_name}, Stats: {str(player_stats)}"
                    lineup_data_raw.append((player_data_string, pos))

                lineup_raw_dict = {
                    position: (data_string)
                    for data_string, position in lineup_data_raw
                }
                lineup_order = [
                    'c1', 'c2', 'l1', 'l2', 'r1', 'r2', 'd1', 'd2', 'd3', 'd4',
                    'g1', 'g2', 'b1', 'b2', 'b3', 'b4', 'b5', 'b6',
                    'b7', 'b8', 'b9', 'b10', 'b11', 'b12', 'b13', 'b14',
                    'b15', 'b16', 'b17', 'b18', 'b19', 'i1', 'i2', 'i3', 'i4', 'i5'
                ]
                #player_dict = {position: (player_id, goals) for player_id, goals, position in player_list}
                # Result: {'lw1': (1234, 1), 'rw2': (2345, 2), 'lw2': (3456, 1), 'c1': (4567, 3)}
                #final_list = [player_dict.get(pos, (None, None)) for pos in desired_order]
                lineup_data_values = [lineup_raw_dict.get(pos, None) for pos in lineup_order]
                full_row = [current_date, team_id] + lineup_data_values
                lineup_data_to_insert.append(tuple(full_row))
                current_date = (date.fromisoformat(current_date)+timedelta(1)).isoformat()
            team_id += 1

        if not lineup_data_to_insert:
            logging.info("No new daily lineups to insert for the specified date range.")
            return

        placeholders = ', '.join(['?'] * 38)
        sql = f"""
            INSERT INTO daily_lineups_dump (
                date_, team_id, c1, c2, l1, l2, r1, r2, d1, d2, d3, d4, g1, g2,
                b1, b2, b3, b4, b5, b6, b7, b8, b9, b10, b11, b12, b13, b14, b15,
                b16, b17, b18, b19, i1, i2, i3, i4, i5
            ) VALUES ({placeholders})
        """


        cursor.executemany(sql, lineup_data_to_insert)
        logging.info(f"Successfully inserted or ignored data for {len(lineup_data_to_insert)} dates.")
    except Exception as e:
        logging.error(f"Failed to update lineup info: {e}", exc_info=True)


def _update_player_id(yq, cursor):
    """
    Writes player name, normalized player name, team, and yahoo id to players
    table for all players in the league. This is a long-running operation.

    Args:
        yq: An authenticated yfpy query object.
        cursor: A sqlite3 cursor object.
    """
    logging.info("Fetching all league players (this may take a while)...")
    try:
        TEAM_TRICODE_MAP = {
            "TB": "TBL",
            "NJ": "NJD",
            "SJ": "SJS",
            "LA": "LAK",
            "MON": "MTL",
            "WAS": "WSH"
        }

        player_data_to_insert = []
        batch_size = 100
        player_count = 0
        sql = "INSERT OR IGNORE INTO players (player_id, player_name, player_team, player_name_normalized) VALUES (?, ?, ?, ?)"

        # yfpy's get_league_players is a generator that handles pagination automatically.
        for player in yq.get_league_players():
            player_count += 1
            player_name = player.name.full
            nfkd_form = unicodedata.normalize('NFKD', player_name.lower())
            ascii_name = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
            player_name_normalized = re.sub(r'[^a-z0-9]', '', ascii_name)
            player_team_abbr = player.editorial_team_abbr.upper()
            player_team = TEAM_TRICODE_MAP.get(player_team_abbr, player_team_abbr)

            player_data_to_insert.append((player.player_id, player_name, player_team, player_name_normalized))

            # Insert in batches to manage memory and provide progress
            if len(player_data_to_insert) >= batch_size:
                logging.info(f"Processed {player_count} players, inserting batch of {len(player_data_to_insert)}...")
                cursor.executemany(sql, player_data_to_insert)
                player_data_to_insert = [] # Clear the batch

        # Insert any remaining players after the loop
        if player_data_to_insert:
            logging.info(f"Inserting final batch of {len(player_data_to_insert)} players...")
            cursor.executemany(sql, player_data_to_insert)

        logging.info(f"Successfully processed and inserted data for a total of {player_count} players.")

    except Exception as e:
        logging.error(f"Failed to update player info: {e}", exc_info=True)


def _update_league_scoring_settings(yq, cursor):
    """
    Writes the leagues scoring settings

    Args:
        yq: An authenticated yfpy query object.
        cursor: A sqlite3 cursor object.
    """
    logging.info("Fetching league scoring...")
    try:
        settings = yq.get_league_settings()
        playoff_start_week = settings.playoff_start_week
        scoring_settings_to_insert = []
        for stat_item in settings.stat_categories.stats:
            stat_details = stat_item
            category = stat_details.display_name
            scoring_group = stat_details.group
            stat_id = stat_details.stat_id


            scoring_settings_to_insert.append((stat_id, category, scoring_group))

        sql = "INSERT OR IGNORE INTO scoring (stat_id, category, scoring_group) VALUES (?, ?, ?)"
        cursor.executemany(sql, scoring_settings_to_insert)
        logging.info(f"Successfully inserted or ignored data for {len(scoring_settings_to_insert)} categories.")
        return playoff_start_week
    except Exception as e:
        logging.error(f"Failed to update scoring info: {e}", exc_info=True)
        return None


def _update_fantasy_weeks(yq, cursor, league_key):
    """
    Fetches the weekly struture for the league

    Args:
        yq: An authenticated yfpy query object.
        cursor: A sqlite3 cursor object.
    """
    logging.info("Fetching fantasy weeks...")
    try:
        game_id_end_pos = league_key.index('.')
        game_id = league_key[:game_id_end_pos]
        weeks = yq.get_game_weeks_by_game_id(game_id)

        weeks_to_insert = []
        for gameweek in weeks:
            week_num = gameweek.week
            start_date = gameweek.start
            end_date = gameweek.end
            weeks_to_insert.append((week_num, start_date, end_date))

        sql = "INSERT OR IGNORE INTO weeks (week_num, start_date, end_date) VALUES (?, ?, ?)"
        cursor.executemany(sql, weeks_to_insert)
        logging.info(f"Successfully inserted or ignored data for {len(weeks_to_insert)} weeks.")
    except Exception as e:
        logging.error(f"Failed to update week info: {e}", exc_info=True)


def _update_league_matchups(yq, cursor, playoff_start_week):
    """
    Writes the leagues matchups

    Args:
        yq: An authenticated yfpy query object.
        cursor: A sqlite3 cursor object.
    """
    logging.info("Fetching league matchups...")
    try:
        if not playoff_start_week:
            logging.error("Cannot fetch matchups without playoff_start_week.")
            return

        last_reg_season_week = playoff_start_week-1
        start_week = 1
        matchup_data_to_insert = []

        while start_week <= last_reg_season_week:
            matchups = yq.get_league_matchups_by_week(start_week)
            for matchup in matchups:
                matchups_for_week = []
                for team_item in matchup.teams:
                    team_block = team_item
                    team_name = team_block.name
                    matchups_for_week.append(team_name)
                matchups_for_week.insert(0,start_week)
                matchup_data_to_insert.append(matchups_for_week)
            start_week += 1



        sql = "INSERT OR IGNORE INTO matchups (week, team1, team2) VALUES (?, ?, ?)"
        cursor.executemany(sql, matchup_data_to_insert)
        logging.info(f"Successfully inserted or ignored data for {len(matchup_data_to_insert)} matchups.")
    except Exception as e:
        logging.error(f"Failed to update matchup info: {e}", exc_info=True)


def _update_current_rosters(yq, cursor, conn, num_teams):
    """
    Writes each team's current roster to the database.

    Args:
        yq: An authenticated yfpy query object.
        cursor: A sqlite3 cursor object.
    """
    logging.info("Fetching current roster info...")
    try:
        logging.info("Clearing existing data from rosters table.")
        cursor.execute("DELETE FROM rosters")
        conn.commit()
    except Exception as e:
        logging.error("Failed to clear rosters table.", exc_info=True)
        conn.rollback()

    try:
        roster_data_to_insert = []

        MAX_PLAYERS = 29

        for team_id in range(1, num_teams + 1):
            players = yq.get_team_roster_player_info_by_date(team_id, date.today().isoformat())
            player_ids = [player.player_id for player in players][:MAX_PLAYERS]
            padded_player_ids = player_ids + [None] * (MAX_PLAYERS - len(player_ids))
            row_data = [team_id] + padded_player_ids
            roster_data_to_insert.append(row_data)

        placeholders = ', '.join(['?'] * (MAX_PLAYERS + 1))
        cols = ", ".join([f"p{i}" for i in range(1, MAX_PLAYERS + 1)])
        sql = f"""INSERT INTO rosters (
                 team_id, {cols})
                 VALUES ({placeholders})
        """
        cursor.executemany(sql, roster_data_to_insert)
        conn.commit()

        logging.info(f"Successfully inserted data for {len(roster_data_to_insert)} teams.")
    except Exception as e:
        logging.error(f"Failed to update roster info: {e}", exc_info=True)

def _update_free_agents(lg, conn):
    """
    Writes all current free agents to free agent table
    """
    logging.info("Fetching free agent info...")
    cursor = conn.cursor()
    try:
        logging.info("Clearing existing data from free_agents table.")
        cursor.execute("DELETE FROM free_agents")
        conn.commit()
    except Exception as e:
        logging.error("Failed to clear free_agents table.", exc_info=True)
        conn.rollback()
        return

    free_agents_to_insert = []
    for pos in ['C', 'LW', 'RW', 'D', 'G']:
        try:
            logging.info(f"Fetching free agents for position: {pos}")
            fas = lg.free_agents(pos)
            for player in fas:
                player_id = player['player_id']
                free_agents_to_insert.append((player_id, 'FA'))
        except Exception as e:
            logging.error(f"Could not fetch FAs for position {pos}: {e}")

    sql = "INSERT OR IGNORE INTO free_agents (player_id, status) VALUES (?, ?)"
    cursor.executemany(sql, free_agents_to_insert)
    conn.commit()
    logging.info(f"Successfully inserted data for {len(free_agents_to_insert)} free agents.")


def _update_waivers(lg, conn):
    """
    Writes all current waiver players to waiver_players table
    """
    logging.info("Fetching waiver player info...")
    cursor = conn.cursor()
    try:
        logging.info("Clearing existing data from waiver_players table.")
        cursor.execute("DELETE FROM waiver_players")
        conn.commit()
    except Exception as e:
        logging.error("Failed to clear waiver_players table.", exc_info=True)
        conn.rollback()
        return

    waiver_players_to_insert = []
    try:
        logging.info(f"Fetching all waiver players")
        wvp = lg.waivers()
        for player in wvp:
            player_id = player['player_id']
            waiver_players_to_insert.append((player_id, 'W'))
    except Exception as e:
        logging.error(f"Could not fetch waiver players: {e}")

    sql = "INSERT OR IGNORE INTO waiver_players (player_id, status) VALUES (?, ?)"
    cursor.executemany(sql, waiver_players_to_insert)
    conn.commit()
    logging.info(f"Successfully inserted data for {len(waiver_players_to_insert)} waiver players.")


def _update_rostered_players(lg, conn):
    """
    Writes all currently rostered players to rostered_players table
    """
    logging.info("Fetching rostered player info...")
    cursor = conn.cursor()
    try:
        logging.info("Clearing existing data from rostered_players table.")
        cursor.execute("DELETE FROM rostered_players")
        conn.commit()
    except Exception as e:
        logging.error("Failed to clear rostered_players table.", exc_info=True)
        conn.rollback()
        return

    rostered_players_to_insert = []
    try:
        logging.info(f"Fetching all rostered players")
        tkp = lg.taken_players()
        for player in tkp:
            player_id = player['player_id']
            rostered_players_to_insert.append((player_id, 'R'))
    except Exception as e:
        logging.error(f"Could not fetch rostered players: {e}")

    sql = "INSERT OR IGNORE INTO rostered_players (player_id, status) VALUES (?, ?)"
    cursor.executemany(sql, rostered_players_to_insert)
    conn.commit()
    logging.info(f"Successfully inserted data for {len(rostered_players_to_insert)} rostered players.")


def update_league_db(yq, lg, league_id, data_dir, capture_lineups=False):
    """
    Creates or updates the league-specific SQLite database by calling
    individual query and update functions.

    Args:
        yq: An authenticated yfpy.query.YahooFantasySportsQuery object.
        lg: An authenticated yahoo_fantasy_api.league.League object.
        league_id: The ID of the fantasy league.
        data_dir: The directory where the database file should be stored.
        capture_lineups: Boolean to determine if daily lineups should be captured.

    Returns:
        A dictionary with the success status and database info, or an error message.
    """
    try:
        logging.info(f"Starting DB update for league {league_id}...")

        logging.info("Fetching league metadata to determine filename...")
        league_metadata = yq.get_league_metadata()

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

        # --- yfpy API Call Functions ---
        _create_tables(cursor)
        _update_league_info(yq, cursor, league_id, sanitized_name, league_metadata)
        _update_teams_info(yq, cursor)
        if capture_lineups:
            _update_daily_lineups(yq, cursor, conn, league_metadata.num_teams, league_metadata.start_date)
        #_update_player_id(yq, cursor)
        playoff_start_week = _update_league_scoring_settings(yq, cursor)
        _update_fantasy_weeks(yq, cursor, league_metadata.league_key)
        _update_league_matchups(yq, cursor, playoff_start_week)
        _update_current_rosters(yq, cursor, conn, league_metadata.num_teams)

        # --- yfa API Call Functions ---
        _update_free_agents(lg, conn)
        _update_waivers(lg, conn)
        _update_rostered_players(lg, conn)


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
