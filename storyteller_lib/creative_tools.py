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
        LANGUAGE CONSIDERATION:
        Generate ideas appropriate for a story written in {SUPPORTED_LANGUAGES[language.lower()]}.
        Character names, places, and cultural references should be authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures.
        Consider cultural nuances, idioms, and storytelling traditions specific to {SUPPORTED_LANGUAGES[language.lower()]}-speaking regions.
        """
    
    # Genre-specific guidance
    genre_guidance = f"""
    GENRE REQUIREMENTS:
    This is a {genre} story with a {tone} tone. All ideas MUST adhere to the conventions and expectations of the {genre} genre.
    
    Key elements that must be present for a {genre} story:
    """
    
    # Add genre-specific elements based on the genre
    if genre.lower() == "mystery":
        genre_guidance += """
        - A central mystery or puzzle to be solved
        - Clues and red herrings
        - Investigation and deduction
        - Suspects with motives, means, and opportunities
        - A resolution that explains the mystery
        """
    elif genre.lower() == "fantasy":
        genre_guidance += """
        - Magical or supernatural elements
        - Worldbuilding with consistent rules
        - Fantastical creatures or beings
        - Epic conflicts or quests
        - Themes of good vs. evil, power, or destiny
        """
    elif genre.lower() == "sci-fi" or genre.lower() == "science fiction":
        genre_guidance += """
        - Scientific or technological concepts
        - Futuristic or alternative settings
        - Exploration of the impact of science/technology on society
        - Speculative elements based on scientific principles
        - Themes of progress, ethics, or humanity's future
        """
    elif genre.lower() == "romance":
        genre_guidance += """
        - Focus on a developing relationship between characters
        - Emotional connection and attraction
        - Obstacles to the relationship
        - Character growth through the relationship
        - Satisfying emotional resolution
        """
    elif genre.lower() == "horror":
        genre_guidance += """
        - Elements designed to frighten or disturb
        - Building tension and suspense
        - Threats to characters' safety or sanity
        - Atmosphere of dread or unease
        - Exploration of fears and taboos
        """
    elif genre.lower() == "thriller":
        genre_guidance += """
        - High stakes and tension
        - Danger and time pressure
        - Complex plot with twists
        - Protagonist facing formidable opposition
        - Themes of survival, justice, or moral dilemmas
        """
    else:
        # Generic genre guidance for other genres
        genre_guidance += f"""
        - Elements typical of {genre} stories
        - Appropriate pacing and structure for {genre}
        - Character types commonly found in {genre}
        - Themes and motifs associated with {genre}
        - Reader expectations for a {genre} story
        """
    
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
    return {
        "ideas": ideas_response,
        "evaluation": evaluation,
        "recommended_ideas": evaluation.split("recommend")[-1].strip() if "recommend" in evaluation.lower() else None
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

def parse_json_with_langchain(text: str, description: str = "world elements") -> Dict[str, Any]:
    """
    Parse JSON from text using LangChain's JSON parser with multiple fallback methods.
    
    Args:
        text: Text containing JSON to parse
        description: Description of what we're parsing (for error messages)
        
    Returns:
        Parsed JSON data as a dictionary
    """
    # First try direct parsing without LLM
    try:
        # Try to extract JSON if it's within a code block
        if "```json" in text and "```" in text.split("```json", 1)[1]:
            json_content = text.split("```json", 1)[1].split("```", 1)[0].strip()
            return json.loads(json_content)
        # Try direct JSON parsing
        elif text.strip().startswith("{") and text.strip().endswith("}"):
            return json.loads(text)
    except Exception:
        pass
    
    # Try to manually parse the structure if it looks like the example in the error
    try:
        # Check if this is the format from the error message
        if "GEOGRAPHY" in text and "HISTORY" in text and "CULTURE" in text:
            result = {}
            
            # Define the main categories we expect
            categories = [
                "GEOGRAPHY", "HISTORY", "CULTURE", "POLITICS",
                "ECONOMICS", "TECHNOLOGY/MAGIC", "RELIGION", "DAILY_LIFE"
            ]
            
            # Extract each category's content
            for i, category in enumerate(categories):
                if category in text:
                    # Find the start of this category
                    start_idx = text.find(category)
                    
                    # Find the end (either the next category or the end of text)
                    end_idx = len(text)
                    for next_cat in categories[i+1:]:
                        next_idx = text.find(next_cat)
                        if next_idx > start_idx:
                            end_idx = next_idx
                            break
                    
                    # Extract the category content
                    category_content = text[start_idx:end_idx].strip()
                    
                    # Process the content into a dictionary
                    category_dict = {}
                    lines = category_content.split('\n')
                    
                    # Skip the category name line
                    current_key = None
                    for line in lines[1:]:
                        line = line.strip()
                        if not line:
                            continue
                            
                        # Check if this is a new key
                        if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
                            parts = line.split(":", 1)
                            current_key = parts[0].strip()
                            value = parts[1].strip() if len(parts) > 1 else ""
                            category_dict[current_key] = value
                        elif current_key and (line.startswith(" ") or line.startswith("\t")):
                            # This is a continuation of the previous value
                            category_dict[current_key] += " " + line
                    
                    result[category] = category_dict
            
            # If we successfully extracted at least some categories, return the result
            if result:
                return result
    except Exception as e:
        print(f"Manual parsing failed: {str(e)}")
    
    # Try with direct LLM JSON generation
    try:
        prompt = f"""
        I need to convert this world building information into a valid JSON object:
        
        {text}
        
        Format it as a JSON object with these top-level keys:
        - GEOGRAPHY
        - HISTORY
        - CULTURE
        - POLITICS
        - ECONOMICS
        - TECHNOLOGY/MAGIC
        - RELIGION
        - DAILY_LIFE
        
        Each top-level key should contain a nested object with the elements for that category.
        For example:
        
        {{
          "GEOGRAPHY": {{
            "Major Locations": "Description of locations",
            "Physical Features": "Description of features"
          }},
          "HISTORY": {{
            "Timeline": "Historical events",
            "Past Conflicts": "Description of conflicts"
          }}
        }}
        
        Return ONLY the valid JSON object without any additional text, explanation, or code block markers.
        """
        
        json_response = llm.invoke(prompt).content
        
        # Try to extract JSON if it's within a code block
        if "```json" in json_response and "```" in json_response.split("```json", 1)[1]:
            json_content = json_response.split("```json", 1)[1].split("```", 1)[0].strip()
            return json.loads(json_content)
        # Try to extract JSON if it's within any code block
        elif "```" in json_response and "```" in json_response.split("```", 1)[1]:
            json_content = json_response.split("```", 1)[1].split("```", 1)[0].strip()
            return json.loads(json_content)
        # Try direct JSON parsing
        elif json_response.strip().startswith("{") and json_response.strip().endswith("}"):
            return json.loads(json_response)
    except Exception as e:
        print(f"Direct LLM JSON generation failed: {str(e)}")
    
    # If all else fails, try with JsonOutputParser
    try:
        json_parser = JsonOutputParser()
        
        fix_prompt = PromptTemplate(
            template="""The following text contains world building information that needs to be converted to JSON:

