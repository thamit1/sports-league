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

        conn.commit()
        print("Database initialized successfully")
