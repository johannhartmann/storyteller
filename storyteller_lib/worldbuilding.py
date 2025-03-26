"""
StoryCraft Agent - Worldbuilding node for generating detailed world elements.

This module provides functions for generating rich worldbuilding elements
based on the story parameters (genre, tone, author style, and initial idea).
It uses Pydantic models for structured data extraction and validation.
"""

from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage
from storyteller_lib.config import llm, manage_memory_tool, search_memory_tool, MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState
from storyteller_lib import track_progress
from storyteller_lib.creative_tools import parse_json_with_langchain, structured_output_with_pydantic

# Pydantic models for structured worldbuilding data extraction

class GeographyElement(BaseModel):
    """Geography elements of the world."""
    major_locations: Dict[str, str] = Field(
        default_factory=dict,
        description="Major locations (cities, countries, planets, realms, etc.)"
    )
    physical_features: Dict[str, str] = Field(
        default_factory=dict,
        description="Physical features (mountains, rivers, forests, etc.)"
    )
    climate: str = Field(
        default="",
        description="Climate and weather patterns"
    )
    landmarks: Dict[str, str] = Field(
        default_factory=dict,
        description="Notable landmarks"
    )
    spatial_relationships: str = Field(
        default="",
        description="Spatial relationships between locations"
    )

class HistoryElement(BaseModel):
    """Historical elements of the world."""
    timeline: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Timeline of significant events"
    )
    historical_figures: Dict[str, str] = Field(
        default_factory=dict,
        description="Historical figures and their impact"
    )
    past_conflicts: Dict[str, str] = Field(
        default_factory=dict,
        description="Past conflicts and resolutions"
    )
    origin_stories: Dict[str, str] = Field(
        default_factory=dict,
        description="Origin stories or myths"
    )
    historical_trends: List[str] = Field(
        default_factory=list,
        description="Historical trends that shape the present"
    )

class CultureElement(BaseModel):
    """Cultural elements of the world."""
    languages: Dict[str, str] = Field(
        default_factory=dict,
        description="Languages and communication"
    )
    arts: Dict[str, str] = Field(
        default_factory=dict,
        description="Arts and entertainment"
    )
    traditions: Dict[str, str] = Field(
        default_factory=dict,
        description="Traditions and customs"
    )
    values: List[str] = Field(
        default_factory=list,
        description="Cultural values and taboos"
    )
    diversity: Dict[str, str] = Field(
        default_factory=dict,
        description="Cultural diversity and subcultures"
    )

class PoliticsElement(BaseModel):
    """Political elements of the world."""
    government: Dict[str, str] = Field(
        default_factory=dict,
        description="Government systems and power structures"
    )
    factions: Dict[str, str] = Field(
        default_factory=dict,
        description="Political factions and their relationships"
    )
    laws: Dict[str, str] = Field(
        default_factory=dict,
        description="Laws and justice systems"
    )
    military: Dict[str, str] = Field(
        default_factory=dict,
        description="Military and defense"
    )
    international_relations: Dict[str, str] = Field(
        default_factory=dict,
        description="International/inter-realm relations"
    )

class EconomicsElement(BaseModel):
    """Economic elements of the world."""
    resources: Dict[str, str] = Field(
        default_factory=dict,
        description="Resources and their distribution"
    )
    trade: Dict[str, str] = Field(
        default_factory=dict,
        description="Trade systems and currencies"
    )
    classes: Dict[str, str] = Field(
        default_factory=dict,
        description="Economic classes and inequality"
    )
    industries: Dict[str, str] = Field(
        default_factory=dict,
        description="Industries and occupations"
    )
    challenges: List[str] = Field(
        default_factory=list,
        description="Economic challenges and opportunities"
    )

class TechnologyMagicElement(BaseModel):
    """Technology or magic elements of the world."""
    systems: Dict[str, str] = Field(
        default_factory=dict,
        description="Available technologies or magic systems"
    )
    limitations: Dict[str, str] = Field(
        default_factory=dict,
        description="Limitations and costs of technology/magic"
    )
    impact: str = Field(
        default="",
        description="Impact on society and daily life"
    )
    rare_elements: Dict[str, str] = Field(
        default_factory=dict,
        description="Rare or forbidden technologies/magic"
    )
    acquisition: str = Field(
        default="",
        description="How technology/magic is learned or acquired"
    )

