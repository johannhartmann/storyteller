"""Memory management functions for storing and retrieving story elements."""

import json
from typing import Any

from storyteller_lib.core.logger import get_logger
from storyteller_lib.persistence.database import get_db_manager

logger = get_logger(__name__)


def create_memory(
    key: str, value: Any, namespace: str = "storyteller"
) -> None:
    """Create a new memory entry in the database."""
    db_manager = get_db_manager()
    if not db_manager:
        raise RuntimeError("Database manager not available")
        
    try:
        value_str = json.dumps(value) if not isinstance(value, str) else value
        db_manager.create_memory(key, value_str, namespace)
        logger.debug(f"Created memory: {key} in namespace: {namespace}")
    except Exception as e:
        logger.error(f"Failed to create memory {key}: {e}")
        raise


def update_memory(
    key: str, value: Any, namespace: str = "storyteller"
) -> None:
    """Update an existing memory entry."""
    db_manager = get_db_manager()
    if not db_manager:
        raise RuntimeError("Database manager not available")
        
    value_str = json.dumps(value) if not isinstance(value, str) else value
    db_manager.update_memory(key, value_str, namespace)
    logger.debug(f"Updated memory: {key} in namespace: {namespace}")


def delete_memory(key: str, namespace: str = "storyteller") -> None:
    """Delete a memory entry."""
    db_manager = get_db_manager()
    if not db_manager:
        raise RuntimeError("Database manager not available")
        
    db_manager.delete_memory(key, namespace)
    logger.debug(f"Deleted memory: {key} from namespace: {namespace}")


def search_memories(
    query: str, namespace: str = "storyteller"
) -> list[dict[str, Any]]:
    """Search for memories containing the query string."""
    db_manager = get_db_manager()
    if not db_manager:
        raise RuntimeError("Database manager not available")
        
    results = db_manager.search_memories(query, namespace)
    logger.debug(f"Found {len(results)} memories for query: {query}")

    # Parse JSON values back to objects where possible
    processed_results = []
    for result in results:
        try:
            value = json.loads(result["value"])
        except (json.JSONDecodeError, TypeError):
            value = result["value"]

        processed_results.append(
            {"key": result["key"], "value": value, "namespace": result["namespace"]}
        )

    return processed_results


def get_memory(
    key: str, namespace: str = "storyteller"
) -> Any | None:
    """Get a specific memory by key."""
    db_manager = get_db_manager()
    if not db_manager:
        raise RuntimeError("Database manager not available")
        
    result = db_manager.get_memory(key, namespace)
    if result:
        try:
            return json.loads(result["value"])
        except (json.JSONDecodeError, TypeError):
            return result["value"]
    return None


def manage_memory(
    action: str,
    key: str,
    value: Any | None = None,
    namespace: str = "storyteller",
) -> dict[str, Any]:
    """Function interface compatible with the old manage_memory_tool.invoke() calls."""
    if action == "create":
        create_memory(key, value, namespace)
        return {"status": "created", "key": key}
    elif action == "update":
        update_memory(key, value, namespace)
        return {"status": "updated", "key": key}
    elif action == "delete":
        delete_memory(key, namespace)
        return {"status": "deleted", "key": key}
    else:
        raise ValueError(f"Unknown action: {action}")


def search_memory(
    query: str, namespace: str = "storyteller"
) -> list[dict[str, Any]]:
    """Function interface compatible with the old search_memory_tool.invoke() calls."""
    return search_memories(query, namespace)