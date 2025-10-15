"""
Processes and joins data in the fantasy hockey database.

This script is for running SQL queries on the existing database to combine
API-pulled data with static projection data from other sources. No API calls
are made from this file.

Author: Jason Druckenmiller
Date: 10/13/2025
"""

import sqlite3
import logging
import os
import argparse
import re
import ast

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

class DataProcessor:
    def __init__(self, league_id, db_dir=None):
        self.league_id = league_id
        # If no directory is provided, default to the current script's directory
        if db_dir is None:
            db_dir = os.path.dirname(__file__)
        self.db_path = os.path.join(db_dir, f"yahoo-nhl-{self.league_id}-custom.db")
        self.con = self.get_db_connection()

    def get_db_connection(self):
        """Gets a connection to the SQLite database."""
        if not os.path.exists(self.db_path):
            logging.error(f"Database not found at {self.db_path}. Please run the fetcher first.")
            return None
        return sqlite3.connect(self.db_path)

    def close_connection(self):
        """Closes the database connection if it's open."""
        if self.con:
            self.con.close()
            logging.info("Database connection closed.")

    def process_with_projections(self, projections_db_path):
        """
        Attaches the projections DB and runs all related processing functions
        (imports and joins) within a single transaction.
        """
        if not self.con:
            logging.error("No database connection.")
            return

        if not os.path.exists(projections_db_path):
            logging.error(f"Projections database not found at: {projections_db_path}")
            return

        absolute_proj_path = os.path.abspath(projections_db_path)
        logging.info(f"Found projections DB. Absolute path: {absolute_proj_path}")

        attached_successfully = False
        try:
            logging.info(f"Attaching projections database...")
            self.con.execute(f"ATTACH DATABASE '{absolute_proj_path}' AS projections")
            attached_successfully = True
            cursor = self.con.cursor()

            cursor.execute("SELECT name FROM projections.sqlite_master WHERE type='table';")
            tables_in_proj_db = [row[0] for row in cursor.fetchall()]
            logging.info(f"Tables found in attached projections database: {tables_in_proj_db}")

            logging.info("Importing static tables (off_days, schedule, team_schedules)...")
            tables_to_import = ['off_days', 'schedule', 'team_schedules', 'fantasy_weeks']
            for table in tables_to_import:
                logging.info(f"Importing table: {table}")
                cursor.execute(f"DROP TABLE IF EXISTS main.{table}")
                cursor.execute(f"CREATE TABLE main.{table} AS SELECT * FROM projections.{table}")

            logging.info("Joining player data with projections...")
            cursor.execute("DROP TABLE IF EXISTS main.joined_player_stats")
            cursor.execute("""
                CREATE TABLE main.joined_player_stats AS
                SELECT
                    p.player_id,
                    p.player_name,
                    p.player_team,
                    CASE
                        WHEN fa.player_id IS NOT NULL THEN 'F'
                        WHEN w.player_id IS NOT NULL THEN 'W'
                        WHEN r.player_id IS NOT NULL THEN 'R'
                        ELSE 'Unk'
                    END AS availability_status,
                    proj.*
                FROM main.players AS p
                LEFT JOIN projections.projections AS proj
                ON p.player_name_normalized = proj.normalized_name
                LEFT JOIN main.free_agents AS fa
                ON p.player_id = fa.player_id
                LEFT JOIN main.waiver_players AS w
                ON p.player_id = w.player_id
                LEFT JOIN main.rostered_players AS r
                ON p.player_id = r.player_id;
            """)

            self.con.commit()
            logging.info("Successfully imported static tables and joined player projections.")

            # Now create the new tables.
            self.create_additional_tables()


        except sqlite3.Error as e:
            logging.error(f"An error occurred while processing with projections DB: {e}")
            logging.info("Rolling back any pending changes.")
            self.con.rollback()
        finally:
            if attached_successfully:
                logging.info("Detaching projections database.")
                self.con.execute("DETACH DATABASE projections")

    def create_additional_tables(self):
        """Create new tables that will be used later."""
        if not self.con:
            logging.error("No database connection.")
            return

        logging.info("Creating additional analysis tables...")
        cursor = self.con.cursor()

        try:
            # Create skater_values table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS skater_values AS
                SELECT
                    player_name,
                    positions,
                    playerid,
                    "g", "a", "pts", "plus_minus", "sog", "ppg", "ppa", "ppp", "shg",
                    "sha", "shp", "hit", "blk", "pim", "fow", "fol", "g_cat_rank",
                    "a_cat_rank", "pts_cat_rank", "plus_minus_cat_rank", "sog_cat_rank",
                    "ppg_cat_rank", "ppa_cat_rank", "ppp_cat_rank", "shg_cat_rank",
                    "sha_cat_rank", "shp_cat_rank", "hit_cat_rank", "blk_cat_rank",
                    "pim_cat_rank", "fow_cat_rank", "fol_cat_rank"
                FROM joined_player_stats
                WHERE positions NOT LIKE '%G%';
            """)

            # Create goalie_values table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS goalie_values AS
                SELECT
                    player_name,
                    positions,
                    playerid,
                    "gs", "w", "l", "ga", "sv", "so", "gpts", "qs", "rbs",
                    "gs_cat_rank", "w_cat_rank", "l_cat_rank", "ga_cat_rank",
                    "sv_cat_rank", "so_cat_rank", "gpts_cat_rank", "qs_cat_rank",
                    "rbs_cat_rank"
                FROM joined_player_stats
                WHERE positions LIKE '%G%';
            """)

            self.con.commit()
            logging.info("Successfully created skater_values and goalie_values tables.")
        except sqlite3.Error as e:
            logging.error(f"An error occurred while creating additional tables: {e}")
            self.con.rollback()

    def parse_and_store_player_stats(self):
        # This function is not required by the db_initializer flow for now.
        pass
