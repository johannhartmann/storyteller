"""
Simplified graph construction using the refactored scene creation workflow.
This version reduces complexity while maintaining story quality.
"""

from operator import add
from typing import Any, Dict, List, Optional

from langgraph.graph import END, START, StateGraph

from storyteller_lib import track_progress
from storyteller_lib.workflow.nodes.initialization import (
    brainstorm_story_concepts,
    initialize_state,
)
from storyteller_lib.core.config import DATABASE_PATH
from storyteller_lib.core.constants import NodeNames
from storyteller_lib.persistence.database import (
    StoryDatabaseManager,
    get_db_manager,
    initialize_db_manager,
)
from storyteller_lib.core.logger import get_logger
from storyteller_lib.core.models import StoryState
from storyteller_lib.workflow.nodes.outline import generate_story_outline, plan_chapters
from storyteller_lib.workflow.nodes.progression import (
    update_world_elements,
    update_character_knowledge,
    check_plot_threads,
    manage_character_arcs,
    log_story_progress,
    update_progress_status,
)
from storyteller_lib.output.manuscript import review_and_polish_manuscript

# Use simplified scene modules
from storyteller_lib.workflow.nodes.scenes import (
    reflect_on_scene,
    revise_scene_if_needed,
    write_scene,
)
from storyteller_lib.workflow.nodes.summary_node import generate_summaries
from storyteller_lib.universe.world.builder import generate_worldbuilding
from storyteller_lib.universe.characters.profiles import generate_characters

# Import research-enabled world building if available
try:
    from storyteller_lib.universe.world.research_integration import generate_worldbuilding_with_research
    RESEARCH_WORLDBUILDING_AVAILABLE = True
except ImportError:
    RESEARCH_WORLDBUILDING_AVAILABLE = False
    logger.warning("Research-based worldbuilding not available")

logger = get_logger(__name__)


# Simplified condition functions


def needs_revision_check(state: StoryState) -> str:
    """
    Simple check if scene needs revision based on reflection.
    Style corrections are now handled within reflect_on_scene.
    """
    needs_revision = state.get("needs_revision", False)
    current_chapter = state.get("current_chapter", "")
    current_scene = state.get("current_scene", "")

    if needs_revision:
        logger.info(
            f"Scene Ch:{current_chapter}/Sc:{current_scene} needs full revision"
        )
        return "revise"
    else:
        logger.debug(
            f"Scene Ch:{current_chapter}/Sc:{current_scene} - no revision needed, continuing"
        )
        return "continue"


def is_story_complete(state: StoryState) -> str:
    """Check if all chapters and scenes are complete."""
    # First check if the advancement logic has marked the story as complete
    if state.get("completed", False):
        logger.info("Story marked as completed by advancement logic")
        return "complete"

    chapters = state.get("chapters", {})

    # Check if we have at least the minimum chapters
    if len(chapters) < 8:
        logger.debug(f"Only {len(chapters)} chapters, need at least 8")
        return "continue"

    # Check if all planned scenes are written
    for chapter_num, chapter_data in chapters.items():
        scenes = chapter_data.get("scenes", {})
        for scene_num, scene_data in scenes.items():
            if not scene_data.get("db_stored", False):
                logger.debug(
                    f"Chapter {chapter_num}, Scene {scene_num} not yet written"
                )
            return "continue"

    logger.info("All planned scenes are written")
    return "complete"


@track_progress
def advance_to_next_scene_or_chapter(state: StoryState) -> Dict:
    """Advance to the next scene or chapter in the story."""
    current_chapter = int(state.get("current_chapter", 1))
    current_scene = int(state.get("current_scene", 1))
    chapters = state.get("chapters", {})

    # Check if we have more scenes in current chapter
    current_chapter_data = chapters.get(str(current_chapter), {})
    scenes_in_chapter = current_chapter_data.get("scenes", {})

    # Find the highest scene number in current chapter
    max_scene = max([int(s) for s in scenes_in_chapter.keys()], default=0)

    if current_scene < max_scene:
        # Move to next scene in same chapter
        next_scene = current_scene + 1
        logger.info(f"Advancing to Chapter {current_chapter}, Scene {next_scene}")
        return {"current_scene": str(next_scene), "completed": False}
    else:
        # Move to next chapter
        next_chapter = current_chapter + 1

        # Check if we have more chapters
        if str(next_chapter) in chapters:
            logger.info(f"Advancing to Chapter {next_chapter}, Scene 1")
            return {
                "current_chapter": str(next_chapter),
                "current_scene": "1",
                "completed": False,
            }
        else:
            # Story is complete
            logger.info("All chapters and scenes completed")
            return {"completed": True}


