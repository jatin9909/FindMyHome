from __future__ import annotations

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import uuid 
from datetime import datetime

from ..workflow import compile_workflow
from ..auth import get_current_user, require_admin, create_access_token
from ..database import UserManager, ChatSessionManager, create_tables
from ..models import (
    User, EmailApprovalRequest, SignupRequest, LoginRequest, 
    UserResponse, ChatSessionCreate, ChatSessionResponse, UserStatus
)
from ..memory import UserPreferences, store_user_preferences, get_user_preferences_memory
import logging

# create logger
logger = logging.getLogger(__name__)

app = FastAPI(title="FindMyHome API")
workflow = compile_workflow()

# Initialize database tables on startup
@app.on_event("startup")
async def startup_event():
    create_tables()

# Updated request model with authentication
class InvokeRequest(BaseModel):
    user_query: str
    thread_id: str = None

# Public endpoints (no authentication required)

@app.post("/request-approval")
def request_approval(request: EmailApprovalRequest):
    """Request approval for email address"""
    try:
        user = UserManager.request_approval(request.email, request.reason)
        return {
            "message": "Approval request submitted successfully",
            "email": user.email,
            "status": user.status
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/signup")
def signup(request: SignupRequest):
    """Complete signup after email approval"""
    try:
        user = UserManager.signup_user(request.email, request.password)
        token = create_access_token(user.id, user.email)
        return {
            "message": "Signup successful",
            "user": UserResponse.from_orm(user),
            "access_token": token,
            "token_type": "bearer"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/login")
def login(request: LoginRequest):
    """User login"""
    user = UserManager.authenticate_user(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_access_token(user.id, user.email)
    return {
        "message": "Login successful",
        "user": UserResponse.from_orm(user),
        "access_token": token,
        "token_type": "bearer"
    }

# Protected endpoints (require authentication)

@app.post("/invoke")
def invoke(req: InvokeRequest, current_user: User = Depends(get_current_user)):
    """Main chat interface - requires authentication"""
    thread_id = req.thread_id or str(uuid.uuid4())
    
    # If no thread_id provided, create a new chat session
    if not req.thread_id:
        chat_session = ChatSessionManager.create_session(current_user.id)
        thread_id = chat_session.thread_id
    else:
        # Update activity for existing session
        ChatSessionManager.update_session_activity(thread_id)

    config_dict = {"configurable": {"thread_id": thread_id, "user_id": current_user.id}}
    state = workflow.invoke({"user_query": [req.user_query]}, config=config_dict)
    
    return {
        "state": state,
        "thread_id": thread_id,
        "user_id": current_user.id
    }

@app.get("/my-chats")
def get_my_chats(current_user: User = Depends(get_current_user)):
    """Get all chat sessions for the current user"""
    sessions = ChatSessionManager.get_user_sessions(current_user.id)
    return [ChatSessionResponse.from_orm(session) for session in sessions]

@app.post("/create-chat")
def create_chat(request: ChatSessionCreate, current_user: User = Depends(get_current_user)):
    """Create a new chat session"""
    chat_session = ChatSessionManager.create_session(current_user.id, request.title)
    return ChatSessionResponse.from_orm(chat_session)

@app.get("/conversation/{thread_id}")
def get_conversation_history(thread_id: str, current_user: User = Depends(get_current_user)):
    """Get conversation history for a specific thread - user can only access their own"""
    # Verify the thread belongs to the current user
    user_sessions = ChatSessionManager.get_user_sessions(current_user.id)
    user_thread_ids = [session.thread_id for session in user_sessions]
    
    if thread_id not in user_thread_ids:
        raise HTTPException(status_code=403, detail="Access denied to this conversation")
    
    config_dict = {"configurable": {"thread_id": thread_id}}
    current_state = workflow.get_state(config_dict)
    
    return {
        "thread_id": thread_id,
        "conversation_history": current_state.values.get("turn_log", []),
        "user_queries": current_state.values.get("user_query", [])
    }

# Admin endpoints

@app.get("/admin/pending-approvals")
def get_pending_approvals(admin_user: User = Depends(require_admin)):
    """Get all users pending approval (admin only)"""
    users = UserManager.get_pending_approvals()
    return [UserResponse.from_orm(user) for user in users]

@app.post("/admin/approve-user/{email}")
def approve_user(email: str, admin_user: User = Depends(require_admin)):
    """Approve a user by email (admin only)"""
    try:
        user = UserManager.approve_user(email)
        return {
            "message": f"User {email} approved successfully",
            "user": UserResponse.from_orm(user)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/profile")
def get_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return UserResponse.from_orm(current_user)

@app.post("/save-preferences")
def save_user_preferences(
    preferences: UserPreferences, 
    current_user: User = Depends(get_current_user)
):
    """Save user preferences to long-term memory"""
    try:
        store_user_preferences(current_user.id, preferences)
        return {
            "message": "Preferences saved successfully",
            "preferences": preferences
        }
    except Exception as e:
        logger.error(f"Error saving preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to save preferences")

@app.get("/my-preferences")
def get_my_preferences(current_user: User = Depends(get_current_user)):
    """Get user's saved preferences from memory"""
    try:
        preferences = get_user_preferences_memory(current_user.id)
        return {
            "user_id": current_user.id,
            "preferences": preferences
        }
    except Exception as e:
        logger.error(f"Error retrieving preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve preferences")