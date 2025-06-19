"""
Context-aware scene analysis module for StoryCraft Agent.

This module provides intelligent scene analysis that considers genre, tone, and story
context rather than enforcing rigid rules.
"""

from typing import Dict, List, Any, Optional, Tuple
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from storyteller_lib.config import llm
from storyteller_lib.models import StoryState
from storyteller_lib.logger import get_logger

logger = get_logger(__name__)


class SceneAnalysis(BaseModel):
    """Context-aware analysis of a scene."""
    
    scene_type: str = Field(description="Identified scene type (action, dialogue, reflection, etc.)")
    pacing_assessment: str = Field(description="Assessment of pacing appropriateness for genre/tone")
    variety_assessment: str = Field(description="Assessment of variety in context of recent scenes")
    strengths: List[str] = Field(default_factory=list, description="What works well in this scene")
    suggestions: List[str] = Field(default_factory=list, description="Context-aware suggestions")
    genre_alignment: bool = Field(description="Whether the scene aligns with genre expectations")
    tone_consistency: bool = Field(description="Whether the scene maintains tonal consistency")


class SceneSequenceAnalysis(BaseModel):
    """Analysis of scene sequence variety."""
    
    pattern_detected: Optional[str] = Field(description="Any problematic pattern detected")
    variety_appropriate: bool = Field(description="Whether variety level suits the story")
    intentional_pattern: bool = Field(description="Whether any pattern seems intentional")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations if needed")


def analyze_scene_in_context(
    scene_content: str,
    scene_number: int,
    chapter_number: int,
    genre: str,
    tone: str,
    story_premise: str,
    recent_scenes: List[Dict[str, Any]],
    author_style: Optional[str] = None,
    language: str = "english"
) -> SceneAnalysis:
    """
    Analyze a scene considering its context within the story.
    
    Args:
        scene_content: The scene text
        scene_number: Current scene number
        chapter_number: Current chapter number
        genre: Story genre
        tone: Story tone
        story_premise: Overall story premise
        recent_scenes: List of recent scene summaries
        author_style: Optional author style being emulated
        language: Language for analysis
        
    Returns:
        Context-aware scene analysis
    """
    from storyteller_lib.prompt_templates import render_prompt
    
    # Prepare recent scenes summary
    recent_context = ""
    if recent_scenes:
        recent_summaries = []
        for scene in recent_scenes[-3:]:  # Last 3 scenes
            summary = f"Chapter {scene['chapter']}, Scene {scene['scene']}: {scene['type']} - {scene['summary']}"
            recent_summaries.append(summary)
        recent_context = "\n".join(recent_summaries)
    
    prompt = render_prompt(
        'context_aware_scene_analysis',
        language=language,
        scene_content=scene_content,
        scene_number=scene_number,
        chapter_number=chapter_number,
        genre=genre,
        tone=tone,
        story_premise=story_premise,
        recent_scenes=recent_context,
        author_style=author_style or "not specified"
    )
    
    try:
        structured_llm = llm.with_structured_output(SceneAnalysis)
        analysis = structured_llm.invoke(prompt)
        
        logger.info(f"Scene analysis complete - Type: {analysis.scene_type}, Genre aligned: {analysis.genre_alignment}")
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error in scene analysis: {e}")
        return SceneAnalysis(
            scene_type="unknown",
            pacing_assessment="Analysis failed",
            variety_assessment="Analysis failed",
            strengths=[],
            suggestions=[],
            genre_alignment=True,
            tone_consistency=True
        )


def analyze_scene_sequence_variety(
    recent_scenes: List[Dict[str, Any]],
    genre: str,
    tone: str,
    story_context: str,
    language: str = "english"
) -> SceneSequenceAnalysis:
    """
    Analyze whether the scene sequence has appropriate variety for the story type.
    
    Args:
        recent_scenes: List of recent scenes with metadata
        genre: Story genre
        tone: Story tone
        story_context: Context about the story
        language: Language for analysis
        
    Returns:
        Scene sequence variety analysis
    """
    from storyteller_lib.prompt_templates import render_prompt
    
    # Format scene sequence for analysis
    sequence_description = []
    for scene in recent_scenes:
        # Handle both 'scene' and 'scene_number' field names
        scene_num = scene.get('scene', scene.get('scene_number', '?'))
        desc = f"Scene {scene_num}: {scene['type']} - Focus: {scene.get('focus', 'unknown')}"
        if 'event' in scene:
            desc += f" - Event: {scene['event']}"
        sequence_description.append(desc)
    
    prompt = render_prompt(
        'scene_sequence_variety_analysis',
        language=language,
        scene_sequence="\n".join(sequence_description),
        genre=genre,
        tone=tone,
        story_context=story_context
    )
    
    try:
        structured_llm = llm.with_structured_output(SceneSequenceAnalysis)
        analysis = structured_llm.invoke(prompt)
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error in sequence variety analysis: {e}")
        return SceneSequenceAnalysis(
            pattern_detected=None,
            variety_appropriate=True,
            intentional_pattern=False,
            recommendations=[]
        )


