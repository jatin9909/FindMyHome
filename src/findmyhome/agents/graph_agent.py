from __future__ import annotations

from typing import Dict, List

from langchain_core.prompts import PromptTemplate

from findmyhome.config import get_chat_model, get_graph
from .state import RecommendationState
from langchain_neo4j import GraphCypherQAChain


CYPHER_GENERATION_TEMPLATE = """Generate a single Cypher query for Neo4j.

Rules (hard constraints):
- Start with MATCH and end with `RETURN p`. No prose.
- NEVER use `p.name` in WHERE clauses or equality checks.
  - Do not assign to `p.name`.
  - Do not use `p.name = ...` or `toLower(p.name) CONTAINS ...`.
- For free-text, USE ONLY `toLower(p.description) CONTAINS ...` and/or neighborhood names (`toLower(n.name) CONTAINS ...`) if you match a neighborhood node.
- When combining free-text terms with other filters, ALWAYS parenthesize the free-text group:
    WHERE ( ...free-text conditions joined by AND... ) AND ...other filters...

Property type normalization:
- If the user mentions a property type, normalize:
    flat/apartment -> PropertyType.name = "Flat"
    villa -> "Villa"
    studio -> "Studio"
    independent house -> "Independent House"
- Add an OF_TYPE pattern with the normalized value:
    (p:Property)-[:OF_TYPE]->(pt:PropertyType {{name:"<Normalized>"}})

Structured filtering:
- Cities allowed: ['Chennai','Bangalore','Hyderabad','Mumbai','Thane','Kolkata','Pune','New Delhi'].
- Prefer graph relationships for locality/city:
    (p)-[:IN_NEIGHBORHOOD]->(n:Neighborhood)-[:PART_OF]->(c:City {{name:"<City>"}})
  If only a city is given, match City directly as above.
- Room type:
    (p)-[:HAS_LAYOUT]->(rt:RoomType {{name:"<RoomType>"}})
  If rooms count is given (e.g., 2 BHK), add `rt.rooms >= <min_rooms>` (or exact if specified).
- Numeric filters (use only if present): 
    p.price <= <max_price>, p.totalArea >= <min_area>, p.beds >= <min_beds>, p.baths >= <min_baths>
- Balcony: if requested, include `p.hasBalcony = true`.

Free-text mapping:
- After extracting structured fields (city/neighborhood/property type/room type/price/area), treat remaining tokens (e.g., "near Hinjawadi", "IT city") as keywords.
- Map metro/locality mentions to graph nodes when possible:
    - Keep the original token as a free-text keyword (on description) AND, if it corresponds to a neighborhood, also match (n:Neighborhood {{name:"<Locality>"}}) or `toLower(n.name) CONTAINS "<locality_lower>"`.
- Example free-text group form:
    (toLower(p.description) CONTAINS "<kw1>" AND toLower(p.description) CONTAINS "<kw2>")

Operator precedence:
- When combining free-text with other constraints, wrap the free-text conditions in parentheses before adding AND constraints for city/price/etc.

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

