"""
StoryCraft Agent - Scene generation and management nodes.
"""

from typing import Dict

from storyteller_lib.config import llm, manage_memory_tool, MEMORY_NAMESPACE
from storyteller_lib.models import StoryState
from langchain_core.messages import AIMessage, HumanMessage
from storyteller_lib.creative_tools import creative_brainstorm
from storyteller_lib import track_progress

@track_progress
def brainstorm_scene_elements(state: StoryState) -> Dict:
    """Brainstorm creative elements for the current scene."""
    chapters = state["chapters"]
    characters = state["characters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    genre = state["genre"]
    tone = state["tone"]
    author = state["author"]
    author_style_guidance = state["author_style_guidance"]
    global_story = state["global_story"]
    revelations = state["revelations"]
    creative_elements = state.get("creative_elements", {})
    
    # Get the current chapter data
    chapter = chapters[current_chapter]
    
    # Generate context for this specific scene
    context = f"""
    Chapter {current_chapter}: {chapter['title']}
    Chapter outline: {chapter['outline']}
    
    We are writing Scene {current_scene} of this chapter.
    
    Character information:
    {characters}
    
    Previously revealed information:
    {revelations.get('reader', [])}
    """
    
    # Brainstorm scene-specific elements
    scene_elements_results = creative_brainstorm(
        topic=f"Scene {current_scene} Creative Elements",
        genre=genre,
        tone=tone,
        context=context,
        author=author,
        author_style_guidance=author_style_guidance,
        num_ideas=4,
        evaluation_criteria=[
            "Visual impact and memorability",
            "Character development opportunity",
            "Advancement of plot in unexpected ways",
            "Emotional resonance",
            "Consistency with established world rules"
        ]
    )
    
    # Brainstorm potential surprises or twists for this scene
    scene_surprises_results = creative_brainstorm(
        topic=f"Unexpected Elements for Scene {current_scene}",
        genre=genre,
        tone=tone,
        context=context,
        author=author,
        author_style_guidance=author_style_guidance,
        num_ideas=3,
        evaluation_criteria=[
            "Surprise factor",
            "Logical consistency with established facts",
            "Impact on future plot development", 
            "Character reaction potential",
            "Reader engagement"
        ]
    )
    
    # Update creative elements with scene-specific brainstorming
    current_creative_elements = creative_elements.copy() if creative_elements else {}
    current_creative_elements[f"scene_elements_ch{current_chapter}_sc{current_scene}"] = scene_elements_results
    current_creative_elements[f"scene_surprises_ch{current_chapter}_sc{current_scene}"] = scene_surprises_results
    
    # Store these brainstormed elements in memory for future reference
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"brainstorm_scene_{current_chapter}_{current_scene}",
        "value": {
            "elements": scene_elements_results,
            "surprises": scene_surprises_results
        },
        "namespace": MEMORY_NAMESPACE
    })
    
    return {
        "creative_elements": current_creative_elements,
        "last_node": "brainstorm_scene_elements",
        "messages": [AIMessage(content=f"I've brainstormed creative elements and unexpected twists for scene {current_scene} of chapter {current_chapter}. Now I'll write the scene incorporating the most promising ideas.")]
    }

