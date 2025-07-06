"""
Database integration module for StoryCraft Agent.

This module provides the integration layer between the workflow
and the database persistence layer, enabling automatic state saving during
story generation.
"""

# Standard library imports
import json
import os
from typing import Any

# Local imports
from storyteller_lib.core.constants import NodeNames
from storyteller_lib.core.logger import get_logger
# StoryState no longer used - working directly with database
from storyteller_lib.persistence.models import StoryDatabase

logger = get_logger(__name__)


class StoryDatabaseManager:
    """
    Manages database operations during story generation.

    This class handles automatic state persistence, providing methods to save
    state after each node execution and track changes incrementally.
    """

    def __init__(self, db_path: str | None = None, enabled: bool = True):
        """
        Initialize the database manager.

        Args:
            db_path: Path to the database file (defaults to story_database.db)
            enabled: Whether database operations are enabled
        """
        self.enabled = enabled
        self._db: StoryDatabase | None = None
        self._db_path = db_path or os.environ.get(
            "STORY_DATABASE_PATH", "story_database.db"
        )
        self._modified_entities: set[str] = set()
        self._current_chapter_id: int | None = None
        self._current_scene_id: int | None = None
        self._character_id_map: dict[str, int] = {}
        self._chapter_id_map: dict[str, int] = {}
        if self.enabled:
            self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize database connection."""
        self._db = StoryDatabase(self._db_path)
        logger.info(f"Database initialized at {self._db_path}")

    def save_node_state(self, node_name: str, state: dict) -> None:
        """
        Save state after a node execution.

        This method performs incremental updates based on the node type,
        only saving what has changed to avoid full state syncs.

        Args:
            node_name: Name of the node that just executed
            state: Current story state
        """
        logger.info(f"save_node_state called for node: {node_name}")
        logger.debug(
            f"Database enabled: {self.enabled}, DB exists: {self._db is not None}"
        )

        if not self.enabled or not self._db:
            logger.warning(
                f"Skipping save for {node_name}: enabled={self.enabled}, db={self._db is not None}"
            )
            return

        try:
            # Map node names to save operations - handle both constants and actual node names
            if node_name in [NodeNames.INITIALIZE, "initialize_state"]:
                self._save_initial_state(state)
            elif node_name in [NodeNames.WORLDBUILDING, "generate_worldbuilding"]:
                self._save_world_elements(state)
            elif node_name in [NodeNames.CREATE_CHARACTERS, "generate_characters"]:
                self._save_characters(state)
            # Plot threads are saved after outline generation and scene reflection
            elif node_name in ["generate_story_outline"]:
                self._save_plot_threads(state)
            elif node_name in [
                NodeNames.SCENE_REFLECTION,
                "reflect_on_scene",
                "check_plot_threads",
            ]:
                self._save_plot_threads(state)
            elif node_name == NodeNames.PLAN_CHAPTER:
                self._save_chapter(state)
            elif node_name == "plan_chapters":  # Handle the actual node name from graph
                logger.info(
                    "Processing plan_chapters node, calling _save_all_chapters"
                )
                self._save_all_chapters(state)
            elif node_name in [
                NodeNames.SCENE_WRITING,
                NodeNames.SCENE_REVISION,
                "write_scene",
                "revise_scene_if_needed",
            ]:
                self._save_scene(state)
            elif node_name in [
                NodeNames.CHARACTER_EVOLUTION,
                "update_character_knowledge",
            ]:
                self._update_character_states(state)
            # Story outline is saved by the generate_story_outline node itself

            logger.debug(f"Saved state after {node_name}")
        except Exception as e:
            logger.error(f"Failed to save state after {node_name}: {e}")

    def _save_initial_state(self, state: dict) -> None:
        """Initialize context provider for story generation."""
        # Story configuration is already saved by storyteller.py
        # Just ensure context provider is initialized
        from storyteller_lib.prompts.context import (
            get_context_provider,
            initialize_context_provider,
        )

        if not get_context_provider():
            initialize_context_provider(self)

    def _save_world_elements(self, state: dict) -> None:
        """Save world building elements."""
        world_elements = state.get("world_elements", {})

        # Check if world_elements is just a marker (stored_in_db: True)
        if isinstance(world_elements, dict) and world_elements.get("stored_in_db"):
            # Already saved directly by worldbuilding.py
            logger.debug("World elements already saved to database")
            return

        # Otherwise save them if they exist
        if isinstance(world_elements, dict):
            for category, elements in world_elements.items():
                if isinstance(elements, dict):
                    for key, value in elements.items():
                        self._db.create_world_element(
                            category=category, element_key=key, element_value=value
                        )

            # Also save locations if they exist in world elements
            if "locations" in world_elements and isinstance(
                world_elements["locations"], dict
            ):
                for loc_id, loc_data in world_elements["locations"].items():
                    if isinstance(loc_data, dict):
                        self._db.create_location(
                            identifier=loc_id,
                            name=loc_data.get("name", loc_id),
                            description=loc_data.get("description", ""),
                            location_type=loc_data.get("type", "unknown"),
                            properties=loc_data.get("properties", {}),
                        )

    def _save_characters(self, state: dict) -> None:
        """Save character profiles and relationships."""
        characters = state.get("characters", {})

        # First pass: Create all characters
        char_id_map = {}
        for char_id, char_data in characters.items():
            try:
                # Serialize any dict fields to JSON strings, ensure all are strings
                personality = char_data.get("personality", "")
                if isinstance(personality, dict):
                    personality = json.dumps(personality)
                elif personality is None:
                    personality = ""
                else:
                    personality = str(personality)

                backstory = char_data.get("backstory", "")
                if isinstance(backstory, dict):
                    backstory = json.dumps(backstory)
                elif backstory is None:
                    backstory = ""
                else:
                    backstory = str(backstory)

                role = char_data.get("role", "")
                if isinstance(role, dict):
                    role = json.dumps(role)
                elif role is None:
                    role = ""
                else:
                    role = str(role)

                # Debug logging
                logger.debug(f"Creating character {char_id} with:")
                logger.debug(
                    f"  name: {char_data.get('name', char_id)} (type: {type(char_data.get('name', char_id))})"
                )
                logger.debug(f"  role: {role} (type: {type(role)})")
                logger.debug(
                    f"  backstory: {backstory[:100] if backstory else 'None'}... (type: {type(backstory)})"
                )
                logger.debug(
                    f"  personality: {personality[:100] if personality else 'None'}... (type: {type(personality)})"
                )

                db_char_id = self._db.create_character(
                    identifier=char_id,
                    name=char_data.get("name", char_id),
                    role=role,
                    backstory=backstory,
                    personality=personality,
                )
                char_id_map[char_id] = db_char_id
            except Exception as e:
                # Character might already exist
                logger.debug(f"Character {char_id} may already exist: {e}")
                # Try to get existing character ID
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM characters WHERE identifier = ?", (char_id,)
                    )
                    result = cursor.fetchone()
                    if result:
                        char_id_map[char_id] = result["id"]

        # Second pass: Create relationships
        for char_id, char_data in characters.items():
            if char_id in char_id_map and "relationships" in char_data:
                for other_char, rel_type in char_data["relationships"].items():
                    if other_char in char_id_map:
                        self._db.create_relationship(
                            char1_id=char_id_map[char_id],
                            char2_id=char_id_map[other_char],
                            rel_type=rel_type,
                        )

    def _save_plot_threads(self, state: dict) -> None:
        """Save plot threads."""
        plot_threads = state.get("plot_threads", {})

        for thread_name, thread_data in plot_threads.items():
            # Skip if it's just a marker
            if isinstance(thread_data, dict) and thread_data.get("stored_in_db"):
                continue

            # Handle the PlotThread data structure
            if isinstance(thread_data, dict):
                try:
                    # First check if thread already exists
                    with self._db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM plot_threads WHERE name = ?", (thread_name,)
                        )
                        result = cursor.fetchone()

                        if result:
                            # Update existing thread
                            self._db.update_plot_thread_status(
                                result["id"], thread_data.get("status", "introduced")
                            )
                        else:
                            # Create new thread
                            self._db.create_plot_thread(
                                name=thread_name,
                                description=thread_data.get("description", ""),
                                thread_type=thread_data.get(
                                    "importance", "minor"
                                ),  # PlotThread uses 'importance' not 'thread_type'
                                importance=thread_data.get("importance", "minor"),
                                status=thread_data.get("status", "introduced"),
                            )
                except Exception as e:
                    logger.error(f"Failed to save plot thread {thread_name}: {e}")

    def _save_all_chapters(self, state: dict) -> None:
        """Save all chapters after planning."""
        chapters = state.get("chapters", {})
        if not chapters:
            logger.warning("No chapters found in state after plan_chapters")
            logger.warning(f"State keys available: {list(state.keys())}")
            return

        logger.info(f"Saving {len(chapters)} chapters to database")
        logger.debug(f"Chapter keys: {list(chapters.keys())}")

        for chapter_key, chapter_data in chapters.items():
            # Extract chapter number
            try:
                # Handle both "1" and "Chapter 1" formats
                if chapter_key.isdigit():
                    chapter_num = int(chapter_key)
                else:
                    chapter_num = int(chapter_key.split()[-1])
            except (ValueError, IndexError):
                logger.error(f"Could not extract chapter number from: {chapter_key}")
                continue

            # Check if chapter already exists
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM chapters WHERE chapter_number = ?", (chapter_num,)
                )
                result = cursor.fetchone()

                if not result:
                    # Create new chapter
                    try:
                        chapter_id = self._db.create_chapter(
                            chapter_num=chapter_num,
                            title=chapter_data.get("title", ""),
                            outline=chapter_data.get("outline", ""),
                        )
                        self._chapter_id_map[chapter_key] = chapter_id
                        logger.info(
                            f"Created chapter {chapter_num}: {chapter_data.get('title', '')}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to create chapter {chapter_key}: {e}")
                else:
                    # Store existing chapter ID
                    self._chapter_id_map[chapter_key] = result["id"]
                    logger.debug(
                        f"Chapter {chapter_num} already exists with ID {result['id']}"
                    )

    def _save_chapter(self, state: dict) -> None:
        """Save current chapter."""
        current_chapter = state.get("current_chapter", "")
        if not current_chapter:
            return

        chapters = state.get("chapters", {})
        if current_chapter in chapters:
            chapter_data = chapters[current_chapter]

            # Extract chapter number
            try:
                chapter_num = int(current_chapter.split()[-1])
            except (ValueError, IndexError):
                chapter_num = len(chapters)

            # First check if chapter exists
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM chapters WHERE chapter_number = ?", (chapter_num,)
                )
                result = cursor.fetchone()

                if result:
                    # Chapter already exists, just update the ID
                    self._current_chapter_id = result["id"]
                else:
                    # Create new chapter
                    try:
                        self._current_chapter_id = self._db.create_chapter(
                            chapter_num=chapter_num,
                            title=chapter_data.get("title", ""),
                            outline=chapter_data.get("outline", ""),
                        )
                    except Exception as e:
                        logger.error(f"Failed to create chapter {current_chapter}: {e}")

    def _save_scene(self, state: dict) -> None:
        """Save current scene and its entities."""
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")

        if not current_chapter or not current_scene or not self._current_chapter_id:
            return

        chapters = state.get("chapters", {})
        if current_chapter in chapters and "scenes" in chapters[current_chapter]:
            scenes = chapters[current_chapter]["scenes"]
            if current_scene in scenes:
                scene_data = scenes[current_scene]

                # Extract scene number
                try:
                    scene_num = int(current_scene.split()[-1])
                except (ValueError, IndexError):
                    scene_num = len(scenes)

                try:
                    self._current_scene_id = self._db.create_scene(
                        chapter_id=self._current_chapter_id,
                        scene_num=scene_num,
                        outline=scene_data.get(
                            "description", ""
                        ),  # Use 'description' from chapter planning
                        content=scene_data.get("content", ""),
                    )

                    # Save scene entities
                    self._save_scene_entities(state, scene_data)

                except Exception as e:
                    # Scene might already exist
                    logger.debug(f"Scene {current_scene} may already exist: {e}")
                    with self._db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM scenes WHERE chapter_id = ? AND scene_number = ?",
                            (self._current_chapter_id, scene_num),
                        )
                        result = cursor.fetchone()
                        if result:
                            self._current_scene_id = result["id"]

    def _save_scene_entities(
        self, state: dict, scene_data: dict[str, Any]
    ) -> None:
        """Save entities involved in the current scene."""
        if not self._current_scene_id:
            return

        # Get scene content for entity detection
        content = scene_data.get("content", "")

        # Detect and save character involvement
        characters = state.get("characters", {})
        for char_id, char_data in characters.items():
            char_name = char_data.get("name", "")
            if char_name and char_name in content:
                # Get character database ID
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM characters WHERE identifier = ?", (char_id,)
                    )
                    result = cursor.fetchone()
                    if result:
                        self._db.add_entity_to_scene(
                            self._current_scene_id, "character", result["id"], "present"
                        )

        # Save location involvement if mentioned
        world_elements = state.get("world_elements", {})
        if "locations" in world_elements:
            for loc_id, loc_data in world_elements["locations"].items():
                if isinstance(loc_data, dict):
                    loc_name = loc_data.get("name", "")
                if loc_name and loc_name in content:
                    # Get location database ID
                    with self._db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM locations WHERE identifier = ?", (loc_id,)
                        )
                        result = cursor.fetchone()
                        if result:
                            self._db.add_entity_to_scene(
                                self._current_scene_id,
                                "location",
                                result["id"],
                                "present",
                            )

    def _update_character_states(self, state: dict) -> None:
        """Update character states for the current scene."""
        if not self._current_scene_id:
            return

        characters = state.get("characters", {})
        for char_id, char_data in characters.items():
            # Get character database ID
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM characters WHERE identifier = ?", (char_id,)
                )
                result = cursor.fetchone()
                if result:
                    char_db_id = result["id"]

                    # Build state update
                    state_update = {}

                    # Check for evolution in current scene
                    evolution = char_data.get("evolution", [])
                    if evolution:
                        # Get the latest evolution entry
                        latest_evolution = evolution[-1]
                        state_update["evolution_notes"] = latest_evolution

                    # Note: Character knowledge is now tracked via character_knowledge table
                    # The old fact fields have been removed from CharacterProfile

                    if state_update:
                        self._db.update_character_state(
                            character_id=char_db_id,
                            scene_id=self._current_scene_id,
                            state=state_update,
                        )

    def get_context_for_chapter(self, chapter_num: int) -> dict[str, Any]:
        """
        Get database context for a chapter.

        Args:
            chapter_num: Chapter number

        Returns:
            Context dictionary with relevant information
        """
        if not self._db:
            return {}

        try:
            # Get chapter ID
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM chapters WHERE chapter_number = ?", (chapter_num,)
                )
                result = cursor.fetchone()
                if result:
                    return self._db.get_chapter_start_context(result["id"])
        except Exception as e:
            logger.error(f"Failed to get chapter context: {e}")

        return {}

    def get_context_for_scene(self, chapter_num: int, scene_num: int) -> dict[str, Any]:
        """
        Get database context for a scene.

        Args:
            chapter_num: Chapter number
            scene_num: Scene number

        Returns:
            Context dictionary with relevant information
        """
        if not self._db:
            return {}

        try:
            # Get scene ID
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT s.id
                    FROM scenes s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE c.chapter_number = ? AND s.scene_number = ?
                    """,
                    (chapter_num, scene_num),
                )
                result = cursor.fetchone()
                if result:
                    return self._db.get_scene_context(result["id"])
        except Exception as e:
            logger.error(f"Failed to get scene context: {e}")

        return {}

    def update_character(
        self, character_id: str, changes: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Update character properties and find affected scenes.

        Args:
            character_id: Character identifier (e.g., 'hero', 'mentor')
            changes: Dictionary of changes to apply

        Returns:
            List of affected scenes that may need revision
        """
        if not self.enabled or not self._db:
            return []

        try:
            # Get character database ID
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM characters WHERE identifier = ?", (character_id,)
                )
                result = cursor.fetchone()
                if not result:
                    logger.error(f"Character {character_id} not found")
                    return []

                char_db_id = result["id"]

            # Update character in database
            update_fields = []
            update_values = []

            for field in ["name", "role", "backstory", "personality"]:
                if field in changes:
                    update_fields.append(f"{field} = ?")
                    update_values.append(changes[field])

            if update_fields:
                update_values.append(char_db_id)
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    query = f"""
                        UPDATE characters
                        SET {', '.join(update_fields)}
                        WHERE id = ?
                    """
                    cursor.execute(query, update_values)
                    conn.commit()

                logger.info(f"Updated character {character_id} in database")

            # Find affected scenes using analyzer
            from storyteller_lib.analysis.story_analysis import StoryAnalyzer

            analyzer = StoryAnalyzer(self._db)

            # Determine change type
            change_type = (
                "name"
                if "name" in changes
                else "backstory"
                if "backstory" in changes
                else "minor"
            )

            return analyzer.find_revision_candidates(
                change_type, "character", char_db_id
            )

        except Exception as e:
            logger.error(f"Failed to update character: {e}")
            return []

    def update_plot_thread(
        self, thread_name: str, changes: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Update plot thread and find affected scenes.

        Args:
            thread_name: Plot thread name
            changes: Dictionary of changes to apply

        Returns:
            List of affected scenes that may need revision
        """
        if not self.enabled or not self._db:
            return []

        try:
            # Get plot thread ID
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM plot_threads WHERE name = ?", (thread_name,)
                )
                result = cursor.fetchone()
                if not result:
                    logger.error(f"Plot thread {thread_name} not found")
                    return []

                thread_id = result["id"]

            # Update plot thread
            update_fields = []
            update_values = []

            for field in ["description", "thread_type", "importance", "status"]:
                if field in changes:
                    update_fields.append(f"{field} = ?")
                    update_values.append(changes[field])

            if update_fields:
                update_values.append(thread_id)
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    query = f"""
                        UPDATE plot_threads
                        SET {', '.join(update_fields)}
                        WHERE id = ?
                    """
                    cursor.execute(query, update_values)
                    conn.commit()

                logger.info(f"Updated plot thread {thread_name} in database")

            # Find affected scenes
            from storyteller_lib.analysis.story_analysis import StoryAnalyzer

            analyzer = StoryAnalyzer(self._db)
            dependencies = analyzer.find_plot_dependencies(thread_id)

            affected_scenes = []
            for scene in dependencies["dependencies"]["key_scenes"]:
                affected_scenes.append(
                    {
                        "scene_id": scene["id"],
                        "chapter_id": scene.get("chapter_id"),
                        "chapter_number": scene["chapter_number"],
                        "scene_number": scene["scene_number"],
                        "involvement": "plot_development",
                        "priority": 10 if changes.get("status") == "resolved" else 5,
                        "reason": f"Plot thread '{thread_name}' was modified",
                    }
                )

            return affected_scenes

        except Exception as e:
            logger.error(f"Failed to update plot thread: {e}")
            return []

    def update_world_element(
        self, category: str, element_key: str, element_value: Any
    ) -> list[dict[str, Any]]:
        """
        Update world element and find affected scenes.

        Args:
            category: Element category (e.g., 'geography', 'magic')
            element_key: Specific element key
            element_value: New value for the element

        Returns:
            List of affected scenes that may need revision
        """
        if not self.enabled or not self._db:
            return []

        try:
            # Update world element
            self._db.create_world_element(category, element_key, element_value)
            logger.info(f"Updated world element {category}.{element_key}")

            # For major world elements, all scenes might be affected
            # For minor ones, we'd need more sophisticated detection
            major_categories = ["magic", "technology", "politics", "geography"]

            if category not in major_categories:
                return []

            # Get a sample of scenes that might need review
            affected_scenes = []
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT s.id, s.scene_number, c.chapter_number, c.id as chapter_id
                    FROM scenes s
                    JOIN chapters c ON s.chapter_id = c.id
                    ORDER BY c.chapter_number, s.scene_number
                    LIMIT 10
                    """
                )

                for row in cursor.fetchall():
                    affected_scenes.append(
                        {
                            "scene_id": row["id"],
                            "chapter_id": row["chapter_id"],
                            "chapter_number": row["chapter_number"],
                            "scene_number": row["scene_number"],
                            "involvement": "world_element",
                            "priority": 3,
                            "reason": f"World element '{category}.{element_key}' was modified",
                        }
                    )

            return affected_scenes

        except Exception as e:
            logger.error(f"Failed to update world element: {e}")
            return []

    def get_revision_candidates(
        self, change_type: str, entity_type: str, entity_id: str
    ) -> list[dict[str, Any]]:
        """
        Get revision candidates for a specific change.

        Args:
            change_type: Type of change (e.g., 'backstory', 'name')
            entity_type: Type of entity (e.g., 'character', 'location')
            entity_id: Entity identifier

        Returns:
            List of scenes that may need revision
        """
        if not self.enabled or not self._db:
            return []

        try:
            # Convert string ID to database ID if needed
            db_entity_id = None
            if entity_type == "character":
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM characters WHERE identifier = ?", (entity_id,)
                    )
                    result = cursor.fetchone()
                    if result:
                        db_entity_id = result["id"]
            else:
                # For other entity types, assume numeric ID
                try:
                    db_entity_id = int(entity_id)
                except ValueError:
                    logger.error(f"Invalid entity ID: {entity_id}")
                    return []

            if not db_entity_id:
                return []

            # Use analyzer to find candidates
            from storyteller_lib.analysis.story_analysis import StoryAnalyzer

            analyzer = StoryAnalyzer(self._db)
            return analyzer.find_revision_candidates(
                change_type, entity_type, db_entity_id
            )

        except Exception as e:
            logger.error(f"Failed to get revision candidates: {e}")
            return []

    def update_global_story(self, global_story: str) -> None:
        """Update the global story outline in the database."""
        if not self.enabled or not self._db:
            logger.warning("Database manager is disabled or not initialized")
            return

        try:
            # Extract title from the global story
            logger.info(
                f"update_global_story called with outline of length {len(global_story)}"
            )
            story_title = self._extract_title_from_outline(global_story)
            logger.info(f"Extracted title from outline: '{story_title}'")

            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                # First check if the row exists
                cursor.execute("SELECT COUNT(*) FROM story_config WHERE id = 1")
                exists = cursor.fetchone()[0] > 0

                if exists:
                    cursor.execute(
                        "UPDATE story_config SET global_story = ?, title = ? WHERE id = 1",
                        (global_story, story_title),
                    )
                    conn.commit()
                    logger.info(
                        f"Updated existing story_config with title: '{story_title}'"
                    )
                else:
                    # Create the row with minimal data
                    cursor.execute(
                        """INSERT INTO story_config (id, title, genre, tone, global_story)
                        VALUES (1, ?, 'unknown', 'unknown', ?)""",
                        (story_title, global_story),
                    )
                    logger.info(f"Created new story_config with title: '{story_title}'")
                conn.commit()

            # Verify the update was successful
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT title FROM story_config WHERE id = 1")
                result = cursor.fetchone()
                if result:
                    logger.info(f"Verified title in database: '{result['title']}'")
                else:
                    logger.error("Could not verify title update in database")

            logger.info(
                f"Updated global story (length: {len(global_story)} chars) with title: {story_title}"
            )
        except Exception as e:
            logger.error(f"Failed to update global story: {e}")
            raise

    def update_book_level_instructions(self, instructions: str) -> None:
        """Update the book-level writing instructions in the database."""
        if not self.enabled or not self._db:
            logger.warning("Database manager is disabled or not initialized")
            return

        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                # First check if the row exists
                cursor.execute("SELECT COUNT(*) FROM story_config WHERE id = 1")
                exists = cursor.fetchone()[0] > 0

                if exists:
                    cursor.execute(
                        "UPDATE story_config SET book_level_instructions = ? WHERE id = 1",
                        (instructions,),
                    )
                    logger.info("Updated book_level_instructions in database")
                else:
                    logger.error(
                        "story_config row does not exist - cannot store book_level_instructions"
                    )

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to update book_level_instructions: {e}")
            raise

    def get_book_level_instructions(self) -> str | None:
        """Retrieve the book-level writing instructions from the database."""
        if not self.enabled or not self._db:
            logger.warning("Database manager is disabled or not initialized")
            return None

        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()

                # Get book level instructions directly - assume column exists

                cursor.execute(
                    "SELECT book_level_instructions FROM story_config WHERE id = 1"
                )
                result = cursor.fetchone()

                if result and result["book_level_instructions"]:
                    return result["book_level_instructions"]
                else:
                    logger.warning("No book_level_instructions found in database")
                    return None

        except Exception as e:
            logger.error(f"Failed to retrieve book_level_instructions: {e}")
            return None

    def _extract_title_from_outline(self, global_story: str) -> str:
        """Extract the story title from the global story outline."""
        if not global_story:
            logger.warning("No global story provided for title extraction")
            return "Untitled Story"

        logger.debug(
            f"Extracting title from outline (first 500 chars): {global_story[:500]}..."
        )

        # Look for lines containing "Title:" or "Titel:" (for German)
        lines = global_story.split("\n")
        for i, line in enumerate(lines[:30]):  # Check first 30 lines
            if "title:" in line.lower() or "titel:" in line.lower():
                logger.debug(f"Found title line at position {i}: {line}")
                # Extract the title after the colon
                parts = line.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    # Title is on the same line
                    title = parts[1].strip()
                else:
                    # Title might be on the next line
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        # Skip separator lines
                        if (
                            next_line
                            and not next_line.startswith("---")
                            and not next_line.startswith("===")
                        ):
                            title = next_line
                        else:
                            # Try line after that
                            if i + 2 < len(lines):
                                title = lines[i + 2].strip()
                            else:
                                continue
                    else:
                        continue

                # Remove any quotes or special formatting - handle multiple levels
                title = title.strip()
                # Remove markdown bold formatting
                while "**" in title:
                    title = title.replace("**", "")
                # Remove various quote types
                title = (
                    title.strip('"')
                    .strip("'")
                    .strip("*")
                    .strip("„")
                    .strip('"')
                    .strip("»")
                    .strip("«")
                )
                # Final strip to remove any remaining whitespace
                title = title.strip()
                if title and title != "---" and title != "===":
                    logger.info(f"Successfully extracted title: '{title}'")
                    return title

        # If no explicit title line, try to get the first non-empty line
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("*"):
                # Take the first meaningful line as title
                if len(line) > 100:
                    title = line[:97] + "..."
                else:
                    title = line
                logger.info(f"Using first meaningful line as title: '{title}'")
                return title

        logger.warning("Could not extract any title from outline")
        return "Untitled Story"

    # Public methods for saving specific data types
    def save_worldbuilding(self, world_elements: dict[str, Any]) -> None:
        """Save worldbuilding elements to database."""
        if not self.enabled or not self._db:
            return

        try:
            # List of metadata fields to skip
            metadata_fields = {
                "stored_in_db",
                "research_sources",
                "research_context",
                "error",
                "source_urls",
                "search_queries",
            }

            for category, elements in world_elements.items():
                if category in metadata_fields:  # Skip metadata
                    continue
                if isinstance(elements, dict):
                    for key, value in elements.items():
                        # Skip any metadata fields within categories
                        if key in metadata_fields:
                            continue
                        # Save any non-empty content
                        if value and isinstance(value, str) and len(value.strip()) > 0:
                            # Log warning for very short content
                            if len(value.strip()) < 50:
                                logger.warning(
                                    f"Short worldbuilding content for {category}.{key}: {len(value.strip())} chars"
                                )
                            self._db.create_world_element(
                                category=category, element_key=key, element_value=value
                            )
            logger.info("Saved worldbuilding elements")
        except Exception as e:
            logger.error(f"Failed to save worldbuilding: {e}")
            raise

    def save_character(self, char_id: str, char_data: dict[str, Any]) -> None:
        """Save a character to database."""
        if not self.enabled or not self._db:
            return

        try:
            # Serialize any dict fields to JSON strings, ensure all are strings
            personality = char_data.get("personality", "")
            if isinstance(personality, dict):
                personality = json.dumps(personality)
            elif personality is None:
                personality = ""
            else:
                personality = str(personality)

            backstory = char_data.get("backstory", "")
            if isinstance(backstory, dict):
                backstory = json.dumps(backstory)
            elif backstory is None:
                backstory = ""
            else:
                backstory = str(backstory)

            role = char_data.get("role", "")
            if isinstance(role, dict):
                role = json.dumps(role)
            elif role is None:
                role = ""
            else:
                role = str(role)

            # Check if character already exists
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM characters WHERE identifier = ?", (char_id,)
                )
                existing = cursor.fetchone()

                if existing:
                    # Update existing character
                    db_char_id = existing["id"]
                    cursor.execute(
                        """UPDATE characters
                        SET name = ?, role = ?, backstory = ?, personality = ?
                        WHERE id = ?""",
                        (
                            char_data.get("name", char_id),
                            role,
                            backstory,
                            personality,
                            db_char_id,
                        ),
                    )
                    conn.commit()
                    logger.info(f"Updated existing character {char_id}")
                else:
                    # Create new character
                    db_char_id = self._db.create_character(
                        identifier=char_id,
                        name=char_data.get("name", char_id),
                        role=role,
                        backstory=backstory,
                        personality=personality,
                    )
                    logger.info(f"Created new character {char_id}")

            # Store character ID mapping
            self._character_id_map[char_id] = db_char_id

            # Save relationships if they exist
            if "relationships" in char_data:
                for other_char, rel_data in char_data["relationships"].items():
                    if other_char in self._character_id_map:
                        rel_type = (
                            rel_data
                            if isinstance(rel_data, str)
                            else rel_data.get("type", "unknown")
                        )
                        other_char_id = self._character_id_map[other_char]

                        # Check if relationship already exists
                        with self._db._get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                """SELECT id FROM character_relationships
                                    WHERE (character1_id = ? AND character2_id = ?)
                                        OR (character1_id = ? AND character2_id = ?)""",
                                (db_char_id, other_char_id, other_char_id, db_char_id),
                            )
                            existing_rel = cursor.fetchone()

                            if not existing_rel:
                                self._db.create_relationship(
                                    char1_id=db_char_id,
                                    char2_id=other_char_id,
                                    rel_type=rel_type,
                                )
                    else:
                        logger.debug(
                            f"Skipping relationship to {other_char} - character not yet saved"
                        )

            logger.info(f"Saved character {char_id}")
        except Exception as e:
            logger.error(f"Failed to save character {char_id}: {e}")
            raise

    def save_chapter_outline(
        self, chapter_num: int, chapter_data: dict[str, Any]
    ) -> None:
        """Save chapter outline to database."""
        if not self.enabled or not self._db:
            return

        try:
            # First check if chapter already exists
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM chapters WHERE chapter_number = ?", (chapter_num,)
                )
                result = cursor.fetchone()

                if result:
                    # Chapter exists, update it
                    chapter_id = result["id"]
                    cursor.execute(
                        "UPDATE chapters SET title = ?, outline = ? WHERE id = ?",
                        (
                            chapter_data.get("title", f"Chapter {chapter_num}"),
                            chapter_data.get("outline", ""),
                            chapter_id,
                        ),
                    )
                    conn.commit()
                    logger.info(f"Updated existing chapter {chapter_num} outline")
                else:
                    # Create new chapter
                    chapter_id = self._db.create_chapter(
                        chapter_num=chapter_num,
                        title=chapter_data.get("title", f"Chapter {chapter_num}"),
                        outline=chapter_data.get("outline", ""),
                    )
                    logger.info(f"Saved new chapter {chapter_num} outline")

            # Store chapter ID mapping
            self._chapter_id_map[str(chapter_num)] = chapter_id

            # Save scene descriptions from chapter planning
            scenes = chapter_data.get("scenes", {})
            for scene_num_str, scene_data in scenes.items():
                try:
                    scene_num = int(scene_num_str)
                    scene_description = scene_data.get("description", "")
                    scene_type = scene_data.get(
                        "scene_type", "exploration"
                    )  # Get scene_type with default

                    if scene_description:
                        # Check if scene already exists
                        with self._db._get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "SELECT id FROM scenes WHERE chapter_id = ? AND scene_number = ?",
                                (chapter_id, scene_num),
                            )
                            existing_scene = cursor.fetchone()

                            if existing_scene:
                                # Update existing scene with description and type
                                cursor.execute(
                                    "UPDATE scenes SET description = ?, scene_type = ? WHERE id = ?",
                                    (
                                        scene_description,
                                        scene_type,
                                        existing_scene["id"],
                                    ),
                                )
                            else:
                                # Create scene with description and type
                                cursor.execute(
                                    "INSERT INTO scenes (chapter_id, scene_number, description, scene_type) VALUES (?, ?, ?, ?)",
                                    (
                                        chapter_id,
                                        scene_num,
                                        scene_description,
                                        scene_type,
                                    ),
                                )
                            conn.commit()
                            logger.info(
                                f"Saved scene {scene_num} description (type: {scene_type}) for chapter {chapter_num}"
                            )
                except (ValueError, KeyError) as e:
                    logger.warning(f"Could not save scene {scene_num_str}: {e}")

        except Exception as e:
            logger.error(f"Failed to save chapter {chapter_num}: {e}")
            raise

    def save_scene_content(
        self, chapter_num: int, scene_num: int, content: str
    ) -> None:
        """Save scene content to database."""
        if not self.enabled or not self._db:
            return

        try:
            # Get chapter ID
            chapter_id = self._chapter_id_map.get(str(chapter_num))
            if not chapter_id:
                # Try to get from database
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM chapters WHERE chapter_number = ?",
                        (chapter_num,),
                    )
                    result = cursor.fetchone()
                    if result:
                        chapter_id = result["id"]
                        self._chapter_id_map[str(chapter_num)] = chapter_id

            if chapter_id:
                # Check if scene already exists
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM scenes WHERE chapter_id = ? AND scene_number = ?",
                        (chapter_id, scene_num),
                    )
                    existing_scene = cursor.fetchone()

                    if existing_scene:
                        # Update existing scene
                        cursor.execute(
                            "UPDATE scenes SET content = ? WHERE id = ?",
                            (content, existing_scene["id"]),
                        )
                        conn.commit()
                        logger.info(
                            f"Updated scene {scene_num} of chapter {chapter_num}"
                        )
                    else:
                        # Create new scene
                        self._db.create_scene(
                            chapter_id=chapter_id,
                            scene_num=scene_num,
                            outline="",  # Can be added later
                            content=content,
                        )
                        logger.info(
                            f"Created scene {scene_num} of chapter {chapter_num}"
                        )
            else:
                logger.warning(
                    f"Could not find chapter {chapter_num} to save scene {scene_num}"
                )

        except Exception as e:
            logger.error(
                f"Failed to save scene {scene_num} of chapter {chapter_num}: {e}"
            )
            raise

    def save_scene_instructions(
        self, chapter_num: int, scene_num: int, instructions: str
    ) -> None:
        """Save scene instructions to database."""
        if not self.enabled or not self._db:
            return

        try:
            # Get chapter ID
            chapter_id = self._chapter_id_map.get(str(chapter_num))
            if not chapter_id:
                # Try to get from database
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM chapters WHERE chapter_number = ?",
                        (chapter_num,),
                    )
                    result = cursor.fetchone()
                    if result:
                        chapter_id = result["id"]
                        self._chapter_id_map[str(chapter_num)] = chapter_id

            if chapter_id:
                # Update scene with instructions - assume column exists
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE scenes SET instructions = ? WHERE chapter_id = ? AND scene_number = ?",
                        (instructions, chapter_id, scene_num),
                    )
                    conn.commit()
                    logger.info(
                        f"Saved instructions for scene {scene_num} of chapter {chapter_num}"
                    )
            else:
                logger.warning(
                    f"Could not find chapter {chapter_num} to save scene instructions"
                )

        except Exception as e:
            logger.error(
                f"Failed to save scene instructions for Ch{chapter_num}/Sc{scene_num}: {e}"
            )
            raise

    def get_scene_instructions(self, chapter_num: int, scene_num: int) -> str | None:
        """Get scene instructions from database."""
        if not self.enabled or not self._db:
            return None

        try:
            # Get chapter ID
            chapter_id = self._chapter_id_map.get(str(chapter_num))
            if not chapter_id:
                # Try to get from database
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM chapters WHERE chapter_number = ?",
                        (chapter_num,),
                    )
                    result = cursor.fetchone()
                    if result:
                        chapter_id = result["id"]
                        self._chapter_id_map[str(chapter_num)] = chapter_id

            if chapter_id:
                # Get scene instructions - assume column exists
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT instructions FROM scenes WHERE chapter_id = ? AND scene_number = ?",
                        (chapter_id, scene_num),
                    )
                    result = cursor.fetchone()

                    if result and result["instructions"]:
                        logger.info(
                            f"Retrieved instructions for scene {scene_num} of chapter {chapter_num}"
                        )
                        return result["instructions"]
                    else:
                        logger.debug(
                            f"No instructions found for scene {scene_num} of chapter {chapter_num}"
                        )
                        return None
            else:
                logger.warning(
                    f"Could not find chapter {chapter_num} to get scene instructions"
                )
                return None

        except Exception as e:
            logger.error(
                f"Failed to get scene instructions for Ch{chapter_num}/Sc{scene_num}: {e}"
            )
            return None

    def track_plot_progression(
        self,
        progression_key: str,
        chapter_num: int,
        scene_num: int,
        description: str = "",
    ) -> bool:
        """
        Track a plot progression that has occurred.

        Args:
            progression_key: Unique key for the plot point (e.g., "felix_learns_about_mission")
            chapter_num: Chapter number where this occurs
            scene_num: Scene number where this occurs
            description: Optional description of the progression

        Returns:
            True if successfully tracked, False if already exists
        """
        if not self.enabled or not self._db:
            return False

        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO plot_progressions
                    (progression_key, chapter_number, scene_number, description)
                    VALUES (?, ?, ?, ?)
                """,
                    (progression_key, chapter_num, scene_num, description),
                )
                conn.commit()
                logger.info(
                    f"Tracked plot progression: {progression_key} at Ch{chapter_num}/Sc{scene_num}"
                )
                return True
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                logger.warning(f"Plot progression already exists: {progression_key}")
                return False
            logger.error(f"Failed to track plot progression: {e}")
            return False

    def get_plot_progressions(self) -> list[dict[str, Any]]:
        """
        Get all plot progressions that have occurred.

        Returns:
            List of plot progression dictionaries
        """
        if not self.enabled or not self._db:
            return []

        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT progression_key, chapter_number, scene_number, description
                    FROM plot_progressions
                    ORDER BY chapter_number, scene_number
                """
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get plot progressions: {e}")
            return []

    def check_plot_progression_exists(self, progression_key: str) -> bool:
        """
        Check if a plot progression has already occurred.

        Args:
            progression_key: The progression key to check

        Returns:
            True if the progression has already occurred
        """
        if not self.enabled or not self._db:
            return False

        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM plot_progressions WHERE progression_key = ?",
                    (progression_key,),
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Failed to check plot progression: {e}")
            return False

    def get_scene_id(self, chapter_num: int, scene_num: int) -> int | None:
        """Get the database ID for a specific scene.

        Args:
            chapter_num: Chapter number
            scene_num: Scene number

        Returns:
            Scene database ID or None if not found
        """
        if not self.enabled or not self._db:
            return None

        try:
            # Get chapter ID
            chapter_id = self._chapter_id_map.get(str(chapter_num))
            if not chapter_id:
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM chapters WHERE chapter_number = ?",
                        (chapter_num,),
                    )
                    result = cursor.fetchone()
                    if result:
                        chapter_id = result["id"]

            if chapter_id:
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM scenes WHERE chapter_id = ? AND scene_number = ?",
                        (chapter_id, scene_num),
                    )
                    result = cursor.fetchone()
                    return result["id"] if result else None

            return None

        except Exception as e:
            logger.error(f"Failed to get scene ID: {e}")
            return None

    def get_scene_content(self, chapter_num: int, scene_num: int) -> str | None:
        """Retrieve scene content from database."""
        if not self.enabled or not self._db:
            return None

        try:
            # Get chapter ID
            chapter_id = self._chapter_id_map.get(str(chapter_num))
            if not chapter_id:
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM chapters WHERE chapter_number = ?",
                        (chapter_num,),
                    )
                    result = cursor.fetchone()
                    if result:
                        chapter_id = result["id"]

            if chapter_id:
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT content FROM scenes WHERE chapter_id = ? AND scene_number = ?",
                        (chapter_id, scene_num),
                    )
                    result = cursor.fetchone()
                    if result:
                        return result["content"]

            return None

        except Exception as e:
            logger.error(
                f"Failed to get scene {scene_num} of chapter {chapter_num}: {e}"
            )
            return None

    def compile_story(self) -> str:
        """Compile the full story from the database."""
        if not self.enabled or not self._db:
            return ""

        try:
            story_parts = []

            # Get story title and metadata
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT title, genre, tone FROM story_config WHERE id = 1"
                )
                story_info = cursor.fetchone()
                if story_info and story_info["title"]:
                    story_parts.append(f"# {story_info['title']}\n")
                else:
                    story_parts.append(
                        f"# Generated {story_info['tone'].title()} {story_info['genre'].title()} Story\n"
                    )

            # Get all chapters and scenes
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT c.chapter_number, c.title as chapter_title,
                        s.scene_number, s.content
                    FROM chapters c
                    LEFT JOIN scenes s ON c.id = s.chapter_id
                    ORDER BY c.chapter_number, s.scene_number
                """
                )

                current_chapter = None
                for row in cursor.fetchall():
                    # Add chapter header if new chapter
                    if row["chapter_number"] != current_chapter:
                        current_chapter = row["chapter_number"]
                        chapter_title = row["chapter_title"] or f"{current_chapter}"
                        # Only use chapter title, no "Chapter X:" prefix
                        story_parts.append(f"\n## {chapter_title}\n")

                    # Add scene content with just separator, no "Scene X" label
                    if row["content"]:
                        story_parts.append("\n### \n")
                        story_parts.append(row["content"])
                        story_parts.append("\n")

            return "\n".join(story_parts)

        except Exception as e:
            logger.error(f"Failed to compile story: {e}")
            return ""
    
    def get_current_chapter(self) -> str:
        """Get the current chapter number being worked on."""
        if not self._db:
            return "1"
        
        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MAX(chapter_number) as current_chapter
                    FROM chapters
                    WHERE id IN (
                        SELECT DISTINCT chapter_id 
                        FROM scenes 
                        WHERE content IS NOT NULL
                    )
                """)
                result = cursor.fetchone()
                if result and result["current_chapter"]:
                    # Check if there are more chapters
                    cursor.execute("SELECT MAX(chapter_number) as max_chapter FROM chapters")
                    max_result = cursor.fetchone()
                    if max_result and max_result["max_chapter"] > result["current_chapter"]:
                        return str(result["current_chapter"] + 1)
                    return str(result["current_chapter"])
                return "1"
        except Exception as e:
            logger.error(f"Failed to get current chapter: {e}")
            return "1"
    
    def get_current_scene(self) -> str:
        """Get the current scene number being worked on."""
        if not self._db:
            return "1"
        
        try:
            current_chapter = int(self.get_current_chapter())
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MAX(s.scene_number) as current_scene
                    FROM scenes s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE c.chapter_number = ? AND s.content IS NOT NULL
                """, (current_chapter,))
                result = cursor.fetchone()
                if result and result["current_scene"]:
                    # Check if there are more scenes in this chapter
                    cursor.execute("""
                        SELECT COUNT(*) as total_scenes
                        FROM scenes s
                        JOIN chapters c ON s.chapter_id = c.id
                        WHERE c.chapter_number = ?
                    """, (current_chapter,))
                    total_result = cursor.fetchone()
                    if total_result and total_result["total_scenes"] > result["current_scene"]:
                        return str(result["current_scene"] + 1)
                    return str(result["current_scene"])
                return "1"
        except Exception as e:
            logger.error(f"Failed to get current scene: {e}")
            return "1"
    
    def set_current_chapter(self, chapter: int) -> None:
        """Set the current chapter being worked on."""
        # This is handled implicitly by writing scenes to the database
        pass
    
    def set_current_scene(self, chapter: int, scene: int) -> None:
        """Set the current scene being worked on."""
        # This is handled implicitly by writing scenes to the database
        pass
    
    def get_chapter_count(self) -> int:
        """Get the total number of chapters."""
        if not self._db:
            return 0
        
        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM chapters")
                result = cursor.fetchone()
                return result["count"] if result else 0
        except Exception as e:
            logger.error(f"Failed to get chapter count: {e}")
            return 0
    
    def get_scene_count_for_chapter(self, chapter: int) -> int:
        """Get the number of scenes in a specific chapter."""
        if not self._db:
            return 0
        
        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM scenes s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE c.chapter_number = ?
                """, (chapter,))
                result = cursor.fetchone()
                return result["count"] if result else 0
        except Exception as e:
            logger.error(f"Failed to get scene count for chapter {chapter}: {e}")
            return 0
    
    def get_total_scene_count(self) -> int:
        """Get the total number of scenes across all chapters."""
        if not self._db:
            return 0
        
        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM scenes")
                result = cursor.fetchone()
                return result["count"] if result else 0
        except Exception as e:
            logger.error(f"Failed to get total scene count: {e}")
            return 0
    
    def store_chapter_plan(self, chapters_dict: dict) -> None:
        """Store the planned chapter and scene structure in the database."""
        if not self._db:
            return
            
        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                
                # Store each chapter and its planned scenes
                for chapter_num_str, chapter_data in chapters_dict.items():
                    chapter_num = int(chapter_num_str)
                    
                    # Create the chapter
                    cursor.execute("""
                        INSERT OR REPLACE INTO chapters (chapter_number, title, outline)
                        VALUES (?, ?, ?)
                    """, (chapter_num, chapter_data.get("title", ""), chapter_data.get("outline", "")))
                    
                    chapter_id = cursor.lastrowid
                    
                    # Create placeholder scenes for this chapter
                    scenes = chapter_data.get("scenes", {})
                    for scene_num_str, scene_data in scenes.items():
                        scene_num = int(scene_num_str)
                        
                        # Create scene with empty content (to be filled when written)
                        cursor.execute("""
                            INSERT OR REPLACE INTO scenes (chapter_id, scene_number, description, scene_type, content)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            chapter_id, 
                            scene_num, 
                            scene_data.get("description", ""),
                            scene_data.get("scene_type", "exploration"),
                            ""  # Empty content, to be filled when scene is written
                        ))
                        
                        scene_id = cursor.lastrowid
                        
                        # Store scene planning data
                        cursor.execute("""
                            INSERT OR REPLACE INTO scene_planning (
                                scene_id, plot_progressions, character_learns, 
                                required_characters, forbidden_repetitions,
                                dramatic_purpose, tension_level, ends_with,
                                connects_to_next, pov_character, location
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            scene_id,
                            json.dumps(scene_data.get("plot_progressions", [])),
                            json.dumps(scene_data.get("character_learns", [])),
                            json.dumps(scene_data.get("required_characters", [])),
                            json.dumps(scene_data.get("forbidden_repetitions", [])),
                            scene_data.get("dramatic_purpose", "development"),
                            scene_data.get("tension_level", 5),
                            scene_data.get("ends_with", "transition"),
                            scene_data.get("connects_to_next", ""),
                            scene_data.get("pov_character", ""),
                            scene_data.get("location", "")
                        ))
                
                conn.commit()
                logger.info(f"Stored chapter plan with {len(chapters_dict)} chapters in database")
                
        except Exception as e:
            logger.error(f"Failed to store chapter plan: {e}")
    
    def get_planned_scene_count_for_chapter(self, chapter: int) -> int:
        """Get the planned number of scenes for a chapter (including empty placeholders)."""
        return self.get_scene_count_for_chapter(chapter)

    def close(self) -> None:
        """Close database connections."""
        # SQLite connections are closed automatically
        self._db = None
        logger.debug("Database manager closed")


# Global instance for easy access
_db_manager: StoryDatabaseManager | None = None


def get_db_manager() -> StoryDatabaseManager | None:
    """Get the global database manager instance."""
    return _db_manager


def initialize_db_manager(
    db_path: str | None = None, enabled: bool = True
) -> StoryDatabaseManager:
    """
    Initialize the global database manager.

    Args:
        db_path: Path to the database file
        enabled: Whether database operations are enabled

    Returns:
        The initialized database manager
    """
    global _db_manager
    _db_manager = StoryDatabaseManager(db_path, enabled)
    return _db_manager
