"""
StoryCraft Agent - Character arc tracking and management.
"""

from typing import Dict, List, Any, Optional
import json
from langchain_core.messages import HumanMessage
from storyteller_lib.config import llm, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from pydantic import BaseModel, Field


# Pydantic models for character arc planning
class CharacterArcStage(BaseModel):
    """A single stage in a character's arc."""
    stage_name: str = Field(description="Name of the arc stage")
    description: str = Field(description="What happens in this stage")
    emotional_state: str = Field(description="Character's emotional state in this stage")
    turning_point: str = Field(description="Key moment or realization")


class CharacterArcPlan(BaseModel):
    """Complete character arc plan."""
    character_name: str = Field(description="Name of the character")
    arc_type: str = Field(description="Type of arc (positive change, negative change, flat, circular)")
    arc_stages: List[CharacterArcStage] = Field(description="Stages of the character arc")
    relationship_dynamics: Dict[str, str] = Field(description="How relationships evolve")
    thematic_connection: str = Field(description="How the arc reflects story themes")
    emotional_journey_summary: str = Field(description="Summary of emotional progression")


class CharacterArcPlans(BaseModel):
    """Collection of character arc plans."""
    character_arcs: List[CharacterArcPlan] = Field(description="List of character arc plans")


def plan_character_arcs(characters: Dict[str, Any], story_outline: str, genre: str, tone: str,
                       theme: str = "", author_style: str = "", language: str = DEFAULT_LANGUAGE) -> Dict[str, Any]:
    """
    Plan comprehensive character arcs for all major characters in the story.
    
    This function uses the character_arc template to create detailed development
    plans for each character, including arc types, stages, and emotional journeys.
    
    Args:
        characters: Dictionary of character data
        story_outline: The overall story outline
        genre: Story genre
        tone: Story tone
        theme: Story theme (optional)
        author_style: Author style guidance (optional)
        language: Target language for generation
        
    Returns:
        Dictionary containing character arc plans for all characters
    """
    # Use the template system
    from storyteller_lib.prompt_templates import render_prompt
    
    # Prepare character data for template
    characters_data = {}
    for char_id, char_data in characters.items():
        char_info = {
            "role": char_data.get("role", "Unknown"),
            "initial_state": char_data.get("emotional_state", {}).get("initial", "Unknown"),
            "backstory": char_data.get("backstory", ""),
            "traits": char_data.get("personality", {}).get("traits", []),
            "inner_conflicts": [
                conflict.get("description", "") 
                for conflict in char_data.get("inner_conflicts", [])
            ]
        }
        characters_data[char_data.get("name", char_id)] = char_info
    
    # Render the prompt
    prompt = render_prompt(
        'character_arc',
        language=language,
        genre=genre,
        tone=tone,
        theme=theme,
        story_outline=story_outline,
        characters=characters_data,
        author_style=author_style if author_style else None
    )
    
    try:
        # Use structured output for comprehensive arc planning
        structured_llm = llm.with_structured_output(CharacterArcPlans)
        result = structured_llm.invoke(prompt)
        
        # Convert to dictionary format
        arc_plans = {}
        for arc_plan in result.character_arcs:
            arc_plans[arc_plan.character_name] = {
                "arc_type": arc_plan.arc_type,
                "stages": [stage.dict() for stage in arc_plan.arc_stages],
                "relationship_dynamics": arc_plan.relationship_dynamics,
                "thematic_connection": arc_plan.thematic_connection,
                "emotional_journey_summary": arc_plan.emotional_journey_summary
            }
        
        return arc_plans
        
    except Exception as e:
        print(f"Error planning character arcs: {e}")
        # Fallback: create basic arc plans
        arc_plans = {}
        for char_id, char_data in characters.items():
            char_name = char_data.get("name", char_id)
            arc_plans[char_name] = {
                "arc_type": "growth",
                "stages": [
                    {
                        "stage_name": "Beginning",
                        "description": "Character introduced with limitations",
                        "emotional_state": "Unaware or resistant",
                        "turning_point": "Inciting incident"
                    },
                    {
                        "stage_name": "Middle",
                        "description": "Character faces challenges",
                        "emotional_state": "Struggling but learning",
                        "turning_point": "Major setback or revelation"
                    },
                    {
                        "stage_name": "End",
                        "description": "Character overcomes or succumbs",
                        "emotional_state": "Transformed",
                        "turning_point": "Final test"
                    }
                ],
                "relationship_dynamics": {},
                "thematic_connection": "Reflects story's central theme",
                "emotional_journey_summary": "From limitation to growth"
            }
        
        return arc_plans