def suggest_next_scene_type(
    recent_scenes: List[Dict[str, Any]],
    chapter_outline: str,
    remaining_chapter_goals: List[str],
    genre: str,
    tone: str,
    language: str = "english",
    scene_description: str = ""
) -> Dict[str, Any]:
    """
    Suggest appropriate scene type and focus for the next scene.
    
    Args:
        recent_scenes: Recent scene information
        chapter_outline: Current chapter outline
        remaining_chapter_goals: What still needs to be accomplished
        genre: Story genre
        tone: Story tone
        language: Language for suggestions
        scene_description: The actual description of the scene to write
        
    Returns:
        Suggestions for next scene
    """
    from storyteller_lib.prompt_templates import render_prompt
    
    class SceneSuggestion(BaseModel):
        """Suggestion for next scene."""
        suggested_type: str = Field(description="Suggested scene type")
        suggested_focus: str = Field(description="Suggested scene focus")
        reasoning: str = Field(description="Why this type/focus is appropriate")
        elements_to_include: List[str] = Field(default_factory=list)
        elements_to_avoid: List[str] = Field(default_factory=list)
    
    recent_types = [s.get('type', 'unknown') for s in recent_scenes[-5:]] if recent_scenes else []
    
    prompt = render_prompt(
        'next_scene_suggestion',
        language=language,
        recent_scene_types=recent_types,
        chapter_outline=chapter_outline,
        remaining_goals=remaining_chapter_goals,
        genre=genre,
        tone=tone,
        scene_description=scene_description
    )
    
    try:
        structured_llm = llm.with_structured_output(SceneSuggestion)
        suggestion = structured_llm.invoke(prompt)
        
        return suggestion.dict()
        
    except Exception as e:
        logger.error(f"Error suggesting next scene: {e}")
        return {
            'suggested_type': 'development',
            'suggested_focus': 'advance plot',
            'reasoning': 'Default suggestion',
            'elements_to_include': [],
            'elements_to_avoid': []
        }


def evaluate_scene_necessity(
    proposed_scene: str,
    chapter_goals: List[str],
    story_arc_position: str,  # 'beginning', 'middle', 'climax', 'resolution'
    genre: str,
    tone: str,
    language: str = "english"
) -> Dict[str, Any]:
    """
    Evaluate whether a proposed scene serves the story.
    
    Args:
        proposed_scene: Description of the proposed scene
        chapter_goals: Goals for the current chapter
        story_arc_position: Where we are in the story arc
        genre: Story genre
        tone: Story tone
        language: Language for evaluation
        
    Returns:
        Evaluation of scene necessity
    """
    from storyteller_lib.prompt_templates import render_prompt
    
    class SceneNecessity(BaseModel):
        """Evaluation of scene necessity."""
        serves_story: bool = Field(description="Whether the scene serves the story")
        advances_plot: bool = Field(description="Whether it advances the plot")
        develops_character: bool = Field(description="Whether it develops character")
        maintains_pacing: bool = Field(description="Whether it maintains appropriate pacing")
        reasoning: str = Field(description="Explanation of the evaluation")
        alternatives: List[str] = Field(default_factory=list, description="Alternative approaches if needed")
    
    prompt = render_prompt(
        'scene_necessity_evaluation',
        language=language,
        proposed_scene=proposed_scene,
        chapter_goals=chapter_goals,
        story_position=story_arc_position,
        genre=genre,
        tone=tone
    )
    
    try:
        structured_llm = llm.with_structured_output(SceneNecessity)
        evaluation = structured_llm.invoke(prompt)
        
        return evaluation.dict()
        
    except Exception as e:
        logger.error(f"Error evaluating scene necessity: {e}")
        return {
            'serves_story': True,
            'advances_plot': True,
            'develops_character': True,
            'maintains_pacing': True,
            'reasoning': 'Evaluation failed - defaulting to approved',
            'alternatives': []
        }


def generate_scene_variety_suggestions(
    scene_analysis: SceneAnalysis,
    sequence_analysis: SceneSequenceAnalysis,
    genre: str,
    tone: str
) -> str:
    """
    Generate contextual suggestions for scene variety.
    
    Args:
        scene_analysis: Individual scene analysis
        sequence_analysis: Scene sequence analysis
        genre: Story genre
        tone: Story tone
        
    Returns:
        Formatted suggestions for the writer
    """
    # Be much more permissive - only suggest if there's a serious issue
    if sequence_analysis.variety_appropriate or sequence_analysis.intentional_pattern:
        return ""  # Pattern is fine or intentional
    
    # Keep suggestions minimal and gentle
    suggestions = []
    
    # Only mention if pattern is very repetitive and clearly unintentional
    if sequence_analysis.pattern_detected and len(sequence_analysis.recommendations) > 2:
        suggestions.append("PACING CONSIDERATION:")
        suggestions.append(f"The story might benefit from: {sequence_analysis.recommendations[0]}")
    
    # Trust the writer's instincts more
    if suggestions:
        suggestions.append("\nBut follow your instincts - sometimes patterns serve the story.")
    
    return "\n".join(suggestions) if suggestions else ""