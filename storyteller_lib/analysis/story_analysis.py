"""
Story Analysis Module - Advanced queries and analysis for story dependencies.

This module provides high-level analysis capabilities for understanding story
structure, character arcs, plot development, and identifying dependencies
between story elements.
"""

# Standard library imports
import json
from collections import defaultdict
from typing import Any

from storyteller_lib.core.exceptions import DatabaseError
from storyteller_lib.core.logger import get_logger

# Local imports
from storyteller_lib.database import StoryDatabase, StoryQueries

logger = get_logger(__name__)


class StoryAnalyzer:
    """
    Advanced story analysis and query capabilities.

    This class provides methods for analyzing story structure, tracking
    dependencies, and generating insights about the narrative.
    """

    def __init__(self, db: StoryDatabase):
        """
        Initialize the story analyzer.

        Args:
            db: StoryDatabase instance
        """
        self.db = db
        self.queries = StoryQueries(db)

    def analyze_story_structure(self, story_id: int) -> dict[str, Any]:
        """
        Analyze the overall structure of a story.

        Args:
            story_id: The story ID

        Returns:
            Dictionary containing structural analysis
        """
        try:
            story = self.db.get_story(story_id)

            # Get basic statistics
            with self.db._get_connection() as conn:
                cursor = conn.cursor()

                # Count chapters
                cursor.execute(
                    "SELECT COUNT(*) as count FROM chapters WHERE story_id = ?",
                    (story_id,),
                )
                chapter_count = cursor.fetchone()["count"]

                # Count scenes
                cursor.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM scenes s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE c.story_id = ?
                    """,
                    (story_id,),
                )
                scene_count = cursor.fetchone()["count"]

                # Count characters
                cursor.execute(
                    "SELECT COUNT(*) as count FROM characters WHERE story_id = ?",
                    (story_id,),
                )
                character_count = cursor.fetchone()["count"]

                # Count locations
                cursor.execute(
                    "SELECT COUNT(*) as count FROM locations WHERE story_id = ?",
                    (story_id,),
                )
                location_count = cursor.fetchone()["count"]

                # Count plot threads
                cursor.execute(
                    "SELECT COUNT(*) as count FROM plot_threads WHERE story_id = ?",
                    (story_id,),
                )
                plot_thread_count = cursor.fetchone()["count"]

                # Analyze plot thread resolution
                cursor.execute(
                    """
                    SELECT status, COUNT(*) as count
                    FROM plot_threads
                    WHERE story_id = ?
                    GROUP BY status
                    """,
                    (story_id,),
                )
                plot_status = {row["status"]: row["count"] for row in cursor.fetchall()}

            return {
                "story_info": story,
                "statistics": {
                    "chapters": chapter_count,
                    "scenes": scene_count,
                    "characters": character_count,
                    "locations": location_count,
                    "plot_threads": plot_thread_count,
                    "average_scenes_per_chapter": (
                        scene_count / chapter_count if chapter_count > 0 else 0
                    ),
                },
                "plot_thread_status": plot_status,
                "completeness": {
                    "has_chapters": chapter_count > 0,
                    "has_scenes": scene_count > 0,
                    "has_characters": character_count > 0,
                    "has_world_building": location_count > 0,
                    "has_plot_threads": plot_thread_count > 0,
                    "unresolved_threads": plot_status.get("introduced", 0)
                    + plot_status.get("developed", 0),
                },
            }
        except Exception as e:
            logger.error(f"Failed to analyze story structure: {e}")
            raise DatabaseError(f"Failed to analyze story structure: {e}")

    def analyze_character_arc(self, character_id: int) -> dict[str, Any]:
        """
        Analyze a character's complete arc through the story.

        Args:
            character_id: The character ID

        Returns:
            Dictionary containing character arc analysis
        """
        # Get basic character info
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM characters WHERE id = ?", (character_id,))
            character = dict(cursor.fetchone())

        # Get character journey
        journey = self.queries.get_character_journey(character_id)

        # Analyze emotional arc
        emotional_states = []
        for appearance in journey["appearances"]:
            if appearance["state"].get("emotional_state"):
                emotional_states.append(
                    {
                        "chapter": appearance["chapter"],
                        "scene": appearance["scene"],
                        "state": appearance["state"]["emotional_state"],
                    }
                )

        # Analyze knowledge progression using character_knowledge table
        knowledge_progression = []
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT c.chapter_number, s.scene_number, ck.knowledge_content, ck.knowledge_type
                FROM character_knowledge ck
                JOIN scenes s ON ck.scene_id = s.id
                JOIN chapters c ON s.chapter_id = c.id
                WHERE ck.character_id = ?
                ORDER BY c.chapter_number, s.scene_number
            """,
                (character_id,),
            )

            for row in cursor.fetchall():
                knowledge_progression.append(
                    {
                        "chapter": row["chapter_number"],
                        "scene": row["scene_number"],
                        "knowledge": row["knowledge_content"],
                        "type": row["knowledge_type"],
                    }
                )

        # Get plot thread involvement
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT pt.name, pt.importance, cpt.involvement_role
                FROM character_plot_threads cpt
                JOIN plot_threads pt ON cpt.plot_thread_id = pt.id
                WHERE cpt.character_id = ?
                """,
                (character_id,),
            )
            plot_involvement = [dict(row) for row in cursor.fetchall()]

        # Analyze relationship dynamics
        relationships = self.db.get_character_relationships(character_id)

        return {
            "character": character,
            "arc_summary": {
                "total_appearances": len(journey["appearances"]),
                "first_appearance": (
                    journey["appearances"][0] if journey["appearances"] else None
                ),
                "last_appearance": (
                    journey["appearances"][-1] if journey["appearances"] else None
                ),
                "emotional_journey": emotional_states,
                "knowledge_growth": knowledge_progression,
                "major_changes": journey["state_changes"],
            },
            "plot_involvement": plot_involvement,
            "relationships": {"total": len(relationships), "types": defaultdict(int)},
            "evolution_timeline": journey["evolution"],
        }

    def find_plot_dependencies(self, plot_thread_id: int) -> dict[str, Any]:
        """
        Find all dependencies for a plot thread.

        Args:
                plot_thread_id: The plot thread ID

        Returns:
                Dictionary containing plot dependencies
        """
        dependencies = {
            "characters": [],
            "locations": [],
            "other_threads": [],
            "key_scenes": [],
        }

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Get plot thread info
            cursor.execute("SELECT * FROM plot_threads WHERE id = ?", (plot_thread_id,))
            plot_thread = dict(cursor.fetchone())

            # Find characters involved
            cursor.execute(
                """
                SELECT c.*, cpt.involvement_role
                FROM character_plot_threads cpt
                JOIN characters c ON cpt.character_id = c.id
                WHERE cpt.plot_thread_id = ?
                """,
                (plot_thread_id,),
            )
            dependencies["characters"] = [dict(row) for row in cursor.fetchall()]

            # Find scenes where thread develops
            cursor.execute(
                """
                SELECT s.*, c.chapter_number, ptd.development_type, ptd.description
                FROM plot_thread_developments ptd
                JOIN scenes s ON ptd.scene_id = s.id
                JOIN chapters c ON s.chapter_id = c.id
                WHERE ptd.plot_thread_id = ?
                ORDER BY c.chapter_number, s.scene_number
                """,
                (plot_thread_id,),
            )
            dependencies["key_scenes"] = [dict(row) for row in cursor.fetchall()]

            # Find locations associated with thread scenes
            location_ids = set()
            for scene in dependencies["key_scenes"]:
                cursor.execute(
                    """
                    SELECT DISTINCT l.*
                    FROM scene_entities se
                    JOIN locations l ON se.entity_id = l.id
                    WHERE se.scene_id = ? AND se.entity_type = 'location'
                    """,
                    (scene["id"],),
                )
                for row in cursor.fetchall():
                    location_ids.add(row["id"])
                    dependencies["locations"].append(dict(row))

            # Find related plot threads (threads that share scenes)
            cursor.execute(
                """
                SELECT DISTINCT pt2.*, COUNT(DISTINCT ptd2.scene_id) as shared_scenes
                FROM plot_thread_developments ptd1
                JOIN plot_thread_developments ptd2 ON ptd1.scene_id = ptd2.scene_id
                JOIN plot_threads pt2 ON ptd2.plot_thread_id = pt2.id
                WHERE ptd1.plot_thread_id = ? AND pt2.id != ?
                GROUP BY pt2.id
                """,
                (plot_thread_id, plot_thread_id),
            )
            dependencies["other_threads"] = [dict(row) for row in cursor.fetchall()]

        return {
            "plot_thread": plot_thread,
            "dependencies": dependencies,
            "dependency_summary": {
                "character_count": len(dependencies["characters"]),
                "location_count": len(dependencies["locations"]),
                "scene_count": len(dependencies["key_scenes"]),
                "related_threads": len(dependencies["other_threads"]),
            },
        }

    def analyze_scene_impact(self, scene_id: int) -> dict[str, Any]:
        """
        Analyze the impact of a specific scene on the story.

        Args:
                scene_id: The scene ID

        Returns:
                Dictionary containing scene impact analysis
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Get scene info
            cursor.execute(
                """
                SELECT s.*, c.chapter_number, c.title as chapter_title
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE s.id = ?
                """,
                (scene_id,),
            )
            scene = dict(cursor.fetchone())

            # Get entities in scene
            entities = self.db.get_entities_in_scene(scene_id)

            # Get character state changes
            state_changes = []
            for char in entities["characters"]:
                cursor.execute(
                    """
                    SELECT * FROM character_states
                    WHERE character_id = ? AND scene_id = ?
                    """,
                    (char["id"], scene_id),
                )
                state = cursor.fetchone()
                if state:
                    state_changes.append(
                        {"character": char["name"], "changes": dict(state)}
                    )

            # Get plot developments
            cursor.execute(
                """
                SELECT pt.name, ptd.development_type, ptd.description
                FROM plot_thread_developments ptd
                JOIN plot_threads pt ON ptd.plot_thread_id = pt.id
                WHERE ptd.scene_id = ?
                """,
                (scene_id,),
            )
            plot_developments = [dict(row) for row in cursor.fetchall()]

            # Get entity changes
            cursor.execute(
                """
                SELECT * FROM entity_changes
                WHERE scene_id = ?
                """,
                (scene_id,),
            )
            entity_changes = []
            for row in cursor.fetchall():
                change = dict(row)
                # Deserialize JSON fields
                if change.get("old_value"):
                    try:
                        change["old_value"] = json.loads(change["old_value"])
                    except json.JSONDecodeError:
                        pass
                if change.get("new_value"):
                    try:
                        change["new_value"] = json.loads(change["new_value"])
                    except json.JSONDecodeError:
                        pass
                entity_changes.append(change)

            # Calculate impact score
            impact_score = (
                len(entities["characters"]) * 2  # Characters have high impact
                + len(state_changes) * 3  # State changes are very important
                + len(plot_developments) * 4  # Plot developments are critical
                + len(entity_changes) * 2  # Entity changes are important
            )

        return {
            "scene": scene,
            "entities_involved": entities,
            "character_state_changes": state_changes,
            "plot_developments": plot_developments,
            "entity_changes": entity_changes,
            "impact_metrics": {
                "impact_score": impact_score,
                "character_count": len(entities["characters"]),
                "location_count": len(entities["locations"]),
                "state_change_count": len(state_changes),
                "plot_development_count": len(plot_developments),
                "entity_change_count": len(entity_changes),
            },
        }

    def find_revision_candidates(
        self, story_id: int, change_type: str, entity_type: str, entity_id: int
    ) -> list[dict[str, Any]]:
        """
        Find scenes and chapters that need revision based on an entity change.

        Args:
                story_id: The story ID
            change_type: Type of change (e.g., 'backstory', 'personality', 'name')
            entity_type: Type of entity (e.g., 'character', 'location')
            entity_id: The entity ID

        Returns:
                List of revision candidates with priority scores
        """
        candidates = []

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            if entity_type == "character":
                # Find all scenes where character appears
                cursor.execute(
                    """
                    SELECT s.id, s.content, c.chapter_number, c.id as chapter_id,
                        se.involvement_type
                    FROM scene_entities se
                    JOIN scenes s ON se.scene_id = s.id
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE se.entity_type = 'character' AND se.entity_id = ?
                    ORDER BY c.chapter_number, s.scene_number
                    """,
                    (entity_id,),
                )

                for row in cursor.fetchall():
                    scene = dict(row)

                    # Calculate revision priority
                    priority = 0

                    # Major changes affect all appearances
                    if change_type in ["backstory", "personality", "name"]:
                        priority = 10

                    # Present scenes have higher priority
                    if scene["involvement_type"] == "present":
                        priority += 5

                    # Check for specific mentions in content
                    if change_type == "name":
                        # Get character name
                        cursor.execute(
                            "SELECT name FROM characters WHERE id = ?", (entity_id,)
                        )
                        char_name = cursor.fetchone()["name"]
                        if char_name in scene["content"]:
                            priority += 3

                    candidates.append(
                        {
                            "scene_id": scene["id"],
                            "chapter_id": scene["chapter_id"],
                            "chapter_number": scene["chapter_number"],
                            "involvement": scene["involvement_type"],
                            "priority": priority,
                            "reason": f"{change_type} change affects this scene",
                        }
                    )

            elif entity_type == "location":
                # Similar logic for locations
                cursor.execute(
                    """
                    SELECT s.id, s.content, c.chapter_number, c.id as chapter_id,
                        se.involvement_type
                    FROM scene_entities se
                    JOIN scenes s ON se.scene_id = s.id
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE se.entity_type = 'location' AND se.entity_id = ?
                    ORDER BY c.chapter_number, s.scene_number
                    """,
                    (entity_id,),
                )

                for row in cursor.fetchall():
                    scene = dict(row)
                    priority = 5 if scene["involvement_type"] == "present" else 2

                    candidates.append(
                        {
                            "scene_id": scene["id"],
                            "chapter_id": scene["chapter_id"],
                            "chapter_number": scene["chapter_number"],
                            "involvement": scene["involvement_type"],
                            "priority": priority,
                            "reason": f"Location {change_type} change affects this scene",
                        }
                    )

        # Sort by priority (highest first) and chapter number
        candidates.sort(key=lambda x: (-x["priority"], x["chapter_number"]))

        return candidates

    def generate_dependency_graph(self, story_id: int) -> dict[str, Any]:
        """
        Generate a complete dependency graph for the story.

        Args:
                story_id: The story ID

        Returns:
                Dictionary representing the dependency graph
        """
        graph = {
            "nodes": {
                "characters": [],
                "locations": [],
                "plot_threads": [],
                "chapters": [],
                "scenes": [],
            },
            "edges": {
                "character_relationships": [],
                "character_locations": [],
                "character_plot_threads": [],
                "scene_entities": [],
                "plot_developments": [],
                "entity_changes": [],
            },
        }

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Get all characters
            cursor.execute(
                "SELECT id, identifier, name FROM characters WHERE story_id = ?",
                (story_id,),
            )
            graph["nodes"]["characters"] = [dict(row) for row in cursor.fetchall()]

            # Get all locations
            cursor.execute(
                "SELECT id, identifier, name FROM locations WHERE story_id = ?",
                (story_id,),
            )
            graph["nodes"]["locations"] = [dict(row) for row in cursor.fetchall()]

            # Get all plot threads
            cursor.execute(
                "SELECT id, name, importance, status FROM plot_threads WHERE story_id = ?",
                (story_id,),
            )
            graph["nodes"]["plot_threads"] = [dict(row) for row in cursor.fetchall()]

            # Get all chapters
            cursor.execute(
                "SELECT id, chapter_number, title FROM chapters WHERE story_id = ?",
                (story_id,),
            )
            graph["nodes"]["chapters"] = [dict(row) for row in cursor.fetchall()]

            # Get all scenes
            cursor.execute(
                """
                SELECT s.id, s.scene_number, c.chapter_number
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE c.story_id = ?
                """,
                (story_id,),
            )
            graph["nodes"]["scenes"] = [dict(row) for row in cursor.fetchall()]

            # Get character relationships
            cursor.execute(
                """
                SELECT character1_id, character2_id, relationship_type
                FROM character_relationships
                WHERE story_id = ?
                """,
                (story_id,),
            )
            graph["edges"]["character_relationships"] = [
                {
                    "source": row["character1_id"],
                    "target": row["character2_id"],
                    "type": row["relationship_type"],
                }
                for row in cursor.fetchall()
            ]

            # Get character-location associations
            cursor.execute(
                """
                SELECT cl.character_id, cl.location_id, cl.association_type
                FROM character_locations cl
                JOIN characters c ON cl.character_id = c.id
                WHERE c.story_id = ?
                """,
                (story_id,),
            )
            graph["edges"]["character_locations"] = [
                {
                    "character": row["character_id"],
                    "location": row["location_id"],
                    "type": row["association_type"],
                }
                for row in cursor.fetchall()
            ]

            # Get character-plot thread associations
            cursor.execute(
                """
                SELECT cpt.character_id, cpt.plot_thread_id, cpt.involvement_role
                FROM character_plot_threads cpt
                JOIN characters c ON cpt.character_id = c.id
                WHERE c.story_id = ?
                """,
                (story_id,),
            )
            graph["edges"]["character_plot_threads"] = [
                {
                    "character": row["character_id"],
                    "plot_thread": row["plot_thread_id"],
                    "role": row["involvement_role"],
                }
                for row in cursor.fetchall()
            ]

        return graph

    def get_story_timeline(self, story_id: int) -> list[dict[str, Any]]:
        """
        Get a timeline of all major events in the story.

        Args:
                story_id: The story ID

        Returns:
                List of timeline events ordered chronologically
        """
        timeline = []

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Get all plot developments
            cursor.execute(
                """
                SELECT pt.name as thread_name, ptd.development_type,
                        ptd.description, s.scene_number, c.chapter_number
                FROM plot_thread_developments ptd
                JOIN plot_threads pt ON ptd.plot_thread_id = pt.id
                JOIN scenes s ON ptd.scene_id = s.id
                JOIN chapters c ON s.chapter_id = c.id
                WHERE pt.story_id = ?
                ORDER BY c.chapter_number, s.scene_number
                """,
                (story_id,),
            )

            for row in cursor.fetchall():
                timeline.append(
                    {
                        "type": "plot_development",
                        "chapter": row["chapter_number"],
                        "scene": row["scene_number"],
                        "thread": row["thread_name"],
                        "development": row["development_type"],
                        "description": row["description"],
                    }
                )

            # Get major character state changes
            cursor.execute(
                """
                SELECT c.name as character_name, cs.evolution_notes,
                        s.scene_number, ch.chapter_number
                FROM character_states cs
                JOIN characters c ON cs.character_id = c.id
                JOIN scenes s ON cs.scene_id = s.id
                JOIN chapters ch ON s.chapter_id = ch.id
                WHERE c.story_id = ? AND cs.evolution_notes IS NOT NULL
                ORDER BY ch.chapter_number, s.scene_number
                """,
                (story_id,),
            )

            for row in cursor.fetchall():
                timeline.append(
                    {
                        "type": "character_evolution",
                        "chapter": row["chapter_number"],
                        "scene": row["scene_number"],
                        "character": row["character_name"],
                        "description": row["evolution_notes"],
                    }
                )

            # Get entity changes
            cursor.execute(
                """
                SELECT ec.*, s.scene_number, c.chapter_number
                FROM entity_changes ec
                JOIN scenes s ON ec.scene_id = s.id
                JOIN chapters c ON s.chapter_id = c.id
                JOIN stories st ON c.story_id = st.id
                WHERE st.id = ?
                ORDER BY c.chapter_number, s.scene_number
                """,
                (story_id,),
            )

            for row in cursor.fetchall():
                timeline.append(
                    {
                        "type": "entity_change",
                        "chapter": row["chapter_number"],
                        "scene": row["scene_number"],
                        "entity_type": row["entity_type"],
                        "change_type": row["change_type"],
                        "description": row["change_description"],
                    }
                )

        # Sort timeline by chapter and scene
        timeline.sort(key=lambda x: (x["chapter"], x["scene"]))

        return timeline
