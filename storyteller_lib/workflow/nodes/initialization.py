"""
StoryCraft Agent - Initialization nodes.
"""

from typing import Dict

from storyteller_lib.core.config import (
    llm,
    MEMORY_NAMESPACE,
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
)
from storyteller_lib.core.models import StoryState

# Memory manager imports removed - using state and database instead
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.messages.modifier import RemoveMessage
from storyteller_lib import track_progress


@track_progress
def initialize_state(state: StoryState) -> Dict:
    """Initialize the story state with user input."""
    messages = state["messages"]

    # Load configuration from database
    from storyteller_lib.persistence.database import get_db_manager

    db_manager = get_db_manager()

    # Default values
    genre = "fantasy"
    tone = "epic"
    author = ""
    initial_idea = ""
    author_style_guidance = ""
    language = DEFAULT_LANGUAGE

    if db_manager:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT genre, tone, language, author, initial_idea 
                FROM story_config WHERE id = 1
            """
            )
            result = cursor.fetchone()
            if result:
                genre = result["genre"] or genre
                tone = result["tone"] or tone
                language = result["language"] or language
                author = result["author"] or ""
                initial_idea = result["initial_idea"] or ""

    print(f"[DEBUG] initialize_state: language from DB = '{language}'")
    print(f"[DEBUG] initialize_state: DEFAULT_LANGUAGE = '{DEFAULT_LANGUAGE}'")

    # Validate language and default to English if not supported
    if language.lower() not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE

    # Get initial idea elements from database or extract them if needed
    idea_elements = {}
    if db_manager and initial_idea:
        with db_manager._db._get_connection() as conn2:
            cursor2 = conn2.cursor()
            # Check if we have stored idea elements
            cursor2.execute(
                """
                SELECT value FROM memories 
                WHERE key = 'initial_idea_elements' AND namespace = 'storyteller'
            """
            )
            result = cursor2.fetchone()
            if result:
                import json

                try:
                    idea_elements = json.loads(result["value"])
                except:
                    pass

        # If we don't have elements yet, parse them
        if not idea_elements:
            from storyteller_lib.utils.parser import parse_initial_idea

            idea_elements = parse_initial_idea(initial_idea, language)

    # Initial idea is already stored in story_config table by database_integration
    # No need to duplicate in memory

    # If author guidance wasn't provided in the initial state, but we have an author, get it now
    if author and not author_style_guidance:
        # See if we have cached guidance
        try:
            # Author style caching removed - will generate fresh each time
            results = []

            # Extract the author style from the results
            author_style_object = None
            if results and len(results) > 0:
                for item in results:
                    if (
                        hasattr(item, "key")
                        and item.key
                        == f"author_style_{author.lower().replace(' ', '_')}"
                    ):
                        author_style_object = {"key": item.key, "value": item.value}
                        break

            if author_style_object and "value" in author_style_object:
                author_style_guidance = author_style_object["value"]
        except Exception:
            # If error, we'll generate it later
            pass

    # Prepare language-specific response message
    if language.lower() == "german":
        author_mention = f" im Stil von {author}" if author else ""
        idea_mention = f" mit der Idee: '{initial_idea}'" if initial_idea else ""
        response_message = f"Ich werde eine {tone} {genre}-Geschichte{author_mention}{idea_mention} für Sie erstellen. Lassen Sie mich mit der Planung der Erzählung beginnen..."
    else:
        # Default to English for other languages
        author_mention = f" in the style of {author}" if author else ""
        idea_mention = (
            f" implementing the idea: '{initial_idea}'" if initial_idea else ""
        )
        language_mention = (
            f" in {SUPPORTED_LANGUAGES[language.lower()]}"
            if language.lower() != DEFAULT_LANGUAGE
            else ""
        )
        response_message = f"I'll create a {tone} {genre} story{author_mention}{language_mention}{idea_mention} for you. Let me start planning the narrative..."

    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]

    # Initialize language-specific naming and cultural elements if not English
    if language.lower() != DEFAULT_LANGUAGE:
        # Use template system
        from storyteller_lib.prompts.renderer import render_prompt

        # Render the language elements prompt
        language_elements_prompt = render_prompt(
            "language_elements",
            language=language,
            target_language=SUPPORTED_LANGUAGES[language.lower()],
        )

        # Get structured language elements directly
        from storyteller_lib.core.config import get_llm_with_structured_output
        from pydantic import BaseModel, Field
        from typing import Dict, List

        class LanguageElements(BaseModel):
            """Language-specific cultural elements."""

            common_names: List[str] = Field(
                description="Common character names for this culture"
            )
            places: List[str] = Field(description="Typical place names")
            cultural_items: List[str] = Field(description="Cultural items and concepts")
            expressions: List[str] = Field(description="Common expressions and idioms")

        structured_llm = get_llm_with_structured_output(LanguageElements)
        language_elements_response = structured_llm.invoke(language_elements_prompt)

        # Convert to dictionary format
        language_elements = (
            language_elements_response.dict() if language_elements_response else {}
        )

        # Language elements will be passed through state instead of memory storage

        # Create a specific instruction to ensure language consistency
        language_consistency_instruction = f"""
            CRITICAL LANGUAGE CONSISTENCY INSTRUCTION:
            
            This story MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
            ALL content - including outlines, character descriptions, scene elements, reflections, and revisions - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
            DO NOT switch to any other language at ANY point in the story generation process.
            
            When writing in {SUPPORTED_LANGUAGES[language.lower()]}, ensure that:
            1. ALL text is in {SUPPORTED_LANGUAGES[language.lower()]} without ANY English phrases or words
            2. Character names must be authentic {SUPPORTED_LANGUAGES[language.lower()]} names
            3. Place names must follow {SUPPORTED_LANGUAGES[language.lower()]} naming conventions
            4. Cultural references must be appropriate for {SUPPORTED_LANGUAGES[language.lower()]}-speaking audiences
            5. Dialogue must use expressions and idioms natural to {SUPPORTED_LANGUAGES[language.lower()]}
            6. ALL planning, outlining, and internal notes are also in {SUPPORTED_LANGUAGES[language.lower()]}
            
            CRITICAL: Maintain {SUPPORTED_LANGUAGES[language.lower()]} throughout ALL parts of the story and ALL stages of the generation process without ANY exceptions.
            
            REMINDER: Even if you are analyzing, planning, or reflecting on the story, you MUST do so in {SUPPORTED_LANGUAGES[language.lower()]}.
            """

        # Language consistency instruction is temporary - no need to store

    # Select narrative structure after we have all the context
    from storyteller_lib.generation.story.narrative_structures import (
        NarrativeStructureAnalysis,
        get_structure_by_name,
        determine_story_length,
    )
    from storyteller_lib.prompts.renderer import render_prompt
    from storyteller_lib.core.logger import get_logger

    logger = get_logger(__name__)

    # Check if we already have a narrative structure set
    narrative_structure = None
    story_length = None
    target_chapters = None
    target_scenes_per_chapter = None
    target_words_per_scene = None
    target_pages = None

    if db_manager:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT narrative_structure, story_length, target_chapters, 
                       target_scenes_per_chapter, target_words_per_scene, target_pages
                FROM story_config WHERE id = 1
            """
            )
            result = cursor.fetchone()
            if result:
                narrative_structure = result["narrative_structure"]
                story_length = result["story_length"]
                target_chapters = result["target_chapters"]
                target_scenes_per_chapter = result["target_scenes_per_chapter"]
                target_words_per_scene = result["target_words_per_scene"]
                try:
                    target_pages = result["target_pages"]
                except (KeyError, IndexError):
                    target_pages = None  # May not exist in older DBs

    # If narrative structure is 'auto' or not set, determine it now
    if not narrative_structure or narrative_structure == "auto":
        logger.info("Selecting narrative structure based on story concept...")

        # Render the structure selection prompt
        structure_prompt = render_prompt(
            "narrative_structure_selection",
            language=language,  # Use the story's target language
            genre=genre,
            tone=tone,
            story_language=language,  # Language the story will be written in
            initial_idea=initial_idea,
            idea_elements=idea_elements if idea_elements else None,
        )

        # Get structured output for narrative structure
        structured_llm = llm.with_structured_output(NarrativeStructureAnalysis)
        structure_analysis = structured_llm.invoke(structure_prompt)

        # Extract the recommended values
        narrative_structure = structure_analysis.primary_structure
        story_complexity = structure_analysis.story_complexity

        # If pages are specified, calculate parameters from pages
        if target_pages:
            from storyteller_lib.generation.story.narrative_structures import (
                calculate_story_parameters_from_pages,
            )

            structure_obj = get_structure_by_name(narrative_structure)
            if not structure_obj:
                logger.warning(
                    f"Unknown narrative structure '{narrative_structure}', using hero_journey as fallback"
                )
                narrative_structure = "hero_journey"
                structure_obj = get_structure_by_name(narrative_structure)
            (
                story_length_enum,
                target_chapters,
                target_scenes_per_chapter,
                target_words_per_scene,
            ) = calculate_story_parameters_from_pages(target_pages, structure_obj)
            story_length = story_length_enum.value
            logger.info(
                f"Calculated from {target_pages} pages: {target_chapters} chapters, "
                f"{target_scenes_per_chapter} scenes/chapter, {target_words_per_scene} words/scene"
            )
        else:
            # Use AI recommendations
            story_length = structure_analysis.story_length
            target_chapters = structure_analysis.chapter_count
            target_scenes_per_chapter = structure_analysis.scenes_per_chapter
            target_words_per_scene = structure_analysis.words_per_scene

        # Create structure metadata
        structure_metadata = {
            "structure_reasoning": structure_analysis.structure_reasoning,
            "complexity": story_complexity,
            "complexity_reasoning": structure_analysis.complexity_reasoning,
            "length_reasoning": structure_analysis.length_reasoning,
            "customization": structure_analysis.structure_customization,
            "subplot_count": structure_analysis.subplot_count,
            "pov_count": structure_analysis.pov_count,
        }

        logger.info(f"Selected narrative structure: {narrative_structure}")
        logger.info(f"Story length: {story_length} ({target_chapters} chapters)")
        logger.info(f"Scenes per chapter: {target_scenes_per_chapter}")
        logger.info(f"Target words per scene: {target_words_per_scene}")

        # Save the structure selection to database
        if db_manager:
            import json

            with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE story_config SET 
                        narrative_structure = ?,
                        story_length = ?,
                        target_chapters = ?,
                        target_scenes_per_chapter = ?,
                        target_words_per_scene = ?,
                        structure_metadata = ?
                    WHERE id = 1
                """,
                    (
                        narrative_structure,
                        story_length,
                        target_chapters,
                        target_scenes_per_chapter,
                        target_words_per_scene,
                        json.dumps(structure_metadata),
                    ),
                )
                conn.commit()
    else:
        # Structure is already set (not 'auto'), but we might need to calculate from pages
        if target_pages and not target_chapters:
            # User specified pages but not chapters - calculate from pages
            from storyteller_lib.generation.story.narrative_structures import (
                calculate_story_parameters_from_pages,
            )

            structure_obj = get_structure_by_name(narrative_structure)
            if structure_obj:
                (
                    story_length_enum,
                    target_chapters,
                    target_scenes_per_chapter,
                    target_words_per_scene,
                ) = calculate_story_parameters_from_pages(target_pages, structure_obj)
                story_length = story_length_enum.value
                logger.info(
                    f"Using {narrative_structure} structure with {target_pages} pages: "
                    f"{target_chapters} chapters, {target_scenes_per_chapter} scenes/chapter, "
                    f"{target_words_per_scene} words/scene"
                )

                # Update database with calculated values
                if db_manager:
                    with db_manager._db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            UPDATE story_config SET 
                                story_length = ?,
                                target_chapters = ?,
                                target_scenes_per_chapter = ?,
                                target_words_per_scene = ?
                            WHERE id = 1
                        """,
                            (
                                story_length,
                                target_chapters,
                                target_scenes_per_chapter,
                                target_words_per_scene,
                            ),
                        )
                        conn.commit()

    # Log story parameters to progress log
    from storyteller_lib.utils.progress_logger import log_progress
    
    log_progress(
        "story_params",
        genre=genre,
        tone=tone,
        author=author,
        language=language,
        idea=initial_idea,
    )

    # Return only the workflow state updates
    # Configuration is already stored in database by storyteller.py
    result_state = {
        "messages": [
            *[RemoveMessage(id=msg_id) for msg_id in message_ids],
            AIMessage(content=response_message),
        ],
        "narrative_structure": narrative_structure,
        "target_chapters": target_chapters,
        "target_scenes_per_chapter": target_scenes_per_chapter,
    }

    # Add temporary fields if we have them
    if idea_elements:
        result_state["initial_idea_elements"] = idea_elements
    if author_style_guidance:
        result_state["author_style_guidance"] = author_style_guidance

    return result_state


