"""
Book statistics calculation and reporting module.

This module provides functions to calculate and display book length statistics
including word count, page count, and progress tracking.
"""

from typing import Dict, Optional, Tuple
import sqlite3
from pathlib import Path


def calculate_book_stats(db_manager=None) -> Dict:
    """
    Calculate current book statistics from the database.
    
    Returns:
        Dict containing book statistics
    """
    try:
        # Get database connection - handle context manager
        if db_manager and hasattr(db_manager, '_db') and db_manager._db:
            # Use context manager properly
            with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                
                # Get current content stats
                cursor.execute("""
                    SELECT COUNT(*) as scene_count, SUM(LENGTH(content)) as total_chars
                    FROM scenes 
                    WHERE content IS NOT NULL AND content != ''
                """)
                result = cursor.fetchone()
                current_scenes = result[0] if result and result[0] else 0
                current_chars = result[1] if result and result[1] else 0
                
                # Calculate word count (approximate)
                current_words = current_chars // 5 if current_chars else 0  # Rough estimate: 5 chars per word
                
                # Calculate pages (250 words per page standard)
                current_pages = current_words // 250 if current_words else 0
                
                # Calculate average words per scene
                avg_scene_words = current_words // current_scenes if current_scenes > 0 else 600  # Default 600 words
                
                # Get chapter and scene breakdown
                cursor.execute("""
                    SELECT c.chapter_number, COUNT(s.id) as scene_count
                    FROM chapters c
                    LEFT JOIN scenes s ON c.id = s.chapter_id
                    WHERE s.content IS NOT NULL AND s.content != ''
                    GROUP BY c.chapter_number
                    ORDER BY c.chapter_number
                """)
                chapter_progress = cursor.fetchall()
                
                # Get total planned chapters
                cursor.execute('SELECT MAX(chapter_number) FROM chapters')
                result = cursor.fetchone()
                total_chapters = result[0] if result and result[0] else 0
                
                return {
                    'current_words': current_words,
                    'current_pages': current_pages,
                    'avg_scene_words': avg_scene_words,
                    'current_scenes': current_scenes,
                    'total_chars': current_chars,
                    'chapter_progress': chapter_progress,
                    'total_chapters': total_chapters
                }
        else:
            # Fallback to direct connection
            db_path = Path.home() / '.storyteller' / 'story_database.db'
            if not db_path.exists():
                return {
                    'current_words': 0,
                    'current_pages': 0,
                    'avg_scene_words': 600,
                    'current_scenes': 0,
                    'total_chars': 0,
                    'chapter_progress': [],
                    'total_chapters': 0
                }
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Same queries as above
                cursor.execute("""
                    SELECT COUNT(*) as scene_count, SUM(LENGTH(content)) as total_chars
                    FROM scenes 
                    WHERE content IS NOT NULL AND content != ''
                """)
                result = cursor.fetchone()
                current_scenes = result[0] if result and result[0] else 0
                current_chars = result[1] if result and result[1] else 0
                
                current_words = current_chars // 5 if current_chars else 0
                current_pages = current_words // 250 if current_words else 0
                avg_scene_words = current_words // current_scenes if current_scenes > 0 else 600
                
                cursor.execute("""
                    SELECT c.chapter_number, COUNT(s.id) as scene_count
                    FROM chapters c
                    LEFT JOIN scenes s ON c.id = s.chapter_id
                    WHERE s.content IS NOT NULL AND s.content != ''
                    GROUP BY c.chapter_number
                    ORDER BY c.chapter_number
                """)
                chapter_progress = cursor.fetchall()
                
                cursor.execute('SELECT MAX(chapter_number) FROM chapters')
                result = cursor.fetchone()
                total_chapters = result[0] if result and result[0] else 0
                
                return {
                    'current_words': current_words,
                    'current_pages': current_pages,
                    'avg_scene_words': avg_scene_words,
                    'current_scenes': current_scenes,
                    'total_chars': current_chars,
                    'chapter_progress': chapter_progress,
                    'total_chapters': total_chapters
                }
                
    except Exception as e:
        # Return defaults if database query fails
        return {
            'current_words': 0,
            'current_pages': 0,
            'avg_scene_words': 600,
            'current_scenes': 0,
            'total_chars': 0,
            'chapter_progress': [],
            'total_chapters': 0
        }
    
    # Calculate averages
    avg_chars_per_scene = current_chars / current_scenes if current_scenes > 0 else 0
    
    # Book metrics
    chars_per_word = 5.5
    words_per_page_manuscript = 250  # Double-spaced
    words_per_page_printed = 300     # Single-spaced printed book
    
    # Current stats
    current_words = current_chars / chars_per_word if current_chars > 0 else 0
    current_pages_manuscript = current_words / words_per_page_manuscript
    current_pages_printed = current_words / words_per_page_printed
    
    # Projected stats (12 chapters, 4 scenes each for hero's journey)
    typical_chapters = 12
    scenes_per_chapter = 4
    total_projected_scenes = typical_chapters * scenes_per_chapter
    
    projected_chars = avg_chars_per_scene * total_projected_scenes
    projected_words = projected_chars / chars_per_word
    projected_pages_manuscript = projected_words / words_per_page_manuscript
    projected_pages_printed = projected_words / words_per_page_printed
    
    # Close connection if we created it
    if not db_manager:
        conn.close()
    
    return {
        'current_scenes': current_scenes,
        'current_chars': current_chars,
        'current_words': int(current_words),
        'current_pages_manuscript': int(current_pages_manuscript),
        'current_pages_printed': int(current_pages_printed),
        'avg_chars_per_scene': int(avg_chars_per_scene),
        'avg_words_per_scene': int(avg_chars_per_scene / chars_per_word),
        'chapters_with_content': len(chapter_progress),
        'total_chapters_created': total_chapters,
        'projected_scenes': total_projected_scenes,
        'projected_words': int(projected_words),
        'projected_pages_printed': int(projected_pages_printed),
        'completion_percentage': int((current_scenes / total_projected_scenes) * 100) if total_projected_scenes > 0 else 0,
        'chapter_breakdown': chapter_progress
    }


