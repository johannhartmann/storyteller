"""Scene variety enforcement for StoryCraft Agent.

This module ensures variety in scene types, structures, and content to prevent
repetitive storytelling patterns.
"""

from typing import Dict, List, Any, Optional, Tuple
from pydantic import BaseModel, Field
from storyteller_lib.logger import get_logger
from storyteller_lib.config import llm
from langchain_core.messages import HumanMessage

logger = get_logger(__name__)


class SceneVarietyRequirements(BaseModel):
    """Requirements for the next scene to ensure variety."""
    scene_type: str = Field(description="Required scene type: action, dialogue, exploration, revelation, transition, character_moment")
    setting_change: bool = Field(description="Whether the setting must be different from previous scene")
    required_characters: List[str] = Field(description="Characters that must appear")
    excluded_characters: List[str] = Field(description="Characters that should NOT appear to add variety")
    forbidden_elements: List[str] = Field(description="Story elements to avoid (e.g., 'visions', 'system failures')")
    required_plot_thread: str = Field(description="Which plot thread must be advanced")
    pov_focus: str = Field(description="Whose perspective to emphasize")
    emotional_tone: str = Field(description="Required emotional tone: tense, calm, mysterious, hopeful, dark")


class SceneStructureAnalysis(BaseModel):
    """Analysis of a scene's structure."""
    opening_type: str = Field(description="How the scene opens: action, dialogue, description, internal_thought")
    main_events: List[str] = Field(description="List of main events in order")
    climax_type: str = Field(description="Type of scene climax: revelation, action, emotional, cliffhanger")
    resolution: str = Field(description="How the scene resolves: complete, partial, cliffhanger")
    structure_pattern: str = Field(description="Overall pattern like 'routine->disruption->vision->dismissal'")


def analyze_scene_structure(scene_content: str) -> SceneStructureAnalysis:
    """Analyze the structure of a written scene.
    
    Args:
        scene_content: The full scene text
        
    Returns:
        SceneStructureAnalysis object
    """
    prompt = f"""Analyze the structure of this scene:

{scene_content[:1500]}...

Identify:
1. How the scene opens (action, dialogue, description, or internal thought)
2. The main events that occur in order (be specific but concise)
3. The type of climax or high point
4. How the scene resolves
5. The overall structural pattern (e.g., 'routine->disruption->discovery')

Be analytical and specific about the actual structure, not the content."""

    try:
        structured_llm = llm.with_structured_output(SceneStructureAnalysis)
        analysis = structured_llm.invoke(prompt)
        logger.info(f"Analyzed scene structure: {analysis.structure_pattern}")
        return analysis
    except Exception as e:
        logger.error(f"Failed to analyze scene structure: {e}")
        # Return a basic analysis
        return SceneStructureAnalysis(
            opening_type="unknown",
            main_events=["unknown"],
            climax_type="unknown",
            resolution="unknown",
            structure_pattern="unknown"
        )


def determine_scene_variety_requirements(
    previous_scenes: List[Dict[str, Any]], 
    chapter_outline: str,
    scene_number: int,
    total_scenes_in_chapter: int
) -> SceneVarietyRequirements:
    """Determine requirements for the next scene to ensure variety.
    
    Args:
        previous_scenes: List of previous scene metadata
        chapter_outline: The chapter outline
        scene_number: Current scene number
        total_scenes_in_chapter: Total number of scenes planned
        
    Returns:
        SceneVarietyRequirements object
    """
    # Build context about previous scenes
    scene_history = []
    for scene in previous_scenes[-3:]:  # Last 3 scenes
        scene_history.append({
            'scene_type': scene.get('scene_type', 'unknown'),
            'structure': scene.get('structure_pattern', 'unknown'),
            'characters': scene.get('characters', []),
            'events': scene.get('event_types', [])
        })
    
    prompt = f"""Based on the previous scenes and chapter outline, determine requirements for Scene {scene_number} to ensure variety and progression.

CHAPTER OUTLINE:
{chapter_outline}

PREVIOUS SCENES:
{scene_history}

This is scene {scene_number} of {total_scenes_in_chapter} in this chapter.

Determine:
1. What type of scene would provide the best variety (action, dialogue, exploration, revelation, transition, character_moment)
2. Whether the setting should change
3. Which characters should appear (for variety)
4. Which characters should be excluded (to avoid repetition)
5. What elements to avoid that have been overused
6. Which plot thread needs advancement
7. Whose perspective to focus on
8. What emotional tone would provide contrast

Ensure variety by avoiding patterns from previous scenes."""

    try:
        structured_llm = llm.with_structured_output(SceneVarietyRequirements)
        requirements = structured_llm.invoke(prompt)
        logger.info(f"Generated variety requirements: scene_type={requirements.scene_type}")
        return requirements
    except Exception as e:
        logger.error(f"Failed to determine variety requirements: {e}")
        # Return basic requirements
        return SceneVarietyRequirements(
            scene_type="dialogue",  # Default to dialogue for variety
            setting_change=True,
            required_characters=[],
            excluded_characters=[],
            forbidden_elements=[],
            required_plot_thread="main",
            pov_focus="protagonist",
            emotional_tone="calm"
        )


