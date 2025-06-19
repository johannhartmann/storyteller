"""
Scene structure pattern analysis module for StoryCraft Agent.

This module detects and analyzes repetitive narrative structures within scenes,
such as recurring character dynamics and plot beats.
"""

from typing import Dict, List, Any, Optional, Tuple
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from storyteller_lib.config import llm
from storyteller_lib.logger import get_logger

logger = get_logger(__name__)


class SceneStructurePattern(BaseModel):
    """A detected scene structure pattern."""
    
    pattern_type: str = Field(description="Type of pattern (e.g., 'reluctant hero', 'authority confrontation')")
    description: str = Field(description="Description of the pattern")
    scenes_using_pattern: List[str] = Field(description="List of scenes using this pattern")
    frequency: int = Field(description="How many times this pattern appears")
    variation_suggestions: List[str] = Field(default_factory=list, description="Ways to vary this pattern")


class StructuralAnalysis(BaseModel):
    """Analysis of structural patterns across scenes."""
    
    detected_patterns: List[SceneStructurePattern] = Field(default_factory=list)
    dominant_pattern: Optional[str] = Field(description="Most frequently used pattern")
    variety_score: float = Field(description="Score from 0-1 indicating structural variety")
    recommendations: List[str] = Field(default_factory=list)


def analyze_scene_structures(
    recent_scenes: List[Dict[str, Any]],
    genre: str,
    tone: str,
    language: str = "english"
) -> StructuralAnalysis:
    """
    Analyze scenes for repetitive structural patterns.
    
    Args:
        recent_scenes: List of recent scenes with content
        genre: Story genre
        tone: Story tone
        language: Language for analysis
        
    Returns:
        Structural analysis with patterns and recommendations
    """
    from storyteller_lib.prompt_templates import render_prompt
    from storyteller_lib.scene_progression import SceneProgressionTracker
    
    # First try to get stored scene structures from database
    tracker = SceneProgressionTracker()
    stored_structures = tracker.get_scene_structures_detailed(limit=10)
    
    if stored_structures and len(stored_structures) >= 3:
        # Use stored structures for analysis
        logger.info(f"Using {len(stored_structures)} stored scene structures for pattern analysis")
        
        # Format stored structures for the prompt
        scene_summaries = []
        for structure in stored_structures:
            summary = f"Chapter {structure['chapter']}, Scene {structure['scene']}:\n"
            summary += f"Type: {structure['scene_type']}\n"
            summary += f"Opening: {structure.get('opening_type', 'unknown')}\n"
            summary += f"Structure: {structure['structure_pattern']}\n"
            if structure.get('main_events'):
                summary += f"Events: {', '.join(structure['main_events'][:3])}\n"
            summary += f"Climax: {structure.get('climax_type', 'unknown')}\n"
            summary += f"Resolution: {structure.get('resolution', 'unknown')}"
            scene_summaries.append(summary)
        
        prompt = render_prompt(
            'scene_structure_pattern_analysis',
            language=language,
            scenes="\n---\n".join(scene_summaries),
            genre=genre,
            tone=tone
        )
    else:
        # Fall back to content analysis if not enough stored structures
        logger.info("Not enough stored structures, falling back to content analysis")
        
        # Format scenes for analysis - use full content for accurate pattern detection
        scene_summaries = []
        for scene in recent_scenes:
            content = scene.get('content', '')
            summary = f"Chapter {scene['chapter']}, Scene {scene['scene']}:\n{content}"
            scene_summaries.append(summary)
        
        prompt = render_prompt(
            'scene_structure_pattern_analysis',
            language=language,
            scenes="\n---\n".join(scene_summaries),
            genre=genre,
            tone=tone
        )
    
    try:
        structured_llm = llm.with_structured_output(StructuralAnalysis)
        analysis = structured_llm.invoke(prompt)
        
        logger.info(f"Detected {len(analysis.detected_patterns)} structural patterns")
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing scene structures: {e}")
        return StructuralAnalysis(
            detected_patterns=[],
            dominant_pattern=None,
            variety_score=0.7,
            recommendations=[]
        )


