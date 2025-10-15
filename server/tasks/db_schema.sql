-- A simple schema for a custom database.
-- You can define your own tables here.

CREATE TABLE IF NOT EXISTS league (
    league_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    num_teams INTEGER,
    start_date TEXT NOT NULL,
    end_date TEXT
);

CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    manager_nickname TEXT
);

CREATE TABLE IF NOT EXISTS metadata (
    key_ TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_lineups_dump (
  lineup_id INTEGER PRIMARY KEY AUTOINCREMENT,
  date_ TEXT NOT NULL,
  team_id INTEGER NOT NULL,
  c1 TEXT,
  c2 TEXT,
  l1 TEXT,
  l2 TEXT,
  r1 TEXT,
  r2 TEXT,
  d1 TEXT,
  d2 TEXT,
  d3 TEXT,
  d4 TEXT,
  g1 TEXT,
  g2 TEXT,
  b1 TEXT,
  b2 TEXT,
  b3 TEXT,
  b4 TEXT,
  b5 TEXT,
  b6 TEXT,
  b7 TEXT,
  b8 TEXT,
  b9 TEXT,
  b10 TEXT,
  i1 TEXT,
  i2 TEXT,
  i3 TEXT,
  i4 TEXT,
  i5 TEXT

);


CREATE TABLE IF NOT EXISTS players (
    player_id TEXT NOT NULL UNIQUE,
    player_name TEXT NOT NULL,
    player_team TEXT,
    player_name_normalized TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scoring (
    stat_id INTEGER NOT NULL UNIQUE,
    category TEXT NOT NULL,
    scoring_group TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weeks (
    week_num INTEGER NOT NULL UNIQUE,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS matchups (
    week INTEGER NOT NULL,
    team1 TEXT NOT NULL,
    team2 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rosters (
    team_id INTEGER NOT NULL UNIQUE,
    p1 INTEGER,
    p2 INTEGER,
    p3 INTEGER,
    p4 INTEGER,
    p5 INTEGER,
    p6 INTEGER,
    p7 INTEGER,
    p8 INTEGER,
    p9 INTEGER,
    p10 INTEGER,
    p11 INTEGER,
    p12 INTEGER,
    p13 INTEGER,
    p14 INTEGER,
    p15 INTEGER,
    p16 INTEGER,
    p17 INTEGER,
    p18 INTEGER,
    p19 INTEGER
);

CREATE TABLE IF NOT EXISTS free_agents (
    player_id INTEGER PRIMARY KEY,
    status TEXT
);
CREATE TABLE IF NOT EXISTS waiver_players (
    player_id INTEGER PRIMARY KEY,
    status TEXT
);
CREATE TABLE IF NOT EXISTS rostered_players (
    player_id INTEGER PRIMARY KEY,
    status TEXT
);
