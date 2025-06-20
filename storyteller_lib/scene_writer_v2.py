"""
Simplified scene writer implementation following the refactoring plan.
This module consolidates the scene writing process into a cleaner, more maintainable workflow.
"""

from typing import Dict, List, Optional, Tuple
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from storyteller_lib import track_progress
from storyteller_lib.config import llm, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState
from storyteller_lib.database_integration import get_db_manager
from storyteller_lib.logger import scene_logger as logger
from storyteller_lib.prompt_templates import render_prompt


class SceneContext(BaseModel):
    """Consolidated scene context for writing."""
    requirements: Dict = Field(description="What must happen in the scene")
    previous_ending: str = Field(description="How the previous scene ended")
    next_preview: Optional[str] = Field(description="What comes next")
    active_threads: List[Dict] = Field(description="Currently active plot threads")


class CharacterContext(BaseModel):
    """Character information for the scene."""
    name: str
    current_state: str
    motivation: str
    knowledge: List[str]


class UnifiedSceneContext(BaseModel):
    """All context needed for scene writing."""
    scene: SceneContext
    characters: List[CharacterContext]
    world_elements: Dict[str, str]
    style_guide: str
    constraints: List[str]


def build_scene_context(chapter: int, scene: int, state: StoryState) -> SceneContext:
    """
    Gather core scene requirements and connections.
    Replaces: _prepare_database_context, _generate_previous_scenes_summary, and others.
    """
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        raise RuntimeError("Database manager not available")
    
    # Get scene specifications from state
    scene_spec = {}
    chapters = state.get("chapters", {})
    if str(chapter) in chapters and "scenes" in chapters[str(chapter)]:
        scene_data = chapters[str(chapter)]["scenes"].get(str(scene), {})
        scene_spec = {
            'description': scene_data.get('description', ''),
            'plot_progressions': scene_data.get('plot_progressions', []),
            'character_learns': scene_data.get('character_learns', []),
            'required_characters': scene_data.get('required_characters', []),
            'dramatic_purpose': scene_data.get('dramatic_purpose', 'development'),
            'tension_level': scene_data.get('tension_level', 5),
            'ends_with': scene_data.get('ends_with', 'transition'),
            'scene_type': scene_data.get('scene_type', 'exploration')
        }
    
    # Get previous scene ending (simplified)
    previous_ending = ""
    if scene > 1:
        prev_content = db_manager.get_scene_content(chapter, scene - 1)
        if prev_content:
            # Get last 200 words
            words = prev_content.split()
            previous_ending = ' '.join(words[-200:]) if len(words) > 200 else prev_content
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
                    previous_ending = ' '.join(words[-200:]) if len(words) > 200 else prev_content
    
    # Get next scene preview if available
    next_preview = None
    if str(chapter) in chapters and "scenes" in chapters[str(chapter)]:
        next_scene_data = chapters[str(chapter)]["scenes"].get(str(scene + 1), {})
        if next_scene_data and 'description' in next_scene_data:
            next_preview = next_scene_data['description']
    
    # Get top 3 active plot threads
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
            LIMIT 3
        """)
        for row in cursor.fetchall():
            active_threads.append({
                'name': row['name'],
                'description': row['description'],
                'importance': row['importance'],
                'status': row['status'],
                'last_development': row['last_development'] or row['description']
            })
    
    return SceneContext(
        requirements=scene_spec,
        previous_ending=previous_ending,
        next_preview=next_preview,
        active_threads=active_threads
    )


def build_character_context(scene_description: str, required_characters: List[str]) -> List[CharacterContext]:
    """
    Get only active character information.
    Replaces: entity_relevance analysis, _identify_scene_characters, and character filtering.
    """
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        return []
    
    # Simple keyword-based character identification
    scene_characters = set(required_characters)
    
    # Add characters mentioned in scene description
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT identifier, name FROM characters")
        for row in cursor.fetchall():
            if row['name'].lower() in scene_description.lower():
                scene_characters.add(row['identifier'])
    
    # Limit to 5 most relevant characters
    scene_characters = list(scene_characters)[:5]
    
    # Get character details
    character_contexts = []
    for char_id in scene_characters:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, personality
                FROM characters
                WHERE identifier = ? OR name = ?
            """, (char_id, char_id))
            result = cursor.fetchone()
            
            if result:
                char_db_id = result['id']
                
                # Get current emotional state from character_states if available
                cursor.execute("""
                    SELECT cs.emotional_state
                    FROM character_states cs
                    JOIN scenes s ON cs.scene_id = s.id
                    WHERE cs.character_id = ?
                    ORDER BY s.id DESC
                    LIMIT 1
                """, (char_db_id,))
                state_result = cursor.fetchone()
                
                # Get current knowledge
                cursor.execute("""
                    SELECT knowledge_content
                    FROM character_knowledge ck
                    JOIN scenes s ON ck.scene_id = s.id
                    WHERE ck.character_id = ?
                    ORDER BY s.id DESC
                    LIMIT 5
                """, (char_db_id,))
                knowledge = [row['knowledge_content'] for row in cursor.fetchall()]
                
                # Parse personality
                import json
                personality = json.loads(result['personality'] or '{}')
                
                # Parse emotional state if available
                current_state = 'Unknown'
                if state_result and state_result['emotional_state']:
                    emotional_state = json.loads(state_result['emotional_state'])
                    current_state = emotional_state.get('current', 'Unknown')
                
                character_contexts.append(CharacterContext(
                    name=result['name'],
                    current_state=current_state,
                    motivation=personality.get('core_motivation', 'Unknown'),
                    knowledge=knowledge
                ))
    
    return character_contexts


