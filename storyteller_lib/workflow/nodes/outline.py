"""
StoryCraft Agent - Story outline and planning nodes.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from storyteller_lib.core.config import (
    llm,
    MEMORY_NAMESPACE,
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
)
from storyteller_lib.core.models import StoryState

# Memory manager imports removed - using state and database instead
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from storyteller_lib import track_progress
from storyteller_lib.generation.story.plot_threads import (
    PlotThread,
    THREAD_IMPORTANCE,
    THREAD_STATUS,
)


# Flattened model to avoid nested dictionaries
class StoryOutlineFlat(BaseModel):
    """Flattened story outline for structured output without nested dictionaries."""

    title: str = Field(description="A captivating title for the story")
    main_character_names: str = Field(
        description="Comma-separated list of 3-5 main character names"
    )
    main_character_descriptions: str = Field(
        description="Pipe-separated list of character descriptions matching the order of names"
    )
    central_conflict: str = Field(
        description="The central conflict or challenge of the story (or central question for non-conflict structures)"
    )
    world_setting: str = Field(
        description="The world/setting where the story takes place"
    )
    key_themes_csv: str = Field(
        description="Comma-separated list of key themes or messages"
    )
    story_phase_names: str = Field(
        description="Pipe-separated list of story phase/section names"
    )
    story_phase_descriptions: str = Field(
        description="Pipe-separated list of phase descriptions matching the order of phase names"
    )


# Pydantic models for validation responses
class ValidationResult(BaseModel):
    """Result of a validation check."""

    is_valid: bool = Field(
        description="Whether the validation passed (YES) or failed (NO)"
    )
    score: int = Field(ge=1, le=10, description="Validation score from 1-10")
    issues: List[str] = Field(
        default_factory=list, description="List of specific issues found"
    )
    suggestions: str = Field(default="", description="Suggestions for improvement")


# Pydantic model for author style analysis
class AuthorStyleAnalysis(BaseModel):
    """Analysis of an author's writing style."""

    narrative_style: str = Field(
        description="Description of the author's narrative style and techniques"
    )
    character_development: str = Field(
        description="How the author typically develops characters"
    )
    dialogue_patterns: str = Field(
        description="The author's approach to dialogue and character voice"
    )
    thematic_elements: str = Field(
        description="Common themes and motifs in the author's work"
    )
    pacing_rhythm: str = Field(
        description="The author's typical pacing and story rhythm"
    )
    descriptive_approach: str = Field(
        description="How the author handles descriptions and world-building"
    )
    unique_elements: str = Field(
        description="Unique or signature elements of the author's style"
    )
    emotional_tone: str = Field(
        description="The emotional tone and atmosphere the author typically creates"
    )


# Flattened models to avoid nested dictionaries for chapter planning
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


def generate_plot_threads_from_outline(
    story_outline: str,
    genre: str,
    tone: str,
    initial_idea: str,
    language: str = DEFAULT_LANGUAGE,
) -> Dict[str, Dict]:
    """Generate initial plot threads from the story outline."""
    # Use template system
    from storyteller_lib.prompts.renderer import render_prompt

    # Render the plot threads prompt
    prompt = render_prompt(
        "plot_threads_from_outline",
        language=language,
        story_outline=story_outline,
        genre=genre,
        tone=tone,
        initial_idea=initial_idea,
    )

    # Define the structured output
    class PlotThreadDefinition(BaseModel):
        name: str = Field(description="A concise, memorable name for the thread")
        description: str = Field(
            description="What this thread is about (2-3 sentences)"
        )
        importance: str = Field(
            description="Thread importance: major, minor, or background"
        )
        related_characters: List[str] = Field(
            description="Character roles involved in this thread"
        )

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
            related_characters=thread_def.related_characters,
        )
        plot_threads[thread_def.name] = thread.to_dict()

    return plot_threads


