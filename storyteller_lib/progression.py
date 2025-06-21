"""
StoryCraft Agent - Story progression and character management nodes.

This is a refactored version optimized for LangGraph's native edge system,
removing router-specific code that could cause infinite loops.
"""

from typing import Dict, List
import json

from storyteller_lib.config import llm, MEMORY_NAMESPACE, cleanup_old_state, log_memory_usage, get_llm_with_structured_output
from storyteller_lib.models import StoryState
# Memory manager imports removed - using state and database instead
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from storyteller_lib import track_progress
from storyteller_lib.constants import NodeNames
from storyteller_lib.story_context import get_context_provider
from storyteller_lib.logger import get_logger

logger = get_logger(__name__)

def generate_scene_progress_report(state: StoryState, chapter_num: str, scene_num: str) -> str:
    """Generate a progress report after scene completion.
    
    Args:
        state: Current story state
        chapter_num: Chapter number just completed
        scene_num: Scene number just completed
        
    Returns:
        Formatted progress report string
    """
    from storyteller_lib.book_statistics import calculate_book_stats
    from storyteller_lib.database_integration import get_db_manager
    
    # Get basic scene counts
    chapters = state.get("chapters", {})
    total_chapters = len(chapters)
    current_chapter_data = chapters.get(chapter_num, {})
    scenes_in_chapter = len(current_chapter_data.get("scenes", {}))
    
    # Calculate progress
    completed_chapters = int(chapter_num) - 1
    completed_scenes_current_chapter = int(scene_num)
    
    # Get database statistics
    db_manager = get_db_manager()
    stats = {}
    if db_manager:
        try:
            stats = calculate_book_stats(db_manager)
        except Exception as e:
            logger.warning(f"Could not calculate book stats: {e}")
    
    # Extract stats
    total_words = stats.get('current_words', 0)
    total_pages = stats.get('current_pages', 0)
    avg_scene_words = stats.get('avg_scene_words', 0)
    
    # Format progress bar
    scenes_per_chapter = scenes_in_chapter  # Assume consistent
    total_scenes = total_chapters * scenes_per_chapter
    completed_scenes = completed_chapters * scenes_per_chapter + completed_scenes_current_chapter
    progress_percentage = (completed_scenes / total_scenes * 100) if total_scenes > 0 else 0
    
    # Create progress bar
    bar_length = 20
    filled_length = int(bar_length * progress_percentage / 100)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    # Build the report
    report = f"""
📊 **Progress Report - Chapter {chapter_num}, Scene {scene_num} Complete**

📖 **Story Progress:**
{bar} {progress_percentage:.1f}%
- Chapter {chapter_num} of {total_chapters} 
- Scene {scene_num} of {scenes_in_chapter} in current chapter
- Total scenes completed: {completed_scenes} of {total_scenes}

📝 **Current Statistics:**
- Total words written: {total_words:,}
- Estimated pages: {total_pages}
- Average words per scene: {avg_scene_words:,}
- Words remaining (estimate): {max(0, (total_scenes - completed_scenes) * avg_scene_words):,}

🎯 **Next:** Chapter {chapter_num}, Scene {int(scene_num) + 1}
"""
    
    # Add milestone messages
    if completed_scenes_current_chapter == scenes_in_chapter:
        report += f"\n🎉 **Chapter {chapter_num} Complete!**"
    
    if progress_percentage >= 25 and progress_percentage < 26:
        report += "\n📍 **Milestone: 25% Complete!** - The journey is well underway."
    elif progress_percentage >= 50 and progress_percentage < 51:
        report += "\n📍 **Milestone: 50% Complete!** - Halfway through the story!"
    elif progress_percentage >= 75 and progress_percentage < 76:
        report += "\n📍 **Milestone: 75% Complete!** - The climax approaches!"
    
    return report

