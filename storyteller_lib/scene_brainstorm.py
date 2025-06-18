"""Scene brainstorming module for StoryCraft Agent.

This module handles the creative brainstorming phase of scene generation,
including plot thread integration, character dynamics, and creative elements.
"""

# Standard library imports
from typing import Any, Dict, List

# Third party imports
from langchain_core.messages import HumanMessage

# Local imports
from storyteller_lib import track_progress
from storyteller_lib.config import MEMORY_NAMESPACE, llm, manage_memory_tool, search_memory_tool
from storyteller_lib.constants import NodeNames, SceneElements
from storyteller_lib.creative_tools import creative_brainstorm
from storyteller_lib.logger import scene_logger as logger
from storyteller_lib.models import StoryState
from storyteller_lib.plot_threads import get_active_plot_threads_for_scene
from storyteller_lib.context_aware_scene_analysis import (
    analyze_scene_sequence_variety, suggest_next_scene_type
)


def _prepare_creative_guidance(creative_elements: Dict, current_chapter: str, current_scene: str) -> Dict:
    """Prepare creative guidance based on brainstormed elements.
    
    Args:
        creative_elements: Dictionary of creative elements from brainstorming
        current_chapter: Current chapter number
        current_scene: Current scene number
        
    Returns:
        Structured creative elements dictionary
    """
    # Return the creative elements as-is for the template to format
    return creative_elements


def _prepare_plot_thread_guidance(active_plot_threads: List[Dict]) -> List[Dict[str, Any]]:
    """Prepare guidance for active plot threads in the scene.
    
    Args:
        active_plot_threads: List of active plot thread dictionaries
        
    Returns:
        List of structured plot thread dictionaries
    """
    if not active_plot_threads:
        return []
        
    structured_threads = []
    for thread in active_plot_threads:
        # Use importance field if type is not available
        thread_type = thread.get('type', thread.get('importance', 'minor'))
        
        # Handle different field names for development
        current_dev = thread.get('current_development', thread.get('last_development', 'No development yet'))
        
        # Get characters involved
        chars = thread.get('involved_characters', thread.get('related_characters', []))
        
        structured_thread = {
            'name': thread['name'],
            'type': thread_type,
            'status': thread['status'],
            'current_development': current_dev,
            'characters_involved': chars if chars else None
        }
        
        # Add optional fields if present
        if thread.get('next_steps'):
            structured_thread['next_steps'] = thread['next_steps']
        if thread.get('tension_level'):
            structured_thread['tension_level'] = thread['tension_level']
            
        structured_threads.append(structured_thread)
    
    return structured_threads


