"""
Story Summary Management

This module provides functionality to create and maintain comprehensive
story summaries to prevent repetition and maintain consistency.
"""

import json
import logging
from typing import Dict, List, Optional, Any

from langchain_core.messages import HumanMessage

from storyteller_lib.config import get_llm, MEMORY_NAMESPACE, manage_memory_tool
from storyteller_lib.database_integration import get_db_manager

logger = logging.getLogger(__name__)


def generate_story_summary() -> Dict[str, Any]:
    """
    Generate a comprehensive summary of the story so far.
    
    This includes:
    - Key events from each chapter
    - Character developments and revelations
    - Plot threads and their status
    - Important locations and world elements
    - Unique descriptions and phrases used
    
    Returns:
        Dictionary containing comprehensive story summary
    """
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        return {}
    
    summary = {
        "chapters": {},
        "character_actions": {},
        "plot_developments": [],
        "used_descriptions": [],
        "key_revelations": [],
        "scene_types": []
    }
    
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        
        # Get all chapters and their scenes
        cursor.execute("""
            SELECT c.chapter_number, c.title, c.outline,
                   s.scene_number, s.content
            FROM chapters c
            LEFT JOIN scenes s ON c.id = s.chapter_id
            ORDER BY c.chapter_number, s.scene_number
        """)
        
        current_chapter = None
        for row in cursor.fetchall():
            chapter_num = row['chapter_number']
            
            # Initialize chapter if new
            if chapter_num != current_chapter:
                current_chapter = chapter_num
                summary["chapters"][chapter_num] = {
                    "title": row['title'],
                    "outline": row['outline'],
                    "key_events": [],
                    "scenes": {}
                }
            
            # Process scene content
            if row['content']:
                scene_num = row['scene_number']
                content = row['content']
                
                # Extract key information from scene
                scene_info = extract_scene_information(content, chapter_num, scene_num)
                
                summary["chapters"][chapter_num]["scenes"][scene_num] = scene_info
                summary["chapters"][chapter_num]["key_events"].extend(scene_info["events"])
                
                # Track character actions
                for char, actions in scene_info["character_actions"].items():
                    if char not in summary["character_actions"]:
                        summary["character_actions"][char] = []
                    summary["character_actions"][char].extend(actions)
                
                # Track other elements
                summary["used_descriptions"].extend(scene_info["descriptions"])
                summary["key_revelations"].extend(scene_info["revelations"])
                summary["scene_types"].append(scene_info["scene_type"])
        
        # Get plot thread developments
        cursor.execute("""
            SELECT pt.name, pt.description, pt.status,
                   ptd.development_type, ptd.description as dev_desc
            FROM plot_threads pt
            LEFT JOIN plot_thread_developments ptd ON pt.id = ptd.plot_thread_id
            ORDER BY pt.id, ptd.id
        """)
        
        for row in cursor.fetchall():
            summary["plot_developments"].append({
                "thread": row['name'],
                "status": row['status'],
                "development": row['dev_desc'] or row['description']
            })
    
    return summary


