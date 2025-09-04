from __future__ import annotations

from typing import Dict, List, Set

from langchain_core.messages import HumanMessage, SystemMessage

from findmyhome.config import get_chat_model
from .state import RecommendationState
from langgraph.prebuilt.chat_agent_executor import create_react_agent


def accumulative_query_agent(state: RecommendationState):
    db_responses_history = state.get("database_responses", [])
    db_results = db_responses_history[-1] if db_responses_history else []
    
    graph_history_all = state.get("graph_raw_history", [])
    graph_history = graph_history_all[-1][0] if graph_history_all else []

    graph_props_raw: List[Dict] = []
    for run in graph_history:
        if isinstance(run, list):
            for item in run:
                if isinstance(item, Dict):
                    p = item.get("p") or item.get("property") or None
                    if isinstance(p, Dict):
                        graph_props_raw.append(p)

    db_ids: List[str] = []
    for row in db_results:
        if isinstance(row, Dict) and "id" in row and row["id"] is not None:
            db_ids.append(str(row["id"]))

    graph_ids: List[str] = []
    seen: Set[str] = set()
    for p in graph_props_raw:
        pid = p.get("id")
        if pid and str(pid) not in seen:
            seen.add(str(pid))
            graph_ids.append(str(pid))

    set_db = set(db_ids)
    set_graph = set(graph_ids)
    overlap_ids = sorted(set_db & set_graph)
    only_db_ids = sorted(set_db - set_graph)
    only_graph_ids = sorted(set_graph - set_db)

    db_by_id = {str(r["id"]): r for r in db_results if isinstance(r, Dict) and "id" in r}
    graph_by_id = {str(p.get("id")): p for p in graph_props_raw if isinstance(p, Dict) and p.get("id")}

    unified_ids = overlap_ids + only_db_ids + only_graph_ids
    unified_properties: List[Dict] = []
    for pid in unified_ids:
        if pid in db_by_id:
            unified_properties.append(db_by_id[pid])
        else:
            unified_properties.append(graph_by_id[pid])

    DROP_KEYS = {"id", "score"}
    sanitized_unified = [
        {k: v for k, v in (p or {}).items() if k not in DROP_KEYS} for p in unified_properties
    ]

    msgs_list = state.get("user_query", []) or []
    last_human_text = msgs_list[-1] if msgs_list else ""
    qc = state.get("query_correction") or ""
    query_used = qc if qc else last_human_text
    all_user_messages = msgs_list[:]

    messages = [
        SystemMessage(content="You create a single, user-friendly summary of property recommendations without revealing any system or data source details."),
        HumanMessage(
            content=f"""
You will receive:
- The latest user query
- The prior conversation context
- A combined de-duplicated list of property recommendations

Your Task:
- Provide a holistic, easy-to-read summary covering each property.
- Use clear bullets or a numbered list.
- Emphasize location, type, price, area (sq ft), bedrooms, bathrooms, and standout features.
- Do not mention internal systems, databases, or where the data came from.
- Be concise and neutral.
- There might be some instances where the recommended properties are not directly matches with the user query or helping the user but still you can craft your response in such way to make the recommended properties relevant to the user.


User query: {query_used}
Previous conversation: {all_user_messages}
Combined property recommendations (already de-duplicated):
{sanitized_unified}
""",
        ),
    ]

    answer = get_chat_model().invoke(messages)
    response_text = getattr(answer, "content", str(answer))

    return {
      "augmentation_summary": response_text,
      "turn_log":[{
      "question":last_human_text,
      "answered_by":"recommendation_agent",
      "answer":response_text,
      "query_used":query_used,
      "recommended_properties":sanitized_unified
      }]
  }

