#!/usr/bin/env python3
"""
Migrate data from SQLite (slms.db) to MySQL
Run from backend directory: python migrate_db.py
"""

import sqlite3
import pymysql
import os
import sys
from pathlib import Path

# Load environment variables from .env before importing app settings
from dotenv import load_dotenv
load_dotenv()

# Ensure backend package path is available when running from the backend directory
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from app.core.database import init_db

# Database connection settings
SQLITE_DB = Path(__file__).parent.parent / "slms.db"

MYSQL_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "slmsdb"),
}

# Tables to migrate (order matters for foreign keys)
TABLES = [
    "users",
    "clubs",
    "sports",
    "teams",
    "tournaments",
    "player_memberships",
    "team_members",
    "tournament_registrations",
    "matches",
    "match_events",
    "sport_rating_configs",
    "player_ratings",
    "rating_history",
    "player_rankings",
    "recalculation_jobs",
]


def migrate():
    """Main migration function"""
    
    # Check SQLite file exists
    if not SQLITE_DB.exists():
        print(f"ERROR: SQLite database not found at {SQLITE_DB}")
        sys.exit(1)
    
    print(f"📁 SQLite DB: {SQLITE_DB}")
    print(f"🗄️  MySQL: {MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}")
    print()
    
    # Ensure the MySQL schema exists before migrating
    if settings.DB_TYPE == "mysql":
        print("🔧 Ensuring MySQL tables exist")
        init_db()
        print("🔧 MySQL schema ready")

    try:
        # Connect to SQLite
        sqlite_conn = sqlite3.connect(str(SQLITE_DB))
        sqlite_conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        sqlite_cursor = sqlite_conn.cursor()
        
        # Connect to MySQL
        mysql_conn = pymysql.connect(**MYSQL_CONFIG)
        mysql_cursor = mysql_conn.cursor()
        
        print("✅ Connected to both databases\n")
        
        # Disable foreign key checks during migration
        mysql_cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        mysql_conn.commit()
        
        total_rows = 0
        
        # Migrate each table
        for table in TABLES:
            try:
                # Get all rows from SQLite
                sqlite_cursor.execute(f"SELECT * FROM {table}")
                rows = sqlite_cursor.fetchall()
                
                if not rows:
                    print(f"⏭️  {table}: 0 rows (empty)")
                    continue
                
                # Get column names
                columns = [desc[0] for desc in sqlite_cursor.description]
                
                # Build INSERT statement
                placeholders = ", ".join(["%s"] * len(columns))
                columns_str = ", ".join(columns)
                insert_sql = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
                
                # Convert rows to tuples and insert
                row_count = 0
                for row in rows:
                    values = tuple(row[col] for col in columns)
                    try:
                        mysql_cursor.execute(insert_sql, values)
                        row_count += 1
                    except pymysql.err.IntegrityError as e:
                        print(f"  ⚠️  Skipped row in {table} (constraint error): {e}")
                        continue
                
                mysql_conn.commit()
                total_rows += row_count
                print(f"✅ {table}: {row_count} rows migrated")
                
            except sqlite3.OperationalError as e:
                print(f"⚠️  {table}: Table not found in SQLite (skipped)")
            except Exception as e:
                print(f"❌ {table}: ERROR - {e}")
                mysql_conn.rollback()
                continue
        
        # Re-enable foreign key checks
        mysql_cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        mysql_conn.commit()
        
        sqlite_conn.close()
        mysql_conn.close()
        
        print(f"\n✨ Migration complete! Total rows: {total_rows}")
        return True
        
    except pymysql.Error as e:
        print(f"❌ MySQL error: {e}")
        print("\nMake sure:")
        print("  - MySQL is running")
        print("  - .env has correct DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
