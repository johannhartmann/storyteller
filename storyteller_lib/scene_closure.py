"""
StoryCraft Agent - Scene closure verification and management.

This module provides functionality to detect and fix abrupt scene endings,
ensuring proper narrative closure for each scene.
"""

from typing import Dict, List, Any, Tuple
from langchain_core.messages import HumanMessage
from storyteller_lib.config import llm
from storyteller_lib.models import StoryState
from storyteller_lib.plot_threads import get_active_plot_threads_for_scene

# Scene closure status options
CLOSURE_STATUS = {
    "COMPLETE": "complete",
    "ABRUPT": "abrupt",
    "TRANSITIONAL": "transitional",
    "CLIFFHANGER": "cliffhanger"
}

def analyze_scene_closure(scene_content: str, chapter_num: str, scene_num: str) -> Dict[str, Any]:
    """
    Analyze a scene for proper narrative closure.
    
    Args:
        scene_content: The content of the scene
        chapter_num: The chapter number
        scene_num: The scene number
        
    Returns:
        A dictionary with closure analysis results
    """
    # Prepare the prompt for analyzing scene closure
    prompt = f"""
    Analyze the closure of this scene from Chapter {chapter_num}, Scene {scene_num}:
    
    {scene_content}
    
    Evaluate whether this scene has proper narrative closure or ends abruptly.
    
    A scene with proper closure should:
    1. Resolve the immediate tension or question raised in the scene
    2. Complete the action or interaction that was central to the scene
    3. Provide a sense of completion or transition to the next scene
    4. Not end mid-paragraph, mid-dialogue, or mid-action without purpose
    
    A scene can end with a cliffhanger, but even cliffhangers should feel intentional
    rather than abrupt or incomplete.
    
    Provide the following in your analysis:
    1. Closure status: "complete", "abrupt", "transitional", or "cliffhanger"
    2. Closure score: 1-10 (where 10 is perfect closure, 1 is completely abrupt)
    3. Issues: List specific issues with the scene closure if any
    4. Recommendations: Suggestions for improving the scene closure
    
    Format your response as a valid JSON object.
    """
    
    try:
        # Define a Pydantic model for structured output
        from pydantic import BaseModel, Field
        
        class SceneClosureAnalysis(BaseModel):
            """Analysis of a scene's closure."""
            
            closure_status: str = Field(
                description="The closure status: complete, abrupt, transitional, or cliffhanger"
            )
            closure_score: int = Field(
                ge=1, le=10,
                description="Score from 1-10 indicating how well the scene closes"
            )
            issues: List[str] = Field(
                default_factory=list,
                description="List of issues with the scene closure"
            )
            recommendations: List[str] = Field(
                default_factory=list,
                description="List of recommendations for improving the scene closure"
            )
        
        # Create a structured LLM that outputs a SceneClosureAnalysis object
        structured_llm = llm.with_structured_output(SceneClosureAnalysis)
        
        # Use the structured LLM to analyze scene closure
        closure_analysis = structured_llm.invoke(prompt)
        
        # Convert Pydantic model to dictionary
        return closure_analysis.dict()
    
    except Exception as e:
        print(f"Error analyzing scene closure: {str(e)}")
        return {
            "closure_status": CLOSURE_STATUS["ABRUPT"],
            "closure_score": 5,
            "issues": ["Error analyzing scene closure"],
            "recommendations": ["Review the scene ending manually"]
        }

