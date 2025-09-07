from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional, List
import math

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings
# from neo4j.debug import watch
import logging

# Set up logger
logger = logging.getLogger(__name__)

# watch("neo4j")

# load variables from a local .env if present
load_dotenv(override=False)
os.environ["AZURE_OPENAI_API_KEY"] = os.getenv('AZURE_OPENAI_API_KEY')


class Settings(BaseSettings):
    # Azure OpenAI - Chat
    azure_openai_api_key: str = Field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY", ""))
    azure_endpoint: str = Field(default_factory=lambda: os.getenv("AZURE_ENDPOINT", ""))
    azure_openai_api_version: str = Field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_VERSION"))
    azure_openai_deployment: str = Field(default_factory=lambda: os.getenv("AZURE_OPENAI_DEPLOYMENT"))

    # Azure OpenAI - Embeddings (often key/env naming differs)
    azure_openai_key: str = Field(default_factory=lambda: os.getenv("AZURE_OPENAI_KEY", os.getenv("AZURE_OPENAI_API_KEY", "")))
    azure_embed_deployment: str = Field(default_factory=lambda: os.getenv("AZURE_EMBED_DEPLOYMENT", ""))
    embed_dim: int = Field(default_factory=lambda: int(os.getenv("EMBED_DIM", "1536")))
    azure_api_version: str = Field(default_factory=lambda: os.getenv("AZURE_API_VERSION"))
    azure_openai_endpoint: str = Field(default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", ""))

    # Neo4j
    neo4j_url: str = Field(default_factory=lambda: os.getenv("NEO4J_URL", ""))
    neo4j_username: str = Field(default_factory=lambda: os.getenv("NEO4J_USERNAME", "neo4j"))
    neo4j_password: str = Field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", ""))
    neo4j_database: str = Field(default_factory=lambda: os.getenv("NEO4J_DATABASE", "neo4j"))

    # Postgres (Neon)
    neon_url: str = Field(default_factory=lambda: os.getenv("NEON_URL", ""))

    # Redis
    redis_host: str = Field(default_factory=lambda: os.getenv("REDIS_HOST"))
    redis_port: int = Field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    redis_password: str = Field(default_factory=lambda: os.getenv("REDIS_PASSWORD"))

    class Config:
        env_prefix = "FINDMYHOME_"
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]


# Lazy imports, keeping these here avoids cycles in modules that need clients
def get_chat_model(temperature: float = 0.5):
    """Return an AzureChatOpenAI model configured from env."""
    from langchain_openai import AzureChatOpenAI

    s = get_settings()
    return AzureChatOpenAI(
        azure_endpoint=s.azure_endpoint,
        azure_deployment=s.azure_openai_deployment,
        openai_api_version=s.azure_openai_api_version,
        # temperature=temperature,
    )


def get_azure_openai_client():
    """Return raw Azure OpenAI client for embeddings, etc."""
    from openai import AzureOpenAI

    s = get_settings()
    return AzureOpenAI(
        api_key=s.azure_openai_key,
        api_version=s.azure_api_version,
        azure_endpoint=s.azure_openai_endpoint,
    )


def get_graph(enhanced_schema: bool = True):
    from langchain_neo4j import Neo4jGraph
    s = get_settings()
    return Neo4jGraph(
        url=s.neo4j_url,
        username=s.neo4j_username,
        password=s.neo4j_password,
        database=s.neo4j_database,
        enhanced_schema=enhanced_schema,
    )

def get_redis_checkpointer():
    """Return a Redis checkpointer for conversation state persistence."""
    from redis import Redis
    from langgraph.checkpoint.redis import RedisSaver
    
    s = get_settings()
    redis_client = Redis(
                    host=s.redis_host,
                    port=s.redis_port,
                    decode_responses=True,
                    username="default",
                    password=s.redis_password,
                )
    
    redis_saver = RedisSaver(redis_client=redis_client)
    redis_saver.setup()
    return redis_saver

def get_pg_connection():
    import psycopg2
    s = get_settings()
    if not s.neon_url:
        raise RuntimeError("NEON_URL not configured; set it or use a .env file")
    return psycopg2.connect(s.neon_url)

def embed_query(text: str) -> List[float]:
    """Embed a single query string with Azure OpenAI (deployment from settings)."""
    client = get_azure_openai_client()
    s = get_settings()
    resp = client.embeddings.create(model=s.azure_embed_deployment, input=[text])
    emb = resp.data[0].embedding
    if len(emb) != s.embed_dim:
        raise ValueError(f"Unexpected embedding dim {len(emb)} (expected {s.embed_dim})")
    
    # Validate embedding values
    for i, val in enumerate(emb):
        if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
            logger.warning(f"Invalid embedding value at index {i}: {val}")
            emb[i] = 0.0
    
    return emb