@track_progress
def generate_story_outline(state: StoryState) -> Dict:
    """Generate the overall story outline using the selected narrative structure."""
    # Import dependencies at the start
    from storyteller_lib.core.logger import get_logger
    from storyteller_lib.persistence.database import get_db_manager
    from storyteller_lib.utils.progress_logger import log_progress
    from storyteller_lib.prompts.renderer import render_prompt

    logger = get_logger(__name__)

    # Load configuration from database
    from storyteller_lib.core.config import get_story_config

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
            if result and result["narrative_structure"]:
                narrative_structure = result["narrative_structure"]

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
            from storyteller_lib.prompts.renderer import render_prompt

            # Render the author style analysis prompt
            author_prompt = render_prompt(
                "author_style_analysis", language=language, author=author
            )

            # Use structured output for author style analysis
            structured_llm = llm.with_structured_output(AuthorStyleAnalysis)
            style_analysis = structured_llm.invoke(author_prompt)

            # Format the analysis into guidance text using template
            # First get just the formatted analysis for storage
            author_style_guidance = render_prompt(
                "author_style_guidance",
                language,
                author=author,
                narrative_style=style_analysis.narrative_style,
                character_development=style_analysis.character_development,
                dialogue_patterns=style_analysis.dialogue_patterns,
                thematic_elements=style_analysis.thematic_elements,
                pacing_rhythm=style_analysis.pacing_rhythm,
                descriptive_approach=style_analysis.descriptive_approach,
                unique_elements=style_analysis.unique_elements,
                emotional_tone=style_analysis.emotional_tone,
                include_header=False  # Just the analysis, no header
            )
            
            # Store the formatted analysis
            state["author_style_guidance"] = author_style_guidance

        # Now get the full guidance with header for the prompt
        style_guidance = render_prompt(
            "author_style_guidance",
            language,
            author=author,
            narrative_style=style_analysis.narrative_style,
            character_development=style_analysis.character_development,
            dialogue_patterns=style_analysis.dialogue_patterns,
            thematic_elements=style_analysis.thematic_elements,
            pacing_rhythm=style_analysis.pacing_rhythm,
            descriptive_approach=style_analysis.descriptive_approach,
            unique_elements=style_analysis.unique_elements,
            emotional_tone=style_analysis.emotional_tone,
            include_header=True  # Include the full header and instructions
        )

    # Include brainstormed creative elements if available
    creative_guidance = ""
    if creative_elements:
        # Extract recommended story concept
        story_concept = ""
        if "story_concepts" in creative_elements and creative_elements[
            "story_concepts"
        ].get("recommended_ideas"):
            story_concept = creative_elements["story_concepts"]["recommended_ideas"]

        # Extract recommended world building elements
        world_building = ""
        if "world_building" in creative_elements and creative_elements[
            "world_building"
        ].get("recommended_ideas"):
            world_building = creative_elements["world_building"]["recommended_ideas"]

        # Extract recommended central conflict
        conflict = ""
        if "central_conflicts" in creative_elements and creative_elements[
            "central_conflicts"
        ].get("recommended_ideas"):
            conflict = creative_elements["central_conflicts"]["recommended_ideas"]

        # Compile creative guidance using template
        creative_guidance = render_prompt(
            "creative_guidance",
            language,
            story_concept=story_concept,
            world_building=world_building,
            conflict=conflict
        )

    # Prepare language guidance
    language_guidance = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_guidance = render_prompt(
            "language_guidance_outline",
            language
        )

    # Pass raw elements to template - let template handle formatting
    idea_elements = (
        initial_idea_elements if initial_idea and initial_idea_elements else None
    )

    # Import prompt template system
    from storyteller_lib.prompts.renderer import render_prompt

    # No language instruction needed - templates are already in the correct language

    # Prepare template variables
    template_vars = {
        "tone": tone,
        "genre": genre,
        "initial_idea": initial_idea,
        "idea_elements": idea_elements,  # Pass structured elements instead of formatted guidance
        "creative_guidance": creative_guidance,
        "style_guidance": style_guidance,
        "language_guidance": language_guidance,
    }

    # Determine which template to use based on narrative structure
    template_name = f"story_outline_{narrative_structure}"

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
    descriptions = [
        d.strip() for d in outline_flat.main_character_descriptions.split("|")
    ]
    for name, desc in zip(names, descriptions):
        story_outline += f"- {name}: {desc}\n"

    story_outline += f"\nCentral Conflict: {outline_flat.central_conflict}\n"
    story_outline += f"\nWorld/Setting: {outline_flat.world_setting}\n"

    story_outline += "\nKey Themes:\n"
    themes = [t.strip() for t in outline_flat.key_themes_csv.split(",") if t.strip()]
    for theme in themes:
        story_outline += f"- {theme}\n"

    story_outline += (
        f"\nStory Structure ({narrative_structure.replace('_', ' ').title()}):\n"
    )
    phase_names = [n.strip() for n in outline_flat.story_phase_names.split("|")]
    phase_descriptions = [
        d.strip() for d in outline_flat.story_phase_descriptions.split("|")
    ]
    for i, (name, desc) in enumerate(zip(phase_names, phase_descriptions), 1):
        story_outline += f"\n{i}. {name}\n{desc}\n"

    print(f"[DEBUG] Story outline length: {len(story_outline)}")
    logger.info(f"Generated structured story outline with length: {len(story_outline)}")

    # Perform multiple validation checks on the story outline
    print(f"[DEBUG] Before validation, story_outline length: {len(story_outline)}")
    validation_results = {}

    # Language validation removed - templates ensure correct language

    # 1. Validate that the outline adheres to the initial idea if one was provided
    if initial_idea and initial_idea_elements:
        # Render the idea validation prompt
        idea_validation_prompt = render_prompt(
            "idea_validation",
            language,  # Use story's language for validation
            initial_idea=initial_idea,
            setting=initial_idea_elements.get("setting", "Unknown"),
            characters=initial_idea_elements.get("characters", []),
            plot=initial_idea_elements.get("plot", "Unknown"),
            themes=initial_idea_elements.get("themes", []),
            genre_elements=initial_idea_elements.get("genre_elements", []),
            story_outline=story_outline,
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
        "genre_validation",
        language,  # Use story's language for validation
        genre=genre,
        tone=tone,
        story_outline=story_outline,
        genre_elements=genre_elements,
    )

    # Use structured output for validation
    structured_llm = llm.with_structured_output(ValidationResult)
    genre_validation_result = structured_llm.invoke(genre_validation_prompt)
    validation_results["genre"] = genre_validation_result

    # Store the validation result in memory
    # Genre validation is temporary and used immediately

    # 3. Validate that the outline adheres to the specified setting if one was provided
    if initial_idea_elements and initial_idea_elements.get("setting"):
        setting = initial_idea_elements.get("setting")
        # Render the setting validation prompt
        setting_validation_prompt = render_prompt(
            "setting_validation",
            language,  # Use story's language for validation
            setting=setting,
            story_outline=story_outline,
        )

        # Use structured output for validation
        structured_llm = llm.with_structured_output(ValidationResult)
        setting_validation_result = structured_llm.invoke(setting_validation_prompt)
        validation_results["setting"] = setting_validation_result

        # Store the validation result in memory
        # Setting validation is temporary and used immediately

    # Determine if we need to regenerate the outline based on validation results
    needs_regeneration = False
    
    # Collect validation issues for template
    validation_context = {
        "idea_issues": False,
        "genre_issues": False,
        "setting_issues": False,
        "all_issues": ""
    }
    
    improvement_guidance = ""

    # Language validation removed - templates ensure correct language

    # Check initial idea validation
    if "initial_idea" in validation_results:
        result = validation_results["initial_idea"]
        # Regenerate if validation failed or score is below 8
        if not result.is_valid or result.score < 8:
            needs_regeneration = True
            validation_context["idea_issues"] = True
            validation_context["idea_issues_details"] = result.issues
            validation_context["idea_suggestions"] = result.suggestions

    # Check genre validation
    if "genre" in validation_results:
        result = validation_results["genre"]
        # Regenerate if validation failed or score is below 8
        if not result.is_valid or result.score < 8:
            needs_regeneration = True
            validation_context["genre_issues"] = True
            validation_context["genre_issues_details"] = result.issues
            validation_context["genre_suggestions"] = result.suggestions

    # Check setting validation
    if "setting" in validation_results:
        result = validation_results["setting"]
        # Regenerate if validation failed or score is below 7
        if not result.is_valid or result.score < 7:
            needs_regeneration = True
            validation_context["setting_issues"] = True
            validation_context["setting_issues_details"] = result.issues
            validation_context["setting_suggestions"] = result.suggestions

    print(f"[DEBUG] Validation complete. Needs regeneration: {needs_regeneration}")
    logger.info(f"Validation complete. Needs regeneration: {needs_regeneration}")

    # If regeneration is needed, create a new improved prompt
    if needs_regeneration:
        logger.info("Regenerating story outline based on validation feedback...")
        print("[DEBUG] Regenerating story outline based on validation feedback...")

        # Generate validation feedback using template
        improvement_guidance = render_prompt(
            "validation_feedback",
            language,
            **validation_context
        )
        
        validation_context["all_issues"] = improvement_guidance
        
        # Add improvement guidance to the original prompt
        improvement_prompt = prompt + "\n\n" + improvement_guidance

        # Regenerate with improvement guidance using structured output
        structured_llm = llm.with_structured_output(StoryOutlineFlat)
        outline_flat = structured_llm.invoke(improvement_prompt)

        # Convert flattened output to text format
        story_outline = f"Title: {outline_flat.title}\n\n"

        story_outline += "Main Characters:\n"
        names = [n.strip() for n in outline_flat.main_character_names.split(",")]
        descriptions = [
            d.strip() for d in outline_flat.main_character_descriptions.split("|")
        ]
        for name, desc in zip(names, descriptions):
            story_outline += f"- {name}: {desc}\n"

        story_outline += f"\nCentral Conflict: {outline_flat.central_conflict}\n"
        story_outline += f"\nWorld/Setting: {outline_flat.world_setting}\n"

        story_outline += "\nKey Themes:\n"
        themes = [
            t.strip() for t in outline_flat.key_themes_csv.split(",") if t.strip()
        ]
        for theme in themes:
            story_outline += f"- {theme}\n"

        story_outline += (
            f"\nStory Structure ({narrative_structure.replace('_', ' ').title()}):\n"
        )
        phase_names = [n.strip() for n in outline_flat.story_phase_names.split("|")]
        phase_descriptions = [
            d.strip() for d in outline_flat.story_phase_descriptions.split("|")
        ]
        for i, (name, desc) in enumerate(zip(phase_names, phase_descriptions), 1):
            story_outline += f"\n{i}. {name}\n{desc}\n"

        print(f"[DEBUG] Regenerated story outline length: {len(story_outline)}")
        logger.info(f"Regenerated story outline with length: {len(story_outline)}")

    # After validation and any regeneration, generate plot threads
    plot_threads = generate_plot_threads_from_outline(
        story_outline=story_outline,
        genre=genre,
        tone=tone,
        initial_idea=initial_idea or "",
        language=language,
    )

    # Initialize PlotThreadRegistry with the generated threads
    from storyteller_lib.generation.story.plot_threads import PlotThreadRegistry, PlotThread

    registry = PlotThreadRegistry()
    for thread_name, thread_data in plot_threads.items():
        thread = PlotThread(**thread_data)
        registry.add_thread(thread)

    # Store the outline in the database
    from storyteller_lib.persistence.database import get_db_manager
    db_manager = get_db_manager()
    if db_manager:
        db_manager.update_global_story(story_outline)
        logger.info(f"Stored story outline in database (length: {len(story_outline)})")
    else:
        logger.warning("Database manager not available - outline not stored")

    # Log the generated outline details
    # Note: log_progress doesn't have a handler for "outline_generated", 
    # so we'll use "story_outline" instead
    if "outline_flat" in locals() and hasattr(outline_flat, "outline"):
        log_progress("story_outline", outline=outline_flat.outline)

    # Generate and store book-level instructions now that we have the outline and author style
    logger.info("Generating book-level writing instructions...")
    from storyteller_lib.prompts.synthesis import generate_book_level_instructions
    
    book_instructions = generate_book_level_instructions(state)
    
    # Store them in database for future use
    if db_manager:
        db_manager.update_book_level_instructions(book_instructions)
        logger.info("Stored book-level instructions in database")
    
    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]

    # Create language-specific messages using proper localization
    structure_name = narrative_structure.replace('_', ' ').title()
    if language.lower() == "german":
        new_msg = AIMessage(
            content=f"Ich habe eine detaillierte Geschichte mit der {structure_name} Struktur erstellt. Als Nächstes werde ich die Welt aufbauen, in der diese Geschichte stattfindet."
        )
    else:
        new_msg = AIMessage(
            content=f"I've created a detailed story outline using the {structure_name} structure. Next, I'll build the world where this story takes place."
        )

    return {
        "story_outline": story_outline,
        "plot_threads": plot_threads,
        "messages": [*[RemoveMessage(id=msg_id) for msg_id in message_ids], new_msg],
    }


