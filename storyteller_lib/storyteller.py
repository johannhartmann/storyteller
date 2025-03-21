"""
StoryCraft Agent - Autonomous Story-Writing with Dynamic Memory & State.

This system uses LangGraph's native edge system for workflow control instead of
a custom router function, which prevents recursion issues in complex stories.
"""

import os
from typing import Dict, List
from langchain_core.messages import HumanMessage

# Import the graph builder
from storyteller_lib.graph import build_story_graph
from storyteller_lib.config import search_memory_tool, manage_memory_tool, MEMORY_NAMESPACE

def extract_partial_story(genre: str = "fantasy", tone: str = "epic", author: str = ""):
    """
    Attempt to extract a partial story from memory when normal generation fails.
    This function tries to recover whatever content has been generated so far,
    even if the full story generation process didn't complete.
    
    Args:
        genre: The genre of the story (e.g., fantasy, sci-fi, mystery)
        tone: The tone of the story (e.g., epic, dark, humorous)
        author: Optional author whose style to emulate (e.g., Tolkien, Rowling, Martin)
        
    Returns:
        The partial story as a string, or None if nothing could be recovered
    """
    story_parts = []
    
    # Try to get the title and global story from memory
    try:
        title = ""
        global_story = search_memory_tool.invoke({
            "query": "global story outline or plot summary",
            "namespace": MEMORY_NAMESPACE
        })
        
        if global_story:
            # Extract a title
            title_lines = [line for line in global_story.split('\n') 
                           if line.strip() and not line.lower().startswith("outline") 
                           and not line.lower().startswith("summary")]
            if title_lines:
                title = title_lines[0].strip()
                # Clean up title if needed (remove any "Title: " prefix)
                if ":" in title and len(title.split(":")) > 1:
                    title = title.split(":", 1)[1].strip()
        
        if title:
            story_parts.append(f"# {title}\n\n")
        else:
            story_parts.append(f"# Partial {tone.capitalize()} {genre.capitalize()} Story\n\n")
    except Exception:
        story_parts.append(f"# Partial {tone.capitalize()} {genre.capitalize()} Story\n\n")
    
    # Add a note about the incomplete status
    story_parts.append("*Note: This story was partially generated before an error occurred.*\n\n")
    
    # Try to retrieve chapters and scenes from memory
    try:
        # Get all chapters and scenes from memory
        chapter_data = manage_memory_tool.invoke({
            "action": "list",
            "prefix": "chapter_",
            "namespace": MEMORY_NAMESPACE
        })
        
        if chapter_data and "keys" in chapter_data:
            chapter_keys = chapter_data["keys"]
            
            # Extract chapter numbers
            chapter_dict = {}
            for key in chapter_keys:
                # Extract chapter number from key like "chapter_1", "chapter_2", etc.
                if "_" in key:
                    try:
                        ch_num = key.split("_")[1]
                        # Get chapter content
                        ch_data = manage_memory_tool.invoke({
                            "action": "get",
                            "key": key,
                            "namespace": MEMORY_NAMESPACE
                        })
                        
                        if ch_data and "value" in ch_data:
                            chapter_dict[ch_num] = ch_data["value"]
                    except Exception:
                        pass
            
            # Get scene data
            scene_data = manage_memory_tool.invoke({
                "action": "list",
                "prefix": "scene_",
                "namespace": MEMORY_NAMESPACE
            })
            
            scene_dict = {}
            if scene_data and "keys" in scene_data:
                scene_keys = scene_data["keys"]
                
                for key in scene_keys:
                    # Extract chapter and scene numbers from keys like "scene_1_2"
                    parts = key.split("_")
                    if len(parts) >= 3:
                        try:
                            ch_num = parts[1]
                            sc_num = parts[2]
                            
                            # Get scene content
                            sc_data = manage_memory_tool.invoke({
                                "action": "get",
                                "key": key,
                                "namespace": MEMORY_NAMESPACE
                            })
                            
                            if sc_data and "value" in sc_data:
                                if ch_num not in scene_dict:
                                    scene_dict[ch_num] = {}
                                scene_dict[ch_num][sc_num] = sc_data["value"]
                        except Exception:
                            pass
            
            # Assemble the partial story
            for ch_num in sorted(chapter_dict.keys(), key=lambda x: int(x) if x.isdigit() else float('inf')):
                chapter = chapter_dict[ch_num]
                
                # Add chapter heading
                if isinstance(chapter, dict) and "title" in chapter:
                    story_parts.append(f"\n## Chapter {ch_num}: {chapter['title']}\n\n")
                else:
                    story_parts.append(f"\n## Chapter {ch_num}\n\n")
                
                # Add scenes for this chapter if available
                if ch_num in scene_dict:
                    for sc_num in sorted(scene_dict[ch_num].keys(), key=lambda x: int(x) if x.isdigit() else float('inf')):
                        scene = scene_dict[ch_num][sc_num]
                        
                        # Add scene content
                        if isinstance(scene, dict) and "content" in scene:
                            story_parts.append(f"### Scene {sc_num}\n\n")
                            story_parts.append(f"{scene['content']}\n\n")
    except Exception as e:
        story_parts.append(f"\n*Error recovering chapter content: {str(e)}*\n\n")
    
    # If we have any content, return it
    if len(story_parts) > 1:  # More than just the title
        return "".join(story_parts)
    
    return None


