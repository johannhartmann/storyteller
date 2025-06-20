"""
StoryCraft Agent - Story outline and planning nodes.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from storyteller_lib.config import llm, MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState
# Memory manager imports removed - using state and database instead
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from storyteller_lib import track_progress
from storyteller_lib.plot_threads import PlotThread, THREAD_IMPORTANCE, THREAD_STATUS


# Flattened model to avoid nested dictionaries
class StoryOutlineFlat(BaseModel):
    """Flattened story outline for structured output without nested dictionaries."""
    title: str = Field(description="A captivating title for the story")
    main_character_names: str = Field(description="Comma-separated list of 3-5 main character names")
    main_character_descriptions: str = Field(description="Pipe-separated list of character descriptions matching the order of names")
    central_conflict: str = Field(description="The central conflict or challenge of the story (or central question for non-conflict structures)")
    world_setting: str = Field(description="The world/setting where the story takes place")
    key_themes_csv: str = Field(description="Comma-separated list of key themes or messages")
    story_phase_names: str = Field(description="Pipe-separated list of story phase/section names")
    story_phase_descriptions: str = Field(description="Pipe-separated list of phase descriptions matching the order of phase names")

# Pydantic models for validation responses
class ValidationResult(BaseModel):
    """Result of a validation check."""
    is_valid: bool = Field(description="Whether the validation passed (YES) or failed (NO)")
    score: int = Field(ge=1, le=10, description="Validation score from 1-10")
    issues: List[str] = Field(default_factory=list, description="List of specific issues found")
    suggestions: str = Field(default="", description="Suggestions for improvement")


# Pydantic model for author style analysis
class AuthorStyleAnalysis(BaseModel):
    """Analysis of an author's writing style."""
    narrative_style: str = Field(description="Description of the author's narrative style and techniques")
    character_development: str = Field(description="How the author typically develops characters")
    dialogue_patterns: str = Field(description="The author's approach to dialogue and character voice")
    thematic_elements: str = Field(description="Common themes and motifs in the author's work")
    pacing_rhythm: str = Field(description="The author's typical pacing and story rhythm")
    descriptive_approach: str = Field(description="How the author handles descriptions and world-building")
    unique_elements: str = Field(description="Unique or signature elements of the author's style")
    emotional_tone: str = Field(description="The emotional tone and atmosphere the author typically creates")


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


