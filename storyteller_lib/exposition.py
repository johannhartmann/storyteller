"""
StoryCraft Agent - Exposition clarity and key concepts tracking.

This module provides functionality to track and manage key concepts that need clear exposition,
addressing issues with unclear introduction of important story elements in multiple languages.
"""

from typing import Dict, List, Any, Optional
from langchain_core.messages import HumanMessage
from storyteller_lib.config import llm, manage_memory_tool, search_memory_tool, MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState

def identify_key_concepts(global_story: str, genre: str, language: str = DEFAULT_LANGUAGE) -> Dict[str, Any]:
    """
    Identify key concepts in the story that will need clear exposition.
    
    Args:
        global_story: The overall story outline
        genre: The genre of the story
        language: The language of the story (default: from config)
        
    Returns:
        A dictionary with key concepts information
    """
    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        print(f"Warning: Unsupported language '{language}'. Falling back to {DEFAULT_LANGUAGE}.")
        language = DEFAULT_LANGUAGE
    
    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[language]
    
    # Prepare the prompt for identifying key concepts
    prompt = f"""
    Analyze this {genre} story outline written in {language_name} and identify key concepts that will need clear exposition:
    
    {global_story}
    
    For each key concept (e.g., unique world elements, magic systems, historical events, organizations, cultural practices),
    provide:
    1. Concept name (in {language_name})
    2. Brief description (in {language_name})
    3. Importance to the story (high, medium, low)
    4. Recommended chapter for introduction
    5. Recommended exposition approach (dialogue, narration, flashback, etc.)
    
    Focus on concepts that are:
    - Unique to this story world
    - Critical to understanding the plot
    - Potentially confusing without proper explanation
    - Referenced multiple times throughout the story
    - Culturally relevant in {language_name} literature
    
    Format your response as a structured JSON object.
    Analyze and respond in {language_name}.
    """
    
    try:
        # Define Pydantic models for structured output
        from pydantic import BaseModel, Field, field_validator
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
    
    # Get the language from the state or use default
    language = state.get("language", DEFAULT_LANGUAGE)
    
    # Identify key concepts
    key_concepts_analysis = identify_key_concepts(global_story, genre, language)
    
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

def analyze_concept_clarity(scene_content: str, concept_name: str, language: str = DEFAULT_LANGUAGE) -> Dict[str, Any]:
    """
    Analyze how clearly a concept is explained in a scene.
    
    Args:
        scene_content: The content of the scene
        concept_name: The name of the concept to analyze
        language: The language of the scene (default: from config)
        
    Returns:
        A dictionary with clarity analysis results
    """
    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        print(f"Warning: Unsupported language '{language}'. Falling back to {DEFAULT_LANGUAGE}.")
        language = DEFAULT_LANGUAGE
    
    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[language]
    
    # Prepare the prompt for analyzing concept clarity
    prompt = f"""
    Analyze how clearly this concept is explained in the scene written in {language_name}:
    
    CONCEPT: {concept_name}
    
    SCENE CONTENT:
    {scene_content}
    
    Evaluate:
    1. Is the concept clearly introduced?
    2. Is enough information provided for the reader to understand the concept?
    3. Is the exposition natural or forced?
    4. Is the concept integrated into the story or just explained?
    5. Are there any aspects of the concept that remain unclear?
    6. Does the exposition respect cultural and linguistic norms of {language_name}?
    
    Provide:
    - A clarity score from 1-10 (where 10 is perfectly clear)
    - The specific text that introduces the concept (in the original {language_name})
    - Strengths of the exposition
    - Weaknesses of the exposition
    - Suggestions for improvement that are appropriate for {language_name} literature
    
    Format your response as a structured JSON object.
    Analyze and respond in {language_name}.
    """
    
    try:
        # Define Pydantic models for structured output
        from pydantic import BaseModel, Field, field_validator
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

