"""
Comprehensive scene context builder that gathers ALL necessary information
for scene writing and reflection. This ensures scenes are properly connected
to the overall story, characters, world, and plot progression.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from storyteller_lib.core.models import StoryState
from storyteller_lib.persistence.database import get_db_manager
from storyteller_lib.core.logger import get_logger
logger = get_logger(__name__)


@dataclass
class ComprehensiveSceneContext:
    """Complete context needed for writing a coherent scene."""
    # Story-level context
    story_premise: str
    initial_idea: str
    genre: str
    tone: str
    author_style: Optional[str]
    
    # Chapter context
    chapter_number: int
    chapter_title: str
    chapter_outline: str
    chapter_themes: List[str]
    
    # Scene specifications
    scene_number: int
    scene_description: str
    scene_type: str
    dramatic_purpose: str
    tension_level: int
    ends_with: str
    
    # Plot context
    plot_progressions: List[Dict[str, Any]]
    active_plot_threads: List[Dict[str, Any]]
    
    # Character context
    required_characters: List[str]
    character_learns: List[str]
    character_details: List[Dict[str, Any]]
    character_relationships: List[Dict[str, Any]]
    
    # World context
    relevant_locations: List[Dict[str, Any]]
    relevant_world_elements: Dict[str, Any]
    
    # Previous/Next context
    previous_scene_ending: str
    previous_scenes_summary: str
    next_scene_preview: Optional[str]
    
    # Writing constraints
    forbidden_repetitions: List[str]
    recent_scene_types: List[str]
    overused_phrases: List[str]
    
    # Style and language
    language: str
    style_guide: Dict[str, Any]
    

def build_comprehensive_scene_context(
    chapter: int, 
    scene: int, 
    state: StoryState
) -> ComprehensiveSceneContext:
    """
    Build complete scene context by gathering ALL necessary information.
    This replaces the fragmented context gathering in v2.
    
    Args:
        chapter: Chapter number
        scene: Scene number  
        state: Current story state
        
    Returns:
        ComprehensiveSceneContext with all information needed for coherent scene writing
    """
    logger.info(f"Building comprehensive context for Chapter {chapter}, Scene {scene}")
    
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        raise RuntimeError("Database manager not available")
    
    # 1. Get story-level context (including author style guidance from state)
    story_context = _get_story_context(db_manager, state)
    
    # 2. Get chapter context
    chapter_context = _get_chapter_context(db_manager, chapter)
    
    # 3. Get scene specifications from state
    scene_specs = _get_scene_specifications(state, chapter, scene)
    
    # 4. Get plot context
    plot_context = _get_plot_context(db_manager, scene_specs)
    
    # 5. Get character context
    character_context = _get_character_context(
        db_manager, 
        scene_specs['required_characters'],
        scene_specs['description'],
        state
    )
    
    # 6. Get world context using intelligent selection
    from storyteller_lib.universe.world.scene_integration import get_intelligent_world_context
    
    # Extract plot thread descriptions
    plot_thread_descriptions = [thread['name'] for thread in plot_context.get('active_threads', [])]
    
    # Get intelligent world context
    intelligent_world = get_intelligent_world_context(
        scene_description=scene_specs['description'],
        scene_type=scene_specs['scene_type'],
        location=character_context['locations'][0]['name'] if character_context['locations'] else "Unknown",
        characters=scene_specs['required_characters'],
        plot_threads=plot_thread_descriptions,
        dramatic_purpose=scene_specs['dramatic_purpose'],
        chapter_themes=chapter_context['themes'],
        chapter=chapter,
        scene=scene
    )
    
    # Still get basic location data
    world_context = _get_world_context(
        db_manager,
        scene_specs['description'],
        character_context['locations']
    )
    
    # Merge intelligent worldbuilding with location data
    world_context['elements'] = intelligent_world['elements']
    world_context['worldbuilding_analysis'] = intelligent_world.get('needs_analysis', {})
    
    # 7. Get previous/next scene context
    sequence_context = _get_sequence_context(db_manager, chapter, scene, state)
    
    # 8. Get writing constraints
    constraints = _get_writing_constraints(db_manager, chapter, scene)
    
    # 9. Get style guide
    style_data = _get_comprehensive_style_guide(
        story_context['genre'],
        story_context['tone'], 
        story_context['author'],
        story_context['language'],
        story_context.get('author_style_guidance', '')
    )
    
    # Build comprehensive context
    return ComprehensiveSceneContext(
        # Story-level
        story_premise=story_context['premise'],
        initial_idea=story_context['initial_idea'],
        genre=story_context['genre'],
        tone=story_context['tone'],
        author_style=story_context['author'],
        
        # Chapter
        chapter_number=chapter,
        chapter_title=chapter_context['title'],
        chapter_outline=chapter_context['outline'],
        chapter_themes=chapter_context['themes'],
        
        # Scene specs
        scene_number=scene,
        scene_description=scene_specs['description'],
        scene_type=scene_specs['scene_type'],
        dramatic_purpose=scene_specs['dramatic_purpose'],
        tension_level=scene_specs['tension_level'],
        ends_with=scene_specs['ends_with'],
        
        # Plot
        plot_progressions=plot_context['progressions'],
        active_plot_threads=plot_context['active_threads'],
        
        # Characters
        required_characters=scene_specs['required_characters'],
        character_learns=scene_specs['character_learns'],
        character_details=character_context['characters'],
        character_relationships=character_context['relationships'],
        
        # World
        relevant_locations=world_context['locations'],
        relevant_world_elements=world_context['elements'],
        
        # Sequence
        previous_scene_ending=sequence_context['previous_ending'],
        previous_scenes_summary=sequence_context['previous_summary'],
        next_scene_preview=sequence_context['next_preview'],
        
        # Constraints
        forbidden_repetitions=constraints['forbidden_repetitions'],
        recent_scene_types=constraints['recent_scene_types'],
        overused_phrases=constraints['overused_phrases'],
        
        # Style
        language=story_context['language'],
        style_guide=style_data
    )


def _get_story_context(db_manager, state: StoryState = None) -> Dict[str, Any]:
    """Get story-level context from database and state."""
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title, genre, tone, author, language, initial_idea, global_story
            FROM story_config WHERE id = 1
        """)
        result = cursor.fetchone()
        
        if not result:
                raise RuntimeError("No story configuration found")
        
        # Extract premise from global story
        premise = ""
        if result['global_story']:
            # Take first paragraph as premise, or first 500 chars
            paragraphs = result['global_story'].split('\n\n')
            premise = paragraphs[0] if paragraphs else result['global_story'][:500]
        
        # Get author style guidance from state if available
        author_style_guidance = ""
        if state and "author_style_guidance" in state:
                author_style_guidance = state["author_style_guidance"]
        
        return {
            'title': result['title'] or "Untitled Story",
            'genre': result['genre'] or "fantasy",
            'tone': result['tone'] or "adventurous", 
            'author': result['author'],
            'language': result['language'] or "english",
            'initial_idea': result['initial_idea'] or "",
            'premise': premise,
            'author_style_guidance': author_style_guidance
        }


