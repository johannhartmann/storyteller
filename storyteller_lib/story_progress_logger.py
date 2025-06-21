"""
Story Progress Logger - Real-time story generation logging.

This module provides functionality to log story generation progress in a
human-readable format, allowing users to monitor the story as it's being created.
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from storyteller_lib.logger import get_logger

logger = get_logger(__name__)


class StoryProgressLogger:
    """Logs story generation progress to a human-readable file."""
    
    def __init__(self, log_file_path: Optional[str] = None):
        """Initialize the story progress logger.
        
        Args:
            log_file_path: Path to the log file. If None, uses default location.
        """
        if log_file_path is None:
            # Create logs directory if it doesn't exist
            log_dir = os.path.expanduser("~/.storyteller/logs")
            os.makedirs(log_dir, exist_ok=True)
            
            # Use a single log file that gets overwritten each run
            self.log_file_path = os.path.join(log_dir, "story_progress.log")
        else:
            self.log_file_path = log_file_path
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        
        # Write header
        self._write_header()
    
    def _write_header(self):
        """Write the log file header."""
        header = f"""
================================================================================
                          STORY GENERATION PROGRESS LOG
                          Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================

This log shows the story as it's being created, allowing you to monitor progress
and see the content being generated in real-time.

================================================================================

"""
        with open(self.log_file_path, 'w', encoding='utf-8') as f:
            f.write(header)
    
    def _write(self, content: str):
        """Write content to the log file.
        
        Args:
            content: Content to write
        """
        try:
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(content)
                f.write('\n')
                f.flush()  # Ensure immediate write
        except Exception as e:
            logger.error(f"Failed to write to progress log: {e}")
    
    def log_story_params(self, genre: str, tone: str, author: Optional[str] = None,
                        language: str = "english", idea: Optional[str] = None):
        """Log the initial story parameters.
        
        Args:
            genre: Story genre
            tone: Story tone
            author: Author style to emulate
            language: Target language
            idea: Initial story idea
        """
        content = f"""
[{datetime.now().strftime('%H:%M:%S')}] STORY PARAMETERS
--------------------------------------------------------------------------------
Genre: {genre}
Tone: {tone}
Language: {language}
Author Style: {author if author else "None"}
Initial Idea: {idea if idea else "None"}
--------------------------------------------------------------------------------

"""
        self._write(content)
    
    def log_creative_concepts(self, concepts: Dict[str, Any]):
        """Log the creative concepts brainstormed.
        
        Args:
            concepts: Dictionary containing creative concepts
        """
        content = f"""
[{datetime.now().strftime('%H:%M:%S')}] CREATIVE CONCEPTS
================================================================================

STORY CONCEPT:
{concepts.get('story_concept', 'Not generated')}

WORLD BUILDING IDEAS:
{concepts.get('worldbuilding_ideas', 'Not generated')}

CENTRAL CONFLICT:
{concepts.get('central_conflict', 'Not generated')}

================================================================================

"""
        self._write(content)
    
    def log_story_outline(self, outline: str):
        """Log the story outline.
        
        Args:
            outline: The story outline text
        """
        content = f"""
[{datetime.now().strftime('%H:%M:%S')}] STORY OUTLINE
================================================================================

{outline}

================================================================================

"""
        self._write(content)
    
    def log_world_elements(self, world_elements: Dict[str, Any]):
        """Log worldbuilding elements.
        
        Args:
            world_elements: Dictionary containing world elements by category
        """
        content = f"""
[{datetime.now().strftime('%H:%M:%S')}] WORLDBUILDING ELEMENTS
================================================================================

"""
        
        for category, elements in world_elements.items():
            content += f"\n{category.upper().replace('_', ' ')}:\n"
            content += "-" * 80 + "\n"
            
            if isinstance(elements, dict):
                for key, value in elements.items():
                    if value and str(value).strip():
                        content += f"{key.title().replace('_', ' ')}: {value}\n"
            else:
                content += f"{elements}\n"
            
            content += "\n"
        
        content += "================================================================================\n\n"
        self._write(content)
    
    def log_character(self, character: Dict[str, Any]):
        """Log a character profile.
        
        Args:
            character: Character data dictionary
        """
        content = f"""
