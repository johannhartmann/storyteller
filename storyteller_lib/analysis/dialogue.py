"""
./StoryCraft Agent - Dialogue enhancement and optimization.

This module provides functionality to analyze and improve dialogue quality,
addressing issues with expository dialogue, character voice consistency,
and dialogue naturalness in multiple languages.
"""

from typing import Dict, List, Any, Optional
from langchain_core.messages import HumanMessage
from storyteller_lib.core.config import llm, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.core.models import StoryState
def analyze_dialogue(scene_content: str, characters: Dict[str, Any], language: str = DEFAULT_LANGUAGE) -> Dict[str, Any]:
    """
    Analyze dialogue in a scene for quality and naturalness.
    
    Args:
        scene_content: The content of the scene
        characters: Character data for context
        language: The language of the dialogue (default: from config)
        
    Returns:
        A dictionary with dialogue analysis results
    """
    # Extract character names for reference
    character_names = []
    for char_id, char_data in characters.items():
        if "name" in char_data:
                character_names.append(char_data["name"])
    
    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        print(f"Warning: Unsupported language '{language}'. Falling back to {DEFAULT_LANGUAGE}.")
        language = DEFAULT_LANGUAGE
    
    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[language]
    
    # Use template system
    from storyteller_lib.prompts.renderer import render_prompt    
    # Prepare the prompt for analyzing dialogue
    prompt = render_prompt(
        'dialogue_analysis',
        language=language,
        scene_content=scene_content,
        character_names=', '.join(character_names),
        language_name=language_name
    )
    
    try:
        # Define Pydantic models for structured output
        from pydantic import BaseModel, Field
        from typing import List, Optional
        
class DialogueIssue(BaseModel):
            """A specific dialogue issue identified in the scene."""
            
            original_dialogue: str = Field(
                description="The original problematic dialogue"
            )
            character: str = Field(
                description="The character speaking"
            )
            issue_type: str = Field(
                description="Type of issue (exposition, naturalness, voice, etc.)"
            )
            problem: str = Field(
                description="Description of the problem"
            )
            suggestion: str = Field(
                description="Suggested improvement"
            )
        
class DialogueExchange(BaseModel):
            """A dialogue exchange between characters."""
            
            speakers: List[str] = Field(
                description="The characters speaking in this exchange"
            )
            content: str = Field(
                description="The content of the dialogue exchange"
            )
            purpose: str = Field(
                description="The purpose of this exchange (character development, plot advancement, exposition, etc.)"
            )
            subtext_level: int = Field(
                ge=1, le=10,
                description="Level of subtext in this exchange (1=direct/literal, 10=highly implicit)"
            )
        
        from pydantic import validator
        
class DialogueAnalysis(BaseModel):
            """Analysis of dialogue in a scene."""
            
            naturalness_score: int = Field(
                ge=1, le=10,
                description="How natural the dialogue sounds"
            )
            character_voice_score: int = Field(
                ge=1, le=10,
                description="How distinctive each character's voice is"
            )
            exposition_score: int = Field(
                ge=1, le=10,
                description="How naturally information is revealed"
            )
            subtext_score: int = Field(
                ge=1, le=10,
                description="How well dialogue uses subtext"
            )
            purpose_score: int = Field(
                ge=1, le=10,
                description="How purposeful each exchange is"
            )
            efficiency_score: int = Field(
                ge=1, le=10,
                description="How concise and efficient the dialogue is"
            )
            overall_score: int = Field(
                ge=1, le=10,
                description="Overall dialogue quality"
            )
            issues: List[DialogueIssue] = Field(
                default_factory=list,
                description="List of specific dialogue issues"
            )
            strengths: List[str] = Field(
                default_factory=list,
                description="Dialogue strengths"
            )
            recommendations: List[str] = Field(
                default_factory=list,
                description="General recommendations for improving dialogue"
            )
            # New fields
            exposition_instances: List[str] = Field(
                default_factory=list,
                description="Instances where characters explain things both already know"
            )
            dialogue_exchanges: List[DialogueExchange] = Field(
                default_factory=list,
                description="Analysis of individual dialogue exchanges"
            )
            dialogue_purpose_map: Dict[str, str] = Field(
                default_factory=dict,
                description="Map of dialogue exchanges to their purpose (character, plot, both, or none)"
            )
            
            @validator("dialogue_purpose_map", pre=True)
    def validate_dialogue_purpose_map(cls, v):
                """Validate dialogue_purpose_map to handle string values."""
                if isinstance(v, str):
                    # Convert string to a simple dictionary with a default key
                    return {"default": v}
                return v
            