def _get_chapter_context(db_manager, chapter: int) -> Dict[str, Any]:
    """Get chapter-level context from database."""
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title, outline FROM chapters 
            WHERE chapter_number = ?
        """, (chapter,))
        result = cursor.fetchone()
        
        if not result:
            logger.warning(f"No chapter {chapter} found in database")
            return {
                'title': f"Chapter {chapter}",
                'outline': "",
                'themes': []
            }
        
        # Extract themes from outline (simple approach)
        themes = []
        outline = result['outline'] or ""
        if "theme" in outline.lower():
            # Extract themes mentioned in outline
            lines = outline.split('\n')
            for line in lines:
                if "theme" in line.lower():
                    themes.append(line.strip())
        
        return {
            'title': result['title'] or f"Chapter {chapter}",
            'outline': outline,
            'themes': themes[:3]  # Limit to 3 main themes
        }


def _get_scene_specifications(state: StoryState, chapter: int, scene: int) -> Dict[str, Any]:
    """Get scene specifications from state."""
    chapters = state.get("chapters", {})
    scene_data = {}
    
    if str(chapter) in chapters and "scenes" in chapters[str(chapter)]:
        scene_data = chapters[str(chapter)]["scenes"].get(str(scene), {})
    
    return {
        'description': scene_data.get('description', ''),
        'plot_progressions': scene_data.get('plot_progressions', []),
        'character_learns': scene_data.get('character_learns', []),
        'required_characters': scene_data.get('required_characters', []),
        'dramatic_purpose': scene_data.get('dramatic_purpose', 'development'),
        'tension_level': scene_data.get('tension_level', 5),
        'ends_with': scene_data.get('ends_with', 'transition'),
        'scene_type': scene_data.get('scene_type', 'exploration')
    }


def _get_plot_context(db_manager, scene_specs: Dict[str, Any]) -> Dict[str, Any]:
    """Get plot-related context."""
    # Get existing plot progressions
    existing_progressions = db_manager.get_plot_progressions()
    existing_keys = [p['progression_key'] for p in existing_progressions]
    
    # Structure plot progressions with status
    progressions = []
    for prog in scene_specs['plot_progressions']:
        progressions.append({
            'key': prog,
            'already_occurred': prog in existing_keys,
            'description': prog
        })
    
    # Get active plot threads
    active_threads = []
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pt.name, pt.description, pt.importance, pt.status,
                ptd.description as last_development
            FROM plot_threads pt
            LEFT JOIN plot_thread_developments ptd ON pt.id = ptd.plot_thread_id
            WHERE pt.status IN ('introduced', 'developing')
            AND pt.importance IN ('major', 'minor')
            ORDER BY 
                CASE pt.importance 
                WHEN 'major' THEN 1 
                WHEN 'minor' THEN 2 
                ELSE 3 
                END,
                ptd.scene_id DESC
            LIMIT 5
        """)
        
        for row in cursor.fetchall():
                active_threads.append({
                'name': row['name'],
                'description': row['description'],
                'importance': row['importance'],
                'status': row['status'],
                'last_development': row['last_development'] or row['description']
            })
    
    return {
        'progressions': progressions,
        'active_threads': active_threads
    }


