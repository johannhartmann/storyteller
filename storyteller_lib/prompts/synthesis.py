"""
Intelligent instruction synthesis for story writing.
Uses LLM to create coherent, structured instructions instead of string concatenation.
"""

from langchain_core.messages import HumanMessage

from storyteller_lib.core.config import DEFAULT_LANGUAGE, llm
from storyteller_lib.core.logger import get_logger
from storyteller_lib.core.models import StoryState
from storyteller_lib.persistence.database import get_db_manager
from storyteller_lib.prompts.renderer import render_prompt

logger = get_logger(__name__)


def generate_book_level_instructions(state: StoryState) -> str:
    """
    Generate comprehensive writing instructions for the entire book.
    This synthesizes genre, tone, and author style into coherent guidance.

    Args:
        state: Current story state containing configuration and style analysis

    Returns:
        Coherent writing instructions for the book
    """
    logger.info("Generating book-level writing instructions")

    # Load configuration from database
    db_manager = get_db_manager()
    if not db_manager:
        raise RuntimeError("Database manager not available")

    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT genre, tone, author, language, initial_idea
            FROM story_config WHERE id = 1
        """
        )
        config = cursor.fetchone()

    genre = config["genre"] or "fantasy"
    tone = config["tone"] or "adventurous"
    author = config["author"] or ""
    language = config["language"] or DEFAULT_LANGUAGE
    initial_idea = config["initial_idea"] or ""

    # Get author style guidance from state
    author_style_guidance = state.get("author_style_guidance", "")

    # Prepare template variables
    template_vars = {
        "genre": genre,
        "tone": tone,
        "author": author,
        "author_style_guidance": author_style_guidance,
        "initial_idea": initial_idea,
    }

    # Use template to create synthesis prompt
    prompt = render_prompt(
        "synthesize_book_instructions", language=language, **template_vars
    )

    # Generate synthesized instructions
    response = llm.invoke([HumanMessage(content=prompt)])
    book_instructions = response.content

    logger.info(f"Generated book-level instructions ({len(book_instructions)} chars)")
    return book_instructions


def generate_scene_level_instructions(
    chapter: int, scene: int, state: StoryState
) -> str:
    """
    Generate specific instructions for a scene by synthesizing all relevant context.

    Args:
        chapter: Chapter number
        scene: Scene number
        state: Current story state

    Returns:
        Coherent instructions for writing this specific scene
    """
    logger.info(
        f"Generating scene-level instructions for Chapter {chapter}, Scene {scene}"
    )

    # Debug: Log the state chapters structure
    chapters = state.get("chapters", {})
    if str(chapter) in chapters and "scenes" in chapters[str(chapter)]:
        scenes_in_chapter = chapters[str(chapter)]["scenes"]
        logger.debug(f"Chapter {chapter} has {len(scenes_in_chapter)} scenes")
        for scene_num, scene_data in scenes_in_chapter.items():
            desc = scene_data.get("description", "NO DESCRIPTION")
            logger.debug(f"  Scene {scene_num}: {desc[:100]}...")

    # Get database manager
    db_manager = get_db_manager()
    if not db_manager:
        raise RuntimeError("Database manager not available")

    # Gather all scene-relevant data using existing functions
    from storyteller_lib.generation.scene.context import (
        _get_chapter_context,
        _get_character_context,
        _get_plot_context,
        _get_scene_specifications,
        _get_sequence_context,
        _get_story_context,
        _get_world_context,
        _get_writing_constraints,
    )

    # 1. Get story context
    story_context = _get_story_context(db_manager, state)

    # 2. Get chapter context
    chapter_context = _get_chapter_context(db_manager, chapter)

    # 3. Get scene specifications
    scene_specs = _get_scene_specifications(state, chapter, scene)

    # Debug: Log POV character
    logger.debug(
        f"Scene {scene} POV character: {scene_specs.get('pov_character', 'Not specified')}"
    )

    # 4. Get plot context
    plot_context = _get_plot_context(db_manager, scene_specs)

    # 5. Get character context
    character_context = _get_character_context(
        db_manager,
        scene_specs["required_characters"],
        scene_specs["description"],
        state,
    )

    # 6. Get world context using intelligent selection
    try:
        from storyteller_lib.universe.world.scene_integration import (
            get_intelligent_world_context,
        )

        # Extract plot thread descriptions
        plot_thread_descriptions = [
            thread["name"] for thread in plot_context.get("active_threads", [])
        ]

        # Get intelligent world context
        logger.info(f"Getting intelligent worldbuilding for scene {scene}")

        # Use location from scene specifications
        scene_location = scene_specs.get("location", "Unknown")
        logger.info(f"Scene location: {scene_location}")

        intelligent_world = get_intelligent_world_context(
            scene_description=scene_specs["description"],
            scene_type=scene_specs["scene_type"],
            location=scene_location,
            characters=scene_specs["required_characters"],
            plot_threads=plot_thread_descriptions,
            dramatic_purpose=scene_specs["dramatic_purpose"],
            chapter_themes=chapter_context["themes"],
            chapter=chapter,
            scene=scene,
        )

        # Still get basic location data
        world_context = _get_world_context(
            db_manager, scene_specs["description"], character_context["locations"]
        )

        # Merge intelligent worldbuilding with location data
        world_context["elements"] = intelligent_world.get("elements", [])

        logger.info(
            f"Selected {len(world_context['elements'])} worldbuilding elements with content"
        )

    except Exception as e:
        logger.error(f"Failed to get intelligent worldbuilding: {str(e)}")
        logger.error("Falling back to basic world context")
        # Fallback to basic world context
        world_context = _get_world_context(
            db_manager, scene_specs["description"], character_context["locations"]
        )

    # 7. Get sequence context
    sequence_context = _get_sequence_context(db_manager, chapter, scene, state)

    # 8. Get writing constraints
    constraints = _get_writing_constraints(db_manager, chapter, scene)

    # 9. Get story so far (previous summaries)
    from storyteller_lib.output.summary import get_story_so_far

    story_so_far = get_story_so_far(chapter, scene)

    # Debug: Log worldbuilding content
    logger.debug(
        f"World context elements: {len(world_context.get('elements', []))} items"
    )
    for idx, elem in enumerate(world_context.get("elements", [])):
        if isinstance(elem, str):
            content_preview = elem[:100] + "..." if elem else "No content"
        else:
            content_preview = str(elem)[:100] + "..."
        logger.debug(f"  Element {idx+1}: {content_preview}")

    # Prepare all data for synthesis
    template_vars = {
        # Story level
        "story_premise": story_context["premise"],
        "initial_idea": story_context["initial_idea"],
        # Chapter level
        "chapter_number": chapter,
        "chapter_title": chapter_context["title"],
        "chapter_outline": chapter_context["outline"],
        "chapter_themes": chapter_context["themes"],
        # Scene specifications
        "scene_number": scene,
        "scene_description": scene_specs["description"],
        "scene_type": scene_specs["scene_type"],
        "dramatic_purpose": scene_specs["dramatic_purpose"],
        "tension_level": scene_specs["tension_level"],
        "ends_with": scene_specs["ends_with"],
        "pov_character": scene_specs.get("pov_character", ""),
        # Plot
        "plot_progressions": plot_context["progressions"],
        "active_threads": plot_context["active_threads"],
        # Characters
        "required_characters": scene_specs["required_characters"],
        "character_learns": scene_specs["character_learns"],
        "characters": character_context["characters"],
        "relationships": character_context["relationships"],
        # World
        "locations": world_context["locations"],
        "world_elements": world_context["elements"],
        # Sequence
        "previous_ending": sequence_context["previous_ending"],
        "previous_summary": sequence_context["previous_summary"],
        "next_preview": sequence_context["next_preview"],
        # Constraints
        "forbidden_repetitions": constraints["forbidden_repetitions"],
        "recent_scene_types": constraints["recent_scene_types"],
        "overused_phrases": constraints["overused_phrases"],
        # Story so far
        "previous_chapters": story_so_far["chapter_summaries"],
        "previous_scenes_current_chapter": story_so_far["current_chapter_scenes"],
    }

    # Use template to create synthesis prompt
    prompt = render_prompt(
        "synthesize_scene_instructions",
        language=story_context["language"],
        **template_vars,
    )

    # Generate synthesized instructions
    response = llm.invoke([HumanMessage(content=prompt)])
    scene_instructions = response.content

    logger.info(f"Generated scene instructions ({len(scene_instructions)} chars)")
    return scene_instructions
