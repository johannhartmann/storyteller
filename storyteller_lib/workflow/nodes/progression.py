"""
StoryCraft Agent - Story progression and character management nodes.

This is a refactored version optimized for LangGraph's native edge system,
removing router-specific code that could cause infinite loops.
"""


# Memory manager imports removed - using state and database instead
from langchain_core.messages import AIMessage, RemoveMessage

from storyteller_lib import track_progress
from storyteller_lib.core.config import (
    get_llm_with_structured_output,
)
from storyteller_lib.core.logger import get_logger
# StoryState no longer used - working directly with database
from storyteller_lib.prompts.context import get_context_provider

logger = get_logger(__name__)


def generate_scene_progress_report(
    state: dict, chapter_num: str, scene_num: str
) -> str:
    """Generate a progress report after scene completion.

    Args:
        state: Current story state
        chapter_num: Chapter number just completed
        scene_num: Scene number just completed

    Returns:
        Formatted progress report string
    """
    from storyteller_lib.analysis.statistics import calculate_book_stats
    from storyteller_lib.persistence.database import get_db_manager

    # Get basic scene counts
    chapters = state.get("chapters", {})
    total_chapters = len(chapters)
    current_chapter_data = chapters.get(chapter_num, {})
    scenes_in_chapter = len(current_chapter_data.get("scenes", {}))

    # Calculate progress
    completed_chapters = int(chapter_num) - 1
    completed_scenes_current_chapter = int(scene_num)

    # Get database statistics
    db_manager = get_db_manager()
    stats = {}
    if db_manager:
        try:
            stats = calculate_book_stats(db_manager)
        except Exception as e:
            logger.warning(f"Could not calculate book stats: {e}")

    # Extract stats
    total_words = stats.get("current_words", 0)
    total_pages = stats.get("current_pages", 0)
    avg_scene_words = stats.get("avg_scene_words", 0)

    # Format progress bar
    scenes_per_chapter = scenes_in_chapter  # Assume consistent
    total_scenes = total_chapters * scenes_per_chapter
    completed_scenes = (
        completed_chapters * scenes_per_chapter + completed_scenes_current_chapter
    )
    progress_percentage = (
        (completed_scenes / total_scenes * 100) if total_scenes > 0 else 0
    )

    # Create progress bar
    bar_length = 20
    filled_length = int(bar_length * progress_percentage / 100)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)

    # Build the report
    report = f"""
📊 **Progress Report - Chapter {chapter_num}, Scene {scene_num} Complete**

📖 **Story Progress:**
{bar} {progress_percentage:.1f}%
- Chapter {chapter_num} of {total_chapters}
- Scene {scene_num} of {scenes_in_chapter} in current chapter
- Total scenes completed: {completed_scenes} of {total_scenes}

📝 **Current Statistics:**
- Total words written: {total_words:,}
- Estimated pages: {total_pages}
- Average words per scene: {avg_scene_words:,}
- Words remaining (estimate): {max(0, (total_scenes - completed_scenes) * avg_scene_words):,}

🎯 **Next:** Chapter {chapter_num}, Scene {int(scene_num) + 1}
"""

    # Add milestone messages
    if completed_scenes_current_chapter == scenes_in_chapter:
        report += f"\n🎉 **Chapter {chapter_num} Complete!**"

    if progress_percentage >= 25 and progress_percentage < 26:
        report += "\n📍 **Milestone: 25% Complete!** - The journey is well underway."
    elif progress_percentage >= 50 and progress_percentage < 51:
        report += "\n📍 **Milestone: 50% Complete!** - Halfway through the story!"
    elif progress_percentage >= 75 and progress_percentage < 76:
        report += "\n📍 **Milestone: 75% Complete!** - The climax approaches!"

    return report


