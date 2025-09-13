from __future__ import annotations

import os
import ulid
import logging
from datetime import datetime
from enum import Enum
from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field

from redis import Redis
from redisvl.index import SearchIndex
from redisvl.schema.schema import IndexSchema
from redisvl.query import VectorRangeQuery
from redisvl.query.filter import Tag
from redisvl.utils.vectorize.text.azureopenai import AzureOpenAITextVectorizer

from findmyhome.config import get_settings, embed_query

import math
import numpy as np
from redisvl.utils.vectorize.text.openai import OpenAITextVectorizer

# Set up logger
logger = logging.getLogger(__name__)

class MemoryType(str, Enum):
    EPISODIC = "episodic"  # User preferences and experiences
    SEMANTIC = "semantic"  # General knowledge

class Memory(BaseModel):
    content: str
    memory_type: MemoryType
    metadata: str

class StoredMemory(Memory):
    id: str
    memory_id: str = Field(default_factory=lambda: str(ulid.ULID()))
    created_at: datetime = Field(default_factory=datetime.now)
    user_id: Optional[str] = None
    thread_id: Optional[str] = None

class UserPreferences(BaseModel):
    min_price: int
    max_price: int
    min_area: int  
    max_area: int
    preferred_cities: List[str]

# Azure deployment **name** (not the base model id)
s = get_settings() 

openai_embed = AzureOpenAITextVectorizer(
    model=s.azure_embed_deployment,
    api_config={
        "azure_endpoint": s.azure_openai_endpoint,  # e.g. https://<resource>.openai.azure.com
        "api_version": s.azure_api_version,                            # or the version you use
        "api_key": s.azure_openai_key,
    }
    )

# Redis connection for memory
def get_redis_client():
    settings = get_settings()
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
        password=settings.redis_password,
    )

# Memory schema for Redis
memory_schema = IndexSchema.from_dict({
    "index": {
        "name": "findmyhome_memories",
        "prefix": "memory",
        "key_separator": ":",
        "storage_type": "json",
    },
    "fields": [
        {"name": "content", "type": "text"},
        {"name": "memory_type", "type": "tag"},
        {"name": "metadata", "type": "text"},
        {"name": "created_at", "type": "text"},
        {"name": "user_id", "type": "tag"},
        {"name": "memory_id", "type": "tag"},
        {
            "name": "embedding",
            "type": "vector",
            "attrs": {
                "algorithm": "flat",
                "dims": 1536,  # OpenAI embedding dimension
                "distance_metric": "cosine",
                "datatype": "float32",
            },
        },
    ],
})

# Initialize memory system
redis_client = get_redis_client()
# openai_embed = OpenAITextVectorizer(model="text-embedding-3-small")

try:
    long_term_memory_index = SearchIndex(
        schema=memory_schema,
        redis_client=redis_client,
        validate_on_load=True
    )
    long_term_memory_index.create(overwrite=False)  # Don't overwrite existing
    logger.info("Long-term memory index ready")
except Exception as e:
    logger.warning(f"Memory index might already exist: {e}")

SYSTEM_USER_ID = "system"

def similar_memory_exists(
    content: str,
    memory_type: MemoryType,
    user_id: str = SYSTEM_USER_ID,
    distance_threshold: float = 0.1,
) -> bool:
    """Check if a similar long-term memory already exists."""
    try:
        content_embedding = openai_embed.embed(content)
        
        vector_query = VectorRangeQuery(
            vector=content_embedding,
            num_results=1,
            vector_field_name="embedding",
            distance_threshold=distance_threshold,
            return_fields=["id"],
        )
        
        # Use same string filter approach
        # filter_str = f"@user_id:{{{user_id}}} @memory_type:{{{memory_type.value}}}"
        # vector_query.set_filter(filter_str)
        
        results = long_term_memory_index.query(vector_query)
        return len(results) > 0
    except Exception as e:
        logger.error(f"Error checking similar memory: {e}")
        return False

def store_memory(
    content: str,
    memory_type: MemoryType,
    user_id: str = SYSTEM_USER_ID,
    thread_id: Optional[str] = None,
    metadata: Optional[str] = None,
):
    """Store a long-term memory in Redis with deduplication."""
    if metadata is None:
        metadata = "{}"

    logger.info(f"Preparing to store memory for user {user_id}: {content}")

    if similar_memory_exists(content, memory_type, user_id):
        logger.info("Similar memory found, skipping storage")
        return

    try:
        embedding = openai_embed.embed(content)
        
        memory_data = {
            "user_id": user_id or SYSTEM_USER_ID,
            "content": content,
            "memory_type": memory_type.value,
            "metadata": metadata,
            "created_at": datetime.now().isoformat(),
            "embedding": embedding,
            "memory_id": str(ulid.ULID()),
        }

        long_term_memory_index.load([memory_data])
        logger.info(f"Stored {memory_type} memory: {content}")
    except Exception as e:
        logger.error(f"Error storing memory: {e}")

