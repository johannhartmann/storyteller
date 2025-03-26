"""
StoryCraft Agent - Worldbuilding node for generating detailed world elements.

This module provides functions for generating rich worldbuilding elements
based on the story parameters (genre, tone, author style, and initial idea).
It uses Pydantic models for structured data extraction and validation.
"""

from typing import Dict, Any, List, Optional, Union, Type
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage
from storyteller_lib.config import llm, manage_memory_tool, search_memory_tool, MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState
from storyteller_lib import track_progress
from storyteller_lib.creative_tools import parse_json_with_langchain

# Simple, focused Pydantic models for worldbuilding elements

class Geography(BaseModel):
    """Geography elements of the world."""
    locations: str = Field(description="Major locations (cities, countries, planets, etc.)")
    climate: Optional[str] = Field(default="", description="Climate and weather patterns")
    landmarks: Optional[str] = Field(default="", description="Notable landmarks and physical features")
    relevance: Optional[str] = Field(default="", description="How geography impacts the story")

class History(BaseModel):
    """Historical elements of the world."""
    timeline: str = Field(description="Key historical events in chronological order")
    figures: Optional[str] = Field(default="", description="Important historical figures and their impact")
    conflicts: Optional[str] = Field(default="", description="Major historical conflicts and their resolutions")
    relevance: Optional[str] = Field(default="", description="How history impacts the current story")

class Culture(BaseModel):
    """Cultural elements of the world."""
    languages: str = Field(description="Languages and communication methods")
    traditions: Optional[str] = Field(default="", description="Important traditions, customs, and arts")
    values: Optional[str] = Field(default="", description="Cultural values, taboos, and diversity")
    relevance: Optional[str] = Field(default="", description="How culture influences characters and plot")

class Politics(BaseModel):
    """Political elements of the world."""
    government: str = Field(description="Government systems and power structures")
    factions: Optional[str] = Field(default="", description="Political factions and their relationships")
    laws: Optional[str] = Field(default="", description="Important laws and justice systems")
    relevance: Optional[str] = Field(default="", description="How politics affects the story")

class Economics(BaseModel):
    """Economic elements of the world."""
    resources: str = Field(description="Key resources and their distribution")
    trade: Optional[str] = Field(default="", description="Trade systems, currencies, and markets")
    classes: Optional[str] = Field(default="", description="Economic classes and inequality")
    relevance: Optional[str] = Field(default="", description="How economics drives conflict or cooperation")

class TechnologyMagic(BaseModel):
    """Technology or magic elements of the world."""
    systems: str = Field(description="Available technologies or magic systems")
    limitations: Optional[str] = Field(default="", description="Limitations and costs of technology/magic")
    impact: Optional[str] = Field(default="", description="Impact on society and daily life")
    relevance: Optional[str] = Field(default="", description="How technology/magic creates opportunities or challenges")

class Religion(BaseModel):
    """Religious elements of the world."""
    beliefs: str = Field(description="Belief systems and deities")
    practices: Optional[str] = Field(default="", description="Religious practices and rituals")
    organizations: Optional[str] = Field(default="", description="Religious organizations and leaders")
    relevance: Optional[str] = Field(default="", description="How religion influences society and characters")

class DailyLife(BaseModel):
    """Daily life elements of the world."""
    food: str = Field(description="Food and cuisine")
    clothing: Optional[str] = Field(default="", description="Clothing and fashion")
    housing: Optional[str] = Field(default="", description="Housing and architecture")
    relevance: Optional[str] = Field(default="", description="How daily life reflects culture and status")

class MysteryClue(BaseModel):
    """A clue that reveals part of a mystery."""
    description: str = Field(description="Description of the clue")
    revelation_level: int = Field(ge=1, le=5, description="How much this reveals (1=subtle hint, 5=full revelation)")
    revealed: bool = Field(default=False, description="Whether this clue has been revealed in the story")

class MysteryElement(BaseModel):
    """A key mystery element in the story."""
    name: str = Field(description="Name of the mystery element")
    description: str = Field(description="Description of why it's a compelling mystery")
    clues: List[MysteryClue] = Field(description="Clues that could reveal this mystery")

