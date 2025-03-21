"""
StoryCraft Agent - Data models and state definitions.
"""

from typing import Annotated, Dict, List, Union
from typing_extensions import TypedDict
from operator import add

from langchain_core.messages import AIMessage, HumanMessage

class CharacterProfile(TypedDict):
    """Character profile data structure."""
    name: str
    role: str
    backstory: str
    evolution: List[str]
    known_facts: List[str]
    secret_facts: List[str]
    revealed_facts: List[str]
    relationships: Dict[str, str]

class SceneState(TypedDict):
    """Scene state data structure."""
    content: str
    reflection_notes: List[str]

class ChapterState(TypedDict):
    """Chapter state data structure."""
    title: str
    outline: str
    scenes: Dict[str, SceneState]
    reflection_notes: List[str]

class StoryState(TypedDict):
    """Main state schema for the story generation graph."""
    messages: List[Union[HumanMessage, AIMessage]]
    genre: str
    tone: str
    author: str  # Author whose style to emulate
    author_style_guidance: str  # Specific notes on author's style
    global_story: str  # Overall storyline and hero's journey phases
    chapters: Dict[str, ChapterState]  # Keyed by chapter number or identifier
    characters: Dict[str, CharacterProfile]  # Profiles for each character
    revelations: Dict[str, List[str]]  # e.g., {"reader": [...], "characters": [...]}
    creative_elements: Dict[str, Dict]  # Storage for brainstormed ideas
    current_chapter: str  # Track which chapter is being written
    current_scene: str  # Track which scene is being written
    completed: bool  # Flag to indicate if the story is complete
    last_node: str  # Track which node was last executed for routing