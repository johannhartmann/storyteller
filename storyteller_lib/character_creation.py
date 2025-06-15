"""
StoryCraft Agent - Character creation and management.
"""

from typing import Dict, List, Any, Optional, Union, Set
from pydantic import BaseModel, Field, validator

from storyteller_lib.config import llm, manage_memory_tool, search_memory_tool, MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState, CharacterProfile as CharacterProfileDict
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from storyteller_lib import track_progress

# Default character data - simplified for fallback only
DEFAULT_CHARACTERS = {
    "hero": {
        "name": "Hero",
        "role": "Protagonist",
        "backstory": "Ordinary person with hidden potential",
        "evolution": ["Begins journey", "Faces first challenge"],
        "known_facts": ["Lived in small village", "Dreams of adventure"],
        "secret_facts": ["Has a special lineage", "Possesses latent power"],
        "revealed_facts": [],
        "relationships": {}
    },
    "mentor": {
        "name": "Mentor",
        "role": "Guide",
        "backstory": "Wise figure with past experience",
        "evolution": ["Introduces hero to new world"],
        "known_facts": ["Has many skills", "Traveled widely"],
        "secret_facts": ["Former student of villain", "Hiding a prophecy"],
        "revealed_facts": [],
        "relationships": {}
    },
    "villain": {
        "name": "Villain",
        "role": "Antagonist",
        "backstory": "Once good, corrupted by power",
        "evolution": ["Sends minions after hero"],
        "known_facts": ["Rules with fear", "Seeks ancient artifact"],
        "secret_facts": ["Was once good", "Has personal connection to hero"],
        "revealed_facts": [],
        "relationships": {}
    },
    "ally": {
        "name": "Loyal Ally",
        "role": "Supporting Character",
        "backstory": "Childhood friend or chance encounter with shared goals",
        "evolution": ["Joins hero's quest", "Provides crucial support"],
        "known_facts": ["Skilled in practical matters", "Has local connections"],
        "secret_facts": ["Harbors insecurities", "Has hidden talent"],
        "revealed_facts": [],
        "relationships": {}
    }
}

# Pydantic models for structured data extraction
class PersonalityTraits(BaseModel):
    """Character personality traits model."""
    traits: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    flaws: List[str] = Field(default_factory=list)
    fears: List[str] = Field(default_factory=list)
    desires: List[str] = Field(default_factory=list)
    values: List[str] = Field(default_factory=list)

class EmotionalState(BaseModel):
    """Character emotional state model."""
    initial: str
    current: str
    journey: List[str] = Field(default_factory=list)

class InnerConflict(BaseModel):
    """Character inner conflict model."""
    description: str
    resolution_status: str = "unresolved"
    impact: str

class CharacterArc(BaseModel):
    """Character arc model."""
    type: str
    stages: List[str] = Field(default_factory=list)
    current_stage: str

class RelationshipDynamics(BaseModel):
    """Relationship dynamics between characters."""
    type: str
    dynamics: str
    evolution: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)

