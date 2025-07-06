"""
StoryCraft Agent - Plot thread tracking and management.

This module provides functionality to track, manage, and ensure resolution of plot threads
throughout the story generation process, using database state management.
"""

from typing import Any

from storyteller_lib.core.config import DEFAULT_LANGUAGE, llm
# StoryState no longer used - working directly with database

# Plot thread status options
THREAD_STATUS = {
    "INTRODUCED": "introduced",
    "DEVELOPED": "developed",
    "RESOLVED": "resolved",
    "ABANDONED": "abandoned",
}

# Plot thread importance levels
THREAD_IMPORTANCE = {"MAJOR": "major", "MINOR": "minor", "BACKGROUND": "background"}


class PlotThread:
    """Class representing a plot thread with tracking information."""

    def __init__(
        self,
        name: str,
        description: str,
        importance: str = THREAD_IMPORTANCE["MINOR"],
        status: str = THREAD_STATUS["INTRODUCED"],
        first_chapter: str = "",
        first_scene: str = "",
        last_chapter: str = "",
        last_scene: str = "",
        related_characters: list[str] = None,
        development_history: list[dict[str, Any]] = None,
    ):
        self.name = name
        self.description = description
        self.importance = importance
        self.status = status
        self.first_chapter = first_chapter
        self.first_scene = first_scene
        self.last_chapter = last_chapter
        self.last_scene = last_scene
        self.related_characters = related_characters or []
        self.development_history = development_history or []

    def to_dict(self) -> dict[str, Any]:
        """Convert the plot thread to a dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "importance": self.importance,
            "status": self.status,
            "first_chapter": self.first_chapter,
            "first_scene": self.first_scene,
            "last_chapter": self.last_chapter,
            "last_scene": self.last_scene,
            "related_characters": self.related_characters,
            "development_history": self.development_history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlotThread":
        """Create a plot thread from a dictionary."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            importance=data.get("importance", THREAD_IMPORTANCE["MINOR"]),
            status=data.get("status", THREAD_STATUS["INTRODUCED"]),
            first_chapter=data.get("first_chapter", ""),
            first_scene=data.get("first_scene", ""),
            last_chapter=data.get("last_chapter", ""),
            last_scene=data.get("last_scene", ""),
            related_characters=data.get("related_characters", []),
            development_history=data.get("development_history", []),
        )

    def add_development(self, chapter: str, scene: str, development: str) -> None:
        """Add a development to the plot thread's history."""
        self.development_history.append(
            {"chapter": chapter, "scene": scene, "development": development}
        )
        self.last_chapter = chapter
        self.last_scene = scene

        # Update status to developed if it was just introduced
        if self.status == THREAD_STATUS["INTRODUCED"]:
            self.status = THREAD_STATUS["DEVELOPED"]

    def resolve(self, chapter: str, scene: str, resolution: str) -> None:
        """Mark the plot thread as resolved."""
        self.development_history.append(
            {
                "chapter": chapter,
                "scene": scene,
                "development": resolution,
                "is_resolution": True,
            }
        )
        self.last_chapter = chapter
        self.last_scene = scene
        self.status = THREAD_STATUS["RESOLVED"]

    def abandon(self, chapter: str, scene: str, reason: str) -> None:
        """Mark the plot thread as abandoned."""
        self.development_history.append(
            {
                "chapter": chapter,
                "scene": scene,
                "development": reason,
                "is_abandonment": True,
            }
        )
        self.last_chapter = chapter
        self.last_scene = scene
        self.status = THREAD_STATUS["ABANDONED"]


