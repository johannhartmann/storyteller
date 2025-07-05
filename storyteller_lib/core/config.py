"""
StoryCraft Agent - Configuration and setup.

This module provides a centralized configuration for the storyteller application,
including LLM initialization, memory store setup, and other shared resources.
"""

# Standard library imports
import gc
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Union

# Third party imports
import psutil
from dotenv import load_dotenv
from langchain.embeddings import init_embeddings
from langchain_anthropic import ChatAnthropic
from langchain_community.cache import SQLiteCache
from langchain_core.caches import BaseCache
from langchain_core.globals import set_llm_cache
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver

# Local imports
from storyteller_lib.core.logger import config_logger as logger
from storyteller_lib.persistence.database import initialize_db_manager
from storyteller_lib.persistence.memory import memory_manager as mm, MemoryManager

# Load environment variables
load_dotenv()

# LLM Configuration
# Model provider options
MODEL_PROVIDER_OPTIONS = ["openai", "anthropic", "gemini"]
DEFAULT_PROVIDER = "openai"  # Changed from gemini to avoid timeout issues

# Model configurations for each provider
MODEL_CONFIGS = {
    "openai": {
        "default_model": "gpt-4.1-mini",  # Changed to gpt-4.1-mini for faster responses
        "env_key": "OPENAI_API_KEY",
        "max_tokens": 32768,
    },
    "anthropic": {
        "default_model": "claude-sonnet-4",
        "env_key": "ANTHROPIC_API_KEY",
        "max_tokens": 64000,
    },
    "gemini": {
        "default_model": "gemini-2.5-flash-preview-05-20",
        "env_key": "GEMINI_API_KEY",
        "max_tokens": 1000000,
    },
}

# Default settings
DEFAULT_MODEL_PROVIDER = os.environ.get("DEFAULT_MODEL_PROVIDER", DEFAULT_PROVIDER)
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", None)  # Specific model override
DEFAULT_TEMPERATURE = 0.7
DEFAULT_CACHE_TYPE = "sqlite"  # Only sqlite cache is supported
CACHE_LOCATION = os.environ.get(
    "CACHE_PATH",
    os.environ.get(
        "CACHE_LOCATION", str(Path.home() / ".storyteller" / "cache" / "llm_cache.db")
    ),
)
# Define the path for the SQLite memory database
MEMORY_DB_PATH = os.environ.get(
    "MEMORY_DB_PATH", str(Path.home() / ".storyteller" / "memory.sqlite")
)

# Language Configuration (moved before database init to avoid circular import)
DEFAULT_LANGUAGE = os.environ.get(
    "DEFAULT_LANGUAGE", "english"
)  # Default language from .env or fallback to english
print(f"[CONFIG] DEFAULT_LANGUAGE set to: {DEFAULT_LANGUAGE}")

# Database Configuration
DATABASE_PATH = os.environ.get(
    "STORY_DATABASE_PATH", str(Path.home() / ".storyteller" / "story_database.db")
)

# Initialize database manager and memory manager
db_manager = initialize_db_manager(DATABASE_PATH)
memory_manager = MemoryManager(db_manager)
# Set the global memory manager instance in the module
import storyteller_lib.persistence.memory as mm_module

mm_module.memory_manager = memory_manager
# Dictionary mapping language codes to their full names
SUPPORTED_LANGUAGES = {
    "english": "English",
    "spanish": "Spanish",
    "french": "French",
    "german": "German",
    "italian": "Italian",
    "portuguese": "Portuguese",
    "russian": "Russian",
    "japanese": "Japanese",
    "chinese": "Chinese",
    "korean": "Korean",
    "arabic": "Arabic",
    "hindi": "Hindi",
}


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

    cache = SQLiteCache(database_path=CACHE_LOCATION)
    set_llm_cache(cache)

    return cache