def generate_story(genre: str = "fantasy", tone: str = "epic", author: str = ""):
    """
    Generate a complete story using the StoryCraft agent with the refactored graph.
    
    Args:
        genre: The genre of the story (e.g., fantasy, sci-fi, mystery)
        tone: The tone of the story (e.g., epic, dark, humorous)
        author: Optional author whose style to emulate (e.g., Tolkien, Rowling, Martin)
    """
    # Get the graph with our decorated node functions
    graph = build_story_graph()
    
    # Get author style guidance if an author is specified
    author_style_guidance = ""
    if author:
        # Try to retrieve from memory first
        try:
            author_guidance = search_memory_tool.invoke({
                "query": f"writing style of {author}",
                "namespace": MEMORY_NAMESPACE
            })
            
            if author_guidance:
                author_style_guidance = author_guidance
        except:
            # We'll generate it in the graph if needed
            pass
    
    # Run the graph with proper progress tracking
    print(f"Generating a {tone} {genre} story{' in the style of '+author if author else ''}...")
    
    # Initial state - remove custom router-related fields
    initial_state = {
        "messages": [HumanMessage(content=f"Please write a {tone} {genre} story{' in the style of '+author if author else ''} for me.")],
        "genre": genre,
        "tone": tone,
        "author": author,
        "author_style_guidance": author_style_guidance,
        "global_story": "",
        "chapters": {},
        "characters": {},
        "revelations": {},
        "creative_elements": {},
        "current_chapter": "",
        "current_scene": "",
        "completed": False
        # Removed "last_node" as it's no longer needed
    }
    
    # Configure higher recursion limit to handle longer stories
    # The config dictionary needs to be passed as a named parameter 'config' to invoke()
    
    # Run the graph with our configuration
    # Progress tracking will happen automatically via the decorated node functions
    result = graph.invoke(initial_state, config={"recursion_limit": 200})
    
    # If compiled_story is directly in the result, return it
    if "compiled_story" in result:
        return result["compiled_story"]
    
    # Try to retrieve the complete story using search
    try:
        complete_story = search_memory_tool.invoke({
            "query": "complete final story with all chapters and scenes",
            "namespace": MEMORY_NAMESPACE
        })
        
        if complete_story:
            return complete_story
    except Exception:
        pass
    
    # If search fails, try direct key lookup
    try:
        complete_story_obj = manage_memory_tool.invoke({
            "action": "get",
            "key": "complete_story",
            "namespace": MEMORY_NAMESPACE
        })
        
        if complete_story_obj and "value" in complete_story_obj:
            return complete_story_obj["value"]
    except Exception:
        pass
        
    # If we can't find the compiled story, manually assemble from chapters
    story = []
    
    # Extract title from global story if available
    if "global_story" in result and result["global_story"]:
        story_title = result["global_story"].split('\n')[0]
        # Clean up title if needed (remove any "Title: " prefix)
        if ":" in story_title and len(story_title.split(":")) > 1:
            story_title = story_title.split(":", 1)[1].strip()
        else:
            story_title = story_title
            
        story.append(f"# {story_title}\n\n")
    else:
        story.append(f"# Generated {tone.capitalize()} {genre.capitalize()} Story\n\n")
    
    # Add each chapter
    if "chapters" in result:
        chapters = result["chapters"]
        for chapter_num in sorted(chapters.keys(), key=int):
            chapter = chapters[chapter_num]
            story.append(f"\n## Chapter {chapter_num}: {chapter['title']}\n")
            
            # Add each scene
            for scene_num in sorted(chapter["scenes"].keys(), key=int):
                scene = chapter["scenes"][scene_num]
                if scene.get("content"):
                    story.append(f"### Scene {scene_num}\n")
                    story.append(scene["content"])
                    story.append("\n\n")
    
    # Return the assembled story
    return "\n".join(story)

if __name__ == "__main__":
    # Check if API key is set
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Please set your ANTHROPIC_API_KEY environment variable")
        exit(1)
    
    output_file = "generated_story.md"
    
    try:    
        # Generate a fantasy story
        print("Generating fantasy story...")
        story = generate_story(genre="fantasy", tone="epic")
        
        # Write to file with robust error handling
        try:
            # Write to file
            with open(output_file, "w") as f:
                f.write(story)
            print(f"Story generation complete! Saved to {output_file}")
        except IOError as e:
            print(f"Error saving to {output_file}: {str(e)}")
            # Try fallback location
            fallback_file = "story_fallback.md"
            try:
                with open(fallback_file, "w") as f:
                    f.write(story)
                print(f"Story saved to fallback location: {fallback_file}")
            except IOError:
                print("CRITICAL ERROR: Could not save story to any location")
    except Exception as e:
        print(f"Error during story generation: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Try to recover partial story
        try:
            partial_story = extract_partial_story()
            if partial_story:
                print("Recovered partial story from memory")
                # Try to save the partial story
                try:
                    with open(output_file, "w") as f:
                        f.write(partial_story)
                    print(f"Partial story saved to {output_file}")
                except IOError:
                    print(f"Error saving partial story to {output_file}")
        except Exception as recovery_err:
            print(f"Could not recover partial story: {str(recovery_err)}")