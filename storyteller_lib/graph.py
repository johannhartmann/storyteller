"""
StoryCraft Agent - Graph construction and routing logic.
"""

from typing import Dict, List, Any

from langgraph.graph import StateGraph, START, END
from operator import add  # Default reducer for lists

from storyteller_lib.models import StoryState

# The revelations_reducer is now implemented in models.py using the Annotated typing pattern
from storyteller_lib.config import store
from storyteller_lib.initialization import initialize_state, brainstorm_story_concepts
from storyteller_lib.outline import generate_story_outline, generate_characters, plan_chapters
from storyteller_lib.scenes import (
    brainstorm_scene_elements, 
    write_scene, 
    reflect_on_scene, 
    revise_scene_if_needed
)
from storyteller_lib.progression import (
    update_character_profiles, 
    review_continuity,
    resolve_continuity_issues,
    advance_to_next_scene_or_chapter, 
    compile_final_story
)
from storyteller_lib import track_progress

# Router function
# Routing functions for proper LangGraph conditional edges
def should_brainstorm_concepts(state: StoryState) -> str:
    """Determine if we need to brainstorm story concepts."""
    if "global_story" not in state or not state["global_story"]:
        if "creative_elements" not in state or not state.get("creative_elements"):
            return "brainstorm_story_concepts"
    return None

def should_generate_outline(state: StoryState) -> str:
    """Determine if we need to generate a story outline."""
    if "global_story" not in state or not state["global_story"]:
        if "creative_elements" in state and state.get("creative_elements"):
            return "generate_story_outline"
    return None

def should_generate_characters(state: StoryState) -> str:
    """Determine if we need to generate character profiles."""
    if "global_story" in state and state["global_story"] and ("characters" not in state or not state["characters"]):
        return "generate_characters"
    return None

def should_plan_chapters(state: StoryState) -> str:
    """Determine if we need to plan chapters."""
    if "characters" in state and state["characters"] and ("chapters" not in state or not state["chapters"]):
        return "plan_chapters"
    return None

def should_compile_story(state: StoryState) -> str:
    """Determine if we should compile the final story."""
    if state.get("completed", False):
        return "compile_final_story"
    return None

