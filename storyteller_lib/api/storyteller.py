"""
Simplified storyteller implementation using the refactored workflow.
This provides the main entry point for story generation with reduced complexity.
"""

import time
from typing import Dict, Optional, Tuple

from storyteller_lib.core.config import get_story_config
from storyteller_lib.persistence.database import get_db_manager
from storyteller_lib.workflow.graph import create_simplified_graph
from storyteller_lib.core.logger import get_logger
from storyteller_lib.core.models import StoryState

logger = get_logger(__name__)


def generate_story_simplified(
    genre: str,
    tone: str,
    num_chapters: int = 10,
    author: Optional[str] = None,
    language: str = "english",
    initial_idea: Optional[str] = None,
    progress_log_path: Optional[str] = None,
    narrative_structure: str = "auto",
    story_length: str = "auto",
    target_chapters: Optional[int] = None,
    target_words_per_scene: Optional[int] = None,
    target_pages: Optional[int] = None,
    recursion_limit: int = 200,
    research_worldbuilding: bool = False,
) -> Tuple[str, StoryState]:
    """
    Generate a story using the simplified workflow.

    Args:
        genre: Story genre (fantasy, sci-fi, mystery, etc.)
        tone: Story tone (adventurous, dark, humorous, etc.)
        num_chapters: Number of chapters to generate (default: 10) - deprecated, use target_chapters
        author: Optional author style to emulate
        language: Language for the story (default: english)
        initial_idea: Optional initial story idea
        progress_log_path: Optional path for progress log file
        narrative_structure: Narrative structure to use or "auto" (default: auto)
        story_length: Story length category or "auto" (default: auto) - deprecated, use target_pages
        target_chapters: Override number of chapters (None = auto-determine) - deprecated, use target_pages
        target_words_per_scene: Override words per scene (None = auto-determine) - deprecated, use target_pages
        target_pages: Target number of pages for the story (None = auto-determine based on complexity)
        recursion_limit: Maximum recursion depth for the LangGraph workflow (default: 200)
        research_worldbuilding: Enable research-driven world building (requires TAVILY_API_KEY)

    Returns:
        Tuple of (compiled story markdown, final state)
    """
    start_time = time.time()

    logger.info(
        f"Starting simplified story generation - Genre: {genre}, Tone: {tone}, "
        f"Chapters: {num_chapters}, Language: {language}"
    )

    # Initialize progress logger if requested
    if progress_log_path:
        from storyteller_lib.utils.progress_logger import initialize_progress_logger

        initialize_progress_logger(progress_log_path)
        logger.info(f"Progress logging enabled: {progress_log_path}")

    # Create initial state
    initial_state: StoryState = {
        "messages": [],
        "chapters": {},
        "characters": {},
        "world_elements": {},
        "plot_threads": {},
        "revelations": {},
        "current_chapter": "",
        "current_scene": "",
        "current_scene_content": "",
        "scene_reflection": {},
        "scene_elements": {},
        "active_plot_threads": [],
        "book_level_instructions": "",
        "author_style_guidance": "",
        "completed": False,
        "last_node": "",
        "manuscript_review_completed": False,
        "manuscript_review_results": {},
        "final_story": "",
    }

    # Initialize story configuration in database
    db_manager = get_db_manager()
    if db_manager and db_manager._db:
        # Create a placeholder title - will be updated when outline is generated
        placeholder_title = f"{tone.title()} {genre.title()} Story"
        db_manager._db.initialize_story_config(
            title=placeholder_title,
            genre=genre,
            tone=tone,
            author=author,
            language=language,
            initial_idea=initial_idea or "",
            narrative_structure=narrative_structure,
            story_length=story_length,
            target_chapters=target_chapters,
            target_words_per_scene=target_words_per_scene,
            target_pages=target_pages,
            research_worldbuilding=research_worldbuilding,
        )
        logger.info("Initialized story configuration in database")

    # Create and run the simplified graph
    graph = create_simplified_graph()

    # Configure with recursion limit
    config = {
        "recursion_limit": recursion_limit,  # Use the provided recursion limit
        "configurable": {"thread_id": f"story_{genre}_{tone}_{int(time.time())}"},
    }

    try:
        # Run the graph
        logger.info("Executing simplified story generation graph...")
        result = graph.invoke(initial_state, config)

        # Get the compiled story
        db_manager = get_db_manager()
        if db_manager:
            story = db_manager.compile_story()
        else:
            story = result.get("compiled_story", "")

        elapsed_time = time.time() - start_time
        logger.info(f"Story generation completed in {elapsed_time:.2f} seconds")

        # Log statistics
        word_count = len(story.split())
        logger.info(
            f"Generated story statistics: {word_count} words, "
            f"{len(result.get('chapters', {}))} chapters"
        )

        return story, result

    except Exception as e:
        logger.error(
            f"Error during simplified story generation: {str(e)}", exc_info=True
        )

        # Try to recover partial story
        try:
            db_manager = get_db_manager()
            if db_manager:
                partial_story = db_manager.compile_story()
                if partial_story:
                    logger.info("Partial story recovered from database")
                    return partial_story, initial_state
        except Exception as recovery_error:
            logger.error(f"Failed to recover partial story: {str(recovery_error)}")

        raise
