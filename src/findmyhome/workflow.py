from __future__ import annotations

from typing import Dict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from .agents.state import RecommendationState
from .agents.input import input_agent, invalid_agent
from .agents.supervisor import supervisor_agent
from .agents.discussion import discussion_agent
from .agents.query_correction import query_correction_agent
from .agents.graph_agent import graph_db_agent
from .agents.query_enhancer import query_enhancer_agent
from .agents.sql_agent import query_database_agent, more_recommendation
from .agents.accumulate import accumulative_query_agent
from .config import get_redis_checkpointer

def recommendation_agent(state: RecommendationState):
    # fan-out node placeholder (routes to both query_correction and query_enhancer)
    return {}


def input_agent_evaluation(state: RecommendationState):
    return state.get("input_agent", "invalid")


def supervisor_agent_evaluation(state: RecommendationState):
    return state.get("supervisor_evaluation", "recommendation")


def build_graph() -> StateGraph:
    graph = StateGraph(RecommendationState)

    graph.add_node("input_agent", input_agent)
    graph.add_node("invalid_query", invalid_agent)
    graph.add_node("supervisor", supervisor_agent)
    graph.add_node("discussion_query", discussion_agent)
    graph.add_node("query_correction", query_correction_agent)
    graph.add_node("graph_db_agent", graph_db_agent)
    graph.add_node("more_recommendation", more_recommendation)
    graph.add_node("query_enhancer", query_enhancer_agent)
    graph.add_node("query_database", query_database_agent)
    graph.add_node("accumulative_query_results", accumulative_query_agent)
    graph.add_node("recommendation_node", recommendation_agent)

    graph.add_edge(START, "input_agent")
    graph.add_conditional_edges(
        "input_agent", input_agent_evaluation, {"invalid": "invalid_query", "valid": "supervisor"}
    )
    graph.add_edge("invalid_query", END)
    graph.add_conditional_edges(
        "supervisor",
        supervisor_agent_evaluation,
        {"recommendation": "recommendation_node", "discussion": "discussion_query", "more": "more_recommendation"},
    )
    graph.add_edge("recommendation_node", "query_correction")
    graph.add_edge("recommendation_node", "query_enhancer")
    graph.add_edge("query_correction", "graph_db_agent")
    graph.add_edge("query_enhancer", "query_database")
    graph.add_edge("graph_db_agent", "accumulative_query_results")
    graph.add_edge("query_database", "accumulative_query_results")
    graph.add_edge("discussion_query", END)
    graph.add_edge("more_recommendation", END)
    graph.add_edge("accumulative_query_results", END)

    return graph


def compile_workflow(checkpointer=None):
    checkpointer = checkpointer or get_redis_checkpointer()
    graph = build_graph()
    return graph.compile(checkpointer=checkpointer) # here need to pass redis_saver