class MysteryAnalysis(BaseModel):
    """Analysis of potential mystery elements in the world."""
    key_mysteries: List[MysteryElement] = Field(description="List of key mystery elements")

class WorldbuildingElements(BaseModel):
    """Complete worldbuilding elements model."""
    geography: Optional[Geography] = Field(default=None, description="Geographic elements of the world")
    history: Optional[History] = Field(default=None, description="Historical elements of the world")
    culture: Optional[Culture] = Field(default=None, description="Cultural elements of the world")
    politics: Optional[Politics] = Field(default=None, description="Political elements of the world")
    economics: Optional[Economics] = Field(default=None, description="Economic elements of the world")
    technology_magic: Optional[TechnologyMagic] = Field(default=None, description="Technology or magic elements of the world")
    religion: Optional[Religion] = Field(default=None, description="Religious elements of the world")
    daily_life: Optional[DailyLife] = Field(default=None, description="Daily life elements of the world")

# Helper functions for extraction and generation

def extract_with_model(text: str, model: Type[BaseModel], category_name: str) -> Dict[str, Any]:
    """
    Extract structured data using a Pydantic model with error handling.
    
    Args:
        text: Text to extract from
        model: Pydantic model to use for extraction
        category_name: Name of the category being extracted
        
    Returns:
        Dictionary containing the extracted data or error information
    """
    try:
        structured_llm = llm.with_structured_output(model)
        prompt = f"""
        Extract ONLY {category_name} information from this text:
        
        {text}
        
        Focus specifically on the key aspects of {category_name} and ignore other elements.
        """
        result = structured_llm.invoke(prompt)
        return result.model_dump()
    except Exception as e:
        print(f"Error extracting {category_name}: {str(e)}")
        return {"error": f"Failed to extract {category_name}: {str(e)}"}

def create_category_prompt(category_name: str, genre: str, tone: str, author: str,
                          initial_idea: str, global_story: str, language: str = DEFAULT_LANGUAGE,
                          language_guidance: str = "") -> str:
    """
    Create a focused prompt for generating a specific worldbuilding category.
    
    Args:
        category_name: Name of the category to generate
        genre: Story genre
        tone: Story tone
        author: Author style to emulate
        initial_idea: Initial story idea
        global_story: Global story outline
        language: Target language for generation
        language_guidance: Optional language-specific guidance
        
    Returns:
        Prompt string for generating the category
    """
    # Add language instruction
    language_instruction = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_instruction = f"""
        CRITICAL LANGUAGE INSTRUCTION:
        You MUST generate ALL content ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL elements, descriptions, names, and terms must be authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures.
        DO NOT use English or any other language at any point.
        """
    
    # Add field instructions based on category
    field_instructions = ""
    if category_name.lower() == "geography":
        field_instructions = """
        You MUST include ALL of these fields in your response:
        - locations: Major locations (cities, countries, planets, etc.)
        - climate: Climate and weather patterns
        - landmarks: Notable landmarks and physical features
        - relevance: How geography impacts the story
        """
    elif category_name.lower() == "history":
        field_instructions = """
        You MUST include ALL of these fields in your response:
        - timeline: Key historical events in chronological order
        - figures: Important historical figures and their impact
        - conflicts: Major historical conflicts and their resolutions
        - relevance: How history impacts the current story
        """
    elif category_name.lower() == "culture":
        field_instructions = """
        You MUST include ALL of these fields in your response:
        - languages: Languages and communication methods
        - traditions: Important traditions, customs, and arts
        - values: Cultural values, taboos, and diversity
        - relevance: How culture influences characters and plot
        """
    elif category_name.lower() == "politics":
        field_instructions = """
        You MUST include ALL of these fields in your response:
        - government: Government systems and power structures
        - factions: Political factions and their relationships
        - laws: Important laws and justice systems
        - relevance: How politics affects the story
        """
    elif category_name.lower() == "economics":
        field_instructions = """
        You MUST include ALL of these fields in your response:
        - resources: Key resources and their distribution
        - trade: Trade systems, currencies, and markets
        - classes: Economic classes and inequality
        - relevance: How economics drives conflict or cooperation
        """
    elif category_name.lower() == "technology_magic":
        field_instructions = """
        You MUST include ALL of these fields in your response:
        - systems: Available technologies or magic systems
        - limitations: Limitations and costs of technology/magic
        - impact: Impact on society and daily life
        - relevance: How technology/magic creates opportunities or challenges
        """
    elif category_name.lower() == "religion":
        field_instructions = """
        You MUST include ALL of these fields in your response:
        - beliefs: Belief systems and deities
        - practices: Religious practices and rituals
        - organizations: Religious organizations and leaders
        - relevance: How religion influences society and characters
        """
    elif category_name.lower() == "daily_life":
        field_instructions = """
        You MUST include ALL of these fields in your response:
        - food: Food and cuisine
        - clothing: Clothing and fashion
        - housing: Housing and architecture
        - relevance: How daily life reflects culture and status
        """
    
    return f"""
    Generate {category_name} elements for a {genre} story with a {tone} tone,
    written in the style of {author}, based on this initial idea:
    
    {initial_idea}
    
    And this story outline:
    
    {global_story[:500]}...
    
    {language_instruction}
    {language_guidance}
    
    {field_instructions}
    
    IMPORTANT: You MUST include ALL the fields listed above in your response. Do not omit any fields.
    
    Focus ONLY on {category_name} elements. Be detailed and specific.
    
    Ensure the elements are:
    - Consistent with the {genre} genre conventions
    - Appropriate for the {tone} tone
    - Aligned with {author}'s style
    - Directly relevant to the initial story idea
    - Detailed enough to support rich storytelling
    - {"Authentic to " + SUPPORTED_LANGUAGES[language.lower()] + "-speaking cultures" if language.lower() != DEFAULT_LANGUAGE else ""}
    """
