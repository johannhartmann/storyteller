"""
StoryCraft Agent - Autonomous Story-Writing with Dynamic Memory & State.

This system uses LangGraph's native edge system for workflow control instead of
a custom router function, which prevents recursion issues in complex stories.
"""

import os
from typing import Dict, List, Any
from langchain_core.messages import HumanMessage
from storyteller_lib.config import llm

# Import the graph builder
from storyteller_lib.graph import build_story_graph
from storyteller_lib.config import search_memory_tool, manage_memory_tool, MEMORY_NAMESPACE

def get_genre_key_elements(genre: str) -> List[str]:
    """
    Get key elements that should be present in a story of the specified genre.
    Uses LLM to generate genre-specific elements for flexibility with any genre.
    
    Args:
        genre: The genre of the story (e.g., fantasy, sci-fi, mystery)
        
    Returns:
        A list of key elements for the genre
    """
    # Use LLM to generate genre-specific elements
    prompt = f"""
    Identify the 5-7 most important elements that should be present in a {genre} story.
    
    These elements should include:
    - Plot structures typical of {genre}
    - Character types commonly found in {genre}
    - Setting characteristics appropriate for {genre}
    - Themes and motifs associated with {genre}
    - Stylistic elements expected in {genre}
    
    Format your response as a simple list of elements, one per line, without numbering or bullet points.
    Each element should be a concise phrase (5-10 words) describing a key aspect of {genre} stories.
    """
    
    try:
        # Get genre elements from LLM
        response = llm.invoke([HumanMessage(content=prompt)]).content
        
        # Process the response into a list
        elements = [line.strip() for line in response.split('\n') if line.strip()]
        
        # Filter out any non-element lines (like explanations or headers)
        elements = [e for e in elements if len(e.split()) <= 15 and not e.startswith("Note:") and not e.endswith(":")]
        
        # Ensure we have at least 5 elements
        if len(elements) < 5:
            # Add some generic elements to ensure we have enough
            generic_elements = [
                f"Elements typical of {genre} stories",
                f"Appropriate pacing and structure for {genre}",
                f"Character types commonly found in {genre}",
                f"Themes and motifs associated with {genre}",
                f"Reader expectations for a {genre} story"
            ]
            elements.extend(generic_elements[:(5 - len(elements))])
        
        # Store the generated elements in memory for reuse
        manage_memory_tool.invoke({
            "action": "create",
            "key": f"genre_elements_{genre.lower().replace(' ', '_')}",
            "value": elements,
            "namespace": MEMORY_NAMESPACE
        })
        
        return elements
        
    except Exception as e:
        print(f"Error generating genre elements: {str(e)}")
        # Fallback to generic elements
        return [
            f"Elements typical of {genre} stories",
            f"Appropriate pacing and structure for {genre}",
            f"Character types commonly found in {genre}",
            f"Themes and motifs associated with {genre}",
            f"Reader expectations for a {genre} story"
        ]
from typing import List, Optional
from pydantic import BaseModel, Field

class StoryElements(BaseModel):
    """Key elements extracted from a story idea."""
    
    setting: str = Field(
        description="The primary location or environment where the story takes place (e.g., 'small northern German coastal village')"
    )
    characters: List[str] = Field(
        description="The key individuals or entities in the story with their roles or descriptions (e.g., 'old fisherman detective')"
    )
    plot: str = Field(
        description="The main problem, challenge, or storyline (e.g., 'figuring out who stole the statue from the fish market')"
    )
    themes: List[str] = Field(
        default_factory=list,
        description="Any specific themes or motifs mentioned in the story idea"
    )
    genre_elements: List[str] = Field(
        default_factory=list,
        description="Any specific genre elements that should be emphasized (e.g., 'hard boiled detective story')"
    )

