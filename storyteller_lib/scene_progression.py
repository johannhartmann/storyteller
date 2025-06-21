"""Scene progression tracking for StoryCraft Agent.

This module tracks what has happened in previous scenes to prevent repetition
and ensure proper story progression.
"""

from typing import Dict, List, Set, Any, Optional
from datetime import datetime
from storyteller_lib.logger import get_logger
from storyteller_lib.database_integration import get_db_manager
from storyteller_lib.config import DEFAULT_LANGUAGE

logger = get_logger(__name__)


class SceneProgressionTracker:
    """Tracks story progression to prevent repetition and ensure variety."""
    
    def __init__(self):
        self.db_manager = get_db_manager()
        self._ensure_tables_exist()
    
    def _ensure_tables_exist(self):
        """Ensure progression tracking tables exist in the database."""
        if not self.db_manager or not self.db_manager._db:
            logger.error("Database manager not available for progression tracking")
            return
            
        with self.db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            
            # Table for tracking used phrases and descriptions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS used_phrases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter_number INTEGER NOT NULL,
                    scene_number INTEGER NOT NULL,
                    phrase TEXT NOT NULL,
                    phrase_type TEXT NOT NULL,  -- 'description', 'metaphor', 'action'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(phrase, phrase_type)
                )
            """)
            
            # Table for tracking scene structures with comprehensive data
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scene_structures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter_number INTEGER NOT NULL,
                    scene_number INTEGER NOT NULL,
                    structure_pattern TEXT NOT NULL,  -- e.g., 'maintenance->anomaly->vision->dismissal'
                    scene_type TEXT NOT NULL,  -- 'action', 'dialogue', 'exploration', 'revelation'
                    opening_type TEXT,  -- How scene opens: action, dialogue, description, internal_thought
                    main_events TEXT,  -- JSON array of main events
                    climax_type TEXT,  -- Type of climax: revelation, action, emotional, cliffhanger
                    resolution TEXT,  -- How scene resolves: complete, partial, cliffhanger
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(chapter_number, scene_number)
                )
            """)
            
            # Table for tracking character knowledge and revelations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS character_knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_name TEXT NOT NULL,
                    knowledge_item TEXT NOT NULL,
                    chapter_number INTEGER NOT NULL,
                    scene_number INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(character_name, knowledge_item)
                )
            """)
            
            # Table for tracking specific events
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS story_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter_number INTEGER NOT NULL,
                    scene_number INTEGER NOT NULL,
                    event_type TEXT NOT NULL,  -- 'vision', 'combat', 'discovery', 'dialogue', 'travel'
                    event_description TEXT NOT NULL,
                    participants TEXT,  -- JSON list of character names
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def get_used_phrases(self, phrase_type: Optional[str] = None) -> Set[str]:
        """Get all phrases that have been used in the story.
        
        Args:
            phrase_type: Optional filter by phrase type
            
        Returns:
            Set of used phrases
        """
        if not self.db_manager or not self.db_manager._db:
            return set()
            
        with self.db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            if phrase_type:
                cursor.execute(
                    "SELECT DISTINCT phrase FROM used_phrases WHERE phrase_type = ?",
                    (phrase_type,)
                )
            else:
                cursor.execute("SELECT DISTINCT phrase FROM used_phrases")
            
            return {row['phrase'] for row in cursor.fetchall()}
    
    def add_used_phrases(self, chapter: int, scene: int, phrases: Dict[str, List[str]]):
        """Add phrases that have been used in a scene.
        
        Args:
            chapter: Chapter number
            scene: Scene number
            phrases: Dictionary mapping phrase types to lists of phrases
        """
        if not self.db_manager or not self.db_manager._db:
            return
            
        with self.db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            for phrase_type, phrase_list in phrases.items():
                for phrase in phrase_list:
                    try:
                        cursor.execute("""
                            INSERT INTO used_phrases (chapter_number, scene_number, phrase, phrase_type)
                            VALUES (?, ?, ?, ?)
                        """, (chapter, scene, phrase.lower().strip(), phrase_type))
                    except Exception as e:
                        # Ignore duplicates
                        pass
            conn.commit()
    
    def get_scene_structures(self) -> List[str]:
        """Get all scene structure patterns used so far.
        
        Returns:
            List of structure patterns
        """
        if not self.db_manager or not self.db_manager._db:
            return []
            
        with self.db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT structure_pattern FROM scene_structures ORDER BY id")
            return [row['structure_pattern'] for row in cursor.fetchall()]
    
    def get_scene_structures_detailed(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get detailed scene structure data for recent scenes.
        
        Args:
            limit: Maximum number of scenes to return
            
        Returns:
            List of scene structure dictionaries with full analysis data
        """
        if not self.db_manager or not self.db_manager._db:
            return []
            
        import json
        
        with self.db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT chapter_number, scene_number, structure_pattern, scene_type,
                       opening_type, main_events, climax_type, resolution
                FROM scene_structures 
                ORDER BY chapter_number DESC, scene_number DESC
                LIMIT ?
            """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                scene_data = {
                    'chapter': row['chapter_number'],
                    'scene': row['scene_number'],
                    'structure_pattern': row['structure_pattern'],
                    'scene_type': row['scene_type'],
                    'opening_type': row['opening_type'],
                    'climax_type': row['climax_type'],
                    'resolution': row['resolution']
                }
                
                # Parse JSON main_events if available
                if row['main_events']:
                    try:
                        scene_data['main_events'] = json.loads(row['main_events'])
                    except:
                        scene_data['main_events'] = []
                else:
                    scene_data['main_events'] = []
                
                results.append(scene_data)
            
            return results
    
    def add_scene_structure(self, chapter: int, scene: int, pattern: str, scene_type: str):
        """Record a scene's structure pattern (legacy method for compatibility).
        
        Args:
            chapter: Chapter number
            scene: Scene number
            pattern: Structure pattern (e.g., 'maintenance->anomaly->vision')
            scene_type: Type of scene (action, dialogue, etc.)
        """
        if not self.db_manager or not self.db_manager._db:
            return
            
        with self.db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO scene_structures (chapter_number, scene_number, structure_pattern, scene_type)
                VALUES (?, ?, ?, ?)
            """, (chapter, scene, pattern, scene_type))
            conn.commit()
    
    def add_scene_structure_analysis(self, chapter: int, scene: int, analysis):
        """Record complete scene structure analysis.
        
        Args:
            chapter: Chapter number
            scene: Scene number
            analysis: SceneStructureAnalysis object with full structure data
        """
        if not self.db_manager or not self.db_manager._db:
            return
            
        import json
        
        with self.db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO scene_structures 
                (chapter_number, scene_number, structure_pattern, scene_type, 
                 opening_type, main_events, climax_type, resolution)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chapter, 
                scene, 
                analysis.structure_pattern,
                'unknown',  # We'll update this separately if needed
                analysis.opening_type,
                json.dumps(analysis.main_events),
                analysis.climax_type,
                analysis.resolution
            ))
            conn.commit()
    
    def get_character_knowledge(self, character_name: str) -> Set[str]:
        """Get what a character knows at this point in the story.
        
        Args:
            character_name: Name of the character
            
        Returns:
            Set of knowledge items
        """
        if not self.db_manager or not self.db_manager._db:
            return set()
            
        with self.db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT knowledge_item FROM character_knowledge WHERE character_name = ?",
                (character_name.lower(),)
            )
            return {row['knowledge_item'] for row in cursor.fetchall()}
    
    def add_character_knowledge(self, character_name: str, knowledge: str, chapter: int, scene: int):
        """Record something a character has learned.
        
        Args:
            character_name: Name of the character
            knowledge: What they learned
            chapter: Chapter number
            scene: Scene number
        """
        if not self.db_manager or not self.db_manager._db:
            return
            
        with self.db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO character_knowledge (character_name, knowledge_item, chapter_number, scene_number)
                    VALUES (?, ?, ?, ?)
                """, (character_name.lower(), knowledge, chapter, scene))
                conn.commit()
            except Exception as e:
                # Ignore if character already knows this
                pass
    
    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent story events.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        if not self.db_manager or not self.db_manager._db:
            return []
            
        with self.db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM story_events 
                ORDER BY chapter_number DESC, scene_number DESC 
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def add_story_event(self, chapter: int, scene: int, event_type: str, 
                       description: str, participants: List[str]):
        """Record a story event.
        
        Args:
            chapter: Chapter number
            scene: Scene number
            event_type: Type of event
            description: Brief description of what happened
            participants: List of character names involved
        """
        if not self.db_manager or not self.db_manager._db:
            return
            
        import json
        with self.db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO story_events (chapter_number, scene_number, event_type, event_description, participants)
                VALUES (?, ?, ?, ?, ?)
            """, (chapter, scene, event_type, description, json.dumps(participants)))
            conn.commit()
    
    def get_scene_variety_report(self, chapter: int) -> Dict[str, Any]:
        """Get a report on scene variety within a chapter.
        
        Args:
            chapter: Chapter number
            
        Returns:
            Dictionary with variety metrics
        """
        if not self.db_manager or not self.db_manager._db:
            return {}
            
        with self.db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get scene types in this chapter
            cursor.execute("""
                SELECT scene_type, COUNT(*) as count 
                FROM scene_structures 
                WHERE chapter_number = ? 
                GROUP BY scene_type
            """, (chapter,))
            scene_types = {row['scene_type']: row['count'] for row in cursor.fetchall()}
            
            # Get event types in this chapter
            cursor.execute("""
                SELECT event_type, COUNT(*) as count 
                FROM story_events 
                WHERE chapter_number = ? 
                GROUP BY event_type
            """, (chapter,))
            event_types = {row['event_type']: row['count'] for row in cursor.fetchall()}
            
            # Count repeated structures
            cursor.execute("""
                SELECT structure_pattern, COUNT(*) as count 
                FROM scene_structures 
                WHERE chapter_number = ? 
                GROUP BY structure_pattern 
                HAVING count > 1
            """, (chapter,))
            repeated_structures = [(row['structure_pattern'], row['count']) for row in cursor.fetchall()]
            
            return {
                'scene_types': scene_types,
                'event_types': event_types,
                'repeated_structures': repeated_structures,
                'total_scenes': sum(scene_types.values())
            }
    
    def extract_phrases_from_content(self, content: str, language: str = DEFAULT_LANGUAGE) -> Dict[str, List[str]]:
        """Extract notable phrases from scene content for tracking using LLM.
        
        Args:
            content: Scene content text
            language: The language of the content
            
        Returns:
            Dictionary of phrase types to lists of phrases
        """
        from storyteller_lib.config import llm
        from langchain_core.messages import HumanMessage
        from pydantic import BaseModel, Field
        from storyteller_lib.prompt_templates import render_prompt
        
        class ExtractedPhrases(BaseModel):
            """Phrases extracted from scene content."""
            descriptive_phrases: List[str] = Field(
                description="Notable descriptive phrases that might become repetitive if overused"
            )
            metaphors: List[str] = Field(
                description="Metaphors and similes used"
            )
            character_actions: List[str] = Field(
                description="Specific character actions or gestures"
            )
            
        # Use full scene content for comprehensive phrase extraction
        # This ensures we catch repetitive phrases throughout the entire scene
        
        # Render the phrase extraction prompt
        prompt = render_prompt(
            'phrase_extraction',
            language=language,
            content_sample=content  # Using full content, not just a sample
        )

        try:
            structured_llm = llm.with_structured_output(ExtractedPhrases)
            result = structured_llm.invoke(prompt)
            
            return {
                'description': result.descriptive_phrases[:10],
                'metaphor': result.metaphors[:10],
                'action': result.character_actions[:10]
            }
        except Exception as e:
            logger.error(f"Failed to extract phrases: {e}")
            # Return empty lists on failure
            return {
                'description': [],
                'metaphor': [],
                'action': []
            }