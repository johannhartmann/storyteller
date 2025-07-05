"""
StoryCraft Agent - Character creation and management.
"""

from typing import Any

from langchain_core.messages import AIMessage, RemoveMessage
from pydantic import BaseModel, Field

from storyteller_lib import track_progress
from storyteller_lib.core.config import (
    DEFAULT_LANGUAGE,
    llm,
)

# StoryState no longer used - working directly with database

# Default character data - simplified for fallback only
DEFAULT_CHARACTERS = {
    "hero": {
        "name": "Hero",
        "role": "Protagonist",
        "backstory": "Ordinary person with hidden potential",
        "evolution": ["Begins journey", "Faces first challenge"],
        "relationships": {},
    },
    "mentor": {
        "name": "Mentor",
        "role": "Guide",
        "backstory": "Wise figure with past experience",
        "evolution": ["Introduces hero to new world"],
        "relationships": {},
    },
    "villain": {
        "name": "Villain",
        "role": "Antagonist",
        "backstory": "Once good, corrupted by power",
        "evolution": ["Sends minions after hero"],
        "relationships": {},
    },
    "ally": {
        "name": "Loyal Ally",
        "role": "Supporting Character",
        "backstory": "Childhood friend or chance encounter with shared goals",
        "evolution": ["Joins hero's quest", "Provides crucial support"],
        "relationships": {},
    },
}

# Initial character knowledge to be added via CharacterKnowledgeManager
DEFAULT_CHARACTER_KNOWLEDGE = {
    "hero": {
        "public": ["Lived in small village", "Dreams of adventure"],
        "secret": ["Has a special lineage", "Possesses latent power"],
    },
    "mentor": {
        "public": ["Has many skills", "Traveled widely"],
        "secret": ["Former student of villain", "Hiding a prophecy"],
    },
    "villain": {
        "public": ["Rules with fear", "Seeks ancient artifact"],
        "secret": ["Was once good", "Has personal connection to hero"],
    },
    "ally": {
        "public": ["Skilled in practical matters", "Has local connections"],
        "secret": ["Harbors insecurities", "Has hidden talent"],
    },
}


# Pydantic models for structured data extraction
class PersonalityTraits(BaseModel):
    """Character personality traits model."""

    traits: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    flaws: list[str] = Field(default_factory=list)
    fears: list[str] = Field(default_factory=list)
    desires: list[str] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)


class EmotionalState(BaseModel):
    """Character emotional state model."""

    initial: str
    current: str
    journey: list[str] = Field(default_factory=list)


class InnerConflict(BaseModel):
    """Character inner conflict model."""

    description: str
    resolution_status: str = "unresolved"
    impact: str


class CharacterArc(BaseModel):
    """Character arc model."""

    type: str
    stages: list[str] = Field(default_factory=list)
    current_stage: str


class RelationshipDynamics(BaseModel):
    """Relationship dynamics between characters."""

    target_character: str = Field(
        description="Name of the other character in this relationship"
    )
    type: str
    dynamics: str
    evolution: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