def _get_character_context(db_manager, required_chars: List[str], scene_desc: str, state: StoryState = None) -> Dict[str, Any]:
    """Get comprehensive character context including worldbuilding descriptions."""
    characters = []
    character_ids = []
    
    # Get character info from state if available for richer descriptions
    state_characters = {}
    if state and "characters" in state:
        state_characters = state.get("characters", {})
    
    # Get required characters first
    for char_identifier in required_chars:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.id, c.identifier, c.name, c.role, c.backstory, c.personality,
                    cs.emotional_state
                FROM characters c
                LEFT JOIN character_states cs ON c.id = cs.character_id
                WHERE c.identifier = ? OR c.name = ?
                ORDER BY cs.scene_id DESC
                LIMIT 1
            """, (char_identifier, char_identifier))
            
            result = cursor.fetchone()
            if result:
                character_ids.append(result['id'])
                
                # Parse personality JSON
                import json
                personality = json.loads(result['personality'] or '{}')
                
                # Get emotional state
                emotional_state = "neutral"
                if result['emotional_state']:
                    state_data = json.loads(result['emotional_state'])
                    emotional_state = state_data.get('current', 'neutral')
                
                # Get recent knowledge
                cursor.execute("""
                SELECT knowledge_content, knowledge_type
                FROM character_knowledge
                WHERE character_id = ?
                ORDER BY scene_id DESC
                LIMIT 5
                """, (result['id'],))
                
                knowledge = [{'content': row['knowledge_content'], 
                        'type': row['knowledge_type']} 
                        for row in cursor.fetchall()]
                
                # Check if we have richer character data in state
                char_data = {
                'id': result['id'],
                'identifier': result['identifier'],
                'name': result['name'],
                'role': result['role'],
                'backstory': result['backstory'],
                'personality': personality,
                'emotional_state': emotional_state,
                'motivation': personality.get('desires', ['Unknown'])[0] if personality.get('desires') else 'Unknown',
                'inner_conflicts': personality.get('inner_conflicts', []),
                'recent_knowledge': knowledge
                }
                
                # Enhance with state data if available
                if state_characters and result['identifier'] in state_characters:
                    state_char = state_characters[result['identifier']]
                
                    # Add personality details if more comprehensive in state
                    if isinstance(state_char.get('personality'), dict):
                        state_personality = state_char['personality']
                        # Merge personality data, preferring state data when richer
                        if 'traits' in state_personality:
                            char_data['personality']['traits'] = state_personality.get('traits', [])
                    if 'strengths' in state_personality:
                            char_data['personality']['strengths'] = state_personality.get('strengths', [])
                    if 'flaws' in state_personality:
                            char_data['personality']['flaws'] = state_personality.get('flaws', [])
                    if 'fears' in state_personality:
                            char_data['personality']['fears'] = state_personality.get('fears', [])
                    if 'desires' in state_personality:
                            char_data['personality']['desires'] = state_personality.get('desires', [])
                    if 'values' in state_personality:
                            char_data['personality']['values'] = state_personality.get('values', [])
                
                    # Add emotional journey if available
                    if 'emotional_state' in state_char and isinstance(state_char['emotional_state'], dict):
                        char_data['emotional_journey'] = state_char['emotional_state'].get('journey', [])
                        char_data['initial_emotional_state'] = state_char['emotional_state'].get('initial', emotional_state)
                
                    # Add inner conflicts from state (more detailed than DB)
                    if 'inner_conflicts' in state_char and isinstance(state_char['inner_conflicts'], list):
                        char_data['inner_conflicts'] = state_char['inner_conflicts']
                
                    # Add character arc information
                    if 'character_arc' in state_char and isinstance(state_char['character_arc'], dict):
                        char_data['character_arc'] = state_char['character_arc']
                
                    # Add evolution notes
                    if 'evolution' in state_char and isinstance(state_char['evolution'], list):
                        char_data['evolution'] = state_char['evolution']
                
                    # Extract physical description from key traits if available
                    if 'key_traits' in state_char and isinstance(state_char['key_traits'], list):
                        char_data['key_traits'] = state_char['key_traits']
                        # Look for physical descriptions in key traits
                        physical_traits = [trait for trait in state_char['key_traits'] 
                                        if any(word in trait.lower() for word in 
                                                ['tall', 'short', 'hair', 'eyes', 'build', 'appearance', 'looks'])]
                        if physical_traits:
                            char_data['physical_description'] = ', '.join(physical_traits)
                
                characters.append(char_data)
    
    # Get relationships between characters
    relationships = []
    if len(character_ids) > 1:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(character_ids))
            cursor.execute(f"""
                SELECT cr.*, c1.name as char1_name, c2.name as char2_name,
                    cr.character1_id, cr.character2_id, cr.properties
                FROM character_relationships cr
                JOIN characters c1 ON cr.character1_id = c1.id
                JOIN characters c2 ON cr.character2_id = c2.id
                WHERE cr.character1_id IN ({placeholders})
                AND cr.character2_id IN ({placeholders})
            """, character_ids + character_ids)
            
            for row in cursor.fetchall():
                rel_data = {
                'character1': row['char1_name'],
                'character2': row['char2_name'],
                'type': row['relationship_type'],
                'description': row['description']
                }
                
                # Parse properties if available for dynamics and evolution
                if row['properties']:
                    try:
                        properties = json.loads(row['properties'])
                        if 'dynamics' in properties:
                            rel_data['dynamics'] = properties['dynamics']
                        if 'evolution' in properties:
                            rel_data['evolution'] = properties['evolution']
                        if 'conflicts' in properties:
                            rel_data['conflicts'] = properties['conflicts']
                    except json.JSONDecodeError:
                        pass
                
                # Also check state for richer relationship data
                if state_characters:
                    # Look for relationship data in state characters
                    for char_id in [row['character1_id'], row['character2_id']]:
                        # Find the character identifier for this ID
                        char_identifier = None
                        for char in characters:
                                if char['id'] == char_id:
                                    char_identifier = char['identifier']
                                break
                        
                        if char_identifier and char_identifier in state_characters:
                            state_char = state_characters[char_identifier]
                            if 'relationships' in state_char and isinstance(state_char['relationships'], dict):
                                # Look for relationship with the other character
                                for rel_key, rel_info in state_char['relationships'].items():
                                    if isinstance(rel_info, dict):
                                        # Check if this relationship matches
                                        target_name = rel_info.get('target_character', '')
                                        if target_name in [row['char1_name'], row['char2_name']]:
                                            # Enhance with state data
                                            if 'dynamics' in rel_info and not rel_data.get('dynamics'):
                                                rel_data['dynamics'] = rel_info['dynamics']
                                            if 'evolution' in rel_info:
                                                rel_data['evolution'] = rel_info.get('evolution', [])
                                            if 'conflicts' in rel_info:
                                                rel_data['conflicts'] = rel_info.get('conflicts', [])
                                            break
                
                relationships.append(rel_data)
    
    # Get character locations
    locations = []
    for char_id in character_ids:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.identifier, l.name, l.description, cl.association_type
                FROM character_locations cl
                JOIN locations l ON cl.location_id = l.id
                WHERE cl.character_id = ?
            """, (char_id,))
            
            for row in cursor.fetchall():
                locations.append({
                'identifier': row['identifier'],
                'name': row['name'],
                'description': row['description'],
                'association': row['association_type']
                })
    
    return {
        'characters': characters,
        'relationships': relationships,
        'locations': locations
    }


