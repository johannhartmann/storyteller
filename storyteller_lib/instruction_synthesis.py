"""
Intelligent instruction synthesis for story writing.
Uses LLM to create coherent, structured instructions instead of string concatenation.
"""

from typing import Dict, Optional
from langchain_core.messages import HumanMessage

from storyteller_lib.config import llm
from storyteller_lib.models import StoryState
from storyteller_lib.database_integration import get_db_manager
from storyteller_lib.logger import get_logger
from storyteller_lib.prompt_templates import render_prompt

logger = get_logger(__name__)


def generate_book_level_instructions(state: StoryState) -> str:
    """
    Generate comprehensive writing instructions for the entire book.
    This synthesizes genre, tone, and author style into coherent guidance.
    
    Args:
        state: Current story state containing configuration and style analysis
        
    Returns:
        Coherent writing instructions for the book
    """
    logger.info("Generating book-level writing instructions")
    
    # Load configuration from database
    db_manager = get_db_manager()
    if not db_manager:
        raise RuntimeError("Database manager not available")
        
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT genre, tone, author, language, initial_idea
            FROM story_config WHERE id = 1
        """)
        config = cursor.fetchone()
    
    genre = config['genre'] or 'fantasy'
    tone = config['tone'] or 'adventurous'
    author = config['author'] or ''
    language = config['language'] or 'english'
    initial_idea = config['initial_idea'] or ''
    
    # Get author style guidance from state
    author_style_guidance = state.get("author_style_guidance", "")
    
    # Prepare template variables
    template_vars = {
        'genre': genre,
        'tone': tone,
        'author': author,
        'author_style_guidance': author_style_guidance,
        'initial_idea': initial_idea
    }
    
    # Use template to create synthesis prompt
    prompt = render_prompt(
        'synthesize_book_instructions',
        language=language,
        **template_vars
    )
    
    # Generate synthesized instructions
    response = llm.invoke([HumanMessage(content=prompt)])
    book_instructions = response.content
    
    logger.info(f"Generated book-level instructions ({len(book_instructions)} chars)")
    return book_instructions


def generate_scene_level_instructions(
    chapter: int,
    scene: int, 
    state: StoryState
) -> str:
    """
    Generate specific instructions for a scene by synthesizing all relevant context.
    
    Args:
        chapter: Chapter number
        scene: Scene number
        state: Current story state
        
    Returns:
        Coherent instructions for writing this specific scene
    """
    logger.info(f"Generating scene-level instructions for Chapter {chapter}, Scene {scene}")
    
    # Get database manager
    db_manager = get_db_manager()
    if not db_manager:
        raise RuntimeError("Database manager not available")
    
    # Gather all scene-relevant data using existing functions
    from storyteller_lib.scene_context_builder import (
        _get_story_context,
        _get_chapter_context,
        _get_scene_specifications,
        _get_plot_context,
        _get_character_context,
        _get_world_context,
        _get_sequence_context,
        _get_writing_constraints
    )
    
    # 1. Get story context
    story_context = _get_story_context(db_manager, state)
    
    # 2. Get chapter context
    chapter_context = _get_chapter_context(db_manager, chapter)
    
    # 3. Get scene specifications
    scene_specs = _get_scene_specifications(state, chapter, scene)
    
    # 4. Get plot context
    plot_context = _get_plot_context(db_manager, scene_specs)
    
    # 5. Get character context
    character_context = _get_character_context(
        db_manager,
        scene_specs['required_characters'],
        scene_specs['description']
    )
    
    # 6. Get world context
    world_context = _get_world_context(
        db_manager,
        scene_specs['description'],
        character_context['locations']
    )
    
    # 7. Get sequence context
    sequence_context = _get_sequence_context(db_manager, chapter, scene, state)
    
    # 8. Get writing constraints
    constraints = _get_writing_constraints(db_manager, chapter, scene)
    
    # Prepare all data for synthesis
    template_vars = {
        # Story level
        'story_premise': story_context['premise'],
        'initial_idea': story_context['initial_idea'],
        
        # Chapter level
        'chapter_number': chapter,
        'chapter_title': chapter_context['title'],
        'chapter_outline': chapter_context['outline'],
        'chapter_themes': chapter_context['themes'],
        
        # Scene specifications
        'scene_number': scene,
        'scene_description': scene_specs['description'],
        'scene_type': scene_specs['scene_type'],
        'dramatic_purpose': scene_specs['dramatic_purpose'],
        'tension_level': scene_specs['tension_level'],
        'ends_with': scene_specs['ends_with'],
        
        # Plot
        'plot_progressions': plot_context['progressions'],
        'active_threads': plot_context['active_threads'],
        
        # Characters
        'required_characters': scene_specs['required_characters'],
        'character_learns': scene_specs['character_learns'],
        'characters': character_context['characters'],
        'relationships': character_context['relationships'],
        
        # World
        'locations': world_context['locations'],
        'world_elements': world_context['elements'],
        
        # Sequence
        'previous_ending': sequence_context['previous_ending'],
        'previous_summary': sequence_context['previous_summary'],
        'next_preview': sequence_context['next_preview'],
        
        # Constraints
        'forbidden_repetitions': constraints['forbidden_repetitions'],
        'recent_scene_types': constraints['recent_scene_types'],
        'overused_phrases': constraints['overused_phrases']
    }
    
    # Use template to create synthesis prompt
    prompt = render_prompt(
        'synthesize_scene_instructions',
        language=story_context['language'],
        **template_vars
    )
    
    # Generate synthesized instructions
    response = llm.invoke([HumanMessage(content=prompt)])
    scene_instructions = response.content
    
    logger.info(f"Generated scene instructions ({len(scene_instructions)} chars)")
    return scene_instructions