"""
Intelligent repetition analysis module for StoryCraft Agent.

This module provides context-aware repetition analysis that evaluates whether
repetition serves a narrative purpose rather than just counting occurrences.
"""

from typing import Dict, List, Any, Optional, Tuple
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from storyteller_lib.config import llm
from storyteller_lib.models import StoryState
from storyteller_lib.logger import get_logger

logger = get_logger(__name__)


class RepetitionPurpose(BaseModel):
    """Analysis of whether repetition serves a purpose."""
    
    element: str = Field(description="The repeated element")
    count: int = Field(description="Number of occurrences")
    serves_purpose: bool = Field(description="Whether the repetition serves a narrative purpose")
    purpose: Optional[str] = Field(description="The narrative purpose if applicable")
    recommendation: str = Field(description="Recommendation for this element")


class IntelligentRepetitionAnalysis(BaseModel):
    """Context-aware repetition analysis."""
    
    intentional_repetitions: List[RepetitionPurpose] = Field(
        default_factory=list,
        description="Repetitions that serve a narrative purpose"
    )
    unintentional_repetitions: List[RepetitionPurpose] = Field(
        default_factory=list,
        description="Repetitions that appear accidental or excessive"
    )
    overall_assessment: str = Field(
        description="Overall assessment of repetition in context"
    )
    genre_appropriate: bool = Field(
        description="Whether the repetition level is appropriate for the genre/tone"
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Context-aware suggestions for improvement"
    )


def analyze_repetition_in_context(
    text: str,
    genre: str,
    tone: str,
    author_style: Optional[str] = None,
    story_context: Optional[str] = None,
    language: str = "english"
) -> IntelligentRepetitionAnalysis:
    """
    Analyze repetition with awareness of genre, tone, and narrative purpose.
    
    Args:
        text: The text to analyze
        genre: Story genre
        tone: Story tone
        author_style: Optional author style being emulated
        story_context: Optional context about the story
        language: Language for analysis
        
    Returns:
        Intelligent repetition analysis
    """
    from storyteller_lib.prompt_templates import render_prompt
    
    # Create a comprehensive prompt for intelligent analysis
    prompt = render_prompt(
        'intelligent_repetition_analysis',
        language=language,
        text=text,
        genre=genre,
        tone=tone,
        author_style=author_style or "none specified",
        story_context=story_context or "not provided"
    )
    
    structured_llm = llm.with_structured_output(IntelligentRepetitionAnalysis)
    analysis = structured_llm.invoke(prompt)
    
    logger.info(f"Intelligent repetition analysis complete - {len(analysis.intentional_repetitions)} intentional, {len(analysis.unintentional_repetitions)} unintentional")
    
    return analysis


def evaluate_phrase_repetition(
    phrases: List[str],
    scene_content: str,
    scene_type: str,
    genre: str,
    tone: str,
    language: str = "english"
) -> Dict[str, Any]:
    """
    Evaluate whether specific phrase repetitions are problematic in context.
    
    Args:
        phrases: List of potentially repeated phrases
        scene_content: The scene content
        scene_type: Type of scene (action, dialogue, reflection, etc.)
        genre: Story genre
        tone: Story tone
        language: Language for analysis
        
    Returns:
        Evaluation of each phrase
    """
    from storyteller_lib.prompt_templates import render_prompt
    
    class PhraseEvaluation(BaseModel):
        """Evaluation of phrase repetition."""
        evaluations: List[Dict[str, Any]] = Field(
            description="List of phrase evaluations with 'phrase', 'problematic', and 'reason' keys"
        )
    
    prompt = render_prompt(
        'phrase_repetition_evaluation',
        language=language,
        phrases=phrases,
        scene_content=scene_content,
        scene_type=scene_type,
        genre=genre,
        tone=tone
    )
    
    try:
        structured_llm = llm.with_structured_output(PhraseEvaluation)
        result = structured_llm.invoke(prompt)
        
        # Convert to dictionary keyed by phrase
        evaluations = {}
        for eval_item in result.evaluations:
            evaluations[eval_item['phrase']] = {
                'problematic': eval_item['problematic'],
                'reason': eval_item['reason']
            }
        
        return evaluations
        
    except Exception as e:
        logger.error(f"Error evaluating phrase repetition: {e}")
        # Return all phrases as non-problematic on error
        return {phrase: {'problematic': False, 'reason': 'Evaluation failed'} for phrase in phrases}


