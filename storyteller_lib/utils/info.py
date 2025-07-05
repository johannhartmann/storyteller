"""
StoryCraft Agent - Story information file management.

This module provides functionality to extract data from the StoryState and save it
to a YAML file, as well as load data from a YAML file back into the system.
"""

import os
from typing import Any

import yaml

# StoryState no longer used - working directly with database


def get_info_filename(book_filename: str) -> str:
    """
    Generate the info filename based on the book filename.

    Args:
        book_filename: The filename of the book markdown file

    Returns:
        The filename for the corresponding info file
    """
    base, ext = os.path.splitext(book_filename)
    return f"{base}_info.md"


def extract_story_info(state: dict) -> dict[str, Any]:
    """
    Extract story information from the state and database.

    Args:
        state: The current story state

    Returns:
        A dictionary containing the extracted story information
    """
    # Load configuration from database
    from storyteller_lib.core.config import get_story_config

    config = get_story_config()

    # Get title from database
    title = ""
    from storyteller_lib.persistence.database import get_db_manager

    db_manager = get_db_manager()
    if db_manager and db_manager._db:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title, global_story FROM story_config WHERE id = 1")
            result = cursor.fetchone()
            if result:
                title = result["title"] or ""
                global_story = result["global_story"] or ""

    info = {
        "story_info": {
            "title": title,
            "genre": config["genre"],
            "tone": config["tone"],
            "author_style": config["author"],
            "language": config["language"],
            "initial_idea": config["initial_idea"],
            "global_story": global_story,
        },
        "characters": state.get("characters", {}),
        "world_elements": state.get("world_elements", {}),
        "mystery_elements": {},
        "plot_threads": state.get("plot_threads", {}),
        "revelations": state.get("revelations", {}),
        "creative_elements": state.get("creative_elements", {}),
    }

    # Extract mystery elements if they exist
    if "world_elements" in state and "mystery_elements" in state["world_elements"]:
        info["mystery_elements"] = state["world_elements"]["mystery_elements"]

    return info


def save_story_info(state: dict, book_filename: str) -> str:
    """
    Save story information to a YAML file.

    Args:
        state: The current story state
        book_filename: The filename of the book markdown file

    Returns:
        The path to the saved info file
    """
    info_filename = get_info_filename(book_filename)
    info = extract_story_info(state)

    # Convert to YAML
    yaml_content = yaml.dump(
        info, default_flow_style=False, sort_keys=False, allow_unicode=True
    )

    # Add a header comment
    yaml_content = f"# Story Information File for {book_filename}\n# This file contains metadata and worldbuilding elements for the story\n\n{yaml_content}"

    # Save to file
    with open(info_filename, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    return info_filename


def load_story_info(info_filename: str) -> dict[str, Any]:
    """
    Load story information from a YAML file.

    Args:
        info_filename: The filename of the info file

    Returns:
        A dictionary containing the loaded story information
    """
    if not os.path.exists(info_filename):
        return {}

    with open(info_filename, encoding="utf-8") as f:
        yaml_content = f.read()

    # Parse YAML
    info = yaml.safe_load(yaml_content)

    return info


def update_state_from_info(state: dict, info: dict[str, Any]) -> StoryState:
    """
    Update the state and database with information from the info dictionary.

    NOTE: Configuration fields (genre, tone, etc.) are now stored in database only.
    This function updates the database for config and state for workflow data.

    Args:
        state: The current story state
        info: The info dictionary loaded from a YAML file

    Returns:
        The updated story state
    """
    from storyteller_lib.persistence.database import get_db_manager

    db_manager = get_db_manager()

    # Update story configuration in database
    if "story_info" in info and db_manager and db_manager._db:
        story_info = info["story_info"]
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            # Update relevant fields
            if "title" in story_info:
                cursor.execute(
                    "UPDATE story_config SET title = ? WHERE id = 1",
                    (story_info["title"],),
                )
            if "genre" in story_info:
                cursor.execute(
                    "UPDATE story_config SET genre = ? WHERE id = 1",
                    (story_info["genre"],),
                )
            if "tone" in story_info:
                cursor.execute(
                    "UPDATE story_config SET tone = ? WHERE id = 1",
                    (story_info["tone"],),
                )
            if "author_style" in story_info:
                cursor.execute(
                    "UPDATE story_config SET author = ? WHERE id = 1",
                    (story_info["author_style"],),
                )
            if "language" in story_info:
                cursor.execute(
                    "UPDATE story_config SET language = ? WHERE id = 1",
                    (story_info["language"],),
                )
            if "initial_idea" in story_info:
                cursor.execute(
                    "UPDATE story_config SET initial_idea = ? WHERE id = 1",
                    (story_info["initial_idea"],),
                )
            if "global_story" in story_info:
                cursor.execute(
                    "UPDATE story_config SET global_story = ? WHERE id = 1",
                    (story_info["global_story"],),
                )
            conn.commit()

    # Update workflow data in state
    if "characters" in info:
        state["characters"] = info["characters"]

    if "world_elements" in info:
        state["world_elements"] = info["world_elements"]

    if "mystery_elements" in info and "world_elements" in state:
        state["world_elements"]["mystery_elements"] = info["mystery_elements"]

    if "plot_threads" in info:
        state["plot_threads"] = info["plot_threads"]

    if "revelations" in info:
        state["revelations"] = info["revelations"]

    # Note: creative_elements was removed from state in cleanup

    return state


def load_story_info_from_book(book_filename: str) -> dict[str, Any]:
    """
    Load story information from the info file corresponding to a book file.

    Args:
        book_filename: The filename of the book markdown file

    Returns:
        A dictionary containing the loaded story information
    """
    info_filename = get_info_filename(book_filename)
    return load_story_info(info_filename)


def update_state_from_book(state: dict, book_filename: str) -> StoryState:
    """
    Update the state with information from the info file corresponding to a book file.

    Args:
        state: The current story state
        book_filename: The filename of the book markdown file

    Returns:
        The updated story state
    """
    info = load_story_info_from_book(book_filename)
    return update_state_from_info(state, info)
