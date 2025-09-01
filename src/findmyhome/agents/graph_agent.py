from __future__ import annotations

from typing import Dict, List

from langchain_core.prompts import PromptTemplate

from findmyhome.config import get_chat_model, get_graph
from .state import RecommendationState
from langchain_neo4j import GraphCypherQAChain


CYPHER_GENERATION_TEMPLATE = """Generate a single Cypher query for Neo4j.

Rules:
- Start with MATCH and end with `RETURN p`. No prose.
- If the user mentions a property type word:
    flat/apartment → PropertyType.name="Flat"
    villa → "Villa"
    studio → "Studio"
    independent house → "Independent House"
  Even if user mentions any other property type outside of the allowed property type then you need to convert that into one of the available property options with your best available knowledge.
  Add an OF_TYPE match with that normalized value (do NOT treat it as free text).

- FREE-TEXT → DESCRIPTION RULE:
  After normalizing any structured fields (city/neighborhood/property type/room type/price/area),
  treat remaining words/phrases (including “near <place>”) as keywords and filter with:
  (toLower(p.name) CONTAINS "<kw>" OR toLower(p.description) CONTAINS "<kw>")
  If multiple keywords remain, join them with AND (each must match).

CITY NORMALIZATION & NEARBY MAPPING
- Allowed cities: ['Chennai','Bangalore','Hyderabad','Mumbai','Thane','Kolkata','Pune','New Delhi']
  (return ONLY one of these in the city field)
- If the user mentions a locality that is effectively part of a metro region, map it to the nearest allowed city AND keep the mentioned locality as a free-text keyword (do NOT lose it).

Schema:
{schema}

Question:
{question}
"""


CYPHER_PROMPT = PromptTemplate(input_variables=["question"], template=CYPHER_GENERATION_TEMPLATE)


def graph_db_agent(state: RecommendationState):
    msgs = state.get("user_query", []) or []
    last_human_text: str = msgs[-1] if msgs else ""
    qc = state.get("query_correction") or ""
    query_used = qc if qc else last_human_text

    # Build chain

    graphdb = get_graph(enhanced_schema=True)
    model = get_chat_model(temperature=0.5)
    chain = GraphCypherQAChain.from_llm(
        graph=graphdb,
        llm=model,
        cypher_prompt=CYPHER_PROMPT,
        verbose=True,
        validate_cypher=True,
        allow_dangerous_requests=True,
        return_intermediate_steps=True,
        top_k=10,
    )

    response: Dict = chain.invoke({"query": query_used})
    answer = response.get("result") or "No answer."
    steps: List = response.get("intermediate_steps") or []
    ctx_step = next((s for s in steps if isinstance(s, dict) and "context" in s), {})
    generated_graph_query = next(
        (s["query"] for s in steps if isinstance(s, dict) and "query" in s),
        "",
    )
    recommended_props = ctx_step.get("context", [])

    prop_ids: List[str] = []
    seen = set()
    for item in recommended_props:
        pid = (item.get("p") or {}).get("id")
        if pid and pid not in seen:
            seen.add(pid)
            prop_ids.append(str(pid))

    return {
        "graph_db_agent": [answer],
        "graph_raw_history": [recommended_props],
        "previous_generated_graph_query": generated_graph_query,
        "graph_property_id_shown": prop_ids,
    }

