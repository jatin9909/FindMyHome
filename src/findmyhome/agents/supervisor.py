from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from findmyhome.config import get_chat_model
from .state import RecommendationState, SupervisorEvaluation


def supervisor_agent(state: RecommendationState):
    msgs = state.get("user_query", []) or []
    last_human_text: str = msgs[-1] if msgs else ""
    previous_conversation = state.get("turn_log", []) or []

    messages = [
        SystemMessage(content="You are a supervisor agent that classifies the intent of the user query."),
        HumanMessage(
            content=f"""
        You will receive a user query along with the previous conversation context.

        Your task is to evaluate the query and determine its intent based on the following definitions:

        - If the user is requesting new or updated property recommendations (e.g., changing location, budget, size, etc.), classify it as **recommendation**.
        - If the user is asking a follow-up question about an existing property or seeking clarification based on previously shared results, classify it as **discussion**.
        - If user is asking for more recommendation of properties, classify it as **more**.

        Examples of queries that should be classified as **recommendation**:
        - "Show me villas in South Delhi instead of North Delhi"
        - "I want something under 1.5 Cr with 3 BHK"
        - "Now show me options with a garden"

        Examples of queries that should be classified as **discussion**:
        - "What is the price per square foot of the second property?"
        - "Which one had the highest maintenance charges?"
        - "Was there a villa with 5 bathrooms?"

        Examples of queries that should be classifies as **more**:
        - "show me more properties"
        - "is that all you have"
        - "can I have more properties"
        - "show me more similar to this"

        Respond with **one word only**: `recommendation` or `discussion` or `more`

        User query:
        → {last_human_text}

        Consider the previous conversation context while giving result, the previous conversation includes the question, the responses, also the agent who was responsible for giving the answer:
        {previous_conversation}
        """,
        ),
    ]

    model = get_chat_model()
    sup = model.with_structured_output(SupervisorEvaluation)
    response = sup.invoke(messages)
    return {"supervisor_evaluation": response.evaluation}

