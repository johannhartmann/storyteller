"""
Dramatic arc analysis for StoryCraft Agent.

This module analyzes dramatic structure to ensure scene breaks are motivated
by narrative necessity rather than arbitrary divisions.
"""

from typing import Dict, List, Any, Optional, Tuple
from storyteller_lib.logger import get_logger
from storyteller_lib.models import StoryState
from storyteller_lib.database_integration import get_db_manager

logger = get_logger(__name__)


def analyze_dramatic_necessity(
    current_scene_outline: str,
    next_scene_outline: str,
    active_plot_threads: List[Dict],
    current_tension: int,
    next_tension: int,
    current_purpose: str,
    next_purpose: str
) -> Dict[str, Any]:
    """
    Determine if a scene break is dramatically necessary or if content should flow continuously.
    
    Args:
        current_scene_outline: Outline of the current scene
        next_scene_outline: Outline of the next scene
        active_plot_threads: List of active plot threads
        current_tension: Tension level of current scene (1-10)
        next_tension: Tension level of next scene (1-10)
        current_purpose: Dramatic purpose of current scene
        next_purpose: Dramatic purpose of next scene
        
    Returns:
        Dictionary containing:
        - needs_scene_break: bool - Whether a scene break is necessary
        - break_type: str - 'hard' (new scene), 'soft' (section break), 'none' (continuous)
        - transition_guidance: str - How to handle the transition
        - merge_recommendation: bool - Whether scenes should be merged
    """
    
    # Analyze tension change
    tension_change = abs(next_tension - current_tension)
    
    # Analyze purpose transition
    purpose_transitions = {
        ('setup', 'rising_action'): 'soft',
        ('rising_action', 'climax'): 'hard',
        ('climax', 'falling_action'): 'hard',
        ('falling_action', 'resolution'): 'soft',
        ('resolution', 'setup'): 'hard',  # New sequence
    }
    
    # Default break type based on purpose transition
    default_break = purpose_transitions.get((current_purpose, next_purpose), 'soft')
    
    # Determine if break is necessary
    needs_break = True
    break_type = default_break
    merge_recommendation = False
    
    # Cases where scenes should merge
    if (tension_change <= 2 and 
        current_purpose == next_purpose and
        len(active_plot_threads) < 3):
        needs_break = False
        break_type = 'none'
        merge_recommendation = True
        transition_guidance = "These scenes flow naturally together and should be combined into a single continuous narrative."
    
    # Cases requiring hard breaks
    elif (tension_change >= 5 or
          current_purpose == 'climax' or
          next_purpose == 'climax'):
        needs_break = True
        break_type = 'hard'
        transition_guidance = "A clear scene break is needed due to significant dramatic shift."
    
    # Soft breaks for moderate changes
    elif tension_change >= 3:
        needs_break = True
        break_type = 'soft'
        transition_guidance = "A section break (***) would provide a gentle pause while maintaining flow."
    
    # Default soft break
    else:
        needs_break = True
        break_type = 'soft'
        transition_guidance = "A soft transition maintains narrative momentum."
    
    return {
        'needs_scene_break': needs_break,
        'break_type': break_type,
        'transition_guidance': transition_guidance,
        'merge_recommendation': merge_recommendation,
        'tension_analysis': {
            'current': current_tension,
            'next': next_tension,
            'change': tension_change
        },
        'purpose_analysis': {
            'current': current_purpose,
            'next': next_purpose,
            'natural_flow': current_purpose == next_purpose
        }
    }


def get_scene_dramatic_context(state: StoryState, chapter_num: str, scene_num: str) -> Dict[str, Any]:
    """
    Get the dramatic context for a specific scene from the story state.
    
    Args:
        state: Current story state
        chapter_num: Chapter number
        scene_num: Scene number
        
    Returns:
        Dictionary with dramatic context information
    """
    chapters = state.get("chapters", {})
    chapter = chapters.get(chapter_num, {})
    scenes = chapter.get("scenes", {})
    scene = scenes.get(scene_num, {})
    
    return {
        'dramatic_purpose': scene.get('dramatic_purpose', 'development'),
        'tension_level': scene.get('tension_level', 5),
        'ends_with': scene.get('ends_with', 'transition'),
        'connects_to_next': scene.get('connects_to_next', '')
    }


