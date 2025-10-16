# This file contains all the functions to insert data into the SQLite database.
# It's imported by the main app.py file.

def insert_game(con, game):
    with con:
        con.execute(
            "INSERT OR REPLACE INTO game (game_key, game_id, name, code, type, url, season, is_registration_over, is_game_over, is_offseason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (game.game_key, game.game_id, game.name, game.code, game.type, game.url, game.season, game.is_registration_over, game.is_game_over, game.is_offseason)
        )


def insert_leagues(con, leagues):
    with con:
        con.executemany(
            "INSERT OR REPLACE INTO leagues (league_key, league_id, name, url, draft_status, num_teams, current_week, end_week) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(league.league_key, league.league_id, league.name, league.url, league.draft_status, league.num_teams, league.current_week, league.end_week) for league in leagues]
        )


def insert_settings(con, league_id, settings):
    with con:
        con.execute(
            "INSERT OR REPLACE INTO settings (league_id, name, draft_type, is_auction_draft, scoring_type, uses_faab, waiver_type, waiver_rule, faab_balance, draft_time, draft_pick_time, post_draft_players, max_teams, waiver_time, trade_end_date, trade_ratify_type, trade_reject_time, player_pool, cant_cut_list, draft_together, can_trade_draft_picks, send_email_notifications, has_playoff_consolation_games, has_playoff_reseeding, playoff_start_week, playoff_end_week) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (league_id, settings.name, settings.draft_type, settings.is_auction_draft, settings.scoring_type, settings.uses_faab, settings.waiver_type, settings.waiver_rule, settings.faab_balance, settings.draft_time, settings.draft_pick_time, settings.post_draft_players, settings.max_teams, settings.waiver_time, settings.trade_end_date, settings.trade_ratify_type, settings.trade_reject_time, settings.player_pool, settings.cant_cut_list, settings.draft_together, settings.can_trade_draft_picks, settings.send_email_notifications, settings.has_playoff_consolation_games, settings.has_playoff_reseeding, settings.playoff_start_week, settings.playoff_end_week)
        )


def insert_stat_categories(con, league_id, stat_categories):
    with con:
        con.executemany(
            "INSERT OR REPLACE INTO stat_categories (league_id, stat_id, name, display_name, sort_order, position_type) VALUES (?, ?, ?, ?, ?, ?)",
            [(league_id, stat.stat_id, stat.name, stat.display_name, stat.sort_order, stat.position_type) for stat in stat_categories]
        )


def insert_roster_positions(con, league_id, roster_positions):
    with con:
        con.executemany(
            "INSERT OR REPLACE INTO roster_positions (league_id, position, position_type, count) VALUES (?, ?, ?, ?)",
            [(league_id, p.position, p.position_type, p.count) for p in roster_positions]
        )


def insert_teams(con, league_id, teams):
    with con:
        con.executemany(
            "INSERT OR REPLACE INTO teams (league_id, team_key, team_id, name, url, faab_balance, number_of_moves, number_of_trades) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(league_id, team.team_key, team.team_id, team.name, team.url, team.faab_balance, team.number_of_moves, team.number_of_trades) for team in teams]
        )


def insert_standings(con, league_id, standings):
    with con:
        con.executemany(
            "INSERT OR REPLACE INTO standings (league_id, team_id, rank, wins, losses, ties, percentage) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(league_id, s.team_id, s.rank, s.wins, s.losses, s.ties, s.percentage) for s in standings]
        )


def insert_matchups(con, league_id, matchups):
    with con:
        con.executemany(
            "INSERT OR REPLACE INTO matchups (league_id, week, team1_id, team1_points, team2_id, team2_points, winner_team_id, is_playoffs, is_consolation, is_tied) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(league_id, m.week, m.team1.team_id, m.team1_points, m.team2.team_id, m.team2_points, m.winner_team_id, m.is_playoffs, m.is_consolation, m.is_tied) for m in matchups]
        )


def insert_players(con, league_id, players):
    with con:
        con.executemany(
            "INSERT OR REPLACE INTO players (league_id, player_id, first_name, last_name, status, editorial_team_full_name, display_position, primary_position, eligible_positions, image_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(league_id, p.player_id, p.first_name, p.last_name, p.status, p.editorial_team_full_name, p.display_position, p.primary_position, ",".join(p.eligible_positions), p.image_url) for p in players]
        )


def insert_rosters(con, team_id, week, roster):
    with con:
        con.executemany(
            "INSERT OR REPLACE INTO rosters (team_id, week, player_id, position) VALUES (?, ?, ?, ?)",
            [(team_id, week, p.player_id, p.position) for p in roster]
        )


def insert_transactions(con, league_id, transactions):
    with con:
        con.executemany(
            "INSERT OR REPLACE INTO transactions (league_id, transaction_key, transaction_id, type, status, timestamp, faab_cost, players) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(league_id, t.transaction_key, t.transaction_id, t.type, t.status, t.timestamp, getattr(t, 'faab_cost', None), ",".join([p.player_id for p in t.players])) for t in transactions]
        )


def insert_draft_results(con, league_id, draft_results):
    with con:
        con.executemany(
            "INSERT OR REPLACE INTO draft_results (league_id, pick, round, team_id, player_id, cost) VALUES (?, ?, ?, ?, ?, ?)",
            [(league_id, d.pick, d.round, d.team_id, d.player_id, d.cost) for d in draft_results]
        )
