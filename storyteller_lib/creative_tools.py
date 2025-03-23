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
    evaluation_criteria: List[str] = None
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
        
    Returns:
        Dictionary with generated ideas and evaluations
    """
    if evaluation_criteria is None:
        evaluation_criteria = [
            "Originality and surprise factor",
            "Coherence with the established narrative",
            "Potential for character development",
            "Reader engagement and emotional impact",
            "Feasibility within the story world"
        ]
        
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
    
    # Brainstorming prompt
    brainstorm_prompt = f"""
    # Creative Brainstorming Session: {topic}
    
    ## Context
    - Genre: {genre}
    - Tone: {tone}
    - Current Story Context: {context}
    {style_section}
    {language_section}
    
    ## Instructions
    Generate {num_ideas} diverse, creative ideas related to {topic}.
    Think outside the box while maintaining coherence with the story context.
    Each idea should be surprising yet plausible within the established world.
    
    For each idea:
    1. Provide a concise title/headline
    2. Describe the idea in 3-5 sentences
    3. Note one potential benefit to the story
    4. Note one potential challenge to implementation
    
    Format each idea clearly and number them 1 through {num_ideas}.
    """
    
    # Generate ideas
    ideas_response = llm.invoke([HumanMessage(content=brainstorm_prompt)]).content
    
    # Evaluation prompt
    eval_prompt = f"""
    # Idea Evaluation for: {topic}
    
    ## Ideas Generated
    {ideas_response}
    
    ## Story Context
    {context}
    
    ## Evaluation Criteria
    {', '.join(evaluation_criteria)}
    
    ## Instructions
    Evaluate each idea against the criteria above on a scale of 1-10.
    For each idea:
    1. Provide scores for each criterion
    2. Calculate a total score
    3. Write a brief justification (2-3 sentences)
    4. Indicate if the idea should be incorporated (YES/MAYBE/NO)
    
    Then rank the ideas from best to worst fit for the story.
    Finally, recommend the top 1-2 ideas to incorporate, with brief reasoning.
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

def parse_json_with_langchain(text: str, default_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Parse JSON from text using LangChain's JSON parser.
    Falls back to default_data if parsing fails.
    
    Args:
        text: Text containing JSON to parse
        default_data: Default data to return if parsing fails
        
    Returns:
        Parsed JSON data as a dictionary
    """
    try:
        # Use LangChain's JsonOutputParser to parse the text
        json_parser = JsonOutputParser()
        
        # First try direct parsing without LLM
        try:
            return json_parser.parse(text)
        except Exception:
            # If direct parsing fails, use the LLM to fix and generate valid JSON
            fix_prompt = PromptTemplate(
                template="""The following text contains JSON that needs to be fixed and parsed:

{text}

Extract and fix the JSON to make it valid. Return ONLY the fixed JSON without any additional text or markup.

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
                return default_data if default_data is not None else {}
    except Exception as e:
        print(f"Unexpected error parsing JSON: {str(e)}")
        return default_data if default_data is not None else {}

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