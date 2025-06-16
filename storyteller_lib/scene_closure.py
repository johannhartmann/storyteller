"""
StoryCraft Agent - Scene closure verification and management.

This module provides functionality to detect and fix abrupt scene endings,
ensuring proper narrative closure for each scene in multiple languages.
"""

from typing import Dict, List, Any, Tuple
from langchain_core.messages import HumanMessage
from storyteller_lib.config import llm, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState
from storyteller_lib.plot_threads import get_active_plot_threads_for_scene

# Scene closure status options
CLOSURE_STATUS = {
    "COMPLETE": "complete",
    "ABRUPT": "abrupt",
    "TRANSITIONAL": "transitional",
    "CLIFFHANGER": "cliffhanger"
}
def analyze_scene_closure(scene_content: str, chapter_num: str, scene_num: str,
                        language: str = DEFAULT_LANGUAGE, state: StoryState = None) -> Dict[str, Any]:
    """
    Analyze a scene for proper narrative closure.
    
    Args:
        scene_content: The content of the scene
        chapter_num: The chapter number
        scene_num: The scene number
        language: The language of the scene (default: from config)
        state: The current state (optional, for additional context)
        
    Returns:
        A dictionary with closure analysis results
    """
    # Use template system
    from storyteller_lib.prompt_templates import render_prompt
    
    # Get additional context from state if available
    genre = "unknown"
    tone = "unknown"
    scene_purpose = None
    next_scene_outline = None
    active_plot_threads = []
    
    if state:
        genre = state.get("genre", "fantasy")
        tone = state.get("tone", "adventurous")
        
        # Try to get scene purpose
        chapters = state.get("chapters", {})
        if str(chapter_num) in chapters:
            scenes = chapters[str(chapter_num)].get("scenes", {})
            if str(scene_num) in scenes:
                scene_purpose = scenes[str(scene_num)].get("outline", "")
                
                # Try to get next scene outline
                next_scene_num = str(int(scene_num) + 1)
                if next_scene_num in scenes:
                    next_scene_outline = scenes[next_scene_num].get("outline", "")
        
        # Get active plot threads
        active_threads = get_active_plot_threads_for_scene(state)
        for thread in active_threads[:3]:  # Limit to 3
            active_plot_threads.append({
                'name': thread.get('name', 'Unknown'),
                'status': thread.get('status', thread.get('current_development', 'Active'))
            })
    
    # Render the closure analysis prompt
    prompt = render_prompt(
        'scene_closure',
        language=language,
        scene_content=scene_content,
        current_chapter=chapter_num,
        current_scene=scene_num,
        genre=genre,
        tone=tone,
        scene_purpose=scene_purpose,
        next_scene_outline=next_scene_outline,
        active_plot_threads=active_plot_threads if active_plot_threads else None
    )
    
    try:
        # Define an enhanced Pydantic model for structured output
        from pydantic import BaseModel, Field
        
        class ClosureScores(BaseModel):
            """Detailed closure scores."""
            resolution: int = Field(ge=1, le=10, description="Resolution score")
            emotional_closure: int = Field(ge=1, le=10, description="Emotional closure score")
            narrative_momentum: int = Field(ge=1, le=10, description="Narrative momentum score")
            thematic_resonance: int = Field(ge=1, le=10, description="Thematic resonance score")
            technical_execution: int = Field(ge=1, le=10, description="Technical execution score")
        
        class SceneClosureAnalysis(BaseModel):
            """Analysis of a scene's closure."""
            
            closure_type: str = Field(
                description="The closure type: resolution, cliffhanger, reflection, transition, image, dialogue, or action"
            )
            closure_effectiveness: int = Field(
                ge=1, le=10,
                description="Overall effectiveness score (1-10)"
            )
            closure_scores: ClosureScores = Field(
                description="Detailed scores for different aspects"
            )
            issues: List[str] = Field(
                default_factory=list,
                description="List of issues with the scene closure"
            )
            improvements: List[str] = Field(
                default_factory=list,
                description="Specific improvements needed"
            )
            strengths: List[str] = Field(
                default_factory=list,
                description="What's working well in the closure"
            )
        
        # Create a structured LLM that outputs a SceneClosureAnalysis object
        structured_llm = llm.with_structured_output(SceneClosureAnalysis)
        
        # Use the structured LLM to analyze scene closure
        closure_analysis = structured_llm.invoke(prompt)
        
        # Convert to the expected format
        result = closure_analysis.dict()
        
        # Map closure_type to closure_status for compatibility
        type_to_status_map = {
            "resolution": CLOSURE_STATUS["COMPLETE"],
            "cliffhanger": CLOSURE_STATUS["CLIFFHANGER"],
            "transition": CLOSURE_STATUS["TRANSITIONAL"],
            "reflection": CLOSURE_STATUS["COMPLETE"],
            "image": CLOSURE_STATUS["COMPLETE"],
            "dialogue": CLOSURE_STATUS["COMPLETE"],
            "action": CLOSURE_STATUS["COMPLETE"]
        }
        
        # Determine if it's abrupt based on effectiveness
        if result['closure_effectiveness'] <= 4:
            result['closure_status'] = CLOSURE_STATUS["ABRUPT"]
        else:
            result['closure_status'] = type_to_status_map.get(
                result['closure_type'], CLOSURE_STATUS["COMPLETE"]
            )
        
        result['closure_score'] = result['closure_effectiveness']
        result['recommendations'] = result.get('improvements', [])
        
        return result
    
    except Exception as e:
        print(f"Error analyzing scene closure: {str(e)}")
        return {
            "closure_status": CLOSURE_STATUS["ABRUPT"],
            "closure_score": 5,
            "issues": ["Error analyzing scene closure"],
            "recommendations": ["Review the scene ending manually"]
        }

