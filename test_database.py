#!/usr/bin/env python3
"""
Test script for the StoryCraft database implementation.

This script creates a test database and verifies basic CRUD operations.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from storyteller_lib.database import StoryDatabase, DatabaseStateAdapter, StoryQueries
from storyteller_lib.models import StoryState


def test_database():
    """Test basic database functionality."""
    print("Testing StoryCraft Database Implementation...")
    
    # Use a test database file
    test_db = "test_story.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    # Create database instance
    db = StoryDatabase(test_db)
    print("✓ Database initialized")
    
    # Test 1: Create a story
    story_id = db.create_story(
        title="The Hero's Quest",
        genre="fantasy",
        tone="epic",
        author="Test Author",
        language="english",
        initial_idea="A young farmer discovers they are the chosen one"
    )
    print(f"✓ Created story with ID: {story_id}")
    
    # Test 2: Get story
    story = db.get_story(story_id)
    print(f"✓ Retrieved story: {story['title']}")
    
    # Test 3: Create characters
    hero_id = db.create_character(
        story_id=story_id,
        identifier="hero",
        name="Aria",
        role="protagonist",
        backstory="A young farmer from a small village"
    )
    
    mentor_id = db.create_character(
        story_id=story_id,
        identifier="mentor",
        name="Gandor",
        role="wise mentor",
        backstory="An ancient wizard with vast knowledge"
    )
    print(f"✓ Created characters: hero (ID: {hero_id}), mentor (ID: {mentor_id})")
    
    # Test 4: Create relationship
    db.create_relationship(
        char1_id=hero_id,
        char2_id=mentor_id,
        rel_type="mentor-student",
        description="Gandor guides Aria on her quest"
    )
    print("✓ Created character relationship")
    
    # Test 5: Create location
    location_id = db.create_location(
        story_id=story_id,
        identifier="starting_village",
        name="Millbrook",
        description="A peaceful farming village",
        location_type="village"
    )
    print(f"✓ Created location: Millbrook (ID: {location_id})")
    
    # Test 6: Create world elements
    db.create_world_element(
        story_id=story_id,
        category="geography",
        element_key="world_name",
        element_value="Aetheria"
    )
    
    db.create_world_element(
        story_id=story_id,
        category="magic",
        element_key="magic_system",
        element_value={
            "type": "elemental",
            "elements": ["fire", "water", "earth", "air"],
            "source": "natural energy"
        }
    )
    print("✓ Created world elements")
    
    # Test 7: Create plot thread
    thread_id = db.create_plot_thread(
        story_id=story_id,
        name="The Prophecy",
        description="An ancient prophecy foretells of a chosen one",
        thread_type="main_plot",
        importance="major"
    )
    print(f"✓ Created plot thread: The Prophecy (ID: {thread_id})")
    
    # Test 8: Create chapter and scene
    chapter_id = db.create_chapter(
        story_id=story_id,
        chapter_num=1,
        title="The Beginning",
        outline="Aria discovers her destiny"
    )
    
    scene_id = db.create_scene(
        chapter_id=chapter_id,
        scene_num=1,
        outline="Aria meets Gandor",
        content="The sun was setting over Millbrook when the wizard arrived..."
    )
    print(f"✓ Created chapter and scene (Chapter ID: {chapter_id}, Scene ID: {scene_id})")
    
    # Test 9: Add entities to scene
    db.add_entity_to_scene(scene_id, "character", hero_id, "present")
    db.add_entity_to_scene(scene_id, "character", mentor_id, "present")
    db.add_entity_to_scene(scene_id, "location", location_id, "present")
    print("✓ Added entities to scene")
    
    # Test 10: Update character state
    db.update_character_state(
        character_id=hero_id,
        scene_id=scene_id,
        state={
            "emotional_state": "confused but curious",
            "physical_location_id": location_id,
            "knowledge_state": ["prophecy exists", "chosen one mentioned"],
            "evolution_notes": "Beginning to understand her importance"
        }
    )
    print("✓ Updated character state")
    
    # Test 11: Add plot thread development
    db.add_plot_thread_development(
        plot_thread_id=thread_id,
        scene_id=scene_id,
        development_type="introduced",
        description="Gandor reveals the prophecy to Aria"
    )
    print("✓ Added plot thread development")
    
    # Test 12: Query functions
    queries = StoryQueries(db)
    
    # Get entities in scene
    entities = db.get_entities_in_scene(scene_id)
    print(f"✓ Scene entities: {len(entities['characters'])} characters, "
          f"{len(entities['locations'])} locations")
    
    # Get character relationships
    relationships = db.get_character_relationships(hero_id)
    print(f"✓ Character relationships: {len(relationships)} found")
    
    # Get scene context
    context = db.get_scene_context(scene_id)
    print(f"✓ Scene context retrieved with {len(context['entities']['characters'])} characters")
    
    # Test 13: State adapter
    adapter = DatabaseStateAdapter(db)
    
    # Create a test state
    test_state: StoryState = {
        'messages': [],
        'genre': 'fantasy',
        'tone': 'epic',
        'author': 'Test Author',
        'author_style_guidance': '',
        'language': 'english',
        'initial_idea': 'A young farmer discovers they are the chosen one',
        'initial_idea_elements': {},
        'global_story': 'A classic hero\'s journey',
        'chapters': {
            'Chapter 1': {
                'title': 'The Beginning',
                'outline': 'Aria discovers her destiny',
                'scenes': {
                    'Scene 1': {
                        'content': 'The sun was setting over Millbrook...',
                        'reflection_notes': []
                    }
                },
                'reflection_notes': []
            }
        },
        'characters': {
            'hero': {
                'name': 'Aria',
                'role': 'protagonist',
                'backstory': 'A young farmer',
                'evolution': [],
                'known_facts': [],
                'secret_facts': [],
                'revealed_facts': [],
                'relationships': {'mentor': 'student'}
            }
        },
        'world_elements': {
            'geography': {
                'world_name': 'Aetheria'
            }
        },
        'plot_threads': {
            'The Prophecy': {
                'description': 'Ancient prophecy',
                'importance': 'major',
                'status': 'introduced'
            }
        },
        'revelations': {},
        'creative_elements': {},
        'current_chapter': 'Chapter 1',
        'current_scene': 'Scene 1',
        'completed': False,
        'last_node': 'test'
    }
    
    # Sync to database
    synced_story_id = adapter.sync_to_database(test_state)
    print(f"✓ Synced state to database (Story ID: {synced_story_id})")
    
    # Load from database
    loaded_state = adapter.load_from_database(story_id)
    print(f"✓ Loaded state from database: {len(loaded_state['characters'])} characters")
    
    print("\n✅ All tests passed!")
    
    # Cleanup
    if os.path.exists(test_db):
        os.remove(test_db)
        print("✓ Cleaned up test database")


if __name__ == "__main__":
    test_database()