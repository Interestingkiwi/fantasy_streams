from yfpy import Data
from yfpy.query import YahooFantasySportsQuery
import sqlite3
import logging

class YahooDataFetcher:
    def __init__(self, con, league_id):
        self.con = con
        self.league_id = league_id
        # Authentication is handled automatically by the library
        # It looks for 'private.json' and 'token_cache.json' in the CWD
        try:
            self.yahoo_query = YahooFantasySportsQuery(
                auth_dir=".",  # Look in the current directory
                league_id=self.league_id,
                game_code="nhl"
            )
        except Exception as e:
            logging.error(f"yfpy_queries: Failed to initialize YahooFantasySportsQuery: {e}", exc_info=True)
            raise # Re-raise the exception to stop the process

    def _insert_data(self, table_name, data_list, column_mapping):
        """
        A generic method to insert a list of dictionaries into a specified table.

        :param table_name: Name of the database table.
        :param data_list: A list of dictionaries, where each dictionary represents a row.
        :param column_mapping: A dictionary mapping dictionary keys to database column names.
        """
        if not data_list:
            logging.warning(f"No data provided for table {table_name}. Skipping insert.")
            return

        cursor = self.con.cursor()

        # Prepare column names and placeholders for the SQL statement
        db_columns = list(column_mapping.values())
        placeholders = ', '.join(['?'] * len(db_columns))

        # Prepare the list of tuples to be inserted
        rows_to_insert = []
        for item in data_list:
            row = []
            for dict_key in column_mapping.keys():
                # Use .get() to handle potentially missing keys gracefully
                value = item.get(dict_key)
                # Convert list values to a string representation if necessary
                if isinstance(value, list):
                    value = ', '.join(map(str, value))
                row.append(value)
            rows_to_insert.append(tuple(row))

        try:
            sql = f"INSERT INTO {table_name} ({', '.join(db_columns)}) VALUES ({placeholders})"
            cursor.executemany(sql, rows_to_insert)
            self.con.commit()
            logging.info(f"Successfully inserted {len(rows_to_insert)} rows into {table_name}.")
        except sqlite3.Error as e:
            logging.error(f"Database error during insert into {table_name}: {e}")
            self.con.rollback()

    def fetch_all_data(self):
        """
        Fetch all required data from the Yahoo Fantasy API and insert it into the database.
        """
        # Fetch teams and insert into 'teams' table
        teams_data = self.yahoo_query.get_league_teams()
        team_mapping = {
            "team_key": "team_key",
            "team_id": "team_id",
            "name": "team_name"
        }
        self._insert_data("teams", teams_data, team_mapping)

        # Fetch players and insert into 'players' table
        players_data = self.yahoo_query.get_league_players()
        player_mapping = {
            "player_key": "player_key",
            "player_id": "player_id",
            "first": "first_name",
            "last": "last_name",
            "full": "full_name",
            "editorial_team_abbr": "team_abbr",
            "uniform_number": "jersey",
            "eligible_positions": "positions"
        }
        self._insert_data("players", players_data, player_mapping)