class ReligionElement(BaseModel):
    """Religious elements of the world."""
    belief_systems: Dict[str, str] = Field(
        default_factory=dict,
        description="Belief systems and deities"
    )
    practices: Dict[str, str] = Field(
        default_factory=dict,
        description="Religious practices and rituals"
    )
    organizations: Dict[str, str] = Field(
        default_factory=dict,
        description="Religious organizations and leaders"
    )
    role: str = Field(
        default="",
        description="Role of religion in society"
    )
    conflicts: Dict[str, str] = Field(
        default_factory=dict,
        description="Conflicts between religious groups"
    )

class DailyLifeElement(BaseModel):
    """Daily life elements of the world."""
    food: Dict[str, str] = Field(
        default_factory=dict,
        description="Food and cuisine"
    )
    clothing: Dict[str, str] = Field(
        default_factory=dict,
        description="Clothing and fashion"
    )
    housing: Dict[str, str] = Field(
        default_factory=dict,
        description="Housing and architecture"
    )
    family: Dict[str, str] = Field(
        default_factory=dict,
        description="Family structures and relationships"
    )
    education: Dict[str, str] = Field(
        default_factory=dict,
        description="Education and knowledge transfer"
    )

class WorldElements(BaseModel):
    """Complete worldbuilding elements model."""
    GEOGRAPHY: GeographyElement = Field(
        default_factory=GeographyElement,
        description="Geographic elements of the world"
    )
    HISTORY: HistoryElement = Field(
        default_factory=HistoryElement,
        description="Historical elements of the world"
    )
    CULTURE: CultureElement = Field(
        default_factory=CultureElement,
        description="Cultural elements of the world"
    )
    POLITICS: PoliticsElement = Field(
        default_factory=PoliticsElement,
        description="Political elements of the world"
    )
    ECONOMICS: EconomicsElement = Field(
        default_factory=EconomicsElement,
        description="Economic elements of the world"
    )
    TECHNOLOGY_MAGIC: TechnologyMagicElement = Field(
        default_factory=TechnologyMagicElement,
        alias="TECHNOLOGY/MAGIC",
        description="Technology or magic elements of the world"
    )
    RELIGION: ReligionElement = Field(
        default_factory=ReligionElement,
        description="Religious elements of the world"
    )
    DAILY_LIFE: DailyLifeElement = Field(
        default_factory=DailyLifeElement,
        description="Daily life elements of the world"
    )

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

# Simplified models for category-by-category generation
class SimplifiedWorldElement(BaseModel):
    """A simplified worldbuilding element with description and relevance."""
    description: str = Field(description="Description of this element")
    relevance: Optional[str] = Field(default="", description="How this element is relevant to the story")

