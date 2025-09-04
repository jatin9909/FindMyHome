from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel
import uuid 

from ..workflow import compile_workflow


app = FastAPI(title="FindMyHome API")
workflow = compile_workflow()


class InvokeRequest(BaseModel):
    user_query: str
    thread_id: str = None
    user_id: str = None


@app.post("/invoke")
def invoke(req: InvokeRequest):
    thread_id = req.thread_id or str(uuid.uuid4())
    user_id = req.user_id or "anonymous"

    config_dict = {"configurable": {"thread_id": thread_id, "user_id": user_id}}
    state = workflow.invoke({"user_query": [req.user_query]}, config=config_dict)
    # make it JSON-friendly
    return {
        "state": state,
        "thread_id": thread_id,
        "user_id": user_id
    }

@app.get("/conversation/{thread_id}")
def get_conversation_history(thread_id: str):
    """Get the conversation history for a specific thread"""
    config_dict = {"configurable": {"thread_id": thread_id}}
    
    # Get the current state from Redis
    current_state = workflow.get_state(config_dict)
    
    return {
        "thread_id": thread_id,
        "conversation_history": current_state.values.get("turn_log", []),
        "user_queries": current_state.values.get("user_query", [])
    }
