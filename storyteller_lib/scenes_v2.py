"""
Simplified scenes module that orchestrates the refactored scene creation workflow.
This replaces the complex scenes.py with a cleaner implementation.
"""

from typing import Dict

from storyteller_lib.models import StoryState
from storyteller_lib.scene_writer_v2 import write_scene_simplified
from storyteller_lib.scene_reflection_v2 import reflect_on_scene_simplified
from storyteller_lib.scene_revision_v2 import revise_scene_simplified


def write_scene(state: StoryState) -> Dict:
    """
    Write a scene using the simplified workflow.
    This is the entry point that replaces the complex write_scene.
    """
    return write_scene_simplified(state)


def reflect_on_scene(state: StoryState) -> Dict:
    """
    Reflect on a scene using simplified quality checks.
    Focuses on 4 key metrics instead of 9.
    """
    return reflect_on_scene_simplified(state)


def revise_scene_if_needed(state: StoryState) -> Dict:
    """
    Revise a scene only if critical issues exist.
    Single pass revision focused on specific problems.
    """
    return revise_scene_simplified(state)