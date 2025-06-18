"""Scene writing module for StoryCraft Agent.

This module handles the actual writing of scenes, incorporating all the
brainstormed elements, character dynamics, and world details.
"""

# Standard library imports
import re
from typing import Any, Dict, List, Optional, Tuple

# Third party imports
from langchain_core.messages import HumanMessage

# Local imports
from storyteller_lib import track_progress
from storyteller_lib.config import (
    DEFAULT_LANGUAGE, MEMORY_NAMESPACE, SUPPORTED_LANGUAGES,
    llm, manage_memory_tool, search_memory_tool
)
from storyteller_lib.memory_manager import manage_memory, search_memory
from storyteller_lib.constants import NodeNames, SceneElements
from storyteller_lib.logger import scene_logger as logger
from storyteller_lib.models import StoryState
from storyteller_lib.story_context import get_context_provider


def _prepare_database_context(current_chapter: str, current_scene: str) -> str:
    """Prepare context from database for scene writing.
    
    Args:
        current_chapter: Current chapter number (as string)
        current_scene: Current scene number (as string)
        
    Returns:
        Formatted context string from database
    """
    context_provider = get_context_provider()
    if not context_provider:
        return ""
    
    # Get scene dependencies from database
    dependencies = context_provider.get_scene_dependencies(int(current_chapter), int(current_scene))
    
    if not dependencies:
        return ""
    
    context_parts = []
    
    # Add continuation context if available
    if dependencies.get('continuation_from_previous'):
        prev = dependencies['continuation_from_previous']
        context_parts.append(f"""
PREVIOUS SCENE ENDING:
The previous scene ended with:
{prev['ending']}

Characters present: {', '.join(prev['characters_present'])}
Location: {prev['location']}
""")
    
    # Add active plot threads
    if dependencies.get('plot_threads'):
        thread_info = []
        for thread in dependencies['plot_threads'][:3]:  # Top 3 most important
            info = f"- {thread['name']}: {thread['description']}"
            if thread.get('last_development'):
                info += f" (last developed in Chapter {thread['last_development']['chapter_number']})"
            thread_info.append(info)
        
        if thread_info:
            context_parts.append(f"""
ACTIVE PLOT THREADS TO CONSIDER:
{chr(10).join(thread_info)}
""")
    
    # Add character context for key characters
    char_contexts = []
    for char in dependencies.get('characters', [])[:5]:  # Top 5 characters
        if char.get('context') and char['context'].get('emotional_state'):
            ctx = char['context']
            char_info = f"- {char['name']}: Currently {ctx['emotional_state']}"
            if ctx.get('current_location'):
                char_info += f" at {ctx['current_location']}"
            char_contexts.append(char_info)
    
    if char_contexts:
        context_parts.append(f"""
CHARACTER STATES:
{chr(10).join(char_contexts)}
""")
    
    return "\n".join(context_parts) if context_parts else ""


def _prepare_author_style_guidance(author: str, author_style_guidance: str) -> str:
    """Return author style guidance for template.
    
    Args:
        author: Author name to emulate
        author_style_guidance: Detailed style guidance
        
    Returns:
        Style guidance string or empty string
    """
    # Just return the guidance - let template handle formatting
    return author_style_guidance if author and author_style_guidance else ""