def _get_world_context(db_manager, scene_desc: str, character_locations: List[Dict]) -> Dict[str, Any]:
    """Get relevant world elements for the scene using intelligent selection."""
    # Get locations mentioned in scene or associated with characters
    relevant_locations = character_locations.copy()
    
    # Add locations mentioned in scene description
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT identifier, name, description FROM locations")
        
        for row in cursor.fetchall():
            if row['name'].lower() in scene_desc.lower():
                if not any(loc['name'] == row['name'] for loc in relevant_locations):
                    relevant_locations.append({
                        'identifier': row['identifier'],
                        'name': row['name'],
                        'description': row['description'],
                        'association': 'scene_location'
                    })
    
    # Use intelligent worldbuilding selection instead of keyword matching
    # This will be properly integrated when called from build_comprehensive_scene_context
    # For now, return the locations we found
    return {
        'locations': relevant_locations[:5],  # Limit to 5 locations
        'elements': {}  # Will be populated by intelligent selector
    }


def _extract_world_keywords(text: str) -> List[str]:
    """Extract keywords that might relate to world elements."""
    # Common world element keywords
    keywords = []
    world_terms = [
        'city', 'town', 'village', 'castle', 'palace', 'temple', 'forest',
        'mountain', 'river', 'ocean', 'desert', 'kingdom', 'empire',
        'magic', 'spell', 'artifact', 'technology', 'weapon', 'creature',
        'god', 'religion', 'culture', 'tradition', 'law', 'government'
    ]
    
    text_lower = text.lower()
    for term in world_terms:
        if term in text_lower:
                keywords.append(term)
    
    return keywords


