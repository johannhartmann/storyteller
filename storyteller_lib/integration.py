"""
StoryCraft Agent - Integration of pacing, dialogue, and exposition improvements.

This module provides functions to integrate the new pacing, dialogue, and exposition
modules into the existing storyteller system.
"""

from typing import Dict, List, Any
from storyteller_lib.models import StoryState
from storyteller_lib.config import llm

def integrate_improvements(state: StoryState) -> Dict:
    """
    Integrate pacing, dialogue, and exposition improvements into the scene writing process.
    
    Args:
        state: The current state
        
    Returns:
        Updates to the state with integrated improvements
    """
    # Import the new modules
    from storyteller_lib.pacing import generate_pacing_guidance
    from storyteller_lib.dialogue import generate_dialogue_guidance
    from storyteller_lib.exposition import check_and_generate_exposition_guidance
    
    # Get basic state information
    genre = state["genre"]
    tone = state["tone"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    characters = state["characters"]
    chapters = state["chapters"]
    
    # Determine chapter and scene position for context-aware guidance
    try:
        total_chapters = len(chapters)
        current_chapter_num = int(current_chapter)
        
        if current_chapter_num <= total_chapters / 3:
            chapter_position = "beginning"
        elif current_chapter_num <= 2 * total_chapters / 3:
            chapter_position = "middle"
        else:
            chapter_position = "end"
        
        # Get the current chapter data
        chapter = chapters[current_chapter]
        total_scenes = len(chapter["scenes"])
        current_scene_num = int(current_scene)
        
        if current_scene_num <= total_scenes / 3:
            scene_position = "beginning"
        elif current_scene_num <= 2 * total_scenes / 3:
            scene_position = "middle"
        else:
            scene_position = "end"
    except:
        # Default positions if calculation fails
        chapter_position = "middle"
        scene_position = "middle"
    
    # Determine scene purpose based on chapter outline and scene position
    scene_purpose = "advancing the plot"  # Default purpose
    chapter_outline = chapter.get("outline", "")
    
    if "character development" in chapter_outline.lower() or "character growth" in chapter_outline.lower():
        scene_purpose = "character development"
    elif "action" in chapter_outline.lower() or "battle" in chapter_outline.lower() or "fight" in chapter_outline.lower():
        scene_purpose = "action"
    elif "revelation" in chapter_outline.lower() or "discovery" in chapter_outline.lower() or "truth" in chapter_outline.lower():
        scene_purpose = "revelation"
    elif "mystery" in chapter_outline.lower() or "investigation" in chapter_outline.lower():
        scene_purpose = "mystery"
    elif "romance" in chapter_outline.lower() or "relationship" in chapter_outline.lower():
        scene_purpose = "relationship"
    
    # Generate pacing guidance
    pacing_guidance = generate_pacing_guidance(
        scene_purpose=scene_purpose,
        genre=genre,
        tone=tone,
        chapter_position=chapter_position,
        scene_position=scene_position
    )
    
    # Generate dialogue guidance
    dialogue_guidance = generate_dialogue_guidance(
        characters=characters,
        genre=genre,
        tone=tone
    )
    
    # Check for concepts to introduce and generate exposition guidance
    exposition_result = check_and_generate_exposition_guidance(state)
    exposition_guidance = exposition_result.get("exposition_guidance", "")
    concepts_to_introduce = exposition_result.get("concepts_to_introduce", [])
    
    # Combine all guidance
    integrated_guidance = {
        "pacing_guidance": pacing_guidance,
        "dialogue_guidance": dialogue_guidance,
        "exposition_guidance": exposition_guidance,
        "concepts_to_introduce": concepts_to_introduce,
        "scene_purpose": scene_purpose,
        "chapter_position": chapter_position,
        "scene_position": scene_position
    }
    
    return integrated_guidance

def post_scene_improvements(state: StoryState) -> Dict:
    """
    Apply post-generation improvements to the scene.
    
    Args:
        state: The current state
        
    Returns:
        Updates to the state with improved scene
    """
    # Import the improvement functions
    from storyteller_lib.pacing import analyze_and_optimize_scene
    from storyteller_lib.dialogue import analyze_and_improve_dialogue
    
    # Apply pacing improvements
    pacing_updates = analyze_and_optimize_scene(state)
    
    # If pacing was optimized, use the optimized scene for dialogue improvements
    if pacing_updates.get("pacing_optimized", False):
        # Create a new state with the pacing-optimized scene
        updated_state = state.copy()
        current_chapter = state["current_chapter"]
        current_scene = state["current_scene"]
        
        # Update the scene content in the state copy
        updated_state["chapters"][current_chapter]["scenes"][current_scene]["content"] = (
            pacing_updates["chapters"][current_chapter]["scenes"][current_scene]["content"]
        )
        
        # Apply dialogue improvements to the pacing-optimized scene
        dialogue_updates = analyze_and_improve_dialogue(updated_state)
    else:
        # Apply dialogue improvements to the original scene
        dialogue_updates = analyze_and_improve_dialogue(state)
    
    # Combine updates
    combined_updates = {
        "chapters": {
            state["current_chapter"]: {
                "scenes": {
                    state["current_scene"]: {}
                }
            }
        }
    }
    
    # Add pacing analysis
    if "pacing_analysis" in pacing_updates["chapters"][state["current_chapter"]]["scenes"][state["current_scene"]]:
        combined_updates["chapters"][state["current_chapter"]]["scenes"][state["current_scene"]]["pacing_analysis"] = (
            pacing_updates["chapters"][state["current_chapter"]]["scenes"][state["current_scene"]]["pacing_analysis"]
        )
    
    # Add dialogue analysis
    if "dialogue_analysis" in dialogue_updates["chapters"][state["current_chapter"]]["scenes"][state["current_scene"]]:
        combined_updates["chapters"][state["current_chapter"]]["scenes"][state["current_scene"]]["dialogue_analysis"] = (
            dialogue_updates["chapters"][state["current_chapter"]]["scenes"][state["current_scene"]]["dialogue_analysis"]
        )
    
    # Use the final improved content
    if dialogue_updates.get("dialogue_improved", False):
        combined_updates["chapters"][state["current_chapter"]]["scenes"][state["current_scene"]]["content"] = (
            dialogue_updates["chapters"][state["current_chapter"]]["scenes"][state["current_scene"]]["content"]
        )
    elif pacing_updates.get("pacing_optimized", False):
        combined_updates["chapters"][state["current_chapter"]]["scenes"][state["current_scene"]]["content"] = (
            pacing_updates["chapters"][state["current_chapter"]]["scenes"][state["current_scene"]]["content"]
        )
    
    # Add improvement flags
    combined_updates["pacing_optimized"] = pacing_updates.get("pacing_optimized", False)
    combined_updates["dialogue_improved"] = dialogue_updates.get("dialogue_improved", False)
    
    return combined_updates

def update_concept_introduction_statuses(state: StoryState) -> Dict:
    """
    Update the introduction status of key concepts in the scene.
    
    Args:
        state: The current state
        
    Returns:
        Updates to the state
    """
    from storyteller_lib.exposition import analyze_concept_clarity, update_concept_introduction_status
    
    # Get the concepts that were supposed to be introduced
    concepts_to_introduce = state.get("concepts_to_introduce", [])
    
    if not concepts_to_introduce:
        return {}
    
    # Get the scene content
    chapters = state["chapters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    scene_content = chapters[current_chapter]["scenes"][current_scene]["content"]
    
    # Check each concept for introduction
    concept_updates = {}
    for concept in concepts_to_introduce:
        concept_name = concept["name"]
        
        # Analyze how clearly the concept was introduced
        clarity_analysis = analyze_concept_clarity(scene_content, concept_name)
        
        # If the concept was introduced with sufficient clarity, update its status
        if clarity_analysis["clarity_score"] >= 6:
            update_result = update_concept_introduction_status(state, concept_name)
            
            # Store the clarity analysis
            if update_result:
                concept_updates[concept_name] = {
                    "introduced": True,
                    "clarity_analysis": clarity_analysis
                }
    
    return {
        "concept_introductions": concept_updates
    }