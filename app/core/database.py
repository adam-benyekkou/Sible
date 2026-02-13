from sqlmodel import SQLModel, create_engine
from app.core.config import get_settings
import logging
import os

settings = get_settings()
logger = logging.getLogger(__name__)

connect_args = {"check_same_thread": False}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

def create_db_and_tables():
    # Import models here to ensure they are registered with SQLModel metadata
    from app.models import JobRun, AppSettings, PlaybookConfig, EnvVar, Host, User, FavoriteServer
    SQLModel.metadata.create_all(engine)
    
    # Lightweight migration: add new columns to existing tables
    _run_migrations()

def _run_migrations():
    """Add missing columns to existing tables (SQLite compatible)."""
    import sqlite3
    from app.core.config import get_settings
    # db_path = s.DATABASE_URL.replace("sqlite:///", "")
    # Use absolute path handling for SQLite
    if s.DATABASE_URL.startswith("sqlite:///"):
        db_path = s.DATABASE_URL[10:]
    else:
        return # Not a local sqlite DB
    
    # Ensure directory exists for migrations
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    
    migrations = [
        ("user", "timezone", "TEXT DEFAULT 'UTC'"),
        ("user", "theme", "TEXT DEFAULT 'light'"),
        ("appsettings", "playbooks_path", "TEXT DEFAULT '/app/infrastructure/playbooks'"),
    ]
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for table, column, col_type in migrations:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Migration error: {e}")

