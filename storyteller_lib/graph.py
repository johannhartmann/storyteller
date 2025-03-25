"""
StoryCraft Agent - Graph construction with native LangGraph edges.

This is a refactored version of the graph.py file that uses LangGraph's native edge system
instead of a custom router function, which should prevent recursion limit errors.
It also uses SQLite for persistent storage instead of in-memory storage.
"""

from typing import Dict, List, Any

from langgraph.graph import StateGraph, START, END
from operator import add  # Default reducer for lists

from storyteller_lib.models import StoryState
# No checkpointer needed for single-session generation
from storyteller_lib.initialization import initialize_state, brainstorm_story_concepts
from storyteller_lib.outline import generate_story_outline, generate_characters, plan_chapters
from storyteller_lib.worldbuilding import generate_worldbuilding
from storyteller_lib.scenes import (
    brainstorm_scene_elements,
    write_scene,
    process_showing_telling,
    reflect_on_scene,
    revise_scene_if_needed
)
# Import the optimized progression functions
from storyteller_lib.progression import (
    update_world_elements,
    update_character_profiles,
    review_continuity,
    resolve_continuity_issues,
    advance_to_next_scene_or_chapter,
    compile_final_story
)
from storyteller_lib import track_progress

# Replace the monolithic router with specific condition functions

def should_brainstorm_concepts(state: StoryState) -> bool:
    """Determine if we need to brainstorm story concepts."""
    return "global_story" not in state or not state["global_story"]

def should_generate_outline(state: StoryState) -> bool:
    """Determine if we need to generate a story outline."""
    has_concepts = "creative_elements" in state and state.get("creative_elements")
    no_outline = "global_story" not in state or not state["global_story"]
    return has_concepts and no_outline

def should_generate_worldbuilding(state: StoryState) -> bool:
    """Determine if we need to generate worldbuilding elements."""
    has_outline = "global_story" in state and state["global_story"]
    no_world_elements = "world_elements" not in state or not state["world_elements"]
    return has_outline and no_world_elements

def should_generate_characters(state: StoryState) -> bool:
    """Determine if we need to generate character profiles."""
    has_worldbuilding = "world_elements" in state and state["world_elements"]
    no_characters = "characters" not in state or not state["characters"]
    return has_worldbuilding and no_characters

def should_plan_chapters(state: StoryState) -> bool:
    """Determine if we need to plan chapters."""
    has_characters = "characters" in state and state["characters"]
    no_chapters = "chapters" not in state or not state["chapters"]
    return has_characters and no_chapters

def is_story_completed(state: StoryState) -> bool:
    """Determine if the story is completed."""
    return state.get("completed", False)

def is_scene_brainstorming_needed(state: StoryState) -> bool:
    """Check if scene elements need to be brainstormed."""
    current_chapter = state.get("current_chapter", "")
    current_scene = state.get("current_scene", "")
    
    if not current_chapter or not current_scene:
        return False
        
    if current_chapter not in state.get("chapters", {}):
        return False
        
    scene_creative_key = f"scene_elements_ch{current_chapter}_sc{current_scene}"
    return "creative_elements" not in state or scene_creative_key not in state.get("creative_elements", {})

def is_scene_writing_needed(state: StoryState) -> bool:
    """Check if the current scene needs to be written."""
    current_chapter = state.get("current_chapter", "")
    current_scene = state.get("current_scene", "")
    
    if not current_chapter or not current_scene:
        return False
        
    if current_chapter not in state.get("chapters", {}):
        return False
        
    if current_scene not in state["chapters"][current_chapter].get("scenes", {}):
        return False
        
    return not state["chapters"][current_chapter]["scenes"][current_scene].get("content")

def is_scene_reflection_needed(state: StoryState) -> bool:
    """Check if scene reflection is needed."""
    current_chapter = state.get("current_chapter", "")
    current_scene = state.get("current_scene", "")
    
    if not current_chapter or not current_scene:
        return False
        
    if current_chapter not in state.get("chapters", {}):
        return False
        
    if current_scene not in state["chapters"][current_chapter].get("scenes", {}):
        return False
        
    # Check if the scene has content but no reflection notes
    scene = state["chapters"][current_chapter]["scenes"][current_scene]
    return scene.get("content") and not scene.get("reflection_notes")

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

