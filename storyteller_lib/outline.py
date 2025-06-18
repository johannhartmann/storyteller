"""
StoryCraft Agent - Story outline and planning nodes.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from storyteller_lib.config import llm, manage_memory_tool, search_memory_tool, MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState
from storyteller_lib.memory_manager import manage_memory, search_memory
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from storyteller_lib.creative_tools import parse_json_with_langchain
from storyteller_lib import track_progress
from storyteller_lib.plot_threads import PlotThread, THREAD_IMPORTANCE, THREAD_STATUS


def generate_plot_threads_from_outline(story_outline: str, genre: str, tone: str, initial_idea: str, language: str = "english") -> Dict[str, Dict]:
    """Generate initial plot threads from the story outline."""
    # Use template system
    from storyteller_lib.prompt_templates import render_prompt
    
    # Render the plot threads prompt
    prompt = render_prompt(
        'plot_threads_from_outline',
        language=language,
        story_outline=story_outline,
        genre=genre,
        tone=tone,
        initial_idea=initial_idea
    )
    
    try:
        # Define the structured output
        class PlotThreadDefinition(BaseModel):
            name: str = Field(description="A concise, memorable name for the thread")
            description: str = Field(description="What this thread is about (2-3 sentences)")
            importance: str = Field(description="Thread importance: major, minor, or background")
            related_characters: List[str] = Field(description="Character roles involved in this thread")
        
        class PlotThreadsContainer(BaseModel):
            threads: List[PlotThreadDefinition] = Field(description="List of plot threads")
        
        # Get structured output
        structured_llm = llm.with_structured_output(PlotThreadsContainer)
        result = structured_llm.invoke(prompt)
        
        # Convert to plot thread objects
        plot_threads = {}
        for thread_def in result.threads:
            thread = PlotThread(
                name=thread_def.name,
                description=thread_def.description,
                importance=thread_def.importance,
                status=THREAD_STATUS["INTRODUCED"],
                first_chapter="",  # Will be set when first used
                first_scene="",
                related_characters=thread_def.related_characters
            )
            plot_threads[thread_def.name] = thread.to_dict()
        
        return plot_threads
        
    except Exception as e:
        print(f"Error generating plot threads: {e}")
        # Return minimal plot threads as fallback
        return {
            "Main Quest": {
                "name": "Main Quest",
                "description": "The hero's primary journey and mission",
                "importance": THREAD_IMPORTANCE["MAJOR"],
                "status": THREAD_STATUS["INTRODUCED"],
                "first_chapter": "",
                "first_scene": "",
                "last_chapter": "",
                "last_scene": "",
                "related_characters": ["hero"],
                "development_history": []
            }
        }


@track_progress
def generate_story_outline(state: StoryState) -> Dict:
    """Generate the overall story outline using the hero's journey structure."""
    # Import dependencies at the start
    from storyteller_lib.logger import get_logger
    from storyteller_lib.database_integration import get_db_manager
    from storyteller_lib.story_progress_logger import log_progress
    from storyteller_lib.prompt_templates import render_prompt
    
    logger = get_logger(__name__)
    
    genre = state["genre"]
    tone = state["tone"]
    author = state["author"]
    initial_idea = state.get("initial_idea", "")
    initial_idea_elements = state.get("initial_idea_elements", {})
    author_style_guidance = state["author_style_guidance"]
    language = state.get("language", DEFAULT_LANGUAGE)
    print(f"[DEBUG] generate_story_outline: language from state = '{state.get('language')}', using language = '{language}'")
    print(f"[DEBUG] generate_story_outline: DEFAULT_LANGUAGE = '{DEFAULT_LANGUAGE}'")
    creative_elements = state.get("creative_elements", {})
    
    # Prepare author style guidance
    style_guidance = ""
    if author:
        # If we don't have author guidance yet, generate it now
        if not author_style_guidance:
            # Use template system
            from storyteller_lib.prompt_templates import render_prompt
            
            # Render the author style analysis prompt
            author_prompt = render_prompt(
                'author_style_analysis',
                language=language,
                author=author
            )
            
            author_style_guidance = llm.invoke([HumanMessage(content=author_prompt)]).content
            
            # Store this for future use
            manage_memory_tool.invoke({
                "action": "create",
                "key": f"author_style_{author.lower().replace(' ', '_')}",
                "value": author_style_guidance,
                "namespace": MEMORY_NAMESPACE
            })
        
        style_guidance = f"""
        AUTHOR STYLE GUIDANCE:
        You will be emulating the writing style of {author}. Here's guidance on this author's style:
        
        {author_style_guidance}
        
        Incorporate these stylistic elements into your story outline while maintaining the hero's journey structure.
        """
    
    # Include brainstormed creative elements if available
    creative_guidance = ""
    if creative_elements:
        # Extract recommended story concept
        story_concept = ""
        if "story_concepts" in creative_elements and creative_elements["story_concepts"].get("recommended_ideas"):
            story_concept = creative_elements["story_concepts"]["recommended_ideas"]
            
        # Extract recommended world building elements
        world_building = ""
        if "world_building" in creative_elements and creative_elements["world_building"].get("recommended_ideas"):
            world_building = creative_elements["world_building"]["recommended_ideas"]
            
        # Extract recommended central conflict
        conflict = ""
        if "central_conflicts" in creative_elements and creative_elements["central_conflicts"].get("recommended_ideas"):
            conflict = creative_elements["central_conflicts"]["recommended_ideas"]
        
        # Compile creative guidance
        creative_guidance = f"""
        BRAINSTORMED CREATIVE ELEMENTS:
        
        Recommended Story Concept:
        {story_concept}
        
        Recommended World Building Elements:
        {world_building}
        
        Recommended Central Conflict:
        {conflict}
        
        Incorporate these brainstormed elements into your story outline, adapting them as needed to fit the hero's journey structure.
        """
    # Prepare language guidance
    language_guidance = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_guidance = f"""
        LANGUAGE CONSIDERATIONS:
        This story will be written in {SUPPORTED_LANGUAGES[language.lower()]}.
        
        When creating the story outline:
        1. Use character names that are authentic and appropriate for {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures
        2. Include settings, locations, and cultural references that resonate with {SUPPORTED_LANGUAGES[language.lower()]}-speaking audiences
        3. Consider storytelling traditions, folklore elements, and narrative structures common in {SUPPORTED_LANGUAGES[language.lower()]} literature
        4. Incorporate cultural values, social dynamics, and historical contexts relevant to {SUPPORTED_LANGUAGES[language.lower()]}-speaking regions
        5. Ensure that idioms, metaphors, and symbolic elements will translate well to {SUPPORTED_LANGUAGES[language.lower()]}
        
        The story should feel authentic to readers of {SUPPORTED_LANGUAGES[language.lower()]} rather than like a translated work.
        """
    
    # Pass raw elements to template - let template handle formatting
    idea_elements = initial_idea_elements if initial_idea and initial_idea_elements else None
    
    # Import prompt template system
    from storyteller_lib.prompt_templates import render_prompt
    
    # Prepare language instruction if needed
    language_instruction = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_instruction = f"""
        !!!CRITICAL LANGUAGE INSTRUCTION!!!
        This outline MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL content - including the title, character descriptions, plot elements, and setting details - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
        DO NOT translate the hero's journey structure - create the outline directly in {SUPPORTED_LANGUAGES[language.lower()]}.
        
        I will verify that your response is completely in {SUPPORTED_LANGUAGES[language.lower()]} and reject any outline that contains English.
        """
    
    # Prepare template variables
    template_vars = {
        'tone': tone,
        'genre': genre,
        'initial_idea': initial_idea,
        'idea_elements': idea_elements,  # Pass structured elements instead of formatted guidance
        'creative_guidance': creative_guidance,
        'style_guidance': style_guidance,
        'language_guidance': language_guidance
    }
    
    # Render the prompt using the template system
    prompt = render_prompt('story_outline', language=language, **template_vars)
    
    # Generate the story outline
    print(f"[DEBUG] About to generate story outline. Prompt length: {len(prompt)}")
    logger.info("Generating story outline with LLM...")
    logger.debug(f"Prompt length: {len(prompt)}")
    try:
        print("[DEBUG] Calling LLM...")
        response = llm.invoke([HumanMessage(content=prompt)])
        print(f"[DEBUG] LLM response type: {type(response)}")
        story_outline = response.content
        print(f"[DEBUG] Story outline length: {len(story_outline) if story_outline else 0}")
        print(f"[DEBUG] Story outline preview: {story_outline[:100] if story_outline else 'EMPTY'}")
        logger.info(f"LLM response type: {type(response)}")
        logger.info(f"LLM response content type: {type(response.content)}")
        logger.info(f"Generated story outline with length: {len(story_outline)}")
        if not story_outline:
            logger.error("LLM returned empty content!")
            logger.debug(f"Full LLM response: {response}")
    except Exception as e:
        print(f"[DEBUG] Exception during LLM call: {e}")
        logger.error(f"Failed to generate story outline: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        story_outline = ""
    # Perform multiple validation checks on the story outline
    print(f"[DEBUG] Before validation, story_outline length: {len(story_outline)}")
    validation_results = {}
    
    # Validate language if not English
    if language.lower() != DEFAULT_LANGUAGE:
        # Use template system
        from storyteller_lib.prompt_templates import render_prompt
        
        # Render the language validation prompt
        language_validation_prompt = render_prompt(
            'language_validation',
            "english",  # Always validate in English
            target_language=SUPPORTED_LANGUAGES[language.lower()],
            text_to_validate=story_outline
        )
        
        language_validation_result = llm.invoke([HumanMessage(content=language_validation_prompt)]).content
        validation_results["language"] = language_validation_result
        
        # Store the validation result in memory
        manage_memory(action="create", key="outline_language_validation", value=language_validation_result,
            namespace=MEMORY_NAMESPACE)
    
    # 1. Validate that the outline adheres to the initial idea if one was provided
    if initial_idea and initial_idea_elements:
        # Render the idea validation prompt
        idea_validation_prompt = render_prompt(
            'idea_validation',
            "english",  # Always validate in English
            initial_idea=initial_idea,
            setting=initial_idea_elements.get('setting', 'Unknown'),
            characters=initial_idea_elements.get('characters', []),
            plot=initial_idea_elements.get('plot', 'Unknown'),
            themes=initial_idea_elements.get('themes', []),
            genre_elements=initial_idea_elements.get('genre_elements', []),
            story_outline=story_outline
        )
        
        idea_validation_result = llm.invoke([HumanMessage(content=idea_validation_prompt)]).content
        validation_results["initial_idea"] = idea_validation_result
        
        # Store the validation result in memory
        manage_memory(action="create", key="outline_idea_validation", value=idea_validation_result,
            namespace=MEMORY_NAMESPACE)
    
    # 2. Validate that the outline adheres to the specified genre
    # Genre validation will be done directly with the genre parameter
    genre_elements = None  # Template will handle genre requirements
    
    # Render the genre validation prompt
    genre_validation_prompt = render_prompt(
        'genre_validation',
        "english",  # Always validate in English
        genre=genre,
        tone=tone,
        story_outline=story_outline,
        genre_elements=genre_elements
    )
    
    genre_validation_result = llm.invoke([HumanMessage(content=genre_validation_prompt)]).content
    validation_results["genre"] = genre_validation_result
    
    # Store the validation result in memory
    manage_memory(action="create", key="outline_genre_validation", value=genre_validation_result,
        namespace=MEMORY_NAMESPACE)
    
    # 3. Validate that the outline adheres to the specified setting if one was provided
    if initial_idea_elements and initial_idea_elements.get('setting'):
        setting = initial_idea_elements.get('setting')
        # Render the setting validation prompt
        setting_validation_prompt = render_prompt(
            'setting_validation',
            "english",  # Always validate in English
            setting=setting,
            story_outline=story_outline
        )
        
        setting_validation_result = llm.invoke([HumanMessage(content=setting_validation_prompt)]).content
        validation_results["setting"] = setting_validation_result
        
        # Store the validation result in memory
        manage_memory(action="create", key="outline_setting_validation", value=setting_validation_result,
            namespace=MEMORY_NAMESPACE)
    # Determine if we need to regenerate the outline based on validation results
    needs_regeneration = False
    improvement_guidance = ""
    
    # Check language validation first if not English
    if language.lower() != DEFAULT_LANGUAGE and "language" in validation_results:
        result = validation_results["language"]
        if "NO" in result:
            needs_regeneration = True
            improvement_guidance += "LANGUAGE ISSUES:\n"
            improvement_guidance += "The outline must be written ENTIRELY in " + SUPPORTED_LANGUAGES[language.lower()] + ".\n"
            if "parts are not in" in result:
                parts_section = result.split("parts are not in")[1].strip() if "parts are not in" in result else ""
                improvement_guidance += "The following parts were not in the correct language: " + parts_section + "\n"
            improvement_guidance += "\n\n"
    
    # Check initial idea validation
    if "initial_idea" in validation_results:
        result = validation_results["initial_idea"]
        # Regenerate if score is below 8 or NO determination
        if "NO" in result or any(f"score: {i}" in result.lower() for i in range(1, 8)):
            needs_regeneration = True
            improvement_guidance += "INITIAL IDEA INTEGRATION ISSUES:\n"
            improvement_guidance += result.split("guidance on how to improve it")[-1].strip() if "guidance on how to improve it" in result else result
            improvement_guidance += "\n\n"
    
    # Check genre validation
    if "genre" in validation_results:
        result = validation_results["genre"]
        if "NO" in result or any(f"score: {i}" in result.lower() for i in range(1, 8)):
            needs_regeneration = True
            improvement_guidance += f"GENRE ({genre}) ISSUES:\n"
            improvement_guidance += result.split("guidance on how to improve it:")[-1].strip() if "guidance on how to improve it:" in result else result
            improvement_guidance += "\n\n"
    
    # Check setting validation
    if "setting" in validation_results:
        result = validation_results["setting"]
        if "NO" in result or any(f"score: {i}" in result.lower() for i in range(1, 8)):
            needs_regeneration = True
            improvement_guidance += "SETTING ISSUES:\n"
            improvement_guidance += result.split("guidance on how to improve it:")[-1].strip() if "guidance on how to improve it:" in result else result
            improvement_guidance += "\n\n"
    
    # Initialize final_verification_result for later use
    final_verification_result = None
    
    # If any validation failed, regenerate the outline
    print(f"[DEBUG] Before regeneration check, story_outline length: {len(story_outline)}, needs_regeneration: {needs_regeneration}")
    if needs_regeneration:
        # Create a revised prompt with the improvement guidance
        language_instruction = ""
        if language.lower() != DEFAULT_LANGUAGE:
            language_instruction = f"""
            !!!CRITICAL LANGUAGE INSTRUCTION!!!
            This outline MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
            ALL content - including the title, character descriptions, plot elements, and setting details - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
            DO NOT translate the hero's journey structure - create the outline directly in {SUPPORTED_LANGUAGES[language.lower()]}.
            
            I will verify that your response is completely in {SUPPORTED_LANGUAGES[language.lower()]} and reject any outline that contains English.
            """
            
        revised_prompt = f"""
        {language_instruction}
        
        REVISION NEEDED: Your previous story outline needs improvement. Please revise it based on this feedback:
        
        AREAS NEEDING IMPROVEMENT:
        {improvement_guidance}
        
        Initial Idea: "{initial_idea}"
        
        KEY ELEMENTS TO INCORPORATE:
        - Setting: {initial_idea_elements.get('setting', 'Unknown') if initial_idea_elements else 'Not specified'}
           * This setting should be the primary location of the story
           * Ensure the setting is well-integrated throughout the narrative
        
        - Characters: {', '.join(initial_idea_elements.get('characters', [])) if initial_idea_elements else 'Not specified'}
           * These characters should be central to the story
           * Maintain their essential nature and roles as described
        
        - Plot: {initial_idea_elements.get('plot', 'Unknown') if initial_idea_elements else 'Not specified'}
           * This plot should be the central conflict
           * Ensure the story revolves around this core conflict
        - Themes: {', '.join(initial_idea_elements.get('themes', [])) if initial_idea_elements else 'Not specified'}
        - Genre Elements: {', '.join(initial_idea_elements.get('genre_elements', [])) if initial_idea_elements else 'Not specified'}
        
        Genre Requirements: This MUST be a {genre} story with a {tone} tone.
        
        {language_instruction if language.lower() != DEFAULT_LANGUAGE else ""}
        
        {prompt}
        """
        
        # Regenerate the outline
        logger.info("Regenerating story outline due to validation failures...")
        print(f"[DEBUG] About to regenerate. Current story_outline length: {len(story_outline)}")
        regenerated_outline = llm.invoke([HumanMessage(content=revised_prompt)]).content
        print(f"[DEBUG] Regenerated outline length: {len(regenerated_outline)}")
        story_outline = regenerated_outline
        logger.info(f"Regenerated story outline with length: {len(story_outline)}")
        # Perform a final verification check to ensure the regenerated outline meets the requirements
        # Render the final verification prompt
        final_verification_prompt = render_prompt(
            'final_verification',
            "english",  # Always validate in English
            initial_idea=initial_idea,
            setting=initial_idea_elements.get('setting', 'Unknown') if initial_idea_elements else 'Not specified',
            characters=initial_idea_elements.get('characters', []) if initial_idea_elements else [],
            plot=initial_idea_elements.get('plot', 'Unknown') if initial_idea_elements else 'Not specified',
            story_outline=story_outline,
            genre=genre,
            tone=tone,
            check_language=language.lower() != DEFAULT_LANGUAGE,
            target_language=SUPPORTED_LANGUAGES[language.lower()] if language.lower() != DEFAULT_LANGUAGE else None
        )
        
        final_verification_result = llm.invoke([HumanMessage(content=final_verification_prompt)]).content
        print(f"[DEBUG] Final verification result: {final_verification_result[:200]}")
        # If the outline still doesn't meet requirements, try one more time with additional guidance
        print(f"[DEBUG] Checking if 'NO' in final_verification_result: {'NO' in final_verification_result}")
        if "NO" in final_verification_result:
            language_instruction = ""
            if language.lower() != DEFAULT_LANGUAGE:
                language_instruction = f"""
                !!!CRITICAL LANGUAGE INSTRUCTION!!!
                This outline MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
                ALL content - including the title, character descriptions, plot elements, and setting details - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
                DO NOT translate the hero's journey structure - create the outline directly in {SUPPORTED_LANGUAGES[language.lower()]}.
                
                I will verify that your response is completely in {SUPPORTED_LANGUAGES[language.lower()]} and reject any outline that contains English.
                """
                
            final_attempt_prompt = f"""
            {language_instruction}
            
            FINAL REVISION NEEDED:
            
            The story outline still needs improvement:
            
            Initial Idea: "{initial_idea}"
            
            What still needs improvement:
            {final_verification_result}
            
            Please create an outline that:
            1. Uses "{initial_idea_elements.get('setting', 'Unknown')}" as the primary setting
            2. Features "{', '.join(initial_idea_elements.get('characters', []))}" as central characters
            3. Centers around "{initial_idea_elements.get('plot', 'Unknown')}" as the main conflict
            4. Adheres to the {genre} genre with a {tone} tone
            {f'5. Is written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]} without ANY English text' if language.lower() != DEFAULT_LANGUAGE else ''}
            
            Maintain the essence of the initial idea while crafting a compelling narrative.
            
            {language_instruction if language.lower() != DEFAULT_LANGUAGE else ""}
            Maintain the essence of the initial idea while crafting a compelling narrative.
            """
            
            # Final regeneration attempt
            print(f"[DEBUG] Final regeneration attempt. Current story_outline length: {len(story_outline)}")
            try:
                final_response = llm.invoke([HumanMessage(content=final_attempt_prompt)])
                final_outline = final_response.content
                print(f"[DEBUG] Final regenerated outline length: {len(final_outline)}")
                print(f"[DEBUG] Final outline preview: {final_outline[:100] if final_outline else 'EMPTY!'}")
                if final_outline:
                    story_outline = final_outline
                else:
                    print("[DEBUG] Final LLM call returned empty content! Keeping previous outline.")
                    # Keep the previous outline instead of overwriting with empty
            except Exception as e:
                print(f"[DEBUG] Exception in final regeneration: {e}")
                # Keep the previous outline on error
        
        # Store the revised outline
        manage_memory(action="create", key="story_outline_revised", value=story_outline,
            namespace=MEMORY_NAMESPACE)
        
        # Store the combined validation results
        manage_memory_tool.invoke({
            "action": "create",
            "key": "outline_validation_combined",
            "value": {
                "initial_validation": validation_results,
                "improvement_guidance": improvement_guidance,
                "final_verification": final_verification_result if final_verification_result else "Not performed",
                "regenerated": True
            },
            "namespace": MEMORY_NAMESPACE
        })
        
    # Ensure we have a story outline to store
    print(f"[DEBUG] Final check - story_outline length: {len(story_outline) if story_outline else 0}")
    print(f"[DEBUG] Final check - story_outline type: {type(story_outline)}")
    if not story_outline:
        logger.error("CRITICAL: story_outline is empty after all generation attempts!")
        print("[DEBUG] story_outline is empty or None!")
        # Try to recover from memory if possible
        try:
            memory_result = search_memory(query="story_outline_revised", namespace=MEMORY_NAMESPACE)
            if memory_result and len(memory_result) > 0:
                story_outline = memory_result[0].get('value', '')
                logger.info(f"Recovered story outline from memory with length: {len(story_outline)}")
        except:
            pass
            
        if not story_outline:
            # Generate a minimal outline as last resort
            logger.error("Generating emergency fallback outline...")
            story_outline = f"Emergency outline for {genre} story with {tone} tone. This should not happen."
    
    # Store in memory
    logger.info(f"About to store story outline in memory. Length: {len(story_outline)}")
    manage_memory(action="create", key="story_outline", value=story_outline)
    
    # Log the story outline
    log_progress("story_outline", outline=story_outline)
    
    # Generate initial plot threads from the outline
    plot_threads = generate_plot_threads_from_outline(story_outline, genre, tone, initial_idea, language)
    
    # Save plot threads to database
    try:
        db_manager = get_db_manager()
        if db_manager and db_manager._db:
            for thread_name, thread_data in plot_threads.items():
                db_manager._db.create_plot_thread(
                    name=thread_name,
                    description=thread_data.get('description', ''),
                    thread_type=thread_data.get('importance', 'minor'),
                    importance=thread_data.get('importance', 'minor'),
                    status=thread_data.get('status', 'introduced')
                )
            logger.info(f"Saved {len(plot_threads)} plot threads to database")
    except Exception as e:
        logger.error(f"Failed to save plot threads to database: {e}")
    
    # Store in procedural memory that this was a result of initial generation
    manage_memory_tool.invoke({
        "action": "create",
        "key": "procedural_memory_outline_generation",
        "value": {
            "timestamp": "initial_creation",
            "method": "hero's_journey_structure",
            "initial_idea_used": bool(initial_idea),
            "validation_performed": bool(initial_idea and initial_idea_elements)
        }
    })
    
    # Update the state
    
    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]
    
    # Create message for the user
    idea_mention = f" based on your idea about {initial_idea_elements.get('setting', 'the specified setting')}" if initial_idea else ""
    new_msg = AIMessage(content=f"I've created a story outline following the hero's journey structure{idea_mention}. Now I'll develop the characters in more detail.")
    
    # Store global story in database
    
    db_manager = get_db_manager()
    if not db_manager:
        raise RuntimeError("Database manager not available - cannot store story outline")
    
    try:
        # Log the outline length for debugging
        logger.info(f"Attempting to store story outline of length {len(story_outline)} to database")
        
        # Update the global story in the database
        db_manager.update_global_story(story_outline)
        logger.info("Story outline stored in database successfully")
        
        # Verify it was stored
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT global_story FROM story_config WHERE id = 1")
            result = cursor.fetchone()
            if result and result['global_story']:
                logger.info(f"Verified: Story outline in database has length {len(result['global_story'])}")
            else:
                logger.error("Warning: Story outline appears empty in database after save!")
                
    except Exception as e:
        logger.error(f"Failed to store story outline in database: {e}")
        raise RuntimeError(f"Could not store story outline in database: {e}")
    
    # Return the full story outline in state
    return {
        "global_story": story_outline,  # Return full outline, not truncated
        "plot_threads": plot_threads,  # Add generated plot threads to state
        "messages": [
            *[RemoveMessage(id=msg_id) for msg_id in message_ids],
            new_msg
        ]
    }


    
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class SceneSpec(BaseModel):
    """Detailed specification for a scene to prevent repetition."""
    description: str = Field(..., description="Brief description of what happens in this scene")
    plot_progressions: List[str] = Field(default_factory=list, description="Key plot points that MUST happen (e.g., 'hero_learns_about_quest')")
    character_knowledge_changes: Dict[str, List[str]] = Field(default_factory=dict, description="What each character learns in this scene")
    required_characters: List[str] = Field(default_factory=list, description="Characters who must appear in this scene")
    forbidden_repetitions: List[str] = Field(default_factory=list, description="Plot points that must NOT be repeated from earlier scenes")
    prerequisites: List[str] = Field(default_factory=list, description="Plot points that must have already happened before this scene")

