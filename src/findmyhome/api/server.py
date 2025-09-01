from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from ..workflow import compile_workflow


app = FastAPI(title="FindMyHome API")
workflow = compile_workflow()


class InvokeRequest(BaseModel):
    user_query: str
    thread_id: str = "1"
    user_id: str = "2"


@app.post("/invoke")
def invoke(req: InvokeRequest):
    config_dict = {"configurable": {"thread_id": req.thread_id, "user_id": req.user_id}}
    state = workflow.invoke({"user_query": [req.user_query]}, config=config_dict)
    # make it JSON-friendly
    return state

