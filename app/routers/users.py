from fastapi import APIRouter, Depends, HTTPException, status, Form
from typing import List, Optional
from sqlmodel import Session, select
from app.dependencies import get_db, requires_role
from app.models import User
from app.models.user import UserRole
from app.core.hashing import get_password_hash
from pydantic import BaseModel

router = APIRouter(prefix="/api/users", tags=["users"])

class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole

class UserRead(BaseModel):
    id: int
    username: str
    role: UserRole

@router.get("/", response_model=List[UserRead])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role("admin"))
) -> List[User]:
    """Lists all registered users.

    Args:
        db: Database session.
        current_user: Admin access required.

    Returns:
        List of user records.
    """
    users = db.exec(select(User)).all()
    return list(users)

@router.post("/", response_model=UserRead)
def create_user(
    username: str = Form(...),
    password: str = Form(...),
    role: UserRole = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role("admin"))
) -> User:
    """Creates a new user with hashed password.

    Args:
        username: Unique login name.
        password: Plaintext password (will be hashed).
        role: Primary authorization level.
        db: Database session.
        current_user: Admin access required.

    Returns:
        The newly created user record.
    """
    # Check if user exists
    existing = db.exec(select(User).where(User.username == username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
        
    hashed = get_password_hash(password)
    user = User(username=username, hashed_password=hashed, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role("admin"))
) -> dict[str, str]:
    """Deletes a user account.

    Why: Hardcoded protection for the 'admin' user and preventing self-deletion
    ensures the core administrative account remains intact.

    Args:
        user_id: Target user PK.
        db: Database session.
        current_user: Admin access required.

    Returns:
        JSON confirmation message.
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.username == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete the default admin user")
    
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
        
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}

class UserUpdate(BaseModel):
    username: str | None = None
    password: str | None = None
    role: UserRole | None = None

@router.put("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    role: Optional[UserRole] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role("admin"))
) -> User:
    """Updates user profile information.

    Args:
        user_id: Target user PK.
        username: Optional new unique name.
        password: Optional new plaintext password.
        role: Optional new authorization role.
        db: Database session.
        current_user: Admin access required.

    Returns:
        The updated user record.
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.username == "admin" and current_user.username != "admin": 
         if role and role != UserRole.ADMIN:
              raise HTTPException(status_code=400, detail="Cannot downgrade default admin user")
              
    # Handle username change
    if username and username != user.username:
        # Check uniqueness
        existing = db.exec(select(User).where(User.username == username)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
            
        # Prevent renaming "admin" user
        if user.username == "admin":
             raise HTTPException(status_code=400, detail="Cannot rename default admin user")
             
        user.username = username

    if password and password.strip():
        user.hashed_password = get_password_hash(password)
    
    if role:
        user.role = role
        
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