@track_progress
def plan_chapters(state: StoryState) -> Dict:
    """Divide the story into chapters with detailed outlines."""
    from storyteller_lib.prompts.renderer import render_prompt
    from storyteller_lib.generation.story.narrative_structures import get_structure_by_name
    
    # Load configuration from database
    from storyteller_lib.core.config import get_story_config
    from storyteller_lib.persistence.database import get_db_manager
    from storyteller_lib.core.logger import get_logger
    
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
    
    # No language instruction or guidance needed - templates are already in the correct language
    
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
    )
    # Generate chapter plan
    chapter_plan_text = llm.invoke([HumanMessage(content=prompt)]).content
    
    # No language validation needed - templates ensure correct language
    
    # Use direct LLM structured output with simplified Pydantic model
    max_retries = 2
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            # Create a structured output prompt that explicitly asks for chapter data with scenes
            # Render the chapter extraction prompt
            structured_prompt = render_prompt(
                'chapter_extraction',
                language=language,
                chapter_plan_text=chapter_plan_text
            )
            
            # Add explicit instruction about chapter count if this is a retry
            if retry_count > 0:
                retry_prompt = render_prompt(
                    'chapter_retry',
                    language,
                    chapter_count=len(chapters) if 'chapters' in locals() else 'too few',
                    min_chapters=max(5, target_chapters - 3),
                    target_chapters=target_chapters,
                    original_prompt=structured_prompt
                )
                structured_prompt = retry_prompt
            
            # Always use flattened model to avoid nested dictionaries
            structured_output_llm = llm.with_structured_output(FlatChapterPlan)
            
            # Get structured output
            result = structured_output_llm.invoke(structured_prompt)
            
            # Convert from flattened structure
            chapters_dict = {}
            
            # Convert from flattened structure
            # First, create chapters with sequential numbering
            # Also create a mapping from LLM chapter numbers to actual sequential numbers
            llm_to_actual_chapter = {}
            for idx, chapter in enumerate(result.chapters, 1):
                # Use sequential numbering instead of trusting LLM output
                actual_chapter_num = str(idx)
                llm_chapter_num = str(chapter.number)
                llm_to_actual_chapter[llm_chapter_num] = actual_chapter_num
                
                logger.info(f"Creating chapter {actual_chapter_num} (LLM labeled it as {llm_chapter_num}): {chapter.title}")
                    
                chapters_dict[actual_chapter_num] = {
                    "title": chapter.title,
                    "outline": chapter.outline,
                    "scenes": {},
                    "reflection_notes": []
                }
            
            # Then add scenes to their respective chapters using the mapping
            for scene in result.total_scenes:
                llm_chapter_num = scene.chapter_number
                # Map the LLM's chapter number to our sequential number
                actual_chapter_num = llm_to_actual_chapter.get(llm_chapter_num, llm_chapter_num)
                scene_num = str(scene.scene_number)
                
                if actual_chapter_num in chapters_dict:
                    chapters_dict[actual_chapter_num]["scenes"][scene_num] = {
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
                        "db_stored": False,
                        "reflection": {}
                    }
                else:
                    logger.warning(f"Scene {scene_num} references non-existent chapter {actual_chapter_num}. Skipping.")
            
            # Validate we have enough chapters
            actual_chapter_count = len(chapters_dict)
            if actual_chapter_count < max(5, target_chapters - 3):
                if retry_count < max_retries:
                    logger.warning(f"Only generated {actual_chapter_count} chapters, need at least {max(5, target_chapters - 3)}. Retrying...")
                    retry_count += 1
                    chapters = chapters_dict  # Store for error message
                    continue
                else:
                    logger.error(f"Failed to generate minimum chapters after {max_retries} retries. Generated {actual_chapter_count} chapters.")
                    # Continue with what we have rather than failing
            
            # Success - log chapter creation
            logger.info(f"Successfully generated {actual_chapter_count} chapters")
            
            # Validate scene count per chapter
            for chapter_num, chapter_data in chapters_dict.items():
                scene_count = len(chapter_data.get("scenes", {}))
                if scene_count == 0:
                    logger.warning(f"Chapter {chapter_num} has no scenes!")
                else:
                    logger.info(f"Chapter {chapter_num}: {scene_count} scenes")
            
            # Get existing message IDs to delete
            message_ids = [msg.id for msg in state.get("messages", [])]
            
            # Create language-specific messages using proper localization
            if language.lower() == "german":
                new_msg = AIMessage(
                    content=f"Ich habe die Geschichte in {actual_chapter_count} Kapitel unterteilt. Als Nächstes werde ich mit dem Schreiben der Szenen beginnen."
                )
            else:
                new_msg = AIMessage(
                    content=f"I've divided the story into {actual_chapter_count} chapters. Next, I'll begin writing the scenes."
                )
            
            # Store chapter plan in database
            # Note: We store the chapter outlines individually when saving chapters
            # The full chapter plan is part of the state and doesn't need separate storage
            logger.info(f"Generated chapter plan with {actual_chapter_count} chapters")
            
            return {
                "chapters": chapters_dict,
                "current_chapter": "1",
                "current_scene": "1",
                "messages": [*[RemoveMessage(id=msg_id) for msg_id in message_ids], new_msg],
            }
            
        except Exception as e:
            logger.error(f"Error extracting chapters (attempt {retry_count + 1}): {str(e)}")
            if retry_count < max_retries:
                retry_count += 1
                logger.info(f"Retrying chapter extraction... (attempt {retry_count + 1}/{max_retries + 1})")
            else:
                raise Exception(f"Failed to extract chapters after {max_retries + 1} attempts: {str(e)}")
    
    # Should not reach here, but just in case
    raise Exception("Failed to generate chapter plan")
