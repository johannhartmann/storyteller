"""
StoryCraft Agent - Repetition detection and reduction.

This module provides functionality to detect and reduce repetition in descriptions, phrases,
and character traits, addressing issues with redundancy in the narrative.
"""

from typing import Dict, List, Any, Optional
from langchain_core.messages import HumanMessage
from storyteller_lib.config import llm
from storyteller_lib.models import StoryState

def detect_repetition(text: str) -> Dict[str, Any]:
    """
    Detect repetitive phrases, descriptions, and themes in text.
    
    Args:
        text: The text to analyze
        
    Returns:
        A dictionary with repetition analysis results
    """
    # Prepare the prompt for detecting repetition
    prompt = f"""
    Analyze this text for repetition:
    
    {text}
    
    Identify:
    1. Repeated phrases or expressions
    2. Overused descriptive elements
    3. Redundant character traits or mannerisms
    4. Repetitive thematic statements
    
    For each repetition, provide:
    - The repeated element
    - Number of occurrences
    - Suggested alternatives for variation
    
    Format your response as a structured JSON object.
    """
    
    try:
        # Define Pydantic models for structured output
        from pydantic import BaseModel, Field
        from typing import List
        
        class RepetitiveElement(BaseModel):
            """A repetitive element in the text."""
            
            element: str = Field(
                description="The repeated phrase, description, or theme"
            )
            occurrences: int = Field(
                description="Number of times it appears"
            )
            alternatives: List[str] = Field(
                default_factory=list,
                description="Suggested alternatives for variation"
            )
        
        class RepetitionAnalysis(BaseModel):
            """Analysis of repetition in text."""
            
            repetitive_phrases: List[RepetitiveElement] = Field(
                default_factory=list,
                description="Repeated phrases or expressions"
            )
            repetitive_descriptions: List[RepetitiveElement] = Field(
                default_factory=list,
                description="Overused descriptive elements"
            )
            repetitive_character_traits: List[RepetitiveElement] = Field(
                default_factory=list,
                description="Redundant character traits or mannerisms"
            )
            repetitive_themes: List[RepetitiveElement] = Field(
                default_factory=list,
                description="Repetitive thematic statements"
            )
            overall_repetition_score: int = Field(
                ge=1, le=10,
                description="Overall repetition score (1=highly repetitive, 10=excellent variation)"
            )
            recommendations: List[str] = Field(
                default_factory=list,
                description="General recommendations for reducing repetition"
            )
        
        # Create a structured LLM that outputs a RepetitionAnalysis
        structured_llm = llm.with_structured_output(RepetitionAnalysis)
        
        # Use the structured LLM to detect repetition
        repetition_analysis = structured_llm.invoke(prompt)
        
        # Convert Pydantic model to dictionary
        return repetition_analysis.dict()
    
    except Exception as e:
        print(f"Error detecting repetition: {str(e)}")
        return {
            "repetitive_phrases": [],
            "repetitive_descriptions": [],
            "repetitive_character_traits": [],
            "repetitive_themes": [],
            "overall_repetition_score": 5,
            "recommendations": ["Error detecting repetition"]
        }

def reduce_repetition(text: str, repetition_analysis: Dict[str, Any]) -> str:
    """
    Reduce repetition in text based on analysis.
    
    Args:
        text: The text to improve
        repetition_analysis: The repetition analysis results
        
    Returns:
        The improved text with reduced repetition
    """
    # If repetition is already low, no need to reduce
    if repetition_analysis["overall_repetition_score"] >= 8:
        return text
    
    # Extract repetitive elements for the prompt
    repetitive_phrases = "\n".join([
        f"- \"{element['element']}\" ({element['occurrences']} times) - Alternatives: {', '.join(element['alternatives'])}"
        for element in repetition_analysis["repetitive_phrases"]
    ])
    
    repetitive_descriptions = "\n".join([
        f"- \"{element['element']}\" ({element['occurrences']} times) - Alternatives: {', '.join(element['alternatives'])}"
        for element in repetition_analysis["repetitive_descriptions"]
    ])
    
    repetitive_character_traits = "\n".join([
        f"- \"{element['element']}\" ({element['occurrences']} times) - Alternatives: {', '.join(element['alternatives'])}"
        for element in repetition_analysis["repetitive_character_traits"]
    ])
    
    repetitive_themes = "\n".join([
        f"- \"{element['element']}\" ({element['occurrences']} times) - Alternatives: {', '.join(element['alternatives'])}"
        for element in repetition_analysis["repetitive_themes"]
    ])
    
    # Prepare the prompt for reducing repetition
    prompt = f"""
    Revise this text to reduce repetition:
    
    {text}
    
    REPETITION ANALYSIS:
    Overall Repetition Score: {repetition_analysis["overall_repetition_score"]}/10
    
    Repetitive Phrases:
    {repetitive_phrases}
    
    Repetitive Descriptions:
    {repetitive_descriptions}
    
    Repetitive Character Traits:
    {repetitive_character_traits}
    
    Repetitive Themes:
    {repetitive_themes}
    
    Recommendations:
    {chr(10).join(repetition_analysis["recommendations"])}
    
    Your task:
    1. Replace repeated phrases with varied alternatives
    2. Diversify descriptive elements
    3. Vary character trait expressions
    4. Rephrase repetitive thematic statements
    5. Maintain the original meaning and tone
    
    IMPORTANT:
    - Preserve the overall narrative and content
    - Maintain the same level of detail and information
    - Return the complete revised text
    """
    
    try:
        # Generate the improved text
        response = llm.invoke([HumanMessage(content=prompt)]).content
        
        # Clean up the response
        improved_text = response.strip()
        
        return improved_text
    
    except Exception as e:
        print(f"Error reducing repetition: {str(e)}")
        return text