def should_merge_scenes(
    scene1_outline: str,
    scene2_outline: str,
    scene1_drama: Dict[str, Any],
    scene2_drama: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Determine if two adjacent scenes should be merged into one.
    
    Args:
        scene1_outline: First scene outline
        scene2_outline: Second scene outline
        scene1_drama: First scene dramatic context
        scene2_drama: Second scene dramatic context
        
    Returns:
        Tuple of (should_merge: bool, reason: str)
    """
    # Check for natural flow
    if (scene1_drama['dramatic_purpose'] == scene2_drama['dramatic_purpose'] and
        abs(scene1_drama['tension_level'] - scene2_drama['tension_level']) <= 2 and
        scene1_drama['ends_with'] in ['soft_transition', 'transition']):
        
        # Check if both scenes are short
        if len(scene1_outline) < 200 and len(scene2_outline) < 200:
            return True, "Both scenes are short and have similar dramatic purpose"
        
        # Check if they're part of the same sequence
        if scene1_drama['connects_to_next'] and 'immediate' in scene1_drama['connects_to_next'].lower():
            return True, "Scenes are marked as immediately connected"
    
    return False, "Scenes serve different dramatic purposes"


def plan_chapter_dramatic_arc(
    chapter_outline: str,
    num_scenes: int,
    chapter_position: str,  # 'beginning', 'middle', 'end'
    story_genre: str,
    story_tone: str
) -> List[Dict[str, Any]]:
    """
    Plan the dramatic arc for all scenes in a chapter.
    
    Args:
        chapter_outline: The chapter outline
        num_scenes: Number of scenes in the chapter
        chapter_position: Position of chapter in story
        story_genre: Story genre
        story_tone: Story tone
        
    Returns:
        List of dramatic specifications for each scene
    """
    dramatic_specs = []
    
    # Define arc patterns based on chapter position
    if chapter_position == 'beginning':
        # Start slow, build gradually
        base_pattern = [
            ('setup', 3), ('setup', 4), ('rising_action', 5), ('rising_action', 6)
        ]
    elif chapter_position == 'end':
        # High tension, climax, resolution
        base_pattern = [
            ('rising_action', 7), ('climax', 9), ('falling_action', 6), ('resolution', 4)
        ]
    else:
        # Middle chapters - varied pattern
        base_pattern = [
            ('rising_action', 5), ('rising_action', 7), ('climax', 8), ('falling_action', 5)
        ]
    
    # Adjust pattern to match number of scenes
    pattern = []
    for i in range(num_scenes):
        idx = min(i, len(base_pattern) - 1)
        pattern.append(base_pattern[idx])
    
    # Create dramatic specs for each scene
    for i, (purpose, tension) in enumerate(pattern):
        # Determine ending type
        if i == num_scenes - 1:  # Last scene
            ends_with = 'cliffhanger' if chapter_position != 'end' else 'resolution'
        elif purpose == 'climax':
            ends_with = 'hard_break'
        elif i < num_scenes - 1 and pattern[i+1][0] != purpose:
            ends_with = 'soft_transition'
        else:
            ends_with = 'transition'
        
        # Determine connection to next
        if i < num_scenes - 1:
            if pattern[i+1][1] - tension >= 3:
                connects = "Tension builds significantly"
            elif pattern[i+1][0] != purpose:
                connects = f"Shifts from {purpose} to {pattern[i+1][0]}"
            else:
                connects = "Continues current thread"
        else:
            connects = "Leads to next chapter"
        
        dramatic_specs.append({
            'scene_number': i + 1,
            'dramatic_purpose': purpose,
            'tension_level': tension,
            'ends_with': ends_with,
            'connects_to_next': connects
        })
    
    return dramatic_specs