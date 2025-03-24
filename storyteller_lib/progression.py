"""
StoryCraft Agent - Story progression and character management nodes.

This is a refactored version optimized for LangGraph's native edge system,
removing router-specific code that could cause infinite loops.
"""

from typing import Dict

from storyteller_lib.config import llm, manage_memory_tool, search_memory_tool, memory_manager, prompt_optimizer, MEMORY_NAMESPACE, cleanup_old_state, log_memory_usage
from storyteller_lib.models import StoryState
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from storyteller_lib import track_progress

@track_progress
def update_world_elements(state: StoryState) -> Dict:
    """Update world elements based on developments in the current scene."""
    chapters = state["chapters"]
    world_elements = state.get("world_elements", {})
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    
    # Get the scene content
    scene_content = chapters[current_chapter]["scenes"][current_scene]["content"]
    
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
    
    # Get the scene content
    scene_content = chapters[current_chapter]["scenes"][current_scene]["content"]
    
    # Prompt for character updates
    prompt = f"""
    Based on this scene from Chapter {current_chapter}, Scene {current_scene}:
    
    {scene_content}
    
    Identify any developments or new information for each character.
    Consider:
    1. New revealed facts about characters
    2. Changes in relationships between characters
    3. Character growth or evolution
    4. New secrets that have been created but not yet revealed
    5. Emotional changes or reactions
    6. Progress in their character arc
    7. Development of inner conflicts
    8. Changes in desires, fears, or values
    
    For each relevant character, specify what should be added to their profile.
    """
    
    # Generate character updates
    character_updates_text = llm.invoke([HumanMessage(content=prompt)]).content
    
    # For each character, check if there are updates and apply them
    updated_characters = state["characters"].copy()
    
    # This simplified implementation assumes the LLM will provide somewhat structured output
    # In a real application, you'd want to parse this more robustly
    character_update_prompt = f"""
    Based on these potential character updates:
    
    {character_updates_text}
    
    And these existing character profiles:
    
    {characters}
    
    For each character that needs updates, provide:
    1. Character name
    2. Any new evolution points to add
    3. Any new known facts to add
    4. Any new revealed facts to add
    5. Any secret facts to add
    6. Any relationship changes
    7. Any emotional state changes
    8. Any progress in inner conflicts
    9. Any advancement in character arc stages
    
    Format as a JSON object where keys are character names and values are objects with the fields to update.
    """
    
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
            # Apply the structured updates
            for char_name, updates in structured_updates.items():
                if char_name in characters:
                    character_updates[char_name] = updates
    except Exception as e:
        print(f"Error parsing character updates: {str(e)}")
    
    # Then, use the character arc tracking module for each character that appears in the scene
    for char_name, char_data in characters.items():
        # Check if character appears in the scene
        if char_name.lower() in scene_content.lower() or (char_data.get("name", "").lower() in scene_content.lower()):
            # Update character arc
            arc_updates = update_character_arc(char_data, scene_content, current_chapter, current_scene)
            
            if arc_updates:
                # If we already have updates for this character, merge them
                if char_name in character_updates:
                    for key, value in arc_updates.items():
                        if key not in character_updates[char_name]:
                            character_updates[char_name][key] = value
                else:
                    character_updates[char_name] = arc_updates
            
            # Store the character's updated profile in memory
            manage_memory_tool.invoke({
                "action": "create",
                "key": f"character_{char_name}_updated_ch{current_chapter}_sc{current_scene}",
                "value": f"Character updated for Ch {current_chapter}, Scene {current_scene}"
            })
    
    # Update state - only return what changed
    return {
        "characters": character_updates,  # Only specify what changes
        "messages": [
            *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
            AIMessage(content=f"I've updated character profiles with emotional developments and arc progression from scene {current_scene} of chapter {current_chapter}.")
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
    
    # Prepare chapter summaries for review
    chapter_summaries = []
    for chapter_num in completed_chapters:
        chapter = chapters[chapter_num]
        scenes_summary = []
        for scene_num, scene in sorted(chapter["scenes"].items(), key=lambda x: int(x[0])):
            scenes_summary.append(f"Scene {scene_num}: {scene['content'][:150]}...")
        
        chapter_summaries.append(f"Chapter {chapter_num}: {chapter['title']}\n{chapter['outline']}\nKey scenes: {'; '.join(scenes_summary)}")
    
    # Prepare world elements section
    world_elements_section = ""
    if world_elements:
        world_elements_section = f"""
        WORLD ELEMENTS:
        {world_elements}
        
        Check for any inconsistencies in how the world elements are portrayed across chapters.
        """
    
    # Prompt for continuity review
    prompt = f"""
    Perform a comprehensive continuity review of the story so far:
    
    STORY OUTLINE:
    {global_story[:1000]}...
    
    COMPLETED CHAPTERS:
    {'\n\n'.join(chapter_summaries)}
    
    CHARACTER PROFILES:
    {characters}
    
    {world_elements_section}
    
    Analyze the story for:
    1. Continuity issues (contradictions, timeline problems, etc.)
    2. Unresolved plot threads or elements
    3. Character inconsistencies (behavior, motivation, etc.)
    4. Hero's journey structure evaluation
    5. World building inconsistencies
    
    For each issue, provide:
    - Description of the issue
    - Affected chapters and characters
    - Severity (1-10)
    - Suggestion for resolution
    
    Determine if any issues need immediate resolution before continuing the story.
    """
    
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
        for line in review_result.split("\n"):
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
        return {
            "continuity_phase": "complete",
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
                AIMessage(content=f"I've resolved the continuity issue: {current_issue}\n\nResolution Plan:\n{resolution_plan}\n\nAll continuity issues have been resolved.")
            ]
        }
    else:
        # More issues to resolve
        return {
            "resolution_index": next_resolution_index,
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content=f"I've resolved the continuity issue: {current_issue}\n\nResolution Plan:\n{resolution_plan}\n\nMoving on to the next issue.")
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
        # Move to the next scene in the same chapter
        return {
            "current_scene": next_scene,
            "continuity_phase": "complete",  # Reset continuity phase
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
        unresolved_threads_warning = "\n\n## WARNING: Unresolved Plot Threads\n\n"
        unresolved_threads_warning += "The following major plot threads were not resolved in the story:\n\n"
        
        for thread in unresolved_threads:
            unresolved_threads_warning += f"- **{thread['name']}**: {thread['description']}\n"
            unresolved_threads_warning += f"  - First appeared: {thread['first_appearance']}\n"
            unresolved_threads_warning += f"  - Last mentioned: {thread['last_appearance']}\n\n"
    
    # Compile the story content
    story_content = []
    
    # Add a title and introduction
    story_title = "Untitled Story"  # Default title
    
    # Try to extract a title from the global story
    title_lines = [line for line in global_story.split("\n") if "title" in line.lower()]
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
    final_story = "\n".join(story_content)
    
    # Store the final story in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": "final_story",
        "value": final_story,
        "namespace": MEMORY_NAMESPACE
    })
    
    # Create a summary of the story
    summary_prompt = f"""
    Create a brief summary of this story:
    
    Title: {story_title}
    Genre: {genre}
    Tone: {tone}
    
    {global_story[:1000]}...
    
    The summary should capture the essence of the story, its main characters, and key plot points.
    Keep it concise but engaging, around 200-300 words.
    """
    
    story_summary = llm.invoke([HumanMessage(content=summary_prompt)]).content
    
    # Store the summary in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": "story_summary",
        "value": story_summary,
        "namespace": MEMORY_NAMESPACE
    })
    
    # Return the final state with plot thread resolution information
    return {
        "final_story": final_story,
        "story_summary": story_summary,
        "plot_thread_resolution": plot_thread_resolution,
        "messages": [
            *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
            AIMessage(content=f"I've compiled the final story: {story_title}\n\nSummary:\n{story_summary}\n\nThe complete story has been generated successfully." +
                      (f"\n\nNote: {len(plot_thread_resolution.get('unresolved_major_threads', []))} major plot threads remain unresolved."
                       if not plot_thread_resolution.get("all_major_threads_resolved", True) else ""))
        ]
    }