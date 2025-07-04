"""
StoryCraft Agent - Character consistency tracking and verification.

This module provides functionality to track and ensure character consistency throughout the story,
addressing issues with character motivation inconsistencies in multiple languages.
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from storyteller_lib.core.config import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    llm,
)  # Memory manager imports removed - using state and database instead
from storyteller_lib.core.models import StoryState
from storyteller_lib.generation.story.plot_threads import (
    get_active_plot_threads_for_scene,
)


# Pydantic models for scene consistency checking
class ConsistencyIssue(BaseModel):
    """A consistency issue found in the scene."""

    issue_type: str = Field(
        description="Type of inconsistency (character, world, plot, timeline, detail)"
    )
    description: str = Field(description="What is inconsistent")
    conflicts_with: str = Field(
        description="What established element it conflicts with"
    )
    severity: int = Field(ge=1, le=10, description="Severity of the issue (1-10)")
    correction: str = Field(description="Suggested correction")


class SceneConsistencyCheck(BaseModel):
    """Complete scene consistency check results."""

    overall_consistency: int = Field(
        ge=1, le=10, description="Overall consistency score (1-10)"
    )
    character_consistency: bool = Field(description="Whether characters are consistent")
    world_consistency: bool = Field(description="Whether world elements are consistent")
    plot_consistency: bool = Field(description="Whether plot elements are consistent")
    timeline_consistency: bool = Field(description="Whether timeline is consistent")
    detail_consistency: bool = Field(description="Whether details are consistent")
    issues: list[ConsistencyIssue] = Field(
        default_factory=list, description="List of consistency issues"
    )
    suggestions: list[str] = Field(
        default_factory=list, description="General suggestions for improvement"
    )


def check_scene_consistency(
    state: StoryState, scene_content: str = None, language: str = DEFAULT_LANGUAGE
) -> dict[str, Any]:
    """
    Perform comprehensive consistency checking on a scene using the template system.

    This function checks for consistency across characters, world elements, plot,
    timeline, and details, using language-specific templates.

    Args:
        state: Current story state
        scene_content: Scene content to check (if None, gets from state/database)
        language: Target language for checking

    Returns:
        Dictionary with consistency check results
    """
    # Use template system
    from storyteller_lib.persistence.database import get_db_manager
    from storyteller_lib.prompts.renderer import render_prompt

    current_chapter = str(state.get("current_chapter", "1"))
    current_scene = str(state.get("current_scene", "1"))

    # Get database manager
    db_manager = get_db_manager()

    # Get scene content if not provided
    if not scene_content:
        if db_manager:
            scene_content = db_manager.get_scene_content(
                int(current_chapter), int(current_scene)
            )
        if not scene_content:
            scene_content = state.get("current_scene_content", "")
        if not scene_content:
            raise ValueError("No scene content available for consistency check")

    # Get characters from database
    characters = {}
    if db_manager and db_manager._db:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT identifier, name, role, backstory, personality,
                       emotional_state
                FROM characters
            """
            )
            for row in cursor.fetchall():
                characters[row["name"]] = {
                    "role": row["role"],
                    "traits": json.loads(row["personality"] or "{}").get("traits", []),
                    "current_state": json.loads(row["emotional_state"] or "{}").get(
                        "current", "Unknown"
                    ),
                }

    # Get world elements from database
    world_elements = {}
    if db_manager and db_manager._db:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT category, element_key, element_value
                FROM world_elements
            """
            )
            for row in cursor.fetchall():
                if row["category"] not in world_elements:
                    world_elements[row["category"]] = {}
                world_elements[row["category"]][row["element_key"]] = row[
                    "element_value"
                ]

    # Get previous events
    previous_events = []
    if db_manager and db_manager._db:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT c.chapter_number, s.scene_number, s.content
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE (c.chapter_number < ? OR (c.chapter_number = ? AND s.scene_number < ?))
                ORDER BY c.chapter_number DESC, s.scene_number DESC
                LIMIT 5
            """,
                (int(current_chapter), int(current_chapter), int(current_scene)),
            )

            for row in cursor.fetchall():
                if row["content"]:
                    summary = row["content"][:200] + "..."
                previous_events.append(
                    {
                        "chapter": row["chapter_number"],
                        "scene": row["scene_number"],
                        "summary": summary,
                    }
                )

    # Get plot threads
    plot_threads = get_active_plot_threads_for_scene(state)
    plot_thread_data = []
    for thread in plot_threads[:5]:  # Limit to 5
        plot_thread_data.append(
            {
                "name": thread.get("name", "Unknown"),
                "type": thread.get("type", "unknown"),
                "current_status": thread.get("current_development", "No status"),
            }
        )

    # Get timeline info (simplified for now)
    timeline = {
        "current": f"Chapter {current_chapter}, Scene {current_scene}",
        "important_dates": [],
    }

    # Get specific checks based on story type
    specific_checks = []
    genre = state.get("genre", "").lower()
    if "fantasy" in genre or "magic" in genre:
        specific_checks.append("Check magic system consistency")
    if "sci-fi" in genre or "science" in genre:
        specific_checks.append("Check technology consistency")
    if "mystery" in genre:
        specific_checks.append("Check clue and revelation consistency")

    # Render the consistency check prompt
    prompt = render_prompt(
        "consistency_check",
        language=language,
        scene_content=scene_content,
        current_chapter=current_chapter,
        current_scene=current_scene,
        genre=state.get("genre", "fantasy"),
        tone=state.get("tone", "adventurous"),
        characters=characters if characters else None,
        world_elements=world_elements if world_elements else None,
        previous_events=previous_events if previous_events else None,
        plot_threads=plot_thread_data if plot_thread_data else None,
        timeline=timeline,
        specific_checks=specific_checks if specific_checks else None,
    )

    try:
        # Use structured output
        structured_llm = llm.with_structured_output(SceneConsistencyCheck)
        result = structured_llm.invoke(prompt)

        # Convert to dictionary
        return result.dict()

    except Exception as e:
        print(f"Error in scene consistency check: {e}")
        # Fallback response
        return {
            "overall_consistency": 8,
            "character_consistency": True,
            "world_consistency": True,
            "plot_consistency": True,
            "timeline_consistency": True,
            "detail_consistency": True,
            "issues": [],
            "suggestions": [],
        }


