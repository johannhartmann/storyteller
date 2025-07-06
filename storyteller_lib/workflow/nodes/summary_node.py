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
def generate_summaries(params: dict) -> dict:
    """
    Generate summaries for the current scene and chapter if needed.
    This is called after scene is finalized (written and potentially revised).
    """
    current_chapter = int(params.get("current_chapter", 1))
    current_scene = int(params.get("current_scene", 1))

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

    # Check if this is the last scene of a chapter by querying database
    is_last_scene = False
    if db_manager and db_manager._db:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            # Get the max scene number for this chapter
            cursor.execute("""
                SELECT MAX(s.scene_number) as max_scene
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE c.chapter_number = ?
            """, (current_chapter,))
            result = cursor.fetchone()
            if result and result["max_scene"]:
                is_last_scene = (current_scene >= result["max_scene"])

    # Generate chapter summary if this is the last scene
    if is_last_scene:
        logger.info(
            f"Last scene of Chapter {current_chapter} - generating chapter summary"
        )
        chapter_summary = generate_chapter_summary(current_chapter, language)
        logger.info(f"Generated chapter summary: {chapter_summary[:100]}...")

    # No state updates needed - summaries are stored directly in database
    return {}