class CharacterProfile(BaseModel):
    """Complete character profile model."""
    name: str
    role: str
    backstory: str
    personality: Optional[PersonalityTraits] = None
    emotional_state: Optional[EmotionalState] = None
    inner_conflicts: List[InnerConflict] = Field(default_factory=list)
    character_arc: Optional[CharacterArc] = None
    evolution: List[str] = Field(default_factory=list)
    known_facts: List[str] = Field(default_factory=list)
    secret_facts: List[str] = Field(default_factory=list)
    revealed_facts: List[str] = Field(default_factory=list)
    relationships: Dict[str, RelationshipDynamics] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format compatible with the existing system."""
        return self.dict(exclude_none=True)

class CharacterRole(BaseModel):
    """Basic character role information for initial planning."""
    role: str
    importance: str
    brief_description: str

class CharacterRoles(BaseModel):
    """Collection of character roles for the story."""
    roles: List[CharacterRole]

class BasicCharacterInfo(BaseModel):
    """Basic character information for initial generation."""
    name: str
    role: str
    backstory: str
    key_traits: List[str] = Field(default_factory=list)

class CharacterRelationship(BaseModel):
    """Relationship between two characters."""
    target_character: str
    relationship_type: str
    dynamics: str
    conflicts: List[str] = Field(default_factory=list)

def create_character(name: str, role: str, backstory: str = "", **kwargs) -> Dict:
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
        "known_facts": kwargs.get("known_facts", []),
        "secret_facts": kwargs.get("secret_facts", []),
        "revealed_facts": kwargs.get("revealed_facts", []),
        "relationships": kwargs.get("relationships", {})
    }
    
    # Add optional complex fields if provided
    if any(key in kwargs for key in ["traits", "strengths", "flaws", "fears", "desires", "values"]):
        character["personality"] = {
            "traits": kwargs.get("traits", []),
            "strengths": kwargs.get("strengths", []),
            "flaws": kwargs.get("flaws", []),
            "fears": kwargs.get("fears", []),
            "desires": kwargs.get("desires", []),
            "values": kwargs.get("values", [])
        }
    
    if any(key in kwargs for key in ["initial_emotional_state", "current_emotional_state", "emotional_journey"]):
        character["emotional_state"] = {
            "initial": kwargs.get("initial_emotional_state", "Neutral"),
            "current": kwargs.get("current_emotional_state", "Neutral"),
            "journey": kwargs.get("emotional_journey", [])
        }
    
    if "inner_conflicts" in kwargs:
        character["inner_conflicts"] = kwargs.get("inner_conflicts", [])
    
    if any(key in kwargs for key in ["arc_type", "arc_stages", "current_arc_stage"]):
        character["character_arc"] = {
            "type": kwargs.get("arc_type", "growth"),
            "stages": kwargs.get("arc_stages", []),
            "current_stage": kwargs.get("current_arc_stage", "Beginning")
        }
    
    return character

def generate_character_roles(
    story_outline: str, 
    genre: str, 
    tone: str, 
    required_characters: List[str] = None,
    language: str = DEFAULT_LANGUAGE
) -> List[CharacterRole]:
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
    # Prepare language instruction
    language_instruction = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_instruction = f"""
        !!!CRITICAL LANGUAGE INSTRUCTION!!!
        Your response MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL content must be in {SUPPORTED_LANGUAGES[language.lower()]}.
        """
    
    # Prepare required characters instruction
    required_chars_instruction = ""
    if required_characters and len(required_characters) > 0:
        required_chars_instruction = f"""
        REQUIRED CHARACTERS (HIGHEST PRIORITY):
        The following characters MUST be included as they are central to the story:
        {', '.join(required_characters)}
        
        These characters are non-negotiable and must be included in your list of roles.
        """
    
    # Create the prompt
    prompt = f"""
    {language_instruction}
    
    Based on this story outline:
    
    {story_outline}
    
    Identify 4-6 key character roles needed for this {tone} {genre} story.
    {required_chars_instruction}
    
    For each character role, provide:
    1. The role in the story (protagonist, antagonist, mentor, etc.)
    2. The importance level (primary, secondary, tertiary)
    3. A brief description of what this character contributes to the story
    
    Focus on creating a balanced cast of characters that will drive the plot forward and create interesting dynamics.
    
    {language_instruction}
    """
    
    try:
        # Use structured output with Pydantic
        structured_output_llm = llm.with_structured_output(CharacterRoles)
        result = structured_output_llm.invoke(prompt)
        return result.roles
    except Exception as e:
        print(f"Error generating character roles: {str(e)}")
        
        # Fallback: Generate basic roles
        fallback_roles = [
            CharacterRole(role="Protagonist", importance="primary", brief_description="Main character who drives the story"),
            CharacterRole(role="Antagonist", importance="primary", brief_description="Character who opposes the protagonist"),
            CharacterRole(role="Mentor", importance="secondary", brief_description="Character who guides the protagonist"),
            CharacterRole(role="Ally", importance="secondary", brief_description="Character who helps the protagonist")
        ]
        
        # Add required characters if they're not already covered
        if required_characters:
            existing_roles = {role.role.lower() for role in fallback_roles}
            for char in required_characters:
                if not any(char.lower() in role.lower() for role in existing_roles):
                    fallback_roles.append(
                        CharacterRole(
                            role=char, 
                            importance="primary", 
                            brief_description=f"Required character from initial story concept"
                        )
                    )
        
        return fallback_roles

def generate_basic_character(
    role: CharacterRole, 
    story_outline: str, 
    genre: str, 
    tone: str,
    author_style_guidance: str = "",
    language: str = DEFAULT_LANGUAGE
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
    # Prepare language instruction
    language_instruction = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_instruction = f"""
        !!!CRITICAL LANGUAGE INSTRUCTION!!!
        Your response MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL content - including the character name, backstory, and traits - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
        The character name should be authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures.
        """
    
    # Prepare author style guidance
    style_guidance = ""
    if author_style_guidance:
        style_guidance = f"""
        AUTHOR STYLE GUIDANCE:
        Consider these guidelines when creating the character:
        
        {author_style_guidance}
        """
    
    # Create the prompt
    prompt = f"""
    {language_instruction}
    
    Based on this story outline:
    
    {story_outline}
    
    Create a character with the following role:
    
    Role: {role.role}
    Importance: {role.importance}
    Description: {role.brief_description}
    
    For this {tone} {genre} story, provide:
    
    1. A suitable name for the character
    2. The character's role in the story (be specific about their function)
    3. A concise backstory (3-5 sentences) that explains their motivations
    4. 3-5 key personality traits that define this character
    
    {style_guidance}
    
    Create a character that feels authentic and three-dimensional, with clear motivations that drive their actions in the story.
    
    {language_instruction}
    """
    
    try:
        # Use structured output with Pydantic
        structured_output_llm = llm.with_structured_output(BasicCharacterInfo)
        return structured_output_llm.invoke(prompt)
    except Exception as e:
        print(f"Error generating basic character info: {str(e)}")
        
        # Fallback: Create a basic character
        return BasicCharacterInfo(
            name=role.role,
            role=role.role,
            backstory=role.brief_description,
            key_traits=["Determined", "Resourceful", "Complex"]
        )

def generate_personality_traits(
    character: BasicCharacterInfo, 
    story_outline: str,
    language: str = DEFAULT_LANGUAGE
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
    # Prepare language instruction
    language_instruction = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_instruction = f"""
        !!!CRITICAL LANGUAGE INSTRUCTION!!!
        Your response MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL content must be in {SUPPORTED_LANGUAGES[language.lower()]}.
        """
    
    # Create the prompt
    prompt = f"""
    {language_instruction}
    
    For this character:
    
    Name: {character.name}
    Role: {character.role}
    Backstory: {character.backstory}
    Key Traits: {', '.join(character.key_traits)}
    
    Generate detailed personality traits including:
    
    1. 3-5 defining character traits
    2. 2-3 notable strengths that help them in the story
    3. 2-3 significant flaws or weaknesses that create obstacles
    4. 1-2 core fears that drive their behavior
    5. 1-2 deep desires or goals that motivate them
    6. 1-2 values or principles they hold dear
    
    Consider how these traits will influence their actions in this story:
    
    {story_outline}
    
    {language_instruction}
    """
    
    try:
        # Use structured output with Pydantic
        structured_output_llm = llm.with_structured_output(PersonalityTraits)
        return structured_output_llm.invoke(prompt)
    except Exception as e:
        print(f"Error generating personality traits: {str(e)}")
        
        # Fallback: Create basic personality traits based on key_traits
        return PersonalityTraits(
            traits=character.key_traits,
            strengths=["Adaptable", "Resourceful"],
            flaws=["Stubborn", "Impulsive"],
            fears=["Failure"],
            desires=["Success"],
            values=["Loyalty"]
        )

def generate_emotional_state(
    character: BasicCharacterInfo, 
    personality: PersonalityTraits,
    language: str = DEFAULT_LANGUAGE
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
    # Prepare language instruction
    language_instruction = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_instruction = f"""
        !!!CRITICAL LANGUAGE INSTRUCTION!!!
        Your response MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL content must be in {SUPPORTED_LANGUAGES[language.lower()]}.
        """
    
    # Create the prompt
    prompt = f"""
    {language_instruction}
    
    For this character:
    
    Name: {character.name}
    Role: {character.role}
    Backstory: {character.backstory}
    
    Personality:
    - Traits: {', '.join(personality.traits)}
    - Strengths: {', '.join(personality.strengths)}
    - Flaws: {', '.join(personality.flaws)}
    - Fears: {', '.join(personality.fears)}
    - Desires: {', '.join(personality.desires)}
    - Values: {', '.join(personality.values)}
    
    Determine:
    
    1. The character's initial emotional state at the beginning of the story
    2. Their current emotional state (same as initial for now)
    
    Describe each emotional state in 1-2 sentences that capture their feelings, outlook, and attitude.
    
    {language_instruction}
    """
    
    try:
        # Use structured output with Pydantic
        structured_output_llm = llm.with_structured_output(EmotionalState)
        return structured_output_llm.invoke(prompt)
    except Exception as e:
        print(f"Error generating emotional state: {str(e)}")
        
        # Fallback: Create a basic emotional state
        return EmotionalState(
            initial="Neutral with hints of anticipation",
            current="Neutral with hints of anticipation",
            journey=[]
        )

def generate_inner_conflicts(
    character: BasicCharacterInfo, 
    personality: PersonalityTraits,
    language: str = DEFAULT_LANGUAGE
) -> List[InnerConflict]:
    """
    Generate inner conflicts for a character.
    
    Args:
        character: Basic character information
        personality: Character's personality traits
        language: Target language for generation
        
    Returns:
        List of InnerConflict objects
    """
    # Prepare language instruction
    language_instruction = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_instruction = f"""
        !!!CRITICAL LANGUAGE INSTRUCTION!!!
        Your response MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL content must be in {SUPPORTED_LANGUAGES[language.lower()]}.
        """
    
    # Create the prompt
    prompt = f"""
    {language_instruction}
    
    For this character:
    
    Name: {character.name}
    Role: {character.role}
    Backstory: {character.backstory}
    
    Personality:
    - Traits: {', '.join(personality.traits)}
    - Strengths: {', '.join(personality.strengths)}
    - Flaws: {', '.join(personality.flaws)}
    - Fears: {', '.join(personality.fears)}
    - Desires: {', '.join(personality.desires)}
    - Values: {', '.join(personality.values)}
    
    Generate 1-2 inner conflicts this character struggles with. For each conflict:
    
    1. Provide a description of the conflict (e.g., "Desire for revenge vs. moral code")
    2. Set the resolution status as "unresolved" (since the story hasn't started)
    3. Explain how this conflict impacts the character's behavior
    
    Focus on conflicts that create interesting tension and drive character development.
    
    {language_instruction}
    """
    
    try:
        # Create a model for the response
        class InnerConflicts(BaseModel):
            conflicts: List[InnerConflict]
        
        # Use structured output with Pydantic
        structured_output_llm = llm.with_structured_output(InnerConflicts)
        result = structured_output_llm.invoke(prompt)
        return result.conflicts
    except Exception as e:
        print(f"Error generating inner conflicts: {str(e)}")
        
        # Fallback: Create a basic inner conflict
        return [
            InnerConflict(
                description=f"Desire for {personality.desires[0] if personality.desires else 'success'} vs. fear of {personality.fears[0] if personality.fears else 'failure'}",
                resolution_status="unresolved",
                impact="Causes hesitation at critical moments"
            )
        ]

def generate_character_arc(
    character: BasicCharacterInfo, 
    inner_conflicts: List[InnerConflict],
    language: str = DEFAULT_LANGUAGE
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
    # Prepare language instruction
    language_instruction = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_instruction = f"""
        !!!CRITICAL LANGUAGE INSTRUCTION!!!
        Your response MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL content must be in {SUPPORTED_LANGUAGES[language.lower()]}.
        """
    
    # Create the prompt
    prompt = f"""
    {language_instruction}
    
    For this character:
    
    Name: {character.name}
    Role: {character.role}
    Backstory: {character.backstory}
    
    Inner Conflicts:
    {' '.join([f"- {conflict.description}" for conflict in inner_conflicts])}
    
    Determine:
    
    1. The type of character arc they will undergo (e.g., growth, fall, redemption, flat, etc.)
    2. 3-5 potential stages in their character development journey
    3. Their current stage at the beginning of the story
    
    {language_instruction}
    """
    
    try:
        # Use structured output with Pydantic
        structured_output_llm = llm.with_structured_output(CharacterArc)
        return structured_output_llm.invoke(prompt)
    except Exception as e:
        print(f"Error generating character arc: {str(e)}")
        
        # Fallback: Create a basic character arc
        return CharacterArc(
            type="growth",
            stages=["Beginning", "Challenge", "Change", "Resolution"],
            current_stage="Beginning"
        )

def generate_character_facts(
    character: BasicCharacterInfo, 
    story_outline: str,
    language: str = DEFAULT_LANGUAGE
) -> Dict[str, List[str]]:
    """
    Generate known and secret facts about a character.
    
    Args:
        character: Basic character information
        story_outline: The story outline
        language: Target language for generation
        
    Returns:
        Dictionary with known_facts, secret_facts, and evolution
    """
    # Prepare language instruction
    language_instruction = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_instruction = f"""
        !!!CRITICAL LANGUAGE INSTRUCTION!!!
        Your response MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL content must be in {SUPPORTED_LANGUAGES[language.lower()]}.
        """
    
    # Create the prompt
    prompt = f"""
    {language_instruction}
    
    For this character:
    
    Name: {character.name}
    Role: {character.role}
    Backstory: {character.backstory}
    
    Based on this story outline:
    
    {story_outline}
    
    Generate:
    
    1. 2-4 known facts about the character (information that is known at the start)
    2. 1-3 secret facts about the character (information hidden initially)
    3. 1-2 evolution points (how the character might develop during the story)
    
    {language_instruction}
    """
    
    try:
        # Create a model for the response
        class CharacterFacts(BaseModel):
            known_facts: List[str]
            secret_facts: List[str]
            evolution: List[str]
        
        # Use structured output with Pydantic
        structured_output_llm = llm.with_structured_output(CharacterFacts)
        result = structured_output_llm.invoke(prompt)
        return {
            "known_facts": result.known_facts,
            "secret_facts": result.secret_facts,
            "evolution": result.evolution
        }
    except Exception as e:
        print(f"Error generating character facts: {str(e)}")
        
        # Fallback: Create basic facts
        return {
            "known_facts": [f"{character.name} is a {character.role}", f"Has a background as {character.backstory.split()[0]}"],
            "secret_facts": ["Has a hidden motivation", "Harbors a secret from the past"],
            "evolution": ["Will face a significant challenge", "May undergo a transformation"]
        }

# Simplified model for a single character relationship
class SingleRelationship(BaseModel):
    """Model for a single relationship between two characters."""
    relationship_type: str
    dynamics: str
    evolution: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)

def generate_single_relationship(
    character: Dict[str, Any],
    other_character: Dict[str, Any],
    story_outline: str,
    language: str = DEFAULT_LANGUAGE
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
    # Prepare language instruction
    language_instruction = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_instruction = f"""
        !!!CRITICAL LANGUAGE INSTRUCTION!!!
        Your response MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL content must be in {SUPPORTED_LANGUAGES[language.lower()]}.
        """
    
    # Create the prompt for a single relationship
    prompt = f"""
    {language_instruction}
    
    Define the relationship between these two characters:
    
    Character 1:
    Name: {character['name']}
    Role: {character['role']}
    Backstory: {character['backstory']}
    
    Character 2:
    Name: {other_character['name']}
    Role: {other_character['role']}
    Backstory: {other_character['backstory']}
    
    Based on this story outline:
    {story_outline}
    
    Define their relationship with:
    
    1. The type of relationship (friend, enemy, mentor, etc.)
    2. The dynamics between them (power balance, emotional connection)
    3. 1-2 potential conflicts or tensions between them
    4. 1-2 evolution points for how their relationship might develop
    
    {language_instruction}
    """
    
    try:
        # Use structured output with Pydantic
        structured_output_llm = llm.with_structured_output(SingleRelationship)
        return structured_output_llm.invoke(prompt)
    except Exception as e:
        print(f"Error generating relationship between {character['name']} and {other_character['name']}: {str(e)}")
        
        # Create a basic relationship based on roles
        if character['role'] == 'Protagonist' and other_character['role'] == 'Antagonist':
            return SingleRelationship(
                relationship_type="enemy",
                dynamics="Conflict and opposition",
                evolution=["Initial confrontation", "Escalating conflict"],
                conflicts=["Opposing goals", "Ideological differences"]
            )
        elif character['role'] == 'Protagonist' and other_character['role'] == 'Mentor':
            return SingleRelationship(
                relationship_type="student",
                dynamics="Learning and guidance",
                evolution=["Initial meeting", "Growing trust"],
                conflicts=["Resistance to advice", "Different approaches"]
            )
        elif character['role'] == 'Protagonist' and other_character['role'] == 'Ally':
            return SingleRelationship(
                relationship_type="friend",
                dynamics="Mutual support and trust",
                evolution=["Initial meeting", "Developing friendship"],
                conflicts=["Occasional disagreements", "Different priorities"]
            )
        else:
            return SingleRelationship(
                relationship_type="acquaintance",
                dynamics="Neutral interaction",
                evolution=["Initial meeting", "Developing relationship"],
                conflicts=["Potential misunderstandings", "Different backgrounds"]
            )

def establish_character_relationships(
    characters: Dict[str, Dict[str, Any]],
    story_outline: str,
    language: str = DEFAULT_LANGUAGE
) -> Dict[str, Dict[str, Any]]:
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
            print(f"Generating relationship between {char_data['name']} and {other_data['name']}...")
            
            # Generate the relationship
            relationship = generate_single_relationship(
                character=char_data,
                other_character=other_data,
                story_outline=story_outline,
                language=language
            )
            
            # Add the relationship to the dictionary
            relationships[other_id] = relationship.dict()
        
        # Update the character with the relationships
        char_data_copy = char_data.copy()
        char_data_copy['relationships'] = relationships
        updated_characters[char_id] = char_data_copy
    
    return updated_characters

@track_progress
def generate_characters(state: StoryState) -> Dict:
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
    from storyteller_lib.database_integration import get_db_manager
    db_manager = get_db_manager()
    
    if not db_manager or not db_manager._db:
        raise RuntimeError("Database manager not available - cannot retrieve story outline")
    
    # Get from database
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT global_story FROM story_config WHERE id = 1"
        )
        result = cursor.fetchone()
        if not result:
            raise RuntimeError("Story outline not found in database")
        global_story = result['global_story']
    genre = state["genre"]
    tone = state["tone"]
    author = state["author"]
    initial_idea = state.get("initial_idea", "")
    initial_idea_elements = state.get("initial_idea_elements", {})
    author_style_guidance = state["author_style_guidance"]
    language = state.get("language", DEFAULT_LANGUAGE)
    
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
        language=language
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
            language=language
        )
        
        # Create a character ID from the name
        char_id = basic_info.name.lower().replace(" ", "_")
        
        # Initialize the character with basic info
        characters_dict[char_id] = {
            "name": basic_info.name,
            "role": basic_info.role,
            "backstory": basic_info.backstory,
            "evolution": [],
            "known_facts": [],
            "secret_facts": [],
            "revealed_facts": [],
            "relationships": {}
        }
        
        # Step 3a: Generate personality traits
        print(f"Step 3a: Generating personality traits for {basic_info.name}...")
        personality = generate_personality_traits(
            character=basic_info,
            story_outline=global_story,
            language=language
        )
        characters_dict[char_id]["personality"] = personality.dict()
        
        # Step 3b: Generate emotional state
        print(f"Step 3b: Generating emotional state for {basic_info.name}...")
        emotional_state = generate_emotional_state(
            character=basic_info,
            personality=personality,
            language=language
        )
        characters_dict[char_id]["emotional_state"] = emotional_state.dict()
        
        # Step 3c: Generate inner conflicts
        print(f"Step 3c: Generating inner conflicts for {basic_info.name}...")
        inner_conflicts = generate_inner_conflicts(
            character=basic_info,
            personality=personality,
            language=language
        )
        characters_dict[char_id]["inner_conflicts"] = [conflict.dict() for conflict in inner_conflicts]
        
        # Step 3d: Generate character arc
        print(f"Step 3d: Generating character arc for {basic_info.name}...")
        character_arc = generate_character_arc(
            character=basic_info,
            inner_conflicts=inner_conflicts,
            language=language
        )
        characters_dict[char_id]["character_arc"] = character_arc.dict()
        
        # Step 3e: Generate character facts
        print(f"Step 3e: Generating character facts for {basic_info.name}...")
        facts = generate_character_facts(
            character=basic_info,
            story_outline=global_story,
            language=language
        )
        characters_dict[char_id]["known_facts"] = facts["known_facts"]
        characters_dict[char_id]["secret_facts"] = facts["secret_facts"]
        characters_dict[char_id]["evolution"] = facts["evolution"]
    
    # Step 4: Establish relationships between characters
    print("Step 4: Establishing relationships between characters...")
    characters_dict = establish_character_relationships(
        characters=characters_dict,
        story_outline=global_story,
        language=language
    )
    
    # Validate that we have at least 4 characters
    if len(characters_dict) < 4:
        print(f"Only {len(characters_dict)} characters were generated. Adding default characters to reach at least 4.")
        # Add missing default characters
        default_keys = list(DEFAULT_CHARACTERS.keys())
        for i in range(4 - len(characters_dict)):
            if i < len(default_keys):
                default_key = default_keys[i]
                if default_key not in characters_dict:
                    characters_dict[default_key] = DEFAULT_CHARACTERS[default_key]
    
    # Character profiles are now stored in database via database_integration
    # Only store character creation metadata in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": "character_creation_metadata",
        "value": {
            "character_count": len(characters_dict),
            "character_roles": {name: char.get("role", "") for name, char in characters_dict.items()},
            "creation_notes": "Characters created and stored in database"
        },
        "namespace": MEMORY_NAMESPACE
    })
    
    # Update state
    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]
    
    # Log each character
    from storyteller_lib.story_progress_logger import log_progress
    for char_data in characters_dict.values():
        log_progress("character", character=char_data)
    
    # Create message for the user
    new_msg = AIMessage(content="I've developed detailed character profiles with interconnected backgrounds and motivations. Now I'll plan the chapters.")
    
    # Store characters in database
    from storyteller_lib.database_integration import get_db_manager
    from storyteller_lib.logger import get_logger
    logger = get_logger(__name__)
    
    db_manager = get_db_manager()
    if db_manager:
        try:
            # Store each character
            for char_id, char_data in characters_dict.items():
                db_manager.save_character(char_id, char_data)
            logger.info(f"Stored {len(characters_dict)} characters in database")
        except Exception as e:
            logger.warning(f"Could not store characters in database: {e}")
    
    # Return minimal state update - just character IDs
    minimal_characters = {char_id: {"name": char_data.get("name", char_id)} 
                         for char_id, char_data in characters_dict.items()}
    
    return {
        "characters": minimal_characters,
        "messages": [
            *[RemoveMessage(id=msg_id) for msg_id in message_ids],
            new_msg
        ]
    }
