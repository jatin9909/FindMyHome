from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Column, String, DateTime, Boolean, create_engine, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash

Base = declarative_base()

class UserStatus(str, Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved" 
    REJECTED = "rejected"
    ACTIVE = "active"
    SUSPENDED = "suspended"

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=True)  # Null until they sign up
    status = Column(String, default=UserStatus.PENDING_APPROVAL.value)
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    last_login = Column(DateTime, nullable=True)
    
    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    thread_id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    title = Column(String, nullable=True)  # Optional chat title
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)

# Pydantic models for API
class EmailApprovalRequest(BaseModel):
    email: EmailStr
    reason: Optional[str] = Field(None, description="Why the user wants access")

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    status: UserStatus
    created_at: datetime
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ChatSessionCreate(BaseModel):
    title: Optional[str] = None

class ChatSessionResponse(BaseModel):
    thread_id: str
    title: Optional[str]
    created_at: datetime
    last_active: datetime 

    class Config:
        from_attributes = True