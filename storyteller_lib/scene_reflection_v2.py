"""
Simplified scene reflection following the refactoring plan.
Reduces 9 quality metrics to 4 key ones and focuses on critical issues only.
"""

from typing import Dict, List, Optional
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from storyteller_lib import track_progress
from storyteller_lib.config import llm, get_story_config
from storyteller_lib.models import StoryState
from storyteller_lib.database_integration import get_db_manager
from storyteller_lib.logger import get_logger

logger = get_logger(__name__)


class SimplifiedReflection(BaseModel):
    """Simplified scene reflection with focus on critical aspects."""
    overall_quality: int = Field(ge=1, le=10, description="Overall scene quality")
    advances_plot: bool = Field(description="Does the scene advance the plot meaningfully?")
    character_consistency: bool = Field(description="Are characters acting consistently?")
    engaging_prose: bool = Field(description="Is the prose engaging and well-written?")
    critical_issues: List[str] = Field(default_factory=list, description="Critical issues that must be fixed")
    needs_revision: bool = Field(description="Does this scene need revision?")


@track_progress
def reflect_on_scene_simplified(state: StoryState) -> Dict:
    """
    Simplified scene reflection focusing on critical quality aspects.
    Replaces complex 9-metric analysis with 4 key checks.
    """
    current_chapter = int(state.get("current_chapter", 1))
    current_scene = int(state.get("current_scene", 1))
    
    logger.info(f"Reflecting on Chapter {current_chapter}, Scene {current_scene} (simplified)")
    
    # Get scene content
    db_manager = get_db_manager()
    if not db_manager:
        raise RuntimeError("Database manager not available")
    
    scene_content = db_manager.get_scene_content(current_chapter, current_scene)
    if not scene_content:
        scene_content = state.get("current_scene_content", "")
    
    if not scene_content:
        raise RuntimeError(f"No content found for Chapter {current_chapter}, Scene {current_scene}")
    
    # Get scene requirements for context
    chapters = state.get("chapters", {})
    scene_requirements = {}
    if str(current_chapter) in chapters and "scenes" in chapters[str(current_chapter)]:
        scene_data = chapters[str(current_chapter)]["scenes"].get(str(current_scene), {})
        scene_requirements = {
            'description': scene_data.get('description', ''),
            'plot_progressions': scene_data.get('plot_progressions', []),
            'character_learns': scene_data.get('character_learns', []),
            'scene_type': scene_data.get('scene_type', 'exploration')
        }
    
    # Get story configuration
    config = get_story_config()
    genre = config.get("genre", "fantasy")
    tone = config.get("tone", "adventurous")
    language = config.get("language", "english")
    
    # Use template for reflection prompt
    from storyteller_lib.prompt_templates import render_prompt
    
    prompt = render_prompt(
        'scene_reflection_simplified',
        language=language,
        scene_content=scene_content,
        scene_description=scene_requirements.get('description', 'Not specified'),
        plot_progressions=scene_requirements.get('plot_progressions', []),
        character_learns=scene_requirements.get('character_learns', []),
        scene_type=scene_requirements.get('scene_type', 'exploration'),
        genre=genre,
        tone=tone,
        chapter=current_chapter,
        scene=current_scene
    )
    
    # Get structured reflection
    structured_llm = llm.with_structured_output(SimplifiedReflection)
    reflection = structured_llm.invoke(prompt)
    
    # Log reflection results
    logger.info(f"Reflection complete - Quality: {reflection.overall_quality}/10, "
                f"Needs revision: {reflection.needs_revision}")
    
    # Store reflection in state (minimal data)
    reflection_data = {
        'quality': reflection.overall_quality,
        'needs_revision': reflection.needs_revision,
        'issues': reflection.critical_issues
    }
    
    # Update chapters with reflection
    if str(current_chapter) not in chapters:
        chapters[str(current_chapter)] = {"scenes": {}}
    if str(current_scene) not in chapters[str(current_chapter)]["scenes"]:
        chapters[str(current_chapter)]["scenes"][str(current_scene)] = {}
    
    chapters[str(current_chapter)]["scenes"][str(current_scene)]["reflection"] = reflection_data
    
    return {
        "chapters": chapters,
        "scene_reflection": reflection.dict(),
        "needs_revision": reflection.needs_revision
    }