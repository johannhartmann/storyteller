#!/usr/bin/env python3
"""
Direct test of database module without going through __init__.py
"""

import sys
import os

# Get the absolute path to the database models
db_path = os.path.join(os.path.dirname(__file__), 'storyteller_lib', 'database', 'models.py')

# Read and execute the models file directly
with open(db_path, 'r') as f:
    db_code = f.read()

# Create a namespace for execution
namespace = {}
# Execute the database code in the namespace
exec(db_code, namespace)

# Get the classes we need
StoryDatabase = namespace['StoryDatabase']
DatabaseStateAdapter = namespace['DatabaseStateAdapter'] 
StoryQueries = namespace['StoryQueries']

print("Testing StoryCraft Database (Direct Import)...")

# Use a test database file
test_db = "test_direct.db"
if os.path.exists(test_db):
    os.remove(test_db)

try:
    # Create database instance
    db = StoryDatabase(test_db)
    print("✓ Database initialized")
    
    # Test basic operations
    story_id = db.create_story(
        title="Test Story",
        genre="fantasy",
        tone="epic"
    )
    print(f"✓ Created story with ID: {story_id}")
    
    # Get story
    story = db.get_story(story_id)
    print(f"✓ Retrieved story: {story['title']}")
    
    # Create a character
    char_id = db.create_character(
        story_id=story_id,
        identifier="hero",
        name="Test Hero",
        role="protagonist"
    )
    print(f"✓ Created character with ID: {char_id}")
    
    # Create a location
    loc_id = db.create_location(
        story_id=story_id,
        identifier="village",
        name="Test Village",
        location_type="village"
    )
    print(f"✓ Created location with ID: {loc_id}")
    
    # Create world element
    db.create_world_element(
        story_id=story_id,
        category="geography",
        element_key="world_name",
        element_value="Test World"
    )
    print("✓ Created world element")
    
    # Create plot thread
    thread_id = db.create_plot_thread(
        story_id=story_id,
        name="Main Quest",
        thread_type="main_plot",
        importance="major"
    )
    print(f"✓ Created plot thread with ID: {thread_id}")
    
    # Create chapter and scene
    chapter_id = db.create_chapter(
        story_id=story_id,
        chapter_num=1,
        title="Chapter One"
    )
    
    scene_id = db.create_scene(
        chapter_id=chapter_id,
        scene_num=1,
        content="Test scene content..."
    )
    print(f"✓ Created chapter {chapter_id} and scene {scene_id}")
    
    # Add entity to scene
    db.add_entity_to_scene(scene_id, "character", char_id)
    db.add_entity_to_scene(scene_id, "location", loc_id)
    print("✓ Added entities to scene")
    
    # Update character state
    db.update_character_state(
        character_id=char_id,
        scene_id=scene_id,
        state={
            "emotional_state": "curious",
            "physical_location_id": loc_id
        }
    )
    print("✓ Updated character state")
    
    # Test queries
    queries = StoryQueries(db)
    
    entities = db.get_entities_in_scene(scene_id)
    print(f"✓ Retrieved scene entities: {len(entities['characters'])} characters")
    
    context = db.get_scene_context(scene_id) 
    print(f"✓ Retrieved scene context")
    
    print("\n✅ All basic database tests passed!")
    
except Exception as e:
    print(f"\n❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
finally:
    # Cleanup
    if os.path.exists(test_db):
        os.remove(test_db)
        print("✓ Cleaned up test database")