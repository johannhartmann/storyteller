"""
Simplified scenes module that orchestrates the refactored scene creation workflow.
This replaces the complex scenes.py with a cleaner implementation.
"""


from storyteller_lib.core.models import StoryState
from storyteller_lib.generation.scene.reflection import reflect_on_scene_simplified
from storyteller_lib.generation.scene.revision import revise_scene_simplified
from storyteller_lib.generation.scene.writer import write_scene_simplified


def write_scene(state: StoryState) -> dict:
    """
    Write a scene using the simplified workflow.
    This is the entry point that replaces the complex write_scene.
    """
    return write_scene_simplified(state)


def reflect_on_scene(state: StoryState) -> dict:
    """
    Reflect on a scene using simplified quality checks.
    Focuses on 4 key metrics instead of 9.
    """
    return reflect_on_scene_simplified(state)


def revise_scene_if_needed(state: StoryState) -> dict:
    """
    Revise a scene only if critical issues exist.
    Single pass revision focused on specific problems.
    """
    return revise_scene_simplified(state)