def generate_chapter_progress_report(state: StoryState, chapter_num: str) -> str:
    """Generate a progress report after chapter completion.
    
    Args:
        state: Current story state
        chapter_num: Chapter number just completed
        
    Returns:
        Formatted progress report string
    """
    from storyteller_lib.book_statistics import calculate_book_stats
    from storyteller_lib.database_integration import get_db_manager
    
    # Get basic counts
    chapters = state.get("chapters", {})
    total_chapters = len(chapters)
    
    # Get database statistics
    db_manager = get_db_manager()
    stats = {}
    if db_manager:
        try:
            stats = calculate_book_stats(db_manager)
        except Exception as e:
            logger.warning(f"Could not calculate book stats: {e}")
    
    # Extract stats
    total_words = stats.get('current_words', 0)
    total_pages = stats.get('current_pages', 0)
    avg_scene_words = stats.get('avg_scene_words', 0)
    
    # Calculate progress
    completed_chapters = int(chapter_num)
    progress_percentage = (completed_chapters / total_chapters * 100) if total_chapters > 0 else 0
    
    # Create progress bar
    bar_length = 20
    filled_length = int(bar_length * progress_percentage / 100)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    # Get chapter-specific stats
    chapter_data = chapters.get(chapter_num, {})
    chapter_title = chapter_data.get("title", f"Chapter {chapter_num}")
    scenes_in_chapter = len(chapter_data.get("scenes", {}))
    
    # Build the report
    report = f"""
🎉 **Chapter {chapter_num} Complete!**

📊 **"{chapter_title}"**
- Scenes written: {scenes_in_chapter}
- Estimated chapter words: {scenes_in_chapter * avg_scene_words:,}

📖 **Overall Progress:**
{bar} {progress_percentage:.1f}%
- Chapters completed: {completed_chapters} of {total_chapters}
- Total words written: {total_words:,}
- Total pages: {total_pages}

📈 **Story Statistics:**
- Average words per scene: {avg_scene_words:,}
- Chapters remaining: {total_chapters - completed_chapters}
- Estimated words remaining: {max(0, (total_chapters - completed_chapters) * scenes_in_chapter * avg_scene_words):,}
"""
    
    # Add milestone messages for chapter completion
    if completed_chapters == total_chapters // 2:
        report += "\n🌟 **Major Milestone: Halfway through the story!**"
    elif completed_chapters == total_chapters - 1:
        report += "\n🏁 **Almost there! Just one more chapter to go!**"
    
    # Add next chapter preview if available
    if str(int(chapter_num) + 1) in chapters:
        next_chapter = chapters[str(int(chapter_num) + 1)]
        next_title = next_chapter.get("title", f"Chapter {int(chapter_num) + 1}")
        report += f"\n🎯 **Next Chapter:** \"{next_title}\""
    
    return report

@track_progress
def update_world_elements(state: StoryState) -> Dict:
    """Update world elements based on developments in the current scene."""
    from storyteller_lib.prompt_templates import render_prompt
    
    chapters = state["chapters"]
    world_elements = state.get("world_elements", {})
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    
    # Get the scene content from temporary state or database
    scene_content = state.get("current_scene_content", "")
    
    # If not in state, get from database
    if not scene_content:
        from storyteller_lib.story_context import get_context_provider
        context_provider = get_context_provider()
        if context_provider:
            scene_data = context_provider.get_scene(int(current_chapter), int(current_scene))
            if scene_data:
                scene_content = scene_data.get("content", "")
    
    if not scene_content:
        logger.warning(f"No scene content found for Ch{current_chapter}/Sc{current_scene}")
        return {}
    
    # Use template system
    from storyteller_lib.prompt_templates import render_prompt
    
    # Get language from state
    language = state.get("language", "english")
    
    # Get structured world updates directly
    from storyteller_lib.config import get_llm_with_structured_output
    from pydantic import BaseModel, Field
    from typing import Dict, Any, Optional
    
    class WorldElementUpdate(BaseModel):
        """A single world element update."""
        category: str = Field(description="Category of the world element (e.g., GEOGRAPHY, CULTURE)")
        element: str = Field(description="Specific element being updated")
        old_value: Optional[str] = Field(None, description="Previous value if updating existing element")
        new_value: str = Field(description="New or updated value")
        reason: str = Field(description="Why this update is needed based on the scene")
    
    class WorldUpdatesResponse(BaseModel):
        """World updates from a scene."""
        updates: List[WorldElementUpdate] = Field(description="List of world element updates")
        
    # Create prompt for structured world updates
    prompt = render_prompt(
        'world_element_updates',
        language=language,
        scene_content=scene_content,
        current_chapter=current_chapter,
        current_scene=current_scene
    )
    
    structured_llm = get_llm_with_structured_output(WorldUpdatesResponse)
    world_updates_response = structured_llm.invoke(prompt)
    
    # Convert to the expected dictionary format
    world_updates = {}
    if world_updates_response and world_updates_response.updates:
        for update in world_updates_response.updates:
            if update.category not in world_updates:
                world_updates[update.category] = {}
            world_updates[update.category][update.element] = update.new_value
    
    # World updates are stored in the database world_elements table
    
    # World state is tracked through the database world_elements table
    # No need for separate memory-based world state tracker
    try:
        results = []
        
        # Extract the world state tracker from the results
        world_state_tracker = None
        if results and len(results) > 0:
            for item in results:
                if hasattr(item, 'key') and item.key == "world_state_tracker":
                    world_state_tracker = {"key": item.key, "value": item.value}
                    break
        
        if world_state_tracker and "value" in world_state_tracker:
            tracker = world_state_tracker["value"]
            
            # Update the current state with the new changes
            current_state = tracker.get("current_state", {}).copy()
            for category, updates in world_updates.items():
                if category in current_state:
                    # Update existing category
                    for key, value in updates.items():
                        current_state[category][key] = value
                else:
                    # Add new category
                    current_state[category] = updates
            
            # Record the changes
            changes = tracker.get("changes", [])
            if world_updates:
                changes.append({
                    "chapter": current_chapter,
                    "scene": current_scene,
                    "updates": world_updates
                })
            
            # Update the tracker
            updated_tracker = {
                "initial_state": tracker.get("initial_state", {}),
                "current_state": current_state,
                "changes": changes,
                "revelations": tracker.get("revelations", [])
            }
            
            # Store the updated tracker
            # World state is tracked through database world_elements table
    except Exception as e:
        print(f"Error updating world state tracker: {str(e)}")
    
    # Only return updates if there are any
    if not world_updates:
        return {
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content=f"I've checked for world developments in scene {current_scene} of chapter {current_chapter}, but found no significant updates to the established world elements.")
            ]
        }
    
    # Return the updates
    return {
        "world_elements": world_updates,
        "messages": [
            *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
            AIMessage(content=f"I've updated the world elements with new developments from scene {current_scene} of chapter {current_chapter}.")
        ]
    }

