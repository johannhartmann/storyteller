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
    """Prepare author style guidance section for scene writing.
    
    Args:
        author: Author name to emulate
        author_style_guidance: Detailed style guidance
        
    Returns:
        Formatted author style guidance string
    """
    if not author:
        return ""
        
    return f"""
    AUTHOR STYLE GUIDANCE:
    You are writing in the style of {author}. Apply these stylistic elements:
    
    {author_style_guidance}
    """


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
        consistency_result = search_memory_tool.invoke({
            "query": "language_consistency_instruction",
            "namespace": MEMORY_NAMESPACE
        })
        
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
        
        # Add previous scenes in current chapter
        if int(current_scene) > 1:
            # Get previous scenes up to 3 scenes back
            scene_start = max(1, int(current_scene) - 3)
            for i in range(scene_start, int(current_scene)):
                content = db_manager.get_scene_content(int(current_chapter), i)
                if content:
                    # Get first paragraph as summary
                    first_para = content.strip().split('\n\n')[0]
                    summary_parts.append(f"Scene {i}: {first_para[:150]}...")
    
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
    
    # Get story elements
    story_premise = state.get("story_premise", "")
    genre = state.get("genre", "fantasy")
    tone = state.get("tone", "adventurous")
    language = state.get("language", DEFAULT_LANGUAGE)
    author = state.get("author", "")
    author_style_guidance = state.get("author_style_guidance", "")
    
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
    
    # Scene description from brainstorming phase (if available)
    scene_description = state.get("scene_elements", {}).get("scene_approach", f"Scene {current_scene}")
    
    # Get creative elements from brainstorming
    scene_elements = state.get("scene_elements", {})
    active_plot_threads = state.get("active_plot_threads", [])
    
    # Import optimization utilities
    from storyteller_lib.prompt_optimization import (
        get_relevant_characters, summarize_world_elements,
        truncate_scene_content, log_prompt_size
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
    
    # Get only relevant characters for this scene
    scene_context = f"{chapter_outline}\n{scene_description}"
    relevant_characters = get_relevant_characters(all_characters, scene_context, max_characters=5)
    
    # Get world information from database
    world_elements = {}
    if db_manager and db_manager._db:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT category, element_key, element_value
                FROM world_elements
            """)
            for row in cursor.fetchall():
                if row['category'] not in world_elements:
                    world_elements[row['category']] = {}
                world_elements[row['category']][row['element_key']] = row['element_value']
    
    # Identify which characters are in this scene
    scene_characters = list(relevant_characters.keys())
    
    # Prepare various guidance sections
    author_guidance = _prepare_author_style_guidance(author, author_style_guidance)
    language_guidance = _prepare_language_guidance(language)
    emotional_guidance = _prepare_emotional_guidance(relevant_characters, scene_characters, tone, genre)
    previous_context = _generate_previous_scenes_summary(state, db_manager)
    
    # Get database context if available
    database_context = _prepare_database_context(current_chapter, current_scene)
    
    # Import helper functions from original scenes.py
    from storyteller_lib.scene_helpers import (
        _prepare_creative_guidance,
        _prepare_plot_thread_guidance,
        _prepare_worldbuilding_guidance
    )
    
    creative_guidance = _prepare_creative_guidance(scene_elements, current_chapter, current_scene)
    plot_guidance = _prepare_plot_thread_guidance(active_plot_threads)
    world_guidance = _prepare_worldbuilding_guidance(world_elements, chapter_outline)
    
    # Truncate story premise and chapter outline
    premise_brief = story_premise[:200] + "..." if len(story_premise) > 200 else story_premise
    outline_brief = chapter_outline[:300] + "..." if len(chapter_outline) > 300 else chapter_outline
    
    # Construct the scene writing prompt
    prompt = f"""You are a skilled novelist writing Chapter {current_chapter}, Scene {current_scene} of a {genre} story.

    STORY CONTEXT:
    Premise: {premise_brief}
    Genre: {genre}
    Tone: {tone}
    
    CHAPTER FOCUS:
    {outline_brief}
    
    CURRENT SCENE:
    Scene {current_scene}: {scene_description}
    
    {previous_context}
    {database_context}
    {creative_guidance}
    {plot_guidance}
    {emotional_guidance}
    {world_guidance}
    {author_guidance}
    {language_guidance}
    
    WRITING GUIDELINES:
    1. Start the scene immediately with action, dialogue, or vivid description
    2. Show character emotions through actions and dialogue, not exposition
    3. Use all five senses to create immersive descriptions
    4. Advance the plot while developing characters
    5. End with a hook that propels the reader forward
    6. Maintain consistent POV throughout the scene
    7. Write 800-1200 words
    
    Write the scene now:
    """
    
    # Log prompt size
    log_prompt_size(prompt, f"scene writing Ch{current_chapter}/Sc{current_scene}")
    
    # Generate the scene
    messages = [HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    scene_content = response.content
    
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
    
    # Return the updates to state
    return {
        "current_scene_content": scene_content,
        "last_node": NodeNames.WRITE_SCENE,
        "chapters": chapters
    }