def identify_character_arc_type(character_data: Dict[str, Any]) -> str:
    """
    Identify the most appropriate character arc type based on character data.
    
    Common arc types:
    - Redemption: Character overcomes moral failing
    - Fall: Character succumbs to negative traits
    - Growth: Character develops and improves
    - Flat: Character remains essentially unchanged
    - Transformation: Character fundamentally changes identity
    - Disillusionment: Character loses idealism
    - Education: Character gains new understanding
    
    Args:
        character_data: The character data dictionary
        
    Returns:
        The identified arc type as a string
    """
    # Extract relevant character information
    backstory = character_data.get("backstory", "")
    personality = character_data.get("personality", {})
    flaws = personality.get("flaws", [])
    fears = personality.get("fears", [])
    desires = personality.get("desires", [])
    
    # If character already has an arc type defined, use it
    if "character_arc" in character_data and "type" in character_data["character_arc"]:
        return character_data["character_arc"]["type"]
    
    # Use LLM to identify the most appropriate arc type
    prompt = f"""
    Based on this character information:
    
    Backstory: {backstory}
    Flaws: {', '.join(flaws)}
    Fears: {', '.join(fears)}
    Desires: {', '.join(desires)}
    
    Identify the most appropriate character arc type from the following options:
    - Redemption: Character overcomes moral failing or past mistake
    - Fall: Character succumbs to negative traits or temptation
    - Growth: Character develops and improves as a person
    - Flat: Character remains essentially unchanged but affects others
    - Transformation: Character fundamentally changes identity or beliefs
    - Disillusionment: Character loses idealism or innocence
    - Education: Character gains new understanding or wisdom
    
    Respond with ONLY the arc type name, nothing else.
    """
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)]).content.strip()
        # Extract just the arc type name if there's additional text
        for arc_type in ["Redemption", "Fall", "Growth", "Flat", "Transformation", "Disillusionment", "Education"]:
            if arc_type.lower() in response.lower():
                return arc_type.lower()
        return "growth"  # Default to growth if no match found
    except Exception:
        # Default to growth arc if LLM fails
        return "growth"

