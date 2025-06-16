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
from storyteller_lib.models import StoryState
from storyteller_lib.plot_threads import get_active_plot_threads_for_scene


def _prepare_creative_guidance(creative_elements: Dict, current_chapter: str, current_scene: str) -> str:
    """Prepare creative guidance based on brainstormed elements.
    
    Args:
        creative_elements: Dictionary of creative elements from brainstorming
        current_chapter: Current chapter number
        current_scene: Current scene number
        
    Returns:
        Formatted creative guidance string
    """
    # Keep it concise and scene-focused - we'll use these in the prompt
    guidance = f"\nCREATIVE ELEMENTS for Chapter {current_chapter}, Scene {current_scene}:\n"
    
    if "plot_progression" in creative_elements:
        guidance += f"Plot Progression: {creative_elements['plot_progression']}\n"
    
    if "character_dynamics" in creative_elements:
        guidance += f"Character Dynamics: {creative_elements['character_dynamics']}\n"
        
    if "scene_purpose" in creative_elements:
        guidance += f"Scene Purpose: {creative_elements['scene_purpose']}\n"
        
    if "creative_opportunities" in creative_elements:
        guidance += f"Creative Opportunities: {creative_elements['creative_opportunities']}\n"
    
    return guidance


def _prepare_plot_thread_guidance(active_plot_threads: List[Dict]) -> str:
    """Prepare guidance for active plot threads in the scene.
    
    Args:
        active_plot_threads: List of active plot thread dictionaries
        
    Returns:
        Formatted plot thread guidance string
    """
    if not active_plot_threads:
        return ""
        
    guidance = "\nACTIVE PLOT THREADS for this scene:\n"
    for thread in active_plot_threads:
        guidance += f"\n{thread['name']} ({thread['type']}):\n"
        guidance += f"  Status: {thread['status']}\n"
        guidance += f"  Current Development: {thread['current_development']}\n"
        
        if thread.get('next_steps'):
            guidance += f"  Next Steps: {thread['next_steps']}\n"
            
        if thread.get('tension_level'):
            guidance += f"  Tension Level: {thread['tension_level']}\n"
            
        if thread.get('involved_characters'):
            guidance += f"  Characters Involved: {', '.join(thread['involved_characters'])}\n"
            
        # Add guidance about how this thread should progress in this scene
        if thread['type'] == 'main_plot':
            guidance += "  >>> This is a MAIN PLOT thread. It should drive the primary narrative forward.\n"
        elif thread['type'] == 'subplot':
            guidance += "  >>> This subplot should complement the main narrative without overshadowing it.\n"
        elif thread['type'] == 'character_arc':
            guidance += "  >>> Focus on character development and emotional growth.\n"
        elif thread['type'] == 'mystery':
            guidance += "  >>> Reveal information carefully, maintaining suspense.\n"
        elif thread['type'] == 'relationship':
            guidance += "  >>> Explore the dynamics between characters.\n"
    
    return guidance


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
    
    # Get scene description if available
    scene_description = ""
    chapter_id = db_manager._chapter_id_map.get(current_chapter)
    if chapter_id:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT outline FROM scenes WHERE chapter_id = ? AND scene_number = ?",
                (chapter_id, int(current_scene))
            )
            result = cursor.fetchone()
            if result and result['outline']:
                scene_description = result['outline']
    
    # Use generic description if scene outline not available yet
    if not scene_description:
        scene_description = f"Scene {current_scene} of Chapter {current_chapter}"
    
    # Get active plot threads for this scene
    active_plot_threads = get_active_plot_threads_for_scene(state)
    
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
            
            previous_scenes = cursor.fetchall()
            if previous_scenes:
                previous_scenes_summary = "\n\nPREVIOUS SCENES (DO NOT REPEAT):\n"
                for scene in previous_scenes:
                    # Get first paragraph of each scene
                    content = scene['content']
                    if content:
                        first_para = content.strip().split('\n\n')[0]
                        previous_scenes_summary += f"Ch{scene['chapter_number']}/Sc{scene['scene_number']}: {first_para}\n"
    
    # Get scene variety requirements if available
    from storyteller_lib.scene_variety import get_scene_variety_requirements
    scene_variety_requirements = get_scene_variety_requirements(state)
    
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
            content = scene['content']
            if content:
                first_para = content.strip().split('\n\n')[0]
                previous_scenes_data.append({
                    "summary": f"Ch{scene['chapter_number']}/Sc{scene['scene_number']}: {first_para[:200]}..."
                })
    
    # Get language from state
    language = state.get("language", "english")
    
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
        forbidden_elements=forbidden_elements if any(forbidden_elements.values()) else None
    )
    
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
    
    # Log scene start
    from storyteller_lib.story_progress_logger import log_progress
    log_progress("scene_start", chapter_num=current_chapter, scene_num=current_scene, 
                description=scene_description)
    
    # Update state
    state["scene_elements"] = scene_elements
    state["active_plot_threads"] = active_plot_threads
    state["last_node"] = NodeNames.BRAINSTORM_SCENE
    
    return state