# Flattened model to avoid nested dictionaries
class CharacterProfileFlat(BaseModel):
    """Flattened character profile for structured output without nested dictionaries."""

    name: str = Field(description="Character's name")
    role: str = Field(description="Character's role in the story")
    backstory: str = Field(description="Character's backstory")
    # Personality traits flattened
    personality_traits: str = Field(
        default="", description="Comma-separated list of personality traits"
    )
    personality_strengths: str = Field(
        default="", description="Comma-separated list of strengths"
    )
    personality_flaws: str = Field(
        default="", description="Comma-separated list of flaws"
    )
    personality_fears: str = Field(
        default="", description="Comma-separated list of fears"
    )
    personality_desires: str = Field(
        default="", description="Comma-separated list of desires"
    )
    personality_values: str = Field(
        default="", description="Comma-separated list of values"
    )
    # Emotional state flattened
    emotional_initial: str = Field(default="", description="Initial emotional state")
    emotional_current: str = Field(default="", description="Current emotional state")
    emotional_journey: str = Field(
        default="", description="Pipe-separated list of emotional journey stages"
    )
    # Inner conflicts flattened
    inner_conflict_descriptions: str = Field(
        default="", description="Pipe-separated list of inner conflict descriptions"
    )
    inner_conflict_resolutions: str = Field(
        default="", description="Pipe-separated list of resolution statuses"
    )
    inner_conflict_impacts: str = Field(
        default="", description="Pipe-separated list of conflict impacts"
    )
    # Character arc flattened
    arc_type: str = Field(default="", description="Type of character arc")
    arc_stages: str = Field(default="", description="Pipe-separated list of arc stages")
    arc_current_stage: str = Field(default="", description="Current stage in the arc")
    # Evolution
    evolution: str = Field(
        default="", description="Pipe-separated list of evolution points"
    )
    # Relationships flattened
    relationship_targets: str = Field(
        default="", description="Pipe-separated list of character names"
    )
    relationship_types: str = Field(
        default="", description="Pipe-separated list of relationship types"
    )
    relationship_dynamics: str = Field(
        default="", description="Pipe-separated list of relationship dynamics"
    )
    relationship_evolutions: str = Field(
        default="",
        description="Double-pipe-separated list of pipe-separated evolution lists",
    )
    relationship_conflicts: str = Field(
        default="",
        description="Double-pipe-separated list of pipe-separated conflict lists",
    )


