"""
Simplified scene revision following the refactoring plan.
Only revises when critical issues are present, with a single focused pass.
"""


from langchain_core.messages import HumanMessage

from storyteller_lib import track_progress
from storyteller_lib.core.config import get_story_config, llm
from storyteller_lib.core.logger import get_logger
# StoryState no longer used - working directly with database
from storyteller_lib.persistence.database import get_db_manager

logger = get_logger(__name__)


@track_progress
def revise_scene_simplified(params: dict) -> dict:
    """
    Simplified scene revision - only revises if critical issues exist.
    Maximum one revision pass, focused on specific issues.
    """
    current_chapter = int(params.get("current_chapter", 1))
    current_scene = int(params.get("current_scene", 1))

    # Check if revision is needed
    scene_reflection = params.get("scene_reflection", {})
    needs_revision_flag = params.get("needs_revision", False)

    logger.info(
        f"Chapter {current_chapter}, Scene {current_scene} - Revision check: "
        f"needs_revision={needs_revision_flag}, "
        f"scene_reflection.needs_revision={scene_reflection.get('needs_revision', False)}"
    )

    # Check both the top-level flag and the scene_reflection flag
    if not needs_revision_flag and not scene_reflection.get("needs_revision", False):
        logger.info(
            f"Chapter {current_chapter}, Scene {current_scene} - No revision needed"
        )
        return {}

    logger.info(f"Revising Chapter {current_chapter}, Scene {current_scene}")

    # Get scene content
    db_manager = get_db_manager()
    if not db_manager:
        raise RuntimeError("Database manager not available")

    scene_content = db_manager.get_scene_content(current_chapter, current_scene)
    if not scene_content:
        raise RuntimeError(
            f"No content found for Chapter {current_chapter}, Scene {current_scene}"
        )

    # Get critical issues
    critical_issues = scene_reflection.get("critical_issues", [])
    if not critical_issues:
        logger.info("No critical issues identified, skipping revision")
        return {}

    # Get scene requirements from database
    from storyteller_lib.generation.scene.context import _get_scene_specifications
    
    scene_requirements = _get_scene_specifications(params, current_chapter, current_scene)

    # Get story configuration
    config = get_story_config()
    genre = config.get("genre", "fantasy")
    tone = config.get("tone", "adventurous")

    # Use template for revision prompt
    from storyteller_lib.prompts.renderer import render_prompt

    prompt = render_prompt(
        "scene_revision_simplified",
        language=config.get("language", "english"),
        scene_content=scene_content,
        critical_issues=critical_issues,
        scene_description=scene_requirements.get("description", ""),
        plot_progressions=scene_requirements.get("plot_progressions", []),
        character_learns=scene_requirements.get("character_learns", []),
        genre=genre,
        tone=tone,
    )

    # Generate revision
    response = llm.invoke([HumanMessage(content=prompt)])
    revised_content = response.content

    # Save revised scene
    db_manager.save_scene_content(current_chapter, current_scene, revised_content)
    logger.info(f"Revised scene saved - {len(revised_content)} characters")

    # Update state
    chapters[str(current_chapter)]["scenes"][str(current_scene)]["revised"] = True

    # Clear reflection data to prevent re-revision
    # We need to clear the needs_revision flag at the top level
    # because that's what the graph condition checks
    return {
        "current_scene_content": revised_content,
        "chapters": chapters,
        "needs_revision": False,  # Clear the flag that the graph checks
    }
