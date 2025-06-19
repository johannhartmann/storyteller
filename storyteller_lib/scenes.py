"""StoryCraft Agent - Scene generation orchestration.

This module serves as the main entry point for scene generation,
delegating to specialized modules for each phase of the process.
"""

# Local imports
from storyteller_lib.scene_reflection import reflect_on_scene
from storyteller_lib.scene_revision import revise_scene_if_needed
from storyteller_lib.scene_writer import write_scene

# Re-export the main scene generation functions
__all__ = [
    'write_scene', 
    'reflect_on_scene',
    'revise_scene_if_needed'
]