@track_progress
def update_character_profiles(state: StoryState) -> Dict:
    """Update character profiles based on developments in the current scene."""
    from storyteller_lib.prompt_templates import render_prompt
    
    chapters = state["chapters"]
    characters = state["characters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    language = state.get("language", "english")
    
    # Get the scene content from temporary state or database
    scene_content = state.get("current_scene_content", "")
    
    # If not in state, get from database
    if not scene_content:
        from storyteller_lib.story_context import get_context_provider
        context_provider = get_context_provider()
        if context_provider:
            scene_data = context_provider.get_scene(int(current_chapter), int(current_scene))
            if scene_data:
                scene_content = scene_data.get("content", "")
    
    if not scene_content:
        logger.warning(f"No scene content found for Ch{current_chapter}/Sc{current_scene}")
        return {}
    
    # Import optimization utilities
    from storyteller_lib.logger import get_logger
    from storyteller_lib.prompt_optimization import (
        summarize_character, log_prompt_size
    )
    logger = get_logger(__name__)
    
    # Import entity relevance detection
    from storyteller_lib.entity_relevance import (
        analyze_scene_entities, filter_characters_for_scene
    )
    
    # Use full scene content for character analysis - NO TRUNCATION
    # Character development can happen anywhere in the scene
    
    # Use LLM to identify relevant characters
    chapter_outline = ""  # We don't have chapter outline here, use scene content
    relevant_entities = analyze_scene_entities(
        chapter_outline=chapter_outline,
        scene_description=scene_content[:500],  # Use first part of scene as description
        all_characters=characters,
        world_elements={},
        language=language
    )
    
    # Filter to relevant characters
    relevant_characters = filter_characters_for_scene(
        all_characters=characters,
        relevant_entities=relevant_entities,
        include_limit=5
    )
    
    scene_characters = [(char_id, char_data.get('name', '')) 
                       for char_id, char_data in relevant_characters.items()]
    
    logger.info(f"Characters found in scene: {[name for _, name in scene_characters]}")
    
    # Get structured character updates directly
    from pydantic import BaseModel, Field
    from typing import List, Optional, Dict
    
    class RelationshipChange(BaseModel):
        """A change in relationship between two characters."""
        other_character: str = Field(description="Name of the other character")
        change_description: str = Field(description="Description of how the relationship changed")
    
    class CharacterUpdate(BaseModel):
        """Updates for a single character."""
        character_name: str = Field(description="Name of the character")
        new_facts: List[str] = Field(default_factory=list, description="New facts learned about the character (max 2)")
        emotional_change: Optional[str] = Field(default=None, description="Change in emotional state")
        relationship_changes: List[RelationshipChange] = Field(default_factory=list, description="Changes in relationships with other characters")
    
    class CharacterUpdatesResponse(BaseModel):
        """All character updates from a scene."""
        updates: List[CharacterUpdate] = Field(description="List of character updates")
    
    # Create prompt for structured character updates
    prompt = render_prompt(
        'character_updates',
        language=language,
        scene_content=scene_content,  # Use full scene content, not truncated
        current_chapter=current_chapter,
        current_scene=current_scene,
        characters=[name for _, name in scene_characters]
    )
    
    # Log prompt size
    log_prompt_size(prompt, "character update analysis")
    
    structured_llm = get_llm_with_structured_output(CharacterUpdatesResponse)
    character_updates_response = structured_llm.invoke(prompt)
    
    # Import the character arc tracking module
    from storyteller_lib.character_arcs import update_character_arc, evaluate_arc_consistency
    
    # For each character, check if there are updates and apply them
    updated_characters = state["characters"].copy()
    character_updates = {}
    
    # Process the structured updates
    if character_updates_response and character_updates_response.updates:
        for update in character_updates_response.updates:
            # Find the character in our character dictionary
            char_id = None
            for cid, cdata in characters.items():
                if cdata.get('name', '') == update.character_name:
                    char_id = cid
                    break
            
            if char_id and char_id in updated_characters:
                # Apply the updates to the character
                char_data = updated_characters[char_id]
                
                # Add new knowledge using the character knowledge manager
                if update.new_facts:
                    from storyteller_lib.character_knowledge_manager import CharacterKnowledgeManager
                    from storyteller_lib.database_integration import get_db_manager
                    knowledge_manager = CharacterKnowledgeManager()
                    db_manager = get_db_manager()
                    scene_id = db_manager.get_scene_id(int(current_chapter), int(current_scene))
                    
                    # Get character ID from database
                    character_id = None
                    if db_manager and db_manager._db:
                        with db_manager._db._get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("SELECT id FROM characters WHERE identifier = ?", (update.character_name,))
                            result = cursor.fetchone()
                            if result:
                                character_id = result['id']
                    
                    # Add knowledge to the character
                    if character_id and scene_id:
                        for fact in update.new_facts[:2]:  # Max 2 facts
                            knowledge_manager.add_knowledge(character_id, fact, scene_id)
                
                # Update emotional state
                if update.emotional_change:
                    if 'emotional_state' not in char_data:
                        char_data['emotional_state'] = {}
                    char_data['emotional_state']['current'] = update.emotional_change
                
                # Update relationships
                if update.relationship_changes:
                    if 'relationships' not in char_data:
                        char_data['relationships'] = {}
                    for rel_change in update.relationship_changes:
                        other_char = rel_change.other_character
                        change_desc = rel_change.change_description
                        if other_char in char_data['relationships']:
                            # Update existing relationship
                            if isinstance(char_data['relationships'][other_char], dict):
                                char_data['relationships'][other_char]['dynamics'] = change_desc
                        else:
                            # Create new relationship
                            char_data['relationships'][other_char] = {
                                'type': 'evolved',
                                'dynamics': change_desc
                            }
                
                character_updates[char_id] = char_data
    
    # Then, use the character arc tracking module for each character that appears in the scene
    for char_name, char_data in characters.items():
        # Skip if char_data is None
        if char_data is None:
            continue
            
        # Check if character appears in the scene
        if char_name.lower() in scene_content.lower() or (char_data.get("name", "").lower() in scene_content.lower()):
            try:
                # Update character arc
                arc_updates = update_character_arc(char_data, scene_content, current_chapter, current_scene)
                
                if arc_updates and isinstance(arc_updates, dict):
                    # If we already have updates for this character, merge them
                    if char_name in character_updates:
                        for key, value in arc_updates.items():
                            if key not in character_updates[char_name]:
                                character_updates[char_name][key] = value
                    else:
                        character_updates[char_name] = arc_updates
            except Exception as e:
                print(f"Error updating character arc for {char_name}: {str(e)}")
            
            # Character updates are stored in the database characters table
    
    # Update state - return the full updated characters dictionary if there were changes
    if character_updates:
        return {
            "characters": updated_characters,  # Return the full updated dictionary
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content=f"I've updated character profiles with emotional developments and arc progression from scene {current_scene} of chapter {current_chapter}.")
            ]
        }
    else:
        # No updates needed
        return {
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content=f"I've reviewed scene {current_scene} of chapter {current_chapter} but found no significant character updates needed.")
            ]
        }

