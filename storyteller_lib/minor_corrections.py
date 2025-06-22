"""
Minor corrections module for applying targeted fixes to scenes.
This module handles non-critical issues that don't warrant a full revision.
"""

from typing import Dict, List
from storyteller_lib import track_progress
from storyteller_lib.models import StoryState
from storyteller_lib.scene_correction import correct_scene
from storyteller_lib.logger import get_logger

logger = get_logger(__name__)


@track_progress
def apply_minor_corrections(state: StoryState) -> Dict:
    """
    Apply minor corrections to a scene using targeted fixes.
    
    This node is called when a scene has minor issues that don't require
    a full revision. It uses the correct_scene function to apply surgical
    corrections while preserving the rest of the scene.
    
    Args:
        state: Current story state
        
    Returns:
        Updated state dictionary
    """
    current_chapter = int(state.get("current_chapter", 1))
    current_scene = int(state.get("current_scene", 1))
    
    # Check if minor corrections are needed
    needs_minor_corrections = state.get("needs_minor_corrections", False)
    minor_issues = state.get("minor_issues", [])
    
    if not needs_minor_corrections or not minor_issues:
        logger.info(f"Chapter {current_chapter}, Scene {current_scene} - No minor corrections needed")
        return {}
    
    logger.info(f"Applying minor corrections to Chapter {current_chapter}, Scene {current_scene}")
    logger.info(f"Minor issues to fix: {len(minor_issues)}")
    
    # Combine minor issues into a single correction instruction
    correction_instruction = create_correction_instruction(minor_issues)
    
    # Apply the correction
    success = correct_scene(
        chapter_num=current_chapter,
        scene_num=current_scene,
        correction_instruction=correction_instruction
    )
    
    if success:
        logger.info(f"Successfully applied minor corrections to Chapter {current_chapter}, Scene {current_scene}")
        
        # Update state to reflect corrections were applied
        chapters = state.get("chapters", {})
        if str(current_chapter) in chapters and "scenes" in chapters[str(current_chapter)]:
            if str(current_scene) in chapters[str(current_chapter)]["scenes"]:
                chapters[str(current_chapter)]["scenes"][str(current_scene)]["minor_corrections_applied"] = True
        
        # Clear the minor corrections flag
        return {
            "chapters": chapters,
            "needs_minor_corrections": False,
            "minor_issues": []
        }
    else:
        logger.error(f"Failed to apply minor corrections to Chapter {current_chapter}, Scene {current_scene}")
        # Continue anyway - minor issues shouldn't block progress
        return {
            "needs_minor_corrections": False,
            "minor_issues": []
        }


def create_correction_instruction(minor_issues: List[str]) -> str:
    """
    Create a comprehensive correction instruction from a list of minor issues.
    
    Args:
        minor_issues: List of minor issues identified during reflection
        
    Returns:
        A single correction instruction addressing all issues
    """
    if len(minor_issues) == 1:
        return f"Please fix the following minor issue: {minor_issues[0]}"
    
    # For multiple issues, create a structured instruction
    instruction_parts = ["Please address the following minor issues in the scene:"]
    
    for i, issue in enumerate(minor_issues, 1):
        instruction_parts.append(f"{i}. {issue}")
    
    instruction_parts.append("\nMake minimal changes to fix only these specific issues while preserving everything else about the scene.")
    
    return "\n".join(instruction_parts)


def should_apply_minor_corrections(state: StoryState) -> bool:
    """
    Helper function to determine if minor corrections should be applied.
    
    Args:
        state: Current story state
        
    Returns:
        True if minor corrections should be applied, False otherwise
    """
    # Don't apply if there's a need for full revision
    if state.get("needs_revision", False):
        return False
    
    # Apply if there are minor issues flagged
    return state.get("needs_minor_corrections", False) and bool(state.get("minor_issues", []))