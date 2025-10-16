import argparse
import sqlite3
import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add the parent directory of 'tasks' to the Python path
# This allows us to import yfpy_queries and yfa_queries
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tasks')))

try:
    from yfpy_queries import YahooDataFetcher
    from yfa_queries import YahooFantasyApiData
except ImportError as e:
    logging.critical(f"Failed to import data fetcher modules: {e}")
    sys.exit(1)

def run(league_id, db_path):
    """
    Initializes the fantasy sports database for a given league.
    """
    try:
        logging.info(f"Database initialization started for league_id: {league_id} at path: {db_path}")

        # Connect to the SQLite database. It will be created if it doesn't exist.
        con = sqlite3.connect(db_path)

        # Read the schema.sql file and execute it to create the database tables.
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        if not os.path.exists(schema_path):
            logging.critical("schema.sql not found!")
            con.close()
            return

        with open(schema_path) as f:
            con.executescript(f.read())
        logging.info("Custom DB tables created from schema.sql")

        # --- Data Fetching ---
        # The authentication should be handled automatically by the libraries
        # finding private.json and token_cache.json in the current working directory.

        # Initialize and run yfpy queries to populate player and team data.
        logging.info("--- Running yfpy queries ---")
        fetcher = YahooDataFetcher(con, league_id)
        fetcher.fetch_all_data()
        logging.info("--- yfpy queries completed ---")

        # Initialize and run yfa_queries to populate matchup data.
        logging.info("--- Running yfa queries ---")
        yfa_data = YahooFantasyApiData(con, league_id)
        yfa_data.get_matchups()
        logging.info("--- yfa queries completed ---")

    except Exception as e:
        logging.critical(f"Fatal error during DB initialization. Aborting. Error: {e}", exc_info=True)
        # Optionally, clean up the partially created DB file on error
        if con:
            con.close()
        if os.path.exists(db_path):
            os.remove(db_path)
        sys.exit(1) # Exit with an error code
    finally:
        # Ensure the database connection is closed.
        if con:
            con.close()
            logging.info(f"Database connection closed. Initialization for league {league_id} is complete.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Initialize the fantasy sports database.")
    parser.add_argument("league_id", type=str, help="The Yahoo Fantasy Sports league ID.")
    args = parser.parse_args()

    # Determine the database path based on the script's location
    db_dir = os.path.dirname(os.path.abspath(__file__))
    db_filename = f"yahoo-nhl-{args.league_id}-custom.db"
    full_db_path = os.path.join(db_dir, db_filename)

    run(args.league_id, full_db_path)
