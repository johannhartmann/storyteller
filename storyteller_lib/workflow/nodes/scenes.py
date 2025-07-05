"""
Simplified scenes module that orchestrates the refactored scene creation workflow.
This replaces the complex scenes.py with a cleaner implementation.
"""


from storyteller_lib.generation.scene.reflection import reflect_on_scene_simplified
from storyteller_lib.generation.scene.revision import revise_scene_simplified
from storyteller_lib.generation.scene.writer import write_scene_simplified


def write_scene(params: dict) -> dict:
    """
    Write a scene using the simplified workflow.
    This is the entry point that replaces the complex write_scene.
    """
    return write_scene_simplified(params)


def reflect_on_scene(params: dict) -> dict:
    """
    Reflect on a scene using simplified quality checks.
    Focuses on 4 key metrics instead of 9.
    """
    return reflect_on_scene_simplified(params)


def revise_scene_if_needed(params: dict) -> dict:
    """
    Revise a scene only if critical issues exist.
    Single pass revision focused on specific problems.
    """
    return revise_scene_simplified(params)
