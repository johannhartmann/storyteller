"""
Simplified scene reflection following the refactoring plan.
Reduces 9 quality metrics to 4 key ones and focuses on critical issues only.
"""

from pydantic import BaseModel, Field

from storyteller_lib.core.config import get_story_config, llm
from storyteller_lib.core.logger import get_logger
# StoryState no longer used - working directly with database
from storyteller_lib.persistence.database import get_db_manager

logger = get_logger(__name__)


class SimplifiedReflection(BaseModel):
    """Simplified scene reflection with focus on critical aspects."""

    overall_quality: int = Field(ge=1, le=10, description="Overall scene quality")
    advances_plot: bool = Field(
        description="Does the scene advance the plot meaningfully?"
    )
    character_consistency: bool = Field(
        description="Are characters acting consistently?"
    )
    engaging_prose: bool = Field(description="Is the prose engaging and well-written?")
    critical_issues: list[str] = Field(
        default_factory=list, description="Critical issues that must be fixed"
    )
    style_issues: list[str] = Field(
        default_factory=list,
        description="Style issues like word repetition, redundant descriptions",
    )
    minor_issues: list[str] = Field(
        default_factory=list, description="Minor issues that could be improved"
    )
    needs_revision: bool = Field(description="Does this scene need revision?")
    needs_style_corrections: bool = Field(
        default=False, description="Does this scene need style corrections?"
    )
    needs_minor_corrections: bool = Field(
        default=False, description="Does this scene need minor corrections?"
    )


def reflect_on_scene_simplified(params: dict) -> dict:
    """
    Simplified scene reflection focusing on critical quality aspects.
    Replaces complex 9-metric analysis with 4 key checks.
    """
    current_chapter = int(params.get("current_chapter", 1))
    current_scene = int(params.get("current_scene", 1))

    logger.info(
        f"Reflecting on Chapter {current_chapter}, Scene {current_scene} (simplified)"
    )

    # Get database manager
    db_manager = get_db_manager()
    if not db_manager:
        raise RuntimeError("Database manager not available")

    # Get book-level instructions from database
    book_instructions = ""
    if db_manager:
        book_instructions = db_manager.get_book_level_instructions() or ""

    logger.info(
        f"Attempting to retrieve scene instructions from database for Ch{current_chapter}/Sc{current_scene}"
    )
    scene_instructions = db_manager.get_scene_instructions(
        current_chapter, current_scene
    )

    # If not found in database, generate them (shouldn't happen in normal flow)
    if not scene_instructions:
        logger.warning(
            f"Scene instructions not found in database for Ch{current_chapter}/Sc{current_scene}. Generating now."
        )
        from storyteller_lib.prompts.synthesis import generate_scene_level_instructions

        scene_instructions = generate_scene_level_instructions(
            current_chapter, current_scene, params
        )
        # Save for future use
        db_manager.save_scene_instructions(
            current_chapter, current_scene, scene_instructions
        )
    else:
        logger.info(
            f"Successfully retrieved scene instructions from database (length: {len(scene_instructions)} chars)"
        )

    # Get scene content
    scene_content = db_manager.get_scene_content(current_chapter, current_scene)
    if not scene_content:
        scene_content = params.get("current_scene_content", "")

    if not scene_content:
        raise RuntimeError(
            f"No content found for Chapter {current_chapter}, Scene {current_scene}"
        )

    # Get language
    config = get_story_config()
    language = config.get("language", "english")

    # Use intelligent reflection template
    from storyteller_lib.prompts.renderer import render_prompt

    prompt = render_prompt(
        "reflect_scene_intelligent",
        language=language,
        book_instructions=book_instructions,
        scene_instructions=scene_instructions,
        scene_content=scene_content,
        chapter=current_chapter,
        scene=current_scene,
    )

    # Get structured reflection
    structured_llm = llm.with_structured_output(SimplifiedReflection)
    reflection = structured_llm.invoke(prompt)

    # Log reflection results
    logger.info(
        f"Reflection complete - Quality: {reflection.overall_quality}/10, "
        f"Needs revision: {reflection.needs_revision}"
    )

    if reflection.needs_revision:
        logger.info(
            f"Revision needed due to: {', '.join(reflection.critical_issues[:3])}"
        )
        logger.debug(
            f"Full reflection: advances_plot={reflection.advances_plot}, "
            f"character_consistency={reflection.character_consistency}, "
            f"engaging_prose={reflection.engaging_prose}"
        )

    # Store reflection in state (minimal data)
    reflection_data = {
        "quality": reflection.overall_quality,
        "needs_revision": reflection.needs_revision,
        "issues": reflection.critical_issues,
    }

    # Reflection data is stored in the function return value
    # No need to update params - database is the source of truth

    # Handle style corrections immediately if needed
    if reflection.needs_style_corrections and reflection.style_issues:
        logger.info(
            f"Scene needs style corrections: {', '.join(reflection.style_issues[:3])}"
        )

        # Import correction function
        from storyteller_lib.output.corrections.scene import correct_scene

        # Create correction instruction focused on style issues
        style_correction_instruction = _create_style_correction_instruction(
            reflection.style_issues
        )

        # Apply the correction
        success = correct_scene(
            chapter_num=current_chapter,
            scene_num=current_scene,
            correction_instruction=style_correction_instruction,
        )

        if success:
            logger.info(
                f"Successfully applied style corrections to Chapter {current_chapter}, Scene {current_scene}"
            )
            # Style corrections are tracked in the database
            # Clear the style correction flag since we've handled it
            reflection.needs_style_corrections = False
            reflection.style_issues = []

            # Verify the correction was saved by reading it back
            corrected_content = db_manager.get_scene_content(
                current_chapter, current_scene
            )
            if corrected_content:
                logger.info(
                    f"Verified corrected content saved - length: {len(corrected_content)} chars"
                )
            else:
                logger.error("Could not verify corrected content was saved")
        else:
            logger.error("Failed to apply style corrections, but continuing anyway")

    # Log if minor corrections are needed
    if reflection.needs_minor_corrections and reflection.minor_issues:
        logger.info(
            f"Scene needs minor corrections: {', '.join(reflection.minor_issues[:3])}"
        )

    return {
        "scene_reflection": reflection.model_dump(),
        "needs_revision": reflection.needs_revision,
        "needs_style_corrections": reflection.needs_style_corrections,
        "needs_minor_corrections": reflection.needs_minor_corrections,
        "style_issues": reflection.style_issues,
        "minor_issues": reflection.minor_issues,
    }


def _create_style_correction_instruction(style_issues: list[str]) -> str:
    """
    Create a correction instruction specifically for style issues.

    Args:
        style_issues: List of style issues identified during reflection

    Returns:
        A correction instruction focused on style improvements
    """
    # Get language from config
    config = get_story_config()
    language = config.get("language", "english")

    # Use template to generate instruction
    from storyteller_lib.prompts.renderer import render_prompt

    return render_prompt(
        "style_correction_instruction", language=language, style_issues=style_issues
    )
