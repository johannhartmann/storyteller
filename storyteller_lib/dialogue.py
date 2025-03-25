"""
./StoryCraft Agent - Dialogue enhancement and optimization.

This module provides functionality to analyze and improve dialogue quality,
addressing issues with expository dialogue, character voice consistency,
and dialogue naturalness.
"""

from typing import Dict, List, Any, Optional
from langchain_core.messages import HumanMessage
from storyteller_lib.config import llm
from storyteller_lib.models import StoryState

def analyze_dialogue(scene_content: str, characters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze dialogue in a scene for quality and naturalness.
    
    Args:
        scene_content: The content of the scene
        characters: Character data for context
        
    Returns:
        A dictionary with dialogue analysis results
    """
    # Extract character names for reference
    character_names = []
    for char_id, char_data in characters.items():
        if "name" in char_data:
            character_names.append(char_data["name"])
    
    # Prepare the prompt for analyzing dialogue
    prompt = f"""
    Analyze the dialogue in this scene:
    
    {scene_content}
    
    Characters in the story: {', '.join(character_names)}
    
    Evaluate the following aspects of dialogue:
    
    1. Naturalness - Does it sound like real speech?
    2. Character voice - Is each character's dialogue distinctive?
    3. Exposition - Is information revealed naturally or forced?
    4. Subtext - Does dialogue contain subtext and implied meaning?
    5. Purpose - Does each exchange advance character or plot?
    6. Efficiency - Is the dialogue concise or verbose?
    
    For each issue, provide:
    - The problematic dialogue
    - The character(s) speaking
    - Why it's problematic
    - A suggested improvement
    
    Also identify:
    - Dialogue that explains things characters would already know
    - Dialogue that could be more concise without losing meaning
    - Dialogue that lacks distinctive character voice
    
    Format your response as a structured JSON object.
    """
    
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

def _generate_character_dialogue_patterns(characters: Dict[str, Any]) -> str:
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
                    characters: Dict[str, Any], focus_on_exposition: bool = False) -> str:
    """
    Improve dialogue based on analysis.
    
    Args:
        scene_content: The content of the scene
        dialogue_analysis: The dialogue analysis results
        characters: Character data for context
        focus_on_exposition: Whether to focus specifically on reducing exposition
        
    Returns:
        The scene content with improved dialogue
    """
    # If dialogue is already good and we're not focusing on exposition, no need to improve
    if dialogue_analysis["overall_score"] >= 8 and not focus_on_exposition:
        return scene_content
    
    # If we're focusing on exposition but exposition score is good, no need to improve
    if focus_on_exposition and dialogue_analysis.get("exposition_score", 0) >= 8:
        return scene_content
    
    # Extract character information for context
    character_info = ""
    for char_id, char_data in characters.items():
        if "name" in char_data and "role" in char_data:
            character_info += f"{char_data['name']} ({char_data['role']}): "
            
            # Add voice characteristics if available
            if "voice_characteristics" in char_data:
                character_info += f"Voice: {char_data['voice_characteristics']}. "
            
            # Add personality traits if available
            if "personality" in char_data:
                character_info += f"Personality: {char_data['personality']}. "
            
            character_info += "\n"
    
    # Get exposition instances if available
    exposition_instances = dialogue_analysis.get("exposition_instances", [])
    exposition_instances_text = "\n".join([f"- {instance}" for instance in exposition_instances]) if exposition_instances else "None specifically identified."
    
    # Get dialogue purpose map if available
    dialogue_purpose_map = dialogue_analysis.get("dialogue_purpose_map", {})
    purpose_map_text = ""
    if dialogue_purpose_map:
        for exchange, purpose in dialogue_purpose_map.items():
            purpose_map_text += f"- \"{exchange}\": {purpose}\n"
    
    # Generate character dialogue patterns
    dialogue_patterns = _generate_character_dialogue_patterns(characters)
    
    # Prepare the prompt for improving dialogue
    prompt = f"""
    Revise the dialogue in this scene to address the identified issues:
    
    {scene_content}
    
    CHARACTER INFORMATION:
    {character_info}
    
    CHARACTER DIALOGUE PATTERNS:
    {dialogue_patterns}
    
    DIALOGUE ANALYSIS:
    Overall Score: {dialogue_analysis["overall_score"]}/10
    Naturalness: {dialogue_analysis["naturalness_score"]}/10
    Character Voice: {dialogue_analysis["character_voice_score"]}/10
    Exposition: {dialogue_analysis["exposition_score"]}/10
    Subtext: {dialogue_analysis["subtext_score"]}/10
    Purpose: {dialogue_analysis["purpose_score"]}/10
    Efficiency: {dialogue_analysis["efficiency_score"]}/10
    
    Issues to address:
    {dialogue_analysis["issues"]}
    
    Recommendations:
    {dialogue_analysis["recommendations"]}
    
    {"EXPOSITION ISSUES TO FOCUS ON:" if focus_on_exposition else ""}
    {"These instances explain things characters would already know:" if focus_on_exposition else ""}
    {exposition_instances_text if focus_on_exposition else ""}
    
    DIALOGUE REVISION GUIDELINES:
    - Cut any dialogue where a character explains something the listener already knows
    - Replace direct statements with reactions, questions, or partial information
    - Add physical actions, gestures, or facial expressions between dialogue lines
    - Create tension through what characters DON'T say or deliberately avoid
    - Use dialect, word choice, and sentence structure to differentiate characters
    
    BEFORE AND AFTER EXAMPLE:
    
    BEFORE: "As you know, the Salzmal is the ancient salt tax that the Patrizier imposed on us Sülfmeister."
    
    AFTER: [Character spits on ground] "Another tax collector. The Patrizier grow fat while we break our backs hauling salt." [Glances at the Salzmal symbol with disgust]
    
    Your task:
    1. Make dialogue more natural and conversational
    2. Ensure each character has a distinctive voice based on their patterns
    3. Remove exposition that characters would already know
    4. Add appropriate subtext and implied meaning
    5. Make dialogue more concise and purposeful
    6. Convert direct statements to implied meanings with subtext
    7. Replace information-heavy dialogue with character actions or observations
    8. Maintain all plot points and character development
    
    IMPORTANT:
    - Only modify the dialogue, keeping all narration and description intact
    - Preserve the essential information conveyed in the dialogue
    - Return the complete revised scene, not just the modified dialogue
    """
    
    try:
        # Generate the improved scene
        response = llm.invoke([HumanMessage(content=prompt)]).content
        
        # Clean up the response
        improved_scene = response.strip()
        
        return improved_scene
    
    except Exception as e:
        print(f"Error improving dialogue: {str(e)}")
        return scene_content

def generate_dialogue_guidance(characters: Dict[str, Any], genre: str, tone: str) -> str:
    """
    Generate dialogue guidance for scene writing based on characters, genre, and tone.
    
    Args:
        characters: Character data
        genre: The genre of the story
        tone: The tone of the story
        
    Returns:
        Dialogue guidance text to include in scene writing prompts
    """
    # Extract character names for reference
    character_names = []
    for char_id, char_data in characters.items():
        if "name" in char_data:
            character_names.append(char_data["name"])
    
    # Prepare the prompt for generating dialogue guidance
    prompt = f"""
    Generate specific dialogue guidance for a {genre} story with a {tone} tone.
    
    Characters: {', '.join(character_names)}
    
    Provide guidance on:
    1. How to make dialogue natural and conversational
    2. How to create distinctive voices for each character
    3. How to reveal information naturally through dialogue
    4. How to use subtext and implied meaning
    5. How to make dialogue concise and purposeful
    6. Common dialogue pitfalls to avoid in this genre
    
    Format your response as concise, actionable guidelines that could be included in a scene writing prompt.
    Focus on creating engaging, natural dialogue appropriate for the genre and tone.
    """
    
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
        return """
        DIALOGUE GUIDANCE:
        1. Each character should have a distinctive voice reflecting their background and personality
        2. Dialogue should sound natural, not formal or expository
        3. Characters should not explain things they both already know
        4. Use subtext - characters often don't directly say what they mean
        5. Dialogue should reveal character and/or advance plot
        6. Break up dialogue with action beats and character observations
        7. Vary dialogue length based on character and emotional state
        8. Use dialect, slang, or speech patterns sparingly and consistently
        """

def analyze_and_improve_dialogue(state: StoryState) -> Dict:
    """
    Analyze and improve the dialogue in the current scene.
    
    Args:
        state: The current state
        
    Returns:
        Updates to the state
    """
    chapters = state["chapters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    characters = state["characters"]
    
    # Get the scene content
    scene_content = chapters[current_chapter]["scenes"][current_scene]["content"]
    
    # Analyze dialogue
    dialogue_analysis = analyze_dialogue(scene_content, characters)
    
    # Store the dialogue analysis in the state
    dialogue_updates = {
        "chapters": {
            current_chapter: {
                "scenes": {
                    current_scene: {
                        "dialogue_analysis": dialogue_analysis
                    }
                }
            }
        }
    }
    
    # If dialogue needs improvement, improve the scene
    if dialogue_analysis["overall_score"] < 8:
        improved_scene = improve_dialogue(scene_content, dialogue_analysis, characters)
        
        # Update the scene content with the improved version
        dialogue_updates["chapters"][current_chapter]["scenes"][current_scene]["content"] = improved_scene
        dialogue_updates["dialogue_improved"] = True
    else:
        dialogue_updates["dialogue_improved"] = False
    
    return dialogue_updates