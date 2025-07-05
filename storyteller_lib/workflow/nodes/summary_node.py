"""
Node for generating scene and chapter summaries in the story workflow.
"""


from storyteller_lib import track_progress
from storyteller_lib.core.config import get_story_config
from storyteller_lib.core.logger import get_logger
# StoryState no longer used - working directly with database
from storyteller_lib.output.summary import (
    generate_chapter_summary,
    generate_scene_summary,
)
from storyteller_lib.persistence.database import get_db_manager

logger = get_logger(__name__)


@track_progress
def generate_summaries(state: dict) -> dict:
    """
    Generate summaries for the current scene and chapter if needed.
    This is called after scene is finalized (written and potentially revised).
    """
    current_chapter = int(state.get("current_chapter", 1))
    current_scene = int(state.get("current_scene", 1))

    logger.info(
        f"Generating summaries for Chapter {current_chapter}, Scene {current_scene}"
    )

    # Get database manager
    db_manager = get_db_manager()
    if not db_manager:
        logger.error("Database manager not available for summary generation")
        return {}

    # Get language
    config = get_story_config()
    language = config.get("language", "english")

    # Get final scene content
    scene_content = db_manager.get_scene_content(current_chapter, current_scene)
    if not scene_content:
        logger.warning(
            f"No scene content found for Chapter {current_chapter}, Scene {current_scene}"
        )
        return {}

    # Generate scene summary
    scene_summary = generate_scene_summary(
        current_chapter, current_scene, scene_content, language
    )
    logger.info(f"Generated scene summary: {scene_summary[:100]}...")

    # Check if this is the last scene of a chapter
    chapters = state.get("chapters", {})
    chapter_data = chapters.get(str(current_chapter), {})
    scenes = chapter_data.get("scenes", {})

    # Check if we're at the last scene of the chapter
    is_last_scene = True
    for scene_num in scenes:
        if int(scene_num) > current_scene:
            is_last_scene = False
            break

    # Generate chapter summary if this is the last scene
    if is_last_scene:
        logger.info(
            f"Last scene of Chapter {current_chapter} - generating chapter summary"
        )
        chapter_summary = generate_chapter_summary(current_chapter, language)
        logger.info(f"Generated chapter summary: {chapter_summary[:100]}...")

    # No state updates needed - summaries are stored directly in database
    return {}
