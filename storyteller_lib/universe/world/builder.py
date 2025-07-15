"""
StoryCraft Agent - Worldbuilding node for generating detailed world elements.

This module provides functions for generating rich worldbuilding elements
based on the story parameters (genre, tone, author style, and initial idea).
It uses Pydantic models for structured data extraction and validation.
"""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from pydantic import BaseModel, Field, field_validator

# Memory manager imports removed - using state and database instead
from storyteller_lib.core.config import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    llm,
)
from storyteller_lib.core.logger import get_logger
# StoryState no longer used - working directly with database

logger = get_logger(__name__)

# Simple, focused Pydantic models for worldbuilding elements


class Geography(BaseModel):
    """Geography elements of the world."""

    locations: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 4-6 detailed paragraphs describing major locations including cities, regions, territories, and settlements. Include specific names, unique characteristics, architectural styles, population details, and how they connect to each other. Describe the atmosphere and feeling of each place."
        },
    )
    climate: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-4 detailed paragraphs about climate zones, seasonal variations, weather patterns, and extreme events. Explain how climate affects agriculture, architecture, daily life, and migration patterns. Include specific details about temperature ranges, precipitation, and unique atmospheric phenomena."
        },
    )
    landmarks: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-5 detailed paragraphs about notable physical features including mountain ranges, rivers, forests, deserts, and natural wonders. Give them evocative names and describe their strategic importance, local legends, and how they shape travel and trade routes."
        },
    )
    relevance: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 2-3 detailed paragraphs explaining how the geography directly impacts your story. Specify which features create obstacles, influence conflicts, affect plot pacing, and serve as key settings for major scenes."
        },
    )

    @field_validator("locations", "climate", "landmarks", "relevance")
    @classmethod
    def validate_content_quality(cls, v: str, info) -> str:
        # Be more fault-tolerant
        if not v:
            return ""  # Return empty string instead of failing

        # If it looks like a description field, raise an error to trigger retry
        if (
            v.strip()
            .lower()
            .startswith(("description:", "beschreibung:", "desc:", "field:"))
        ):
            logger.error(
                f"{info.field_name} received description instead of content: {v[:50]}..."
            )
            raise ValueError(
                f"{info.field_name} contains description/metadata instead of actual content. "
                f"Please generate the actual worldbuilding content, not field descriptions."
            )

        # Only reject obvious placeholders
        if v.strip().lower() in [
            "n/a",
            "none",
            "not applicable",
            "tbd",
            "to be determined",
        ]:
            return ""  # Return empty string instead of failing

        return v.strip()


class History(BaseModel):
    """Historical elements of the world."""

    timeline: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 4-5 detailed paragraphs presenting key historical events in chronological order. Include founding events, golden ages, dark periods, revolutions, and recent history. Provide specific dates or eras, describe causes and effects, and show how events connect to create a coherent historical narrative."
        },
    )
    figures: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-4 detailed paragraphs about important historical figures including founders, rulers, revolutionaries, inventors, and villains. Describe their achievements, failures, personalities, and lasting legacies. Explain how their actions still influence the present day."
        },
    )
    conflicts: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-4 detailed paragraphs about major wars, rebellions, and social upheavals. Detail the causes, key battles or turning points, resolution, and long-term consequences. Include information about alliances, betrayals, and how these conflicts shaped current borders and relationships."
        },
    )
    relevance: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 2-3 detailed paragraphs explaining how historical events directly impact your story. Identify old grudges, inherited conflicts, historical mysteries, and traditions that influence character motivations and plot developments."
        },
    )

    @field_validator("timeline", "figures", "conflicts", "relevance")
    @classmethod
    def validate_content_quality(cls, v: str, info) -> str:
        # Be more fault-tolerant
        if not v:
            return ""  # Return empty string instead of failing

        # If it looks like a description field, raise an error to trigger retry
        if (
            v.strip()
            .lower()
            .startswith(("description:", "beschreibung:", "desc:", "field:"))
        ):
            logger.error(
                f"{info.field_name} received description instead of content: {v[:50]}..."
            )
            raise ValueError(
                f"{info.field_name} contains description/metadata instead of actual content. "
                f"Please generate the actual worldbuilding content, not field descriptions."
            )

        # Only reject obvious placeholders
        if v.strip().lower() in [
            "n/a",
            "none",
            "not applicable",
            "tbd",
            "to be determined",
        ]:
            return ""  # Return empty string instead of failing

        return v.strip()