def _retrieve_language_elements(language: str) -> Tuple[Optional[Dict], str, str]:
    """Retrieve language elements and consistency instructions from memory.
    
    Args:
        language: Target language for the story
        
    Returns:
        Tuple of (language_elements, consistency_instruction, language_examples)
    """
    language_elements = None
    consistency_instruction = ""
    language_examples = ""
    
    if language.lower() == DEFAULT_LANGUAGE:
        return language_elements, consistency_instruction, language_examples
    
    # Try to retrieve language elements from memory
    try:
        language_elements_result = search_memory_tool.invoke({
            "query": f"language_elements_{language.lower()}",
            "namespace": MEMORY_NAMESPACE
        })
        
        # Handle different return types from search_memory_tool
        if language_elements_result:
            if isinstance(language_elements_result, dict) and "value" in language_elements_result:
                # Direct dictionary with value
                language_elements = language_elements_result["value"]
            elif isinstance(language_elements_result, list):
                # List of objects
                for item in language_elements_result:
                    if hasattr(item, 'key') and item.key == f"language_elements_{language.lower()}":
                        language_elements = item.value
                        break
            elif isinstance(language_elements_result, str):
                # Try to parse JSON string
                try:
                    import json
                    language_elements = json.loads(language_elements_result)
                except:
                    # If not JSON, use as is
                    language_elements = language_elements_result
    except Exception as e:
        logger.error(f"Error retrieving language elements: {str(e)}")
    
    # Create language guidance with specific examples if available
    if language_elements:
        # Add cultural references if available
        if "CULTURAL REFERENCES" in language_elements:
            cultural_refs = language_elements["CULTURAL REFERENCES"]
            
            idioms = cultural_refs.get("Common idioms and expressions", "")
            if idioms:
                language_examples += f"\nCommon idioms and expressions in {SUPPORTED_LANGUAGES[language.lower()]}:\n{idioms}\n"
            
            traditions = cultural_refs.get("Cultural traditions and customs", "")
            if traditions:
                language_examples += f"\nCultural traditions and customs in {SUPPORTED_LANGUAGES[language.lower()]}:\n{traditions}\n"
        
        # Add narrative elements if available
        if "NARRATIVE ELEMENTS" in language_elements:
            narrative_elements = language_elements["NARRATIVE ELEMENTS"]
            
            storytelling = narrative_elements.get("Storytelling traditions", "")
            if storytelling:
                language_examples += f"\nStorytelling traditions in {SUPPORTED_LANGUAGES[language.lower()]} literature:\n{storytelling}\n"
            
            dialogue = narrative_elements.get("Dialogue patterns or speech conventions", "")
            if dialogue:
                language_examples += f"\nDialogue patterns in {SUPPORTED_LANGUAGES[language.lower()]}:\n{dialogue}\n"
    
    # Try to retrieve language consistency instruction
    try:
        consistency_result = search_memory(query="language_consistency_instruction", namespace=MEMORY_NAMESPACE)
        
        # Handle different return types from search_memory_tool
        if consistency_result:
            if isinstance(consistency_result, dict) and "value" in consistency_result:
                consistency_instruction = consistency_result["value"]
            elif isinstance(consistency_result, list) and consistency_result:
                for item in consistency_result:
                    if hasattr(item, 'key') and item.key == "language_consistency_instruction":
                        consistency_instruction = item.value
                        break
            elif isinstance(consistency_result, str):
                consistency_instruction = consistency_result
    except Exception as e:
        logger.error(f"Error retrieving consistency instruction: {str(e)}")
    
    return language_elements, consistency_instruction, language_examples


def _prepare_language_guidance(language: str) -> str:
    """Prepare language-specific guidance for scene writing.
    
    Args:
        language: Target language for the story
        
    Returns:
        Formatted language guidance string
    """
    if language.lower() == DEFAULT_LANGUAGE:
        return ""
    
    # Retrieve language elements from memory
    language_elements, consistency_instruction, language_examples = _retrieve_language_elements(language)
    
    base_guidance = f"""
    LANGUAGE GUIDANCE:
    Write this scene entirely in {SUPPORTED_LANGUAGES[language.lower()]}. 
    Ensure all dialogue, narration, and descriptions are in {SUPPORTED_LANGUAGES[language.lower()]}.
    {consistency_instruction}
    """
    
    if language_examples:
        base_guidance += f"\n{language_examples}"
    
    return base_guidance


def _identify_scene_characters(chapter_outline: str, characters: Dict) -> List[str]:
    """Identify which characters appear in the current scene.
    
    Args:
        chapter_outline: The outline text for the chapter
        characters: Dictionary of all characters
        
    Returns:
        List of character names appearing in the scene
    """
    scene_characters = []
    
    for char_name in characters.keys():
        # Check if character name appears in the chapter outline
        if char_name.lower() in chapter_outline.lower():
            scene_characters.append(char_name)
    
    return scene_characters


def _get_character_motivations(char_name: str) -> List[Dict[str, Any]]:
    """Retrieve character motivations from memory.
    
    Args:
        char_name: Character name to look up
        
    Returns:
        List of motivation dictionaries
    """
    try:
        motivations_result = search_memory_tool.invoke({
            "query": f"{char_name}_motivations",
            "namespace": MEMORY_NAMESPACE
        })
        
        if motivations_result:
            if isinstance(motivations_result, list):
                return motivations_result
            elif isinstance(motivations_result, dict) and "value" in motivations_result:
                return motivations_result["value"]
    except:
        pass
    
    return []