def determine_scene_action(state: StoryState) -> str:
    """Determine what action to take for the current scene."""
    # Safety checks
    current_chapter = state.get("current_chapter", "")
    current_scene = state.get("current_scene", "")
    
    # Safety check - if current_chapter or current_scene are not set, go to plan_chapters
    if not current_chapter or not current_scene:
        print("WARNING: Current chapter or scene not set. Going back to planning.")
        return "plan_chapters"
        
    # Safety check - make sure the chapter exists in the chapters dictionary
    if current_chapter not in state.get("chapters", {}):
        print(f"WARNING: Chapter {current_chapter} not found. Going back to planning.")
        return "plan_chapters"
        
    chapter = state["chapters"][current_chapter]
    
    # Safety check - make sure the scene exists in the chapter
    if current_scene not in chapter.get("scenes", {}):
        print(f"WARNING: Scene {current_scene} not found in chapter {current_chapter}. Moving to next chapter.")
        return "advance_to_next_scene_or_chapter"
    
    # Check if we need to brainstorm for the current scene
    scene_creative_key = f"scene_elements_ch{current_chapter}_sc{current_scene}"
    if "creative_elements" not in state or scene_creative_key not in state.get("creative_elements", {}):
        return "brainstorm_scene_elements"
    
    # Check if the current scene has content
    if not chapter["scenes"][current_scene].get("content"):
        return "write_scene"
    
    # Check if the current scene has reflection notes
    if not chapter["scenes"][current_scene].get("reflection_notes"):
        return "reflect_on_scene"
        
    # Check if we're in a revision cycle (if we have the revision marker in reflection_notes)
    if (chapter["scenes"][current_scene].get("reflection_notes") and 
          len(chapter["scenes"][current_scene]["reflection_notes"]) == 1 and 
          chapter["scenes"][current_scene]["reflection_notes"][0] == "Scene has been revised"):
        # Skip reflection and move to character profiles
        # Reset character update count when starting new updates
        state["character_update_count"] = 0
        return "update_character_profiles"
    
    # Check based on last node
    last_node = state.get("last_node", "")
    
    # After reflection or revision, update character profiles
    if last_node == "reflect_on_scene" or last_node == "revise_scene_if_needed":
        # Reset character update count when starting new updates
        state["character_update_count"] = 0
        return "update_character_profiles"
    
    # Check if we've updated characters and need to move to the next scene/chapter
    elif last_node == "update_character_profiles":
        # Get counter to prevent infinite loops in character profile updates
        character_update_count = state.get("character_update_count", 0)
        
        # If we've processed this more than once, force advance to next step
        if character_update_count > 0:
            print(f"NOTICE: Forced advance after multiple character profile updates")
            return "advance_to_next_scene_or_chapter"
        
        # Check if we've completed a chapter
        all_scenes_complete = True
        for scene in chapter["scenes"].values():
            if not scene.get("content") or not scene.get("reflection_notes"):
                all_scenes_complete = False
                break
        
        # Check if we need to do a continuity review or move to next scene/chapter
        if all_scenes_complete:
            return "review_continuity"
        else:
            return "advance_to_next_scene_or_chapter"
            
        # IMPORTANT: Do not return "update_character_profiles" here to avoid loops
    
    # Handle continuity review state transitions based on phase
    elif last_node == "review_continuity":
        continuity_phase = state.get("continuity_phase", "complete")
        global_recursion_count = state.get("global_recursion_count", 0)
        review_flags = state.get("continuity_review_flags", {})
        current_chapter = state.get("current_chapter", "1")
        review_key = f"continuity_review_ch{current_chapter}"
        
        print(f"Continuity review phase: {continuity_phase}, recursion count: {global_recursion_count}")
        
        # Safety check - if we've already processed too many iterations or this chapter is flagged as reviewed, force advance
        if global_recursion_count > 5 or (review_key in review_flags and review_flags[review_key]):
            print("⚠️ Excessive recursion or chapter already reviewed, forcing advance")
            return "advance_to_next_scene_or_chapter"
        
        # Route based on the continuity phase
        if continuity_phase == "needs_resolution":
            print("🔍 Routing to continuity resolution node")
            # We no longer need to directly modify state here since the functions now
            # return these values in their response dictionaries
            return "resolve_continuity_issues"
        else:
            print("✓ Continuity review complete, advancing")
            return "advance_to_next_scene_or_chapter"
            
    # Handle continuity resolution
    elif last_node == "resolve_continuity_issues":
        continuity_phase = state.get("continuity_phase", "complete")
        resolution_index = state.get("resolution_index", 0)
        global_recursion_count = state.get("global_recursion_count", 0)
        review_flags = state.get("continuity_review_flags", {})
        current_chapter = state.get("current_chapter", "1")
        review_key = f"continuity_review_ch{current_chapter}"
        
        print(f"Continuity resolution phase: {continuity_phase}, index: {resolution_index}, recursion: {global_recursion_count}")
        
        # Safety check - if we're stuck in a loop or chapter is marked as done, force advance
        if global_recursion_count > 5 or (review_key in review_flags and review_flags[review_key]):
            print("⚠️ Excessive recursion or chapter already resolved, forcing advance")
            return "advance_to_next_scene_or_chapter"
        
        # Only check for pending issues if we're in the needs_resolution phase
        if continuity_phase == "needs_resolution":
            # Check if there are more issues to resolve by examining revelations
            has_pending_issues = False
            for review in state.get("revelations", {}).get("continuity_issues", []):
                if review.get("needs_resolution") and review.get("resolution_status") == "pending":
                    has_pending_issues = True
                    break
                    
            # If we have pending issues and aren't stuck in a loop, continue resolution
            if has_pending_issues and resolution_index > 0 and global_recursion_count < 5:
                print("🔄 Continuing continuity resolution process")
                return "resolve_continuity_issues"
        
        # Default to advancing if we're done or any condition isn't met
        print("✓ Continuity resolution complete, advancing")
        return "advance_to_next_scene_or_chapter"
    
    # Default to writing the next scene
    return "write_scene"

# Main routing function using LangGraph pattern
def route_next_step(state: StoryState) -> str:
    """Determine the next node based on state conditions."""
    # Track router calls for infinite loop detection
    router_count = state.get("router_count", 0) + 1
    state["router_count"] = router_count
    
    # If we've hit the router too many times, something is wrong - go to final node
    if router_count > 50:
        print("WARNING: Router has been called too many times. Terminating execution.")
        state["completed"] = True
        return "compile_final_story"
    
    # Try each routing function in sequence
    for route_func in [
        should_brainstorm_concepts,
        should_generate_outline,
        should_generate_characters, 
        should_plan_chapters,
        should_compile_story,
        determine_scene_action
    ]:
        result = route_func(state)
        if result:
            # When switching to a node other than update_character_profiles, reset the counter
            if result != "update_character_profiles":
                state["character_update_count"] = 0
            return result
    
    # Safety fallback
    print("WARNING: No routing rule matched. Terminating execution.")
    state["completed"] = True
    return "compile_final_story"