def track_story_repetition(state: StoryState) -> Dict[str, Any]:
    """
    Track repetition across the entire story.
    
    Args:
        state: The current state
        
    Returns:
        A dictionary with story-level repetition analysis
    """
    chapters = state["chapters"]
    
    # Collect all scene content
    all_content = ""
    for chapter_num, chapter in chapters.items():
        for scene_num, scene in chapter["scenes"].items():
            if "content" in scene:
                all_content += scene["content"] + "\n\n"
    
    # Analyze repetition across the story
    repetition_analysis = detect_repetition(all_content)
    
    return {
        "story_repetition_analysis": repetition_analysis
    }

def analyze_scene_repetition(state: StoryState) -> Dict:
    """
    Analyze and reduce repetition in the current scene.
    
    Args:
        state: The current state
        
    Returns:
        Updates to the state
    """
    chapters = state["chapters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    
    # Get database manager
    from storyteller_lib.database_integration import get_db_manager
    db_manager = get_db_manager()
    
    if not db_manager or not db_manager._db:
        raise RuntimeError("Database manager not available")
    
    # Get the scene content from database or temporary state
    scene_content = db_manager.get_scene_content(int(current_chapter), int(current_scene))
    if not scene_content:
        scene_content = state.get("current_scene_content", "")
        if not scene_content:
            raise RuntimeError(f"Scene {current_scene} of chapter {current_chapter} not found")
    
    # Analyze repetition
    repetition_analysis = detect_repetition(scene_content)
    
    # Prepare minimal state updates
    repetition_updates = {}
    
    # If repetition needs improvement, reduce it
    if repetition_analysis["overall_repetition_score"] < 8:
        improved_scene = reduce_repetition(scene_content, repetition_analysis)
        
        # Update the scene content in database
        db_manager.save_scene_content(int(current_chapter), int(current_scene), improved_scene)
        
        # Update temporary state for next nodes
        repetition_updates["current_scene_content"] = improved_scene
        repetition_updates["repetition_reduced"] = True
    else:
        repetition_updates["repetition_reduced"] = False
    
    return repetition_updates

def generate_variation_guidance(repetitive_elements: List[Dict[str, Any]] = None) -> str:
    """
    Generate guidance for avoiding repetition in scene writing.
    
    Args:
        repetitive_elements: Optional list of repetitive elements from previous scenes
        
    Returns:
        Variation guidance text to include in scene writing prompts
    """
    # Prepare context from repetitive elements if available
    repetition_context = ""
    if repetitive_elements and len(repetitive_elements) > 0:
        elements_text = "\n".join([
            f"- \"{element['element']}\" - Avoid by using: {', '.join(element['alternatives'])}"
            for element in repetitive_elements[:5]  # Limit to top 5
        ])
        
        repetition_context = f"""
        Previously identified repetitive elements to avoid:
        {elements_text}
        """
    
    # Prepare the prompt for generating variation guidance
    prompt = f"""
    Generate guidance for avoiding repetition in scene writing.
    
    {repetition_context}
    
    Provide guidance on:
    1. How to vary descriptive language
    2. How to avoid repeating the same phrases
    3. How to diversify character expressions and mannerisms
    4. How to present recurring themes in fresh ways
    5. Common repetition pitfalls to avoid
    
    Format your response as concise, actionable guidelines that could be included in a scene writing prompt.
    Focus on creating varied, engaging prose.
    """
    
    try:
        # Generate the variation guidance
        response = llm.invoke([HumanMessage(content=prompt)]).content
        
        # Clean up the response
        variation_guidance = response.strip()
        
        return f"""
        VARIATION GUIDANCE:
        {variation_guidance}
        """
    
    except Exception as e:
        print(f"Error generating variation guidance: {str(e)}")
        return """
        VARIATION GUIDANCE:
        1. Use a thesaurus to find alternative words for commonly repeated terms
        2. Vary sentence structure and length to create rhythm
        3. Describe characters through different senses (sight, sound, smell, etc.)
        4. Use different techniques to convey emotions (dialogue, body language, internal thoughts)
        5. Introduce new metaphors and similes rather than reusing the same ones
        6. Alternate between showing and telling for important information
        7. Vary how you transition between scenes and paragraphs
        """