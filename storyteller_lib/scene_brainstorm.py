"""Scene brainstorming module for StoryCraft Agent.

This module handles the creative brainstorming phase of scene generation,
including plot thread integration, character dynamics, and creative elements.
"""

# Standard library imports
from typing import Any, Dict, List

# Third party imports
from langchain_core.messages import HumanMessage

# Local imports
from storyteller_lib import track_progress
from storyteller_lib.config import MEMORY_NAMESPACE, llm, manage_memory_tool, search_memory_tool
from storyteller_lib.constants import NodeNames, SceneElements
from storyteller_lib.creative_tools import creative_brainstorm
from storyteller_lib.models import StoryState
from storyteller_lib.plot_threads import get_active_plot_threads_for_scene


def _prepare_creative_guidance(creative_elements: Dict, current_chapter: str, current_scene: str) -> str:
    """Prepare creative guidance based on brainstormed elements.
    
    Args:
        creative_elements: Dictionary of creative elements from brainstorming
        current_chapter: Current chapter number
        current_scene: Current scene number
        
    Returns:
        Formatted creative guidance string
    """
    # Keep it concise and scene-focused - we'll use these in the prompt
    guidance = f"\nCREATIVE ELEMENTS for Chapter {current_chapter}, Scene {current_scene}:\n"
    
    if "plot_progression" in creative_elements:
        guidance += f"Plot Progression: {creative_elements['plot_progression']}\n"
    
    if "character_dynamics" in creative_elements:
        guidance += f"Character Dynamics: {creative_elements['character_dynamics']}\n"
        
    if "scene_purpose" in creative_elements:
        guidance += f"Scene Purpose: {creative_elements['scene_purpose']}\n"
        
    if "creative_opportunities" in creative_elements:
        guidance += f"Creative Opportunities: {creative_elements['creative_opportunities']}\n"
    
    return guidance


def _prepare_plot_thread_guidance(active_plot_threads: List[Dict]) -> str:
    """Prepare guidance for active plot threads in the scene.
    
    Args:
        active_plot_threads: List of active plot thread dictionaries
        
    Returns:
        Formatted plot thread guidance string
    """
    if not active_plot_threads:
        return ""
        
    guidance = "\nACTIVE PLOT THREADS for this scene:\n"
    for thread in active_plot_threads:
        guidance += f"\n{thread['name']} ({thread['type']}):\n"
        guidance += f"  Status: {thread['status']}\n"
        guidance += f"  Current Development: {thread['current_development']}\n"
        
        if thread.get('next_steps'):
            guidance += f"  Next Steps: {thread['next_steps']}\n"
            
        if thread.get('tension_level'):
            guidance += f"  Tension Level: {thread['tension_level']}\n"
            
        if thread.get('involved_characters'):
            guidance += f"  Characters Involved: {', '.join(thread['involved_characters'])}\n"
            
        # Add guidance about how this thread should progress in this scene
        if thread['type'] == 'main_plot':
            guidance += "  >>> This is a MAIN PLOT thread. It should drive the primary narrative forward.\n"
        elif thread['type'] == 'subplot':
            guidance += "  >>> This subplot should complement the main narrative without overshadowing it.\n"
        elif thread['type'] == 'character_arc':
            guidance += "  >>> Focus on character development and emotional growth.\n"
        elif thread['type'] == 'mystery':
            guidance += "  >>> Reveal information carefully, maintaining suspense.\n"
        elif thread['type'] == 'relationship':
            guidance += "  >>> Explore the dynamics between characters.\n"
    
    return guidance


def brainstorm_scene_elements(state: StoryState) -> Dict:
    """Brainstorm creative elements for the upcoming scene.
    
    This node generates creative ideas and approaches for the scene,
    considering plot threads, character dynamics, and story progression.
    
    Args:
        state: Current story state
        
    Returns:
        Updated state with brainstormed scene elements
    """
    
    current_chapter = state.get("current_chapter", "1")
    current_scene = state.get("current_scene", "1")
    chapter_outline = state["chapters"][current_chapter]["outline"]
    # Get scene description from the scene's description field if it exists
    scene_data = state["chapters"][current_chapter]["scenes"][current_scene]
    scene_description = scene_data.get("description", scene_data.get("outline", ""))
    
    # Get active plot threads for this scene
    active_plot_threads = get_active_plot_threads_for_scene(state)
    
    # Get the overall story context
    story_context = state.get("story_premise", "")
    genre = state.get("genre", "fantasy")
    tone = state.get("tone", "adventurous")
    
    # Prepare plot thread information for brainstorming
    plot_thread_context = ""
    if active_plot_threads:
        plot_thread_context = "\nActive plot threads to consider:\n"
        for thread in active_plot_threads:
            plot_thread_context += f"- {thread['name']}: {thread['current_development']}\n"
    
    # Use creative brainstorming for scene approach
    brainstorm_result = creative_brainstorm(
        topic=f"scene approach for Chapter {current_chapter}, Scene {current_scene}",
        genre=genre,
        context=f"""
        Story Context: {story_context}
        Chapter Outline: {chapter_outline}
        Scene Description: {scene_description}
        {plot_thread_context}
        
        Consider:
        1. How to advance the plot threads naturally
        2. Character dynamics and emotional beats
        3. The scene's purpose in the larger narrative
        4. Creative ways to engage the reader
        5. Sensory details and atmosphere
        """,
        num_ideas=3,
        tone=tone
    )
    
    # Extract the best approach
    scene_elements = {
        "creative_approach": brainstorm_result.get("recommended_ideas", ""),
        "plot_progression": "Advance key plot threads naturally through character actions",
        "character_dynamics": "Focus on character interactions and emotional depth",
        "scene_purpose": f"Advance the narrative while developing character relationships",
        "creative_opportunities": brainstorm_result.get("ideas", "")[:500] if brainstorm_result.get("ideas") else ""
    }
    
    # Store the brainstormed elements in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"scene_elements_ch{current_chapter}_sc{current_scene}",
        "value": scene_elements,
        "namespace": MEMORY_NAMESPACE
    })
    
    # Update state
    state["scene_elements"] = scene_elements
    state["active_plot_threads"] = active_plot_threads
    state["last_node"] = NodeNames.BRAINSTORM_SCENE
    
    
    return state