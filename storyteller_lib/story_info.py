"""
StoryCraft Agent - Story information file management.

This module provides functionality to extract data from the StoryState and save it
to a YAML file, as well as load data from a YAML file back into the system.
"""

import os
import yaml
from typing import Dict, Any, Optional
from storyteller_lib.models import StoryState

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

def extract_story_info(state: StoryState) -> Dict[str, Any]:
    """
    Extract story information from the state.
    
    Args:
        state: The current story state
        
    Returns:
        A dictionary containing the extracted story information
    """
    info = {
        "story_info": {
            "title": state.get("title", ""),
            "genre": state.get("genre", ""),
            "tone": state.get("tone", ""),
            "author_style": state.get("author", ""),
            "language": state.get("language", ""),
            "initial_idea": state.get("initial_idea", ""),
            "global_story": state.get("global_story", "")
        },
        "characters": state.get("characters", {}),
        "world_elements": state.get("world_elements", {}),
        "mystery_elements": {},
        "plot_threads": state.get("plot_threads", {}),
        "revelations": state.get("revelations", {}),
        "creative_elements": state.get("creative_elements", {})
    }
    
    # Extract mystery elements if they exist
    if "world_elements" in state and "mystery_elements" in state["world_elements"]:
        info["mystery_elements"] = state["world_elements"]["mystery_elements"]
    
    return info

def save_story_info(state: StoryState, book_filename: str) -> str:
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
    yaml_content = yaml.dump(info, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    # Add a header comment
    yaml_content = f"# Story Information File for {book_filename}\n# This file contains metadata and worldbuilding elements for the story\n\n{yaml_content}"
    
    # Save to file
    with open(info_filename, 'w', encoding='utf-8') as f:
        f.write(yaml_content)
    
    return info_filename

def load_story_info(info_filename: str) -> Dict[str, Any]:
    """
    Load story information from a YAML file.
    
    Args:
        info_filename: The filename of the info file
        
    Returns:
        A dictionary containing the loaded story information
    """
    if not os.path.exists(info_filename):
        return {}
    
    with open(info_filename, 'r', encoding='utf-8') as f:
        yaml_content = f.read()
    
    # Parse YAML
    info = yaml.safe_load(yaml_content)
    
    return info

def update_state_from_info(state: StoryState, info: Dict[str, Any]) -> StoryState:
    """
    Update the state with information from the info dictionary.
    
    Args:
        state: The current story state
        info: The info dictionary loaded from a YAML file
        
    Returns:
        The updated story state
    """
    # Update basic story information
    if "story_info" in info:
        story_info = info["story_info"]
        if "title" in story_info:
            state["title"] = story_info["title"]
        if "genre" in story_info:
            state["genre"] = story_info["genre"]
        if "tone" in story_info:
            state["tone"] = story_info["tone"]
        if "author_style" in story_info:
            state["author"] = story_info["author_style"]
        if "language" in story_info:
            state["language"] = story_info["language"]
        if "initial_idea" in story_info:
            state["initial_idea"] = story_info["initial_idea"]
        if "global_story" in story_info:
            state["global_story"] = story_info["global_story"]
    
    # Update characters
    if "characters" in info:
        state["characters"] = info["characters"]
    
    # Update world elements
    if "world_elements" in info:
        state["world_elements"] = info["world_elements"]
    
    # Update mystery elements
    if "mystery_elements" in info and "world_elements" in state:
        state["world_elements"]["mystery_elements"] = info["mystery_elements"]
    
    # Update plot threads
    if "plot_threads" in info:
        state["plot_threads"] = info["plot_threads"]
    
    # Update revelations
    if "revelations" in info:
        state["revelations"] = info["revelations"]
    
    # Update creative elements
    if "creative_elements" in info:
        state["creative_elements"] = info["creative_elements"]
    
    return state

def load_story_info_from_book(book_filename: str) -> Dict[str, Any]:
    """
    Load story information from the info file corresponding to a book file.
    
    Args:
        book_filename: The filename of the book markdown file
        
    Returns:
        A dictionary containing the loaded story information
    """
    info_filename = get_info_filename(book_filename)
    return load_story_info(info_filename)

def update_state_from_book(state: StoryState, book_filename: str) -> StoryState:
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