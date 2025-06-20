"""
Simplified scene writer implementation following the refactoring plan.
This module uses the comprehensive scene context builder for all context gathering.
"""

from typing import Dict
from langchain_core.messages import HumanMessage

from storyteller_lib import track_progress
from storyteller_lib.config import llm
from storyteller_lib.models import StoryState
from storyteller_lib.database_integration import get_db_manager
from storyteller_lib.logger import scene_logger as logger


@track_progress
def write_scene_simplified(state: StoryState) -> Dict:
    """
    Simplified scene writing function using comprehensive context builder.
    This replaces the complex write_scene function with a cleaner implementation.
    """
    current_chapter = int(state.get("current_chapter", 1))
    current_scene = int(state.get("current_scene", 1))
    
    logger.info(f"Writing scene {current_scene} of chapter {current_chapter} (simplified)")
    
    # Use the comprehensive context builder
    from storyteller_lib.scene_context_builder import build_comprehensive_scene_context
    
    context = build_comprehensive_scene_context(current_chapter, current_scene, state)
    
    # Prepare template variables with all context
    template_vars = {
        # All context fields from the comprehensive context
        'context': context,
        # Individual fields for backward compatibility
        'chapter': context.chapter_number,
        'scene': context.scene_number,
        'story_premise': context.story_premise,
        'initial_idea': context.initial_idea,
        'genre': context.genre,
        'tone': context.tone,
        'chapter_title': context.chapter_title,
        'chapter_outline': context.chapter_outline,
        'chapter_themes': context.chapter_themes,
        'scene_description': context.scene_description,
        'scene_type': context.scene_type,
        'dramatic_purpose': context.dramatic_purpose,
        'tension_level': context.tension_level,
        'scene_ending': context.ends_with,
        'plot_progressions': context.plot_progressions,
        'active_threads': context.active_plot_threads[:3],
        'required_characters': context.required_characters,
        'character_learning': context.character_learns,
        'characters': context.character_details,
        'character_relationships': context.character_relationships,
        'locations': context.relevant_locations,
        'world_elements': context.relevant_world_elements,
        'previous_ending': context.previous_scene_ending,
        'previous_summary': context.previous_scenes_summary,
        'next_preview': context.next_scene_preview,
        'forbidden_repetitions': context.forbidden_repetitions,
        'recent_scene_types': context.recent_scene_types,
        'overused_phrases': context.overused_phrases,
        'style_guide': context.style_guide,
        'author': context.author_style
    }
    
    # Use template system for multilingual support
    from storyteller_lib.prompt_templates import render_prompt
    prompt = render_prompt('scene_writing_comprehensive', 
                          language=context.language, 
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