@track_progress
def brainstorm_scene_elements(state: StoryState) -> Dict:
    """Brainstorm creative elements for the upcoming scene.
    
    This node generates creative ideas and approaches for the scene,
    considering plot threads, character dynamics, and story progression.
    
    Args:
        state: Current story state
        
    Returns:
        Updated state with brainstormed scene elements
    """
    
    current_chapter = state.get("current_chapter", "1")
    current_scene = state.get("current_scene", "1")
    
    # Get chapter outline from database
    from storyteller_lib.database_integration import get_db_manager
    db_manager = get_db_manager()
    
    if not db_manager or not db_manager._db:
        raise RuntimeError("Database manager not available - cannot retrieve chapter outline")
    
    # Get chapter outline from database
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT outline FROM chapters WHERE chapter_number = ?",
            (int(current_chapter),)
        )
        result = cursor.fetchone()
        if not result:
            raise RuntimeError(f"Chapter {current_chapter} outline not found in database")
        chapter_outline = result['outline']
    
    # Get scene description and specifications if available
    scene_description = ""
    scene_specifications = {
        "plot_progressions": [],
        "character_learns": [],
        "required_characters": [],
        "forbidden_repetitions": [],
        "dramatic_purpose": "development",
        "tension_level": 5,
        "ends_with": "transition",
        "connects_to_next": "",
        "scene_type": "exploration"  # Default scene type
    }
    
    # Get chapter_id from database directly
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM chapters WHERE chapter_number = ?",
            (int(current_chapter),)
        )
        chapter_result = cursor.fetchone()
        if chapter_result:
            chapter_id = chapter_result['id']
            cursor.execute(
                "SELECT description, scene_type FROM scenes WHERE chapter_id = ? AND scene_number = ?",
                (chapter_id, int(current_scene))
            )
            result = cursor.fetchone()
            if result:
                if result['description']:
                    scene_description = result['description']
                if result['scene_type']:
                    scene_specifications['scene_type'] = result['scene_type']
    
    # Try to get scene specifications from state
    chapters = state.get("chapters", {})
    if current_chapter in chapters and "scenes" in chapters[current_chapter]:
        scene_data = chapters[current_chapter]["scenes"].get(current_scene, {})
        if scene_data:
            # ALWAYS use scene description from chapter planning
            if 'description' in scene_data:
                scene_description = scene_data['description']
            
            scene_specifications["plot_progressions"] = scene_data.get("plot_progressions", [])
            scene_specifications["character_learns"] = scene_data.get("character_learns", [])
            scene_specifications["required_characters"] = scene_data.get("required_characters", [])
            scene_specifications["forbidden_repetitions"] = scene_data.get("forbidden_repetitions", [])
            scene_specifications["dramatic_purpose"] = scene_data.get("dramatic_purpose", "development")
            scene_specifications["tension_level"] = scene_data.get("tension_level", 5)
            scene_specifications["ends_with"] = scene_data.get("ends_with", "transition")
            scene_specifications["connects_to_next"] = scene_data.get("connects_to_next", "")
            # Get scene_type from state if available and not already set from DB
            if 'scene_type' in scene_data and 'scene_type' not in scene_specifications:
                scene_specifications["scene_type"] = scene_data.get("scene_type", "exploration")
    
    # Fail if no scene description found - we should never use generic descriptions
    if not scene_description:
        logger.error(f"No scene description found for Chapter {current_chapter}, Scene {current_scene}")
        raise RuntimeError(f"No scene description found for Chapter {current_chapter}, Scene {current_scene}")
    
    logger.info(f"Scene description for Ch{current_chapter}/Sc{current_scene}: {scene_description[:100]}...")
    
    # Check plot progressions that have already occurred
    existing_progressions = db_manager.get_plot_progressions()
    existing_progression_keys = [p['progression_key'] for p in existing_progressions]
    
    # Prepare structured data for specifications
    plot_progressions = []
    if scene_specifications["plot_progressions"]:
        for prog in scene_specifications["plot_progressions"]:
            plot_progressions.append({
                'key': prog,
                'already_occurred': prog in existing_progression_keys
            })
    
    forbidden_repetitions = scene_specifications.get("forbidden_repetitions", [])
    required_characters = scene_specifications.get("required_characters", [])
    character_learns = scene_specifications.get("character_learns", [])
    
    # Get active plot threads for this scene
    active_plot_threads = get_active_plot_threads_for_scene(state)
    
    # Prepare structured plot threads for template
    structured_plot_threads = _prepare_plot_thread_guidance(active_plot_threads)
    
    # Get the overall story context
    story_context = state.get("story_premise", "")
    genre = state.get("genre", "fantasy")
    tone = state.get("tone", "adventurous")
    
    # Prepare plot thread information for brainstorming
    plot_thread_context = ""
    if active_plot_threads:
        plot_thread_context = "\nActive plot threads to consider:\n"
        for thread in active_plot_threads:
            development = thread.get('last_development', thread.get('description', 'No development yet'))
            plot_thread_context += f"- {thread['name']}: {development}\n"
    
    # Get summary of previous scenes to avoid repetition
    previous_scenes_summary = ""
    if db_manager and db_manager._db:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            # Get all previous scenes
            cursor.execute("""
                SELECT c.chapter_number, s.scene_number, s.content
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE (c.chapter_number < ? OR (c.chapter_number = ? AND s.scene_number < ?))
                ORDER BY c.chapter_number DESC, s.scene_number DESC
                LIMIT 20
            """, (int(current_chapter), int(current_chapter), int(current_scene)))
            
            previous_content_scenes = cursor.fetchall()
            if previous_content_scenes:
                previous_scenes_summary = "\n\nPREVIOUS SCENES (DO NOT REPEAT):\n"
                for scene in previous_content_scenes:
                    # Get first paragraph of each scene
                    content = scene['content']
                    if content:
                        first_para = content.strip().split('\n\n')[0]
                        previous_scenes_summary += f"Ch{scene['chapter_number']}/Sc{scene['scene_number']}: {first_para}\n"
    
    # Get scene variety requirements if available
    from storyteller_lib.scene_variety import determine_scene_variety_requirements
    # Get previous scenes and chapter outline for variety requirements
    previous_scenes = []
    chapter_outline = ""
    current_chapter = state.get("current_chapter", "1")
    current_scene = state.get("current_scene", "1")
    
    # Get chapter outline from database
    from storyteller_lib.database_integration import get_db_manager
    db_manager = get_db_manager()
    if db_manager and db_manager._db:
        try:
            # Get chapter outline
            with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT outline FROM chapters WHERE chapter_number = ?",
                    (int(current_chapter),)
                )
                
                result = cursor.fetchone()
                if result:
                    chapter_outline = result['outline']
        except Exception as e:
            logger.warning(f"Could not get chapter outline from database: {e}")
        
        # Get previous scene metadata for analysis
        previous_scenes = []
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.chapter_number, s.scene_number, s.description, s.scene_type, se.event_type, se.event_description
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                LEFT JOIN story_events se ON se.chapter_number = c.chapter_number 
                    AND se.scene_number = s.scene_number
                WHERE c.chapter_number <= ?
                ORDER BY c.chapter_number DESC, s.scene_number DESC
                LIMIT 10
            """, (int(current_chapter),))
            
            for row in cursor.fetchall():
                # Use scene description if available, otherwise event description
                summary = row['description'] if row['description'] else (row['event_description'] or 'No summary available')
                
                # Use stored scene_type from database, fallback to event_type or default
                scene_type = row['scene_type'] if row['scene_type'] else (row['event_type'] or 'exploration')
                
                previous_scenes.append({
                    'chapter': row['chapter_number'],
                    'scene': row['scene_number'],
                    'type': scene_type,  # Keep for backward compatibility
                    'scene_type': scene_type,  # Add proper field name
                    'summary': summary,
                    'description': row['description'] if row['description'] else '',  # Include actual scene description
                    'focus': 'character development' if 'character' in summary.lower() else 'plot progression'  # Infer focus
                })
    
    # Analyze scene sequence for variety appropriateness
    sequence_analysis = None
    next_scene_suggestion = None
    
    if previous_scenes:
        # Debug: Log what we're passing to variety analysis
        logger.info(f"Previous scenes for variety analysis: {len(previous_scenes)} scenes")
        for i, scene in enumerate(previous_scenes[:3]):
            logger.info(f"  Scene {i}: Ch{scene['chapter']}/Sc{scene['scene']} - Type: {scene['type']}, Summary: {scene['summary'][:50]}...")
        
        # Analyze if the scene sequence has appropriate variety
        sequence_analysis = analyze_scene_sequence_variety(
            recent_scenes=previous_scenes[:5],  # Last 5 scenes
            genre=genre,
            tone=tone,
            story_context=story_context,
            language=state.get("language", "english")
        )
        
        # Get suggestions for the next scene type
        remaining_goals = []  # Goals are managed through plot progressions system
        next_scene_suggestion = suggest_next_scene_type(
            recent_scenes=previous_scenes[:5],
            chapter_outline=chapter_outline,
            remaining_chapter_goals=remaining_goals,
            genre=genre,
            tone=tone,
            language=state.get("language", "english")
        )
    
    # Determine variety requirements with context awareness
    scene_variety_requirements = determine_scene_variety_requirements(
        previous_scenes=previous_scenes,
        chapter_outline=chapter_outline,
        scene_number=int(current_scene),
        total_scenes_in_chapter=len(state.get("chapters", {}).get(current_chapter, {}).get("scenes", {})),
        language=state.get("language", "english")
    )
    
    # Override variety requirements if sequence analysis suggests it
    if sequence_analysis and next_scene_suggestion:
        if sequence_analysis.intentional_pattern:
            # If pattern is intentional, allow it to continue
            scene_variety_requirements.scene_type = next_scene_suggestion.get('suggested_type', scene_variety_requirements.scene_type)
        elif not sequence_analysis.variety_appropriate:
            # If variety is lacking, enforce the suggestion
            scene_variety_requirements.scene_type = next_scene_suggestion.get('suggested_type', scene_variety_requirements.scene_type)
            # Add elements to avoid from the suggestion
            elements_to_avoid = next_scene_suggestion.get('elements_to_avoid', [])
            if elements_to_avoid:
                scene_variety_requirements.forbidden_elements.extend(elements_to_avoid)
    
    # Get forbidden elements from scene progression
    forbidden_elements = {"phrases": [], "structures": []}
    try:
        from storyteller_lib.scene_progression import get_forbidden_elements
        forbidden_elements = get_forbidden_elements(state)
    except:
        pass
    
    # Use template system for scene brainstorming
    from storyteller_lib.prompt_templates import render_prompt
    
    # Prepare previous scenes data for template
    previous_scenes_data = []
    if previous_scenes:
        for scene in previous_scenes[:5]:  # Limit to 5 most recent
            # Use the summary field from the previous_scenes data structure
            summary = scene.get('summary', 'No summary available')
            previous_scenes_data.append({
                "summary": f"Ch{scene['chapter']}/Sc{scene['scene']}: {summary[:200]}..."
            })
    
    # Get language from state
    language = state.get("language", "english")
    
    # Check if we should consider merging with previous scene
    merge_analysis = None
    if int(current_scene) > 1:
        from storyteller_lib.dramatic_arc import analyze_dramatic_necessity
        prev_scene = str(int(current_scene) - 1)
        prev_scene_data = chapters.get(current_chapter, {}).get("scenes", {}).get(prev_scene, {})
        
        if prev_scene_data:
            merge_analysis = analyze_dramatic_necessity(
                prev_scene_data.get("description", ""),
                scene_description,
                active_plot_threads,
                prev_scene_data.get("tension_level", 5),
                scene_specifications["tension_level"],
                prev_scene_data.get("dramatic_purpose", "development"),
                scene_specifications["dramatic_purpose"]
            )
    
    # Prepare dramatic context for brainstorming
    dramatic_context = {
        "purpose": scene_specifications["dramatic_purpose"],
        "tension_level": scene_specifications["tension_level"],
        "ends_with": scene_specifications["ends_with"],
        "connects_to_next": scene_specifications["connects_to_next"],
        "scene_type": scene_specifications["scene_type"],
        "merge_analysis": merge_analysis
    }
    
    # Log scene description before rendering
    logger.info(f"About to render brainstorm prompt with scene_description: {scene_description[:100] if scene_description else 'NONE'}...")
    
    # Render the brainstorming prompt
    brainstorm_prompt = render_prompt(
        'scene_brainstorm',
        language=language,
        current_chapter=current_chapter,
        chapter_title=chapter_outline.split('\n')[0] if chapter_outline else f"Chapter {current_chapter}",
        chapter_outline=chapter_outline,
        scene_number=current_scene,
        scene_description=scene_description,
        genre=genre,
        tone=tone,
        story_premise=story_context,
        previous_scenes=previous_scenes_data if previous_scenes_data else None,
        scene_variety_requirements=scene_variety_requirements if scene_variety_requirements else None,
        forbidden_elements=forbidden_elements if any(forbidden_elements.values()) else None,
        sequence_analysis=sequence_analysis,
        next_scene_suggestion=next_scene_suggestion,
        plot_progressions=plot_progressions if plot_progressions else None,
        forbidden_repetitions=forbidden_repetitions if forbidden_repetitions else None,
        required_characters=required_characters if required_characters else None,
        character_learns=character_learns if character_learns else None,
        active_plot_threads=structured_plot_threads if structured_plot_threads else None,
        creative_elements=creative_elements if 'creative_elements' in locals() else None,
        dramatic_context=dramatic_context
    )
    
    # Log the first part of the prompt to check if scene description is there
    logger.info("=== BRAINSTORM PROMPT START ===")
    prompt_lines = brainstorm_prompt.split('\n')[:50]  # First 50 lines
    for i, line in enumerate(prompt_lines):
        if 'szene' in line.lower() and ('2:' in line or 'beschreibung' in line.lower()):
            logger.info(f"Line {i}: {line}")
            if i < len(prompt_lines) - 1:
                logger.info(f"Line {i+1}: {prompt_lines[i+1]}")
    logger.info("=== BRAINSTORM PROMPT END ===")
    
    # Generate brainstorming ideas using LLM directly
    try:
        response = llm.invoke([HumanMessage(content=brainstorm_prompt)])
        brainstorm_content = response.content
        
        # Parse the response to extract ideas
        ideas = []
        if "Approach" in brainstorm_content or "approach" in brainstorm_content:
            # Extract numbered approaches
            import re
            approaches = re.findall(r'(?:Approach |approach |\d+\.|\d+\))[^\n]*(?:\n(?!(?:Approach |approach |\d+\.|\d+\)))[^\n]*)*', brainstorm_content)
            ideas = [approach.strip() for approach in approaches[:3]]
        
        if not ideas:
            # Fallback: take first three paragraphs
            ideas = [p.strip() for p in brainstorm_content.split('\n\n')[:3] if p.strip()]
        
        brainstorm_result = {
            "ideas": ideas,
            "recommended_ideas": ideas[0] if ideas else "Standard scene progression"
        }
    except Exception as e:
        print(f"Error in scene brainstorming: {e}")
        # Fallback to creative_brainstorm
        brainstorm_result = creative_brainstorm(
            topic=f"scene approach for Chapter {current_chapter}, Scene {current_scene}",
            genre=genre,
            context=f"""
            Story Context: {story_context}
            Chapter Outline: {chapter_outline}
            Scene Description: {scene_description}
            {plot_thread_context}
            {previous_scenes_summary}
            """,
            num_ideas=3,
            tone=tone
        )
    
    # Extract the best approach
    scene_elements = {
        "creative_approach": brainstorm_result.get("recommended_ideas", ""),
        "plot_progression": "Advance key plot threads naturally through character actions",
        "character_dynamics": "Focus on character interactions and emotional depth",
        "scene_purpose": f"Advance the narrative while developing character relationships",
        "creative_opportunities": brainstorm_result.get("ideas", "")[:500] if brainstorm_result.get("ideas") else ""
    }
    
    # Store the brainstormed elements in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"scene_elements_ch{current_chapter}_sc{current_scene}",
        "value": scene_elements,
        "namespace": MEMORY_NAMESPACE
    })
    
    # Check if this scene should be merged with the previous one
    if merge_analysis and merge_analysis.get('merge_recommendation', False):
        # Mark this scene for merging instead of separate writing
        scene_elements['should_merge'] = True
        scene_elements['merge_guidance'] = merge_analysis['transition_guidance']
        
        # Update the scene specifications to indicate merging
        if current_chapter in state["chapters"] and "scenes" in state["chapters"][current_chapter]:
            if current_scene in state["chapters"][current_chapter]["scenes"]:
                state["chapters"][current_chapter]["scenes"][current_scene]["should_merge"] = True
    
    # Log scene start
    from storyteller_lib.story_progress_logger import log_progress
    log_progress("scene_start", chapter_num=current_chapter, scene_num=current_scene, 
                description=scene_description)
    
    # Update state
    state["scene_elements"] = scene_elements
    state["active_plot_threads"] = active_plot_threads
    state["last_node"] = NodeNames.BRAINSTORM_SCENE
    
    return state