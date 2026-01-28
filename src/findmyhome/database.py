from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from typing import List, Optional

from .config import get_settings
from .models import Base, User, ChatSession, UserStatus

def get_database_url():
    settings = get_settings()
    return settings.neon_url

engine = create_engine(get_database_url())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Create all tables in the database"""
    Base.metadata.create_all(bind=engine)

@contextmanager
def get_db_session():
    """Context manager for database sessions"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

class UserManager:
    @staticmethod
    def check_and_increment_queries(user_id: str, max_queries: int) -> int:
        """Increment user query count if under the limit and return new count."""
        with get_db_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            current_count = user.num_of_queries or 0
            if current_count >= max_queries:
                raise ValueError("Query limit reached")

            user.num_of_queries = current_count + 1
            session.flush()
            new_count = user.num_of_queries

            session.expunge(user)
            return new_count

    @staticmethod
    def request_approval(email: str, reason: str = None) -> User:
        """Submit email for approval"""
        with get_db_session() as session:
            # Check if user already exists
            existing_user = session.query(User).filter(User.email == email).first()
            if existing_user:
                if existing_user.status == UserStatus.PENDING_APPROVAL:
                    raise ValueError("Email already submitted for approval")
                elif existing_user.status == UserStatus.APPROVED:
                    raise ValueError("Email already approved. Please sign up.")
                elif existing_user.status == UserStatus.ACTIVE:
                    raise ValueError("User already exists. Please log in.")
                else:
                    raise ValueError(f"Email status: {existing_user.status}")
            
            # Create new user with pending status
            user = User(email=email, status=UserStatus.PENDING_APPROVAL)
            session.add(user)
            session.flush()
            # Access attributes to ensure they're loaded before session closes
            _ = user.id
            _ = user.email
            _ = user.status
            _ = user.created_at
            _ = user.approved_at
            
            # Detach from session to prevent lazy loading issues
            session.expunge(user)
            return user
    
    @staticmethod
    def approve_user(email: str) -> User:
        """Approve a user by email (admin function)"""
        with get_db_session() as session:
            user = session.query(User).filter(User.email == email).first()
            if not user:
                raise ValueError("User not found")
            if user.status != UserStatus.PENDING_APPROVAL:
                raise ValueError(f"User status is {user.status}, cannot approve")
            
            user.status = UserStatus.APPROVED
            user.approved_at = datetime.utcnow()
            session.flush()
            # Access attributes to ensure they're loaded before session closes
            _ = user.id
            _ = user.email
            _ = user.status
            _ = user.created_at
            _ = user.approved_at
            
            # Detach from session to prevent lazy loading issues
            session.expunge(user)
            return user
    
    @staticmethod
    def signup_user(email: str, password: str) -> User:
        """Complete user signup after approval"""
        with get_db_session() as session:
            user = session.query(User).filter(User.email == email).first()
            if not user:
                raise ValueError("Email not found. Please request approval first.")
            if user.status != UserStatus.APPROVED:
                raise ValueError("Email not approved yet")
            if user.password_hash:
                raise ValueError("User already signed up")
            
            user.set_password(password)
            user.status = UserStatus.ACTIVE
            session.flush()
            # Access attributes to ensure they're loaded before session closes
            _ = user.id
            _ = user.email
            _ = user.status
            _ = user.created_at
            _ = user.approved_at
            
            # Detach from session to prevent lazy loading issues
            session.expunge(user)
            return user
    
    @staticmethod
    def authenticate_user(email: str, password: str) -> Optional[User]:
        """Authenticate user login"""
        with get_db_session() as session:
            user = session.query(User).filter(User.email == email).first()
            if not user or not user.check_password(password):
                return None
            if user.status != UserStatus.ACTIVE:
                return None
            
            user.last_login = datetime.utcnow()
            session.flush()
            # Access attributes to ensure they're loaded before session closes
            _ = user.id
            _ = user.email
            _ = user.status
            _ = user.created_at
            _ = user.approved_at
            
            # Detach from session to prevent lazy loading issues
            session.expunge(user)
            return user
    
    @staticmethod
    def get_pending_approvals() -> List[User]:
        """Get all users pending approval (admin function)"""
        with get_db_session() as session:
            users = session.query(User).filter(User.status == UserStatus.PENDING_APPROVAL).all()
            
            # Access attributes for all users to ensure they're loaded before session closes
            for user in users:
                _ = user.id
                _ = user.email
                _ = user.status
                _ = user.created_at
                _ = user.approved_at
                
                # Detach from session to prevent lazy loading issues
                session.expunge(user)
            
            return users

class ChatSessionManager:
    @staticmethod
    def create_session(user_id: str, title: str = None) -> ChatSession:
        """Create a new chat session for a user"""
        with get_db_session() as session:
            chat_session = ChatSession(
                thread_id=str(uuid.uuid4()),
                user_id=user_id,
                title=title
            )
            session.add(chat_session)
            session.flush()
            # Access attributes to ensure they're loaded before session closes
            _ = chat_session.thread_id
            _ = chat_session.title
            _ = chat_session.created_at
            _ = chat_session.last_active
            
            # Detach from session to prevent lazy loading issues
            session.expunge(chat_session)
            return chat_session
    
    @staticmethod
    def get_user_sessions(user_id: str) -> List[ChatSession]:
        """Get all chat sessions for a user"""
        with get_db_session() as session:
            sessions = session.query(ChatSession).filter(
                ChatSession.user_id == user_id
            ).order_by(ChatSession.last_active.desc()).all()
        
            # Access attributes for all sessions to ensure they're loaded before session closes
            for session_obj in sessions:
                _ = session_obj.thread_id
                _ = session_obj.title
                _ = session_obj.created_at
                _ = session_obj.last_active
                
                # Detach from session to prevent lazy loading issues
                session.expunge(session_obj)
            
            return sessions
    
    @staticmethod
    def update_session_activity(thread_id: str):
        """Update last active time for a session"""
        with get_db_session() as session:
            chat_session = session.query(ChatSession).filter(
                ChatSession.thread_id == thread_id
            ).first()
            if chat_session:
                chat_session.last_active = datetime.utcnow() 
