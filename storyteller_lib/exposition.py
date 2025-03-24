"""
StoryCraft Agent - Exposition clarity and key concepts tracking.

This module provides functionality to track and manage key concepts that need clear exposition,
addressing issues with unclear introduction of important story elements.
"""

from typing import Dict, List, Any, Optional
from langchain_core.messages import HumanMessage
from storyteller_lib.config import llm, manage_memory_tool, search_memory_tool, MEMORY_NAMESPACE
from storyteller_lib.models import StoryState

def identify_key_concepts(global_story: str, genre: str) -> Dict[str, Any]:
    """
    Identify key concepts in the story that will need clear exposition.
    
    Args:
        global_story: The overall story outline
        genre: The genre of the story
        
    Returns:
        A dictionary with key concepts information
    """
    # Prepare the prompt for identifying key concepts
    prompt = f"""
    Analyze this {genre} story outline and identify key concepts that will need clear exposition:
    
    {global_story}
    
    For each key concept (e.g., unique world elements, magic systems, historical events, organizations, cultural practices),
    provide:
    1. Concept name
    2. Brief description
    3. Importance to the story (high, medium, low)
    4. Recommended chapter for introduction
    5. Recommended exposition approach (dialogue, narration, flashback, etc.)
    
    Focus on concepts that are:
    - Unique to this story world
    - Critical to understanding the plot
    - Potentially confusing without proper explanation
    - Referenced multiple times throughout the story
    
    Format your response as a structured JSON object.
    """
    
    try:
        # Define Pydantic models for structured output
        from pydantic import BaseModel, Field
        from typing import List, Literal
        
        class KeyConcept(BaseModel):
            """A key concept that needs clear exposition."""
            
            name: str = Field(
                description="Name of the key concept"
            )
            description: str = Field(
                description="Brief description of the concept"
            )
            importance: Literal["high", "medium", "low"] = Field(
                description="Importance to the story"
            )
            recommended_chapter: str = Field(
                description="Recommended chapter for introduction"
            )
            exposition_approach: str = Field(
                description="Recommended exposition approach"
            )
            introduced: bool = Field(
                default=False,
                description="Whether the concept has been introduced"
            )
            introduction_chapter: str = Field(
                default="",
                description="Chapter where concept was introduced"
            )
            introduction_scene: str = Field(
                default="",
                description="Scene where concept was introduced"
            )
            clarity_score: int = Field(
                default=0, ge=0, le=10,
                description="Clarity of exposition (0=not introduced, 10=perfectly clear)"
            )
        
        class KeyConceptsAnalysis(BaseModel):
            """Analysis of key concepts in a story."""
            
            key_concepts: List[KeyConcept] = Field(
                default_factory=list,
                description="List of key concepts"
            )
        
        # Create a structured LLM that outputs a KeyConceptsAnalysis
        structured_llm = llm.with_structured_output(KeyConceptsAnalysis)
        
        # Use the structured LLM to identify key concepts
        key_concepts_analysis = structured_llm.invoke(prompt)
        
        # Convert Pydantic model to dictionary
        return key_concepts_analysis.dict()
    
    except Exception as e:
        print(f"Error identifying key concepts: {str(e)}")
        return {
            "key_concepts": []
        }

def track_key_concepts(state: StoryState) -> Dict:
    """
    Track and manage key concepts that need clear exposition.
    
    Args:
        state: The current state
        
    Returns:
        Updates to the state
    """
    # Extract key concepts from the story outline
    global_story = state["global_story"]
    genre = state["genre"]
    
    # Identify key concepts
    key_concepts_analysis = identify_key_concepts(global_story, genre)
    
    # Store key concepts in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": "key_concepts_tracker",
        "value": key_concepts_analysis,
        "namespace": MEMORY_NAMESPACE
    })
    
    return {
        "key_concepts_tracker": key_concepts_analysis
    }

