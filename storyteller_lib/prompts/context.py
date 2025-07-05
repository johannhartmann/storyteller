"""
Context provider for story generation.

This module provides context information from the database to prompts,
ensuring consistency across the story.
"""

from typing import Any

from storyteller_lib.core.logger import get_logger
from storyteller_lib.persistence.database import StoryDatabaseManager

logger = get_logger(__name__)

# Global context provider instance
_context_provider = None


class StoryContextProvider:
    """Provides context information from the database for prompts."""

    def __init__(self, db_manager: StoryDatabaseManager | None = None):
        """Initialize with database manager."""
        self.db = db_manager
        self.story_id = None

        if self.db and hasattr(self.db, "story_id"):
            self.story_id = self.db.story_id
            logger.info(
                f"StoryContextProvider initialized with story_id: {self.story_id}"
            )
        else:
            logger.warning("StoryContextProvider initialized without story_id")

    def get_character_context(
        self, character_id: str, chapter_num: int, scene_num: int
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
        if not self.db or not self.story_id:
            return {}

        try:
            # Get character database ID
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM characters WHERE story_id = ? AND identifier = ?",
                    (self.story_id, character_id),
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
                "known_facts": [],  # Character knowledge from database
                "relationships": {},
                "recent_events": [],
            }

            # Find previous scene
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT s.id, s.scene_number, c.chapter_number
                    FROM scenes s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE c.story_id = ?
                    AND (c.chapter_number < ? OR
                        (c.chapter_number = ? AND s.scene_number < ?))
                    ORDER BY c.chapter_number DESC, s.scene_number DESC
                    LIMIT 5
                    """,
                    (self.story_id, chapter_num, chapter_num, scene_num),
                )
                recent_scenes = cursor.fetchall()

            # Get state from most recent appearance
            for scene in recent_scenes:
                state = self.db.get_character_state_at_scene(char_db_id, scene["id"])
                if state:
                    context["emotional_state"] = state.get("emotional_state")
                    context["current_location"] = state.get("location")
                    break

            # Get character knowledge
            with self.db._get_connection() as conn:
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
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT DISTINCT
                        c2.identifier as other_character,
                        cr.relationship_type,
                        cr.description
                    FROM character_relationships cr
                    JOIN characters c1 ON cr.character1_id = c1.id
                    JOIN characters c2 ON cr.character2_id = c2.id
                    WHERE (cr.character1_id = ? OR cr.character2_id = ?)
                    AND c1.story_id = ? AND c2.story_id = ?
                    """,
                    (char_db_id, char_db_id, self.story_id, self.story_id),
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

    def get_scene(self, chapter_num: int, scene_num: int) -> dict[str, Any] | None:
        """
        Get scene content and metadata.

        Args:
            chapter_num: Chapter number
            scene_num: Scene number

        Returns:
            Dictionary with scene content and metadata, or None if not found
        """
        if not self.db:
            return None

        content = self.db.get_scene_content(chapter_num, scene_num)
        if not content:
            return None

        return {"content": content, "chapter": chapter_num, "scene": scene_num}

    def get_recent_scenes(
        self, chapter_num: int, scene_num: int, limit: int = 3
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
        if not self.db or not self.story_id:
            return []

        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT s.content, s.scene_number, c.chapter_number
                    FROM scenes s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE c.story_id = ?
                    AND (c.chapter_number < ? OR
                        (c.chapter_number = ? AND s.scene_number < ?))
                    ORDER BY c.chapter_number DESC, s.scene_number DESC
                    LIMIT ?
                    """,
                    (self.story_id, chapter_num, chapter_num, scene_num, limit),
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

    def get_plot_thread_state(self, thread_name: str) -> dict[str, Any] | None:
        """
        Get the current state of a plot thread.

        Args:
            thread_name: Name of the plot thread

        Returns:
            Dictionary with thread state or None if not found
        """
        if not self.db or not self.story_id:
            return None

        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM plot_threads
                    WHERE story_id = ? AND name = ?
                    """,
                    (self.story_id, thread_name),
                )
                result = cursor.fetchone()

                if result:
                    return {
                        "name": result["name"],
                        "description": result["description"],
                        "status": result["status"],
                        "importance": result["importance"],
                        "first_chapter": result["first_chapter"],
                        "first_scene": result["first_scene"],
                        "last_chapter": result["last_chapter"],
                        "last_scene": result["last_scene"],
                    }

                return None

        except Exception as e:
            logger.error(f"Error getting plot thread state: {e}")
            return None

    def get_world_elements(self, category: str | None = None) -> dict[str, Any]:
        """
        Get world elements, optionally filtered by category.

        Args:
            category: Optional category to filter by

        Returns:
            Dictionary of world elements
        """
        if not self.db or not self.story_id:
            return {}

        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()

                if category:
                    cursor.execute(
                        """
                        SELECT category, name, description
                        FROM world_elements
                        WHERE story_id = ? AND category = ?
                        """,
                        (self.story_id, category),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT category, name, description
                        FROM world_elements
                        WHERE story_id = ?
                        """,
                        (self.story_id,),
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


def initialize_context_provider(
    db_manager: StoryDatabaseManager,
) -> StoryContextProvider:
    """Initialize the global context provider."""
    global _context_provider
    _context_provider = StoryContextProvider(db_manager)
    logger.info("Global context provider initialized")
    return _context_provider


def get_context_provider() -> StoryContextProvider | None:
    """Get the global context provider instance."""
    return _context_provider
