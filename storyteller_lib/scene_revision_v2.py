"""
Simplified scene revision following the refactoring plan.
Only revises when critical issues are present, with a single focused pass.
"""

from typing import Dict
from langchain_core.messages import HumanMessage

from storyteller_lib import track_progress
from storyteller_lib.config import llm, get_story_config
from storyteller_lib.models import StoryState
from storyteller_lib.database_integration import get_db_manager
from storyteller_lib.logger import get_logger

logger = get_logger(__name__)


@track_progress
def revise_scene_simplified(state: StoryState) -> Dict:
    """
    Simplified scene revision - only revises if critical issues exist.
    Maximum one revision pass, focused on specific issues.
    """
    current_chapter = int(state.get("current_chapter", 1))
    current_scene = int(state.get("current_scene", 1))
    
    # Check if revision is needed
    scene_reflection = state.get("scene_reflection", {})
    if not scene_reflection.get("needs_revision", False):
        logger.info(f"Chapter {current_chapter}, Scene {current_scene} - No revision needed")
        return {}
    
    logger.info(f"Revising Chapter {current_chapter}, Scene {current_scene}")
    
    # Get scene content
    db_manager = get_db_manager()
    if not db_manager:
        raise RuntimeError("Database manager not available")
    
    scene_content = db_manager.get_scene_content(current_chapter, current_scene)
    if not scene_content:
        raise RuntimeError(f"No content found for Chapter {current_chapter}, Scene {current_scene}")
    
    # Get critical issues
    critical_issues = scene_reflection.get("critical_issues", [])
    if not critical_issues:
        logger.info("No critical issues identified, skipping revision")
        return {}
    
    # Get scene requirements
    chapters = state.get("chapters", {})
    scene_requirements = {}
    if str(current_chapter) in chapters and "scenes" in chapters[str(current_chapter)]:
        scene_data = chapters[str(current_chapter)]["scenes"].get(str(current_scene), {})
        scene_requirements = {
            'description': scene_data.get('description', ''),
            'plot_progressions': scene_data.get('plot_progressions', []),
            'character_learns': scene_data.get('character_learns', [])
        }
    
    # Get story configuration
    config = get_story_config()
    genre = config.get("genre", "fantasy")
    tone = config.get("tone", "adventurous")
    
    # Create focused revision prompt
    prompt = f"""
Revise this scene to fix the identified critical issues.

CURRENT SCENE:
{scene_content}

CRITICAL ISSUES TO FIX:
{chr(10).join(f'- {issue}' for issue in critical_issues)}

SCENE REQUIREMENTS TO MAINTAIN:
- Description: {scene_requirements.get('description', '')}
- Plot progressions: {', '.join(scene_requirements.get('plot_progressions', []))}
- Character learning: {', '.join(scene_requirements.get('character_learns', []))}

STORY CONTEXT:
- Genre: {genre}
- Tone: {tone}

REVISION INSTRUCTIONS:
1. Fix ONLY the critical issues identified above
2. Maintain all plot progressions and character developments
3. Keep what works well in the current scene
4. Preserve the scene's length and pacing
5. Ensure the revision flows naturally

Write the revised scene:
"""
    
    # Generate revision
    response = llm.invoke([HumanMessage(content=prompt)])
    revised_content = response.content
    
    # Save revised scene
    db_manager.save_scene_content(current_chapter, current_scene, revised_content)
    logger.info(f"Revised scene saved - {len(revised_content)} characters")
    
    # Update state
    chapters[str(current_chapter)]["scenes"][str(current_scene)]["revised"] = True
    
    # Clear reflection data to prevent re-revision
    if "scene_reflection" in state:
        state["scene_reflection"]["needs_revision"] = False
    
    return {
        "current_scene_content": revised_content,
        "chapters": chapters
    }