"""Helper functions for scene generation.

This module contains utility functions used by both scene writing and reflection.
"""

# Standard library imports
from typing import Any, Dict, List

# Local imports
from storyteller_lib.logger import get_logger

logger = get_logger(__name__)



def _get_previously_established_elements(world_elements: Dict) -> str:
    """Extract previously established world elements that should be remembered.
    
    Args:
        world_elements: Dictionary of world building elements
        
    Returns:
        Formatted string of established elements
    """
    established = []
    
    # Focus on concrete, established facts
    if "geography" in world_elements:
        geo = world_elements["geography"]
        if "major_locations" in geo and geo["major_locations"]:
            established.append(f"Known locations: {', '.join(geo['major_locations'][:3])}")
            
    if "magic_system" in world_elements:
        magic = world_elements["magic_system"]
        if "rules" in magic and magic["rules"]:
            established.append(f"Magic rules: {magic['rules'][0] if isinstance(magic['rules'], list) else magic['rules']}")
            
    if "technology" in world_elements:
        tech = world_elements["technology"]
        if "level" in tech:
            established.append(f"Technology level: {tech['level']}")
    
    if established:
        return "\nPreviously Established World Elements:\n" + "\n".join(f"- {e}" for e in established) + "\n"
    
    return ""


def _prepare_worldbuilding_guidance(world_elements: Dict, chapter_outline: str, mystery_relevance: bool = False, language: str = "english") -> str:
    """Prepare worldbuilding guidance for scene writing.
    
    Args:
        world_elements: Dictionary of world building elements (already filtered for scene relevance)
        chapter_outline: The chapter outline
        mystery_relevance: Whether mystery elements are relevant
        language: The language for the guidance
        
    Returns:
        Formatted worldbuilding guidance string
    """
    if not world_elements:
        return ""
    
    # Import optimization utility
    from storyteller_lib.prompt_optimization import summarize_world_elements
    
    # The world_elements passed in are already filtered for scene relevance
    # by analyze_scene_entities, so we just use all of them
    selected_categories = list(world_elements.keys())[:3]  # Still limit to 3 for brevity
    
    # Use the optimization utility to create concise summaries
    world_summary = summarize_world_elements(
        world_elements, 
        relevant_categories=selected_categories,
        max_words_per_category=30
    )
    
    # Create the worldbuilding guidance section
    worldbuilding_sections = []
    for category, summary in world_summary.items():
        category_section = f"{category.upper()}: {summary}"
        worldbuilding_sections.append(category_section)
    
    # Combine the sections
    worldbuilding_details = "\n".join(worldbuilding_sections)
    
    # Get previously established elements
    previously_established = _get_previously_established_elements(world_elements)
    
    # Check if there are mystery elements to emphasize
    mystery_guidance = ""
    if mystery_relevance and "mystery_elements" in world_elements:
        key_mysteries = []
        if isinstance(world_elements["mystery_elements"], dict) and "key_mysteries" in world_elements["mystery_elements"]:
            key_mysteries = world_elements["mystery_elements"]["key_mysteries"]
        
        if key_mysteries:
            mystery_guidance = """
            MYSTERY ELEMENTS GUIDANCE:
            - Introduce mystery elements through character interactions rather than narrator explanation
            - Show characters' different perspectives on these elements
            - Create scenes where characters must interact with these elements
            """
    
    guidance = f"""
    WORLDBUILDING ELEMENTS TO INCORPORATE:
    Use these world details to enrich your scene naturally:
    
    {worldbuilding_details}
    {previously_established}
    {mystery_guidance}
    
    IMPORTANT: Weave these elements into the narrative naturally. Show them through:
    - Character observations and interactions
    - Environmental descriptions
    - Dialogue and character knowledge
    - Actions and their consequences
    Never info-dump or explain these elements directly to the reader.
    """
    
    return guidance