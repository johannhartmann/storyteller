"""
StoryCraft Agent - Scene and chapter transition enhancement.

This module provides functionality to create smooth transitions between scenes and chapters,
addressing issues with abrupt transitions in the narrative in multiple languages.
"""

from typing import Any

from langchain_core.messages import HumanMessage

from storyteller_lib.core.config import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, llm
from storyteller_lib.core.models import StoryState
from storyteller_lib.generation.story.plot_threads import (
    get_active_plot_threads_for_scene,
)


def analyze_transition_needs(
    current_content: str,
    next_content_outline: str,
    transition_type: str = "scene",
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, Any]:
    """
    Analyze the transition needs between current content and next content.

    Args:
        current_content: The current scene or chapter content
        next_content_outline: The outline of the next scene or chapter
        transition_type: The type of transition ("scene" or "chapter")
        language: The language of the content (default: from config)

    Returns:
        A dictionary with transition analysis results
    """
    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        print(
            f"Warning: Unsupported language '{language}'. Falling back to {DEFAULT_LANGUAGE}."
        )
        language = DEFAULT_LANGUAGE

    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[language]

    # Prepare the prompt for analyzing transition needs
    prompt = f"""
    Analyze the transition needs between this {transition_type} and the next in this {language_name} narrative:

    CURRENT {transition_type.upper()} ENDING:
    {current_content[-500:]}

    NEXT {transition_type.upper()} OUTLINE:
    {next_content_outline}

    Evaluate:
    1. Is the current ending abrupt?
    2. Are there unresolved immediate tensions that should be addressed?
    3. Is there a clear connection to the next {transition_type}?
    4. Does the transition follow natural flow patterns in {language_name} narrative?
    5. Are there any language-specific transition techniques that could be applied?
    6. What elements would create a smoother transition?
    7. What tone would be appropriate for the transition?

    Format your response as a structured JSON object.
    """

    try:
        # Define Pydantic models for structured output

        from pydantic import BaseModel, Field

        class TransitionAnalysis(BaseModel):
            """Analysis of transition needs."""

            abruptness_score: int = Field(
                ge=1,
                le=10,
                description="How abrupt the current ending is (1=smooth, 10=very abrupt)",
            )
            unresolved_tensions: list[str] = Field(
                default_factory=list,
                description="Unresolved immediate tensions that should be addressed",
            )
            connection_strength: int = Field(
                ge=1,
                le=10,
                description="Strength of connection to the next content (1=weak, 10=strong)",
            )
            recommended_elements: list[str] = Field(
                default_factory=list,
                description="Elements that would create a smoother transition",
            )
            recommended_tone: str = Field(
                description="Recommended tone for the transition"
            )
            transition_length: str = Field(
                description="Recommended length for the transition (short, medium, long)"
            )

        # Create a structured LLM that outputs a TransitionAnalysis
        structured_llm = llm.with_structured_output(TransitionAnalysis)

        # Use the structured LLM to analyze transition needs
        transition_analysis = structured_llm.invoke(prompt)

        # Convert Pydantic model to dictionary
        return transition_analysis.dict()

    except Exception as e:
        print(f"Error analyzing transition needs: {str(e)}")
        return {
            "abruptness_score": 5,
            "unresolved_tensions": [],
            "connection_strength": 5,
            "recommended_elements": [],
            "recommended_tone": "neutral",
            "transition_length": "medium",
        }


