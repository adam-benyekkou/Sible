from sqlmodel import SQLModel, create_engine
from app.core.config import get_settings

settings = get_settings()
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
    s = get_settings()
    db_path = s.DATABASE_URL.replace("sqlite:///", "")
    
    migrations = [
        ("user", "timezone", "TEXT DEFAULT 'UTC'"),
        ("user", "theme_preference", "TEXT DEFAULT 'light'"),
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
    except Exception:
        pass  # Non-SQLite or other error, skip