@track_progress
def write_scene(state: StoryState) -> Dict:
    """Write a detailed scene based on the current chapter and scene."""
    chapters = state["chapters"]
    characters = state["characters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    genre = state["genre"]
    tone = state["tone"]
    author = state["author"]
    author_style_guidance = state["author_style_guidance"]
    global_story = state["global_story"]
    revelations = state["revelations"]
    creative_elements = state.get("creative_elements", {})
    
    # Get the current chapter and scene data
    chapter = chapters[current_chapter]
    scene = chapter["scenes"][current_scene]
    
    # Prepare author style guidance
    style_section = ""
    if author:
        style_section = f"""
        AUTHOR STYLE GUIDANCE:
        You are writing in the style of {author}. Apply these stylistic elements:
        
        {author_style_guidance}
        """
    
    # Get brainstormed creative elements for this scene
    scene_elements_key = f"scene_elements_ch{current_chapter}_sc{current_scene}"
    scene_surprises_key = f"scene_surprises_ch{current_chapter}_sc{current_scene}"
    
    creative_guidance = ""
    if creative_elements and scene_elements_key in creative_elements:
        # Extract recommended creative elements
        scene_elements = ""
        if creative_elements[scene_elements_key].get("recommended_ideas"):
            scene_elements = creative_elements[scene_elements_key]["recommended_ideas"]
        
        # Extract recommended surprises/twists
        scene_surprises = ""
        if scene_surprises_key in creative_elements and creative_elements[scene_surprises_key].get("recommended_ideas"):
            scene_surprises = creative_elements[scene_surprises_key]["recommended_ideas"]
        
        # Compile creative guidance
        creative_guidance = f"""
        BRAINSTORMED CREATIVE ELEMENTS:
        
        Recommended Scene Elements:
        {scene_elements}
        
        Recommended Surprise Elements:
        {scene_surprises}
        
        Incorporate these creative elements into your scene in natural, organic ways. Adapt them as needed
        while ensuring they serve the overall narrative and character development.
        """
    
    # Create a prompt for scene writing
    prompt = f"""
    Write a detailed scene for Chapter {current_chapter}: "{chapter['title']}" (Scene {current_scene}).
    
    Story context:
    - Genre: {genre}
    - Tone: {tone}
    - Chapter outline: {chapter['outline']}
    
    Characters present:
    {characters}
    
    Previously revealed information:
    {revelations.get('reader', [])}
    
    {creative_guidance}
    
    Your task is to write an engaging, vivid scene of 500-800 words that advances the story according to the chapter outline.
    Use rich descriptions, meaningful dialogue, and show character development.
    Ensure consistency with established character traits and previous events.
    
    Make sure to incorporate the brainstormed creative elements in compelling ways that enhance the scene.
    Use unexpected elements and surprising twists to keep readers engaged while maintaining narrative coherence.
    
    Write the scene in third-person perspective with a {tone} style appropriate for {genre} fiction.
    {style_section}
    """
    
    # Generate the scene content
    scene_content = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Store scene in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"chapter_{current_chapter}_scene_{current_scene}",
        "value": scene_content
    })
    
    # Store which creative elements were used
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"creative_elements_used_ch{current_chapter}_sc{current_scene}",
        "value": {
            "scene_elements_key": scene_elements_key,
            "scene_surprises_key": scene_surprises_key,
            "timestamp": "now"
        }
    })
    
    # Update the scene in the chapters dictionary
    updated_chapters = state["chapters"].copy()
    updated_chapters[current_chapter]["scenes"][current_scene]["content"] = scene_content
    
    # Update state with the new scene
    return {
        "chapters": updated_chapters,
        "last_node": "write_scene",
        "messages": [AIMessage(content=f"I've written scene {current_scene} of chapter {current_chapter} incorporating creative elements and surprising twists. Now I'll reflect on it to ensure quality and consistency.")]
    }

@track_progress
def reflect_on_scene(state: StoryState) -> Dict:
    """Reflect on the current scene to evaluate quality and consistency."""
    chapters = state["chapters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    characters = state["characters"]
    revelations = state["revelations"]
    global_story = state["global_story"]
    
    # Get the scene content
    scene_content = chapters[current_chapter]["scenes"][current_scene]["content"]
    
    # Gather previous scenes for context and continuity checking
    previous_scenes = []
    for chap_num in sorted(chapters.keys(), key=int):
        if int(chap_num) < int(current_chapter) or (chap_num == current_chapter and int(current_scene) > 1):
            for scene_num in sorted(chapters[chap_num]["scenes"].keys(), key=int):
                if chap_num == current_chapter and int(scene_num) >= int(current_scene):
                    continue
                prev_scene = chapters[chap_num]["scenes"][scene_num]["content"][:200]  # First 200 chars as summary
                previous_scenes.append(f"Chapter {chap_num}, Scene {scene_num}: {prev_scene}...")
    
    previous_context = "\n".join(previous_scenes[-5:])  # Last 5 scenes for context
    
    # Prompt for reflection
    prompt = f"""
    Analyze this scene from Chapter {current_chapter}, Scene {current_scene}:
    
    {scene_content}
    
    Story context:
    {global_story[:500]}...
    
    Previous scenes (summaries):
    {previous_context}
    
    Current character profiles:
    {characters}
    
    Previously revealed information:
    {revelations['reader'] if 'reader' in revelations else []}
    
    Evaluate the scene on these criteria:
    1. Consistency with established character traits and motivations
    2. Advancement of the plot according to the chapter outline
    3. Quality of writing (descriptions, dialogue, pacing)
    4. Tone and style appropriateness
    5. Information management (revelations and secrets)
    6. Continuity with previous scenes and the overall story arc
    
    Identify:
    - Any new information revealed to the reader that should be tracked
    - Any character developments or relationship changes
    - Any inconsistencies or continuity errors (e.g., contradictions with previous scenes, plot holes)
    - Any areas that need improvement
    
    Provide 3-5 specific reflection notes.
    """
    
    # Generate reflection
    reflection = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Extract new revelations from reflection for tracking
    revelation_prompt = f"""
    Based on this scene and reflection:
    
    Scene: {scene_content}
    
    Reflection: {reflection}
    
    Extract a list of any new information revealed to the reader that wasn't known before.
    Each item should be a specific fact or revelation that's now known to the reader.
    Format as a simple bulleted list.
    """
    
    # Get new revelations
    new_revelations_text = llm.invoke([HumanMessage(content=revelation_prompt)]).content
    
    # Convert to list (simplified)
    new_revelations = [line.strip().replace("- ", "") for line in new_revelations_text.split("\n") if line.strip().startswith("- ")]
    
    # Check for continuity errors
    continuity_prompt = f"""
    Based on this scene, reflection, and the story context so far:
    
    Scene: {scene_content}
    
    Reflection: {reflection}
    
    Story context:
    {global_story[:500]}...
    
    Previous scenes (summaries):
    {previous_context}
    
    Character profiles:
    {characters}
    
    Previously revealed information:
    {revelations['reader'] if 'reader' in revelations else []}
    
    Identify any specific continuity errors, contradictions, or plot holes in this scene.
    For each issue, specify:
    1. What the inconsistency is
    2. Why it's a problem (what it contradicts)
    3. How it could be fixed
    
    Format as a structured list of issues. If no issues are found, respond with "No continuity errors detected."
    """
    
    # Check for continuity errors
    continuity_check = llm.invoke([HumanMessage(content=continuity_prompt)]).content
    
    # Update revelations in state
    updated_revelations = state["revelations"].copy()
    updated_revelations["reader"] = updated_revelations.get("reader", []) + new_revelations
    
    # Store reflection notes in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"reflection_chapter_{current_chapter}_scene_{current_scene}",
        "value": reflection
    })
    
    # Store continuity check in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"continuity_check_chapter_{current_chapter}_scene_{current_scene}",
        "value": continuity_check
    })
    
    # Update the scene's reflection notes
    updated_chapters = state["chapters"].copy()
    updated_chapters[current_chapter]["scenes"][current_scene]["reflection_notes"] = [reflection, continuity_check]
    
    # Update state
    return {
        "chapters": updated_chapters,
        "revelations": updated_revelations,
        "last_node": "reflect_on_scene",
        "messages": [AIMessage(content=f"I've analyzed scene {current_scene} of chapter {current_chapter} for quality and consistency.")]
    }

