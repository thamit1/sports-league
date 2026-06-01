import sqlite3
import json
import logging
import pymysql
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
from app.core.config import settings
from datetime import datetime

logger = logging.getLogger("slms.db")

DB_PATH = settings.DATABASE_URL.replace("sqlite:///", "") if settings.DB_TYPE == "sqlite" else None


def dict_factory(cursor, row):
    """Convert SQLite row to dictionary."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def create_index(cursor, sql: str) -> None:
    """Create an index, ignoring duplicate index errors on SQLite and MySQL."""
    try:
        cursor.execute(sql)
    except pymysql.err.InternalError as e:
        if e.args and e.args[0] == 1061:
            logger.debug("Index already exists: %s", sql)
        else:
            raise
    except sqlite3.OperationalError as e:
        if "already exists" in str(e).lower():
            logger.debug("Index already exists: %s", sql)
        else:
            raise


def table_has_column(conn, table: str, column: str) -> bool:
    if settings.DB_TYPE == "mysql":
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) AS count FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s AND column_name = %s",
            (settings.DB_NAME, table, column),
        )
        row = cursor.fetchone()
        return bool(row and row.get("count", 0))

    cursor = conn.execute(f"PRAGMA table_info({table})")
    return any(row['name'] == column for row in cursor.fetchall())


@contextmanager
def get_db():
    """Context manager for database connection."""
    if settings.DB_TYPE == "mysql":
        conn = pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,
            charset="utf8mb4",
            autocommit=False,
            connect_timeout=10,
            read_timeout=30,
            write_timeout=30,
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            yield conn
        finally:
            conn.close()

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = dict_factory
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def execute_query(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False, return_lastid: bool = False):
    """
    Execute a database query.

    Args:
        query: SQL query string
        params: Query parameters (tuple)
        fetch_one: Return single row
        fetch_all: Return all rows
        return_lastid: Return last inserted row ID
    """
    logger.debug("Executing query: %s | params=%s", query.strip(), params)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)

        if fetch_one:
            result = cursor.fetchone()
            conn.commit()
            logger.debug("Query returned one row")
            return result
        elif fetch_all:
            result = cursor.fetchall()
            conn.commit()
            logger.debug("Query returned %s rows", len(result))
            return result
        elif return_lastid:
            conn.commit()
            logger.debug("Query inserted row id=%s", cursor.lastrowid)
            return cursor.lastrowid
        else:
            rowcount = cursor.rowcount
            conn.commit()
            logger.debug("Query affected %s rows", rowcount)
            return rowcount


# ── Canonical sport catalog — single source of truth ─────────────────────
# Used by init_db() to keep names/icons/team sizes consistent across deploys.
# Mirror this list when adding new defaults; existing rows are matched by name.
DEFAULT_SPORTS = [
    {"name": "Football",     "category": "team",      "max_team_size": 11, "min_team_size": 7,  "icon": "⚽"},
    {"name": "Cricket",      "category": "team",      "max_team_size": 11, "min_team_size": 11, "icon": "🏏"},
    {"name": "Basketball",   "category": "team",      "max_team_size": 5,  "min_team_size": 5,  "icon": "🏀"},
    {"name": "Volleyball",   "category": "team",      "max_team_size": 6,  "min_team_size": 6,  "icon": "🏐"},
    {"name": "Tennis",       "category": "racket",    "max_team_size": 2,  "min_team_size": 1,  "icon": "🎾"},
    {"name": "Badminton",    "category": "racket",    "max_team_size": 2,  "min_team_size": 1,  "icon": "🏸"},
    {"name": "Table Tennis", "category": "racket",    "max_team_size": 2,  "min_team_size": 1,  "icon": "🏓"},
    {"name": "Pickleball",   "category": "racket",    "max_team_size": 2,  "min_team_size": 1,  "icon": "🏓"},
    {"name": "Snooker",      "category": "precision", "max_team_size": 1,  "min_team_size": 1,  "icon": "🎱"},
    {"name": "Billiards",    "category": "precision", "max_team_size": 1,  "min_team_size": 1,  "icon": "🎱"},
    {"name": "Darts",        "category": "precision", "max_team_size": 1,  "min_team_size": 1,  "icon": "🎯"},
    {"name": "Archery",      "category": "precision", "max_team_size": 1,  "min_team_size": 1,  "icon": "🏹"},
    {"name": "Chess",        "category": "other",     "max_team_size": 1,  "min_team_size": 1,  "icon": "♟️"},
    {"name": "Carrom",       "category": "other",     "max_team_size": 2,  "min_team_size": 1,  "icon": "🎯"},
    {"name": "Swimming",     "category": "aquatic",   "max_team_size": 1,  "min_team_size": 1,  "icon": "🏊"},
    {"name": "Rowing",       "category": "aquatic",   "max_team_size": 8,  "min_team_size": 1,  "icon": "🚣"},
    {"name": "Foosball",     "category": "other",     "max_team_size": 2,  "min_team_size": 1,  "icon": "⚽"},
    {"name": "Tug of War",   "category": "team",      "max_team_size": 8,  "min_team_size": 4,  "icon": "💪"},
]


def _seed_default_sports(cursor) -> None:
    """Insert any missing canonical sports. Existing rows (by name) untouched."""
    cursor.execute("SELECT name FROM sports")
    existing = {row['name'] for row in cursor.fetchall()}
    added = 0
    insert_sql = (
        "INSERT INTO sports (name, category, max_team_size, min_team_size, icon, is_active) "
        "VALUES (%s, %s, %s, %s, %s, 1)"
        if settings.DB_TYPE == "mysql"
        else "INSERT INTO sports (name, category, max_team_size, min_team_size, icon, is_active) VALUES (?, ?, ?, ?, ?, 1)"
    )

    for sport in DEFAULT_SPORTS:
        if sport['name'] in existing:
            continue
        cursor.execute(
            insert_sql,
            (sport['name'], sport['category'], sport['max_team_size'],
             sport['min_team_size'], sport['icon']),
        )
        added += 1
    if added:
        logger.info("Seeded %s default sport(s) into 'sports' table", added)


def init_db():
    """Initialize database schema."""
    if settings.DB_TYPE == "mysql":
        logger.info("Initializing MySQL database at %s", settings.DATABASE_URL)
    else:
        logger.info("Initializing SQLite database at %s", DB_PATH)

    with get_db() as conn:
        cursor = conn.cursor()

        if settings.DB_TYPE == "mysql":
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

        # Clubs table
        if settings.DB_TYPE == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clubs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    short_name VARCHAR(255),
                    code VARCHAR(100) UNIQUE NOT NULL,
                    description TEXT,
                    logo_url TEXT,
                    primary_color VARCHAR(7) DEFAULT '#1a56db',
                    secondary_color VARCHAR(7) DEFAULT '#ffffff',
                    city VARCHAR(100),
                    country VARCHAR(100) DEFAULT 'India',
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clubs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    short_name TEXT,
                    code TEXT UNIQUE NOT NULL,
                    description TEXT,
                    logo_url TEXT,
                    primary_color TEXT DEFAULT '#1a56db',
                    secondary_color TEXT DEFAULT '#ffffff',
                    city TEXT,
                    country TEXT DEFAULT 'India',
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

        # Users table
        if settings.DB_TYPE == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    phone VARCHAR(50) UNIQUE,
                    password_hash TEXT NOT NULL,
                    first_name VARCHAR(255) NOT NULL,
                    last_name VARCHAR(255) NOT NULL,
                    role VARCHAR(50) DEFAULT 'viewer',
                    club_id INT,
                    global_player_id VARCHAR(50) UNIQUE,
                    avatar_url TEXT,
                    date_of_birth DATE,
                    gender VARCHAR(50),
                    is_active BOOLEAN DEFAULT 1,
                    is_verified BOOLEAN DEFAULT 0,
                    password_reset_required BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (club_id) REFERENCES clubs(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT UNIQUE,
                    password_hash TEXT NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    role TEXT DEFAULT 'viewer',
                    club_id INTEGER,
                    global_player_id TEXT UNIQUE,
                    avatar_url TEXT,
                    date_of_birth TEXT,
                    gender TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    is_verified BOOLEAN DEFAULT 0,
                    password_reset_required BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (club_id) REFERENCES clubs(id)
                )
            """)

        # Ensure existing databases gain the password_reset_required column
        if not table_has_column(conn, 'users', 'password_reset_required'):
            logger.info("Adding missing users.password_reset_required column")
            cursor.execute("ALTER TABLE users ADD COLUMN password_reset_required BOOLEAN DEFAULT 0")

        # Normalize any legacy role values to lowercase so enum validation stays consistent
        logger.info("Normalizing existing user roles to lowercase")
        cursor.execute("UPDATE users SET role = lower(role) WHERE role IS NOT NULL")

        # Ensure legacy rows do not contain NULL password_reset_required values
        logger.info("Normalizing existing password_reset_required values")
        cursor.execute("UPDATE users SET password_reset_required = 0 WHERE password_reset_required IS NULL")

        # Ensure legacy rows do not contain NULL is_active values
        logger.info("Normalizing existing is_active values")
        cursor.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")

        # Ensure legacy rows do not contain NULL is_verified values
        logger.info("Normalizing existing is_verified values")
        cursor.execute("UPDATE users SET is_verified = 0 WHERE is_verified IS NULL")

        # Ensure legacy rows do not contain NULL timestamps
        logger.info("Normalizing existing created_at/updated_at values")
        cursor.execute("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        cursor.execute("UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")

        # Player memberships table
        if settings.DB_TYPE == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_memberships (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    player_id INT NOT NULL,
                    club_id INT NOT NULL,
                    jersey_no VARCHAR(50),
                    position VARCHAR(50),
                    status VARCHAR(50) DEFAULT 'active',
                    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    left_at DATETIME,
                    FOREIGN KEY (player_id) REFERENCES users(id),
                    FOREIGN KEY (club_id) REFERENCES clubs(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_memberships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id INTEGER NOT NULL,
                    club_id INTEGER NOT NULL,
                    jersey_no TEXT,
                    position TEXT,
                    status TEXT DEFAULT 'active',
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    left_at TEXT,
                    FOREIGN KEY (player_id) REFERENCES users(id),
                    FOREIGN KEY (club_id) REFERENCES clubs(id)
                )
            """)

        # Sports table
        if settings.DB_TYPE == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sports (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    category VARCHAR(100),
                    max_team_size INT DEFAULT 1,
                    min_team_size INT DEFAULT 1,
                    scoring_config TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    icon VARCHAR(50)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    category TEXT,
                    max_team_size INTEGER DEFAULT 1,
                    min_team_size INTEGER DEFAULT 1,
                    scoring_config TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    icon TEXT
                )
            """)

        # ── Seed canonical sports list (idempotent — match by name) ───
        _seed_default_sports(cursor)

        # Teams table
        if settings.DB_TYPE == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS teams (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    club_id INT NOT NULL,
                    sport_id INT NOT NULL,
                    captain_id INT,
                    age_group VARCHAR(100),
                    division VARCHAR(100),
                    logo_url TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (club_id) REFERENCES clubs(id),
                    FOREIGN KEY (sport_id) REFERENCES sports(id),
                    FOREIGN KEY (captain_id) REFERENCES users(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    club_id INTEGER NOT NULL,
                    sport_id INTEGER NOT NULL,
                    captain_id INTEGER,
                    age_group TEXT,
                    division TEXT,
                    logo_url TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (club_id) REFERENCES clubs(id),
                    FOREIGN KEY (sport_id) REFERENCES sports(id),
                    FOREIGN KEY (captain_id) REFERENCES users(id)
                )
            """)

        # Team members table
        if settings.DB_TYPE == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS team_members (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    team_id INT NOT NULL,
                    player_id INT NOT NULL,
                    jersey_no VARCHAR(50),
                    position VARCHAR(50),
                    is_active BOOLEAN DEFAULT 1,
                    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (team_id) REFERENCES teams(id),
                    FOREIGN KEY (player_id) REFERENCES users(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS team_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id INTEGER NOT NULL,
                    player_id INTEGER NOT NULL,
                    jersey_no TEXT,
                    position TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (team_id) REFERENCES teams(id),
                    FOREIGN KEY (player_id) REFERENCES users(id)
                )
            """)

        # Tournaments table
        if settings.DB_TYPE == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tournaments (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    sport_id INT NOT NULL,
                    organizer_id INT NOT NULL,
                    bracket_type VARCHAR(50) DEFAULT 'single_elimination',
                    status VARCHAR(50) DEFAULT 'draft',
                    max_teams INT DEFAULT 16,
                    start_date DATE,
                    end_date DATE,
                    venue TEXT,
                    description TEXT,
                    prize_pool DOUBLE DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sport_id) REFERENCES sports(id),
                    FOREIGN KEY (organizer_id) REFERENCES clubs(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tournaments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    sport_id INTEGER NOT NULL,
                    organizer_id INTEGER NOT NULL,
                    bracket_type TEXT DEFAULT 'single_elimination',
                    status TEXT DEFAULT 'draft',
                    max_teams INTEGER DEFAULT 16,
                    start_date TEXT,
                    end_date TEXT,
                    venue TEXT,
                    description TEXT,
                    prize_pool REAL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sport_id) REFERENCES sports(id),
                    FOREIGN KEY (organizer_id) REFERENCES clubs(id)
                )
            """)

        # Tournament registrations table
        if settings.DB_TYPE == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tournament_registrations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    tournament_id INT NOT NULL,
                    team_id INT NOT NULL,
                    seed INT,
                    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_approved BOOLEAN DEFAULT 0,
                    FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
                    FOREIGN KEY (team_id) REFERENCES teams(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tournament_registrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tournament_id INTEGER NOT NULL,
                    team_id INTEGER NOT NULL,
                    seed INTEGER,
                    registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    is_approved BOOLEAN DEFAULT 0,
                    FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
                    FOREIGN KEY (team_id) REFERENCES teams(id)
                )
            """)

        # Matches table
        if settings.DB_TYPE == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    sport_id INT NOT NULL,
                    tournament_id INT,
                    team_a_id INT NOT NULL,
                    team_b_id INT NOT NULL,
                    official_id INT,
                    status VARCHAR(50) DEFAULT 'scheduled',
                    scheduled_at DATETIME,
                    started_at DATETIME,
                    ended_at DATETIME,
                    venue TEXT,
                    score_a TEXT,
                    score_b TEXT,
                    winner_id INT,
                    round_number INT,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (sport_id) REFERENCES sports(id),
                    FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
                    FOREIGN KEY (team_a_id) REFERENCES teams(id),
                    FOREIGN KEY (team_b_id) REFERENCES teams(id),
                    FOREIGN KEY (official_id) REFERENCES users(id),
                    FOREIGN KEY (winner_id) REFERENCES teams(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sport_id INTEGER NOT NULL,
                    tournament_id INTEGER,
                    team_a_id INTEGER NOT NULL,
                    team_b_id INTEGER NOT NULL,
                    official_id INTEGER,
                    status TEXT DEFAULT 'scheduled',
                    scheduled_at TEXT,
                    started_at TEXT,
                    ended_at TEXT,
                    venue TEXT,
                    score_a TEXT,
                    score_b TEXT,
                    winner_id INTEGER,
                    round_number INTEGER,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sport_id) REFERENCES sports(id),
                    FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
                    FOREIGN KEY (team_a_id) REFERENCES teams(id),
                    FOREIGN KEY (team_b_id) REFERENCES teams(id),
                    FOREIGN KEY (official_id) REFERENCES users(id),
                    FOREIGN KEY (winner_id) REFERENCES teams(id)
                )
            """)

        # Match events table
        if settings.DB_TYPE == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS match_events (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    match_id INT NOT NULL,
                    team_id INT,
                    player_id INT,
                    event_type VARCHAR(100),
                    event_data TEXT,
                    minute INT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES matches(id),
                    FOREIGN KEY (team_id) REFERENCES teams(id),
                    FOREIGN KEY (player_id) REFERENCES users(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS match_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER NOT NULL,
                    team_id INTEGER,
                    player_id INTEGER,
                    event_type TEXT,
                    event_data TEXT,
                    minute INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES matches(id),
                    FOREIGN KEY (team_id) REFERENCES teams(id),
                    FOREIGN KEY (player_id) REFERENCES users(id)
                )
            """)

        # ── Ratings: per-sport configuration ──────────────────────────
        if settings.DB_TYPE == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sport_rating_configs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    sport_id INT NOT NULL UNIQUE,
                    provisional_threshold INT NOT NULL DEFAULT 5,
                    season_reset_type VARCHAR(50) NOT NULL DEFAULT 'none',
                    season_reset_factor DOUBLE NOT NULL DEFAULT 0.3,
                    visibility VARCHAR(50) NOT NULL DEFAULT 'club_members',
                    k_factor_provisional DOUBLE NOT NULL DEFAULT 32.0,
                    k_factor_established DOUBLE NOT NULL DEFAULT 16.0,
                    k_factor_elite DOUBLE NOT NULL DEFAULT 8.0,
                    starting_rating DOUBLE NOT NULL DEFAULT 50.0,
                    max_rating_change_per_match DOUBLE NOT NULL DEFAULT 15.0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (sport_id) REFERENCES sports(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sport_rating_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sport_id INTEGER NOT NULL UNIQUE,
                    provisional_threshold INTEGER NOT NULL DEFAULT 5,
                    season_reset_type TEXT NOT NULL DEFAULT 'none',
                    season_reset_factor REAL NOT NULL DEFAULT 0.3,
                    visibility TEXT NOT NULL DEFAULT 'club_members',
                    k_factor_provisional REAL NOT NULL DEFAULT 32.0,
                    k_factor_established REAL NOT NULL DEFAULT 16.0,
                    k_factor_elite REAL NOT NULL DEFAULT 8.0,
                    starting_rating REAL NOT NULL DEFAULT 50.0,
                    max_rating_change_per_match REAL NOT NULL DEFAULT 15.0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sport_id) REFERENCES sports(id)
                )
            """)

        # ── Ratings: per player / sport / match-type ──────────────────
        if settings.DB_TYPE == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_ratings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    player_id INT NOT NULL,
                    sport_id INT NOT NULL,
                    match_type VARCHAR(100) NOT NULL,
                    rating DOUBLE NOT NULL DEFAULT 50.0,
                    peak_rating DOUBLE NOT NULL DEFAULT 50.0,
                    matches_played INT NOT NULL DEFAULT 0,
                    matches_won INT NOT NULL DEFAULT 0,
                    matches_drawn INT NOT NULL DEFAULT 0,
                    matches_lost INT NOT NULL DEFAULT 0,
                    is_provisional BOOLEAN DEFAULT 1,
                    is_active BOOLEAN DEFAULT 1,
                    last_match_at DATETIME,
                    last_calculated_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE(player_id, sport_id, match_type),
                    FOREIGN KEY (player_id) REFERENCES users(id),
                    FOREIGN KEY (sport_id) REFERENCES sports(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            create_index(cursor, "CREATE INDEX idx_player_ratings_leaderboard ON player_ratings(sport_id, match_type, rating DESC)")
            create_index(cursor, "CREATE INDEX idx_player_ratings_player ON player_ratings(player_id)")
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id INTEGER NOT NULL,
                    sport_id INTEGER NOT NULL,
                    match_type TEXT NOT NULL,
                    rating REAL NOT NULL DEFAULT 50.0,
                    peak_rating REAL NOT NULL DEFAULT 50.0,
                    matches_played INTEGER NOT NULL DEFAULT 0,
                    matches_won INTEGER NOT NULL DEFAULT 0,
                    matches_drawn INTEGER NOT NULL DEFAULT 0,
                    matches_lost INTEGER NOT NULL DEFAULT 0,
                    is_provisional BOOLEAN DEFAULT 1,
                    is_active BOOLEAN DEFAULT 1,
                    last_match_at TEXT,
                    last_calculated_at TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(player_id, sport_id, match_type),
                    FOREIGN KEY (player_id) REFERENCES users(id),
                    FOREIGN KEY (sport_id) REFERENCES sports(id)
                )
            """)
            create_index(cursor, "CREATE INDEX idx_player_ratings_leaderboard ON player_ratings(sport_id, match_type, rating DESC)")
            create_index(cursor, "CREATE INDEX idx_player_ratings_player ON player_ratings(player_id)")

        # ── Ratings: one row per player per match per recalculation ───
        if settings.DB_TYPE == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rating_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    player_id INT NOT NULL,
                    sport_id INT NOT NULL,
                    match_id INT NOT NULL,
                    match_type VARCHAR(100) NOT NULL,
                    rating_before DOUBLE NOT NULL,
                    rating_after DOUBLE NOT NULL,
                    rating_delta DOUBLE NOT NULL,
                    expected_score DOUBLE NOT NULL,
                    actual_score DOUBLE NOT NULL,
                    opponent_rating_at_time DOUBLE NOT NULL,
                    k_factor_used DOUBLE NOT NULL,
                    match_played_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (player_id) REFERENCES users(id),
                    FOREIGN KEY (sport_id) REFERENCES sports(id),
                    FOREIGN KEY (match_id) REFERENCES matches(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            create_index(cursor, "CREATE INDEX idx_rating_history_player ON rating_history(player_id, sport_id, match_played_at DESC)")
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rating_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id INTEGER NOT NULL,
                    sport_id INTEGER NOT NULL,
                    match_id INTEGER NOT NULL,
                    match_type TEXT NOT NULL,
                    rating_before REAL NOT NULL,
                    rating_after REAL NOT NULL,
                    rating_delta REAL NOT NULL,
                    expected_score REAL NOT NULL,
                    actual_score REAL NOT NULL,
                    opponent_rating_at_time REAL NOT NULL,
                    k_factor_used REAL NOT NULL,
                    match_played_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (player_id) REFERENCES users(id),
                    FOREIGN KEY (sport_id) REFERENCES sports(id),
                    FOREIGN KEY (match_id) REFERENCES matches(id)
                )
            """)
            create_index(cursor, "CREATE INDEX idx_rating_history_player ON rating_history(player_id, sport_id, match_played_at DESC)")

        # ── Ratings: computed ranking snapshots ───────────────────────
        if settings.DB_TYPE == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_rankings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    player_id INT NOT NULL,
                    sport_id INT NOT NULL,
                    match_type VARCHAR(100) NOT NULL,
                    scope VARCHAR(100) NOT NULL,
                    scope_value VARCHAR(255),
                    rank INT NOT NULL,
                    rating DOUBLE NOT NULL,
                    total_ranked INT NOT NULL,
                    calculated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(player_id, sport_id, match_type, scope, scope_value),
                    FOREIGN KEY (player_id) REFERENCES users(id),
                    FOREIGN KEY (sport_id) REFERENCES sports(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            create_index(cursor, "CREATE INDEX idx_player_rankings_lookup ON player_rankings(sport_id, match_type, scope, rank ASC)")
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_rankings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id INTEGER NOT NULL,
                    sport_id INTEGER NOT NULL,
                    match_type TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    scope_value TEXT,
                    rank INTEGER NOT NULL,
                    rating REAL NOT NULL,
                    total_ranked INTEGER NOT NULL,
                    calculated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(player_id, sport_id, match_type, scope, scope_value),
                    FOREIGN KEY (player_id) REFERENCES users(id),
                    FOREIGN KEY (sport_id) REFERENCES sports(id)
                )
            """)
            create_index(cursor, "CREATE INDEX idx_player_rankings_lookup ON player_rankings(sport_id, match_type, scope, rank ASC)")

        # ── Ratings: recalculation job audit trail ────────────────────
        if settings.DB_TYPE == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recalculation_jobs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    triggered_by_id INT,
                    sport_id INT,
                    status VARCHAR(50) NOT NULL DEFAULT 'pending',
                    matches_processed INT NOT NULL DEFAULT 0,
                    players_updated INT NOT NULL DEFAULT 0,
                    error_message TEXT,
                    started_at DATETIME,
                    completed_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (triggered_by_id) REFERENCES users(id),
                    FOREIGN KEY (sport_id) REFERENCES sports(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recalculation_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    triggered_by_id INTEGER,
                    sport_id INTEGER,
                    status TEXT NOT NULL DEFAULT 'pending',
                    matches_processed INTEGER NOT NULL DEFAULT 0,
                    players_updated INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (triggered_by_id) REFERENCES users(id),
                    FOREIGN KEY (sport_id) REFERENCES sports(id)
                )
            """)

        # Normalize NULL timestamps across all tables (legacy rows)
        logger.info("Normalizing NULL created_at/updated_at across tables")
        if settings.DB_TYPE == "mysql":
            for table in ("clubs", "matches", "teams", "tournaments", "match_events"):
                cursor.execute(f"UPDATE {table} SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
                if table in ("clubs", "matches"):
                    cursor.execute(f"UPDATE {table} SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
        else:
            for table in ("clubs", "matches"):
                cursor.execute(f"UPDATE {table} SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
                cursor.execute(f"UPDATE {table} SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
            for table in ("teams", "tournaments", "match_events"):
                cursor.execute(f"UPDATE {table} SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")

        conn.commit()
        print("Database initialized successfully")
