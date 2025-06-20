"""
StoryCraft Agent - Worldbuilding node for generating detailed world elements.

This module provides functions for generating rich worldbuilding elements
based on the story parameters (genre, tone, author style, and initial idea).
It uses Pydantic models for structured data extraction and validation.
"""

from typing import Dict, Any, List, Optional, Union, Type
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage
from storyteller_lib.config import llm, MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState
# Memory manager imports removed - using state and database instead
from storyteller_lib import track_progress
from storyteller_lib.logger import get_logger

logger = get_logger(__name__)

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

class MysteryAnalysisFlat(BaseModel):
    """Flattened analysis of potential mystery elements to avoid nested dictionaries."""
    mystery_names: str = Field(description="Pipe-separated list of mystery element names")
    mystery_descriptions: str = Field(description="Pipe-separated list of why each mystery is compelling")
    mystery_clues: str = Field(description="Pipe-separated list of semicolon-separated clue descriptions for each mystery")
    mystery_clue_levels: str = Field(description="Pipe-separated list of comma-separated revelation levels (1-5) for each mystery's clues")

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
        # Use template system
        from storyteller_lib.prompt_templates import render_prompt
        
        structured_llm = llm.with_structured_output(model)
        prompt = render_prompt(
            'extract_category_info',
            "english",  # Always extract in English for consistency
            category_name=category_name,
            text=text
        )
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
    # Use the template system
    from storyteller_lib.prompt_templates import render_prompt
    
    # Handle special category names
    category_template_name = category_name.lower()
    if category_template_name == "technology_magic":
        category_template_name = "technology_or_magic"
    elif category_template_name == "daily_life":
        category_template_name = "daily_life"
    
    # Check if we have a worldbuilding template
    try:
        # Worldbuilding elements are stored in database world_elements table
        existing_elements = ""
        
        # Render the template with just the category name
        # The template will handle all field descriptions in the appropriate language
        prompt = render_prompt(
            'worldbuilding',
            language=language,
            story_outline=global_story,  # Pass full story outline, not truncated
            genre=genre,
            tone=tone,
            existing_elements=existing_elements if existing_elements else None,
            category_name=category_name,
            initial_idea=initial_idea,
            author=author
        )
        
        # Remove all hardcoded field instructions - they're now in the templates
        if False:  # Keep structure for backwards compatibility but never execute
            field_instructions = """
            
            FOCUS ON GEOGRAPHY:
            You MUST include ALL of these fields in your response:
            - locations: Major locations (cities, countries, planets, etc.)
            - climate: Climate and weather patterns
            - landmarks: Notable landmarks and physical features
            - relevance: How geography impacts the story
            """
        elif category_name.lower() == "history":
            field_instructions = """
            
            FOCUS ON HISTORY:
            You MUST include ALL of these fields in your response:
            - timeline: Key historical events in chronological order
            - figures: Important historical figures and their impact
            - conflicts: Major historical conflicts and their resolutions
            - relevance: How history impacts the current story
            """
        elif category_name.lower() == "culture":
            field_instructions = """
            
            FOCUS ON CULTURE:
            You MUST include ALL of these fields in your response:
            - languages: Languages and communication methods
            - traditions: Important traditions, customs, and arts
            - values: Cultural values, taboos, and diversity
            - relevance: How culture influences characters and plot
            """
        elif category_name.lower() == "politics":
            field_instructions = """
            
            FOCUS ON POLITICS:
            You MUST include ALL of these fields in your response:
            - government: Government systems and power structures
            - factions: Political factions and their relationships
            - laws: Important laws and justice systems
            - relevance: How politics affects the story
            """
        elif category_name.lower() == "economics":
            field_instructions = """
            
            FOCUS ON ECONOMICS:
            You MUST include ALL of these fields in your response:
            - resources: Key resources and their distribution
            - trade: Trade systems, currencies, and markets
            - classes: Economic classes and inequality
            - relevance: How economics drives conflict or cooperation
            """
        elif category_name.lower() == "technology_magic":
            field_instructions = """
            
            FOCUS ON TECHNOLOGY/MAGIC:
            You MUST include ALL of these fields in your response:
            - systems: Available technologies or magic systems
            - limitations: Limitations and costs of technology/magic
            - impact: Impact on society and daily life
            - relevance: How technology/magic creates opportunities or challenges
            """
        elif category_name.lower() == "religion":
            field_instructions = """
            
            FOCUS ON RELIGION:
            You MUST include ALL of these fields in your response:
            - beliefs: Belief systems and deities
            - practices: Religious practices and rituals
            - organizations: Religious organizations and leaders
            - relevance: How religion influences society and characters
            """
        elif category_name.lower() == "daily_life":
            field_instructions = """
            
            FOCUS ON DAILY LIFE:
            You MUST include ALL of these fields in your response:
            - food: Food and cuisine
            - clothing: Clothing and fashion
            - housing: Housing and architecture
            - relevance: How daily life reflects culture and status
            """
        
        return prompt
        
    except Exception as e:
        # Fallback to the original implementation if template fails
        logger.warning(f"Failed to use template for worldbuilding: {e}")
        
        # Original implementation as fallback
        language_instruction = ""
        if language.lower() != DEFAULT_LANGUAGE:
            language_instruction = f"""
            CRITICAL LANGUAGE INSTRUCTION:
            You MUST generate ALL content ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
            ALL elements, descriptions, names, and terms must be authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures.
            DO NOT use English or any other language at any point.
            """
        
        # Field instructions (same as above)
        field_instructions = ""
        if category_name.lower() == "geography":
            field_instructions = """
            You MUST include ALL of these fields in your response:
            - locations: Major locations (cities, countries, planets, etc.)
            - climate: Climate and weather patterns
            - landmarks: Notable landmarks and physical features
            - relevance: How geography impacts the story
            """
        # ... rest of field instructions ...
        
        return f"""
        Generate {category_name} elements for a {genre} story with a {tone} tone,
        written in the style of {author}, based on this initial idea:
        
        {initial_idea}
        
        And this story outline:
        
        {global_story}
        
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
    # Use structured output only - no fallback
    structured_llm = llm.with_structured_output(model)
    prompt = create_category_prompt(
        category_name, genre, tone, author, initial_idea, global_story, language, language_guidance
    )
    
    result = structured_llm.invoke(prompt)
    return result.model_dump()

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
    from storyteller_lib.prompt_templates import render_prompt
    
    # Create a simplified representation of the world elements
    simplified_world = {}
    for category_name, category_data in world_elements.items():
        simplified_world[category_name] = {
            k: v for k, v in category_data.items() if k != "relevance"
        }
    
    try:
        # Create a structured LLM that outputs a flattened MysteryAnalysis
        structured_llm = llm.with_structured_output(MysteryAnalysisFlat)
        
        # Add language instruction
        language_instruction = ""
        if language.lower() != DEFAULT_LANGUAGE:
            language_instruction = f"""
            CRITICAL LANGUAGE INSTRUCTION:
            You MUST generate ALL content ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
            ALL mystery elements, descriptions, names, and clues must be authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures.
            DO NOT use English or any other language at any point.
            """
        
        # Use template system
        from storyteller_lib.prompt_templates import render_prompt
        
        # Create a prompt for identifying mystery elements
        prompt = render_prompt(
            'mystery_elements',
            language=language,
            num_mysteries=num_mysteries,
            world_elements=simplified_world,
            language_instruction=language_instruction if language.lower() != DEFAULT_LANGUAGE else None,
            make_authentic=language.lower() != DEFAULT_LANGUAGE,
            target_language=SUPPORTED_LANGUAGES[language.lower()] if language.lower() != DEFAULT_LANGUAGE else None
        )
        
        # Extract the structured data
        mystery_analysis_flat = structured_llm.invoke(prompt)
        
        # Convert flattened data to nested structure
        names = [n.strip() for n in mystery_analysis_flat.mystery_names.split("|")]
        descriptions = [d.strip() for d in mystery_analysis_flat.mystery_descriptions.split("|")]
        clues_lists = [c.strip() for c in mystery_analysis_flat.mystery_clues.split("|")]
        levels_lists = [l.strip() for l in mystery_analysis_flat.mystery_clue_levels.split("|")]
        
        key_mysteries = []
        for name, desc, clues_str, levels_str in zip(names, descriptions, clues_lists, levels_lists):
            clues = [c.strip() for c in clues_str.split(";") if c.strip()]
            levels = [int(l.strip()) for l in levels_str.split(",") if l.strip()]
            
            mystery_clues = []
            for clue_desc, level in zip(clues, levels):
                mystery_clues.append({
                    "description": clue_desc,
                    "revelation_level": level,
                    "revealed": False
                })
            
            key_mysteries.append({
                "name": name,
                "description": desc,
                "clues": mystery_clues
            })
        
        return {"key_mysteries": key_mysteries}
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
    from storyteller_lib.prompt_templates import render_prompt
    
    # Extract category summaries
    category_summaries = []
    for category_name, category_data in world_elements.items():
        relevance = category_data.get("relevance", "")
        summary = f"**{category_name}**: "
        
        # Add key elements to the summary
        for field, value in category_data.items():
            if field != "relevance" and value is not None:
                # Handle different value types
                if isinstance(value, str):
                    value_str = value[:100] + "..." if len(value) > 100 else value
                elif isinstance(value, list):
                    value_str = ", ".join(str(v) for v in value[:3]) + ("..." if len(value) > 3 else "")
                else:
                    value_str = str(value)
                summary += f"{field}: {value_str} "
        
        # Add relevance if available
        if relevance:
            summary += f"{chr(10)}Relevance: {relevance}"
            
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
    
    # Use template system
    from storyteller_lib.prompt_templates import render_prompt
    
    # Generate the world summary
    prompt = render_prompt(
        'world_summary',
        language=language,
        category_summaries=chr(10) + chr(10).join(category_summaries),
        language_instruction=language_instruction if language.lower() != DEFAULT_LANGUAGE else None,
        genre=genre,
        tone=tone,
        make_authentic=language.lower() != DEFAULT_LANGUAGE,
        target_language=SUPPORTED_LANGUAGES[language.lower()] if language.lower() != DEFAULT_LANGUAGE else None
    )
    
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
    # Load configuration from database
    from storyteller_lib.config import get_story_config
    config = get_story_config()
    
    genre = config["genre"]
    tone = config["tone"]
    author = config["author"]
    initial_idea = config["initial_idea"]
    # Get full story outline from database
    from storyteller_lib.database_integration import get_db_manager
    db_manager = get_db_manager()
    
    if not db_manager or not db_manager._db:
        raise RuntimeError("Database manager not available - cannot retrieve story outline")
    
    # Get full story outline from database
    from storyteller_lib.logger import get_logger
    logger = get_logger(__name__)
    logger.debug("Fetching global story from database")
    
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, global_story, genre, tone FROM story_config WHERE id = 1"
        )
        result = cursor.fetchone()
        
        if not result:
            logger.error("No story configuration found in database")
            # Try to check if any rows exist
            cursor.execute("SELECT COUNT(*) FROM story_config")
            count = cursor.fetchone()[0]
            logger.error(f"Total rows in story_config: {count}")
            raise RuntimeError("Story configuration not found in database")
        
        logger.info(f"Found story config row with id={result['id']}")
        global_story = result['global_story']
        
        if not global_story or global_story.strip() == "":
            logger.error(f"Story configuration exists but has empty global_story. Genre={result['genre']}, Tone={result['tone']}")
            # Check state for global_story
            if 'global_story' in state and state['global_story']:
                logger.info(f"Found global_story in state with length {len(state['global_story'])}")
                global_story = state['global_story']
            else:
                raise RuntimeError("Story outline is empty in database")
        
        logger.info(f"Retrieved global story for worldbuilding (length: {len(global_story)} chars)")
    
    # Get language elements if not English
    language = state.get("language", DEFAULT_LANGUAGE)
    language_guidance = ""
    
    if language.lower() != DEFAULT_LANGUAGE:
        # Language elements are generated fresh during initialization
        try:
            language_elements_result = None
            
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
                        place_name_examples += f"- {key}: {value}{chr(10)}"
            
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
    
    # World elements are now stored in database via database_integration
    # Memory tool has been removed - metadata is tracked in the database
    
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
    
    # World state tracker is now managed through database tables
    # No need to store separately
    
    # Generate a summary of the world
    world_summary = generate_world_summary(world_elements, genre, tone, language)
    
    # World summary is generated on demand, not stored separately
    
    # Log world elements
    from storyteller_lib.story_progress_logger import log_progress
    log_progress("world_elements", world_elements=world_elements)
    
    # Return the world elements and summary
    # Store world elements in database
    from storyteller_lib.database_integration import get_db_manager
    db_manager = get_db_manager()
    if db_manager:
        try:
            # Store world elements
            db_manager.save_worldbuilding(world_elements)
            logger.info("World elements stored in database")
        except Exception as e:
            logger.warning(f"Could not store world elements in database: {e}")
    
    # Return minimal state update - just a flag that worldbuilding is done
    return {
        "world_elements": {"stored_in_db": True},  # Minimal marker
        "messages": [
            *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
            AIMessage(content=f"I've created detailed worldbuilding elements for your {genre} story with a {tone} tone. The world includes geography, history, culture, politics, economics, technology/magic, religion, and daily life elements that will support your story.{chr(10)}{chr(10)}World Summary:{chr(10)}{world_summary}")
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
        
        # Use template system
        from storyteller_lib.prompt_templates import render_prompt
        
        # Create a prompt for identifying mystery elements
        prompt = render_prompt(
            'mystery_elements',
            "english",  # Always extract in English for consistency
            num_mysteries=num_mysteries,
            world_elements=text
        )
        
        # Extract the structured data
        mystery_analysis_flat = structured_llm.invoke(prompt)
        
        # Convert flattened data to nested structure
        names = [n.strip() for n in mystery_analysis_flat.mystery_names.split("|")]
        descriptions = [d.strip() for d in mystery_analysis_flat.mystery_descriptions.split("|")]
        clues_lists = [c.strip() for c in mystery_analysis_flat.mystery_clues.split("|")]
        levels_lists = [l.strip() for l in mystery_analysis_flat.mystery_clue_levels.split("|")]
        
        key_mysteries = []
        for name, desc, clues_str, levels_str in zip(names, descriptions, clues_lists, levels_lists):
            clues = [c.strip() for c in clues_str.split(";") if c.strip()]
            levels = [int(l.strip()) for l in levels_str.split(",") if l.strip()]
            
            mystery_clues = []
            for clue_desc, level in zip(clues, levels):
                mystery_clues.append({
                    "description": clue_desc,
                    "revelation_level": level,
                    "revealed": False
                })
            
            key_mysteries.append({
                "name": name,
                "description": desc,
                "clues": mystery_clues
            })
        
        return {"key_mysteries": key_mysteries}
    except Exception as e:
        print(f"Error extracting mystery elements: {str(e)}")
        return {"error": f"Failed to extract mystery elements: {str(e)}"}