def check_character_consistency(
    character_data: dict,
    scene_content: str,
    previous_scenes: list[str] = None,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, Any]:
    """
    Check if character actions and motivations are consistent with established traits.

    Args:
        character_data: The character data
        scene_content: The content of the current scene
        previous_scenes: Optional list of previous scene contents for context
        language: The language of the content (default: from config)

    Returns:
        A dictionary with consistency analysis results
    """
    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        print(
            f"Warning: Unsupported language '{language}'. Falling back to {DEFAULT_LANGUAGE}."
        )
        language = DEFAULT_LANGUAGE

    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[language]
    character_name = character_data.get("name", "")

    # Extract relevant character information
    character_data.get("backstory", "")
    personality = character_data.get("personality", {})
    personality.get("traits", [])
    personality.get("flaws", [])

    # Extract character arc information if available
    character_arc = character_data.get("character_arc", {})
    character_arc.get("type", "")
    character_arc.get("current_stage", "")

    # Extract emotional state if available
    emotional_state = character_data.get("emotional_state", {})
    emotional_state.get("current", "")

    # Import optimization utility
    from storyteller_lib.prompts.optimizer import log_prompt_size

    # Prepare context from previous scenes if available
    previous_context = ""
    if previous_scenes and len(previous_scenes) > 0:
        # Use full recent scene for character consistency check
        recent_scene = previous_scenes[-1]
        previous_context = f"Previous scene:\n{recent_scene}"

    # Use full scene content for character consistency check
    # Character development and consistency cannot be properly checked with truncated content

    # Prepare optimized character summary
    from storyteller_lib.prompts.optimizer import summarize_character

    char_summary = summarize_character(character_data, max_words=80)

    # Prepare the prompt for checking character consistency
    prompt = f"""
    Analyze {character_name}'s consistency in this scene written in {language_name}:

    CHARACTER SUMMARY:
    {json.dumps(char_summary, indent=2)}

    {previous_context}

    CURRENT SCENE:
    {scene_content}

    Evaluate:
    1. Are {character_name}'s actions consistent with established traits?
    2. Are their motivations clear and consistent with previous behavior?
    3. Does their dialogue match their established voice?
    4. Are emotional reactions appropriate to their personality and situation?
    5. Is character development gradual and believable?
    6. Are cultural and linguistic aspects of the character appropriate for {language_name}?
    7. Does the character's speech pattern match expectations for their background in {language_name}?

    For any inconsistencies, provide:
    - Description of the inconsistency
    - Why it's inconsistent with the character profile
    - A suggested revision in {language_name}

    Format your response as a structured JSON object.
    Analyze and respond in {language_name}.
    Keep analysis under 300 words.
    """

    # Log prompt size
    log_prompt_size(prompt, f"character consistency check for {character_name}")

    try:
        # Define Pydantic models for structured output

        from pydantic import BaseModel, Field

        class ConsistencyIssue(BaseModel):
            """A specific character consistency issue."""

            issue_type: str = Field(
                description="Type of inconsistency (action, motivation, dialogue, emotion)"
            )
            description: str = Field(description="Description of the inconsistency")
            reason: str = Field(
                description="Why it's inconsistent with the character profile"
            )
            suggestion: str = Field(description="Suggested revision")
            severity: int = Field(
                ge=1,
                le=10,
                description="Severity of the inconsistency (1=minor, 10=major)",
            )

        class CharacterMotivation(BaseModel):
            """A character's motivation."""

            motivation: str = Field(description="Description of the motivation")
            source: str = Field(
                description="Source of the motivation (backstory, recent event, etc.)"
            )
            strength: int = Field(
                ge=1,
                le=10,
                description="Strength of the motivation (1=weak, 10=driving force)",
            )
            consistency: int = Field(
                ge=1,
                le=10,
                description="How consistently this motivation is reflected in actions",
            )

        class ConsistencyAnalysis(BaseModel):
            """Analysis of character consistency in a scene."""

            character_name: str = Field(description="Name of the character")
            consistency_score: int = Field(
                ge=1,
                le=10,
                description="Overall consistency score (1=very inconsistent, 10=perfectly consistent)",
            )
            action_consistency: int = Field(
                ge=1,
                le=10,
                description="Consistency of actions with established traits",
            )
            motivation_clarity: int = Field(
                ge=1, le=10, description="Clarity and consistency of motivations"
            )
            dialogue_consistency: int = Field(
                ge=1, le=10, description="Consistency of dialogue with character voice"
            )
            emotional_consistency: int = Field(
                ge=1, le=10, description="Consistency of emotional reactions"
            )
            development_believability: int = Field(
                ge=1, le=10, description="Believability of character development"
            )
            # New fields
            motivation_alignment: int = Field(
                ge=1,
                le=10,
                description="How well actions align with established motivations",
            )
            decision_consistency: int = Field(
                ge=1, le=10, description="Consistency of decisions with past choices"
            )
            knowledge_consistency: int = Field(
                ge=1, le=10, description="Consistency of character knowledge"
            )
            motivations: list[CharacterMotivation] = Field(
                default_factory=list,
                description="Character's motivations identified in the scene",
            )
            issues: list[ConsistencyIssue] = Field(
                default_factory=list, description="List of specific consistency issues"
            )
            strengths: list[str] = Field(
                default_factory=list, description="Character consistency strengths"
            )

        # Create a structured LLM that outputs a ConsistencyAnalysis
        structured_llm = llm.with_structured_output(ConsistencyAnalysis)

        # Use the structured LLM to check character consistency
        consistency_analysis = structured_llm.invoke(prompt)

        # Convert Pydantic model to dictionary
        return consistency_analysis.dict()

    except Exception as e:
        print(f"Error checking character consistency: {str(e)}")
        return {
            "character_name": character_name,
            "consistency_score": 5,
            "action_consistency": 5,
            "motivation_clarity": 5,
            "dialogue_consistency": 5,
            "emotional_consistency": 5,
            "development_believability": 5,
            "issues": [],
            "strengths": [],
        }


