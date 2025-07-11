"""Entity relevance detection for StoryCraft Agent.

This module provides intelligent filtering of characters and world elements
based on their relevance to the current scene being generated.
"""

from typing import Any

from pydantic import BaseModel, Field

from storyteller_lib.core.config import llm
from storyteller_lib.core.logger import get_logger

logger = get_logger(__name__)


class RelevantEntities(BaseModel):
    """Model for storing relevant entities for a scene."""

    character_names: list[str] = Field(
        description="Names of characters relevant to this scene"
    )
    locations: list[str] = Field(
        description="Locations mentioned or implied in the scene"
    )
    world_categories: list[str] = Field(
        description="World element categories relevant to the scene"
    )
    plot_elements: list[str] = Field(
        description="Plot elements or objects important to the scene"
    )


def analyze_scene_entities(
    chapter_outline: str,
    scene_description: str,
    all_characters: dict[str, Any],
    world_elements: dict[str, Any],
    language: str,
) -> RelevantEntities:
    """Use LLM to intelligently analyze which entities are relevant to a scene.

    Args:
        chapter_outline: The outline for the current chapter
        scene_description: Description of the current scene
        all_characters: Dictionary of all characters in the story
        world_elements: Dictionary of all world elements

    Returns:
        RelevantEntities object with filtered lists
    """
    # Prepare character list for analysis
    character_list = []
    for char_id, char_data in all_characters.items():
        if char_data:
            name = char_data.get("name", char_id)
            role = char_data.get("role", "unknown")
            character_list.append(f"{name} ({role})")

    # Prepare world categories
    world_categories = list(world_elements.keys()) if world_elements else []

    # Use template system
    from storyteller_lib.prompts.renderer import render_prompt

    # Render the scene entity analysis prompt
    prompt = render_prompt(
        "scene_entity_analysis",
        language=language,
        chapter_outline=chapter_outline,
        scene_description=scene_description,
        available_characters=character_list,
        world_categories=world_categories,
    )

    try:
        # Use structured output
        structured_llm = llm.with_structured_output(RelevantEntities)
        result = structured_llm.invoke(prompt)

        logger.info(
            f"Identified {len(result.character_names)} relevant characters for scene"
        )
        return result

    except Exception as e:
        logger.error(f"Failed to analyze scene entities: {e}")
        # Return minimal safe defaults - no guessing
        return RelevantEntities(
            character_names=[],  # Empty - let the scene writer use defaults
            locations=[],
            world_categories=["geography"],  # Always need basic setting
            plot_elements=[],
        )


def filter_characters_for_scene(
    all_characters: dict[str, Any],
    relevant_entities: RelevantEntities,
    include_limit: int = 5,
) -> dict[str, Any]:
    """Filter characters to only those relevant to the current scene.

    Args:
        all_characters: Dictionary of all characters
        relevant_entities: RelevantEntities object with character names
        include_limit: Maximum number of characters to include

    Returns:
        Filtered dictionary of relevant characters
    """
    filtered_chars = {}

    # First, include explicitly mentioned characters
    for char_name in relevant_entities.character_names[:include_limit]:
        for char_id, char_data in all_characters.items():
            if char_data and char_data.get("name", "") == char_name:
                filtered_chars[char_id] = char_data
            break

    # If we have room, add protagonist/antagonist if not already included
    if len(filtered_chars) < include_limit:
        for char_id, char_data in all_characters.items():
            if len(filtered_chars) >= include_limit:
                break
            if char_data and char_id not in filtered_chars:
                role = str(char_data.get("role", "")).lower()
                if "protagonist" in role or "antagonist" in role:
                    filtered_chars[char_id] = char_data

    logger.info(
        f"Filtered characters from {len(all_characters)} to {len(filtered_chars)} for scene"
    )
    return filtered_chars


def filter_world_elements_for_scene(
    world_elements: dict[str, Any],
    relevant_entities: RelevantEntities,
    include_limit: int = 3,
) -> dict[str, Any]:
    """Filter world elements to only those relevant to the current scene.

    Args:
        world_elements: Dictionary of all world elements
        relevant_entities: RelevantEntities object with world categories
        include_limit: Maximum number of categories to include

    Returns:
        Filtered dictionary of relevant world elements
    """
    filtered_elements = {}

    # Include only the relevant categories
    for category in relevant_entities.world_categories[:include_limit]:
        if category in world_elements:
            filtered_elements[category] = world_elements[category]

    # Always include geography if we have identified specific locations
    if relevant_entities.locations and "geography" in world_elements:
        if "geography" not in filtered_elements:
            filtered_elements["geography"] = world_elements["geography"]

    logger.info(
        f"Filtered world elements from {len(world_elements)} to {len(filtered_elements)} categories for scene"
    )
    return filtered_elements


def get_scene_relevant_plot_threads(
    plot_threads: list[dict[str, Any]],
    relevant_entities: RelevantEntities,
    chapter_num: str,
    scene_num: str,
) -> list[dict[str, Any]]:
    """Filter plot threads to those relevant to the current scene.

    Args:
        plot_threads: List of all plot threads
        relevant_entities: RelevantEntities object
        chapter_num: Current chapter number
        scene_num: Current scene number

    Returns:
        Filtered list of relevant plot threads
    """
    relevant_threads = []

    for thread in plot_threads:
        # Include thread if it involves relevant characters
        thread_chars = thread.get("related_characters", [])
        if any(char in relevant_entities.character_names for char in thread_chars):
            relevant_threads.append(thread)
            continue

        # Include thread if it's a major plot thread
        if thread.get("importance") == "major":
            relevant_threads.append(thread)
            continue

        # Include thread if it was recently developed
        last_chapter = thread.get("last_chapter", "")
        if last_chapter and abs(int(chapter_num) - int(last_chapter)) <= 1:
            relevant_threads.append(thread)

    # Sort by importance
    relevant_threads.sort(
        key=lambda x: (
            0 if x.get("importance") == "major" else 1,
            0 if x.get("status") == "developed" else 1,
        )
    )

    logger.info(
        f"Filtered plot threads from {len(plot_threads)} to {len(relevant_threads)} for scene"
    )
    return relevant_threads[:5]  # Limit to 5 most relevant threads
