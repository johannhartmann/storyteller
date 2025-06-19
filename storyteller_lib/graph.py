"""
StoryCraft Agent - Graph construction with native LangGraph edges.

This is a refactored version of the graph.py file that uses LangGraph's native edge system
instead of a custom router function, which should prevent recursion limit errors.
It also uses SQLite for persistent storage instead of in-memory storage.
"""

# Standard library imports
from operator import add  # Default reducer for lists
from typing import Any, Dict, List, Optional

# Third party imports
from langgraph.graph import END, START, StateGraph

# Local imports
from storyteller_lib import track_progress
from storyteller_lib.character_creation import generate_characters
from storyteller_lib.config import DATABASE_PATH
from storyteller_lib.constants import NodeNames
from storyteller_lib.database_integration import StoryDatabaseManager, get_db_manager, initialize_db_manager
from storyteller_lib.initialization import brainstorm_story_concepts, initialize_state
from storyteller_lib.logger import get_logger
from storyteller_lib.models import StoryState
from storyteller_lib.outline import generate_story_outline, plan_chapters
from storyteller_lib.progression import (
    advance_to_next_scene_or_chapter,
    compile_final_story,
    resolve_continuity_issues,
    review_continuity,
    update_character_profiles,
    update_world_elements
)
from storyteller_lib.scenes import (
    reflect_on_scene,
    revise_scene_if_needed,
    write_scene
)
from storyteller_lib.worldbuilding import generate_worldbuilding

logger = get_logger(__name__)


# Condition functions for scene iteration and continuity checking

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
        return "write_scene"

# Build the graph with native LangGraph edges
def build_story_graph() -> StateGraph:
    """
    Build and compile the story generation graph using LangGraph's native edge system.
    Each node is responsible for its own database operations.
    """
    # Initialize database manager
    db_manager = initialize_db_manager(DATABASE_PATH)
    logger.info(f"Database initialized at {DATABASE_PATH}")
    
    # Create a state graph using Annotated type hints for custom reducers
    graph_builder = StateGraph(
        StoryState
    )
    
    # Add nodes directly - each handles its own DB operations
    graph_builder.add_node("initialize_state", initialize_state)
    graph_builder.add_node("brainstorm_story_concepts", brainstorm_story_concepts)
    graph_builder.add_node("generate_story_outline", generate_story_outline)
    graph_builder.add_node("generate_worldbuilding", generate_worldbuilding)
    graph_builder.add_node("generate_characters", generate_characters)
    graph_builder.add_node("plan_chapters", plan_chapters)
    # Brainstorming is now integrated into write_scene
    graph_builder.add_node("write_scene", write_scene)
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
    # Always go from initialize to brainstorming
    graph_builder.add_edge("initialize_state", "brainstorm_story_concepts")
    
    # Always go from brainstorming to outline generation
    graph_builder.add_edge("brainstorm_story_concepts", "generate_story_outline")
    
    # Always go from outline to worldbuilding
    graph_builder.add_edge("generate_story_outline", "generate_worldbuilding")
    
    # Always go from worldbuilding to characters
    graph_builder.add_edge("generate_worldbuilding", "generate_characters")
    
    # Always go from characters to chapter planning
    graph_builder.add_edge("generate_characters", "plan_chapters")
    
    # From plan_chapters directly to scene writing
    graph_builder.add_edge("plan_chapters", "write_scene")
    
    # Add edge from writing directly to reflection
    graph_builder.add_edge("write_scene", "reflect_on_scene")
    
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
            "write_scene": "write_scene",
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