class Culture(BaseModel):
    """Cultural elements of the world."""

    languages: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-4 detailed paragraphs about languages, dialects, and communication methods. Include naming conventions, common phrases, how language reflects social status, and any magical or technological communication systems. Describe writing systems and literacy rates."
        },
    )
    traditions: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 4-5 detailed paragraphs about important customs, festivals, rites of passage, and artistic traditions. Describe specific ceremonies, traditional foods, music, dance, and storytelling. Include both everyday customs and special occasions."
        },
    )
    values: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-4 detailed paragraphs about core cultural values, social hierarchies, taboos, and attitudes toward outsiders. Explain concepts of honor, family structures, gender roles, and how different cultures within your world view each other."
        },
    )
    relevance: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 2-3 detailed paragraphs explaining how cultural elements create conflicts, misunderstandings, or bonds between characters. Identify specific traditions or values that drive plot points or character development."
        },
    )

    @field_validator("languages", "traditions", "values", "relevance")
    @classmethod
    def validate_content_quality(cls, v: str, info) -> str:
        # Be more fault-tolerant
        if not v:
            return ""  # Return empty string instead of failing

        # If it looks like a description field, raise an error to trigger retry
        if (
            v.strip()
            .lower()
            .startswith(("description:", "beschreibung:", "desc:", "field:"))
        ):
            logger.error(
                f"{info.field_name} received description instead of content: {v[:50]}..."
            )
            raise ValueError(
                f"{info.field_name} contains description/metadata instead of actual content. "
                f"Please generate the actual worldbuilding content, not field descriptions."
            )

        # Only reject obvious placeholders
        if v.strip().lower() in [
            "n/a",
            "none",
            "not applicable",
            "tbd",
            "to be determined",
        ]:
            return ""  # Return empty string instead of failing

        return v.strip()


class Politics(BaseModel):
    """Political elements of the world."""

    government: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 4-5 detailed paragraphs about government systems, power structures, and how leaders are chosen. Describe the balance of power, bureaucracy, corruption levels, and how different regions are governed. Include information about succession, councils, and administrative divisions."
        },
    )
    factions: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-4 detailed paragraphs about political parties, noble houses, guilds, or other power groups. Describe their goals, methods, leaders, and relationships with each other. Include secret societies, reformers, and traditionalists."
        },
    )
    laws: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-4 detailed paragraphs about legal systems, important laws, enforcement methods, and concepts of justice. Describe courts, punishments, rights of citizens, and how laws differ between regions or social classes."
        },
    )
    relevance: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 2-3 detailed paragraphs explaining how political elements drive your story. Identify power struggles, unjust laws, or political machinations that create obstacles or opportunities for characters."
        },
    )

    @field_validator("government", "factions", "laws", "relevance")
    @classmethod
    def validate_content_quality(cls, v: str, info) -> str:
        # Be more fault-tolerant
        if not v:
            return ""  # Return empty string instead of failing

        # If it looks like a description field, raise an error to trigger retry
        if (
            v.strip()
            .lower()
            .startswith(("description:", "beschreibung:", "desc:", "field:"))
        ):
            logger.error(
                f"{info.field_name} received description instead of content: {v[:50]}..."
            )
            raise ValueError(
                f"{info.field_name} contains description/metadata instead of actual content. "
                f"Please generate the actual worldbuilding content, not field descriptions."
            )

        # Only reject obvious placeholders
        if v.strip().lower() in [
            "n/a",
            "none",
            "not applicable",
            "tbd",
            "to be determined",
        ]:
            return ""  # Return empty string instead of failing

        return v.strip()