def needs_continuity_resolution(state: StoryState) -> bool:
    """Check if continuity issues need resolution."""
    continuity_phase = state.get("continuity_phase", "complete")
    return continuity_phase == "needs_resolution"

def has_more_issues_to_resolve(state: StoryState) -> bool:
    """Check if there are more continuity issues to resolve."""
    # First check the phase - if not in resolution mode, no issues to resolve
    continuity_phase = state.get("continuity_phase", "complete")
    if continuity_phase != "needs_resolution":
        return False
    
    # Get current issue index and count
    resolution_index = state.get("resolution_index", 0)
    
    # Find pending issues from revelations
    continuity_reviews = state.get("revelations", {}).get("continuity_issues", [])
    current_review = None
    for review in continuity_reviews:
        if review.get("needs_resolution") and review.get("resolution_status") == "pending":
            current_review = review
            break
    
    # If no review pending or no issues to resolve, we're done
    if not current_review:
        return False
    
    # Check if there are more issues to process
    issues_to_resolve = current_review.get("issues_to_resolve", [])
    return resolution_index < len(issues_to_resolve)

def decide_after_chapter_profiles(state: StoryState) -> str:
    """Decide what to do after updating character profiles."""
    if is_chapter_complete(state):
        return "review_continuity"
    else:
        return "advance_to_next_scene_or_chapter"

def decide_after_continuity_review(state: StoryState) -> str:
    """Decide what to do after continuity review."""
    # Simply check if resolution is needed based on the continuity phase
    # This relies on LangGraph's proper state management
    if needs_continuity_resolution(state):
        return "resolve_continuity_issues"
    else:
        return "advance_to_next_scene_or_chapter"

def decide_after_continuity_resolution(state: StoryState) -> str:
    """Decide what to do after continuity resolution."""
    if has_more_issues_to_resolve(state):
        return "resolve_continuity_issues"
    else:
        return "advance_to_next_scene_or_chapter"

def decide_after_advancing(state: StoryState) -> str:
    """Decide what to do after advancing to the next scene or chapter."""
    if is_story_completed(state):
        return "compile_final_story"
    else:
        return "brainstorm_scene_elements"

