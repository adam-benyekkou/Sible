from datetime import datetime, timedelta
from typing import Optional
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
    def __init__(self, session: Session):
        self.session = session

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        statement = select(User).where(User.username == username)
        user = self.session.exec(statement).first()
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def create_user(self, username: str, password: str, role: str = "watcher") -> User:
        hashed_password = get_password_hash(password)
        db_user = User(username=username, hashed_password=hashed_password, role=role)
        self.session.add(db_user)
        self.session.commit()
        self.session.refresh(db_user)
        return db_user
