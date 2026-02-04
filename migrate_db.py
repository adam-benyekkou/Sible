import sqlite3

def migrate():
    try:
        conn = sqlite3.connect('sible.db')
        cursor = conn.cursor()
        
        # Check if columns exist
        cursor.execute("PRAGMA table_info(appsettings)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'logo_path' not in columns:
            print("Adding logo_path column...")
            cursor.execute("ALTER TABLE appsettings ADD COLUMN logo_path VARCHAR")
            
        if 'favicon_path' not in columns:
            print("Adding favicon_path column...")
            cursor.execute("ALTER TABLE appsettings ADD COLUMN favicon_path VARCHAR")
            
        conn.commit()
        conn.close()
        print("Migration successful.")
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