# Build the graph with native LangGraph edges
def build_story_graph():
    """
    Build and compile the story generation graph using LangGraph's native edge system.
    """
    # Create a state graph using Annotated type hints for custom reducers
    graph_builder = StateGraph(
        StoryState
    )
    
    # Add nodes
    graph_builder.add_node("initialize_state", initialize_state)
    graph_builder.add_node("brainstorm_story_concepts", brainstorm_story_concepts)
    graph_builder.add_node("generate_story_outline", generate_story_outline)
    graph_builder.add_node("generate_worldbuilding", generate_worldbuilding)
    graph_builder.add_node("generate_characters", generate_characters)
    graph_builder.add_node("plan_chapters", plan_chapters)
    graph_builder.add_node("brainstorm_scene_elements", brainstorm_scene_elements)
    graph_builder.add_node("write_scene", write_scene)
    graph_builder.add_node("process_showing_telling", process_showing_telling)
    graph_builder.add_node("reflect_on_scene", reflect_on_scene)
    graph_builder.add_node("revise_scene_if_needed", revise_scene_if_needed)
    graph_builder.add_node("update_world_elements", update_world_elements)
    graph_builder.add_node("update_character_profiles", update_character_profiles)
    graph_builder.add_node("review_continuity", review_continuity)
    graph_builder.add_node("resolve_continuity_issues", resolve_continuity_issues)
    graph_builder.add_node("advance_to_next_scene_or_chapter", advance_to_next_scene_or_chapter)
    graph_builder.add_node("compile_final_story", compile_final_story)
    
    # Set up the entry point
    graph_builder.add_edge(START, "initialize_state")
    
    # Story setup phase - initial flow
    graph_builder.add_conditional_edges(
        "initialize_state",
        lambda state: "brainstorm_story_concepts" if should_brainstorm_concepts(state) else "generate_story_outline",
        {
            "brainstorm_story_concepts": "brainstorm_story_concepts",
            "generate_story_outline": "generate_story_outline"
        }
    )
    
    graph_builder.add_conditional_edges(
        "brainstorm_story_concepts",
        lambda state: "generate_story_outline" if should_generate_outline(state) else "brainstorm_story_concepts",
        {
            "generate_story_outline": "generate_story_outline",
            "brainstorm_story_concepts": "brainstorm_story_concepts"
        }
    )
    
    graph_builder.add_conditional_edges(
        "generate_story_outline",
        lambda state: "generate_worldbuilding" if should_generate_worldbuilding(state) else "generate_story_outline",
        {
            "generate_worldbuilding": "generate_worldbuilding",
            "generate_story_outline": "generate_story_outline"
        }
    )
    
    graph_builder.add_conditional_edges(
        "generate_worldbuilding",
        lambda state: "generate_characters" if should_generate_characters(state) else "generate_worldbuilding",
        {
            "generate_characters": "generate_characters",
            "generate_worldbuilding": "generate_worldbuilding"
        }
    )
    
    graph_builder.add_conditional_edges(
        "generate_characters",
        lambda state: "plan_chapters" if should_plan_chapters(state) else "generate_characters",
        {
            "plan_chapters": "plan_chapters",
            "generate_characters": "generate_characters"
        }
    )
    
    # From plan_chapters to the scene iteration phase
    graph_builder.add_edge("plan_chapters", "brainstorm_scene_elements")
    # Scene iteration phase
    # Simplified: Always go from brainstorming to writing
    graph_builder.add_edge("brainstorm_scene_elements", "write_scene")
    
    # Add edge from writing to showing/telling processing
    graph_builder.add_edge("write_scene", "process_showing_telling")
    
    # Add edge from showing/telling processing to reflection
    graph_builder.add_edge("process_showing_telling", "reflect_on_scene")
    
    # Fixed edge for reflection to revision
    graph_builder.add_edge("reflect_on_scene", "revise_scene_if_needed")
    
    # Fixed edge for revision to world element updates
    graph_builder.add_edge("revise_scene_if_needed", "update_world_elements")
    
    # Fixed edge for world element updates to character profile updates
    graph_builder.add_edge("update_world_elements", "update_character_profiles")
    
    # Character profiles to either continuity review or next scene
    graph_builder.add_conditional_edges(
        "update_character_profiles",
        decide_after_chapter_profiles,
        {
            "review_continuity": "review_continuity",
            "advance_to_next_scene_or_chapter": "advance_to_next_scene_or_chapter"
        }
    )
    
    # Continuity review branching
    graph_builder.add_conditional_edges(
        "review_continuity",
        decide_after_continuity_review,
        {
            "resolve_continuity_issues": "resolve_continuity_issues",
            "advance_to_next_scene_or_chapter": "advance_to_next_scene_or_chapter"
        }
    )
    
    # Continuity resolution branching
    graph_builder.add_conditional_edges(
        "resolve_continuity_issues",
        decide_after_continuity_resolution,
        {
            "resolve_continuity_issues": "resolve_continuity_issues",
            "advance_to_next_scene_or_chapter": "advance_to_next_scene_or_chapter"
        }
    )
    
    # Advancement to next scene/chapter
    graph_builder.add_conditional_edges(
        "advance_to_next_scene_or_chapter",
        decide_after_advancing,
        {
            "brainstorm_scene_elements": "brainstorm_scene_elements",
            "compile_final_story": "compile_final_story"
        }
    )
    
    # End the story
    graph_builder.add_edge("compile_final_story", END)
    
    # Compile the graph without checkpointing (single-session use)
    graph = graph_builder.compile()
    
    # Configure with a higher recursion limit when it's invoked
    # This needs to be passed during invoke(), not during compile()
    
    # Return the compiled graph
    return graph