"""
StoryCraft Agent - Creative tools and utilities.
"""

from typing import Dict, List, Any, Optional, Union, Type, TypeVar
import json

from storyteller_lib.config import llm, manage_memory_tool, MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field, create_model

T = TypeVar('T', bound=BaseModel)


# Pydantic models for structured creative brainstorming
class CreativeIdea(BaseModel):
    """A single creative idea."""
    title: str = Field(description="Clear, concise title for the idea")
    description: str = Field(description="Detailed description (2-3 sentences)")
    enhancement_value: str = Field(description="How this enhances the story")
    challenges: str = Field(description="Potential challenges or considerations")
    fit_score: int = Field(ge=1, le=10, description="How well it fits the context (1-10)")


class CreativeBrainstormResult(BaseModel):
    """Result of creative brainstorming."""
    ideas: List[CreativeIdea] = Field(description="List of creative ideas")
    recommended_idea: CreativeIdea = Field(description="The best idea to use")
    rationale: str = Field(description="Why this idea is recommended")


def creative_brainstorm(
    topic: str,
    genre: str,
    tone: str,
    context: str,
    author: str = "",
    author_style_guidance: str = "",
    language: str = DEFAULT_LANGUAGE,
    num_ideas: int = 5,
    evaluation_criteria: List[str] = None,
    constraints: Dict[str, str] = None,
    strict_adherence: bool = True
) -> Dict:
    """
    Generate and evaluate multiple creative ideas for a given story element.
    
    Args:
        topic: What to brainstorm about (e.g., "plot twist", "character backstory", "magical system")
        genre: Story genre
        tone: Story tone
        context: Current story context
        author: Optional author style to emulate
        author_style_guidance: Optional guidance on author's style
        language: Target language for story generation
        num_ideas: Number of ideas to generate
        evaluation_criteria: List of criteria to evaluate ideas against
        constraints: Dictionary of specific constraints to enforce (e.g., setting, characters)
        
    Returns:
        Dictionary with generated ideas and evaluations
    """
    if evaluation_criteria is None:
        evaluation_criteria = [
            "Enhancement of the existing storyline",
            "Coherence with the established narrative",
            "Contribution to character development or plot advancement",
            "Reader engagement and emotional impact",
            "Seamless integration with the story world"
        ]
    
    # Default constraints if none provided
    if constraints is None:
        constraints = {}
    
    # Extract key constraints for emphasis
    setting_constraint = constraints.get("setting", "")
    character_constraints = constraints.get("characters", "")
    plot_constraints = constraints.get("plot", "")
    
    # All constraint handling and language instructions are now in the templates
    
    # Use template system for brainstorming
    from storyteller_lib.prompt_templates import render_prompt
    
    # Extract the idea context if available
    idea_context = ""
    if context:
        # Extract just the idea-specific part if it exists
        if "Initial idea:" in context:
            idea_context = context.split("Initial idea:")[1].strip()
        elif idea_context == "":
            # If no initial idea marker, check for other context
            lines = context.strip().split('\n')
            for line in lines:
                if line.strip() and not line.strip().startswith("We're creating"):
                    idea_context = line.strip()
                    break
    
    # Render the brainstorming prompt
    brainstorm_prompt = render_prompt(
        'creative_brainstorm',
        language=language,
        topic=topic,
        genre=genre,
        tone=tone,
        idea_context=idea_context,
        setting_constraint=setting_constraint,
        character_constraints=character_constraints,
        plot_constraints=plot_constraints,
        num_ideas=num_ideas,
        author=author,
        author_style_guidance=author_style_guidance
    )
    
    # Author style will be handled in the template if needed
    
    # Generate ideas
    ideas_response = llm.invoke([HumanMessage(content=brainstorm_prompt)]).content
    
    # Use template system
    from storyteller_lib.prompt_templates import render_prompt
    
    # Evaluation prompt - let template handle all the text
    eval_prompt = render_prompt(
        'creative_evaluation',
        language=language,
        topic=topic,
        ideas_response=ideas_response,
        idea_context=idea_context,
        setting_constraint=setting_constraint,
        character_constraints=character_constraints,
        plot_constraints=plot_constraints,
        genre=genre,
        tone=tone,
        strict_adherence=strict_adherence
    )
    
    # Evaluate ideas
    evaluation = llm.invoke([HumanMessage(content=eval_prompt)]).content
    
    # Store brainstorming results in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"brainstorm_{topic.lower().replace(' ', '_')}",
        "value": {
            "ideas": ideas_response,
            "evaluation": evaluation,
            "timestamp": "now",
            "topic": topic
        },
        "namespace": MEMORY_NAMESPACE
    })
    # Return results
    # Extract recommended ideas from evaluation, with fallback to the best idea from ideas_response
    recommended_ideas = None
    if "recommend" in evaluation.lower():
        recommended_ideas = evaluation.split("recommend")[-1].strip()
    else:
        # Try to extract the first idea as a fallback
        idea_sections = ideas_response.split("\n\n")
        for section in idea_sections:
            if section.strip().startswith("1.") or section.strip().startswith("1)") or "Idea 1:" in section:
                recommended_ideas = section.strip()
                break
        
        # If still no recommended ideas, use the first paragraph of the evaluation
        if not recommended_ideas and evaluation:
            recommended_ideas = evaluation.split("\n\n")[0] if "\n\n" in evaluation else evaluation
    
    # Ensure we always have some content
    if not recommended_ideas:
        recommended_ideas = f"Best idea for {topic}: " + (ideas_response.split("\n")[0] if "\n" in ideas_response else ideas_response[:100])
    
    return {
        "ideas": ideas_response,
        "evaluation": evaluation,
        "recommended_ideas": recommended_ideas
    }

