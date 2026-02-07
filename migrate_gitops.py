import sqlite3
import os

DB_PATH = "sible.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print("Database not found, skipping migration.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if columns exist
        cursor.execute("PRAGMA table_info(appsettings)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "git_repository_url" not in columns:
            print("Adding git_repository_url column...")
            cursor.execute("ALTER TABLE appsettings ADD COLUMN git_repository_url VARCHAR")
            
        if "git_ssh_key" not in columns:
            print("Adding git_ssh_key column...")
            cursor.execute("ALTER TABLE appsettings ADD COLUMN git_ssh_key VARCHAR")
            
        conn.commit()
        print("Migration complete.")
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