@track_progress
def review_continuity(state: StoryState) -> Dict:
    """Dedicated continuity review module that checks the overall story for inconsistencies."""
    # This is called after completing a chapter to check for broader continuity issues
    chapters = state["chapters"]
    characters = state["characters"]
    revelations = state["revelations"]
    global_story = state["global_story"]
    current_chapter = state.get("current_chapter", "1")
    world_elements = state.get("world_elements", {})
    
    # Default message in case of early returns
    message = AIMessage(content=f"I've performed a continuity review after Chapter {current_chapter}.")
    
    # Create a consistent key for references
    review_key = f"continuity_review_ch{current_chapter}"
    
    # Get all completed chapters and their scenes for review
    completed_chapters = []
    for chapter_num in sorted(chapters.keys(), key=int):
        chapter = chapters[chapter_num]
        if all(scene.get("content") for scene in chapter["scenes"].values()):
            completed_chapters.append(chapter_num)
    
    # If there are fewer than 2 completed chapters, not enough for full continuity check
    if len(completed_chapters) < 2:
        return {
            "continuity_phase": "complete",  # Mark this phase as complete
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content="Not enough completed chapters for a full continuity review yet.")
            ]
        }
    
    # Import optimization utilities
    from storyteller_lib.prompt_optimization import create_context_summary, log_prompt_size
    
    # Prepare optimized chapter summaries for review
    chapter_summaries = []
    for chapter_num in completed_chapters[-3:]:  # Only last 3 chapters
        chapter = chapters[chapter_num]
        # Just chapter title and brief outline
        outline_brief = chapter['outline'][:200] + "..." if len(chapter['outline']) > 200 else chapter['outline']
        chapter_summaries.append(f"Chapter {chapter_num}: {chapter['title']} - {outline_brief}")
    
    # Get database context if available
    database_continuity_data = ""
    context_provider = get_context_provider()
    if context_provider:
        try:
            # Get continuity data for the current chapter
            continuity_data = context_provider.get_continuity_check_data(int(current_chapter))
            
            if continuity_data and continuity_data.get('potential_issues'):
                issues = []
                for issue in continuity_data['potential_issues']:
                    issues.append(f"- {issue['type']}: {issue['description']}")
                
                if issues:
                    database_continuity_data = f"""
        DATABASE DETECTED ISSUES:
        {chr(10).join(issues)}
        """
            
            # Add character tracking info
            if continuity_data and continuity_data.get('character_tracking'):
                char_tracking = []
                for char_id, data in continuity_data['character_tracking'].items():
                    if data['appearances']:
                        char_tracking.append(f"- {char_id}: appears in scenes {[a['scene'] for a in data['appearances']]}")
                
                if char_tracking:
                    database_continuity_data += f"""
        
        CHARACTER APPEARANCES THIS CHAPTER:
        {chr(10).join(char_tracking)}
        """
        except Exception as e:
            # Log but don't fail if database context is unavailable
            pass
    
    # Prepare world elements section
    world_elements_section = ""
    if world_elements:
        world_elements_section = f"""
        WORLD ELEMENTS:
        {world_elements}
        
        Check for any inconsistencies in how the world elements are portrayed across chapters.
        """
    
    # Import character summary utility
    from storyteller_lib.prompt_optimization import create_character_summary_batch, summarize_world_elements
    
    # Create character summary
    character_summary = create_character_summary_batch(characters, max_characters=10)
    
    # Create world elements summary
    world_summary = ""
    if world_elements:
        world_summary = summarize_world_elements(world_elements, max_words_per_category=30)
        world_elements_section = f"""
        WORLD ELEMENTS (Summary):
        {json.dumps(world_summary, indent=2)}
        """
    
    # Prompt for continuity review
    prompt = f"""
    Perform a focused continuity review of the story so far:
    
    STORY PREMISE:
    {global_story[:500]}...
    
    RECENT CHAPTERS:
    {chr(10).join(chapter_summaries)}
    
    KEY CHARACTERS:
    {character_summary}
    
    {world_elements_section}
    
    {database_continuity_data}
    
    Analyze for CRITICAL issues only:
    1. Major contradictions or timeline errors
    2. Unresolved central plot threads
    3. Significant character inconsistencies
    4. Major world-building contradictions
    
    For each CRITICAL issue found:
    - Brief description (1-2 sentences)
    - Severity (only report if 7-10)
    - Quick fix suggestion
    
    Keep response under 500 words.
    """
    
    # Log prompt size before sending
    log_prompt_size(prompt, "continuity review")
    
    # Generate the continuity review
    review_result = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Store the review in memory
    # Review results are temporary and included in state
    
    # Check if there are issues that need resolution
    needs_resolution = "needs resolution" in review_result.lower() or "critical issue" in review_result.lower()
    
    # Create a continuity issue object for revelations
    if needs_resolution:
        # Extract issues to resolve
        issues_to_resolve = []
        for line in review_result.split(chr(10)):
            if "issue:" in line.lower() or "problem:" in line.lower() or "inconsistency:" in line.lower():
                issues_to_resolve.append(line.strip())
        
        continuity_issue = {
            "after_chapter": current_chapter,
            "review_key": review_key,
            "needs_resolution": True,
            "resolution_status": "pending",
            "issues_to_resolve": issues_to_resolve
        }
        
        # Update revelations with the continuity issue
        revelations_update = {
            "continuity_issues": [continuity_issue]
        }
        
        # Set the continuity phase to indicate resolution is needed
        return {
            "revelations": revelations_update,
            "continuity_phase": "needs_resolution",
            "resolution_index": 0,  # Start with the first issue
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content=f"I've completed a continuity review after Chapter {current_chapter} and found issues that need resolution before continuing.")
            ]
        }
    else:
        # No issues that need resolution
        
        # Chapter completion is tracked through state
        
        # Log that the chapter is complete
        print(f"{chr(10)}==== CHAPTER {current_chapter} COMPLETED ====")
        print(f"Continuity review completed for Chapter {current_chapter} with no critical issues.")
        print(f"The chapter is now ready to be written to the output file.")
        print(f"================================={chr(10)}")
        
        # Chapter completion logging is handled by the progress callback
        # No need for duplicate logging here
        
        return {
            "continuity_phase": "complete",
            "chapter_complete": True,  # Add this flag to indicate the chapter is complete
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content=f"I've completed a continuity review after Chapter {current_chapter}. No critical issues found.")
            ]
        }