@track_progress
def generate_story_outline(state: StoryState) -> Dict:
    """Generate the overall story outline using the selected narrative structure."""
    # Import dependencies at the start
    from storyteller_lib.logger import get_logger
    from storyteller_lib.database_integration import get_db_manager
    from storyteller_lib.story_progress_logger import log_progress
    from storyteller_lib.prompt_templates import render_prompt
    
    logger = get_logger(__name__)
    
    # Load configuration from database
    from storyteller_lib.config import get_story_config
    config = get_story_config()
    
    genre = config["genre"]
    tone = config["tone"]
    author = config["author"]
    initial_idea = config["initial_idea"]
    language = config["language"]
    
    # Get narrative structure from state or database
    narrative_structure = state.get("narrative_structure", "hero_journey")
    db_manager = get_db_manager()
    if db_manager and not narrative_structure:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT narrative_structure FROM story_config WHERE id = 1")
            result = cursor.fetchone()
            if result and result['narrative_structure']:
                narrative_structure = result['narrative_structure']
    
    logger.info(f"Generating story outline using {narrative_structure} structure")
    
    # Get temporary workflow data from state
    initial_idea_elements = state.get("initial_idea_elements", {})
    author_style_guidance = state.get("author_style_guidance", "")
    creative_elements = state.get("creative_elements", {})
    
    print(f"[DEBUG] generate_story_outline: language from config = '{language}'")
    print(f"[DEBUG] generate_story_outline: DEFAULT_LANGUAGE = '{DEFAULT_LANGUAGE}'")
    
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
            
            # Use structured output for author style analysis
            structured_llm = llm.with_structured_output(AuthorStyleAnalysis)
            style_analysis = structured_llm.invoke(author_prompt)
            
            # Format the analysis into guidance text
            author_style_guidance = f"""
Narrative Style: {style_analysis.narrative_style}

Character Development: {style_analysis.character_development}

Dialogue Patterns: {style_analysis.dialogue_patterns}

Thematic Elements: {style_analysis.thematic_elements}

Pacing and Rhythm: {style_analysis.pacing_rhythm}

Descriptive Approach: {style_analysis.descriptive_approach}

Unique Elements: {style_analysis.unique_elements}

Emotional Tone: {style_analysis.emotional_tone}
"""
            
            # Update state with the generated guidance
            state["author_style_guidance"] = author_style_guidance
        
        # Format style guidance based on language
        if language.lower() == 'german':
            style_guidance = f"""
        AUTORSTIL-ANLEITUNG:
        Sie werden den Schreibstil von {author} nachahmen. Hier ist eine Anleitung zu diesem Autorstil:
        
        {author_style_guidance}
        
        Integrieren Sie diese stilistischen Elemente in Ihre Geschichte, während Sie die Struktur der Heldenreise beibehalten.
        """
        else:
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
        if language.lower() == 'german':
            creative_guidance = f"""
        KREATIVE ELEMENTE AUS DEM BRAINSTORMING:
        
        Empfohlenes Storykonzept:
        {story_concept}
        
        Empfohlene Weltbau-Elemente:
        {world_building}
        
        Empfohlener zentraler Konflikt:
        {conflict}
        
        Integrieren Sie diese erarbeiteten Elemente in Ihre Geschichte und passen Sie sie nach Bedarf an die Struktur der Heldenreise an.
        """
        else:
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
        DO NOT translate the narrative structure - create the outline directly in {SUPPORTED_LANGUAGES[language.lower()]}.
        
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
        'language_guidance': language_guidance,
        'language_instruction': language_instruction
    }
    
    # Determine which template to use based on narrative structure
    template_name = f'story_outline_{narrative_structure}'
    
    # Render the prompt using the structure-specific template
    prompt = render_prompt(template_name, language=language, **template_vars)
    
    # Generate the story outline using structured output
    print(f"[DEBUG] About to generate story outline. Prompt length: {len(prompt)}")
    logger.info("Generating story outline with LLM...")
    logger.debug(f"Prompt length: {len(prompt)}")
    
    # Use structured output only - no fallback
    print("[DEBUG] Calling LLM with structured output...")
    
    # Always use flattened model to avoid nested dictionaries
    structured_llm = llm.with_structured_output(StoryOutlineFlat)
    outline_flat = structured_llm.invoke(prompt)
    
    # Convert flattened output to text format
    story_outline = f"Title: {outline_flat.title}\n\n"
    
    story_outline += "Main Characters:\n"
    names = [n.strip() for n in outline_flat.main_character_names.split(",")]
    descriptions = [d.strip() for d in outline_flat.main_character_descriptions.split("|")]
    for name, desc in zip(names, descriptions):
        story_outline += f"- {name}: {desc}\n"
    
    story_outline += f"\nCentral Conflict: {outline_flat.central_conflict}\n"
    story_outline += f"\nWorld/Setting: {outline_flat.world_setting}\n"
    
    story_outline += "\nKey Themes:\n"
    themes = [t.strip() for t in outline_flat.key_themes_csv.split(",") if t.strip()]
    for theme in themes:
        story_outline += f"- {theme}\n"
    
    story_outline += f"\nStory Structure ({narrative_structure.replace('_', ' ').title()}):\n"
    phase_names = [n.strip() for n in outline_flat.story_phase_names.split("|")]
    phase_descriptions = [d.strip() for d in outline_flat.story_phase_descriptions.split("|")]
    for i, (name, desc) in enumerate(zip(phase_names, phase_descriptions), 1):
        story_outline += f"\n{i}. {name}\n{desc}\n"
    
    print(f"[DEBUG] Story outline length: {len(story_outline)}")
    logger.info(f"Generated structured story outline with length: {len(story_outline)}")
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
        
        # Use structured output for validation
        structured_llm = llm.with_structured_output(ValidationResult)
        language_validation_result = structured_llm.invoke(language_validation_prompt)
        validation_results["language"] = language_validation_result
        
        # Store the validation result in memory
        # Language validation is temporary and used immediately
    
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
        
        # Use structured output for validation
        structured_llm = llm.with_structured_output(ValidationResult)
        idea_validation_result = structured_llm.invoke(idea_validation_prompt)
        validation_results["initial_idea"] = idea_validation_result
        
        # Store the validation result in memory
        # Idea validation is temporary and used immediately
    
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
    
    # Use structured output for validation
    structured_llm = llm.with_structured_output(ValidationResult)
    genre_validation_result = structured_llm.invoke(genre_validation_prompt)
    validation_results["genre"] = genre_validation_result
    
    # Store the validation result in memory
    # Genre validation is temporary and used immediately
    
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
        
        # Use structured output for validation
        structured_llm = llm.with_structured_output(ValidationResult)
        setting_validation_result = structured_llm.invoke(setting_validation_prompt)
        validation_results["setting"] = setting_validation_result
        
        # Store the validation result in memory
        # Setting validation is temporary and used immediately
    # Determine if we need to regenerate the outline based on validation results
    needs_regeneration = False
    improvement_guidance = ""
    
    # Check language validation first if not English
    if language.lower() != DEFAULT_LANGUAGE and "language" in validation_results:
        result = validation_results["language"]
        if not result.is_valid or result.score < 8:
            needs_regeneration = True
            improvement_guidance += "LANGUAGE ISSUES:\n"
            improvement_guidance += "The outline must be written ENTIRELY in " + SUPPORTED_LANGUAGES[language.lower()] + ".\n"
            if result.issues:
                improvement_guidance += "Issues found:\n"
                for issue in result.issues:
                    improvement_guidance += f"- {issue}\n"
            improvement_guidance += f"\nSuggestions: {result.suggestions}\n\n"
    
    # Check initial idea validation
    if "initial_idea" in validation_results:
        result = validation_results["initial_idea"]
        # Regenerate if validation failed or score is below 8
        if not result.is_valid or result.score < 8:
            needs_regeneration = True
            improvement_guidance += "INITIAL IDEA INTEGRATION ISSUES:\n"
            if result.issues:
                improvement_guidance += "Issues found:\n"
                for issue in result.issues:
                    improvement_guidance += f"- {issue}\n"
            improvement_guidance += f"\nSuggestions: {result.suggestions}\n\n"
    
    # Check genre validation
    if "genre" in validation_results:
        result = validation_results["genre"]
        if not result.is_valid or result.score < 8:
            needs_regeneration = True
            improvement_guidance += f"GENRE ({genre}) ISSUES:\n"
            if result.issues:
                improvement_guidance += "Issues found:\n"
                for issue in result.issues:
                    improvement_guidance += f"- {issue}\n"
            improvement_guidance += f"\nSuggestions: {result.suggestions}\n\n"
    
    # Check setting validation
    if "setting" in validation_results:
        result = validation_results["setting"]
        if not result.is_valid or result.score < 8:
            needs_regeneration = True
            improvement_guidance += "SETTING ISSUES:\n"
            if result.issues:
                improvement_guidance += "Issues found:\n"
                for issue in result.issues:
                    improvement_guidance += f"- {issue}\n"
            improvement_guidance += f"\nSuggestions: {result.suggestions}\n\n"
    
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
        
        # Use structured output for final verification
        structured_llm = llm.with_structured_output(ValidationResult)
        final_verification_result = structured_llm.invoke(final_verification_prompt)
        print(f"[DEBUG] Final verification result: is_valid={final_verification_result.is_valid}, score={final_verification_result.score}")
        # If the outline still doesn't meet requirements, try one more time with additional guidance
        print(f"[DEBUG] Checking if validation failed: {not final_verification_result.is_valid or final_verification_result.score < 8}")
        if not final_verification_result.is_valid or final_verification_result.score < 8:
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
            Score: {final_verification_result.score}/10
            Issues:
{chr(10).join(f'            - {issue}' for issue in final_verification_result.issues) if final_verification_result.issues else '            No specific issues listed'}
            
            Suggestions: {final_verification_result.suggestions}
            
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
        
        # Revised outline is stored in state, validation results are temporary
        
    # Ensure we have a story outline to store
    # print(f"[DEBUG] Final check - story_outline length: {len(story_outline) if story_outline else 0}")
    # print(f"[DEBUG] Final check - story_outline type: {type(story_outline)}")
    if not story_outline:
        logger.error("CRITICAL: story_outline is empty after all generation attempts!")
        # print("[DEBUG] story_outline is empty or None!")
        # Outline should always be in state at this point
        # If missing, there's a critical error in the workflow
        if not story_outline:
            # Generate a minimal outline as last resort
            logger.error("Generating emergency fallback outline...")
            story_outline = f"Emergency outline for {genre} story with {tone} tone. This should not happen."
    
    # Story outline is stored in database via db_manager.update_global_story()
    logger.info(f"Story outline ready for database storage. Length: {len(story_outline)}")
    
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
    
    # Outline generation metadata is tracked through the state and database
    
    # Create a temporary state with author_style_guidance for book instruction generation
    temp_state = dict(state)
    temp_state["author_style_guidance"] = author_style_guidance
    
    # Generate book-level instructions after outline is created
    from storyteller_lib.instruction_synthesis import generate_book_level_instructions
    book_instructions = generate_book_level_instructions(temp_state)
    logger.info("Generated book-level writing instructions")
    
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
        
        # Store book-level instructions in the database
        db_manager.update_book_level_instructions(book_instructions)
        logger.info("Book-level instructions stored in database")
        
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
        "book_level_instructions": book_instructions,  # Add book-level instructions to state
        "author_style_guidance": author_style_guidance,  # Include author style guidance in state
        "messages": [
            *[RemoveMessage(id=msg_id) for msg_id in message_ids],
            new_msg
        ]
    }


    
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

