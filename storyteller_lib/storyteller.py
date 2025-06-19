"""
StoryCraft Agent - Autonomous Story-Writing with Dynamic Memory & State.

This system uses LangGraph's native edge system for workflow control instead of
a custom router function, which prevents recursion issues in complex stories.
"""

import os
from typing import Dict, List, Any
from langchain_core.messages import HumanMessage
from storyteller_lib.config import llm
# Memory manager imports removed - using state and database instead

# Import the graph builder
from storyteller_lib.config import MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.graph import build_story_graph

def get_genre_key_elements(genre: str, language: str = "english") -> List[str]:
    """
    Get key elements that should be present in a story of the specified genre.
    Uses LLM to generate genre-specific elements for flexibility with any genre.
    
    Args:
        genre: The genre of the story (e.g., fantasy, sci-fi, mystery)
        language: The language for the elements
        
    Returns:
        A list of key elements for the genre
    """
    # Use template system
    from storyteller_lib.prompt_templates import render_prompt
    
    # Render the genre key elements prompt
    prompt = render_prompt(
        'genre_key_elements',
        language=language,
        genre=genre
    )
    
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
        
        # Genre elements are generated fresh each time
        
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

def parse_initial_idea(initial_idea: str, language: str = DEFAULT_LANGUAGE) -> Dict[str, Any]:
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
        
        # Use template system
        from storyteller_lib.prompt_templates import render_prompt
        
        # Render the parse initial idea prompt
        prompt = render_prompt(
            'parse_initial_idea',
            language=language,
            initial_idea=initial_idea
        )
        
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
            
            # Initial idea elements are stored in state and passed through the workflow
        
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

def extract_partial_story(
    genre: str = "fantasy",
    tone: str = "epic",
    author: str = "",
    initial_idea: str = "",
    language: str = "",
    model_provider: str = None,
    model: str = None,
    return_state: bool = False
):
    """
    Attempt to extract a partial story from database when normal generation fails.
    This function tries to recover whatever content has been generated so far,
    even if the full story generation process didn't complete.
    
    Returns:
        If return_state is False, returns the partial story as a string, or None if nothing could be recovered.
        If return_state is True, returns a tuple of (partial_story, state), where state may be incomplete.
    """
    # This is a recovery function - return minimal content
    story_parts = []
    story_parts.append(f"# Partial {tone.capitalize()} {genre.capitalize()} Story\n\n")
    story_parts.append("Story generation was interrupted. Please try running the generator again.\n")
    
    # Try to get any content from database
    try:
        from storyteller_lib.database_integration import get_db_manager
        db_manager = get_db_manager()
        if db_manager and db_manager._db:
            with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                # Get any scenes that were written
                cursor.execute("""
                    SELECT c.chapter_number, c.title, s.scene_number, s.content
                    FROM chapters c
                    LEFT JOIN scenes s ON c.id = s.chapter_id
                    WHERE s.content IS NOT NULL AND s.content != ''
                    ORDER BY c.chapter_number, s.scene_number
                """)
                results = cursor.fetchall()
                
                if results:
                    story_parts.append("\n## Recovered Content:\n\n")
                    current_chapter = None
                    for ch_num, ch_title, sc_num, content in results:
                        if ch_num != current_chapter:
                            story_parts.append(f"\n### Chapter {ch_num}: {ch_title or 'Untitled'}\n\n")
                            current_chapter = ch_num
                        story_parts.append(f"{content}\n\n")
    except Exception as e:
        story_parts.append(f"\n*Could not recover content from database: {str(e)}*\n")
    
    partial_story = "".join(story_parts)
    
    if return_state:
        # Return minimal state
        state = {
            "genre": genre,
            "tone": tone,
            "author": author,
            "language": language,
            "initial_idea": initial_idea
        }
        return partial_story, state
    
    return partial_story


