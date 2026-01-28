from __future__ import annotations

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .database import UserManager, get_db_session
from .models import User, UserStatus
from .config import get_settings

security = HTTPBearer()

SECRET_KEY = get_settings().secret_key  # Move to environment variables
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

def create_access_token(user_id: str, email: str) -> str:
    """Create JWT access token"""
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> dict:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user"""
    token = credentials.credentials
    payload = verify_token(token)
    
    with get_db_session() as session:
        user = session.query(User).filter(User.id == payload["user_id"]).first()
        if not user or user.status != UserStatus.ACTIVE:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        # Access attributes to ensure they're loaded before session closes
        _ = user.id
        _ = user.email
        _ = user.status
        _ = user.created_at
        _ = user.approved_at
        _ = user.num_of_queries
        
        # Detach from session to prevent lazy loading issues
        session.expunge(user)
        return user

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin privileges (you can implement admin logic)"""
    # For now, you can use a specific admin email or add admin flag to User model
    admin_emails = get_settings().admin_email
    # Configure in environment
    if current_user.email.strip().lower() != admin_emails.strip().lower():
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user 
