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

def generate_genre_guidance(genre: str, tone: str, language: str = DEFAULT_LANGUAGE) -> str:
    """
    Dynamically generate genre-specific guidance using the LLM.
    
    Args:
        genre: Story genre
        tone: Story tone
        language: Target language for story generation
        
    Returns:
        String containing genre-specific guidance
    """
    # Prompt the LLM to generate genre-specific guidance
    prompt = f"""
    You are a literary expert specializing in genre fiction. I need you to provide guidance on the key elements
    and conventions of the "{genre}" genre with a "{tone}" tone.
    
    Please provide:
    1. A brief description of what makes the {genre} genre distinctive
    2. 5-7 key elements that must be present for a story to be considered part of this genre
    3. Common tropes, themes, or motifs associated with this genre
    4. How the "{tone}" tone typically manifests in this genre
    
    Format your response as follows:
    
    GENRE REQUIREMENTS:
    This is a {genre} story with a {tone} tone. All ideas MUST adhere to the conventions and expectations of the {genre} genre.
    
    Key elements that must be present for a {genre} story:
    - [Element 1]
    - [Element 2]
    - [Element 3]
    - [Element 4]
    - [Element 5]
    - [Additional elements if relevant]
    
    Provide only the formatted guidance without any additional explanations or commentary.
    """
    
    # Add language instruction if not English
    if language.lower() != DEFAULT_LANGUAGE:
        prompt += f"""
        
        CRITICAL LANGUAGE INSTRUCTION:
        Your response MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL content - including descriptions, elements, and guidance - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
        
        This is a STRICT requirement. Your ENTIRE response must be written ONLY in {SUPPORTED_LANGUAGES[language.lower()]}.
        """
    
    # Get the response from the LLM
    response = llm.invoke([HumanMessage(content=prompt)]).content
    
    # If the response doesn't start with "GENRE REQUIREMENTS", extract just the relevant part
    if "GENRE REQUIREMENTS:" not in response:
        # Create a properly formatted response
        formatted_guidance = f"""
    GENRE REQUIREMENTS:
    This is a {genre} story with a {tone} tone. All ideas MUST adhere to the conventions and expectations of the {genre} genre.
    
    Key elements that must be present for a {genre} story:
    """
        # Extract bullet points if they exist
        if "-" in response:
            bullet_points = [line.strip() for line in response.split("\n") if line.strip().startswith("-")]
            if bullet_points:
                formatted_guidance += "\n        " + "\n        ".join(bullet_points)
            else:
                # If no bullet points found, use the whole response
                formatted_guidance += f"\n        - {response.strip()}"
        else:
            # If no bullet points, create some from the response
            formatted_guidance += f"\n        - {response.strip()}"
        
        return formatted_guidance
    
    return response

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
    
    # Build constraints section
    constraints_section = ""
    if any([setting_constraint, character_constraints, plot_constraints]):
        constraints_section = f"""
        CRITICAL CONSTRAINTS (MUST BE FOLLOWED):
        """
        
        if setting_constraint:
            constraints_section += f"""
            - Setting: All ideas MUST take place in {setting_constraint}. Do not deviate from this setting.
            """
            
        if character_constraints:
            constraints_section += f"""
            - Characters: All ideas MUST incorporate these characters: {character_constraints}
            """
            
        if plot_constraints:
            constraints_section += f"""
            - Plot Elements: All ideas MUST align with this plot: {plot_constraints}
            """
            
        constraints_section += """
        These constraints are non-negotiable. Any idea that violates these constraints will be rejected.
        """
        
    # Prepare author style guidance if provided
    style_section = ""
    if author and author_style_guidance:
        style_section = f"""
        AUTHOR STYLE CONSIDERATION:
        Consider the writing style of {author} as you generate ideas:
        
        {author_style_guidance}
        
        The ideas should feel like they could appear in a story by this author.
        """
    
    # Prepare language guidance if not English
    language_section = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_section = f"""
        CRITICAL LANGUAGE INSTRUCTION:
        You MUST generate ALL ideas ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL content - including idea titles, descriptions, explanations, and analyses - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
        DO NOT switch to any other language at ANY point in your response.
        
        Additionally:
        - Character names, places, and cultural references should be authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures
        - Consider cultural nuances, idioms, and storytelling traditions specific to {SUPPORTED_LANGUAGES[language.lower()]}-speaking regions
        - Use vocabulary, expressions, and sentence structures natural to {SUPPORTED_LANGUAGES[language.lower()]}
        
        This is a STRICT requirement. Your ENTIRE response must be written ONLY in {SUPPORTED_LANGUAGES[language.lower()]}.
        """
    
    # Generate genre-specific guidance dynamically using the LLM
    genre_guidance = generate_genre_guidance(genre, tone, language)
    
    # Brainstorming prompt
    brainstorm_prompt = f"""
    # Story Enhancement Brainstorming Session: {topic}
    
    ## Context
    - Genre: {genre}
    - Tone: {tone}
    - Current Story Context: {context}
    
    {constraints_section}
    {genre_guidance}
    {style_section}
    {language_section}
    ## IMPORTANT INSTRUCTIONS
    {"Your ideas must adhere to the initial story concept and constraints. Maintain consistency with the core elements." if strict_adherence else ""}
    
    CRITICAL: Generate {num_ideas} ideas that ENHANCE the existing storyline rather than distract from it.
    Each idea should ADD VALUE to the story by deepening character development, enriching the setting, or advancing the plot in meaningful ways.
    
    DO NOT generate ideas that:
    - Introduce unnecessary complexity
    - Distract from the main storyline
    - Contradict established elements
    - Feel disconnected from the core narrative
    
    {"If the initial idea specifies particular settings, characters, or plot elements, these should be preserved in your ideas. Do not substitute core elements with alternatives." if strict_adherence else ""}
    
    For each idea:
    1. Provide a concise title/headline
    2. Describe the idea in 3-5 sentences
    3. Explain specifically how this idea ENHANCES the existing storyline
    4. Note one potential challenge to implementation
    5. Explain how this idea adheres to the genre requirements and constraints
    {"6. Verify that this idea maintains consistency with the initial concept" if strict_adherence else ""}
    
    Format each idea clearly and number them 1 through {num_ideas}.
    
    IMPORTANT: Double-check each idea to ensure it complies with ALL constraints and genre requirements before finalizing.
    {"FINAL CHECK: Verify that your ideas preserve the essential elements of the initial concept while ENHANCING the storyline rather than distracting from it." if strict_adherence else ""}
    IMPORTANT: Double-check each idea to ensure it fully complies with ALL constraints and genre requirements before finalizing.
    """
    
    # Generate ideas
    ideas_response = llm.invoke([HumanMessage(content=brainstorm_prompt)]).content
    
    # Evaluation prompt with emphasis on story enhancement
    eval_prompt = f"""
    # Idea Evaluation for: {topic}
    
    ## Ideas Generated
    {ideas_response}
    
    ## Story Context
    {context}
    
    ## Constraints
    {constraints_section}
    
    ## Genre Requirements
    {genre_guidance}
    
    ## Evaluation Criteria
    {', '.join(evaluation_criteria)}
    
    ## EVALUATION INSTRUCTIONS
    {"First, check if each idea maintains consistency with the initial concept and preserves essential elements." if strict_adherence else ""}
    
    First, check each idea for compliance with the constraints and genre requirements.
    REJECT any idea that:
    """
    
    # Add language instruction for evaluation if not English
    if language.lower() != DEFAULT_LANGUAGE:
        eval_prompt += f"""
    - Is not written entirely in {SUPPORTED_LANGUAGES[language.lower()]}
    - Contains any English text or other languages
    - Uses character names or cultural references not authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures
    
    CRITICAL LANGUAGE INSTRUCTION:
    Your evaluation MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
    ALL content - including your analysis, ratings, and recommendations - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
    DO NOT switch to any other language at ANY point in your evaluation.
    
    This is a STRICT requirement. Your ENTIRE evaluation must be written ONLY in {SUPPORTED_LANGUAGES[language.lower()]}.
    """
    
    eval_prompt += """
    {"1. Significantly alters or omits essential elements from the initial concept" if strict_adherence else ""}
    2. Violates the constraints
    3. Doesn't fit the {genre} genre
    4. Distracts from rather than enhances the main storyline
    
    {"Ideas should build upon the initial concept while preserving its core elements. Significant deviations from the established setting, characters, or central conflict should be avoided." if strict_adherence else ""}
    
    Then, evaluate the remaining ideas against the criteria above on a scale of 1-10.
    For each idea:
    1. Provide scores for each criterion
    2. Calculate a total score
    3. Write a brief justification focusing on how the idea enhances the storyline
    4. Indicate if the idea should be incorporated (YES/MAYBE/NO)
    
    Then rank the ideas from best to worst fit for the story.
    Finally, recommend the top 1-2 ideas to incorporate, with brief reasoning that explains how they enhance the storyline without distracting from it.
    
    {"FINAL CHECK: Verify that your recommended ideas maintain consistency with the initial concept while enhancing the storyline." if strict_adherence else ""}
    """
    
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
    model_name: str = "DynamicModel"
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
        
        # Invoke with the text content
        prompt = f"""
        Based on this {description}:
        
        {text_content}
        
        Extract the structured data according to the specified format.
        """
        
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

def parse_json_with_langchain(text: str, description: str = "world elements") -> Dict[str, Any]:
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
        prompt = f"""Extract the world building information from this text into a structured format:

{text}

Organize the information into these categories:
- GEOGRAPHY: locations, physical features, climate
- HISTORY: timeline, past conflicts, important events  
- CULTURE: customs, values, arts
- POLITICS: government, laws, factions
- ECONOMICS: currency, trade, resources
- TECHNOLOGY/MAGIC: level, systems, limitations
- RELIGION: deities, practices, beliefs
- DAILY_LIFE: food, clothing, housing

For each category, extract the relevant information. If a category is not mentioned in the text, leave it empty."""
        
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