def generate_scene_closure(scene_content: str, chapter_num: str, scene_num: str,
                          closure_analysis: Dict[str, Any], state: StoryState = None,
                          language: str = DEFAULT_LANGUAGE) -> str:
    """
    Generate improved scene closure for a scene that ends abruptly.
    
    Args:
        scene_content: The content of the scene
        chapter_num: The chapter number
        scene_num: The scene number
        closure_analysis: The closure analysis results
        state: The current state (optional, for plot thread integration)
        language: The language of the scene (default: from config)
        
    Returns:
        The improved scene content with proper closure
    """
    # Get language from state if provided and not explicitly specified
    if state and not language:
        language = state.get("language", DEFAULT_LANGUAGE)
        
    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        print(f"Warning: Unsupported language '{language}'. Falling back to {DEFAULT_LANGUAGE}.")
        language = DEFAULT_LANGUAGE
    
    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[language]
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
    This scene from Chapter {chapter_num}, Scene {scene_num} written in {language_name} ends abruptly and needs improved closure:
    
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
    
    LANGUAGE CONSIDERATIONS:
    - Use natural closure phrases and techniques common in {language_name} literature
    - Consider cultural context and linguistic norms specific to {language_name}
    - Ensure the closure flows naturally in {language_name}
    
    YOUR TASK:
    Write an improved ending for this scene in {language_name} that provides proper narrative closure.
    Your ending should:
    1. Resolve the immediate tension or question raised in the scene
    2. Complete any unfinished action or dialogue
    3. Provide a sense of completion or transition to the next scene
    4. Feel natural and consistent with the scene's tone and content
    5. Address relevant plot threads, especially major ones
    6. Use appropriate closure techniques for {language_name} literature
    7. Sound natural to native {language_name} speakers
    
    Write 1-3 paragraphs that would replace or extend the current ending.
    The improved ending should flow seamlessly from the existing content.
    
    IMPORTANT: Return ONLY the new ending paragraphs in {language_name}, not the entire scene.
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
    
    # Get the language from the state or use default
    language = state.get("language", DEFAULT_LANGUAGE)
    
    # Get the scene content from state or database
    scene_content = state.get("current_scene_content", "")
    if not scene_content:
        # Try to get from database
        from storyteller_lib.database_integration import get_db_manager
        db_manager = get_db_manager()
        if db_manager:
            scene_content = db_manager.get_scene_content(int(current_chapter), int(current_scene))
    
    if not scene_content:
        raise RuntimeError(f"Scene content not found for Chapter {current_chapter}, Scene {current_scene}")
    
    # Analyze scene closure
    closure_analysis = analyze_scene_closure(scene_content, current_chapter, current_scene, language, state)
    
    # Check if the scene needs improved closure
    needs_improved_closure = (
        closure_analysis["closure_status"] == CLOSURE_STATUS["ABRUPT"] or
        closure_analysis["closure_score"] <= 4
    )
    
    # Generate improved scene closure if needed
    improved_scene = scene_content
    if needs_improved_closure:
        improved_scene = generate_scene_closure(
            scene_content, current_chapter, current_scene, closure_analysis, state, language
        )
    
    return needs_improved_closure, closure_analysis, improved_scene