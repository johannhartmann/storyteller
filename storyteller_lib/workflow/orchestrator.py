"""
Simple orchestrator for story generation workflow.
Replaces LangGraph with direct function calls and database state management.
"""

import time
from typing import Callable, Dict, Any, Optional

from storyteller_lib import track_progress
from storyteller_lib.core.logger import get_logger
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

logger = get_logger(__name__)

# Import research-enabled world building if available
try:
    from storyteller_lib.universe.world.research_integration import (
        generate_worldbuilding_with_research,
    )
    RESEARCH_WORLDBUILDING_AVAILABLE = True
except ImportError:
    RESEARCH_WORLDBUILDING_AVAILABLE = False
    logger.warning("Research-based worldbuilding not available")


class StoryOrchestrator:
    """
    Simple orchestrator that executes story generation workflow steps in sequence.
    All state is managed through the database, not in memory.
    """
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        """
        Initialize the orchestrator.
        
        Args:
            progress_callback: Optional callback function for progress updates
        """
        self.progress_callback = progress_callback
        self.db_manager = get_db_manager()
        
    def _execute_step(self, step_name: str, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a workflow step with logging and progress tracking.
        
        Args:
            step_name: Name of the step for logging
            func: Function to execute
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Result from the function
        """
        logger.info(f"Executing step: {step_name}")
        start_time = time.time()
        
        try:
            # Execute the function
            result = func(*args, **kwargs)
            
            # Report progress if callback is provided
            if self.progress_callback:
                # Create a minimal state dict for the callback
                state = {
                    "last_node": step_name,
                    "current_chapter": self.db_manager.get_current_chapter() if self.db_manager else "",
                    "current_scene": self.db_manager.get_current_scene() if self.db_manager else "",
                }
                self.progress_callback(step_name, state)
            
            elapsed = time.time() - start_time
            logger.info(f"Step {step_name} completed in {elapsed:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error in step {step_name}: {str(e)}", exc_info=True)
            raise
    
    def run_workflow(self, initial_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the complete story generation workflow.
        
        Args:
            initial_params: Initial parameters (genre, tone, etc.)
            
        Returns:
            Final results dict
        """
        logger.info("Starting story generation workflow")
        
        # Initialize state in database
        self._execute_step("initialize_state", initialize_state, initial_params)
        
        # Brainstorm story concepts
        self._execute_step("brainstorm_story_concepts", brainstorm_story_concepts, {})
        
        # Generate story outline
        self._execute_step("generate_story_outline", generate_story_outline, {})
        
        # Generate worldbuilding
        if RESEARCH_WORLDBUILDING_AVAILABLE and initial_params.get("research_worldbuilding"):
            # Use research-enabled worldbuilding
            logger.info("Using research-enabled world building")
            # For now, use regular worldbuilding - research integration needs async handling
            self._execute_step("generate_worldbuilding", generate_worldbuilding, {})
        else:
            self._execute_step("generate_worldbuilding", generate_worldbuilding, {})
        
        # Generate characters
        self._execute_step("generate_characters", generate_characters, {})
        
        # Plan chapters
        self._execute_step("plan_chapters", plan_chapters, {})
        
        # Scene generation loop
        completed = False
        while not completed:
            # Get current chapter and scene from database
            current_chapter = self.db_manager.get_current_chapter()
            current_scene = self.db_manager.get_current_scene()
            
            logger.info(f"Working on Chapter {current_chapter}, Scene {current_scene}")
            
            # Write scene
            self._execute_step("write_scene", write_scene, {
                "current_chapter": current_chapter,
                "current_scene": current_scene
            })
            
            # Reflect on scene
            reflection_result = self._execute_step("reflect_on_scene", reflect_on_scene, {
                "current_chapter": current_chapter,
                "current_scene": current_scene
            })
            
            # Revise if needed
            if reflection_result.get("needs_revision", False):
                self._execute_step("revise_scene_if_needed", revise_scene_if_needed, {
                    "current_chapter": current_chapter,
                    "current_scene": current_scene
                })
            
            # Update world elements
            self._execute_step("update_world_elements", update_world_elements, {
                "current_chapter": current_chapter,
                "current_scene": current_scene
            })
            
            # Update character knowledge
            self._execute_step("update_character_knowledge", update_character_knowledge, {
                "current_chapter": current_chapter,
                "current_scene": current_scene
            })
            
            # Check plot threads
            self._execute_step("check_plot_threads", check_plot_threads, {
                "current_chapter": current_chapter,
                "current_scene": current_scene
            })
            
            # Generate summaries
            self._execute_step("generate_summaries", generate_summaries, {
                "current_chapter": current_chapter,
                "current_scene": current_scene
            })
            
            # Advance to next scene/chapter
            completed = self._advance_to_next_scene_or_chapter()
        
        # Review and polish manuscript
        self._execute_step("review_and_polish_manuscript", review_and_polish_manuscript, {})
        
        # Compile final story
        final_story = self.db_manager.compile_story() if self.db_manager else ""
        
        logger.info("Story generation workflow completed")
        
        return {
            "final_story": final_story,
            "completed": True,
            "chapters": self._get_chapter_count(),
            "scenes": self._get_scene_count()
        }
    
    def _advance_to_next_scene_or_chapter(self) -> bool:
        """
        Advance to the next scene or chapter in the story.
        
        Returns:
            True if story is complete, False otherwise
        """
        if not self.db_manager:
            return True
            
        current_chapter = int(self.db_manager.get_current_chapter() or 1)
        current_scene = int(self.db_manager.get_current_scene() or 1)
        
        # Get chapter and scene counts from database
        chapter_count = self.db_manager.get_chapter_count()
        scenes_in_chapter = self.db_manager.get_scene_count_for_chapter(current_chapter)
        
        if current_scene < scenes_in_chapter:
            # Move to next scene in same chapter
            next_scene = current_scene + 1
            logger.info(f"Advancing to Chapter {current_chapter}, Scene {next_scene}")
            self.db_manager.set_current_scene(current_chapter, next_scene)
            return False
        else:
            # Move to next chapter
            next_chapter = current_chapter + 1
            
            if next_chapter <= chapter_count:
                logger.info(f"Advancing to Chapter {next_chapter}, Scene 1")
                self.db_manager.set_current_chapter(next_chapter)
                self.db_manager.set_current_scene(next_chapter, 1)
                return False
            else:
                # Story is complete
                logger.info("All chapters and scenes completed")
                return True
    
    def _get_chapter_count(self) -> int:
        """Get the total number of chapters."""
        return self.db_manager.get_chapter_count() if self.db_manager else 0
    
    def _get_scene_count(self) -> int:
        """Get the total number of scenes."""
        return self.db_manager.get_total_scene_count() if self.db_manager else 0