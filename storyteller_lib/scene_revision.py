"""Scene revision module for StoryCraft Agent.

This module handles revising scenes based on reflection feedback,
implementing improvements while maintaining story consistency.
"""

# Standard library imports
import json
from typing import Any, Dict, List

# Third party imports
from langchain_core.messages import HumanMessage

# Local imports
from storyteller_lib import track_progress
from storyteller_lib.config import (
    DEFAULT_LANGUAGE, MEMORY_NAMESPACE, SUPPORTED_LANGUAGES,
    llm
)
from storyteller_lib.constants import NodeNames, RevisionTypes
from storyteller_lib.models import StoryState
from storyteller_lib.story_context import get_context_provider


def _prepare_revision_guidance(reflection: Dict, scene_content: str) -> str:
    """Prepare specific guidance for scene revision based on reflection.
    
    Args:
        reflection: Reflection analysis results
        scene_content: Current scene content
        
    Returns:
        Formatted revision guidance string
    """
    guidance_parts = []
    
    # Add priority fixes
    if "priority_fixes" in reflection.get("revision_recommendation", {}):
        fixes = reflection["revision_recommendation"]["priority_fixes"]
        if fixes:
            guidance_parts.append("PRIORITY FIXES:\n" + "\n".join(f"- {fix}" for fix in fixes))
    
    # Add specific issues to address
    if "issues" in reflection and reflection["issues"]:
        issue_guidance = "SPECIFIC ISSUES TO ADDRESS:"
        for issue in reflection["issues"]:
            issue_type = issue.get("type", "unknown")
            severity = issue.get("severity", 0)
            description = issue.get("description", "")
            recommendation = issue.get("recommendation", "")
            
            issue_guidance += f"\n\n{issue_type.upper()} (Severity: {severity}/10):"
            issue_guidance += f"\nProblem: {description}"
            issue_guidance += f"\nSolution: {recommendation}"
        
        guidance_parts.append(issue_guidance)
    
    # Add quality improvement targets
    quality_scores = reflection.get("quality_scores", {})
    low_scores = [(area, score) for area, score in quality_scores.items() 
                  if score < 7 and area != "overall"]
    
    if low_scores:
        quality_guidance = "AREAS NEEDING IMPROVEMENT:"
        for area, score in low_scores:
            quality_guidance += f"\n- {area.replace('_', ' ').title()}: Currently {score}/10"
        guidance_parts.append(quality_guidance)
    
    # Add plot thread effectiveness guidance
    plot_effectiveness = reflection.get("plot_thread_effectiveness", {})
    if plot_effectiveness.get("missed_opportunities"):
        plot_guidance = "PLOT THREAD OPPORTUNITIES:"
        for opportunity in plot_effectiveness["missed_opportunities"]:
            plot_guidance += f"\n- {opportunity}"
        guidance_parts.append(plot_guidance)
    
    return "\n\n".join(guidance_parts)