[{datetime.now().strftime('%H:%M:%S')}] CHARACTER PROFILE: {character.get('name', 'Unknown')}
--------------------------------------------------------------------------------
Role: {character.get('role', 'Not specified')}
Personality: {character.get('personality', {}).get('key_trait', 'Not specified')}
Strength: {character.get('personality', {}).get('strength', 'Not specified')}
Flaw: {character.get('personality', {}).get('flaw', 'Not specified')}

BACKSTORY:
{character.get('facts', {}).get('backstory', 'Not provided')}

CURRENT STATE:
- Emotional: {character.get('emotional_state', {}).get('current_emotion', 'Unknown')}
- Goals: {self._extract_character_goals(character)}

CHARACTER ARC:
{character.get('character_arc', {}).get('transformation', 'Not specified')}
--------------------------------------------------------------------------------

"""
        self._write(content)
    
    def log_chapter_plan(self, chapter_num: str, chapter_data: Dict[str, Any]):
        """Log a chapter plan.
        
        Args:
            chapter_num: Chapter number
            chapter_data: Chapter data dictionary
        """
        content = f"""
[{datetime.now().strftime('%H:%M:%S')}] CHAPTER {chapter_num}: {chapter_data.get('title', 'Untitled')}
--------------------------------------------------------------------------------
{chapter_data.get('outline', 'No outline provided')}

Planned Scenes: {len(chapter_data.get('scenes', {}))}
--------------------------------------------------------------------------------

"""
        self._write(content)
    
    def log_scene_start(self, chapter_num: str, scene_num: str, description: str):
        """Log the start of scene generation.
        
        Args:
            chapter_num: Chapter number
            scene_num: Scene number
            description: Scene description
        """
        content = f"""
[{datetime.now().strftime('%H:%M:%S')}] STARTING SCENE {chapter_num}-{scene_num}
--------------------------------------------------------------------------------
Description: {description}
--------------------------------------------------------------------------------

"""
        self._write(content)
    
    def log_scene_content(self, chapter_num: str, scene_num: str, scene_content: str):
        """Log the generated scene content.
        
        Args:
            chapter_num: Chapter number
            scene_num: Scene number
            scene_content: The actual scene text
        """
        content = f"""
[{datetime.now().strftime('%H:%M:%S')}] SCENE {chapter_num}-{scene_num} CONTENT
================================================================================

{scene_content}

================================================================================

"""
        self._write(content)
    
    def log_scene_reflection(self, chapter_num: str, scene_num: str, reflection: Dict[str, Any]):
        """Log scene reflection results.
        
        Args:
            chapter_num: Chapter number
            scene_num: Scene number
            reflection: Reflection data
        """
        quality_scores = reflection.get('quality_scores', {})
        issues = reflection.get('issues', [])
        strengths = reflection.get('strengths', [])
        
        content = f"""
[{datetime.now().strftime('%H:%M:%S')}] SCENE {chapter_num}-{scene_num} REFLECTION
--------------------------------------------------------------------------------
Quality Score: {quality_scores.get('overall', 'N/A')}/10

STRENGTHS:
"""
        for strength in strengths:
            content += f"- {strength}\n"
        
        if issues:
            content += "\nISSUES IDENTIFIED:\n"
            for issue in issues:
                content += f"- {issue}\n"
        
        content += "--------------------------------------------------------------------------------\n\n"
        self._write(content)
    
    def log_revision(self, chapter_num: str, scene_num: str, revision_reason: str):
        """Log that a scene is being revised.
        
        Args:
            chapter_num: Chapter number
            scene_num: Scene number
            revision_reason: Reason for revision
        """
        content = f"""
[{datetime.now().strftime('%H:%M:%S')}] REVISING SCENE {chapter_num}-{scene_num}
--------------------------------------------------------------------------------
Reason: {revision_reason}
--------------------------------------------------------------------------------

"""
        self._write(content)
    
    def log_chapter_complete(self, chapter_num: str):
        """Log chapter completion.
        
        Args:
            chapter_num: Chapter number
        """
        content = f"""
[{datetime.now().strftime('%H:%M:%S')}] CHAPTER {chapter_num} COMPLETE
================================================================================

"""
        self._write(content)
    
    def log_story_complete(self, total_chapters: int, total_words: int, duration: str):
        """Log story completion.
        
        Args:
            total_chapters: Total number of chapters
            total_words: Total word count
            duration: Time taken to generate
        """
        content = f"""
