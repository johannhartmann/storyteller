"""
StoryCraft Agent - Pacing control and optimization.

This module provides functionality to analyze and optimize the pacing of scenes,
addressing issues with slow narrative, verbose dialogue, and redundant descriptions
in multiple languages.
"""

from typing import Dict, List, Any, Optional
from langchain_core.messages import HumanMessage
from storyteller_lib.config import llm, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState

# Pacing types
PACING_TYPES = {
    "FAST": "fast",
    "MODERATE": "moderate",
    "SLOW": "slow",
    "VARIED": "varied"
}

def analyze_scene_pacing(scene_content: str, genre: str, tone: str,
                        language: str = DEFAULT_LANGUAGE) -> Dict[str, Any]:
    """
    Analyze the pacing of a scene and identify areas that could be tightened.
    
    Args:
        scene_content: The content of the scene
        genre: The genre of the story
        tone: The tone of the story
        language: The language of the scene (default: from config)
        
    Returns:
        A dictionary with pacing analysis results
    """
    # Use template system
    from storyteller_lib.prompt_templates import render_prompt
    
    # Render the pacing analysis prompt
    prompt = render_prompt(
        'pacing_analysis',
        language=language,
        scene_content=scene_content,
        genre=genre,
        tone=tone
    )
    
    try:
        # Define Pydantic models for structured output
        from pydantic import BaseModel, Field
        from typing import List, Optional
        
        class PacingIssue(BaseModel):
            """A specific pacing issue identified in the scene."""
            
            issue_type: str = Field(
                description="Type of pacing issue (dialogue, description, action, monologue, etc.)"
            )
            original_text: str = Field(
                description="The original text with pacing issues"
            )
            suggested_revision: str = Field(
                description="A more concise revision"
            )
            reason: str = Field(
                description="Why this change improves pacing"
            )
            location: str = Field(
                description="Beginning, middle, or end of scene"
            )
        
        class PacingAnalysis(BaseModel):
            """Analysis of a scene's pacing."""
            
            overall_pacing: str = Field(
                description="Overall pacing assessment (fast, moderate, slow, varied)"
            )
            overall_pacing_score: int = Field(
                ge=1, le=10,
                description="Overall pacing score (1=very slow, 10=excellent)"
            )
            dialogue_efficiency_score: int = Field(
                ge=1, le=10,
                description="How concise and effective the dialogue is"
            )
            description_efficiency_score: int = Field(
                ge=1, le=10,
                description="How efficient the descriptions are"
            )
            plot_advancement_score: int = Field(
                ge=1, le=10,
                description="How well the plot advances at an appropriate rate"
            )
            reflection_balance_score: int = Field(
                ge=1, le=10,
                description="How well internal monologue/reflection is balanced"
            )
            issues: List[PacingIssue] = Field(
                default_factory=list,
                description="List of specific pacing issues"
            )
            recommendations: List[str] = Field(
                default_factory=list,
                description="General recommendations for improving pacing"
            )
            appropriate_for_genre: bool = Field(
                description="Whether the pacing is appropriate for the genre and tone"
            )
        
        # Create a structured LLM that outputs a PacingAnalysis
        structured_llm = llm.with_structured_output(PacingAnalysis)
        
        # Use the structured LLM to analyze pacing
        pacing_analysis = structured_llm.invoke(prompt)
        
        # Convert Pydantic model to dictionary
        return pacing_analysis.dict()
    
    except Exception as e:
        print(f"Error analyzing scene pacing: {str(e)}")
        return {
            "overall_pacing": PACING_TYPES["MODERATE"],
            "overall_pacing_score": 5,
            "dialogue_efficiency_score": 5,
            "description_efficiency_score": 5,
            "plot_advancement_score": 5,
            "reflection_balance_score": 5,
            "issues": [],
            "recommendations": ["Error analyzing scene pacing"],
            "appropriate_for_genre": True
        }

