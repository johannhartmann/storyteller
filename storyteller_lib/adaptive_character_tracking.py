"""
Adaptive character development tracking module for StoryCraft Agent.

This module tracks character development based on story promises and genre expectations
rather than enforcing rigid progression rules.
"""

from typing import Dict, List, Any, Optional, Tuple
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from storyteller_lib.config import llm
from storyteller_lib.models import StoryState
from storyteller_lib.logger import get_logger

logger = get_logger(__name__)


class CharacterPromise(BaseModel):
    """A promise made about a character's journey."""
    
    character_name: str = Field(description="Character's name")
    promise_type: str = Field(description="Type of promise (growth, revelation, relationship, etc.)")
    promise_description: str = Field(description="What was promised about this character")
    introduced_chapter: int = Field(description="Chapter where promise was introduced")
    expected_resolution: str = Field(description="Expected resolution timing (early, middle, late, ongoing)")
    fulfilled: bool = Field(default=False, description="Whether promise has been fulfilled")


class CharacterDevelopmentAssessment(BaseModel):
    """Assessment of character development progress."""
    
    character_name: str = Field(description="Character's name")
    development_appropriate: bool = Field(description="Whether development pace suits the story")
    current_state: str = Field(description="Character's current emotional/psychological state")
    promises_status: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Status of each promise made about this character"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Context-aware recommendations for this character"
    )
    genre_alignment: bool = Field(description="Whether development aligns with genre expectations")


class CharacterMomentAnalysis(BaseModel):
    """Analysis of a character moment's effectiveness."""
    
    moment_type: str = Field(description="Type of moment (revelation, growth, setback, etc.)")
    earned: bool = Field(description="Whether the moment feels earned")
    impact: str = Field(description="Impact on character arc")
    reader_satisfaction: str = Field(description="Likely reader satisfaction level")
    suggestions: List[str] = Field(default_factory=list, description="Improvement suggestions")


def identify_character_promises(
    story_outline: str,
    character_profiles: Dict[str, Any],
    genre: str,
    tone: str,
    language: str = "english"
) -> List[CharacterPromise]:
    """
    Identify implicit and explicit promises made about character development.
    
    Args:
        story_outline: The story outline
        character_profiles: Character information
        genre: Story genre
        tone: Story tone
        language: Language for analysis
        
    Returns:
        List of character promises
    """
    from storyteller_lib.prompt_templates import render_prompt
    
    class CharacterPromises(BaseModel):
        """Collection of character promises."""
        promises: List[CharacterPromise] = Field(default_factory=list)
    
    # Format character information
    characters_summary = []
    for name, profile in character_profiles.items():
        summary = f"{name}: {profile.get('role', 'Unknown role')} - {profile.get('arc', 'No arc specified')}"
        if 'personality' in profile:
            summary += f" - Personality: {profile['personality']}"
        characters_summary.append(summary)
    
    prompt = render_prompt(
        'identify_character_promises',
        language=language,
        story_outline=story_outline,
        characters="\n".join(characters_summary),
        genre=genre,
        tone=tone
    )
    
    try:
        structured_llm = llm.with_structured_output(CharacterPromises)
        result = structured_llm.invoke(prompt)
        
        logger.info(f"Identified {len(result.promises)} character promises")
        return result.promises
        
    except Exception as e:
        logger.error(f"Error identifying character promises: {e}")
        return []


def assess_character_development(
    character_name: str,
    character_history: List[Dict[str, Any]],
    character_promises: List[CharacterPromise],
    current_chapter: int,
    total_chapters: int,
    genre: str,
    tone: str,
    language: str = "english"
) -> CharacterDevelopmentAssessment:
    """
    Assess whether a character's development is appropriate for the story.
    
    Args:
        character_name: Name of the character
        character_history: List of character's appearances and changes
        character_promises: Promises made about this character
        current_chapter: Current chapter number
        total_chapters: Total planned chapters
        genre: Story genre
        tone: Story tone
        language: Language for analysis
        
    Returns:
        Character development assessment
    """
    from storyteller_lib.prompt_templates import render_prompt
    
    # Filter promises for this character
    relevant_promises = [p for p in character_promises if p.character_name == character_name]
    
    # Format character history
    history_summary = []
    for event in character_history[-10:]:  # Last 10 events
        summary = f"Chapter {event['chapter']}, Scene {event['scene']}: {event['description']}"
        if 'emotional_state' in event:
            summary += f" - State: {event['emotional_state']}"
        history_summary.append(summary)
    
    prompt = render_prompt(
        'assess_character_development',
        language=language,
        character_name=character_name,
        character_history="\n".join(history_summary),
        promises=[p.dict() for p in relevant_promises],
        current_chapter=current_chapter,
        total_chapters=total_chapters,
        story_progress_percentage=int((current_chapter / total_chapters) * 100),
        genre=genre,
        tone=tone
    )
    
    try:
        structured_llm = llm.with_structured_output(CharacterDevelopmentAssessment)
        assessment = structured_llm.invoke(prompt)
        
        return assessment
        
    except Exception as e:
        logger.error(f"Error assessing character development: {e}")
        return CharacterDevelopmentAssessment(
            character_name=character_name,
            development_appropriate=True,
            current_state="Unknown",
            promises_status=[],
            recommendations=[],
            genre_alignment=True
        )


