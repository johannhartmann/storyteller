"""
StoryCraft Agent - Scene and chapter transition enhancement.

This module provides functionality to create smooth transitions between scenes and chapters,
addressing issues with abrupt transitions in the narrative.
"""

from typing import Dict, List, Any, Optional
from langchain_core.messages import HumanMessage
from storyteller_lib.config import llm
from storyteller_lib.models import StoryState

def analyze_transition_needs(current_content: str, next_content_outline: str, 
                           transition_type: str = "scene") -> Dict[str, Any]:
    """
    Analyze the transition needs between current content and next content.
    
    Args:
        current_content: The current scene or chapter content
        next_content_outline: The outline of the next scene or chapter
        transition_type: The type of transition ("scene" or "chapter")
        
    Returns:
        A dictionary with transition analysis results
    """
    # Prepare the prompt for analyzing transition needs
    prompt = f"""
    Analyze the transition needs between this {transition_type} and the next:
    
    CURRENT {transition_type.upper()} ENDING:
    {current_content[-500:]}
    
    NEXT {transition_type.upper()} OUTLINE:
    {next_content_outline}
    
    Evaluate:
    1. Is the current ending abrupt?
    2. Are there unresolved immediate tensions that should be addressed?
    3. Is there a clear connection to the next {transition_type}?
    4. What elements would create a smoother transition?
    5. What tone would be appropriate for the transition?
    
    Format your response as a structured JSON object.
    """
    
    try:
        # Define Pydantic models for structured output
        from pydantic import BaseModel, Field
        from typing import List
        
        class TransitionAnalysis(BaseModel):
            """Analysis of transition needs."""
            
            abruptness_score: int = Field(
                ge=1, le=10,
                description="How abrupt the current ending is (1=smooth, 10=very abrupt)"
            )
            unresolved_tensions: List[str] = Field(
                default_factory=list,
                description="Unresolved immediate tensions that should be addressed"
            )
            connection_strength: int = Field(
                ge=1, le=10,
                description="Strength of connection to the next content (1=weak, 10=strong)"
            )
            recommended_elements: List[str] = Field(
                default_factory=list,
                description="Elements that would create a smoother transition"
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
            "transition_length": "medium"
        }

def create_scene_transition(current_scene_content: str, next_scene_outline: str) -> str:
    """
    Create a smooth transition between scenes.
    
    Args:
        current_scene_content: The content of the current scene
        next_scene_outline: The outline of the next scene
        
    Returns:
        The transition text
    """
    # Analyze transition needs
    transition_analysis = analyze_transition_needs(current_scene_content, next_scene_outline, "scene")
    
    # Prepare the prompt for creating a scene transition
    prompt = f"""
    Create a smooth transition between these two scenes:
    
    CURRENT SCENE ENDING:
    {current_scene_content[-500:]}
    
    NEXT SCENE OUTLINE:
    {next_scene_outline}
    
    TRANSITION ANALYSIS:
    Abruptness Score: {transition_analysis["abruptness_score"]}/10
    Unresolved Tensions: {', '.join(transition_analysis["unresolved_tensions"])}
    Connection Strength: {transition_analysis["connection_strength"]}/10
    Recommended Elements: {', '.join(transition_analysis["recommended_elements"])}
    Recommended Tone: {transition_analysis["recommended_tone"]}
    
    Write a {transition_analysis["transition_length"]} transition (1-3 paragraphs) that:
    1. Provides closure to the current scene
    2. Creates a bridge to the next scene
    3. Maintains narrative flow and reader engagement
    4. Addresses any unresolved immediate tensions
    5. Sets up the next scene naturally
    
    The transition should feel organic and maintain the story's rhythm.
    """
    
    try:
        # Generate the transition
        response = llm.invoke([HumanMessage(content=prompt)]).content
        
        # Clean up the response
        transition = response.strip()
        
        return transition
    
    except Exception as e:
        print(f"Error creating scene transition: {str(e)}")
        return ""

