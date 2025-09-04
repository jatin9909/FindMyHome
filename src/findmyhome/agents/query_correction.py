from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from findmyhome.config import get_chat_model
from .state import QueryEnhancer, RecommendationState


def query_correction_agent(state: RecommendationState):
    msgs = state.get("user_query", []) or []
    last_human_text: str = msgs[-1] if msgs else ""
    all_user_messages = msgs[:]

    messages = [
        SystemMessage(content="You are a query correction agent responsible for mapping user queries to structured graph-compatible queries."),
        HumanMessage(
            content=f"""
        You will receive a natural language user query along with the previous conversation context.

        Your job is to:
        - Interpret the **true user intent**, even if the original query is vague, informal, or uses colloquial terms.
        - Rewrite the query into a **clear, unambiguous version** that maps directly to the graph schema—making it easier for the graph query agent to generate an accurate Cypher query.
        - Ensure the rewritten query includes **explicit values for nodes and relationships** wherever possible.

        ### Graph Schema Overview:

        **Node Labels and Properties**:
        - `Property`: id, name, totalArea, pricePerSqft, price, beds, baths, hasBalcony, description
        - `Neighborhood`: name
        - `City`: name
        - `PropertyType`: name
        - `RoomType`: name, rooms

        **Relationships**:
        - (:Property)-[:IN_NEIGHBORHOOD]->(:Neighborhood)
        - (:Property)-[:OF_TYPE]->(:PropertyType)
        - (:Property)-[:HAS_LAYOUT]->(:RoomType)
        - (:Neighborhood)-[:PART_OF]->(:City)

        ---

        ### Special Handling Rules:

        1. **BHK / Room-Type Mapping**:
            If the user mentions any variant like "2 bhk", "3B", "1rk", or "4 R", normalize these to match:
            - Valid types: `['BHK', 'RK', 'R', 'BH']`
            - Convert them into the format: "2 BHK", "1 RK", etc.

        2. **City Matching**:
            If a location is mentioned, ensure it matches among them:
            - `['Chennai', 'Bangalore', 'Hyderabad', 'Mumbai', 'Thane', 'Kolkata', 'Pune', 'New Delhi']`
            - Be mindful of misspellings or case mismatches like "delhi", "newdelhi", "banglore" etc.

        3. **PropertyType Recognition**:
            If the user refers to a living style (e.g., "apartment", "villa", "independent house", "studio", "flat"), normalize to among them:
            - `['Flat', 'Independent House', 'Villa', 'Studio']`

        4. If the user says "like the one you showed me earlier", then you need to transform the query to include the previous conditions.
        5. Never set any value of property name and Neighborhood name in your generated text from user query.
        6. Any free text will always be in description field of property.
        ---

        ### Output Format:

        Respond with enhanced query, don't overcomplicate things, but make sure that query must be adhered to the scehma we have.

        ---

        ### Examples:

        **Input**: "show me 2 bhk in south delhi under 1 cr"
        **Output**: "2 BHK Flats in New Delhi priced under 10000000"

        **Input**: "I want a villa in banglore with garden"
        **Output**: "Villa in Bangalore with a garden"

        **Input**: "something cheap in hyderabad with balcony"
        **Output**: "Properties in Hyderabad with a balcony and low price"

        ---

        User query:
        → {last_human_text}

        Take reference of previous questions asked by user while enhancing the user query:
        {all_user_messages}
        """,
        ),
    ]

    model = get_chat_model()
    response = model.invoke(messages)
    return {"query_correction": response.content}

