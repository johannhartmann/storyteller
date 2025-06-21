"""Prompt optimization utilities for StoryCraft Agent.

This module provides utilities to optimize and reduce the size of prompts
sent to LLMs, helping to avoid text size limits while maintaining quality.
"""

from typing import Dict, List, Any, Optional, Set
import re
from storyteller_lib.logger import get_logger

logger = get_logger(__name__)


def summarize_character(character_data: Dict[str, Any], max_words: int = 100) -> Dict[str, Any]:
    """Create a concise character summary for LLM prompts.
    
    Args:
        character_data: Full character data dictionary
        max_words: Maximum words for the summary
        
    Returns:
        Condensed character dictionary with essential information
    """
    if not character_data:
        return {}
    
    summary = {
        "name": character_data.get("name", "Unknown"),
        "role": character_data.get("role", "Unknown"),
    }
    
    # Add key personality trait (first one)
    personality = character_data.get("personality", {})
    if isinstance(personality, dict):
        traits = personality.get("traits", [])
        if traits and isinstance(traits, list):
            summary["key_trait"] = traits[0] if traits else "Unknown"
    
    # Add current emotional state
    emotional_state = character_data.get("emotional_state", {})
    if isinstance(emotional_state, dict):
        summary["current_emotion"] = emotional_state.get("current", "Stable")
    
    # Add one-line backstory
    backstory = character_data.get("backstory", "")
    if backstory:
        # Take first sentence only
        first_sentence = backstory.split('.')[0] + '.' if '.' in backstory else backstory[:50] + "..."
        summary["backstory_brief"] = first_sentence
    
    # Add current arc stage if available
    character_arc = character_data.get("character_arc", {})
    if isinstance(character_arc, dict) and "current_stage" in character_arc:
        summary["arc_stage"] = character_arc["current_stage"]
    
    return summary


def summarize_world_elements(world_elements: Dict[str, Any], 
                           relevant_categories: Optional[List[str]] = None,
                           max_words_per_category: int = 50) -> Dict[str, str]:
    """Extract and summarize only relevant world elements.
    
    Args:
        world_elements: Full world elements dictionary
        relevant_categories: List of categories to include (None = all)
        max_words_per_category: Maximum words per category
        
    Returns:
        Condensed world elements with brief descriptions
    """
    if not world_elements:
        return {}
    
    summary = {}
    categories_to_include = relevant_categories or list(world_elements.keys())
    
    for category in categories_to_include:
        if category in world_elements:
            element = world_elements[category]
            if isinstance(element, dict):
                # Take the most important field (usually first non-relevance field)
                for key, value in element.items():
                    if key != "relevance" and value:
                        # Truncate to max words
                        value_str = str(value)
                        words = value_str.split()
                        if len(words) > max_words_per_category:
                            value_str = ' '.join(words[:max_words_per_category]) + "..."
                        summary[category] = value_str
                        break
            elif isinstance(element, str):
                # Direct string value
                words = element.split()
                if len(words) > max_words_per_category:
                    element = ' '.join(words[:max_words_per_category]) + "..."
                summary[category] = element
    
    return summary


def truncate_scene_content(scene_content: str, 
                         keep_start: int = 300, 
                         keep_end: int = 200,
                         preserve_dialogue: bool = True,
                         preserve_character_moments: bool = True) -> str:
    """Return full scene content - truncation removed for character development.
    
    IMPORTANT: This function now returns the full scene content without truncation.
    Character development, consistency checking, and story analysis require the 
    complete scene text. Truncation was removing critical middle sections where
    most character development occurs.
    
    Args:
        scene_content: Full scene text
        keep_start: DEPRECATED - ignored
        keep_end: DEPRECATED - ignored
        preserve_dialogue: DEPRECATED - ignored
        preserve_character_moments: DEPRECATED - ignored
        
    Returns:
        Full scene content without any truncation
    """
    if not scene_content:
        return ""
    
    # Always return full content - truncation makes no sense for story analysis
    total_words = len(scene_content.split())
    logger.info(f"Returning full scene content ({total_words} words) - truncation disabled")
    return scene_content


def get_relevant_characters(all_characters: Dict[str, Any], 
                           context: str,
                           max_characters: int = 5) -> Dict[str, Any]:
    """Filter to only characters mentioned in the current context.
    
    Args:
        all_characters: Dictionary of all characters
        context: Text context to search for character mentions
        max_characters: Maximum number of characters to return
        
    Returns:
        Filtered dictionary of relevant characters
    """
    if not all_characters or not context:
        return {}
    
    relevant_chars = {}
    context_lower = context.lower()
    
    # Score characters by relevance
    character_scores = []
    
    for char_id, char_data in all_characters.items():
        if not char_data:
            continue
            
        score = 0
        char_name = char_data.get("name", char_id).lower()
        
        # Count mentions
        mentions = context_lower.count(char_name)
        score += mentions * 10
        
        # Bonus for being protagonist/antagonist
        role = str(char_data.get("role", "")).lower()
        if "protagonist" in role:
            score += 50
        elif "antagonist" in role:
            score += 40
        elif "main" in role or "key" in role:
            score += 30
        
        if score > 0:
            character_scores.append((char_id, char_data, score))
    
    # Sort by score and take top N
    character_scores.sort(key=lambda x: x[2], reverse=True)
    
    for char_id, char_data, score in character_scores[:max_characters]:
        relevant_chars[char_id] = char_data
        logger.debug(f"Including character {char_id} with relevance score {score}")
    
    return relevant_chars


