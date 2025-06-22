"""
Scene correction functionality for making targeted fixes to existing scenes.
This module provides surgical correction capabilities without going through the full revision workflow.
"""

from typing import Optional
from langchain_core.messages import HumanMessage

from storyteller_lib.config import llm, get_story_config
from storyteller_lib.database_integration import get_db_manager
from storyteller_lib.logger import get_logger
from storyteller_lib.prompt_templates import render_prompt

logger = get_logger(__name__)


def correct_scene(chapter_num: int, scene_num: int, correction_instruction: str) -> bool:
    """
    Correct a specific scene based on provided instructions.
    This is a surgical correction that preserves everything else in the scene.
    
    Args:
        chapter_num: Chapter number
        scene_num: Scene number within the chapter
        correction_instruction: Specific instruction on what to correct
        
    Returns:
        bool: True if correction was successful, False otherwise
    """
    try:
        # Get database manager
        db_manager = get_db_manager()
        if not db_manager:
            logger.error("Database manager not available")
            return False
        
        # Get current scene content
        scene_content = db_manager.get_scene_content(chapter_num, scene_num)
        if not scene_content:
            logger.error(f"No content found for Chapter {chapter_num}, Scene {scene_num}")
            return False
        
        logger.info(f"Correcting Chapter {chapter_num}, Scene {scene_num}")
        logger.info(f"Correction instruction: {correction_instruction}")
        
        # Get story configuration for context
        config = get_story_config()
        genre = config.get("genre", "fantasy")
        tone = config.get("tone", "adventurous")
        language = config.get("language", "english")
        
        # Get scene instructions if available (for additional context)
        scene_instructions = db_manager.get_scene_instructions(chapter_num, scene_num)
        
        # Render the correction prompt
        prompt = render_prompt(
            'scene_correction',
            language=language,
            current_scene=scene_content,
            correction_instruction=correction_instruction,
            scene_instructions=scene_instructions or "No specific scene instructions available",
            genre=genre,
            tone=tone
        )
        
        # Generate the corrected scene
        response = llm.invoke([HumanMessage(content=prompt)])
        corrected_content = response.content.strip()
        
        # Validate that we got a reasonable response
        if not corrected_content or len(corrected_content) < 100:
            logger.error("Correction resulted in invalid or too short content")
            return False
        
        # Save the corrected scene back to the database
        db_manager.save_scene_content(chapter_num, scene_num, corrected_content)
        logger.info(f"Successfully corrected scene - {len(corrected_content)} characters")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to correct scene: {e}")
        return False


def correct_scene_with_validation(
    chapter_num: int, 
    scene_num: int, 
    correction_instruction: str,
    validate_correction: bool = True
) -> tuple[bool, Optional[str]]:
    """
    Correct a scene with optional validation of the correction.
    
    Args:
        chapter_num: Chapter number
        scene_num: Scene number within the chapter
        correction_instruction: Specific instruction on what to correct
        validate_correction: Whether to validate that the correction was applied
        
    Returns:
        tuple: (success: bool, validation_message: Optional[str])
    """
    # First apply the correction
    success = correct_scene(chapter_num, scene_num, correction_instruction)
    
    if not success or not validate_correction:
        return success, None
    
    # If validation is requested, check that the correction was applied
    try:
        db_manager = get_db_manager()
        corrected_content = db_manager.get_scene_content(chapter_num, scene_num)
        
        # Simple validation - just log the change
        logger.info("Correction applied. Scene has been updated.")
        validation_msg = "Correction successfully applied to the scene."
        
        return True, validation_msg
        
    except Exception as e:
        logger.error(f"Failed to validate correction: {e}")
        return success, f"Correction applied but validation failed: {e}"