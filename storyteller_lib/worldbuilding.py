"""
StoryCraft Agent - Worldbuilding node for generating detailed world elements.

This module provides functions for generating rich worldbuilding elements
based on the story parameters (genre, tone, author style, and initial idea).
"""

from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage
from storyteller_lib.config import llm, manage_memory_tool, search_memory_tool, MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState
from storyteller_lib import track_progress
from storyteller_lib.creative_tools import parse_json_with_langchain

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
    language_elements = None
    language_guidance = ""
    
    if language.lower() != DEFAULT_LANGUAGE:
        # Try to retrieve language elements from memory
        try:
            language_elements_result = search_memory_tool.invoke({
                "query": f"language_elements_{language.lower()}",
                "namespace": MEMORY_NAMESPACE
            })
            
            # Handle different return types from search_memory_tool
            if language_elements_result:
                if isinstance(language_elements_result, dict) and "value" in language_elements_result:
                    # Direct dictionary with value
                    language_elements = language_elements_result["value"]
                elif isinstance(language_elements_result, list):
                    # List of objects
                    for item in language_elements_result:
                        if hasattr(item, 'key') and item.key == f"language_elements_{language.lower()}":
                            language_elements = item.value
                            break
                elif isinstance(language_elements_result, str):
                    # Try to parse JSON string
                    try:
                        import json
                        language_elements = json.loads(language_elements_result)
                    except:
                        # If not JSON, use as is
                        language_elements = language_elements_result
        except Exception as e:
            print(f"Error retrieving language elements: {str(e)}")
        
        # Create language guidance with specific place name examples if available
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
    
    # Create a prompt for worldbuilding
    prompt = f"""
    Generate detailed worldbuilding elements for a {genre} story with a {tone} tone,
    written in the style of {author}, based on this initial idea:
    
    {initial_idea}
    
    And this story outline:
    
    {global_story[:1000]}...
    
    {language_guidance}
    
    Create a comprehensive world with rich details across these categories:
    
    1. GEOGRAPHY:
       - Major locations (cities, countries, planets, realms, etc.)
       - Physical features (mountains, rivers, forests, etc.)
       - Climate and weather patterns
       - Notable landmarks
       - Spatial relationships between locations
    
    2. HISTORY:
       - Timeline of significant events
       - Historical figures and their impact
       - Past conflicts and resolutions
       - Origin stories or myths
       - Historical trends that shape the present
    
    3. CULTURE:
       - Languages and communication
       - Arts and entertainment
       - Traditions and customs
       - Cultural values and taboos
       - Cultural diversity and subcultures
    
    4. POLITICS:
       - Government systems and power structures
       - Political factions and their relationships
       - Laws and justice systems
       - Military and defense
       - International/inter-realm relations
    
    5. ECONOMICS:
       - Resources and their distribution
       - Trade systems and currencies
       - Economic classes and inequality
       - Industries and occupations
       - Economic challenges and opportunities
    
    6. TECHNOLOGY/MAGIC:
       - Available technologies or magic systems
       - Limitations and costs of technology/magic
       - Impact on society and daily life
       - Rare or forbidden technologies/magic
       - How technology/magic is learned or acquired
    
    7. RELIGION:
       - Belief systems and deities
       - Religious practices and rituals
       - Religious organizations and leaders
       - Role of religion in society
       - Conflicts between religious groups
    
    8. DAILY LIFE:
       - Food and cuisine
       - Clothing and fashion
       - Housing and architecture
       - Family structures and relationships
       - Education and knowledge transfer
    
    Ensure the worldbuilding elements are:
    - Consistent with the {genre} genre conventions but with unique twists
    - Appropriate for the {tone} tone
    - Aligned with {author}'s style
    - Directly relevant to the initial story idea
    - Internally consistent and logically connected
    - Detailed enough to support rich storytelling
    - Contain elements that can create conflict and drive the plot
    
    Format your response as a structured JSON object where each category is a key,
    and the value is an object containing specific elements within that category.
    """
    
    # Generate worldbuilding elements
    worldbuilding_response = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Parse the response into structured data
    try:
        world_elements = parse_json_with_langchain(worldbuilding_response, "world elements")
        
        # Ensure we have a valid dictionary
        if not isinstance(world_elements, dict):
            world_elements = {
                "geography": {"locations": "Default world location"},
                "note": "Failed to parse worldbuilding elements properly"
            }
    except Exception as e:
        print(f"Error parsing worldbuilding elements: {str(e)}")
        # Provide a minimal default structure
        world_elements = {
            "geography": {"locations": "Default world location"},
            "error": f"Failed to parse worldbuilding elements: {str(e)}"
        }
    
    # Store the world elements in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": "world_elements_initial",
        "value": world_elements,
        "namespace": MEMORY_NAMESPACE
    })
    
    # Create a world state tracker to monitor changes over time
    world_state_tracker = {
        "initial_state": world_elements,
        "current_state": world_elements,
        "changes": [],
        "revelations": [],
        "mystery_elements": {  # New section for tracking mystery elements
            "key_mysteries": [],
            "clues_revealed": {},
            "reader_knowledge": {},
            "character_knowledge": {}
        }
    }
    
    # Identify potential mystery elements from the world elements
    mystery_prompt = f"""
    Analyze these world elements and identify key mystery elements that should be gradually revealed:
    
    {world_elements}
    
    Identify 3-5 elements that would work well as mysteries in the story. For each mystery:
    1. Provide the name of the mystery element
    2. Explain why it would make a compelling mystery
    3. Suggest 3-5 clues that could gradually reveal this mystery
    
    Format your response as a structured JSON object with "key_mysteries" as a list of objects.
    """
    
    try:
        # Define Pydantic model for structured output
        from pydantic import BaseModel, Field
        from typing import List, Dict
        
        class MysteryClue(BaseModel):
            """A clue that reveals part of a mystery."""
            description: str = Field(description="Description of the clue")
            revelation_level: int = Field(ge=1, le=5, description="How much this reveals (1=subtle hint, 5=full revelation)")
            
        class MysteryElement(BaseModel):
            """A key mystery element in the story."""
            name: str = Field(description="Name of the mystery element")
            description: str = Field(description="Description of why it's a compelling mystery")
            clues: List[MysteryClue] = Field(description="Clues that could reveal this mystery")
            
        class MysteryAnalysis(BaseModel):
            """Analysis of potential mystery elements in the world."""
            key_mysteries: List[MysteryElement] = Field(description="List of key mystery elements")
            
        # Create a structured LLM that outputs a MysteryAnalysis
        structured_llm = llm.with_structured_output(MysteryAnalysis)
        
        # Use the structured LLM to identify mystery elements
        mystery_analysis = structured_llm.invoke(mystery_prompt)
        
        # Update the world state tracker with the identified mysteries
        world_state_tracker["mystery_elements"]["key_mysteries"] = [
            {
                "name": mystery.name,
                "description": mystery.description,
                "clues": [{"description": clue.description, "revelation_level": clue.revelation_level, "revealed": False}
                         for clue in mystery.clues]
            }
            for mystery in mystery_analysis.key_mysteries
        ]
    except Exception as e:
        print(f"Error identifying mystery elements: {str(e)}")
    
    # Store the world state tracker in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": "world_state_tracker",
        "value": world_state_tracker,
        "namespace": MEMORY_NAMESPACE
    })
    
    # Generate a summary of the world for quick reference
    world_summary_prompt = f"""
    Based on these detailed world elements:
    
    {world_elements}
    
    Create a concise summary (300-500 words) that captures the essence of this world.
    Focus on the most distinctive and important elements that make this world unique
    and that will most significantly impact the story.
    
    The summary should give a clear picture of what makes this world special and
    how it supports the {genre} genre with a {tone} tone.
    """
    
    # Generate the world summary
    world_summary = llm.invoke([HumanMessage(content=world_summary_prompt)]).content
    
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