def define_arc_stages(arc_type: str, character_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Define the expected stages for a character's arc based on the arc type.
    
    Returns a list of stage definitions with expected emotional states,
    challenges, and growth points.
    
    Args:
        arc_type: The type of character arc
        character_data: The character data dictionary
        
    Returns:
        A list of stage definitions
    """
    # Define common stage patterns for different arc types
    arc_stage_patterns = {
        "redemption": [
            {"name": "Establishment of flaw", "emotional_state": "Denial or justification"},
            {"name": "Inciting incident", "emotional_state": "Defensive or resistant"},
            {"name": "Recognition of flaw", "emotional_state": "Guilt or shame"},
            {"name": "Struggle with change", "emotional_state": "Conflicted or determined"},
            {"name": "Sacrifice or atonement", "emotional_state": "Acceptance or resolve"},
            {"name": "Redemption achieved", "emotional_state": "Peace or new purpose"}
        ],
        "fall": [
            {"name": "Initial virtue", "emotional_state": "Principled or idealistic"},
            {"name": "Temptation introduced", "emotional_state": "Curious or conflicted"},
            {"name": "First compromise", "emotional_state": "Rationalization or guilt"},
            {"name": "Deeper corruption", "emotional_state": "Power or pleasure seeking"},
            {"name": "Point of no return", "emotional_state": "Embracing darkness"},
            {"name": "Complete fall", "emotional_state": "Transformed by corruption"}
        ],
        "growth": [
            {"name": "Limited awareness", "emotional_state": "Complacent or frustrated"},
            {"name": "Challenge to worldview", "emotional_state": "Confused or resistant"},
            {"name": "Experimentation", "emotional_state": "Curious or tentative"},
            {"name": "Gathering wisdom", "emotional_state": "Reflective or determined"},
            {"name": "Integration", "emotional_state": "Accepting or empowered"},
            {"name": "New mastery", "emotional_state": "Confident or peaceful"}
        ],
        "flat": [
            {"name": "Established character", "emotional_state": "Consistent"},
            {"name": "Tested by events", "emotional_state": "Challenged but resilient"},
            {"name": "Reinforcement of traits", "emotional_state": "Steadfast"},
            {"name": "Influence on others", "emotional_state": "Impactful"},
            {"name": "Return to equilibrium", "emotional_state": "Unchanged but affecting change"}
        ],
        "transformation": [
            {"name": "Original identity", "emotional_state": "Established but limited"},
            {"name": "Catalyst for change", "emotional_state": "Shocked or destabilized"},
            {"name": "Identity crisis", "emotional_state": "Confused or searching"},
            {"name": "Exploration of new identity", "emotional_state": "Experimental or adaptive"},
            {"name": "Rebirth", "emotional_state": "Emerging new self"},
            {"name": "Integration of new identity", "emotional_state": "Transformed and authentic"}
        ],
        "disillusionment": [
            {"name": "Idealism", "emotional_state": "Hopeful or naive"},
            {"name": "First cracks", "emotional_state": "Doubtful or concerned"},
            {"name": "Confrontation with reality", "emotional_state": "Shocked or betrayed"},
            {"name": "Cynicism", "emotional_state": "Bitter or angry"},
            {"name": "Acceptance of reality", "emotional_state": "Resigned or pragmatic"},
            {"name": "New perspective", "emotional_state": "Wiser or more nuanced"}
        ],
        "education": [
            {"name": "Ignorance", "emotional_state": "Unaware or mistaken"},
            {"name": "Introduction to new information", "emotional_state": "Curious or skeptical"},
            {"name": "Resistance to learning", "emotional_state": "Defensive or confused"},
            {"name": "Gradual acceptance", "emotional_state": "Opening up or questioning"},
            {"name": "Integration of knowledge", "emotional_state": "Enlightened or humbled"},
            {"name": "Application of wisdom", "emotional_state": "Confident or thoughtful"}
        ]
    }
    
    # Get the appropriate stages for the arc type, defaulting to growth
    arc_type = arc_type.lower()
    stages = arc_stage_patterns.get(arc_type, arc_stage_patterns["growth"])
    
    # If character already has stages defined, use those instead
    if "character_arc" in character_data and "stages" in character_data["character_arc"]:
        existing_stages = character_data["character_arc"]["stages"]
        if existing_stages and isinstance(existing_stages, list):
            return [{"name": stage, "emotional_state": "Varies"} for stage in existing_stages]
    
    return stages

def update_character_arc(character: Dict[str, Any], scene_content: str, chapter_num: str, scene_num: str) -> Dict[str, Any]:
    """
    Update a character's arc based on developments in a scene.
    
    Args:
        character: The character data
        scene_content: The content of the scene
        chapter_num: The chapter number
        scene_num: The scene number
        
    Returns:
        Updated character data with arc progression
    """
    # Initialize character arc if it doesn't exist
    if "character_arc" not in character:
        arc_type = identify_character_arc_type(character)
        character["character_arc"] = {
            "type": arc_type,
            "stages": [stage["name"] for stage in define_arc_stages(arc_type, character)],
            "current_stage": ""
        }
    
    # Initialize emotional state if it doesn't exist
    if "emotional_state" not in character:
        character["emotional_state"] = {
            "initial": "Not specified",
            "current": "Not specified",
            "journey": []
        }
    
    # Initialize inner conflicts if they don't exist
    if "inner_conflicts" not in character:
        character["inner_conflicts"] = []
    
    # Extract character name for the prompt
    character_name = character.get("name", "Character")
    
    # Prepare the prompt for analyzing character development in the scene
    prompt = f"""
    Analyze the character development for {character_name} in this scene from Chapter {chapter_num}, Scene {scene_num}:
    
    {scene_content}
    
    Current character information:
    - Arc type: {character["character_arc"].get("type", "Not specified")}
    - Current arc stage: {character["character_arc"].get("current_stage", "Not specified")}
    - Current emotional state: {character["emotional_state"].get("current", "Not specified")}
    - Inner conflicts: {json.dumps(character.get("inner_conflicts", []))}
    
    Provide the following information in JSON format:
    1. Has the character progressed to a new stage in their arc? If so, which one?
    2. Has their emotional state changed? If so, how?
    3. Have any inner conflicts developed, progressed, or been resolved?
    4. Any new emotional experiences that should be added to their journey?
    Format your response as a valid JSON object with these keys:
    {{
        "new_arc_stage": "Stage name or empty if unchanged",
        "emotional_state_update": "New emotional state or empty if unchanged",
        "inner_conflict_updates": [
            {{
                "conflict_index": 0,
                "description": "Description of conflict",
                "resolution_status": "unresolved|in_progress|resolved",
                "impact": "How this affects the character"
            }}
        ],
        "emotional_journey_addition": "New emotional experience to add to journey or empty"
    }}
    """
    
    try:
        # Get the analysis from the LLM
        from typing import Optional, List
        from pydantic import BaseModel, Field
        
        # Define a Pydantic model for character arc updates
        class InnerConflictUpdate(BaseModel):
            """Update to a character's inner conflict."""
            
            conflict_index: int = Field(
                default=0,
                description="Index of the conflict to update, or -1 for new"
            )
            description: str = Field(
                default="",
                description="Description of the conflict"
            )
            resolution_status: str = Field(
                default="unresolved",
                description="Resolution status: unresolved, in_progress, or resolved"
            )
            impact: str = Field(
                default="",
                description="How this affects the character"
            )
            
            class Config:
                """Configuration for the model."""
                extra = "ignore"  # Ignore extra fields
        
        class CharacterArcUpdate(BaseModel):
            """Character arc updates after a scene."""
            
            new_arc_stage: Optional[str] = Field(
                default="",
                description="The new character arc stage after this scene"
            )
            emotional_state_update: Optional[str] = Field(
                default="",
                description="The updated emotional state of the character"
            )
            inner_conflict_updates: List[InnerConflictUpdate] = Field(
                default_factory=list,
                description="Updates to the character's inner conflicts"
            )
            emotional_journey_addition: Optional[str] = Field(
                default="",
                description="New entry for the character's emotional journey"
            )
            
            class Config:
                """Configuration for the model."""
                extra = "ignore"  # Ignore extra fields
        
        # Create a structured LLM that outputs a CharacterArcUpdate object
        structured_llm = llm.with_structured_output(CharacterArcUpdate)
        
        # Use the structured LLM to extract updates
        updates = structured_llm.invoke(prompt)
        
        # Convert Pydantic model to dictionary
        updates_dict = updates.dict()
        
        if not any(updates_dict.values()):
            return {}  # No updates if all fields are empty
        
        # Prepare the character updates
        character_updates = {}
        
        # Update arc stage if provided
        if updates_dict["new_arc_stage"]:
            character_updates["character_arc"] = character.get("character_arc", {}).copy()
            character_updates["character_arc"]["current_stage"] = updates_dict["new_arc_stage"]
        
        # Update emotional state if provided
        if updates_dict["emotional_state_update"]:
            character_updates["emotional_state"] = character.get("emotional_state", {}).copy()
            character_updates["emotional_state"]["current"] = updates_dict["emotional_state_update"]
        
        # Add to emotional journey if provided
        if updates_dict["emotional_journey_addition"]:
            if "emotional_state" not in character_updates:
                character_updates["emotional_state"] = character.get("emotional_state", {}).copy()
            
            journey = character_updates["emotional_state"].get("journey", []).copy()
            journey.append(f"Ch{chapter_num}-Sc{scene_num}: {updates_dict['emotional_journey_addition']}")
            character_updates["emotional_state"]["journey"] = journey
        
        # Update inner conflicts if provided
        if updates_dict.get("inner_conflict_updates") and isinstance(updates_dict["inner_conflict_updates"], list):
            inner_conflicts = character.get("inner_conflicts", []).copy()
            
            for conflict_update in updates_dict["inner_conflict_updates"]:
                if conflict_update.get("conflict_index", -1) == -1:
                    # Add new conflict
                    inner_conflicts.append({
                        "description": conflict_update.get("description", ""),
                        "resolution_status": conflict_update.get("resolution_status", "unresolved"),
                        "impact": conflict_update.get("impact", "")
                    })
                else:
                    # Update existing conflict
                    index = conflict_update.get("conflict_index", 0)
                    if 0 <= index < len(inner_conflicts):
                        if "description" in conflict_update:
                            inner_conflicts[index]["description"] = conflict_update["description"]
                        if "resolution_status" in conflict_update:
                            inner_conflicts[index]["resolution_status"] = conflict_update["resolution_status"]
                        if "impact" in conflict_update:
                            inner_conflicts[index]["impact"] = conflict_update["impact"]
            
            character_updates["inner_conflicts"] = inner_conflicts
        
        return character_updates
    
    except Exception as e:
        print(f"Error updating character arc: {str(e)}")
        return {}

def evaluate_arc_consistency(character: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate whether a character's development is consistent with their defined arc.
    
    Returns evaluation results with any inconsistencies or suggestions.
    
    Args:
        character: The character data dictionary
        
    Returns:
        Evaluation results dictionary
    """
    # Extract character information
    character_name = character.get("name", "Character")
    arc_type = character.get("character_arc", {}).get("type", "")
    current_stage = character.get("character_arc", {}).get("current_stage", "")
    stages = character.get("character_arc", {}).get("stages", [])
    emotional_journey = character.get("emotional_state", {}).get("journey", [])
    inner_conflicts = character.get("inner_conflicts", [])
    
    # Prepare the prompt for evaluating arc consistency
    prompt = f"""
    Evaluate the consistency of {character_name}'s character arc:
    
    Character arc type: {arc_type}
    Current stage: {current_stage}
    Arc stages: {stages}
    Emotional journey: {emotional_journey}
    Inner conflicts: {json.dumps(inner_conflicts)}
    
    Analyze the following:
    1. Is the character's progression through arc stages logical and consistent?
    2. Do the emotional states align with the expected arc type?
    3. Are inner conflicts developing in a way that supports the character arc?
    4. Are there any gaps or inconsistencies in the character's development?
    5. What suggestions would improve the character's arc?
    
    Format your response as a valid JSON object:
    {{
        "consistency_score": 1-10,
        "strengths": ["Strength 1", "Strength 2"],
        "inconsistencies": ["Inconsistency 1", "Inconsistency 2"],
        "suggestions": ["Suggestion 1", "Suggestion 2"],
        "next_logical_developments": ["Development 1", "Development 2"]
    }}
    """
    
    try:
        from typing import List
        from pydantic import BaseModel, Field
        
        # Define a Pydantic model for character arc evaluation
        class CharacterArcEvaluation(BaseModel):
            """Evaluation of a character's arc development."""
            
            consistency_score: int = Field(
                ge=1, le=10,
                description="Score from 1-10 indicating how consistent the character's arc development is"
            )
            strengths: List[str] = Field(
                description="List of strengths in the character's arc development"
            )
            inconsistencies: List[str] = Field(
                description="List of inconsistencies or issues in the character's arc development"
            )
            suggestions: List[str] = Field(
                description="List of suggestions to improve the character's arc"
            )
            next_logical_developments: List[str] = Field(
                description="List of logical next developments for the character's arc"
            )
        
        # Create a structured LLM that outputs a CharacterArcEvaluation object
        structured_llm = llm.with_structured_output(CharacterArcEvaluation)
        
        # Use the structured LLM to get the evaluation
        evaluation = structured_llm.invoke(prompt)
        
        # Convert Pydantic model to dictionary
        evaluation_dict = evaluation.dict()
        
        if not evaluation_dict:
            # Return a default evaluation if parsing failed
            return {
                "consistency_score": 7,
                "strengths": ["Character has a defined arc"],
                "inconsistencies": [],
                "suggestions": ["Consider adding more emotional depth"],
                "next_logical_developments": ["Continue current arc progression"]
            }
        
        return evaluation_dict
    
    except Exception as e:
        print(f"Error evaluating character arc consistency: {str(e)}")
        return {
            "consistency_score": 7,
            "strengths": ["Character has a defined arc"],
            "inconsistencies": [],
            "suggestions": ["Consider adding more emotional depth"],
            "next_logical_developments": ["Continue current arc progression"]
        }