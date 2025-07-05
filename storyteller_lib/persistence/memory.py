"""Memory management module for storing and retrieving story elements."""

import json
from typing import Any

from storyteller_lib.core.logger import get_logger
from storyteller_lib.persistence.database import StoryDatabaseManager

logger = get_logger(__name__)


class MemoryManager:
    """Manages story memories using the database."""

    def __init__(self, db_manager: StoryDatabaseManager):
        self.db_manager = db_manager

    def create_memory(
        self, key: str, value: Any, namespace: str | None = "storyteller"
    ) -> None:
        """Create a new memory entry."""
        try:
            value_str = json.dumps(value) if not isinstance(value, str) else value
            self.db_manager.create_memory(key, value_str, namespace)
            logger.debug(f"Created memory: {key} in namespace: {namespace}")
        except Exception as e:
            logger.error(f"Failed to create memory {key}: {e}")
            # Re-raise to maintain compatibility
            raise

    def update_memory(
        self, key: str, value: Any, namespace: str | None = "storyteller"
    ) -> None:
        """Update an existing memory entry."""
        value_str = json.dumps(value) if not isinstance(value, str) else value
        self.db_manager.update_memory(key, value_str, namespace)
        logger.debug(f"Updated memory: {key} in namespace: {namespace}")

    def delete_memory(self, key: str, namespace: str | None = "storyteller") -> None:
        """Delete a memory entry."""
        self.db_manager.delete_memory(key, namespace)
        logger.debug(f"Deleted memory: {key} from namespace: {namespace}")

    def search_memories(
        self, query: str, namespace: str | None = "storyteller"
    ) -> list[dict[str, Any]]:
        """Search for memories containing the query string."""
        results = self.db_manager.search_memories(query, namespace)
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
        self, key: str, namespace: str | None = "storyteller"
    ) -> Any | None:
        """Get a specific memory by key."""
        result = self.db_manager.get_memory(key, namespace)
        if result:
            try:
                return json.loads(result["value"])
            except (json.JSONDecodeError, TypeError):
                return result["value"]
        return None


# Global instance that will be initialized in config.py
memory_manager: MemoryManager | None = None


def manage_memory(
    action: str,
    key: str,
    value: Any | None = None,
    namespace: str | None = "storyteller",
) -> dict[str, Any]:
    """Function interface compatible with the old manage_memory_tool.invoke() calls."""
    if memory_manager is None:
        raise RuntimeError("Memory manager not initialized")

    if action == "create":
        memory_manager.create_memory(key, value, namespace)
        return {"status": "created", "key": key}
    elif action == "update":
        memory_manager.update_memory(key, value, namespace)
        return {"status": "updated", "key": key}
    elif action == "delete":
        memory_manager.delete_memory(key, namespace)
        return {"status": "deleted", "key": key}
    else:
        raise ValueError(f"Unknown action: {action}")


def search_memory(
    query: str, namespace: str | None = "storyteller"
) -> list[dict[str, Any]]:
    """Function interface compatible with the old search_memory_tool.invoke() calls."""
    if memory_manager is None:
        raise RuntimeError("Memory manager not initialized")

    return memory_manager.search_memories(query, namespace)