def create_context_summary(previous_scenes: List[Dict[str, Any]], 
                         max_scenes: int = 3,
                         words_per_scene: int = 50) -> List[str]:
    """Generate brief summaries of previous scenes for context.
    
    Args:
        previous_scenes: List of previous scene dictionaries
        max_scenes: Maximum number of scenes to summarize
        words_per_scene: Maximum words per scene summary
        
    Returns:
        List of scene summaries
    """
    if not previous_scenes:
        return []
    
    summaries = []
    
    # Take the most recent scenes
    recent_scenes = previous_scenes[-max_scenes:] if len(previous_scenes) > max_scenes else previous_scenes
    
    for scene in recent_scenes:
        if not scene:
            continue
            
        content = scene.get("content", "")
        if not content:
            continue
        
        # Extract first paragraph or key action
        paragraphs = content.strip().split('\n\n')
        if paragraphs:
            first_para = paragraphs[0]
            words = first_para.split()
            
            if len(words) > words_per_scene:
                summary = ' '.join(words[:words_per_scene]) + "..."
            else:
                summary = first_para
            
            # Add scene identifier if available
            chapter = scene.get("chapter", "?")
            scene_num = scene.get("scene", "?")
            summary = f"[Ch{chapter}/Sc{scene_num}] {summary}"
            
            summaries.append(summary)
    
    return summaries


def estimate_prompt_size(prompt: str) -> Dict[str, int]:
    """Estimate the size of a prompt in various metrics.
    
    Args:
        prompt: The prompt text
        
    Returns:
        Dictionary with size metrics
    """
    return {
        "characters": len(prompt),
        "words": len(prompt.split()),
        "lines": len(prompt.split('\n')),
        "tokens_estimate": len(prompt) // 4  # Rough estimate
    }


def log_prompt_size(prompt: str, context: str, warn_threshold: int = 5000) -> None:
    """Log prompt size and warn if too large.
    
    Args:
        prompt: The prompt text
        context: Description of where this prompt is used
        warn_threshold: Word count threshold for warnings
    """
    metrics = estimate_prompt_size(prompt)
    
    log_msg = f"Prompt size for {context}: {metrics['words']} words, {metrics['characters']} chars"
    
    if metrics['words'] > warn_threshold:
        logger.warning(f"LARGE PROMPT: {log_msg}")
    else:
        logger.info(log_msg)
    
    return metrics


def create_character_summary_batch(characters: Dict[str, Any], 
                                 max_characters: int = 10) -> str:
    """Create a batch summary of multiple characters for prompts.
    
    Args:
        characters: Dictionary of characters
        max_characters: Maximum number to include
        
    Returns:
        Formatted string summary of characters
    """
    if not characters:
        return "No characters defined."
    
    summary_lines = []
    count = 0
    
    # Prioritize main characters
    sorted_chars = []
    for char_id, char_data in characters.items():
        if not char_data:
            continue
        role = str(char_data.get("role", "")).lower()
        priority = 0
        if "protagonist" in role:
            priority = 3
        elif "antagonist" in role:
            priority = 2
        elif "main" in role or "key" in role:
            priority = 1
        sorted_chars.append((priority, char_id, char_data))
    
    sorted_chars.sort(key=lambda x: x[0], reverse=True)
    
    for _, char_id, char_data in sorted_chars[:max_characters]:
        char_summary = summarize_character(char_data, max_words=30)
        line = f"- {char_summary['name']} ({char_summary['role']}): {char_summary.get('key_trait', 'Unknown trait')}"
        if 'current_emotion' in char_summary:
            line += f", currently {char_summary['current_emotion']}"
        summary_lines.append(line)
        count += 1
    
    if len(characters) > max_characters:
        summary_lines.append(f"... and {len(characters) - max_characters} other characters")
    
    return "\n".join(summary_lines)


def create_plot_thread_summary(plot_threads: List[Dict[str, Any]], 
                             max_threads: int = 5) -> str:
    """Create a concise summary of active plot threads.
    
    Args:
        plot_threads: List of plot thread dictionaries
        max_threads: Maximum threads to include
        
    Returns:
        Formatted string summary
    """
    if not plot_threads:
        return "No active plot threads."
    
    summary_lines = []
    
    # Take most important threads
    threads_to_include = plot_threads[:max_threads]
    
    for thread in threads_to_include:
        name = thread.get("name", "Unknown")
        status = thread.get("status", "active")
        desc = thread.get("description", "")
        
        # Truncate description
        if len(desc) > 50:
            desc = desc[:50] + "..."
        
        summary_lines.append(f"- {name} ({status}): {desc}")
    
    if len(plot_threads) > max_threads:
        summary_lines.append(f"... and {len(plot_threads) - max_threads} other threads")
    
    return "\n".join(summary_lines)