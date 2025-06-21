"""
Summary generation for scenes and chapters.
Creates concise summaries to track "what happened until now" in the story.
"""

from typing import Optional
from langchain_core.messages import HumanMessage

from storyteller_lib.config import llm, DEFAULT_LANGUAGE
from storyteller_lib.database_integration import get_db_manager
from storyteller_lib.logger import get_logger
from storyteller_lib.prompt_templates import render_prompt

logger = get_logger(__name__)


def generate_scene_summary(
    chapter: int,
    scene: int,
    scene_content: str,
    language: str = DEFAULT_LANGUAGE
) -> str:
    """
    Generate a concise summary of a scene.
    Called AFTER reflection/revision to ensure summary reflects final content.
    
    Args:
        chapter: Chapter number
        scene: Scene number
        scene_content: The final scene content (after any revisions)
        language: Language for the summary
        
    Returns:
        A concise summary (2-3 sentences) of what happened
    """
    logger.info(f"Generating summary for Chapter {chapter}, Scene {scene}")
    
    # Use template for summary generation
    prompt = render_prompt(
        'generate_scene_summary',
        language=language,
        chapter=chapter,
        scene=scene,
        scene_content=scene_content
    )
    
    response = llm.invoke([HumanMessage(content=prompt)])
    summary = response.content.strip()
    
    # Store in database
    db_manager = get_db_manager()
    if db_manager and db_manager._db:
        try:
            with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                # Update the scenes table with the summary
                cursor.execute("""
                    UPDATE scenes 
                    SET summary = ?
                    WHERE chapter_id = (SELECT id FROM chapters WHERE chapter_number = ?)
                    AND scene_number = ?
                """, (summary, chapter, scene))
                conn.commit()
                logger.info(f"Stored scene summary in database")
        except Exception as e:
            logger.error(f"Failed to store scene summary: {e}")
    
    return summary


def generate_chapter_summary(
    chapter: int,
    language: str = DEFAULT_LANGUAGE
) -> str:
    """
    Generate a concise summary of a complete chapter.
    Called when transitioning to a new chapter.
    
    Args:
        chapter: Chapter number
        language: Language for the summary
        
    Returns:
        A concise summary of the chapter's key events
    """
    logger.info(f"Generating summary for Chapter {chapter}")
    
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        logger.error("Database manager not available")
        return ""
    
    # Get all scene summaries for this chapter
    scene_summaries = []
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.scene_number, s.summary
            FROM scenes s
            JOIN chapters c ON s.chapter_id = c.id
            WHERE c.chapter_number = ?
            ORDER BY s.scene_number
        """, (chapter,))
        
        for row in cursor.fetchall():
            if row['summary']:
                scene_summaries.append(f"Scene {row['scene_number']}: {row['summary']}")
    
    if not scene_summaries:
        logger.warning(f"No scene summaries found for Chapter {chapter}")
        return ""
    
    # Use template for chapter summary generation
    prompt = render_prompt(
        'generate_chapter_summary',
        language=language,
        chapter=chapter,
        scene_summaries=scene_summaries
    )
    
    response = llm.invoke([HumanMessage(content=prompt)])
    summary = response.content.strip()
    
    # Store in database
    try:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE chapters 
                SET summary = ?
                WHERE chapter_number = ?
            """, (summary, chapter))
            conn.commit()
            logger.info(f"Stored chapter summary in database")
    except Exception as e:
        logger.error(f"Failed to store chapter summary: {e}")
    
    return summary


def get_story_so_far(chapter: int, scene: int) -> dict:
    """
    Get all previous chapter summaries and scene summaries for the current chapter.
    Used to provide context for "what happened until now".
    
    Args:
        chapter: Current chapter number
        scene: Current scene number
        
    Returns:
        Dictionary with 'chapter_summaries' and 'current_chapter_scenes'
    """
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        return {"chapter_summaries": [], "current_chapter_scenes": []}
    
    story_so_far = {
        "chapter_summaries": [],
        "current_chapter_scenes": []
    }
    
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        
        # Get all previous chapter summaries
        cursor.execute("""
            SELECT chapter_number, title, summary
            FROM chapters
            WHERE chapter_number < ?
            AND summary IS NOT NULL
            ORDER BY chapter_number
        """, (chapter,))
        
        for row in cursor.fetchall():
            story_so_far["chapter_summaries"].append({
                "chapter": row['chapter_number'],
                "title": row['title'],
                "summary": row['summary']
            })
        
        # Get previous scenes in current chapter
        if scene > 1:
            cursor.execute("""
                SELECT s.scene_number, s.summary
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE c.chapter_number = ?
                AND s.scene_number < ?
                AND s.summary IS NOT NULL
                ORDER BY s.scene_number
            """, (chapter, scene))
            
            for row in cursor.fetchall():
                story_so_far["current_chapter_scenes"].append({
                    "scene": row['scene_number'],
                    "summary": row['summary']
                })
    
    return story_so_far