def _get_sequence_context(db_manager, chapter: int, scene: int, state: StoryState) -> Dict[str, Any]:
    """Get context from previous and next scenes."""
    # Get previous scene ending
    previous_ending = ""
    previous_summary = ""
    
    if scene > 1:
        # Previous scene in same chapter
        prev_content = db_manager.get_scene_content(chapter, scene - 1)
        if prev_content:
            # Get last 300 words for ending
            words = prev_content.split()
            previous_ending = ' '.join(words[-300:]) if len(words) > 300 else prev_content
            
            # Get summary of previous scenes in chapter
            with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT s.scene_number, s.description
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE c.chapter_number = ? AND s.scene_number < ?
                ORDER BY s.scene_number DESC
                LIMIT 3
                """, (chapter, scene))
                
                summaries = []
                for row in cursor.fetchall():
                    if row['description']:
                        summaries.append(f"Scene {row['scene_number']}: {row['description']}")
                
                previous_summary = "\n".join(reversed(summaries))
    
    elif chapter > 1:
        # Get ending of previous chapter
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(s.scene_number) as last_scene
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE c.chapter_number = ?
            """, (chapter - 1,))
            
            result = cursor.fetchone()
            if result and result['last_scene']:
                prev_content = db_manager.get_scene_content(chapter - 1, result['last_scene'])
                if prev_content:
                    words = prev_content.split()
                    previous_ending = ' '.join(words[-300:]) if len(words) > 300 else prev_content
    
    # Get next scene preview
    next_preview = None
    chapters = state.get("chapters", {})
    if str(chapter) in chapters and "scenes" in chapters[str(chapter)]:
        next_scene_data = chapters[str(chapter)]["scenes"].get(str(scene + 1), {})
        if next_scene_data and 'description' in next_scene_data:
            next_preview = next_scene_data['description']
    
    return {
        'previous_ending': previous_ending,
        'previous_summary': previous_summary,
        'next_preview': next_preview
    }