def create_pydantic_model_from_dict(schema_dict: Dict, model_name: str = "DynamicModel") -> Type[BaseModel]:
    """
    Create a Pydantic model from a dictionary schema description.
    
    Args:
        schema_dict: Dictionary of field names to field types and descriptions
        model_name: Name for the generated model class
        
    Returns:
        A Pydantic model class
    """
    field_definitions = {}
    
    # Convert the schema description to Field objects
    for field_name, field_info in schema_dict.items():
        if isinstance(field_info, dict):
            # For nested objects
            field_type = Dict[str, Any]
            field_desc = field_info.get("description", "")
            field_definitions[field_name] = (field_type, Field(description=field_desc))
        elif isinstance(field_info, list):
            # For array fields
            field_type = List[str]
            field_definitions[field_name] = (field_type, Field(description=f"List of {field_name}"))
        else:
            # For simple types
            field_type = str
            field_definitions[field_name] = (field_type, Field(description=field_info))
    
    # Create and return the model
    return create_model(model_name, **field_definitions)

def structured_output_with_pydantic(
    text_content: str, 
    schema_dict: Dict,
    description: str,
    model_name: str = "DynamicModel",
    language: str = DEFAULT_LANGUAGE
) -> Dict[str, Any]:
    """
    Parse structured data from text using LangChain's structured output approach.
    
    Args:
        text_content: Text to parse into structured data
        schema_dict: Dictionary describing the schema
        description: Description of what we're parsing
        model_name: Name for the dynamic Pydantic model
        
    Returns:
        Structured data as a dictionary
    """
    try:
        # Create a Pydantic model from the schema dictionary
        model_class = create_pydantic_model_from_dict(schema_dict, model_name)
        
        # Use structured output with the model
        structured_output_llm = llm.with_structured_output(model_class)
        
        # Use template system
        from storyteller_lib.prompt_templates import render_prompt
        
        # Invoke with the text content
        prompt = render_prompt(
            'structured_extraction',
            language=language,
            description=description,
            text_content=text_content
        )
        
        result = structured_output_llm.invoke(prompt)
        return result.dict()
    except Exception as e:
        print(f"Structured output parsing failed: {str(e)}")
        return {}

