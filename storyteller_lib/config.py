"""
StoryCraft Agent - Configuration and setup.

This module provides a centralized configuration for the storyteller application,
including LLM initialization, memory store setup, and other shared resources.
"""

import os
import gc
import logging
import sqlite3
import psutil
from typing import Optional, Union, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.caches import BaseCache
from langchain_core.globals import set_llm_cache
from langchain_community.cache import SQLiteCache
from langchain.embeddings import init_embeddings
from langgraph.checkpoint.sqlite import SqliteSaver
# Import LangMem tools
from langmem import create_manage_memory_tool, create_search_memory_tool, create_memory_manager, create_prompt_optimizer
# Import our memory adapter
from storyteller_lib.memory_adapter import MemoryStoreAdapter

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# LLM Configuration
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_CACHE_TYPE = "sqlite"  # Only sqlite cache is supported
CACHE_LOCATION = os.environ.get("CACHE_LOCATION", str(Path.home() / ".storyteller" / "llm_cache.db"))
# Define the path for the SQLite memory database
MEMORY_DB_PATH = os.environ.get("MEMORY_DB_PATH", str(Path.home() / ".storyteller" / "memory.sqlite"))

def setup_cache(cache_type: str = DEFAULT_CACHE_TYPE) -> Optional[BaseCache]:
    """
    Set up the LLM cache based on the specified type.
    
    Args:
        cache_type: The type of cache to use ("sqlite" or "none")
        
    Returns:
        The configured cache instance
    """
    if cache_type.lower() == "none":
        logger.info("LLM caching disabled")
        return None
    
    # Create parent directories for cache if needed
    cache_path = Path(CACHE_LOCATION)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Using SQLite LLM cache at {CACHE_LOCATION}")
    cache = SQLiteCache(database_path=CACHE_LOCATION)
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

# Define the memory namespace consistently
MEMORY_NAMESPACE = ("storyteller",)

# Create parent directories for memory database if needed
memory_db_dir = Path(MEMORY_DB_PATH).parent
memory_db_dir.mkdir(parents=True, exist_ok=True)

# Create a persistent SqliteSaver instance
memory_conn = sqlite3.connect(MEMORY_DB_PATH, check_same_thread=False)
sqlite_store = SqliteSaver(memory_conn)

# Set up the database schema
sqlite_store.setup()

# Create a memory adapter that bridges between LangMem and SqliteSaver
memory_store = MemoryStoreAdapter(sqlite_store, namespace=MEMORY_NAMESPACE)

# Force garbage collection after creating the memory store
gc.collect()

# Create memory tools with the adapter
manage_memory_tool = create_manage_memory_tool(namespace=MEMORY_NAMESPACE, store=memory_store)
search_memory_tool = create_search_memory_tool(namespace=MEMORY_NAMESPACE, store=memory_store)

# Force garbage collection after creating memory tools
gc.collect()

# Create memory manager for background processing
# Note: memory_manager doesn't accept a store parameter directly
memory_manager = create_memory_manager(
    f"openai:{DEFAULT_MODEL}",
    instructions="Extract key narrative elements, character developments, plot points, and thematic elements from the story content.",
    enable_inserts=True
)

# Force garbage collection after creating memory manager
gc.collect()

# Create prompt optimizer
# Note: prompt_optimizer doesn't accept a store parameter directly
prompt_optimizer = create_prompt_optimizer(
    f"openai:{DEFAULT_MODEL}",
    kind="metaprompt",
    config={"max_reflection_steps": 3}
)
# Memory profiling utility
def log_memory_usage(label: str) -> Dict[str, Any]:
    """
    Log current memory usage with a descriptive label.
    
    Args:
        label: A descriptive label for this memory measurement
        
    Returns:
        A dictionary with memory usage statistics
    """
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    
    # Calculate memory usage in MB
    rss_mb = memory_info.rss / 1024 / 1024
    vms_mb = memory_info.vms / 1024 / 1024
    
    # Log the memory usage
    logger.info(f"MEMORY [{label}]: RSS={rss_mb:.2f}MB, VMS={vms_mb:.2f}MB")
    
    # Force garbage collection
    gc.collect()
    
    # Return memory stats for potential storage
    return {
        "timestamp": "now",
        "label": label,
        "rss_mb": rss_mb,
        "vms_mb": vms_mb,
        "percent": process.memory_percent()
    }

# State cleanup utility
def cleanup_old_state(state: Dict[str, Any], current_chapter: str) -> Dict[str, Any]:
    """
    Remove old state data that's no longer needed to reduce memory usage.
    
    Args:
        state: The current state dictionary
        current_chapter: The current chapter being processed
        
    Returns:
        A dictionary with state updates to remove old data
    """
    # Convert current chapter to int for comparison
    try:
        current_ch_num = int(current_chapter)
    except ValueError:
        current_ch_num = 1
    
    # Initialize cleanup updates
    cleanup_updates = {}
    
    # 1. Clean up creative elements for old chapters
    if "creative_elements" in state:
        creative_keys_to_remove = []
        for key in state["creative_elements"]:
            # Check if this is a chapter-specific creative element
            if "ch" in key and "_sc" in key:
                # Extract chapter number
                try:
                    ch_match = key.split("ch")[1].split("_")[0]
                    ch_num = int(ch_match)
                    # Keep only current and recent chapters (within 2 chapters)
                    if ch_num < current_ch_num - 2:
                        creative_keys_to_remove.append(key)
                except (ValueError, IndexError):
                    pass
        
        # Add removal updates for creative elements
        if creative_keys_to_remove:
            cleanup_updates["creative_elements"] = {
                key: None for key in creative_keys_to_remove
            }
    
    # 2. Clean up old continuity reviews
    if "continuity_review_history" in state:
        history = state["continuity_review_history"]
        if len(history) > 3:  # Keep only the 3 most recent
            # Sort by chapter number if possible
            review_keys = list(history.keys())
            review_keys_to_remove = []
            
            for key in review_keys:
                if "ch" in key:
                    try:
                        ch_num = int(key.split("ch")[1])
                        if ch_num < current_ch_num - 2:
                            review_keys_to_remove.append(key)
                    except (ValueError, IndexError):
                        pass
            
            # Add removal updates for continuity reviews
            if review_keys_to_remove:
                cleanup_updates["continuity_review_history"] = {
                    key: None for key in review_keys_to_remove
                }
    
    # 3. Optimize SQLite database if needed
    if sqlite_store and hasattr(sqlite_store, "conn"):
        try:
            sqlite_store.conn.execute("PRAGMA optimize;")
            sqlite_store.conn.execute("VACUUM;")
            logger.info("SQLite database optimized")
        except Exception as e:
            logger.error(f"Error optimizing SQLite database: {e}")
    
    # Force garbage collection
    gc.collect()
    
    return cleanup_updates

# Final garbage collection
gc.collect()
gc.collect()