def generate_category(category_name: str, model: Type[BaseModel], genre: str, tone: str,
                     author: str, initial_idea: str, global_story: str,
                     language: str = DEFAULT_LANGUAGE, language_guidance: str = "") -> Dict[str, Any]:
    """
    Generate a specific worldbuilding category using a Pydantic model.
    
    Args:
        category_name: Name of the category to generate
        model: Pydantic model to use for generation
        genre: Story genre
        tone: Story tone
        author: Author style to emulate
        initial_idea: Initial story idea
        global_story: Global story outline
        language: Target language for generation
        language_guidance: Optional language-specific guidance
        
    Returns:
        Dictionary containing the generated category data
    """
    try:
        structured_llm = llm.with_structured_output(model)
        prompt = create_category_prompt(
            category_name, genre, tone, author, initial_idea, global_story, language, language_guidance
        )
        
        
        result = structured_llm.invoke(prompt)
                
        return result.model_dump()

    except Exception as e:
        print(f"Error generating {category_name}: {str(e)}")
        
        # Fallback to unstructured generation and parsing
        try:
            response = llm.invoke([HumanMessage(content=prompt)]).content
            
            # Try to parse the response using the model
            retry_prompt = f"""
            Based on this information about {category_name}:
            
            {response}
            
            Extract the key elements in a structured format.
            """
            
            retry_llm = llm.with_structured_output(model)
            retry_result = retry_llm.invoke(retry_prompt)
            return retry_result.model_dump()
        except Exception as e2:
            print(f"Fallback also failed for {category_name}: {str(e2)}")
            
            # Create minimal structure with default values for all fields
            default_values = {}
            for field_name in model.__fields__:
                if field_name == "relevance":
                    default_values[field_name] = f"Error generating {category_name}: {str(e)}, {str(e2)}"
                else:
                    default_values[field_name] = f"Default {field_name} (generation failed)"
            return default_values