# Pydantic models for world elements
class GeographyElements(BaseModel):
    """Geography category elements."""
    major_locations: Optional[str] = Field(None, description="Major locations in the world")
    physical_features: Optional[str] = Field(None, description="Physical features and terrain")
    climate_weather: Optional[str] = Field(None, description="Climate and weather patterns")
    additional_info: Optional[str] = Field(None, description="Any other geography-related information")

class HistoryElements(BaseModel):
    """History category elements."""
    timeline: Optional[str] = Field(None, description="Historical timeline")
    past_conflicts: Optional[str] = Field(None, description="Past conflicts and wars")
    important_events: Optional[str] = Field(None, description="Important historical events")
    additional_info: Optional[str] = Field(None, description="Any other history-related information")

class CultureElements(BaseModel):
    """Culture category elements."""
    customs: Optional[str] = Field(None, description="Cultural customs and traditions")
    values: Optional[str] = Field(None, description="Cultural values and beliefs")
    arts: Optional[str] = Field(None, description="Arts and entertainment")
    additional_info: Optional[str] = Field(None, description="Any other culture-related information")

class PoliticsElements(BaseModel):
    """Politics category elements."""
    government: Optional[str] = Field(None, description="Government structure")
    laws: Optional[str] = Field(None, description="Legal system and laws")
    factions: Optional[str] = Field(None, description="Political factions and parties")
    additional_info: Optional[str] = Field(None, description="Any other politics-related information")

class EconomicsElements(BaseModel):
    """Economics category elements."""
    currency: Optional[str] = Field(None, description="Currency and monetary system")
    trade: Optional[str] = Field(None, description="Trade and commerce")
    resources: Optional[str] = Field(None, description="Natural resources")
    additional_info: Optional[str] = Field(None, description="Any other economics-related information")

class TechnologyMagicElements(BaseModel):
    """Technology/Magic category elements."""
    level: Optional[str] = Field(None, description="Technology or magic level")
    systems: Optional[str] = Field(None, description="Technology or magic systems")
    limitations: Optional[str] = Field(None, description="Limitations and constraints")
    additional_info: Optional[str] = Field(None, description="Any other technology/magic-related information")

class ReligionElements(BaseModel):
    """Religion category elements."""
    deities: Optional[str] = Field(None, description="Deities and divine beings")
    practices: Optional[str] = Field(None, description="Religious practices and rituals")
    beliefs: Optional[str] = Field(None, description="Core religious beliefs")
    additional_info: Optional[str] = Field(None, description="Any other religion-related information")

class DailyLifeElements(BaseModel):
    """Daily life category elements."""
    food: Optional[str] = Field(None, description="Food and cuisine")
    clothing: Optional[str] = Field(None, description="Clothing and fashion")
    housing: Optional[str] = Field(None, description="Housing and architecture")
    additional_info: Optional[str] = Field(None, description="Any other daily life information")

class WorldElements(BaseModel):
    """Complete world elements structure."""
    GEOGRAPHY: Optional[GeographyElements] = Field(None, description="Geography elements")
    HISTORY: Optional[HistoryElements] = Field(None, description="History elements")
    CULTURE: Optional[CultureElements] = Field(None, description="Culture elements")
    POLITICS: Optional[PoliticsElements] = Field(None, description="Politics elements")
    ECONOMICS: Optional[EconomicsElements] = Field(None, description="Economics elements")
    TECHNOLOGY_MAGIC: Optional[TechnologyMagicElements] = Field(None, alias="TECHNOLOGY/MAGIC", description="Technology or magic elements")
    RELIGION: Optional[ReligionElements] = Field(None, description="Religion elements")
    DAILY_LIFE: Optional[DailyLifeElements] = Field(None, description="Daily life elements")

