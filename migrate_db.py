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

        if 'auth_enabled' not in columns:
            print("Adding auth_enabled column...")
            cursor.execute("ALTER TABLE appsettings ADD COLUMN auth_enabled BOOLEAN DEFAULT 0")

        if 'auth_username' not in columns:
            print("Adding auth_username column...")
            cursor.execute("ALTER TABLE appsettings ADD COLUMN auth_username VARCHAR DEFAULT 'admin'")

        if 'auth_password' not in columns:
            print("Adding auth_password column...")
            cursor.execute("ALTER TABLE appsettings ADD COLUMN auth_password VARCHAR DEFAULT 'admin'")
            
        conn.commit()
        conn.close()
        print("Migration successful.")
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