# Initialize the cache
cache = setup_cache()


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> BaseChatModel:
    """
    Get an instance of the LLM with the specified parameters.

    Args:
        provider: The model provider to use (openai, anthropic, gemini)
        model: The model name to use (defaults to provider's default model)
        temperature: The temperature setting (defaults to 0.7)
        max_tokens: The maximum number of tokens to generate (defaults to provider's max_tokens)

    Returns:
        A configured LLM instance
    """
    # If provider is explicitly provided, use it (command line takes precedence)
    # Otherwise, use the environment variable or default
    provider = provider or os.environ.get("MODEL_PROVIDER") or DEFAULT_MODEL_PROVIDER
    temp = temperature or DEFAULT_TEMPERATURE

    # Validate provider
    if provider not in MODEL_PROVIDER_OPTIONS:
        logger.warning(
            f"Invalid provider '{provider}'. Falling back to {DEFAULT_PROVIDER}."
        )
        provider = DEFAULT_PROVIDER

    # Get provider config
    provider_config = MODEL_CONFIGS[provider]
    # Use model parameter, then DEFAULT_MODEL env var, then provider's default
    model_name = model or DEFAULT_MODEL or provider_config["default_model"]
    api_key_env = provider_config["env_key"]
    api_key = os.environ.get(api_key_env)

    # Check if API key is available
    if not api_key:
        logger.warning(
            f"No API key found for {provider} (env: {api_key_env}). Falling back to {DEFAULT_PROVIDER}."
        )
        provider = DEFAULT_PROVIDER
        provider_config = MODEL_CONFIGS[provider]
        model_name = model or DEFAULT_MODEL or provider_config["default_model"]
        api_key = os.environ.get(provider_config["env_key"])

        # If still no API key, raise error
        if not api_key:
            raise ValueError(
                f"No API key found for {provider}. Please set {provider_config['env_key']} in your .env file."
            )

    # Use provided max_tokens or get from provider config
    tokens = max_tokens or provider_config.get("max_tokens")

    # Create the appropriate LLM instance based on provider
    if provider == "openai":
        return ChatOpenAI(
            model=model_name,
            temperature=temp,
            openai_api_key=api_key,
            max_tokens=tokens,
        )
    elif provider == "anthropic":
        return ChatAnthropic(
            model=model_name,
            temperature=temp,
            anthropic_api_key=api_key,
            max_tokens=tokens,
        )
    elif provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temp,
            google_api_key=api_key,
            max_tokens=tokens,
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")


# Initialize the default LLM instance
llm = get_llm()

# Track the current provider for Gemini-specific handling
_current_provider = None


def get_current_provider() -> str:
    """Get the current LLM provider being used."""
    global _current_provider
    if _current_provider is None:
        _current_provider = os.environ.get("MODEL_PROVIDER") or DEFAULT_MODEL_PROVIDER
    return _current_provider


def get_llm_with_structured_output(
    response_schema: Dict[str, Any],
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> BaseChatModel:
    """
    Get an LLM instance configured for structured output using LangChain's with_structured_output.

    Args:
        response_schema: JSON schema or Pydantic model defining the expected output structure
        provider: The model provider (defaults to current provider)
        model: The model name to use
        temperature: The temperature setting
        max_tokens: Maximum tokens to generate

    Returns:
        A configured LLM instance with structured output
    """
    # Get the base LLM
    base_llm = get_llm(provider, model, temperature, max_tokens)

    # Use LangChain's with_structured_output method
    return base_llm.with_structured_output(response_schema)


# Define the memory namespace consistently
MEMORY_NAMESPACE = "storyteller"


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
        "percent": process.memory_percent(),
    }