def _prepare_emotional_guidance(characters: Dict, scene_characters: List[str], tone: str, genre: str) -> str:
    """Prepare emotional and character dynamics guidance.
    
    Args:
        characters: Dictionary of all characters
        scene_characters: List of characters in the current scene
        tone: Story tone
        genre: Story genre
        
    Returns:
        Formatted emotional guidance string
    """
    if not scene_characters:
        return ""
        
    guidance = "\nCHARACTER DYNAMICS AND EMOTIONAL GUIDANCE:\n"
    
    # Add specific character information
    for char_name in scene_characters:
        if char_name in characters:
            char = characters[char_name]
            guidance += f"\n{char_name}:\n"
            guidance += f"- Personality: {char.get('personality', 'Unknown')}\n"
            guidance += f"- Current emotional state: {char.get('emotional_state', 'Stable')}\n"
            
            # Get motivations from memory if available
            motivations = _get_character_motivations(char_name)
            if motivations:
                guidance += f"- Key motivations: {', '.join([m.get('description', '') for m in motivations[:2]])}\n"
    
    # Add tone and genre-specific guidance
    emotional_guidance_map = {
        "adventurous": "Focus on excitement, wonder, and the thrill of discovery",
        "mysterious": "Build tension through uncertainty and hidden emotions",
        "romantic": "Emphasize emotional connections and tender moments",
        "dark": "Explore deeper fears, doubts, and psychological complexity",
        "epic": "Convey grand emotions and the weight of destiny",
        "comedic": "Find humor in character interactions and situations",
        "philosophical": "Delve into characters' thoughts and existential questions"
    }
    
    if tone in emotional_guidance_map:
        guidance += f"\nTone Guidance: {emotional_guidance_map[tone]}\n"
    
    # Add genre-specific character dynamics
    genre_dynamics_map = {
        "fantasy": "Magic and wonder should affect how characters perceive their world",
        "science fiction": "Technology and future concepts shape character worldviews",
        "mystery": "Characters should have secrets and hidden knowledge",
        "romance": "Focus on emotional vulnerability and connection",
        "thriller": "Characters should feel constant pressure and urgency",
        "horror": "Fear and dread should influence character decisions"
    }
    
    if genre in genre_dynamics_map:
        guidance += f"Genre Dynamics: {genre_dynamics_map[genre]}\n"
    
    return guidance


