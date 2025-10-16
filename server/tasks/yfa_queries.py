"""
Queries to update fantasy hockey optimizer database using yahoo_fantasy_api.

This file provides a class-based approach to fetching data from the Yahoo
Fantasy Sports API and storing it in a SQLite database.
"""

import logging
from yahoo_fantasy_api import league
from yahoo_oauth import OAuth2
import os

logger = logging.getLogger(__name__)


class YfaDataFetcher:
    """
    A class to fetch data from Yahoo Fantasy Sports and store it in a database.
    """
    def __init__(self, con, league_id):
        """
        Initializes the YfaDataFetcher.

        Args:
            con: A sqlite3 database connection object.
            league_id (str): The Yahoo Fantasy league ID.
        """
        self.con = con
        self.league_id = league_id
        # The auth file is in the project root, so we go up two directories from the current script
        self.auth_dir = os.path.join(os.path.dirname(__file__), '..', '..')
        self.lg = self._authenticate_and_get_league()

    def _authenticate_and_get_league(self):
        """
        Authenticates with Yahoo and returns a League object.

        It looks for an authentication file (private.json) in the specified
        directory. If not found, it will initiate the OAuth2 flow.
        """
        logger.debug("Authenticating with Yahoo and getting league object...")
        try:
            # The OAuth2 object will look for private.json in the specified auth_dir
            sc = OAuth2(None, None, from_file=os.path.join(self.auth_dir, "private.json"))
            lg = league.League(sc, self.league_id)
            logger.info("Authentication successful with yfa.")
            return lg
        except Exception as e:
            logger.error(f"Failed to authenticate or get league with yfa: {e}")
            raise

    def fetch_free_agents(self):
        """
        Writes all current free agents to free agent table
        """
        logging.info("Fetching free agent info...")

        try:
            logging.info("Clearing existing data from free_agents table.")
            cursor = self.con.cursor()
            cursor.execute("DELETE FROM free_agents")
            self.con.commit()
        except Exception as e:
            logging.error("Failed to clear free_agents table.", exc_info=True)
            self.con.rollback()

        free_agents_to_insert = []
        for pos in ['C', 'LW', 'RW', 'D', 'G']:
            try:
                print(f"Fetching free agents for position: {pos}")
                fas = self.lg.free_agents(pos)
                for player in fas:
                    player_id = player['player_id']
                    free_agents_to_insert.append((player_id, 'FA'))
            except Exception as e:
                print(f"Could not fetch FAs for position {pos}: {e}")

        sql = "INSERT OR IGNORE INTO free_agents (player_id, status) VALUES (?, ?)"
        self.con.executemany(sql, free_agents_to_insert)
        self.con.commit()

        logger.info(f"Successfully inserted data for {len(free_agents_to_insert)} players into free_agents.")


    def fetch_waivers(self):
        """
        Writes all current waiver players to waiver_players table
        """
        logging.info("Fetching waiver info...")

        try:
            logging.info("Clearing existing data from waiver_players table.")
            cursor = self.con.cursor()
            cursor.execute("DELETE FROM waiver_players")
            self.con.commit()
        except Exception as e:
            logging.error("Failed to clear waiver_players table.", exc_info=True)
            self.con.rollback()

        waiver_players_to_insert = []
        try:
            print(f"Fetching all waiver players")
            wvp = self.lg.waivers()
            for player in wvp:
                player_id = player['player_id']
                waiver_players_to_insert.append((player_id, 'W'))
        except Exception as e:
            print(f"Could not fetch waiver players: {e}")

        sql = "INSERT OR IGNORE INTO waiver_players (player_id, status) VALUES (?, ?)"
        self.con.executemany(sql, waiver_players_to_insert)
        self.con.commit()

        logger.info(f"Successfully inserted data for {len(waiver_players_to_insert)} players into waiver_players.")


    def fetch_rostered_players(self):
        """
        Writes all currently rostered players to rostered_players table
        """
        logging.info("Fetching rostered player info...")

        try:
            logging.info("Clearing existing data from rostered_players table.")
            cursor = self.con.cursor()
            cursor.execute("DELETE FROM rostered_players")
            self.con.commit()
        except Exception as e:
            logging.error("Failed to clear rostered_players table.", exc_info=True)
            self.con.rollback()

        rostered_players_to_insert = []
        try:
            print(f"Fetching all rostered players")
            tkp = self.lg.taken_players()
            for player in tkp:
                player_id = player['player_id']
                rostered_players_to_insert.append((player_id, 'R'))
        except Exception as e:
            print(f"Could not fetch rostered players: {e}")

        sql = "INSERT OR IGNORE INTO rostered_players (player_id, status) VALUES (?, ?)"
        self.con.executemany(sql, rostered_players_to_insert)
        self.con.commit()

        logger.info(f"Successfully inserted data for {len(rostered_players_to_insert)} players into rostered_players.")
