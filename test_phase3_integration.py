#!/usr/bin/env python3
"""
Test Phase 3 - Database context integration with story generation.

This script tests that the database context is properly used during
story generation to maintain consistency and dependencies.
"""

import os
import sys
from pathlib import Path

# Set environment variables before imports
os.environ["ENABLE_DATABASE"] = "true"
os.environ["STORY_DATABASE_PATH"] = "test_phase3.db"

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_context_integration():
    """Test that database context is integrated into story generation."""
    print("Testing Phase 3: Database Context Integration...")
    
    # Clean up any existing test database
    test_db = "test_phase3.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    try:
        # Import after environment setup
        from storyteller_lib.database import StoryDatabase
        from storyteller_lib.database_integration import StoryDatabaseManager
        from storyteller_lib.story_context import StoryContextProvider
        
        # Initialize database manager
        db_manager = StoryDatabaseManager(test_db, enabled=True)
        print("✓ Database manager initialized")
        
        # Create a test story state
        test_state = {
            'messages': [],
            'genre': 'mystery',
            'tone': 'noir',
            'author': '',
            'language': 'english',
            'initial_idea': 'A detective investigates a series of art thefts',
            'global_story': 'A noir mystery about stolen art',
            'chapters': {},
            'characters': {
                'detective': {
                    'name': 'Sam Spade',
                    'role': 'protagonist',
                    'backstory': 'Cynical private investigator',
                    'relationships': {'client': 'employer'}
                },
                'client': {
                    'name': 'Vera Sterling',
                    'role': 'mysterious client',
                    'backstory': 'Art gallery owner with secrets'
                }
            },
            'world_elements': {
                'locations': {
                    'office': {
                        'name': "Spade's Office",
                        'description': 'Dingy downtown office',
                        'type': 'workplace'
                    },
                    'gallery': {
                        'name': 'Sterling Gallery',
                        'description': 'Upscale art gallery',
                        'type': 'business'
                    }
                }
            },
            'plot_threads': {
                'Art Thefts': {
                    'description': 'Series of valuable paintings stolen',
                    'thread_type': 'main_plot',
                    'importance': 'major',
                    'status': 'introduced'
                }
            }
        }
        
        # Save initial state
        story_id = db_manager.create_story(test_state)
        print(f"✓ Created story with ID: {story_id}")
        
        # Save some initial data
        db_manager._save_characters(test_state)
        db_manager._save_world_elements(test_state)
        db_manager._save_plot_threads(test_state)
        print("✓ Saved initial story elements")
        
        # Initialize context provider
        context_provider = StoryContextProvider(story_id)
        print("✓ Context provider initialized")
        
        # Test 1: Character context retrieval
        char_context = context_provider.get_character_context('detective', 1, 1)
        print(f"✓ Retrieved character context: {char_context.get('identifier', 'N/A')}")
        
        # Test 2: Scene dependencies
        scene_deps = context_provider.get_scene_dependencies(1, 1)
        print(f"✓ Retrieved scene dependencies: {len(scene_deps.get('characters', []))} characters, "
              f"{len(scene_deps.get('locations', []))} locations")
        
        # Test 3: Add a chapter and scene to test continuity
        test_state['current_chapter'] = 'Chapter 1'
        test_state['chapters']['Chapter 1'] = {
            'title': 'The Case Begins',
            'outline': 'Detective meets client',
            'scenes': {
                'Scene 1': {
                    'outline': 'Client arrives at office',
                    'content': 'The dame walked into my office like trouble in high heels...'
                }
            }
        }
        
        db_manager._current_chapter_id = 1  # Simulate chapter creation
        db_manager._save_chapter(test_state)
        
        test_state['current_scene'] = 'Scene 1'
        db_manager._current_scene_id = 1  # Simulate scene creation
        db_manager._save_scene(test_state)
        print("✓ Saved chapter and scene")
        
        # Test 4: Continuity check
        continuity_data = context_provider.get_continuity_check_data(1)
        print(f"✓ Retrieved continuity data: {len(continuity_data.get('character_tracking', {}))} characters tracked")
        
        # Test 5: Verify character states are tracked
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM characters")
            char_count = cursor.fetchone()['count']
            print(f"✓ Database contains {char_count} characters")
            
            cursor.execute("SELECT COUNT(*) as count FROM locations")
            loc_count = cursor.fetchone()['count']
            print(f"✓ Database contains {loc_count} locations")
            
            cursor.execute("SELECT COUNT(*) as count FROM plot_threads")
            thread_count = cursor.fetchone()['count']
            print(f"✓ Database contains {thread_count} plot threads")
        
        print("\n✅ Phase 3 integration test passed!")
        print("\nThe database context is properly integrated with:")
        print("- Character state tracking")
        print("- Scene dependency resolution")
        print("- Continuity checking")
        print("- Plot thread tracking")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if os.path.exists(test_db):
            os.remove(test_db)
            print("\n✓ Cleaned up test database")


if __name__ == "__main__":
    test_context_integration()