@track_progress
def brainstorm_story_concepts(state: StoryState) -> Dict:
    """Brainstorm creative story concepts before generating the outline."""
    from storyteller_lib.generation.creative.brainstorming import creative_brainstorm
    from storyteller_lib.utils.progress_logger import log_progress

    # Load configuration from database
    from storyteller_lib.persistence.database import get_db_manager

    db_manager = get_db_manager()

    # Default values
    genre = "fantasy"
    tone = "adventurous"
    author = ""
    initial_idea = ""
    language = DEFAULT_LANGUAGE

    if db_manager:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT genre, tone, language, author, initial_idea 
                FROM story_config WHERE id = 1
            """
            )
            result = cursor.fetchone()
            if result:
                genre = result["genre"] or genre
                tone = result["tone"] or tone
                language = result["language"] or language
                author = result["author"] or ""
                initial_idea = result["initial_idea"] or ""

    # Get initial_idea_elements from state (was set by initialize_state)
    initial_idea_elements = state.get("initial_idea_elements", {})

    # If we still don't have elements but have an initial idea, parse it now
    if not initial_idea_elements and initial_idea:
        from storyteller_lib.utils.parser import parse_initial_idea

        initial_idea_elements = parse_initial_idea(initial_idea, language)

    # Get author_style_guidance from state (was set by initialize_state)
    author_style_guidance = state.get("author_style_guidance", "")

    # Generate enhanced context based on genre, tone, language, and initial idea

    # Generate enhanced context based on genre, tone, language, and initial idea
    idea_context = ""
    if initial_idea:
        # Create a more detailed context using the structured idea elements
        setting = initial_idea_elements.get("setting", "Unknown")
        characters = initial_idea_elements.get("characters", [])
        plot = initial_idea_elements.get("plot", "Unknown")
        themes = initial_idea_elements.get("themes", [])
        genre_elements = initial_idea_elements.get("genre_elements", [])

        # Just pass the initial idea - let templates handle formatting
        idea_context = initial_idea

        # Brainstorm context elements are already in state and passed to next nodes
    else:
        # When no initial idea is provided, we need to generate and select one
        print(
            f"[STORYTELLER] No initial idea provided - generating unique story concepts for {tone} {genre}..."
        )

        # First, brainstorm several potential story ideas
        from storyteller_lib.generation.creative.brainstorming import (
            creative_brainstorm as generate_ideas,
        )

        # Create genre-specific context to guide idea generation
        genre_context = f"We need unique and compelling story ideas for a {tone} {genre} story. The ideas should avoid clichés and bring fresh perspectives to the {genre} genre."

        if author:
            genre_context += f" The story will be written in the style of {author}."

        # Generate multiple story concept ideas
        initial_concepts = generate_ideas(
            topic="Unique Story Premises",
            genre=genre,
            tone=tone,
            context=genre_context,
            author=author,
            author_style_guidance=author_style_guidance,
            language=language,
            num_ideas=5,
            evaluation_criteria=[
                "Originality and uniqueness within the genre",
                "Potential for rich character development",
                "Opportunities for compelling conflict",
                "Avoidance of overused tropes",
                "Strong narrative hook",
            ],
        )

        # Extract the recommended idea and use it as our initial concept
        if initial_concepts and "recommended_ideas" in initial_concepts:
            selected_concept = initial_concepts["recommended_ideas"]
            print(f"[STORYTELLER] Selected story concept: {selected_concept[:200]}...")

            # Parse the selected concept to extract elements
            from storyteller_lib.utils.parser import parse_initial_idea

            initial_idea = selected_concept
            initial_idea_elements = parse_initial_idea(initial_idea, language)

            # Update the context with the selected idea
            idea_context = initial_idea

            # Store the selected concept in database
            if db_manager:
                with db_manager._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE story_config SET initial_idea = ? WHERE id = 1
                    """,
                        (initial_idea,),
                    )
                    conn.commit()
        else:
            # Fallback if idea generation fails
            print(
                f"[STORYTELLER] WARNING: Could not generate initial concepts - proceeding with generic {genre} story"
            )
            idea_context = ""

    # Just pass the idea context directly, let the template handle the formatting
    context = idea_context if idea_context else ""

    # Create constraints dictionary from initial idea elements
    constraints = {}

    # Now we always have initial_idea_elements, either from user input or generated
    if initial_idea_elements:
        constraints = {
            "setting": initial_idea_elements.get("setting", ""),
            "characters": ", ".join(initial_idea_elements.get("characters", [])),
            "plot": initial_idea_elements.get("plot", ""),
        }

        # Update state with the idea elements (whether user-provided or generated)
        state["initial_idea_elements"] = initial_idea_elements

        # Constraints are already in state and passed through the workflow
        # Genre requirement is enforced through prompts and state

    # Brainstorm different high-level story concepts
    brainstorm_results = creative_brainstorm(
        topic="Story Concept",
        genre=genre,
        tone=tone,
        context=context,
        author=author,
        author_style_guidance=author_style_guidance,
        language=language,
        num_ideas=5,
        evaluation_criteria=None,  # Let template use its own criteria
        constraints=constraints,
        strict_adherence=True,
    )

    # Brainstorm unique world-building elements
    world_building_results = creative_brainstorm(
        topic="World Building Elements",
        genre=genre,
        tone=tone,
        context=context,
        author=author,
        author_style_guidance=author_style_guidance,
        language=language,
        num_ideas=4,
        evaluation_criteria=None,  # Let template use its own criteria
        constraints=constraints,
        strict_adherence=True,
    )

    # Brainstorm central conflicts
    conflict_results = creative_brainstorm(
        topic="Central Conflict",
        genre=genre,
        tone=tone,
        context=context,
        author=author,
        author_style_guidance=author_style_guidance,
        language=language,
        num_ideas=3,
        evaluation_criteria=None,  # Let template use its own criteria
        constraints=constraints,
        strict_adherence=True,
    )

    # Validate that the brainstormed ideas adhere to the initial idea
    if initial_idea:
        # Use template system
        from storyteller_lib.prompts.renderer import render_prompt

        validation_prompt = render_prompt(
            "brainstorm_validation",
            language=language,
            initial_idea=initial_idea,
            story_concepts=brainstorm_results.get(
                "recommended_ideas", "No recommendations available"
            ),
            world_building=world_building_results.get(
                "recommended_ideas", "No recommendations available"
            ),
            central_conflicts=conflict_results.get(
                "recommended_ideas", "No recommendations available"
            ),
        )

        validation_result = llm.invoke(
            [HumanMessage(content=validation_prompt)]
        ).content

        # Validation result is temporary and included in state

    # Store all creative elements
    creative_elements = {
        "story_concepts": brainstorm_results,
        "world_building": world_building_results,
        "central_conflicts": conflict_results,
    }

    # Store the initial idea elements with the creative elements for easy reference
    if initial_idea_elements:
        creative_elements["initial_idea_elements"] = initial_idea_elements

    # Create language-specific messages
    if language.lower() == "german":
        idea_mention = f" basierend auf Ihrer Idee" if initial_idea else ""
        new_msg = AIMessage(
            content=f"Ich habe mehrere kreative Konzepte für Ihre {tone} {genre}-Geschichte{idea_mention} entwickelt. Jetzt werde ich eine zusammenhängende Gliederung basierend auf den vielversprechendsten Ideen entwickeln."
        )
    else:
        idea_mention = f" based on your idea" if initial_idea else ""
        new_msg = AIMessage(
            content=f"I've brainstormed several creative concepts for your {tone} {genre} story{idea_mention}. Now I'll develop a cohesive outline based on the most promising ideas."
        )

    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]

    # Log creative concepts
    log_progress(
        "creative_concepts",
        concepts={
            "story_concept": brainstorm_results.get("recommended_ideas", ""),
            "worldbuilding_ideas": world_building_results.get("recommended_ideas", ""),
            "central_conflict": conflict_results.get("recommended_ideas", ""),
        },
    )

    # Update state with brainstormed ideas
    return {
        "creative_elements": creative_elements,
        "messages": [*[RemoveMessage(id=msg_id) for msg_id in message_ids], new_msg],
    }
