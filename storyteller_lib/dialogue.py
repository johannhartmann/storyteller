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

def improve_dialogue(scene_content: str, dialogue_analysis: Dict[str, Any], 
                    characters: Dict[str, Any]) -> str:
    """
    Improve dialogue based on analysis.
    
    Args:
        scene_content: The content of the scene
        dialogue_analysis: The dialogue analysis results
        characters: Character data for context
        
    Returns:
        The scene content with improved dialogue
    """
    # If dialogue is already good, no need to improve
    if dialogue_analysis["overall_score"] >= 8:
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
    
    # Prepare the prompt for improving dialogue
    prompt = f"""
    Revise the dialogue in this scene to address the identified issues:
    
    {scene_content}
    
    CHARACTER INFORMATION:
    {character_info}
    
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
    
    Your task:
    1. Make dialogue more natural and conversational
    2. Ensure each character has a distinctive voice
    3. Remove exposition that characters would already know
    4. Add appropriate subtext and implied meaning
    5. Make dialogue more concise and purposeful
    6. Maintain all plot points and character development
    
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