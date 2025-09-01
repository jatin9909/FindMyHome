from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from findmyhome.config import get_chat_model
from .state import RecommendationState


def discussion_agent(state: RecommendationState):
    msgs = state.get("user_query", []) or []
    last_human_text: str = msgs[-1] if msgs else ""
    previous_conversation = state.get("turn_log", []) or []

    messages = [
        SystemMessage(content="You are a discussion agent that answers user queries based on previously shown property recommendations by graphdb agent and the converation might also include your previous responses."),
        HumanMessage(
            content=f"""
You will receive a user query along with the previous conversation context.

Your task is to:
- Answer questions related to properties that have already been shown to the user.
- Use details from the prior recommendations to provide an accurate and relevant response.
- Do not generate or recommend new properties. Only discuss, compare, or elaborate on existing ones.
- If the user's query refers to a specific property (e.g., by location, name, or index), use that reference to fetch details from the previous context.
- If the user's query is not clear then you can ask for the clarification so that you can give better answer to the user.

Examples of valid user questions for this agent:
- "What is the price per square foot of the Uttam Nagar villa?"
- "Which property had 5 bathrooms?"
- "Is the Vasant Kunj property still available?"
- "Can you compare the carpet area of the second and third options?"

Keep your answer factual, helpful, and concise.

user query -
{last_human_text}

previous discussion with Graphdb agent and discussion agent, question key specifies the the actual query asked by user, and the query_used means the refined query created by query correction agent -
{previous_conversation}
""",
        ),
    ]

    model = get_chat_model()
    response = model.invoke(messages)
    return {
        "discussion": [response.content],
        "turn_log": [
            {
                "question": last_human_text,
                "answered_by": "discussion_agent",
                "answer": response.content,
                "query_used": "Similar to question",
                "recommended_properties": "No property recommended by discusison agent for the user question",
            }
        ],
    }