@track_progress
def resolve_continuity_issues(state: StoryState) -> Dict:
    """Resolve identified continuity issues."""
    chapters = state["chapters"]
    characters = state["characters"]
    revelations = state["revelations"]
    current_chapter = state.get("current_chapter", "1")
    resolution_index = state.get("resolution_index", 0)
    world_elements = state.get("world_elements", {})
    
    # Find the current continuity review that needs resolution
    current_review = None
    for review in revelations.get("continuity_issues", []):
        if review.get("needs_resolution") and review.get("resolution_status") == "pending":
            current_review = review
            break
    
    # If no review needs resolution, we're done
    if not current_review:
        return {
            "continuity_phase": "complete",
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content="No continuity issues need resolution at this time.")
            ]
        }
    
    # Get the issues to resolve
    issues_to_resolve = current_review.get("issues_to_resolve", [])
    
    # If no issues or we've resolved all issues, mark the review as complete
    if not issues_to_resolve or resolution_index >= len(issues_to_resolve):
        # Update the review status
        updated_review = current_review.copy()
        updated_review["resolution_status"] = "completed"
        updated_review["needs_resolution"] = False
        
        # Update revelations with the updated review
        revelations_update = {
            "continuity_issues": [updated_review]
        }
        
        return {
            "revelations": revelations_update,
            "continuity_phase": "complete",
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content="All continuity issues have been resolved.")
            ]
        }
    
    # Get the current issue to resolve
    current_issue = issues_to_resolve[resolution_index]
    
    # Get the review key to retrieve the full review from memory
    review_key = current_review.get("review_key")
    full_review = None
    
    if review_key:
        try:
            # Reviews are now stored in database
            # TODO: Implement database retrieval for reviews if needed
            full_review = None
        except Exception as e:
            print(f"Error retrieving full review: {str(e)}")
    
    # Prepare the prompt for resolving the issue
    prompt = f"""
    You need to resolve the following continuity issue in the story:
    
    ISSUE TO RESOLVE:
    {current_issue}
    
    STORY CONTEXT:
    {full_review if full_review else "No additional context available."}
    
    WORLD ELEMENTS:
    {world_elements}
    
    Provide a detailed plan to resolve this continuity issue. Your plan should:
    1. Identify the specific changes needed to resolve the issue
    2. Explain how these changes maintain consistency with the rest of the story
    3. Specify which chapters and scenes need to be updated
    4. Provide any new content or revisions needed
    
    Your resolution should be comprehensive and ensure that the story remains coherent and engaging.
    """
    
    # Generate the resolution plan
    resolution_plan = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Resolution plan is temporary and included in the state
    
    # Increment the resolution index for the next issue
    next_resolution_index = resolution_index + 1
    
    # Check if we've resolved all issues
    if next_resolution_index >= len(issues_to_resolve):
        # Update the review status
        updated_review = current_review.copy()
        updated_review["resolution_status"] = "completed"
        updated_review["needs_resolution"] = False
        
        # Update revelations with the updated review
        revelations_update = {
            "continuity_issues": [updated_review]
        }
        
        return {
            "revelations": revelations_update,
            "resolution_index": next_resolution_index,
            "continuity_phase": "complete",
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content=f"I've resolved the continuity issue: {current_issue}{chr(10)}{chr(10)}Resolution Plan:{chr(10)}{resolution_plan}{chr(10)}{chr(10)}All continuity issues have been resolved.")
            ]
        }
    else:
        # More issues to resolve
        return {
            "resolution_index": next_resolution_index,
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content=f"I've resolved the continuity issue: {current_issue}{chr(10)}{chr(10)}Resolution Plan:{chr(10)}{resolution_plan}{chr(10)}{chr(10)}Moving on to the next issue.")
            ]
        }