def suggest_contextual_alternatives(
    repetitive_element: str,
    element_type: str,  # 'phrase', 'description', 'structure', 'character_trait'
    scene_context: str,
    genre: str,
    tone: str,
    language: str = "english"
) -> List[str]:
    """
    Generate context-appropriate alternatives for repetitive elements.
    
    Args:
        repetitive_element: The element that's repeated
        element_type: Type of element
        scene_context: Context where it appears
        genre: Story genre
        tone: Story tone
        language: Language for suggestions
        
    Returns:
        List of appropriate alternatives
    """
    from storyteller_lib.prompt_templates import render_prompt
    
    class Alternatives(BaseModel):
        """Alternative suggestions."""
        alternatives: List[str] = Field(
            description="List of context-appropriate alternatives"
        )
        usage_notes: str = Field(
            description="Notes on when/how to use these alternatives"
        )
    
    prompt = render_prompt(
        'contextual_alternatives',
        language=language,
        element=repetitive_element,
        element_type=element_type,
        context=scene_context,
        genre=genre,
        tone=tone
    )
    
    try:
        structured_llm = llm.with_structured_output(Alternatives)
        result = structured_llm.invoke(prompt)
        
        return result.alternatives
        
    except Exception as e:
        logger.error(f"Error generating alternatives: {e}")
        return []


def track_narrative_patterns(
    story_state: StoryState,
    current_chapter: int,
    current_scene: int
) -> Dict[str, Any]:
    """
    Track narrative patterns across the story to identify meaningful vs. problematic repetition.
    
    Args:
        story_state: Current story state
        current_chapter: Current chapter number
        current_scene: Current scene number
        
    Returns:
        Pattern analysis results
    """
    from storyteller_lib.database_integration import get_db_manager
    
    db_manager = get_db_manager()
    if not db_manager or not db_manager._db:
        logger.warning("Database not available for pattern tracking")
        return {}
    
    patterns = {
        'recurring_themes': [],
        'character_catchphrases': {},
        'stylistic_patterns': [],
        'structural_patterns': []
    }
    
    # Analyze patterns from database
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        
        # Get recent scenes for pattern analysis
        cursor.execute("""
            SELECT s.content, s.scene_number, c.chapter_number
            FROM scenes s
            JOIN chapters c ON s.chapter_id = c.id
            WHERE c.chapter_number <= ?
            ORDER BY c.chapter_number DESC, s.scene_number DESC
            LIMIT 10
        """, (current_chapter,))
        
        recent_scenes = cursor.fetchall()
        
        if recent_scenes:
            # Combine recent content for pattern analysis
            recent_content = "\n\n".join([scene['content'] for scene in recent_scenes])
            
            # Use LLM to identify patterns
            class CharacterCatchphrase(BaseModel):
                """Character catchphrase mapping."""
                character_name: str = Field(description="Name of the character")
                catchphrases: List[str] = Field(description="List of catchphrases for this character")
            
            class NarrativePatterns(BaseModel):
                """Identified narrative patterns."""
                recurring_themes: List[str] = Field(description="Themes that recur meaningfully")
                character_catchphrases: List[CharacterCatchphrase] = Field(
                    description="Character-specific repeated phrases",
                    default_factory=list
                )
                stylistic_patterns: List[str] = Field(
                    description="Recurring stylistic elements"
                )
                structural_patterns: List[str] = Field(
                    description="Recurring structural elements"
                )
            
            prompt = f"""
            Analyze these recent scenes to identify narrative patterns.
            Distinguish between:
            1. Meaningful recurring themes that build the story
            2. Character-defining catchphrases or speech patterns
            3. Intentional stylistic choices
            4. Structural patterns in scene construction
            
            Recent scenes:
            {recent_content[:3000]}  # Limit for context
            
            Focus on patterns that appear intentional rather than accidental repetition.
            """
            
            try:
                structured_llm = llm.with_structured_output(NarrativePatterns)
                patterns = structured_llm.invoke(prompt).dict()
            except Exception as e:
                logger.error(f"Error analyzing narrative patterns: {e}")
    
    return patterns


def generate_intelligent_variation_guidance(
    analysis: IntelligentRepetitionAnalysis,
    scene_type: str,
    genre: str,
    tone: str
) -> str:
    """
    Generate variation guidance based on intelligent analysis.
    
    Args:
        analysis: The intelligent repetition analysis
        scene_type: Type of scene being written
        genre: Story genre
        tone: Story tone
        
    Returns:
        Contextual variation guidance
    """
    # Only provide guidance if there are significant issues
    if not analysis.unintentional_repetitions or len(analysis.unintentional_repetitions) < 3:
        return ""
    
    # Keep guidance gentle and suggestive
    guidance_parts = ["GENTLE VARIATION SUGGESTIONS:"]
    
    # Only mention the most egregious repetitions
    major_repetitions = [r for r in analysis.unintentional_repetitions if r.count > 5]
    if major_repetitions:
        guidance_parts.append("\nYou might consider varying:")
        for rep in major_repetitions[:2]:  # Only top 2
            guidance_parts.append(f"- '{rep.element}' appears frequently - perhaps {rep.recommendation}")
    
    # Positive reinforcement takes precedence
    if analysis.intentional_repetitions:
        guidance_parts.append("\nNice use of repetition for effect:")
        for rep in analysis.intentional_repetitions[:2]:
            guidance_parts.append(f"- '{rep.element}' - {rep.purpose}")
    
    # Only return if we have substantial guidance
    if len(guidance_parts) > 1:
        return "\n".join(guidance_parts)
    return ""