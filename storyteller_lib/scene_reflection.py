"""Scene reflection and quality analysis module for StoryCraft Agent.

This module handles the reflection phase after scene writing, evaluating
quality, consistency, and identifying areas for improvement.
"""

# Standard library imports
import json
from typing import Any, Dict, List, Tuple

# Third party imports
from langchain_core.messages import HumanMessage

# Local imports
from storyteller_lib import track_progress
from storyteller_lib.config import (
    DEFAULT_LANGUAGE, MEMORY_NAMESPACE, SUPPORTED_LANGUAGES,
    llm, manage_memory_tool, search_memory_tool
)
from storyteller_lib.constants import NodeNames, QualityThresholds, RevisionTypes
from storyteller_lib.logger import scene_logger as logger
from storyteller_lib.models import StoryState


def _gather_previous_scenes_context(state: StoryState) -> Tuple[List[str], str]:
    """Gather context from previous scenes for continuity checking.
    
    Args:
        state: Current story state
        
    Returns:
        Tuple of (previous_scenes list, formatted context string)
    """
    chapters = state["chapters"]
    current_chapter = str(state["current_chapter"])
    current_scene = str(state["current_scene"])
    
    previous_scenes = []
    # Iterate through chapters (dictionary with string keys)
    for chap_key, chapter in chapters.items():
        chap_num = int(chap_key)
        curr_chap_num = int(current_chapter)
        curr_scene_num = int(current_scene)
        if chap_num < curr_chap_num or (chap_num == curr_chap_num and curr_scene_num > 1):
            # Iterate through scenes in this chapter (also dictionary)
            scenes = chapter.get("scenes", {})
            for scene_key, scene in scenes.items():
                scene_num = int(scene_key)
                if chap_num == curr_chap_num and scene_num >= curr_scene_num:
                    continue
                # Get scene content from database if not in state
                scene_content = None
                if "content" in scene:
                    scene_content = scene["content"]
                elif scene.get("db_stored"):
                    # Get from database
                    from storyteller_lib.database_integration import get_db_manager
                    db_manager = get_db_manager()
                    if db_manager:
                        scene_content = db_manager.get_scene_content(chap_num, scene_num)
                
                if scene_content:
                    prev_scene = scene_content[:200]  # First 200 chars as summary
                    previous_scenes.append(f"Chapter {chap_num}, Scene {scene_num}: {prev_scene}...")
    
    previous_context = "\n".join(previous_scenes[-5:])  # Last 5 scenes for context
    return previous_scenes, previous_context


def _prepare_worldbuilding_context(world_elements: Dict) -> str:
    """Format worldbuilding elements for reflection context.
    
    Args:
        world_elements: Dictionary of world elements
        
    Returns:
        Formatted worldbuilding context string
    """
    if not world_elements:
        return ""
        
    worldbuilding_sections = []
    for category, elements in world_elements.items():
        category_section = f"{category.upper()}:\n"
        for key, value in elements.items():
            if isinstance(value, list) and value:
                # For lists, include a summary
                category_section += f"- {key.replace('_', ' ').title()}: {', '.join(value[:3])}\n"
            elif value:
                # For strings or other values
                category_section += f"- {key.replace('_', ' ').title()}: {value}\n"
        worldbuilding_sections.append(category_section)
    
    return "Established World Elements:\n" + "\n".join(worldbuilding_sections)


def _prepare_language_validation(language: str) -> str:
    """Prepare language validation instructions for reflection.
    
    Args:
        language: Target language for the story
        
    Returns:
        Language validation section string
    """
    if language.lower() == DEFAULT_LANGUAGE:
        return ""
        
    return f"""
    LANGUAGE VALIDATION:
    The story is supposed to be written in {SUPPORTED_LANGUAGES[language.lower()]}.
    You MUST check if the scene is actually written in {SUPPORTED_LANGUAGES[language.lower()]} or if it was mistakenly written in English or another language.
    
    If the scene is NOT written in {SUPPORTED_LANGUAGES[language.lower()]}, you MUST:
    1. Create an issue with type "language_mismatch"
    2. Set the severity to 10 (highest)
    3. Provide a recommendation to rewrite the scene entirely in {SUPPORTED_LANGUAGES[language.lower()]}
    4. Set needs_revision to true
    """