{text}

Convert this to a valid JSON object with these top-level keys:
- GEOGRAPHY
- HISTORY
- CULTURE
- POLITICS
- ECONOMICS
- TECHNOLOGY/MAGIC
- RELIGION
- DAILY_LIFE

Each top-level key should contain a nested object with the elements for that category.

{format_instructions}""",
            input_variables=["text"],
            partial_variables={"format_instructions": json_parser.get_format_instructions()}
        )
        
        # Create and run the chain
        fix_chain = fix_prompt | llm | json_parser
        
        try:
            return fix_chain.invoke({"text": text})
        except Exception as e:
            print(f"LangChain JSON parser failed: {str(e)}")
    except Exception as e:
        print(f"All JSON parsing methods failed: {str(e)}")
    
    # Last resort: return a minimal structure with the original text preserved
    # This ensures we don't lose the content even if parsing fails
    return {
        "GEOGRAPHY": {"content": text.split("HISTORY")[0] if "HISTORY" in text else "Geographic elements"},
        "HISTORY": {"content": text.split("HISTORY")[1].split("CULTURE")[0] if "HISTORY" in text and "CULTURE" in text else "Historical elements"},
        "CULTURE": {"content": text.split("CULTURE")[1].split("POLITICS")[0] if "CULTURE" in text and "POLITICS" in text else "Cultural elements"},
        "POLITICS": {"content": text.split("POLITICS")[1].split("ECONOMICS")[0] if "POLITICS" in text and "ECONOMICS" in text else "Political elements"},
        "ECONOMICS": {"content": text.split("ECONOMICS")[1].split("TECHNOLOGY/MAGIC")[0] if "ECONOMICS" in text and "TECHNOLOGY/MAGIC" in text else "Economic elements"},
        "TECHNOLOGY/MAGIC": {"content": text.split("TECHNOLOGY/MAGIC")[1].split("RELIGION")[0] if "TECHNOLOGY/MAGIC" in text and "RELIGION" in text else "Technology or magic"},
        "RELIGION": {"content": text.split("RELIGION")[1].split("DAILY_LIFE")[0] if "RELIGION" in text and "DAILY_LIFE" in text else "Religious elements"},
        "DAILY_LIFE": {"content": text.split("DAILY_LIFE")[1] if "DAILY_LIFE" in text else "Daily life elements"}
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