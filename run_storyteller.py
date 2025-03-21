#!/usr/bin/env python
"""
Run the StoryCraft agent to generate a complete story with progress updates.
"""

import os
import sys
import time
import argparse
from dotenv import load_dotenv
from storyteller_lib.storyteller import generate_story
from storyteller_lib import set_progress_callback, reset_progress_tracking

# Load environment variables from .env file
load_dotenv()

# Progress tracking variables
start_time = None
node_counts = {}
current_chapter = None
current_scene = None

def progress_callback(node_name, state):
    """
    Report progress during story generation.
    
    Args:
        node_name: The name of the node that just finished executing
        state: The current state of the story generation
    """
    global start_time, node_counts, current_chapter, current_scene
    
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
    elif node_name == "generate_story_outline":
        progress_message = f"[{elapsed_str}] Generated story outline following hero's journey structure"
    elif node_name == "generate_characters":
        progress_message = f"[{elapsed_str}] Created {len(state.get('characters', {}))} detailed character profiles with interconnected backgrounds"
    elif node_name == "plan_chapters":
        progress_message = f"[{elapsed_str}] Planned {len(state.get('chapters', {}))} chapters for the story"
    elif node_name == "brainstorm_scene_elements":
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        progress_message = f"[{elapsed_str}] Brainstormed creative elements for Scene {current_scene} of Chapter {current_chapter}"
    elif node_name == "write_scene":
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        chapters = state.get("chapters", {})
        if current_chapter in chapters:
            chapter = chapters[current_chapter]
            chapter_title = chapter.get("title", f"Chapter {current_chapter}")
            progress_message = f"[{elapsed_str}] Wrote Scene {current_scene} of Chapter {current_chapter}: {chapter_title}"
    elif node_name == "reflect_on_scene":
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        progress_message = f"[{elapsed_str}] Analyzed Scene {current_scene} of Chapter {current_chapter} for quality and consistency"
    elif node_name == "revise_scene_if_needed":
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        progress_message = f"[{elapsed_str}] Reviewed Scene {current_scene} of Chapter {current_chapter} for potential revisions"
    elif node_name == "update_character_profiles":
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        progress_message = f"[{elapsed_str}] Updated character profiles after Scene {current_scene} of Chapter {current_chapter}"
    elif node_name == "review_continuity":
        current_chapter = state.get("current_chapter", "")
        progress_message = f"[{elapsed_str}] Performed continuity review after Chapter {current_chapter}"
    elif node_name == "advance_to_next_scene_or_chapter":
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        progress_message = f"[{elapsed_str}] Advanced to Scene {current_scene} of Chapter {current_chapter}"
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
                        if sc_data.get("content"):
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
    parser = argparse.ArgumentParser(description="Generate a story using the StoryCraft agent")
    parser.add_argument("--genre", type=str, default="fantasy", 
                        help="Genre of the story (e.g., fantasy, sci-fi, mystery)")
    parser.add_argument("--tone", type=str, default="epic", 
                        help="Tone of the story (e.g., epic, dark, humorous)")
    parser.add_argument("--author", type=str, default="", 
                        help="Author whose style to emulate (e.g., Tolkien, Rowling, Martin)")
    parser.add_argument("--output", type=str, default="story.md",
                        help="Output file to save the generated story")
    args = parser.parse_args()
    
    # Check if API key is set
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable is not set.")
        print("Please create a .env file with ANTHROPIC_API_KEY=your_api_key")
        return
    
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
        try:
            # Start the story generation 
            # We don't need to pass progress_callback since we registered it globally
            story = generate_story(
                genre=args.genre, 
                tone=args.tone, 
                author=args.author
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
            return 1
        
        # Ensure we have a story to save
        if story is None:
            print("No story was generated. Please check the error messages above.")
            return 1
            
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
        
        # Save to file
        with open(args.output, "w") as f:
            f.write(story)
        
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