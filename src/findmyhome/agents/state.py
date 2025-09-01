from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict, Annotated
import operator

from langgraph.graph import START, END  # re-export convenience
from langgraph.graph.message import add_messages  # noqa: F401  (used in type annotations)
from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel, Field


# Pydantic models for structured outputs
class InputEvaluation(BaseModel):
    evaluation: Literal["valid", "invalid"] = Field(..., description="Input agent evaluation result")


class SupervisorEvaluation(BaseModel):
    evaluation: Literal["recommendation", "discussion", "more"] = Field(..., description="Supervisor agent evaluation result")


City = Literal['Chennai','Bangalore','Hyderabad','Mumbai','Thane','Kolkata','Pune','New Delhi']
PropertyType = Literal['Flat','Independent House','Villa','Studio']
RoomType = Literal['BHK','RK','R','BH']


class QueryEnhancer(BaseModel):
    enhanced_user_query: str
    city: Optional[City] = None
    has_balcony: Optional[bool] = None
    min_beds: Optional[int] = None
    max_price: Optional[int] = None
    min_baths: Optional[int] = None
    min_area: Optional[int] = None
    property_type: Optional[PropertyType] = None
    room_type: Optional[RoomType] = None


class DatabaseRow(TypedDict, total=False):
    id: str
    name: str
    cityName: str
    beds: Optional[int]
    baths: Optional[int]
    price: Optional[float]
    totalArea: Optional[float]
    pricePerSqft: Optional[float]
    room_type: Optional[str]
    property_type: Optional[str]
    hasBalcony: Optional[bool]
    description: Optional[str]
    score: Optional[float]


DatabaseResponse = List[DatabaseRow]
SQLQuery = str
PropertyIDList = List[str]


class QueryEnhancerOutput(TypedDict, total=False):
    enhanced_user_query: str
    city: Optional[City]
    has_balcony: Optional[bool]
    min_beds: Optional[int]
    max_price: Optional[int]
    min_baths: Optional[int]
    min_area: Optional[int]
    property_type: Optional[PropertyType]
    room_type: Optional[RoomType]


class TurnEntry(TypedDict, total=False):
    question: str
    answered_by: Literal["recommendation_agent", "discussion_agent", "invalid"]
    answer: str
    query_used: str
    recommended_properties: List[Dict[str, Any]]


class RecommendationState(TypedDict):
    user_query: Annotated[List[str], operator.add]

    input_agent: Literal["valid", "invalid"]
    supervisor_evaluation: Literal["recommendation", "discussion","more"]

    invalid: str
    discussion: Annotated[List[str], operator.add]
    query_correction: str

    graph_db_agent: Annotated[List[str], operator.add]
    # store the recommended properties (the 'context' array) for each run
    graph_raw_history: Annotated[List[List[Dict[str, Any]]], operator.add]
    previous_generated_graph_query: str
    graph_property_id_shown: Annotated[List[str], operator.add]

    query_enhancer: QueryEnhancerOutput
    database_responses: Annotated[List[DatabaseResponse], operator.add]
    database_generated_query: SQLQuery
    database_property_id_shown: Annotated[PropertyIDList, operator.add]

    augmentation_summary: str
    turn_log: Annotated[List[TurnEntry], operator.add]


def latest_human_text(msgs: List[BaseMessage]) -> str:
    for m in reversed(msgs or []):
        if isinstance(m, HumanMessage):
            return m.content
    return ""

