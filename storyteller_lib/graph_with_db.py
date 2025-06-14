"""
StoryCraft Agent - Graph with database integration.

This module wraps the story generation graph with database persistence,
saving state after each node execution.
"""

# Standard library imports
from typing import Any, Dict, Optional

# Third party imports
from langgraph.graph import StateGraph

# Local imports  
from storyteller_lib import track_progress
from storyteller_lib.config import DATABASE_PATH
from storyteller_lib.constants import NodeNames
from storyteller_lib.database_integration import StoryDatabaseManager, get_db_manager, initialize_db_manager
from storyteller_lib.logger import get_logger
from storyteller_lib.models import StoryState

logger = get_logger(__name__)


def create_node_with_db_save(node_func, node_name: str, db_manager: Optional[StoryDatabaseManager]):
    """
    Wrapper that saves state to database after node execution.
    
    Args:
        node_func: The original node function
        node_name: Name of the node for tracking
        db_manager: Database manager instance
        
    Returns:
        Wrapped function that includes database persistence
    """
    @track_progress
    def wrapped(state: StoryState) -> Dict[str, Any]:
        # Execute the original node
        result = node_func(state)
        
        # Save to database
        if db_manager:
            try:
                # Merge result into state for saving
                merged_state = {**state}
                if isinstance(result, dict):
                    merged_state.update(result)
                
                # Save state after node execution
                db_manager.save_node_state(node_name, merged_state)
            except Exception as e:
                logger.error(f"Failed to save state after {node_name}: {e}")
        
        return result
    
    # Preserve function name and metadata
    wrapped.__name__ = node_func.__name__
    wrapped.__doc__ = node_func.__doc__
    
    return wrapped


def build_story_graph_with_db() -> StateGraph:
    """
    Build the story generation graph with database integration.
    
    This creates the same graph as build_story_graph() but wraps each node
    to save state to the database after execution.
    """
    # Initialize database manager
    db_manager = initialize_db_manager(DATABASE_PATH)
    logger.info(f"Database integration enabled at {DATABASE_PATH}")
    
    # Import node functions
    from storyteller_lib.character_creation import generate_characters
    from storyteller_lib.initialization import brainstorm_story_concepts, initialize_state
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
        brainstorm_scene_elements,
        reflect_on_scene,
        revise_scene_if_needed,
        write_scene
    )
    from storyteller_lib.worldbuilding import generate_worldbuilding
    
    # Import routing functions
    from storyteller_lib.graph import (
        decide_after_advancing,
        decide_after_chapter_profiles,
        decide_after_continuity_resolution,
        decide_after_continuity_review,
        should_brainstorm_concepts,
        should_generate_characters,
        should_generate_outline,
        should_generate_worldbuilding,
        should_plan_chapters
    )
    
    # Create wrapped versions of node functions
    wrapped_nodes = {
        "initialize_state": create_node_with_db_save(
            initialize_state, NodeNames.INITIALIZE, db_manager
        ),
        "brainstorm_story_concepts": create_node_with_db_save(
            brainstorm_story_concepts, NodeNames.CREATIVE_BRAINSTORM, db_manager
        ),
        "generate_story_outline": create_node_with_db_save(
            generate_story_outline, NodeNames.OUTLINE_STORY, db_manager
        ),
        "generate_worldbuilding": create_node_with_db_save(
            generate_worldbuilding, NodeNames.WORLDBUILDING, db_manager
        ),
        "generate_characters": create_node_with_db_save(
            generate_characters, NodeNames.CREATE_CHARACTERS, db_manager
        ),
        "plan_chapters": create_node_with_db_save(
            plan_chapters, NodeNames.PLAN_CHAPTER, db_manager
        ),
        "brainstorm_scene_elements": create_node_with_db_save(
            brainstorm_scene_elements, NodeNames.SCENE_BRAINSTORM, db_manager
        ),
        "write_scene": create_node_with_db_save(
            write_scene, NodeNames.SCENE_WRITING, db_manager
        ),
        "reflect_on_scene": create_node_with_db_save(
            reflect_on_scene, NodeNames.SCENE_REFLECTION, db_manager
        ),
        "revise_scene_if_needed": create_node_with_db_save(
            revise_scene_if_needed, NodeNames.SCENE_REVISION, db_manager
        ),
        "update_world_elements": create_node_with_db_save(
            update_world_elements, NodeNames.WORLD_UPDATE, db_manager
        ),
        "update_character_profiles": create_node_with_db_save(
            update_character_profiles, NodeNames.CHARACTER_EVOLUTION, db_manager
        ),
        "review_continuity": create_node_with_db_save(
            review_continuity, NodeNames.CONTINUITY_REVIEW, db_manager
        ),
        "resolve_continuity_issues": create_node_with_db_save(
            resolve_continuity_issues, NodeNames.CONTINUITY_RESOLUTION, db_manager
        ),
        "advance_to_next_scene_or_chapter": create_node_with_db_save(
            advance_to_next_scene_or_chapter, NodeNames.PROGRESSION, db_manager
        ),
        "compile_final_story": create_node_with_db_save(
            compile_final_story, NodeNames.STORY_COMPILATION, db_manager
        )
    }
    
    # Build graph with wrapped nodes
    from langgraph.graph import END, START
    
    # Create a state graph
    graph_builder = StateGraph(StoryState)
    
    # Add wrapped nodes
    for node_name, wrapped_func in wrapped_nodes.items():
        graph_builder.add_node(node_name, wrapped_func)
    
    # Set up the same edges as the original graph
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
    graph_builder.add_edge("brainstorm_scene_elements", "write_scene")
    graph_builder.add_edge("write_scene", "reflect_on_scene")
    graph_builder.add_edge("reflect_on_scene", "revise_scene_if_needed")
    graph_builder.add_edge("revise_scene_if_needed", "update_world_elements")
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
    
    # Compile the graph
    return graph_builder.compile()


def load_story_from_database(story_id: int) -> Optional[StoryState]:
    """
    Load a story from the database.
    
    Args:
        story_id: The ID of the story to load
        
    Returns:
        The loaded story state, or None if not found
    """
    db_manager = get_db_manager()
    if not db_manager:
        logger.error("Database manager not initialized")
        return None
    
    return db_manager.load_story(story_id)