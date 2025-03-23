"""
StoryCraft Agent - Visualization tools for character relationships and arcs.
"""

from typing import Dict, Any, List, Optional
import json

def generate_character_network(characters: Dict[str, Any]) -> str:
    """
    Generate a Mermaid.js diagram showing character relationships.
    
    Args:
        characters: Dictionary of character data
        
    Returns:
        A string containing Mermaid.js markdown for a relationship diagram
    """
    mermaid_code = "```mermaid\ngraph TD\n"
    
    # Add nodes for each character
    for char_slug, char_data in characters.items():
        name = char_data.get("name", char_slug)
        role = char_data.get("role", "")
        mermaid_code += f'  {char_slug}["{name}<br/>{role}"]\n'
    
    # Add relationships
    for char_slug, char_data in characters.items():
        relationships = char_data.get("relationships", {})
        for other_char, rel_data in relationships.items():
            if other_char in characters:  # Only include relationships to characters that exist
                if isinstance(rel_data, dict):
                    rel_type = rel_data.get("type", "")
                    mermaid_code += f'  {char_slug} -->|"{rel_type}"| {other_char}\n'
                else:
                    mermaid_code += f'  {char_slug} -->|"{rel_data}"| {other_char}\n'
    
    mermaid_code += "```"
    return mermaid_code

def generate_character_arc_diagram(character: Dict[str, Any]) -> str:
    """
    Generate a Mermaid.js diagram showing a character's emotional arc.
    
    Args:
        character: Character data dictionary
        
    Returns:
        A string containing Mermaid.js markdown for an arc diagram
    """
    # Extract character information
    name = character.get("name", "Character")
    arc_type = character.get("character_arc", {}).get("type", "undefined")
    arc_stages = character.get("character_arc", {}).get("stages", [])
    current_stage = character.get("character_arc", {}).get("current_stage", "")
    emotional_journey = character.get("emotional_state", {}).get("journey", [])
    
    # Create a timeline diagram
    mermaid_code = f"```mermaid\njourney\n  title {name}'s {arc_type.capitalize()} Arc\n"
    
    # Add sections for each stage
    completed_stages = []
    future_stages = []
    found_current = False
    
    for stage in arc_stages:
        if stage == current_stage:
            found_current = True
        
        if not found_current and stage != current_stage:
            completed_stages.append(stage)
        elif stage != current_stage:
            future_stages.append(stage)
    
    # Add completed stages
    for i, stage in enumerate(completed_stages):
        mermaid_code += f"  section {stage}\n"
        mermaid_code += f"    Completed: 5: done\n"
    
    # Add current stage
    if current_stage:
        mermaid_code += f"  section {current_stage}\n"
        mermaid_code += f"    In progress: 3: active\n"
    
    # Add future stages
    for i, stage in enumerate(future_stages):
        mermaid_code += f"  section {stage}\n"
        mermaid_code += f"    Future: 1: future\n"
    
    mermaid_code += "```"
    return mermaid_code

def generate_emotional_journey_chart(character: Dict[str, Any]) -> str:
    """
    Generate a Mermaid.js diagram showing a character's emotional journey.
    
    Args:
        character: Character data dictionary
        
    Returns:
        A string containing Mermaid.js markdown for an emotional journey chart
    """
    # Extract character information
    name = character.get("name", "Character")
    journey = character.get("emotional_state", {}).get("journey", [])
    
    if not journey:
        return f"No emotional journey data available for {name}"
    
    # Create a timeline diagram
    mermaid_code = f"```mermaid\ngantt\n  title {name}'s Emotional Journey\n"
    mermaid_code += "  dateFormat X\n"
    mermaid_code += "  axisFormat %s\n"
    
    # Add sections for each emotional state
    for i, entry in enumerate(journey):
        # Extract chapter and scene if available
        chapter_scene = "unknown"
        if entry.startswith("Ch") and "-Sc" in entry:
            chapter_scene = entry.split(":")[0].strip()
            emotion = ":".join(entry.split(":")[1:]).strip()
        else:
            emotion = entry
        
        mermaid_code += f"  section {chapter_scene}\n"
        mermaid_code += f"  {emotion}: {i}, {i+1}\n"
    
    mermaid_code += "```"
    return mermaid_code