def generate_chapter_progress_report(state: dict, chapter_num: str) -> str:
    """Generate a progress report after chapter completion.

    Args:
        state: Current story state
        chapter_num: Chapter number just completed

    Returns:
        Formatted progress report string
    """
    from storyteller_lib.analysis.statistics import calculate_book_stats
    from storyteller_lib.persistence.database import get_db_manager

    # Get basic counts
    chapters = state.get("chapters", {})
    total_chapters = len(chapters)

    # Get database statistics
    db_manager = get_db_manager()
    stats = {}
    if db_manager:
        try:
            stats = calculate_book_stats(db_manager)
        except Exception as e:
            logger.warning(f"Could not calculate book stats: {e}")

    # Extract stats
    total_words = stats.get("current_words", 0)
    total_pages = stats.get("current_pages", 0)
    avg_scene_words = stats.get("avg_scene_words", 0)

    # Calculate progress
    completed_chapters = int(chapter_num)
    progress_percentage = (
        (completed_chapters / total_chapters * 100) if total_chapters > 0 else 0
    )

    # Create progress bar
    bar_length = 20
    filled_length = int(bar_length * progress_percentage / 100)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)

    # Get chapter-specific stats
    chapter_data = chapters.get(chapter_num, {})
    chapter_title = chapter_data.get("title", f"Chapter {chapter_num}")
    scenes_in_chapter = len(chapter_data.get("scenes", {}))

    # Build the report
    report = f"""
🎉 **Chapter {chapter_num} Complete!**

📊 **"{chapter_title}"**
- Scenes written: {scenes_in_chapter}
- Estimated chapter words: {scenes_in_chapter * avg_scene_words:,}

📖 **Overall Progress:**
{bar} {progress_percentage:.1f}%
- Chapters completed: {completed_chapters} of {total_chapters}
- Total words written: {total_words:,}
- Total pages: {total_pages}

📈 **Story Statistics:**
- Average words per scene: {avg_scene_words:,}
- Chapters remaining: {total_chapters - completed_chapters}
- Estimated words remaining: {max(0, (total_chapters - completed_chapters) * scenes_in_chapter * avg_scene_words):,}
"""

    # Add milestone messages for chapter completion
    if completed_chapters == total_chapters // 2:
        report += "\n🌟 **Major Milestone: Halfway through the story!**"
    elif completed_chapters == total_chapters - 1:
        report += "\n🏁 **Almost there! Just one more chapter to go!**"

    # Add next chapter preview if available
    if str(int(chapter_num) + 1) in chapters:
        next_chapter = chapters[str(int(chapter_num) + 1)]
        next_title = next_chapter.get("title", f"Chapter {int(chapter_num) + 1}")
        report += f'\n🎯 **Next Chapter:** "{next_title}"'

    return report


@track_progress
def update_world_elements(state: dict) -> dict:
    """Update world elements based on developments in the current scene."""
    from storyteller_lib.prompts.renderer import render_prompt

    state["chapters"]
    world_elements = state.get("world_elements", {})
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]

    # Get the scene content from temporary state or database
    scene_content = state.get("current_scene_content", "")

    # If not in state, get from database
    if not scene_content:
        from storyteller_lib.prompts.context import get_context_provider

        context_provider = get_context_provider()
        if context_provider:
            scene_data = context_provider.get_scene(
                int(current_chapter), int(current_scene)
            )
            if scene_data:
                scene_content = scene_data.get("content", "")

    if not scene_content:
        logger.warning(
            f"No scene content found for Ch{current_chapter}/Sc{current_scene}"
        )
        return {}

    # Get language from state
    language = state.get("language", "english")

    # Get structured world updates directly

    from pydantic import BaseModel, Field

    class WorldElementUpdate(BaseModel):
        """A single world element update."""

        category: str = Field(
            description="Category of the world element (e.g., GEOGRAPHY, CULTURE)"
        )
        element: str = Field(description="Specific element being updated")
        old_value: str | None = Field(
            None, description="Previous value if updating existing element"
        )
        new_value: str = Field(description="New or updated value")
        reason: str = Field(description="Why this update is needed based on the scene")

    class WorldUpdatesResponse(BaseModel):
        """World updates from a scene."""

        updates: list[WorldElementUpdate] = Field(
            description="List of world element updates"
        )

    # Create prompt for structured world updates
    prompt = render_prompt(
        "world_element_updates",
        language=language,
        scene_content=scene_content,
        current_chapter=current_chapter,
        current_scene=current_scene,
    )

    structured_llm = get_llm_with_structured_output(WorldUpdatesResponse)
    world_updates_response = structured_llm.invoke(prompt)

    # Convert to the expected dictionary format
    world_updates = {}
    if world_updates_response and world_updates_response.updates:
        for update in world_updates_response.updates:
            if update.category not in world_updates:
                world_updates[update.category] = {}
            world_updates[update.category][update.element] = update.new_value

    # World updates are stored in the database world_elements table

    # World state is tracked through the database world_elements table
    # No need for separate memory-based world state tracker

    # Merge with existing world elements
    for category, elements in world_updates.items():
        if category not in world_elements:
            world_elements[category] = {}
        world_elements[category].update(elements)

    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]

    # Create language-specific messages
    if language.lower() == "german":
        new_msg = AIMessage(
            content=f"Ich habe die Weltelemente basierend auf den Entwicklungen in Kapitel {current_chapter}, Szene {current_scene} aktualisiert."
        )
    else:
        new_msg = AIMessage(
            content=f"I've updated the world elements based on developments in Chapter {current_chapter}, Scene {current_scene}."
        )

    return {
        "world_elements": world_elements,
        "messages": [*[RemoveMessage(id=msg_id) for msg_id in message_ids], new_msg],
    }


