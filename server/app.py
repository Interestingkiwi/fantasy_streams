import os
import json
import sqlite3
import tempfile
import shutil
from pathlib import Path
from flask import Flask, render_template, request, send_file, jsonify

from yfpy import YahooFantasySportsQuery
import queries  # Import the queries from queries.py

app = Flask(__name__)

# The main page that shows the user interface
@app.route('/')
def index():
    """Renders the main HTML page."""
    return render_template('index.html')

# The endpoint that handles the database generation
@app.route('/generate', methods=['POST'])
def generate_db():
    """
    Handles the form submission, generates the database, and returns it for download.
    """
    data = request.get_json()
    private_json_content = data.get('privateJsonContent')
    league_id = data.get('leagueId')

    if not private_json_content or not league_id:
        return jsonify({"error": "Missing private.json content or League ID."}), 400

    # Create temporary directories to securely handle user credentials and the db file
    temp_dir = tempfile.mkdtemp()
    auth_dir = Path(temp_dir) / "auth"
    db_path = Path(temp_dir) / f"yahoo-nhl-{league_id}.db"
    os.makedirs(auth_dir)

    try:
        # Write the user-provided credentials to a temporary private.json file
        with open(auth_dir / "private.json", "w") as f:
            f.write(private_json_content)

        # --- Start of yfpy data fetching logic ---

        # Authenticate with yfpy using the temporary auth directory
        session = YahooFantasySportsQuery(auth_dir=str(auth_dir), league_id=str(league_id))

        # Connect to the SQLite database and create the schema
        con = sqlite3.connect(db_path)
        with open("schema.sql") as schema_file:
            con.executescript(schema_file.read())
        print("Database schema created.")

        # Fetch all necessary data from the Yahoo Fantasy API
        game = session.get_game()
        queries.insert_game(con, game)
        print("Fetched and stored game data.")

        league = session.get_league()
        queries.insert_leagues(con, [league])
        print(f"Fetched and stored league data for: {league.name}")

        settings = session.get_league_settings()
        queries.insert_settings(con, league.league_id, settings)
        queries.insert_stat_categories(con, league.league_id, settings.stat_categories)
        queries.insert_roster_positions(con, league.league_id, settings.roster_positions)
        print("Fetched and stored league settings.")

        teams = session.get_league_teams()
        queries.insert_teams(con, league.league_id, teams)
        print("Fetched and stored team data.")

        standings = session.get_league_standings()
        queries.insert_standings(con, league.league_id, standings)
        print("Fetched and stored standings.")

        # Fetch data for all weeks
        for week in range(1, settings.playoff_end_week + 1):
            try:
                scoreboard = session.get_league_scoreboard_by_week(week)
                queries.insert_matchups(con, league.league_id, scoreboard.matchups)
                print(f"Fetched and stored scoreboard for week {week}.")
            except Exception as e:
                print(f"Could not fetch scoreboard for week {week}: {e}")


        players = session.get_league_players()
        queries.insert_players(con, league.league_id, players)
        print(f"Fetched and stored {len(players)} players.")

        # Fetch rosters for all teams
        for team in teams:
            roster = session.get_team_roster_by_week(team.team_id, settings.current_week)
            queries.insert_rosters(con, team.team_id, settings.current_week, roster)
            print(f"Fetched and stored roster for team {team.name}.")

        transactions = session.get_league_transactions()
        queries.insert_transactions(con, league.league_id, transactions)
        print(f"Fetched and stored {len(transactions)} transactions.")

        draft_results = session.get_league_draft_results()
        queries.insert_draft_results(con, league.league_id, draft_results)
        print("Fetched and stored draft results.")

        con.close()
        print("Database generation complete.")

        # --- End of yfpy data fetching logic ---

        # Send the generated database file to the user for download
        return send_file(
            db_path,
            as_attachment=True,
            download_name=f"yahoo-nhl-{league_id}.db"
        )

    except Exception as e:
        # If anything goes wrong, return an error message
        print(f"An error occurred: {e}")
        return jsonify({"error": f"An error occurred: {e}"}), 500
    finally:
        # Clean up the temporary directory and its contents
        shutil.rmtree(temp_dir)
        print(f"Cleaned up temporary directory: {temp_dir}")


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
