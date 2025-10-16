-- This schema defines the structure of the SQLite database.

CREATE TABLE IF NOT EXISTS game (
    game_key TEXT PRIMARY KEY,
    game_id INTEGER,
    name TEXT,
    code TEXT,
    type TEXT,
    url TEXT,
    season INTEGER,
    is_registration_over INTEGER,
    is_game_over INTEGER,
    is_offseason INTEGER
);

CREATE TABLE IF NOT EXISTS leagues (
    league_key TEXT PRIMARY KEY,
    league_id INTEGER,
    name TEXT,
    url TEXT,
    draft_status TEXT,
    num_teams INTEGER,
    current_week INTEGER,
    end_week INTEGER
);

CREATE TABLE IF NOT EXISTS settings (
    league_id INTEGER PRIMARY KEY,
    name TEXT,
    draft_type TEXT,
    is_auction_draft INTEGER,
    scoring_type TEXT,
    uses_faab INTEGER,
    waiver_type TEXT,
    waiver_rule TEXT,
    faab_balance INTEGER,
    draft_time INTEGER,
    draft_pick_time INTEGER,
    post_draft_players TEXT,
    max_teams INTEGER,
    waiver_time TEXT,
    trade_end_date TEXT,
    trade_ratify_type TEXT,
    trade_reject_time INTEGER,
    player_pool TEXT,
    cant_cut_list TEXT,
    draft_together INTEGER,
    can_trade_draft_picks INTEGER,
    send_email_notifications INTEGER,
    has_playoff_consolation_games INTEGER,
    has_playoff_reseeding INTEGER,
    playoff_start_week INTEGER,
    playoff_end_week INTEGER
);

CREATE TABLE IF NOT EXISTS stat_categories (
    league_id INTEGER,
    stat_id INTEGER,
    name TEXT,
    display_name TEXT,
    sort_order INTEGER,
    position_type TEXT,
    PRIMARY KEY (league_id, stat_id)
);

CREATE TABLE IF NOT EXISTS roster_positions (
    league_id INTEGER,
    position TEXT,
    position_type TEXT,
    count INTEGER,
    PRIMARY KEY (league_id, position)
);

CREATE TABLE IF NOT EXISTS teams (
    team_key TEXT PRIMARY KEY,
    league_id INTEGER,
    team_id INTEGER,
    name TEXT,
    url TEXT,
    faab_balance INTEGER,
    number_of_moves INTEGER,
    number_of_trades INTEGER
);

CREATE TABLE IF NOT EXISTS standings (
    league_id INTEGER,
    team_id INTEGER,
    rank INTEGER,
    wins INTEGER,
    losses INTEGER,
    ties REAL,
    percentage REAL,
    PRIMARY KEY (league_id, team_id)
);

CREATE TABLE IF NOT EXISTS matchups (
    league_id INTEGER,
    week INTEGER,
    team1_id INTEGER,
    team1_points REAL,
    team2_id INTEGER,
    team2_points REAL,
    winner_team_id INTEGER,
    is_playoffs INTEGER,
    is_consolation INTEGER,
    is_tied INTEGER,
    PRIMARY KEY (league_id, week, team1_id)
);

CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY,
    league_id INTEGER,
    first_name TEXT,
    last_name TEXT,
    status TEXT,
    editorial_team_full_name TEXT,
    display_position TEXT,
    primary_position TEXT,
    eligible_positions TEXT,
    image_url TEXT
);

CREATE TABLE IF NOT EXISTS rosters (
    team_id INTEGER,
    week INTEGER,
    player_id INTEGER,
    position TEXT,
    PRIMARY KEY (team_id, week, player_id)
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_key TEXT PRIMARY KEY,
    league_id INTEGER,
    transaction_id INTEGER,
    type TEXT,
    status TEXT,
    timestamp INTEGER,
    faab_cost INTEGER,
    players TEXT
);

CREATE TABLE IF NOT EXISTS draft_results (
    league_id INTEGER,
    pick INTEGER,
    round INTEGER,
    team_id INTEGER,
    player_id INTEGER,
    cost REAL,
    PRIMARY KEY (league_id, pick)
);