def create_chapter_transition(current_chapter_data: Dict, next_chapter_data: Dict) -> str:
    """
    Create a smooth transition between chapters.
    
    Args:
        current_chapter_data: The data for the current chapter
        next_chapter_data: The data for the next chapter
        
    Returns:
        The transition text
    """
    # Extract relevant data
    current_chapter_title = current_chapter_data.get("title", "")
    current_chapter_outline = current_chapter_data.get("outline", "")
    next_chapter_title = next_chapter_data.get("title", "")
    next_chapter_outline = next_chapter_data.get("outline", "")
    
    # Get the last scene of the current chapter
    current_chapter_scenes = current_chapter_data.get("scenes", {})
    last_scene_num = max(current_chapter_scenes.keys(), key=int)
    last_scene_content = current_chapter_scenes[last_scene_num].get("content", "")
    
    # Analyze transition needs
    transition_analysis = analyze_transition_needs(last_scene_content, next_chapter_outline, "chapter")
    
    # Prepare the prompt for creating a chapter transition
    prompt = f"""
    Create a smooth chapter transition:
    
    CURRENT CHAPTER: {current_chapter_title}
    {current_chapter_outline}
    
    Last scene ending:
    {last_scene_content[-500:]}
    
    NEXT CHAPTER: {next_chapter_title}
    {next_chapter_outline}
    
    TRANSITION ANALYSIS:
    Abruptness Score: {transition_analysis["abruptness_score"]}/10
    Unresolved Tensions: {', '.join(transition_analysis["unresolved_tensions"])}
    Connection Strength: {transition_analysis["connection_strength"]}/10
    Recommended Elements: {', '.join(transition_analysis["recommended_elements"])}
    Recommended Tone: {transition_analysis["recommended_tone"]}
    
    Write a {transition_analysis["transition_length"]} chapter transition (2-4 paragraphs) that:
    1. Provides satisfying closure to the current chapter
    2. Creates anticipation for the next chapter
    3. Maintains narrative momentum
    4. Connects thematically to both chapters
    5. Addresses any unresolved immediate tensions
    
    The transition should be 2-4 paragraphs that could either end the current chapter
    or begin the next chapter.
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

def add_scene_transition(state: StoryState) -> Dict:
    """
    Add a smooth transition to the current scene.
    
    Args:
        state: The current state
        
    Returns:
        Updates to the state
    """
    chapters = state["chapters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    
    # Get the current chapter data
    chapter = chapters[current_chapter]
    
    # Get the current scene content
    scene_content = chapter["scenes"][current_scene]["content"]
    
    # Calculate the next scene number
    next_scene = str(int(current_scene) + 1)
    
    # Check if the next scene exists in the current chapter
    if next_scene in chapter["scenes"]:
        # Get the next scene outline
        next_scene_outline = chapter["scenes"][next_scene].get("outline", "")
        
        # Create a transition to the next scene
        transition = create_scene_transition(scene_content, next_scene_outline)
        
        # Add the transition to the current scene
        updated_scene_content = scene_content + "\n\n" + transition
        
        return {
            "chapters": {
                current_chapter: {
                    "scenes": {
                        current_scene: {
                            "content": updated_scene_content,
                            "has_transition": True
                        }
                    }
                }
            }
        }
    
    # If there's no next scene, we might be at the end of a chapter
    # In that case, we'll handle it in add_chapter_transition
    return {}

def add_chapter_transition(state: StoryState) -> Dict:
    """
    Add a smooth transition between chapters.
    
    Args:
        state: The current state
        
    Returns:
        Updates to the state
    """
    chapters = state["chapters"]
    current_chapter = state["current_chapter"]
    
    # Calculate the next chapter number
    next_chapter = str(int(current_chapter) + 1)
    
    # Check if the next chapter exists
    if next_chapter in chapters:
        # Get the current and next chapter data
        current_chapter_data = chapters[current_chapter]
        next_chapter_data = chapters[next_chapter]
        
        # Create a transition between chapters
        transition = create_chapter_transition(current_chapter_data, next_chapter_data)
        
        # Get the last scene of the current chapter
        current_chapter_scenes = current_chapter_data.get("scenes", {})
        if not current_chapter_scenes:
            return {}
            
        last_scene_num = max(current_chapter_scenes.keys(), key=int)
        last_scene_content = current_chapter_scenes[last_scene_num].get("content", "")
        
        # Add the transition to the last scene of the current chapter
        updated_scene_content = last_scene_content + "\n\n" + transition
        
        return {
            "chapters": {
                current_chapter: {
                    "scenes": {
                        last_scene_num: {
                            "content": updated_scene_content,
                            "has_chapter_transition": True
                        }
                    }
                }
            }
        }
    
    return {}