@track_progress
def revise_scene_if_needed(state: StoryState) -> Dict:
    """Determine if the scene needs revision based on reflection notes and continuity errors."""
    chapters = state["chapters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    characters = state["characters"]
    global_story = state["global_story"]
    revelations = state["revelations"]
    
    # Get the scene content and reflection notes
    scene_content = chapters[current_chapter]["scenes"][current_scene]["content"]
    reflection_notes = chapters[current_chapter]["scenes"][current_scene]["reflection_notes"]
    
    # Check if there are continuity errors
    continuity_errors_detected = False
    continuity_notes = ""
    if len(reflection_notes) > 1:
        continuity_check = reflection_notes[1]
        if continuity_check != "No continuity errors detected.":
            continuity_errors_detected = True
            continuity_notes = continuity_check
    
    # Check if revision is needed (looking for critical issues in reflection)
    needs_revision = continuity_errors_detected
    if not needs_revision:
        for note in reflection_notes:
            if any(keyword in note.lower() for keyword in ["inconsistent", "contradiction", "error", "confusing", "improve", "revise"]):
                needs_revision = True
                break
    
    if needs_revision:
        # Prompt for scene revision
        prompt = f"""
        Revise this scene based on the following feedback:
        
        Original scene:
        {scene_content}
        
        Reflection notes:
        {reflection_notes[0]}
        
        Continuity issues:
        {continuity_notes}
        
        Story context:
        {global_story[:300]}...
        
        Character information:
        {characters}
        
        Previously revealed information:
        {revelations.get('reader', [])}
        
        Your task:
        1. Rewrite the scene to address ALL identified issues, especially continuity problems.
        2. Ensure consistency with previous events, character traits, and established facts.
        3. Maintain the same general plot progression and purpose of the scene.
        4. Improve the quality, style, and flow if needed.
        5. Ensure no NEW continuity errors are introduced.
        
        Provide a complete, polished scene that can replace the original.
        """
        
        # Generate revised scene
        revised_scene = llm.invoke([HumanMessage(content=prompt)]).content
        
        # Update the scene in chapters
        updated_chapters = state["chapters"].copy()
        updated_chapters[current_chapter]["scenes"][current_scene]["content"] = revised_scene
        
        # Store revision information in LangMem for procedural memory
        manage_memory_tool.invoke({
            "action": "create",
            "key": f"chapter_{current_chapter}_scene_{current_scene}_revision_reason",
            "value": {
                "had_continuity_errors": continuity_errors_detected,
                "continuity_notes": continuity_notes,
                "reflection_issues": reflection_notes[0]
            }
        })
        
        # Store revised scene in memory
        manage_memory_tool.invoke({
            "action": "create",
            "key": f"chapter_{current_chapter}_scene_{current_scene}_revised",
            "value": revised_scene
        })
        
        # Clear reflection notes to trigger a fresh analysis after revision
        updated_chapters[current_chapter]["scenes"][current_scene]["reflection_notes"] = []
        
        return {
            "chapters": updated_chapters,
            "last_node": "revise_scene_if_needed",
            "messages": [AIMessage(content=f"I've revised scene {current_scene} of chapter {current_chapter} to address continuity issues and other feedback.")]
        }
    else:
        # No revision needed
        manage_memory_tool.invoke({
            "action": "create",
            "key": f"chapter_{current_chapter}_scene_{current_scene}_revision_status",
            "value": "No revision needed - scene approved"
        })
        
        return {
            "last_node": "revise_scene_if_needed",
            "messages": [AIMessage(content=f"Scene {current_scene} of chapter {current_chapter} is consistent and well-crafted, no revision needed.")]
        }