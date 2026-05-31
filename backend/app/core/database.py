import sqlite3
import json
import logging
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
from app.core.config import settings
from datetime import datetime

logger = logging.getLogger("slms.db")

DB_PATH = settings.DATABASE_URL.replace("sqlite:///", "")


def dict_factory(cursor, row):
    """Convert database row to dictionary."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def table_has_column(conn, table: str, column: str) -> bool:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return any(row['name'] == column for row in cursor.fetchall())


@contextmanager
def get_db():
    """Context manager for database connection."""
    conn = sqlite3.connect(DB_PATH)
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
    for sport in DEFAULT_SPORTS:
        if sport['name'] in existing:
            continue
        cursor.execute(
            """INSERT INTO sports (name, category, max_team_size, min_team_size, icon, is_active)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (sport['name'], sport['category'], sport['max_team_size'],
             sport['min_team_size'], sport['icon']),
        )
        added += 1
    if added:
        logger.info("Seeded %s default sport(s) into 'sports' table", added)


def init_db():
    """Initialize database schema."""
    logger.info("Initializing SQLite database at %s", DB_PATH)
    with get_db() as conn:
        cursor = conn.cursor()

        # Users table
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
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

        # Ensure legacy rows do not contain NULL timestamps
        logger.info("Normalizing existing created_at/updated_at values")
        cursor.execute("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        cursor.execute("UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")

        # Clubs table
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Player memberships table
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (club_id) REFERENCES clubs(id),
                FOREIGN KEY (sport_id) REFERENCES sports(id),
                FOREIGN KEY (captain_id) REFERENCES users(id)
            )
        """)

        # Team members table
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sport_id) REFERENCES sports(id),
                FOREIGN KEY (organizer_id) REFERENCES clubs(id)
            )
        """)

        # Tournament registrations table
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sport_id) REFERENCES sports(id),
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
                FOREIGN KEY (team_a_id) REFERENCES teams(id),
                FOREIGN KEY (team_b_id) REFERENCES teams(id),
                FOREIGN KEY (official_id) REFERENCES users(id),
                FOREIGN KEY (winner_id) REFERENCES teams(id)
            )
        """)

        # Match events table
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sport_id) REFERENCES sports(id)
            )
        """)

        # ── Ratings: per player / sport / match-type ──────────────────
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(player_id, sport_id, match_type),
                FOREIGN KEY (player_id) REFERENCES users(id),
                FOREIGN KEY (sport_id) REFERENCES sports(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_player_ratings_leaderboard ON player_ratings(sport_id, match_type, rating DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_player_ratings_player ON player_ratings(player_id)")

        # ── Ratings: one row per player per match per recalculation ───
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rating_history_player ON rating_history(player_id, sport_id, match_played_at DESC)")

        # ── Ratings: computed ranking snapshots ───────────────────────
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_player_rankings_lookup ON player_rankings(sport_id, match_type, scope, rank ASC)")

        # ── Ratings: recalculation job audit trail ────────────────────
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
        for table in ("clubs", "matches"):
            cursor.execute(f"UPDATE {table} SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
            cursor.execute(f"UPDATE {table} SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
        for table in ("teams", "tournaments", "match_events"):
            cursor.execute(f"UPDATE {table} SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")

        conn.commit()
        print("Database initialized successfully")
