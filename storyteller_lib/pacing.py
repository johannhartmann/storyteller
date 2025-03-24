"""
StoryCraft Agent - Pacing control and optimization.

This module provides functionality to analyze and optimize the pacing of scenes,
addressing issues with slow narrative, verbose dialogue, and redundant descriptions.
"""

from typing import Dict, List, Any, Optional
from langchain_core.messages import HumanMessage
from storyteller_lib.config import llm
from storyteller_lib.models import StoryState

# Pacing types
PACING_TYPES = {
    "FAST": "fast",
    "MODERATE": "moderate",
    "SLOW": "slow",
    "VARIED": "varied"
}

def analyze_scene_pacing(scene_content: str, genre: str, tone: str) -> Dict[str, Any]:
    """
    Analyze the pacing of a scene and identify areas that could be tightened.
    
    Args:
        scene_content: The content of the scene
        genre: The genre of the story
        tone: The tone of the story
        
    Returns:
        A dictionary with pacing analysis results
    """
    # Prepare the prompt for analyzing scene pacing
    prompt = f"""
    Analyze the pacing of this {genre} scene with a {tone} tone:
    
    {scene_content}
    
    Evaluate the following aspects of pacing:
    
    1. Overall pacing (fast, moderate, slow, varied)
    2. Dialogue efficiency (concise vs. verbose)
    3. Description efficiency (vivid but concise vs. overly detailed)
    4. Action/plot advancement rate
    5. Internal monologue/reflection balance
    
    For each aspect, provide:
    - A rating from 1-10 (where 10 is excellent pacing, 1 is problematic)
    - Specific examples of text that could be tightened
    - Suggested revisions that would improve pacing while maintaining essential content
    
    Also identify:
    - Any sections where tension is lost due to pacing issues
    - Paragraphs or dialogue exchanges that could be condensed
    - Repetitive elements that slow the narrative
    
    Format your response as a structured JSON object.
    """
    
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
                         genre: str, tone: str) -> str:
    """
    Optimize the pacing of a scene based on analysis.
    
    Args:
        scene_content: The content of the scene
        pacing_analysis: The pacing analysis results
        genre: The genre of the story
        tone: The tone of the story
        
    Returns:
        The optimized scene content
    """
    # If pacing is already good, no need to optimize
    if pacing_analysis["overall_pacing_score"] >= 8:
        return scene_content
    
    # Prepare the prompt for optimizing scene pacing
    prompt = f"""
    Revise this {genre} scene with a {tone} tone to improve its pacing:
    
    {scene_content}
    
    Based on this pacing analysis:
    {pacing_analysis}
    
    Your task:
    1. Make dialogue more concise and impactful
    2. Tighten descriptive passages while maintaining vivid imagery
    3. Ensure internal monologues advance character development efficiently
    4. Maintain tension throughout the scene
    5. Preserve all plot points and character development
    
    The revised scene should be more concise while maintaining all essential elements.
    Focus especially on the specific issues identified in the analysis.
    
    IMPORTANT: Return the complete revised scene, not just the modified sections.
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
                           chapter_position: str, scene_position: str) -> str:
    """
    Generate pacing guidance for scene writing based on scene purpose and position.
    
    Args:
        scene_purpose: The purpose of the scene (e.g., action, character development)
        genre: The genre of the story
        tone: The tone of the story
        chapter_position: The position of the chapter (beginning, middle, end)
        scene_position: The position of the scene in the chapter (beginning, middle, end)
        
    Returns:
        Pacing guidance text to include in scene writing prompts
    """
    # Prepare the prompt for generating pacing guidance
    prompt = f"""
    Generate specific pacing guidance for a {scene_purpose} scene in a {genre} story with a {tone} tone.
    
    Context:
    - Chapter position: {chapter_position} of the story
    - Scene position: {scene_position} of the chapter
    
    Provide guidance on:
    1. Appropriate pacing type (fast, moderate, slow, varied)
    2. Dialogue-to-description ratio
    3. Sentence and paragraph length recommendations
    4. Internal monologue/reflection balance
    5. Tension development recommendations
    6. Word count target range
    
    Format your response as concise, actionable guidelines that could be included in a scene writing prompt.
    Focus on creating engaging, well-paced narrative appropriate for the genre, tone, and scene purpose.
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
        return """
        PACING GUIDANCE:
        1. Maintain a balanced pace appropriate for the scene's purpose
        2. Keep dialogue concise and purposeful - every line should reveal character or advance plot
        3. Vary sentence and paragraph length for rhythm
        4. Use shorter sentences and paragraphs during action or tension
        5. Balance description, dialogue, and action
        6. Limit internal monologues to key character insights
        7. Target word count: 2100-2800 words
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
    
    # Get the scene content
    scene_content = chapters[current_chapter]["scenes"][current_scene]["content"]
    
    # Analyze pacing
    pacing_analysis = analyze_scene_pacing(scene_content, genre, tone)
    
    # Store the pacing analysis in the state
    pacing_updates = {
        "chapters": {
            current_chapter: {
                "scenes": {
                    current_scene: {
                        "pacing_analysis": pacing_analysis
                    }
                }
            }
        }
    }
    
    # If pacing needs improvement, optimize the scene
    if pacing_analysis["overall_pacing_score"] < 8:
        optimized_scene = optimize_scene_pacing(scene_content, pacing_analysis, genre, tone)
        
        # Update the scene content with the optimized version
        pacing_updates["chapters"][current_chapter]["scenes"][current_scene]["content"] = optimized_scene
        pacing_updates["pacing_optimized"] = True
    else:
        pacing_updates["pacing_optimized"] = False
    
    return pacing_updates