def create_scene_transition(
    current_scene_content: str,
    next_scene_outline: str,
    state: StoryState = None,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """
    Create a smooth transition between scenes.

    Args:
        current_scene_content: The content of the current scene
        next_scene_outline: The outline of the next scene
        state: The current state (optional, for plot thread integration)
        language: The language of the content (default: from config)

    Returns:
        The transition text
    """
    # Use template system
    from storyteller_lib.prompts.renderer import render_prompt

    # Get language from state if provided and not explicitly specified
    if state and not language:
        language = state.get("language", DEFAULT_LANGUAGE)

    # Extract scene ending (last 500 chars)
    previous_scene_ending = (
        current_scene_content[-500:] if current_scene_content else ""
    )

    # Extract scene beginning from outline
    next_scene_beginning = next_scene_outline[:500] if next_scene_outline else ""

    # Get current scene info from state
    previous_chapter = str(state.get("current_chapter", "1")) if state else "1"
    previous_scene = str(state.get("current_scene", "1")) if state else "1"
    next_chapter = previous_chapter  # Same chapter for scene transitions
    next_scene = str(int(previous_scene) + 1)

    # Get genre and tone
    genre = state.get("genre", "fantasy") if state else "fantasy"
    tone = state.get("tone", "adventurous") if state else "adventurous"

    # Detect if there's a time gap, location change, or POV change
    # This would require more sophisticated analysis, but for now we'll leave as optional
    time_gap = None
    location_change = None
    pov_change = None
    emotional_shift = None

    # Get active plot threads if state is provided
    plot_threads = []
    if state:
        active_plot_threads = get_active_plot_threads_for_scene(state)

        # Format for template
        for thread in active_plot_threads[:3]:  # Limit to 3
            plot_threads.append(
                {
                    "name": thread.get("name", "Unknown"),
                    "status": thread.get(
                        "status", thread.get("current_development", "Active")
                    ),
                }
            )

    # Analyze transition needs for specific requirements
    transition_analysis = analyze_transition_needs(
        current_scene_content, next_scene_outline, "scene", language
    )

    # Prepare specific requirements based on analysis
    specific_requirements = None
    if transition_analysis.get("unresolved_tensions"):
        specific_requirements = f"Address these unresolved tensions: {', '.join(transition_analysis['unresolved_tensions'])}"

    # Render the transition prompt
    prompt = render_prompt(
        "scene_transition",
        language=language,
        previous_scene_ending=previous_scene_ending,
        next_scene_beginning=next_scene_beginning,
        previous_chapter=previous_chapter,
        previous_scene=previous_scene,
        next_chapter=next_chapter,
        next_scene=next_scene,
        genre=genre,
        tone=tone,
        time_gap=time_gap,
        location_change=location_change,
        previous_location=None,
        next_location=None,
        pov_change=pov_change,
        previous_pov=None,
        next_pov=None,
        emotional_shift=emotional_shift,
        plot_threads=plot_threads if plot_threads else None,
        specific_requirements=specific_requirements,
    )

    try:
        # Generate the transition
        response = llm.invoke([HumanMessage(content=prompt)]).content

        # Clean up the response
        transition = response.strip()

        return transition

    except Exception as e:
        print(f"Error creating scene transition: {str(e)}")
        return ""


def create_chapter_transition(
    current_chapter_data: dict,
    next_chapter_data: dict,
    state: StoryState = None,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """
    Create a smooth transition between chapters.

    Args:
        current_chapter_data: The data for the current chapter
        next_chapter_data: The data for the next chapter
        state: The current state (optional, for plot thread integration)
        language: The language of the content (default: from config)

    Returns:
        The transition text
    """
    # Get language from state if provided and not explicitly specified
    if state and not language:
        language = state.get("language", DEFAULT_LANGUAGE)

    # Extract relevant data
    current_chapter_title = current_chapter_data.get("title", "")
    current_chapter_outline = current_chapter_data.get("outline", "")
    next_chapter_title = next_chapter_data.get("title", "")
    next_chapter_outline = next_chapter_data.get("outline", "")

    # Get database manager
    from storyteller_lib.persistence.database import get_db_manager

    db_manager = get_db_manager()

    if not db_manager or not db_manager._db:
        raise RuntimeError("Database manager not available")

    # Get the last scene of the current chapter
    current_chapter_scenes = current_chapter_data.get("scenes", {})
    last_scene_num = max(current_chapter_scenes.keys(), key=int)

    # Get scene content from database
    chapter_num = int(
        current_chapter_data.get(
            "number", current_chapter_data.get("chapter_number", "0")
        )
    )
    last_scene_content = db_manager.get_scene_content(chapter_num, int(last_scene_num))
    if not last_scene_content:
        raise RuntimeError(f"Last scene of chapter {chapter_num} not found in database")

    # Analyze transition needs
    transition_analysis = analyze_transition_needs(
        last_scene_content, next_chapter_outline, "chapter", language
    )

    # Get active plot threads if state is provided
    plot_thread_guidance = ""
    if state:
        # Save the original current_chapter and current_scene
        state.get("current_chapter", "")
        state.get("current_scene", "")

        # Temporarily set the current chapter and scene to the last scene of the current chapter
        # This is needed for get_active_plot_threads_for_scene to work correctly
        temp_state = state.copy()
        temp_state["current_chapter"] = current_chapter_data.get("number", "")
        temp_state["current_scene"] = last_scene_num

        active_plot_threads = get_active_plot_threads_for_scene(temp_state)

        if active_plot_threads:
            # Group threads by importance
            major_threads = [
                t for t in active_plot_threads if t["importance"] == "major"
            ]

            # Format major threads
            major_thread_text = ""
            if major_threads:
                major_thread_text = (
                    "Major plot threads to carry forward to the next chapter:\n"
                )
                for thread in major_threads:
                    major_thread_text += f"- {thread['name']}: {thread['description']}\n  Status: {thread['status']}\n"

            # Combine thread guidance
            plot_thread_guidance = f"""
            PLOT THREAD CONTINUITY BETWEEN CHAPTERS:
            {major_thread_text}

            Ensure your chapter transition maintains continuity of major plot threads.
            Reference key plot elements that will carry forward into the next chapter.
            Consider how plot threads will evolve or develop in the upcoming chapter.
            """

    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        print(
            f"Warning: Unsupported language '{language}'. Falling back to {DEFAULT_LANGUAGE}."
        )
        language = DEFAULT_LANGUAGE

    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[language]

    # Prepare the prompt for creating a chapter transition
    prompt = f"""
    Create a smooth chapter transition in {language_name}:

    CURRENT CHAPTER: {current_chapter_title}
    {current_chapter_outline}

    LAST SCENE OF CURRENT CHAPTER (last 500 characters):
    {last_scene_content[-500:]}

    NEXT CHAPTER: {next_chapter_title}
    {next_chapter_outline}

    TRANSITION ANALYSIS:
    - Abruptness Score: {transition_analysis.get('abruptness_score', 5)}/10
    - Connection Strength: {transition_analysis.get('connection_strength', 5)}/10
    - Recommended Tone: {transition_analysis.get('recommended_tone', 'neutral')}
    - Transition Length: {transition_analysis.get('transition_length', 'medium')}

    {plot_thread_guidance}

    Create a transition that:
    1. Concludes the current chapter appropriately in {language_name} style
    2. Addresses any unresolved immediate tensions
    3. Creates anticipation for the next chapter
    4. Maintains plot thread continuity
    5. Respects the language's narrative conventions
    6. Uses appropriate transition techniques for {language_name}

    The transition should be a single paragraph that flows naturally from the end of the
    current chapter and sets up the beginning of the next chapter.

    IMPORTANT: The transition text must be written entirely in {language_name}.
    """

    try:
        # Generate the transition
        response = llm.invoke([HumanMessage(content=prompt)]).content

        # Clean up the response
        transition = response.strip()

        return transition

    except Exception as e:
        print(f"Error creating chapter transition: {str(e)}")
        return ""


def enhance_scene_ending(
    scene_content: str,
    next_scene_outline: str = None,
    state: StoryState = None,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """
    Enhance the ending of a scene to make it less abrupt.

    Args:
        scene_content: The current scene content
        next_scene_outline: The outline of the next scene (optional)
        state: The current state (optional, for plot thread integration)
        language: The language of the content (default: from config)

    Returns:
        The enhanced ending text
    """
    # Get language from state if provided and not explicitly specified
    if state and not language:
        language = state.get("language", DEFAULT_LANGUAGE)

    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        print(
            f"Warning: Unsupported language '{language}'. Falling back to {DEFAULT_LANGUAGE}."
        )
        language = DEFAULT_LANGUAGE

    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[language]

    # Analyze current ending
    current_ending = scene_content[-500:] if scene_content else ""

    # Get plot thread context if state is provided
    plot_thread_context = ""
    if state:
        active_plot_threads = get_active_plot_threads_for_scene(state)
        if active_plot_threads:
            plot_thread_context = "Active plot threads in this scene:\n"
            for thread in active_plot_threads[:3]:
                plot_thread_context += (
                    f"- {thread['name']}: {thread.get('status', 'active')}\n"
                )

    # Prepare the prompt for enhancing the scene ending
    prompt = f"""
    Enhance this scene ending to make it less abrupt in {language_name}:

    CURRENT SCENE ENDING:
    {current_ending}

    {plot_thread_context}

    {"NEXT SCENE OUTLINE:" if next_scene_outline else ""}
    {next_scene_outline if next_scene_outline else ""}

    Create an enhanced ending that:
    1. Provides a more natural conclusion to the scene in {language_name} style
    2. Reduces abruptness while maintaining narrative flow
    3. Subtly hints at what's to come (if next scene outline is provided)
    4. Maintains the tone and atmosphere of the scene
    5. Uses appropriate ending techniques for {language_name} narrative
    6. Respects language-specific conventions for scene endings

    The enhanced ending should be approximately 2-3 paragraphs that replace or extend
    the current ending.

    IMPORTANT: The enhanced ending must be written entirely in {language_name}.
    """

    try:
        # Generate the enhanced ending
        response = llm.invoke([HumanMessage(content=prompt)]).content

        # Clean up the response
        enhanced_ending = response.strip()

        return enhanced_ending

    except Exception as e:
        print(f"Error enhancing scene ending: {str(e)}")
        return ""


def create_scene_hook(
    scene_outline: str,
    previous_scene_content: str = None,
    state: StoryState = None,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """
    Create an engaging hook for the beginning of a scene.

    Args:
        scene_outline: The outline of the scene
        previous_scene_content: The content of the previous scene (optional)
        state: The current state (optional, for plot thread integration)
        language: The language of the content (default: from config)

    Returns:
        The scene hook text
    """
    # Get language from state if provided and not explicitly specified
    if state and not language:
        language = state.get("language", DEFAULT_LANGUAGE)

    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        print(
            f"Warning: Unsupported language '{language}'. Falling back to {DEFAULT_LANGUAGE}."
        )
        language = DEFAULT_LANGUAGE

    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[language]

    # Extract previous scene ending if available
    previous_ending = ""
    if previous_scene_content:
        previous_ending = previous_scene_content[-500:]

    # Get plot thread context if state is provided
    plot_thread_context = ""
    if state:
        active_plot_threads = get_active_plot_threads_for_scene(state)
        if active_plot_threads:
            plot_thread_context = "Plot threads relevant to this scene:\n"
            for thread in active_plot_threads[:3]:
                plot_thread_context += (
                    f"- {thread['name']}: {thread.get('status', 'active')}\n"
                )

    # Prepare the prompt for creating a scene hook
    prompt = f"""
    Create an engaging hook for this scene opening in {language_name}:

    SCENE OUTLINE:
    {scene_outline}

    {"PREVIOUS SCENE ENDING:" if previous_ending else ""}
    {previous_ending if previous_ending else ""}

    {plot_thread_context}

    Create a scene hook that:
    1. Immediately engages the reader in {language_name} style
    2. Sets the tone for the scene
    3. Connects naturally with the previous scene (if provided)
    4. Introduces key elements without being heavy-handed
    5. Uses engaging opening techniques appropriate for {language_name}
    6. Follows language-specific conventions for scene openings

    The hook should be 1-2 paragraphs that draw the reader into the scene.

    IMPORTANT: The scene hook must be written entirely in {language_name}.
    """

    try:
        # Generate the scene hook
        response = llm.invoke([HumanMessage(content=prompt)]).content

        # Clean up the response
        scene_hook = response.strip()

        return scene_hook

    except Exception as e:
        print(f"Error creating scene hook: {str(e)}")
        return ""