# Flattened models to avoid nested dictionaries
class FlatSceneSpec(BaseModel):
    """Flattened scene specification for structured output without nested dictionaries."""
    chapter_number: str = Field(..., description="The chapter number this scene belongs to")
    scene_number: int = Field(..., description="The scene number within the chapter")
    description: str = Field(..., description="Brief description of what happens in this scene")
    scene_type: str = Field(..., description="Type of scene: action, dialogue, exploration, revelation, character_moment, transition, conflict, resolution")
    plot_progressions_csv: str = Field(default="", description="Comma-separated list of plot points that MUST happen")
    character_learns_csv: str = Field(default="", description="Comma-separated list of what characters learn")
    required_characters_csv: str = Field(default="", description="Comma-separated list of characters who must appear")
    forbidden_repetitions_csv: str = Field(default="", description="Comma-separated list of plot points that must NOT be repeated")
    dramatic_purpose: str = Field(default="development", description="Primary dramatic purpose: setup, rising_action, climax, falling_action, resolution")
    tension_level: int = Field(default=5, ge=1, le=10, description="Tension level from 1 (calm) to 10 (maximum tension)")
    ends_with: str = Field(default="transition", description="How scene should end: cliffhanger, resolution, soft_transition, hard_break")
    connects_to_next: str = Field(default="", description="How this scene connects to the next one narratively")