def fix_character_inconsistencies(
    scene_content: str,
    character_data: dict,
    consistency_analysis: dict[str, Any],
    state: StoryState = None,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """
    Fix character inconsistencies in a scene.

    Args:
        scene_content: The content of the scene
        character_data: The character data
        consistency_analysis: The consistency analysis results
        state: The current state (optional, for plot thread integration)
        language: The language of the content (default: from config)

    Returns:
        The scene content with fixed inconsistencies
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
    # If consistency is already good, no need to fix
    if consistency_analysis["consistency_score"] >= 8:
        return scene_content

    # Extract character name
    character_name = character_data.get("name", "")

    # Get active plot threads if state is provided
    plot_thread_guidance = ""
    if state:
        active_plot_threads = get_active_plot_threads_for_scene(state)

        if active_plot_threads:
            # Filter plot threads related to this character
            character_threads = []
            for thread in active_plot_threads:
                if character_name in thread.get("related_characters", []):
                    character_threads.append(thread)

            if character_threads:
                # Format character-related threads
                thread_text = "Plot threads involving this character:\n"
                for thread in character_threads:
                    thread_text += f"- {thread['name']}: {thread['description']}\n  Status: {thread['status']}\n"

                # Combine thread guidance
                plot_thread_guidance = f"""
                CHARACTER PLOT THREAD INVOLVEMENT:
                {thread_text}

                Ensure that {character_name}'s actions, motivations, and dialogue remain consistent with their involvement in these plot threads.
                Character behavior should align with their role in each thread and reflect their knowledge of thread-related events.
                """

    # Prepare the prompt for fixing inconsistencies
    prompt = f"""
    Revise this scene written in {language_name} to fix character inconsistencies for {character_name}:

    {scene_content}

    CHARACTER PROFILE:
    {character_data}

    CONSISTENCY ANALYSIS:
    Overall Consistency Score: {consistency_analysis["consistency_score"]}/10
    Action Consistency: {consistency_analysis["action_consistency"]}/10
    Motivation Clarity: {consistency_analysis["motivation_clarity"]}/10
    Dialogue Consistency: {consistency_analysis["dialogue_consistency"]}/10
    Emotional Consistency: {consistency_analysis["emotional_consistency"]}/10
    Development Believability: {consistency_analysis["development_believability"]}/10

    LANGUAGE CONSIDERATIONS:
    - Ensure character dialogue and expressions are natural in {language_name}
    - Consider cultural context and linguistic norms specific to {language_name}
    - Maintain appropriate speech patterns for the character's background in {language_name}

    Issues to fix:
    {consistency_analysis["issues"]}

    {plot_thread_guidance}

    Your task:
    1. Revise {character_name}'s actions to be consistent with their established traits
    2. Clarify their motivations to align with previous behavior
    3. Adjust dialogue to match their established voice
    4. Make emotional reactions appropriate to their personality
    5. Ensure character development is gradual and believable
    6. Maintain consistency with the character's involvement in plot threads
    7. Ensure dialogue and expressions are culturally and linguistically appropriate in {language_name}
    8. Adapt speech patterns to match the character's background in {language_name} culture

    IMPORTANT:
    - Maintain the overall plot and scene structure
    - Only modify elements related to {character_name}'s consistency
    - Return the complete revised scene
    """

    try:
        # Generate the improved scene
        response = llm.invoke([HumanMessage(content=prompt)]).content

        # Clean up the response
        improved_scene = response.strip()

        return improved_scene

    except Exception as e:
        print(f"Error fixing character inconsistencies: {str(e)}")
        return scene_content


def _extract_character_motivations(
    char_name: str, scene_content: str, language: str = DEFAULT_LANGUAGE
) -> list[dict[str, Any]]:
    """
    Extract character motivations from a scene.

    Args:
        char_name: The character name
        scene_content: The content of the scene
        language: The language of the content (default: from config)

    Returns:
        A list of character motivations
    """
    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        print(
            f"Warning: Unsupported language '{language}'. Falling back to {DEFAULT_LANGUAGE}."
        )
        language = DEFAULT_LANGUAGE

    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[language]

    # Prepare the prompt for extracting motivations
    prompt = f"""
    Extract the motivations driving {char_name}'s actions in this scene written in {language_name}:

    {scene_content}

    Consider cultural and linguistic context in {language_name} when analyzing motivations.
    {scene_content}

    For each motivation:
    1. Identify the specific motivation
    2. Determine its source (backstory, recent event, immediate situation, etc.)
    3. Assess its strength (1-10 scale)
    4. Evaluate how consistently it's reflected in the character's actions

    Format your response as a structured JSON array of motivation objects.
    """

    try:
        # Define Pydantic model for structured output

        from pydantic import BaseModel, Field

        class Motivation(BaseModel):
            """A character motivation."""

            motivation: str = Field(description="Description of the motivation")
            source: str = Field(description="Source of the motivation")
            strength: int = Field(ge=1, le=10, description="Strength of the motivation")
            consistency: int = Field(ge=1, le=10, description="Consistency in actions")

        class MotivationList(BaseModel):
            """List of character motivations."""

            motivations: list[Motivation] = Field(description="List of motivations")

        # Create a structured LLM that outputs a MotivationList
        structured_llm = llm.with_structured_output(MotivationList)

        # Use the structured LLM to extract motivations
        motivation_list = structured_llm.invoke(prompt)

        # Check if we got a valid response
        if motivation_list is None:
            print("Error extracting character motivations: LLM returned None")
            return []

        # Ensure all motivations have valid strength and consistency values
        valid_motivations = []
        for m in motivation_list.motivations:
            # Ensure strength is at least 1
            if m.strength < 1:
                m.strength = 1
            # Ensure consistency is at least 1
            if m.consistency < 1:
                m.consistency = 1
            valid_motivations.append(m.dict())

        return valid_motivations

    except Exception as e:
        print(f"Error extracting character motivations: {str(e)}")
        return []


def track_character_consistency(state: StoryState) -> dict:
    """
    Track character consistency throughout the story.

    Args:
        state: The current state

    Returns:
        Updates to the state
    """
    state["chapters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]

    # Get the language from the state or use default
    language = state.get("language", DEFAULT_LANGUAGE)

    # Get database manager
    from storyteller_lib.persistence.database import get_db_manager

    db_manager = get_db_manager()

    if not db_manager or not db_manager._db:
        raise RuntimeError("Database manager not available")

    # Get characters from database
    characters = {}
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT identifier, name, role, backstory, personality
            FROM characters
        """
        )
        for row in cursor.fetchall():
            characters[row["identifier"]] = {
                "name": row["name"],
                "role": row["role"],
                "backstory": row["backstory"],
                "personality": row["personality"],
            }

    # Get the current scene content from database or temporary state
    scene_content = db_manager.get_scene_content(
        int(current_chapter), int(current_scene)
    )
    if not scene_content:
        scene_content = state.get("current_scene_content", "")
        if not scene_content:
            raise RuntimeError(
                f"Scene {current_scene} of chapter {current_chapter} not found"
            )

    # Get previous scenes for context (up to 2)
    previous_scenes = []

    # Get all scenes from database to find the last 2
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT c.chapter_number, s.scene_number, s.content
            FROM scenes s
            JOIN chapters c ON s.chapter_id = c.id
            WHERE (c.chapter_number < ? OR (c.chapter_number = ? AND s.scene_number < ?))
            ORDER BY c.chapter_number DESC, s.scene_number DESC
            LIMIT 2
        """,
            (int(current_chapter), int(current_chapter), int(current_scene)),
        )

        for row in cursor.fetchall():
            previous_scenes.append(row["content"])

    # Reverse to get chronological order
    previous_scenes = list(reversed(previous_scenes))

    # Check consistency for each character in the scene
    consistency_updates = {}
    character_consistency_analyses = {}
    character_motivations = {}

    for char_name, char_data in characters.items():
        # Skip if char_data is None
        if char_data is None:
            continue

        # Check if character appears in the scene
        if char_name.lower() in scene_content.lower() or (
            char_data.get("name", "").lower() in scene_content.lower()
        ):
            try:
                # Check character consistency
                consistency_analysis = check_character_consistency(
                    char_data, scene_content, previous_scenes, language
                )

                # Store the analysis
                character_consistency_analyses[char_name] = consistency_analysis

                # Extract and store character motivations
                motivations = _extract_character_motivations(
                    char_data.get("name", char_name), scene_content, language
                )
                if motivations:
                    character_motivations[char_name] = motivations
                    # Character motivations are temporary processing data
                    # They're already tracked in character_motivations dict for this scene

                # If there are significant inconsistencies, fix them
                if (
                    consistency_analysis["consistency_score"] < 7
                    and consistency_analysis["issues"]
                ):
                    improved_scene = fix_character_inconsistencies(
                        scene_content, char_data, consistency_analysis, state, language
                    )

                    # Update the scene content in database
                    db_manager.save_scene_content(
                        int(current_chapter), int(current_scene), improved_scene
                    )

                    # Update temporary state for next nodes
                    consistency_updates = {
                        "current_scene_content": improved_scene,
                        "consistency_fixed": True,
                    }

                    # Only fix one character at a time to avoid conflicting changes
                    break
            except Exception as e:
                print(f"Error tracking consistency for {char_name}: {str(e)}")

    # Store the consistency analyses and motivations
    return {
        **consistency_updates,
        "character_consistency_analyses": character_consistency_analyses,
        "character_motivations": character_motivations,
    }


def generate_consistency_guidance(
    characters: dict[str, Any], plot_threads: list[dict[str, Any]] = None
) -> str:
    """
    Generate character consistency guidance for scene writing.

    Args:
        characters: The character data
        plot_threads: Optional list of active plot threads

    Returns:
        Consistency guidance text to include in scene writing prompts
    """
    # Extract character information
    character_info = []
    for char_name, char_data in characters.items():
        if char_data is None:
            continue

        # Extract key consistency elements
        name = char_data.get("name", char_name)
        traits = char_data.get("personality", {}).get("traits", [])
        voice = char_data.get("voice_characteristics", "Not specified")
        arc = char_data.get("character_arc", {}).get("type", "Not specified")
        stage = char_data.get("character_arc", {}).get("current_stage", "Not specified")
        emotion = char_data.get("emotional_state", {}).get("current", "Not specified")

        character_info.append(
            f"- {name}: Traits: {', '.join(traits) if traits else 'Not specified'}, Voice: {voice}, Arc: {arc}, Current Stage: {stage}, Current Emotion: {emotion}"
        )

    # Prepare plot thread information if provided
    plot_thread_info = []
    if plot_threads:
        for thread in plot_threads:
            thread_name = thread.get("name", "")
            thread_desc = thread.get("description", "")
            thread_status = thread.get("status", "")
            related_chars = thread.get("related_characters", [])

            if related_chars:
                plot_thread_info.append(
                    f"- {thread_name}: {thread_desc} (Status: {thread_status}, Characters: {', '.join(related_chars)})"
                )

    # Prepare the prompt for generating consistency guidance
    prompt = f"""
    Generate character consistency guidance for scene writing based on these character profiles:

    {chr(10).join(character_info)}

    {f"Active plot threads involving these characters:\n{chr(10).join(plot_thread_info)}" if plot_thread_info else ""}

    Provide guidance on:
    1. How to maintain consistent character voices and behaviors
    2. How to ensure character motivations are clear and consistent
    3. How to handle character development in a gradual, believable way
    4. How to ensure emotional reactions are appropriate to personalities
    5. How to maintain character consistency with their involvement in plot threads
    6. Common consistency pitfalls to avoid

    Format your response as concise, actionable guidelines that could be included in a scene writing prompt.
    Focus on creating consistent, believable characters whose actions align with their involvement in plot threads.
    """

    try:
        # Generate the consistency guidance
        response = llm.invoke([HumanMessage(content=prompt)]).content

        # Clean up the response
        consistency_guidance = response.strip()

        return f"""
        CHARACTER CONSISTENCY GUIDANCE:
        {consistency_guidance}
        """

    except Exception as e:
        print(f"Error generating consistency guidance: {str(e)}")
        return """
        CHARACTER CONSISTENCY GUIDANCE:
        1. Maintain each character's unique voice and speech patterns throughout
        2. Ensure character actions align with their established traits and values
        3. Make character motivations clear and consistent with previous behavior
        4. Develop characters gradually rather than with sudden changes
        5. Ensure emotional reactions match the character's personality and situation
        6. Reference past experiences that influence current decisions
        7. Keep character knowledge consistent with what they've learned so far
        """
