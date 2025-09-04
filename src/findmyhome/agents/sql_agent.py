from __future__ import annotations

from typing import List, Dict, Any, Optional, Union
import numbers
from langchain_core.messages import HumanMessage, SystemMessage
from findmyhome.config import get_azure_openai_client, get_pg_connection, get_settings, get_chat_model, get_graph
from .state import RecommendationState


def embed_query(text: str) -> List[float]:
    """Embed a single query string with Azure OpenAI (deployment from settings)."""
    client = get_azure_openai_client()
    s = get_settings()
    resp = client.embeddings.create(model=s.azure_embed_deployment, input=[text])
    emb = resp.data[0].embedding
    if len(emb) != s.embed_dim:
        raise ValueError(f"Unexpected embedding dim {len(emb)} (expected {s.embed_dim})")
    return emb

def _enhancer_to_dict(enhancer: Any) -> Dict[str, Any]:
    if enhancer is None:
        return {}
    # pydantic v2 model
    if hasattr(enhancer, "model_dump"):
        return enhancer.model_dump()
    # pydantic v1 model
    if hasattr(enhancer, "dict"):
        return enhancer.dict()
    if isinstance(enhancer, dict):
        return enhancer
    return {}

def query_database_agent(state: RecommendationState):
    k = 10
    s = get_settings()

    enh = _enhancer_to_dict(state.get("query_enhancer"))
    enhanced_user_query: str = enh.get("enhanced_user_query") or ""
    city: Optional[str]         = enh.get("city")
    has_balcony: Optional[bool] = enh.get("has_balcony")
    min_beds: Optional[int]     = enh.get("min_beds")
    max_price: Optional[float]  = enh.get("max_price")
    min_baths: Optional[int]    = enh.get("min_baths")
    min_area: Optional[float]   = enh.get("min_area")
    property_type: Optional[str]= enh.get("property_type")
    room_type: Optional[str]    = enh.get("room_type")

    q_vec = embed_query(enhanced_user_query or "")

    # ---- WHERE builder ----
    where: List[str] = []
    params: List[Any] = [q_vec]  # first %s used in SELECT score

    if city:
        where.append('"cityName" ILIKE %s')
        params.append(f"%{city}%")

    if has_balcony is not None:
        where.append('"hasBalcony" = %s')
        params.append(bool(has_balcony))

    if isinstance(min_beds, numbers.Number):
        where.append('beds >= %s')
        params.append(int(min_beds))

    if isinstance(min_baths, numbers.Number):
        where.append('baths >= %s')
        params.append(int(min_baths))

    if isinstance(max_price, numbers.Number):
        where.append('price <= %s')
        params.append(float(max_price))

    if isinstance(min_area, numbers.Number):
        where.append('"totalArea" >= %s')
        params.append(float(min_area))

    if property_type:
        # you already normalize upstream; equality is cleaner than ILIKE if canonicalized
        where.append('property_type = %s')
        params.append(property_type)

    if room_type:
        where.append('room_type = %s')
        params.append(room_type)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
    SELECT
      id, name, "cityName", beds, baths, price, "totalArea", "pricePerSqft",
      room_type, property_type, "hasBalcony",
      description,
      description_embed <=> %s::float8[]::vector({s.embed_dim}) AS score
    FROM properties
    {where_sql}
    ORDER BY description_embed <=> %s::float8[]::vector({s.embed_dim})
    LIMIT %s
    """.strip()

    params_for_query = [params[0]]
    if len(params) > 1:
        params_for_query += params[1:]
    params_for_query += [q_vec, k]

    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params_for_query)
        cols = [c.name for c in cur.description]
        results = [dict(zip(cols, row)) for row in cur.fetchall()]
        generated_query = cur.mogrify(sql, params_for_query).decode("utf-8")

    recommended_ids = [row["id"] for row in results]
    print("generated_query - ", generated_query)

    return {
        "database_generated_query": generated_query,
        "database_property_id_shown": recommended_ids,
        "database_responses": [results],
    }


def more_recommendation(state: RecommendationState):
    msgs = state.get("user_query", []) or []
    last_human_text: str = msgs[-1] if msgs else ""
    qc = state.get("query_correction") or ""
    query_used = qc if qc else last_human_text

    inner = (state.get("previous_generated_graph_query") or "").strip().rstrip(";")
    graph_shown_ids = state.get("graph_property_id_shown") or []
    sql_shown_ids = state.get("database_property_id_shown") or []

    graph_exclude_all = sorted(set(map(str, graph_shown_ids)) | set(map(str, sql_shown_ids)))
    limit = 10

    # 1) Graph query with exclude
    recommended_props_graph: List[Dict] = []
    graph_prop_ids: List[str] = []
    if inner:
        graphdb = get_graph()
        q = f"""
        CALL {{
          {inner}
        }}
        WITH DISTINCT p
        WHERE size($exclude) = 0 OR NOT p.id IN $exclude
        RETURN p
        ORDER BY p.price DESC
        LIMIT $limit
        """
        result_graph = graphdb.query(q, params={"exclude": graph_exclude_all, "limit": limit}) or []
        seen_g = set()
        for item in result_graph:
            pid = (item.get("p") or {}).get("id")
            if pid and pid not in seen_g:
                seen_g.add(pid)
                graph_prop_ids.append(str(pid))
        recommended_props_graph = result_graph

    # 2) SQL with exclude
    enh = state.get("query_enhancer") or {}
    if hasattr(enh, "dict"):
        enh = enh.dict()

    enhanced_user_query = enh.get("enhanced_user_query") or last_human_text
    q_vec = embed_query(enhanced_user_query)

    s = get_settings()
    where: List[str] = []
    params: list = [q_vec]
    city = enh.get("city")
    has_balcony = enh.get("has_balcony")
    min_beds = enh.get("min_beds")
    max_price = enh.get("max_price")
    min_baths = enh.get("min_baths")
    min_area = enh.get("min_area")
    property_type = enh.get("property_type")
    room_type = enh.get("room_type")

    if city:
        where.append('"cityName" ILIKE %s');     params.append(f"%{city}%")
    if has_balcony is not None:
        where.append('"hasBalcony" = %s');       params.append(bool(has_balcony))
    if min_beds is not None:
        where.append('beds >= %s');              params.append(int(min_beds))
    if min_baths is not None:
        where.append('baths >= %s');             params.append(int(min_baths))
    if max_price is not None:
        where.append('price <= %s');             params.append(float(max_price))
    if min_area is not None:
        where.append('"totalArea" >= %s');       params.append(float(min_area))
    if property_type:
        where.append('property_type ILIKE %s');  params.append(f"%{property_type}%")
    if room_type:
        where.append('room_type ILIKE %s');      params.append(f"%{room_type}%")

    # exclude ids
    sql_exclude_ids = list(dict.fromkeys((state.get("database_property_id_shown") or []) + (state.get("graph_property_id_shown") or []) + graph_prop_ids))
    if sql_exclude_ids:
        where.append('NOT (id = ANY(%s))')
        params.append(sql_exclude_ids)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
    SELECT
      id, name, "cityName", beds, baths, price, "totalArea", "pricePerSqft",
      room_type, property_type, "hasBalcony",
      description,
      description_embed <=> %s::float8[]::vector({s.embed_dim}) AS score
    FROM properties
    {where_sql}
    ORDER BY description_embed <=> %s::float8[]::vector({s.embed_dim})
    LIMIT %s
    """

    params_for_query = [params[0]]
    if len(params) > 1:
        params_for_query += params[1:]
    params_for_query += [q_vec, limit]

    results_sql: List[Dict] = []
    generated_query_sql = ""
    with get_pg_connection() as conn, conn.cursor() as cur:
        generated_query_sql = cur.mogrify(sql, params_for_query).decode("utf-8")
        cur.execute(sql, params_for_query)
        cols = [c.name for c in cur.description]
        results_sql = [dict(zip(cols, row)) for row in cur.fetchall()]

    recommended_ids_sql = [r["id"] for r in results_sql]

    # 3) Combine
    graph_props_flat: List[Dict] = []
    for item in recommended_props_graph:
        p = item.get("p") if isinstance(item, dict) else None
        if isinstance(p, dict):
            graph_props_flat.append(p)

    db_by_id = {str(r["id"]): r for r in results_sql if isinstance(r, dict) and "id" in r}
    graph_by_id = {str(p.get("id")): p for p in graph_props_flat if p.get("id")}
    unified_ids = list(dict.fromkeys(list(db_by_id.keys()) + list(graph_by_id.keys())))
    unified_properties = [db_by_id.get(pid, graph_by_id.get(pid)) for pid in unified_ids]

    # 4) Summarize
    if unified_properties:
        last_human_text = msgs[-1] if msgs else ""
        messages = [
            SystemMessage(content="You are a recommendation agent that explains the results of the recommended properties."),
            HumanMessage(
                content=f"""
You will get the user query and the properties which got recommended to the user, and now you have to give a brief summary of the recommended properties to the user.

Few examples:
Here are some villas available in New Delhi:
1. A 3 BHK Villa in Block E, Krishna Nagar, priced at Rs 1.15 Cr with a built-up area of 1250 sq ft. It has 3 bathrooms and no balcony.
2. A 7 BHK Villa in Rajpur Khurd Village, Chhattarpur, with 5 bathrooms, priced at Rs 20 Cr.
...
8. A 1.5 BHK Villa in Sewak Park, New Delhi, priced at Rs 50 L with a built-up area of 550 sq ft. It has 5 bathrooms and no balcony, with no maintenance charges.
These villas offer a range of options in terms of size, price, and amenities in New Delhi.

Important Instructions:
1. Explain about every property that is present in the recommendation (use bullets or numbering).
2. Do not include the 'id' key/value in your final summary output.
3. Do not disclose any internal systems or data sources.

User query:
{last_human_text}

Recommended properties to the user (de-duplicated combined list):
{unified_properties}
""",
            ),
        ]
        answer = get_chat_model().invoke(messages)
        response_text = getattr(answer, "content", str(answer))
    else:
        response_text = "No properties found"

    return {
        "graph_db_agent": [response_text],
        "graph_raw_history": [recommended_props_graph],
        "previous_generated_graph_query": inner,
        "graph_property_id_shown": graph_prop_ids,
        "database_generated_query": generated_query_sql,
        "database_property_id_shown": recommended_ids_sql,
        "database_responses": [results_sql],
        "turn_log": [
            {
                "question": last_human_text,
                "answered_by": "recommendation_agent",
                "answer": response_text,
                "query_used": query_used,
                "recommended_properties": unified_properties,
            }
        ],
    }