def check_concept_introduction(state: StoryState) -> Dict[str, Any]:
    """
    Check if any key concepts should be introduced in the current chapter/scene.
    
    Args:
        state: The current state
        
    Returns:
        A dictionary with concepts to introduce
    """
    chapters = state["chapters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    
    # Retrieve key concepts tracker from memory
    try:
        results = search_memory_tool.invoke({
            "query": "key_concepts_tracker",
            "namespace": MEMORY_NAMESPACE
        })
        
        key_concepts_tracker = None
        if results:
            # Handle different return types from search_memory_tool
            if isinstance(results, dict) and "value" in results:
                key_concepts_tracker = results["value"]
            elif isinstance(results, list):
                for item in results:
                    if hasattr(item, 'key') and item.key == "key_concepts_tracker":
                        key_concepts_tracker = item.value
                        break
        
        if not key_concepts_tracker:
            return {}
        
        # Check which concepts should be introduced in this chapter
        concepts_for_current_chapter = []
        for concept in key_concepts_tracker["key_concepts"]:
            if concept["recommended_chapter"] == current_chapter and not concept["introduced"]:
                concepts_for_current_chapter.append(concept)
        
        if not concepts_for_current_chapter:
            return {}
        
        # Return concepts that should be introduced
        return {
            "concepts_to_introduce": concepts_for_current_chapter
        }
    
    except Exception as e:
        print(f"Error checking concept introduction: {str(e)}")
        return {}

def update_concept_introduction_status(state: StoryState, concept_name: str) -> Dict:
    """
    Update the introduction status of a key concept.
    
    Args:
        state: The current state
        concept_name: The name of the concept that was introduced
        
    Returns:
        Updates to the state
    """
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    
    # Retrieve key concepts tracker from memory
    try:
        results = search_memory_tool.invoke({
            "query": "key_concepts_tracker",
            "namespace": MEMORY_NAMESPACE
        })
        
        key_concepts_tracker = None
        if results:
            # Handle different return types from search_memory_tool
            if isinstance(results, dict) and "value" in results:
                key_concepts_tracker = results["value"]
            elif isinstance(results, list):
                for item in results:
                    if hasattr(item, 'key') and item.key == "key_concepts_tracker":
                        key_concepts_tracker = item.value
                        break
        
        if not key_concepts_tracker:
            return {}
        
        # Update the concept introduction status
        updated_concepts = []
        for concept in key_concepts_tracker["key_concepts"]:
            if concept["name"] == concept_name:
                concept["introduced"] = True
                concept["introduction_chapter"] = current_chapter
                concept["introduction_scene"] = current_scene
                concept["clarity_score"] = 7  # Initial clarity score after introduction
            
            updated_concepts.append(concept)
        
        # Update the key concepts tracker
        updated_tracker = {
            "key_concepts": updated_concepts
        }
        
        # Store the updated tracker in memory
        manage_memory_tool.invoke({
            "action": "create",
            "key": "key_concepts_tracker",
            "value": updated_tracker,
            "namespace": MEMORY_NAMESPACE
        })
        
        return {
            "key_concepts_tracker": updated_tracker
        }
    
    except Exception as e:
        print(f"Error updating concept introduction status: {str(e)}")
        return {}

def analyze_concept_clarity(scene_content: str, concept_name: str) -> Dict[str, Any]:
    """
    Analyze how clearly a concept is explained in a scene.
    
    Args:
        scene_content: The content of the scene
        concept_name: The name of the concept to analyze
        
    Returns:
        A dictionary with clarity analysis results
    """
    # Prepare the prompt for analyzing concept clarity
    prompt = f"""
    Analyze how clearly this concept is explained in the scene:
    
    CONCEPT: {concept_name}
    
    SCENE CONTENT:
    {scene_content}
    
    Evaluate:
    1. Is the concept clearly introduced?
    2. Is enough information provided for the reader to understand the concept?
    3. Is the exposition natural or forced?
    4. Is the concept integrated into the story or just explained?
    5. Are there any aspects of the concept that remain unclear?
    
    Provide:
    - A clarity score from 1-10 (where 10 is perfectly clear)
    - The specific text that introduces the concept
    - Strengths of the exposition
    - Weaknesses of the exposition
    - Suggestions for improvement
    
    Format your response as a structured JSON object.
    """
    
    try:
        # Define Pydantic models for structured output
        from pydantic import BaseModel, Field
        from typing import List, Optional
        
        class ConceptClarity(BaseModel):
            """Analysis of concept clarity in a scene."""
            
            concept_name: str = Field(
                description="Name of the concept"
            )
            clarity_score: int = Field(
                ge=1, le=10,
                description="Clarity score (1=unclear, 10=perfectly clear)"
            )
            introduction_text: str = Field(
                description="The specific text that introduces the concept"
            )
            exposition_method: str = Field(
                description="How the concept is introduced (dialogue, narration, etc.)"
            )
            natural_integration: int = Field(
                ge=1, le=10,
                description="How naturally the concept is integrated (1=forced, 10=seamless)"
            )
            strengths: List[str] = Field(
                default_factory=list,
                description="Strengths of the exposition"
            )
            weaknesses: List[str] = Field(
                default_factory=list,
                description="Weaknesses of the exposition"
            )
            improvement_suggestions: List[str] = Field(
                default_factory=list,
                description="Suggestions for improvement"
            )
        
        # Create a structured LLM that outputs a ConceptClarity
        structured_llm = llm.with_structured_output(ConceptClarity)
        
        # Use the structured LLM to analyze concept clarity
        clarity_analysis = structured_llm.invoke(prompt)
        
        # Convert Pydantic model to dictionary
        return clarity_analysis.dict()
    
    except Exception as e:
        print(f"Error analyzing concept clarity: {str(e)}")
        return {
            "concept_name": concept_name,
            "clarity_score": 5,
            "introduction_text": "",
            "exposition_method": "unknown",
            "natural_integration": 5,
            "strengths": [],
            "weaknesses": [],
            "improvement_suggestions": ["Error analyzing concept clarity"]
        }

def generate_exposition_guidance(concepts_to_introduce: List[Dict[str, Any]], genre: str, tone: str) -> str:
    """
    Generate exposition guidance for scene writing based on concepts to introduce.
    
    Args:
        concepts_to_introduce: List of concepts to introduce
        genre: The genre of the story
        tone: The tone of the story
        
    Returns:
        Exposition guidance text to include in scene writing prompts
    """
    if not concepts_to_introduce:
        return ""
    
    # Format concepts for the prompt
    concepts_text = ""
    for concept in concepts_to_introduce:
        concepts_text += f"- {concept['name']}: {concept['description']} (Importance: {concept['importance']}, Approach: {concept['exposition_approach']})\n"
    
    # Prepare the prompt for generating exposition guidance
    prompt = f"""
    Generate specific exposition guidance for introducing these concepts in a {genre} story with a {tone} tone:
    
    CONCEPTS TO INTRODUCE:
    {concepts_text}
    
    Provide guidance on:
    1. How to introduce these concepts naturally and clearly
    2. How to avoid info-dumping
    3. How to integrate the concepts into the narrative
    4. How to ensure the reader understands the concepts' importance
    5. Common exposition pitfalls to avoid in this genre
    
    Format your response as concise, actionable guidelines that could be included in a scene writing prompt.
    Focus on creating clear, engaging exposition appropriate for the genre and tone.
    """
    
    try:
        # Generate the exposition guidance
        response = llm.invoke([HumanMessage(content=prompt)]).content
        
        # Clean up the response
        exposition_guidance = response.strip()
        
        return f"""
        EXPOSITION GUIDANCE:
        {exposition_guidance}
        """
    
    except Exception as e:
        print(f"Error generating exposition guidance: {str(e)}")
        return f"""
        EXPOSITION GUIDANCE:
        1. Introduce these key concepts clearly in this scene:
        {concepts_text}
        
        2. Guidelines for clear exposition:
           - Introduce concepts organically through character interaction or observation
           - Avoid info-dumping - break exposition into digestible pieces
           - Show rather than tell when possible
           - Use character questions or confusion to naturally explain concepts
           - Ensure the reader understands the concept's importance to the story
        """

def check_and_generate_exposition_guidance(state: StoryState) -> Dict:
    """
    Check if any key concepts should be introduced and generate exposition guidance.
    
    Args:
        state: The current state
        
    Returns:
        Updates to the state
    """
    genre = state["genre"]
    tone = state["tone"]
    
    # Check if any concepts should be introduced
    concepts_result = check_concept_introduction(state)
    
    if not concepts_result or "concepts_to_introduce" not in concepts_result:
        return {}
    
    concepts_to_introduce = concepts_result["concepts_to_introduce"]
    
    # Generate exposition guidance
    exposition_guidance = generate_exposition_guidance(concepts_to_introduce, genre, tone)
    
    return {
        "concepts_to_introduce": concepts_to_introduce,
        "exposition_guidance": exposition_guidance
    }