def create_simplified_graph(checkpointer=None) -> StateGraph:
    """
    Create a simplified story generation graph.

    Key simplifications:
    1. Removed scene brainstorming as separate node (integrated into writing)
    2. Removed continuity checking (integrated into reflection)
    3. Simplified revision logic (single pass only)
    4. Reduced condition checks
    """

    # Initialize database manager
    initialize_db_manager(DATABASE_PATH)
    logger.info(f"Initialized database at {DATABASE_PATH}")

    # Create the graph
    graph_builder = StateGraph(StoryState)

    # Add all nodes - simplified flow
    graph_builder.add_node("initialize_state", initialize_state)
    graph_builder.add_node("brainstorm_story_concepts", brainstorm_story_concepts)
    graph_builder.add_node("generate_story_outline", generate_story_outline)
    
    # Use research-enabled worldbuilding if configured
    if RESEARCH_WORLDBUILDING_AVAILABLE:
        # Check if research is enabled in config
        from storyteller_lib.core.config import get_story_config
        try:
            config = get_story_config()
            if config.get("world_building_research", {}).get("enable_research", False):
                logger.info("Using research-enabled world building")
                # Need to wrap async function for sync graph
                import asyncio
                def worldbuilding_wrapper(state):
                    return asyncio.run(generate_worldbuilding_with_research(state))
                graph_builder.add_node("generate_worldbuilding", worldbuilding_wrapper)
            else:
                graph_builder.add_node("generate_worldbuilding", generate_worldbuilding)
        except:
            # Config not available yet, use standard worldbuilding
            graph_builder.add_node("generate_worldbuilding", generate_worldbuilding)
    else:
        graph_builder.add_node("generate_worldbuilding", generate_worldbuilding)
    
    graph_builder.add_node("generate_characters", generate_characters)
    graph_builder.add_node("plan_chapters", plan_chapters)

    # Simplified scene flow - reflect_on_scene now handles style corrections internally
    graph_builder.add_node("write_scene", write_scene)
    graph_builder.add_node("reflect_on_scene", reflect_on_scene)
    graph_builder.add_node("revise_scene_if_needed", revise_scene_if_needed)
    graph_builder.add_node("update_world_elements", update_world_elements)
    graph_builder.add_node("update_character_knowledge", update_character_knowledge)
    graph_builder.add_node("check_plot_threads", check_plot_threads)
    graph_builder.add_node("generate_summaries", generate_summaries)
    graph_builder.add_node(
        "advance_to_next_scene_or_chapter", advance_to_next_scene_or_chapter
    )
    graph_builder.add_node("review_and_polish_manuscript", review_and_polish_manuscript)

    # Linear story setup flow
    graph_builder.add_edge(START, "initialize_state")
    graph_builder.add_edge("initialize_state", "brainstorm_story_concepts")
    graph_builder.add_edge("brainstorm_story_concepts", "generate_story_outline")
    graph_builder.add_edge("generate_story_outline", "generate_worldbuilding")
    graph_builder.add_edge("generate_worldbuilding", "generate_characters")
    graph_builder.add_edge("generate_characters", "plan_chapters")

    # Simplified scene writing flow
    graph_builder.add_edge("plan_chapters", "write_scene")
    graph_builder.add_edge("write_scene", "reflect_on_scene")

    # Conditional routing: full revision or continue (style corrections handled in reflect_on_scene)
    graph_builder.add_conditional_edges(
        "reflect_on_scene",
        needs_revision_check,
        {"revise": "revise_scene_if_needed", "continue": "update_world_elements"},
    )

    # Continue flow after revision
    graph_builder.add_edge("revise_scene_if_needed", "update_world_elements")
    graph_builder.add_edge("update_world_elements", "update_character_knowledge")
    graph_builder.add_edge("update_character_knowledge", "check_plot_threads")
    graph_builder.add_edge("check_plot_threads", "generate_summaries")
    graph_builder.add_edge("generate_summaries", "advance_to_next_scene_or_chapter")

    # Check if story is complete
    graph_builder.add_conditional_edges(
        "advance_to_next_scene_or_chapter",
        is_story_complete,
        {"continue": "write_scene", "complete": "review_and_polish_manuscript"},
    )

    # End
    graph_builder.add_edge("review_and_polish_manuscript", END)

    # Compile the graph
    if checkpointer:
        graph = graph_builder.compile(checkpointer=checkpointer)
    else:
        graph = graph_builder.compile()

    logger.info("Simplified story generation graph created successfully")

    return graph