def _format_previously_addressed_issues(previously_addressed_issues: List[Dict]) -> str:
    """Format previously addressed issues for the reflection prompt.
    
    Args:
        previously_addressed_issues: List of previously addressed issues
        
    Returns:
        Formatted section about previously addressed issues
    """
    if not previously_addressed_issues:
        return ""
        
    issues_text = "\n".join([f"- {issue.get('type', 'unknown').upper()}: {issue.get('description', 'No description')}"
                           for issue in previously_addressed_issues])
    
    return f"""
    IMPORTANT - Previously Addressed Issues:
    The following issues have already been identified and addressed in previous revisions.
    DO NOT report these issues again unless they still exist in the current version:
    
    {issues_text}
    """


@track_progress
def reflect_on_scene(state: StoryState) -> Dict:
    """Reflect on the current scene to evaluate quality and consistency.
    
    This function performs a comprehensive analysis of the written scene,
    checking for quality, consistency, pacing, and other issues.
    
    Args:
        state: Current story state
        
    Returns:
        Updated state with reflection results
    """
    
    chapters = state["chapters"]
    current_chapter = str(state["current_chapter"])
    current_scene = str(state["current_scene"])
    revelations = state["revelations"]
    language = state.get("language", DEFAULT_LANGUAGE)
    genre = state.get("genre", "fantasy")
    tone = state.get("tone", "adventurous")
    
    # Get database manager
    from storyteller_lib.database_integration import get_db_manager
    db_manager = get_db_manager()
    
    if not db_manager or not db_manager._db:
        raise RuntimeError("Database manager not available")
    
    # Get full story outline from database
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT global_story FROM story_config WHERE id = 1"
        )
        result = cursor.fetchone()
        if not result:
            raise RuntimeError("Story outline not found in database")
        global_story = result['global_story']
    
    # Get characters from database
    characters = {}
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT identifier, name, role, backstory, personality
            FROM characters
        """)
        for row in cursor.fetchall():
            characters[row['identifier']] = {
                'name': row['name'],
                'role': row['role'],
                'backstory': row['backstory'],
                'personality': row['personality']
            }
    
    # Get the scene content from database or temporary state
    scene_content = db_manager.get_scene_content(int(current_chapter), int(current_scene))
    if not scene_content:
        scene_content = state.get("current_scene_content", "")
        if not scene_content:
            raise RuntimeError(f"Scene {current_scene} of chapter {current_chapter} not found")
    
    # Get worldbuilding elements from database
    world_elements = {}
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category, element_key, element_value
            FROM world_elements
        """)
        for row in cursor.fetchall():
            if row['category'] not in world_elements:
                world_elements[row['category']] = {}
            world_elements[row['category']][row['element_key']] = row['element_value']
    
    # Get previously addressed issues if available
    previously_addressed_issues = chapters[current_chapter]["scenes"][current_scene].get("issues_addressed", [])
    
    # Update plot threads based on this scene
    from storyteller_lib.plot_threads import update_plot_threads
    plot_thread_updates = update_plot_threads(state)
    
    # Check scene closure
    from storyteller_lib.scene_closure import check_and_improve_scene_closure
    needs_improved_closure, closure_analysis, improved_scene = check_and_improve_scene_closure(state)
    
    # Update scene content if closure improvement is needed
    if needs_improved_closure:
        scene_content = improved_scene
        # Save improved scene to database
        if db_manager:
            db_manager.save_scene_content(int(current_chapter), int(current_scene), improved_scene)
        logger.info(f"Improved scene closure for Chapter {current_chapter}, Scene {current_scene}")
    
    # Gather previous scenes for context
    previous_scenes, previous_context = _gather_previous_scenes_context(state)
    
    # Prepare various context sections
    worldbuilding_context = _prepare_worldbuilding_context(world_elements)
    language_validation_section = _prepare_language_validation(language)
    previously_addressed_section = _format_previously_addressed_issues(previously_addressed_issues)
    
    # Construct the reflection prompt
    prompt = f"""Analyze this scene from Chapter {current_chapter}, Scene {current_scene}:

SCENE CONTENT:
{scene_content}

STORY CONTEXT:
- Characters: {', '.join(characters.keys())}
- Important revelations so far: {revelations}
- Genre: {genre}
- Tone: {tone}

PREVIOUS SCENES CONTEXT:
{previous_context}

{worldbuilding_context}

{previously_addressed_section}

{language_validation_section}

PLOT THREAD UPDATES (from this scene):
{json.dumps(plot_thread_updates, indent=2)}

CLOSURE ANALYSIS:
{json.dumps(closure_analysis, indent=2)}

Analyze the scene and provide a detailed evaluation as a JSON object with the following structure:

{{
    "quality_scores": {{
        "overall": <1-10>,
        "pacing": <1-10>,
        "character_development": <1-10>,
        "dialogue": <1-10>,
        "description": <1-10>,
        "emotional_impact": <1-10>,
        "plot_advancement": <1-10>,
        "worldbuilding_integration": <1-10>,
        "closure_quality": <1-10>
    }},
    "strengths": [
        // List key strengths of the scene
    ],
    "issues": [
        {{
            "type": "<consistency|pacing|character|dialogue|description|worldbuilding|closure|language_mismatch|other>",
            "severity": <1-10>,
            "description": "<detailed description>",
            "recommendation": "<specific fix>"
        }}
        // Include multiple issues if found
    ],
    "continuity_check": {{
        "maintains_consistency": <true/false>,
        "character_consistency": <true/false>,
        "world_consistency": <true/false>,
        "timeline_consistency": <true/false>,
        "specific_issues": [
            // List any continuity problems
        ]
    }},
    "revision_recommendation": {{
        "needs_revision": <true/false>,
        "revision_type": "<minor|moderate|major|complete_rewrite>",
        "priority_fixes": [
            // List the most important things to fix
        ]
    }},
    "plot_thread_effectiveness": {{
        "threads_advanced": <true/false>,
        "effectiveness_score": <1-10>,
        "missed_opportunities": [
            // Any plot threads that could have been better utilized
        ]
    }},
    "scene_impact": {{
        "advances_story": <true/false>,
        "reveals_character": <true/false>,
        "builds_tension": <true/false>,
        "provides_resolution": <true/false>,
        "sets_up_future": <true/false>
    }},
    "technical_analysis": {{
        "word_count_estimate": <number>,
        "pov_consistency": <true/false>,
        "tense_consistency": <true/false>,
        "showing_vs_telling_ratio": "<good|needs_improvement|too_much_telling>"
    }}
}}

Be thorough but constructive in your analysis. Focus on actionable improvements."""

    # Get reflection from LLM
    messages = [HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    
    # Parse the JSON response
    try:
        # Extract JSON from the response - handle cases where LLM returns markdown code blocks
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]  # Remove ```json
        if content.startswith("```"):
            content = content[3:]  # Remove ```
        if content.endswith("```"):
            content = content[:-3]  # Remove trailing ```
        content = content.strip()
        
        reflection = json.loads(content)
    except (json.JSONDecodeError, AttributeError) as e:
        # If JSON parsing fails, create a basic reflection
        logger.warning(f"Failed to parse reflection JSON: {e}")
        logger.debug(f"Response content: {response.content if hasattr(response, 'content') else 'No content'}")
        reflection = {
            "quality_scores": {"overall": 7},
            "issues": [],
            "revision_recommendation": {"needs_revision": False}
        }
    
    # Store the reflection in the scene data
    chapters[current_chapter]["scenes"][current_scene]["reflection"] = reflection
    
    # Determine if revision is needed based on quality scores and issues
    needs_revision = reflection["revision_recommendation"]["needs_revision"]
    
    # Also check quality thresholds
    if not needs_revision:
        scores = reflection["quality_scores"]
        if (scores.get("overall", 10) < QualityThresholds.MIN_OVERALL_SCORE or
            scores.get("character_development", 10) < QualityThresholds.MIN_CHARACTER_SCORE or
            scores.get("plot_advancement", 10) < QualityThresholds.MIN_PLOT_RESOLUTION_SCORE):
            needs_revision = True
            reflection["revision_recommendation"]["needs_revision"] = True
            reflection["revision_recommendation"]["revision_type"] = RevisionTypes.MODERATE
    
    # Update state
    state["last_node"] = NodeNames.REFLECT_ON_SCENE
    state["scene_needs_revision"] = needs_revision
    state["scene_reflection"] = reflection
    
    # Store reflection in memory for future reference
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"scene_reflection_ch{current_chapter}_sc{current_scene}",
        "value": reflection,
        "namespace": MEMORY_NAMESPACE
    })
    
    # Log the reflection
    from storyteller_lib.story_progress_logger import get_progress_logger
    progress_logger = get_progress_logger()
    if progress_logger:
        progress_logger.log_scene_reflection(current_chapter, current_scene, reflection)
    
    # Return state updates
    return {
        "current_scene_content": scene_content,  # Pass along the (possibly improved) scene content
        "scene_reflection": {
            "issues": reflection.get("issues", []) if needs_revision else [],
            "needs_revision": needs_revision
        }
    }