class FlatChapter(BaseModel):
    """Flattened chapter model for structured output without nested dictionaries."""
    number: str = Field(..., description="The chapter number (as a string)")
    title: str = Field(..., description="The title of the chapter")
    outline: str = Field(..., description="Detailed summary of the chapter (200-300 words)")
    scene_count: int = Field(..., description="Number of scenes in this chapter")

class FlatChapterPlan(BaseModel):
    """Flattened chapter plan for structured output without nested dictionaries."""
    chapters: List[FlatChapter] = Field(..., description="List of chapters without nested scenes")
    total_scenes: List[FlatSceneSpec] = Field(..., description="All scenes in the story, flattened")

@track_progress
def plan_chapters(state: StoryState) -> Dict:
    """Divide the story into chapters with detailed outlines."""
    from storyteller_lib.prompt_templates import render_prompt
    from storyteller_lib.narrative_structures import get_structure_by_name
    
    # Load configuration from database
    from storyteller_lib.config import get_story_config
    from storyteller_lib.database_integration import get_db_manager
    from storyteller_lib.logger import get_logger
    
    logger = get_logger(__name__)
    
    config = get_story_config()
    genre = config["genre"]
    tone = config["tone"]
    language = config["language"]
    
    # Get narrative structure and targets from state
    narrative_structure = state.get("narrative_structure", "hero_journey")
    target_chapters = state.get("target_chapters", 12)
    target_scenes_per_chapter = state.get("target_scenes_per_chapter", 5)
    
    # Get global_story from database
    global_story = ""
    db_manager = get_db_manager()
    if db_manager and db_manager._db:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT global_story FROM story_config WHERE id = 1")
            result = cursor.fetchone()
            if result:
                global_story = result['global_story'] or ""
    
    if not global_story:
        raise ValueError("No story outline found in database")
    
    characters = state["characters"]
    
    # Get the narrative structure object for guidance
    structure = get_structure_by_name(narrative_structure)
    chapter_distribution = {}
    
    if structure:
        # Get chapter distribution for this structure
        distribution = structure.get_chapter_distribution()
        chapter_distribution = distribution.get_chapter_counts(target_chapters)
        logger.info(f"Using {narrative_structure} structure with {target_chapters} chapters")
    
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
        narrative_structure=narrative_structure,
        target_chapters=target_chapters,
        min_chapters=max(5, target_chapters - 3),  # Allow some flexibility
        flexibility=2,  # Allow ±2 chapters
        chapter_distribution=chapter_distribution,  # Pass the raw data to template
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
        # Language validation is temporary and used immediately
        
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
        
        # Always use flattened model to avoid nested dictionaries
        structured_output_llm = llm.with_structured_output(FlatChapterPlan)
        
        # Get structured output
        result = structured_output_llm.invoke(structured_prompt)
        
        # Convert from flattened structure
        chapters_dict = {}
        
        # Convert from flattened structure
        # First, create chapters
        for chapter in result.chapters:
            chapter_num = chapter.number
            if not isinstance(chapter_num, str):
                chapter_num = str(chapter_num)
                
            chapters_dict[chapter_num] = {
                "title": chapter.title,
                "outline": chapter.outline,
                "scenes": {},
                "reflection_notes": []
            }
        
        # Then add scenes to their respective chapters
        for scene in result.total_scenes:
            chapter_num = scene.chapter_number
            scene_num = str(scene.scene_number)
            
            if chapter_num in chapters_dict:
                chapters_dict[chapter_num]["scenes"][scene_num] = {
                    "content": "",
                    "description": scene.description,
                    "scene_type": scene.scene_type,
                    "plot_progressions": [s.strip() for s in scene.plot_progressions_csv.split(",") if s.strip()] if scene.plot_progressions_csv else [],
                    "character_learns": [s.strip() for s in scene.character_learns_csv.split(",") if s.strip()] if scene.character_learns_csv else [],
                    "required_characters": [s.strip() for s in scene.required_characters_csv.split(",") if s.strip()] if scene.required_characters_csv else [],
                    "forbidden_repetitions": [s.strip() for s in scene.forbidden_repetitions_csv.split(",") if s.strip()] if scene.forbidden_repetitions_csv else [],
                    "dramatic_purpose": scene.dramatic_purpose,
                    "tension_level": scene.tension_level,
                    "ends_with": scene.ends_with,
                    "connects_to_next": scene.connects_to_next,
                    "reflection_notes": []
                }
        
        # Use the dictionary as our chapters
        chapters = chapters_dict
        
        # Fail if we don't have enough chapters
        min_chapters = max(5, target_chapters - 3)
        if len(chapters) < min_chapters:
            raise RuntimeError(f"Only {len(chapters)} chapters were generated. At least {min_chapters} chapters are required for this story structure.")
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
                        # Fail - we should not create scenes without proper descriptions
                        raise RuntimeError(f"Chapter planning failed: No scene descriptions were generated for chapter {chapter_num}. Structured output is required.")
                    
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
                # Fail - we should not create scenes without proper descriptions
                raise RuntimeError(f"Chapter planning failed: No scene descriptions were generated for chapter {chapter_num}. Structured output is required.")
            
            # Fail if we still don't have enough chapters
            min_chapters = max(5, target_chapters - 3)
            if len(chapters) < min_chapters:
                raise RuntimeError(f"Chapter planning failed: Only {len(chapters)} chapters were extracted. At least {min_chapters} chapters are required.")
        except Exception as e2:
            print(f"Error parsing chapter data directly: {str(e2)}")
            # Re-raise the error - no fallback allowed
            raise RuntimeError(f"Chapter planning failed completely: {str(e2)}. Cannot continue without proper scene descriptions.")
    
    # Validate the structure and ensure each chapter has the required fields
    for chapter_num, chapter in chapters.items():
        if "title" not in chapter:
            chapter["title"] = f"Chapter {chapter_num}"
        if "outline" not in chapter:
            chapter["outline"] = f"Events of chapter {chapter_num}"
        if "scenes" not in chapter:
            raise RuntimeError(f"Chapter {chapter_num} has no scenes. Cannot continue without proper scene descriptions.")
        if "reflection_notes" not in chapter:
            chapter["reflection_notes"] = []
            
        # Ensure all scenes have the required structure
        for scene_num, scene in chapter["scenes"].items():
            if "content" not in scene:
                scene["content"] = ""
            if "description" not in scene:
                raise RuntimeError(f"Scene {scene_num} of Chapter {chapter_num} has no description. Cannot continue without proper scene descriptions.")
            if "reflection_notes" not in scene:
                scene["reflection_notes"] = []
    
    # Chapter plans are now stored in database via database_integration
    # Outline metadata is tracked through state
    
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
    
    # Create a lightweight chapters structure with only planning data
    # Scene content will be stored in database, not in state
    planning_chapters = {}
    for ch_num, ch_data in chapters.items():
        planning_chapters[ch_num] = {
            "title": ch_data.get("title", f"Chapter {ch_num}"),
            # Don't include full outline - it's in the database
            "scenes": {}
        }
        
        # Only include essential planning data for each scene
        for scene_num, scene_data in ch_data.get("scenes", {}).items():
            planning_chapters[ch_num]["scenes"][scene_num] = {
                # Planning data only - no content
                "description": scene_data.get("description", ""),
                "plot_progressions": scene_data.get("plot_progressions", []),
                "character_learns": scene_data.get("character_learns", []),
                "required_characters": scene_data.get("required_characters", []),
                "forbidden_repetitions": scene_data.get("forbidden_repetitions", []),
                "dramatic_purpose": scene_data.get("dramatic_purpose", "development"),
                "tension_level": scene_data.get("tension_level", 5),
                "ends_with": scene_data.get("ends_with", "transition"),
                "connects_to_next": scene_data.get("connects_to_next", ""),
                # Flags for workflow
                "written": False,
                "db_stored": False
            }
    
    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]
    
    # Create message for the user
    new_msg = AIMessage(content="I've planned out the chapters for the story. Now I'll begin writing the first scene of chapter 1.")
    
    return {
        "chapters": planning_chapters,  # Lightweight structure with only planning data
        "current_chapter": "1",  # Start with the first chapter
        "current_scene": "1",    # Start with the first scene
        
        "messages": [
            *[RemoveMessage(id=msg_id) for msg_id in message_ids],
            new_msg
        ]
    }
