#!/usr/bin/env python3
"""
Standalone test script for the StoryCraft database implementation.

This script tests the database module in isolation without importing
the full storyteller library.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

# Add just the database module path
sys.path.insert(0, str(Path(__file__).parent))

# Import only the database components directly
from storyteller_lib.database.models import StoryDatabase, DatabaseStateAdapter, StoryQueries


def test_database_standalone():
    """Test database functionality without full library dependencies."""
    print("Testing StoryCraft Database Implementation (Standalone)...")
    
    # Use a test database file
    test_db = "test_story_standalone.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    try:
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
            backstory="A young farmer from a small village",
            personality="Brave but inexperienced"
        )
        
        mentor_id = db.create_character(
            story_id=story_id,
            identifier="mentor",
            name="Gandor",
            role="wise mentor",
            backstory="An ancient wizard with vast knowledge",
            personality="Patient and cryptic"
        )
        
        villain_id = db.create_character(
            story_id=story_id,
            identifier="villain",
            name="Lord Malachar",
            role="antagonist",
            backstory="A fallen hero corrupted by dark magic",
            personality="Ruthless and calculating"
        )
        print(f"✓ Created characters: hero (ID: {hero_id}), mentor (ID: {mentor_id}), villain (ID: {villain_id})")
        
        # Test 4: Create relationships
        db.create_relationship(
            char1_id=hero_id,
            char2_id=mentor_id,
            rel_type="mentor-student",
            description="Gandor guides Aria on her quest",
            properties={"trust_level": "growing", "established": "chapter_1"}
        )
        
        db.create_relationship(
            char1_id=hero_id,
            char2_id=villain_id,
            rel_type="enemies",
            description="Destined to clash",
            properties={"awareness": "unaware", "prophecy_linked": True}
        )
        print("✓ Created character relationships")
        
        # Test 5: Verify relationships query
        hero_relationships = db.get_character_relationships(hero_id)
        print(f"✓ Retrieved {len(hero_relationships)} relationships for hero")
        
        # Test 6: Create locations
        village_id = db.create_location(
            story_id=story_id,
            identifier="starting_village",
            name="Millbrook",
            description="A peaceful farming village surrounded by rolling hills",
            location_type="village",
            properties={"population": 500, "notable_features": ["mill", "market square", "inn"]}
        )
        
        castle_id = db.create_location(
            story_id=story_id,
            identifier="dark_castle",
            name="Shadowspire Keep",
            description="A foreboding fortress shrouded in perpetual mist",
            location_type="castle",
            properties={"defenses": "magical barriers", "atmosphere": "oppressive"}
        )
        print(f"✓ Created locations: village (ID: {village_id}), castle (ID: {castle_id})")
        
        # Test 7: Create world elements
        db.create_world_element(
            story_id=story_id,
            category="geography",
            element_key="world_name",
            element_value="Aetheria"
        )
        
        db.create_world_element(
            story_id=story_id,
            category="geography",
            element_key="continents",
            element_value=["Northlands", "Central Kingdoms", "Southern Wastes"]
        )
        
        db.create_world_element(
            story_id=story_id,
            category="magic",
            element_key="magic_system",
            element_value={
                "type": "elemental",
                "elements": ["fire", "water", "earth", "air", "spirit"],
                "source": "natural energy channeled through willpower",
                "limitations": "exhaustion and elemental balance"
            }
        )
        
        db.create_world_element(
            story_id=story_id,
            category="history",
            element_key="the_sundering",
            element_value={
                "when": "1000 years ago",
                "what": "Great magical war that split the continent",
                "consequences": ["magic became unstable", "ancient knowledge lost"]
            }
        )
        print("✓ Created world elements")
        
        # Test 8: Retrieve world elements
        world_elements = db.get_world_elements(story_id)
        print(f"✓ Retrieved world elements: {len(world_elements)} categories")
        
        # Test 9: Create plot threads
        main_thread_id = db.create_plot_thread(
            story_id=story_id,
            name="The Prophecy of the Chosen One",
            description="An ancient prophecy foretells of a farmer who will defeat the darkness",
            thread_type="main_plot",
            importance="major",
            status="introduced"
        )
        
        subplot_id = db.create_plot_thread(
            story_id=story_id,
            name="Gandor's Hidden Past",
            description="The mentor harbors secrets about his connection to the villain",
            thread_type="subplot",
            importance="major",
            status="introduced"
        )
        
        character_arc_id = db.create_plot_thread(
            story_id=story_id,
            name="Aria's Self-Discovery",
            description="Learning to believe in herself and her abilities",
            thread_type="character_arc",
            importance="major",
            status="introduced"
        )
        print(f"✓ Created plot threads: main (ID: {main_thread_id}), subplot (ID: {subplot_id}), arc (ID: {character_arc_id})")
        
        # Test 10: Create chapters and scenes
        chapter1_id = db.create_chapter(
            story_id=story_id,
            chapter_num=1,
            title="The Call to Adventure",
            outline="Aria's ordinary life is disrupted by Gandor's arrival"
        )
        
        scene1_id = db.create_scene(
            chapter_id=chapter1_id,
            scene_num=1,
            outline="Opening - Aria's daily life in Millbrook",
            content="The sun rose over the peaceful village of Millbrook, casting golden light across the wheat fields..."
        )
        
        scene2_id = db.create_scene(
            chapter_id=chapter1_id,
            scene_num=2,
            outline="The mysterious visitor arrives",
            content="The inn fell silent as the cloaked figure entered, staff tapping against the wooden floor..."
        )
        
        chapter2_id = db.create_chapter(
            story_id=story_id,
            chapter_num=2,
            title="The Journey Begins",
            outline="Aria and Gandor set out on their quest"
        )
        
        scene3_id = db.create_scene(
            chapter_id=chapter2_id,
            scene_num=1,
            outline="Leaving home",
            content="With the village disappearing behind them, Aria felt the weight of her decision..."
        )
        print(f"✓ Created chapters and scenes (C1: {chapter1_id}, C2: {chapter2_id})")
        
        # Test 11: Add entities to scenes
        # Scene 1: Aria in village
        db.add_entity_to_scene(scene1_id, "character", hero_id, "present")
        db.add_entity_to_scene(scene1_id, "location", village_id, "present")
        
        # Scene 2: Gandor arrives, meets Aria
        db.add_entity_to_scene(scene2_id, "character", hero_id, "present")
        db.add_entity_to_scene(scene2_id, "character", mentor_id, "present")
        db.add_entity_to_scene(scene2_id, "location", village_id, "present")
        
        # Scene 3: Both traveling
        db.add_entity_to_scene(scene3_id, "character", hero_id, "present")
        db.add_entity_to_scene(scene3_id, "character", mentor_id, "present")
        db.add_entity_to_scene(scene3_id, "location", village_id, "mentioned")
        print("✓ Added entities to scenes")
        
        # Test 12: Update character states
        db.update_character_state(
            character_id=hero_id,
            scene_id=scene1_id,
            state={
                "emotional_state": "content but restless",
                "physical_location_id": village_id,
                "knowledge_state": ["farm life", "local legends"],
                "evolution_notes": "Establishing baseline ordinary world"
            }
        )
        
        db.update_character_state(
            character_id=hero_id,
            scene_id=scene2_id,
            state={
                "emotional_state": "curious and apprehensive",
                "physical_location_id": village_id,
                "knowledge_state": ["farm life", "local legends", "stranger seeks her"],
                "revealed_secrets": ["chosen one prophecy hinted"],
                "evolution_notes": "First glimpse of larger destiny"
            }
        )
        
        db.update_character_state(
            character_id=hero_id,
            scene_id=scene3_id,
            state={
                "emotional_state": "determined but homesick",
                "knowledge_state": ["farm life", "local legends", "prophecy basics", "quest ahead"],
                "evolution_notes": "Crossed the threshold, no turning back"
            }
        )
        print("✓ Updated character states across scenes")
        
        # Test 13: Add character knowledge
        db.add_character_knowledge(
            character_id=hero_id,
            scene_id=scene2_id,
            knowledge={
                "knowledge_type": "prophecy",
                "knowledge_content": "A chosen one will rise from humble beginnings",
                "source": "Gandor's cryptic words"
            }
        )
        
        db.add_character_knowledge(
            character_id=mentor_id,
            scene_id=scene2_id,
            knowledge={
                "knowledge_type": "secret",
                "knowledge_content": "Aria's true parentage",
                "source": "personal knowledge"
            }
        )
        print("✓ Added character knowledge entries")
        
        # Test 14: Plot thread developments
        db.add_plot_thread_development(
            plot_thread_id=main_thread_id,
            scene_id=scene2_id,
            development_type="introduced",
            description="Gandor hints at the prophecy to Aria"
        )
        
        db.add_plot_thread_development(
            plot_thread_id=character_arc_id,
            scene_id=scene3_id,
            development_type="advanced",
            description="Aria makes the choice to leave her comfortable life"
        )
        print("✓ Added plot thread developments")
        
        # Test 15: Log entity changes
        db.log_entity_change(
            entity_type="character",
            entity_id=hero_id,
            scene_id=scene2_id,
            change_type="revealed",
            change_description="Aria learns she might be special",
            old_value={"awareness": "none"},
            new_value={"awareness": "prophecy_mentioned"}
        )
        print("✓ Logged entity changes")
        
        # Test 16: Complex queries
        queries = StoryQueries(db)
        
        # Get entities in scene
        scene2_entities = db.get_entities_in_scene(scene2_id)
        print(f"✓ Scene 2 entities: {len(scene2_entities['characters'])} characters, "
              f"{len(scene2_entities['locations'])} locations")
        
        # Get scenes with hero
        hero_scenes = db.get_scenes_with_entity("character", hero_id)
        print(f"✓ Hero appears in {len(hero_scenes)} scenes")
        
        # Get character journey
        hero_journey = queries.get_character_journey(hero_id)
        print(f"✓ Hero journey: {len(hero_journey['appearances'])} appearances, "
              f"{len(hero_journey['state_changes'])} state changes")
        
        # Get unresolved plot threads
        unresolved = queries.get_unresolved_plot_threads(story_id)
        print(f"✓ Unresolved plot threads: {len(unresolved)}")
        
        # Get scene context
        scene2_context = db.get_scene_context(scene2_id)
        print(f"✓ Scene 2 context: {len(scene2_context['character_states'])} character states")
        
        # Get chapter contexts
        chapter1_start = db.get_chapter_start_context(chapter1_id)
        chapter1_end = db.get_chapter_end_context(chapter1_id)
        chapter2_start = db.get_chapter_start_context(chapter2_id)
        print("✓ Retrieved chapter start/end contexts")
        
        # Test 17: Update plot thread status
        db.update_plot_thread_status(main_thread_id, "developed")
        print("✓ Updated plot thread status")
        
        # Test 18: Get entity evolution
        hero_evolution = db.get_entity_evolution("character", hero_id)
        print(f"✓ Retrieved hero evolution: {len(hero_evolution)} changes")
        
        # Test relationship dynamics
        relationship_dynamics = queries.get_relationship_dynamics_over_time(hero_id, mentor_id)
        print(f"✓ Relationship dynamics: {len(relationship_dynamics)} interaction points")
        
        # Test finding affected chapters
        affected_chapters = queries.find_chapters_affected_by_character_change(hero_id, "backstory")
        print(f"✓ Chapters affected by hero backstory change: {len(affected_chapters)}")
        
        print("\n✅ All database tests passed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if os.path.exists(test_db):
            os.remove(test_db)
            print("✓ Cleaned up test database")


if __name__ == "__main__":
    test_database_standalone()