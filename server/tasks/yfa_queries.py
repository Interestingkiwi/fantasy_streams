import yahoo_fantasy_api as yfa
from yahoo_oauth import OAuth2
import sqlite3
import logging

class YahooFantasyApiData:
    def __init__(self, con, league_id):
        self.con = con
        self.league_id = league_id
        # Authentication is handled automatically by the library
        # It looks for 'private.json' and 'token_cache.json' in the CWD
        try:
            self.oauth = OAuth2(None, None, from_file='private.json')
            if not self.oauth.token_is_valid():
                self.oauth.refresh_access_token()
        except Exception as e:
            logging.error(f"yfa_queries: Failed to authenticate: {e}", exc_info=True)
            raise  # Re-raise the exception to stop the process

    def get_matchups(self):
        """
        Fetches all weekly matchups for the league and inserts them into the database.
        """
        try:
            gm = yfa.Game(self.oauth, 'nhl')
            lg = gm.to_league(self.league_id)

            # Fetch all matchups for the entire season
            matchups = lg.matchups()

            cursor = self.con.cursor()

            for week, matchup_data in matchups['fantasy_content']['league'][1]['scoreboard']['0']['matchups'].items():
                if not week.isdigit():
                    continue  # Skip non-week entries like 'count'

                for i in range(matchup_data['count']):
                    matchup_details = matchup_data[str(i)]['matchup']

                    # Ensure teams data exists and is in the expected format
                    if '0' not in matchup_details or 'teams' not in matchup_details['0'] or matchup_details['0']['teams']['count'] < 2:
                        continue # Skip if matchup doesn't have at least two teams

                    team1_name = matchup_details['0']['teams']['0']['team'][0][2]['name']
                    team2_name = matchup_details['0']['teams']['1']['team'][0][2]['name']

                    # Insert the matchup into the database
                    cursor.execute("INSERT INTO matchups (week, team1, team2) VALUES (?, ?, ?)",
                                   (int(week), team1_name, team2_name))

            self.con.commit()
            logging.info(f"Successfully inserted all matchups for league {self.league_id}.")

        except Exception as e:
            logging.error(f"An error occurred while fetching matchups: {e}", exc_info=True)
            self.con.rollback() # Rollback any partial inserts
