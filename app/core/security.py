import base64
import hashlib
from cryptography.fernet import Fernet
from app.core.config import get_settings

settings = get_settings()

def get_fernet() -> Fernet:
    """Derives a Fernet key from the SECRET_KEY and returns a Fernet instance.
    
    Why: Fernet requires a 32-byte url-safe base64-encoded key. We derive this
    from the application's SECRET_KEY to ensure consistency and security.
    """
    # Derive a 32-byte key from SECRET_KEY
    key_bytes = settings.SECRET_KEY.encode()
    hash_object = hashlib.sha256(key_bytes)
    key_32 = base64.urlsafe_b64encode(hash_object.digest())
    return Fernet(key_32)

def encrypt_secret(plain_text: str) -> str:
    """Encrypts a string using Fernet symmetric encryption.
    
    Args:
        plain_text: The sensitive data to encrypt.
        
    Returns:
        The encrypted token as a string.
    """
    if not plain_text:
        return ""
    f = get_fernet()
    return f.encrypt(plain_text.encode()).decode()

def decrypt_secret(cipher_text: str) -> str:
    """Decrypts a Fernet token back to its original string.
    
    Args:
        cipher_text: The encrypted token.
        
    Returns:
        The original plain-text string.
    """
    if not cipher_text:
        return ""
    try:
        f = get_fernet()
        return f.decrypt(cipher_text.encode()).decode()
    except Exception:
        # If decryption fails (e.g., if it was stored as plain text previously)
        # return the original text during migration phases, but log it?
        # For a clean implementation, we might want to return original if NOT a valid fernet token
        return cipher_text
