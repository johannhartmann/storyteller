"""
StoryCraft Agent - Story progression and character management nodes.

This is a refactored version optimized for LangGraph's native edge system,
removing router-specific code that could cause infinite loops.
"""

from typing import Dict
import json

from storyteller_lib.config import llm, manage_memory_tool, search_memory_tool, memory_manager, prompt_optimizer, MEMORY_NAMESPACE, cleanup_old_state, log_memory_usage
from storyteller_lib.models import StoryState
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from storyteller_lib import track_progress
from storyteller_lib.constants import NodeNames
from storyteller_lib.story_context import get_context_provider

@track_progress
def update_world_elements(state: StoryState) -> Dict:
    """Update world elements based on developments in the current scene."""
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
    
    # Prompt for world element updates
    prompt = f"""
    Based on this scene from Chapter {current_chapter}, Scene {current_scene}:
    
    {scene_content}
    
    Identify any developments or new information about the world.
    Consider:
    1. New geographical locations or details about existing locations
    2. Historical information revealed
    3. Cultural elements introduced or expanded upon
    4. Political developments or revelations
    5. Economic systems or changes
    6. Technology or magic details revealed
    7. Religious or belief system information
    8. Daily life elements shown
    
    For each category of world elements, specify what should be added or modified.
    """
    
    # Generate world updates
    world_updates_text = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Get the existing world elements for reference
    world_update_prompt = f"""
    Based on these potential world updates:
    
    {world_updates_text}
    
    And these existing world elements:
    
    {world_elements}
    
    For each category of world elements that needs updates, provide:
    1. Category name (geography, history, culture, politics, economics, technology_magic, religion, daily_life)
    2. Specific elements within that category to add or update
    
    Format as a JSON object where keys are category names and values are objects with the elements to update.
    Only include categories and elements that have meaningful updates from this scene.
    """
    
    # Get structured world updates
    world_updates_structured = llm.invoke([HumanMessage(content=world_update_prompt)]).content
    
    # Process updates for world elements
    world_updates = {}
    
    # Try to parse the structured updates from the LLM
    try:
        from storyteller_lib.creative_tools import parse_json_with_langchain
        structured_updates = parse_json_with_langchain(world_updates_structured, "world updates")
        
        if structured_updates and isinstance(structured_updates, dict):
            # Apply the structured updates
            world_updates = structured_updates
    except Exception as e:
        print(f"Error parsing world updates: {str(e)}")
    
    # Store the world updates in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"world_updates_ch{current_chapter}_sc{current_scene}",
        "value": world_updates,
        "namespace": MEMORY_NAMESPACE
    })
    
    # Update the world state tracker in memory
    try:
        # Use search_memory_tool to retrieve the world state tracker
        results = search_memory_tool.invoke({
            "query": "world_state_tracker"
        })
        
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
            manage_memory_tool.invoke({
                "action": "create",
                "key": "world_state_tracker",
                "value": updated_tracker,
                "namespace": MEMORY_NAMESPACE
            })
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
    chapters = state["chapters"]
    characters = state["characters"]
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
    
    # Import optimization utilities
    from storyteller_lib.logger import get_logger
    from storyteller_lib.prompt_optimization import (
        truncate_scene_content, summarize_character, log_prompt_size,
        get_relevant_characters
    )
    logger = get_logger(__name__)
    
    # Truncate scene content smartly
    truncated_scene = truncate_scene_content(scene_content, keep_start=300, keep_end=200)
    
    # Get only relevant characters mentioned in the scene
    relevant_characters = get_relevant_characters(characters, scene_content, max_characters=5)
    scene_characters = [(char_id, char_data.get('name', '')) 
                       for char_id, char_data in relevant_characters.items()]
    
    logger.info(f"Characters found in scene: {[name for _, name in scene_characters]}")
    
    # Prompt for character updates
    prompt = f"""
    Based on this scene from Chapter {current_chapter}, Scene {current_scene}:
    
    {truncated_scene}
    
    Characters in this scene: {', '.join([name for _, name in scene_characters])}
    
    Identify any developments or new information for each character.
    Consider:
    1. New revealed facts about characters
    2. Changes in relationships between characters
    3. Character growth or evolution
    4. New secrets that have been created but not yet revealed
    5. Emotional changes or reactions
    6. Progress in their character arc
    
    For each relevant character, provide a BRIEF summary of what should be updated.
    Keep your response under 300 words total.
    """
    
    # Log prompt size
    log_prompt_size(prompt, "character update analysis")
    
    # Generate character updates
    character_updates_text = llm.invoke([HumanMessage(content=prompt)]).content
    
    # For each character, check if there are updates and apply them
    updated_characters = state["characters"].copy()
    
    # Create optimized character summaries using utility function
    character_summaries = {}
    for char_id, char_name in scene_characters[:3]:  # Limit to 3 characters max
        char_data = relevant_characters.get(char_id, {})
        char_summary = summarize_character(char_data, max_words=50)
        character_summaries[char_name] = char_summary
    
    # More focused update prompt
    character_update_prompt = f"""
    Based on these character developments from the scene:
    
    {character_updates_text[:400]}  # Further limit the updates text
    
    Current character status (summary):
    {json.dumps(character_summaries, indent=2)}
    
    For each character that needs updates, provide a JSON object with:
    - character_name: The character's name
    - new_facts: List of new facts learned (max 2)
    - emotional_change: Any emotional state change (one line)
    - relationship_changes: Dictionary of relationship changes (max 2)
    
    Keep the response under 200 words total.
    """
    
    # Log prompt size
    log_prompt_size(character_update_prompt, "character updates structured")
    
    # Get structured character updates
    character_updates_structured = llm.invoke([HumanMessage(content=character_update_prompt)]).content
    
    # Import the character arc tracking module
    from storyteller_lib.character_arcs import update_character_arc, evaluate_arc_consistency
    
    # Process updates for each character
    character_updates = {}
    
    # First, try to parse the structured updates from the LLM
    try:
        from storyteller_lib.creative_tools import parse_json_with_langchain
        structured_updates = parse_json_with_langchain(character_updates_structured, "character updates")
        
        if structured_updates and isinstance(structured_updates, dict):
            # Process the simpler update structure
            for char_name, updates in structured_updates.items():
                # Skip if updates is None
                if updates is None:
                    continue
                
                # Find the character in our character dictionary
                char_id = None
                for cid, cdata in characters.items():
                    if cdata.get('name', '') == char_name:
                        char_id = cid
                        break
                
                if char_id and char_id in updated_characters:
                    # Apply the updates to the character
                    char_data = updated_characters[char_id]
                    
                    # Add new facts
                    if 'new_facts' in updates and updates['new_facts']:
                        if 'known_facts' not in char_data:
                            char_data['known_facts'] = []
                        char_data['known_facts'].extend(updates['new_facts'][:2])  # Max 2 facts
                    
                    # Update emotional state
                    if 'emotional_change' in updates and updates['emotional_change']:
                        if 'emotional_state' not in char_data:
                            char_data['emotional_state'] = {}
                        char_data['emotional_state']['current'] = updates['emotional_change']
                    
                    # Update relationships
                    if 'relationship_changes' in updates and updates['relationship_changes']:
                        if 'relationships' not in char_data:
                            char_data['relationships'] = {}
                        for other_char, rel_change in updates['relationship_changes'].items():
                            if other_char in char_data['relationships']:
                                # Update existing relationship
                                if isinstance(char_data['relationships'][other_char], dict):
                                    char_data['relationships'][other_char]['dynamics'] = rel_change
                            else:
                                # Create new relationship
                                char_data['relationships'][other_char] = {
                                    'type': 'evolved',
                                    'dynamics': rel_change
                                }
                    
                    character_updates[char_id] = char_data
    except Exception as e:
        logger.error(f"Error parsing character updates: {str(e)}")
    
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
            
            # Store the character's updated profile in memory
            manage_memory_tool.invoke({
                "action": "create",
                "key": f"character_{char_name}_updated_ch{current_chapter}_sc{current_scene}",
                "value": f"Character updated for Ch {current_chapter}, Scene {current_scene}"
            })
    
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
    manage_memory_tool.invoke({
        "action": "create",
        "key": review_key,
        "value": review_result,
        "namespace": MEMORY_NAMESPACE
    })
    
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
        
        # Mark the chapter as complete in memory
        manage_memory_tool.invoke({
            "action": "create",
            "key": f"chapter_{current_chapter}_complete",
            "value": True,
            "namespace": MEMORY_NAMESPACE
        })
        
        # Log that the chapter is complete
        print(f"{chr(10)}==== CHAPTER {current_chapter} COMPLETED ====")
        print(f"Continuity review completed for Chapter {current_chapter} with no critical issues.")
        print(f"The chapter is now ready to be written to the output file.")
        print(f"================================={chr(10)}")
        
        # Log chapter completion
        from storyteller_lib.story_progress_logger import log_progress
        log_progress("chapter_complete", chapter_num=current_chapter)
        
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
            # Use search_memory_tool to retrieve the review
            results = search_memory_tool.invoke({
                "query": review_key
            })
            
            # Extract the review from the results
            review_obj = None
            if results and len(results) > 0:
                for item in results:
                    if hasattr(item, 'key') and item.key == review_key:
                        review_obj = {"key": item.key, "value": item.value}
                        break
            
            if review_obj and "value" in review_obj:
                full_review = review_obj["value"]
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
    
    # Store the resolution plan in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"resolution_plan_{review_key}_{resolution_index}",
        "value": resolution_plan,
        "namespace": MEMORY_NAMESPACE
    })
    
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
    
    # Check if the next scene exists in the current chapter
    if next_scene in chapter["scenes"]:
        # Get cleanup updates for scene transition
        cleanup_updates = cleanup_old_state(state, current_chapter, current_scene)
        
        # Move to the next scene in the same chapter
        return {
            "current_scene": next_scene,
            "current_scene_content": None,  # Clear previous scene content
            "continuity_phase": "complete",  # Reset continuity phase
            # Include cleanup updates
            **cleanup_updates,
            # Add memory tracking
            "memory_usage": {
                f"scene_transition_{current_chapter}_{current_scene}_to_{next_scene}": log_memory_usage(f"Scene transition {current_scene} to {next_scene}")
            },
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content=f"Moving on to write scene {next_scene} of chapter {current_chapter}.")
            ]
        }
    else:
        # Move to the next chapter
        next_chapter = str(int(current_chapter) + 1)
        
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
    global_story = state["global_story"]
    genre = state["genre"]
    tone = state["tone"]
    author = state["author"]
    initial_idea = state.get("initial_idea", "")
    world_elements = state.get("world_elements", {})
    
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
    
    # Try to extract a title from the global story
    title_lines = [line for line in global_story.split(chr(10)) if "title" in line.lower()]
    if title_lines:
        # Extract the title from the first line that mentions "title"
        title_line = title_lines[0]
        title_parts = title_line.split(":")
        if len(title_parts) > 1:
            story_title = title_parts[1].strip()
    
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
            
            # Add scene content
            story_content.append(scene["content"])
            story_content.append("")
    
    # Join all content
    final_story = chr(10).join(story_content)
    
    # Store the final story in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": "final_story",
        "value": final_story,
        "namespace": MEMORY_NAMESPACE
    })
    
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
    manage_memory_tool.invoke({
        "action": "create",
        "key": "story_summary",
        "value": story_summary,
        "namespace": MEMORY_NAMESPACE
    })
    
    # Log story completion
    from storyteller_lib.story_progress_logger import log_progress
    total_chapters = len(chapters)
    total_scenes = sum(len(ch["scenes"]) for ch in chapters.values())
    total_words = len(final_story.split())
    log_progress("story_complete", total_chapters=total_chapters, 
                total_scenes=total_scenes, total_words=total_words)
    
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