#!/usr/bin/env python3
"""
Regenerate SSML content for all scenes with proper title announcements.

This script uses the updated SSML converter to regenerate SSML content
that includes book and chapter titles for first scenes.
"""

import os
import sys
import sqlite3
from pathlib import Path
from storyteller_lib.ssml_converter import SSMLConverter
from storyteller_lib.database.models import StoryDatabase
from storyteller_lib.logger import get_logger

logger = get_logger(__name__)

def main():
    """Regenerate SSML content with titles."""
    db_path = os.path.expanduser("~/.storyteller/story_database.db")
    
    if not Path(db_path).exists():
        print(f"Database not found at {db_path}")
        return
    
    print("Regenerating SSML content with title announcements...")
    
    # Initialize database
    db = StoryDatabase(db_path)
    
    # Get story metadata
    story_config = db.get_story_config()
    genre = story_config.get('genre', 'fiction')
    tone = story_config.get('tone', 'neutral')
    title = story_config.get('title', 'Untitled Story')
    language = story_config.get('language', 'english')
    
    # Initialize SSML converter
    converter = SSMLConverter(language=language)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all scenes with their chapter information
    cursor.execute("""
        SELECT s.id, s.content, s.scene_number, s.description,
               c.chapter_number, c.title as chapter_title
        FROM scenes s
        JOIN chapters c ON s.chapter_id = c.id
        WHERE s.content IS NOT NULL
        ORDER BY c.chapter_number, s.scene_number
    """)
    
    scenes = cursor.fetchall()
    total_scenes = len(scenes)
    updated_count = 0
    
    print(f"Found {total_scenes} scenes to process")
    print(f"Book title: {title}")
    print("=" * 60)
    
    for scene in scenes:
        # Determine if this is the first scene in chapter/book
        is_first_scene_in_chapter = scene['scene_number'] == 1
        is_first_scene_in_book = scene['chapter_number'] == 1 and scene['scene_number'] == 1
        
        print(f"\nProcessing Chapter {scene['chapter_number']}, Scene {scene['scene_number']}...", end='', flush=True)
        
        if is_first_scene_in_book:
            print(" (Book & Chapter intro)", end='', flush=True)
        elif is_first_scene_in_chapter:
            print(" (Chapter intro)", end='', flush=True)
        
        try:
            # Generate new SSML with title information
            new_ssml = converter.scene_to_ssml(
                scene_content=scene['content'],
                chapter_number=scene['chapter_number'],
                scene_number=scene['scene_number'],
                scene_description=scene['description'] or '',
                genre=genre,
                tone=tone,
                chapter_title=scene['chapter_title'],
                book_title=title if is_first_scene_in_book else None,
                is_first_scene_in_chapter=is_first_scene_in_chapter,
                is_first_scene_in_book=is_first_scene_in_book
            )
            
            # Update the database
            cursor.execute("""
                UPDATE scenes 
                SET content_ssml = ? 
                WHERE id = ?
            """, (new_ssml, scene['id']))
            
            updated_count += 1
            print(" ✓")
            
        except Exception as e:
            print(f" ✗ Error: {str(e)}")
            logger.error(f"Error processing scene {scene['id']}: {str(e)}")
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 60)
    print(f"✓ Successfully regenerated SSML for {updated_count}/{total_scenes} scenes")
    print("\nThe SSML content now includes:")
    print("- Book title announcement at the beginning of Chapter 1, Scene 1")
    print("- Chapter title announcements at the beginning of each chapter")
    print("\nYou can now generate the audiobook with proper title narration.")

if __name__ == "__main__":
    main()