class SimplifiedCategory(BaseModel):
    """A simplified category with key elements."""
    elements: Dict[str, SimplifiedWorldElement] = Field(
        default_factory=dict,
        description="Key elements in this category"
    )
    summary: str = Field(
        default="",
        description="Summary of this category"
    )

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
    Uses an incremental category-by-category approach with templates for reliability.
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
    
    # Define categories and their key elements to generate
    categories = [
        {
            "name": "GEOGRAPHY",
            "description": "Geographic elements of the world",
            "key_elements": [
                "major_locations", "climate", "landmarks"
            ],
            "template": """
            {
                "elements": {
                    "major_locations": {
                        "description": "Description of the major locations (cities, countries, planets, etc.)",
                        "relevance": "How these locations impact the story"
                    },
                    "climate": {
                        "description": "Description of the climate and weather patterns",
                        "relevance": "How the climate affects the story and characters"
                    },
                    "landmarks": {
                        "description": "Description of notable landmarks",
                        "relevance": "Significance of these landmarks to the world and story"
                    }
                },
                "summary": "A brief summary of the geographic elements"
            }
            """
        },
        {
            "name": "HISTORY",
            "description": "Historical elements of the world",
            "key_elements": [
                "timeline", "figures", "conflicts"
            ],
            "template": """
            {
                "elements": {
                    "timeline": {
                        "description": "Key historical events in chronological order",
                        "relevance": "How these events shaped the current world"
                    },
                    "figures": {
                        "description": "Important historical figures",
                        "relevance": "Their impact on the world and story"
                    },
                    "conflicts": {
                        "description": "Major historical conflicts",
                        "relevance": "How these conflicts affect the current situation"
                    }
                },
                "summary": "A brief summary of the historical elements"
            }
            """
        },
        {
            "name": "CULTURE",
            "description": "Cultural elements of the world",
            "key_elements": [
                "languages", "traditions", "values"
            ],
            "template": """
            {
                "elements": {
                    "languages": {
                        "description": "Languages and communication methods",
                        "relevance": "How language affects interactions in the story"
                    },
                    "traditions": {
                        "description": "Important traditions and customs",
                        "relevance": "How these traditions impact characters and plot"
                    },
                    "values": {
                        "description": "Cultural values and taboos",
                        "relevance": "How these values create conflict or harmony"
                    }
                },
                "summary": "A brief summary of the cultural elements"
            }
            """
        },
        {
            "name": "POLITICS",
            "description": "Political elements of the world",
            "key_elements": [
                "government", "factions", "laws"
            ],
            "template": """
            {
                "elements": {
                    "government": {
                        "description": "Government systems and power structures",
                        "relevance": "How the government affects the story"
                    },
                    "factions": {
                        "description": "Political factions and their relationships",
                        "relevance": "How factions create tension or alliances"
                    },
                    "laws": {
                        "description": "Important laws and justice systems",
                        "relevance": "How laws constrain or enable characters"
                    }
                },
                "summary": "A brief summary of the political elements"
            }
            """
        },
        {
            "name": "ECONOMICS",
            "description": "Economic elements of the world",
            "key_elements": [
                "resources", "trade", "classes"
            ],
            "template": """
            {
                "elements": {
                    "resources": {
                        "description": "Key resources and their distribution",
                        "relevance": "How resources drive conflict or cooperation"
                    },
                    "trade": {
                        "description": "Trade systems and currencies",
                        "relevance": "How trade affects different regions and people"
                    },
                    "classes": {
                        "description": "Economic classes and inequality",
                        "relevance": "How class differences impact characters"
                    }
                },
                "summary": "A brief summary of the economic elements"
            }
            """
        },
        {
            "name": "TECHNOLOGY_MAGIC",
            "description": "Technology or magic elements of the world",
            "key_elements": [
                "systems", "limitations", "impact"
            ],
            "template": """
            {
                "elements": {
                    "systems": {
                        "description": "Available technologies or magic systems",
                        "relevance": "How these systems are used in the story"
                    },
                    "limitations": {
                        "description": "Limitations and costs of technology/magic",
                        "relevance": "How these limitations create challenges"
                    },
                    "impact": {
                        "description": "Impact on society and daily life",
                        "relevance": "How technology/magic shapes the world"
                    }
                },
                "summary": "A brief summary of the technology/magic elements"
            }
            """
        },
        {
            "name": "RELIGION",
            "description": "Religious elements of the world",
            "key_elements": [
                "beliefs", "practices", "organizations"
            ],
            "template": """
            {
                "elements": {
                    "beliefs": {
                        "description": "Belief systems and deities",
                        "relevance": "How beliefs influence characters and society"
                    },
                    "practices": {
                        "description": "Religious practices and rituals",
                        "relevance": "How practices manifest in daily life"
                    },
                    "organizations": {
                        "description": "Religious organizations and leaders",
                        "relevance": "How religious power structures affect the world"
                    }
                },
                "summary": "A brief summary of the religious elements"
            }
            """
        },
        {
            "name": "DAILY_LIFE",
            "description": "Daily life elements of the world",
            "key_elements": [
                "food", "clothing", "housing"
            ],
            "template": """
            {
                "elements": {
                    "food": {
                        "description": "Food and cuisine",
                        "relevance": "How food reflects culture and status"
                    },
                    "clothing": {
                        "description": "Clothing and fashion",
                        "relevance": "How clothing indicates identity and role"
                    },
                    "housing": {
                        "description": "Housing and architecture",
                        "relevance": "How living spaces reflect society"
                    }
                },
                "summary": "A brief summary of the daily life elements"
            }
            """
        }
    ]
    
    # Initialize world elements dictionary
    world_elements = {}
    
    # Generate each category incrementally
    for category in categories:
        category_name = category["name"]
        print(f"Generating {category_name} elements...")
        
        # Create a prompt for this specific category
        category_prompt = f"""
        Generate {category_name} elements for a {genre} story with a {tone} tone,
        written in the style of {author}, based on this initial idea:
        
        {initial_idea}
        
        And this story outline:
        
        {global_story[:500]}...
        
        {language_guidance}
        
        Focus ONLY on {category_name} elements, including:
        {', '.join(category["key_elements"])}
        
        Use EXACTLY this JSON template structure, replacing the placeholders with your content:
        
        {category["template"]}
        
        Ensure the elements are:
        - Consistent with the {genre} genre conventions
        - Appropriate for the {tone} tone
        - Aligned with {author}'s style
        - Directly relevant to the initial story idea
        - Detailed enough to support rich storytelling
        """
        
        try:
            # Try to generate with structured output first
            structured_llm = llm.with_structured_output(SimplifiedCategory)
            category_elements = structured_llm.invoke(category_prompt)
            category_data = category_elements.model_dump()
        except Exception as e:
            print(f"Error generating structured {category_name} elements: {str(e)}")
            
            # Fall back to template-based parsing
            try:
                # Generate with template
                response = llm.invoke([HumanMessage(content=category_prompt)]).content
                
                # Parse the response into structured data
                category_data = parse_json_with_langchain(response, f"{category_name} elements")
                
                # Ensure we have a valid dictionary with expected structure
                if not isinstance(category_data, dict) or "elements" not in category_data:
                    # Create minimal structure from template
                    category_data = parse_json_with_langchain(category["template"], f"{category_name} elements")
                    category_data["summary"] = f"Failed to generate {category_name} elements properly"
            except Exception as e2:
                print(f"Fallback parsing also failed for {category_name}: {str(e2)}")
                # Create minimal structure
                category_data = {
                    "elements": {element: {"description": f"Default {element}", "relevance": ""} for element in category["key_elements"]},
                    "summary": f"Failed to generate {category_name} elements: {str(e)}, {str(e2)}"
                }
        
        # Add to world elements
        world_elements[category_name] = category_data
    
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
    
    # Create a simplified world elements representation for mystery generation
    simplified_world = {}
    for category_name, category_data in world_elements.items():
        # Extract just the summaries and key descriptions to reduce complexity
        simplified_world[category_name] = {
            "summary": category_data.get("summary", ""),
            "elements": {k: v.get("description", "") for k, v in category_data.get("elements", {}).items()}
        }
    
    # Identify potential mystery elements from the simplified world elements
    mystery_prompt = f"""
    Analyze these world elements and identify key mystery elements that should be gradually revealed:
    
    {simplified_world}
    
    Identify 3 elements that would work well as mysteries in the story. For each mystery:
    1. Provide the name of the mystery element
    2. Explain why it would make a compelling mystery
    3. Suggest 3 clues that could gradually reveal this mystery
    
    Format your response as a structured JSON object with "key_mysteries" as a list of objects.
    Each mystery should have a "name", "description", and "clues" (a list of objects with "description",
    "revelation_level" (1-5), and "revealed" (false)).
    """
    
    try:
        # Create a structured LLM that outputs a MysteryAnalysis
        structured_llm = llm.with_structured_output(MysteryAnalysis)
        
        # Use the structured LLM to identify mystery elements
        mystery_analysis = structured_llm.invoke(mystery_prompt)
        
        # Update the world state tracker with the identified mysteries
        world_state_tracker["mystery_elements"]["key_mysteries"] = [
            mystery.model_dump() for mystery in mystery_analysis.key_mysteries
        ]
    except Exception as e:
        print(f"Error identifying mystery elements: {str(e)}")
        # Create basic mystery elements as fallback
        world_state_tracker["mystery_elements"]["key_mysteries"] = [
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
    
    # Store the world state tracker in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": "world_state_tracker",
        "value": world_state_tracker,
        "namespace": MEMORY_NAMESPACE
    })
    
    # Extract category summaries for the world summary
    category_summaries = []
    for category in categories:
        category_name = category["name"]
        if category_name in world_elements and "summary" in world_elements[category_name]:
            category_summaries.append(f"**{category_name}**: {world_elements[category_name]['summary']}")
    
    # Generate a summary of the world for quick reference
    world_summary_prompt = f"""
    Based on these world elements:
    
    {'\n\n'.join(category_summaries)}
    
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


def extract_structured_worldbuilding(text: str) -> Dict[str, Any]:
    """
    Extract structured worldbuilding data from text using Pydantic models.
    
    This function takes unstructured text containing worldbuilding information
    and extracts it into a structured format using the WorldElements Pydantic model.
    If the structured extraction fails, it falls back to the parse_json_with_langchain method.
    
    Args:
        text: Text containing worldbuilding information
        
    Returns:
        Dictionary containing structured worldbuilding elements
    """
    try:
        # Try to extract structured data using Pydantic
        structured_llm = llm.with_structured_output(WorldElements)
        
        prompt = f"""
        Extract structured worldbuilding elements from this text:
        
        {text}
        
        Format the data according to the specified schema with these categories:
        - GEOGRAPHY (major_locations, physical_features, climate, landmarks, spatial_relationships)
        - HISTORY (timeline, historical_figures, past_conflicts, origin_stories, historical_trends)
        - CULTURE (languages, arts, traditions, values, diversity)
        - POLITICS (government, factions, laws, military, international_relations)
        - ECONOMICS (resources, trade, classes, industries, challenges)
        - TECHNOLOGY/MAGIC (systems, limitations, impact, rare_elements, acquisition)
        - RELIGION (belief_systems, practices, organizations, role, conflicts)
        - DAILY_LIFE (food, clothing, housing, family, education)
        """
        
        # Extract structured data
        world_elements_model = structured_llm.invoke(prompt)
        
        # Convert to dictionary
        return world_elements_model.model_dump(by_alias=True)
    except Exception as e:
        print(f"Error extracting structured worldbuilding data: {str(e)}")
        
        # Fall back to parse_json_with_langchain
        try:
            return parse_json_with_langchain(text, "world elements")
        except Exception as e2:
            print(f"Fallback parsing also failed: {str(e2)}")
            return {
                "GEOGRAPHY": {"major_locations": "Failed to extract structured data"},
                "error": f"Failed to extract structured worldbuilding data: {str(e)}, {str(e2)}"
            }


def extract_specific_worldbuilding_element(text: str, element_type: str) -> Dict[str, Any]:
    """
    Extract a specific type of worldbuilding element from text using Pydantic models.
    
    This function extracts a specific category of worldbuilding elements (e.g., geography,
    history, culture) from text using the appropriate Pydantic model.
    
    Args:
        text: Text containing worldbuilding information
        element_type: Type of element to extract (e.g., "geography", "history", "culture")
        
    Returns:
        Dictionary containing the structured element data
    """
    # Map element types to their corresponding Pydantic models
    element_models = {
        "geography": GeographyElement,
        "history": HistoryElement,
        "culture": CultureElement,
        "politics": PoliticsElement,
        "economics": EconomicsElement,
        "technology": TechnologyMagicElement,
        "magic": TechnologyMagicElement,
        "religion": ReligionElement,
        "daily_life": DailyLifeElement
    }
    
    # Normalize the element type
    element_type_lower = element_type.lower()
    
    # Get the appropriate model
    model = element_models.get(element_type_lower)
    if not model:
        raise ValueError(f"Unknown element type: {element_type}. Valid types are: {', '.join(element_models.keys())}")
    
    try:
        # Create a structured LLM with the appropriate model
        structured_llm = llm.with_structured_output(model)
        
        # Create a prompt for extracting the specific element
        prompt = f"""
        Extract structured {element_type} information from this text:
        
        {text}
        
        Focus only on the {element_type} elements and ignore other aspects of worldbuilding.
        """
        
        # Extract the structured data
        element_model = structured_llm.invoke(prompt)
        
        # Convert to dictionary
        return element_model.model_dump()
    except Exception as e:
        print(f"Error extracting {element_type} data: {str(e)}")
        return {"error": f"Failed to extract {element_type} data: {str(e)}"}


def extract_mystery_elements(text: str, num_mysteries: int = 3) -> Dict[str, Any]:
    """
    Extract potential mystery elements from text using the MysteryAnalysis Pydantic model.
    
    This function analyzes text to identify elements that would work well as mysteries
    in a story, along with potential clues for revealing those mysteries.
    
    Args:
        text: Text to analyze for potential mysteries
        num_mysteries: Number of mysteries to identify (default: 3)
        
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