class Economics(BaseModel):
    """Economic elements of the world."""

    resources: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-4 detailed paragraphs about natural resources, their locations, extraction methods, and who controls them. Include scarce resources that drive conflict, abundant resources that enable prosperity, and unique materials specific to your world."
        },
    )
    trade: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 4-5 detailed paragraphs about trade routes, merchant guilds, currencies, banking systems, and markets. Describe major trade goods, caravan routes or shipping lanes, and how trade connects different regions. Include black markets and smuggling."
        },
    )
    classes: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-4 detailed paragraphs about wealth distribution, social mobility, and economic classes. Describe the lifestyles of rich and poor, middle class occupations, and how economic status affects daily life and opportunities."
        },
    )
    relevance: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 2-3 detailed paragraphs explaining how economic factors create plot tensions. Identify resource scarcities, trade disputes, or class conflicts that motivate characters or create obstacles."
        },
    )

    @field_validator("resources", "trade", "classes", "relevance")
    @classmethod
    def validate_content_quality(cls, v: str, info) -> str:
        # Be more fault-tolerant
        if not v:
            return ""  # Return empty string instead of failing

        # If it looks like a description field, raise an error to trigger retry
        if (
            v.strip()
            .lower()
            .startswith(("description:", "beschreibung:", "desc:", "field:"))
        ):
            logger.error(
                f"{info.field_name} received description instead of content: {v[:50]}..."
            )
            raise ValueError(
                f"{info.field_name} contains description/metadata instead of actual content. "
                f"Please generate the actual worldbuilding content, not field descriptions."
            )

        # Only reject obvious placeholders
        if v.strip().lower() in [
            "n/a",
            "none",
            "not applicable",
            "tbd",
            "to be determined",
        ]:
            return ""  # Return empty string instead of failing

        return v.strip()


class TechnologyMagic(BaseModel):
    """Technology or magic elements of the world."""

    systems: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 4-5 detailed paragraphs about available technologies or magic systems. For technology: describe key inventions, power sources, and technological level. For magic: explain how it works, who can use it, and different schools or types. Include specific examples and applications."
        },
    )
    limitations: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-4 detailed paragraphs about the constraints, costs, and dangers of technology or magic. Describe what's impossible, what requires rare materials or extensive training, and potential catastrophic failures or side effects."
        },
    )
    impact: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-4 detailed paragraphs about how technology or magic shapes society, from transportation and communication to warfare and medicine. Describe how it affects different social classes and professions differently."
        },
    )
    relevance: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 2-3 detailed paragraphs explaining how technology or magic creates specific plot opportunities or challenges. Identify key abilities or limitations that enable or constrain character actions."
        },
    )

    @field_validator("systems", "limitations", "impact", "relevance")
    @classmethod
    def validate_content_quality(cls, v: str, info) -> str:
        # Be more fault-tolerant
        if not v:
            return ""  # Return empty string instead of failing

        # If it looks like a description field, raise an error to trigger retry
        if (
            v.strip()
            .lower()
            .startswith(("description:", "beschreibung:", "desc:", "field:"))
        ):
            logger.error(
                f"{info.field_name} received description instead of content: {v[:50]}..."
            )
            raise ValueError(
                f"{info.field_name} contains description/metadata instead of actual content. "
                f"Please generate the actual worldbuilding content, not field descriptions."
            )

        # Only reject obvious placeholders
        if v.strip().lower() in [
            "n/a",
            "none",
            "not applicable",
            "tbd",
            "to be determined",
        ]:
            return ""  # Return empty string instead of failing

        return v.strip()


class Religion(BaseModel):
    """Religious elements of the world."""

    beliefs: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 4-5 detailed paragraphs about belief systems, pantheons, creation myths, and concepts of afterlife. Describe major and minor deities or spiritual forces, their domains, and relationships. Include competing or complementary belief systems."
        },
    )
    practices: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-4 detailed paragraphs about religious rituals, prayers, pilgrimages, and holy days. Describe temple services, personal devotions, sacrifices or offerings, and how religion intersects with major life events."
        },
    )
    organizations: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-4 detailed paragraphs about religious hierarchies, monastic orders, and influential leaders. Describe their political power, wealth, internal conflicts, and relationships with secular authorities."
        },
    )
    relevance: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 2-3 detailed paragraphs explaining how religious elements influence your story. Identify faith-based conflicts, divine interventions, religious obligations, or crises of faith that affect characters."
        },
    )

    @field_validator("beliefs", "practices", "organizations", "relevance")
    @classmethod
    def validate_content_quality(cls, v: str, info) -> str:
        # Be more fault-tolerant
        if not v:
            return ""  # Return empty string instead of failing

        # If it looks like a description field, raise an error to trigger retry
        if (
            v.strip()
            .lower()
            .startswith(("description:", "beschreibung:", "desc:", "field:"))
        ):
            logger.error(
                f"{info.field_name} received description instead of content: {v[:50]}..."
            )
            raise ValueError(
                f"{info.field_name} contains description/metadata instead of actual content. "
                f"Please generate the actual worldbuilding content, not field descriptions."
            )

        # Only reject obvious placeholders
        if v.strip().lower() in [
            "n/a",
            "none",
            "not applicable",
            "tbd",
            "to be determined",
        ]:
            return ""  # Return empty string instead of failing

        return v.strip()