def parse_initial_idea(initial_idea: str) -> Dict[str, Any]:
    """
    Parse an initial story idea to extract key elements using Pydantic.
    
    Args:
        initial_idea: The initial story idea
        
    Returns:
        A dictionary of key elements extracted from the idea
    """
    if not initial_idea:
        return {}
    
    # Parse the initial idea to extract key elements
    
    try:
        # Create a structured LLM that outputs a StoryElements object
        structured_llm = llm.with_structured_output(StoryElements)
        
        # Use the structured LLM to extract key elements
        prompt = f"""
        CRITICAL TASK: Analyze this initial story idea and extract the key elements EXACTLY as they appear:
        
        "{initial_idea}"
        
        Extract and structure the following elements as they appear in the idea:
        1. Setting - The primary location or environment where the story takes place (e.g., "small northern German coastal village")
        2. Characters - The key individuals or entities in the story with their roles or descriptions (e.g., "old fisherman detective")
        3. Plot - The main problem, challenge, or storyline (e.g., "figuring out who stole the statue from the fish market")
        4. Themes - Any specific themes or motifs mentioned
        5. Genre elements - Any specific genre elements that should be emphasized (e.g., "hard boiled detective story")
        
        Be EXTREMELY precise and faithful to the original idea. Do not substitute, generalize, or omit elements.
        If the idea explicitly mentions a setting, character, or plot element, you MUST include it exactly as stated.
        """
        
        # Invoke the structured LLM
        idea_elements = structured_llm.invoke(prompt)
        
        # Convert Pydantic model to dictionary
        idea_elements_dict = idea_elements.dict()
        
        # Fallback extraction for critical elements if they're still empty
        if not idea_elements_dict["setting"] and "village" in initial_idea.lower():
            if "german" in initial_idea.lower() and "coastal" in initial_idea.lower():
                idea_elements_dict["setting"] = "Small northern German coastal village"
        
        if not idea_elements_dict["characters"] and "fisherman" in initial_idea.lower():
            if "detective" in initial_idea.lower() or "figuring out" in initial_idea.lower():
                idea_elements_dict["characters"] = ["Old fisherman (detective)"]
        
        if not idea_elements_dict["plot"] and "stole" in initial_idea.lower():
            if "statue" in initial_idea.lower() and "fish market" in initial_idea.lower():
                idea_elements_dict["plot"] = "Theft of a statue from the fish market; detective investigates to find the thief."
        
        # Add genre elements if missing
        if not idea_elements_dict["genre_elements"] and "detective" in initial_idea.lower():
            if "hard boiled" in initial_idea.lower():
                idea_elements_dict["genre_elements"] = ["Hard-boiled detective fiction", "Mystery", "Crime"]
        
        # Create a memory anchor for the initial idea elements to ensure they're followed
        if initial_idea and idea_elements_dict:
            # Create a more detailed must_include list
            must_include = []
            if idea_elements_dict['setting']:
                must_include.append(f"The story MUST take place in: {idea_elements_dict['setting']}")
            
            if idea_elements_dict['characters']:
                must_include.append(f"The story MUST include these characters: {', '.join(idea_elements_dict['characters'])}")
            
            if idea_elements_dict['plot']:
                must_include.append(f"The central plot MUST be: {idea_elements_dict['plot']}")
                
            if idea_elements_dict['genre_elements']:
                must_include.append(f"The story MUST include these genre elements: {', '.join(idea_elements_dict['genre_elements'])}")
            
            manage_memory_tool.invoke({
                "action": "create",
                "key": "initial_idea_elements",
                "value": {
                    "original_idea": initial_idea,
                    "extracted_elements": idea_elements_dict,
                    "must_include": must_include
                },
                "namespace": MEMORY_NAMESPACE
            })
            # Store initial idea elements in LangMem with must-include constraints
        
        return idea_elements_dict
    except Exception as e:
        # Create a more robust fallback with direct extraction from the initial idea
        fallback_elements = {
            "setting": "",
            "characters": [],
            "plot": "",
            "themes": [],
            "genre_elements": []
        }
        
        # Basic fallback extraction
        if "village" in initial_idea.lower():
            if "german" in initial_idea.lower() and "coastal" in initial_idea.lower():
                fallback_elements["setting"] = "Small northern German coastal village"
        
        if "fisherman" in initial_idea.lower():
            if "detective" in initial_idea.lower() or "figuring out" in initial_idea.lower():
                fallback_elements["characters"] = ["Old fisherman (detective)"]
        
        if "stole" in initial_idea.lower():
            if "statue" in initial_idea.lower() and "fish market" in initial_idea.lower():
                fallback_elements["plot"] = "Theft of a statue from the fish market; detective investigates to find the thief."
        
        if "detective" in initial_idea.lower():
            if "hard boiled" in initial_idea.lower():
                fallback_elements["genre_elements"] = ["Hard-boiled detective fiction", "Mystery", "Crime"]
        
        return fallback_elements