class Config:
                """Configuration for the model."""
                validate_assignment = True
        
        # Create a structured LLM that outputs a DialogueAnalysis
        structured_llm = llm.with_structured_output(DialogueAnalysis)
        
        # Use the structured LLM to analyze dialogue
        dialogue_analysis = structured_llm.invoke(prompt)
        
        # Check if we got a valid response
        if dialogue_analysis is None:
                print("Error analyzing dialogue: LLM returned None")
                return {
                "naturalness_score": 5,
                "character_voice_score": 5,
                "exposition_score": 5,
                "subtext_score": 5,
                "purpose_score": 5,
                "efficiency_score": 5,
                "overall_score": 5,
                "issues": [],
                "strengths": [],
                "recommendations": ["Error analyzing dialogue: LLM returned None"]
            }
        
        # Convert Pydantic model to dictionary
            return dialogue_analysis.dict()
    
    except Exception as e:
        print(f"Error analyzing dialogue: {str(e)}")
            return {
            "naturalness_score": 5,
            "character_voice_score": 5,
            "exposition_score": 5,
            "subtext_score": 5,
            "purpose_score": 5,
            "efficiency_score": 5,
            "overall_score": 5,
            "issues": [],
            "strengths": [],
            "recommendations": ["Error analyzing dialogue"]
        }
    def _generate_character_dialogue_patterns(characters: Dict[str, Any], language: str = DEFAULT_LANGUAGE) -> str:
    """
    Generate dialogue patterns guidance for each character.
    
    Args:
        characters: Character data for context
        language: The language of the dialogue (default: from config)
        
    Returns:
        A string with dialogue patterns for each character
    """
    """Generate dialogue patterns guidance for each character."""
    patterns = []
    
    for char_id, char_data in characters.items():
        if "name" not in char_data:
                continue
            
        name = char_data["name"]
        traits = []
        
        # Add voice characteristics if available
        if "voice_characteristics" in char_data:
                traits.append(f"Voice: {char_data['voice_characteristics']}")
        
        # Add personality traits if available
        if "personality" in char_data and "traits" in char_data["personality"]:
                personality_traits = char_data["personality"]["traits"]
            if personality_traits:
                    traits.append(f"Traits: {', '.join(personality_traits)}")
        
        # Add background if available
        if "backstory" in char_data:
            # Extract a brief summary (first 50 words)
            backstory = char_data["backstory"]
            backstory_summary = " ".join(backstory.split()[:50])
            if backstory_summary:
                    traits.append(f"Background: {backstory_summary}...")
        
        if traits:
                patterns.append(f"{name}: {'; '.join(traits)}")
    
    return "\n".join(patterns)

def improve_dialogue(scene_content: str, dialogue_analysis: Dict[str, Any],
                    characters: Dict[str, Any], focus_on_exposition: bool = False,
                    language: str = DEFAULT_LANGUAGE) -> str:
    """
    Improve dialogue based on analysis.
    
    Args:
        scene_content: The content of the scene
        dialogue_analysis: The dialogue analysis results
        characters: Character data for context
        focus_on_exposition: Whether to focus specifically on reducing exposition
        language: The language of the dialogue (default: from config)
        
    Returns:
        The scene content with improved dialogue
    """
    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        print(f"Warning: Unsupported language '{language}'. Falling back to {DEFAULT_LANGUAGE}.")
        language = DEFAULT_LANGUAGE
    
    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[language]
    # If dialogue is already good and we're not focusing on exposition, no need to improve
    if dialogue_analysis["overall_score"] >= 8 and not focus_on_exposition:
        return scene_content
    
    # If we're focusing on exposition but exposition score is good, no need to improve
    if focus_on_exposition and dialogue_analysis.get("exposition_score", 0) >= 8:
        return scene_content
    
    # Extract character information for the template
    characters_info = {}
    for char_id, char_data in characters.items():
        if "name" in char_data:
                char_info = {
                "role": char_data.get("role", "Unknown"),
                "personality": char_data.get("personality", "Not specified")
            }
            
            # Add voice characteristics if available
            if "voice_characteristics" in char_data:
                    char_info["voice_characteristics"] = char_data['voice_characteristics']
            
            # Add emotional state if available
            if "emotional_state" in char_data:
                    char_info["emotional_state"] = char_data['emotional_state']
            
            characters_info[char_data['name']] = char_info
    
    # Get scene context
    from storyteller_lib.persistence.database import get_db_manager  
    db_manager = get_db_manager()
    current_chapter = 1
    current_scene = 1
    genre = "Unknown"
    tone = "Unknown"
    author_style = ""
    
    if db_manager and db_manager._db:
        with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
            cursor.execute("SELECT genre, tone, author FROM story_config WHERE id = 1")
            result = cursor.fetchone()
            if result:
                    genre = result['genre']
                tone = result['tone']
                if result['author']:
                        author_style = f"Write in the style of {result['author']}"
    
    # Use the template system for dialogue enhancement
    from storyteller_lib.prompts.renderer import render_prompt    
  
    prompt = render_prompt(
        'dialogue_enhancement',
        language=language,
        scene_content=scene_content,
        current_chapter=current_chapter,
        current_scene=current_scene,
        genre=genre,
        tone=tone,
        characters=characters_info,
        author_style=author_style
    )
    
    try:
        # Generate the improved scene
        response = llm.invoke([HumanMessage(content=prompt)]).content
        
        # Clean up the response
        improved_scene = response.strip()
        
        return improved_scene
    
    except Exception as e:
        print(f"Error improving dialogue: {str(e)}")
        return scene_content

