#!/usr/bin/env python
"""
Run the StoryCraft agent to generate a complete story with progress updates.
Uses LangGraph's native edge system for improved reliability with complex stories.
"""

# Standard library imports
import argparse
import logging.config
import os
import sys
import time
from typing import Any, Dict, Optional

# Third party imports
from dotenv import load_dotenv

# Local imports
from storyteller_lib import reset_progress_tracking, set_progress_callback
from storyteller_lib.config import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.constants import NodeNames
from storyteller_lib.progress_manager import ProgressManager, create_progress_manager
from storyteller_lib.story_info import save_story_info
from storyteller_lib.storyteller import generate_story_simplified
from storyteller_lib.book_statistics import display_progress_report

# Load environment variables from .env file
load_dotenv()

# Configure logging to suppress httpx messages
if os.path.exists('logging.conf'):
    logging.config.fileConfig('logging.conf')
else:
    # Fallback if config file not found - at least silence httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)

# Global progress manager instance
progress_manager: Optional[ProgressManager] = None

def write_scene_to_file(chapter_num: int, scene_num: int, output_file: str) -> None:
    """
    Write a single scene to the output file.
    
    Args:
        chapter_num: The chapter number
        scene_num: The scene number
        output_file: The output file path
    """
    try:
        # Get content from database
        from storyteller_lib.database_integration import get_db_manager
        db_manager = get_db_manager()
        
        if not db_manager or not db_manager._db:
            print(f"Error: Database manager not available for Scene {scene_num} of Chapter {chapter_num}")
            return
        
        # Get scene content from database
        content = db_manager.get_scene_content(chapter_num, scene_num)
        if not content:
            print(f"Error: No content found for Scene {scene_num} of Chapter {chapter_num}")
            return
            
        # Ensure the directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Check if the file exists and if we need to add headers
        file_exists = os.path.exists(output_file)
        needs_story_title = not file_exists or os.path.getsize(output_file) < 300  # Less than error message size
        
        # Check if this chapter header has been written
        chapter_header_written = False
        if file_exists and os.path.getsize(output_file) > 300:
            with open(output_file, 'r') as f:
                existing_content = f.read()
                chapter_header_written = f"## Chapter {chapter_num}:" in existing_content
        
        # Open the file in append mode
        with open(output_file, 'a' if file_exists else 'w') as f:
            # If this is a new file or very small (error message), add a title
            if needs_story_title:
                # Get story info from database
                with db_manager._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT title, genre, tone, global_story FROM story_config WHERE id = 1")
                    story_info = cursor.fetchone()
                    if story_info:
                        story_title = story_info['title']
                        # If title is still the placeholder, try to extract from global_story
                        if (not story_title or 
                            story_title == f"{story_info['tone'].title()} {story_info['genre'].title()} Story" or
                            "Story" in story_title and len(story_title) < 30):
                            print(f"[DEBUG] Title in DB is placeholder: '{story_title}', attempting to extract from outline")
                            if story_info['global_story']:
                                # Re-extract the title
                                from storyteller_lib.database_integration import StoryDatabaseManager
                                temp_manager = StoryDatabaseManager()
                                extracted_title = temp_manager._extract_title_from_outline(story_info['global_story'])
                                if extracted_title and extracted_title != "Untitled Story":
                                    story_title = extracted_title
                                    print(f"[DEBUG] Re-extracted title: '{story_title}'")
                                    # Update the database with the correct title
                                    cursor.execute("UPDATE story_config SET title = ? WHERE id = 1", (story_title,))
                                    conn.commit()
                        print(f"[DEBUG] Using story title: '{story_title}'")
                    else:
                        story_title = "Generated Story"
                        print(f"[DEBUG] No story_config found, using default title")
                
                # Clear any error message and write title
                f.seek(0)
                f.truncate()
                f.write(f"# {story_title}\n\n")
            
            # Write chapter header if this is the first scene of the chapter
            if not chapter_header_written and scene_num == 1:
                # Get chapter title from database
                with db_manager._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT title FROM chapters WHERE chapter_number = ?", (chapter_num,))
                    result = cursor.fetchone()
                    if result and result['title']:
                        chapter_title = result['title']
                        print(f"[DEBUG] Found chapter title in DB: '{chapter_title}'")
                    else:
                        chapter_title = f"Chapter {chapter_num}"
                        print(f"[DEBUG] No chapter title in DB, using default")
                f.write(f"\n## Chapter {chapter_num}: {chapter_title}\n\n")
            
            # Write scene title
            f.write(f"### Scene {scene_num}\n\n")
            
            # Write the scene content
            f.write(content)
            f.write("\n\n")
        
        print(f"Scene {scene_num} of Chapter {chapter_num} successfully written to {output_file}")
        
    except Exception as e:
        print(f"Error writing scene {scene_num} of chapter {chapter_num} to {output_file}: {str(e)}")
        import traceback
        traceback.print_exc()