class CharacterProfile(BaseModel):
    """Complete character profile model."""

    name: str
    role: str
    backstory: str
    personality: PersonalityTraits | None = None
    emotional_state: EmotionalState | None = None
    inner_conflicts: list[InnerConflict] = Field(default_factory=list)
    character_arc: CharacterArc | None = None
    evolution: list[str] = Field(default_factory=list)
    # Changed from Dict[str, RelationshipDynamics] to List to avoid nested dict issues with Gemini
    relationships: list[RelationshipDynamics] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format compatible with the existing system."""
        data = self.dict(exclude_none=True)
        # Convert relationships list back to dict format for compatibility
        if "relationships" in data and isinstance(data["relationships"], list):
            relationships_dict = {}
            for rel in data["relationships"]:
                # Use target_character as the key
                key = rel.get("target_character", rel.get("type", "unknown"))
                relationships_dict[key] = rel
            data["relationships"] = relationships_dict
        return data


class CharacterRole(BaseModel):
    """Basic character role information for initial planning."""

    role: str
    importance: str
    brief_description: str


class CharacterRoles(BaseModel):
    """Collection of character roles for the story."""

    roles: list[CharacterRole]


class BasicCharacterInfo(BaseModel):
    """Basic character information for initial generation."""

    name: str
    role: str
    backstory: str
    key_traits: list[str] = Field(default_factory=list)


class CharacterRelationship(BaseModel):
    """Relationship between two characters."""

    target_character: str
    relationship_type: str
    dynamics: str
    conflicts: list[str] = Field(default_factory=list)


def create_character(name: str, role: str, backstory: str = "", **kwargs) -> dict:
    """
    Create a new character with the given attributes.

    Args:
        name: The character's name
        role: The character's role in the story (protagonist, antagonist, etc.)
        backstory: The character's backstory
        **kwargs: Additional character attributes

    Returns:
        A CharacterProfile dictionary with the character's attributes
    """
    # Create a basic character profile
    character = {
        "name": name,
        "role": role,
        "backstory": backstory,
        "evolution": kwargs.get("evolution", []),
        "relationships": kwargs.get("relationships", {}),
    }

    # Add optional complex fields if provided
    if any(
        key in kwargs
        for key in ["traits", "strengths", "flaws", "fears", "desires", "values"]
    ):
        character["personality"] = {
            "traits": kwargs.get("traits", []),
            "strengths": kwargs.get("strengths", []),
            "flaws": kwargs.get("flaws", []),
            "fears": kwargs.get("fears", []),
            "desires": kwargs.get("desires", []),
            "values": kwargs.get("values", []),
        }

    if any(
        key in kwargs
        for key in [
            "initial_emotional_state",
            "current_emotional_state",
            "emotional_journey",
        ]
    ):
        character["emotional_state"] = {
            "initial": kwargs.get("initial_emotional_state", "Neutral"),
            "current": kwargs.get("current_emotional_state", "Neutral"),
            "journey": kwargs.get("emotional_journey", []),
        }

    if "inner_conflicts" in kwargs:
        character["inner_conflicts"] = kwargs.get("inner_conflicts", [])

    if any(key in kwargs for key in ["arc_type", "arc_stages", "current_arc_stage"]):
        character["character_arc"] = {
            "type": kwargs.get("arc_type", "growth"),
            "stages": kwargs.get("arc_stages", []),
            "current_stage": kwargs.get("current_arc_stage", "Beginning"),
        }

    return character


def generate_character_roles(
    story_outline: str,
    genre: str,
    tone: str,
    required_characters: list[str] = None,
    language: str = DEFAULT_LANGUAGE,
) -> list[CharacterRole]:
    """
    Generate a list of character roles needed for the story.

    Args:
        story_outline: The story outline
        genre: The story genre
        tone: The story tone
        required_characters: List of characters that must be included
        language: Target language for generation

    Returns:
        List of CharacterRole objects
    """
    # Language instruction no longer needed - prompting in target language

    # Prepare required characters instruction
    if required_characters and len(required_characters) > 0:
        f"""
        REQUIRED CHARACTERS (HIGHEST PRIORITY):
        The following characters MUST be included as they are central to the story:
        {', '.join(required_characters)}

        These characters are non-negotiable and must be included in your list of roles.
        """

    # Use template system
    from storyteller_lib.prompts.renderer import render_prompt

    # Create the prompt
    prompt = render_prompt(
        "character_roles",
        language=language,
        language_instruction=None,  # No longer needed
        story_outline=story_outline,
        tone=tone,
        genre=genre,
        required_characters=(
            ", ".join(required_characters) if required_characters else None
        ),
    )

    # Use structured output with Pydantic
    structured_output_llm = llm.with_structured_output(CharacterRoles)
    result = structured_output_llm.invoke(prompt)
    return result.roles


def generate_basic_character(
    role: CharacterRole,
    story_outline: str,
    genre: str,
    tone: str,
    author_style_guidance: str = "",
    language: str = DEFAULT_LANGUAGE,
) -> BasicCharacterInfo:
    """
    Generate basic information for a character based on their role.

    Args:
        role: The character's role information
        story_outline: The story outline
        genre: The story genre
        tone: The story tone
        author_style_guidance: Guidance on author's style
        language: Target language for generation

    Returns:
        BasicCharacterInfo object with name, role, backstory, and key traits
    """
    # Language instruction no longer needed - prompting in target language

    # Prepare author style guidance
    style_guidance = ""
    if author_style_guidance:
        style_guidance = f"""
        AUTHOR STYLE GUIDANCE:
        Consider these guidelines when creating the character:

        {author_style_guidance}
        """

    # Import prompt template system
    from storyteller_lib.prompts.renderer import render_prompt

    # Use template system

    # Create a simple template for basic character generation
    prompt = render_prompt(
        "create_character",
        language=language,
        language_instruction=None,  # No longer needed
        story_outline=story_outline,
        role=role.role,
        importance=role.importance,
        description=role.brief_description,
        tone=tone,
        genre=genre,
        style_guidance=style_guidance if author_style_guidance else None,
    )

    # Use structured output with Pydantic
    structured_output_llm = llm.with_structured_output(BasicCharacterInfo)
    return structured_output_llm.invoke(prompt)


def generate_personality_traits(
    character: BasicCharacterInfo, story_outline: str, language: str = DEFAULT_LANGUAGE
) -> PersonalityTraits:
    """
    Generate detailed personality traits for a character.

    Args:
        character: Basic character information
        story_outline: The story outline
        language: Target language for generation

    Returns:
        PersonalityTraits object
    """
    # Use template system
    from storyteller_lib.prompts.renderer import render_prompt

    # Create the prompt
    prompt = render_prompt(
        "personality_traits",
        language=language,
        language_instruction=None,  # No longer needed - prompting in target language
        name=character.name,
        role=character.role,
        backstory=character.backstory,
        key_traits=", ".join(character.key_traits),
        story_outline=story_outline,
    )

    # Use structured output with Pydantic
    structured_output_llm = llm.with_structured_output(PersonalityTraits)
    return structured_output_llm.invoke(prompt)


def generate_emotional_state(
    character: BasicCharacterInfo,
    personality: PersonalityTraits,
    language: str = DEFAULT_LANGUAGE,
) -> EmotionalState:
    """
    Generate the emotional state for a character.

    Args:
        character: Basic character information
        personality: Character's personality traits
        language: Target language for generation

    Returns:
        EmotionalState object
    """
    # Use template system
    from storyteller_lib.prompts.renderer import render_prompt

    # Create the prompt
    prompt = render_prompt(
        "emotional_state",
        language=language,
        language_instruction=None,  # No longer needed - prompting in target language
        name=character.name,
        role=character.role,
        backstory=character.backstory,
        traits=", ".join(personality.traits),
        strengths=", ".join(personality.strengths),
        flaws=", ".join(personality.flaws),
        fears=", ".join(personality.fears),
        desires=", ".join(personality.desires),
        values=", ".join(personality.values),
    )

    # Use structured output with Pydantic
    structured_output_llm = llm.with_structured_output(EmotionalState)
    return structured_output_llm.invoke(prompt)


def generate_inner_conflicts(
    character: BasicCharacterInfo,
    personality: PersonalityTraits,
    language: str = DEFAULT_LANGUAGE,
) -> list[InnerConflict]:
    """
    Generate inner conflicts for a character.

    Args:
        character: Basic character information
        personality: Character's personality traits
        language: Target language for generation

    Returns:
        List of InnerConflict objects
    """
    # Use template system
    from storyteller_lib.prompts.renderer import render_prompt

    # Create the prompt
    prompt = render_prompt(
        "inner_conflicts",
        language=language,
        language_instruction=None,  # No longer needed - prompting in target language
        name=character.name,
        role=character.role,
        backstory=character.backstory,
        traits=", ".join(personality.traits),
        strengths=", ".join(personality.strengths),
        flaws=", ".join(personality.flaws),
        fears=", ".join(personality.fears),
        desires=", ".join(personality.desires),
        values=", ".join(personality.values),
    )

    # Create a model for the response
    class InnerConflicts(BaseModel):
        conflicts: list[InnerConflict]

    # Use structured output with Pydantic
    structured_output_llm = llm.with_structured_output(InnerConflicts)
    result = structured_output_llm.invoke(prompt)
    return result.conflicts


def generate_character_arc(
    character: BasicCharacterInfo,
    inner_conflicts: list[InnerConflict],
    language: str = DEFAULT_LANGUAGE,
) -> CharacterArc:
    """
    Generate a character arc for a character.

    Args:
        character: Basic character information
        inner_conflicts: Character's inner conflicts
        language: Target language for generation

    Returns:
        CharacterArc object
    """
    # Use template system
    from storyteller_lib.prompts.renderer import render_prompt

    # Create the prompt
    prompt = render_prompt(
        "single_character_arc",
        language=language,
        language_instruction=None,  # No longer needed - prompting in target language
        name=character.name,
        role=character.role,
        backstory=character.backstory,
        inner_conflicts=" ".join(
            [f"- {conflict.description}" for conflict in inner_conflicts]
        ),
    )

    # Use structured output with Pydantic
    structured_output_llm = llm.with_structured_output(CharacterArc)
    return structured_output_llm.invoke(prompt)


def generate_character_facts(
    character: BasicCharacterInfo, story_outline: str, language: str = DEFAULT_LANGUAGE
) -> dict[str, list[str]]:
    """
    Generate known and secret facts about a character.

    Args:
        character: Basic character information
        story_outline: The story outline
        language: Target language for generation

    Returns:
        Dictionary with evolution data
    """
    # Use template system
    from storyteller_lib.prompts.renderer import render_prompt

    # Create the prompt
    prompt = render_prompt(
        "character_facts",
        language=language,
        language_instruction=None,  # No longer needed - prompting in target language
        name=character.name,
        role=character.role,
        backstory=character.backstory,
        story_outline=story_outline,
    )

    # Create a model for the response
    class CharacterEvolution(BaseModel):
        evolution: list[str]

    # Use structured output with Pydantic
    structured_output_llm = llm.with_structured_output(CharacterEvolution)
    result = structured_output_llm.invoke(prompt)
    return {"evolution": result.evolution}


# Simplified model for a single character relationship
class SingleRelationship(BaseModel):
    """Model for a single relationship between two characters."""

    relationship_type: str
    dynamics: str
    evolution: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


def generate_single_relationship(
    character: dict[str, Any],
    other_character: dict[str, Any],
    story_outline: str,
    language: str = DEFAULT_LANGUAGE,
) -> SingleRelationship:
    """
    Generate a relationship between two specific characters.

    Args:
        character: The first character
        other_character: The second character
        story_outline: The story outline
        language: Target language for generation

    Returns:
        SingleRelationship object describing their relationship
    """
    # Use template system
    from storyteller_lib.prompts.renderer import render_prompt

    # Create the prompt for a single relationship
    prompt = render_prompt(
        "single_relationship",
        language=language,
        language_instruction=None,  # No longer needed - prompting in target language
        char1_name=character["name"],
        char1_role=character["role"],
        char1_backstory=character["backstory"],
        char2_name=other_character["name"],
        char2_role=other_character["role"],
        char2_backstory=other_character["backstory"],
        story_outline=story_outline,
    )

    # Use structured output with Pydantic
    structured_output_llm = llm.with_structured_output(SingleRelationship)
    return structured_output_llm.invoke(prompt)


def establish_character_relationships(
    characters: dict[str, dict[str, Any]],
    story_outline: str,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, dict[str, Any]]:
    """
    Establish relationships between characters one pair at a time.

    Args:
        characters: Dictionary of characters
        story_outline: The story outline
        language: Target language for generation

    Returns:
        Dictionary of updated characters with relationships
    """
    # If there's only one character, no relationships to establish
    if len(characters) <= 1:
        return characters

    # Process each character
    updated_characters = {}

    for char_id, char_data in characters.items():
        # Get other characters
        other_characters = {k: v for k, v in characters.items() if k != char_id}

        # Create a dictionary for this character's relationships
        relationships = {}

        # Generate a relationship with each other character individually
        for other_id, other_data in other_characters.items():
            print(
                f"Generating relationship between {char_data['name']} and {other_data['name']}..."
            )

            # Generate the relationship
            relationship = generate_single_relationship(
                character=char_data,
                other_character=other_data,
                story_outline=story_outline,
                language=language,
            )

            # Add the relationship to the dictionary
            relationships[other_id] = relationship.dict()

        # Update the character with the relationships
        char_data_copy = char_data.copy()
        char_data_copy["relationships"] = relationships
        updated_characters[char_id] = char_data_copy

    return updated_characters


@track_progress
def generate_characters(params: dict) -> dict:
    """
    Generate detailed character profiles based on the story outline using a step-by-step approach.

    This function implements a multi-step process to create characters:
    1. Identify key character roles needed for the story
    2. Generate basic information for each character
    3. Enrich each character with personality traits, emotional states, etc.
    4. Establish relationships between characters

    Args:
        state: The current story state

    Returns:
        Dictionary with updated characters and messages
    """
    # Get full story outline from database
    from storyteller_lib.persistence.database import get_db_manager

    db_manager = get_db_manager()

    if not db_manager or not db_manager._db:
        raise RuntimeError(
            "Database manager not available - cannot retrieve story outline"
        )

    # Clear character ID map to avoid conflicts
    if db_manager:
        db_manager._character_id_map.clear()

    # Get from database
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT global_story FROM story_config WHERE id = 1")
        result = cursor.fetchone()
        if not result:
            raise RuntimeError("Story outline not found in database")
        global_story = result["global_story"]
    # Load configuration from database
    from storyteller_lib.core.config import get_story_config

    config = get_story_config()

    genre = config["genre"]
    tone = config["tone"]
    config["author"]
    initial_idea = config["initial_idea"]
    language = config["language"]

    # Get temporary workflow data from state
    initial_idea_elements = state.get("initial_idea_elements", {})
    author_style_guidance = state.get("author_style_guidance", "")

    # Extract required characters from initial idea if available
    required_characters = []
    if initial_idea and initial_idea_elements:
        characters_from_idea = initial_idea_elements.get("characters", [])
        if characters_from_idea:
            required_characters = characters_from_idea

    # Step 1: Identify key character roles needed for the story
    print("Step 1: Identifying key character roles...")
    character_roles = generate_character_roles(
        story_outline=global_story,
        genre=genre,
        tone=tone,
        required_characters=required_characters,
        language=language,
    )

    # Step 2: Generate basic information for each character
    print("Step 2: Generating basic character information...")
    characters_dict = {}

    for role in character_roles:
        # Generate basic character info
        basic_info = generate_basic_character(
            role=role,
            story_outline=global_story,
            genre=genre,
            tone=tone,
            author_style_guidance=author_style_guidance,
            language=language,
        )

        # Create a character ID from the name
        # Remove special characters and normalize for database compatibility
        import unicodedata

        normalized_name = unicodedata.normalize("NFKD", basic_info.name)
        # Keep only ASCII characters
        ascii_name = normalized_name.encode("ascii", "ignore").decode("ascii")
        # Replace spaces with underscores and convert to lowercase
        char_id = ascii_name.lower().replace(" ", "_").replace("-", "_")
        # Ensure we have a valid ID
        if not char_id:
            char_id = f"character_{len(characters_dict) + 1}"

        # Initialize the character with basic info
        characters_dict[char_id] = {
            "name": basic_info.name,
            "role": basic_info.role,
            "backstory": basic_info.backstory,
            "evolution": [],
            "relationships": {},
        }

        # Step 3a: Generate personality traits
        print(f"Step 3a: Generating personality traits for {basic_info.name}...")
        personality = generate_personality_traits(
            character=basic_info, story_outline=global_story, language=language
        )
        characters_dict[char_id]["personality"] = personality.dict()

        # Step 3b: Generate emotional state
        print(f"Step 3b: Generating emotional state for {basic_info.name}...")
        emotional_state = generate_emotional_state(
            character=basic_info, personality=personality, language=language
        )
        characters_dict[char_id]["emotional_state"] = emotional_state.dict()

        # Step 3c: Generate inner conflicts
        print(f"Step 3c: Generating inner conflicts for {basic_info.name}...")
        inner_conflicts = generate_inner_conflicts(
            character=basic_info, personality=personality, language=language
        )
        characters_dict[char_id]["inner_conflicts"] = [
            conflict.dict() for conflict in inner_conflicts
        ]

        # Step 3d: Generate character arc
        print(f"Step 3d: Generating character arc for {basic_info.name}...")
        character_arc = generate_character_arc(
            character=basic_info, inner_conflicts=inner_conflicts, language=language
        )
        characters_dict[char_id]["character_arc"] = character_arc.dict()

        # Step 3e: Generate character facts
        print(f"Step 3e: Generating character facts for {basic_info.name}...")
        facts = generate_character_facts(
            character=basic_info, story_outline=global_story, language=language
        )
        characters_dict[char_id]["evolution"] = facts["evolution"]

    # Step 4: Establish relationships between characters
    print("Step 4: Establishing relationships between characters...")
    characters_dict = establish_character_relationships(
        characters=characters_dict, story_outline=global_story, language=language
    )

    # Validate that we have at least 4 characters
    if len(characters_dict) < 4:
        print(
            f"Only {len(characters_dict)} characters were generated. Adding default characters to reach at least 4."
        )
        # Add missing default characters
        default_keys = list(DEFAULT_CHARACTERS.keys())
        for i in range(4 - len(characters_dict)):
            if i < len(default_keys):
                default_key = default_keys[i]
                if default_key not in characters_dict:
                    characters_dict[default_key] = DEFAULT_CHARACTERS[default_key]

    # Character profiles are now stored in database via database_integration
    # Only store character creation metadata in memory
    # Character creation metadata - this is just logging info, doesn't need persistence
    # Characters are already stored in the database via database_integration

    # Update state
    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]

    # Log each character
    from storyteller_lib.utils.progress_logger import log_progress

    for char_data in characters_dict.values():
        log_progress("character", character=char_data)

    # Create message for the user
    new_msg = AIMessage(
        content="I've developed detailed character profiles with interconnected backgrounds and motivations. Now I'll plan the chapters."
    )

    # Store characters in database
    from storyteller_lib.core.logger import get_logger
    from storyteller_lib.persistence.database import get_db_manager

    logger = get_logger(__name__)

    db_manager = get_db_manager()
    if db_manager:
        try:
            # Store each character first (without relationships)
            for char_id, char_data in characters_dict.items():
                db_manager.save_character(char_id, char_data)
            logger.info(f"Stored {len(characters_dict)} characters in database")

            # Second pass: Now save all relationships after all characters exist
            for char_id, char_data in characters_dict.items():
                if "relationships" in char_data:
                    # Re-save to update relationships
                    db_manager.save_character(char_id, char_data)
            logger.info("Updated character relationships")

            # Add initial character knowledge using the new system
            from storyteller_lib.universe.characters.knowledge import (
                CharacterKnowledgeManager,
            )

            knowledge_manager = CharacterKnowledgeManager()

            # Get the first scene ID (where characters are introduced)
            first_scene_id = db_manager.get_scene_id(1, 1)  # Chapter 1, Scene 1
            if first_scene_id:
                for char_id in characters_dict:
                    # Check if this character has default knowledge
                    if char_id in DEFAULT_CHARACTER_KNOWLEDGE:
                        char_db_id = knowledge_manager.get_character_id_by_name(char_id)
                        if char_db_id:
                            # Add public knowledge
                            for knowledge in DEFAULT_CHARACTER_KNOWLEDGE[char_id].get(
                                "public", []
                            ):
                                knowledge_manager.add_knowledge(
                                    char_db_id,
                                    knowledge,
                                    first_scene_id,
                                    knowledge_type="fact",
                                    visibility="public",
                                )
                            # Add secrets
                            for secret in DEFAULT_CHARACTER_KNOWLEDGE[char_id].get(
                                "secret", []
                            ):
                                knowledge_manager.add_knowledge(
                                    char_db_id,
                                    secret,
                                    first_scene_id,
                                    knowledge_type="secret",
                                    visibility="secret",
                                )
                            logger.info(f"Added initial knowledge for {char_id}")
        except Exception as e:
            logger.error(f"Could not store characters in database: {e}")
            raise

    # Return minimal state update - just character IDs with essential info
    minimal_characters = {
        char_id: {
            "name": char_data.get("name", char_id),
            "role": char_data.get("role", "Unknown"),
        }
        for char_id, char_data in characters_dict.items()
    }

    return {
        "characters": minimal_characters,
        "messages": [*[RemoveMessage(id=msg_id) for msg_id in message_ids], new_msg],
    }
