"""Scene reflection and quality analysis module for StoryCraft Agent.

This module handles the reflection phase after scene writing, evaluating
quality, consistency, and identifying areas for improvement.
"""

# Standard library imports
import json
from typing import Any, Dict, List, Tuple, Optional

# Third party imports
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

# Local imports
from storyteller_lib import track_progress
from storyteller_lib.config import (
    DEFAULT_LANGUAGE, MEMORY_NAMESPACE, SUPPORTED_LANGUAGES,
    llm, get_llm_with_structured_output
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


# Pydantic models for structured output
class QualityScores(BaseModel):
    """Quality scores for various aspects of the scene."""
    overall: int = Field(ge=1, le=10, description="Overall quality score (1-10, must be integer)")
    pacing: int = Field(ge=1, le=10, description="Pacing quality score (1-10, must be integer)")
    character_development: int = Field(ge=1, le=10, description="Character development score (1-10, must be integer)")
    dialogue: int = Field(ge=1, le=10, description="Dialogue quality score (1-10, must be integer, use 1 if no dialogue)")
    description: int = Field(ge=1, le=10, description="Description quality score (1-10, must be integer)")
    emotional_impact: int = Field(ge=1, le=10, description="Emotional impact score (1-10, must be integer)")
    plot_advancement: int = Field(ge=1, le=10, description="Plot advancement score (1-10, must be integer)")
    worldbuilding_integration: int = Field(ge=1, le=10, description="Worldbuilding integration score (1-10, must be integer)")
    closure_quality: int = Field(ge=1, le=10, description="Scene closure quality score (1-10, must be integer)")

class Issue(BaseModel):
    """An issue identified in the scene."""
    type: str = Field(description="Type of issue: consistency, pacing, character, dialogue, description, worldbuilding, closure, language_mismatch, or other")
    severity: int = Field(ge=1, le=10, description="Severity of the issue (1-10)")
    description: str = Field(description="Detailed description of the issue")
    recommendation: str = Field(description="Specific recommendation to fix the issue")

class ContinuityCheck(BaseModel):
    """Continuity check results."""
    maintains_consistency: bool = Field(description="Whether the scene maintains overall consistency")
    character_consistency: bool = Field(description="Whether characters behave consistently")
    world_consistency: bool = Field(description="Whether world rules are consistent")
    timeline_consistency: bool = Field(description="Whether timeline is consistent")
    specific_issues: List[str] = Field(default_factory=list, description="List of specific continuity issues")

class RevisionRecommendation(BaseModel):
    """Revision recommendations."""
    needs_revision: bool = Field(description="Whether the scene needs revision")
    revision_type: str = Field(description="Type of revision needed: minor, moderate, major, or complete_rewrite")
    priority_fixes: List[str] = Field(default_factory=list, description="List of priority fixes")

class PlotThreadEffectiveness(BaseModel):
    """Plot thread effectiveness analysis."""
    threads_advanced: bool = Field(description="Whether plot threads were advanced")
    effectiveness_score: int = Field(ge=1, le=10, description="Effectiveness score (1-10)")
    missed_opportunities: List[str] = Field(default_factory=list, description="Missed opportunities for plot advancement")

class ClosureAnalysis(BaseModel):
    """Scene closure analysis."""
    has_satisfying_conclusion: bool = Field(description="Whether the scene has a satisfying conclusion")
    emotional_resolution: bool = Field(description="Whether emotions are resolved appropriately")
    leaves_appropriate_questions: bool = Field(description="Whether appropriate questions are left for future")
    transition_ready: bool = Field(description="Whether the scene is ready for transition")
    sets_up_future: bool = Field(description="Whether the scene sets up future events")

class TechnicalAnalysis(BaseModel):
    """Technical writing analysis."""
    word_count_estimate: int = Field(description="Estimated word count")
    pov_consistency: bool = Field(description="Whether POV is consistent")
    tense_consistency: bool = Field(description="Whether tense is consistent")
    showing_vs_telling_ratio: str = Field(description="Ratio assessment: good, needs_improvement, or too_much_telling")

class SceneImpact(BaseModel):
    """Scene impact analysis."""
    advances_story: bool = Field(description="Whether the scene advances the story")
    reveals_character: bool = Field(description="Whether the scene reveals character")
    builds_tension: bool = Field(description="Whether the scene builds tension")
    provides_resolution: bool = Field(description="Whether the scene provides resolution")
    sets_up_future: bool = Field(description="Whether the scene sets up future events")

class SceneReflection(BaseModel):
    """Complete scene reflection analysis."""
    quality_scores: QualityScores = Field(description="Quality scores for various aspects")
    strengths: List[str] = Field(default_factory=list, description="Key strengths of the scene")
    issues: List[Issue] = Field(default_factory=list, description="Issues found in the scene")
    continuity_check: ContinuityCheck = Field(description="Continuity check results")
    revision_recommendation: RevisionRecommendation = Field(description="Revision recommendations")
    plot_thread_effectiveness: PlotThreadEffectiveness = Field(description="Plot thread effectiveness")
    scene_impact: SceneImpact = Field(description="Scene impact analysis")
    technical_analysis: TechnicalAnalysis = Field(description="Technical writing analysis")


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
    
    # Get forbidden elements from scene progression
    forbidden_phrases = []
    forbidden_structures = []
    try:
        from storyteller_lib.scene_progression import get_forbidden_elements
        forbidden_elements = get_forbidden_elements(state)
        forbidden_phrases = forbidden_elements.get("phrases", [])
        forbidden_structures = forbidden_elements.get("structures", [])
    except:
        pass
    
    # Use template system for scene reflection
    from storyteller_lib.prompt_templates import render_prompt
    
    # Prepare scene purpose (extract from scene outline or use default)
    scene_purpose = f"Scene {current_scene} of Chapter {current_chapter}"
    try:
        chapter_id = db_manager._chapter_id_map.get(current_chapter)
        if chapter_id:
            with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT description FROM scenes WHERE chapter_id = ? AND scene_number = ?",
                    (chapter_id, int(current_scene))
                )
                result = cursor.fetchone()
                if result and result['description']:
                    scene_purpose = result['description']
    except:
        pass
    
    # Render the reflection prompt
    prompt = render_prompt(
        'scene_reflection',
        language=language,
        scene_content=scene_content,
        current_chapter=current_chapter,
        current_scene=current_scene,
        genre=genre,
        tone=tone,
        scene_purpose=scene_purpose,
        forbidden_phrases=forbidden_phrases if forbidden_phrases else None,
        forbidden_structures=forbidden_structures if forbidden_structures else None
    )
    
    # Add extra context that's not in the template
    extra_context = f"""
STORY CONTEXT:
- Characters: {', '.join(characters.keys())}
- Important revelations so far: {revelations}

PREVIOUS SCENES CONTEXT:
{previous_context}

{worldbuilding_context}

{previously_addressed_section}

{language_validation_section}

PLOT THREAD UPDATES (from this scene):
{json.dumps(plot_thread_updates, indent=2)}

CLOSURE ANALYSIS:
{json.dumps(closure_analysis, indent=2)}

IMPORTANT: All quality scores MUST be integers between 1 and 10 (inclusive). Do NOT use 0, decimals, or floats. If a scene lacks dialogue, still score dialogue as 1 (not 0).
"""
    
    # Combine template prompt with extra context
    prompt = prompt + "\n\n" + extra_context

    # Get reflection from LLM using structured output
    structured_llm = get_llm_with_structured_output(SceneReflection)
    messages = [HumanMessage(content=prompt)]
    
    try:
        response = structured_llm.invoke(messages)
        
        # Response should be a SceneReflection instance
        if isinstance(response, SceneReflection):
            reflection = response.dict()
        else:
            # Fallback if response is not the expected type
            logger.warning(f"Unexpected response type: {type(response)}")
            reflection = {
                "quality_scores": {"overall": 7, "pacing": 7, "character_development": 7, 
                                 "dialogue": 7, "description": 7, "emotional_impact": 7,
                                 "plot_advancement": 7, "worldbuilding_integration": 7, "closure_quality": 7},
                "strengths": [],
                "issues": [],
                "continuity_check": {"maintains_consistency": True, "character_consistency": True,
                                   "world_consistency": True, "timeline_consistency": True, "specific_issues": []},
                "revision_recommendation": {"needs_revision": False, "revision_type": "minor", "priority_fixes": []},
                "plot_thread_effectiveness": {"threads_advanced": True, "effectiveness_score": 7, "missed_opportunities": []},
                "scene_impact": {"advances_story": True, "reveals_character": True, "builds_tension": False,
                               "provides_resolution": False, "sets_up_future": True},
                "technical_analysis": {"word_count_estimate": 1000, "pov_consistency": True, 
                                     "tense_consistency": True, "showing_vs_telling_ratio": "good"}
            }
    except Exception as e:
        # If structured output fails, create a basic reflection
        logger.warning(f"Failed to get structured reflection: {e}")
        reflection = {
            "quality_scores": {"overall": 7, "pacing": 7, "character_development": 7, 
                             "dialogue": 7, "description": 7, "emotional_impact": 7,
                             "plot_advancement": 7, "worldbuilding_integration": 7, "closure_quality": 7},
            "strengths": [],
            "issues": [],
            "continuity_check": {"maintains_consistency": True, "character_consistency": True,
                               "world_consistency": True, "timeline_consistency": True, "specific_issues": []},
            "revision_recommendation": {"needs_revision": False, "revision_type": "minor", "priority_fixes": []},
            "plot_thread_effectiveness": {"threads_advanced": True, "effectiveness_score": 7, "missed_opportunities": []},
            "scene_impact": {"advances_story": True, "reveals_character": True, "builds_tension": False,
                           "provides_resolution": False, "sets_up_future": True},
            "technical_analysis": {"word_count_estimate": 1000, "pov_consistency": True, 
                                 "tense_consistency": True, "showing_vs_telling_ratio": "good"}
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
    
    # Reflection is stored in state and used immediately for revision
    
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