def generate_scene_variety_guidance(requirements: SceneVarietyRequirements) -> str:
    """Generate specific guidance for scene writing based on variety requirements.
    
    Args:
        requirements: SceneVarietyRequirements object
        
    Returns:
        Formatted guidance string
    """
    guidance = f"""
SCENE VARIETY REQUIREMENTS:

Scene Type: {requirements.scene_type.upper()}
{_get_scene_type_guidance(requirements.scene_type)}

Setting: {"MUST change from previous scene" if requirements.setting_change else "Can remain the same"}

Character Focus:
- Must include: {', '.join(requirements.required_characters) if requirements.required_characters else 'No specific requirements'}
- Must EXCLUDE: {', '.join(requirements.excluded_characters) if requirements.excluded_characters else 'None'}
- POV emphasis: {requirements.pov_focus}

FORBIDDEN ELEMENTS (do not include these):
{chr(10).join(f'- {element}' for element in requirements.forbidden_elements) if requirements.forbidden_elements else '- None'}

Plot Thread Focus: {requirements.required_plot_thread}
- This scene must meaningfully advance this thread
- Show clear progression from its previous state

Emotional Tone: {requirements.emotional_tone.upper()}
- Maintain this tone throughout the scene
- Use it to create contrast with previous scenes
"""
    
    return guidance


def _get_scene_type_guidance(scene_type: str) -> str:
    """Get specific guidance for different scene types."""
    guidance_map = {
        "action": """- Start in the middle of action
- Use short, punchy sentences
- Focus on physical movement and external conflict
- Minimal internal reflection""",
        
        "dialogue": """- Open with characters in conversation
- Focus on revealing information through speech
- Use subtext and character dynamics
- Advance plot through what characters say (and don't say)""",
        
        "exploration": """- Focus on discovering new locations or information
- Use rich sensory descriptions
- Build atmosphere and world details
- Character learns something new about their environment""",
        
        "revelation": """- Build to a significant discovery or realization
- Focus on the impact of new information
- Show character's emotional/mental response
- Change the story's direction""",
        
        "transition": """- Move between major story beats
- Can be quieter and reflective
- Set up the next major event
- Show passage of time or change in circumstances""",
        
        "character_moment": """- Focus on internal character development
- Show growth, change, or self-realization
- Can be quieter and more introspective
- Deepen reader's connection to character"""
    }
    
    return guidance_map.get(scene_type, "- Follow standard scene structure")


def check_scene_variety_compliance(
    scene_content: str,
    requirements: SceneVarietyRequirements
) -> Tuple[bool, List[str]]:
    """Check if a scene meets the variety requirements.
    
    Args:
        scene_content: The written scene content
        requirements: The variety requirements
        
    Returns:
        Tuple of (compliance_status, list_of_issues)
    """
    issues = []
    
    # Check for forbidden elements
    content_lower = scene_content.lower()
    for forbidden in requirements.forbidden_elements:
        if forbidden.lower() in content_lower:
            issues.append(f"Scene contains forbidden element: {forbidden}")
    
    # Check for excluded characters
    for character in requirements.excluded_characters:
        if character.lower() in content_lower:
            issues.append(f"Scene includes excluded character: {character}")
    
    # Check for required characters
    for character in requirements.required_characters:
        if character.lower() not in content_lower:
            issues.append(f"Scene missing required character: {character}")
    
    # More checks could be added here
    
    return len(issues) == 0, issues


def get_overused_elements(scene_progression_tracker) -> List[str]:
    """Identify elements that have been overused in recent scenes.
    
    Args:
        scene_progression_tracker: SceneProgressionTracker instance
        
    Returns:
        List of overused elements to avoid
    """
    overused = []
    
    # Check recent events
    recent_events = scene_progression_tracker.get_recent_events(limit=5)
    event_counts = {}
    for event in recent_events:
        event_type = event.get('event_type', '')
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
    
    # Flag any event type that appears more than twice
    for event_type, count in event_counts.items():
        if count > 2:
            overused.append(f"{event_type} events")
    
    # Get ALL used phrases from the database - no hardcoded list
    used_phrases = scene_progression_tracker.get_used_phrases('description')
    # Count phrase frequency
    phrase_counts = {}
    for phrase in used_phrases:
        # Only track phrases longer than 3 words to avoid common terms
        if len(phrase.split()) > 3:
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
    
    # Add any phrase used more than once
    for phrase, count in phrase_counts.items():
        if count > 1:
            overused.append(f"phrase: {phrase}")
    
    # Check scene structures
    structures = scene_progression_tracker.get_scene_structures()
    if len(structures) > 2:
        # Find any structure used more than once
        structure_counts = {}
        for structure in structures:
            structure_counts[structure] = structure_counts.get(structure, 0) + 1
        
        for structure, count in structure_counts.items():
            if count > 1:
                overused.append(f"structure: {structure}")
    
    return overused