@track_progress
def advance_to_next_scene_or_chapter(state: StoryState) -> Dict:
    """Move to the next scene or chapter, or complete the story if all chapters are done."""
    chapters = state["chapters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    
    # Get the current chapter data
    chapter = chapters[current_chapter]
    
    # Calculate the next scene or chapter
    next_scene = str(int(current_scene) + 1)
    
    # Check if there are more unwritten scenes in the current chapter
    unwritten_scenes = []
    for scene_num, scene_data in chapter["scenes"].items():
        if not scene_data.get("db_stored", False):
            unwritten_scenes.append(int(scene_num))
    
    if unwritten_scenes:
        # Find the next unwritten scene
        unwritten_scenes.sort()
        next_unwritten = str(unwritten_scenes[0])
        
        # Generate progress report after scene completion
        progress_report = generate_scene_progress_report(state, current_chapter, current_scene)
        
        # Get cleanup updates for scene transition
        cleanup_updates = cleanup_old_state(state, current_chapter, current_scene)
        
        # Move to the next unwritten scene in the same chapter
        return {
            "current_scene": next_unwritten,
            "current_scene_content": None,  # Clear previous scene content
            "continuity_phase": "complete",  # Reset continuity phase
            # Include cleanup updates
            **cleanup_updates,
            # Add memory tracking
            "memory_usage": {
                f"scene_transition_{current_chapter}_{current_scene}_to_{next_unwritten}": log_memory_usage(f"Scene transition {current_scene} to {next_unwritten}")
            },
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content=progress_report),
                AIMessage(content=f"Moving on to write scene {next_unwritten} of chapter {current_chapter}.")
            ]
        }
    else:
        # Move to the next chapter
        next_chapter = str(int(current_chapter) + 1)
        
        # Generate chapter completion progress report
        progress_report = generate_chapter_progress_report(state, current_chapter)
        
        # Check if the next chapter exists
        if next_chapter in chapters:
            # Get cleanup updates for old state data
            cleanup_updates = cleanup_old_state(state, current_chapter)
            
            # Return updates with cleanup
            return {
                "current_chapter": next_chapter,
                "current_scene": "1",  # Start with first scene of new chapter
                "current_scene_content": None,  # Clear scene content
                "continuity_phase": "complete",  # Reset continuity phase
                # Include cleanup updates
                **cleanup_updates,
                # Add memory tracking
                "memory_usage": {
                    f"chapter_transition_{current_chapter}_to_{next_chapter}": log_memory_usage(f"Chapter transition {current_chapter} to {next_chapter}")
                },
                "messages": [
                    *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                    AIMessage(content=progress_report),
                    AIMessage(content=f"Chapter {current_chapter} is complete. Moving on to chapter {next_chapter}.")
                ]
            }
        else:
            # All chapters are complete
            return {
                "completed": True,
                "continuity_phase": "complete",  # Reset continuity phase
                "messages": [
                    *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                    AIMessage(content="The story is now complete! I'll compile the final narrative for you.")
                ]
            }

