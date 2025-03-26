#!/usr/bin/env python
"""
Run the StoryCraft agent to generate a complete story with progress updates.
Uses LangGraph's native edge system for improved reliability with complex stories.
"""

import os
import sys
import time
import argparse
import logging.config
from dotenv import load_dotenv
from storyteller_lib.storyteller import generate_story
from storyteller_lib import set_progress_callback, reset_progress_tracking
from storyteller_lib.config import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES

# Load environment variables from .env file
load_dotenv()

# Configure logging to suppress httpx messages
if os.path.exists('logging.conf'):
    logging.config.fileConfig('logging.conf')
else:
    # Fallback if config file not found - at least silence httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)

# Progress tracking variables
start_time = None
node_counts = {}
current_chapter = None
current_scene = None
verbose_mode = False
def write_chapter_to_file(chapter_num, chapter_data, output_file):
    """
    Write a completed chapter to the output file.
    
    Args:
        chapter_num: The chapter number
        chapter_data: The chapter data
        output_file: The output file path
    """
    try:
        # Validate input parameters
        if not chapter_data:
            print(f"Error: No chapter data provided for Chapter {chapter_num}")
            return
            
        if not isinstance(chapter_data, dict):
            print(f"Error: Chapter data for Chapter {chapter_num} is not a dictionary")
            return
            
        if "scenes" not in chapter_data:
            print(f"Error: No scenes found in Chapter {chapter_num}")
            return
            
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
                f.write(f"# Generated Story\n\n")
            
            # Write the chapter title (with a fallback if title is missing)
            chapter_title = chapter_data.get('title', f"Chapter {chapter_num}")
            f.write(f"\n## Chapter {chapter_num}: {chapter_title}\n\n")
            
            # Write each scene
            if not chapter_data.get("scenes"):
                f.write("*No scenes available for this chapter*\n\n")
            else:
                for scene_num in sorted(chapter_data["scenes"].keys(), key=int):
                    scene = chapter_data["scenes"][scene_num]
                    if "content" in scene and scene["content"]:
                        f.write(scene["content"])
                        f.write("\n\n")
                    else:
                        f.write(f"*Scene {scene_num} content not available*\n\n")
        
        print(f"Chapter {chapter_num} successfully written to {output_file}")
    except IOError as e:
        print(f"Error writing chapter {chapter_num} to {output_file}: {str(e)}")