def optimize_scene_pacing(scene_content: str, pacing_analysis: Dict[str, Any],
                          genre: str, tone: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Optimize the pacing of a scene based on analysis.
    
    Args:
        scene_content: The content of the scene
        pacing_analysis: The pacing analysis results
        genre: The genre of the story
        tone: The tone of the story
        language: The language of the scene (default: from config)
        
    Returns:
        The optimized scene content
    """
    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        print(f"Warning: Unsupported language '{language}'. Falling back to {DEFAULT_LANGUAGE}.")
        language = DEFAULT_LANGUAGE
    
    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[language]
    # If pacing is already good, no need to optimize
    if pacing_analysis["overall_pacing_score"] >= 8:
        return scene_content
    
    # Prepare the prompt for optimizing scene pacing
    prompt = f"""
    Revise this {genre} scene with a {tone} tone written in {language_name} to improve its pacing:
    
    {scene_content}
    
    Based on this pacing analysis:
    {pacing_analysis}
    
    Your task:
    1. Make dialogue more concise and impactful
    2. Tighten descriptive passages while maintaining vivid imagery
    3. Ensure internal monologues advance character development efficiently
    4. Maintain tension throughout the scene
    5. Preserve all plot points and character development
    6. Consider narrative pacing norms in {language_name} literature
    7. Respect cultural and linguistic conventions of {language_name}
    
    The revised scene should be more concise while maintaining all essential elements.
    Focus especially on the specific issues identified in the analysis.
    
    IMPORTANT:
    - Return the complete revised scene in {language_name}, not just the modified sections
    - Ensure the text sounds natural to native {language_name} speakers
    """
    
    try:
        # Generate the optimized scene
        response = llm.invoke([HumanMessage(content=prompt)]).content
        
        # Clean up the response
        optimized_scene = response.strip()
        
        return optimized_scene
    
    except Exception as e:
        print(f"Error optimizing scene pacing: {str(e)}")
        return scene_content

def generate_pacing_guidance(scene_purpose: str, genre: str, tone: str,
                            chapter_position: str, scene_position: str,
                            language: str = DEFAULT_LANGUAGE) -> str:
    """
    Generate pacing guidance for scene writing based on scene purpose and position.
    
    Args:
        scene_purpose: The purpose of the scene (e.g., action, character development)
        genre: The genre of the story
        tone: The tone of the story
        chapter_position: The position of the chapter (beginning, middle, end)
        scene_position: The position of the scene in the chapter (beginning, middle, end)
        language: The language of the scene (default: from config)
        
    Returns:
        Pacing guidance text to include in scene writing prompts
    """
    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        print(f"Warning: Unsupported language '{language}'. Falling back to {DEFAULT_LANGUAGE}.")
        language = DEFAULT_LANGUAGE
    
    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[language]
    # Prepare the prompt for generating pacing guidance
    prompt = f"""
    Generate specific pacing guidance for a {scene_purpose} scene in a {genre} story with a {tone} tone written in {language_name}.
    
    Context:
    - Chapter position: {chapter_position} of the story
    - Scene position: {scene_position} of the chapter
    - Language: {language_name}
    
    Provide guidance on:
    1. Appropriate pacing type (fast, moderate, slow, varied)
    2. Dialogue-to-description ratio
    3. Sentence and paragraph length recommendations
    4. Internal monologue/reflection balance
    5. Tension development recommendations
    6. Word count target range
    7. Language-specific pacing considerations for {language_name}
    8. Cultural narrative conventions in {language_name} literature
    
    Format your response as concise, actionable guidelines that could be included in a scene writing prompt.
    Focus on creating engaging, well-paced narrative appropriate for the genre, tone, scene purpose, and language.
    Provide your guidance in {language_name}.
    """
    
    try:
        # Generate the pacing guidance
        response = llm.invoke([HumanMessage(content=prompt)]).content
        
        # Clean up the response
        pacing_guidance = response.strip()
        
        return f"""
        PACING GUIDANCE:
        {pacing_guidance}
        """
    
    except Exception as e:
        print(f"Error generating pacing guidance: {str(e)}")
        return f"""
        PACING GUIDANCE FOR {language_name.upper()}:
        1. Maintain a balanced pace appropriate for the scene's purpose
        2. Keep dialogue concise and purposeful - every line should reveal character or advance plot
        3. Vary sentence and paragraph length for rhythm
        4. Use shorter sentences and paragraphs during action or tension
        5. Balance description, dialogue, and action
        6. Limit internal monologues to key character insights
        7. Target word count: 2100-2800 words
        8. Consider narrative pacing conventions in {language_name} literature
        9. Respect cultural storytelling traditions in {language_name}
        10. Adapt sentence structure to the natural flow of {language_name}
        """

def analyze_and_optimize_scene(state: StoryState) -> Dict:
    """
    Analyze and optimize the pacing of the current scene.
    
    Args:
        state: The current state
        
    Returns:
        Updates to the state
    """
    chapters = state["chapters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    genre = state["genre"]
    tone = state["tone"]
    
    # Get the language from the state or use default
    language = state.get("language", DEFAULT_LANGUAGE)
    
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
    
    # Analyze pacing
    pacing_analysis = analyze_scene_pacing(scene_content, genre, tone, language)
    
    # Prepare minimal state updates
    pacing_updates = {}
    
    # If pacing needs improvement, optimize the scene
    if pacing_analysis["overall_pacing_score"] < 8:
        optimized_scene = optimize_scene_pacing(scene_content, pacing_analysis, genre, tone, language)
        
        # Update the scene content in database
        db_manager.save_scene_content(int(current_chapter), int(current_scene), optimized_scene)
        
        # Update temporary state for next nodes
        pacing_updates["current_scene_content"] = optimized_scene
        pacing_updates["pacing_optimized"] = True
    else:
        pacing_updates["pacing_optimized"] = False
    
    return pacing_updates