from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig

from findmyhome.config import get_chat_model
from .state import QueryEnhancer, RecommendationState
from ..memory import get_user_preferences_memory


def query_enhancer_agent(state: RecommendationState, config: RunnableConfig):
    msgs = state.get("user_query", []) or []
    last_human_text: str = msgs[-1] if msgs else ""
    all_user_messages = msgs[:]

    user_id = config.get("configurable", {}).get("user_id", "anonymous")

    # Retrieve user preferences from memory
    user_preferences = ""
    if user_id != "anonymous":
        prefs = get_user_preferences_memory(user_id)
        if prefs:
            user_preferences = f"\n\n### User's Saved Preferences:\n{prefs}\nUse these preferences to fill in missing details in the query.\n"

    messages = [
        SystemMessage(content="You are a query enhancer agent responsible for enhancing and structuring the user query."),
        HumanMessage(
            content=f"""
You will receive a natural language user query along with the previous conversation context.

### Your Task:
- Interpret the **true user intent**, even if the query is vague, informal, or incomplete.
- Rewrite the query into a **clear, unambiguous, enhanced version** that makes explicit what the user wants.
- Extract values and normalize them to match the **database schema** below.
- Always return a structured response with all required keys. If the user did not specify a value, set it to `None`.
- Use the user's saved preferences to keep the user preferences in mind, but the previous questions asked by user should be given priority (if present)because there user might change their preferences. 

User's Saved Preferences:
{user_preferences}

---

### Database Schema:

**Columns**:
- city
- has_balcony
- min_beds
- max_price
- min_baths
- min_area
- property_type
- room_type

**Allowed Values**:
- city: `['Chennai', 'Bangalore', 'Hyderabad', 'Mumbai', 'Thane', 'Kolkata', 'Pune', 'New Delhi']`
- has_balcony: `[True, False]`
- property_type: `['Flat', 'Independent House', 'Villa', 'Studio']`
- room_type: `['BHK', 'RK', 'R', 'BH']`

---

### Special Handling Rules:

1. **BHK / Room-Type Mapping**
   Normalize variants like "2 bhk", "3B", "1rk", "4 r" → `"2 BHK"`, `"3 BHK"`, `"1 RK"`, `"4 R"`.
   Use the `room_type` field for type and `min_beds` for number.

2. **City Matching**
   Map mentions like "delhi", "newdelhi", "banglore" → standardized values (case-sensitive):
   `['Chennai', 'Bangalore', 'Hyderabad', 'Mumbai', 'Thane', 'Kolkata', 'Pune', 'New Delhi']`.

3. **PropertyType Recognition**
   Normalize terms like "apartment", "flat" → `Flat`;
   "villa" → `Villa`;
   "independent house" → `Independent House`;
   "studio" → `Studio`.

4. **Numeric Extraction**
   - "under 1 crore" → `max_price = 10000000`
   - "below 50L" → `max_price = 5000000`
   - "more than 1200 sq ft" → `min_area = 1200`

   Normalize Indian currency terms:
   - `L` → Lakh (100000)
   - `Cr` → Crore (10000000)

5. **Boolean Detection**
   If query mentions "with balcony" → `has_balcony=True`;
   If query mentions "without balcony" → `has_balcony=False`.

6. **Missing Values**
   If the user does not specify something, set its value to `None`.

7. CITY NORMALIZATION & NEARBY MAPPING
   - Only return one of these in "city": ['Chennai','Bangalore','Hyderabad','Mumbai','Thane','Kolkata','Pune','New Delhi'].
   - If the user mentions a locality that belongs to a metro region, set "city" to the nearest allowed city AND keep the locality as free-text (do NOT discard it).
     NCR → New Delhi: Gurgaon/Gurugram/Noida/Greater Noida/Ghaziabad/Faridabad/Dwarka/Saket/Rohini/Pitampura...
     Mumbai region: Navi Mumbai → city="Mumbai"; (Thane is already allowed)
     Pune region: Pimpri/Chinchwad/PCMC/Hinjewadi/Wakad → city="Pune"
     Hyderabad region: Secunderabad/Gachibowli/HITEC → city="Hyderabad"
     Bangalore region: Whitefield/Electronic City/HSR/Koramangala → city="Bangalore"
     Chennai region: Tambaram/Velachery/OMR/ECR → city="Chennai"
     Kolkata region: Howrah/Salt Lake/New Town (Rajarhat) → city="Kolkata"
   - If the current message lacks a city but a previous message in the conversation mentions a locality, apply the same mapping using the conversation context.
   - Reflect this locality in "enhanced_user_query" as “near <locality>”.
---

### Output Format:

Return: enhanced_user_query, city, has_balcony, min_beds, max_price, min_baths, min_area, property_type, room_type
- If a mapped city was inferred, include it in enhanced_user_query (“… in <City> …”).
- If a locality was mentioned, include “near <locality>” in enhanced_user_query.

---

### Examples:

**Input**: "Show me 2 bhk in south delhi under 1 cr with balcony"
**Output**:
{{
  "enhanced_user_query": "2 BHK Flats in New Delhi priced under 1 crore with a balcony",
  "city": "New Delhi",
  "has_balcony": true,
  "min_beds": 2,
  "max_price": 10000000,
  "min_baths": None,
  "min_area": None,
  "property_type": "Flat",
  "room_type": "BHK"
}}

**Input**: "Looking for a villa in banglore above 1200 sqft"
**Output**:
{{
  "enhanced_user_query": "Villas in Bangalore with a minimum area of 1200 sq ft",
  "city": "Bangalore",
  "has_balcony": None,
  "min_beds": None,
  "max_price": None,
  "min_baths": None,
  "min_area": 1200,
  "property_type": "Villa",
  "room_type": None
}}

---

User query:
→ {last_human_text}

Previous conversation for context:
{all_user_messages}
""",
        ),
    ]

    model = get_chat_model(temperature=0.5)
    query_enhancer = model.with_structured_output(QueryEnhancer)
    response = query_enhancer.invoke(messages)
    return {"query_enhancer": response}