def suggest_structural_alternatives(
    pattern: SceneStructurePattern,
    character_dynamics: Dict[str, Any],
    plot_situation: str,
    genre: str,
    tone: str,
    language: str = "english"
) -> List[str]:
    """
    Generate alternative scene structures for a repetitive pattern.
    
    Args:
        pattern: The repetitive pattern
        character_dynamics: Current character relationships
        plot_situation: Current plot situation
        genre: Story genre
        tone: Story tone
        language: Language for suggestions
        
    Returns:
        List of alternative structural approaches
    """
    from storyteller_lib.prompt_templates import render_prompt
    
    class StructuralAlternatives(BaseModel):
        """Alternative scene structures."""
        alternatives: List[str] = Field(
            description="List of alternative ways to structure this type of scene"
        )
        rationale: str = Field(
            description="Why these alternatives would work"
        )
    
    prompt = render_prompt(
        'structural_alternatives',
        language=language,
        pattern_type=pattern.pattern_type,
        pattern_description=pattern.description,
        frequency=pattern.frequency,
        character_dynamics=str(character_dynamics),
        plot_situation=plot_situation,
        genre=genre,
        tone=tone
    )
    
    try:
        structured_llm = llm.with_structured_output(StructuralAlternatives)
        result = structured_llm.invoke(prompt)
        
        return result.alternatives
        
    except Exception as e:
        logger.error(f"Error generating structural alternatives: {e}")
        return []


def detect_character_dynamic_patterns(
    scenes: List[Dict[str, Any]],
    character_pairs: List[Tuple[str, str]],
    language: str = "english"
) -> Dict[str, List[str]]:
    """
    Detect repetitive character interaction patterns.
    
    Args:
        scenes: List of scenes with character interactions
        character_pairs: Pairs of characters to analyze
        language: Language for analysis
        
    Returns:
        Dictionary mapping character pairs to their repetitive patterns
    """
    patterns = {}
    
    for char1, char2 in character_pairs:
        pair_key = f"{char1}-{char2}"
        
        # Find scenes where both characters interact
        interactions = []
        for scene in scenes:
            if char1 in scene.get('characters', []) and char2 in scene.get('characters', []):
                interactions.append({
                    'chapter': scene['chapter'],
                    'scene': scene['scene'],
                    'summary': scene.get('summary', '')
                })
        
        if len(interactions) >= 3:
            # Analyze if interactions follow a pattern
            from storyteller_lib.prompt_templates import render_prompt
            
            class InteractionPattern(BaseModel):
                """Character interaction pattern."""
                pattern_detected: bool = Field(description="Whether a repetitive pattern exists")
                pattern_description: str = Field(description="Description of the pattern")
                variation_needed: bool = Field(description="Whether variation would improve the story")
            
            prompt = render_prompt(
                'character_interaction_pattern',
                language=language,
                character1=char1,
                character2=char2,
                interactions=[f"Ch{i['chapter']}/Sc{i['scene']}: {i['summary']}" for i in interactions]
            )
            
            try:
                structured_llm = llm.with_structured_output(InteractionPattern)
                result = structured_llm.invoke(prompt)
                
                if result.pattern_detected and result.variation_needed:
                    patterns[pair_key] = [result.pattern_description]
                    
            except Exception as e:
                logger.error(f"Error analyzing character patterns for {pair_key}: {e}")
    
    return patterns


def generate_structural_guidance(
    analysis: StructuralAnalysis,
    upcoming_scene_type: str,
    characters_involved: List[str]
) -> str:
    """
    Generate guidance to avoid repetitive structures.
    
    Args:
        analysis: Structural analysis results
        upcoming_scene_type: Type of scene being written
        characters_involved: Characters in the upcoming scene
        
    Returns:
        Guidance string for scene writing
    """
    # Only provide guidance if there's a clear repetitive pattern
    if analysis.variety_score > 0.6 or not analysis.dominant_pattern:
        return ""
    
    # Check if the upcoming scene might repeat the pattern
    problematic_patterns = [p for p in analysis.detected_patterns 
                           if p.frequency >= 3 and p.pattern_type == analysis.dominant_pattern]
    
    if not problematic_patterns:
        return ""
    
    pattern = problematic_patterns[0]
    
    guidance = ["STRUCTURAL VARIETY SUGGESTION:"]
    guidance.append(f"\nThe '{pattern.pattern_type}' structure has appeared {pattern.frequency} times.")
    
    if pattern.variation_suggestions:
        guidance.append("\nConsider one of these alternatives:")
        for i, suggestion in enumerate(pattern.variation_suggestions[:2], 1):
            guidance.append(f"{i}. {suggestion}")
    
    guidance.append("\nOr find your own fresh approach to this moment.")
    
    return "\n".join(guidance)