def generate_scene_closure(scene_content: str, chapter_num: str, scene_num: str,
                          closure_analysis: Dict[str, Any], state: StoryState = None) -> str:
    """
    Generate improved scene closure for a scene that ends abruptly.
    
    Args:
        scene_content: The content of the scene
        chapter_num: The chapter number
        scene_num: The scene number
        closure_analysis: The closure analysis results
        state: The current state (optional, for plot thread integration)
        
    Returns:
        The improved scene content with proper closure
    """
    # Extract the last few paragraphs of the scene
    paragraphs = scene_content.split('\n\n')
    last_paragraphs = '\n\n'.join(paragraphs[-min(5, len(paragraphs)):])
    
    # Get active plot threads if state is provided
    plot_thread_guidance = ""
    if state:
        active_plot_threads = get_active_plot_threads_for_scene(state)
        
        if active_plot_threads:
            # Group threads by importance
            major_threads = [t for t in active_plot_threads if t["importance"] == "major"]
            minor_threads = [t for t in active_plot_threads if t["importance"] == "minor"]
            
            # Format major threads
            major_thread_text = ""
            if major_threads:
                major_thread_text = "Major plot threads that need attention:\n"
                for thread in major_threads:
                    major_thread_text += f"- {thread['name']}: {thread['description']}\n  Status: {thread['status']}\n"
            
            # Format minor threads
            minor_thread_text = ""
            if minor_threads:
                minor_thread_text = "Minor plot threads to consider:\n"
                for thread in minor_threads:
                    minor_thread_text += f"- {thread['name']}: {thread['description']}\n"
            
            # Combine thread guidance
            plot_thread_guidance = f"""
            ACTIVE PLOT THREADS:
            {major_thread_text}
            {minor_thread_text}
            
            Ensure your scene closure addresses or advances major plot threads where appropriate.
            Minor threads can be referenced if they fit naturally with the scene's purpose.
            """
    
    # Prepare the prompt for generating improved scene closure
    prompt = f"""
    This scene from Chapter {chapter_num}, Scene {scene_num} ends abruptly and needs improved closure:
    
    --- LAST PART OF SCENE ---
    {last_paragraphs}
    
    CLOSURE ANALYSIS:
    Status: {closure_analysis["closure_status"]}
    Score: {closure_analysis["closure_score"]}/10
    Issues:
    {chr(10).join(f"- {issue}" for issue in closure_analysis["issues"])}
    
    Recommendations:
    {chr(10).join(f"- {rec}" for rec in closure_analysis["recommendations"])}
    
    {plot_thread_guidance}
    
    YOUR TASK:
    Write an improved ending for this scene that provides proper narrative closure.
    Your ending should:
    1. Resolve the immediate tension or question raised in the scene
    2. Complete any unfinished action or dialogue
    3. Provide a sense of completion or transition to the next scene
    4. Feel natural and consistent with the scene's tone and content
    5. Address relevant plot threads, especially major ones
    
    Write 1-3 paragraphs that would replace or extend the current ending.
    The improved ending should flow seamlessly from the existing content.
    
    IMPORTANT: Return ONLY the new ending paragraphs, not the entire scene.
    Do NOT include any explanations, comments, or meta-information.
    """
    
    try:
        # Generate the improved scene closure
        response = llm.invoke([HumanMessage(content=prompt)]).content
        
        # Clean up the response
        improved_closure = response.strip()
        
        # Combine with the original scene content
        # If the scene ends mid-paragraph, we need to be careful about how we append
        if closure_analysis.get("closure_status") == CLOSURE_STATUS["ABRUPT"]:
            # Check if the last paragraph is incomplete
            last_paragraph = paragraphs[-1]
            if not last_paragraph.endswith('.') and not last_paragraph.endswith('!') and not last_paragraph.endswith('?'):
                # Scene ends mid-paragraph, so we need to append to the last paragraph
                paragraphs[-1] = last_paragraph + " " + improved_closure.split('\n\n')[0]
                # Add any remaining paragraphs from the improved closure
                if '\n\n' in improved_closure:
                    paragraphs.extend(improved_closure.split('\n\n')[1:])
            else:
                # Scene doesn't end mid-paragraph, so we can just append the improved closure
                paragraphs.append(improved_closure)
        else:
            # For other closure statuses, just append the improved closure
            paragraphs.append(improved_closure)
        
        # Combine the paragraphs back into a single string
        improved_scene = '\n\n'.join(paragraphs)
        
        return improved_scene
    
    except Exception as e:
        print(f"Error generating scene closure: {str(e)}")
        return scene_content

def check_and_improve_scene_closure(state: StoryState) -> Tuple[bool, Dict[str, Any], str]:
    """
    Check if a scene has proper closure and improve it if needed.
    
    Args:
        state: The current state
        
    Returns:
        A tuple containing:
        - Whether the scene needs improved closure
        - The closure analysis results
        - The improved scene content (if needed)
    """
    chapters = state["chapters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    
    # Get the scene content
    scene_content = chapters[current_chapter]["scenes"][current_scene]["content"]
    
    # Analyze scene closure
    closure_analysis = analyze_scene_closure(scene_content, current_chapter, current_scene)
    
    # Check if the scene needs improved closure
    needs_improved_closure = (
        closure_analysis["closure_status"] == CLOSURE_STATUS["ABRUPT"] or
        closure_analysis["closure_score"] <= 4
    )
    
    # Generate improved scene closure if needed
    improved_scene = scene_content
    if needs_improved_closure:
        improved_scene = generate_scene_closure(
            scene_content, current_chapter, current_scene, closure_analysis, state
        )
    
    return needs_improved_closure, closure_analysis, improved_scene