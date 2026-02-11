from datetime import datetime, timedelta
from typing import Optional, Any
from jose import jwt, JWTError
from app.core.config import get_settings
from app.core.hashing import verify_password, get_password_hash
from app.models import User
from sqlmodel import Session, select

settings = get_settings()

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

class AuthService:
    """Manages user authentication, password hashing, and JWT issuance.

    This service handles the security layer of the application, verifying
    credentials against the database and generating signed tokens for
    Stateless session management.
    """
    def __init__(self, session: Session):
        """Initializes the service with a database session.

        Args:
            session: SQLModel session for user queries.
        """
        self.session = session

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Verifies user credentials against the database.

        Why: Centralizes authentication logic to ensure consistent security
        checks and password verification across all entry points (API, Web).

        Args:
            username: The unique username.
            password: The raw password attempt.

        Returns:
            The User object if authentication succeeded, else None.
        """
        statement = select(User).where(User.username == username)
        user = self.session.exec(statement).first()
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def create_access_token(
        self, 
        data: dict[str, Any], 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Generates a signed JWT access token for a user.

        Why: stateless JWTs allow the backend to be horizontally scalable
        while maintaining secure session state.

        Args:
            data: Payload to encode (typically 'sub' and 'role').
            expires_delta: How long before the token expires. If None,
                defaults to a short fallback duration.

        Returns:
            A signed HS256 JWT string.
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def create_user(self, username: str, password: str, role: str = "watcher") -> User:
        """Registers a new user in the system with a hashed password.

        Args:
            username: Unique username.
            password: Raw password to hash.
            role: Initial role ('admin', 'operator', 'watcher').

        Returns:
            The newly created User record.
        """
        hashed_password = get_password_hash(password)
        db_user = User(username=username, hashed_password=hashed_password, role=role)
        self.session.add(db_user)
        self.session.commit()
        self.session.refresh(db_user)
        return db_user