class PlotThreadRegistry:
    """Registry for tracking all plot threads in a story."""

    def __init__(self) -> None:
        self.threads = {}

    def add_thread(self, thread: PlotThread) -> None:
        """Add a plot thread to the registry."""
        self.threads[thread.name] = thread

    def get_thread(self, name: str) -> PlotThread | None:
        """Get a plot thread by name."""
        return self.threads.get(name)

    def list_threads(self) -> list[PlotThread]:
        """List all plot threads."""
        return list(self.threads.values())

    def list_active_threads(self) -> list[PlotThread]:
        """List all active (non-resolved, non-abandoned) plot threads."""
        return [
            thread
            for thread in self.threads.values()
            if thread.status
            not in [THREAD_STATUS["RESOLVED"], THREAD_STATUS["ABANDONED"]]
        ]

    def list_unresolved_major_threads(self) -> list[PlotThread]:
        """List all unresolved major plot threads."""
        return [
            thread
            for thread in self.threads.values()
            if thread.importance == THREAD_IMPORTANCE["MAJOR"]
            and thread.status
            not in [THREAD_STATUS["RESOLVED"], THREAD_STATUS["ABANDONED"]]
        ]

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Convert the registry to a dictionary."""
        return {name: thread.to_dict() for name, thread in self.threads.items()}

    @classmethod
    def from_dict(cls, data: dict[str, dict[str, Any]]) -> "PlotThreadRegistry":
        """Create a registry from a dictionary."""
        registry = cls()
        for _name, thread_data in data.items():
            registry.add_thread(PlotThread.from_dict(thread_data))
        return registry

    @classmethod
    def from_params(cls, params: dict) -> "PlotThreadRegistry":
        """Create a registry from the parameters."""
        registry = cls()

        # Get plot threads from params
        plot_threads = params.get("plot_threads", {})

        for _name, thread_data in plot_threads.items():
            registry.add_thread(PlotThread.from_dict(thread_data))

        return registry


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
        structured_llm = llm.with_structured_output(PlotThreadUpdateContainer)

        # Use the structured LLM to identify plot threads
        container = structured_llm.invoke(prompt)

        # Convert Pydantic models to dictionaries
        return [update.dict() for update in container.updates]

    except Exception as e:
        print(f"Error identifying plot threads: {str(e)}")
        return []


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
    from storyteller_lib.persistence.database import get_db_manager

    db_manager = get_db_manager()

    if not db_manager or not db_manager._db:
        raise RuntimeError("Database manager not available")

    # Get characters from database
    characters = {}
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT identifier, name, role, backstory, personality
            FROM characters
        """
        )
        for row in cursor.fetchall():
            characters[row["identifier"]] = {
                "name": row["name"],
                "role": row["role"],
                "backstory": row["backstory"],
                "personality": row["personality"],
            }

    # Get the scene content from database or temporary state
    scene_content = db_manager.get_scene_content(
        int(current_chapter), int(current_scene)
    )
    if not scene_content:
        scene_content = params.get("current_scene_content", "")
        if not scene_content:
            raise RuntimeError(
                f"Scene {current_scene} of chapter {current_chapter} not found"
            )

    # Get language from params
    language = params.get("language", DEFAULT_LANGUAGE)

    # Identify plot threads in the scene
    thread_updates = identify_plot_threads_in_scene(
        scene_content, current_chapter, current_scene, characters, language
    )

    # Load the plot thread registry from params
    registry = PlotThreadRegistry.from_params(params)

    # Process each thread update
    for update in thread_updates:
        thread_name = update["thread_name"]
        thread = registry.get_thread(thread_name)

        if thread is None:
            # Create a new thread if it doesn't exist
            thread = PlotThread(
                name=thread_name,
                description=update["description"],
                importance=update["importance"],
                status=update["status"],
                first_chapter=current_chapter,
                first_scene=current_scene,
                last_chapter=current_chapter,
                last_scene=current_scene,
                related_characters=update["related_characters"],
            )
            registry.add_thread(thread)

        # Update the thread based on its status
        if update["status"] == THREAD_STATUS["RESOLVED"]:
            thread.resolve(current_chapter, current_scene, update["development"])
        elif update["status"] == THREAD_STATUS["ABANDONED"]:
            thread.abandon(current_chapter, current_scene, update["development"])
        else:
            thread.add_development(
                current_chapter, current_scene, update["development"]
            )

    # Add plot thread information to the scene
    scene_threads = {
        update["thread_name"]: {
            "status": update["status"],
            "development": update["development"],
        }
        for update in thread_updates
    }

    # Return updates to the state
    return {
        "chapters": {
            current_chapter: {
                "scenes": {current_scene: {"plot_threads": scene_threads}}
            }
        },
        "plot_threads": registry.to_dict(),  # Store the entire registry in state
        "plot_thread_updates": thread_updates,
    }


def check_plot_thread_resolution(params: dict) -> dict[str, Any]:
    """
    Check if all major plot threads are resolved at the end of the story.

    Args:
        params: The current parameters

    Returns:
        A dictionary with resolution status and unresolved threads
    """
    # Load the plot thread registry from params
    registry = PlotThreadRegistry.from_params(params)

    # Get all unresolved major threads
    unresolved_major_threads = registry.list_unresolved_major_threads()

    # Check if all major threads are resolved
    all_resolved = len(unresolved_major_threads) == 0

    # Format unresolved threads for display
    unresolved_threads = [
        {
            "name": thread.name,
            "description": thread.description,
            "first_appearance": f"Chapter {thread.first_chapter}, Scene {thread.first_scene}",
            "last_appearance": f"Chapter {thread.last_chapter}, Scene {thread.last_scene}",
        }
        for thread in unresolved_major_threads
    ]

    return {
        "all_major_threads_resolved": all_resolved,
        "unresolved_major_threads": unresolved_threads,
    }


def get_active_plot_threads_for_scene(params: dict) -> list[dict[str, Any]]:
    """
    Get active plot threads that should be considered for the current scene.

    Args:
        params: The current parameters

    Returns:
        A list of active plot threads with their details
    """
    params["current_chapter"]
    params["current_scene"]

    # Load the plot thread registry from params
    registry = PlotThreadRegistry.from_params(params)

    # Get all active threads
    active_threads = registry.list_active_threads()

    # Format threads for display
    formatted_threads = [
        {
            "name": thread.name,
            "description": thread.description,
            "importance": thread.importance,
            "status": thread.status,
            "related_characters": thread.related_characters,
            "last_development": (
                thread.development_history[-1]["development"]
                if thread.development_history
                else "None"
            ),
        }
        for thread in active_threads
    ]

    return formatted_threads