# State cleanup utility
def cleanup_old_state(
    state: Dict[str, Any], current_chapter: str, current_scene: Optional[str] = None
) -> Dict[str, Any]:
    """
    Remove old state data that's no longer needed to reduce memory usage.

    Args:
        state: The current state dictionary
        current_chapter: The current chapter being processed
        current_scene: The current scene being processed (optional)

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

    # 1. Clean up old scene content to save memory
    if "chapters" in state:
        chapters_update = {}
        for ch_num, chapter in state["chapters"].items():
            try:
                ch_int = int(ch_num)
                # For chapters more than 1 behind current, clear scene content
                if ch_int < current_ch_num - 1:
                    if "scenes" in chapter:
                        scenes_update = {}
                        for sc_num, scene in chapter["scenes"].items():
                            if (
                                "content" in scene
                                and isinstance(scene["content"], str)
                                and len(scene["content"]) > 100
                            ):
                                # Replace content with placeholder
                                scenes_update[sc_num] = {
                                    "content": f"[Cleared - was {len(scene['content'])} chars]"
                                }
                        if scenes_update:
                            chapters_update[ch_num] = {"scenes": scenes_update}
            except (ValueError, TypeError):
                pass

        if chapters_update:
            cleanup_updates["chapters"] = chapters_update

    # 2. Clean up current_scene_content if we've moved to a new scene
    if current_scene and "current_scene_content" in state:
        cleanup_updates["current_scene_content"] = "[Previous scene cleared]"

    # 3. Clean up creative elements for old chapters
    if "creative_elements" in state:
        creative_keys_to_remove = []
        for key in state["creative_elements"]:
            # Check if this is a chapter-specific creative element
            if "ch" in key and "_sc" in key:
                # Extract chapter number
                try:
                    ch_match = key.split("ch")[1].split("_")[0]
                    ch_num = int(ch_match)
                    # Keep only current and recent chapters (within 1 chapter)
                    if ch_num < current_ch_num - 1:
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
    # Database optimization is now handled by the database manager

    # Force garbage collection
    gc.collect()

    return cleanup_updates


# Translation utility for guidance text
from langchain_core.messages import HumanMessage


def translate_guidance(guidance_text: str, target_language: str) -> str:
    """
    Translate guidance text to the target language using LLM.

    Args:
        guidance_text: The text to translate (in English)
        target_language: The target language code

    Returns:
        Translated guidance text
    """
    if target_language.lower() == DEFAULT_LANGUAGE:
        return guidance_text

    # Check if language is supported
    if target_language.lower() not in SUPPORTED_LANGUAGES:
        logger.warning(
            f"Unsupported language '{target_language}'. Falling back to {DEFAULT_LANGUAGE}."
        )
        return guidance_text

    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[target_language.lower()]

    # Use template system
    from storyteller_lib.prompts.renderer import render_prompt

    prompt = render_prompt(
        "translate_guidance",
        "english",  # Always use English template for translation instructions
        language_name=language_name,
        guidance_text=guidance_text,
    )

    try:
        translated_guidance = llm.invoke([HumanMessage(content=prompt)]).content
        return translated_guidance
    except Exception as e:
        logger.error(f"Translation failed: {str(e)}")
        return guidance_text  # Fallback to original text if translation fails


def get_story_config() -> Dict[str, Any]:
    """
    Load story configuration from database.
    This is a helper function to be used by nodes that need access to configuration.

    Returns:
        Dictionary with genre, tone, language, author, initial_idea
    """
    from storyteller_lib.persistence.database import get_db_manager

    # Default values
    config = {
        "genre": "fantasy",
        "tone": "epic",
        "language": DEFAULT_LANGUAGE,
        "author": "",
        "initial_idea": "",
    }

    db_manager = get_db_manager()
    if db_manager:
        try:
            with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT genre, tone, language, author, initial_idea, research_worldbuilding 
                    FROM story_config WHERE id = 1
                """
                )
                result = cursor.fetchone()
                if result:
                    config["genre"] = result["genre"] or config["genre"]
                    config["tone"] = result["tone"] or config["tone"]
                    config["language"] = result["language"] or config["language"]
                    config["author"] = result["author"] or ""
                    config["initial_idea"] = result["initial_idea"] or ""
                    # Add research worldbuilding config
                    config["world_building_research"] = {
                        "enable_research": bool(result["research_worldbuilding"])
                    }
        except Exception as e:
            logger.error(f"Failed to load story config: {e}")

    return config


# Final garbage collection
gc.collect()
gc.collect()