[{datetime.now().strftime('%H:%M:%S')}] STORY GENERATION COMPLETE
================================================================================
Total Chapters: {total_chapters}
Total Words: {total_words:,}
Generation Time: {duration}
Log File: {self.log_file_path}
================================================================================

"""
        self._write(content)
    
    def log_error(self, error_msg: str, location: Optional[str] = None):
        """Log an error.
        
        Args:
            error_msg: Error message
            location: Where the error occurred
        """
        content = f"""
[{datetime.now().strftime('%H:%M:%S')}] ERROR{f' at {location}' if location else ''}
--------------------------------------------------------------------------------
{error_msg}
--------------------------------------------------------------------------------

"""
        self._write(content)
    
    def get_log_path(self) -> str:
        """Get the path to the log file.
        
        Returns:
            Path to the log file
        """
        return self.log_file_path
    
    def _extract_character_goals(self, character: Dict[str, Any]) -> str:
        """Extract character goals from various possible locations."""
        # Check if personality dict has desires
        personality = character.get('personality', {})
        if isinstance(personality, dict) and 'desires' in personality:
            desires = personality.get('desires', [])
            if isinstance(desires, list) and desires:
                return ", ".join(desires[:2])
        
        # Check inner_conflicts for desires
        inner_conflicts = character.get('inner_conflicts', [])
        if isinstance(inner_conflicts, list):
            # Extract desires from conflict descriptions
            desires = []
            for conflict in inner_conflicts:
                if isinstance(conflict, dict) and 'description' in conflict:
                    desc = conflict['description']
                    if 'desire' in desc.lower():
                        desires.append(desc)
            if desires:
                return desires[0][:100] + "..." if len(desires[0]) > 100 else desires[0]
        
        return "Not specified"


# Global instance for easy access
_progress_logger: Optional[StoryProgressLogger] = None


def get_progress_logger() -> Optional[StoryProgressLogger]:
    """Get the global progress logger instance.
    
    Returns:
        The progress logger instance or None if not initialized
    """
    global _progress_logger
    # if _progress_logger is None:
    #     print("[DEBUG] Progress logger is None in get_progress_logger()")
    return _progress_logger


def initialize_progress_logger(log_file_path: Optional[str] = None) -> StoryProgressLogger:
    """Initialize the global progress logger.
    
    Args:
        log_file_path: Optional custom log file path
        
    Returns:
        The initialized progress logger
    """
    global _progress_logger
    _progress_logger = StoryProgressLogger(log_file_path)
    return _progress_logger


def log_progress(content_type: str, **kwargs):
    """Convenience function to log progress.
    
    Args:
        content_type: Type of content to log
        **kwargs: Arguments specific to the content type
    """
    logger = get_progress_logger()
    if not logger:
        # Debug: print when logger is not available
        # print(f"[DEBUG] Progress logger not available for {content_type}")
        return
    
    try:
        if content_type == "story_params":
            logger.log_story_params(**kwargs)
        elif content_type == "creative_concepts":
            logger.log_creative_concepts(**kwargs)
        elif content_type == "story_outline":
            logger.log_story_outline(**kwargs)
        elif content_type == "world_elements":
            logger.log_world_elements(**kwargs)
        elif content_type == "character":
            logger.log_character(**kwargs)
        elif content_type == "chapter_plan":
            logger.log_chapter_plan(**kwargs)
        elif content_type == "scene_start":
            logger.log_scene_start(**kwargs)
        elif content_type == "scene_content":
            logger.log_scene_content(**kwargs)
        elif content_type == "scene_reflection":
            logger.log_scene_reflection(**kwargs)
        elif content_type == "revision":
            logger.log_revision(**kwargs)
        elif content_type == "chapter_complete":
            logger.log_chapter_complete(**kwargs)
        elif content_type == "story_complete":
            logger.log_story_complete(**kwargs)
        elif content_type == "error":
            logger.log_error(**kwargs)
    except Exception as e:
        # Print error to stderr for debugging
        import sys
        print(f"[ERROR] Failed to log {content_type}: {str(e)}", file=sys.stderr)
        # Try to write error to log file
        try:
            logger._write(f"[ERROR] Failed to log {content_type}: {str(e)}")
        except:
            pass