def generate_mystery_elements(world_elements: Dict[str, Any], num_mysteries: int = 3, language: str = DEFAULT_LANGUAGE) -> Dict[str, Any]:
    """
    Generate mystery elements based on the worldbuilding elements.
    
    Args:
        world_elements: Dictionary of worldbuilding elements
        num_mysteries: Number of mysteries to generate
        language: Target language for generation
        
    Returns:
        Dictionary containing mystery elements
    """
    # Create a simplified representation of the world elements
    simplified_world = {}
    for category_name, category_data in world_elements.items():
        simplified_world[category_name] = {
            k: v for k, v in category_data.items() if k != "relevance"
        }
    
    try:
        # Create a structured LLM that outputs a MysteryAnalysis
        structured_llm = llm.with_structured_output(MysteryAnalysis)
        
        # Add language instruction
        language_instruction = ""
        if language.lower() != DEFAULT_LANGUAGE:
            language_instruction = f"""
            CRITICAL LANGUAGE INSTRUCTION:
            You MUST generate ALL content ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
            ALL mystery elements, descriptions, names, and clues must be authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures.
            DO NOT use English or any other language at any point.
            """
        
        # Create a prompt for identifying mystery elements
        prompt = f"""
        Analyze these world elements and identify {num_mysteries} elements that would work well as mysteries in a story:
        
        {simplified_world}
        
        {language_instruction}
        
        Identify {num_mysteries} elements that would work well as mysteries in the story. For each mystery:
        1. Provide the name of the mystery element
        2. Explain why it would make a compelling mystery
        3. Suggest 3-5 clues that could gradually reveal this mystery
        
        Each clue should have a revelation level from 1 (subtle hint) to 5 (full revelation).
        
        {"Make sure all content is authentic to " + SUPPORTED_LANGUAGES[language.lower()] + "-speaking cultures." if language.lower() != DEFAULT_LANGUAGE else ""}
        """
        
        # Extract the structured data
        mystery_analysis = structured_llm.invoke(prompt)
        
        # Convert to dictionary
        return mystery_analysis.model_dump()
    except Exception as e:
        print(f"Error generating mystery elements: {str(e)}")
        
        # Create basic mystery elements as fallback
        return {
            "key_mysteries": [
                {
                    "name": "Hidden Past",
                    "description": "A mysterious element from the world's history",
                    "clues": [
                        {"description": "A subtle reference in ancient texts", "revelation_level": 1, "revealed": False},
                        {"description": "Physical evidence discovered", "revelation_level": 3, "revealed": False},
                        {"description": "The full truth revealed", "revelation_level": 5, "revealed": False}
                    ]
                }
            ]
        }