class DailyLife(BaseModel):
    """Daily life elements of the world."""

    food: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-4 detailed paragraphs about cuisine, cooking methods, staple foods, and dining customs. Describe regional specialties, feast foods versus everyday meals, food preservation, and how different classes eat differently."
        },
    )
    clothing: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-4 detailed paragraphs about clothing styles, materials, colors, and what fashion signifies. Describe everyday wear versus formal attire, occupational clothing, and how climate and culture influence fashion."
        },
    )
    housing: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 3-4 detailed paragraphs about architectural styles, building materials, and living arrangements. Describe urban versus rural homes, how the wealthy live differently, and communal versus private spaces."
        },
    )
    relevance: str = Field(
        ...,
        json_schema_extra={
            "instruction": "Generate 2-3 detailed paragraphs explaining how daily life details enhance your story. Identify customs or living conditions that create atmosphere, reveal character, or provide plot opportunities."
        },
    )

    @field_validator("food", "clothing", "housing", "relevance")
    @classmethod
    def validate_content_quality(cls, v: str, info) -> str:
        # Be more fault-tolerant
        if not v:
            return ""  # Return empty string instead of failing

        # If it looks like a description field, raise an error to trigger retry
        if (
            v.strip()
            .lower()
            .startswith(("description:", "beschreibung:", "desc:", "field:"))
        ):
            logger.error(
                f"{info.field_name} received description instead of content: {v[:50]}..."
            )
            raise ValueError(
                f"{info.field_name} contains description/metadata instead of actual content. "
                f"Please generate the actual worldbuilding content, not field descriptions."
            )

        # Only reject obvious placeholders
        if v.strip().lower() in [
            "n/a",
            "none",
            "not applicable",
            "tbd",
            "to be determined",
        ]:
            return ""  # Return empty string instead of failing

        return v.strip()


class MysteryAnalysisFlat(BaseModel):
    """Flattened analysis of potential mystery elements to avoid nested dictionaries."""

    mystery_names: str = Field(
        description="Pipe-separated list of mystery element names"
    )
    mystery_descriptions: str = Field(
        description="Pipe-separated list of why each mystery is compelling"
    )
    mystery_clues: str = Field(
        description="Pipe-separated list of semicolon-separated clue descriptions for each mystery"
    )
    mystery_clue_levels: str = Field(
        description="Pipe-separated list of comma-separated revelation levels (1-5) for each mystery's clues"
    )


class WorldbuildingElements(BaseModel):
    """Complete worldbuilding elements model."""

    geography: Geography | None = Field(
        default=None, description="Geographic elements of the world"
    )
    history: History | None = Field(
        default=None, description="Historical elements of the world"
    )
    culture: Culture | None = Field(
        default=None, description="Cultural elements of the world"
    )
    politics: Politics | None = Field(
        default=None, description="Political elements of the world"
    )
    economics: Economics | None = Field(
        default=None, description="Economic elements of the world"
    )
    technology_magic: TechnologyMagic | None = Field(
        default=None, description="Technology or magic elements of the world"
    )
    religion: Religion | None = Field(
        default=None, description="Religious elements of the world"
    )
    daily_life: DailyLife | None = Field(
        default=None, description="Daily life elements of the world"
    )


# Helper functions for extraction and generation


def extract_with_model(
    text: str, model: type[BaseModel], category_name: str
) -> dict[str, Any]:
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
        from storyteller_lib.prompts.renderer import render_prompt

        structured_llm = llm.with_structured_output(model)
        prompt = render_prompt(
            "extract_category_info",
            "english",  # Always extract in English for consistency
            category_name=category_name,
            text=text,
        )
        result = structured_llm.invoke(prompt)
        return result.model_dump()
    except Exception as e:
        print(f"Error extracting {category_name}: {str(e)}")
        return {"error": f"Failed to extract {category_name}: {str(e)}"}