def _get_writing_constraints(db_manager, chapter: int, scene: int) -> Dict[str, Any]:
    """Get constraints to avoid repetition and maintain variety."""
    constraints = {
        'forbidden_repetitions': [],
        'recent_scene_types': [],
        'overused_phrases': []
    }
    
    # Get recent scene types
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.scene_type
            FROM scenes s
            JOIN chapters c ON s.chapter_id = c.id
            WHERE c.chapter_number = ? AND s.scene_number < ?
            ORDER BY s.scene_number DESC
            LIMIT 5
        """, (chapter, scene))
        
        constraints['recent_scene_types'] = [
            row['scene_type'] for row in cursor.fetchall() 
            if row['scene_type']
        ]
    
    # Get overused content from registry
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT content_text, COUNT(*) as usage_count
            FROM used_content_registry
            WHERE content_type IN ('description', 'metaphor', 'action')
            GROUP BY content_text
            HAVING usage_count > 2
            ORDER BY usage_count DESC
            LIMIT 10
        """)
        
        constraints['overused_phrases'] = [
            row['content_text'] for row in cursor.fetchall()
        ]
    
    # Add specific forbidden repetitions based on recent content
    if len(constraints['recent_scene_types']) >= 3:
        # If we've had 3 of the same type recently, forbid it
        from collections import Counter
      
        type_counts = Counter(constraints['recent_scene_types'][:3])
        for scene_type, count in type_counts.items():
            if count >= 2:
                constraints['forbidden_repetitions'].append(
                    f"Another {scene_type} scene (already had {count} recently)"
                )
    
    return constraints


def _get_comprehensive_style_guide(genre: str, tone: str, author: Optional[str], language: str, author_style_guidance: str = "") -> Dict[str, Any]:
    """Create a comprehensive style guide data structure for template use."""
    style_data = {
        'genre': genre,
        'tone': tone,
        'author': author,
        'language': language,
        'author_style_guidance': {}
    }
    
    # If we have detailed author style guidance, parse it into structured data
    if author and author_style_guidance:
        # Parse the author style guidance into components
        guidance_sections = {}
        sections = author_style_guidance.split('\n\n')
        
        for section in sections:
            if section.strip() and ':' in section:
                lines = section.strip().split('\n')
                if lines:
                # First line is the section header
                    header_line = lines[0]
                    if ':' in header_line:
                        header, content = header_line.split(':', 1)
                        header = header.strip()
                        
                        # Combine header content with any additional lines
                        full_content = content.strip()
                        if len(lines) > 1:
                            full_content = '\n'.join([content.strip()] + lines[1:])
                        
                        # Map to standardized keys
                        if 'Narrative Style' in header:
                                guidance_sections['narrative_style'] = full_content
                        elif 'Character Development' in header:
                                guidance_sections['character_development'] = full_content
                        elif 'Dialogue' in header:
                                guidance_sections['dialogue_patterns'] = full_content
                        elif 'Thematic' in header:
                                guidance_sections['thematic_elements'] = full_content
                        elif 'Pacing' in header:
                                guidance_sections['pacing_rhythm'] = full_content
                        elif 'Descriptive' in header:
                                guidance_sections['descriptive_approach'] = full_content
                        elif 'Unique' in header:
                                guidance_sections['unique_elements'] = full_content
                        elif 'Emotional' in header:
                                guidance_sections['emotional_tone'] = full_content
        
        style_data['author_style_guidance'] = guidance_sections
    
    return style_data