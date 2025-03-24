"""
StoryCraft Agent - Character consistency tracking and verification.

This module provides functionality to track and ensure character consistency throughout the story,
addressing issues with character motivation inconsistencies.
"""

from typing import Dict, List, Any, Optional
from langchain_core.messages import HumanMessage
from storyteller_lib.config import llm
from storyteller_lib.models import StoryState
from storyteller_lib.plot_threads import get_active_plot_threads_for_scene

def check_character_consistency(character_data: Dict, scene_content: str, 
                              previous_scenes: List[str] = None) -> Dict[str, Any]:
    """
    Check if character actions and motivations are consistent with established traits.
    
    Args:
        character_data: The character data
        scene_content: The content of the current scene
        previous_scenes: Optional list of previous scene contents for context
        
    Returns:
        A dictionary with consistency analysis results
    """
    character_name = character_data.get("name", "")
    
    # Extract relevant character information
    backstory = character_data.get("backstory", "")
    personality = character_data.get("personality", {})
    traits = personality.get("traits", [])
    flaws = personality.get("flaws", [])
    
    # Extract character arc information if available
    character_arc = character_data.get("character_arc", {})
    arc_type = character_arc.get("type", "")
    current_stage = character_arc.get("current_stage", "")
    
    # Extract emotional state if available
    emotional_state = character_data.get("emotional_state", {})
    current_emotion = emotional_state.get("current", "")
    
    # Prepare context from previous scenes if available
    previous_context = ""
    if previous_scenes and len(previous_scenes) > 0:
        previous_context = "\n\n".join([f"Previous scene excerpt: {scene[:300]}..." for scene in previous_scenes[-2:]])
    
    # Prepare the prompt for checking character consistency
    prompt = f"""
    Analyze {character_name}'s consistency in this scene:
    
    CHARACTER PROFILE:
    Name: {character_name}
    Backstory: {backstory}
    Traits: {', '.join(traits) if traits else 'Not specified'}
    Flaws: {', '.join(flaws) if flaws else 'Not specified'}
    Arc Type: {arc_type}
    Current Arc Stage: {current_stage}
    Current Emotional State: {current_emotion}
    
    {previous_context}
    
    CURRENT SCENE:
    {scene_content}
    
    Evaluate:
    1. Are {character_name}'s actions consistent with established traits?
    2. Are their motivations clear and consistent with previous behavior?
    3. Does their dialogue match their established voice?
    4. Are emotional reactions appropriate to their personality and situation?
    5. Is character development gradual and believable?
    
    For any inconsistencies, provide:
    - Description of the inconsistency
    - Why it's inconsistent with the character profile
    - A suggested revision
    
    Format your response as a structured JSON object.
    """
    
    try:
        # Define Pydantic models for structured output
        from pydantic import BaseModel, Field
        from typing import List, Optional
        
        class ConsistencyIssue(BaseModel):
            """A specific character consistency issue."""
            
            issue_type: str = Field(
                description="Type of inconsistency (action, motivation, dialogue, emotion)"
            )
            description: str = Field(
                description="Description of the inconsistency"
            )
            reason: str = Field(
                description="Why it's inconsistent with the character profile"
            )
            suggestion: str = Field(
                description="Suggested revision"
            )
            severity: int = Field(
                ge=1, le=10,
                description="Severity of the inconsistency (1=minor, 10=major)"
            )
        
        class ConsistencyAnalysis(BaseModel):
            """Analysis of character consistency in a scene."""
            
            character_name: str = Field(
                description="Name of the character"
            )
            consistency_score: int = Field(
                ge=1, le=10,
                description="Overall consistency score (1=very inconsistent, 10=perfectly consistent)"
            )
            action_consistency: int = Field(
                ge=1, le=10,
                description="Consistency of actions with established traits"
            )
            motivation_clarity: int = Field(
                ge=1, le=10,
                description="Clarity and consistency of motivations"
            )
            dialogue_consistency: int = Field(
                ge=1, le=10,
                description="Consistency of dialogue with character voice"
            )
            emotional_consistency: int = Field(
                ge=1, le=10,
                description="Consistency of emotional reactions"
            )
            development_believability: int = Field(
                ge=1, le=10,
                description="Believability of character development"
            )
            issues: List[ConsistencyIssue] = Field(
                default_factory=list,
                description="List of specific consistency issues"
            )
            strengths: List[str] = Field(
                default_factory=list,
                description="Character consistency strengths"
            )
        
        # Create a structured LLM that outputs a ConsistencyAnalysis
        structured_llm = llm.with_structured_output(ConsistencyAnalysis)
        
        # Use the structured LLM to check character consistency
        consistency_analysis = structured_llm.invoke(prompt)
        
        # Convert Pydantic model to dictionary
        return consistency_analysis.dict()
    
    except Exception as e:
        print(f"Error checking character consistency: {str(e)}")
        return {
            "character_name": character_name,
            "consistency_score": 5,
            "action_consistency": 5,
            "motivation_clarity": 5,
            "dialogue_consistency": 5,
            "emotional_consistency": 5,
            "development_believability": 5,
            "issues": [],
            "strengths": []
        }