def build_world_context(scene_description: str) -> Dict[str, str]:
    """
    Extract only directly relevant world elements.
    Replaces: complex entity_relevance and world filtering.
    """
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        return {}
    
    # Simple keyword extraction
    keywords = []
    # Common world element keywords
    world_keywords = ['city', 'town', 'village', 'forest', 'mountain', 'river', 'castle', 
                      'palace', 'temple', 'market', 'tavern', 'road', 'bridge', 'magic',
                      'technology', 'weapon', 'artifact', 'creature', 'beast', 'monster']
    
    scene_lower = scene_description.lower()
    for keyword in world_keywords:
        if keyword in scene_lower:
            keywords.append(keyword)
    
    # Get relevant world elements
    world_context = {}
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category, element_key, element_value
            FROM world_elements
            WHERE category IN ('geography', 'culture', 'magic_system', 'technology')
        """)
        
        for row in cursor.fetchall():
            # Include if key or value contains any keyword
            if any(kw in row['element_key'].lower() or kw in row['element_value'].lower() 
                   for kw in keywords):
                if row['category'] not in world_context:
                    world_context[row['category']] = {}
                world_context[row['category']][row['element_key']] = row['element_value']
    
    # Limit to most relevant elements
    for category in world_context:
        if len(world_context[category]) > 3:
            # Keep only first 3 elements per category
            items = list(world_context[category].items())[:3]
            world_context[category] = dict(items)
    
    return world_context


def analyze_scene_requirements(state: StoryState) -> Dict:
    """
    Combine all requirement analyses into one.
    Replaces: 8 separate analysis phases.
    """
    current_chapter = int(state.get("current_chapter", 1))
    current_scene = int(state.get("current_scene", 1))
    
    # Get scene specifications
    chapters = state.get("chapters", {})
    scene_data = {}
    if str(current_chapter) in chapters and "scenes" in chapters[str(current_chapter)]:
        scene_data = chapters[str(current_chapter)]["scenes"].get(str(current_scene), {})
    
    # Check variety needs (simplified)
    db_manager = get_db_manager()
    recent_types = []
    if db_manager and db_manager._db:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.scene_type
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE c.chapter_number = ? AND s.scene_number < ?
                ORDER BY s.scene_number DESC
                LIMIT 3
            """, (current_chapter, current_scene))
            recent_types = [row['scene_type'] for row in cursor.fetchall() if row['scene_type']]
    
    # Determine scene variety needs
    scene_type = scene_data.get('scene_type', 'exploration')
    if recent_types.count(scene_type) >= 2:
        # Too many of same type recently, suggest alternative
        alternatives = ['action', 'dialogue', 'exploration', 'revelation', 'character_moment']
        alternatives.remove(scene_type)
        suggested_type = alternatives[0]  # Simple selection
    else:
        suggested_type = scene_type
    
    return {
        'must_happen': {
            'plot_progressions': scene_data.get('plot_progressions', []),
            'character_learning': scene_data.get('character_learns', [])
        },
        'characters_needed': scene_data.get('required_characters', []),
        'dramatic_needs': {
            'purpose': scene_data.get('dramatic_purpose', 'development'),
            'tension': scene_data.get('tension_level', 5),
            'ending': scene_data.get('ends_with', 'transition')
        },
        'variety_needs': {
            'scene_type': suggested_type,
            'avoid_repetition': recent_types
        }
    }


def create_unified_style_guide(state: StoryState) -> str:
    """
    Create a single, unified style guide combining genre, tone, and author.
    """
    from storyteller_lib.config import get_story_config
    config = get_story_config()
    
    genre = config.get("genre", "fantasy")
    tone = config.get("tone", "adventurous")
    author = config.get("author", "")
    language = config.get("language", DEFAULT_LANGUAGE)
    
    # Basic style guide
    style_guide = f"""
STYLE GUIDE:
- Genre: {genre} - Focus on {get_genre_elements(genre)}
- Tone: {tone} - Maintain {get_tone_guidance(tone)}
- Voice: {get_voice_guidance(genre, tone)}
"""
    
    # Add author style if specified
    if author and state.get("author_style_guidance"):
        style_guide += f"\n- Author Style: Emulate {author}'s narrative techniques"
    
    # Add language considerations
    if language != DEFAULT_LANGUAGE:
        style_guide += f"\n- Language: Write naturally in {SUPPORTED_LANGUAGES[language]}"
    
    return style_guide.strip()


