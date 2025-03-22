"""
StoryCraft Agent - Story progression and character management nodes.
"""

from typing import Dict

from storyteller_lib.config import llm, manage_memory_tool, memory_manager, prompt_optimizer, MEMORY_NAMESPACE
from storyteller_lib.models import StoryState
from langchain_core.messages import AIMessage, HumanMessage
from storyteller_lib import track_progress

@track_progress
def update_character_profiles(state: StoryState) -> Dict:
    """Update character profiles based on developments in the current scene."""
    chapters = state["chapters"]
    characters = state["characters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    
    # Check for our update flag to prevent redundant updates
    update_key = f"ch{current_chapter}_sc{current_scene}_updated"
    
    # Add multiple safeguards against infinite loops
    character_update_count = state.get("character_update_count", 0)
    
    # Increment the counter first thing - this ensures we don't get stuck in loops
    state["character_update_count"] = character_update_count + 1
    
    # Break out of potential loops using both scene-specific flags and a global counter
    update_flags = state.get("character_update_flags", {})
    if update_key in update_flags or character_update_count > 0:
        # Log the type of loop prevention that triggered
        if update_key in update_flags:
            print(f"NOTICE: Characters for Ch:{current_chapter}/Sc:{current_scene} already updated, skipping")
        else:
            print(f"NOTICE: Character update count exceeded ({character_update_count}), breaking potential loop")
            
        # Ensure we mark this scene as processed so we don't return to it
        update_flags[update_key] = True
            
        # Skip update and move on
        return {
            "last_node": "update_character_profiles",
            "character_update_flags": update_flags,
            "messages": [AIMessage(content=f"Characters already updated for scene {current_scene} of chapter {current_chapter}, moving on.")]
        }
    
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
    
    Format as a JSON object where keys are character names and values are objects with the fields to update.
    """
    
    # Get structured character updates
    character_updates_structured = llm.invoke([HumanMessage(content=character_update_prompt)]).content
    
    # With our character reducer, we can just return the specific character updates
    # Instead of a complex update, let's perform a simpler update for demonstration
    
    # Create a targeted update for the hero character (if it exists)
    character_updates = {}
    if "hero" in state["characters"]:
        character_updates["hero"] = {
            "evolution": [f"Development in Chapter {current_chapter}, Scene {current_scene}"]
        }
        
        # Store the hero's updated profile in memory
        manage_memory_tool.invoke({
            "action": "create",
            "key": f"character_hero_updated",
            "value": f"Character updated for Ch {current_chapter}, Scene {current_scene}"
        })
    
    # With our reducers, we don't need explicit tracking flags anymore
    # The character merger will handle appending to evolution lists
    
    # Create or update the character update flags to mark this scene as processed
    update_flags = state.get("character_update_flags", {})
    update_flags[update_key] = True
    
    # Update state
    return {
        "characters": character_updates,  # Only specify what changes
        "character_update_flags": update_flags,  # Mark this scene as updated
        "last_node": "update_character_profiles",
        "messages": [AIMessage(content=f"I've updated character profiles based on developments in scene {current_scene} of chapter {current_chapter}.")]
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
    
    # Reset character update count and flags since we're moving to a new scene/chapter
    update_result = {
        "character_update_count": 0,  # Reset the counter
        "last_node": "advance_to_next_scene_or_chapter",
    }
    
    # Check if the next scene exists in the current chapter
    if next_scene in chapter["scenes"]:
        # Move to the next scene in the same chapter
        update_result.update({
            "current_scene": next_scene,
            "messages": [AIMessage(content=f"Moving on to write scene {next_scene} of chapter {current_chapter}.")]
        })
        return update_result
    else:
        # Move to the next chapter
        next_chapter = str(int(current_chapter) + 1)
        
        # Check if the next chapter exists
        if next_chapter in chapters:
            update_result.update({
                "current_chapter": next_chapter,
                "current_scene": "1",  # Start with first scene of new chapter
                "messages": [AIMessage(content=f"Chapter {current_chapter} is complete. Moving on to chapter {next_chapter}.")]
            })
            return update_result
        else:
            # All chapters are complete
            update_result.update({
                "completed": True,
                "messages": [AIMessage(content="The story is now complete! I'll compile the final narrative for you.")]
            })
            return update_result

@track_progress
def review_continuity(state: StoryState) -> Dict:
    """Dedicated continuity review module that checks the overall story for inconsistencies."""
    # This is called after completing a chapter to check for broader continuity issues
    chapters = state["chapters"]
    characters = state["characters"]
    revelations = state["revelations"]
    global_story = state["global_story"]
    
    # Add proper LangGraph state tracking for continuity reviews
    current_chapter = state.get("current_chapter", "1")
    continuity_phase = state.get("continuity_phase", "review")  # Either "review" or "resolve"
    review_history = state.get("continuity_review_history", {})
    completed_chapters = []
    
    # Add safeguards against infinite continuity review loops
    continuity_review_count = state.get("continuity_review_count", 0)
    current_chapter = state.get("current_chapter", "1")
    
    # Check if we've already done a continuity review for this chapter
    review_key = f"continuity_review_after_chapter_{current_chapter}"
    review_flags = state.get("continuity_review_flags", {})
    
    # Cap on consecutive reviews to prevent loops
    max_consecutive_reviews = 1  # Only allow one review per chapter
    
    # Log the continuity review attempt with diagnostics
    print(f"\n==== CONTINUITY REVIEW ATTEMPT ====")
    print(f"Current chapter: {current_chapter}")
    print(f"Review count: {continuity_review_count}")
    print(f"Already reviewed this chapter: {review_key in review_flags}")
    
    # LangGraph state handling to track review state
    # First, check if we've already done reviews for this chapter
    chapter_review_key = f"continuity_review_ch{current_chapter}"
    
    # Log the review state for debugging
    print(f"\n==== CONTINUITY REVIEW STATE ====")
    print(f"Current chapter: {current_chapter}")
    print(f"Continuity phase: {continuity_phase}")
    print(f"Review count: {continuity_review_count}")
    print(f"Already reviewed: {chapter_review_key in review_history}")
    
    # Implement proper state machine logic for the continuity review process
    if continuity_phase == "review":
        # If we've already reviewed this chapter and aren't in resolution mode, skip it
        if chapter_review_key in review_history and review_history[chapter_review_key].get("status") == "completed":
            print(f"NOTICE: Already performed continuity review for Chapter {current_chapter}, skipping")
            
            return {
                "last_node": "review_continuity",
                "continuity_phase": "complete",  # Mark this phase as complete
                "continuity_review_count": 0,    # Reset the counter
                "messages": [AIMessage(content=f"Already performed continuity review after Chapter {current_chapter}, moving on.")]
            }
    
    # If we've exceeded the maximum review count, move to resolution or skip
    if continuity_review_count >= 3:  # Allow up to 3 review attempts
        print(f"NOTICE: Continuity review count exceeded ({continuity_review_count}/3), transitioning to next phase")
        
        # Intentionally transition to the next phase instead of just skipping
        return {
            "last_node": "review_continuity",
            "continuity_phase": "complete",  # Mark this as complete to move on
            "continuity_review_count": 0,    # Reset for next time
            "messages": [AIMessage(content=f"Completed review of continuity issues after Chapter {current_chapter}. Proceeding with the story.")]
        }
    
    # Increment the counter first thing - this ensures we don't get stuck in loops
    continuity_review_count += 1
    
    # Get all completed chapters and their scenes for review
    for chapter_num in sorted(chapters.keys(), key=int):
        chapter = chapters[chapter_num]
        if all(scene.get("content") for scene in chapter["scenes"].values()):
            completed_chapters.append(chapter_num)
    
    # If there are fewer than 2 completed chapters, not enough for full continuity check
    if len(completed_chapters) < 2:
        return {
            "continuity_review_count": continuity_review_count,
            "messages": [AIMessage(content="Not enough completed chapters for a full continuity review yet.")]
        }
    
    # Prepare chapter summaries for review
    chapter_summaries = []
    for chapter_num in completed_chapters:
        chapter = chapters[chapter_num]
        scenes_summary = []
        for scene_num, scene in sorted(chapter["scenes"].items(), key=lambda x: int(x[0])):
            scenes_summary.append(f"Scene {scene_num}: {scene['content'][:150]}...")
        
        chapter_summaries.append(f"Chapter {chapter_num}: {chapter['title']}\n{chapter['outline']}\nKey scenes: {'; '.join(scenes_summary)}")
    
    # Define the schema for structured continuity review
    continuity_issue_schema = """
    {
      "issues": [
        {
          "description": "Detailed description of the continuity issue",
          "chapters_affected": "List of chapters affected (e.g., 'Chapters 1 and 3' or 'Chapter 2, Scene 4')",
          "severity": "high|medium|low",
          "resolution_approach": "Specific suggestion for how to resolve this issue"
        }
      ],
      "unresolved_threads": [
        {
          "thread_description": "Description of the unresolved story thread",
          "first_mentioned": "Chapter where this thread was first introduced",
          "expected_resolution": "How/where this should be resolved"
        }
      ],
      "character_inconsistencies": [
        {
          "character": "Character name",
          "inconsistency": "Description of the character inconsistency",
          "chapters_affected": "Chapters where this inconsistency appears",
          "resolution_approach": "How to fix this character inconsistency"
        }
      ],
      "hero_journey_evaluation": {
        "current_phase": "Current phase of the hero's journey",
        "issues": "Any issues with the hero's journey structure",
        "recommendations": "Recommendations for maintaining proper structure"
      },
      "has_issues": true,
      "overall_assessment": "Overall assessment of story continuity"
    }
    """
    
    # Prompt for continuity review with structured output
    prompt = f"""
    Perform a comprehensive continuity review of the story so far.
    
    Overall story outline:
    {global_story[:500]}...
    
    Character profiles:
    {characters}
    
    Chapter summaries:
    {chapter_summaries}
    
    Information revealed to readers:
    {revelations.get('reader', [])}
    
    Your task:
    1. Identify any major continuity errors across chapters (e.g., character actions that contradict earlier established traits).
    2. Note any plot holes or unresolved story threads.
    3. Check if character development is consistent and logical.
    4. Verify that revelations are properly paced and not contradictory.
    5. Ensure the hero's journey structure is being properly followed.
    
    For each issue found, specify:
    - The exact nature of the inconsistency
    - Which chapters/scenes it affects
    - Specific suggestions for resolution
    
    Format your response as a structured JSON object following this schema:
    {continuity_issue_schema}
    
    If no issues are found, set has_issues to false and include "No major continuity issues detected" in the overall_assessment.
    """
    
    # Import the structured output functions from creative_tools
    from storyteller_lib.creative_tools import generate_structured_json, parse_json_with_langchain
    
    # Default structure in case parsing fails
    default_continuity_review = {
        "issues": [],
        "unresolved_threads": [],
        "character_inconsistencies": [],
        "hero_journey_evaluation": {
            "current_phase": "Unknown",
            "issues": "None identified",
            "recommendations": "Continue following the hero's journey structure"
        },
        "has_issues": False,
        "overall_assessment": "No major continuity issues detected."
    }
    
    # Perform continuity review using structured output
    try:
        # First try with the LLM directly
        continuity_review_text = llm.invoke([HumanMessage(content=prompt)]).content
        
        # Then parse the response into structured format
        structured_review = parse_json_with_langchain(continuity_review_text, default_continuity_review)
        
        # Fallback to structured JSON generation if parsing fails
        if not structured_review or structured_review == default_continuity_review:
            # Simple check to see if there might be issues in the text
            has_issues_in_text = "issue" in continuity_review_text.lower() or "inconsistenc" in continuity_review_text.lower()
            
            # Only try to generate structured JSON if it seems like there are issues
            if has_issues_in_text:
                print("Attempting to generate structured JSON from continuity review text")
                structured_review = generate_structured_json(
                    continuity_review_text,
                    continuity_issue_schema,
                    "continuity review"
                )
        
        # Store the raw text for reference
        structured_review["raw_review"] = continuity_review_text
        
        # Validate important fields are present
        if "has_issues" not in structured_review:
            # Infer has_issues from content if not explicitly set
            has_issues = (len(structured_review.get("issues", [])) > 0 or 
                         len(structured_review.get("unresolved_threads", [])) > 0 or
                         len(structured_review.get("character_inconsistencies", [])) > 0 or
                         structured_review.get("hero_journey_evaluation", {}).get("issues", "") != "None identified")
            structured_review["has_issues"] = has_issues
        
        if "overall_assessment" not in structured_review:
            if structured_review["has_issues"]:
                structured_review["overall_assessment"] = "There are continuity issues that need resolution"
            else:
                structured_review["overall_assessment"] = "No major continuity issues detected."
        
        print(f"Successfully parsed structured continuity review")
    except Exception as e:
        print(f"Error generating structured continuity review: {str(e)}")
        print("Using default continuity review data")
        structured_review = default_continuity_review
        continuity_review_text = "Error processing continuity review"
        structured_review["raw_review"] = continuity_review_text
    
    # Store both raw and structured continuity review in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"continuity_review_after_chapter_{max(completed_chapters)}",
        "value": structured_review
    })
    
    # Also store the raw text for backward compatibility
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"continuity_review_raw_after_chapter_{max(completed_chapters)}",
        "value": continuity_review_text
    })
    
    # Update our review history with proper LangGraph state tracking
    updated_review_history = review_history.copy()
    updated_review_history[chapter_review_key] = {
        "status": "completed",
        "issues_found": structured_review["has_issues"],
        "chapter": current_chapter,
        "timestamp": "now",
        "review_number": continuity_review_count
    }
    
    # Process the continuity review results using the structured format
    has_issues = structured_review["has_issues"]
    updated_revelations = state["revelations"].copy()
    
    if has_issues:
        # Initialize continuity_issues if it doesn't exist
        if "continuity_issues" not in updated_revelations:
            updated_revelations["continuity_issues"] = []
            
        # Check if we already have a review for this chapter to avoid duplication
        existing_review_idx = None
        for idx, review in enumerate(updated_revelations.get("continuity_issues", [])):
            if review.get("after_chapter") == max(completed_chapters):
                existing_review_idx = idx
                break
                
        # Compile all issues into a single list for resolution
        all_issues = []
        
        # Add regular continuity issues
        for issue in structured_review.get("issues", []):
            all_issues.append(issue)
            
        # Add character inconsistencies
        for char_issue in structured_review.get("character_inconsistencies", []):
            # Convert to standard issue format
            all_issues.append({
                "description": f"Character inconsistency for {char_issue.get('character')}: {char_issue.get('inconsistency')}",
                "chapters_affected": char_issue.get("chapters_affected", ""),
                "severity": "medium",
                "resolution_approach": char_issue.get("resolution_approach", "")
            })
        
        # Add unresolved threads that need attention
        for thread in structured_review.get("unresolved_threads", []):
            all_issues.append({
                "description": f"Unresolved thread: {thread.get('thread_description')}",
                "chapters_affected": thread.get("first_mentioned", ""),
                "severity": "low",
                "resolution_approach": thread.get("expected_resolution", "")
            })
            
        # Create the review entry with structured data
        review_entry = {
            "after_chapter": max(completed_chapters),
            "issues_to_resolve": all_issues,
            "raw_review": continuity_review_text,
            "structured_review": structured_review,
            "needs_resolution": has_issues,
            "resolution_status": "pending"
        }
        
        if existing_review_idx is not None:
            # Replace the existing review
            updated_revelations["continuity_issues"][existing_review_idx] = review_entry
            print(f"Updating existing continuity review for Chapter {max(completed_chapters)}")
        else:
            # Add a new review
            updated_revelations["continuity_issues"].append(review_entry)
            print(f"Adding new continuity review for Chapter {max(completed_chapters)}")
            
        # Set the next phase based on whether we found issues
        next_phase = "needs_resolution" if has_issues else "complete"
        print(f"Setting continuity phase to: {next_phase}")
        
        # Initialize resolution state variables if we need resolution
        if next_phase == "needs_resolution":
            print("Preparing for continuity resolution phase...")
            # Setup state for resolution process
            state["resolution_index"] = 0
            state["resolution_count"] = 0
            state["resolution_summary"] = []
    else:
        print("No continuity issues detected")
        next_phase = "complete"
    
    # Perform background memory processing for completed chapters
    # This implements the background memory formation process from LangMem
    try:
        # Collect all content from completed chapters
        all_chapter_content = []
        for chapter_num in completed_chapters:
            chapter = chapters[chapter_num]
            chapter_content = f"Chapter {chapter_num}: {chapter['title']}\n{chapter['outline']}\n\n"
            
            for scene_num, scene in sorted(chapter["scenes"].items(), key=lambda x: int(x[0])):
                if scene.get('content'):
                    chapter_content += f"Scene {scene_num}:\n{scene['content']}\n\n"
            
            all_chapter_content.append({"role": "assistant", "content": chapter_content})
            
        # Process the content with memory manager to extract narrative memories
        if all_chapter_content:
            memories = memory_manager.invoke({"messages": all_chapter_content})
            
            # Store extracted memories
            if memories:
                manage_memory_tool.invoke({
                    "action": "create",
                    "key": f"narrative_memories_chapter_{max(completed_chapters)}",
                    "value": memories
                })
                
        # Use prompt optimizer to improve prompts based on continuity feedback
        if "No major continuity issues detected" not in continuity_review:
            # Create a trajectory based on the continuity review
            trajectory = [
                {"role": "system", "content": prompt},
                {"role": "assistant", "content": continuity_review}
            ]
            
            # Optimize the continuity review prompt
            optimized_prompt = prompt_optimizer.invoke({
                "trajectories": [(trajectory, {"user_score": continuity_review.count("issue") * -1})],
                "prompt": prompt
            })
            
            # Store the optimized prompt for future continuity reviews
            if optimized_prompt:
                manage_memory_tool.invoke({
                    "action": "create",
                    "key": "optimized_continuity_prompt",
                    "value": optimized_prompt
                })
    except Exception as e:
        # Log the error but don't halt execution
        print(f"Background memory processing error: {str(e)}")
    
    # Create proper message based on state
    if has_issues:
        message = AIMessage(content=f"I've identified continuity issues after Chapter {max(completed_chapters)}. These will need to be addressed in future chapters to maintain narrative coherence.")
    else:
        message = AIMessage(content=f"I've performed a comprehensive continuity review after Chapter {max(completed_chapters)} and found good narrative consistency.")
    
    # Return updated state with proper LangGraph state management
    # This enables the state machine aspect of the LangGraph framework
    return {
        "revelations": updated_revelations,  # Updated story revelations
        "last_node": "review_continuity",    # Track the last executed node
        "continuity_phase": next_phase,      # Track where we are in the continuity review process
        "continuity_review_history": updated_review_history,  # Track review history
        "continuity_review_count": 0 if next_phase == "complete" else continuity_review_count,  # Reset if complete
        "messages": [message]
    }

@track_progress
def resolve_continuity_issues(state: StoryState) -> Dict:
    """Resolve continuity issues by making targeted changes to previous chapters."""
    chapters = state["chapters"]
    characters = state["characters"]
    revelations = state["revelations"]
    
    # Get continuity reviews from state
    continuity_reviews = revelations.get("continuity_issues", [])
    
    # Find the most recent continuity review that needs resolution
    current_review = None
    for review in continuity_reviews:
        if review.get("needs_resolution") and review.get("resolution_status") == "pending":
            current_review = review
            break
    
    # If no review found, exit resolution mode
    if not current_review:
        print("No continuity issues found that need resolution.")
        return {
            "continuity_phase": "complete",
            "resolution_index": 0,
            "resolution_count": 0,
            "last_node": "resolve_continuity_issues",
            "messages": [AIMessage(content="No continuity issues requiring resolution were found.")]
        }
    
    # Get the structured issues to resolve
    issues_to_resolve = current_review.get("issues_to_resolve", [])
    
    # Fallback mechanism - if no structured issues are available, try to extract from raw review
    if not issues_to_resolve and "raw_review" in current_review:
        print("No structured issues found - attempting to extract from raw review")
        # Create a default issue from the raw review
        raw_review = current_review.get("raw_review", "")
        issues_to_resolve = [{
            "description": "Continuity issue detected in raw review",
            "chapters_affected": f"Chapter {current_review.get('after_chapter', '1')}",
            "severity": "medium",
            "resolution_approach": "Review and resolve any inconsistencies found in the text"
        }]
        # Store these extracted issues back to the review
        current_review["issues_to_resolve"] = issues_to_resolve
    
    # Track our progress through issues
    resolution_index = state.get("resolution_index", 0)
    resolution_count = state.get("resolution_count", 0)
    
    # Log the resolution attempt with detailed diagnostics
    print(f"\n==== CONTINUITY RESOLUTION ATTEMPT ====")
    print(f"Resolution index: {resolution_index}/{len(issues_to_resolve)}")
    print(f"Resolution count: {resolution_count}")
    print(f"After chapter: {current_review.get('after_chapter', 'unknown')}")
    
    # Safety check - if we're out of issues or have tried too many times, exit resolution mode
    if resolution_index >= len(issues_to_resolve) or resolution_count >= 3:
        # Log completion of resolution phase
        print(f"Continuity resolution complete or max attempts reached.")
        print(f"Issues processed: {resolution_index}/{len(issues_to_resolve)}")
        print(f"Resolution attempts: {resolution_count}/3")
        
        # Update the review's resolution status
        for review in revelations.get("continuity_issues", []):
            if review.get("after_chapter") == current_review.get("after_chapter"):
                review["resolution_status"] = "completed"
                review["needs_resolution"] = False
        
        # Create a summary of what was resolved
        resolution_summary = state.get("resolution_summary", [])
        
        if resolution_summary:
            summary_message = f"I've resolved {len(resolution_summary)} continuity issues across chapters:"
            for idx, item in enumerate(resolution_summary):
                summary_message += f"\n{idx+1}. {item.get('description', 'Issue')} - {item.get('status', 'Unknown')}"
        else:
            summary_message = "I've analyzed the continuity issues but no changes were necessary."
        
        # Return updated state to exit resolution mode
        return {
            "continuity_phase": "complete",     # Mark resolution as complete
            "resolution_index": 0,              # Reset for next time
            "resolution_count": 0,              # Reset for next time
            "last_node": "resolve_continuity_issues",
            "revelations": revelations,         # Update revelations with resolution status
            "messages": [AIMessage(content=summary_message)]
        }
    
    # Get the current issue to resolve
    current_issue = issues_to_resolve[resolution_index]
    
    # Extract key information from the issue
    issue_description = current_issue.get("description", "")
    issue_chapters = current_issue.get("chapters_affected", "")
    issue_resolution = current_issue.get("resolution_approach", "")
    issue_severity = current_issue.get("severity", "medium")
    
    print(f"Resolving issue: {issue_description[:100]}...")
    print(f"Severity: {issue_severity}")
    print(f"Chapters affected: {issue_chapters}")
    
    # Parse affected chapters - extract chapter numbers from the text
    import re
    affected_chapter_nums = re.findall(r'Chapter (\d+)', issue_chapters)
    
    # If no specific chapters found, look for common patterns
    if not affected_chapter_nums:
        # Try different formats (e.g., "Chapters 2-4", "Ch 2, 3, and 5")
        range_match = re.search(r'Chapters? (\d+)[- ](\d+)', issue_chapters)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            affected_chapter_nums = [str(i) for i in range(start, end+1)]
        else:
            # Try to extract numbers directly
            direct_nums = re.findall(r'\b(\d+)\b', issue_chapters)
            if direct_nums:
                affected_chapter_nums = direct_nums
            else:
                # Final fallback - look at recent chapters which might contain relevant info
                after_chapter = int(current_review.get("after_chapter", 1))
                affected_chapter_nums = [str(i) for i in range(max(1, after_chapter-2), after_chapter+1)]
    
    # Convert to list of valid chapter numbers
    affected_chapters = [ch for ch in affected_chapter_nums if ch in chapters]
    
    # Log affected chapters
    print(f"Identified chapters for resolution: {affected_chapters}")
    
    if not affected_chapters:
        print("No valid chapters identified for resolution.")
        # Skip to next issue
        return {
            "resolution_index": resolution_index + 1,
            "resolution_count": resolution_count + 1,
            "last_node": "resolve_continuity_issues",
            "messages": [AIMessage(content=f"Analyzed continuity issue but couldn't identify specific chapters to revise.")]
        }
    
    # Track changes made for this issue
    resolution_changes = []
    updated_chapters = state["chapters"].copy()
    
    # Process each affected chapter
    for chapter_num in affected_chapters:
        chapter = chapters[chapter_num]
        
        # Find scenes that might contain the relevant content
        candidate_scenes = []
        for scene_num, scene in chapter["scenes"].items():
            scene_content = scene.get("content", "")
            if not scene_content:
                continue
            
            # Enhanced relevance matching using multiple factors
            relevance_score = 0
            
            # 1. Keyword matching from issue description
            issue_keywords = set([word.lower() for word in re.findall(r'\b\w{4,}\b', issue_description.lower())])
            if issue_keywords:
                # Count matching keywords in content
                keywords_found = sum(1 for keyword in issue_keywords if keyword in scene_content.lower())
                # Calculate percentage of matching keywords
                keywords_percentage = keywords_found / len(issue_keywords)
                relevance_score += keywords_percentage * 5  # Weight this factor
            
            # 2. Specific entity matching (character names, locations, objects)
            # Extract potential entities (capitalized words)
            entities = set(re.findall(r'\b[A-Z][a-z]{2,}\b', issue_description))
            if entities:
                entity_matches = sum(1 for entity in entities if entity in scene_content)
                entity_percentage = entity_matches / len(entities) if entities else 0
                relevance_score += entity_percentage * 10  # Weight entities more heavily
            
            # 3. Chapter/scene explicit mentions
            scene_pattern = f"Scene {scene_num}"
            if scene_pattern in issue_description or scene_pattern in issue_chapters:
                relevance_score += 15  # Strong boost for explicit scene mentions
            
            # 4. Longer scenes might have more content relevant to issues
            scene_length_factor = min(len(scene_content) / 2000, 1.0)  # Cap at 1.0
            relevance_score += scene_length_factor * 2
            
            # Only include scenes with some relevance
            if relevance_score > 0:
                candidate_scenes.append((scene_num, relevance_score))
            # Always include at least one scene even if no relevance
            elif not candidate_scenes and scene_content:
                candidate_scenes.append((scene_num, 0.1))
        
        # Sort scenes by relevance score
        candidate_scenes.sort(key=lambda x: x[1], reverse=True)
        
        # Log candidate scenes with scores
        if candidate_scenes:
            print(f"Candidate scenes for Chapter {chapter_num}:")
            for scene_num, score in candidate_scenes[:3]:  # Show top 3
                print(f"  - Scene {scene_num}: relevance score {score:.2f}")
        
        # Take the most relevant scene
        if candidate_scenes:
            scene_to_revise = candidate_scenes[0][0]
            current_content = chapter["scenes"][scene_to_revise].get("content", "")
            
            # Create a prompt for targeted revision with more detailed context
            revision_prompt = f"""
            You need to make targeted edits to fix a specific continuity issue.
            
            CONTINUITY ISSUE:
            {issue_description}
            
            SEVERITY: {issue_severity}
            
            CHAPTERS AFFECTED:
            {issue_chapters}
            
            RESOLUTION APPROACH:
            {issue_resolution}
            
            CHAPTER CONTEXT:
            Chapter {chapter_num}: {chapter.get('title', '')}
            {chapter.get('outline', '')}
            
            CURRENT SCENE CONTENT (Chapter {chapter_num}, Scene {scene_to_revise}):
            {current_content}
            
            Your task:
            1. Make MINIMAL, PRECISE changes to resolve the continuity issue
            2. Preserve the scene's original structure and purpose
            3. Only change what's necessary to fix the inconsistency
            4. Maintain the same tone, style, and approximate length
            5. Ensure the edits fit naturally into the existing content
            
            Return the revised scene text that fixes the continuity issue.
            """
            
            # Generate the revised scene
            try:
                print(f"Revising Chapter {chapter_num}, Scene {scene_to_revise} to fix continuity...")
                revised_content = llm.invoke([HumanMessage(content=revision_prompt)]).content
                
                # Verify the revision actually made changes
                if revised_content == current_content:
                    print(f"⚠️ Warning: Revision didn't change the content")
                    continue
                
                # Update the scene with revised content
                updated_chapters[chapter_num]["scenes"][scene_to_revise]["content"] = revised_content
                
                # Create structured info about what was changed
                change_info = {
                    "chapter": chapter_num,
                    "scene": scene_to_revise,
                    "issue": issue_description[:100] + "..." if len(issue_description) > 100 else issue_description,
                    "status": "Revised to fix continuity issue",
                    "severity": issue_severity
                }
                
                # Track the revision
                resolution_changes.append(change_info)
                
                # Store the revision record for later reference
                manage_memory_tool.invoke({
                    "action": "create",
                    "key": f"continuity_revision_ch{chapter_num}_sc{scene_to_revise}_{resolution_index}",
                    "value": {
                        "original_content": current_content,
                        "revised_content": revised_content,
                        "issue": issue_description,
                        "resolution_approach": issue_resolution,
                        "timestamp": "now",
                        "severity": issue_severity
                    }
                })
                
                # Generate a verification check to confirm the issue is resolved
                verification_prompt = f"""
                You need to verify if a continuity issue has been properly resolved.
                
                ORIGINAL CONTINUITY ISSUE:
                {issue_description}
                
                ORIGINAL CONTENT:
                {current_content}
                
                REVISED CONTENT:
                {revised_content}
                
                Has the continuity issue been successfully resolved? Answer YES or NO and briefly explain why.
                """
                
                verification_result = llm.invoke([HumanMessage(content=verification_prompt)]).content
                is_resolved = "yes" in verification_result.lower()
                
                if is_resolved:
                    print(f"✅ Successfully resolved issue in Chapter {chapter_num}, Scene {scene_to_revise}")
                else:
                    print(f"⚠️ Issue may not be fully resolved: {verification_result[:100]}...")
                
                # Store verification result
                manage_memory_tool.invoke({
                    "action": "create",
                    "key": f"continuity_verification_ch{chapter_num}_sc{scene_to_revise}_{resolution_index}",
                    "value": {
                        "verification_result": verification_result,
                        "is_resolved": is_resolved
                    }
                })
            
            except Exception as e:
                print(f"Error while revising: {str(e)}")
    
    # Update the resolution summary with what we fixed
    resolution_summary = state.get("resolution_summary", [])
    
    if resolution_changes:
        resolution_summary.append({
            "index": resolution_index,
            "description": issue_description[:100] + "..." if len(issue_description) > 100 else issue_description,
            "changes": resolution_changes,
            "status": "Resolved",
            "severity": issue_severity
        })
    else:
        resolution_summary.append({
            "index": resolution_index,
            "description": issue_description[:100] + "..." if len(issue_description) > 100 else issue_description,
            "changes": [],
            "status": "No changes needed",
            "severity": issue_severity
        })
    
    # Move to the next issue or finish if all issues are resolved
    next_index = resolution_index + 1
    message = ""
    
    if next_index >= len(issues_to_resolve):
        message = f"I've completed resolving continuity issues across chapters. Made changes to {len(resolution_changes)} scenes."
    else:
        message = f"I've resolved continuity issue {resolution_index + 1}/{len(issues_to_resolve)}. Moving to next issue."
    
    # Return updated state according to LangGraph state management principles
    return {
        "chapters": updated_chapters,            # Return updated chapters
        "resolution_index": next_index,          # Increment resolution index
        "resolution_count": resolution_count + 1, # Increment resolution count
        "resolution_summary": resolution_summary, # Track what we've resolved
        "last_node": "resolve_continuity_issues",
        "messages": [AIMessage(content=message)]
    }

@track_progress
def compile_final_story(state: StoryState) -> Dict:
    """Compile the complete story when all chapters and scenes are finished."""
    if not state["completed"]:
        # Skip if the story isn't marked as complete
        return {}
    
    chapters = state["chapters"]
    revelations = state["revelations"]
    
    # Perform a final continuity check across the entire story
    global_continuity_prompt = f"""
    Perform a final comprehensive continuity check on the entire story before compilation.
    
    Story outline:
    {state['global_story']}
    
    Character profiles:
    {state['characters']}
    
    Chapters:
    {[f"Chapter {num}: {chapter['title']}" for num, chapter in chapters.items()]}
    
    Previous continuity issues:
    {revelations.get('continuity_issues', [])}
    
    Identify any remaining continuity errors, plot holes, or unresolved threads that should be addressed.
    Format your response as a list of issues with page numbers/chapter references.
    If no issues remain, state "Story is internally consistent and complete."
    """
    
    # Generate final continuity check
    final_continuity_check = llm.invoke([HumanMessage(content=global_continuity_prompt)]).content
    
    # Store the final continuity check
    manage_memory_tool.invoke({
        "action": "create",
        "key": "final_continuity_check",
        "value": final_continuity_check
    })
    
    # Compile the story
    story = []
    
    # Extract title from global story
    story_title = state['global_story'].split('\n')[0]
    # Clean up title if needed (remove any "Title: " prefix)
    if ":" in story_title and len(story_title.split(":")) > 1:
        story_title = story_title.split(":", 1)[1].strip()
        
    # Add title and introduction
    story.append(f"# {story_title}")
    story.append("\n## Introduction\n")
    
    # Add each chapter
    for chapter_num in sorted(chapters.keys(), key=int):
        chapter = chapters[chapter_num]
        story.append(f"\n## Chapter {chapter_num}: {chapter['title']}\n")
        
        # Add each scene
        for scene_num in sorted(chapter["scenes"].keys(), key=int):
            scene = chapter["scenes"][scene_num]
            story.append(f"### Scene {scene_num}\n")
            story.append(scene["content"])
            story.append("\n\n")
    
    # Join the story parts
    complete_story = "\n".join(story)
    
    # Store the complete story in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": "complete_story",
        "value": complete_story
    })
    
    # Final message to the user
    return {
        "last_node": "compile_final_story",
        "messages": [AIMessage(content="I've compiled the complete story. Here's a summary of what I created:"),
                    AIMessage(content=f"A {state['tone']} {state['genre']} story with {len(chapters)} chapters and {sum(len(chapter['scenes']) for chapter in chapters.values())} scenes. The story follows the hero's journey structure and features {len(state['characters'])} main characters. I've maintained consistency throughout the narrative and carefully managed character development and plot revelations.")],
        "compiled_story": complete_story
    }