def fix_character_inconsistencies(scene_content: str, character_data: Dict,
                                consistency_analysis: Dict[str, Any], state: StoryState = None) -> str:
    """
    Fix character inconsistencies in a scene.
    
    Args:
        scene_content: The content of the scene
        character_data: The character data
        consistency_analysis: The consistency analysis results
        state: The current state (optional, for plot thread integration)
        
    Returns:
        The scene content with fixed inconsistencies
    """
    # If consistency is already good, no need to fix
    if consistency_analysis["consistency_score"] >= 8:
        return scene_content
    
    # Extract character name
    character_name = character_data.get("name", "")
    
    # Get active plot threads if state is provided
    plot_thread_guidance = ""
    if state:
        active_plot_threads = get_active_plot_threads_for_scene(state)
        
        if active_plot_threads:
            # Filter plot threads related to this character
            character_threads = []
            for thread in active_plot_threads:
                if character_name in thread.get("related_characters", []):
                    character_threads.append(thread)
            
            if character_threads:
                # Format character-related threads
                thread_text = "Plot threads involving this character:\n"
                for thread in character_threads:
                    thread_text += f"- {thread['name']}: {thread['description']}\n  Status: {thread['status']}\n"
                
                # Combine thread guidance
                plot_thread_guidance = f"""
                CHARACTER PLOT THREAD INVOLVEMENT:
                {thread_text}
                
                Ensure that {character_name}'s actions, motivations, and dialogue remain consistent with their involvement in these plot threads.
                Character behavior should align with their role in each thread and reflect their knowledge of thread-related events.
                """
    
    # Prepare the prompt for fixing inconsistencies
    prompt = f"""
    Revise this scene to fix character inconsistencies for {character_name}:
    
    {scene_content}
    
    CHARACTER PROFILE:
    {character_data}
    
    CONSISTENCY ANALYSIS:
    Overall Consistency Score: {consistency_analysis["consistency_score"]}/10
    Action Consistency: {consistency_analysis["action_consistency"]}/10
    Motivation Clarity: {consistency_analysis["motivation_clarity"]}/10
    Dialogue Consistency: {consistency_analysis["dialogue_consistency"]}/10
    Emotional Consistency: {consistency_analysis["emotional_consistency"]}/10
    Development Believability: {consistency_analysis["development_believability"]}/10
    
    Issues to fix:
    {consistency_analysis["issues"]}
    
    {plot_thread_guidance}
    
    Your task:
    1. Revise {character_name}'s actions to be consistent with their established traits
    2. Clarify their motivations to align with previous behavior
    3. Adjust dialogue to match their established voice
    4. Make emotional reactions appropriate to their personality
    5. Ensure character development is gradual and believable
    6. Maintain consistency with the character's involvement in plot threads
    
    IMPORTANT:
    - Maintain the overall plot and scene structure
    - Only modify elements related to {character_name}'s consistency
    - Return the complete revised scene
    """
    
    try:
        # Generate the improved scene
        response = llm.invoke([HumanMessage(content=prompt)]).content
        
        # Clean up the response
        improved_scene = response.strip()
        
        return improved_scene
    
    except Exception as e:
        print(f"Error fixing character inconsistencies: {str(e)}")
        return scene_content

