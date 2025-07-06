"""
StoryCraft Agent - Plot thread tracking and management.

This module provides functionality to track and manage plot threads
throughout the story generation process using database storage.
"""

from typing import Any

from storyteller_lib.core.config import DEFAULT_LANGUAGE, llm
from storyteller_lib.core.logger import get_logger
from storyteller_lib.persistence.database import get_db_manager

logger = get_logger(__name__)

# Plot thread status options
THREAD_STATUS = {
    "INTRODUCED": "introduced",
    "DEVELOPED": "developed",
    "RESOLVED": "resolved",
    "ABANDONED": "abandoned",
}

# Plot thread importance levels
THREAD_IMPORTANCE = {"MAJOR": "major", "MINOR": "minor", "BACKGROUND": "background"}


def get_plot_threads_from_db() -> list[dict[str, Any]]:
    """Get all plot threads from the database."""
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        return []
    
    try:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, description, thread_type, importance, status,
                       introduced_chapter, introduced_scene, 
                       resolved_chapter, resolved_scene
                FROM plot_threads
                ORDER BY importance DESC, introduced_chapter, introduced_scene
            """)
            
            threads = []
            for row in cursor.fetchall():
                threads.append({
                    "name": row["name"],
                    "description": row["description"],
                    "thread_type": row["thread_type"],
                    "importance": row["importance"],
                    "status": row["status"],
                    "introduced_chapter": row["introduced_chapter"],
                    "introduced_scene": row["introduced_scene"],
                    "resolved_chapter": row["resolved_chapter"],
                    "resolved_scene": row["resolved_scene"],
                })
            return threads
    except Exception as e:
        logger.error(f"Error getting plot threads from database: {e}")
        return []


def get_active_plot_threads() -> list[dict[str, Any]]:
    """Get all active (non-resolved, non-abandoned) plot threads."""
    threads = get_plot_threads_from_db()
    return [
        thread for thread in threads
        if thread["status"] not in [THREAD_STATUS["RESOLVED"], THREAD_STATUS["ABANDONED"]]
    ]


def get_unresolved_major_threads() -> list[dict[str, Any]]:
    """Get all unresolved major plot threads."""
    threads = get_plot_threads_from_db()
    return [
        thread for thread in threads
        if thread["importance"] == THREAD_IMPORTANCE["MAJOR"]
        and thread["status"] not in [THREAD_STATUS["RESOLVED"], THREAD_STATUS["ABANDONED"]]
    ]


def identify_plot_threads_in_scene(
    scene_content: str,
    chapter_num: str,
    scene_num: str,
    characters: dict[str, Any],
    language: str = DEFAULT_LANGUAGE,
) -> list[dict[str, Any]]:
    """
    Identify plot threads introduced or developed in a scene.

    Args:
        scene_content: The content of the scene
        chapter_num: The chapter number
        scene_num: The scene number
        characters: The character data
        language: The language for analysis

    Returns:
        A list of plot thread updates
    """
    # Use template system
    from storyteller_lib.prompts.renderer import render_prompt

    # Render the plot thread identification prompt
    prompt = render_prompt(
        "plot_thread_identification",
        language=language,
        scene_content=scene_content,
        chapter_num=chapter_num,
        scene_num=scene_num,
    )
    try:
        # Define Pydantic models for structured output

        from pydantic import BaseModel, Field

        class PlotThreadUpdate(BaseModel):
            """A plot thread update identified in a scene."""

            thread_name: str = Field(description="A concise name for the plot thread")
            description: str = Field(description="What this thread is about")
            status: str = Field(
                description="The status of the thread: introduced, developed, resolved, or abandoned"
            )
            importance: str = Field(
                description="The importance of the thread: major, minor, or background"
            )
            related_characters: list[str] = Field(
                default_factory=list, description="Characters involved in this thread"
            )
            development: str = Field(
                description="How the thread develops in this specific scene"
            )

        # Create a container class for the list of updates
        class PlotThreadUpdateContainer(BaseModel):
            """Container for plot thread updates."""

            updates: list[PlotThreadUpdate] = Field(
                default_factory=list, description="List of plot thread updates"
            )

        # Create a structured LLM that outputs a PlotThreadUpdateContainer
        from storyteller_lib.core.config import get_llm_with_structured_output

        structured_llm = get_llm_with_structured_output(PlotThreadUpdateContainer)

        # Use the structured LLM to identify plot threads
        thread_container = structured_llm.invoke(prompt)

        # Convert the Pydantic models to dictionaries
        updates = []
        for update in thread_container.updates:
            updates.append(update.dict())

        return updates

    except Exception as e:
        logger.error(f"Error identifying plot threads: {str(e)}")
        return []


def get_active_plot_threads_for_scene(params: dict) -> list[dict[str, Any]]:
    """
    Get plot threads that are active (introduced or developed) for a specific scene.

    Args:
        params: The current parameters with current_chapter and current_scene

    Returns:
        A list of active plot threads
    """
    current_chapter = int(params.get("current_chapter", 1))
    current_scene = int(params.get("current_scene", 1))

    # Get all plot threads
    threads = get_plot_threads_from_db()

    # Filter for threads that have been introduced by this point
    active_threads = []
    for thread in threads:
        # Skip if not yet introduced
        intro_chapter = thread.get("introduced_chapter")
        intro_scene = thread.get("introduced_scene")

        if intro_chapter is None:
            continue

        # Check if introduced before or at current position
        if intro_chapter < current_chapter or (
            intro_chapter == current_chapter and intro_scene <= current_scene
        ):
            # Check if not resolved before current position
            resolved_chapter = thread.get("resolved_chapter")
            if resolved_chapter is None:
                # Not resolved yet
                active_threads.append(thread)
            elif resolved_chapter > current_chapter or (
                resolved_chapter == current_chapter
                and thread.get("resolved_scene", 999) >= current_scene
            ):
                # Resolved after current position
                active_threads.append(thread)

    return active_threads


def update_plot_threads(params: dict) -> dict[str, Any]:
    """
    Update plot threads based on the current scene.

    Args:
        params: The current parameters

    Returns:
        Updates to the state
    """
    current_chapter = params["current_chapter"]
    current_scene = params["current_scene"]

    # Get database manager
    db_manager = get_db_manager()

    if not db_manager or not db_manager._db:
        raise RuntimeError("Database manager not available")

    # Get characters from database
    characters = {}
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT character_id, name, role, backstory, personality
            FROM characters
        """
        )
        for row in cursor.fetchall():
            characters[row["character_id"]] = {
                "name": row["name"],
                "role": row["role"],
                "backstory": row["backstory"],
                "personality": row["personality"],
            }

    # Get the current scene content
    scene_content = db_manager.get_scene_content(
        int(current_chapter), int(current_scene)
    )
    if not scene_content:
        logger.warning(
            f"No scene content found for Chapter {current_chapter}, Scene {current_scene}"
        )
        return {}

    # Get language from database
    language = DEFAULT_LANGUAGE
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT language FROM story_config WHERE id = 1")
        result = cursor.fetchone()
        if result and result["language"]:
            language = result["language"]

    # Identify plot threads in the scene
    plot_updates = identify_plot_threads_in_scene(
        scene_content,
        current_chapter,
        current_scene,
        characters,
        language,
    )

    # Process the updates and store in database
    for update in plot_updates:
        thread_name = update["thread_name"]
        
        # Check if thread exists
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM plot_threads WHERE name = ?", (thread_name,)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing thread
                thread_id = existing["id"]
                
                # Update status
                cursor.execute(
                    "UPDATE plot_threads SET status = ? WHERE id = ?",
                    (update["status"], thread_id)
                )
                
                # If resolved or abandoned, update the resolution chapter/scene
                if update["status"] in [THREAD_STATUS["RESOLVED"], THREAD_STATUS["ABANDONED"]]:
                    cursor.execute(
                        "UPDATE plot_threads SET resolved_chapter = ?, resolved_scene = ? WHERE id = ?",
                        (int(current_chapter), int(current_scene), thread_id)
                    )
                
                # Store development
                cursor.execute(
                    """
                    INSERT INTO plot_thread_developments 
                    (thread_id, chapter, scene, development, development_type)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        thread_id,
                        int(current_chapter),
                        int(current_scene),
                        update["development"],
                        update["status"]
                    )
                )
            else:
                # Create new thread
                cursor.execute(
                    """
                    INSERT INTO plot_threads 
                    (name, description, thread_type, importance, status,
                     introduced_chapter, introduced_scene)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        thread_name,
                        update["description"],
                        "plot",  # Default type
                        update["importance"],
                        update["status"],
                        int(current_chapter),
                        int(current_scene)
                    )
                )
            
            conn.commit()

    logger.info(
        f"Updated {len(plot_updates)} plot threads for Chapter {current_chapter}, Scene {current_scene}"
    )

    return {
        "plot_thread_updates": plot_updates
    }