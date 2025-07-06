"""
Simple orchestrator for story generation workflow.
Uses direct function calls and database state management.
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
        
        # Maintain essential state variables that nodes expect
        self.state = {
            "initial_idea": "",
            "genre": "",
            "tone": "",
            "author": "",
            "language": "english",
            "target_pages": 200,
            "research_worldbuilding": False,
            "current_chapter": "1",
            "current_scene": "1",
            "chapters": {},
            "characters": {},
            "world_elements": {},
            "plot_threads": {},
            "scene_reflection": {},
            "needs_revision": False,
            "last_node": "",
            "messages": [],
        }
        
    def _execute_step(self, step_name: str, func: Callable, params: Dict[str, Any]) -> Any:
        """
        Execute a workflow step with logging and progress tracking.
        
        Args:
            step_name: Name of the step for logging
            func: Function to execute
            params: Parameters to pass to the function
            
        Returns:
            Result from the function
        """
        logger.info(f"Executing step: {step_name}")
        start_time = time.time()
        
        try:
            # Update state with current position
            self.state["last_node"] = step_name
            self.state["current_chapter"] = self.db_manager.get_current_chapter() if self.db_manager else "1"
            self.state["current_scene"] = self.db_manager.get_current_scene() if self.db_manager else "1"
            
            # Merge state with params for backward compatibility
            full_params = {**self.state, **params}
            
            # Execute the function
            result = func(full_params)
            
            # Update state with any returned values
            if isinstance(result, dict):
                for key, value in result.items():
                    if key in self.state:
                        self.state[key] = value
            
            # Save state to database after each step
            if self.db_manager:
                self.db_manager.save_node_state(step_name, self.state)
            
            # Report progress if callback is provided
            if self.progress_callback:
                self.progress_callback(step_name, self.state)
            
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
        
        # Initialize state from initial parameters
        self.state.update(initial_params)
        
        # Load any existing data from database
        self._load_state_from_database()
        
        # Initialize state in database
        result = self._execute_step("initialize_state", initialize_state, initial_params)
        
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
        
        # Initialize scene generation starting position
        logger.info("Initializing scene generation loop...")
        
        # Reset position to start of story
        if self.db_manager:
            self.db_manager.reset_scene_position()
        
        # Scene generation loop
        completed = False
        scene_count = 0
        max_scenes = 1000  # Safety limit to prevent infinite loops
        
        while not completed and scene_count < max_scenes:
            # Get current chapter and scene from database
            current_chapter = self.db_manager.get_current_chapter()
            current_scene = self.db_manager.get_current_scene()
            
            # Log the current position for debugging
            logger.debug(f"Scene loop iteration {scene_count + 1}: Chapter {current_chapter}, Scene {current_scene}")
            
            logger.info(f"Working on Chapter {current_chapter}, Scene {current_scene}")
            
            # Update state with current position
            self.state["current_chapter"] = current_chapter
            self.state["current_scene"] = current_scene
            
            # Write scene
            scene_result = self._execute_step("write_scene", write_scene, {})
            
            # Reflect on scene
            reflection_result = self._execute_step("reflect_on_scene", reflect_on_scene, {})
            
            # Update state with reflection results
            if reflection_result:
                self.state["scene_reflection"] = reflection_result
                self.state["needs_revision"] = reflection_result.get("needs_revision", False)
            
            # Revise if needed
            if self.state.get("needs_revision", False):
                revision_result = self._execute_step("revise_scene_if_needed", revise_scene_if_needed, {
                    "scene_reflection": self.state.get("scene_reflection", {}),
                    "needs_revision": True
                })
                # Clear revision flag after revision
                self.state["needs_revision"] = False
            
            # Update world elements
            self._execute_step("update_world_elements", update_world_elements, {})
            
            # Update character knowledge
            self._execute_step("update_character_knowledge", update_character_knowledge, {})
            
            # Check plot threads
            self._execute_step("check_plot_threads", check_plot_threads, {})
            
            # Generate summaries
            self._execute_step("generate_summaries", generate_summaries, {})
            
            # Advance to next scene/chapter
            completed = self._advance_to_next_scene_or_chapter()
            scene_count += 1
            
            if scene_count >= max_scenes:
                logger.error(f"Scene generation loop exceeded maximum iterations ({max_scenes}). Stopping to prevent infinite loop.")
                break
        
        logger.info(f"Scene generation completed. Total scenes processed: {scene_count}")
        logger.info("All chapters and scenes completed")
        
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
    
    def _load_state_from_database(self) -> None:
        """Load existing state from database if available."""
        if not self.db_manager or not self.db_manager._db:
            return
            
        try:
            # Load story configuration
            with self.db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM story_config WHERE id = 1")
                config = cursor.fetchone()
                if config:
                    self.state["genre"] = config["genre"] or self.state["genre"]
                    self.state["tone"] = config["tone"] or self.state["tone"]
                    self.state["author"] = config["author"] or self.state["author"]
                    self.state["language"] = config["language"] or self.state["language"]
                    self.state["initial_idea"] = config["initial_idea"] or self.state["initial_idea"]
                    self.state["target_pages"] = config["target_pages"] or self.state["target_pages"]
                    self.state["research_worldbuilding"] = bool(config["research_worldbuilding"])
                    
            # Load chapters structure
            chapters = {}
            with self.db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT c.chapter_number, c.title, c.summary,
                           COUNT(s.id) as scene_count
                    FROM chapters c
                    LEFT JOIN scenes s ON c.id = s.chapter_id
                    GROUP BY c.id
                    ORDER BY c.chapter_number
                """)
                for row in cursor.fetchall():
                    chapter_num = str(row["chapter_number"])
                    chapters[chapter_num] = {
                        "title": row["title"] or f"Chapter {chapter_num}",
                        "summary": row["summary"] or "",
                        "scenes": {},
                        "scene_count": row["scene_count"]
                    }
            self.state["chapters"] = chapters
            
            # Load characters
            characters = {}
            with self.db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM characters")
                for row in cursor.fetchall():
                    char_id = row["character_id"]
                    characters[char_id] = {
                        "name": row["name"],
                        "role": row["role"],
                        "backstory": row["backstory"],
                        "personality": row["personality"],
                        "physical_description": row["physical_description"],
                        "goals": row["goals"],
                        "obstacles": row["obstacles"],
                        "arc": row["arc"],
                        "relationships": row["relationships"],
                        "unique_traits": row["unique_traits"],
                        "inner_conflict": row["inner_conflict"],
                        "character_id": char_id
                    }
            self.state["characters"] = characters
            
            # Load plot threads
            plot_threads = {}
            with self.db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM plot_threads")
                for row in cursor.fetchall():
                    thread_name = row["name"]
                    plot_threads[thread_name] = {
                        "name": thread_name,
                        "description": row["description"],
                        "thread_type": row["thread_type"],
                        "importance": row["importance"],
                        "introduced_chapter": row["introduced_chapter"],
                        "introduced_scene": row["introduced_scene"],
                        "resolved_chapter": row["resolved_chapter"],
                        "resolved_scene": row["resolved_scene"],
                        "status": row["status"],
                        "peak_chapter": row["peak_chapter"],
                        "peak_scene": row["peak_scene"]
                    }
            self.state["plot_threads"] = plot_threads
            
            logger.info(f"Loaded state from database: {len(chapters)} chapters, {len(characters)} characters, {len(plot_threads)} plot threads")
            
        except Exception as e:
            logger.error(f"Error loading state from database: {e}")
            # Continue with empty state if loading fails