def generate_dialogue_guidance(characters: Dict[str, Any], genre: str, tone: str,
                            language: str = DEFAULT_LANGUAGE) -> str:
    """
    Generate dialogue guidance for scene writing based on characters, genre, and tone.
    
    Args:
        characters: Character data
        genre: The genre of the story
        tone: The tone of the story
        language: The language of the dialogue (default: from config)
        
    Returns:
        Dialogue guidance text to include in scene writing prompts
    """
    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        print(f"Warning: Unsupported language '{language}'. Falling back to {DEFAULT_LANGUAGE}.")
        language = DEFAULT_LANGUAGE
    
    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[language]
    # Extract character names for reference
    character_names = []
    for char_id, char_data in characters.items():
        if "name" in char_data:
                character_names.append(char_data["name"])
    
    # Use template system
    from storyteller_lib.prompts.renderer import render_prompt    
    # Prepare the prompt for generating dialogue guidance
    prompt = render_prompt(
        'dialogue_guidance',
        language=language,
        genre=genre,
        tone=tone,
        character_names=', '.join(character_names),
        language_name=language_name
    )
    
    try:
        # Generate the dialogue guidance
        response = llm.invoke([HumanMessage(content=prompt)]).content
        
        # Clean up the response
        dialogue_guidance = response.strip()
        
        return f"""
        DIALOGUE GUIDANCE:
        {dialogue_guidance}
        """
    
    except Exception as e:
        print(f"Error generating dialogue guidance: {str(e)}")
        return f"""
        DIALOGUE GUIDANCE FOR {language_name.upper()}:
        1. Each character should have a distinctive voice reflecting their background and personality
        2. Dialogue should sound natural to native {language_name} speakers, not formal or expository
        3. Characters should not explain things they both already know
        4. Use subtext - characters often don't directly say what they mean
        5. Dialogue should reveal character and/or advance plot
        6. Break up dialogue with action beats and character observations
        7. Vary dialogue length based on character and emotional state
        8. Use dialect, slang, or speech patterns sparingly and consistently
        9. Consider cultural context and linguistic norms specific to {language_name}
        10. Respect idiomatic expressions and natural speech patterns in {language_name}
        """

def analyze_and_improve_dialogue(state: StoryState) -> Dict:
    """
    Analyze and improve the dialogue in the current scene.
    
    Args:
        state: The current state
        
    Returns:
        Updates to the state
    """
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    
    # Get the language from the state or use default
    language = state.get("language", DEFAULT_LANGUAGE)
    
    # Get scene content from database
    from storyteller_lib.persistence.database import get_db_manager  
    db_manager = get_db_manager()
    
    if not db_manager or not db_manager._db:
        raise RuntimeError("Database manager not available - cannot retrieve scene content")
    
    scene_content = db_manager.get_scene_content(int(current_chapter), int(current_scene))
    if not scene_content:
        # Try temporary state
        scene_content = state.get("current_scene_content", "")
        if not scene_content:
                raise RuntimeError(f"Scene {current_scene} of chapter {current_chapter} not found")
    
    # Get characters from database
    characters = {}
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT identifier, name, role, backstory, personality
            FROM characters
        """)
        for row in cursor.fetchall():
                characters[row['identifier']] = {
                'name': row['name'],
                'role': row['role'],
                'backstory': row['backstory'],
                'personality': row['personality']
            }
    
    # Analyze dialogue
    dialogue_analysis = analyze_dialogue(scene_content, characters, language)
    
    # Prepare minimal state updates
    dialogue_updates = {}
    
    # If dialogue needs improvement, improve the scene
    if dialogue_analysis["overall_score"] < 8:
        improved_scene = improve_dialogue(scene_content, dialogue_analysis, characters,
                                        language=language)
        
        # Update the scene content in database
        db_manager.save_scene_content(int(current_chapter), int(current_scene), improved_scene)
        
        # Update temporary state for next nodes
        dialogue_updates["current_scene_content"] = improved_scene
        dialogue_updates["dialogue_improved"] = True
    else:
        dialogue_updates["dialogue_improved"] = False
    
    return dialogue_updates