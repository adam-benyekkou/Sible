import bcrypt

def verify_password(plain_password, hashed_password):
    try:
        # bcrypt.checkpw expects bytes
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        # Fallback if valid hash format check failed, it might be plain text
        return plain_password == hashed_password

def get_password_hash(password):
    # bcrypt.hashpw returns bytes, we decode to store as string
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