def create_category_prompt(
    category_name: str,
    genre: str,
    tone: str,
    author: str,
    initial_idea: str,
    global_story: str,
    language: str = DEFAULT_LANGUAGE,
    language_guidance: str = "",
) -> str:
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
    from storyteller_lib.prompts.renderer import render_prompt

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
            "worldbuilding",
            language=language,
            story_outline=global_story,  # Pass full story outline, not truncated
            genre=genre,
            tone=tone,
            existing_elements=existing_elements if existing_elements else None,
            category_name=category_name,
            initial_idea=initial_idea,
            author=author,
        )

        return prompt

    except Exception as e:
        # No fallback - fail fast if template is missing
        logger.error(f"Failed to use template for worldbuilding: {e}")
        raise ValueError(f"Required worldbuilding template not found: {e}")


def generate_category(
    category_name: str,
    model: type[BaseModel],
    genre: str,
    tone: str,
    author: str,
    initial_idea: str,
    global_story: str,
    language: str = DEFAULT_LANGUAGE,
    language_guidance: str = "",
) -> dict[str, Any]:
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

    # Extract field-specific instructions from the Pydantic model
    field_instructions = []
    for field_name, field_info in model.model_fields.items():
        if hasattr(field_info, "json_schema_extra") and field_info.json_schema_extra:
            instruction = field_info.json_schema_extra.get("instruction", "")
            if instruction:
                field_instructions.append(f"- {field_name}: {instruction}")

    # Add explicit pre-processing instructions
    pre_instructions = """
CRITICAL INSTRUCTIONS:
1. You must generate ACTUAL CONTENT for each field, not descriptions or metadata
2. DO NOT start any field with 'description:', 'Description:', 'beschreibung:', or similar prefixes
3. DO NOT return field descriptions or explanations of what should be written
4. Each field should contain the actual worldbuilding content as multiple paragraphs
5. Write the content directly - imagine you are writing the worldbuilding document itself

Example of WRONG output:
locations: "description: Major locations in the world"

Example of CORRECT output:
locations: "The city of Eldenhaven rises from the mist-shrouded valleys..."

SPECIFIC FIELD REQUIREMENTS:
"""

    # Add field-specific instructions if available
    if field_instructions:
        pre_instructions += "\n".join(field_instructions) + "\n\n"
    else:
        pre_instructions += (
            "Each field must contain multiple paragraphs of detailed content.\n\n"
        )

    pre_instructions += "Now generate the actual worldbuilding content:\n\n"

    base_prompt = create_category_prompt(
        category_name,
        genre,
        tone,
        author,
        initial_idea,
        global_story,
        language,
        language_guidance,
    )

    # Combine pre-instructions with the base prompt
    full_prompt = pre_instructions + base_prompt

    result = structured_llm.invoke(full_prompt)
    return result.model_dump()


def generate_mystery_elements(
    world_elements: dict[str, Any],
    num_mysteries: int = 3,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, Any]:
    """
    Generate mystery elements based on the worldbuilding elements.

    Args:
        world_elements: Dictionary of worldbuilding elements
        num_mysteries: Number of mysteries to generate
        language: Target language for generation

    Returns:
        Dictionary containing mystery elements
    """
    from storyteller_lib.prompts.renderer import render_prompt

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
        from storyteller_lib.prompts.renderer import render_prompt

        # Create a prompt for identifying mystery elements
        prompt = render_prompt(
            "mystery_elements",
            language=language,
            num_mysteries=num_mysteries,
            world_elements=simplified_world,
            language_instruction=(
                language_instruction if language.lower() != DEFAULT_LANGUAGE else None
            ),
            make_authentic=language.lower() != DEFAULT_LANGUAGE,
            target_language=(
                SUPPORTED_LANGUAGES[language.lower()]
                if language.lower() != DEFAULT_LANGUAGE
                else None
            ),
        )

        # Extract the structured data
        mystery_analysis_flat = structured_llm.invoke(prompt)

        # Convert flattened data to nested structure
        names = [n.strip() for n in mystery_analysis_flat.mystery_names.split("|")]
        descriptions = [
            d.strip() for d in mystery_analysis_flat.mystery_descriptions.split("|")
        ]
        clues_lists = [
            c.strip() for c in mystery_analysis_flat.mystery_clues.split("|")
        ]
        levels_lists = [
            l.strip() for l in mystery_analysis_flat.mystery_clue_levels.split("|")
        ]

        key_mysteries = []
        for name, desc, clues_str, levels_str in zip(
            names, descriptions, clues_lists, levels_lists, strict=False
        ):
            clues = [c.strip() for c in clues_str.split(";") if c.strip()]
            levels = [int(l.strip()) for l in levels_str.split(",") if l.strip()]

            mystery_clues = []
            for clue_desc, level in zip(clues, levels, strict=False):
                mystery_clues.append(
                    {
                        "description": clue_desc,
                        "revelation_level": level,
                        "revealed": False,
                    }
                )

            key_mysteries.append(
                {"name": name, "description": desc, "clues": mystery_clues}
            )

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
                        {
                            "description": "A subtle reference in ancient texts",
                            "revelation_level": 1,
                            "revealed": False,
                        },
                        {
                            "description": "Physical evidence discovered",
                            "revelation_level": 3,
                            "revealed": False,
                        },
                        {
                            "description": "The full truth revealed",
                            "revelation_level": 5,
                            "revealed": False,
                        },
                    ],
                }
            ]
        }