def write_chapter_to_file(chapter_num: int, chapter_data: Dict[str, Any], output_file: str) -> None:
    """
    Write a completed chapter to the output file.
    
    Args:
        chapter_num: The chapter number
        chapter_data: The chapter data
        output_file: The output file path
    """
    try:
        # Convert chapter_num to int if it's a string
        if isinstance(chapter_num, str):
            chapter_num = int(chapter_num)
        
        # Get content from database since we're using thin state pattern
        from storyteller_lib.database_integration import get_db_manager
        db_manager = get_db_manager()
        
        if not db_manager or not db_manager._db:
            print(f"Error: Database manager not available for Chapter {chapter_num}")
            return
        
        # Get chapter title from database
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title FROM chapters WHERE chapter_number = ?", (chapter_num,))
            result = cursor.fetchone()
            chapter_title = result['title'] if result else f"Chapter {chapter_num}"
            
        # Ensure the directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Check if the file exists
        file_exists = os.path.exists(output_file)
        
        # Open the file in append mode if it exists, otherwise in write mode
        mode = 'a' if file_exists else 'w'
        
        with open(output_file, mode) as f:
            # If this is a new file, add a title
            if not file_exists:
                # Try to get the actual title from the database
                story_title = "Generated Story"  # Default
                try:
                    with db_manager._db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT title FROM story_config WHERE id = 1")
                        result = cursor.fetchone()
                        if result and result['title']:
                            story_title = result['title']
                except Exception:
                    pass  # Use default title if database query fails
                
                f.write(f"# {story_title}\n\n")
            
            # Write the chapter title
            f.write(f"\n## Chapter {chapter_num}: {chapter_title}\n\n")
            
            # Get all scenes for this chapter from database
            with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT s.scene_number, s.content 
                    FROM scenes s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE c.chapter_number = ?
                    ORDER BY s.scene_number
                """, (chapter_num,))
                
                scenes = cursor.fetchall()
                
            if not scenes:
                f.write("*No scenes available for this chapter*\n\n")
            else:
                for scene in scenes:
                    scene_num = scene['scene_number']
                    content = scene['content']
                    if content:
                        f.write(content)
                        f.write("\n\n")
                    else:
                        f.write(f"*Scene {scene_num} content not available*\n\n")
        
        print(f"Chapter {chapter_num} successfully written to {output_file}")
    except IOError as e:
        print(f"Error writing chapter {chapter_num} to {output_file}: {str(e)}")

def progress_callback(node_name: str, state: Dict[str, Any]) -> None:
    """
    Report progress during story generation.
    
    Args:
        node_name: The name of the node that just finished executing
        state: The current state of the story generation
    """
    if not progress_manager:
        return
        
    # Initialize tracking variables
    current_chapter = progress_manager.state.current_chapter
    current_scene = progress_manager.state.current_scene
        
    # Update node counts and state directly to avoid recursion
    progress_manager.state.node_counts[node_name] = progress_manager.state.node_counts.get(node_name, 0) + 1
    
    # Update chapter/scene tracking
    if "current_chapter" in state:
        progress_manager.state.current_chapter = state["current_chapter"]
    if "current_scene" in state:
        progress_manager.state.current_scene = state["current_scene"]
    
    # Get formatted progress message
    progress_message = progress_manager.get_progress_message(node_name)
    elapsed_str = progress_manager.state.get_elapsed_time()
    
    # Add detailed node-specific progress information
    if node_name == "initialize_state":
        initial_idea = state.get('initial_idea', '')
        idea_info = f" based on: '{initial_idea}'" if initial_idea else ""
        progress_message = f"[{elapsed_str}] Initialized story state - preparing to generate {state.get('tone', '')} {state.get('genre', '')} story{idea_info}"
        
        # Always show the initial idea and key elements
        if initial_idea:
            sys.stdout.write("\n------ INITIAL STORY IDEA ------\n")
            sys.stdout.write(f"{initial_idea}\n")
            
            # Show extracted elements if available
            if "initial_idea_elements" in state:
                elements = state["initial_idea_elements"]
                sys.stdout.write("\nKey elements extracted:\n")
                sys.stdout.write(f"- Setting: {elements.get('setting', 'Unknown')}\n")
                sys.stdout.write(f"- Characters: {', '.join(elements.get('characters', []))}\n")
                sys.stdout.write(f"- Plot: {elements.get('plot', 'Unknown')}\n")
                if elements.get('themes'):
                    sys.stdout.write(f"- Themes: {', '.join(elements.get('themes', []))}\n")
            sys.stdout.write("-------------------------------\n\n")
            
    elif node_name == "brainstorm_story_concepts":
        progress_message = f"[{elapsed_str}] Brainstormed creative story concepts - developing potential themes and ideas"
        
        # Always show a summary of the creative concepts
        if "creative_elements" in state:
            creative = state["creative_elements"]
            sys.stdout.write("\n------ CREATIVE CONCEPTS ------\n")
            if "story_concepts" in creative and "recommended_ideas" in creative["story_concepts"]:
                # Extract just the first paragraph for a quick preview
                concept = creative['story_concepts']['recommended_ideas']
                if concept:  # Check if concept is not None
                    concept_preview = concept.split('\n\n')[0] if '\n\n' in concept else concept
                    sys.stdout.write(f"STORY CONCEPT: \n{concept_preview}\n\n")
                else:
                    sys.stdout.write(f"STORY CONCEPT: \nNo concept available\n\n")
            else:
                sys.stdout.write(f"STORY CONCEPT: \nNo concept available\n\n")
                    
            if "world_building" in creative and "recommended_ideas" in creative["world_building"]:
                # Extract just the title and first sentence
                world = creative['world_building']['recommended_ideas']
                if world:  # Check if world is not None
                    world_preview = ': '.join(world.split(':')[:2]) if ':' in world else world.split('.')[0]
                    sys.stdout.write(f"WORLD BUILDING: \n{world_preview}\n\n")
                else:
                    sys.stdout.write(f"WORLD BUILDING: \nNo world building available\n\n")
            else:
                sys.stdout.write(f"WORLD BUILDING: \nNo world building available\n\n")
                    
            if "central_conflicts" in creative and "recommended_ideas" in creative["central_conflicts"]:
                # Extract just the title and first sentence
                conflict = creative['central_conflicts']['recommended_ideas']
                if conflict:  # Check if conflict is not None
                    conflict_preview = ': '.join(conflict.split(':')[:2]) if ':' in conflict else conflict.split('.')[0]
                    sys.stdout.write(f"CENTRAL CONFLICT: \n{conflict_preview}\n\n")
                else:
                    sys.stdout.write(f"CENTRAL CONFLICT: \nNo central conflict available\n\n")
            else:
                sys.stdout.write(f"CENTRAL CONFLICT: \nNo central conflict available\n\n")
            sys.stdout.write("------------------------------\n\n")
            
    elif node_name == "generate_story_outline":
        # Get narrative structure from state
        narrative_structure = state.get("narrative_structure", "hero_journey")
        structure_name = narrative_structure.replace('_', ' ').title()
        progress_message = f"[{elapsed_str}] Generated story outline following {structure_name} structure"
        
        # Always show a preview of the story outline
        if "global_story" in state:
            outline = state["global_story"]
            
            # Extract title and first few sections
            title = outline.split('\n')[0] if outline else "Untitled Story"
            sections = outline.split('\n\n')[:3]  # Get first 3 sections
            
            sys.stdout.write("\n------ STORY OUTLINE PREVIEW ------\n")
            sys.stdout.write(f"TITLE: {title}\n\n")
            
            # Show the first few sections
            for i, section in enumerate(sections):
                if i > 0:  # Skip title which we already showed
                    preview = section[:200] + "..." if len(section) > 200 else section
                    sys.stdout.write(f"{preview}\n\n")
            
            # Count the number of sections by splitting on double newlines
            section_count = len(outline.split('\n\n')) - 3
            sys.stdout.write(f"[Story outline continues with {section_count} more sections...]\n")
            sys.stdout.write("----------------------------------\n\n")
            
    elif node_name == "generate_characters":
        progress_message = f"[{elapsed_str}] Created {len(state.get('characters', {}))} detailed character profiles with interconnected backgrounds"
        
        # Always show a summary of the main characters
        if "characters" in state:
            characters = state["characters"]
            sys.stdout.write("\n------ MAIN CHARACTERS ------\n")
            
            # Limit to showing just 3-4 main characters
            main_chars = []
            for char_name, char_data in characters.items():
                role = char_data.get('role', '').lower()
                # Prioritize protagonist, antagonist, and key supporting characters
                if 'protagonist' in role or 'main' in role or 'detective' in role:
                    main_chars.insert(0, (char_name, char_data))  # Add protagonist first
                elif 'antagonist' in role or 'villain' in role:
                    main_chars.append((char_name, char_data))  # Add antagonist
                elif len(main_chars) < 4:  # Add other important characters
                    main_chars.append((char_name, char_data))
            
            # Ensure we don't show too many characters
            main_chars = main_chars[:4]
            
            for char_name, char_data in main_chars:
                sys.stdout.write(f"CHARACTER: {char_data.get('name', char_name)}\n")
                sys.stdout.write(f"Role: {char_data.get('role', 'Unknown')}\n")
                
                # Show one key trait, one strength, one flaw
                if 'personality' in char_data:
                    personality = char_data['personality']
                    if 'traits' in personality and personality['traits']:
                        sys.stdout.write(f"Key trait: {personality['traits'][0]}\n")
                    if 'strengths' in personality and personality['strengths']:
                        sys.stdout.write(f"Strength: {personality['strengths'][0]}\n")
                    if 'flaws' in personality and personality['flaws']:
                        sys.stdout.write(f"Flaw: {personality['flaws'][0]}\n")
                
                # Show very brief backstory
                backstory = char_data.get('backstory', '')
                if backstory:
                    first_sentence = backstory.split('.')[0] + '.'
                    sys.stdout.write(f"Backstory: {first_sentence}\n")
                
                sys.stdout.write("\n")
            
            sys.stdout.write(f"[Plus {len(characters) - len(main_chars)} additional characters...]\n")
            sys.stdout.write("----------------------------\n\n")
            sys.stdout.write("-------------------------------\n\n")
            
    elif node_name == "plan_chapters":
        progress_message = f"[{elapsed_str}] Planned {len(state.get('chapters', {}))} chapters for the story"
        
        # Always show the chapter plan
        if "chapters" in state:
            chapters = state["chapters"]
            sys.stdout.write("\n------ STORY STRUCTURE ------\n")
            
            # Show total number of chapters and estimated word count
            total_scenes = sum(len(chapter.get('scenes', {})) for chapter in chapters.values())
            sys.stdout.write(f"Story structure: {len(chapters)} chapters with approximately {total_scenes} scenes\n")
            sys.stdout.write(f"Estimated final length: {total_scenes * 1500}-{total_scenes * 2500} words\n\n")
            
            # Show chapter breakdown
            for ch_num in sorted(chapters.keys(), key=lambda x: int(x) if x.isdigit() else float('inf')):
                chapter = chapters[ch_num]
                sys.stdout.write(f"CHAPTER {ch_num}: {chapter.get('title', 'Untitled')}\n")
                
                # Show key plot points or themes for this chapter
                if 'themes' in chapter:
                    themes = chapter['themes']
                    if isinstance(themes, list) and themes:
                        sys.stdout.write(f"Theme: {themes[0]}\n")
                    elif isinstance(themes, str):
                        sys.stdout.write(f"Theme: {themes}\n")
                
                # Show truncated outline - just the first sentence
                outline = chapter.get('outline', '')
                first_sentence = outline.split('.')[0] + '.' if outline and '.' in outline else outline
                if len(first_sentence) > 100:
                    first_sentence = first_sentence[:100] + "..."
                sys.stdout.write(f"Focus: {first_sentence}\n")
                
                # Show scene count and key scenes
                scenes = chapter.get('scenes', {})
                sys.stdout.write(f"Scenes: {len(scenes)}\n")
                
                # If we have scene summaries, show the first one as an example
                if scenes and '1' in scenes and 'summary' in scenes['1']:
                    summary = scenes['1']['summary']
                    if len(summary) > 80:
                        summary = summary[:80] + "..."
                    sys.stdout.write(f"First scene: {summary}\n")
                
                sys.stdout.write("\n")
            sys.stdout.write("--------------------------\n\n")
            
    elif node_name == "write_scene":
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        chapters = state.get("chapters", {})
        scene_info = f"Ch:{current_chapter}/Sc:{current_scene}"
        if current_chapter in chapters:
            chapter = chapters[current_chapter]
            chapter_title = chapter.get("title", f"Chapter {current_chapter}")
            progress_message = f"[{elapsed_str}] Wrote Scene {current_scene} of Chapter {current_chapter}: {chapter_title} [{scene_info}]"
            
            # Always show a preview of the scene
            if current_chapter in chapters and current_scene in chapters[current_chapter]["scenes"]:
                scene_content = chapters[current_chapter]["scenes"][current_scene].get("content", "")
                if scene_content:
                    # Get scene summary
                    scene_summary = ""
                    if "summary" in chapters[current_chapter]["scenes"][current_scene]:
                        scene_summary = chapters[current_chapter]["scenes"][current_scene]["summary"]
                    
                    # Extract key elements from the scene
                    paragraphs = scene_content.split('\n\n')
                    first_paragraph = paragraphs[0] if paragraphs else ""
                    
                    # Find a key piece of dialogue if present
                    dialogue = ""
                    for para in paragraphs:
                        if '"' in para or "'" in para:
                            dialogue_start = para.find('"') if '"' in para else para.find("'")
                            if dialogue_start >= 0:
                                dialogue_end = para.find('"', dialogue_start+1) if '"' in para else para.find("'", dialogue_start+1)
                                if dialogue_end > dialogue_start:
                                    dialogue = para[dialogue_start:dialogue_end+1]
                                    break
                    
                    # Show a meaningful preview
                    sys.stdout.write(f"\n------ SCENE {scene_info}: {chapter_title} ------\n")
                    
                    # Show summary if available
                    if scene_summary:
                        sys.stdout.write(f"SUMMARY: {scene_summary}\n\n")
                    
                    # Show first paragraph (truncated if needed)
                    first_para_preview = first_paragraph[:200] + "..." if len(first_paragraph) > 200 else first_paragraph
                    sys.stdout.write(f"OPENING: {first_para_preview}\n\n")
                    
                    # Show a key piece of dialogue if found
                    if dialogue:
                        sys.stdout.write(f"KEY DIALOGUE: {dialogue}\n\n")
                    
                    # Show scene length stats
                    sys.stdout.write(f"Scene length: {len(scene_content)} characters, {len(paragraphs)} paragraphs\n")
                    sys.stdout.write("---------------------------\n\n")
                    
    elif node_name == "reflect_on_scene":
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        
        # Always print the scene info even when empty to help with debugging
        scene_info = f"Ch:{current_chapter}/Sc:{current_scene}"
        progress_message = f"[{elapsed_str}] Analyzed Scene {current_scene} of Chapter {current_chapter} for quality and consistency [{scene_info}]"
        
        # Always show reflection notes if available
        if current_chapter in state.get("chapters", {}) and current_scene in state["chapters"][current_chapter]["scenes"]:
            reflection_notes = state["chapters"][current_chapter]["scenes"][current_scene].get("reflection_notes", [])
            if reflection_notes:
                sys.stdout.write(f"\n------ SCENE ANALYSIS [{scene_info}] ------\n")
                
                # Show a summary of the analysis
                sys.stdout.write(f"Analysis of scene {current_scene} in chapter {current_chapter}:\n")
                
                # Show only the most important notes (max 3)
                important_notes = reflection_notes[:min(3, len(reflection_notes))]
                for i, note in enumerate(important_notes):
                    # Extract just the first sentence for brevity
                    first_sentence = note.split('.')[0] + '.' if '.' in note else note
                    if len(first_sentence) > 100:
                        first_sentence = first_sentence[:100] + "..."
                    sys.stdout.write(f"{i+1}. {first_sentence}\n")
                
                # Indicate if there are more notes
                if len(reflection_notes) > 3:
                    sys.stdout.write(f"[Plus {len(reflection_notes) - 3} additional notes...]\n")
                
                sys.stdout.write("-----------------------------\n\n")
                
    elif node_name == "revise_scene_if_needed":
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        
        # Always print the scene info even when empty to help with debugging
        scene_info = f"Ch:{current_chapter}/Sc:{current_scene}"
        progress_message = f"[{elapsed_str}] Reviewed Scene {current_scene} of Chapter {current_chapter} for potential revisions [{scene_info}]"
        
        if progress_manager and progress_manager.state.verbose_mode:
            # Determine if revisions were made by checking presence of reflection notes
            chapters = state.get("chapters", {})
            scene_revised = False
            
            if current_chapter in chapters and current_scene in chapters[current_chapter]["scenes"]:
                # Check for revision marker in reflection notes
                scene = chapters[current_chapter]["scenes"][current_scene]
                if scene.get("reflection_notes") and len(scene["reflection_notes"]) == 1 and scene["reflection_notes"][0] == "Scene has been revised":
                    scene_revised = True
                    
            if scene_revised:
                sys.stdout.write(f"\n------ SCENE REVISED [{scene_info}] ------\n")
                sys.stdout.write("The scene was revised based on reflection notes and continuity checks.\n")
                sys.stdout.write("--------------------------\n\n")
            else:
                sys.stdout.write(f"\n------ NO REVISION NEEDED [{scene_info}] ------\n")
                sys.stdout.write("The scene was reviewed and found to be consistent and well-crafted.\n")
                sys.stdout.write("-------------------------------\n\n")
                
    elif node_name == "update_character_profiles":
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        scene_info = f"Ch:{current_chapter}/Sc:{current_scene}"
        progress_message = f"[{elapsed_str}] Updated character profiles after Scene {current_scene} of Chapter {current_chapter} [{scene_info}]"
    elif node_name == "review_continuity":
        current_chapter = state.get("current_chapter", "")
        progress_message = f"[{elapsed_str}] Performed continuity review after Chapter {current_chapter}"
        
        if progress_manager and progress_manager.state.verbose_mode and "revelations" in state and "continuity_issues" in state["revelations"]:
            continuity_issues = state["revelations"]["continuity_issues"]
            sys.stdout.write(f"\n------ CONTINUITY REVIEW [Chapter {current_chapter}] ------\n")
            for issue in continuity_issues:
                sys.stdout.write(f"After Chapter {issue.get('after_chapter', 'unknown')}:\n")
                issues_text = issue.get('issues', '')
                if len(issues_text) > 300:
                    issues_text = issues_text[:300] + "...\n[issues truncated for display]"
                sys.stdout.write(f"{issues_text}\n\n")
            sys.stdout.write("-----------------------------\n\n")
        
        # Progress report will be displayed at story completion
        # No need to display it after every chapter to avoid duplication
            
    elif node_name == "advance_to_next_scene_or_chapter":
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        scene_info = f"Ch:{current_chapter}/Sc:{current_scene}"
        progress_message = f"[{elapsed_str}] Advanced to Scene {current_scene} of Chapter {current_chapter} [{scene_info}]"
    elif node_name == "compile_final_story":
        chapter_count = len(state.get("chapters", {}))
        scene_count = sum(len(chapter.get("scenes", {})) for chapter in state.get("chapters", {}).values())
        progress_message = f"[{elapsed_str}] Story complete! Compiled final narrative with {chapter_count} chapters and {scene_count} scenes"
        
        # Display final progress report
        try:
            from storyteller_lib.database_integration import get_db_manager
            db_manager = get_db_manager()
            display_progress_report(db_manager)
        except Exception as e:
            print(f"[Warning] Could not display final progress report: {e}")
    
    # Print the progress message
    sys.stdout.write(f"{progress_message}\n")
    sys.stdout.flush()
    
    # Write scene to file only after revision check is complete
    # This ensures we write the final version of the scene, not the initial draft
    if node_name == "revise_scene_if_needed":
        try:
            current_chapter = state.get("current_chapter", "")
            current_scene = state.get("current_scene", "")
            if current_chapter and current_scene and progress_manager and progress_manager.state.output_file:
                # Write the scene to the output file (either original or revised version)
                sys.stdout.write(f"\n[{elapsed_str}] Writing scene {current_scene} of chapter {current_chapter} to output file...\n")
                write_scene_to_file(int(current_chapter), int(current_scene), progress_manager.state.output_file)
                sys.stdout.flush()
        except Exception as e:
            sys.stdout.write(f"\n[{elapsed_str}] Error writing scene to file: {str(e)}\n")
            sys.stdout.flush()
    
    # Check for chapter/scene updates
    new_chapter = state.get("current_chapter")
    new_scene = state.get("current_scene")
    
    # If we're transitioning to a new chapter/scene, show more detailed information
    if new_chapter and new_scene and (current_chapter != new_chapter or current_scene != new_scene):
        # Update the progress manager's state
        progress_manager.state.current_chapter = new_chapter
        progress_manager.state.current_scene = new_scene
        
        # Report chapter and scene progress with more details
        if new_chapter and new_scene:
            chapters = state.get("chapters", {})
            if new_chapter in chapters:
                chapter = chapters[new_chapter]
                chapter_title = chapter.get("title", f"Chapter {new_chapter}")
                total_scenes = len(chapter.get("scenes", {}))
                
                # Show chapter transition info
                sys.stdout.write(f"\n[{elapsed_str}] Working on Chapter {new_chapter}: {chapter_title} - Scene {new_scene}/{total_scenes}\n")
                
                # Get current completion statistics
                completed_chapters = 0
                completed_scenes = 0
                total_chapters = len(chapters)
                total_planned_scenes = sum(len(chapter.get("scenes", {})) for chapter in chapters.values())
                
                # Count completed chapters and scenes
                for ch_num, ch_data in chapters.items():
                    scenes_completed = True
                    for sc_num, sc_data in ch_data.get("scenes", {}).items():
                        # A scene is only complete if it has both content and reflection notes
                        if sc_data.get("content") and sc_data.get("reflection_notes"):
                            completed_scenes += 1
                        else:
                            scenes_completed = False
                    if scenes_completed:
                        completed_chapters += 1
                        
                        # Check if this is a newly completed chapter
                        # If the current chapter is different from the completed chapter, it means we've moved on
                        # from a completed chapter, so we should write it to the output file
                        # Only check if current_chapter is actually set (not empty string)
                        if current_chapter and current_chapter.strip() and int(ch_num) < int(current_chapter):
                            # Check if this chapter has been written to the file already
                            chapter_written_key = f"chapter_{ch_num}_written"
                            if not state.get(chapter_written_key, False):
                                # Write the completed chapter to the output file
                                sys.stdout.write(f"\n[{elapsed_str}] Chapter {ch_num} completed! Writing to output file...\n")
                                write_chapter_to_file(ch_num, ch_data, output_file)
                                # Mark the chapter as written in the state
                                state[chapter_written_key] = True
                
                # Show overall progress
                progress_pct = (completed_scenes / total_planned_scenes * 100) if total_planned_scenes > 0 else 0
                sys.stdout.write(f"[{elapsed_str}] Overall progress: {progress_pct:.1f}% - {completed_chapters}/{total_chapters} chapters, {completed_scenes}/{total_planned_scenes} scenes\n")
                sys.stdout.flush()

def get_story_title_from_db() -> Optional[str]:
    """Get the story title from the database."""
    try:
        from storyteller_lib.database_integration import get_db_manager
        db_manager = get_db_manager()
        
        if db_manager and db_manager._db:
            with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT title FROM story_config WHERE id = 1")
                result = cursor.fetchone()
                if result and result['title']:
                    return result['title']
    except Exception:
        pass
    return None


def sanitize_filename(title: str) -> str:
    """Convert a story title to a valid filename."""
    import re
    # Replace spaces and invalid filename characters with underscores
    # Keep Unicode letters, numbers, dashes, and common international characters
    filename = re.sub(r'[^\w\-äöüÄÖÜßéèêàâçñáíóúÁÍÓÚ]+', '_', title, flags=re.UNICODE)
    # Remove multiple consecutive underscores
    filename = re.sub(r'_+', '_', filename)
    # Remove leading/trailing underscores
    filename = filename.strip('_')
    # Ensure we have a valid filename
    if not filename:
        filename = "untitled_story"
    return filename


def main() -> None:
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Generate a story using the refactored StoryCraft agent")
    parser.add_argument("--genre", type=str, default="fantasy",
                        help="Genre of the story (e.g., fantasy, sci-fi, mystery)")
    parser.add_argument("--tone", type=str, default="epic",
                        help="Tone of the story (e.g., epic, dark, humorous)")
    parser.add_argument("--author", type=str, default="",
                        help="Author whose style to emulate (e.g., Tolkien, Rowling, Martin)")
    parser.add_argument("--use-v1", action="store_true",
                        help="Use legacy v1 workflow (deprecated, for backward compatibility only)")
    parser.add_argument("--language", type=str, default=DEFAULT_LANGUAGE,
                        help=f"Target language for story generation (e.g., {', '.join(SUPPORTED_LANGUAGES.keys())})")
    parser.add_argument("--idea", type=str, default="",
                        help="Initial story idea to use as a starting point (e.g., 'A detective story set in a zoo')")
    parser.add_argument("--output", type=str, default="story.md",
                        help="Output file to save the generated story")
    parser.add_argument("--info-file", action="store_true",
                        help="Generate a YAML info file with story metadata and worldbuilding elements")
    parser.add_argument("--verbose", action="store_true",
                        help="Display detailed information about the story elements as they're generated")
    parser.add_argument("--cache", type=str, choices=["memory", "sqlite", "none"], default="sqlite",
                        help="LLM cache type to use (default: sqlite)")
    parser.add_argument("--cache-path", type=str,
                        help="Path to the cache file (for sqlite cache)")
    parser.add_argument("--recursion-limit", type=int, default=200,
                        help="LangGraph recursion limit (default: 200)")
    # Add model provider options
    from storyteller_lib.config import MODEL_PROVIDER_OPTIONS, DEFAULT_MODEL_PROVIDER, MODEL_CONFIGS
    parser.add_argument("--model-provider", type=str, choices=MODEL_PROVIDER_OPTIONS, default=DEFAULT_MODEL_PROVIDER,
                        help=f"LLM provider to use (default: {DEFAULT_MODEL_PROVIDER})")
    parser.add_argument("--model", type=str,
                        help="Specific model to use (defaults to provider's default model)")
    # Add narrative structure options
    parser.add_argument("--structure", type=str, default="auto",
                        choices=["auto", "hero_journey", "three_act", "kishotenketsu", "in_medias_res", "circular", "nonlinear_mosaic"],
                        help="Narrative structure to use (default: auto - let AI choose based on genre/tone)")
    parser.add_argument("--pages", type=int,
                        help="Target number of pages for the story (e.g., 200 for a short novel, 400 for standard)")
    # Add database options
    parser.add_argument("--database-path", type=str,
                        help="Path to the story database file (default: ~/.storyteller/story_database.db)")
    # Story continuation is not supported in single-story mode
    parser.add_argument("--progress-log", type=str,
                        help="Path to save progress log file (default: automatically generated in ~/.storyteller/logs/)")
    parser.add_argument("--audio-book", action="store_true",
                        help="Generate SSML-formatted audiobook version of the story (during or after generation)")
    args = parser.parse_args()
    
    # Import config to check API keys
    from storyteller_lib.config import MODEL_CONFIGS
    
    # Check if API key is set for the selected provider
    provider = args.model_provider
    api_key_env = MODEL_CONFIGS[provider]["env_key"]
    if not os.environ.get(api_key_env):
        print(f"Error: {api_key_env} environment variable is not set for the {provider} provider.")
        print(f"Please create a .env file with {api_key_env}=your_api_key")
        return
        
    # Create progress manager
    global progress_manager
    progress_manager = create_progress_manager(verbose=args.verbose, output_file=args.output)
    progress_manager.set_write_chapter_callback(write_chapter_to_file)
    
    # Set up caching based on command line arguments
    from storyteller_lib.config import setup_cache, CACHE_LOCATION
    if args.cache_path:
        # Setting environment variable before importing other modules
        os.environ["CACHE_LOCATION"] = args.cache_path
        print(f"Using cache at: {args.cache_path}")
    else:
        print(f"Using default cache location: {CACHE_LOCATION}")
    
    # Setup the cache with the specified type
    cache = setup_cache(args.cache)
    print(f"LLM caching: {args.cache}")
    
    # Setup database
    if args.database_path:
        os.environ["STORY_DATABASE_PATH"] = args.database_path
    from storyteller_lib.config import DATABASE_PATH
    print(f"Database persistence: {DATABASE_PATH}")
    
    # Handle SSML conversion for existing story (if audio-book flag is set without generating new story)
    if args.audio_book and not any([args.genre, args.tone, args.idea]):
        # User wants to convert existing story to audiobook
        try:
            print("Converting existing story to SSML format for audiobook...")
            from storyteller_lib.ssml_converter import SSMLConverter
            from storyteller_lib.config import DATABASE_PATH
            
            # Check if database exists
            if not os.path.exists(DATABASE_PATH):
                print(f"Error: No story database found at {DATABASE_PATH}")
                print("Please generate a story first before converting to audiobook.")
                return
                
            # Create SSML converter
            ssml_converter = SSMLConverter(
                model_provider=args.model_provider,
                model=args.model,
                language=args.language
            )
            
            # Get story title for output filename
            story_title = get_story_title_from_db()
            if story_title:
                output_filename = f"{sanitize_filename(story_title)}_audiobook.ssml"
            else:
                output_filename = "story_audiobook.ssml"
            
            # Convert to SSML
            ssml_converter.convert_book_to_ssml(DATABASE_PATH, output_filename)
            
            print(f"\nSSML conversion complete!")
            print(f"SSML file saved to: {output_filename}")
            print("\nTo generate audio files, run:")
            print(f"  nix develop -c python generate_audiobook.py")
            return
            
        except Exception as e:
            print(f"Error converting to audiobook: {str(e)}")
            import traceback
            traceback.print_exc()
            return
    
    try:
        # Single story mode - always starts fresh
        
        # Generate the story with visual progress display
        author_str = f" in the style of {args.author}" if args.author else ""
        language_str = f" in {SUPPORTED_LANGUAGES.get(args.language.lower(), args.language)}" if args.language.lower() != DEFAULT_LANGUAGE else ""
        
        # Get model information
        from storyteller_lib.config import MODEL_CONFIGS
        provider_config = MODEL_CONFIGS[args.model_provider]
        model_name = args.model or provider_config["default_model"]
        
        print(f"Generating a {args.tone} {args.genre} story{author_str}{language_str}...")
        print(f"Using {args.model_provider.upper()} model: {model_name}")
        print(f"This will take some time. Progress updates will be displayed below:")
        
        # Reset progress tracking
        progress_manager.reset()
        # Remove duplicate callback registration - we only need one
        # progress_manager.set_progress_callback(progress_callback)
        
        # Set up the progress callback in our library
        reset_progress_tracking()
        set_progress_callback(progress_callback)
        
        story = None
        partial_story = None
        try:
            # Start the story generation
            # We don't need to pass progress_callback since we registered it globally
            if args.use_v1:
                # Legacy v1 workflow - deprecated
                from storyteller_lib.storyteller import generate_story
                story, state = generate_story(
                    genre=args.genre,
                    tone=args.tone,
                    author=args.author,
                    initial_idea=args.idea,
                    language=args.language,
                    model_provider=args.model_provider,
                    model=args.model,
                    return_state=True,  # Return both story text and state
                    progress_log_path=args.progress_log
                )
            else:
                # Default v2 workflow
                story, state = generate_story_simplified(
                    genre=args.genre,
                    tone=args.tone,
                    author=args.author,
                    initial_idea=args.idea,
                    language=args.language,
                    progress_log_path=args.progress_log,
                    narrative_structure=args.structure,
                    target_pages=args.pages,
                    recursion_limit=args.recursion_limit
                )
            
            # Show completion message
            elapsed_str = progress_manager.state.get_elapsed_time()
            print(f"[{elapsed_str}] Story generation complete!")
            
            # If using default output filename, try to use the story title
            if args.output == "story.md":
                story_title = get_story_title_from_db()
                if story_title:
                    sanitized_title = sanitize_filename(story_title)
                    args.output = f"{sanitized_title}.md"
                    print(f"Using story title for filename: {args.output}")
        except Exception as e:
            # Show error message with elapsed time
            elapsed_str = progress_manager.state.get_elapsed_time()
            print(f"[{elapsed_str}] Error during story generation: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Try to recover partial story from database
            try:
                print("Attempting to recover partial story...")
                from storyteller_lib.database_integration import get_db_manager
                db_manager = get_db_manager()
                if db_manager:
                    partial_story = db_manager.compile_story()
                    if partial_story:
                        print("Partial story recovered successfully!")
                        story = partial_story
                        
                        # Generate info file if requested
                        if args.info_file:
                            try:
                                # Create a minimal state for info file
                                state = {"chapters": {}, "characters": {}, "world_elements": {}}
                                info_file = save_story_info(state, args.output)
                                print(f"Partial story information saved to {info_file}")
                            except Exception as info_err:
                                print(f"Error saving partial story information: {str(info_err)}")
            except Exception as recovery_err:
                print(f"Could not recover partial story: {str(recovery_err)}")
        
        # Ensure we have a story to save
        if story is None:
            print("No story was generated. Please check the error messages above.")
            # Create a minimal story that explains the error
            title = f"Incomplete {args.tone.capitalize()} {args.genre.capitalize()} Story"
            story = f"# {title}\n\n"
            story += "## Error During Generation\n\n"
            story += "This story could not be fully generated due to an error in the LangGraph workflow.\n\n"
            story += "Please check the console output for error details and try again.\n\n"
            print("Created minimal error-explaining story file instead.")
            
        # Ensure the output has proper markdown formatting
        if not story.startswith("# "):
            # Add a title if not already present
            story = f"# Generated {args.tone.capitalize()} {args.genre.capitalize()} Story\n\n{story}"
        
        # Make sure chapters are properly formatted with markdown headers
        import re
        # Find chapter headings that aren't already markdown headers
        story = re.sub(r'(?<!\n\n)Chapter (\d+): ([^\n]+)(?!\n#)', r'\n\n## Chapter \1: \2', story)
        
        # Fix scene transitions if they exist but aren't formatted
        story = re.sub(r'(?<!\n\n)Scene (\d+)(?!\n#)', r'\n\n### Scene \1', story)
        
        # Save to file with robust error handling
        try:
            # Ensure the directory exists
            output_dir = os.path.dirname(args.output)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            # Write the file with error handling
            with open(args.output, "w") as f:
                f.write(story)
            print(f"Story successfully saved to {args.output}")
            
            # Database persistence is automatic for the single story
            
            # Generate info file if requested
            if args.info_file and 'state' in locals():
                try:
                    info_file = save_story_info(state, args.output)
                    print(f"Story information saved to {info_file}")
                except Exception as info_err:
                    print(f"Error saving story information: {str(info_err)}")
        except IOError as e:
            print(f"Error saving story to {args.output}: {str(e)}")
            # Try to save to a fallback location
            fallback_path = "story_fallback.md"
            try:
                with open(fallback_path, "w") as f:
                    f.write(story)
                print(f"Story saved to fallback location: {fallback_path}")
            except IOError as fallback_err:
                print(f"Critical error: Could not save story to fallback location: {str(fallback_err)}")
        
        # Calculate total elapsed time using progress manager
        elapsed_str = progress_manager.state.get_elapsed_time()
        
        # Print summary statistics
        print(f"\nStory Generation Summary:")
        print(f"- Total time: {elapsed_str}")
        
        # Count chapters and scenes
        try:
            if "chapters" in story:
                chapter_count = 0
                scene_count = 0
                
                # Roughly count chapters and scenes from the markdown
                chapter_lines = [line for line in story.split('\n') if line.startswith('## Chapter')]
                scene_lines = [line for line in story.split('\n') if line.startswith('### Scene')]
                
                chapter_count = len(chapter_lines)
                scene_count = len(scene_lines)
                
                if chapter_count > 0:
                    print(f"- Chapters: {chapter_count}")
                if scene_count > 0:
                    print(f"- Scenes: {scene_count}")
        except:
            pass
        
        # Word count statistics
        word_count = len(story.split())
        print(f"- Word count: {word_count}")
        
        print(f"\nStory successfully saved to {args.output} in markdown format")
        
        # Generate audiobook SSML if requested during generation
        if args.audio_book:
            try:
                print("\nGenerating SSML for audiobook...")
                from storyteller_lib.ssml_converter import SSMLConverter
                
                # Create SSML converter with the appropriate configuration
                ssml_converter = SSMLConverter(
                    model_provider=args.model_provider,
                    model=args.model,
                    language=args.language
                )
                
                # Generate output filename for SSML
                base_name = os.path.splitext(args.output)[0]
                ssml_output = f"{base_name}_audiobook.ssml"
                
                # Convert the book to SSML
                ssml_converter.convert_book_to_ssml(DATABASE_PATH, ssml_output)
                
                print(f"SSML audiobook successfully saved to {ssml_output}")
                print("\nTo generate audio files, run:")
                print(f"  nix develop -c python generate_audiobook.py")
                
            except Exception as ssml_err:
                print(f"Error generating audiobook SSML: {str(ssml_err)}")
                import traceback
                traceback.print_exc()
        
    except Exception as e:
        print(f"Error during story generation: {str(e)}")
        import traceback
        traceback.print_exc()
        print("Please check the error message above and fix the issue in the code.")

if __name__ == "__main__":
    main()