# Build the graph
def build_story_graph():
    """
    Build and compile the story generation graph.
    """
    # Create a state graph using Annotated type hints for custom reducers
    graph_builder = StateGraph(
        StoryState
    )
    
    # Add nodes
    graph_builder.add_node("initialize_state", initialize_state)
    graph_builder.add_node("brainstorm_story_concepts", brainstorm_story_concepts)
    graph_builder.add_node("generate_story_outline", generate_story_outline)
    graph_builder.add_node("generate_characters", generate_characters)
    graph_builder.add_node("plan_chapters", plan_chapters)
    graph_builder.add_node("brainstorm_scene_elements", brainstorm_scene_elements)
    graph_builder.add_node("write_scene", write_scene)
    graph_builder.add_node("reflect_on_scene", reflect_on_scene)
    graph_builder.add_node("revise_scene_if_needed", revise_scene_if_needed)
    graph_builder.add_node("update_character_profiles", update_character_profiles)
    graph_builder.add_node("review_continuity", review_continuity)
    graph_builder.add_node("resolve_continuity_issues", resolve_continuity_issues)  # New node for continuity resolution
    graph_builder.add_node("advance_to_next_scene_or_chapter", advance_to_next_scene_or_chapter)
    graph_builder.add_node("compile_final_story", compile_final_story)
    
    # Set up the entry point
    graph_builder.add_edge(START, "initialize_state")
    
    # Create edges for initialization and direct transitions
    graph_builder.add_edge("reflect_on_scene", "revise_scene_if_needed")
    graph_builder.add_edge("compile_final_story", END)
    
    # Create a single conditional edge from initialization to route all workflow steps
    graph_builder.add_conditional_edges(
        "initialize_state", 
        route_next_step,
        {
            "brainstorm_story_concepts": "brainstorm_story_concepts",
            "generate_story_outline": "generate_story_outline",
            "generate_characters": "generate_characters",
            "plan_chapters": "plan_chapters",
            "compile_final_story": "compile_final_story",
        }
    )
    
    # Create conditional edges for standard nodes
    for node in [
        "brainstorm_story_concepts", 
        "generate_story_outline", 
        "generate_characters", 
        "plan_chapters",
        "brainstorm_scene_elements", 
        "write_scene", 
        "revise_scene_if_needed", 
        "review_continuity",
        "resolve_continuity_issues",  # Add the new node 
        "advance_to_next_scene_or_chapter"
    ]:
        graph_builder.add_conditional_edges(
            node, 
            route_next_step,
            {
                "brainstorm_story_concepts": "brainstorm_story_concepts",
                "generate_story_outline": "generate_story_outline",
                "generate_characters": "generate_characters",
                "plan_chapters": "plan_chapters",
                "brainstorm_scene_elements": "brainstorm_scene_elements",
                "write_scene": "write_scene",
                "reflect_on_scene": "reflect_on_scene",
                "update_character_profiles": "update_character_profiles",
                "review_continuity": "review_continuity",
                "resolve_continuity_issues": "resolve_continuity_issues",  # Add route to the new node
                "advance_to_next_scene_or_chapter": "advance_to_next_scene_or_chapter",
                "compile_final_story": "compile_final_story"
            }
        )
        
    # Define a simple condition function to check if a chapter is complete
    def is_chapter_complete(state: StoryState) -> bool:
        """Check if the current chapter has all scenes completed."""
        current_chapter = state.get("current_chapter", "")
        
        # Check if we have a valid chapter
        if current_chapter not in state.get("chapters", {}):
            return False
            
        chapter = state["chapters"][current_chapter]
        
        # Check if all scenes in the chapter are complete
        for scene in chapter.get("scenes", {}).values():
            if not scene.get("content") or not scene.get("reflection_notes"):
                return False
                
        return True
    
    # Direct conditional edges from update_character_profiles to next steps
    # This node can only go to review_continuity or advance_to_next_scene_or_chapter
    graph_builder.add_conditional_edges(
        "update_character_profiles",
        # Use a lambda that checks if chapter is complete
        lambda state: "review_continuity" if is_chapter_complete(state) else "advance_to_next_scene_or_chapter",
        {
            "review_continuity": "review_continuity",
            "advance_to_next_scene_or_chapter": "advance_to_next_scene_or_chapter"
        }
    )
    
    # Compile the graph with a higher recursion limit to allow for longer stories
    graph = graph_builder.compile()
    
    # Return the compiled graph
    return graph