def _generate_previous_scenes_summary(state: StoryState, db_manager) -> str:
    """Generate a summary of previous scenes for context.
    
    Args:
        state: Current story state
        db_manager: Database manager instance
        
    Returns:
        Formatted summary of previous scenes
    """
    current_chapter = str(state.get("current_chapter", "1"))
    current_scene = str(state.get("current_scene", "1"))
    
    summary_parts = []
    
    # Get previous scenes from database
    if db_manager and db_manager._db:
        # First, add EVENT-BASED summaries from ALL previous chapters
        if int(current_chapter) > 1:
            summary_parts.append("=== KEY EVENTS FROM PREVIOUS CHAPTERS ===")
            for chapter_num in range(1, int(current_chapter)):
                # Get story events for this chapter
                with db_manager._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT event_type, event_description, participants
                        FROM story_events
                        WHERE chapter_number = ?
                        ORDER BY scene_number
                    """, (chapter_num,))
                    events = cursor.fetchall()
                    
                    if events:
                        summary_parts.append(f"\nChapter {chapter_num} Events:")
                        for event in events[:3]:  # Limit to 3 key events per chapter
                            summary_parts.append(f"- {event['event_type']}: {event['event_description']}")
                        summary_parts.append("---")
                    else:
                        # Fallback to extracting from content if no events logged
                        cursor.execute("""
                            SELECT s.scene_number, s.content
                            FROM scenes s
                            JOIN chapters c ON s.chapter_id = c.id
                            WHERE c.chapter_number = ?
                            ORDER BY s.scene_number
                            LIMIT 1
                        """, (chapter_num,))
                        result = cursor.fetchone()
                        if result:
                            # Extract just the key action
                            content = result['content'][:500]
                            summary_parts.append(f"\nChapter {chapter_num}: [Scene content begins with maintenance/routine work]")
                            summary_parts.append("---")
        # Add previous chapter ending if this is the first scene
        if current_scene == "1" and int(current_chapter) > 1:
            prev_chapter_num = int(current_chapter) - 1
            # Get last scene of previous chapter from database
            content = db_manager.get_scene_content(prev_chapter_num, 999)  # Try high number
            if not content:
                # Find actual last scene number
                with db_manager._db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT MAX(s.scene_number) as last_scene
                        FROM scenes s
                        JOIN chapters c ON s.chapter_id = c.id
                        WHERE c.chapter_number = ?
                    """, (prev_chapter_num,))
                    result = cursor.fetchone()
                    if result and result['last_scene']:
                        content = db_manager.get_scene_content(prev_chapter_num, result['last_scene'])
            
            if content:
                # Extract last paragraph for continuity
                paragraphs = content.strip().split('\n\n')
                if paragraphs:
                    summary_parts.append(f"Previous Chapter Ending: {paragraphs[-1][:200]}...")
        
        # Add previous scenes in current chapter as EVENT SUMMARIES
        if int(current_scene) > 1:
            summary_parts.append(f"\n=== PREVIOUS SCENES IN CHAPTER {current_chapter} ===")
            
            # Get events from previous scenes
            with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT scene_number, event_type, event_description
                    FROM story_events
                    WHERE chapter_number = ? AND scene_number < ?
                    ORDER BY scene_number
                """, (int(current_chapter), int(current_scene)))
                events = cursor.fetchall()
                
                if events:
                    for event in events:
                        summary_parts.append(f"Scene {event['scene_number']}: {event['event_type']} - {event['event_description']}")
                else:
                    # Fallback: extract key information from scenes
                    for i in range(1, int(current_scene)):
                        # Get character knowledge updates
                        cursor.execute("""
                            SELECT knowledge_item
                            FROM character_knowledge
                            WHERE chapter_number = ? AND scene_number = ?
                            LIMIT 2
                        """, (int(current_chapter), i))
                        knowledge = cursor.fetchall()
                        
                        if knowledge:
                            summary_parts.append(f"Scene {i}: Character learned - {', '.join([k['knowledge_item'] for k in knowledge])}")
                        else:
                            summary_parts.append(f"Scene {i}: [Routine maintenance and system checks]")
    
    # Look for recent important events in memory
    try:
        recent_events = search_memory_tool.invoke({
            "query": f"important_events_chapter_{current_chapter}",
            "namespace": MEMORY_NAMESPACE
        })
        
        if recent_events:
            if isinstance(recent_events, list) and recent_events:
                summary_parts.append(f"Recent Important Events: {str(recent_events[0])[:200]}...")
    except:
        pass
    
    if summary_parts:
        return "\nPREVIOUS SCENES CONTEXT:\n" + "\n".join(summary_parts) + "\n"
    
    return ""


@track_progress
def write_scene(state: StoryState) -> Dict:
    """Write the actual scene content.
    
    This is the main scene writing function that combines all elements
    to create the narrative content.
    
    Args:
        state: Current story state
        
    Returns:
        Updated state with written scene
    """
    
    current_chapter = str(state.get("current_chapter", "1"))
    current_scene = str(state.get("current_scene", "1"))
    
    # Check if this scene should be merged with the previous one
    scene_elements = state.get("scene_elements", {})
    if scene_elements.get("should_merge", False):
        # This scene should be appended to the previous scene
        prev_scene = str(int(current_scene) - 1)
        logger.info(f"Scene {current_scene} marked for merging with scene {prev_scene}")
        
        # Skip actual merging for now - just mark it
        # In a full implementation, we would append to the previous scene
        # For now, we'll write it with a soft transition marker
    
    # Get story elements
    story_premise = state.get("story_premise", "")
    genre = state.get("genre", "fantasy")
    tone = state.get("tone", "adventurous")
    language = state.get("language", DEFAULT_LANGUAGE)
    author = state.get("author", "")
    author_style_guidance = state.get("author_style_guidance", "")
    
    # Get scene specifications from state
    scene_specifications = {
        "plot_progressions": [],
        "character_learns": [],
        "required_characters": [],
        "forbidden_repetitions": [],
        "prerequisites": [],
        "dramatic_purpose": "development",
        "tension_level": 5,
        "ends_with": "transition",
        "connects_to_next": "",
        "scene_type": "exploration"  # Default scene type
    }
    
    chapters = state.get("chapters", {})
    if current_chapter in chapters and "scenes" in chapters[current_chapter]:
        scene_data = chapters[current_chapter]["scenes"].get(current_scene, {})
        if scene_data:
            scene_specifications["plot_progressions"] = scene_data.get("plot_progressions", [])
            scene_specifications["character_learns"] = scene_data.get("character_learns", [])
            scene_specifications["required_characters"] = scene_data.get("required_characters", [])
            scene_specifications["forbidden_repetitions"] = scene_data.get("forbidden_repetitions", [])
            scene_specifications["prerequisites"] = scene_data.get("prerequisites", [])
            scene_specifications["dramatic_purpose"] = scene_data.get("dramatic_purpose", "development")
            scene_specifications["tension_level"] = scene_data.get("tension_level", 5)
            scene_specifications["ends_with"] = scene_data.get("ends_with", "transition")
            scene_specifications["connects_to_next"] = scene_data.get("connects_to_next", "")
            scene_specifications["scene_type"] = scene_data.get("scene_type", "exploration")
    
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
    
    # ALWAYS get scene description from chapter planning data
    scene_description = ""
    chapters = state.get("chapters", {})
    if current_chapter in chapters and "scenes" in chapters[current_chapter]:
        scene_data = chapters[current_chapter]["scenes"].get(current_scene, {})
        if scene_data and 'description' in scene_data:
            scene_description = scene_data['description']
    
    if not scene_description:
        logger.error(f"No scene description found for Chapter {current_chapter}, Scene {current_scene}")
        raise RuntimeError(f"No scene description found for Chapter {current_chapter}, Scene {current_scene}")
    
    # Get creative elements from brainstorming
    scene_elements = state.get("scene_elements", {})
    active_plot_threads = state.get("active_plot_threads", [])
    
    # Import optimization utilities
    from storyteller_lib.prompt_optimization import (
        summarize_world_elements,
        truncate_scene_content, log_prompt_size
    )
    
    # Import entity relevance detection
    from storyteller_lib.entity_relevance import (
        analyze_scene_entities, filter_characters_for_scene,
        filter_world_elements_for_scene, get_scene_relevant_plot_threads
    )
    
    # Import scene progression and variety tracking
    from storyteller_lib.scene_progression import SceneProgressionTracker
    from storyteller_lib.scene_variety import (
        determine_scene_variety_requirements, generate_scene_variety_guidance,
        get_overused_elements
    )
    
    # Import intelligent repetition analysis
    from storyteller_lib.intelligent_repetition import (
        analyze_repetition_in_context, generate_intelligent_variation_guidance
    )
    
    # Import scene structure analysis
    from storyteller_lib.scene_structure_analysis import (
        analyze_scene_structures, generate_structural_guidance
    )
    
    # Import story summary for comprehensive context
    from storyteller_lib.story_summary import get_story_summary_for_context
    
    # Initialize progression tracker
    progression_tracker = SceneProgressionTracker()
    
    # Get previous scene metadata for variety analysis
    previous_scenes = []
    if db_manager and db_manager._db:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.scene_number, se.event_type, se.event_description
                FROM scenes s
                LEFT JOIN story_events se ON se.chapter_number = ? AND se.scene_number = s.scene_number
                JOIN chapters c ON s.chapter_id = c.id
                WHERE c.chapter_number = ?
                ORDER BY s.scene_number
            """, (int(current_chapter), int(current_chapter)))
            for row in cursor.fetchall():
                previous_scenes.append({
                    'scene_number': row['scene_number'],
                    'event_types': [row['event_type']] if row['event_type'] else []
                })
    
    # Determine variety requirements
    total_scenes = len(state.get("chapters", {}).get(current_chapter, {}).get("scenes", {}))
    variety_requirements = determine_scene_variety_requirements(
        previous_scenes=previous_scenes,
        chapter_outline=chapter_outline,
        scene_number=int(current_scene),
        total_scenes_in_chapter=total_scenes,
        language=language
    )
    
    # Get overused elements to avoid
    overused_elements = get_overused_elements(progression_tracker)
    
    # We need to identify scene characters early for structural analysis
    # This is a simple placeholder - the actual scene characters will be determined later
    preliminary_scene_characters = []
    
    # Perform intelligent repetition analysis on recent content
    recent_content = ""
    intelligent_variation_guidance = ""
    structural_guidance = ""
    structural_analysis_result = None
    
    if db_manager and db_manager._db:
        # Get last 5 scenes for context and structure analysis
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.content, s.scene_number, c.chapter_number
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE (c.chapter_number < ? OR (c.chapter_number = ? AND s.scene_number < ?))
                ORDER BY c.chapter_number DESC, s.scene_number DESC
                LIMIT 5
            """, (int(current_chapter), int(current_chapter), int(current_scene)))
            
            recent_scenes_data = cursor.fetchall()
            if recent_scenes_data:
                # Format for structure analysis
                scenes_for_structure = []
                for scene_data in recent_scenes_data:
                    scenes_for_structure.append({
                        'chapter': scene_data['chapter_number'],
                        'scene': scene_data['scene_number'],
                        'content': scene_data['content'],
                        'characters': preliminary_scene_characters  # Empty for now, just for structure
                    })
                
                # Analyze scene structures
                structural_analysis = analyze_scene_structures(
                    recent_scenes=scenes_for_structure,
                    genre=genre,
                    tone=tone,
                    language=language
                )
                
                # Store structural analysis for later use
                structural_analysis_result = structural_analysis
                
                # For repetition analysis, use just the content
                recent_content = "\n\n---\n\n".join([s['content'] for s in recent_scenes_data[:3]])
                
                # Analyze repetition intelligently
                intelligent_analysis = analyze_repetition_in_context(
                    text=recent_content,
                    genre=genre,
                    tone=tone,
                    author_style=author,
                    story_context=story_premise,
                    language=language
                )
                
                # Generate intelligent variation guidance
                intelligent_variation_guidance = generate_intelligent_variation_guidance(
                    analysis=intelligent_analysis,
                    scene_type=variety_requirements.scene_type,
                    genre=genre,
                    tone=tone
                )
    
    # Get characters from database
    all_characters = {}
    if db_manager and db_manager._db:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT identifier, name, role, backstory, personality
                FROM characters
            """)
            for row in cursor.fetchall():
                all_characters[row['identifier']] = {
                    'name': row['name'],
                    'role': row['role'],
                    'backstory': row['backstory'],
                    'personality': row['personality']
                }
    
    # Get world information from database
    all_world_elements = {}
    if db_manager and db_manager._db:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT category, element_key, element_value
                FROM world_elements
            """)
            for row in cursor.fetchall():
                if row['category'] not in all_world_elements:
                    all_world_elements[row['category']] = {}
                all_world_elements[row['category']][row['element_key']] = row['element_value']
    
    # Use intelligent entity analysis to determine what's relevant
    relevant_entities = analyze_scene_entities(
        chapter_outline=chapter_outline,
        scene_description=scene_description,
        all_characters=all_characters,
        world_elements=all_world_elements,
        language=language
    )
    
    # Filter to only relevant characters
    relevant_characters = filter_characters_for_scene(
        all_characters=all_characters,
        relevant_entities=relevant_entities,
        include_limit=5
    )
    
    # Filter to only relevant world elements
    world_elements = filter_world_elements_for_scene(
        world_elements=all_world_elements,
        relevant_entities=relevant_entities,
        include_limit=3
    )
    
    # Filter plot threads to only relevant ones
    filtered_plot_threads = get_scene_relevant_plot_threads(
        plot_threads=active_plot_threads,
        relevant_entities=relevant_entities,
        chapter_num=current_chapter,
        scene_num=current_scene
    )
    
    # Identify which characters are in this scene
    scene_characters = list(relevant_characters.keys())
    
    # Now that we have scene_characters, generate structural guidance if we have analysis
    if structural_analysis_result is not None:
        structural_guidance = generate_structural_guidance(
            analysis=structural_analysis_result,
            upcoming_scene_type=variety_requirements.scene_type,
            characters_involved=scene_characters
        )
    
    # Prepare various guidance sections
    author_guidance = _prepare_author_style_guidance(author, author_style_guidance)
    language_guidance = _prepare_language_guidance(language)
    emotional_guidance = _prepare_emotional_guidance(relevant_characters, scene_characters, tone, genre)
    previous_context = _generate_previous_scenes_summary(state, db_manager)
    
    # Get comprehensive story summary to prevent repetition
    story_summary = get_story_summary_for_context()
    
    # Get database context if available
    database_context = _prepare_database_context(current_chapter, current_scene)
    
    # Prepare structured specification data for templates
    plot_progressions = []
    plot_progression_warnings = []
    forbidden_content = []
    character_learning = []
    required_characters = scene_specifications.get("required_characters", [])
    
    if db_manager:
        existing_progressions = db_manager.get_plot_progressions()
        existing_progression_keys = [p['progression_key'] for p in existing_progressions]
        
        # Check for required plot progressions
        if scene_specifications["plot_progressions"]:
            for prog in scene_specifications["plot_progressions"]:
                if prog not in existing_progression_keys:
                    plot_progressions.append(prog)
                else:
                    plot_progression_warnings.append(prog)
        
        # Check for forbidden repetitions
        if scene_specifications["forbidden_repetitions"]:
            forbidden_content = scene_specifications["forbidden_repetitions"]
        
        # Check character knowledge
        if scene_specifications["character_learns"]:
            # Parse character_learns list which contains "CharacterName: knowledge item" strings
            character_knowledge_map = {}
            for learning in scene_specifications["character_learns"]:
                if ": " in learning:
                    char_name, knowledge = learning.split(": ", 1)
                    if char_name not in character_knowledge_map:
                        character_knowledge_map[char_name] = []
                    character_knowledge_map[char_name].append(knowledge)
            
            for char, knowledge_list in character_knowledge_map.items():
                char_learning = {
                    'character': char,
                    'learns': knowledge_list,
                    'warnings': []
                }
                
                # Check if character already knows this
                if db_manager and db_manager._db:
                    with db_manager._db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM characters WHERE identifier = ? OR name = ?",
                            (char, char)
                        )
                        char_result = cursor.fetchone()
                        if char_result:
                            cursor.execute(
                                """
                                SELECT knowledge_content 
                                FROM character_knowledge ck
                                JOIN scenes s ON ck.scene_id = s.id
                                JOIN chapters c ON s.chapter_id = c.id
                                WHERE ck.character_id = ?
                                """,
                                (char_result['id'],)
                            )
                            existing_knowledge = [row['knowledge_content'] for row in cursor.fetchall()]
                            for knowledge in knowledge_list:
                                if knowledge in existing_knowledge:
                                    char_learning['warnings'].append(f"{char} already knows '{knowledge}'!")
                
                character_learning.append(char_learning)
    
    # Import helper functions from original scenes.py
    from storyteller_lib.scene_helpers import (
        _prepare_creative_guidance,
        _prepare_plot_thread_guidance,
        _prepare_worldbuilding_guidance
    )
    
    creative_elements = _prepare_creative_guidance(scene_elements, current_chapter, current_scene)
    structured_plot_threads = _prepare_plot_thread_guidance(active_plot_threads)
    world_guidance = _prepare_worldbuilding_guidance(world_elements, chapter_outline, language=language)
    
    # Don't truncate story premise and chapter outline to maintain full context
    premise_brief = story_premise
    outline_brief = chapter_outline
    
    # Import prompt template system
    from storyteller_lib.prompt_templates import render_prompt
    
    # Extract forbidden phrases and structures
    forbidden_phrases = [elem.replace('phrase: ', '') for elem in overused_elements if 'phrase:' in elem]
    forbidden_structures = [elem.replace('structure: ', '') for elem in overused_elements if 'structure:' in elem]
    
    # Prepare dramatic context
    dramatic_context = {
        'purpose': scene_specifications["dramatic_purpose"],
        'tension_level': scene_specifications["tension_level"],
        'ends_with': scene_specifications["ends_with"],
        'connects_to_next': scene_specifications["connects_to_next"],
        'scene_type': scene_specifications["scene_type"]
    }
    
    # Prepare template variables
    template_vars = {
        'current_chapter': current_chapter,
        'current_scene': current_scene,
        'genre': genre,
        'tone': tone,
        'story_premise': premise_brief,
        'chapter_outline': outline_brief,
        'scene_description': scene_description,
        'story_summary': story_summary,
        'previous_context': previous_context,
        'database_context': database_context,
        'creative_elements': creative_elements if creative_elements else None,
        'active_plot_threads': structured_plot_threads if structured_plot_threads else None,
        'emotional_guidance': emotional_guidance,
        'world_guidance': world_guidance,
        'author': author,  # Pass author name for template
        'author_guidance': author_guidance,
        'variety_guidance': generate_scene_variety_guidance(variety_requirements),
        'forbidden_phrases': forbidden_phrases,
        'forbidden_structures': forbidden_structures,
        'scene_type': variety_requirements.scene_type,
        'intelligent_variation_guidance': intelligent_variation_guidance,
        'structural_guidance': structural_guidance,
        'plot_progressions': plot_progressions if plot_progressions else None,
        'plot_progression_warnings': plot_progression_warnings if plot_progression_warnings else None,
        'forbidden_content': forbidden_content if forbidden_content else None,
        'character_learning': character_learning if character_learning else None,
        'required_characters': required_characters if required_characters else None,
        'dramatic_context': dramatic_context  # Add dramatic context
    }
    
    # Render the prompt using the template system
    prompt = render_prompt('scene_writing', language=language, **template_vars)
    
    # Log prompt size
    log_prompt_size(prompt, f"scene writing Ch{current_chapter}/Sc{current_scene}")
    
    # Generate the scene
    messages = [HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    scene_content = response.content
    
    # Handle different transition types
    if scene_elements.get("should_merge", False):
        # Add soft transition marker instead of scene break
        scene_content = f"\n\n***\n\n{scene_content}"
    elif scene_specifications.get("ends_with") == "soft_transition" and int(current_scene) > 1:
        # Use section break for soft transitions
        scene_content = f"\n\n***\n\n{scene_content}"
    
    # Store only scene metadata in memory (content goes to database)
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"scene_metadata_ch{current_chapter}_sc{current_scene}",
        "value": {
            "characters": scene_characters,
            "plot_threads_advanced": [pt["name"] for pt in active_plot_threads],
            "generated_at": state.get("current_timestamp", "")
        },
        "namespace": MEMORY_NAMESPACE
    })
    
    # Store scene to database
    from storyteller_lib.database_integration import get_db_manager
    db_manager = get_db_manager()
    
    if db_manager:
        try:
            # Store scene content to database
            db_manager.save_scene_content(
                int(current_chapter), 
                int(current_scene), 
                scene_content
            )
            logger.info(f"Scene content stored to database - {len(scene_content)} chars")
        except Exception as e:
            logger.warning(f"Could not store scene to database: {e}")
    
    # Prepare chapters update
    chapters = state.get("chapters", {})
    if current_chapter not in chapters:
        chapters[current_chapter] = {"scenes": {}}
    if "scenes" not in chapters[current_chapter]:
        chapters[current_chapter]["scenes"] = {}
    
    # Store only metadata - no content
    chapters[current_chapter]["scenes"][current_scene] = {
        "db_stored": True,
        "characters": scene_characters
    }
    
    # Log the scene
    from storyteller_lib.story_progress_logger import log_progress
    log_progress("scene_content", chapter_num=current_chapter, scene_num=current_scene, 
                scene_content=scene_content)
    
    # Track scene progression
    try:
        # Extract and track used phrases
        phrases = progression_tracker.extract_phrases_from_content(scene_content, language)
        progression_tracker.add_used_phrases(int(current_chapter), int(current_scene), phrases)
        
        # Analyze and track scene structure
        from storyteller_lib.scene_variety import analyze_scene_structure
        structure_analysis = analyze_scene_structure(scene_content, language)
        progression_tracker.add_scene_structure(
            int(current_chapter), 
            int(current_scene), 
            structure_analysis.structure_pattern,
            variety_requirements.scene_type
        )
        
        # Track main event (simplified for now)
        main_event_type = variety_requirements.scene_type
        main_event_desc = f"{variety_requirements.scene_type} scene with {', '.join(scene_characters[:2])}"
        progression_tracker.add_story_event(
            int(current_chapter),
            int(current_scene),
            main_event_type,
            main_event_desc,
            scene_characters
        )
        
        logger.info(f"Tracked scene progression for Ch{current_chapter}/Sc{current_scene}")
    except Exception as e:
        logger.warning(f"Failed to track scene progression: {e}")
    
    # Track plot progressions that occurred in this scene
    if db_manager and scene_specifications["plot_progressions"]:
        for progression in scene_specifications["plot_progressions"]:
            # Only track if it wasn't already tracked
            if not db_manager.check_plot_progression_exists(progression):
                db_manager.track_plot_progression(
                    progression,
                    int(current_chapter),
                    int(current_scene),
                    f"Occurred in Ch{current_chapter}/Sc{current_scene}"
                )
                logger.info(f"Tracked plot progression: {progression}")
    
    # Track character knowledge changes
    if db_manager and scene_specifications["character_learns"]:
        # Parse character_learns list which contains "CharacterName: knowledge item" strings
        character_knowledge_map = {}
        for learning in scene_specifications["character_learns"]:
            if ": " in learning:
                char_name, knowledge = learning.split(": ", 1)
                if char_name not in character_knowledge_map:
                    character_knowledge_map[char_name] = []
                character_knowledge_map[char_name].append(knowledge)
        
        for char_name, knowledge_list in character_knowledge_map.items():
            # Get character ID
            with db_manager._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM characters WHERE identifier = ? OR name = ?",
                    (char_name, char_name)
                )
                char_result = cursor.fetchone()
                if char_result and db_manager._current_scene_id:
                    char_id = char_result['id']
                    for knowledge in knowledge_list:
                        try:
                            cursor.execute("""
                                INSERT INTO character_knowledge 
                                (character_id, scene_id, knowledge_type, knowledge_content, source)
                                VALUES (?, ?, ?, ?, ?)
                            """, (
                                char_id,
                                db_manager._current_scene_id,
                                'fact',
                                knowledge,
                                f"Learned in Ch{current_chapter}/Sc{current_scene}"
                            ))
                            conn.commit()
                            logger.info(f"Tracked character knowledge: {char_name} learned '{knowledge}'")
                        except Exception as e:
                            logger.warning(f"Failed to track character knowledge: {e}")
    
    # Return the updates to state
    return {
        "current_scene_content": scene_content,
        "last_node": NodeNames.WRITE_SCENE,
        "chapters": chapters
    }