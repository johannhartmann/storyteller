"""
StoryCraft Agent - Creative tools and utilities.
"""

from typing import Dict, List, Any, Optional, Union, Type, TypeVar
import json

from storyteller_lib.core.config import (
    llm,
    MEMORY_NAMESPACE,
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
)
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field, create_model
from storyteller_lib.core.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


# Pydantic models for structured creative brainstorming
class CreativeBrainstormResultFlat(BaseModel):
    """Flattened result of creative brainstorming to avoid nested dictionaries."""

    ideas_titles: str = Field(
        description="Pipe-separated list of clear, concise titles for ideas"
    )
    ideas_descriptions: str = Field(
        description="Pipe-separated list of detailed descriptions (2-3 sentences each)"
    )
    ideas_enhancement_values: str = Field(
        description="Pipe-separated list of how each idea enhances the story"
    )
    ideas_challenges: str = Field(
        description="Pipe-separated list of potential challenges for each idea"
    )
    ideas_fit_scores: str = Field(
        description="Comma-separated list of fit scores (1-10) for each idea"
    )
    recommended_title: str = Field(description="Title of the best idea to use")
    recommended_description: str = Field(description="Description of the best idea")
    recommended_enhancement_value: str = Field(
        description="How the recommended idea enhances the story"
    )
    recommended_challenges: str = Field(
        description="Challenges for the recommended idea"
    )
    recommended_fit_score: int = Field(
        ge=1, le=10, description="Fit score for the recommended idea"
    )
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
    strict_adherence: bool = True,
    scene_specifications: Optional[Dict[str, Any]] = None,
    chapter_outline: Optional[str] = None,
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
        scene_specifications: Optional scene-specific requirements and constraints
        chapter_outline: Optional chapter outline for context

    Returns:
        Dictionary with generated ideas and evaluations
    """
    if evaluation_criteria is None:
        evaluation_criteria = [
            "Enhancement of the existing storyline",
            "Coherence with the established narrative",
            "Contribution to character development or plot advancement",
            "Reader engagement and emotional impact",
            "Seamless integration with the story world",
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
    from storyteller_lib.prompts.renderer import render_prompt

    # Extract the idea context if available
    idea_context = ""
    if context:
        # The context IS the idea - it's passed directly from initialization.py
        idea_context = context.strip()

    # Render the brainstorming prompt
    # Use special template for generating initial story premises
    if topic == "Unique Story Premises":
        brainstorm_prompt = render_prompt(
            "unique_story_premises",
            language=language,
            genre=genre,
            tone=tone,
            num_ideas=num_ideas,
            author=author,
            author_style_guidance=author_style_guidance,
        )
    else:
        brainstorm_prompt = render_prompt(
            "creative_brainstorm",
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
            author_style_guidance=author_style_guidance,
            scene_specifications=scene_specifications,
            chapter_outline=chapter_outline,
        )

    # Author style will be handled in the template if needed

    # Generate ideas using structured output only
    # Use structured output for brainstorming
    structured_llm = llm.with_structured_output(CreativeBrainstormResultFlat)
    brainstorm_result = structured_llm.invoke(brainstorm_prompt)

    # Extract the recommended idea
    recommended_ideas = f"{brainstorm_result.recommended_title}: {brainstorm_result.recommended_description} (Score: {brainstorm_result.recommended_fit_score}/10)"

    # Parse the flattened lists
    titles = [t.strip() for t in brainstorm_result.ideas_titles.split("|")]
    descriptions = [d.strip() for d in brainstorm_result.ideas_descriptions.split("|")]
    enhancements = [
        e.strip() for e in brainstorm_result.ideas_enhancement_values.split("|")
    ]
    challenges = [c.strip() for c in brainstorm_result.ideas_challenges.split("|")]
    scores = [int(s.strip()) for s in brainstorm_result.ideas_fit_scores.split(",")]

    # Format all ideas for display
    ideas_entries = []
    for i, (title, desc, enhance, challenge, score) in enumerate(
        zip(titles, descriptions, enhancements, challenges, scores)
    ):
        ideas_entries.append(
            f"{i+1}. {title}\n   {desc}\n   Enhancement: {enhance}\n   Challenges: {challenge}\n   Fit Score: {score}/10"
        )
    ideas_response = "\n\n".join(ideas_entries)

    # Include rationale
    evaluation = f"Recommendation: {brainstorm_result.rationale}"

    # Brainstorming results are temporary and returned directly
    # No need to store in memory/database
    return {
        "ideas": ideas_response,
        "evaluation": evaluation,
        "recommended_ideas": recommended_ideas,
    }


def create_pydantic_model_from_dict(
    schema_dict: Dict, model_name: str = "DynamicModel"
) -> Type[BaseModel]:
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
            field_definitions[field_name] = (
                field_type,
                Field(description=f"List of {field_name}"),
            )
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
    language: str = DEFAULT_LANGUAGE,
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
        from storyteller_lib.prompts.renderer import render_prompt

        # Invoke with the text content
        prompt = render_prompt(
            "structured_extraction",
            language=language,
            description=description,
            text_content=text_content,
        )

        result = structured_output_llm.invoke(prompt)
        return result.dict()
    except Exception as e:
        print(f"Structured output parsing failed: {str(e)}")
        return {}


# Pydantic models for world elements
class GeographyElements(BaseModel):
    """Geography category elements."""

    major_locations: Optional[str] = Field(
        None, description="Major locations in the world"
    )
    physical_features: Optional[str] = Field(
        None, description="Physical features and terrain"
    )
    climate_weather: Optional[str] = Field(
        None, description="Climate and weather patterns"
    )
    additional_info: Optional[str] = Field(
        None, description="Any other geography-related information"
    )


class HistoryElements(BaseModel):
    """History category elements."""

    timeline: Optional[str] = Field(None, description="Historical timeline")
    past_conflicts: Optional[str] = Field(None, description="Past conflicts and wars")
    important_events: Optional[str] = Field(
        None, description="Important historical events"
    )
    additional_info: Optional[str] = Field(
        None, description="Any other history-related information"
    )


class CultureElements(BaseModel):
    """Culture category elements."""

    customs: Optional[str] = Field(None, description="Cultural customs and traditions")
    values: Optional[str] = Field(None, description="Cultural values and beliefs")
    arts: Optional[str] = Field(None, description="Arts and entertainment")
    additional_info: Optional[str] = Field(
        None, description="Any other culture-related information"
    )


class PoliticsElements(BaseModel):
    """Politics category elements."""

    government: Optional[str] = Field(None, description="Government structure")
    laws: Optional[str] = Field(None, description="Legal system and laws")
    factions: Optional[str] = Field(None, description="Political factions and parties")
    additional_info: Optional[str] = Field(
        None, description="Any other politics-related information"
    )


class EconomicsElements(BaseModel):
    """Economics category elements."""

    currency: Optional[str] = Field(None, description="Currency and monetary system")
    trade: Optional[str] = Field(None, description="Trade and commerce")
    resources: Optional[str] = Field(None, description="Natural resources")
    additional_info: Optional[str] = Field(
        None, description="Any other economics-related information"
    )


class TechnologyMagicElements(BaseModel):
    """Technology/Magic category elements."""

    level: Optional[str] = Field(None, description="Technology or magic level")
    systems: Optional[str] = Field(None, description="Technology or magic systems")
    limitations: Optional[str] = Field(None, description="Limitations and constraints")
    additional_info: Optional[str] = Field(
        None, description="Any other technology/magic-related information"
    )


class ReligionElements(BaseModel):
    """Religion category elements."""

    deities: Optional[str] = Field(None, description="Deities and divine beings")
    practices: Optional[str] = Field(
        None, description="Religious practices and rituals"
    )
    beliefs: Optional[str] = Field(None, description="Core religious beliefs")
    additional_info: Optional[str] = Field(
        None, description="Any other religion-related information"
    )


class DailyLifeElements(BaseModel):
    """Daily life category elements."""

    food: Optional[str] = Field(None, description="Food and cuisine")
    clothing: Optional[str] = Field(None, description="Clothing and fashion")
    housing: Optional[str] = Field(None, description="Housing and architecture")
    additional_info: Optional[str] = Field(
        None, description="Any other daily life information"
    )


class WorldElements(BaseModel):
    """Complete world elements structure."""

    GEOGRAPHY: Optional[GeographyElements] = Field(
        None, description="Geography elements"
    )
    HISTORY: Optional[HistoryElements] = Field(None, description="History elements")
    CULTURE: Optional[CultureElements] = Field(None, description="Culture elements")
    POLITICS: Optional[PoliticsElements] = Field(None, description="Politics elements")
    ECONOMICS: Optional[EconomicsElements] = Field(
        None, description="Economics elements"
    )
    TECHNOLOGY_MAGIC: Optional[TechnologyMagicElements] = Field(
        None, alias="TECHNOLOGY/MAGIC", description="Technology or magic elements"
    )
    RELIGION: Optional[ReligionElements] = Field(None, description="Religion elements")
    DAILY_LIFE: Optional[DailyLifeElements] = Field(
        None, description="Daily life elements"
    )


def generate_structured_json(
    text_content: str, schema: str, description: str
) -> Dict[str, Any]:
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
        if isinstance(schema, str) and (
            schema.startswith("{") and schema.endswith("}")
        ):
            # If schema is a JSON string, parse it
            schema_dict = json.loads(schema)

            # Try structured output with Pydantic approach first
            if schema_dict:
                result = structured_output_with_pydantic(
                    text_content, schema_dict, description
                )
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
        partial_variables={
            "format_instructions": json_parser.get_format_instructions()
        },
    )

    # Create the LangChain chain
    chain = prompt | llm | json_parser

    try:
        # Execute the chain with our input parameters
        parsed_json = chain.invoke(
            {"text_content": text_content, "description": description, "schema": schema}
        )
        return parsed_json
    except Exception as e:
        print(f"LangChain JSON parser failed for {description}. Error: {str(e)}")

        # If first attempt fails, try again with simpler instructions
        print(
            f"Failed to generate valid JSON for {description}. Trying again with simplified approach."
        )

        # Create a simplified prompt template
        simplified_prompt = PromptTemplate(
            template="""Convert this information about {description} into valid JSON.

{text_content}

Use this exact schema:
{schema}

{format_instructions}

The output should be a JSON object without any additional text or comments.""",
            input_variables=["text_content", "description", "schema"],
            partial_variables={
                "format_instructions": json_parser.get_format_instructions()
            },
        )

        # Create a new chain with the simplified prompt
        simplified_chain = simplified_prompt | llm | json_parser

        try:
            # Execute the simplified chain
            parsed_json = simplified_chain.invoke(
                {
                    "text_content": text_content,
                    "description": description,
                    "schema": schema,
                }
            )
            return parsed_json
        except Exception as e:
            print(
                f"Second attempt to generate JSON for {description} also failed. Error: {str(e)}"
            )

            # If all LangChain approaches fail, return empty dictionary
            return {}