def track_character_consistency(state: StoryState) -> Dict:
    """
    Track character consistency throughout the story.
    
    Args:
        state: The current state
        
    Returns:
        Updates to the state
    """
    chapters = state["chapters"]
    characters = state["characters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    
    # Get the current scene content
    scene_content = chapters[current_chapter]["scenes"][current_scene]["content"]
    
    # Get previous scenes for context (up to 2)
    previous_scenes = []
    for ch_num in sorted(chapters.keys(), key=int):
        if int(ch_num) < int(current_chapter) or (ch_num == current_chapter and int(current_scene) > 1):
            for sc_num in sorted(chapters[ch_num]["scenes"].keys(), key=int):
                if ch_num == current_chapter and int(sc_num) >= int(current_scene):
                    continue
                scene = chapters[ch_num]["scenes"][sc_num]
                if "content" in scene:
                    previous_scenes.append(scene["content"])
    
    # Keep only the last 2 previous scenes
    previous_scenes = previous_scenes[-2:] if len(previous_scenes) > 2 else previous_scenes
    
    # Check consistency for each character in the scene
    consistency_updates = {}
    character_consistency_analyses = {}
    
    for char_name, char_data in characters.items():
        # Skip if char_data is None
        if char_data is None:
            continue
            
        # Check if character appears in the scene
        if char_name.lower() in scene_content.lower() or (char_data.get("name", "").lower() in scene_content.lower()):
            try:
                # Check character consistency
                consistency_analysis = check_character_consistency(char_data, scene_content, previous_scenes)
                
                # Store the analysis
                character_consistency_analyses[char_name] = consistency_analysis
                
                # If there are significant inconsistencies, fix them
                if consistency_analysis["consistency_score"] < 7 and consistency_analysis["issues"]:
                    improved_scene = fix_character_inconsistencies(scene_content, char_data, consistency_analysis, state)
                    
                    # Update the scene content with the improved version
                    consistency_updates = {
                        "chapters": {
                            current_chapter: {
                                "scenes": {
                                    current_scene: {
                                        "content": improved_scene,
                                        "consistency_fixed": True
                                    }
                                }
                            }
                        }
                    }
                    
                    # Only fix one character at a time to avoid conflicting changes
                    break
            except Exception as e:
                print(f"Error tracking consistency for {char_name}: {str(e)}")
    
    # Store the consistency analyses
    return {
        **consistency_updates,
        "character_consistency_analyses": character_consistency_analyses
    }

def generate_consistency_guidance(characters: Dict[str, Any], plot_threads: List[Dict[str, Any]] = None) -> str:
    """
    Generate character consistency guidance for scene writing.
    
    Args:
        characters: The character data
        plot_threads: Optional list of active plot threads
        
    Returns:
        Consistency guidance text to include in scene writing prompts
    """
    # Extract character information
    character_info = []
    for char_name, char_data in characters.items():
        if char_data is None:
            continue
            
        # Extract key consistency elements
        name = char_data.get("name", char_name)
        traits = char_data.get("personality", {}).get("traits", [])
        voice = char_data.get("voice_characteristics", "Not specified")
        arc = char_data.get("character_arc", {}).get("type", "Not specified")
        stage = char_data.get("character_arc", {}).get("current_stage", "Not specified")
        emotion = char_data.get("emotional_state", {}).get("current", "Not specified")
        
        character_info.append(f"- {name}: Traits: {', '.join(traits) if traits else 'Not specified'}, Voice: {voice}, Arc: {arc}, Current Stage: {stage}, Current Emotion: {emotion}")
    
    # Prepare plot thread information if provided
    plot_thread_info = []
    if plot_threads:
        for thread in plot_threads:
            thread_name = thread.get("name", "")
            thread_desc = thread.get("description", "")
            thread_status = thread.get("status", "")
            related_chars = thread.get("related_characters", [])
            
            if related_chars:
                plot_thread_info.append(f"- {thread_name}: {thread_desc} (Status: {thread_status}, Characters: {', '.join(related_chars)})")
    
    # Prepare the prompt for generating consistency guidance
    prompt = f"""
    Generate character consistency guidance for scene writing based on these character profiles:
    
    {chr(10).join(character_info)}
    
    {f"Active plot threads involving these characters:\n{chr(10).join(plot_thread_info)}" if plot_thread_info else ""}
    
    Provide guidance on:
    1. How to maintain consistent character voices and behaviors
    2. How to ensure character motivations are clear and consistent
    3. How to handle character development in a gradual, believable way
    4. How to ensure emotional reactions are appropriate to personalities
    5. How to maintain character consistency with their involvement in plot threads
    6. Common consistency pitfalls to avoid
    
    Format your response as concise, actionable guidelines that could be included in a scene writing prompt.
    Focus on creating consistent, believable characters whose actions align with their involvement in plot threads.
    """
    
    try:
        # Generate the consistency guidance
        response = llm.invoke([HumanMessage(content=prompt)]).content
        
        # Clean up the response
        consistency_guidance = response.strip()
        
        return f"""
        CHARACTER CONSISTENCY GUIDANCE:
        {consistency_guidance}
        """
    
    except Exception as e:
        print(f"Error generating consistency guidance: {str(e)}")
        return """
        CHARACTER CONSISTENCY GUIDANCE:
        1. Maintain each character's unique voice and speech patterns throughout
        2. Ensure character actions align with their established traits and values
        3. Make character motivations clear and consistent with previous behavior
        4. Develop characters gradually rather than with sudden changes
        5. Ensure emotional reactions match the character's personality and situation
        6. Reference past experiences that influence current decisions
        7. Keep character knowledge consistent with what they've learned so far
        """