def analyze_character_moment(
    scene_content: str,
    character_name: str,
    moment_description: str,
    character_history: List[Dict[str, Any]],
    genre: str,
    tone: str,
    language: str = "english"
) -> CharacterMomentAnalysis:
    """
    Analyze whether a specific character moment is earned and effective.
    
    Args:
        scene_content: The scene containing the moment
        character_name: Character experiencing the moment
        moment_description: Description of the moment
        character_history: Character's journey so far
        genre: Story genre
        tone: Story tone
        language: Language for analysis
        
    Returns:
        Analysis of the character moment
    """
    from storyteller_lib.prompt_templates import render_prompt
    
    # Summarize character journey
    journey_summary = []
    for event in character_history[-5:]:  # Last 5 significant events
        journey_summary.append(f"- {event['description']}")
    
    prompt = render_prompt(
        'analyze_character_moment',
        language=language,
        scene_excerpt=scene_content[:1000],
        character_name=character_name,
        moment_description=moment_description,
        character_journey="\n".join(journey_summary),
        genre=genre,
        tone=tone
    )
    
    try:
        structured_llm = llm.with_structured_output(CharacterMomentAnalysis)
        analysis = structured_llm.invoke(prompt)
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing character moment: {e}")
        return CharacterMomentAnalysis(
            moment_type="unknown",
            earned=True,
            impact="unclear",
            reader_satisfaction="uncertain",
            suggestions=[]
        )


def track_character_evolution(
    story_state: StoryState,
    current_chapter: int,
    current_scene: int
) -> Dict[str, Any]:
    """
    Track character evolution across the story.
    
    Args:
        story_state: Current story state
        current_chapter: Current chapter number
        current_scene: Current scene number
        
    Returns:
        Character evolution tracking data
    """
    from storyteller_lib.database_integration import get_db_manager
    
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        logger.warning("Database not available for character tracking")
        return {}
    
    evolution_data = {}
    
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        
        # Get all characters
        cursor.execute("SELECT identifier, name FROM characters")
        characters = cursor.fetchall()
        
        for char in characters:
            char_id = char['identifier']
            char_name = char['name']
            
            # Get character's emotional journey
            cursor.execute("""
                SELECT chapter_number, scene_number, emotional_state, knowledge_gained
                FROM character_states
                WHERE character_id = ?
                ORDER BY chapter_number, scene_number
            """, (char_id,))
            
            states = cursor.fetchall()
            
            # Analyze evolution pattern
            if states:
                evolution_data[char_name] = {
                    'total_appearances': len(states),
                    'emotional_journey': [s['emotional_state'] for s in states],
                    'knowledge_progression': [s['knowledge_gained'] for s in states if s['knowledge_gained']],
                    'static_periods': _identify_static_periods(states),
                    'major_changes': _identify_major_changes(states)
                }
    
    return evolution_data


def _identify_static_periods(states: List[Dict[str, Any]]) -> List[Tuple[int, int]]:
    """Identify periods where character remains static."""
    static_periods = []
    
    if len(states) < 2:
        return static_periods
    
    start_static = None
    prev_state = states[0]['emotional_state']
    
    for i, state in enumerate(states[1:], 1):
        if state['emotional_state'] == prev_state:
            if start_static is None:
                start_static = i - 1
        else:
            if start_static is not None and i - start_static > 2:
                static_periods.append((start_static, i - 1))
            start_static = None
            prev_state = state['emotional_state']
    
    return static_periods


def _identify_major_changes(states: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identify major character changes."""
    major_changes = []
    
    # This would use LLM to identify significant shifts
    # For now, return empty list
    return major_changes


def generate_character_development_guidance(
    character_name: str,
    assessment: CharacterDevelopmentAssessment,
    current_chapter: int,
    scene_type: str
) -> str:
    """
    Generate guidance for character development in the next scene.
    
    Args:
        character_name: Character's name
        assessment: Development assessment
        current_chapter: Current chapter
        scene_type: Type of scene being written
        
    Returns:
        Character development guidance
    """
    # Be very conservative with character development guidance
    # Most development should happen naturally
    
    # Only intervene if development is seriously off-track
    if assessment.development_appropriate:
        return ""
    
    # Keep guidance minimal and suggestive
    guidance_parts = []
    
    # Only mention if character has been completely static for many chapters
    static_chapters = sum(1 for p in assessment.promises_status if not p.get('progress', False))
    if static_chapters > 5:
        guidance_parts.append(f"GENTLE CHARACTER NOTE:")
        guidance_parts.append(f"{character_name} has remained quite consistent - a small shift might feel natural.")
    
    # Avoid pushing too hard on promises
    if scene_type in ['character', 'reflection'] and assessment.recommendations:
        guidance_parts.append(f"\nIf it feels right, {character_name} might: {assessment.recommendations[0]}")
        guidance_parts.append("But only if it serves this scene naturally.")
    
    return "\n".join(guidance_parts) if guidance_parts else ""