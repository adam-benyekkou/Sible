import sqlite3
import bcrypt
from app.auth import get_password_hash

def migrate_passwords():
    try:
        conn = sqlite3.connect('sible.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, auth_password FROM appsettings")
        rows = cursor.fetchall()
        
        updated_count = 0
        for row_id, password in rows:
            if not password:
                continue
            
            # Simple check if it's already a bcrypt hash (starts with $2b$ or $2a$)
            if password.startswith('$2b$') or password.startswith('$2a$'):
                continue
                
            print(f"Hashing password for row {row_id}...")
            new_hash = get_password_hash(password)
            cursor.execute("UPDATE appsettings SET auth_password = ? WHERE id = ?", (new_hash, row_id))
            updated_count += 1
        
        conn.commit()
        conn.close()
        print(f"Migration finished. Updated {updated_count} passwords.")
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate_passwords()