def progress_callback(node_name, state):
    """
    Report progress during story generation.
    
    Args:
        node_name: The name of the node that just finished executing
        state: The current state of the story generation
    """
    global start_time, node_counts, current_chapter, current_scene, verbose_mode, output_file
    global start_time, node_counts, current_chapter, current_scene, verbose_mode
    
    # Initialize start time if not set
    if start_time is None:
        start_time = time.time()
    
    # Initialize the node count for this node if not already tracked
    if node_name not in node_counts:
        node_counts[node_name] = 0
    
    # Increment the count for this node
    node_counts[node_name] += 1
    
    # Get elapsed time
    elapsed = time.time() - start_time
    elapsed_str = f"{elapsed:.1f}s"
    # Create a detailed progress report based on the node that just finished
    progress_message = f"[{elapsed_str}] Completed: {node_name}"
    
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
        progress_message = f"[{elapsed_str}] Generated story outline following hero's journey structure"
        
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
            
            sys.stdout.write(f"[Story outline continues with {len(outline.split('\n\n')) - 3} more sections...]\n")
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
            
    elif node_name == "brainstorm_scene_elements":
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        scene_info = f"Ch:{current_chapter}/Sc:{current_scene}"
        progress_message = f"[{elapsed_str}] Brainstormed creative elements for Scene {current_scene} of Chapter {current_chapter} [{scene_info}]"
        
        # Always show scene elements
        if "creative_elements" in state:
            creative = state["creative_elements"]
            scene_elements_key = f"scene_elements_ch{current_chapter}_sc{current_scene}"
            scene_surprises_key = f"scene_surprises_ch{current_chapter}_sc{current_scene}"
            
            sys.stdout.write(f"\n------ UPCOMING SCENE {scene_info} ------\n")
            
            # Show chapter context
            if current_chapter in state.get("chapters", {}):
                chapter = state["chapters"][current_chapter]
                chapter_title = chapter.get("title", f"Chapter {current_chapter}")
                sys.stdout.write(f"Chapter: {chapter_title}\n")
            
            # Show scene elements in a condensed format
            if scene_elements_key in creative and "recommended_ideas" in creative[scene_elements_key]:
                # Extract just the key points
                ideas = creative[scene_elements_key]["recommended_ideas"]
                
                # Try to extract the title/headline
                title = ""
                if ":" in ideas:
                    title_parts = ideas.split(":", 1)
                    title = title_parts[0].strip()
                    
                # Show a condensed version
                sys.stdout.write(f"Scene focus: {title if title else 'Key scene elements'}\n")
                
                # Extract first paragraph or sentence for a brief preview
                content = ideas.split("\n\n")[0] if "\n\n" in ideas else ideas
                first_sentence = content.split(".")[0] + "." if "." in content else content
                if len(first_sentence) > 100:
                    first_sentence = first_sentence[:100] + "..."
                sys.stdout.write(f"Elements: {first_sentence}\n")
            
            # Show surprise elements if available
            if scene_surprises_key in creative and "recommended_ideas" in creative[scene_surprises_key]:
                surprises = creative[scene_surprises_key]["recommended_ideas"]
                # Extract just the first line or sentence
                first_line = surprises.split("\n")[0] if "\n" in surprises else surprises
                first_sentence = first_line.split(".")[0] + "." if "." in first_line else first_line
                if len(first_sentence) > 80:
                    first_sentence = first_sentence[:80] + "..."
                sys.stdout.write(f"Twist: {first_sentence}\n")
            
            sys.stdout.write("------------------------------\n\n")
            
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
        
        if verbose_mode:
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
        
        if verbose_mode and "revelations" in state and "continuity_issues" in state["revelations"]:
            continuity_issues = state["revelations"]["continuity_issues"]
            sys.stdout.write(f"\n------ CONTINUITY REVIEW [Chapter {current_chapter}] ------\n")
            for issue in continuity_issues:
                sys.stdout.write(f"After Chapter {issue.get('after_chapter', 'unknown')}:\n")
                issues_text = issue.get('issues', '')
                if len(issues_text) > 300:
                    issues_text = issues_text[:300] + "...\n[issues truncated for display]"
                sys.stdout.write(f"{issues_text}\n\n")
            sys.stdout.write("-----------------------------\n\n")
            
    elif node_name == "advance_to_next_scene_or_chapter":
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        scene_info = f"Ch:{current_chapter}/Sc:{current_scene}"
        progress_message = f"[{elapsed_str}] Advanced to Scene {current_scene} of Chapter {current_chapter} [{scene_info}]"
    elif node_name == "compile_final_story":
        chapter_count = len(state.get("chapters", {}))
        scene_count = sum(len(chapter.get("scenes", {})) for chapter in state.get("chapters", {}).values())
        progress_message = f"[{elapsed_str}] Story complete! Compiled final narrative with {chapter_count} chapters and {scene_count} scenes"
    
    # Print the progress message
    sys.stdout.write(f"{progress_message}\n")
    sys.stdout.flush()
    
    # Check if a chapter was just completed and needs to be written to the output file
    if node_name == "review_continuity" or node_name == "revise_scene_if_needed":
        try:
            if state.get("chapter_complete", False):
                # Get the chapter that was just completed
                completed_chapter = state.get("current_chapter", "")
                if completed_chapter and completed_chapter in state.get("chapters", {}):
                    # Check if this chapter has been written to the file already
                    chapter_written_key = f"chapter_{completed_chapter}_written"
                    if not state.get(chapter_written_key, False):
                        # Write the completed chapter to the output file
                        sys.stdout.write(f"\n[{elapsed_str}] Chapter {completed_chapter} completed! Writing to output file...\n")
                        write_chapter_to_file(completed_chapter, state["chapters"][completed_chapter], output_file)
                        # Mark the chapter as written in the state
                        state[chapter_written_key] = True
        except Exception as e:
            sys.stdout.write(f"\n[{elapsed_str}] Error writing chapter to file: {str(e)}\n")
            sys.stdout.flush()
    
    # Check for chapter/scene updates
    new_chapter = state.get("current_chapter")
    new_scene = state.get("current_scene")
    
    # If we're transitioning to a new chapter/scene, show more detailed information
    if new_chapter and new_scene and (current_chapter != new_chapter or current_scene != new_scene):
        current_chapter = new_chapter
        current_scene = new_scene
        
        # Report chapter and scene progress with more details
        if current_chapter and current_scene:
            chapters = state.get("chapters", {})
            if current_chapter in chapters:
                chapter = chapters[current_chapter]
                chapter_title = chapter.get("title", f"Chapter {current_chapter}")
                total_scenes = len(chapter.get("scenes", {}))
                
                # Show chapter transition info
                sys.stdout.write(f"\n[{elapsed_str}] Working on Chapter {current_chapter}: {chapter_title} - Scene {current_scene}/{total_scenes}\n")
                
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
                        if int(ch_num) < int(current_chapter):
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

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Generate a story using the refactored StoryCraft agent")
    parser.add_argument("--genre", type=str, default="fantasy",
                        help="Genre of the story (e.g., fantasy, sci-fi, mystery)")
    parser.add_argument("--tone", type=str, default="epic",
                        help="Tone of the story (e.g., epic, dark, humorous)")
    parser.add_argument("--author", type=str, default="",
                        help="Author whose style to emulate (e.g., Tolkien, Rowling, Martin)")
    parser.add_argument("--language", type=str, default=DEFAULT_LANGUAGE,
                        help=f"Target language for story generation (e.g., {', '.join(SUPPORTED_LANGUAGES.keys())})")
    parser.add_argument("--idea", type=str, default="",
                        help="Initial story idea to use as a starting point (e.g., 'A detective story set in a zoo')")
    parser.add_argument("--output", type=str, default="story.md",
                        help="Output file to save the generated story")
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
        
    # Make output file path available to the progress callback
    global output_file
    output_file = args.output
    
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
        
    # Set global verbose mode from command line argument
    global verbose_mode
    verbose_mode = args.verbose
    
    try:
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
        
        # Reset progress tracking variables
        global start_time, node_counts, current_chapter, current_scene
        start_time = time.time()
        node_counts = {}
        current_chapter = None
        current_scene = None
        
        # Set up the progress callback in our library
        reset_progress_tracking()
        set_progress_callback(progress_callback)
        
        story = None
        partial_story = None
        try:
            # Start the story generation
            # We don't need to pass progress_callback since we registered it globally
            story = generate_story(
                genre=args.genre,
                tone=args.tone,
                author=args.author,
                initial_idea=args.idea,
                language=args.language,
                model_provider=args.model_provider,
                model=args.model
            )
            
            # Show completion message
            elapsed = time.time() - start_time
            elapsed_str = f"{elapsed:.1f}s"
            print(f"[{elapsed_str}] Story generation complete!")
        except Exception as e:
            # Show error message with elapsed time
            elapsed = time.time() - start_time
            elapsed_str = f"{elapsed:.1f}s"
            print(f"[{elapsed_str}] Error during story generation: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Try to recover partial story from the last good state
            from storyteller_lib.storyteller import extract_partial_story
            try:
                print("Attempting to recover partial story...")
                partial_story = extract_partial_story(
                    args.genre,
                    args.tone,
                    args.author,
                    args.idea,
                    args.language,
                    args.model_provider,
                    args.model
                )
                if partial_story:
                    print("Partial story recovered successfully!")
                    story = partial_story
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
        
        # Calculate total elapsed time
        total_time = time.time() - start_time
        minutes, seconds = divmod(total_time, 60)
        hours, minutes = divmod(minutes, 60)
        
        # Print summary statistics
        print(f"\nStory Generation Summary:")
        print(f"- Total time: {int(hours)}h {int(minutes)}m {int(seconds)}s")
        
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
        
    except Exception as e:
        print(f"Error during story generation: {str(e)}")
        import traceback
        traceback.print_exc()
        print("Please check the error message above and fix the issue in the code.")

if __name__ == "__main__":
    main()