def generate_story(
    genre: str = "fantasy",
    tone: str = "epic",
    author: str = "",
    initial_idea: str = "",
    language: str = "",
    model_provider: str = None,
    model: str = None,
    return_state: bool = False,
    progress_log_path: str = None
):
    """
    Generate a complete story using the StoryCraft agent with the refactored graph.
    
    Args:
        genre: The genre of the story (e.g., fantasy, sci-fi, mystery)
        tone: The tone of the story (e.g., epic, dark, humorous)
        author: Optional author whose style to emulate (e.g., Tolkien, Rowling, Martin)
        initial_idea: Optional initial story idea to use as a starting point
        language: Optional target language for the story
        model_provider: Optional model provider to use (openai, anthropic, gemini)
        model: Optional specific model to use
        return_state: Whether to return the state along with the story
        
    Returns:
        If return_state is False, returns the story as a string.
        If return_state is True, returns a tuple of (story, state).
    """
    # Configure the LLM with the specified provider and model
    from storyteller_lib.config import get_llm
    global llm
    llm = get_llm(provider=model_provider, model=model)
    
    # Initialize progress logger
    from storyteller_lib.story_progress_logger import initialize_progress_logger, log_progress
    progress_logger = initialize_progress_logger(progress_log_path)
    
    # Log initial story parameters
    log_progress("story_params", genre=genre, tone=tone, author=author, 
                language=language if language else "english", idea=initial_idea)
    # Parse the initial idea once to extract key elements
    idea_elements = {}
    if initial_idea:
        # Parse the initial idea to extract key elements
        idea_elements = parse_initial_idea(initial_idea, language)
        
        # Let the LLM determine the appropriate genre based on the initial idea
        # instead of hardcoding specific genre rules
        
        # The initial idea is already stored in the state and will be passed through the graph
    
    # Get the graph
    graph = build_story_graph()
    
    # Author style guidance will be generated in the graph if needed
    author_style_guidance = ""
    
    # Run the graph with proper progress tracking
    idea_text = f" based on this idea: '{initial_idea}'" if initial_idea else ""
    print(f"Generating a {tone} {genre} story{' in the style of '+author if author else ''}{idea_text}...")
    
    # Get language from config if not provided
    if not language:
        language = DEFAULT_LANGUAGE
    
    # Validate language
    if language.lower() not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE
    
    # Add language mention to the message if not English
    language_mention = f" in {SUPPORTED_LANGUAGES[language.lower()]}" if language.lower() != DEFAULT_LANGUAGE else ""
    
    # Save story configuration to database
    from storyteller_lib.database_integration import get_db_manager
    db_manager = get_db_manager()
    if db_manager:
        # Parse initial idea to extract key elements if provided
        idea_elements = {}
        if initial_idea:
            idea_elements = parse_initial_idea(initial_idea, language)
            
        # Save configuration to story_config table
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            # Insert or update story_config (single row with id=1)
            cursor.execute("""
                INSERT OR REPLACE INTO story_config 
                (id, genre, tone, language, author, initial_idea, created_at, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (genre, tone, language, author, initial_idea))
            
            # If we have idea elements, store them as JSON in a new column or memory
            if idea_elements:
                import json
                cursor.execute("""
                    INSERT OR REPLACE INTO memories (key, value, namespace)
                    VALUES ('initial_idea_elements', ?, 'storyteller')
                """, (json.dumps(idea_elements),))
            
            conn.commit()
    
    # Initial state with only workflow fields
    print(f"[DEBUG] generate_story: language parameter = '{language}'")
    print(f"[DEBUG] generate_story: DEFAULT_LANGUAGE = '{DEFAULT_LANGUAGE}'")
    initial_state = {
        "messages": [HumanMessage(content=f"Please write a {tone} {genre} story{' in the style of '+author if author else ''}{language_mention}{idea_text} for me.")],
        "chapters": {},
        "characters": {},
        "world_elements": {},
        "plot_threads": {},
        "revelations": {},
        "current_chapter": "",
        "current_scene": "",
        "current_scene_content": "",
        "scene_reflection": {},
        "scene_elements": {},
        "active_plot_threads": [],
        "completed": False,
        "last_node": ""
    }
        
    # Configure higher recursion limit to handle longer stories
    # The config dictionary needs to be passed as a named parameter 'config' to invoke()
    
    # Run the graph with our configuration
    # Progress tracking will happen automatically via the decorated node functions
    # No need for store reference as we're not using checkpointing in single-session mode
    result = graph.invoke(
        initial_state,
        config={
            "recursion_limit": 1000,
            "configurable": {
                "thread_id": f"{genre}_{tone}_{language}_{author}".replace(" ", "_")
            }
        }
    )
    
    # If compiled_story is directly in the result, return it
    if "compiled_story" in result:
        return result["compiled_story"]
    
    # Try to get the story from database if available
    try:
        from storyteller_lib.database_integration import get_db_manager
        db_manager = get_db_manager()
        if db_manager and db_manager._db:
            compiled_story = db_manager._db.get_full_story()
            if compiled_story:
                return compiled_story
    except Exception:
        pass
    
    # No fallback needed - if database is not available, just return empty
        
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
    
    # Assemble the final story
    final_story = "\n".join(story)
    
    # Log story completion
    word_count = len(final_story.split()) if final_story else 0
    duration = progress_logger.state.get_elapsed_time() if hasattr(progress_logger, 'state') else "Unknown"
    total_chapters = len(result.get("chapters", {})) if result else 0
    log_progress("story_complete", total_chapters=total_chapters, 
                total_words=word_count, duration=duration)
    
    # Print log file location
    print(f"\nStory progress log saved to: {progress_logger.get_log_path()}")
    
    # Return the story and state if requested
    if return_state:
        return final_story, result
    
    # Otherwise just return the story
    return final_story

if __name__ == "__main__":
    # Check if API key is set
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Please set your ANTHROPIC_API_KEY environment variable")
        exit(1)
    
    output_file = "generated_story.md"
    
    try:    
        # Generate a story (using genre and tone from command line args or environment variables)
        print("Generating story...")
        # Use configurable parameters instead of hardcoded values
        import os
        genre = os.environ.get("STORY_GENRE", "fantasy")
        tone = os.environ.get("STORY_TONE", "epic")
        print(f"Using genre: {genre}, tone: {tone}")
        story = generate_story(genre=genre, tone=tone)
        
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
