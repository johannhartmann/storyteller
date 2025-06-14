"""Helper functions for scene generation.

This module contains utility functions used by both scene writing and reflection.
"""

# Standard library imports
from typing import Any, Dict, List

# Local imports
from storyteller_lib.scene_brainstorm import _prepare_creative_guidance, _prepare_plot_thread_guidance


def _identify_relevant_world_categories(chapter_outline: str, world_elements: Dict) -> List[str]:
    """Identify which world categories are most relevant for the current scene.
    
    Args:
        chapter_outline: The chapter outline text
        world_elements: Dictionary of world building elements
        
    Returns:
        List of relevant category names
    """
    relevant_categories = []
    
    # Keywords that suggest relevance for each category
    category_keywords = {
        "geography": ["location", "place", "travel", "journey", "landscape", "terrain", "weather", "climate"],
        "history": ["past", "history", "ancient", "tradition", "legacy", "ancestor", "founding", "origin"],
        "politics": ["power", "rule", "govern", "law", "authority", "council", "king", "queen", "noble"],
        "economy": ["trade", "merchant", "gold", "coin", "market", "shop", "business", "wealth"],
        "culture": ["custom", "tradition", "festival", "ritual", "ceremony", "belief", "art", "music"],
        "magic_system": ["magic", "spell", "enchant", "wizard", "sorcerer", "power", "mystic", "arcane"],
        "technology": ["device", "machine", "invention", "construct", "mechanism", "tool", "gear", "engine"],
        "religion": ["god", "goddess", "divine", "priest", "temple", "faith", "prayer", "sacred"],
        "social_structure": ["class", "caste", "noble", "common", "servant", "hierarchy", "status", "rank"]
    }
    
    outline_lower = chapter_outline.lower()
    
    # Check each category for keyword matches
    for category, keywords in category_keywords.items():
        if category in world_elements:
            # Check if any keywords appear in the outline
            for keyword in keywords:
                if keyword in outline_lower:
                    relevant_categories.append(category)
                    break
    
    # Always include geography if it exists (location is fundamental)
    if "geography" in world_elements and "geography" not in relevant_categories:
        relevant_categories.insert(0, "geography")
    
    return relevant_categories


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


def _prepare_worldbuilding_guidance(world_elements: Dict, chapter_outline: str, mystery_relevance: bool = False) -> str:
    """Prepare worldbuilding guidance for scene writing.
    
    Args:
        world_elements: Dictionary of world building elements
        chapter_outline: The chapter outline
        mystery_relevance: Whether mystery elements are relevant
        
    Returns:
        Formatted worldbuilding guidance string
    """
    if not world_elements:
        return ""
    
    # Identify which categories are most relevant for this chapter
    relevant_categories = _identify_relevant_world_categories(chapter_outline, world_elements)
    
    if not relevant_categories:
        return ""
    
    # Limit to at most 3 most relevant categories to avoid overwhelming the prompt
    if len(relevant_categories) > 3:
        # Geography is most important, so keep it if it's there
        if "geography" in relevant_categories:
            relevant_categories.remove("geography")
            selected_categories = ["geography"] + relevant_categories[:2]
        else:
            selected_categories = relevant_categories[:3]
    else:
        selected_categories = relevant_categories
    
    # Create the worldbuilding guidance section
    worldbuilding_sections = []
    for category in selected_categories:
        if category in world_elements:
            category_elements = world_elements[category]
            category_section = f"{category.upper()}:\n"
            
            for key, value in category_elements.items():
                if isinstance(value, list) and value:
                    # For lists, include the first 2-3 items
                    items_to_include = value[:min(3, len(value))]
                    # Ensure all items are strings
                    items_str = [str(item) for item in items_to_include]
                    category_section += f"- {key.replace('_', ' ').title()}: {', '.join(items_str)}\n"
                elif value:
                    # For strings or other values
                    category_section += f"- {key.replace('_', ' ').title()}: {value}\n"
            
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