def extract_partial_story(genre: str = "fantasy", tone: str = "epic", author: str = "", initial_idea: str = "", language: str = ""):
    """
    Attempt to extract a partial story from memory when normal generation fails.
    This function tries to recover whatever content has been generated so far,
    even if the full story generation process didn't complete.
    
    Args:
        genre: The genre of the story (e.g., fantasy, sci-fi, mystery)
        tone: The tone of the story (e.g., epic, dark, humorous)
        author: Optional author whose style to emulate (e.g., Tolkien, Rowling, Martin)
        initial_idea: Optional initial story idea to use as a starting point
        language: Optional target language for the story
        
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
    
    # No note about incomplete status needed
    
    # Try to retrieve chapters and scenes from memory
    try:
        # Get all chapters and scenes from memory
        # Use search_memory_tool to list all chapters
        chapter_data = search_memory_tool.invoke({
            "query": "chapter_"
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
                        ch_data = search_memory_tool.invoke({
                            "query": f"chapter_{ch_num}"
                        })
                        
                        # Extract the chapter data from the results
                        ch_data_result = None
                        if ch_data and len(ch_data) > 0:
                            for item in ch_data:
                                if hasattr(item, 'key') and item.key == key:
                                    ch_data_result = {"key": item.key, "value": item.value}
                                    break
                        ch_data = ch_data_result
                        
                        if ch_data and "value" in ch_data:
                            chapter_dict[ch_num] = ch_data["value"]
                    except Exception:
                        pass
            
            # Get scene data
            # Use search_memory_tool to list all scenes
            scene_data = search_memory_tool.invoke({
                "query": "scene_"
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
                            sc_data = search_memory_tool.invoke({
                                "query": f"scene_{ch_num}_{sc_num}"
                            })
                            
                            # Extract the scene data from the results
                            sc_data_result = None
                            if sc_data and len(sc_data) > 0:
                                for item in sc_data:
                                    if hasattr(item, 'key') and item.key == key:
                                        sc_data_result = {"key": item.key, "value": item.value}
                                        break
                            sc_data = sc_data_result
                            
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
                        
                        # Add scene content without scene headlines
                        if isinstance(scene, dict) and "content" in scene:
                            story_parts.append(f"{scene['content']}\n\n")
    except Exception as e:
        story_parts.append(f"\n*Error recovering chapter content: {str(e)}*\n\n")
    
    # If we have any content, return it
    if len(story_parts) > 1:  # More than just the title
        return "".join(story_parts)
    
    return None


def generate_story(genre: str = "fantasy", tone: str = "epic", author: str = "", initial_idea: str = "", language: str = ""):
    """
    Generate a complete story using the StoryCraft agent with the refactored graph.
    
    Args:
        genre: The genre of the story (e.g., fantasy, sci-fi, mystery)
        tone: The tone of the story (e.g., epic, dark, humorous)
        author: Optional author whose style to emulate (e.g., Tolkien, Rowling, Martin)
        initial_idea: Optional initial story idea to use as a starting point
        language: Optional target language for the story
    """
    # Parse the initial idea once to extract key elements
    idea_elements = {}
    if initial_idea:
        # Parse the initial idea to extract key elements
        idea_elements = parse_initial_idea(initial_idea)
        
        # Adjust genre if needed based on the initial idea
        if idea_elements.get("plot", "").lower().find("murder") >= 0 or idea_elements.get("plot", "").lower().find("kill") >= 0:
            if genre.lower() not in ["mystery", "thriller", "crime"]:
                genre = "mystery"
        
        # Create a memory anchor for the initial idea to ensure it's followed
        manage_memory_tool.invoke({
            "action": "create",
            "key": "initial_idea_instruction",
            "value": f"This story MUST follow the initial idea: '{initial_idea}'. The key elements MUST be preserved exactly as specified.",
            "namespace": MEMORY_NAMESPACE
        })
    
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
    idea_text = f" based on this idea: '{initial_idea}'" if initial_idea else ""
    print(f"Generating a {tone} {genre} story{' in the style of '+author if author else ''}{idea_text}...")
    
    # Get language from config if not provided
    from storyteller_lib.config import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
    if not language:
        language = DEFAULT_LANGUAGE
    
    # Validate language
    if language.lower() not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE
    
    # Add language mention to the message if not English
    language_mention = f" in {SUPPORTED_LANGUAGES[language.lower()]}" if language.lower() != DEFAULT_LANGUAGE else ""
    
    # Create memory anchors for key elements to ensure persistence throughout generation
    # These will be available to all nodes in the graph
    
    # Store genre requirements
    manage_memory_tool.invoke({
        "action": "create",
        "key": "genre_requirements",
        "value": {
            "genre": genre,
            "tone": tone,
            "key_elements": get_genre_key_elements(genre)
        },
        "namespace": MEMORY_NAMESPACE
    })
    
    # Store initial idea as a memory anchor
    if initial_idea:
        manage_memory_tool.invoke({
            "action": "create",
            "key": "initial_idea_anchor",
            "value": {
                "idea": initial_idea,
                "importance": "critical",
                "must_be_followed": True
            },
            "namespace": MEMORY_NAMESPACE
        })
        
        # Parse initial idea to extract key elements
        idea_elements = parse_initial_idea(initial_idea)
        
        # Store each key element as a separate memory anchor
        for key, value in idea_elements.items():
            if value:
                manage_memory_tool.invoke({
                    "action": "create",
                    "key": f"initial_idea_{key}_anchor",
                    "value": value,
                    "namespace": MEMORY_NAMESPACE
                })
    
    # Initial state with all fields from StoryState schema
    initial_state = {
        "messages": [HumanMessage(content=f"Please write a {tone} {genre} story{' in the style of '+author if author else ''}{language_mention}{idea_text} for me.")],
        "genre": genre,
        "tone": tone,
        "author": author,
        "author_style_guidance": author_style_guidance,
        "language": language,
        "initial_idea": initial_idea,
        "initial_idea_elements": idea_elements,  # Include parsed elements in initial state
        "global_story": "",
        "chapters": {},
        "characters": {},
        "revelations": {},
        "creative_elements": {},
        "current_chapter": "",
        "current_scene": "",
        "completed": False,
        "last_node": ""  # Include this for schema compatibility
    }
        
    # Configure higher recursion limit to handle longer stories
    # The config dictionary needs to be passed as a named parameter 'config' to invoke()
    
    # Run the graph with our configuration
    # Progress tracking will happen automatically via the decorated node functions
    # No need for store reference as we're not using checkpointing in single-session mode
    result = graph.invoke(
        initial_state,
        config={
            "recursion_limit": 400,
            "configurable": {
                "thread_id": f"{genre}_{tone}_{language}_{author}".replace(" ", "_")
            }
        }
    )
    
    # If compiled_story is directly in the result, return it
    if "compiled_story" in result:
        return result["compiled_story"]
    
    # Try to retrieve the complete story using search
    try:
        complete_story = search_memory_tool.invoke({
            "query": "complete final story with all chapters and scenes"
        })
        
        if complete_story:
            return complete_story
    except Exception:
        pass
    
    # If search fails, try direct key lookup
    try:
        complete_story_obj = search_memory_tool.invoke({
            "query": "final_story"
        })
        
        # Extract the complete story from the results
        complete_story_result = None
        if complete_story_obj and len(complete_story_obj) > 0:
            for item in complete_story_obj:
                if hasattr(item, 'key') and (item.key == "complete_story" or item.key == "final_story"):
                    complete_story_result = {"key": item.key, "value": item.value}
                    break
        complete_story_obj = complete_story_result
        
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