@track_progress
def compile_final_story(state: StoryState) -> Dict:
    """Compile the final story from all chapters and scenes."""
    chapters = state["chapters"]
    characters = state["characters"]
    world_elements = state.get("world_elements", {})
    
    # Get story configuration from database
    from storyteller_lib.database_integration import get_db_manager
    from storyteller_lib.logger import get_logger
    logger = get_logger(__name__)
    
    db_manager = get_db_manager()
    if not db_manager:
        raise RuntimeError("Database manager not available")
    
    # Fetch story metadata from database
    with db_manager._db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT genre, tone, author, initial_idea, global_story
            FROM story_config WHERE id = 1
        """)
        config = cursor.fetchone()
    
    if not config:
        raise RuntimeError("Story configuration not found in database")
    
    genre = config['genre'] or 'fantasy'
    tone = config['tone'] or 'adventurous'
    author = config['author'] or ''
    initial_idea = config['initial_idea'] or ''
    global_story = config['global_story'] or ''
    
    # Load full chapter and scene content from database
    if db_manager:
        # Load actual scene content from database for each chapter
        for chapter_num in chapters.keys():
            for scene_num in chapters[chapter_num].get("scenes", {}).keys():
                try:
                    scene_content = db_manager.get_scene_content(int(chapter_num), int(scene_num))
                    if scene_content:
                        # Ensure the scene dictionary exists
                        if "scenes" not in chapters[chapter_num]:
                            chapters[chapter_num]["scenes"] = {}
                        if scene_num not in chapters[chapter_num]["scenes"]:
                            chapters[chapter_num]["scenes"][scene_num] = {}
                        # Add the content to the scene
                        chapters[chapter_num]["scenes"][scene_num]["content"] = scene_content
                    else:
                        logger.warning(f"No content found in database for Chapter {chapter_num}, Scene {scene_num}")
                except Exception as e:
                    logger.error(f"Failed to load scene content for Chapter {chapter_num}, Scene {scene_num}: {e}")
    
    # Check for unresolved plot threads
    from storyteller_lib.plot_threads import check_plot_thread_resolution
    plot_thread_resolution = check_plot_thread_resolution(state)
    
    # Add a warning about unresolved plot threads if any exist
    unresolved_threads_warning = ""
    if not plot_thread_resolution.get("all_major_threads_resolved", True):
        unresolved_threads = plot_thread_resolution.get("unresolved_major_threads", [])
        unresolved_threads_warning = f"{chr(10)}{chr(10)}## WARNING: Unresolved Plot Threads{chr(10)}{chr(10)}"
        unresolved_threads_warning += f"The following major plot threads were not resolved in the story:{chr(10)}{chr(10)}"
        
        for thread in unresolved_threads:
            unresolved_threads_warning += f"- **{thread['name']}**: {thread['description']}{chr(10)}"
            unresolved_threads_warning += f"  - First appeared: {thread['first_appearance']}{chr(10)}"
            unresolved_threads_warning += f"  - Last mentioned: {thread['last_appearance']}{chr(10)}{chr(10)}"
    
    # Compile the story content
    story_content = []
    
    # Add a title and introduction
    story_title = "Untitled Story"  # Default title
    
    # Try to get title from database first
    try:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title FROM story_config WHERE id = 1")
            result = cursor.fetchone()
            if result and result['title']:
                story_title = result['title']
            else:
                # Fallback to extracting from global_story
                # Try to extract a title from the global story
                title_lines = [line for line in global_story.split(chr(10)) if "title" in line.lower() or "titel" in line.lower()]
                if title_lines:
                    # Extract the title from the first line that mentions "title"
                    title_line = title_lines[0]
                    title_parts = title_line.split(":")
                    if len(title_parts) > 1:
                        story_title = title_parts[1].strip().strip('"').strip("'")
    except Exception as e:
        logger.warning(f"Could not get title from database: {e}")
        # Fallback title extraction
        title_lines = [line for line in global_story.split(chr(10)) if "title" in line.lower() or "titel" in line.lower()]
        if title_lines:
            title_line = title_lines[0]
            title_parts = title_line.split(":")
            if len(title_parts) > 1:
                story_title = title_parts[1].strip().strip('"').strip("'")
    
    # Add the title
    story_content.append(f"# {story_title}")
    story_content.append("")
    
    # Add an introduction if available
    story_content.append("## Introduction")
    story_content.append("")
    story_content.append(global_story[:500] + "...")
    story_content.append("")
    
    # Add warning about unresolved plot threads if any exist
    if unresolved_threads_warning:
        story_content.append(unresolved_threads_warning)
    
    # Add each chapter and its scenes
    for chapter_num in sorted(chapters.keys(), key=int):
        chapter = chapters[chapter_num]
        
        # Add chapter title
        story_content.append(f"## Chapter {chapter_num}: {chapter['title']}")
        story_content.append("")
        
        # Add each scene
        for scene_num in sorted(chapter["scenes"].keys(), key=int):
            scene = chapter["scenes"][scene_num]
            
            # Add scene content (handle missing content gracefully)
            if "content" in scene and scene["content"]:
                story_content.append(scene["content"])
                story_content.append("")
            else:
                # Log missing content but continue compilation
                from storyteller_lib.logger import get_logger
                logger = get_logger(__name__)
                logger.warning(f"Chapter {chapter_num}, Scene {scene_num} is missing content")
                story_content.append(f"[Scene {scene_num} content missing]")
                story_content.append("")
    
    # Join all content
    final_story = chr(10).join(story_content)
    
    # Store the final story in memory
    # Final story is stored in database and written to output file
    
    # Import optimization utility
    from storyteller_lib.prompt_optimization import log_prompt_size
    
    # Create a summary of the story
    summary_prompt = f"""
    Create a brief summary of this story:
    
    Title: {story_title}
    Genre: {genre}
    Tone: {tone}
    
    Story premise:
    {global_story[:300]}...
    
    The story has {len(chapters)} chapters covering a hero's journey.
    
    Create an engaging summary (150-200 words) that captures:
    - The main character and their quest
    - The central conflict
    - The story's unique elements
    """
    
    # Log prompt size
    log_prompt_size(summary_prompt, "story summary generation")
    
    story_summary = llm.invoke([HumanMessage(content=summary_prompt)]).content
    
    # Store the summary in memory
    # Story summary is included in the final output
    
    # Story completion statistics are calculated for the return value
    total_chapters = len(chapters)
    total_scenes = sum(len(ch["scenes"]) for ch in chapters.values())
    total_words = len(final_story.split())
    # Story completion logging is handled by the progress callback
    # No need for duplicate logging here
    
    # Return the final state with plot thread resolution information
    return {
        "final_story": final_story,
        "story_summary": story_summary,
        "plot_thread_resolution": plot_thread_resolution,
        "messages": [
            *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
            AIMessage(content=f"I've compiled the final story: {story_title}{chr(10)}{chr(10)}Summary:{chr(10)}{story_summary}{chr(10)}{chr(10)}The complete story has been generated successfully." +
                      (f"{chr(10)}{chr(10)}Note: {len(plot_thread_resolution.get('unresolved_major_threads', []))} major plot threads remain unresolved."
                       if not plot_thread_resolution.get("all_major_threads_resolved", True) else ""))
        ]
    }