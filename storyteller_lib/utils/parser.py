"""
Story parser utilities for extracting elements from initial ideas.
Shared between v1 and v2 workflows.
"""

from typing import Dict, Any
from pydantic import BaseModel, Field

from storyteller_lib.core.config import llm, DEFAULT_LANGUAGE
from storyteller_lib.core.logger import get_logger
logger = get_logger(__name__)


class StoryElements(BaseModel):
    """Extracted elements from an initial story idea."""
    plot: str = Field(default="", description="The main plot or conflict")
    setting: str = Field(default="", description="The story setting or world")
    characters: list[str] = Field(default_factory=list, description="Main character names or descriptions")
    themes: list[str] = Field(default_factory=list, description="Key themes or messages")


def parse_initial_idea(initial_idea: str, language: str = DEFAULT_LANGUAGE) -> Dict[str, Any]:
    """
    Parse an initial story idea to extract key elements using Pydantic.
    
    Args:
        initial_idea: The initial story idea
        language: Target language for parsing
        
    Returns:
        A dictionary of key elements extracted from the idea
    """
    if not initial_idea:
        return {}
    
    try:
        # Create a structured LLM that outputs a StoryElements object
        structured_llm = llm.with_structured_output(StoryElements)
        
        # Use template system
        from storyteller_lib.prompts.renderer import render_prompt        
      
        prompt = render_prompt('parse_initial_idea', 
                            language=language,
                            initial_idea=initial_idea)
        
        from langchain_core.messages import HumanMessage
      
        result = structured_llm.invoke([HumanMessage(content=prompt)])
        
        # Convert to dictionary
        elements = {
            "plot": result.plot,
            "setting": result.setting,
            "characters": result.characters,
            "themes": result.themes
        }
        
        logger.info(f"Extracted elements from initial idea: {elements}")
        return elements
        
    except Exception as e:
        logger.error(f"Failed to parse initial idea: {e}")
        return {}