def get_novel_category(word_count: int) -> str:
    """Get the novel category based on word count."""
    if word_count < 1000:
        return "Flash Fiction"
    elif word_count < 7500:
        return "Short Story"
    elif word_count < 20000:
        return "Novelette"
    elif word_count < 50000:
        return "Novella"
    elif word_count < 110000:
        return "Novel"
    else:
        return "Epic"


def format_progress_report(stats: Dict) -> str:
    """
    Format statistics into a readable progress report.
    
    Args:
        stats: Dictionary of book statistics
        
    Returns:
        Formatted progress report string
    """
    report = []
    report.append("\n" + "="*60)
    report.append("📊 BOOK PROGRESS REPORT")
    report.append("="*60)
    
    # Current progress
    report.append(f"\n📝 Current Progress:")
    report.append(f"  • Scenes completed: {stats['current_scenes']}")
    report.append(f"  • Chapters with content: {stats['chapters_with_content']}")
    report.append(f"  • Total words: {stats['current_words']:,}")
    report.append(f"  • Pages (printed book): {stats['current_pages_printed']}")
    report.append(f"  • Average words per scene: {stats['avg_words_per_scene']:,}")
    
    # Completion status
    report.append(f"\n📈 Completion Status:")
    report.append(f"  • Progress: {stats['completion_percentage']}% ({stats['current_scenes']}/{stats['projected_scenes']} scenes)")
    
    # Progress bar
    progress_bar_length = 30
    filled_length = int(progress_bar_length * stats['completion_percentage'] / 100)
    bar = '█' * filled_length + '░' * (progress_bar_length - filled_length)
    report.append(f"  • [{bar}]")
    
    # Projected full book
    report.append(f"\n📚 Projected Full Book:")
    report.append(f"  • Total words: ~{stats['projected_words']:,}")
    report.append(f"  • Pages (printed): ~{stats['projected_pages_printed']}")
    report.append(f"  • Category: {get_novel_category(stats['projected_words'])}")
    
    # Chapter breakdown
    if stats['chapter_breakdown']:
        report.append(f"\n📖 Chapter Breakdown:")
        for chapter_num, scene_count in stats['chapter_breakdown']:
            report.append(f"  • Chapter {chapter_num}: {scene_count} scenes")
    
    report.append("="*60 + "\n")
    
    return '\n'.join(report)


def display_progress_report(db_manager=None) -> None:
    """Calculate and display the progress report to stdout."""
    try:
        stats = calculate_book_stats(db_manager)
        report = format_progress_report(stats)
        print(report)
    except Exception as e:
        print(f"[Warning] Could not generate progress report: {e}")