def generate_world_summary(world_elements: Dict[str, Any], genre: str, tone: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Generate a summary of the world based on the worldbuilding elements.
    
    Args:
        world_elements: Dictionary of worldbuilding elements
        genre: Story genre
        tone: Story tone
        language: Target language for generation
        
    Returns:
        String containing the world summary
    """
    # Extract category summaries
    category_summaries = []
    for category_name, category_data in world_elements.items():
        relevance = category_data.get("relevance", "")
        summary = f"**{category_name}**: "
        
        # Add key elements to the summary
        for field, value in category_data.items():
            if field != "relevance":
                summary += f"{field}: {value[:100]}... "
        
        # Add relevance if available
        if relevance:
            summary += f"\nRelevance: {relevance}"
            
        category_summaries.append(summary)
    
    # Add language instruction
    language_instruction = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_instruction = f"""
        CRITICAL LANGUAGE INSTRUCTION:
        You MUST write this summary ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL descriptions, names, terms, and concepts must be authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures.
        DO NOT use English or any other language at any point.
        """
    
    # Generate the world summary
    prompt = f"""
    Based on these world elements:
    
    {'\n\n'.join(category_summaries)}
    
    {language_instruction}
    
    Create a concise summary (300-500 words) that captures the essence of this world.
    Focus on the most distinctive and important elements that make this world unique
    and that will most significantly impact the story.
    
    The summary should give a clear picture of what makes this world special and
    how it supports the {genre} genre with a {tone} tone.
    
    {"Make sure the summary is culturally authentic to " + SUPPORTED_LANGUAGES[language.lower()] + "-speaking readers." if language.lower() != DEFAULT_LANGUAGE else ""}
    """
    
    try:
        
        response = llm.invoke([HumanMessage(content=prompt)]).content
        
        
        return response
    except Exception as e:
        print(f"Error generating world summary: {str(e)}")
        return f"Error generating world summary: {str(e)}"

@track_progress
def generate_worldbuilding(state: StoryState) -> Dict:
    """
    Generate detailed worldbuilding elements based on the story parameters.
    
    This function creates a rich set of world elements across multiple categories:
    - Geography: Physical locations, climate, terrain, etc.
    - History: Timeline of events, historical figures, etc.
    - Culture: Customs, traditions, arts, etc.
    - Politics: Government systems, power structures, etc.
    - Economics: Trade systems, currencies, resources, etc.
    - Technology/Magic: Available technologies or magic systems
    - Religion: Belief systems, deities, practices, etc.
    - Daily Life: Food, clothing, housing, etc.
    
    The elements are tailored to the genre, tone, and initial story idea.
    """
    # Extract relevant parameters from state
    genre = state["genre"]
    tone = state["tone"]
    author = state["author"]
    initial_idea = state.get("initial_idea", "")
    global_story = state["global_story"]
    
    # Get language elements if not English
    language = state.get("language", DEFAULT_LANGUAGE)
    language_guidance = ""
    
    if language.lower() != DEFAULT_LANGUAGE:
        # Try to retrieve language elements from memory
        try:
            language_elements_result = search_memory_tool.invoke({
                "query": f"language_elements_{language.lower()}",
                "namespace": MEMORY_NAMESPACE
            })
            
            # Process language elements if found
            language_elements = None
            if language_elements_result:
                if isinstance(language_elements_result, dict) and "value" in language_elements_result:
                    language_elements = language_elements_result["value"]
                elif isinstance(language_elements_result, list):
                    for item in language_elements_result:
                        if hasattr(item, 'key') and item.key == f"language_elements_{language.lower()}":
                            language_elements = item.value
                            break
                elif isinstance(language_elements_result, str):
                    try:
                        import json
                        language_elements = json.loads(language_elements_result)
                    except:
                        language_elements = language_elements_result
            
            # Create language guidance with place name examples if available
            place_name_examples = ""
            if language_elements and "PLACE NAMES" in language_elements:
                place_names = language_elements["PLACE NAMES"]
                place_name_examples = "Examples of authentic place naming conventions:\n"
                for key, value in place_names.items():
                    if value:
                        place_name_examples += f"- {key}: {value}\n"
            
            language_guidance = f"""
            LANGUAGE CONSIDERATIONS:
            This world will be part of a story written in {SUPPORTED_LANGUAGES[language.lower()]}.
            
            When creating worldbuilding elements:
            1. Use place names that follow {SUPPORTED_LANGUAGES[language.lower()]} naming conventions
            2. Include cultural elements authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking regions
            3. Incorporate historical references, myths, and legends familiar to {SUPPORTED_LANGUAGES[language.lower()]} speakers
            4. Design social structures, governance, and customs that reflect {SUPPORTED_LANGUAGES[language.lower()]} cultural contexts
            5. Create religious systems, beliefs, and practices that resonate with {SUPPORTED_LANGUAGES[language.lower()]} cultural traditions
            
            {place_name_examples}
            
            The world should feel authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking readers rather than like a translated setting.
            """
        except Exception as e:
            print(f"Error retrieving language elements: {str(e)}")
    
    # Define category models mapping
    category_models = {
        "geography": Geography,
        "history": History,
        "culture": Culture,
        "politics": Politics,
        "economics": Economics,
        "technology_magic": TechnologyMagic,
        "religion": Religion,
        "daily_life": DailyLife
    }
    
    # Generate each category separately
    world_elements = {}
    for category_name, model in category_models.items():
        print(f"Generating {category_name} elements...")
        category_data = generate_category(
            category_name, model, genre, tone, author, initial_idea, global_story, language, language_guidance
        )
        world_elements[category_name] = category_data
    
    # Store the world elements in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": "world_elements_initial",
        "value": world_elements,
        "namespace": MEMORY_NAMESPACE
    })
    
    # Generate mystery elements
    mystery_elements = generate_mystery_elements(world_elements, 3, language)
    
    # Create a world state tracker to monitor changes over time
    world_state_tracker = {
        "initial_state": world_elements,
        "current_state": world_elements,
        "changes": [],
        "revelations": [],
        "mystery_elements": {
            "key_mysteries": mystery_elements.get("key_mysteries", []),
            "clues_revealed": {},
            "reader_knowledge": {},
            "character_knowledge": {}
        }
    }
    
    # Store the world state tracker in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": "world_state_tracker",
        "value": world_state_tracker,
        "namespace": MEMORY_NAMESPACE
    })
    
    # Generate a summary of the world
    world_summary = generate_world_summary(world_elements, genre, tone, language)
    
    # Store the world summary in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": "world_summary",
        "value": world_summary,
        "namespace": MEMORY_NAMESPACE
    })
    
    # Return the world elements and summary
    return {
        "world_elements": world_elements,
        "messages": [
            *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
            AIMessage(content=f"I've created detailed worldbuilding elements for your {genre} story with a {tone} tone. The world includes geography, history, culture, politics, economics, technology/magic, religion, and daily life elements that will support your story.\n\nWorld Summary:\n{world_summary}")
        ]
    }

def extract_worldbuilding(text: str) -> WorldbuildingElements:
    """
    Extract worldbuilding elements from text.
    
    Args:
        text: Text containing worldbuilding information
        
    Returns:
        WorldbuildingElements object containing the extracted data
    """
    # Define category models mapping
    category_models = {
        "geography": Geography,
        "history": History,
        "culture": Culture,
        "politics": Politics,
        "economics": Economics,
        "technology_magic": TechnologyMagic,
        "religion": Religion,
        "daily_life": DailyLife
    }
    
    # Extract each category separately
    extracted_data = {}
    for category_name, model in category_models.items():
        category_data = extract_with_model(text, model, category_name)
        if "error" not in category_data:
            extracted_data[category_name] = category_data
    
    # Create and return the WorldbuildingElements object
    return WorldbuildingElements(**extracted_data)

def extract_specific_element(text: str, element_type: str) -> Dict[str, Any]:
    """
    Extract a specific worldbuilding element from text.
    
    Args:
        text: Text containing worldbuilding information
        element_type: Type of element to extract (e.g., "geography", "history")
        
    Returns:
        Dictionary containing the extracted element data
    """
    # Map element types to their corresponding models
    element_models = {
        "geography": Geography,
        "history": History,
        "culture": Culture,
        "politics": Politics,
        "economics": Economics,
        "technology": TechnologyMagic,
        "magic": TechnologyMagic,
        "religion": Religion,
        "daily_life": DailyLife
    }
    
    # Normalize the element type
    element_type_lower = element_type.lower()
    
    # Get the appropriate model
    model = element_models.get(element_type_lower)
    if not model:
        raise ValueError(f"Unknown element type: {element_type}. Valid types are: {', '.join(element_models.keys())}")
    
    # Extract the element
    return extract_with_model(text, model, element_type)

def extract_mystery_elements(text: str, num_mysteries: int = 3) -> Dict[str, Any]:
    """
    Extract potential mystery elements from text.
    
    Args:
        text: Text to analyze for potential mysteries
        num_mysteries: Number of mysteries to identify
        
    Returns:
        Dictionary containing structured mystery elements
    """
    try:
        # Create a structured LLM with the MysteryAnalysis model
        structured_llm = llm.with_structured_output(MysteryAnalysis)
        
        # Create a prompt for identifying mystery elements
        prompt = f"""
        Analyze this text and identify {num_mysteries} elements that would work well as mysteries in a story:
        
        {text}
        
        For each mystery:
        1. Provide the name of the mystery element
        2. Explain why it would make a compelling mystery
        3. Suggest 3-5 clues that could gradually reveal this mystery
        
        Each clue should have a revelation level from 1 (subtle hint) to 5 (full revelation).
        """
        
        # Extract the structured data
        mystery_analysis = structured_llm.invoke(prompt)
        
        # Convert to dictionary
        return mystery_analysis.model_dump()
    except Exception as e:
        print(f"Error extracting mystery elements: {str(e)}")
        return {"error": f"Failed to extract mystery elements: {str(e)}"}
