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

def progress_callback(node_name, state):
    """
    Report progress during story generation.
    
    Args:
        node_name: The name of the node that just finished executing
        state: The current state of the story generation
    """
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
        progress_message = f"[{elapsed_str}] Initialized story state - preparing to generate {state.get('tone', '')} {state.get('genre', '')} story"
    elif node_name == "brainstorm_story_concepts":
        progress_message = f"[{elapsed_str}] Brainstormed creative story concepts - developing potential themes and ideas"
        
        if verbose_mode and "creative_elements" in state:
            creative = state["creative_elements"]
            sys.stdout.write("\n------ CREATIVE CONCEPTS ------\n")
            if "story_concepts" in creative and "recommended_ideas" in creative["story_concepts"]:
                sys.stdout.write(f"STORY CONCEPT: \n{creative['story_concepts']['recommended_ideas']}\n\n")
            if "world_building" in creative and "recommended_ideas" in creative["world_building"]:
                sys.stdout.write(f"WORLD BUILDING: \n{creative['world_building']['recommended_ideas']}\n\n")
            if "central_conflicts" in creative and "recommended_ideas" in creative["central_conflicts"]:
                sys.stdout.write(f"CENTRAL CONFLICT: \n{creative['central_conflicts']['recommended_ideas']}\n\n")
            sys.stdout.write("------------------------------\n\n")
            
    elif node_name == "generate_story_outline":
        progress_message = f"[{elapsed_str}] Generated story outline following hero's journey structure"
        
        if verbose_mode and "global_story" in state:
            outline = state["global_story"]
            # Truncate if very long
            if len(outline) > 1000:
                outline_preview = outline[:1000] + "...\n[story outline truncated for display]"
            else:
                outline_preview = outline
                
            sys.stdout.write("\n------ STORY OUTLINE ------\n")
            sys.stdout.write(f"{outline_preview}\n")
            sys.stdout.write("--------------------------\n\n")
            
    elif node_name == "generate_characters":
        progress_message = f"[{elapsed_str}] Created {len(state.get('characters', {}))} detailed character profiles with interconnected backgrounds"
        
        if verbose_mode and "characters" in state:
            characters = state["characters"]
            sys.stdout.write("\n------ CHARACTER PROFILES ------\n")
            for char_name, char_data in characters.items():
                sys.stdout.write(f"CHARACTER: {char_data.get('name', char_name)}\n")
                sys.stdout.write(f"Role: {char_data.get('role', 'Unknown')}\n")
                # Show truncated backstory
                backstory = char_data.get('backstory', '')
                if len(backstory) > 200:
                    backstory = backstory[:200] + "..."
                sys.stdout.write(f"Backstory: {backstory}\n")
                sys.stdout.write(f"Key Relationships: {', '.join([f'{k}: {v}' for k, v in char_data.get('relationships', {}).items()][:3])}\n\n")
            sys.stdout.write("-------------------------------\n\n")
            
    elif node_name == "plan_chapters":
        progress_message = f"[{elapsed_str}] Planned {len(state.get('chapters', {}))} chapters for the story"
        
        if verbose_mode and "chapters" in state:
            chapters = state["chapters"]
            sys.stdout.write("\n------ CHAPTER PLAN ------\n")
            for ch_num in sorted(chapters.keys(), key=lambda x: int(x) if x.isdigit() else float('inf')):
                chapter = chapters[ch_num]
                sys.stdout.write(f"CHAPTER {ch_num}: {chapter.get('title', 'Untitled')}\n")
                # Show truncated outline
                outline = chapter.get('outline', '')
                if len(outline) > 150:
                    outline = outline[:150] + "..."
                sys.stdout.write(f"Outline: {outline}\n")
                sys.stdout.write(f"Scenes: {len(chapter.get('scenes', {}))}\n\n")
            sys.stdout.write("--------------------------\n\n")
            
    elif node_name == "brainstorm_scene_elements":
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        scene_info = f"Ch:{current_chapter}/Sc:{current_scene}"
        progress_message = f"[{elapsed_str}] Brainstormed creative elements for Scene {current_scene} of Chapter {current_chapter} [{scene_info}]"
        
        if verbose_mode and "creative_elements" in state:
            creative = state["creative_elements"]
            scene_elements_key = f"scene_elements_ch{current_chapter}_sc{current_scene}"
            scene_surprises_key = f"scene_surprises_ch{current_chapter}_sc{current_scene}"
            
            if scene_elements_key in creative:
                sys.stdout.write(f"\n------ SCENE ELEMENTS [{scene_info}] ------\n")
                if "recommended_ideas" in creative[scene_elements_key]:
                    sys.stdout.write(f"{creative[scene_elements_key]['recommended_ideas']}\n")
                sys.stdout.write("--------------------------\n\n")
                
            if scene_surprises_key in creative:
                sys.stdout.write(f"\n------ SURPRISE ELEMENTS [{scene_info}] ------\n")
                if "recommended_ideas" in creative[scene_surprises_key]:
                    sys.stdout.write(f"{creative[scene_surprises_key]['recommended_ideas']}\n")
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
            
            if verbose_mode and current_chapter in chapters and current_scene in chapters[current_chapter]["scenes"]:
                scene_content = chapters[current_chapter]["scenes"][current_scene].get("content", "")
                if scene_content:
                    # Show a preview of the scene (first 300 chars)
                    preview_length = min(300, len(scene_content))
                    preview = scene_content[:preview_length]
                    if preview_length < len(scene_content):
                        preview += "...\n[scene content truncated for display]"
                        
                    sys.stdout.write(f"\n------ SCENE PREVIEW [{scene_info}] ------\n")
                    sys.stdout.write(f"{preview}\n")
                    sys.stdout.write("---------------------------\n\n")
                    
    elif node_name == "reflect_on_scene":
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        
        # Always print the scene info even when empty to help with debugging
        scene_info = f"Ch:{current_chapter}/Sc:{current_scene}"
        progress_message = f"[{elapsed_str}] Analyzed Scene {current_scene} of Chapter {current_chapter} for quality and consistency [{scene_info}]"
        
        if verbose_mode and current_chapter in state.get("chapters", {}) and current_scene in state["chapters"][current_chapter]["scenes"]:
            reflection_notes = state["chapters"][current_chapter]["scenes"][current_scene].get("reflection_notes", [])
            if reflection_notes:
                sys.stdout.write(f"\n------ REFLECTION NOTES [{scene_info}] ------\n")
                for i, note in enumerate(reflection_notes):
                    # Truncate if very long
                    if len(note) > 300:
                        note = note[:300] + "...\n[note truncated for display]"
                    sys.stdout.write(f"{i+1}. {note}\n\n")
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
    args = parser.parse_args()
    
    # Check if API key is set
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is not set.")
        print("Please create a .env file with OPENAI_API_KEY=your_api_key")
        return
    
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
        print(f"Generating a {args.tone} {args.genre} story{author_str}...")
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
                initial_idea=args.idea
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
                partial_story = extract_partial_story(args.genre, args.tone, args.author, args.idea)
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