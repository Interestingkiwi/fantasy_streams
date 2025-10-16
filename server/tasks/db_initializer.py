import argparse
import contextlib
import logging
import os
import sqlite3
import sys
import json

# Add the parent directory to the path to allow imports from other folders
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tasks.yfpy_queries import YahooDataFetcher
from tasks.yfa_queries import YfaDataFetcher
from tasks.finalize_db import DataProcessor


logger = logging.getLogger(__name__)

# --- Database Path Configuration ---
DATABASE_DIR = os.environ.get('DATABASE_DIR', os.path.dirname(__file__))

def run():
    """Main function to fetch data and populate the database."""
    args = _get_parsed_args(*sys.argv[1:])
    _configure_logging(True) # Always debug for background task

    # Database and schema paths
    db_path = os.path.join(DATABASE_DIR, f"yahoo-nhl-{args.league_id}-custom.db")
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    projections_db_path = os.path.join(os.path.dirname(__file__), "projections.db")

    try:
        with open(schema_path, "r") as f:
            schema = f.read()

        with _get_db_connection(db_path) as con:
            con.executescript(schema)
            con.commit()
            logger.info("Custom DB tables created from schema.sql")

            # --- Run yfpy queries ---
            logger.info("--- Running yfpy queries ---")
            # The fetcher will now find the credential files on its own
            fetcher = YahooDataFetcher(con, args.league_id)
            fetcher.fetch_all_data()

            # --- Run yfa_queries ---
            logger.info("--- Running yfa_queries ---")
            yfa_fetcher = YfaDataFetcher(con=con, league_id=args.league_id)
            yfa_fetcher.fetch_free_agents()
            yfa_fetcher.fetch_waivers()
            yfa_fetcher.fetch_rostered_players()

            # --- Run finalize_db ---
            logger.info("--- Running finalize_db ---")
            processor = DataProcessor(args.league_id, db_dir=DATABASE_DIR)
            if processor.con:
                processor.process_with_projections(projections_db_path)
                processor.close_connection()


            logger.info("Database initialization complete. Exiting...")

    except Exception:
        logger.critical("Fatal error during DB initialization. Aborting.", exc_info=True)
        # Clean up failed db file
        if os.path.exists(db_path):
            os.remove(db_path)
        sys.exit(1)


def _get_parsed_args(*args):
    parser = argparse.ArgumentParser(
        prog="db-initializer",
        description="A script to create and populate the fantasy league database.",
    )
    parser.add_argument("league_id", type=int, help="Yahoo league id to import")
    return parser.parse_args(args)


def _configure_logging(debug):
    level = logging.INFO
    if debug:
        level = logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s",
    )


@contextlib.contextmanager
def _get_db_connection(db_path):
    con = sqlite3.connect(db_path)
    try:
        yield con
    finally:
        con.close()


if __name__ == "__main__":
    run()