def get_genre_elements(genre: str) -> str:
    """Get key elements for a genre."""
    genre_map = {
        'fantasy': 'magic, wonder, and heroic journeys',
        'sci-fi': 'technology, exploration, and future possibilities',
        'mystery': 'clues, suspense, and revelation',
        'romance': 'relationships, emotions, and connection',
        'thriller': 'tension, danger, and urgency',
        'horror': 'fear, atmosphere, and dread'
    }
    return genre_map.get(genre.lower(), 'engaging storytelling')


def get_tone_guidance(tone: str) -> str:
    """Get guidance for maintaining tone."""
    tone_map = {
        'adventurous': 'excitement and discovery',
        'dark': 'shadow and complexity',
        'humorous': 'wit and levity',
        'epic': 'grandeur and scale',
        'intimate': 'personal connection',
        'mysterious': 'intrigue and uncertainty'
    }
    return tone_map.get(tone.lower(), 'consistent atmosphere')


def get_voice_guidance(genre: str, tone: str) -> str:
    """Get narrative voice guidance."""
    if tone in ['dark', 'mysterious']:
        return "Use measured, atmospheric prose"
    elif tone in ['humorous', 'light']:
        return "Use lively, engaging prose"
    elif genre in ['fantasy', 'epic']:
        return "Use rich, immersive prose"
    else:
        return "Use clear, purposeful prose"


@track_progress
def write_scene_simplified(state: StoryState) -> Dict:
    """
    Simplified scene writing function.
    This replaces the complex write_scene function with a cleaner implementation.
    """
    current_chapter = int(state.get("current_chapter", 1))
    current_scene = int(state.get("current_scene", 1))
    
    logger.info(f"Writing scene {current_scene} of chapter {current_chapter} (simplified)")
    
    # Phase 1: Gather consolidated context
    scene_context = build_scene_context(current_chapter, current_scene, state)
    
    # Phase 2: Analyze requirements
    requirements = analyze_scene_requirements(state)
    
    # Phase 3: Get character context
    character_context = build_character_context(
        scene_context.requirements.get('description', ''),
        requirements['characters_needed']
    )
    
    # Phase 4: Get world context (simplified)
    world_context = build_world_context(scene_context.requirements.get('description', ''))
    
    # Phase 5: Create style guide
    style_guide = create_unified_style_guide(state)
    
    # Phase 6: Identify constraints
    constraints = []
    
    # Add forbidden repetitions
    if 'forbidden_repetitions' in scene_context.requirements:
        constraints.extend(scene_context.requirements['forbidden_repetitions'])
    
    # Add recent scene types to avoid
    if requirements['variety_needs']['avoid_repetition']:
        constraints.append(f"Avoid another {requirements['variety_needs']['avoid_repetition'][0]} scene")
    
    # Phase 7: Generate scene using simplified template
    from storyteller_lib.config import get_story_config
    config = get_story_config()
    
    # Prepare template variables
    template_vars = {
        'chapter': current_chapter,
        'scene': current_scene,
        'scene_description': scene_context.requirements.get('description', ''),
        'scene_type': requirements['variety_needs']['scene_type'],
        'plot_progressions': requirements['must_happen']['plot_progressions'],
        'character_learning': requirements['must_happen']['character_learning'],
        'previous_ending': scene_context.previous_ending,
        'next_preview': scene_context.next_preview,
        'active_threads': scene_context.active_threads[:3],  # Limit to 3
        'characters': [char.dict() for char in character_context],
        'world_context': world_context,
        'style_guide': style_guide,
        'constraints': constraints,
        'tension_level': requirements['dramatic_needs']['tension'],
        'scene_ending': requirements['dramatic_needs']['ending']
    }
    
    # Use simplified template
    prompt = render_prompt('scene_writing_simplified', 
                          language=config.get('language', DEFAULT_LANGUAGE), 
                          **template_vars)
    
    # Generate scene
    response = llm.invoke([HumanMessage(content=prompt)])
    scene_content = response.content
    
    # Store scene in database
    db_manager = get_db_manager()
    if db_manager:
        db_manager.save_scene_content(current_chapter, current_scene, scene_content)
        logger.info(f"Scene saved to database - {len(scene_content)} characters")
    
    # Update state
    chapters = state.get("chapters", {})
    if str(current_chapter) not in chapters:
        chapters[str(current_chapter)] = {"scenes": {}}
    if "scenes" not in chapters[str(current_chapter)]:
        chapters[str(current_chapter)]["scenes"] = {}
    
    chapters[str(current_chapter)]["scenes"][str(current_scene)] = {
        "db_stored": True,
        "written": True
    }
    
    return {
        "current_scene_content": scene_content,
        "chapters": chapters
    }