"""
Queries to update fantasy hockey optimizer database

Author: Jason Druckenmiller
Date: 10/11/2025
Updated: 10/11/2025
"""

import logging
import os
import pathlib
import sqlite3
import unicodedata
import re
from datetime import datetime, timedelta, date
from yfpy.query import YahooFantasySportsQuery
from yahoo_oauth import OAuth2
import time


logger = logging.getLogger(__name__)


class YahooDataFetcher:
    def __init__(
        self, con, league_id, *, auth_data=None
    ):
        self.con = con
        self.league_id = league_id
        self._auth_data = auth_data
        self.yq = None
        self._refresh_yahoo_query()


    def _refresh_yahoo_query(self):
        logger.debug("Refreshing Yahoo query")

        if not self._auth_data:
            raise ValueError("Authentication data was not provided to YahooDataFetcher.")

        # Manually handle token refresh to preserve the non-standard 'guid' field.
        token_data = self._auth_data
        expires_in = token_data.get('expires_in', 3600)
        token_time = token_data.get('token_time', 0)

        if time.time() > token_time + expires_in - 300:
            logger.debug("yfpy_queries: Token is expired or nearing expiration, refreshing manually.")
            try:
                # Preserve the guid before refreshing.
                original_guid = token_data.get('guid') or token_data.get('xoauth_yahoo_guid')

                consumer_key = token_data.get('consumer_key')
                consumer_secret = token_data.get('consumer_secret')

                if not consumer_key or not consumer_secret:
                    logger.error("Consumer key/secret not found in auth_data for token refresh.")
                    raise ValueError("Missing consumer key/secret for token refresh.")

                # Instantiate OAuth2 directly with keys, not from a file.
                oauth = OAuth2(consumer_key, consumer_secret, **token_data)
                oauth.refresh_access_token()

                new_token_data = oauth.token_data
                if original_guid and 'guid' not in new_token_data:
                    new_token_data['guid'] = original_guid

                # The refresh process doesn't retain consumer keys in the new dict, so re-add them.
                new_token_data['consumer_key'] = consumer_key
                new_token_data['consumer_secret'] = consumer_secret

                self._auth_data = new_token_data  # Use the newly refreshed token data.
                logger.debug("yfpy_queries: Token refreshed successfully.")

            except Exception as e:
                logger.error(f"Failed to refresh token within yfpy_queries: {e}", exc_info=True)
                raise

        # The game_id is needed for some queries.
        # We perform an initial query to get the game_id for the league.
        yq_init = YahooFantasySportsQuery(
            league_id=self.league_id,
            game_code="nhl",
            yahoo_access_token_json=self._auth_data
        )

        game_info = yq_init.get_current_game_info()
        game_id = game_info.game_id

        # Now we create the final query object with the game_id,
        # reusing the (potentially refreshed) full authentication data.
        self.yq = YahooFantasySportsQuery(
            league_id=self.league_id,
            game_code="nhl",
            game_id=game_id,
            yahoo_access_token_json=self._auth_data
        )


    def fetch_all_data(self):
        """
        Fetches basic league data, plus contains all additional data calls
        within function
        """
        logger.info("Fetching league info...")

        # 1. Make an API call
        league_metadata = self.yq.get_league_metadata()

        # 2. Extract the data you want
        league_name = league_metadata.name
        self.num_teams = league_metadata.num_teams
        self.start_date = league_metadata.start_date
        self.end_date = league_metadata.end_date
        self.league_key = league_metadata.league_key

        # 3. Define the data to be inserted
        data_to_insert = (self.league_id, league_name, self.num_teams, self.start_date)

        # 4. Insert the data into the database
        sql = "INSERT OR IGNORE INTO league (league_id, name, num_teams, start_date) VALUES (?, ?, ?, ?)"
        self.con.execute(sql, data_to_insert)
        self.con.commit()

        logger.info(f"Successfully inserted or ignored league info for '{league_name}'.")

        self.fetch_player_id()
        self.fetch_league_scoring_settings()
        self.fetch_and_store_fantasy_weeks()
        self.fetch_league_matchups()
        self.fetch_current_rosters()

        # After all fetches are successful, update the metadata
        logger.info("Updating last run date metadata.")
        today = date.today().isoformat()
        # Use INSERT OR REPLACE to handle both creation and update of the metadata key
        sql_meta = "INSERT OR REPLACE INTO metadata (key_, value) VALUES (?, ?)"
        self.con.execute(sql_meta, ('last_run_date', today))
        self.con.commit()


    def fetch_player_id(self):
        """
        Writes player name, normalized player name, team, and yahoo id to players
        table for all players in the league
        """
        logger.info("Fetching player info...")

        players = self.yq.get_league_players()

        TEAM_TRICODE_MAP = {
            "TB": "TBL",
            "NJ": "NJD",
            "SJ": "SJS",
            "LA": "LAK",
            "MON": "MTL",
            "WAS": "WSH"
        }

        player_data_to_insert = []
        for player in players:
            player_id = player.player_id
            player_name = player.name.full
            nfkd_form = unicodedata.normalize('NFKD', player_name.lower())
            ascii_name = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
            player_name_normalized = re.sub(r'[^a-z0-9]', '', ascii_name)
            player_team_abbr = player.editorial_team_abbr.upper()
            player_team = TEAM_TRICODE_MAP.get(player_team_abbr, player_team_abbr)

            player_data_to_insert.append((player_id, player_name, player_team, player_name_normalized))

        sql = "INSERT OR IGNORE INTO players (player_id, player_name, player_team, player_name_normalized) VALUES (?, ?, ?, ?)"
        self.con.executemany(sql, player_data_to_insert)
        self.con.commit()

        logger.info(f"Successfully inserted or ignored data for {len(player_data_to_insert)} players.")


    def fetch_league_scoring_settings(self):
        """
        Writes the leagues scoring settings
        """
        logger.info("Fetching league scoring...")
        settings = self.yq.get_league_settings()
        self.playoff_start_week = settings.playoff_start_week
        scoring_settings_to_insert = []
        for stat_item in settings.stat_categories.stats:
            stat_details = stat_item
            category = stat_details.display_name
            scoring_group = stat_details.group
            stat_id = stat_details.stat_id


            scoring_settings_to_insert.append((stat_id, category, scoring_group))

        sql = "INSERT OR IGNORE INTO scoring (stat_id, category, scoring_group) VALUES (?, ?, ?)"
        self.con.executemany(sql, scoring_settings_to_insert)
        self.con.commit()

        logger.info(f"Successfully inserted or ignored data for {len(scoring_settings_to_insert)} categories.")


    def fetch_and_store_fantasy_weeks(self):
        """
        Fetches the weekly struture for the league
        """
        logger.info("Fetching fantasy weeks...")
        game_id_end_pos = self.league_key.index('.')
        game_id = self.league_key[:game_id_end_pos]
        weeks = self.yq.get_game_weeks_by_game_id(game_id)

        weeks_to_insert = []
        for gameweek in weeks:
            week_num = gameweek.week
            start_date = gameweek.start
            end_date = gameweek.end
            weeks_to_insert.append((week_num, start_date, end_date))

        sql = "INSERT OR IGNORE INTO weeks (week_num, start_date, end_date) VALUES (?, ?, ?)"
        self.con.executemany(sql, weeks_to_insert)
        self.con.commit()

        logger.info(f"Successfully inserted or ignored data for {len(weeks_to_insert)} weeks.")


    def fetch_league_matchups(self):
        """
        Writes the leagues matchups
        """
        logger.info("Fetching league matchups...")
        last_reg_season_week = self.playoff_start_week-1
        start_week = 1
        matchup_data_to_insert = []

        while start_week <= last_reg_season_week:
            matchups = self.yq.get_league_matchups_by_week(start_week)
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
        self.con.executemany(sql, matchup_data_to_insert)
        self.con.commit()

        logger.info(f"Successfully inserted or ignored data for {len(matchup_data_to_insert)} matchups.")


    def fetch_current_rosters(self):
        """
        Writes each team's current roster to the database.
        """
        logger.info("Fetching current roster info...")
        try:
            logging.info("Clearing existing data from rosters table.")
            cursor = self.con.cursor()
            cursor.execute("DELETE FROM rosters")
            self.con.commit()
        except Exception as e:
            logging.error("Failed to clear rosters table.", exc_info=True)
            self.con.rollback()

        roster_data_to_insert = []

        MAX_PLAYERS = 19

        for team_id in range(1, self.num_teams + 1):
            players = self.yq.get_team_roster_player_info_by_date(team_id, date.today().isoformat())
            player_ids = [player.player_id for player in players][:MAX_PLAYERS]
            padded_player_ids = player_ids + [None] * (MAX_PLAYERS - len(player_ids))
            row_data = [team_id] + padded_player_ids
            roster_data_to_insert.append(row_data)
        sql = """INSERT INTO rosters (
                 team_id, p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12, p13, p14,
                 p15, p16, p17, p18, p19)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.con.executemany(sql, roster_data_to_insert)
        self.con.commit()

        logger.info(f"Successfully inserted data for {len(roster_data_to_insert)} teams.")
