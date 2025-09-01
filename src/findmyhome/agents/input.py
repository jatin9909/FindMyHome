from __future__ import annotations

from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from findmyhome.config import get_chat_model
from .state import InputEvaluation, RecommendationState


def input_agent(state: RecommendationState):
    msgs = state.get("user_query", []) or []
    last_human_text: str = msgs[-1] if msgs else ""
    all_user_messages: List[str] = msgs[:]

    messages = [
        SystemMessage(content="You are an input evaluator agent"),
        HumanMessage(
            content=f"""
        You need to evaluate this user query to check if it is related to property recommendation or not, or if user is asking an irrelevant query.
        User can ask anything. You need to be careful while evaluating the query, because the user query might not be directly related to property recommendation,
        but considering the previous conversation history it might still be relevant. For example, the user might be asking about a property shown earlier,
        or following up on a recommendation.

        Classify the query as:
        - "valid" → If it's a query about property recommendation or property-related discussion (direct or follow-up).
        - "invalid" → If it is completely unrelated to real estate or property context.

        Respond with one word only: valid or invalid.

        Here are some examples of valid and invalid queries:
        Valid:
        - Show me villas in South Delhi under 2 crores
        - What’s the price per square foot in Vasant Kunj?
        - Can you show me the properties that were listed in Uttam Nagar again?
        - Is there a villa with 5 bedrooms and a garden?
        - What is the total area of the second property you showed?
        - Are there good schools nearby the Rajpur Khurd property?
        - Which property had the highest maintenance charges?

        Invalid:
        - Who won the cricket match yesterday?
        - Tell me a joke.
        - What is the capital of Spain?
        - Summarize today’s news headlines.
        - Recommend a good laptop under 50,000.
        - What is ChatGPT?
        - How do I cook biryani?
        - who are you?
        - What you can do?
        - How you works?
        - Any query related to Rent.

        Now analyze the following user query and classify it as "valid" or "invalid":
        current user query -> {last_human_text}
        all_previous_users_query -> {all_user_messages}
        """,
        )
    ]

    model = get_chat_model()
    input_evaluator_agent = model.with_structured_output(InputEvaluation)
    response = input_evaluator_agent.invoke(messages)
    return {"input_agent": response.evaluation}


def invalid_agent(state: RecommendationState):
    msgs = state.get("user_query", []) or []
    last_human_text: str = msgs[-1] if msgs else ""
    previous_conversation = state.get("turn_log", []) or []

    messages = [
        SystemMessage(content="You are an agent who recieves the invalid user query"),
        HumanMessage(
            content=f"""
You will receive a user query that has already been classified as invalid because it is unrelated to the property recommendation platform we are building.

Your task is to:
- Politely and constructively explain to the user why their query is not valid in this context.
- Gently remind them that the assistant is designed to help with property search, comparisons, and related discussions.
- Encourage them to ask something relevant about properties, real estate, or follow-ups on previous recommendations.
- If user asks who are you or what you do? then you need to explain about the whole property recommendation system accordingly, and how you recommend properties in some selected cities ['Chennai', 'Bangalore', 'Hyderabad', 'Mumbai', 'Thane', 'Kolkata', 'Pune', 'New Delhi'] in India based on these following requirements: balcony, beds, price, baths, area, property type (['Flat', 'Independent House', 'Villa', 'Studio']), room type (['BHK', 'RK', 'R', 'BH']).
- If user has asked any question related to rent you need to tell user that we don't have any property for rent as of yet, we only have properties to sale.

Here are examples of relevant property-related queries, or you can add some more:
- "Show me 3 BHK apartments in Chennai under 1 crore."
- "What’s the total area of the villa you showed earlier?"
- "Is there a school near the property in Vasant Kunj?"

Always keep the tone friendly and helpful.

User query:
→ {last_human_text}

This is the context of the previous conversation, take the previous conversation in context while replying to the user
{previous_conversation}
""",
        )
    ]

    model = get_chat_model()
    response = model.invoke(messages)
    return {"invalid": response.content}

