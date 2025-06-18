"""
Database integration module for StoryCraft Agent.

This module provides the integration layer between the LangGraph workflow
and the database persistence layer, enabling automatic state saving during
story generation.
"""

# Standard library imports
import json
import os
from typing import Any, Dict, List, Optional, Set

# Local imports
from storyteller_lib.constants import NodeNames
from storyteller_lib.database import DatabaseStateAdapter, StoryDatabase
from storyteller_lib.exceptions import DatabaseError
from storyteller_lib.logger import get_logger
from storyteller_lib.models import StoryState

logger = get_logger(__name__)


class StoryDatabaseManager:
    """
    Manages database operations during story generation.
    
    This class handles automatic state persistence, providing methods to save
    state after each node execution and track changes incrementally.
    """
    
    def __init__(self, db_path: Optional[str] = None, enabled: bool = True):
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to the database file (defaults to story_database.db)
            enabled: Whether database operations are enabled
        """
        self.enabled = enabled
        self._db: Optional[StoryDatabase] = None
        self._adapter: Optional[DatabaseStateAdapter] = None
        self._db_path = db_path or os.environ.get('STORY_DATABASE_PATH', 'story_database.db')
        self._modified_entities: Set[str] = set()
        self._current_chapter_id: Optional[int] = None
        self._current_scene_id: Optional[int] = None
        self._character_id_map: Dict[str, int] = {}
        self._chapter_id_map: Dict[str, int] = {}
        if self.enabled:
            self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize database connection and adapter."""
        self._db = StoryDatabase(self._db_path)
        self._adapter = DatabaseStateAdapter(self._db)
        logger.info(f"Database initialized at {self._db_path}")
    
    def initialize_story_config(self, state: StoryState) -> None:
        """
        Initialize or update the story configuration.
        
        Args:
            state: Initial story state
        """
        if not self.enabled or not self._db:
            return
        
        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                # Insert or replace the single story config row
                cursor.execute("""
                    INSERT OR REPLACE INTO story_config 
                    (id, title, genre, tone, author, language, initial_idea, global_story)
                    VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"{state.get('tone', 'unknown').capitalize()} {state.get('genre', 'unknown').capitalize()} Story",
                    state.get('genre', 'unknown'),
                    state.get('tone', 'unknown'),
                    state.get('author', ''),
                    state.get('language', 'english'),
                    state.get('initial_idea', ''),
                    state.get('global_story', '')
                ))
                conn.commit()
            logger.info("Initialized story configuration")
            
            # Initialize context provider
            from storyteller_lib.story_context import initialize_context_provider
            initialize_context_provider()
            
        except Exception as e:
            logger.error(f"Failed to initialize story config: {e}")
    
    def save_node_state(self, node_name: str, state: StoryState) -> None:
        """
        Save state after a node execution.
        
        This method performs incremental updates based on the node type,
        only saving what has changed to avoid full state syncs.
        
        Args:
            node_name: Name of the node that just executed
            state: Current story state
        """
        logger.debug(f"save_node_state called for node: {node_name}")
        logger.debug(f"Database enabled: {self.enabled}, DB exists: {self._db is not None}")
        
        if not self.enabled or not self._db:
            logger.warning(f"Skipping save for {node_name}: enabled={self.enabled}, db={self._db is not None}")
            return
        
        try:
            # Map node names to save operations
            if node_name == NodeNames.INITIALIZE:
                self._save_initial_state(state)
            elif node_name == NodeNames.WORLDBUILDING:
                self._save_world_elements(state)
            elif node_name == NodeNames.CREATE_CHARACTERS:
                self._save_characters(state)
            # Plot threads are saved after scene reflection
            elif node_name == NodeNames.SCENE_REFLECTION:
                self._save_plot_threads(state)
            elif node_name == NodeNames.PLAN_CHAPTER:
                self._save_chapter(state)
            elif node_name in [NodeNames.SCENE_WRITING, NodeNames.SCENE_REVISION]:
                self._save_scene(state)
            elif node_name == NodeNames.CHARACTER_EVOLUTION:
                self._update_character_states(state)
            
            logger.debug(f"Saved state after {node_name}")
        except Exception as e:
            logger.error(f"Failed to save state after {node_name}: {e}")
    
    def _save_initial_state(self, state: StoryState) -> None:
        """Save initial story setup."""
        self.initialize_story_config(state)
        # Ensure context provider is initialized
        from storyteller_lib.story_context import get_context_provider, initialize_context_provider
        if not get_context_provider():
            initialize_context_provider()
    
    def _save_world_elements(self, state: StoryState) -> None:
        """Save world building elements."""
        world_elements = state.get('world_elements', {})
        
        # Check if world_elements is just a marker (stored_in_db: True)
        if isinstance(world_elements, dict) and world_elements.get('stored_in_db'):
            # Already saved directly by worldbuilding.py
            logger.debug("World elements already saved to database")
            return
        
        # Otherwise save them if they exist
        if isinstance(world_elements, dict):
            for category, elements in world_elements.items():
                if isinstance(elements, dict):
                    for key, value in elements.items():
                        self._db.create_world_element(
                            category=category,
                            element_key=key,
                            element_value=value
                        )
            
            # Also save locations if they exist in world elements
            if 'locations' in world_elements and isinstance(world_elements['locations'], dict):
                for loc_id, loc_data in world_elements['locations'].items():
                    if isinstance(loc_data, dict):
                        self._db.create_location(
                            identifier=loc_id,
                            name=loc_data.get('name', loc_id),
                            description=loc_data.get('description', ''),
                            location_type=loc_data.get('type', 'unknown'),
                            properties=loc_data.get('properties', {})
                        )
    
    def _save_characters(self, state: StoryState) -> None:
        """Save character profiles and relationships."""
        characters = state.get('characters', {})
        
        # First pass: Create all characters
        char_id_map = {}
        for char_id, char_data in characters.items():
            try:
                # Serialize any dict fields to JSON strings, ensure all are strings
                personality = char_data.get('personality', '')
                if isinstance(personality, dict):
                    personality = json.dumps(personality)
                elif personality is None:
                    personality = ''
                else:
                    personality = str(personality)
                
                backstory = char_data.get('backstory', '')
                if isinstance(backstory, dict):
                    backstory = json.dumps(backstory)
                elif backstory is None:
                    backstory = ''
                else:
                    backstory = str(backstory)
                
                role = char_data.get('role', '')
                if isinstance(role, dict):
                    role = json.dumps(role)
                elif role is None:
                    role = ''
                else:
                    role = str(role)
                
                # Debug logging
                logger.debug(f"Creating character {char_id} with:")
                logger.debug(f"  name: {char_data.get('name', char_id)} (type: {type(char_data.get('name', char_id))})")
                logger.debug(f"  role: {role} (type: {type(role)})")
                logger.debug(f"  backstory: {backstory[:100] if backstory else 'None'}... (type: {type(backstory)})")
                logger.debug(f"  personality: {personality[:100] if personality else 'None'}... (type: {type(personality)})")
                
                db_char_id = self._db.create_character(
                    identifier=char_id,
                    name=char_data.get('name', char_id),
                    role=role,
                    backstory=backstory,
                    personality=personality
                )
                char_id_map[char_id] = db_char_id
            except Exception as e:
                # Character might already exist
                logger.debug(f"Character {char_id} may already exist: {e}")
                # Try to get existing character ID
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM characters WHERE identifier = ?",
                        (char_id,)
                    )
                    result = cursor.fetchone()
                    if result:
                        char_id_map[char_id] = result['id']
        
        # Second pass: Create relationships
        for char_id, char_data in characters.items():
            if char_id in char_id_map and 'relationships' in char_data:
                for other_char, rel_type in char_data['relationships'].items():
                    if other_char in char_id_map:
                        self._db.create_relationship(
                            char1_id=char_id_map[char_id],
                            char2_id=char_id_map[other_char],
                            rel_type=rel_type
                        )
    
    def _save_plot_threads(self, state: StoryState) -> None:
        """Save plot threads."""
        plot_threads = state.get('plot_threads', {})
        
        for thread_name, thread_data in plot_threads.items():
            # Skip if it's just a marker
            if isinstance(thread_data, dict) and thread_data.get('stored_in_db'):
                continue
                
            # Handle the PlotThread data structure
            if isinstance(thread_data, dict):
                try:
                    # First check if thread already exists
                    with self._db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM plot_threads WHERE name = ?",
                            (thread_name,)
                        )
                        result = cursor.fetchone()
                        
                        if result:
                            # Update existing thread
                            self._db.update_plot_thread_status(
                                result['id'],
                                thread_data.get('status', 'introduced')
                            )
                        else:
                            # Create new thread
                            self._db.create_plot_thread(
                                name=thread_name,
                                description=thread_data.get('description', ''),
                                thread_type=thread_data.get('importance', 'minor'),  # PlotThread uses 'importance' not 'thread_type'
                                importance=thread_data.get('importance', 'minor'),
                                status=thread_data.get('status', 'introduced')
                            )
                except Exception as e:
                    logger.error(f"Failed to save plot thread {thread_name}: {e}")
    
    def _save_chapter(self, state: StoryState) -> None:
        """Save current chapter."""
        current_chapter = state.get('current_chapter', '')
        if not current_chapter:
            return
        
        chapters = state.get('chapters', {})
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
                    "SELECT id FROM chapters WHERE chapter_number = ?",
                    (chapter_num,)
                )
                result = cursor.fetchone()
                
                if result:
                    # Chapter already exists, just update the ID
                    self._current_chapter_id = result['id']
                else:
                    # Create new chapter
                    try:
                        self._current_chapter_id = self._db.create_chapter(
                            chapter_num=chapter_num,
                            title=chapter_data.get('title', ''),
                            outline=chapter_data.get('outline', '')
                        )
                    except Exception as e:
                        logger.error(f"Failed to create chapter {current_chapter}: {e}")
    
    def _save_scene(self, state: StoryState) -> None:
        """Save current scene and its entities."""
        current_chapter = state.get('current_chapter', '')
        current_scene = state.get('current_scene', '')
        
        if not current_chapter or not current_scene or not self._current_chapter_id:
            return
        
        chapters = state.get('chapters', {})
        if current_chapter in chapters and 'scenes' in chapters[current_chapter]:
            scenes = chapters[current_chapter]['scenes']
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
                        outline=scene_data.get('description', ''),  # Use 'description' from chapter planning
                        content=scene_data.get('content', '')
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
                            (self._current_chapter_id, scene_num)
                        )
                        result = cursor.fetchone()
                        if result:
                            self._current_scene_id = result['id']
    
    def _save_scene_entities(self, state: StoryState, scene_data: Dict[str, Any]) -> None:
        """Save entities involved in the current scene."""
        if not self._current_scene_id:
            return
        
        # Get scene content for entity detection
        content = scene_data.get('content', '')
        
        # Detect and save character involvement
        characters = state.get('characters', {})
        for char_id, char_data in characters.items():
            char_name = char_data.get('name', '')
            if char_name and char_name in content:
                # Get character database ID
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM characters WHERE identifier = ?",
                        (char_id,)
                    )
                    result = cursor.fetchone()
                    if result:
                        self._db.add_entity_to_scene(
                            self._current_scene_id,
                            'character',
                            result['id'],
                            'present'
                        )
        
        # Save location involvement if mentioned
        world_elements = state.get('world_elements', {})
        if 'locations' in world_elements:
            for loc_id, loc_data in world_elements['locations'].items():
                if isinstance(loc_data, dict):
                    loc_name = loc_data.get('name', '')
                    if loc_name and loc_name in content:
                        # Get location database ID
                        with self._db._get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "SELECT id FROM locations WHERE identifier = ?",
                                (loc_id,)
                            )
                            result = cursor.fetchone()
                            if result:
                                self._db.add_entity_to_scene(
                                    self._current_scene_id,
                                    'location',
                                    result['id'],
                                    'present'
                                )
    
    def _update_character_states(self, state: StoryState) -> None:
        """Update character states for the current scene."""
        if not self._current_scene_id:
            return
        
        characters = state.get('characters', {})
        for char_id, char_data in characters.items():
            # Get character database ID
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM characters WHERE identifier = ?",
                    (char_id,)
                )
                result = cursor.fetchone()
                if result:
                    char_db_id = result['id']
                    
                    # Build state update
                    state_update = {}
                    
                    # Check for evolution in current scene
                    evolution = char_data.get('evolution', [])
                    if evolution:
                        # Get the latest evolution entry
                        latest_evolution = evolution[-1]
                        state_update['evolution_notes'] = latest_evolution
                    
                    # Note: Character knowledge is now tracked via character_knowledge table
                    # The old fact fields have been removed from CharacterProfile
                    
                    if state_update:
                        self._db.update_character_state(
                            character_id=char_db_id,
                            scene_id=self._current_scene_id,
                            state=state_update
                        )
    
    def get_context_for_chapter(self, chapter_num: int) -> Dict[str, Any]:
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
                    "SELECT id FROM chapters WHERE chapter_number = ?",
                    (chapter_num,)
                )
                result = cursor.fetchone()
                if result:
                    return self._db.get_chapter_start_context(result['id'])
        except Exception as e:
            logger.error(f"Failed to get chapter context: {e}")
        
        return {}
    
    def get_context_for_scene(self, chapter_num: int, scene_num: int) -> Dict[str, Any]:
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
                    (chapter_num, scene_num)
                )
                result = cursor.fetchone()
                if result:
                    return self._db.get_scene_context(result['id'])
        except Exception as e:
            logger.error(f"Failed to get scene context: {e}")
        
        return {}
    
    def load_story(self) -> Optional[StoryState]:
        """
        Load the story from the database.
        
        Returns:
            Story state if successful, None otherwise
        """
        if not self._adapter:
            return None
        
        try:
            return self._adapter.load_from_database()
        except Exception as e:
            logger.error(f"Failed to load story: {e}")
            return None
    
    def update_character(self, character_id: str, changes: Dict[str, Any]) -> List[Dict[str, Any]]:
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
                    "SELECT id FROM characters WHERE identifier = ?",
                    (character_id,)
                )
                result = cursor.fetchone()
                if not result:
                    logger.error(f"Character {character_id} not found")
                    return []
                
                char_db_id = result['id']
            
            # Update character in database
            update_fields = []
            update_values = []
            
            for field in ['name', 'role', 'backstory', 'personality']:
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
            from storyteller_lib.story_analysis import StoryAnalyzer
            analyzer = StoryAnalyzer(self._db)
            
            # Determine change type
            change_type = 'name' if 'name' in changes else 'backstory' if 'backstory' in changes else 'minor'
            
            return analyzer.find_revision_candidates(
                change_type, 'character', char_db_id
            )
            
        except Exception as e:
            logger.error(f"Failed to update character: {e}")
            return []
    
    def update_plot_thread(self, thread_name: str, changes: Dict[str, Any]) -> List[Dict[str, Any]]:
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
                    "SELECT id FROM plot_threads WHERE name = ?",
                    (thread_name,)
                )
                result = cursor.fetchone()
                if not result:
                    logger.error(f"Plot thread {thread_name} not found")
                    return []
                
                thread_id = result['id']
            
            # Update plot thread
            update_fields = []
            update_values = []
            
            for field in ['description', 'thread_type', 'importance', 'status']:
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
            from storyteller_lib.story_analysis import StoryAnalyzer
            analyzer = StoryAnalyzer(self._db)
            dependencies = analyzer.find_plot_dependencies(thread_id)
            
            affected_scenes = []
            for scene in dependencies['dependencies']['key_scenes']:
                affected_scenes.append({
                    'scene_id': scene['id'],
                    'chapter_id': scene.get('chapter_id'),
                    'chapter_number': scene['chapter_number'],
                    'scene_number': scene['scene_number'],
                    'involvement': 'plot_development',
                    'priority': 10 if changes.get('status') == 'resolved' else 5,
                    'reason': f"Plot thread '{thread_name}' was modified"
                })
            
            return affected_scenes
            
        except Exception as e:
            logger.error(f"Failed to update plot thread: {e}")
            return []
    
    def update_world_element(self, category: str, element_key: str, 
                           element_value: Any) -> List[Dict[str, Any]]:
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
            self._db.create_world_element(
                category, element_key, element_value
            )
            logger.info(f"Updated world element {category}.{element_key}")
            
            # For major world elements, all scenes might be affected
            # For minor ones, we'd need more sophisticated detection
            major_categories = ['magic', 'technology', 'politics', 'geography']
            
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
                    affected_scenes.append({
                        'scene_id': row['id'],
                        'chapter_id': row['chapter_id'],
                        'chapter_number': row['chapter_number'],
                        'scene_number': row['scene_number'],
                        'involvement': 'world_element',
                        'priority': 3,
                        'reason': f"World element '{category}.{element_key}' was modified"
                    })
            
            return affected_scenes
            
        except Exception as e:
            logger.error(f"Failed to update world element: {e}")
            return []
    
    def get_revision_candidates(self, change_type: str, entity_type: str, 
                               entity_id: str) -> List[Dict[str, Any]]:
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
            if entity_type == 'character':
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM characters WHERE identifier = ?",
                        (entity_id,)
                    )
                    result = cursor.fetchone()
                    if result:
                        db_entity_id = result['id']
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
            from storyteller_lib.story_analysis import StoryAnalyzer
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
            logger.info(f"update_global_story called with outline of length {len(global_story)}")
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
                        (global_story, story_title)
                    )
                    logger.info(f"Updated existing story_config with title: '{story_title}'")
                else:
                    # Create the row with minimal data
                    cursor.execute(
                        """INSERT INTO story_config (id, title, genre, tone, global_story) 
                           VALUES (1, ?, 'unknown', 'unknown', ?)""",
                        (story_title, global_story)
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
                
            logger.info(f"Updated global story (length: {len(global_story)} chars) with title: {story_title}")
        except Exception as e:
            logger.error(f"Failed to update global story: {e}")
            raise
    
    def _extract_title_from_outline(self, global_story: str) -> str:
        """Extract the story title from the global story outline."""
        if not global_story:
            logger.warning("No global story provided for title extraction")
            return "Untitled Story"
        
        logger.debug(f"Extracting title from outline (first 500 chars): {global_story[:500]}...")
        
        # Look for lines containing "Title:" or "Titel:" (for German)
        lines = global_story.split('\n')
        for i, line in enumerate(lines[:30]):  # Check first 30 lines
            if 'title:' in line.lower() or 'titel:' in line.lower():
                logger.debug(f"Found title line at position {i}: {line}")
                # Extract the title after the colon
                parts = line.split(':', 1)
                if len(parts) > 1 and parts[1].strip():
                    # Title is on the same line
                    title = parts[1].strip()
                else:
                    # Title might be on the next line
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        # Skip separator lines
                        if next_line and not next_line.startswith('---') and not next_line.startswith('==='):
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
                while '**' in title:
                    title = title.replace('**', '')
                # Remove various quote types
                title = title.strip('"').strip("'").strip('*').strip('„').strip('"').strip('»').strip('«')
                # Final strip to remove any remaining whitespace
                title = title.strip()
                if title and title != '---' and title != '===':
                    logger.info(f"Successfully extracted title: '{title}'")
                    return title
        
        # If no explicit title line, try to get the first non-empty line
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('*'):
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
    def save_worldbuilding(self, world_elements: Dict[str, Any]) -> None:
        """Save worldbuilding elements to database."""
        if not self.enabled or not self._db:
            return
        
        try:
            for category, elements in world_elements.items():
                if category == "stored_in_db":  # Skip our marker
                    continue
                if isinstance(elements, dict):
                    for key, value in elements.items():
                        self._db.create_world_element(
                            category=category,
                            element_key=key,
                            element_value=value
                        )
            logger.info("Saved worldbuilding elements")
        except Exception as e:
            logger.error(f"Failed to save worldbuilding: {e}")
            raise
    
    def save_character(self, char_id: str, char_data: Dict[str, Any]) -> None:
        """Save a character to database."""
        if not self.enabled or not self._db:
            return
        
        try:
            # Serialize any dict fields to JSON strings, ensure all are strings
            personality = char_data.get('personality', '')
            if isinstance(personality, dict):
                personality = json.dumps(personality)
            elif personality is None:
                personality = ''
            else:
                personality = str(personality)
            
            backstory = char_data.get('backstory', '')
            if isinstance(backstory, dict):
                backstory = json.dumps(backstory)
            elif backstory is None:
                backstory = ''
            else:
                backstory = str(backstory)
            
            role = char_data.get('role', '')
            if isinstance(role, dict):
                role = json.dumps(role)
            elif role is None:
                role = ''
            else:
                role = str(role)
            
            # Check if character already exists
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM characters WHERE identifier = ?",
                    (char_id,)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing character
                    db_char_id = existing['id']
                    cursor.execute(
                        """UPDATE characters 
                           SET name = ?, role = ?, backstory = ?, personality = ?
                           WHERE id = ?""",
                        (char_data.get('name', char_id), role, backstory, personality, db_char_id)
                    )
                    conn.commit()
                    logger.info(f"Updated existing character {char_id}")
                else:
                    # Create new character
                    db_char_id = self._db.create_character(
                        identifier=char_id,
                        name=char_data.get('name', char_id),
                        role=role,
                        backstory=backstory,
                        personality=personality
                    )
                    logger.info(f"Created new character {char_id}")
            
            # Store character ID mapping
            self._character_id_map[char_id] = db_char_id
            
            # Save relationships if they exist
            if 'relationships' in char_data:
                for other_char, rel_data in char_data['relationships'].items():
                    if other_char in self._character_id_map:
                        rel_type = rel_data if isinstance(rel_data, str) else rel_data.get('type', 'unknown')
                        other_char_id = self._character_id_map[other_char]
                        
                        # Check if relationship already exists
                        with self._db._get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                """SELECT id FROM character_relationships 
                                   WHERE (character1_id = ? AND character2_id = ?) 
                                      OR (character1_id = ? AND character2_id = ?)""",
                                (db_char_id, other_char_id, other_char_id, db_char_id)
                            )
                            existing_rel = cursor.fetchone()
                            
                            if not existing_rel:
                                self._db.create_relationship(
                                    char1_id=db_char_id,
                                    char2_id=other_char_id,
                                    rel_type=rel_type
                                )
            
            logger.info(f"Saved character {char_id}")
        except Exception as e:
            logger.error(f"Failed to save character {char_id}: {e}")
            raise
    
    def save_chapter_outline(self, chapter_num: int, chapter_data: Dict[str, Any]) -> None:
        """Save chapter outline to database."""
        if not self.enabled or not self._db:
            return
        
        try:
            # First check if chapter already exists
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM chapters WHERE chapter_number = ?",
                    (chapter_num,)
                )
                result = cursor.fetchone()
                
                if result:
                    # Chapter exists, update it
                    chapter_id = result['id']
                    cursor.execute(
                        "UPDATE chapters SET title = ?, outline = ? WHERE id = ?",
                        (chapter_data.get('title', f'Chapter {chapter_num}'),
                         chapter_data.get('outline', ''),
                         chapter_id)
                    )
                    conn.commit()
                    logger.info(f"Updated existing chapter {chapter_num} outline")
                else:
                    # Create new chapter
                    chapter_id = self._db.create_chapter(
                        chapter_num=chapter_num,
                        title=chapter_data.get('title', f'Chapter {chapter_num}'),
                        outline=chapter_data.get('outline', '')
                    )
                    logger.info(f"Saved new chapter {chapter_num} outline")
            
            # Store chapter ID mapping
            self._chapter_id_map[str(chapter_num)] = chapter_id
            
            # Save scene descriptions from chapter planning
            scenes = chapter_data.get('scenes', {})
            for scene_num_str, scene_data in scenes.items():
                try:
                    scene_num = int(scene_num_str)
                    scene_description = scene_data.get('description', '')
                    scene_type = scene_data.get('scene_type', 'exploration')  # Get scene_type with default
                    
                    if scene_description:
                        # Check if scene already exists
                        with self._db._get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "SELECT id FROM scenes WHERE chapter_id = ? AND scene_number = ?",
                                (chapter_id, scene_num)
                            )
                            existing_scene = cursor.fetchone()
                            
                            if existing_scene:
                                # Update existing scene with description and type
                                cursor.execute(
                                    "UPDATE scenes SET description = ?, scene_type = ? WHERE id = ?",
                                    (scene_description, scene_type, existing_scene['id'])
                                )
                            else:
                                # Create scene with description and type
                                cursor.execute(
                                    "INSERT INTO scenes (chapter_id, scene_number, description, scene_type) VALUES (?, ?, ?, ?)",
                                    (chapter_id, scene_num, scene_description, scene_type)
                                )
                            conn.commit()
                            logger.info(f"Saved scene {scene_num} description (type: {scene_type}) for chapter {chapter_num}")
                except (ValueError, KeyError) as e:
                    logger.warning(f"Could not save scene {scene_num_str}: {e}")
            
        except Exception as e:
            logger.error(f"Failed to save chapter {chapter_num}: {e}")
            raise
    
    def save_scene_content(self, chapter_num: int, scene_num: int, content: str) -> None:
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
                        (chapter_num,)
                    )
                    result = cursor.fetchone()
                    if result:
                        chapter_id = result['id']
                        self._chapter_id_map[str(chapter_num)] = chapter_id
            
            if chapter_id:
                # Check if scene already exists
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM scenes WHERE chapter_id = ? AND scene_number = ?",
                        (chapter_id, scene_num)
                    )
                    existing_scene = cursor.fetchone()
                    
                    if existing_scene:
                        # Update existing scene
                        cursor.execute(
                            "UPDATE scenes SET content = ? WHERE id = ?",
                            (content, existing_scene['id'])
                        )
                        conn.commit()
                        logger.info(f"Updated scene {scene_num} of chapter {chapter_num}")
                    else:
                        # Create new scene
                        scene_id = self._db.create_scene(
                            chapter_id=chapter_id,
                            scene_num=scene_num,
                            outline='',  # Can be added later
                            content=content
                        )
                        logger.info(f"Created scene {scene_num} of chapter {chapter_num}")
            else:
                logger.warning(f"Could not find chapter {chapter_num} to save scene {scene_num}")
        
        except Exception as e:
            logger.error(f"Failed to save scene {scene_num} of chapter {chapter_num}: {e}")
            raise
    
    def track_plot_progression(self, progression_key: str, chapter_num: int, scene_num: int, description: str = "") -> bool:
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
                cursor.execute("""
                    INSERT INTO plot_progressions 
                    (progression_key, chapter_number, scene_number, description)
                    VALUES (?, ?, ?, ?)
                """, (progression_key, chapter_num, scene_num, description))
                conn.commit()
                logger.info(f"Tracked plot progression: {progression_key} at Ch{chapter_num}/Sc{scene_num}")
                return True
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                logger.warning(f"Plot progression already exists: {progression_key}")
                return False
            logger.error(f"Failed to track plot progression: {e}")
            return False
    
    def get_plot_progressions(self) -> List[Dict[str, Any]]:
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
                cursor.execute("""
                    SELECT progression_key, chapter_number, scene_number, description
                    FROM plot_progressions
                    ORDER BY chapter_number, scene_number
                """)
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
                    (progression_key,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Failed to check plot progression: {e}")
            return False
    
    def get_scene_id(self, chapter_num: int, scene_num: int) -> Optional[int]:
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
                        (chapter_num,)
                    )
                    result = cursor.fetchone()
                    if result:
                        chapter_id = result['id']
            
            if chapter_id:
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM scenes WHERE chapter_id = ? AND scene_number = ?",
                        (chapter_id, scene_num)
                    )
                    result = cursor.fetchone()
                    return result['id'] if result else None
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get scene ID: {e}")
            return None
    
    def get_scene_content(self, chapter_num: int, scene_num: int) -> Optional[str]:
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
                        (chapter_num,)
                    )
                    result = cursor.fetchone()
                    if result:
                        chapter_id = result['id']
            
            if chapter_id:
                with self._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT content FROM scenes WHERE chapter_id = ? AND scene_number = ?",
                        (chapter_id, scene_num)
                    )
                    result = cursor.fetchone()
                    if result:
                        return result['content']
            
            return None
        
        except Exception as e:
            logger.error(f"Failed to get scene {scene_num} of chapter {chapter_num}: {e}")
            return None
    
    def create_memory(self, key: str, value: str, namespace: str = "storyteller") -> None:
        """Create a new memory entry."""
        if not self.enabled or not self._db:
            return
            
        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT OR REPLACE INTO memories (key, value, namespace) 
                       VALUES (?, ?, ?)""",
                    (key, value, namespace)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to create memory {key}: {e}")
            raise
    
    def update_memory(self, key: str, value: str, namespace: str = "storyteller") -> None:
        """Update an existing memory entry."""
        if not self.enabled or not self._db:
            return
            
        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """UPDATE memories SET value = ?, updated_at = CURRENT_TIMESTAMP 
                       WHERE key = ? AND namespace = ?""",
                    (value, key, namespace)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to update memory {key}: {e}")
            raise
    
    def delete_memory(self, key: str, namespace: str = "storyteller") -> None:
        """Delete a memory entry."""
        if not self.enabled or not self._db:
            return
            
        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM memories WHERE key = ? AND namespace = ?",
                    (key, namespace)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to delete memory {key}: {e}")
            raise
    
    def get_memory(self, key: str, namespace: str = "storyteller") -> Optional[Dict[str, Any]]:
        """Get a specific memory by key."""
        if not self.enabled or not self._db:
            return None
            
        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT key, value, namespace FROM memories WHERE key = ? AND namespace = ?",
                    (key, namespace)
                )
                result = cursor.fetchone()
                if result:
                    return dict(result)
                return None
        except Exception as e:
            logger.error(f"Failed to get memory {key}: {e}")
            return None
    
    def search_memories(self, query: str, namespace: str = "storyteller") -> List[Dict[str, Any]]:
        """Search for memories containing the query string."""
        if not self.enabled or not self._db:
            return []
            
        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                # Simple text search - checks if query is in key or value
                cursor.execute(
                    """SELECT key, value, namespace FROM memories 
                       WHERE namespace = ? AND (key LIKE ? OR value LIKE ?)
                       ORDER BY updated_at DESC""",
                    (namespace, f'%{query}%', f'%{query}%')
                )
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to search memories for '{query}': {e}")
            return []
    
    def close(self) -> None:
        """Close database connections."""
        # SQLite connections are closed automatically
        self._db = None
        self._adapter = None
        logger.debug("Database manager closed")


# Global instance for easy access
_db_manager: Optional[StoryDatabaseManager] = None


def get_db_manager() -> Optional[StoryDatabaseManager]:
    """Get the global database manager instance."""
    return _db_manager


def initialize_db_manager(db_path: Optional[str] = None, enabled: bool = True) -> StoryDatabaseManager:
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