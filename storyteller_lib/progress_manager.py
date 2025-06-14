"""Progress management for StoryCraft Agent.

This module provides a ProgressManager class to replace global state
and handle progress tracking throughout story generation.
"""

# Standard library imports
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Optional

# Local imports
from storyteller_lib.constants import NodeNames, ProgressMessages


@dataclass
class ProgressState:
    """Container for progress tracking state.
    
    This dataclass holds all the state information needed to track
    progress during story generation.
    
    Attributes:
        start_time: Unix timestamp when generation started.
        node_counts: Dictionary tracking execution count for each node.
        current_chapter: Currently processing chapter number.
        current_scene: Currently processing scene number.
        verbose_mode: Whether to display verbose output.
        output_file: Path to the output file.
        total_chapters: Total number of chapters to generate.
        total_scenes_per_chapter: Number of scenes per chapter.
    """
    start_time: Optional[float] = None
    node_counts: Dict[str, int] = field(default_factory=dict)
    current_chapter: Optional[int] = None
    current_scene: Optional[int] = None
    verbose_mode: bool = False
    output_file: Optional[str] = None
    total_chapters: int = 0
    total_scenes_per_chapter: int = 0
    
    def reset(self) -> None:
        """Reset all progress tracking state.
        
        This method clears all tracking information and sets the
        start time to the current time.
        """
        self.start_time = time.time()
        self.node_counts.clear()
        self.current_chapter = None
        self.current_scene = None
        
    def get_elapsed_time(self) -> str:
        """Get formatted elapsed time since start.
        
        Returns:
            Formatted time string (e.g., "2m 34s")
        """
        if self.start_time is None:
            return "0s"
            
        elapsed = time.time() - self.start_time
        if elapsed < 60:
            return f"{int(elapsed)}s"
        else:
            minutes = int(elapsed / 60)
            seconds = int(elapsed % 60)
            return f"{minutes}m {seconds}s"
    
    def increment_node_count(self, node_name: str) -> int:
        """Increment and return the count for a node.
        
        Args:
            node_name: Name of the node to increment
            
        Returns:
            New count for the node
        """
        self.node_counts[node_name] = self.node_counts.get(node_name, 0) + 1
        return self.node_counts[node_name]
    
    def get_progress_percentage(self) -> Optional[float]:
        """Calculate overall progress percentage.
        
        Returns:
            Progress percentage (0-100) or None if not calculable
        """
        if not self.total_chapters or not self.current_chapter:
            return None
            
        # Basic progress based on chapters
        chapter_progress = (self.current_chapter - 1) / self.total_chapters
        
        # Add scene progress if available
        if self.current_scene and self.total_scenes_per_chapter:
            scene_progress = (self.current_scene - 1) / self.total_scenes_per_chapter
            chapter_progress += scene_progress / self.total_chapters
            
        return min(chapter_progress * 100, 99)  # Cap at 99% until fully complete


