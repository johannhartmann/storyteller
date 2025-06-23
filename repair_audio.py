#!/usr/bin/env python3
"""
Repair failed audio generation by fixing SSML errors.

This script scans for failed audio files (0-byte or missing) and attempts to
repair the SSML content using AI, then regenerates the audio.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import sqlite3

from dotenv import load_dotenv

from storyteller_lib.database.models import StoryDatabase
from storyteller_lib.logger import get_logger
from storyteller_lib.ssml_repair import SSMLRepair
from generate_audiobook import AudiobookGenerator

logger = get_logger(__name__)

# Load environment variables
env_path = Path('.env')
if not env_path.exists():
    env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)


class AudioRepairTool:
    """Tool for repairing failed audio generation."""
    
    def __init__(self, db_path: str, output_dir: str, speech_key: str, speech_region: str):
        """
        Initialize the repair tool.
        
        Args:
            db_path: Path to the story database
            output_dir: Directory containing audio files
            speech_key: Azure Speech Service key
            speech_region: Azure Speech Service region
        """
        self.db = StoryDatabase(db_path)
        self.output_dir = Path(output_dir)
        self.repair_module = SSMLRepair(db_path)
        
        # Get story title to find correct output directory
        story_config = self.db.get_story_config()
        story_title = story_config.get('title', 'Untitled Story')
        clean_title = "".join(c for c in story_title if c.isalnum() or c in (' ', '-', '_')).strip()
        clean_title = clean_title.replace(' ', '_')
        
        self.audio_dir = self.output_dir / clean_title
        
        # Initialize audio generator
        self.audio_generator = AudiobookGenerator(
            speech_key=speech_key,
            speech_region=speech_region,
            db_path=db_path,
            output_dir=str(self.output_dir)
        )
        
    def find_failed_audio_files(self) -> List[Tuple[int, int, int, str]]:
        """
        Find all scenes that have failed audio generation.
        
        Returns:
            List of tuples (scene_id, chapter_num, scene_num, expected_filename)
        """
        failed_scenes = []
        
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get all scenes with SSML content
            cursor.execute("""
                SELECT s.id, s.scene_number, c.chapter_number, c.title as chapter_title
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE s.content_ssml IS NOT NULL
                ORDER BY c.chapter_number, s.scene_number
            """)
            
            for row in cursor.fetchall():
                # Generate expected filename
                filename = self.audio_generator._create_audio_filename(
                    row['chapter_number'], 
                    row['scene_number'],
                    row['chapter_title']
                )
                
                audio_path = self.audio_dir / filename
                
                # Check if file is missing or 0-byte
                if not audio_path.exists() or audio_path.stat().st_size == 0:
                    failed_scenes.append((
                        row['id'],
                        row['chapter_number'],
                        row['scene_number'],
                        filename
                    ))
                    
        return failed_scenes
        
    def get_previous_repair_attempts(self, scene_id: int) -> int:
        """Get number of previous repair attempts for a scene."""
        history = self.repair_module.get_repair_history(scene_id)
        return len(history)
        
    def repair_and_regenerate_scene(self, scene_id: int, chapter_num: int, 
                                   scene_num: int, max_attempts: int = 3) -> bool:
        """
        Repair SSML and regenerate audio for a single scene.
        
        Args:
            scene_id: Database scene ID
            chapter_num: Chapter number
            scene_num: Scene number
            max_attempts: Maximum repair attempts
            
        Returns:
            True if successful, False otherwise
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get scene data
            cursor.execute("""
                SELECT s.content_ssml, c.title as chapter_title
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE s.id = ?
            """, (scene_id,))
            
            scene = cursor.fetchone()
            if not scene:
                logger.error(f"Scene {scene_id} not found")
                return False
                
        # Check previous repair attempts
        previous_attempts = self.get_previous_repair_attempts(scene_id)
        if previous_attempts >= max_attempts:
            logger.warning(f"Scene {scene_id} already has {previous_attempts} repair attempts, skipping")
            return False
            
        logger.info(f"Attempting to repair and regenerate Chapter {chapter_num}, Scene {scene_num}")
        
        # Try to generate audio with repair
        audio_path = self.audio_generator.generate_scene_audio(
            scene_id=scene_id,
            chapter_num=chapter_num,
            scene_num=scene_num,
            chapter_title=scene['chapter_title'],
            content_ssml=scene['content_ssml'],
            force_regenerate=True,
            max_repair_attempts=max_attempts - previous_attempts
        )
        
        return audio_path is not None
        
    def repair_all_failed_scenes(self, max_attempts: int = 3) -> Dict[str, any]:
        """
        Repair all failed scenes.
        
        Args:
            max_attempts: Maximum repair attempts per scene
            
        Returns:
            Dictionary with repair statistics
        """
        failed_scenes = self.find_failed_audio_files()
        
        if not failed_scenes:
            print("No failed audio files found!")
            return {"total": 0, "successful": 0, "failed": 0}
            
        print(f"\nFound {len(failed_scenes)} failed audio files")
        print("=" * 60)
        
        successful = 0
        failed = 0
        
        for scene_id, chapter_num, scene_num, filename in failed_scenes:
            print(f"\n[{successful + failed + 1}/{len(failed_scenes)}] "
                  f"Chapter {chapter_num}, Scene {scene_num} ({filename})...", end='', flush=True)
            
            if self.repair_and_regenerate_scene(scene_id, chapter_num, scene_num, max_attempts):
                successful += 1
                print(" ✓ Repaired and regenerated")
            else:
                failed += 1
                print(" ✗ Failed")
                
        print("\n" + "=" * 60)
        print(f"Repair complete: {successful}/{len(failed_scenes)} successful")
        
        return {
            "total": len(failed_scenes),
            "successful": successful,
            "failed": failed
        }
        
    def show_repair_history(self) -> None:
        """Show repair history for all scenes."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT scene_id FROM ssml_repair_log
                ORDER BY scene_id
            """)
            
            scene_ids = [row['scene_id'] for row in cursor.fetchall()]
            
            if not scene_ids:
                print("No repair history found")
                return
                
            print("\nSSML Repair History")
            print("=" * 80)
            
            for scene_id in scene_ids:
                # Get scene info
                cursor.execute("""
                    SELECT c.chapter_number, s.scene_number
                    FROM scenes s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE s.id = ?
                """, (scene_id,))
                
                scene_info = cursor.fetchone()
                if scene_info:
                    print(f"\nChapter {scene_info['chapter_number']}, "
                          f"Scene {scene_info['scene_number']} (ID: {scene_id}):")
                    
                    # Get repair attempts
                    history = self.repair_module.get_repair_history(scene_id)
                    for attempt in history:
                        status = "✓ Success" if attempt['repair_successful'] else "✗ Failed"
                        print(f"  Attempt {attempt['repair_attempt']}: {status} - "
                              f"Error {attempt['error_code']} - {attempt['created_at']}")


