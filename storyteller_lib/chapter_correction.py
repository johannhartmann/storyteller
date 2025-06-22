"""
Chapter correction functionality for making targeted fixes to entire chapters.
This module provides correction capabilities that treat the chapter as a cohesive unit.
"""

from typing import List, Dict, Tuple, Optional, Any
from langchain_core.messages import HumanMessage
import re

from storyteller_lib.config import llm, get_story_config
from storyteller_lib.database_integration import get_db_manager
from storyteller_lib.logger import get_logger
from storyteller_lib.prompt_templates import render_prompt
from storyteller_lib.models import ChapterCorrectionOutput

logger = get_logger(__name__)


def correct_chapter(chapter_num: int, correction_instruction: str) -> bool:
    """
    Correct an entire chapter based on provided instructions.
    This concatenates all scenes, applies corrections, and splits back into scenes.
    
    Args:
        chapter_num: Chapter number
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
        
        # Get all scenes in the chapter
        scenes = get_chapter_scenes(chapter_num)
        if not scenes:
            logger.error(f"No scenes found for Chapter {chapter_num}")
            return False
        
        logger.info(f"Correcting Chapter {chapter_num} ({len(scenes)} scenes)")
        logger.info(f"Correction instruction: {correction_instruction}")
        
        # Get story configuration for context
        config = get_story_config()
        genre = config.get("genre", "fantasy")
        tone = config.get("tone", "adventurous")
        language = config.get("language", "english")
        
        # Get chapter metadata
        chapter_info = get_chapter_info(chapter_num)
        chapter_title = chapter_info.get('title', f'Chapter {chapter_num}')
        chapter_outline = chapter_info.get('outline', '')
        
        # Concatenate all scenes with clear markers
        full_chapter_content = ""
        scene_boundaries = []
        
        for scene_num, scene_content in scenes:
            scene_marker = f"[SCENE {scene_num} START]"
            scene_end_marker = f"[SCENE {scene_num} END]"
            
            full_chapter_content += f"\n\n{scene_marker}\n\n"
            full_chapter_content += scene_content
            full_chapter_content += f"\n\n{scene_end_marker}\n\n"
            
            scene_boundaries.append({
                'scene_num': scene_num,
                'start_marker': scene_marker,
                'end_marker': scene_end_marker
            })
        
        # Render the chapter correction prompt
        prompt = render_prompt(
            'chapter_correction',
            language=language,
            chapter_number=chapter_num,
            chapter_title=chapter_title,
            chapter_outline=chapter_outline,
            current_chapter_content=full_chapter_content,
            correction_instruction=correction_instruction,
            scene_count=len(scenes),
            genre=genre,
            tone=tone
        )
        
        # Generate the corrected chapter using structured output
        response = llm.with_structured_output(ChapterCorrectionOutput).invoke([HumanMessage(content=prompt)])
        
        if not response or not response.corrected_scenes:
            logger.error("Failed to get valid correction response")
            return False
        
        # Validate we got the right number of scenes
        if len(response.corrected_scenes) != len(scenes):
            logger.error(f"Scene count mismatch: expected {len(scenes)}, got {len(response.corrected_scenes)}")
            return False
        
        # Save each corrected scene
        success_count = 0
        for i, (scene_num, _) in enumerate(scenes):
            try:
                corrected_content = response.corrected_scenes[i].content.strip()
                
                # Validate content length
                if not corrected_content or len(corrected_content) < 100:
                    logger.error(f"Scene {scene_num} correction too short")
                    continue
                
                # Save the corrected scene
                db_manager.save_scene_content(chapter_num, scene_num, corrected_content)
                logger.info(f"Successfully corrected scene {scene_num} - {len(corrected_content)} characters")
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to save corrected scene {scene_num}: {e}")
        
        logger.info(f"Chapter correction completed. Successfully corrected {success_count}/{len(scenes)} scenes")
        return success_count == len(scenes)
        
    except Exception as e:
        logger.error(f"Failed to correct chapter: {e}")
        return False


def correct_chapter_fallback(chapter_num: int, correction_instruction: str) -> bool:
    """
    Fallback method that uses text parsing instead of structured output.
    """
    try:
        # Get database manager
        db_manager = get_db_manager()
        if not db_manager:
            logger.error("Database manager not available")
            return False
        
        # Get all scenes in the chapter
        scenes = get_chapter_scenes(chapter_num)
        if not scenes:
            logger.error(f"No scenes found for Chapter {chapter_num}")
            return False
        
        logger.info(f"Correcting Chapter {chapter_num} ({len(scenes)} scenes) - using fallback method")
        
        # Get story configuration for context
        config = get_story_config()
        genre = config.get("genre", "fantasy")
        tone = config.get("tone", "adventurous")
        language = config.get("language", "english")
        
        # Get chapter metadata
        chapter_info = get_chapter_info(chapter_num)
        chapter_title = chapter_info.get('title', f'Chapter {chapter_num}')
        chapter_outline = chapter_info.get('outline', '')
        
        # Concatenate all scenes with clear markers
        full_chapter_content = ""
        scene_boundaries = []
        
        for scene_num, scene_content in scenes:
            scene_marker = f"[SCENE {scene_num} START]"
            scene_end_marker = f"[SCENE {scene_num} END]"
            
            full_chapter_content += f"\n\n{scene_marker}\n\n"
            full_chapter_content += scene_content
            full_chapter_content += f"\n\n{scene_end_marker}\n\n"
            
            scene_boundaries.append({
                'scene_num': scene_num,
                'start_marker': scene_marker,
                'end_marker': scene_end_marker
            })
        
        # Render the chapter correction prompt (fallback version)
        prompt = render_prompt(
            'chapter_correction_text',
            language=language,
            chapter_number=chapter_num,
            chapter_title=chapter_title,
            chapter_outline=chapter_outline,
            current_chapter_content=full_chapter_content,
            correction_instruction=correction_instruction,
            scene_count=len(scenes),
            genre=genre,
            tone=tone
        )
        
        # Generate the corrected chapter
        response = llm.invoke([HumanMessage(content=prompt)])
        corrected_full_content = response.content.strip()
        
        # Parse the corrected content to extract scenes
        corrected_scenes = parse_corrected_chapter(corrected_full_content, scene_boundaries)
        
        if len(corrected_scenes) != len(scenes):
            logger.error(f"Failed to parse correct number of scenes: expected {len(scenes)}, got {len(corrected_scenes)}")
            return False
        
        # Save each corrected scene
        success_count = 0
        for scene_num, corrected_content in corrected_scenes.items():
            try:
                # Validate content length
                if not corrected_content or len(corrected_content) < 100:
                    logger.error(f"Scene {scene_num} correction too short")
                    continue
                
                # Save the corrected scene
                db_manager.save_scene_content(chapter_num, scene_num, corrected_content)
                logger.info(f"Successfully corrected scene {scene_num} - {len(corrected_content)} characters")
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to save corrected scene {scene_num}: {e}")
        
        logger.info(f"Chapter correction completed. Successfully corrected {success_count}/{len(scenes)} scenes")
        return success_count == len(scenes)
        
    except Exception as e:
        logger.error(f"Failed to correct chapter (fallback): {e}")
        return False


def parse_corrected_chapter(content: str, scene_boundaries: List[Dict]) -> Dict[int, str]:
    """
    Parse corrected chapter content to extract individual scenes.
    
    Args:
        content: The full corrected chapter content
        scene_boundaries: List of scene boundary markers
        
    Returns:
        Dictionary mapping scene numbers to their content
    """
    corrected_scenes = {}
    
    for boundary in scene_boundaries:
        scene_num = boundary['scene_num']
        start_marker = boundary['start_marker']
        end_marker = boundary['end_marker']
        
        # Find content between markers
        start_pattern = re.escape(start_marker)
        end_pattern = re.escape(end_marker)
        
        match = re.search(f'{start_pattern}(.*?){end_pattern}', content, re.DOTALL)
        if match:
            scene_content = match.group(1).strip()
            corrected_scenes[scene_num] = scene_content
        else:
            logger.error(f"Could not find scene {scene_num} in corrected content")
    
    return corrected_scenes


def get_chapter_scenes(chapter_num: int) -> List[Tuple[int, str]]:
    """
    Get all scenes in a chapter.
    
    Args:
        chapter_num: Chapter number
        
    Returns:
        List of tuples (scene_number, scene_content)
    """
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        return []
    
    try:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT s.scene_number, s.content
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE c.chapter_number = ?
                ORDER BY s.scene_number
                """,
                (chapter_num,)
            )
            
            scenes = []
            for row in cursor.fetchall():
                if row['content']:
                    scenes.append((row['scene_number'], row['content']))
            
            return scenes
            
    except Exception as e:
        logger.error(f"Failed to get chapter scenes: {e}")
        return []


def get_chapter_info(chapter_num: int) -> Dict[str, Any]:
    """
    Get chapter metadata.
    
    Args:
        chapter_num: Chapter number
        
    Returns:
        Dictionary with chapter info
    """
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        return {}
    
    try:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, title, outline, summary
                FROM chapters
                WHERE chapter_number = ?
                """,
                (chapter_num,)
            )
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            
            return {}
            
    except Exception as e:
        logger.error(f"Failed to get chapter info: {e}")
        return {}