def generate_exposition_guidance(concepts_to_introduce: List[Dict[str, Any]], genre: str, tone: str,
                               language: str = DEFAULT_LANGUAGE) -> str:
    """
    Generate exposition guidance for scene writing based on concepts to introduce.
    
    Args:
        concepts_to_introduce: List of concepts to introduce
        genre: The genre of the story
        tone: The tone of the story
        language: The language of the story (default: from config)
        
    Returns:
        Exposition guidance text to include in scene writing prompts
    """
    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        print(f"Warning: Unsupported language '{language}'. Falling back to {DEFAULT_LANGUAGE}.")
        language = DEFAULT_LANGUAGE
    
    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[language]
    if not concepts_to_introduce:
        return ""
    
    # Format concepts for the prompt
    concepts_text = ""
    for concept in concepts_to_introduce:
        concepts_text += f"- {concept['name']}: {concept['description']} (Importance: {concept['importance']}, Approach: {concept['exposition_approach']})\n"
    
    # Prepare the prompt for generating exposition guidance
    prompt = f"""
    Generate specific exposition guidance for introducing these concepts in a {genre} story with a {tone} tone written in {language_name}:
    
    CONCEPTS TO INTRODUCE:
    {concepts_text}
    
    Provide guidance on:
    1. How to introduce these concepts naturally and clearly in {language_name}
    2. How to avoid info-dumping
    3. How to integrate the concepts into the narrative
    4. How to ensure the reader understands the concepts' importance
    5. Common exposition pitfalls to avoid in this genre
    6. Language-specific exposition techniques for {language_name}
    7. Cultural considerations for introducing concepts in {language_name} literature
    
    Format your response as concise, actionable guidelines that could be included in a scene writing prompt.
    Focus on creating clear, engaging exposition appropriate for the genre, tone, and language.
    Provide your guidance in {language_name}.
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
        EXPOSITION GUIDANCE FOR {language_name.upper()}:
        1. Introduce these key concepts clearly in this scene:
        {concepts_text}
        
        2. Guidelines for clear exposition in {language_name}:
           - Introduce concepts organically through character interaction or observation
           - Avoid info-dumping - break exposition into digestible pieces
           - Show rather than tell when possible
           - Use character questions or confusion to naturally explain concepts
           - Ensure the reader understands the concept's importance to the story
           - Consider cultural context and linguistic norms specific to {language_name}
           - Use idiomatic expressions and natural speech patterns in {language_name}
           - Adapt exposition techniques to match {language_name} literary traditions
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
    
    # Get the language from the state or use default
    language = state.get("language", DEFAULT_LANGUAGE)
    
    # Check if any concepts should be introduced
    concepts_result = check_concept_introduction(state)
    
    if not concepts_result or "concepts_to_introduce" not in concepts_result:
        return {}
    
    concepts_to_introduce = concepts_result["concepts_to_introduce"]
    
    # Generate exposition guidance
    exposition_guidance = generate_exposition_guidance(concepts_to_introduce, genre, tone, language)
    
    # Add sensory checklists for each concept
    sensory_checklists = {}
    for concept in concepts_to_introduce:
        sensory_checklists[concept["name"]] = generate_concept_sensory_checklist(concept, language)
    
    # Add sensory checklists to exposition guidance
    if sensory_checklists:
        sensory_guidance = "\n\nSENSORY CHECKLISTS FOR KEY CONCEPTS:\n"
        for concept_name, checklist in sensory_checklists.items():
            sensory_guidance += f"\n{concept_name}:\n{checklist}\n"
        
        exposition_guidance += sensory_guidance
    
    # Add showing vs. telling guidance
    showing_telling_guidance = """
    SHOWING VS. TELLING FOR CONCEPT INTRODUCTION:
    
    Instead of explaining concepts directly, demonstrate them through:
    
    1. CHARACTER INTERACTIONS:
       - Show characters using or encountering the concept
       - Reveal information through character reactions
       - Use dialogue that naturally incorporates the concept
    
    2. SENSORY EXPERIENCES:
       - Describe how the concept looks, sounds, smells, feels, or tastes
       - Show physical manifestations of abstract concepts
       - Create vivid imagery that embodies the concept
    
    3. ENVIRONMENTAL CUES:
       - Use the setting to reflect or embody the concept
       - Show how the concept affects the environment
       - Create atmosphere that reinforces the concept
    
    4. CONCRETE EXAMPLES:
       - Show specific instances rather than general explanations
       - Use representative examples that illustrate the concept
       - Create symbolic objects or events that embody the concept
    """
    
    exposition_guidance += showing_telling_guidance
    
    return {
        "concepts_to_introduce": concepts_to_introduce,
        "exposition_guidance": exposition_guidance,
        "sensory_checklists": sensory_checklists
    }

def convert_exposition_to_sensory(exposition_text: str) -> str:
    """
    Convert expository statements into sensory descriptions.
    
    Args:
        exposition_text: The expository text to convert
        
    Returns:
        Sensory descriptions that show rather than tell
    """
    # Prepare the prompt for converting exposition to sensory descriptions
    prompt = f"""
    Convert this expository text into sensory descriptions that show rather than tell:
    
    {exposition_text}
    
    Focus on:
    - Visual details (what would a character SEE?)
    - Sounds (what would a character HEAR?)
    - Smells, tastes, and textures (what physical sensations are associated?)
    - Character reactions and emotions (how do characters physically respond?)
    - Environmental cues (how does the environment reflect the information?)
    
    EXAMPLES:
    
    TELLING: "The Sülfmeister were resentful of the Patrizier's power over the salt trade."
    SHOWING: "Müller's knuckles whitened around his salt measure as the Patrizier's tax collector approached. The other Sülfmeister exchanged glances, their shoulders tensing beneath salt-crusted coats. No one spoke, but their silence carried the weight of generations of resentment."
    
    TELLING: "The Salzmal was an ancient salt tax that caused conflict between social classes."
    SHOWING: "The iron seal of the Salzmal glinted on the collection box, its worn edges smoothed by centuries of reluctant tributes. When it appeared, conversations hushed and eyes darted to worn boots. A Sülfmeister spat on the ground, the gesture small but defiant, while the Patrizier's man adjusted his clean collar with manicured fingers."
    
    Return only the converted text with no explanations or comments.
    """
    
    try:
        # Generate the sensory descriptions
        response = llm.invoke([HumanMessage(content=prompt)])
        
        # Check if we got a valid response
        if response is None or response.content is None:
            print("Error converting exposition to sensory: LLM returned None")
            return exposition_text  # Return original text if conversion fails
        
        # Clean up the response
        sensory_text = response.content.strip()
        
        return sensory_text
    
    except Exception as e:
        print(f"Error converting exposition to sensory: {str(e)}")
        return exposition_text  # Return original text if conversion fails

def identify_telling_passages(scene_content: str) -> List[str]:
    """
    Identify passages in a scene that tell rather than show.
    
    Args:
        scene_content: The content of the scene
        
    Returns:
        A list of passages that tell rather than show
    """
    # Prepare the prompt for identifying telling passages
    prompt = f"""
    Identify passages in this scene that "tell" rather than "show":
    
    {scene_content}
    
    Look for:
    1. Direct statements about emotions rather than physical manifestations
    2. Explanations of world elements rather than interactions with them
    3. Abstract descriptions rather than concrete sensory details
    4. Statements that explain character traits rather than demonstrating them
    5. Exposition that could be converted to action, dialogue, or sensory experience
    
    For each passage, extract ONLY the exact text that should be converted to showing.
    Format your response as a JSON array of strings, with each string being a passage to convert.
    """
    
    try:
        # Define Pydantic model for structured output
        from pydantic import BaseModel, Field
        from typing import List
        
        class TellingPassages(BaseModel):
            """Passages that tell rather than show."""
            passages: List[str] = Field(
                description="List of passages that tell rather than show"
            )
        
        # Create a structured LLM that outputs TellingPassages
        structured_llm = llm.with_structured_output(TellingPassages)
        
        # Use the structured LLM to identify telling passages
        telling_passages = structured_llm.invoke(prompt)
        
        # Check if we got a valid response
        if telling_passages is None:
            print("Error identifying telling passages: LLM returned None")
            return []
        
        # Return the list of passages
        return telling_passages.passages
    
    except Exception as e:
        print(f"Error identifying telling passages: {str(e)}")
        return []  # Return empty list if identification fails

def analyze_showing_vs_telling(scene_content: str) -> Dict[str, Any]:
    """
    Analyze the balance of showing vs. telling in a scene.
    
    Args:
        scene_content: The content of the scene
        
    Returns:
        A dictionary with showing vs. telling analysis results
    """
    # Prepare the prompt for analyzing showing vs. telling
    prompt = f"""
    Analyze this scene for the balance of showing vs. telling:
    
    {scene_content}
    
    Evaluate:
    1. How effectively does the scene use sensory details?
    2. Are emotions shown through physical manifestations or just stated?
    3. Are world elements experienced through character interaction or just explained?
    4. Is character development demonstrated through actions or just described?
    5. What is the overall ratio of showing to telling?
    
    Identify specific examples of:
    - Effective showing (with excerpts)
    - Instances of telling that could be improved (with excerpts)
    - Missed opportunities for sensory details
    
    Format your response as a structured JSON object.
    """
    
    try:
        # Define Pydantic models for structured output
        from pydantic import BaseModel, Field
        from typing import List
        
        class TellingInstance(BaseModel):
            """An instance of telling rather than showing."""
            text: str = Field(
                description="The text that tells rather than shows"
            )
            issue: str = Field(
                description="What type of telling issue this is"
            )
            improvement_suggestion: str = Field(
                description="Suggestion for how to convert to showing"
            )
        
        class ShowingInstance(BaseModel):
            """An instance of effective showing."""
            text: str = Field(
                description="The text that effectively shows"
            )
            strength: str = Field(
                description="What makes this an effective example of showing"
            )
        
        class ShowingTellingAnalysis(BaseModel):
                    """Analysis of showing vs. telling in a scene."""
                    sensory_details_score: int = Field(
                        ge=1, le=10,
                        description="Effectiveness of sensory details (1=poor, 10=excellent)"
                    )
                    emotion_showing_score: int = Field(
                        ge=1, le=10,
                        description="How well emotions are shown rather than told"
                    )
                    world_element_showing_score: int = Field(
                        ge=1, le=10,
                        description="How well world elements are shown rather than explained"
                    )
                    character_development_showing_score: int = Field(
                        ge=1, le=10,
                        description="How well character development is shown rather than described"
                    )
                    overall_showing_ratio: int = Field(
                        ge=1, le=10,
                        description="Overall ratio of showing to telling (1=all telling, 10=all showing)"
                    )
                    telling_instances: List[TellingInstance] = Field(
                        default_factory=list,
                        description="Instances of telling that could be improved"
                    )
                    showing_instances: List[ShowingInstance] = Field(
                        default_factory=list,
                        description="Examples of effective showing"
                    )
                    missed_opportunities: List[str] = Field(
                        default_factory=list,
                        description="Missed opportunities for sensory details"
                    )
                    improvement_suggestions: List[str] = Field(
                        default_factory=list,
                        description="General suggestions for improving showing vs. telling"
                    )
                    
                    # Custom validator to handle string inputs for list fields
                    @classmethod
                    def validate_list_fields(cls, v, field):
                        """Handle cases where the LLM returns a string instead of a list."""
                        if isinstance(v, str):
                            # Try to parse the string as JSON
                            try:
                                import json
                                parsed = json.loads(v)
                                if isinstance(parsed, list):
                                    return parsed
                            except:
                                pass
                            # If parsing fails, return an empty list
                            return []
                        return v
                    
                    @field_validator('showing_instances', 'telling_instances', 'missed_opportunities', 'improvement_suggestions', mode='before')
                    def validate_lists(cls, v, info):
                        return cls.validate_list_fields(v, info.field_name)
        
        # Create a structured LLM that outputs a ShowingTellingAnalysis
        structured_llm = llm.with_structured_output(ShowingTellingAnalysis)
        
        # Use the structured LLM to analyze showing vs. telling
        showing_telling_analysis = structured_llm.invoke(prompt)
        
        # Check if we got a valid response
        if showing_telling_analysis is None:
            print("Error analyzing showing vs. telling: LLM returned None")
            return {
                "sensory_details_score": 5,
                "emotion_showing_score": 5,
                "world_element_showing_score": 5,
                "character_development_showing_score": 5,
                "overall_showing_ratio": 5,
                "telling_instances": [],
                "showing_instances": [],
                "missed_opportunities": [],
                "improvement_suggestions": ["Error analyzing showing vs. telling: LLM returned None"]
            }
        
        # Convert Pydantic model to dictionary
        return showing_telling_analysis.dict()
    
    except Exception as e:
        print(f"Error analyzing showing vs. telling: {str(e)}")
        
        # Try to extract partial results if possible
        if "showing_instances" in str(e) and "list_type" in str(e):
            # This is the specific error we're handling
            try:
                # Create a simpler prompt that focuses just on the overall scores
                simple_prompt = f"""
                Analyze this scene for the balance of showing vs. telling and provide only numeric scores:
                
                {scene_content}
                
                Provide only these scores (1-10 scale):
                - sensory_details_score
                - emotion_showing_score
                - world_element_showing_score
                - character_development_showing_score
                - overall_showing_ratio
                """
                
                # Use a simpler model without the problematic fields
                class SimpleShowingTellingAnalysis(BaseModel):
                    sensory_details_score: int = Field(ge=1, le=10)
                    emotion_showing_score: int = Field(ge=1, le=10)
                    world_element_showing_score: int = Field(ge=1, le=10)
                    character_development_showing_score: int = Field(ge=1, le=10)
                    overall_showing_ratio: int = Field(ge=1, le=10)
                
                simple_llm = llm.with_structured_output(SimpleShowingTellingAnalysis)
                simple_analysis = simple_llm.invoke(simple_prompt)
                
                # Create a result with the scores but empty lists for the problematic fields
                return {
                    **simple_analysis.dict(),
                    "telling_instances": [],
                    "showing_instances": [],
                    "missed_opportunities": [],
                    "improvement_suggestions": ["Error processing detailed analysis, showing basic scores only"]
                }
            except Exception as inner_e:
                print(f"Error in fallback analysis: {str(inner_e)}")
                # Fall back to default values if everything fails
                return {
                    "sensory_details_score": 5,
                    "emotion_showing_score": 5,
                    "world_element_showing_score": 5,
                    "character_development_showing_score": 5,
                    "overall_showing_ratio": 5,
                    "telling_instances": [],
                    "showing_instances": [],
                    "missed_opportunities": [],
                    "improvement_suggestions": ["Error analyzing showing vs. telling"]
                }
        else:
            # For other types of errors, return default values
            return {
                "sensory_details_score": 5,
                "emotion_showing_score": 5,
                "world_element_showing_score": 5,
                "character_development_showing_score": 5,
                "overall_showing_ratio": 5,
                "telling_instances": [],
                "showing_instances": [],
                "missed_opportunities": [],
                "improvement_suggestions": ["Error analyzing showing vs. telling"]
            }

def generate_concept_sensory_checklist(concept: Dict[str, Any], language: str = DEFAULT_LANGUAGE) -> str:
    """
    Generate a sensory checklist for a key concept.
    
    Args:
        concept: The concept data
        language: The language of the story (default: from config)
        
    Returns:
        A sensory checklist for the concept
    """
    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        print(f"Warning: Unsupported language '{language}'. Falling back to {DEFAULT_LANGUAGE}.")
        language = DEFAULT_LANGUAGE
    
    # Get the full language name
    language_name = SUPPORTED_LANGUAGES[language]
    
    # Prepare the prompt for generating a sensory checklist
    prompt = f"""
    Generate a sensory checklist for introducing this concept in {language_name}:
    
    CONCEPT: {concept['name']}
    DESCRIPTION: {concept['description']}
    
    Create a checklist of sensory details that could be used to introduce this concept through showing rather than telling.
    Include at least one item for each sensory category:
    - Visual details
    - Sounds
    - Smells/tastes
    - Textures/physical sensations
    - Character reactions
    - Cultural sensory associations in {language_name}-speaking cultures
    
    Format your response as a concise, actionable checklist.
    Provide your checklist in {language_name}.
    """
    
    try:
        # Generate the sensory checklist
        response = llm.invoke([HumanMessage(content=prompt)])
        
        # Check if we got a valid response
        if response is None or response.content is None:
            print("Error generating concept sensory checklist: LLM returned None")
            return f"""
            Sensory Checklist for {concept['name']}:
            - Visual: Show a physical manifestation of the concept
            - Sound: Include sounds associated with the concept
            - Smell/Taste: Add olfactory or gustatory details
            - Touch: Describe textures or physical sensations
            - Reaction: Show character physical/emotional reactions
            """
        
        # Clean up the response
        sensory_checklist = response.content.strip()
        
        return sensory_checklist
    
    except Exception as e:
        print(f"Error generating concept sensory checklist: {str(e)}")
        return f"""
        Sensory Checklist for {concept['name']}:
        - Visual: Show a physical manifestation of the concept
        - Sound: Include sounds associated with the concept
        - Smell/Taste: Add olfactory or gustatory details
        - Touch: Describe textures or physical sensations
        - Reaction: Show character physical/emotional reactions
        """