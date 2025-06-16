"""Chapter variety planning for StoryCraft Agent.

This module ensures chapters are planned with diverse scenes from the start,
preventing repetitive chapter structures.
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from storyteller_lib.logger import get_logger
from storyteller_lib.config import llm
from langchain_core.messages import HumanMessage

logger = get_logger(__name__)


class ScenePlan(BaseModel):
    """Plan for a single scene within a chapter."""
    scene_number: int = Field(description="Scene number within the chapter")
    scene_type: str = Field(description="Type: action, dialogue, exploration, revelation, transition, character_moment")
    primary_location: str = Field(description="Where this scene takes place")
    key_characters: List[str] = Field(description="Main characters in this scene (2-3 max)")
    main_event: str = Field(description="The primary thing that happens")
    advances_plot_thread: str = Field(description="Which plot thread this advances")
    emotional_tone: str = Field(description="Emotional tone: tense, calm, mysterious, joyful, somber")
    
    
class ChapterScenePlan(BaseModel):
    """Detailed scene-by-scene plan for a chapter."""
    chapter_number: int = Field(description="Chapter number")
    chapter_theme: str = Field(description="Overall theme or focus of the chapter")
    scene_plans: List[ScenePlan] = Field(description="Detailed plans for each scene")


def create_varied_chapter_plan(
    chapter_number: int,
    chapter_outline: str,
    story_context: Dict[str, Any],
    previous_chapter_patterns: Optional[List[str]] = None
) -> ChapterScenePlan:
    """Create a detailed chapter plan that ensures scene variety.
    
    Args:
        chapter_number: The chapter number
        chapter_outline: High-level outline for the chapter
        story_context: Context including characters, plot threads, etc.
        previous_chapter_patterns: Patterns to avoid from previous chapters
        
    Returns:
        ChapterScenePlan with varied scenes
    """
    # Extract key information
    characters = story_context.get('characters', {})
    plot_threads = story_context.get('plot_threads', {})
    
    # Build the prompt
    prompt = f"""Create a detailed scene-by-scene plan for Chapter {chapter_number} that ensures variety and progression.

CHAPTER OUTLINE:
{chapter_outline}

AVAILABLE CHARACTERS:
{', '.join([f"{char['name']} ({char.get('role', 'unknown')})" for char in characters.values()])}

PLOT THREADS TO ADVANCE:
{', '.join(plot_threads.keys())}

{"AVOID THESE PATTERNS FROM PREVIOUS CHAPTERS:" + chr(10).join(previous_chapter_patterns) if previous_chapter_patterns else ""}

REQUIREMENTS:
1. Each scene must have a DIFFERENT structure and purpose
2. Vary the locations - don't keep characters in the same place
3. Rotate which characters appear - don't use the same group every scene
4. Each scene type should be different (action, dialogue, exploration, etc.)
5. Vary emotional tones throughout the chapter
6. Each scene must meaningfully advance at least one plot thread

For Chapter 1 specifically:
- Scene 1 can establish routine/normal world
- Remaining scenes must show PROGRESSION and CHANGE
- Avoid multiple "vision/anomaly" scenes
- Show different aspects of the world and character

