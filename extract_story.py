#!/usr/bin/env python3
"""
Extract the last generated story from the database and save it to story.md
"""

import sqlite3
import os
from pathlib import Path

def extract_story():
    # Database path
    db_path = Path.home() / ".storyteller" / "story_database.db"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get story configuration
        cursor.execute("SELECT * FROM story_config WHERE id = 1")
        config = cursor.fetchone()
        
        if not config:
            print("No story configuration found in database")
            return
        
        # Start building the story content
        story_content = []
        
        # Add title if available
        if config['title']:
            story_content.append(f"# {config['title']}")
        else:
            story_content.append("# Generated Story")
        
        story_content.append("")
        
        # Add metadata
        story_content.append("## Story Information")
        story_content.append(f"- **Genre**: {config['genre']}")
        story_content.append(f"- **Tone**: {config['tone']}")
        if config['author']:
            story_content.append(f"- **Author Style**: {config['author']}")
        if config['language']:
            story_content.append(f"- **Language**: {config['language']}")
        if config['initial_idea']:
            story_content.append(f"- **Initial Idea**: {config['initial_idea']}")
        story_content.append("")
        
        # Get all chapters ordered by number
        cursor.execute("""
            SELECT * FROM chapters 
            ORDER BY chapter_number
        """)
        chapters = cursor.fetchall()
        
        if not chapters:
            print("No chapters found in database")
            return
        
        # Process each chapter
        for chapter in chapters:
            # Add chapter title
            story_content.append(f"## Chapter {chapter['chapter_number']}: {chapter['title']}")
            story_content.append("")
            
            # Get all scenes for this chapter
            cursor.execute("""
                SELECT * FROM scenes 
                WHERE chapter_id = ? 
                ORDER BY scene_number
            """, (chapter['id'],))
            scenes = cursor.fetchall()
            
            # Add each scene
            for scene in scenes:
                if scene['content']:
                    story_content.append(scene['content'])
                    story_content.append("")
                else:
                    story_content.append(f"[Scene {scene['scene_number']} - No content found]")
                    story_content.append("")
        
        # Join all content
        final_story = "\n".join(story_content)
        
        # Save to file
        output_path = "story.md"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_story)
        
        print(f"Story successfully extracted and saved to {output_path}")
        print(f"Total chapters: {len(chapters)}")
        
        # Count total scenes
        cursor.execute("SELECT COUNT(*) as count FROM scenes")
        scene_count = cursor.fetchone()['count']
        print(f"Total scenes: {scene_count}")
        
        # Calculate word count
        word_count = len(final_story.split())
        print(f"Total words: {word_count:,}")
        
    except Exception as e:
        print(f"Error extracting story: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    extract_story()