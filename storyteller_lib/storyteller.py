"""
StoryCraft Agent - Autonomous Story-Writing with Dynamic Memory & State.

This agent generates engaging, multi-chapter stories using the hero's journey structure.
It manages the overall story arc, chapters, scenes, characters, and revelations.
"""

import os
from typing import Dict, List
from langchain_core.messages import HumanMessage

from storyteller_lib.graph import build_story_graph
from storyteller_lib.config import search_memory_tool, manage_memory_tool, MEMORY_NAMESPACE

def generate_story(genre: str = "fantasy", tone: str = "epic", author: str = ""):
    """
    Generate a complete story using the StoryCraft agent.
    
    Args:
        genre: The genre of the story (e.g., fantasy, sci-fi, mystery)
        tone: The tone of the story (e.g., epic, dark, humorous)
        author: Optional author whose style to emulate (e.g., Tolkien, Rowling, Martin)
    """
    # Import the graph builder (progress tracking is handled separately)
    from storyteller_lib.graph import build_story_graph
    
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
    
    # Initial state
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
        "completed": False,
        "last_node": ""
    }
    
    # Log the start of story generation
    print(f"Generating a {tone} {genre} story{' in the style of '+author if author else ''}...")
    
    # Run the graph with the initial state with an increased recursion limit
    # Progress tracking will happen automatically via the decorated node functions
    config = {"recursion_limit": 100}  # Increase the recursion limit to avoid errors
    
    # Run the graph with our configuration
    result = graph.invoke(initial_state, config)
    
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
        
    # Generate a fantasy story
    story = generate_story(genre="fantasy", tone="epic")
    
    # Write to file
    with open("generated_story.md", "w") as f:
        f.write(story)
    
    print("Story generation complete! Saved to generated_story.md")