def _get_revision_context(state: StoryState, current_chapter: str, current_scene: str) -> str:
    """Get relevant context for scene revision.
    
    Args:
        state: Current story state
        current_chapter: Current chapter number (as string)
        current_scene: Current scene number (as string)
        
    Returns:
        Formatted context string
    """
    context_parts = []
    
    # Get chapter context
    chapter_data = state["chapters"][current_chapter]
    context_parts.append(f"CHAPTER OUTLINE:\n{chapter_data['outline']}")
    
    # Get scene outline
    scene_data = chapter_data["scenes"][current_scene]
    context_parts.append(f"SCENE OUTLINE:\n{scene_data['outline']}")
    
    # Get character information for scene
    characters_in_scene = scene_data.get("characters", [])
    if characters_in_scene:
        char_info = "CHARACTERS IN SCENE:"
        for char_name in characters_in_scene:
            if char_name in state.get("characters", {}):
                char = state["characters"][char_name]
                char_info += f"\n- {char_name}: {char.get('personality', 'Unknown personality')}"
        context_parts.append(char_info)
    
    # Get active plot threads
    active_threads = state.get("active_plot_threads", [])
    if active_threads:
        thread_info = "ACTIVE PLOT THREADS:"
        for thread in active_threads[:3]:  # Limit to top 3
            thread_info += f"\n- {thread['name']}: {thread['current_development']}"
        context_parts.append(thread_info)
    
    # Get database context if available
    context_provider = get_context_provider()
    if context_provider:
        try:
            # Get scene ID from database
            from storyteller_lib.database_integration import get_db_manager
            db_manager = get_db_manager()
            if db_manager and db_manager._db:
                with db_manager._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT s.id 
                        FROM scenes s
                        JOIN chapters c ON s.chapter_id = c.id
                        WHERE c.chapter_number = ? AND s.scene_number = ?
                        """,
                        (int(current_chapter), int(current_scene))
                    )
                    result = cursor.fetchone()
                    if result:
                        scene_id = result['id']
                        # Get revision context from database
                        db_context = context_provider.get_revision_context(scene_id)
                        
                        # Add revision guidelines if available
                        if db_context.get('revision_guidelines'):
                            guidelines = "DATABASE REVISION GUIDELINES:"
                            for guideline in db_context['revision_guidelines']:
                                guidelines += f"\n- {guideline}"
                            context_parts.append(guidelines)
                        
                        # Add preservation requirements
                        if db_context.get('must_preserve'):
                            preserve_info = "MUST PRESERVE:"
                            if db_context['must_preserve'].get('plot_developments'):
                                for dev in db_context['must_preserve']['plot_developments']:
                                    preserve_info += f"\n- Plot: {dev['thread_name']} - {dev['description']}"
                            if db_context['must_preserve'].get('character_states'):
                                for state_change in db_context['must_preserve']['character_states']:
                                    preserve_info += f"\n- Character state: {state_change['character']} - {state_change['changes'].get('emotional_state', 'N/A')}"
                            context_parts.append(preserve_info)
        except Exception:
            # Don't fail revision if database context unavailable
            pass
    
    return "\n\n".join(context_parts)


def revise_scenes_batch(state: StoryState, revision_candidates: List[Dict[str, Any]]) -> Dict:
    """Process multiple scene revisions in batch.
    
    This function handles revisions triggered by character or plot changes
    that affect multiple scenes.
    
    Args:
        state: Current story state
        revision_candidates: List of scenes that need revision
        
    Returns:
        Updated state with revised scenes
    """
    if not revision_candidates:
        return state
    
    # Sort by priority (highest first) and chapter/scene order
    revision_candidates.sort(key=lambda x: (-x.get('priority', 0), 
                                           x.get('chapter_number', 0), 
                                           x.get('scene_number', 0)))
    
    # Process up to 5 highest priority revisions
    for candidate in revision_candidates[:5]:
        chapter_num = candidate.get('chapter_number')
        scene_num = candidate.get('scene_number')
        reason = candidate.get('reason', 'Unspecified change')
        
        if not chapter_num or not scene_num:
            continue
        
        # Update state to point to this scene
        state['current_chapter'] = str(chapter_num)
        state['current_scene'] = str(scene_num)
        state['revision_reason'] = reason
        state['scene_needs_revision'] = True
        
        # Process the revision
        state = revise_scene_if_needed(state)
    
    # Clear pending revisions
    state.pop('pending_revisions', None)
    return state


@track_progress
def revise_scene_if_needed(state: StoryState) -> Dict:
    """Revise the scene based on reflection feedback if needed.
    
    This function takes the reflection analysis and revises the scene
    to address identified issues while maintaining story consistency.
    
    Args:
        state: Current story state
        
    Returns:
        Updated state with revised scene (if revision was needed)
    """
    
    # Check if revision is needed
    if not state.get("scene_needs_revision", False) and not state.get("pending_revisions", []):
        # No revision needed, just update last node and return
        state["last_node"] = NodeNames.REVISE_SCENE
        return state
    
    current_chapter = str(state["current_chapter"])
    current_scene = str(state["current_scene"])
    chapters = state["chapters"]
    
    # Get current scene content and reflection
    scene_data = chapters[current_chapter]["scenes"][current_scene]
    current_content = scene_data["content"]
    reflection = state.get("scene_reflection", {})
    
    # Get revision type and determine approach
    revision_type = reflection.get("revision_recommendation", {}).get("revision_type", RevisionTypes.MODERATE)
    
    # Get language settings
    language = state.get("language", DEFAULT_LANGUAGE)
    author = state.get("author", "")
    author_style_guidance = state.get("author_style_guidance", "")
    
    # Prepare revision guidance
    revision_guidance = _prepare_revision_guidance(reflection, current_content)
    context = _get_revision_context(state, current_chapter, current_scene)
    
    # Prepare language instructions if needed
    language_instruction = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_instruction = f"""
        CRITICAL LANGUAGE REQUIREMENT:
        The revised scene MUST be written entirely in {SUPPORTED_LANGUAGES[language.lower()]}.
        All dialogue, narration, and descriptions must be in {SUPPORTED_LANGUAGES[language.lower()]}.
        """
    
    # Prepare author style instructions if applicable
    author_instruction = ""
    if author:
        author_instruction = f"""
        AUTHOR STYLE:
        Maintain the style of {author} with these characteristics:
        {author_style_guidance}
        """
    
    # Get database manager for additional context
    from storyteller_lib.database_integration import get_db_manager
    db_manager = get_db_manager()
    
    # Get full scene content from database if needed
    if not current_content and db_manager:
        current_content = db_manager.get_scene_content(int(current_chapter), int(current_scene))
    
    # Get character information from database
    characters = {}
    character_voices = {}
    if db_manager and db_manager._db:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT identifier, name, role, backstory, personality
                FROM characters
            """)
            for row in cursor.fetchall():
                characters[row['identifier']] = {
                    'name': row['name'],
                    'role': row['role'],
                    'backstory': row['backstory'],
                    'personality': row['personality']
                }
                # Extract voice characteristics if available
                if row['personality']:
                    character_voices[row['name']] = f"{row['role']}, {row['personality'][:100]}..."
    
    # Get genre and tone from state
    genre = state.get("genre", "fantasy")
    tone = state.get("tone", "adventurous")
    
    # Use template system for scene revision
    from storyteller_lib.prompt_templates import render_prompt
    
    # Prepare issues for template
    issues = reflection.get("issues", [])
    
    # Prepare quality scores
    quality_scores = reflection.get("quality_scores", {})
    
    # Prepare plot threads
    plot_threads = state.get("active_plot_threads", [])
    
    # Render the revision prompt
    prompt = render_prompt(
        'scene_revision',
        language=language,
        scene_content=current_content,
        current_chapter=current_chapter,
        current_scene=current_scene,
        genre=genre,
        tone=tone,
        issues=issues,
        quality_scores=quality_scores,
        revision_type=revision_type,
        specific_focus=revision_guidance if revision_guidance else None,
        plot_threads=plot_threads[:3] if plot_threads else None,  # Limit to 3
        character_voices=character_voices if character_voices else None
    )
    
    # Add any additional context
    if context:
        prompt += f"\n\nADDITIONAL CONTEXT:\n{context}"
    
    # Add author style if applicable
    if author and author_style_guidance:
        prompt += f"\n\nAUTHOR STYLE:\nMaintain the style of {author} with these characteristics:\n{author_style_guidance}"
    
    # Get the revision from LLM
    messages = [HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    revised_content = response.content
    
    # Update the scene with revised content
    scene_data["content"] = revised_content
    scene_data["revision_count"] = scene_data.get("revision_count", 0) + 1
    
    # Track the issues that were addressed
    addressed_issues = reflection.get("issues", [])
    existing_addressed = scene_data.get("issues_addressed", [])
    scene_data["issues_addressed"] = existing_addressed + addressed_issues
    
    # Revision history is tracked in state through the scene data
    
    # Update state
    state["last_node"] = NodeNames.REVISE_SCENE
    state["scene_revised"] = True
    state["current_scene_content"] = revised_content
    
    # Clear the revision flag
    state["scene_needs_revision"] = False
    
    # Log the revision
    from storyteller_lib.story_progress_logger import log_progress
    log_progress("revision", chapter_num=current_chapter, scene_num=current_scene,
                revision_reason=f"{revision_type} revision - addressing {len(addressed_issues)} issues")
    
    return state