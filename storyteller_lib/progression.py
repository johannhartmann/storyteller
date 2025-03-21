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
    
    # For simplicity, we'll make some basic updates to the hero character
    # In a real implementation, you'd parse the JSON from character_updates_structured
    
    if "hero" in updated_characters:
        hero = updated_characters["hero"].copy()
        hero["evolution"] = hero["evolution"] + [f"Development in Chapter {current_chapter}, Scene {current_scene}"]
        updated_characters["hero"] = hero
    
    # Store updated character profiles in memory
    for char_name, profile in updated_characters.items():
        manage_memory_tool.invoke({
            "action": "create",
            "key": f"character_{char_name}_updated",
            "value": profile
        })
    
    # Update state
    return {
        "characters": updated_characters,
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
    
    # Check if the next scene exists in the current chapter
    if next_scene in chapter["scenes"]:
        # Move to the next scene in the same chapter
        return {
            "current_scene": next_scene,
            "last_node": "advance_to_next_scene_or_chapter",
            "messages": [AIMessage(content=f"Moving on to write scene {next_scene} of chapter {current_chapter}.")]
        }
    else:
        # Move to the next chapter
        next_chapter = str(int(current_chapter) + 1)
        
        # Check if the next chapter exists
        if next_chapter in chapters:
            return {
                "current_chapter": next_chapter,
                "current_scene": "1",  # Start with first scene of new chapter
                "last_node": "advance_to_next_scene_or_chapter",
                "messages": [AIMessage(content=f"Chapter {current_chapter} is complete. Moving on to chapter {next_chapter}.")]
            }
        else:
            # All chapters are complete
            return {
                "completed": True,
                "last_node": "advance_to_next_scene_or_chapter",
                "messages": [AIMessage(content="The story is now complete! I'll compile the final narrative for you.")]
            }

@track_progress
def review_continuity(state: StoryState) -> Dict:
    """Dedicated continuity review module that checks the overall story for inconsistencies."""
    # This is called after completing a chapter to check for broader continuity issues
    chapters = state["chapters"]
    characters = state["characters"]
    revelations = state["revelations"]
    global_story = state["global_story"]
    completed_chapters = []
    
    # Get all completed chapters and their scenes for review
    for chapter_num in sorted(chapters.keys(), key=int):
        chapter = chapters[chapter_num]
        if all(scene.get("content") for scene in chapter["scenes"].values()):
            completed_chapters.append(chapter_num)
    
    # If there are fewer than 2 completed chapters, not enough for full continuity check
    if len(completed_chapters) < 2:
        return {
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
    
    # Prompt for continuity review
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
    
    If no issues are found, state "No major continuity issues detected."
    """
    
    # Perform continuity review
    continuity_review = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Store the continuity review in memory as procedural memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"continuity_review_after_chapter_{max(completed_chapters)}",
        "value": continuity_review
    })
    
    # If there are continuity issues, add them to a dedicated continuity_issues field
    updated_revelations = state["revelations"].copy()
    if "No major continuity issues detected" not in continuity_review:
        if "continuity_issues" not in updated_revelations:
            updated_revelations["continuity_issues"] = []
        updated_revelations["continuity_issues"].append({
            "after_chapter": max(completed_chapters),
            "issues": continuity_review
        })
    
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
    
    return {
        "revelations": updated_revelations,
        "last_node": "review_continuity",
        "messages": [AIMessage(content=f"I've performed a comprehensive continuity review after completing chapter {max(completed_chapters)}.")]
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