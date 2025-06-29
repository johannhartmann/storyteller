"""
StoryCraft Agent - Database models and managers.

This module provides the core database functionality including:
- StoryDatabase: Main database manager with CRUD operations
- DatabaseStateAdapter: Adapter for syncing between LangGraph state and database
- StoryQueries: High-level query functions for common operations
"""

# Standard library imports
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from storyteller_lib.core.exceptions import DatabaseError
from storyteller_lib.core.logger import get_logger
from storyteller_lib.core.models import StoryState

logger = get_logger(__name__)


class StoryDatabase:
    """
    Main database manager for story entity persistence.

    This class provides CRUD operations for all story entities including
    characters, locations, plot threads, chapters, scenes, and their
    relationships and state tracking.
    """

    def __init__(self, db_path: str = "story_database.db"):
        """
        Initialize database connection and create tables if needed.

        Args:
                db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the database schema from schema.sql file."""
        schema_path = Path(__file__).parent / "schema.sql"

        try:
            # Ensure the directory exists
            db_dir = Path(self.db_path).parent
            if not db_dir.exists():
                db_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
            
            with open(schema_path, "r") as f:
                schema_sql = f.read()

            with self._get_connection() as conn:
                conn.executescript(schema_sql)
                logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            raise DatabaseError(f"Failed to initialize database: {str(e)}")


    @contextmanager
    def _get_connection(self):
        """
        Context manager for database connections.

        Yields:
                sqlite3.Connection: Database connection with row factory set
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            yield conn
        finally:
            if conn:
                conn.close()

    # Story Management
    def initialize_story_config(
        self, title: str, genre: str, tone: str, **kwargs
    ) -> None:
        """
        Initialize or update the story configuration.

        Args:
                title: Story title
            genre: Story genre
            tone: Story tone
            **kwargs: Additional story fields (author, language, initial_idea, global_story)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if config exists
            cursor.execute("SELECT COUNT(*) as count FROM story_config")
            exists = cursor.fetchone()["count"] > 0

            if exists:
                # Update existing config
                update_fields = ["title = ?", "genre = ?", "tone = ?"]
                update_values = [title, genre, tone]

                for field in [
                    "author",
                    "language",
                    "initial_idea",
                    "global_story",
                    "narrative_structure",
                    "story_length",
                    "target_chapters",
                    "target_scenes_per_chapter",
                    "target_words_per_scene",
                    "target_pages",
                    "structure_metadata",
                    "book_level_instructions",
                    "research_worldbuilding",
                ]:
                    if field in kwargs:
                        update_fields.append(f"{field} = ?")
                        update_values.append(kwargs[field])

                query = (
                    f"UPDATE story_config SET {', '.join(update_fields)} WHERE id = 1"
                )
                cursor.execute(query, update_values)
            else:
                # Insert new config
                fields = ["id", "title", "genre", "tone"]
                values = [1, title, genre, tone]

                for field in [
                    "author",
                    "language",
                    "initial_idea",
                    "global_story",
                    "narrative_structure",
                    "story_length",
                    "target_chapters",
                    "target_scenes_per_chapter",
                    "target_words_per_scene",
                    "target_pages",
                    "structure_metadata",
                    "book_level_instructions",
                    "research_worldbuilding",
                ]:
                    if field in kwargs:
                        fields.append(field)
                        values.append(kwargs[field])

                placeholders = ", ".join(["?" for _ in values])
                field_names = ", ".join(fields)
                query = (
                    f"INSERT INTO story_config ({field_names}) VALUES ({placeholders})"
                )
                cursor.execute(query, values)

            conn.commit()
            logger.info(f"Initialized story config: {title}")

    def get_story_config(self) -> Dict[str, Any]:
        """
        Get story configuration.

        Returns:
                Dict containing story configuration
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM story_config WHERE id = 1")
            row = cursor.fetchone()

            if not row:
                raise DatabaseError("Story configuration not found")

            return dict(row)

    # Character Management
    def create_character(self, identifier: str, name: str, **kwargs) -> int:
        """
        Create a new character.

        Args:
                identifier: Character identifier (e.g., 'hero', 'mentor')
            name: Character name
            **kwargs: Additional fields (role, backstory, personality)

        Returns:
                int: The ID of the created character
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Prepare fields and values
            fields = ["identifier", "name"]
            values = [identifier, name]

            # Add optional fields
            for field in ["role", "backstory", "personality"]:
                if field in kwargs:
                    fields.append(field)
                    values.append(kwargs[field])

            # Create query
            placeholders = ", ".join(["?" for _ in values])
            field_names = ", ".join(fields)
            query = f"INSERT INTO characters ({field_names}) VALUES ({placeholders})"

            cursor.execute(query, values)
            conn.commit()

            character_id = cursor.lastrowid
            logger.info(f"Created character {name} (ID: {character_id})")
            return character_id

    def update_character_state(
        self, character_id: int, scene_id: int, state: Dict[str, Any]
    ) -> None:
        """
        Update character state at a specific scene.

        Args:
                character_id: The character ID
            scene_id: The scene ID
            state: Dictionary containing state fields (emotional_state, physical_location_id, evolution_notes)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if state already exists
            cursor.execute(
                "SELECT id FROM character_states WHERE character_id = ? AND scene_id = ?",
                (character_id, scene_id),
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing state
                update_fields = []
                update_values = []

                for field in [
                    "emotional_state",
                    "physical_location_id",
                    "evolution_notes",
                ]:
                    if field in state:
                        update_fields.append(f"{field} = ?")
                        update_values.append(state[field])

                if update_fields:
                    update_values.extend([character_id, scene_id])
                    query = f"""
                        UPDATE character_states 
                        SET {', '.join(update_fields)}
                        WHERE character_id = ? AND scene_id = ?
                    """
                    cursor.execute(query, update_values)
            else:
                # Insert new state
                fields = ["character_id", "scene_id"]
                values = [character_id, scene_id]

                for field in [
                    "emotional_state",
                    "physical_location_id",
                    "evolution_notes",
                ]:
                    if field in state:
                        fields.append(field)
                        values.append(state[field])

                placeholders = ", ".join(["?" for _ in values])
                field_names = ", ".join(fields)
                query = f"INSERT INTO character_states ({field_names}) VALUES ({placeholders})"
                cursor.execute(query, values)

            conn.commit()
            logger.debug(
                f"Updated character state for character {character_id} in scene {scene_id}"
            )

    def get_character_state_at_scene(
        self, character_id: int, scene_id: int
    ) -> Dict[str, Any]:
        """
        Get character state at a specific scene.

        Args:
                character_id: The character ID
            scene_id: The scene ID

        Returns:
                Dictionary containing character state
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM character_states WHERE character_id = ? AND scene_id = ?",
                (character_id, scene_id),
            )
            row = cursor.fetchone()

            if not row:
                return {}

            return dict(row)

    def add_character_knowledge(
        self, character_id: int, scene_id: int, knowledge: Dict[str, Any]
    ) -> None:
        """
        Add knowledge to a character at a specific scene.

        Args:
                character_id: The character ID
            scene_id: The scene ID
            knowledge: Dictionary with knowledge_type, knowledge_content, and source
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO character_knowledge 
                (character_id, scene_id, knowledge_type, knowledge_content, source)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    character_id,
                    scene_id,
                    knowledge.get("knowledge_type"),
                    knowledge.get("knowledge_content"),
                    knowledge.get("source"),
                ),
            )
            conn.commit()
            logger.debug(
                f"Added knowledge for character {character_id} in scene {scene_id}"
            )

    # Relationship Management
    def create_relationship(
        self, char1_id: int, char2_id: int, rel_type: str, **kwargs
    ) -> None:
        """
        Create a relationship between two characters.

        Args:
                char1_id: First character ID
            char2_id: Second character ID
            rel_type: Relationship type
            **kwargs: Additional fields (description, properties)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Ensure char1_id < char2_id to prevent duplicates
            if char1_id > char2_id:
                char1_id, char2_id = char2_id, char1_id

            # Serialize properties if provided
            properties = kwargs.get("properties", {})
            if isinstance(properties, dict):
                properties = json.dumps(properties)

            cursor.execute(
                """
                INSERT OR REPLACE INTO character_relationships 
                (character1_id, character2_id, relationship_type, description, properties)
                VALUES (?, ?, ?, ?, ?)
                """,
                (char1_id, char2_id, rel_type, kwargs.get("description"), properties),
            )
            conn.commit()
            logger.debug(
                f"Created relationship between characters {char1_id} and {char2_id}"
            )

    def get_character_relationships(self, character_id: int) -> List[Dict[str, Any]]:
        """
        Get all relationships for a character.

        Args:
                character_id: The character ID

        Returns:
                List of relationship dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get relationships where character is either character1 or character2
            cursor.execute(
                """
                SELECT cr.*, 
                        c1.name as character1_name, c1.identifier as character1_identifier,
                        c2.name as character2_name, c2.identifier as character2_identifier
                FROM character_relationships cr
                JOIN characters c1 ON cr.character1_id = c1.id
                JOIN characters c2 ON cr.character2_id = c2.id
                WHERE cr.character1_id = ? OR cr.character2_id = ?
                """,
                (character_id, character_id),
            )

            relationships = []
            for row in cursor.fetchall():
                rel = dict(row)

                # Deserialize properties
                if rel.get("properties"):
                    try:
                        rel["properties"] = json.loads(rel["properties"])
                    except json.JSONDecodeError:
                        pass

                # Determine the other character
                if rel["character1_id"] == character_id:
                    rel["other_character_id"] = rel["character2_id"]
                    rel["other_character_name"] = rel["character2_name"]
                    rel["other_character_identifier"] = rel["character2_identifier"]
                else:
                    rel["other_character_id"] = rel["character1_id"]
                    rel["other_character_name"] = rel["character1_name"]
                    rel["other_character_identifier"] = rel["character1_identifier"]

                relationships.append(rel)

            return relationships

    # Location Management
    def create_location(self, identifier: str, name: str, **kwargs) -> int:
        """
        Create a new location.

        Args:
                identifier: Location identifier
            name: Location name
            **kwargs: Additional fields (description, location_type, parent_location_id, properties)

        Returns:
                int: The ID of the created location
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Prepare fields and values
            fields = ["identifier", "name"]
            values = [identifier, name]

            # Add optional fields
            for field in ["description", "location_type", "parent_location_id"]:
                if field in kwargs:
                    fields.append(field)
                    values.append(kwargs[field])

            # Handle properties JSON field
            if "properties" in kwargs:
                fields.append("properties")
                properties = kwargs["properties"]
                if isinstance(properties, dict):
                    properties = json.dumps(properties)
                values.append(properties)

            # Create query
            placeholders = ", ".join(["?" for _ in values])
            field_names = ", ".join(fields)
            query = f"INSERT INTO locations ({field_names}) VALUES ({placeholders})"

            cursor.execute(query, values)
            conn.commit()

            location_id = cursor.lastrowid
            logger.info(f"Created location {name} (ID: {location_id})")
            return location_id

    # World Elements Management
    def create_world_element(
        self, category: str, element_key: str, element_value: Union[str, Dict, List]
    ) -> None:
        """
        Create or update a world element.

        Args:
                category: Element category (geography, history, culture, etc.)
            element_key: Specific element identifier
            element_value: Element value (will be JSON-serialized if dict/list)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Serialize value if needed
            if isinstance(element_value, (dict, list)):
                element_value = json.dumps(element_value)

            cursor.execute(
                """
                INSERT OR REPLACE INTO world_elements 
                (category, element_key, element_value)
                VALUES (?, ?, ?)
                """,
                (category, element_key, element_value),
            )
            conn.commit()
            logger.debug(f"Created/updated world element {category}.{element_key}")

    def get_world_elements(self, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Get world elements.

        Args:
                category: Optional category filter

        Returns:
                Dictionary of world elements organized by category
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if category:
                cursor.execute(
                    "SELECT * FROM world_elements WHERE category = ?", (category,)
                )
            else:
                cursor.execute("SELECT * FROM world_elements")

            elements = {}
            for row in cursor.fetchall():
                cat = row["category"]
                key = row["element_key"]
                value = row["element_value"]

                # Deserialize JSON values
                try:
                    value = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    pass

                if cat not in elements:
                    elements[cat] = {}
                elements[cat][key] = value

            return elements

    # Plot Thread Management
    def create_plot_thread(self, name: str, **kwargs) -> int:
        """
        Create a new plot thread.

        Args:
                name: Thread name
            **kwargs: Additional fields (description, thread_type, importance, status)

        Returns:
                int: The ID of the created plot thread
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Prepare fields and values
            fields = ["name"]
            values = [name]

            # Add optional fields with defaults
            field_defaults = {
                "description": None,
                "thread_type": "subplot",
                "importance": "minor",
                "status": "introduced",
            }

            for field, default in field_defaults.items():
                fields.append(field)
                values.append(kwargs.get(field, default))

            # Create query
            placeholders = ", ".join(["?" for _ in values])
            field_names = ", ".join(fields)
            query = f"INSERT OR REPLACE INTO plot_threads ({field_names}) VALUES ({placeholders})"

            cursor.execute(query, values)
            conn.commit()

            thread_id = cursor.lastrowid
            logger.info(f"Created plot thread '{name}' (ID: {thread_id})")
            return thread_id

    def update_plot_thread_status(self, thread_id: int, status: str) -> None:
        """
        Update the status of a plot thread.

        Args:
                thread_id: The plot thread ID
            status: New status (introduced, developed, resolved, abandoned)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE plot_threads SET status = ? WHERE id = ?", (status, thread_id)
            )
            conn.commit()
            logger.debug(f"Updated plot thread {thread_id} status to {status}")

    # Chapter/Scene Management
    def create_chapter(self, chapter_num: int, **kwargs) -> int:
        """
        Create a new chapter.

        Args:
                chapter_num: Chapter number
            **kwargs: Additional fields (title, outline)

        Returns:
                int: The ID of the created chapter
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO chapters (chapter_number, title, outline)
                VALUES (?, ?, ?)
                """,
                (chapter_num, kwargs.get("title"), kwargs.get("outline")),
            )
            conn.commit()

            chapter_id = cursor.lastrowid
            logger.info(f"Created chapter {chapter_num} (ID: {chapter_id})")
            return chapter_id

    def create_scene(self, chapter_id: int, scene_num: int, **kwargs) -> int:
        """
        Create a new scene.

        Args:
                chapter_id: The chapter ID
            scene_num: Scene number
            **kwargs: Additional fields (outline, content, content_ssml)

        Returns:
                int: The ID of the created scene
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO scenes (chapter_id, scene_number, description, content, content_ssml, scene_type)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    chapter_id,
                    scene_num,
                    kwargs.get("description", kwargs.get("outline")),
                    kwargs.get("content"),
                    kwargs.get("content_ssml"),
                    kwargs.get("scene_type", "exploration"),
                ),
            )
            conn.commit()

            scene_id = cursor.lastrowid
            logger.info(
                f"Created scene {scene_num} (ID: {scene_id}) for chapter {chapter_id}"
            )
            return scene_id

    def update_scene_ssml(self, scene_id: int, content_ssml: str) -> None:
        """
        Update the SSML content for a scene.

        Args:
                scene_id: The scene ID
            content_ssml: The SSML formatted content
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE scenes SET content_ssml = ? WHERE id = ?",
                (content_ssml, scene_id),
            )
            conn.commit()
            logger.info(f"Updated SSML content for scene {scene_id}")

    def add_entity_to_scene(
        self,
        scene_id: int,
        entity_type: str,
        entity_id: int,
        involvement: str = "present",
    ) -> None:
        """
        Associate an entity with a scene.

        Args:
                scene_id: The scene ID
            entity_type: Type of entity (character, location, world_element)
            entity_id: The entity ID
            involvement: Type of involvement (present, mentioned, affected)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO scene_entities 
                (scene_id, entity_type, entity_id, involvement_type)
                VALUES (?, ?, ?, ?)
                """,
                (scene_id, entity_type, entity_id, involvement),
            )
            conn.commit()
            logger.debug(f"Added {entity_type} {entity_id} to scene {scene_id}")

    def add_plot_thread_development(
        self,
        plot_thread_id: int,
        scene_id: int,
        development_type: str,
        description: str,
    ) -> None:
        """
        Add a plot thread development to a scene.

        Args:
                plot_thread_id: The plot thread ID
            scene_id: The scene ID
            development_type: Type of development (introduced, advanced, resolved, etc.)
            description: Description of the development
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO plot_thread_developments 
                (plot_thread_id, scene_id, development_type, description)
                VALUES (?, ?, ?, ?)
                """,
                (plot_thread_id, scene_id, development_type, description),
            )
            conn.commit()
            logger.debug(
                f"Added plot thread development for thread {plot_thread_id} in scene {scene_id}"
            )

    # Query Functions
    def get_entities_in_scene(self, scene_id: int) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all entities involved in a scene.

        Args:
                scene_id: The scene ID

        Returns:
                Dictionary organized by entity type, each containing a list of entities
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            entities = {"characters": [], "locations": [], "world_elements": []}

            # Get characters
            cursor.execute(
                """
                SELECT c.*, se.involvement_type
                FROM scene_entities se
                JOIN characters c ON se.entity_id = c.id
                WHERE se.scene_id = ? AND se.entity_type = 'character'
                """,
                (scene_id,),
            )
            entities["characters"] = [dict(row) for row in cursor.fetchall()]

            # Get locations
            cursor.execute(
                """
                SELECT l.*, se.involvement_type
                FROM scene_entities se
                JOIN locations l ON se.entity_id = l.id
                WHERE se.scene_id = ? AND se.entity_type = 'location'
                """,
                (scene_id,),
            )
            entities["locations"] = [dict(row) for row in cursor.fetchall()]

            # Get world elements
            cursor.execute(
                """
                SELECT we.*, se.involvement_type
                FROM scene_entities se
                JOIN world_elements we ON se.entity_id = we.id
                WHERE se.scene_id = ? AND se.entity_type = 'world_element'
                """,
                (scene_id,),
            )
            for row in cursor.fetchall():
                elem = dict(row)
                # Deserialize element value
                try:
                    elem["element_value"] = json.loads(elem["element_value"])
                except (json.JSONDecodeError, TypeError):
                    pass
                entities["world_elements"].append(elem)

            return entities

    def get_scenes_with_entity(
        self, entity_type: str, entity_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get all scenes where an entity appears.

        Args:
                entity_type: Type of entity
            entity_id: The entity ID

        Returns:
                List of scene dictionaries with involvement information
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT s.*, c.chapter_number, c.title as chapter_title, 
                        se.involvement_type
                FROM scene_entities se
                JOIN scenes s ON se.scene_id = s.id
                JOIN chapters c ON s.chapter_id = c.id
                WHERE se.entity_type = ? AND se.entity_id = ?
                ORDER BY c.chapter_number, s.scene_number
                """,
                (entity_type, entity_id),
            )

            return [dict(row) for row in cursor.fetchall()]

    def get_entity_evolution(
        self, entity_type: str, entity_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get the evolution history of an entity.

        Args:
                entity_type: Type of entity
            entity_id: The entity ID

        Returns:
                List of change records ordered by scene
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT ec.*, s.scene_number, c.chapter_number
                FROM entity_changes ec
                JOIN scenes s ON ec.scene_id = s.id
                JOIN chapters c ON s.chapter_id = c.id
                WHERE ec.entity_type = ? AND ec.entity_id = ?
                ORDER BY c.chapter_number, s.scene_number
                """,
                (entity_type, entity_id),
            )

            changes = []
            for row in cursor.fetchall():
                change = dict(row)

                # Deserialize JSON fields
                for field in ["old_value", "new_value"]:
                    if change.get(field):
                        try:
                            change[field] = json.loads(change[field])
                        except json.JSONDecodeError:
                            pass

                changes.append(change)

            return changes

    # Context Functions
    def get_scene_context(self, scene_id: int) -> Dict[str, Any]:
        """
        Get complete context for a scene including all entities, their states, and relationships.

        Args:
                scene_id: The scene ID

        Returns:
                Dictionary containing full scene context
        """
        context = {
            "scene_id": scene_id,
            "entities": self.get_entities_in_scene(scene_id),
            "character_states": {},
            "character_relationships": {},
            "plot_threads": [],
        }

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get scene details
            cursor.execute(
                """
                SELECT s.*, c.chapter_number, c.title as chapter_title
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE s.id = ?
                """,
                (scene_id,),
            )
            scene_info = cursor.fetchone()
            if scene_info:
                context["scene_info"] = dict(scene_info)

            # Get character states for all characters in the scene
            for char in context["entities"]["characters"]:
                char_id = char["id"]
                context["character_states"][char_id] = (
                    self.get_character_state_at_scene(char_id, scene_id)
                )
                context["character_relationships"][char_id] = (
                    self.get_character_relationships(char_id)
                )

            # Get plot thread developments in this scene
            cursor.execute(
                """
                SELECT pt.*, ptd.development_type, ptd.description as development_description
                FROM plot_thread_developments ptd
                JOIN plot_threads pt ON ptd.plot_thread_id = pt.id
                WHERE ptd.scene_id = ?
                """,
                (scene_id,),
            )
            context["plot_threads"] = [dict(row) for row in cursor.fetchall()]

        return context

    def get_chapter_start_context(self, chapter_id: int) -> Dict[str, Any]:
        """
        Get context at the start of a chapter.

        Args:
                chapter_id: The chapter ID

        Returns:
                Dictionary containing context from the end of the previous chapter
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get chapter info
            cursor.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
            chapter = cursor.fetchone()
            if not chapter:
                raise DatabaseError(f"Chapter {chapter_id} not found")

            chapter_info = dict(chapter)
            chapter_num = chapter_info["chapter_number"]

            # Get the last scene of the previous chapter
            if chapter_num > 1:
                cursor.execute(
                    """
                    SELECT s.id
                    FROM scenes s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE c.chapter_number = ?
                    ORDER BY s.scene_number DESC
                    LIMIT 1
                    """,
                    (chapter_num - 1,),
                )
                prev_scene = cursor.fetchone()

                if prev_scene:
                    return self.get_scene_context(prev_scene["id"])

            # If no previous chapter, return initial story context
            return {
                "chapter_info": chapter_info,
                "is_first_chapter": True,
                "story": self.get_story_config(),
            }

    def get_chapter_end_context(self, chapter_id: int) -> Dict[str, Any]:
        """
        Get context at the end of a chapter.

        Args:
                chapter_id: The chapter ID

        Returns:
                Dictionary containing context from the last scene of the chapter
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get the last scene of this chapter
            cursor.execute(
                """
                SELECT id
                FROM scenes
                WHERE chapter_id = ?
                ORDER BY scene_number DESC
                LIMIT 1
                """,
                (chapter_id,),
            )
            last_scene = cursor.fetchone()

            if last_scene:
                return self.get_scene_context(last_scene["id"])

            # If no scenes in chapter yet, return chapter info
            cursor.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
            chapter = cursor.fetchone()

            return {"chapter_info": dict(chapter) if chapter else {}, "no_scenes": True}

    def log_entity_change(
        self,
        entity_type: str,
        entity_id: int,
        scene_id: int,
        change_type: str,
        change_description: str,
        old_value: Any = None,
        new_value: Any = None,
    ) -> None:
        """
        Log a change to an entity.

        Args:
                entity_type: Type of entity
            entity_id: The entity ID
            scene_id: The scene where the change occurs
            change_type: Type of change (created, modified, revealed, etc.)
            change_description: Description of the change
            old_value: Previous value (will be JSON-serialized)
            new_value: New value (will be JSON-serialized)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Serialize values if needed
            if old_value is not None and not isinstance(old_value, str):
                old_value = json.dumps(old_value)
            if new_value is not None and not isinstance(new_value, str):
                new_value = json.dumps(new_value)

            cursor.execute(
                """
                INSERT INTO entity_changes 
                (entity_type, entity_id, scene_id, change_type, change_description,
                old_value, new_value)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entity_type,
                    entity_id,
                    scene_id,
                    change_type,
                    change_description,
                    old_value,
                    new_value,
                ),
            )
            conn.commit()
            logger.debug(
                f"Logged {change_type} change for {entity_type} {entity_id} in scene {scene_id}"
            )

    # Content Registry Methods
    def register_content(
        self,
        content_type: str,
        content_text: str,
        chapter_id: Optional[int] = None,
        scene_id: Optional[int] = None,
    ) -> bool:
        """
        Register content in the used content registry to prevent repetition.

        Args:
                content_type: Type of content (description, event, action, etc.)
            content_text: The actual content text
            chapter_id: Optional chapter ID
            scene_id: Optional scene ID

        Returns:
                True if content was new and registered, False if already exists
        """
        import hashlib

        # Create hash of content for quick lookup
        content_hash = hashlib.md5(content_text.encode()).hexdigest()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    INSERT INTO used_content_registry 
                    (content_type, content_hash, content_text, chapter_id, scene_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (content_type, content_hash, content_text, chapter_id, scene_id),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # Content already exists
                return False

    def check_content_exists(self, content_type: str, content_text: str) -> bool:
        """
        Check if content already exists in the registry.

        Args:
                content_type: Type of content
            content_text: The content to check

        Returns:
                True if content exists, False otherwise
        """
        import hashlib

        content_hash = hashlib.md5(content_text.encode()).hexdigest()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) as count FROM used_content_registry
                WHERE content_type = ? AND content_hash = ?
                """,
                (content_type, content_hash),
            )
            return cursor.fetchone()["count"] > 0

    def get_used_content(
        self, content_type: Optional[str] = None, limit: int = 100
    ) -> List[str]:
        """
        Get list of used content from the registry.

        Args:
                content_type: Optional filter by content type
            limit: Maximum number of items to return

        Returns:
                List of used content strings
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if content_type:
                cursor.execute(
                    """
                    SELECT content_text FROM used_content_registry
                    WHERE content_type = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (content_type, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT content_text FROM used_content_registry
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            return [row["content_text"] for row in cursor.fetchall()]

    # LLM Evaluation Management
    def save_llm_evaluation(
        self,
        evaluation_type: str,
        evaluation_result: Dict[str, Any],
        evaluated_content: str,
        scene_id: Optional[int] = None,
        chapter_id: Optional[int] = None,
        genre: Optional[str] = None,
        tone: Optional[str] = None,
    ) -> int:
        """
        Save an LLM evaluation to the database.

        Args:
                evaluation_type: Type of evaluation (repetition, scene_quality, etc.)
            evaluation_result: The evaluation result dictionary
            evaluated_content: What was evaluated
            scene_id: Optional scene ID
            chapter_id: Optional chapter ID
            genre: Story genre
            tone: Story tone

        Returns:
                The inserted evaluation ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO llm_evaluations 
                (evaluation_type, scene_id, chapter_id, evaluated_content, 
                evaluation_result, genre, tone)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evaluation_type,
                    scene_id,
                    chapter_id,
                    evaluated_content,
                    json.dumps(evaluation_result),
                    genre,
                    tone,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_llm_evaluations(
        self, evaluation_type: Optional[str] = None, scene_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve LLM evaluations from the database.

        Args:
                evaluation_type: Optional filter by type
            scene_id: Optional filter by scene

        Returns:
                List of evaluation records
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM llm_evaluations WHERE 1=1"
            params = []

            if evaluation_type:
                query += " AND evaluation_type = ?"
                params.append(evaluation_type)

            if scene_id:
                query += " AND scene_id = ?"
                params.append(scene_id)

            query += " ORDER BY created_at DESC"

            cursor.execute(query, params)

            evaluations = []
            for row in cursor.fetchall():
                eval_dict = dict(row)
                try:
                    eval_dict["evaluation_result"] = json.loads(
                        eval_dict["evaluation_result"]
                    )
                except json.JSONDecodeError:
                    pass
                evaluations.append(eval_dict)

            return evaluations

    # Character Promise Management
    def save_character_promise(
        self,
        character_id: int,
        promise_type: str,
        promise_description: str,
        introduced_chapter: int,
        expected_resolution: str = "ongoing",
    ) -> int:
        """
        Save a character promise to the database.

        Args:
                character_id: The character ID
            promise_type: Type of promise (growth, revelation, etc.)
            promise_description: Description of the promise
            introduced_chapter: Chapter where introduced
            expected_resolution: When expected to resolve

        Returns:
                The inserted promise ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO character_promises 
                (character_id, promise_type, promise_description, 
                introduced_chapter, expected_resolution)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    character_id,
                    promise_type,
                    promise_description,
                    introduced_chapter,
                    expected_resolution,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def mark_promise_fulfilled(self, promise_id: int, scene_id: int) -> None:
        """
        Mark a character promise as fulfilled.

        Args:
                promise_id: The promise ID
            scene_id: Scene where fulfilled
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE character_promises 
                SET fulfilled = TRUE, fulfilled_scene_id = ?
                WHERE id = ?
                """,
                (scene_id, promise_id),
            )
            conn.commit()

    def get_character_promises(
        self, character_id: int, fulfilled: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Get promises for a character.

        Args:
                character_id: The character ID
            fulfilled: Optional filter by fulfillment status

        Returns:
                List of promises
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM character_promises WHERE character_id = ?"
            params = [character_id]

            if fulfilled is not None:
                query += " AND fulfilled = ?"
                params.append(fulfilled)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    # Story Event Management
    def save_story_event(
        self,
        chapter_number: int,
        scene_number: int,
        event_type: str,
        event_description: str,
        participants: List[int] = None,
        location_id: Optional[int] = None,
        plot_threads_affected: List[int] = None,
    ) -> int:
        """
        Save a story event to the database.

        Args:
                chapter_number: Chapter number
            scene_number: Scene number
            event_type: Type of event
            event_description: Event description
            participants: List of character IDs
            location_id: Optional location ID
            plot_threads_affected: List of plot thread IDs

        Returns:
                The inserted event ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO story_events 
                (chapter_number, scene_number, event_type, event_description,
                participants, location_id, plot_threads_affected)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chapter_number,
                    scene_number,
                    event_type,
                    event_description,
                    json.dumps(participants or []),
                    location_id,
                    json.dumps(plot_threads_affected or []),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_story_events(
        self, chapter_number: Optional[int] = None, event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get story events.

        Args:
                chapter_number: Optional filter by chapter
            event_type: Optional filter by type

        Returns:
                List of events
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM story_events WHERE 1=1"
            params = []

            if chapter_number:
                query += " AND chapter_number = ?"
                params.append(chapter_number)

            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)

            query += " ORDER BY chapter_number, scene_number"

            cursor.execute(query, params)

            events = []
            for row in cursor.fetchall():
                event = dict(row)
                try:
                    event["participants"] = json.loads(event["participants"])
                    event["plot_threads_affected"] = json.loads(
                        event["plot_threads_affected"]
                    )
                except json.JSONDecodeError:
                    pass
                events.append(event)

            return events

    # Scene Quality Metrics
    def save_scene_quality_metrics(
        self, scene_id: int, metrics: Dict[str, float], evaluation_notes: Dict[str, Any]
    ) -> None:
        """
        Save scene quality metrics.

        Args:
                scene_id: The scene ID
            metrics: Dictionary of metric scores
            evaluation_notes: Detailed evaluation notes
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO scene_quality_metrics 
                (scene_id, prose_quality_score, pacing_appropriateness,
                character_consistency, genre_alignment, reader_engagement_estimate,
                evaluation_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scene_id,
                    metrics.get("prose_quality", 0.5),
                    metrics.get("pacing_appropriateness", 0.5),
                    metrics.get("character_consistency", 0.5),
                    metrics.get("genre_alignment", 0.5),
                    metrics.get("reader_engagement", 0.5),
                    json.dumps(evaluation_notes),
                ),
            )
            conn.commit()

    # Narrative Pattern Management
    def save_narrative_pattern(
        self,
        pattern_type: str,
        pattern_description: str,
        occurrences: List[int],
        is_intentional: bool = False,
        narrative_purpose: Optional[str] = None,
    ) -> int:
        """
        Save a detected narrative pattern.

        Args:
                pattern_type: Type of pattern
            pattern_description: Description of the pattern
            occurrences: List of scene IDs where it occurs
            is_intentional: Whether pattern is intentional
            narrative_purpose: Purpose if intentional

        Returns:
                The inserted pattern ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO narrative_patterns 
                (pattern_type, pattern_description, occurrences,
                is_intentional, narrative_purpose)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    pattern_type,
                    pattern_description,
                    json.dumps(occurrences),
                    is_intentional,
                    narrative_purpose,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_narrative_patterns(
        self, pattern_type: Optional[str] = None, is_intentional: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Get narrative patterns.

        Args:
                pattern_type: Optional filter by type
            is_intentional: Optional filter by intentionality

        Returns:
                List of patterns
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM narrative_patterns WHERE 1=1"
            params = []

            if pattern_type:
                query += " AND pattern_type = ?"
                params.append(pattern_type)

            if is_intentional is not None:
                query += " AND is_intentional = ?"
                params.append(is_intentional)

            cursor.execute(query, params)

            patterns = []
            for row in cursor.fetchall():
                pattern = dict(row)
                try:
                    pattern["occurrences"] = json.loads(pattern["occurrences"])
                except json.JSONDecodeError:
                    pass
                patterns.append(pattern)

            return patterns


class DatabaseStateAdapter:
    """
    Adapter to sync between LangGraph StoryState and database.

    This class provides methods to synchronize the in-memory state used by
    LangGraph with the persistent database storage.
    """

    def __init__(self, db: StoryDatabase):
        """
        Initialize the adapter with a database instance.

        Args:
                db: StoryDatabase instance
        """
        self.db = db

    def sync_to_database(self, state: StoryState) -> None:
        """
        Sync current state to database.

        Args:
                state: The current LangGraph StoryState
        """
        # Initialize or update story config
        self.db.initialize_story_config(
            title=state.get("initial_idea", "Untitled Story")[:100],
            genre=state.get("genre", "unknown"),
            tone=state.get("tone", "unknown"),
            author=state.get("author"),
            language=state.get("language", "english"),
            initial_idea=state.get("initial_idea"),
            global_story=state.get("global_story"),
        )

        # Sync world elements
        if "world_elements" in state and state["world_elements"]:
            for category, elements in state["world_elements"].items():
                for key, value in elements.items():
                    self.db.create_world_element(category, key, value)

        # Sync characters
        character_id_map = {}
        if "characters" in state and state["characters"]:
            for char_id, char_data in state["characters"].items():
                # Create character if not exists
                try:
                    char_db_id = self.db.create_character(
                        identifier=char_id,
                        name=char_data.get("name", char_id),
                        role=char_data.get("role", ""),
                        backstory=char_data.get("backstory", ""),
                        personality=char_data.get("personality", ""),
                    )
                except sqlite3.IntegrityError:
                    # Character already exists, get its ID
                    with self.db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM characters WHERE identifier = ?", (char_id,)
                        )
                        result = cursor.fetchone()
                        char_db_id = result["id"] if result else None

                if char_db_id:
                    character_id_map[char_id] = char_db_id

        # Sync relationships
        if character_id_map and "characters" in state:
            for char_id, char_data in state["characters"].items():
                if char_id in character_id_map and "relationships" in char_data:
                    char_db_id = character_id_map[char_id]
                    for other_char, rel_type in char_data["relationships"].items():
                        if other_char in character_id_map:
                            other_db_id = character_id_map[other_char]
                            self.db.create_relationship(
                                char1_id=char_db_id,
                                char2_id=other_db_id,
                                rel_type=rel_type,
                            )

        # Sync plot threads
        plot_thread_id_map = {}
        if "plot_threads" in state and state["plot_threads"]:
            for thread_name, thread_data in state["plot_threads"].items():
                try:
                    thread_id = self.db.create_plot_thread(
                        name=thread_name,
                        description=thread_data.get("description", ""),
                        thread_type=thread_data.get("thread_type", "subplot"),
                        importance=thread_data.get("importance", "minor"),
                        status=thread_data.get("status", "introduced"),
                    )
                    plot_thread_id_map[thread_name] = thread_id
                except sqlite3.IntegrityError:
                    # Thread already exists, update status
                    with self.db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM plot_threads WHERE name = ?", (thread_name,)
                        )
                        result = cursor.fetchone()
                        if result:
                            thread_id = result["id"]
                            plot_thread_id_map[thread_name] = thread_id
                            self.db.update_plot_thread_status(
                                thread_id, thread_data.get("status", "introduced")
                            )

        # Sync chapters and scenes
        if "chapters" in state and state["chapters"]:
            for chapter_key, chapter_data in state["chapters"].items():
                # Extract chapter number from key (e.g., "Chapter 1" -> 1)
                try:
                    chapter_num = int(chapter_key.split()[-1])
                except (ValueError, IndexError):
                    chapter_num = 1

                # Create chapter if not exists
                try:
                    chapter_id = self.db.create_chapter(
                        chapter_num=chapter_num,
                        title=chapter_data.get("title", ""),
                        outline=chapter_data.get("outline", ""),
                    )
                except sqlite3.IntegrityError:
                    # Chapter already exists, get its ID
                    with self.db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM chapters WHERE chapter_number = ?",
                            (chapter_num,),
                        )
                        result = cursor.fetchone()
                        chapter_id = result["id"] if result else None

                # Sync scenes
                if chapter_id and "scenes" in chapter_data:
                    for scene_key, scene_data in chapter_data["scenes"].items():
                        # Extract scene number from key
                        try:
                            scene_num = int(scene_key.split()[-1])
                        except (ValueError, IndexError):
                            scene_num = 1

                        # Create scene if not exists
                        try:
                            scene_id = self.db.create_scene(
                                chapter_id=chapter_id,
                                scene_num=scene_num,
                                outline=scene_data.get("outline", ""),
                                content=scene_data.get("content", ""),
                            )
                        except sqlite3.IntegrityError:
                            # Scene already exists
                            with self.db._get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "SELECT id FROM scenes WHERE chapter_id = ? AND scene_number = ?",
                                    (chapter_id, scene_num),
                                )
                                result = cursor.fetchone()
                                scene_id = result["id"] if result else None

        logger.info("Synced state to database")

    def load_from_database(self) -> StoryState:
        """
        Load state from database.

        Returns:
                StoryState: The loaded state
        """
        # Get story details
        story = self.db.get_story_config()

        # Initialize state with story details
        state: StoryState = {
            "messages": [],
            "genre": story["genre"],
            "tone": story["tone"],
            "author": story.get("author", ""),
            "author_style_guidance": "",
            "language": story.get("language", "english"),
            "initial_idea": story.get("initial_idea", ""),
            "initial_idea_elements": {},
            "global_story": story.get("global_story", ""),
            "chapters": {},
            "characters": {},
            "revelations": {},
            "creative_elements": {},
            "world_elements": {},
            "plot_threads": {},
            "current_chapter": "",
            "current_scene": "",
            "current_scene_content": "",
            "scene_reflection": {},
            "completed": False,
            "last_node": "",
        }

        # Load world elements
        state["world_elements"] = self.db.get_world_elements()

        # Load characters
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM characters")

            for row in cursor.fetchall():
                char = dict(row)
                char_profile = {
                    "name": char["name"],
                    "role": char.get("role", ""),
                    "backstory": char.get("backstory", ""),
                    "evolution": [],
                    "relationships": {},
                }

                # Load relationships
                relationships = self.db.get_character_relationships(char["id"])
                for rel in relationships:
                    char_profile["relationships"][rel["other_character_identifier"]] = (
                        rel["relationship_type"]
                    )

                state["characters"][char["identifier"]] = char_profile

        # Load plot threads
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM plot_threads")

            for row in cursor.fetchall():
                thread = dict(row)
                state["plot_threads"][thread["name"]] = {
                    "description": thread.get("description", ""),
                    "thread_type": thread.get("thread_type", "subplot"),
                    "importance": thread.get("importance", "minor"),
                    "status": thread.get("status", "introduced"),
                    "development_history": [],
                }

        # Load chapters and scenes
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chapters ORDER BY chapter_number")

            for chapter_row in cursor.fetchall():
                chapter = dict(chapter_row)
                chapter_key = f"Chapter {chapter['chapter_number']}"

                state["chapters"][chapter_key] = {
                    "title": chapter.get("title", ""),
                    "outline": chapter.get("outline", ""),
                    "scenes": {},
                    "reflection_notes": [],
                }

                # Load scenes for this chapter
                cursor.execute(
                    "SELECT * FROM scenes WHERE chapter_id = ? ORDER BY scene_number",
                    (chapter["id"],),
                )

                for scene_row in cursor.fetchall():
                    scene = dict(scene_row)
                    scene_key = f"Scene {scene['scene_number']}"

                    state["chapters"][chapter_key]["scenes"][scene_key] = {
                        "content": scene.get("content", ""),
                        "reflection_notes": [],
                    }

        logger.info("Loaded state from database")
        return state

    def update_scene_entities(self, state: StoryState, scene_id: int) -> None:
        """
        Update database with entities involved in current scene.

        Args:
            state: The current LangGraph StoryState
            scene_id: The database scene ID
        """
        # Identify characters in the scene
        current_chapter = state.get("current_chapter")
        current_scene = state.get("current_scene")

        if current_chapter and current_scene:
            scene_content = state["chapters"][current_chapter]["scenes"][
                current_scene
            ].get("content", "")

            # Simple character detection based on names
            for char_id, char_data in state.get("characters", {}).items():
                char_name = char_data.get("name", "")
                if char_name and char_name in scene_content:
                    # Get character database ID
                    with self.db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM characters WHERE identifier = ?", (char_id,)
                        )
                        result = cursor.fetchone()
                        if result:
                            self.db.add_entity_to_scene(
                                scene_id, "character", result["id"], "present"
                            )

        logger.debug(f"Updated entities for scene {scene_id}")


class StoryQueries:
    """
    High-level query functions for common database operations.

    This class provides convenient methods for complex queries that span
    multiple tables or require aggregation.
    """

    def __init__(self, db: StoryDatabase):
        """
        Initialize with a database instance.

        Args:
            db: StoryDatabase instance
        """
        self.db = db

    def find_chapters_affected_by_character_change(
        self, character_id: int, change_type: str
    ) -> List[int]:
        """
        Find all chapters that need revision when a character changes.

        Args:
            character_id: The character ID
            change_type: Type of change (e.g., 'backstory', 'personality')

        Returns:
                List of chapter IDs that may need revision
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Find all chapters where this character appears
            cursor.execute(
                """
                SELECT DISTINCT c.id, c.chapter_number
                FROM chapters c
                JOIN scenes s ON s.chapter_id = c.id
                JOIN scene_entities se ON se.scene_id = s.id
                WHERE se.entity_type = 'character' AND se.entity_id = ?
                ORDER BY c.chapter_number
                """,
                (character_id,),
            )

            affected_chapters = []
            for row in cursor.fetchall():
                chapter_id = row["id"]

                # For major changes, all chapters with the character are affected
                if change_type in ["backstory", "personality", "name"]:
                    affected_chapters.append(chapter_id)
                # For minor changes, only chapters where character is present
                elif change_type in ["appearance", "mannerisms"]:
                    cursor.execute(
                        """
                        SELECT COUNT(*) as presence_count
                        FROM scenes s
                        JOIN scene_entities se ON se.scene_id = s.id
                        WHERE s.chapter_id = ? AND se.entity_type = 'character' 
                        AND se.entity_id = ? AND se.involvement_type = 'present'
                        """,
                        (chapter_id, character_id),
                    )
                    result = cursor.fetchone()
                    if result and result["presence_count"] > 0:
                        affected_chapters.append(chapter_id)

            return affected_chapters

    def get_character_journey(self, character_id: int) -> Dict[str, Any]:
        """
        Get complete journey of a character through the story.

        Args:
                character_id: The character ID

        Returns:
                Dictionary containing the character's complete journey
        """
        journey = {
            "character_id": character_id,
            "appearances": [],
            "state_changes": [],
            "knowledge_progression": [],
            "relationship_changes": [],
        }

        # Get all scenes where character appears
        scenes = self.db.get_scenes_with_entity("character", character_id)

        for scene in scenes:
            scene_id = scene["id"]

            # Get character state at this scene
            state = self.db.get_character_state_at_scene(character_id, scene_id)

            appearance = {
                "chapter": scene["chapter_number"],
                "scene": scene["scene_number"],
                "involvement": scene["involvement_type"],
                "state": state,
            }

            journey["appearances"].append(appearance)

            # Track state changes
            if state.get("evolution_notes"):
                journey["state_changes"].append(
                    {
                        "chapter": scene["chapter_number"],
                        "scene": scene["scene_number"],
                        "change": state["evolution_notes"],
                    }
                )

        # Get entity changes
        journey["evolution"] = self.db.get_entity_evolution("character", character_id)

        return journey

    def get_unresolved_plot_threads(self) -> List[Dict[str, Any]]:
        """
        Get all plot threads that haven't been resolved.

        Returns:
                List of unresolved plot threads with their details
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT pt.*, 
                        COUNT(DISTINCT ptd.scene_id) as development_count,
                        MAX(c.chapter_number) as last_chapter,
                        MAX(s.scene_number) as last_scene
                FROM plot_threads pt
                LEFT JOIN plot_thread_developments ptd ON pt.id = ptd.plot_thread_id
                LEFT JOIN scenes s ON ptd.scene_id = s.id
                LEFT JOIN chapters c ON s.chapter_id = c.id
                WHERE pt.status NOT IN ('resolved', 'abandoned')
                GROUP BY pt.id
                ORDER BY pt.importance DESC, pt.name
                """
            )

            threads = []
            for row in cursor.fetchall():
                thread = dict(row)

                # Get characters involved
                cursor.execute(
                    """
                    SELECT c.id, c.identifier, c.name, cpt.involvement_role
                    FROM character_plot_threads cpt
                    JOIN characters c ON cpt.character_id = c.id
                    WHERE cpt.plot_thread_id = ?
                    """,
                    (thread["id"],),
                )
                thread["involved_characters"] = [dict(r) for r in cursor.fetchall()]

                threads.append(thread)

            return threads

    def get_relationship_dynamics_over_time(
        self, char1_id: int, char2_id: int
    ) -> List[Dict[str, Any]]:
        """
        Track how a relationship evolves through the story.

        Args:
                char1_id: First character ID
            char2_id: Second character ID

        Returns:
                List of relationship states over time
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Ensure proper ordering
            if char1_id > char2_id:
                char1_id, char2_id = char2_id, char1_id

            # Get base relationship
            cursor.execute(
                """
                SELECT * FROM character_relationships
                WHERE character1_id = ? AND character2_id = ?
                """,
                (char1_id, char2_id),
            )
            base_relationship = cursor.fetchone()

            if not base_relationship:
                return []

            # Track relationship mentions/developments in scenes
            cursor.execute(
                """
                SELECT s.id, s.scene_number, c.chapter_number, s.content
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                JOIN scene_entities se1 ON se1.scene_id = s.id
                JOIN scene_entities se2 ON se2.scene_id = s.id
                WHERE se1.entity_type = 'character' AND se1.entity_id = ?
                AND se2.entity_type = 'character' AND se2.entity_id = ?
                ORDER BY c.chapter_number, s.scene_number
                """,
                (char1_id, char2_id),
            )

            dynamics = []
            for row in cursor.fetchall():
                scene = dict(row)

                # Get character states at this scene
                state1 = self.db.get_character_state_at_scene(char1_id, scene["id"])
                state2 = self.db.get_character_state_at_scene(char2_id, scene["id"])

                dynamics.append(
                    {
                        "chapter": scene["chapter_number"],
                        "scene": scene["scene_number"],
                        "character1_state": state1,
                        "character2_state": state2,
                        "base_relationship": dict(base_relationship),
                    }
                )

            return dynamics

    def get_full_story(self) -> str:
        """
        Compile the full story from the database.

        Returns:
                The complete story as a formatted string
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get story metadata
            cursor.execute("SELECT * FROM story_config WHERE id = 1")
            story = cursor.fetchone()
            if not story:
                return ""

            story_text = []
            story_text.append(f"# {story['title']}")
            story_text.append(f"\nGenre: {story['genre']}")
            story_text.append(f"Tone: {story['tone']}")
            if story["author"]:
                story_text.append(f"In the style of: {story['author']}")
            story_text.append("\n---\n")

            # Get all chapters and scenes
            cursor.execute(
                """
                SELECT c.chapter_number, c.title as chapter_title, 
                        s.scene_number, s.content
                FROM chapters c
                LEFT JOIN scenes s ON s.chapter_id = c.id
                ORDER BY c.chapter_number, s.scene_number
                """
            )

            current_chapter = None
            for row in cursor.fetchall():
                if row["chapter_number"] != current_chapter:
                    current_chapter = row["chapter_number"]
                    story_text.append(
                        f"\n## Chapter {current_chapter}: {row['chapter_title']}\n"
                    )

                if row["content"]:
                    story_text.append(f"### Scene {row['scene_number']}\n")
                    story_text.append(row["content"])
                    story_text.append("\n")

            return "\n".join(story_text)