@track_progress
def update_character_knowledge(state: dict) -> dict:
    """Update what each character knows based on the current scene."""
    from storyteller_lib.prompts.renderer import render_prompt
    from storyteller_lib.universe.characters.knowledge import CharacterKnowledgeManager

    # Get current scene info
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    state["chapters"]
    characters = state["characters"]

    # Get the scene content from temporary state or database
    scene_content = state.get("current_scene_content", "")

    # If not in state, get from database
    if not scene_content:
        context_provider = get_context_provider()
        if context_provider:
            scene_data = context_provider.get_scene(
                int(current_chapter), int(current_scene)
            )
            if scene_data:
                scene_content = scene_data.get("content", "")

    if not scene_content:
        return {}

    # Initialize knowledge manager
    knowledge_manager = CharacterKnowledgeManager()

    # Get structured character updates directly

    from pydantic import BaseModel, Field

    class CharacterKnowledgeUpdate(BaseModel):
        """Knowledge update for a specific character."""

        character_name: str = Field(description="Name of the character")
        new_knowledge: list[str] = Field(
            description="List of new facts/events this character learned"
        )
        knowledge_source: str = Field(
            description="How they learned it (witnessed, told by X, overheard, etc.)"
        )

    class CharacterPresenceUpdate(BaseModel):
        """Presence update for a specific character."""

        character_name: str = Field(description="Name of the character")
        location: str = Field(description="Where the character is now")
        status: str = Field(
            description="What the character is doing/their current state"
        )

    class CharacterUpdatesResponse(BaseModel):
        """All character updates from a scene."""

        knowledge_updates: list[CharacterKnowledgeUpdate] = Field(
            description="Knowledge updates for characters"
        )
        presence_updates: list[CharacterPresenceUpdate] = Field(
            description="Presence/location updates for characters"
        )

    # Get language from state
    language = state.get("language", "english")

    # Create prompt for structured character updates
    prompt = render_prompt(
        "character_updates_structured",
        language=language,
        scene_content=scene_content,
        characters=characters,
        current_chapter=current_chapter,
        current_scene=current_scene,
    )

    structured_llm = get_llm_with_structured_output(CharacterUpdatesResponse)
    updates_response = structured_llm.invoke(prompt)

    # Process knowledge updates
    if updates_response and updates_response.knowledge_updates:
        for update in updates_response.knowledge_updates:
            for fact in update.new_knowledge:
                knowledge_manager.add_knowledge(
                    update.character_name,
                    fact,
                    f"Chapter {current_chapter}, Scene {current_scene}",
                    update.knowledge_source,
                )

    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]

    # Create language-specific messages
    if language.lower() == "german":
        new_msg = AIMessage(
            content=f"Ich habe das Wissen der Charaktere basierend auf Kapitel {current_chapter}, Szene {current_scene} aktualisiert."
        )
    else:
        new_msg = AIMessage(
            content=f"I've updated character knowledge based on Chapter {current_chapter}, Scene {current_scene}."
        )

    return {
        "messages": [*[RemoveMessage(id=msg_id) for msg_id in message_ids], new_msg]
    }


