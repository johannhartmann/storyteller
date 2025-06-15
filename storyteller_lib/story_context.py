"""
Story Context Module - Provides context-aware information during story generation.

This module integrates database queries into the story generation process,
ensuring each node has access to relevant historical information and dependencies.
"""

# Standard library imports
from typing import Any, Dict, List, Optional, Set, Tuple

# Local imports
from storyteller_lib.database import StoryDatabase
from storyteller_lib.database_integration import get_db_manager
from storyteller_lib.logger import get_logger
from storyteller_lib.models import StoryState

logger = get_logger(__name__)


class StoryContextProvider:
    """
    Provides context-aware information to story generation nodes.
    
    This class wraps database queries to provide relevant context during
    story generation, ensuring consistency and continuity.
    """
    
    def __init__(self, story_id: Optional[int] = None):
        """
        Initialize the context provider.
        
        Args:
            story_id: Optional story ID for database queries
        """
        self.story_id = story_id
        self.db_manager = get_db_manager()
        self.db = self.db_manager._db if self.db_manager else None
        self._context_cache = {}
    
    def get_character_context(self, character_id: str, chapter_num: int, 
                            scene_num: int) -> Dict[str, Any]:
        """
        Get comprehensive context for a character at a specific point in the story.
        
        Used by scene writing and character evolution nodes.
        
        Args:
            character_id: Character identifier (e.g., 'hero', 'mentor')
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
                    (self.story_id, character_id)
                )
                result = cursor.fetchone()
                if not result:
                    return {}
                
                char_db_id = result['id']
            
            # Get character's state in previous scene
            context = {
                'identifier': character_id,
                'current_location': None,
                'emotional_state': None,
                'known_facts': [],
                'relationships': {},
                'recent_events': []
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
                    (self.story_id, chapter_num, chapter_num, scene_num)
                )
                recent_scenes = cursor.fetchall()
            
            # Get state from most recent appearance
            for scene in recent_scenes:
                state = self.db.get_character_state_at_scene(char_db_id, scene['id'])
                if state:
                    context['emotional_state'] = state.get('emotional_state')
                    context['known_facts'] = state.get('knowledge_state', [])
                    
                    # Get location name if available
                    if state.get('physical_location_id'):
                        cursor.execute(
                            "SELECT name FROM locations WHERE id = ?",
                            (state['physical_location_id'],)
                        )
                        loc = cursor.fetchone()
                        if loc:
                            context['current_location'] = loc['name']
                    break
            
            # Get relationships
            relationships = self.db.get_character_relationships(char_db_id)
            for rel in relationships:
                context['relationships'][rel['other_character_identifier']] = {
                    'type': rel['relationship_type'],
                    'name': rel['other_character_name']
                }
            
            # Get recent events involving character
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT DISTINCT c.chapter_number, s.scene_number, 
                           ptd.description, pt.name as thread_name
                    FROM scene_entities se
                    JOIN scenes s ON se.scene_id = s.id
                    JOIN chapters c ON s.chapter_id = c.id
                    LEFT JOIN plot_thread_developments ptd ON ptd.scene_id = s.id
                    LEFT JOIN plot_threads pt ON ptd.plot_thread_id = pt.id
                    WHERE se.entity_type = 'character' AND se.entity_id = ?
                    AND (c.chapter_number < ? OR 
                         (c.chapter_number = ? AND s.scene_number < ?))
                    ORDER BY c.chapter_number DESC, s.scene_number DESC
                    LIMIT 3
                    """,
                    (char_db_id, chapter_num, chapter_num, scene_num)
                )
                
                for row in cursor.fetchall():
                    if row['description']:
                        context['recent_events'].append({
                            'chapter': row['chapter_number'],
                            'scene': row['scene_number'],
                            'event': row['description'],
                            'thread': row['thread_name']
                        })
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to get character context: {e}")
            return {}
    
    def get_scene_dependencies(self, chapter_num: int, scene_num: int) -> Dict[str, Any]:
        """
        Get all dependencies for a scene being written.
        
        Used by scene brainstorming and writing nodes.
        
        Args:
            chapter_num: Chapter number
            scene_num: Scene number
            
        Returns:
            Dictionary with required characters, locations, and plot threads
        """
        if not self.db or not self.story_id:
            return {'characters': [], 'locations': [], 'plot_threads': []}
        
        try:
            dependencies = {
                'characters': [],
                'locations': [],
                'plot_threads': [],
                'continuation_from_previous': None
            }
            
            # Get previous scene for continuation
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                
                # Find previous scene
                cursor.execute(
                    """
                    SELECT s.id, s.content, s.scene_number, c.chapter_number
                    FROM scenes s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE (c.chapter_number < ? OR 
                         (c.chapter_number = ? AND s.scene_number < ?))
                    ORDER BY c.chapter_number DESC, s.scene_number DESC
                    LIMIT 1
                    """,
                    (chapter_num, chapter_num, scene_num)
                )
                prev_scene = cursor.fetchone()
                
                if prev_scene:
                    # Get entities from previous scene for potential continuation
                    entities = self.db.get_entities_in_scene(prev_scene['id'])
                    
                    dependencies['continuation_from_previous'] = {
                        'chapter': prev_scene['chapter_number'],
                        'scene': prev_scene['scene_number'],
                        'ending': prev_scene['content'][-500:] if prev_scene['content'] else '',
                        'characters_present': [c['name'] for c in entities['characters']],
                        'location': entities['locations'][0]['name'] if entities['locations'] else None
                    }
                
                # Get active plot threads
                cursor.execute(
                    """
                    SELECT DISTINCT pt.id, pt.name, pt.description, pt.importance
                    FROM plot_threads pt
                    WHERE pt.story_id = ? 
                    AND pt.status IN ('introduced', 'developed')
                    ORDER BY 
                        CASE pt.importance 
                            WHEN 'major' THEN 1 
                            WHEN 'minor' THEN 2 
                            ELSE 3 
                        END,
                        pt.name
                    """,
                    (self.story_id,)
                )
                
                for row in cursor.fetchall():
                    thread = dict(row)
                    
                    # Check last development
                    cursor.execute(
                        """
                        SELECT c.chapter_number, s.scene_number, ptd.development_type
                        FROM plot_thread_developments ptd
                        JOIN scenes s ON ptd.scene_id = s.id
                        JOIN chapters c ON s.chapter_id = c.id
                        WHERE ptd.plot_thread_id = ?
                        ORDER BY c.chapter_number DESC, s.scene_number DESC
                        LIMIT 1
                        """,
                        (thread['id'],)
                    )
                    last_dev = cursor.fetchone()
                    
                    thread['last_development'] = dict(last_dev) if last_dev else None
                    dependencies['plot_threads'].append(thread)
                
                # Get characters who might appear
                cursor.execute(
                    """
                    SELECT c.id, c.identifier, c.name, 
                           COUNT(DISTINCT se.scene_id) as appearance_count
                    FROM characters c
                    LEFT JOIN scene_entities se ON se.entity_id = c.id 
                        AND se.entity_type = 'character'
                    WHERE c.story_id = ?
                    GROUP BY c.id
                    ORDER BY appearance_count DESC
                    """,
                    (self.story_id,)
                )
                
                for row in cursor.fetchall():
                    char = dict(row)
                    # Add context for each character
                    char['context'] = self.get_character_context(
                        char['identifier'], chapter_num, scene_num
                    )
                    dependencies['characters'].append(char)
                
                # Get available locations
                cursor.execute(
                    """
                    SELECT l.id, l.identifier, l.name, l.description,
                           COUNT(DISTINCT se.scene_id) as usage_count
                    FROM locations l
                    LEFT JOIN scene_entities se ON se.entity_id = l.id 
                        AND se.entity_type = 'location'
                    GROUP BY l.id
                    ORDER BY usage_count DESC
                    """
                )
                
                dependencies['locations'] = [dict(row) for row in cursor.fetchall()]
            
            return dependencies
            
        except Exception as e:
            logger.error(f"Failed to get scene dependencies: {e}")
            return {'characters': [], 'locations': [], 'plot_threads': []}
    
    def get_continuity_check_data(self, chapter_num: int) -> Dict[str, Any]:
        """
        Get data needed for continuity checking.
        
        Used by the continuity review node.
        
        Args:
            chapter_num: Chapter number to check
            
        Returns:
            Dictionary with character states, plot progressions, and potential issues
        """
        if not self.db or not self.story_id:
            return {}
        
        try:
            data = {
                'character_tracking': {},
                'location_usage': {},
                'plot_progression': {},
                'potential_issues': []
            }
            
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                
                # Get all scenes in the chapter
                cursor.execute(
                    """
                    SELECT s.id, s.scene_number
                    FROM scenes s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE c.story_id = ? AND c.chapter_number = ?
                    ORDER BY s.scene_number
                    """,
                    (self.story_id, chapter_num)
                )
                chapter_scenes = cursor.fetchall()
                
                # Track character appearances and states
                cursor.execute(
                    """
                    SELECT DISTINCT c.id, c.identifier, c.name
                    FROM characters c
                    WHERE c.story_id = ?
                    """,
                    (self.story_id,)
                )
                
                for char in cursor.fetchall():
                    char_data = {
                        'appearances': [],
                        'state_changes': [],
                        'knowledge_gained': []
                    }
                    
                    for scene in chapter_scenes:
                        # Check if character appears
                        cursor.execute(
                            """
                            SELECT involvement_type
                            FROM scene_entities
                            WHERE scene_id = ? AND entity_type = 'character' 
                            AND entity_id = ?
                            """,
                            (scene['id'], char['id'])
                        )
                        involvement = cursor.fetchone()
                        
                        if involvement:
                            char_data['appearances'].append({
                                'scene': scene['scene_number'],
                                'involvement': involvement['involvement_type']
                            })
                            
                            # Get state changes
                            state = self.db.get_character_state_at_scene(
                                char['id'], scene['id']
                            )
                            if state:
                                char_data['state_changes'].append({
                                    'scene': scene['scene_number'],
                                    'emotional_state': state.get('emotional_state'),
                                    'evolution': state.get('evolution_notes')
                                })
                    
                    data['character_tracking'][char['identifier']] = char_data
                
                # Track location usage
                cursor.execute(
                    """
                    SELECT l.identifier, l.name, s.scene_number
                    FROM scene_entities se
                    JOIN locations l ON se.entity_id = l.id
                    JOIN scenes s ON se.scene_id = s.id
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE se.entity_type = 'location' 
                    AND c.story_id = ? AND c.chapter_number = ?
                    ORDER BY s.scene_number
                    """,
                    (self.story_id, chapter_num)
                )
                
                for row in cursor.fetchall():
                    if row['identifier'] not in data['location_usage']:
                        data['location_usage'][row['identifier']] = {
                            'name': row['name'],
                            'scenes': []
                        }
                    data['location_usage'][row['identifier']]['scenes'].append(
                        row['scene_number']
                    )
                
                # Track plot progression
                cursor.execute(
                    """
                    SELECT pt.name, ptd.development_type, ptd.description, 
                           s.scene_number
                    FROM plot_thread_developments ptd
                    JOIN plot_threads pt ON ptd.plot_thread_id = pt.id
                    JOIN scenes s ON ptd.scene_id = s.id
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE c.chapter_number = ?
                    ORDER BY s.scene_number
                    """,
                    (chapter_num,)
                )
                
                for row in cursor.fetchall():
                    if row['name'] not in data['plot_progression']:
                        data['plot_progression'][row['name']] = []
                    
                    data['plot_progression'][row['name']].append({
                        'scene': row['scene_number'],
                        'type': row['development_type'],
                        'description': row['description']
                    })
                
                # Identify potential issues
                # Check for characters disappearing without explanation
                for char_id, char_data in data['character_tracking'].items():
                    if len(char_data['appearances']) > 0:
                        scenes_present = [a['scene'] for a in char_data['appearances']]
                        if len(scenes_present) > 1:
                            # Check for gaps
                            for i in range(min(scenes_present), max(scenes_present)):
                                if i not in scenes_present:
                                    data['potential_issues'].append({
                                        'type': 'character_disappearance',
                                        'character': char_id,
                                        'description': f"{char_id} disappears between scenes without explanation"
                                    })
                                    break
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to get continuity check data: {e}")
            return {}
    
    def get_revision_context(self, scene_id: int) -> Dict[str, Any]:
        """
        Get context needed for scene revision.
        
        Used by the scene revision node.
        
        Args:
            scene_id: Scene ID to revise
            
        Returns:
            Dictionary with dependencies and constraints for revision
        """
        if not self.db or not scene_id:
            return {}
        
        try:
            # Get scene impact analysis
            from storyteller_lib.story_analysis import StoryAnalyzer
            analyzer = StoryAnalyzer(self.db)
            impact = analyzer.analyze_scene_impact(scene_id)
            
            # Add specific revision constraints
            revision_context = {
                'scene_info': impact['scene'],
                'must_preserve': {
                    'plot_developments': impact['plot_developments'],
                    'character_states': impact['character_state_changes'],
                    'entity_changes': impact['entity_changes']
                },
                'connected_elements': {
                    'characters': impact['entities_involved']['characters'],
                    'locations': impact['entities_involved']['locations']
                },
                'revision_guidelines': []
            }
            
            # Generate specific guidelines based on impact
            if impact['plot_developments']:
                revision_context['revision_guidelines'].append(
                    "Preserve all plot developments in this scene"
                )
            
            if impact['character_state_changes']:
                revision_context['revision_guidelines'].append(
                    "Maintain character emotional states and evolution"
                )
            
            if len(impact['entities_involved']['characters']) > 2:
                revision_context['revision_guidelines'].append(
                    "Ensure all characters have meaningful participation"
                )
            
            return revision_context
            
        except Exception as e:
            logger.error(f"Failed to get revision context: {e}")
            return {}
    
    def get_affected_scenes_for_change(self, entity_type: str, entity_id: str, 
                                     change_type: str) -> List[int]:
        """
        Get list of scene IDs affected by an entity change.
        
        Args:
            entity_type: Type of entity ('character', 'location', 'plot_thread')
            entity_id: Entity identifier
            change_type: Type of change ('name', 'backstory', 'status', etc.)
            
        Returns:
            List of scene IDs that may need revision
        """
        if not self.db:
            return []
        
        try:
            affected_scene_ids = []
            
            # Convert entity identifier to database ID
            db_entity_id = None
            if entity_type == 'character':
                with self.db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM characters WHERE identifier = ?",
                        (entity_id,)
                    )
                    result = cursor.fetchone()
                    if result:
                        db_entity_id = result['id']
            elif entity_type == 'plot_thread':
                with self.db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM plot_threads WHERE name = ?",
                        (entity_id,)
                    )
                    result = cursor.fetchone()
                    if result:
                        db_entity_id = result['id']
            
            if not db_entity_id:
                return []
            
            # Get affected scenes based on entity type
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                
                if entity_type == 'character':
                    # Find all scenes where character appears
                    cursor.execute(
                        """
                        SELECT DISTINCT scene_id 
                        FROM scene_entities
                        WHERE entity_type = 'character' AND entity_id = ?
                        """,
                        (db_entity_id,)
                    )
                elif entity_type == 'plot_thread':
                    # Find all scenes with plot developments
                    cursor.execute(
                        """
                        SELECT DISTINCT scene_id
                        FROM plot_thread_developments
                        WHERE plot_thread_id = ?
                        """,
                        (db_entity_id,)
                    )
                
                affected_scene_ids = [row['scene_id'] for row in cursor.fetchall()]
            
            return affected_scene_ids
            
        except Exception as e:
            logger.error(f"Failed to get affected scenes: {e}")
            return []
    
    def get_revision_priorities(self, affected_scenes: List[int]) -> List[Tuple[int, int]]:
        """
        Prioritize scenes for revision based on their importance.
        
        Args:
            affected_scenes: List of scene IDs
            
        Returns:
            List of (scene_id, priority) tuples sorted by priority
        """
        if not self.db or not affected_scenes:
            return []
        
        try:
            scene_priorities = []
            
            for scene_id in affected_scenes:
                # Calculate priority based on scene impact
                impact = self.analyzer.analyze_scene_impact(scene_id) if hasattr(self, 'analyzer') else None
                
                if not impact:
                    # Default priority
                    scene_priorities.append((scene_id, 5))
                    continue
                
                # Higher impact score = higher priority
                impact_score = impact['impact_metrics']['impact_score']
                priority = min(10, max(1, impact_score // 5))  # Normalize to 1-10
                
                scene_priorities.append((scene_id, priority))
            
            # Sort by priority (highest first)
            scene_priorities.sort(key=lambda x: -x[1])
            
            return scene_priorities
            
        except Exception as e:
            logger.error(f"Failed to get revision priorities: {e}")
            return [(scene_id, 5) for scene_id in affected_scenes]  # Default priority


# Global context provider instance
_context_provider: Optional[StoryContextProvider] = None


def initialize_context_provider() -> StoryContextProvider:
    """
    Initialize the global context provider.
    
    Returns:
        Initialized context provider
    """
    global _context_provider
    _context_provider = StoryContextProvider()
    return _context_provider


def get_context_provider() -> Optional[StoryContextProvider]:
    """Get the global context provider instance."""
    return _context_provider