def generate_world_summary(
    world_elements: dict[str, Any],
    genre: str,
    tone: str,
    language: str = DEFAULT_LANGUAGE,
) -> str:
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
    from storyteller_lib.prompts.renderer import render_prompt

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
                    value_str = ", ".join(str(v) for v in value[:3]) + (
                        "..." if len(value) > 3 else ""
                    )
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

    # Generate the world summary
    prompt = render_prompt(
        "world_summary",
        language=language,
        category_summaries=chr(10) + chr(10).join(category_summaries),
        language_instruction=(
            language_instruction if language.lower() != DEFAULT_LANGUAGE else None
        ),
        genre=genre,
        tone=tone,
        make_authentic=language.lower() != DEFAULT_LANGUAGE,
        target_language=(
            SUPPORTED_LANGUAGES[language.lower()]
            if language.lower() != DEFAULT_LANGUAGE
            else None
        ),
    )

    try:
        response = llm.invoke([HumanMessage(content=prompt)]).content

        return response
    except Exception as e:
        print(f"Error generating world summary: {str(e)}")
        return f"Error generating world summary: {str(e)}"


def generate_worldbuilding(params: dict) -> dict:
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
    from storyteller_lib.core.config import get_story_config

    config = get_story_config()

    genre = config["genre"]
    tone = config["tone"]
    author = config["author"]
    initial_idea = config["initial_idea"]
    # Get full story outline from database
    from storyteller_lib.persistence.database import get_db_manager

    db_manager = get_db_manager()

    if not db_manager or not db_manager._db:
        raise RuntimeError(
            "Database manager not available - cannot retrieve story outline"
        )

    # Get full story outline from database
    from storyteller_lib.core.logger import get_logger

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
        global_story = result["global_story"]

        if not global_story or global_story.strip() == "":
            logger.error(
                f"Story configuration exists but has empty global_story. Genre={result['genre']}, Tone={result['tone']}"
            )
            raise RuntimeError("Story outline is empty in database")

        logger.info(
            f"Retrieved global story for worldbuilding (length: {len(global_story)} chars)"
        )

    # Get language elements if not English
    language = config.get("language", DEFAULT_LANGUAGE)
    language_guidance = ""

    if language.lower() != DEFAULT_LANGUAGE:
        # Language elements are generated fresh during initialization
        try:
            language_elements_result = None

            # Process language elements if found
            language_elements = None
            if language_elements_result:
                if (
                    isinstance(language_elements_result, dict)
                    and "value" in language_elements_result
                ):
                    language_elements = language_elements_result["value"]
                elif isinstance(language_elements_result, list):
                    for item in language_elements_result:
                        if (
                            hasattr(item, "key")
                            and item.key == f"language_elements_{language.lower()}"
                        ):
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
                place_name_examples = (
                    "Examples of authentic place naming conventions:\n"
                )
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
        "daily_life": DailyLife,
    }

    # Generate each category separately
    world_elements = {}
    for category_name, model in category_models.items():
        print(f"Generating {category_name} elements...")
        category_data = generate_category(
            category_name,
            model,
            genre,
            tone,
            author,
            initial_idea,
            global_story,
            language,
            language_guidance,
        )
        world_elements[category_name] = category_data

    # World elements are now stored in database via database_integration
    # Memory tool has been removed - metadata is tracked in the database

    # Generate mystery elements
    mystery_elements = generate_mystery_elements(world_elements, 3, language)

    # Create a world state tracker to monitor changes over time
    {
        "initial_state": world_elements,
        "current_state": world_elements,
        "changes": [],
        "revelations": [],
        "mystery_elements": {
            "key_mysteries": mystery_elements.get("key_mysteries", []),
            "clues_revealed": {},
            "reader_knowledge": {},
            "character_knowledge": {},
        },
    }

    # World state tracker is now managed through database tables
    # No need to store separately

    # Generate a summary of the world
    world_summary = generate_world_summary(world_elements, genre, tone, language)

    # World summary is generated on demand, not stored separately

    # Log world elements
    from storyteller_lib.utils.progress_logger import log_progress

    log_progress("world_elements", world_elements=world_elements)

    # Return the world elements and summary
    # Store world elements in database
    from storyteller_lib.persistence.database import get_db_manager

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
            *[RemoveMessage(id=msg.id) for msg in params.get("messages", [])],
            AIMessage(
                content=f"I've created detailed worldbuilding elements for your {genre} story with a {tone} tone. The world includes geography, history, culture, politics, economics, technology/magic, religion, and daily life elements that will support your story.{chr(10)}{chr(10)}World Summary:{chr(10)}{world_summary}"
            ),
        ],
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
        "daily_life": DailyLife,
    }

    # Extract each category separately
    extracted_data = {}
    for category_name, model in category_models.items():
        category_data = extract_with_model(text, model, category_name)
        if "error" not in category_data:
            extracted_data[category_name] = category_data

    # Create and return the WorldbuildingElements object
    return WorldbuildingElements(**extracted_data)


