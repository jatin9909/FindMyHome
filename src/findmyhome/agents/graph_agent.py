from __future__ import annotations

from typing import Dict, List

from langchain_core.prompts import PromptTemplate

from findmyhome.config import get_chat_model, get_graph
from .state import RecommendationState
from langchain_neo4j import GraphCypherQAChain


CYPHER_GENERATION_TEMPLATE = """Generate a single Cypher query for Neo4j.

Rules (hard constraints):
- Output ONLY the Cypher query. No prose.
- Start with MATCH and end with `RETURN p`.
- NEVER use `p.name` in WHERE clauses or equality checks.
  - Do not assign to `p.name`.
  - Do not use `p.name = ...` or `toLower(p.name) CONTAINS ...`.

Free-text rules (hard):
- For free-text keywords, USE ONLY:
    `toLower(p.description) CONTAINS "<kw>"`
  (You may also use `toLower(n.name) CONTAINS "<locality>"` ONLY if the user explicitly provides a locality/neighborhood name.)
- NEVER guess locality/neighborhood names. Only use `n.name` if user mentioned it.
- When combining free-text with other filters, ALWAYS wrap the free-text group in parentheses.

SCHEMA REALITY (hard):
- City is stored on nodes as:
  - Property: `p.cityName`  (authoritative for city filtering)
  - Neighborhood: `n.cityName` (may exist)
  - City node: `c.name`
- Many properties may not have `IN_NEIGHBORHOOD` / `PART_OF` relationships. So:
  - If city/cities are provided, ALWAYS filter by `p.cityName` (mandatory).
  - You may additionally match Neighborhood/City for context, but NEVER rely only on c.name.

NO-OPTIONAL-FILTER RULE (hard):
- If a variable is used in WHERE, it MUST come from a mandatory MATCH, never OPTIONAL MATCH.
- Therefore:
  - If you need to filter by city using `c.name`, then the City path MUST be `MATCH (p)-[:IN_NEIGHBORHOOD]->(n)-[:PART_OF]->(c)`.
  - Do NOT use OPTIONAL MATCH for that path.
- OPTIONAL MATCH is allowed only when the matched variables are NOT used in WHERE (e.g., just for enrichment), but you still must end with `RETURN p`.

Property type normalization:
- If the user mentions a property type, normalize to:
    flat/apartment -> "Flat"
    villa -> "Villa"
    studio -> "Studio"
    independent house -> "Independent House"
- When type is specified, use a mandatory match:
    MATCH (p:Property)-[:OF_TYPE]->(:PropertyType {{name:"<Normalized>"}})
- If type is NOT specified, do not match PropertyType.

Room/layout filtering:
- Only include room/layout matching if user specifies it (e.g., "2 BHK", "1 RK"):
    MATCH (p)-[:HAS_LAYOUT]->(rt:RoomType)
  Then filter by rt.name and/or rt.rooms as needed.
- Do NOT OPTIONAL MATCH room/layout if you will filter on rt.

Structured filtering:
- Cities allowed: ['Chennai','Bangalore','Hyderabad','Mumbai','Thane','Kolkata','Pune','New Delhi'].
- If the user specifies one or more cities, the query MUST include:
    `toLower(trim(p.cityName)) IN <cities_lower_list>`
  This is mandatory and is the primary city guardrail.
- NEVER use OR logic like `(c.name = ... OR p.cityName = ...)`.
  City constraint must be a single consistent constraint (prefer p.cityName).
- Use trim+lower for string comparisons.

Neighborhood/locality:
- If the user explicitly provides a locality/neighborhood name, then:
    MATCH (p)-[:IN_NEIGHBORHOOD]->(n:Neighborhood)
  and add:
    `toLower(n.name) CONTAINS "<locality_lower>"`
- If city is also specified and you want to validate via graph, then use:
    MATCH (p)-[:IN_NEIGHBORHOOD]->(n:Neighborhood)-[:PART_OF]->(c:City)
    AND `toLower(trim(c.name)) IN <cities_lower_list>`
  Only do this if it does not reduce recall unintentionally.

Numeric filters (use only if present in question):
- price range: p.price >= <min_price> AND p.price <= <max_price>
- area range: p.totalArea >= <min_area> AND p.totalArea <= <max_area>
- beds/baths minimums if requested
- balcony: p.hasBalcony = true if requested

Operator precedence:
- Always parenthesize free-text group before AND-ing other constraints.

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
    model = get_chat_model(temperature=0.2)
    chain = GraphCypherQAChain.from_llm(
        graph=graphdb,
        llm=model,
        cypher_prompt=CYPHER_PROMPT,
        verbose=False,
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