def extract_scene_information(content: str, chapter_num: int, scene_num: int) -> Dict[str, Any]:
    """
    Extract key information from a scene using LLM analysis.
    
    Args:
        content: Scene content
        chapter_num: Chapter number
        scene_num: Scene number
        
    Returns:
        Dictionary containing extracted information
    """
    from storyteller_lib.database_integration import get_db_manager
    from storyteller_lib.config import get_llm_with_structured_output, get_llm
    db_manager = get_db_manager()
    
    # Check if we're using Gemini (which supports structured output)
    import os
    provider = os.environ.get("MODEL_PROVIDER", "gemini")
    
    # Define the schema for structured output
    response_schema = {
        "type": "object",
        "properties": {
            "events": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of 2-3 key events that happen (brief phrases)"
            },
            "character_actions": {
                "type": "object",
                "additionalProperties": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "description": "Object mapping character names to list of their key actions"
            },
            "descriptions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of unique descriptive phrases used"
            },
            "revelations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of any important revelations or discoveries"
            },
            "scene_type": {
                "type": "string",
                "enum": ["action", "dialogue", "discovery", "conflict", "exposition", "character_development", "transition", "climax", "resolution", "other"],
                "description": "Category of the scene"
            }
        },
        "required": ["events", "character_actions", "descriptions", "revelations", "scene_type"]
    }
    
    # Get LLM with structured output if using Gemini, otherwise regular LLM
    if provider == "gemini":
        llm = get_llm_with_structured_output(response_schema)
        prompt = f"""Analyze this scene and extract key information.

Scene (Chapter {chapter_num}, Scene {scene_num}):
{content[:2000]}  # Limit to avoid token issues

Extract:
1. Key events that happen (2-3 brief phrases)
2. Character actions (map each character to their actions)
3. Unique descriptive phrases used
4. Important revelations or discoveries
5. The type of scene (action, dialogue, discovery, etc.)
"""
    else:
        # For non-Gemini providers, use regular LLM with explicit JSON instructions
        llm = get_llm()
        prompt = f"""Analyze this scene and extract key information. Return a JSON object with:

1. "events": List of 2-3 key events that happen (brief phrases)
2. "character_actions": Object mapping character names to list of their key actions
3. "descriptions": List of unique descriptive phrases used
4. "revelations": List of any important revelations or discoveries
5. "scene_type": Category like "action", "dialogue", "discovery", "conflict", etc.

Example format:
{{
    "events": ["Event 1", "Event 2"],
    "character_actions": {{"Character Name": ["action 1", "action 2"]}},
    "descriptions": ["description 1", "description 2"],
    "revelations": ["revelation 1"],
    "scene_type": "discovery"
}}

Scene (Chapter {chapter_num}, Scene {scene_num}):
{content[:2000]}  # Limit to avoid token issues

Return ONLY the JSON object, no other text.
"""
    
    try:
        messages = [HumanMessage(content=prompt)]
        response = llm.invoke(messages)
        
        # With structured output, the response should already be valid JSON
        # Check if we're using Gemini with structured output
        if hasattr(response, 'content') and isinstance(response.content, str):
            # Parse the JSON response
            content = response.content.strip()
            
            # Still handle markdown code blocks just in case
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            result = json.loads(content.strip())
        else:
            # Direct structured output result
            result = json.loads(response.content) if isinstance(response.content, str) else response.content
        
        # Register extracted content in the database to prevent repetition
        if db_manager and db_manager._db:
            # Get scene ID
            with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT s.id 
                    FROM scenes s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE c.chapter_number = ? AND s.scene_number = ?
                """, (chapter_num, scene_num))
                scene_row = cursor.fetchone()
                scene_id = scene_row['id'] if scene_row else None
            
            if scene_id:
                # Register events
                for event in result.get("events", []):
                    db_manager._db.register_content("event", event, None, scene_id)
                
                # Register character actions
                for char, actions in result.get("character_actions", {}).items():
                    # Handle both string and list formats
                    if isinstance(actions, str):
                        actions = [actions]
                    elif not isinstance(actions, list):
                        actions = [str(actions)]
                    
                    for action in actions:
                        db_manager._db.register_content("action", f"{char}: {action}", None, scene_id)
                
                # Register descriptions
                for desc in result.get("descriptions", []):
                    db_manager._db.register_content("description", desc, None, scene_id)
                
                # Register revelations
                for rev in result.get("revelations", []):
                    db_manager._db.register_content("revelation", rev, None, scene_id)
        
        return result
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON response: {e}")
        logger.debug(f"Response content that failed to parse: {response.content if hasattr(response, 'content') else 'No content'}")
        
        # Try one more time with regex cleanup for non-Gemini providers
        if provider != "gemini" and hasattr(response, 'content'):
            try:
                import re
                content = response.content.strip()
                # Remove markdown blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                # Fix trailing commas
                content = re.sub(r',(\s*[}\]])', r'\1', content)
                result = json.loads(content.strip())
                return result
            except:
                pass
        
        return {
            "events": [],
            "character_actions": {},
            "descriptions": [],
            "revelations": [],
            "scene_type": "unknown"
        }
    except Exception as e:
        logger.warning(f"Failed to extract scene information: {e}")
        return {
            "events": [],
            "character_actions": {},
            "descriptions": [],
            "revelations": [],
            "scene_type": "unknown"
        }


def get_story_summary_for_context(max_length: int = 5000) -> str:
    """
    Get a formatted story summary suitable for including in prompts.
    
    Args:
        max_length: Maximum length of summary
        
    Returns:
        Formatted string summary
    """
    summary = generate_story_summary()
    
    if not summary or not summary.get("chapters"):
        return ""
    
    # Format summary for prompt inclusion
    lines = ["=== COMPREHENSIVE STORY SUMMARY ===\n"]
    
    # Chapter summaries
    for chapter_num, chapter_data in sorted(summary["chapters"].items()):
        lines.append(f"\nChapter {chapter_num}: {chapter_data.get('title', '')}")
        events = chapter_data.get("key_events", [])[:5]  # Limit events
        if events:
            lines.append("Key Events: " + "; ".join(events))
    
    # Character action tracking
    lines.append("\n=== CHARACTER ACTIONS TRACKER ===")
    for char, actions in summary.get("character_actions", {}).items():
        unique_actions = list(set(actions))[:10]  # Deduplicate and limit
        lines.append(f"{char}: {', '.join(unique_actions)}")
    
    # Plot developments
    if summary.get("plot_developments"):
        lines.append("\n=== PLOT DEVELOPMENTS ===")
        for dev in summary["plot_developments"][:10]:
            lines.append(f"- {dev['thread']}: {dev['development']}")
    
    # Used descriptions to avoid
    if summary.get("used_descriptions"):
        unique_desc = list(set(summary["used_descriptions"]))[:20]
        lines.append("\n=== AVOID REPEATING THESE DESCRIPTIONS ===")
        lines.append(", ".join(unique_desc))
    
    # Scene types used
    if summary.get("scene_types"):
        scene_type_counts = {}
        for st in summary["scene_types"]:
            scene_type_counts[st] = scene_type_counts.get(st, 0) + 1
        lines.append("\n=== SCENE TYPES USED ===")
        for st, count in sorted(scene_type_counts.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"{st}: {count} times")
    
    result = "\n".join(lines)
    
    # Truncate if too long
    if len(result) > max_length:
        result = result[:max_length] + "\n... (truncated)"
    
    return result


def store_story_summary():
    """Store the current story summary in memory for quick access."""
    summary = generate_story_summary()
    
    manage_memory_tool.invoke({
        "action": "create",
        "key": "story_summary_comprehensive",
        "value": summary,
        "namespace": MEMORY_NAMESPACE
    })
    
    logger.info("Stored comprehensive story summary in memory")


def get_repetition_check_data() -> Dict[str, List[str]]:
    """
    Get data specifically for checking repetition.
    
    Returns:
        Dictionary with lists of used elements to avoid
    """
    summary = generate_story_summary()
    
    return {
        "used_events": [event for chapter in summary.get("chapters", {}).values() 
                       for event in chapter.get("key_events", [])],
        "used_actions": [action for actions in summary.get("character_actions", {}).values() 
                        for action in actions],
        "used_descriptions": list(set(summary.get("used_descriptions", []))),
        "used_revelations": summary.get("key_revelations", []),
        "used_scene_types": summary.get("scene_types", [])
    }