def extract_specific_element(text: str, element_type: str) -> dict[str, Any]:
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
        "daily_life": DailyLife,
    }

    # Normalize the element type
    element_type_lower = element_type.lower()

    # Get the appropriate model
    model = element_models.get(element_type_lower)
    if not model:
        raise ValueError(
            f"Unknown element type: {element_type}. Valid types are: {', '.join(element_models.keys())}"
        )

    # Extract the element
    return extract_with_model(text, model, element_type)


def extract_mystery_elements(text: str, num_mysteries: int = 3) -> dict[str, Any]:
    """
    Extract potential mystery elements from text.

    Args:
        text: Text to analyze for potential mysteries
        num_mysteries: Number of mysteries to identify

    Returns:
        Dictionary containing structured mystery elements
    """
    try:
        # Create a structured LLM with the MysteryAnalysisFlat model
        structured_llm = llm.with_structured_output(MysteryAnalysisFlat)

        # Use template system
        from storyteller_lib.prompts.renderer import render_prompt

        # Create a prompt for identifying mystery elements
        prompt = render_prompt(
            "mystery_elements",
            "english",  # Always extract in English for consistency
            num_mysteries=num_mysteries,
            world_elements=text,
        )

        # Extract the structured data
        mystery_analysis_flat = structured_llm.invoke(prompt)

        # Convert flattened data to nested structure
        names = [n.strip() for n in mystery_analysis_flat.mystery_names.split("|")]
        descriptions = [
            d.strip() for d in mystery_analysis_flat.mystery_descriptions.split("|")
        ]
        clues_lists = [
            c.strip() for c in mystery_analysis_flat.mystery_clues.split("|")
        ]
        levels_lists = [
            l.strip() for l in mystery_analysis_flat.mystery_clue_levels.split("|")
        ]

        key_mysteries = []
        for name, desc, clues_str, levels_str in zip(
            names, descriptions, clues_lists, levels_lists, strict=False
        ):
            clues = [c.strip() for c in clues_str.split(";") if c.strip()]
            levels = [int(l.strip()) for l in levels_str.split(",") if l.strip()]

            mystery_clues = []
            for clue_desc, level in zip(clues, levels, strict=False):
                mystery_clues.append(
                    {
                        "description": clue_desc,
                        "revelation_level": level,
                        "revealed": False,
                    }
                )

            key_mysteries.append(
                {"name": name, "description": desc, "clues": mystery_clues}
            )

        return {"key_mysteries": key_mysteries}
    except Exception as e:
        print(f"Error extracting mystery elements: {str(e)}")
        return {"error": f"Failed to extract mystery elements: {str(e)}"}