def retrieve_memories(
    query: str,
    memory_type: Union[Optional[MemoryType], List[MemoryType]] = None,
    user_id: str = SYSTEM_USER_ID,
    distance_threshold: float = 0.5,
    limit: int = 5,
) -> List[StoredMemory]:
    """Retrieve relevant memories using vector similarity search."""
    try:
        logger.debug(f"Retrieving memories for user {user_id}, query: {query}")

        # Get the embedding and normalize any extreme values
        query_embedding = openai_embed.embed(query)

        # Create the query WITHOUT filter_expression first
        vector_query = VectorRangeQuery(
            vector=query_embedding,
            return_fields=[
                "content", "memory_type", "metadata", "created_at",
                "memory_id", "user_id"
            ],
            num_results=limit,
            vector_field_name="embedding",
            distance_threshold=distance_threshold,
        )

        # Build simple string filters (this approach works!)
        # base_filters = [f"@user_id:{{{user_id or SYSTEM_USER_ID}}}"]

        # if memory_type:
        #     if isinstance(memory_type, list):
        #         vals = [mt.value if hasattr(mt, "value") else str(mt) for mt in memory_type]
        #         base_filters.append(f"@memory_type:{{{'|'.join(vals)}}}")
        #     else:
        #         mt_val = memory_type.value if hasattr(memory_type, "value") else str(memory_type)
        #         base_filters.append(f"@memory_type:{{{mt_val}}}")

        # Set the filter using string approach
        # filter_str = " ".join(base_filters)
        # logger.info(f"Using filter: {filter_str}")
        # vector_query.set_filter(filter_str)

        results = long_term_memory_index.query(vector_query)
        logger.info(f"Got {len(results)} results with filters")

        memories = []
        for doc in results:
            try:
                memory = StoredMemory(
                    id=doc["id"],
                    memory_id=doc["memory_id"],
                    user_id=doc["user_id"],
                    memory_type=MemoryType(doc["memory_type"]),
                    content=doc["content"],
                    created_at=doc["created_at"],
                    metadata=doc["metadata"],
                )
                memories.append(memory)
            except Exception as e:
                logger.error(f"Error parsing memory: {e}")
                continue
        
        return memories
    except Exception as e:
        logger.error(f"Error retrieving memories: {e}")
        return []

def store_user_preferences(user_id: str, preferences: UserPreferences):
    """Store user preferences as episodic memory."""
    
    # Format preferences as natural language
    content = f"""User preferences: 
    - Budget: ₹{preferences.min_price:,} to ₹{preferences.max_price:,}
    - Area: {preferences.min_area} to {preferences.max_area} sq ft
    - Preferred cities: {', '.join(preferences.preferred_cities)}"""
    
    
    metadata = {
        "type": "user_preferences",
        "min_price": preferences.min_price,
        "max_price": preferences.max_price,
        "min_area": preferences.min_area,
        "max_area": preferences.max_area,
        "cities": preferences.preferred_cities,
    }
    
    store_memory(
        content=content,
        memory_type=MemoryType.EPISODIC,
        user_id=user_id,
        metadata=str(metadata)
    )

def get_user_preferences_memory(user_id: str) -> Optional[str]:
    """Retrieve user preferences from memory."""
    memories = retrieve_memories(
        query="user preferences budget price area cities",
        memory_type=MemoryType.EPISODIC,
        user_id=user_id,
        limit=3
    )
    
    if memories:
        # Return the most recent preference
        return memories[0].content
    return None 

def clear_all_redis_data():
    """Clear ALL Redis data - both memory and checkpointer data."""
    try:
        # Clear all keys (nuclear option)
        redis_client.flushdb()
        logger.info("Cleared entire Redis database")
        
        # Recreate the memory index
        try:
            long_term_memory_index.create(overwrite=True)
            logger.info("Recreated findmyhome_memories index")
        except Exception as e:
            logger.warning(f"Could not recreate memory index: {e}")
            
    except Exception as e:
        logger.error(f"Error clearing Redis: {e}")

def clear_specific_memory_data():
    """Clear only memory-related data, preserving other Redis data."""
    try:
        # Clear memory keys
        memory_keys = redis_client.keys("memory:*")
        if memory_keys:
            redis_client.delete(*memory_keys)
            logger.info(f"Cleared {len(memory_keys)} memory entries")
        
        # Clear checkpointer keys (these might contain the problematic data)
        checkpoint_keys = redis_client.keys("checkpoint:*")
        thread_keys = redis_client.keys("thread:*")
        writes_keys = redis_client.keys("writes:*")
        
        all_checkpoint_keys = checkpoint_keys + thread_keys + writes_keys
        if all_checkpoint_keys:
            redis_client.delete(*all_checkpoint_keys)
            logger.info(f"Cleared {len(all_checkpoint_keys)} checkpoint entries")
            
        # Clear any vector index keys
        ft_keys = redis_client.keys("ft:*")
        if ft_keys:
            for key in ft_keys:
                try:
                    # Try to drop the index if it exists
                    index_name = key.replace("ft:", "")
                    redis_client.ft(index_name).dropindex(delete_documents=True)
                    logger.info(f"Dropped index: {index_name}")
                except:
                    pass
        
        # Recreate your memory index
        try:
            long_term_memory_index.create(overwrite=True)
            logger.info("Recreated memory index")
        except Exception as e:
            logger.warning(f"Memory index recreation: {e}")
            
    except Exception as e:
        logger.error(f"Error in specific cleanup: {e}")

if __name__ == "__main__":
    # Try the specific cleanup first
    clear_specific_memory_data()
    
    # If you still have issues, uncomment this nuclear option:
    # clear_all_redis_data()