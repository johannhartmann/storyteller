"""
Simplified scene writer implementation using intelligent instruction synthesis.
This module uses LLM to create coherent instructions instead of data concatenation.
"""

from typing import Dict
from langchain_core.messages import HumanMessage

from storyteller_lib import track_progress
from storyteller_lib.config import llm
from storyteller_lib.models import StoryState
from storyteller_lib.database_integration import get_db_manager
from storyteller_lib.logger import scene_logger as logger
from storyteller_lib.instruction_synthesis import generate_scene_level_instructions


@track_progress
def write_scene_simplified(state: StoryState) -> Dict:
    """
    Simplified scene writing function using intelligent instruction synthesis.
    """
    current_chapter = int(state.get("current_chapter", 1))
    current_scene = int(state.get("current_scene", 1))
    
    logger.info(f"Writing scene {current_scene} of chapter {current_chapter} (intelligent synthesis)")
    
    # Get book-level instructions from state (generated once)
    book_instructions = state.get("book_level_instructions", "")
    
    if not book_instructions:
        logger.warning("No book-level instructions found in state. Scene may lack style consistency.")
        # Could regenerate here, but better to fail early
        from storyteller_lib.instruction_synthesis import generate_book_level_instructions
        book_instructions = generate_book_level_instructions(state)
        # Note: Should update state with this, but that's a workflow change
    
    # Generate scene-specific instructions
    scene_instructions = generate_scene_level_instructions(current_chapter, current_scene, state)
    
    # Get language from database
    db_manager = get_db_manager()
    language = "english"
    if db_manager:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT language FROM story_config WHERE id = 1")
            result = cursor.fetchone()
            if result:
                language = result['language'] or 'english'
    
    # Use new intelligent scene writing template
    from storyteller_lib.prompt_templates import render_prompt
    prompt = render_prompt('scene_writing_intelligent',
                          language=language,
                          book_instructions=book_instructions,
                          scene_instructions=scene_instructions,
                          chapter=current_chapter,
                          scene=current_scene)
    
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