Create 3-5 scenes that form a complete chapter arc while maintaining variety."""

    try:
        structured_llm = llm.with_structured_output(ChapterScenePlan)
        plan = structured_llm.invoke(prompt)
        
        # Validate variety
        scene_types = [s.scene_type for s in plan.scene_plans]
        if len(set(scene_types)) < len(scene_types) * 0.7:  # At least 70% unique
            logger.warning("Chapter plan lacks sufficient scene type variety")
        
        logger.info(f"Created varied chapter plan with {len(plan.scene_plans)} scenes")
        return plan
        
    except Exception as e:
        logger.error(f"Failed to create chapter plan: {e}")
        # Return a basic varied plan
        return ChapterScenePlan(
            chapter_number=chapter_number,
            chapter_theme="Chapter events",
            scene_plans=[
                ScenePlan(
                    scene_number=1,
                    scene_type="exploration",
                    primary_location="Main setting",
                    key_characters=["protagonist"],
                    main_event="Introduction to world",
                    advances_plot_thread="main",
                    emotional_tone="calm"
                ),
                ScenePlan(
                    scene_number=2,
                    scene_type="dialogue",
                    primary_location="Different location",
                    key_characters=["protagonist", "mentor"],
                    main_event="Important conversation",
                    advances_plot_thread="character_development",
                    emotional_tone="mysterious"
                ),
                ScenePlan(
                    scene_number=3,
                    scene_type="action",
                    primary_location="New location",
                    key_characters=["protagonist", "antagonist"],
                    main_event="First conflict",
                    advances_plot_thread="main",
                    emotional_tone="tense"
                )
            ]
        )


def validate_chapter_variety(scene_plans: List[ScenePlan]) -> Dict[str, Any]:
    """Validate that a chapter's scenes have sufficient variety.
    
    Args:
        scene_plans: List of scene plans to validate
        
    Returns:
        Dictionary with validation results and suggestions
    """
    validation = {
        'is_valid': True,
        'issues': [],
        'suggestions': []
    }
    
    # Check scene type variety
    scene_types = [s.scene_type for s in scene_plans]
    unique_types = set(scene_types)
    if len(unique_types) < len(scene_types) * 0.6:
        validation['is_valid'] = False
        validation['issues'].append("Too many scenes of the same type")
        validation['suggestions'].append(f"Use more varied scene types. Current: {', '.join(scene_types)}")
    
    # Check location variety
    locations = [s.primary_location for s in scene_plans]
    unique_locations = set(locations)
    if len(unique_locations) < len(locations) * 0.5:
        validation['is_valid'] = False
        validation['issues'].append("Too many scenes in the same location")
        validation['suggestions'].append("Move characters to different settings")
    
    # Check character rotation
    all_characters = []
    for scene in scene_plans:
        all_characters.extend(scene.key_characters)
    
    char_counts = {}
    for char in all_characters:
        char_counts[char] = char_counts.get(char, 0) + 1
    
    # Check if any character appears in every scene
    for char, count in char_counts.items():
        if count == len(scene_plans) and len(scene_plans) > 2:
            validation['issues'].append(f"{char} appears in every scene")
            validation['suggestions'].append(f"Give {char} some scenes off to allow other characters to develop")
    
    # Check emotional tone variety
    tones = [s.emotional_tone for s in scene_plans]
    unique_tones = set(tones)
    if len(unique_tones) < len(tones) * 0.5:
        validation['issues'].append("Insufficient emotional variety")
        validation['suggestions'].append("Vary emotional tones to create better pacing")
    
    return validation


def enforce_scene_variety_in_outline(chapter_outline: str, chapter_number: int) -> str:
    """Add explicit variety instructions to a chapter outline.
    
    Args:
        chapter_outline: Original chapter outline
        chapter_number: Chapter number
        
    Returns:
        Enhanced outline with variety instructions
    """
    variety_instructions = f"""

SCENE VARIETY REQUIREMENTS FOR CHAPTER {chapter_number}:
- Each scene must have a DIFFERENT primary purpose and structure
- Vary locations between scenes (don't stay in one place)
- Rotate which characters appear (avoid using the same group repeatedly)
- Use different scene types: action, dialogue, exploration, revelation, transition
- Vary emotional tones: tense, calm, mysterious, hopeful, somber
- NO repetitive patterns like "work→anomaly→vision→dismissal"

SPECIFIC SCENE GUIDANCE:"""

    if chapter_number == 1:
        variety_instructions += """
- Scene 1: Establish the normal world and protagonist's routine
- Scene 2: Introduce a NEW element (character, location, or situation)
- Scene 3: Show a DIFFERENT aspect of the world or conflict
- Scene 4: Create meaningful change or progression (not just "bigger anomaly")
"""
    else:
        variety_instructions += """
- Build on previous chapter's ending
- Introduce new complications or revelations
- Advance multiple plot threads
- Show character growth and change
"""

    return chapter_outline + variety_instructions