class Chapter(BaseModel):
    """Enhanced model for a chapter with detailed scene specifications."""
    number: str = Field(..., description="The chapter number (as a string)")
    title: str = Field(..., description="The title of the chapter")
    outline: str = Field(..., description="Detailed summary of the chapter (200-300 words)")
    key_scenes: List[SceneSpec] = Field(..., description="List of key scenes with detailed specifications")

class ChapterPlan(BaseModel):
    """Enhanced model for the entire chapter plan with scene specifications."""
    chapters: List[Chapter] = Field(..., description="List of chapters in the story")

@track_progress
def plan_chapters(state: StoryState) -> Dict:
    """Divide the story into chapters with detailed outlines."""
    from storyteller_lib.prompt_templates import render_prompt
    
    global_story = state["global_story"]
    characters = state["characters"]
    genre = state["genre"]
    tone = state["tone"]
    language = state.get("language", DEFAULT_LANGUAGE)
    # Prepare language instruction and guidance
    language_instruction = ""
    language_guidance = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_instruction = f"""
        !!!CRITICAL LANGUAGE INSTRUCTION!!!
        This chapter plan MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL content - including chapter titles, summaries, scene descriptions, and character development - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
        DO NOT translate the hero's journey structure - create the chapter plan directly in {SUPPORTED_LANGUAGES[language.lower()]}.
        
        I will verify that your response is completely in {SUPPORTED_LANGUAGES[language.lower()]} and reject any plan that contains English.
        """
        
        language_guidance = f"""
        CHAPTER LANGUAGE CONSIDERATIONS:
        Plan chapters appropriate for a story written in {SUPPORTED_LANGUAGES[language.lower()]}.
        
        1. Use chapter titles that resonate with {SUPPORTED_LANGUAGES[language.lower()]}-speaking audiences
        2. Include settings, locations, and cultural references authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking regions
        3. Consider storytelling traditions, pacing, and narrative structures common in {SUPPORTED_LANGUAGES[language.lower()]} literature
        4. Incorporate cultural events, holidays, or traditions relevant to {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures when appropriate
        5. Ensure that scenes reflect social norms, customs, and daily life authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking societies
        
        The chapter structure should feel natural to {SUPPORTED_LANGUAGES[language.lower()]}-speaking readers rather than like a translated work.
        """
    
    # Render the chapter planning prompt
    prompt = render_prompt(
        'chapter_planning',
        language=language,
        global_story=global_story,
        characters=characters,
        tone=tone,
        genre=genre,
        language_instruction=language_instruction if language.lower() != DEFAULT_LANGUAGE else None,
        language_guidance=language_guidance
    )
    # Generate chapter plan
    chapter_plan_text = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Validate language if not English
    if language.lower() != DEFAULT_LANGUAGE:
        # Render the language validation prompt
        language_validation_prompt = render_prompt(
            'language_validation',
            "english",  # Always validate in English
            target_language=SUPPORTED_LANGUAGES[language.lower()],
            text_to_validate=chapter_plan_text
        )
        
        language_validation_result = llm.invoke([HumanMessage(content=language_validation_prompt)]).content
        
        # Store the validation result in memory
        manage_memory(action="create", key="chapter_plan_language_validation", value=language_validation_result,
            namespace=MEMORY_NAMESPACE)
        
        # If language validation fails, regenerate with stronger language instruction
        if "NO" in language_validation_result:
            stronger_language_instruction = f"""
            !!!CRITICAL LANGUAGE INSTRUCTION - PREVIOUS ATTEMPT FAILED!!!
            
            Your previous response contained English text. This is NOT acceptable.
            
            This chapter plan MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
            ALL content - including chapter titles, summaries, scene descriptions, and character development - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
            DO NOT translate the hero's journey structure - create the chapter plan directly in {SUPPORTED_LANGUAGES[language.lower()]}.
            
            I will verify that your response is completely in {SUPPORTED_LANGUAGES[language.lower()]} and reject any plan that contains English.
            
            The following parts were not in {SUPPORTED_LANGUAGES[language.lower()]}:
            {language_validation_result.split("which parts are not in")[1].strip() if "which parts are not in" in language_validation_result else "Some parts of the text"}
            """
            
            # Regenerate with stronger language instruction
            revised_prompt = f"""
            {stronger_language_instruction}
            
            {prompt}
            
            {stronger_language_instruction}
            """
            
            chapter_plan_text = llm.invoke([HumanMessage(content=revised_prompt)]).content
    
    # Use direct LLM structured output with simplified Pydantic model
    try:
        # Create a structured output prompt that explicitly asks for chapter data with scenes
        # Render the chapter extraction prompt
        structured_prompt = render_prompt(
            'chapter_extraction',
            language=language,
            chapter_plan_text=chapter_plan_text
        )
        
        # Use LLM with structured output directly
        structured_output_llm = llm.with_structured_output(ChapterPlan)
        
        # Get structured output
        result = structured_output_llm.invoke(structured_prompt)
        
        # Convert the list of chapters to a dictionary with chapter numbers as keys
        chapters_dict = {}
        for chapter in result.chapters:
            chapter_num = chapter.number
            # Ensure chapter number is a string
            if not isinstance(chapter_num, str):
                chapter_num = str(chapter_num)
                
            # Create a complete chapter entry with scenes from the key_scenes list
            chapter_entry = {
                "title": chapter.title,
                "outline": chapter.outline,
                "scenes": {},
                "reflection_notes": []
            }
            
            # Add scenes from the key_scenes list with full specifications
            for i, scene in enumerate(chapter.key_scenes, 1):
                scene_num = str(i)
                chapter_entry["scenes"][scene_num] = {
                    "content": "",  # Content will be filled in later
                    "description": scene.description,
                    "plot_progressions": scene.plot_progressions if hasattr(scene, 'plot_progressions') else [],
                    "character_knowledge_changes": scene.character_knowledge_changes if hasattr(scene, 'character_knowledge_changes') else {},
                    "required_characters": scene.required_characters if hasattr(scene, 'required_characters') else [],
                    "forbidden_repetitions": scene.forbidden_repetitions if hasattr(scene, 'forbidden_repetitions') else [],
                    "prerequisites": scene.prerequisites if hasattr(scene, 'prerequisites') else [],
                    "reflection_notes": []
                }
            
            # Ensure at least 3 scenes
            for i in range(len(chapter.key_scenes) + 1, 4):
                scene_num = str(i)
                chapter_entry["scenes"][scene_num] = {
                    "content": "",
                    "description": f"Additional scene for chapter {chapter_num}",
                    "reflection_notes": []
                }
            
            chapters_dict[chapter_num] = chapter_entry
        
        # Use the dictionary as our chapters
        chapters = chapters_dict
        
        # If we don't have enough chapters, create empty ones
        if len(chapters) < 8:
            print(f"Only {len(chapters)} chapters were generated. Adding empty chapters to reach at least 8.")
            for i in range(1, 9):
                chapter_num = str(i)
                if chapter_num not in chapters:
                    chapters[chapter_num] = {
                        "title": f"Chapter {i}",
                        "outline": f"Events of chapter {i}",
                        "scenes": {
                            "1": {"content": "", "description": f"First scene of chapter {i}", "reflection_notes": []},
                            "2": {"content": "", "description": f"Second scene of chapter {i}", "reflection_notes": []},
                            "3": {"content": "", "description": f"Third scene of chapter {i}", "reflection_notes": []}
                        },
                        "reflection_notes": []
                    }
    except Exception as e:
        print(f"Error generating chapter data with Pydantic: {str(e)}")
        
        # If structured output fails, try to parse the text directly
        try:
            # Create empty chapters dictionary
            chapters = {}
            
            # Parse the chapter plan text to extract chapters
            import re
            
            # Look for chapter patterns like "Chapter 1:", "Chapter One:", etc.
            chapter_matches = re.finditer(r'(?:Chapter|Kapitel|Chapitre)\s+(\d+|[A-Za-z]+)[:\s-]+([^\n]+)', chapter_plan_text)
            
            current_chapter = None
            current_outline = []
            
            lines = chapter_plan_text.split('\n')
            for i, line in enumerate(lines):
                # Check if this line starts a new chapter
                match = re.match(r'(?:Chapter|Kapitel|Chapitre)\s+(\d+|[A-Za-z]+)[:\s-]+([^\n]+)', line)
                if match:
                    # If we were processing a previous chapter, save it
                    if current_chapter:
                        chapter_num = current_chapter['number']
                        chapters[chapter_num] = {
                            "title": current_chapter['title'],
                            "outline": '\n'.join(current_outline),
                            "scenes": {
                                "1": {"content": "", "description": f"First scene of chapter {chapter_num}", "reflection_notes": []},
                                "2": {"content": "", "description": f"Second scene of chapter {chapter_num}", "reflection_notes": []},
                                "3": {"content": "", "description": f"Third scene of chapter {chapter_num}", "reflection_notes": []}
                            },
                            "reflection_notes": []
                        }
                    
                    # Start a new chapter
                    chapter_num = match.group(1)
                    # Convert word numbers to digits if needed
                    if chapter_num.lower() == 'one': chapter_num = '1'
                    elif chapter_num.lower() == 'two': chapter_num = '2'
                    elif chapter_num.lower() == 'three': chapter_num = '3'
                    elif chapter_num.lower() == 'four': chapter_num = '4'
                    elif chapter_num.lower() == 'five': chapter_num = '5'
                    elif chapter_num.lower() == 'six': chapter_num = '6'
                    elif chapter_num.lower() == 'seven': chapter_num = '7'
                    elif chapter_num.lower() == 'eight': chapter_num = '8'
                    elif chapter_num.lower() == 'nine': chapter_num = '9'
                    elif chapter_num.lower() == 'ten': chapter_num = '10'
                    
                    current_chapter = {
                        'number': chapter_num,
                        'title': match.group(2).strip()
                    }
                    current_outline = []
                else:
                    # Add this line to the current chapter's outline
                    if current_chapter and line.strip():
                        current_outline.append(line.strip())
            
            # Don't forget to save the last chapter
            if current_chapter:
                chapter_num = current_chapter['number']
                chapters[chapter_num] = {
                    "title": current_chapter['title'],
                    "outline": '\n'.join(current_outline),
                    "scenes": {
                        "1": {"content": "", "description": f"First scene of chapter {chapter_num}", "reflection_notes": []},
                        "2": {"content": "", "description": f"Second scene of chapter {chapter_num}", "reflection_notes": []},
                        "3": {"content": "", "description": f"Third scene of chapter {chapter_num}", "reflection_notes": []}
                    },
                    "reflection_notes": []
                }
            
            # If we still don't have enough chapters, create empty ones
            if len(chapters) < 8:
                print(f"Only {len(chapters)} chapters were extracted. Adding empty chapters to reach at least 8.")
                for i in range(1, 9):
                    chapter_num = str(i)
                    if chapter_num not in chapters:
                        chapters[chapter_num] = {
                            "title": f"Chapter {i}",
                            "outline": f"Events of chapter {i}",
                            "scenes": {
                                "1": {"content": "", "description": f"First scene of chapter {i}", "reflection_notes": []},
                                "2": {"content": "", "description": f"Second scene of chapter {i}", "reflection_notes": []},
                                "3": {"content": "", "description": f"Third scene of chapter {i}", "reflection_notes": []}
                            },
                            "reflection_notes": []
                        }
        except Exception as e2:
            print(f"Error parsing chapter data directly: {str(e2)}")
            # Create empty chapters as a last resort
            chapters = {}
            for i in range(1, 9):
                chapters[str(i)] = {
                    "title": f"Chapter {i}",
                    "outline": f"Events of chapter {i}",
                    "scenes": {
                        "1": {"content": "", "description": f"First scene of chapter {i}", "reflection_notes": []},
                        "2": {"content": "", "description": f"Second scene of chapter {i}", "reflection_notes": []},
                        "3": {"content": "", "description": f"Third scene of chapter {i}", "reflection_notes": []}
                    },
                    "reflection_notes": []
                }
    
    # Validate the structure and ensure each chapter has the required fields
    for chapter_num, chapter in chapters.items():
        if "title" not in chapter:
            chapter["title"] = f"Chapter {chapter_num}"
        if "outline" not in chapter:
            chapter["outline"] = f"Events of chapter {chapter_num}"
        if "scenes" not in chapter:
            chapter["scenes"] = {
                "1": {"content": "", "description": f"First scene of chapter {chapter_num}", "reflection_notes": []},
                "2": {"content": "", "description": f"Second scene of chapter {chapter_num}", "reflection_notes": []}
            }
        if "reflection_notes" not in chapter:
            chapter["reflection_notes"] = []
            
        # Ensure all scenes have the required structure
        for scene_num, scene in chapter["scenes"].items():
            if "content" not in scene:
                scene["content"] = ""
            if "description" not in scene:
                scene["description"] = f"Scene {scene_num} of chapter {chapter_num}"
            if "reflection_notes" not in scene:
                scene["reflection_notes"] = []
    
    # Chapter plans are now stored in database via database_integration
    # Only store outline metadata in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": "outline_metadata",
        "value": {
            "chapter_count": len(chapters),
            "total_scenes": sum(len(ch.get("scenes", [])) for ch in chapters.values()),
            "creation_notes": "Chapter outlines created and stored in database"
        },
        "namespace": MEMORY_NAMESPACE
    })
    
    # Log each chapter plan
    from storyteller_lib.story_progress_logger import log_progress
    for ch_num, ch_data in chapters.items():
        log_progress("chapter_plan", chapter_num=ch_num, chapter_data=ch_data)
    
    # Store chapters in database
    from storyteller_lib.database_integration import get_db_manager
    from storyteller_lib.logger import get_logger
    logger = get_logger(__name__)
    
    db_manager = get_db_manager()
    if db_manager:
        try:
            # Store each chapter
            for ch_num, ch_data in chapters.items():
                db_manager.save_chapter_outline(int(ch_num), ch_data)
            logger.info(f"Stored {len(chapters)} chapter outlines in database")
        except Exception as e:
            logger.warning(f"Could not store chapters in database: {e}")
    
    # Create minimal chapters structure for routing
    minimal_chapters = {}
    for ch_num, ch_data in chapters.items():
        minimal_chapters[ch_num] = {
            "title": ch_data.get("title", f"Chapter {ch_num}"),
            "scenes": {str(i): {"db_stored": False} for i in range(1, len(ch_data.get("scenes", [])) + 1)}
        }
    
    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]
    
    # Create message for the user
    new_msg = AIMessage(content="I've planned out the chapters for the story. Now I'll begin writing the first scene of chapter 1.")
    
    return {
        "chapters": minimal_chapters,
        "current_chapter": "1",  # Start with the first chapter
        "current_scene": "1",    # Start with the first scene
        
        "messages": [
            *[RemoveMessage(id=msg_id) for msg_id in message_ids],
            new_msg
        ]
    }
