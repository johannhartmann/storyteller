"""
Context functions for story generation.

This module provides context information from the database to prompts,
ensuring consistency across the story.
"""

from typing import Any

from storyteller_lib.core.logger import get_logger
from storyteller_lib.persistence.database import get_db_manager

logger = get_logger(__name__)


def get_character_context(
    character_id: str, chapter_num: int, scene_num: int
) -> dict[str, Any]:
    """
    Get comprehensive character context for a given scene.

    Args:
        character_id: Character identifier
        chapter_num: Current chapter number
        scene_num: Current scene number

    Returns:
        Dictionary with character's current state, relationships, and history
    """
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        return {}

    try:
        # Get character database ID
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM characters WHERE character_id = ?",
                (character_id,)
            )
            result = cursor.fetchone()
            if not result:
                return {}

            char_db_id = result["id"]

        # Get character's state in previous scene
        context = {
            "identifier": character_id,
            "current_location": None,
            "emotional_state": None,
            "known_facts": [],
            "relationships": {},
            "recent_events": [],
        }

        # Find previous scene
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT s.id, s.scene_number, c.chapter_number
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE (c.chapter_number < ? OR
                    (c.chapter_number = ? AND s.scene_number < ?))
                ORDER BY c.chapter_number DESC, s.scene_number DESC
                LIMIT 5
                """,
                (chapter_num, chapter_num, scene_num),
            )
            recent_scenes = cursor.fetchall()

        # Get state from most recent appearance
        for scene in recent_scenes:
            state = db_manager.get_character_state_at_scene(char_db_id, scene["id"])
            if state:
                context["emotional_state"] = state.get("emotional_state")
                context["current_location"] = state.get("location")
                break

        # Get character knowledge
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT fact, source, chapter, scene
                FROM character_knowledge
                WHERE character_id = ?
                AND (chapter < ? OR (chapter = ? AND scene < ?))
                ORDER BY chapter DESC, scene DESC
                LIMIT 20
                """,
                (char_db_id, chapter_num, chapter_num, scene_num),
            )
            knowledge = cursor.fetchall()
            context["known_facts"] = [
                {
                    "fact": k["fact"],
                    "source": k["source"],
                    "when": f"Ch{k['chapter']}/Sc{k['scene']}",
                }
                for k in knowledge
            ]

        # Get relationships
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT
                    c2.character_id as other_character,
                    cr.relationship_type,
                    cr.description
                FROM character_relationships cr
                JOIN characters c1 ON cr.character1_id = c1.id
                JOIN characters c2 ON cr.character2_id = c2.id
                WHERE (cr.character1_id = ? OR cr.character2_id = ?)
                """,
                (char_db_id, char_db_id),
            )
            relationships = cursor.fetchall()

            for rel in relationships:
                context["relationships"][rel["other_character"]] = {
                    "type": rel["relationship_type"],
                    "description": rel["description"],
                }

        return context

    except Exception as e:
        logger.error(f"Error getting character context: {e}")
        return {}


def get_scene(chapter_num: int, scene_num: int) -> dict[str, Any] | None:
    """
    Get scene content and metadata.

    Args:
        chapter_num: Chapter number
        scene_num: Scene number

    Returns:
        Dictionary with scene content and metadata, or None if not found
    """
    db_manager = get_db_manager()
    if not db_manager:
        return None

    content = db_manager.get_scene_content(chapter_num, scene_num)
    if not content:
        return None

    return {"content": content, "chapter": chapter_num, "scene": scene_num}


def get_recent_scenes(
    chapter_num: int, scene_num: int, limit: int = 3
) -> list[dict[str, Any]]:
    """
    Get recent scenes before the current position.

    Args:
        chapter_num: Current chapter number
        scene_num: Current scene number
        limit: Maximum number of scenes to return

    Returns:
        List of scene dictionaries with content and metadata
    """
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        return []

    try:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT s.content, s.scene_number, c.chapter_number
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE (c.chapter_number < ? OR
                    (c.chapter_number = ? AND s.scene_number < ?))
                ORDER BY c.chapter_number DESC, s.scene_number DESC
                LIMIT ?
                """,
                (chapter_num, chapter_num, scene_num, limit),
            )

            scenes = []
            for row in cursor.fetchall():
                scenes.append(
                    {
                        "content": row["content"],
                        "chapter": row["chapter_number"],
                        "scene": row["scene_number"],
                    }
                )

            return scenes

    except Exception as e:
        logger.error(f"Error getting recent scenes: {e}")
        return []


def get_plot_thread_state(thread_name: str) -> dict[str, Any] | None:
    """
    Get the current state of a plot thread.

    Args:
        thread_name: Name of the plot thread

    Returns:
        Dictionary with thread state or None if not found
    """
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        return None

    try:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM plot_threads
                WHERE name = ?
                """,
                (thread_name,),
            )
            result = cursor.fetchone()

            if result:
                return {
                    "name": result["name"],
                    "description": result["description"],
                    "status": result["status"],
                    "importance": result["importance"],
                    "introduced_chapter": result["introduced_chapter"],
                    "introduced_scene": result["introduced_scene"],
                    "resolved_chapter": result["resolved_chapter"],
                    "resolved_scene": result["resolved_scene"],
                }

            return None

    except Exception as e:
        logger.error(f"Error getting plot thread state: {e}")
        return None


def get_world_elements(category: str | None = None) -> dict[str, Any]:
    """
    Get world elements, optionally filtered by category.

    Args:
        category: Optional category to filter by

    Returns:
        Dictionary of world elements
    """
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        return {}

    try:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()

            if category:
                cursor.execute(
                    """
                    SELECT category, name, description
                    FROM world_elements
                    WHERE category = ?
                    """,
                    (category,),
                )
            else:
                cursor.execute(
                    """
                    SELECT category, name, description
                    FROM world_elements
                    """
                )

            elements = {}
            for row in cursor.fetchall():
                if row["category"] not in elements:
                    elements[row["category"]] = {}
                elements[row["category"]][row["name"]] = row["description"]

            return elements

    except Exception as e:
        logger.error(f"Error getting world elements: {e}")
        return {}


# Backward compatibility - some code might still use get_context_provider()
def get_context_provider():
    """Deprecated - use the direct functions instead."""
    logger.warning("get_context_provider() is deprecated - use direct context functions instead")
    return None