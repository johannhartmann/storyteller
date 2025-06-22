"""
Final manuscript review and polish functionality.
This module performs a comprehensive quality check and applies corrections to the complete story.
"""

from typing import Dict, List, Optional
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from storyteller_lib import track_progress
from storyteller_lib.config import llm, get_story_config
from storyteller_lib.database_integration import get_db_manager
from storyteller_lib.logger import get_logger
from storyteller_lib.prompt_templates import render_prompt
from storyteller_lib.models import StoryState
from storyteller_lib.progression import compile_story_content
from storyteller_lib.chapter_correction import correct_chapter

logger = get_logger(__name__)


class ChapterIssue(BaseModel):
    """Issue identified in a specific chapter."""
    chapter_number: int = Field(description="The chapter number")
    issues: List[str] = Field(description="List of issues found in the chapter")
    severity: str = Field(description="Severity level: critical, moderate, or minor")
    correction_instruction: str = Field(description="Specific instruction for correcting this chapter")


class ManuscriptReviewOutput(BaseModel):
    """Structured output for manuscript review."""
    overall_quality_score: float = Field(ge=1, le=10, description="Overall quality score (1-10)")
    overall_assessment: str = Field(description="Overall assessment of the manuscript")
    strengths: List[str] = Field(description="Manuscript strengths")
    chapter_issues: List[ChapterIssue] = Field(description="Issues found per chapter")


@track_progress
def review_and_polish_manuscript(state: StoryState) -> Dict:
    """
    Review the complete manuscript and apply corrections to improve quality.
    
    This function:
    1. Compiles the current story
    2. Analyzes it for quality issues
    3. Applies corrections chapter by chapter
    4. Recompiles the corrected story
    
    Args:
        state: The current story state
        
    Returns:
        Updated state with polished story
    """
    logger.info("Starting final manuscript review and polish")
    
    # Step 1: Compile the current story
    logger.info("Compiling manuscript for review...")
    manuscript = compile_story_content(state)
    
    # Get story configuration
    config = get_story_config()
    genre = config.get("genre", "fantasy")
    tone = config.get("tone", "adventurous")
    language = config.get("language", "english")
    
    # Get chapter count for context
    chapter_count = len(state.get("chapters", {}))
    
    # Step 2: Analyze the manuscript
    logger.info("Analyzing manuscript for quality issues...")
    
    # Render the review prompt
    review_prompt = render_prompt(
        'manuscript_review',
        language=language,
        manuscript=manuscript,
        genre=genre,
        tone=tone,
        chapter_count=chapter_count
    )
    
    # Get structured review output
    try:
        review_result = llm.with_structured_output(ManuscriptReviewOutput).invoke([HumanMessage(content=review_prompt)])
        
        if not review_result:
            logger.error("Failed to get review result")
            return {
                "final_story": manuscript,
                "manuscript_review_completed": True,
                "messages": [HumanMessage(content="Manuscript review completed but no issues found to correct.")]
            }
            
    except Exception as e:
        logger.error(f"Failed to review manuscript: {e}")
        # If review fails, return the original manuscript
        return {
            "final_story": manuscript,
            "manuscript_review_completed": True,
            "messages": [HumanMessage(content=f"Manuscript review failed: {e}. Returning original story.")]
        }
    
    # Log review results
    logger.info(f"Overall quality score: {review_result.overall_quality_score}/10")
    logger.info(f"Found {len(review_result.chapter_issues)} chapters with issues")
    
    # Step 3: Apply corrections
    corrections_applied = []
    correction_failures = []
    
    if review_result.chapter_issues:
        logger.info("Applying corrections to chapters...")
        
        # Sort by severity (critical first)
        severity_order = {"critical": 0, "moderate": 1, "minor": 2}
        sorted_issues = sorted(review_result.chapter_issues, 
                             key=lambda x: (severity_order.get(x.severity, 3), x.chapter_number))
        
        for chapter_issue in sorted_issues:
            chapter_num = chapter_issue.chapter_number
            logger.info(f"Correcting Chapter {chapter_num} ({chapter_issue.severity} issues)")
            
            try:
                # Apply correction using the existing correct_chapter function
                success = correct_chapter(chapter_num, chapter_issue.correction_instruction)
                
                if success:
                    corrections_applied.append({
                        "chapter": chapter_num,
                        "severity": chapter_issue.severity,
                        "issues": chapter_issue.issues
                    })
                    logger.info(f"Successfully corrected Chapter {chapter_num}")
                else:
                    correction_failures.append(chapter_num)
                    logger.error(f"Failed to correct Chapter {chapter_num}")
                    
            except Exception as e:
                correction_failures.append(chapter_num)
                logger.error(f"Error correcting Chapter {chapter_num}: {e}")
    
    # Step 4: Recompile the corrected story
    logger.info("Recompiling corrected manuscript...")
    final_polished_story = compile_story_content(state)
    
    # Create summary message
    summary_parts = [
        f"Manuscript Review Complete!",
        f"",
        f"Overall Quality Score: {review_result.overall_quality_score}/10",
        f"",
        f"Strengths:",
    ]
    
    for strength in review_result.strengths[:3]:  # Top 3 strengths
        summary_parts.append(f"- {strength}")
    
    if corrections_applied:
        summary_parts.extend([
            f"",
            f"Corrections Applied: {len(corrections_applied)} chapters improved"
        ])
        
        # Group by severity
        critical_count = sum(1 for c in corrections_applied if c["severity"] == "critical")
        moderate_count = sum(1 for c in corrections_applied if c["severity"] == "moderate")
        minor_count = sum(1 for c in corrections_applied if c["severity"] == "minor")
        
        if critical_count:
            summary_parts.append(f"- {critical_count} critical issues resolved")
        if moderate_count:
            summary_parts.append(f"- {moderate_count} moderate issues improved")
        if minor_count:
            summary_parts.append(f"- {minor_count} minor refinements")
    
    if correction_failures:
        summary_parts.extend([
            f"",
            f"Note: {len(correction_failures)} chapters could not be corrected automatically"
        ])
    
    summary_message = "\n".join(summary_parts)
    
    # Return updated state
    return {
        "final_story": final_polished_story,
        "manuscript_review_completed": True,
        "manuscript_review_results": {
            "overall_score": review_result.overall_quality_score,
            "assessment": review_result.overall_assessment,
            "corrections_applied": corrections_applied,
            "correction_failures": correction_failures
        },
        "messages": [HumanMessage(content=summary_message)]
    }