def generate_inner_conflict_diagram(character: Dict[str, Any]) -> str:
    """
    Generate a Mermaid.js diagram showing a character's inner conflicts.
    
    Args:
        character: Character data dictionary
        
    Returns:
        A string containing Mermaid.js markdown for an inner conflict diagram
    """
    # Extract character information
    name = character.get("name", "Character")
    conflicts = character.get("inner_conflicts", [])
    
    if not conflicts:
        return f"No inner conflict data available for {name}"
    
    # Create a pie chart for conflict resolution status
    mermaid_code = f"```mermaid\npie title {name}'s Inner Conflicts\n"
    
    # Count conflicts by resolution status
    status_counts = {"unresolved": 0, "in_progress": 0, "resolved": 0}
    for conflict in conflicts:
        status = conflict.get("resolution_status", "unresolved")
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # Add slices to the pie chart
    for status, count in status_counts.items():
        if count > 0:
            mermaid_code += f'  "{status.capitalize()}": {count}\n'
    
    mermaid_code += "```"
    
    # Add a list of conflicts
    conflict_list = f"## {name}'s Inner Conflicts\n\n"
    for i, conflict in enumerate(conflicts):
        description = conflict.get("description", "Undefined conflict")
        status = conflict.get("resolution_status", "unresolved")
        impact = conflict.get("impact", "Unknown impact")
        
        status_emoji = "❓"
        if status == "unresolved":
            status_emoji = "❌"
        elif status == "in_progress":
            status_emoji = "⚙️"
        elif status == "resolved":
            status_emoji = "✅"
        
        conflict_list += f"### Conflict {i+1}: {description}\n"
        conflict_list += f"- Status: {status_emoji} {status.capitalize()}\n"
        conflict_list += f"- Impact: {impact}\n\n"
    
    return mermaid_code + "\n\n" + conflict_list

def generate_character_summary(character: Dict[str, Any]) -> str:
    """
    Generate a comprehensive character summary with visualizations.
    
    Args:
        character: Character data dictionary
        
    Returns:
        A string containing a markdown summary with embedded Mermaid.js diagrams
    """
    # Extract character information
    name = character.get("name", "Character")
    role = character.get("role", "Unknown role")
    backstory = character.get("backstory", "No backstory available")
    
    # Create the summary
    summary = f"# Character Summary: {name}\n\n"
    summary += f"**Role:** {role}\n\n"
    
    # Add personality section
    personality = character.get("personality", {})
    if personality:
        summary += "## Personality\n\n"
        
        # Traits
        traits = personality.get("traits", [])
        if traits:
            summary += "**Traits:** " + ", ".join(traits) + "\n\n"
        
        # Strengths
        strengths = personality.get("strengths", [])
        if strengths:
            summary += "**Strengths:** " + ", ".join(strengths) + "\n\n"
        
        # Flaws
        flaws = personality.get("flaws", [])
        if flaws:
            summary += "**Flaws:** " + ", ".join(flaws) + "\n\n"
        
        # Fears
        fears = personality.get("fears", [])
        if fears:
            summary += "**Fears:** " + ", ".join(fears) + "\n\n"
        
        # Desires
        desires = personality.get("desires", [])
        if desires:
            summary += "**Desires:** " + ", ".join(desires) + "\n\n"
        
        # Values
        values = personality.get("values", [])
        if values:
            summary += "**Values:** " + ", ".join(values) + "\n\n"
    
    # Add backstory
    summary += f"## Backstory\n\n{backstory}\n\n"
    
    # Add character arc diagram
    summary += "## Character Arc\n\n"
    summary += generate_character_arc_diagram(character) + "\n\n"
    
    # Add emotional journey chart
    summary += "## Emotional Journey\n\n"
    emotional_journey = generate_emotional_journey_chart(character)
    summary += emotional_journey + "\n\n"
    
    # Add inner conflicts
    summary += "## Inner Conflicts\n\n"
    conflict_diagram = generate_inner_conflict_diagram(character)
    summary += conflict_diagram + "\n\n"
    
    return summary