def parse_json_with_langchain(text: str, description: str = "world elements", language: str = DEFAULT_LANGUAGE) -> Dict[str, Any]:
    """
    Parse world elements from text using structured output.
    
    Args:
        text: Text containing world elements to parse
        description: Description of what we're parsing (for error messages)
        
    Returns:
        Parsed world elements as a dictionary
    """
    from storyteller_lib.config import get_llm_with_structured_output
    
    # Use structured output to parse the world elements
    try:
        # Use template system
        from storyteller_lib.prompt_templates import render_prompt
        
        prompt = render_prompt(
            'world_extraction',
            language=language,
            text=text
        )
        
        structured_llm = get_llm_with_structured_output(WorldElements)
        response = structured_llm.invoke(prompt)
        
        if isinstance(response, WorldElements):
            # Convert to dict and handle the TECHNOLOGY/MAGIC key
            result = response.dict(by_alias=True, exclude_none=True)
            # Ensure we have the expected structure
            return result
        else:
            print(f"Unexpected response type: {type(response)}")
            return _get_default_world_structure()
    except Exception as e:
        print(f"Structured output parsing failed: {str(e)}")
        return _get_default_world_structure()

def _get_default_world_structure() -> Dict[str, Any]:
    """Return a default world structure."""
    return {
        "GEOGRAPHY": {},
        "HISTORY": {},
        "CULTURE": {},
        "POLITICS": {},
        "ECONOMICS": {},
        "TECHNOLOGY/MAGIC": {},
        "RELIGION": {},
        "DAILY_LIFE": {}
    }

def generate_structured_json(text_content: str, schema: str, description: str) -> Dict[str, Any]:
    """
    Generate structured JSON from unstructured text using LangChain's approach.
    
    Args:
        text_content: The unstructured text to parse into JSON
        schema: A description of the JSON schema to generate (as string)
        description: A brief description of what we're trying to structure
        
    Returns:
        A parsed JSON object matching the requested schema
    """
    # Try to parse the schema string into a dictionary
    schema_dict = {}
    try:
        if isinstance(schema, str) and (schema.startswith('{') and schema.endswith('}')):
            # If schema is a JSON string, parse it
            schema_dict = json.loads(schema)
            
            # Try structured output with Pydantic approach first
            if schema_dict:
                result = structured_output_with_pydantic(text_content, schema_dict, description)
                if result:
                    return result
    except Exception:
        # If schema parsing fails, continue with the standard approach
        pass
    
    # Fall back to JsonOutputParser approach
    json_parser = JsonOutputParser()
    
    # Create a prompt template
    prompt = PromptTemplate(
        template="""Based on this {description}:

{text_content}

Convert this information into a properly formatted JSON object with this structure:
{schema}

{format_instructions}""",
        input_variables=["text_content", "description", "schema"],
        partial_variables={"format_instructions": json_parser.get_format_instructions()}
    )
    
    # Create the LangChain chain
    chain = prompt | llm | json_parser
    
    try:
        # Execute the chain with our input parameters
        parsed_json = chain.invoke({
            "text_content": text_content,
            "description": description,
            "schema": schema
        })
        return parsed_json
    except Exception as e:
        print(f"LangChain JSON parser failed for {description}. Error: {str(e)}")
        
        # If first attempt fails, try again with simpler instructions
        print(f"Failed to generate valid JSON for {description}. Trying again with simplified approach.")
        
        # Create a simplified prompt template
        simplified_prompt = PromptTemplate(
            template="""Convert this information about {description} into valid JSON.

{text_content}

Use this exact schema:
{schema}

{format_instructions}

The output should be a JSON object without any additional text or comments.""",
            input_variables=["text_content", "description", "schema"],
            partial_variables={"format_instructions": json_parser.get_format_instructions()}
        )
        
        # Create a new chain with the simplified prompt
        simplified_chain = simplified_prompt | llm | json_parser
        
        try:
            # Execute the simplified chain
            parsed_json = simplified_chain.invoke({
                "text_content": text_content,
                "description": description,
                "schema": schema
            })
            return parsed_json
        except Exception as e:
            print(f"Second attempt to generate JSON for {description} also failed. Error: {str(e)}")
            
            # If all LangChain approaches fail, return empty dictionary
            return {}