class ProgressManager:
    """Manages progress tracking and reporting for story generation.
    
    This class provides centralized progress tracking, replacing the
    previous global variable approach. It handles progress updates,
    file writing callbacks, and summary reporting.
    
    Attributes:
        state: The ProgressState instance containing all tracking data.
        callback: Optional callback function for progress updates.
        _write_chapter_callback: Optional callback for writing chapters.
    """
    
    def __init__(self, verbose: bool = False, output_file: Optional[str] = None):
        """Initialize the progress manager.
        
        Args:
            verbose: Whether to show verbose output
            output_file: Path to output file for writing chapters
        """
        self.state = ProgressState(
            verbose_mode=verbose,
            output_file=output_file
        )
        self.callback: Optional[Callable] = None
        self._write_chapter_callback: Optional[Callable] = None
        
    def reset(self, total_chapters: int = 0, scenes_per_chapter: int = 0) -> None:
        """Reset progress tracking for a new story.
        
        Args:
            total_chapters: Total number of chapters to generate
            scenes_per_chapter: Number of scenes per chapter
        """
        self.state.reset()
        self.state.total_chapters = total_chapters
        self.state.total_scenes_per_chapter = scenes_per_chapter
        
    def set_progress_callback(self, callback: Callable[[str, Dict], None]) -> None:
        """Set the callback function for progress updates.
        
        Args:
            callback: Function to call with (node_name, state) on progress
        """
        self.callback = callback
        
    def set_write_chapter_callback(self, callback: Callable[[int, Dict, str], None]) -> None:
        """Set the callback function for writing chapters.
        
        Args:
            callback: Function to call with (chapter_num, chapter_data, output_file)
        """
        self._write_chapter_callback = callback
        
    def update_progress(self, node_name: str, state: Dict[str, Any]) -> None:
        """Update progress based on node execution.
        
        Args:
            node_name: Name of the node that was executed
            state: Current story state
        """
        # Update counts
        self.state.increment_node_count(node_name)
        
        # Update chapter/scene tracking
        if "current_chapter" in state:
            self.state.current_chapter = state["current_chapter"]
        if "current_scene" in state:
            self.state.current_scene = state["current_scene"]
            
        # Call the progress callback if set
        if self.callback:
            self.callback(node_name, state)
            
    def write_chapter(self, chapter_num: int, chapter_data: Dict) -> None:
        """Write a completed chapter to file.
        
        Args:
            chapter_num: Chapter number
            chapter_data: Chapter data dictionary
        """
        if self._write_chapter_callback and self.state.output_file:
            self._write_chapter_callback(chapter_num, chapter_data, self.state.output_file)
            
    def get_progress_message(self, node_name: str) -> str:
        """Get a formatted progress message for a node.
        
        Args:
            node_name: Name of the node
            
        Returns:
            Formatted progress message
        """
        elapsed = self.state.get_elapsed_time()
        count = self.state.node_counts.get(node_name, 0)
        
        # Get base message
        message_map = {
            NodeNames.INITIALIZE: ProgressMessages.INITIALIZING,
            NodeNames.CREATIVE_BRAINSTORM: ProgressMessages.BRAINSTORMING,
            NodeNames.OUTLINE_STORY: ProgressMessages.OUTLINING,
            NodeNames.CREATE_WORLD: ProgressMessages.WORLDBUILDING,
            NodeNames.CREATE_CHARACTERS: ProgressMessages.CHARACTER_CREATION,
            NodeNames.COMPILE_STORY: ProgressMessages.COMPILING,
            NodeNames.FINAL_QUALITY_CHECK: ProgressMessages.QUALITY_CHECK,
        }
        
        base_message = message_map.get(node_name, f"Processing {node_name}...")
        
        # Add chapter/scene info if relevant
        if "chapter" in node_name.lower() and self.state.current_chapter:
            base_message = ProgressMessages.WRITING_CHAPTER.format(
                chapter_num=self.state.current_chapter
            )
        elif "scene" in node_name.lower() and self.state.current_scene:
            base_message = ProgressMessages.WRITING_SCENE.format(
                scene_num=self.state.current_scene
            )
            
        # Format with elapsed time and count
        if count > 1:
            return f"[{elapsed}] {base_message} (iteration {count})"
        else:
            return f"[{elapsed}] {base_message}"
            
    def print_summary(self) -> None:
        """Print a summary of the story generation process.
        
        This method displays the total time taken, node execution counts
        (if verbose mode is enabled), and the output file path.
        """
        if not self.state.start_time:
            return
            
        total_time = time.time() - self.state.start_time
        print(f"\n{ProgressMessages.COMPLETE}")
        print(f"Total time: {self.state.get_elapsed_time()}")
        
        if self.state.verbose_mode:
            print("\nNode execution counts:")
            for node, count in sorted(self.state.node_counts.items()):
                print(f"  {node}: {count} time(s)")
                
        if self.state.output_file:
            print(f"\nStory saved to: {self.state.output_file}")


# Singleton instance for backward compatibility
_default_manager = ProgressManager()


def get_progress_manager() -> ProgressManager:
    """Get the default progress manager instance.
    
    Returns:
        The singleton ProgressManager instance
    """
    return _default_manager


def create_progress_manager(verbose: bool = False, 
                          output_file: Optional[str] = None) -> ProgressManager:
    """Create a new progress manager instance.
    
    Args:
        verbose: Whether to show verbose output
        output_file: Path to output file
        
    Returns:
        New ProgressManager instance
    """
    return ProgressManager(verbose=verbose, output_file=output_file)