@track_progress
def check_plot_threads(state: dict) -> dict:
    """Check and update plot thread progress based on the current scene."""
    from storyteller_lib.generation.story.plot_threads import update_plot_threads
    from storyteller_lib.persistence.database import get_db_manager

    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]

    logger.info(
        f"Checking plot threads for Chapter {current_chapter}, Scene {current_scene}"
    )

    # Call the update_plot_threads function which returns state updates
    try:
        plot_updates = update_plot_threads(state)

        # The update_plot_threads function returns:
        # - chapters: Updated chapter data with plot threads per scene
        # - plot_threads: The entire plot thread registry
        # - plot_thread_updates: List of thread updates from this scene

        # Save plot thread developments to database
        db_manager = get_db_manager()
        if db_manager and db_manager._db and "plot_thread_updates" in plot_updates:
            # Get the current scene ID from database
            with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT s.id
                    FROM scenes s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE c.chapter_number = ? AND s.scene_number = ?
                """,
                    (int(current_chapter), int(current_scene)),
                )
                result = cursor.fetchone()

                if result:
                    scene_id = result["id"]

                    # Save each plot thread development
                    for update in plot_updates["plot_thread_updates"]:
                        # Get plot thread ID
                        cursor.execute(
                            "SELECT id FROM plot_threads WHERE name = ?",
                            (update["thread_name"],),
                        )
                        thread_result = cursor.fetchone()

                        if thread_result:
                            thread_id = thread_result["id"]
                            db_manager._db.add_plot_thread_development(
                                plot_thread_id=thread_id,
                                scene_id=scene_id,
                                development_type=update["status"],
                                description=update["development"],
                            )
                            logger.info(
                                f"Saved plot thread development: {update['thread_name']} - {update['status']}"
                            )

    except Exception as e:
        logger.error(f"Error updating plot threads: {e}")
        plot_updates = {}

    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]

    # Get language from state
    language = state.get("language", "english")

    # Create more informative message about plot thread updates
    thread_count = len(plot_updates.get("plot_thread_updates", []))
    if language.lower() == "german":
        if thread_count > 0:
            new_msg = AIMessage(
                content=f"Ich habe {thread_count} Handlungsstrang-Entwicklungen in Kapitel {current_chapter}, Szene {current_scene} identifiziert und aktualisiert."
            )
        else:
            new_msg = AIMessage(
                content=f"Keine neuen Handlungsstrang-Entwicklungen in Kapitel {current_chapter}, Szene {current_scene} gefunden."
            )
    else:
        if thread_count > 0:
            new_msg = AIMessage(
                content=f"I've identified and updated {thread_count} plot thread developments in Chapter {current_chapter}, Scene {current_scene}."
            )
        else:
            new_msg = AIMessage(
                content=f"No new plot thread developments found in Chapter {current_chapter}, Scene {current_scene}."
            )

    # Merge the plot updates with the message update
    return {
        **plot_updates,  # This includes chapters, plot_threads, and plot_thread_updates
        "messages": [*[RemoveMessage(id=msg_id) for msg_id in message_ids], new_msg],
    }


@track_progress
def manage_character_arcs(state: dict) -> dict:
    """Update character arcs based on story progression."""
    from storyteller_lib.generation.story.character_arcs import CharacterArcManager

    arc_manager = CharacterArcManager()

    # Get current position in story
    current_chapter = int(state["current_chapter"])
    current_scene = int(state["current_scene"])
    chapters = state["chapters"]
    total_chapters = len(chapters)

    # Calculate story progress percentage
    scenes_per_chapter = len(chapters.get("1", {}).get("scenes", {}))
    total_scenes = total_chapters * scenes_per_chapter
    completed_scenes = (current_chapter - 1) * scenes_per_chapter + current_scene
    progress_percentage = (completed_scenes / total_scenes) if total_scenes > 0 else 0

    # Get the scene content from temporary state or database
    scene_content = state.get("current_scene_content", "")

    # If not in state, get from database
    if not scene_content:
        context_provider = get_context_provider()
        if context_provider:
            scene_data = context_provider.get_scene(current_chapter, current_scene)
            if scene_data:
                scene_content = scene_data.get("content", "")

    # Check each character's arc progress
    characters = state.get("characters", {})
    for char_name, _char_data in characters.items():
        if scene_content:
            # Analyze character's development in this scene
            arc_manager.analyze_scene_for_arc(
                char_name,
                scene_content,
                current_chapter,
                current_scene,
                progress_percentage,
            )

    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]

    # Get language from state
    language = state.get("language", "english")

    # Create language-specific messages
    if language.lower() == "german":
        new_msg = AIMessage(
            content=f"Ich habe die Charakterentwicklung nach Kapitel {current_chapter}, Szene {current_scene} analysiert."
        )
    else:
        new_msg = AIMessage(
            content=f"I've analyzed character arc progression after Chapter {current_chapter}, Scene {current_scene}."
        )

    return {
        "messages": [*[RemoveMessage(id=msg_id) for msg_id in message_ids], new_msg]
    }


@track_progress
def log_story_progress(state: dict) -> dict:
    """Log current progress and statistics to file."""
    from storyteller_lib.analysis.statistics import calculate_book_stats
    from storyteller_lib.persistence.database import get_db_manager
    from storyteller_lib.utils.progress_logger import log_progress

    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]

    # Get database statistics
    db_manager = get_db_manager()
    stats = {}
    if db_manager:
        try:
            stats = calculate_book_stats(db_manager)
        except Exception as e:
            logger.warning(f"Could not calculate book stats: {e}")

    # Log progress
    log_progress(
        "scene_complete",
        {
            "chapter": current_chapter,
            "scene": current_scene,
            "total_words": stats.get("current_words", 0),
            "total_pages": stats.get("current_pages", 0),
            "avg_words_per_scene": stats.get("avg_scene_words", 0),
        },
    )

    return {}


def update_progress_status(state: dict) -> dict:
    """Update progress status and generate progress report in state messages."""
    chapters = state["chapters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]

    # Get language from state
    state.get("language", "english")

    # Generate appropriate progress report
    current_chapter_data = chapters.get(current_chapter, {})
    scenes_in_chapter = len(current_chapter_data.get("scenes", {}))

    if int(current_scene) == scenes_in_chapter:
        # Chapter complete
        report = generate_chapter_progress_report(state, current_chapter)
    else:
        # Scene complete
        report = generate_scene_progress_report(state, current_chapter, current_scene)

    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]

    # Create progress message
    new_msg = AIMessage(content=report)

    return {
        "messages": [*[RemoveMessage(id=msg_id) for msg_id in message_ids], new_msg]
    }
