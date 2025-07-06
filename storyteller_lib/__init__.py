"""
StoryCraft Agent Package - A multi-component story generation system.
"""

# Progress tracking removed - use logging instead


# Export public API - maintain backward compatibility
from storyteller_lib.api.storyteller import generate_story_simplified as generate_story
from storyteller_lib.output.corrections.scene import (
    correct_scene,
    correct_scene_with_validation,
)

__all__ = [
    "generate_story",
    "correct_scene",
    "correct_scene_with_validation",
]
