"""
StoryCraft Agent - Configuration and setup.

This module provides a centralized configuration for the storyteller application,
including LLM initialization, memory store setup, and other shared resources.
"""

import os
import logging
from typing import Optional, Union, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.caches import BaseCache
from langchain_core.globals import set_llm_cache
from langchain_community.cache import SQLiteCache, InMemoryCache
from langgraph.store.memory import InMemoryStore
from langmem import create_manage_memory_tool, create_search_memory_tool, create_memory_manager, create_prompt_optimizer

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# LLM Configuration
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_CACHE_TYPE = "sqlite"  # Options: "memory", "sqlite", "none"
CACHE_LOCATION = os.environ.get("CACHE_LOCATION", str(Path.home() / ".storyteller" / "llm_cache.db"))

def setup_cache(cache_type: str = DEFAULT_CACHE_TYPE) -> Optional[BaseCache]:
    """
    Set up the LLM cache based on the specified type.
    
    Args:
        cache_type: The type of cache to use ("memory", "sqlite", or "none")
        
    Returns:
        The configured cache instance
    """
    if cache_type.lower() == "none":
        logger.info("LLM caching disabled")
        return None
    
    # Create parent directories for cache if needed
    if cache_type.lower() == "sqlite":
        cache_path = Path(CACHE_LOCATION)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
    
    cache = None
    if cache_type.lower() == "memory":
        logger.info("Using in-memory LLM cache")
        cache = InMemoryCache()
    elif cache_type.lower() == "sqlite":
        logger.info(f"Using SQLite LLM cache at {CACHE_LOCATION}")
        cache = SQLiteCache(database_path=CACHE_LOCATION)
    
    if cache:
        set_llm_cache(cache)
    
    return cache

# Initialize the cache
cache = setup_cache()

def get_llm(model: Optional[str] = None, temperature: Optional[float] = None) -> BaseChatModel:
    """
    Get an instance of the LLM with the specified parameters.
    
    Args:
        model: The model name to use (defaults to gpt-4o-mini)
        temperature: The temperature setting (defaults to 0.7)
        
    Returns:
        A configured LLM instance
    """
    logger.debug(f"Creating LLM instance with model={model or DEFAULT_MODEL}, temp={temperature or DEFAULT_TEMPERATURE}")
    return ChatOpenAI(
        model=model or DEFAULT_MODEL,
        temperature=temperature or DEFAULT_TEMPERATURE,
        api_key=os.environ.get("OPENAI_API_KEY")
    )

# Initialize the default LLM instance
llm = get_llm()

# Initialize a single memory store instance for both LangMem tools and StateGraph checkpointing
store = InMemoryStore(
    index={
        "dims": 1536,
        "embed": "openai:text-embedding-3-small",
    }
) 

# Define the memory namespace consistently
MEMORY_NAMESPACE = ("storyteller",)

# Create memory tools with explicit store parameter
manage_memory_tool = create_manage_memory_tool(namespace=MEMORY_NAMESPACE, store=store)
search_memory_tool = create_search_memory_tool(namespace=MEMORY_NAMESPACE, store=store)

# Create memory manager for background processing
memory_manager = create_memory_manager(
    f"openai:{DEFAULT_MODEL}",
    instructions="Extract key narrative elements, character developments, plot points, and thematic elements from the story content.",
    enable_inserts=True
)

# Create prompt optimizer
prompt_optimizer = create_prompt_optimizer(
    f"openai:{DEFAULT_MODEL}",
    kind="metaprompt",
    config={"max_reflection_steps": 3}
)