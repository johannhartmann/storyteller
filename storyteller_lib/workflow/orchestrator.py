"""
Simple orchestrator for story generation.
Just executes the necessary functions in order without workflow management.
"""

import logging
from typing import Dict, Any

from storyteller_lib.persistence.database import get_db_manager
from storyteller_lib.output.manuscript import review_and_polish_manuscript
from storyteller_lib.universe.characters.profiles import generate_characters
from storyteller_lib.universe.world.builder import generate_worldbuilding
from storyteller_lib.workflow.nodes.initialization import (
    brainstorm_story_concepts,
    initialize_state,
)
from storyteller_lib.workflow.nodes.outline import generate_story_outline, plan_chapters
from storyteller_lib.workflow.nodes.progression import (
    check_plot_threads,
    update_character_knowledge,
    update_world_elements,
)
from storyteller_lib.workflow.nodes.scenes import (
    reflect_on_scene,
    revise_scene_if_needed,
    write_scene,
)
from storyteller_lib.workflow.nodes.summary_node import generate_summaries

logger = logging.getLogger(__name__)


def run_story_generation(initial_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run story generation by executing all necessary steps in sequence.
    
    Args:
        initial_params: Initial parameters (genre, tone, author, etc.)
        
    Returns:
        Dictionary with final story and statistics
    """
    logger.info("Starting story generation")
    
    # Get database manager
    db_manager = get_db_manager()
    if not db_manager:
        raise RuntimeError("Database manager not available")
    
    # Step 1: Initialize the story
    logger.info("Step 1: Initializing story")
    initialize_state(initial_params)
    
    # Step 2: Brainstorm concepts
    logger.info("Step 2: Brainstorming story concepts")
    brainstorm_story_concepts({})
    
    # Step 3: Generate outline
    logger.info("Step 3: Generating story outline")
    generate_story_outline({})
    
    # Step 4: Build the world
    logger.info("Step 4: Building world")
    generate_worldbuilding({})
    
    # Step 5: Create characters
    logger.info("Step 5: Creating characters")
    generate_characters({})
    
    # Step 6: Plan chapters
    logger.info("Step 6: Planning chapters")
    plan_chapters({})
    
    # Step 7: Generate all scenes
    logger.info("Step 7: Generating scenes")
    
    # Reset to start of story
    db_manager.reset_scene_position()
    
    # Get total chapters and scenes
    total_chapters = db_manager.get_chapter_count()
    logger.info(f"Total chapters to generate: {total_chapters}")
    
    # Iterate through all chapters
    for chapter_num in range(1, total_chapters + 1):
        scenes_in_chapter = db_manager.get_scene_count_for_chapter(chapter_num)
        logger.info(f"Chapter {chapter_num}: {scenes_in_chapter} scenes to generate")
        
        # Iterate through all scenes in this chapter
        for scene_num in range(1, scenes_in_chapter + 1):
            logger.info(f"Generating Chapter {chapter_num}, Scene {scene_num}")
            
            # Set current position
            db_manager.set_current_scene(chapter_num, scene_num)
            
            # Create params for this scene
            scene_params = {
                "current_chapter": str(chapter_num),
                "current_scene": str(scene_num)
            }
            
            # Write the scene
            write_scene(scene_params)
            
            # Reflect on the scene
            reflection = reflect_on_scene(scene_params)
            
            # Revise if needed
            if reflection and reflection.get("needs_revision", False):
                scene_params["scene_reflection"] = reflection
                scene_params["needs_revision"] = True
                revise_scene_if_needed(scene_params)
            
            # Update world elements based on scene
            update_world_elements(scene_params)
            
            # Update character knowledge
            update_character_knowledge(scene_params)
            
            # Check plot thread progression
            check_plot_threads(scene_params)
            
            # Generate summaries
            generate_summaries(scene_params)
    
    logger.info("All scenes generated")
    
    # Step 8: Review and polish the manuscript
    logger.info("Step 8: Reviewing and polishing manuscript")
    review_and_polish_manuscript({})
    
    # Step 9: Compile the final story
    logger.info("Step 9: Compiling final story")
    final_story = db_manager.compile_story()
    
    # Get statistics
    chapter_count = db_manager.get_chapter_count()
    scene_count = db_manager.get_total_scene_count()
    
    logger.info(f"Story generation completed: {chapter_count} chapters, {scene_count} scenes")
    
    return {
        "final_story": final_story,
        "completed": True,
        "chapters": chapter_count,
        "scenes": scene_count
    }