def main():
    """Main entry point for the repair tool."""
    parser = argparse.ArgumentParser(
        description="Repair failed audio generation by fixing SSML errors"
    )
    
    parser.add_argument(
        "--db-path",
        type=str,
        default=os.path.expanduser("~/.storyteller/story_database.db"),
        help="Path to the story database"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="audiobook_output",
        help="Directory containing audio files"
    )
    
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum repair attempts per scene (default: 3)"
    )
    
    parser.add_argument(
        "--speech-key",
        type=str,
        help="Azure Speech Service key (or set SPEECH_KEY env var)"
    )
    
    parser.add_argument(
        "--speech-region",
        type=str,
        help="Azure Speech Service region (or set SPEECH_REGION env var)"
    )
    
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show repair history and exit"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be repaired without actually doing it"
    )
    
    args = parser.parse_args()
    
    # Check if database exists
    if not Path(args.db_path).exists():
        print(f"Error: Database not found at {args.db_path}")
        sys.exit(1)
        
    # Get Azure credentials
    speech_key = args.speech_key or os.environ.get('SPEECH_KEY')
    speech_region = args.speech_region or os.environ.get('SPEECH_REGION')
    
    if not speech_key or not speech_region:
        print("Error: Azure Speech Service credentials not provided.")
        print("Set SPEECH_KEY and SPEECH_REGION environment variables or use --speech-key and --speech-region")
        sys.exit(1)
        
    try:
        # Initialize repair tool
        repair_tool = AudioRepairTool(
            db_path=args.db_path,
            output_dir=args.output_dir,
            speech_key=speech_key,
            speech_region=speech_region
        )
        
        if args.history:
            # Show repair history
            repair_tool.show_repair_history()
        elif args.dry_run:
            # Show what would be repaired
            failed_scenes = repair_tool.find_failed_audio_files()
            
            if not failed_scenes:
                print("No failed audio files found!")
            else:
                print(f"\nFound {len(failed_scenes)} failed audio files:")
                print("=" * 60)
                
                for scene_id, chapter_num, scene_num, filename in failed_scenes:
                    previous_attempts = repair_tool.get_previous_repair_attempts(scene_id)
                    print(f"Chapter {chapter_num}, Scene {scene_num}: {filename} "
                          f"(Previous attempts: {previous_attempts})")
                    
                print(f"\nRun without --dry-run to repair these files")
        else:
            # Perform repair
            print(f"\nAudio Repair Tool")
            print(f"Database: {args.db_path}")
            print(f"Audio directory: {repair_tool.audio_dir}")
            print(f"Max attempts: {args.max_attempts}")
            
            results = repair_tool.repair_all_failed_scenes(max_attempts=args.max_attempts)
            
            if results['total'] == 0:
                print("\n✓ All audio files are already generated successfully!")
            else:
                print(f"\n{'✓' if results['failed'] == 0 else '⚠'} "
                      f"Repair completed: {results['successful']}/{results['total']} successful")
                
                if results['failed'] > 0:
                    print(f"\nSome scenes could not be repaired. Check the logs for details.")
                    print(f"Run with --history to see repair attempts.")
                    
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        print(f"\nError: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()