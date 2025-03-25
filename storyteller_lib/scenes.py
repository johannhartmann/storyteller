"""
StoryCraft Agent - Scene generation and management nodes.
"""

from typing import Dict, List, Any

from storyteller_lib.config import llm, manage_memory_tool, search_memory_tool, MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from storyteller_lib.creative_tools import creative_brainstorm
from storyteller_lib.plot_threads import get_active_plot_threads_for_scene
from storyteller_lib.exposition import identify_telling_passages, convert_exposition_to_sensory, analyze_showing_vs_telling
from storyteller_lib import track_progress

def _prepare_author_style_guidance(author: str, author_style_guidance: str) -> str:
    """Prepare author style guidance section for scene writing."""
    if not author:
        return ""
        
    return f"""
    AUTHOR STYLE GUIDANCE:
    You are writing in the style of {author}. Apply these stylistic elements:
    
    {author_style_guidance}
    """

def _retrieve_language_elements(language: str) -> tuple:
    """Retrieve language elements and consistency instructions from memory."""
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
        print(f"Error retrieving language elements: {str(e)}")
    
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
                # Direct dictionary with value
                consistency_instruction = consistency_result["value"]
            elif isinstance(consistency_result, list):
                # List of objects
                for item in consistency_result:
                    if hasattr(item, 'key') and item.key == "language_consistency_instruction":
                        consistency_instruction = item.value
                        break
            elif isinstance(consistency_result, str):
                # Use as is
                consistency_instruction = consistency_result
    except Exception as e:
        print(f"Error retrieving language consistency instruction: {str(e)}")
        
    return language_elements, consistency_instruction, language_examples

def _prepare_language_guidance(language: str) -> str:
    """Prepare language guidance section for scene writing."""
    if language.lower() == DEFAULT_LANGUAGE:
        return ""
        
    _, consistency_instruction, language_examples = _retrieve_language_elements(language)
    
    return f"""
    LANGUAGE CONSIDERATIONS:
    You are writing this scene in {SUPPORTED_LANGUAGES[language.lower()]}. Consider the following:
    
    1. Use dialogue, expressions, and idioms natural to {SUPPORTED_LANGUAGES[language.lower()]}-speaking characters
    2. Incorporate cultural references, settings, and descriptions authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking regions
    3. Consider social norms, customs, and interpersonal dynamics typical in {SUPPORTED_LANGUAGES[language.lower()]} culture
    4. Use narrative techniques, pacing, and stylistic elements common in {SUPPORTED_LANGUAGES[language.lower()]} literature
    5. Ensure names, places, and cultural elements are appropriate for {SUPPORTED_LANGUAGES[language.lower()]}-speaking audiences
    
    {language_examples}
    
    {consistency_instruction}
    
    The scene should read as if it was originally written in {SUPPORTED_LANGUAGES[language.lower()]}, not translated.
    """

def _prepare_creative_guidance(creative_elements: Dict, current_chapter: str, current_scene: str) -> str:
    """Prepare creative guidance section for scene writing."""
    scene_elements_key = f"scene_elements_ch{current_chapter}_sc{current_scene}"
    scene_surprises_key = f"scene_surprises_ch{current_chapter}_sc{current_scene}"
    
    if not creative_elements or scene_elements_key not in creative_elements:
        return ""
    
    # Extract recommended creative elements
    scene_elements = ""
    if creative_elements[scene_elements_key].get("recommended_ideas"):
        scene_elements = creative_elements[scene_elements_key]["recommended_ideas"]
    
    # Extract recommended surprises/twists
    scene_surprises = ""
    if scene_surprises_key in creative_elements and creative_elements[scene_surprises_key].get("recommended_ideas"):
        scene_surprises = creative_elements[scene_surprises_key]["recommended_ideas"]
    
    # Compile creative guidance
    return f"""
    BRAINSTORMED CREATIVE ELEMENTS:
    
    Recommended Scene Elements:
    {scene_elements}
    
    Recommended Surprise Elements:
    {scene_surprises}
    
    Incorporate these creative elements into your scene in natural, organic ways. Adapt them as needed
    while ensuring they serve the overall narrative and character development.
    """
def _identify_scene_characters(chapter_outline: str, characters: Dict) -> List[str]:
    """Identify which characters are likely to appear in the scene."""
    scene_characters = []
    
    for char_name, char_data in characters.items():
        if char_name.lower() in chapter_outline.lower() or char_data.get('name', '').lower() in chapter_outline.lower():
            scene_characters.append(char_name)
    
    # If no characters were identified, include all characters
    if not scene_characters:
        scene_characters = list(characters.keys())
        
    return scene_characters

def _get_character_motivations(char_name: str) -> List[Dict[str, Any]]:
    """Get character motivations from memory."""
    try:
        # Try to retrieve character motivations from memory
        results = search_memory_tool.invoke({
            "query": f"character_motivations_{char_name}",
            "namespace": MEMORY_NAMESPACE
        })
        
        if results:
            # Handle different return types from search_memory_tool
            if isinstance(results, dict) and "value" in results:
                if "motivations" in results["value"]:
                    return results["value"]["motivations"]
                return results["value"]
            elif isinstance(results, list):
                for item in results:
                    if hasattr(item, 'key') and item.key == f"character_motivations_{char_name}":
                        if hasattr(item.value, 'motivations'):
                            return item.value.motivations
                        return item.value
        
        return []
    
    except Exception as e:
        print(f"Error retrieving character motivations: {str(e)}")
        return []

def _prepare_emotional_guidance(characters: Dict, scene_characters: List[str], tone: str, genre: str) -> str:
    """Prepare emotional guidance section for scene writing."""
    # Get motivation chains for each character
    motivation_chains = []
    for name in scene_characters:
        if name in characters:
            char = characters[name]
            char_name = char.get('name', name)
            
            # Get motivations from memory
            motivations = _get_character_motivations(name)
            
            # Format motivations
            if motivations:
                motivation_text = f"{char_name}'s motivations:\n"
                for m in motivations:
                    motivation_text += f"  - {m.get('motivation', 'Unknown')}"
                    if 'source' in m:
                        motivation_text += f" (from {m.get('source')})"
                    motivation_text += "\n"
                motivation_chains.append(motivation_text)
            else:
                # Use inner conflicts as fallback
                inner_conflicts = char.get('inner_conflicts', [{'description': 'No conflicts defined'}])
                if inner_conflicts:
                    conflict_desc = inner_conflicts[0].get('description', 'No conflicts defined')
                    motivation_chains.append(f"{char_name}'s conflict-based motivation: {conflict_desc}")
    
    # Format motivation chains text
    motivation_chains_text = "\n".join(motivation_chains) if motivation_chains else "No specific motivations identified."
    
    return f"""
    EMOTIONAL DEPTH GUIDANCE:
    
    Focus on creating emotional resonance in this scene through:
    
    1. CHARACTER EMOTIONS:
       - Show how characters feel through actions, dialogue, and internal thoughts
       - Reveal the emotional impact of events on each character
       - Demonstrate emotional contrasts between different characters
    
    2. INNER STRUGGLES:
       - Highlight the inner conflicts of these characters:
         {', '.join([f"{characters[name].get('name', name)} ({characters[name].get('inner_conflicts', [{'description': 'No conflicts defined'}])[0].get('description', 'No conflicts defined')})"
                    for name in scene_characters if name in characters])}
       - Show characters wrestling with difficult choices or moral dilemmas
       - Reveal how external events trigger internal turmoil
    
    3. EMOTIONAL JOURNEY:
       - Connect emotions to character arcs and development
       - Show subtle shifts in emotional states that build toward larger changes
       - Create moments of emotional revelation or realization
    
    4. READER ENGAGEMENT:
       - Craft scenes that evoke {tone} emotional responses appropriate for {genre}
       - Balance multiple emotional notes (e.g., tension with humor, fear with hope)
       - Use sensory details to make emotional moments vivid and immersive
       
    5. MOTIVATION-ACTION-REACTION CHAINS:
       - Ensure these character motivations drive their actions and emotional reactions:
       
       {motivation_chains_text}
       
       - Show how competing motivations create internal conflicts
       - Demonstrate how character motivations drive their emotional reactions
       - Reveal motivations through actions and choices rather than statements
       - Ensure character reactions reflect both immediate circumstances AND long-term goals
    """

def _identify_relevant_world_categories(chapter_outline: str, world_elements: Dict) -> List[str]:
    """Identify which world element categories are most relevant to the scene."""
    relevant_categories = []
    chapter_outline_lower = chapter_outline.lower()
    
    # Geography is almost always relevant
    if "geography" in world_elements:
        relevant_categories.append("geography")
    
    # Check chapter outline for keywords that might indicate relevant world elements
    if any(keyword in chapter_outline_lower for keyword in ["government", "law", "ruler", "authority", "power"]):
        if "politics" in world_elements:
            relevant_categories.append("politics")
            
    if any(keyword in chapter_outline_lower for keyword in ["god", "faith", "belief", "pray", "ritual", "worship"]):
        if "religion" in world_elements:
            relevant_categories.append("religion")
            
    if any(keyword in chapter_outline_lower for keyword in ["technology", "machine", "device", "magic", "spell"]):
        if "technology_magic" in world_elements:
            relevant_categories.append("technology_magic")
            
    if any(keyword in chapter_outline_lower for keyword in ["history", "past", "ancient", "legend", "myth"]):
        if "history" in world_elements:
            relevant_categories.append("history")
            
    if any(keyword in chapter_outline_lower for keyword in ["culture", "tradition", "custom", "art", "music"]):
        if "culture" in world_elements:
            relevant_categories.append("culture")
            
    if any(keyword in chapter_outline_lower for keyword in ["trade", "money", "market", "business", "economy"]):
        if "economics" in world_elements:
            relevant_categories.append("economics")
            
    if any(keyword in chapter_outline_lower for keyword in ["food", "clothing", "home", "family", "daily"]):
        if "daily_life" in world_elements:
            relevant_categories.append("daily_life")
    
    # If no specific categories were identified, include all categories
    if not relevant_categories and world_elements:
        relevant_categories = list(world_elements.keys())
    
    return relevant_categories
def _get_previously_established_elements(world_elements: Dict) -> str:
    """Get previously established world elements from memory."""
    try:
        # Try to retrieve world state tracker from memory
        results = search_memory_tool.invoke({
            "query": "world_state_tracker",
            "namespace": MEMORY_NAMESPACE
        })
        
        world_state_tracker = None
        if results:
            # Handle different return types from search_memory_tool
            if isinstance(results, dict) and "value" in results:
                world_state_tracker = results["value"]
            elif isinstance(results, list):
                for item in results:
                    if hasattr(item, 'key') and item.key == "world_state_tracker":
                        world_state_tracker = item.value
                        break
        
        if not world_state_tracker or "revelations" not in world_state_tracker or not world_state_tracker["revelations"]:
            return "No previously established elements."
        
        # Extract the most recent revelations (up to 5)
        recent_revelations = world_state_tracker["revelations"][-5:]
        
        # Format the revelations
        revelations_text = ""
        for revelation in recent_revelations:
            revelations_text += f"- {revelation['element']}: {revelation['description']}\n"
        
        return revelations_text
    
    except Exception as e:
        print(f"Error retrieving previously established elements: {str(e)}")
        return "Error retrieving previously established elements."

def _prepare_worldbuilding_guidance(world_elements: Dict, chapter_outline: str, mystery_relevance: bool = False) -> str:
    """Prepare worldbuilding guidance section for scene writing."""
    if not world_elements:
        return ""
        
    relevant_categories = _identify_relevant_world_categories(chapter_outline, world_elements)
    
    # Apply mystery relevance filtering if requested
    if mystery_relevance and "mystery_elements" in world_elements:
        # Get key mysteries
        key_mysteries = []
        if isinstance(world_elements["mystery_elements"], dict) and "key_mysteries" in world_elements["mystery_elements"]:
            key_mysteries = [m["name"] for m in world_elements["mystery_elements"]["key_mysteries"]]
        
        # Filter categories that contain references to key mysteries
        if key_mysteries:
            mystery_relevant_categories = []
            for category in relevant_categories:
                if category in world_elements:
                    category_str = str(world_elements[category])
                    if any(mystery.lower() in category_str.lower() for mystery in key_mysteries):
                        mystery_relevant_categories.append(category)
            
            # If we found mystery-relevant categories, prioritize them
            if mystery_relevant_categories:
                # Still keep geography if it's in the original relevant categories
                if "geography" in relevant_categories and "geography" not in mystery_relevant_categories:
                    mystery_relevant_categories.insert(0, "geography")
                
                # Update relevant categories to prioritize mystery-relevant ones
                relevant_categories = mystery_relevant_categories + [c for c in relevant_categories if c not in mystery_relevant_categories]
    
    # Limit to at most 3 most relevant categories to avoid overwhelming the prompt
    if len(relevant_categories) > 3:
        # Geography is most important, so keep it if it's there
        if "geography" in relevant_categories:
            relevant_categories.remove("geography")
            selected_categories = ["geography"] + relevant_categories[:2]
        else:
            selected_categories = relevant_categories[:3]
    else:
        selected_categories = relevant_categories
        selected_categories = relevant_categories
    
    # Create the worldbuilding guidance section
    worldbuilding_sections = []
    for category in selected_categories:
        if category in world_elements:
            category_elements = world_elements[category]
            category_section = f"{category.upper()}:\n"
            
            for key, value in category_elements.items():
                if isinstance(value, list) and value:
                    # For lists, include the first 2-3 items
                    items_to_include = value[:min(3, len(value))]
                    category_section += f"- {key.replace('_', ' ').title()}: {', '.join(items_to_include)}\n"
                elif value:
                    # For strings or other values
                    category_section += f"- {key.replace('_', ' ').title()}: {value}\n"
            
            worldbuilding_sections.append(category_section)
    
    # Combine the sections
    worldbuilding_details = "\n".join(worldbuilding_sections)
    
    # Get previously established elements
    previously_established = _get_previously_established_elements(world_elements)
    
    # Check if there are mystery elements to emphasize
    mystery_guidance = ""
    if mystery_relevance and "mystery_elements" in world_elements:
        key_mysteries = []
        if isinstance(world_elements["mystery_elements"], dict) and "key_mysteries" in world_elements["mystery_elements"]:
            key_mysteries = world_elements["mystery_elements"]["key_mysteries"]
        
        if key_mysteries:
            mystery_guidance = """
            MYSTERY ELEMENTS GUIDANCE:
            - Introduce mystery elements through character interactions rather than narrator explanation
            - Show characters' different perspectives on these elements
            - Create scenes where characters must interact with these elements
            - Use physical artifacts, locations, or rituals to embody abstract concepts
            - Reveal information gradually through subtle clues rather than exposition
            """
    
    return f"""
    WORLDBUILDING ELEMENTS:
    
    Previously Established Elements:
    {previously_established}
    
    Incorporate these established world elements into your scene:
    
    {worldbuilding_details}
    
    {mystery_guidance}
    
    Ensure consistency with these world elements while writing the scene. The setting, cultural references,
    technology/magic, and other world details should align with these established elements.
    
    SENSORY EXPERIENCE GUIDANCE:
    When describing world elements, focus on how they would be EXPERIENCED through:
    - Visual details (what would a character SEE?)
    - Sounds (what would a character HEAR?)
    - Smells, tastes, and textures (what physical sensations are associated?)
    - Emotional reactions (how do characters FEEL about these elements?)
    """
def _generate_previous_scenes_summary(state: StoryState) -> str:
    """
    Generate a comprehensive summary of previous chapters and scenes with focus on recent events.
    
    Args:
        state: The current story state
        
    Returns:
        A formatted summary of previous chapters and scenes
    """
    chapters = state["chapters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    
    # Initialize summary sections
    chapter_summaries = []
    recent_scene_details = []
    
    # Process each chapter
    for chap_num in sorted(chapters.keys(), key=int):
        chapter = chapters[chap_num]
        
        # Skip current chapter and scene
        if int(chap_num) > int(current_chapter):
            continue
            
        # For previous chapters, create a brief summary
        if int(chap_num) < int(current_chapter):
            scenes_count = len(chapter["scenes"])
            chapter_summary = f"Chapter {chap_num}: {chapter.get('title', 'Untitled')}\n"
            chapter_summary += f"Summary: {chapter.get('outline', 'No outline available')[:300]}...\n"
            chapter_summary += f"Contains {scenes_count} scenes\n"
            
            # Add key events from the chapter (last scene as conclusion)
            if scenes_count > 0:
                last_scene_num = max(chapter["scenes"].keys(), key=int)
                last_scene = chapter["scenes"][last_scene_num]
                # Extract first 200 chars as a glimpse
                last_scene_glimpse = last_scene.get("content", "")[:200]
                chapter_summary += f"Conclusion: {last_scene_glimpse}...\n"
                
            chapter_summaries.append(chapter_summary)
        
        # For current chapter, include more detailed scene summaries
        elif int(chap_num) == int(current_chapter):
            # Add chapter info
            chapter_summary = f"Current Chapter {chap_num}: {chapter.get('title', 'Untitled')}\n"
            chapter_summary += f"Outline: {chapter.get('outline', 'No outline available')}\n"
            chapter_summaries.append(chapter_summary)
            
            # Add detailed summaries of previous scenes in current chapter
            for scene_num in sorted(chapter["scenes"].keys(), key=int):
                if int(scene_num) >= int(current_scene):
                    continue
                    
                scene = chapter["scenes"][scene_num]
                scene_content = scene.get("content", "")
                
                # Create a more detailed summary for recent scenes
                scene_summary = f"Scene {scene_num}:\n"
                
                # Include first and last paragraph for context
                paragraphs = [p for p in scene_content.split("\n\n") if p.strip()]
                if paragraphs:
                    if len(paragraphs) == 1:
                        # If only one paragraph, include a portion
                        scene_summary += f"Content: {paragraphs[0][:300]}...\n"
                    else:
                        # Include first and last paragraph
                        scene_summary += f"Beginning: {paragraphs[0][:200]}...\n"
                        scene_summary += f"Ending: {paragraphs[-1][:200]}...\n"
                
                # Include any structured reflection data if available
                if "structured_reflection" in scene:
                    reflection = scene["structured_reflection"]
                    if reflection and "formatted_issues" in reflection:
                        scene_summary += "Key points from reflection:\n"
                        for issue in reflection["formatted_issues"][:2]:  # Limit to 2 issues
                            scene_summary += f"- {issue}\n"
                
                recent_scene_details.append(scene_summary)
    
    # Combine all summaries
    full_summary = ""
    
    # Include chapter summaries (limit to last 3 if there are many)
    if chapter_summaries:
        if len(chapter_summaries) > 3:
            full_summary += "PREVIOUS CHAPTERS SUMMARY (most recent 3):\n"
            full_summary += "\n".join(chapter_summaries[-3:])
        else:
            full_summary += "PREVIOUS CHAPTERS SUMMARY:\n"
            full_summary += "\n".join(chapter_summaries)
    
    # Include detailed scene summaries (limit to last 5 if there are many)
    if recent_scene_details:
        full_summary += "\n\nRECENT SCENES DETAILS:\n"
        if len(recent_scene_details) > 5:
            full_summary += "\n".join(recent_scene_details[-5:])
        else:
            full_summary += "\n".join(recent_scene_details)
    
    return full_summary

def _prepare_plot_thread_guidance(active_plot_threads: List[Dict]) -> str:
    """Prepare plot thread guidance section for scene writing."""
    if not active_plot_threads:
        return ""
        
    plot_thread_sections = []
    
    # Group threads by importance
    major_threads = [t for t in active_plot_threads if t["importance"] == "major"]
    minor_threads = [t for t in active_plot_threads if t["importance"] == "minor"]
    background_threads = [t for t in active_plot_threads if t["importance"] == "background"]
    
    # Format major threads
    if major_threads:
        major_section = "MAJOR PLOT THREADS (must be addressed):\n"
        for thread in major_threads:
            major_section += f"- {thread['name']}: {thread['description']}\n  Status: {thread['status']}\n  Last development: {thread['last_development']}\n"
        plot_thread_sections.append(major_section)
    
    # Format minor threads
    if minor_threads:
        minor_section = "MINOR PLOT THREADS (should be addressed if relevant):\n"
        for thread in minor_threads:
            minor_section += f"- {thread['name']}: {thread['description']}\n  Status: {thread['status']}\n"
        plot_thread_sections.append(minor_section)
    
    # Format background threads
    if background_threads:
        background_section = "BACKGROUND THREADS (can be referenced):\n"
        for thread in background_threads:
            background_section += f"- {thread['name']}: {thread['description']}\n"
        plot_thread_sections.append(background_section)
    
    # Combine all sections
    joined_sections = "\n".join(plot_thread_sections)
    return (
        f"ACTIVE PLOT THREADS:\n\n"
        f"{joined_sections}\n\n"
        f"Ensure that major plot threads are meaningfully advanced in this scene.\n"
        f"Minor threads should be addressed if they fit naturally with the scene's purpose.\n"
        f"Background threads can be referenced to maintain continuity."
    )

@track_progress
def brainstorm_scene_elements(state: StoryState) -> Dict:
    """Brainstorm creative elements for the current scene."""
    chapters = state["chapters"]
    characters = state["characters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    genre = state["genre"]
    language = state.get("language", DEFAULT_LANGUAGE)
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
    
    # Get initial idea directly from state
    initial_idea = state.get("initial_idea", "")
    initial_idea_elements = state.get("initial_idea_elements", {})
    
    # Add initial idea constraints to context if available
    if initial_idea:
        
        # Build constraints from initial idea elements
        constraints = []
        if initial_idea_elements:
            if initial_idea_elements.get("setting"):
                constraints.append(f"Setting: {initial_idea_elements.get('setting')}")
            if initial_idea_elements.get("characters"):
                constraints.append(f"Characters: {', '.join(initial_idea_elements.get('characters'))}")
            if initial_idea_elements.get("plot"):
                constraints.append(f"Plot: {initial_idea_elements.get('plot')}")
        
        context += f"""
        
        IMPORTANT: This story is based on the following initial idea:
        {initial_idea}
        
        Key elements that must be preserved:
        {' '.join(constraints) if constraints else "Ensure the scene aligns with the initial idea."}
        """
    
    # Brainstorm scene-specific elements
    scene_elements_results = creative_brainstorm(
        topic=f"Scene {current_scene} Creative Elements",
        genre=genre,
        tone=tone,
        context=context,
        author=author,
        author_style_guidance=author_style_guidance,
        language=language,
        num_ideas=4,
        evaluation_criteria=[
            "Visual impact and memorability",
            "Character development opportunity",
            "Advancement of plot in unexpected ways",
            "Emotional resonance",
            "Consistency with established world rules"
        ],
        strict_adherence=True
    )
    
    # Brainstorm potential surprises or twists for this scene
    scene_surprises_results = creative_brainstorm(
        topic=f"Unexpected Elements for Scene {current_scene}",
        genre=genre,
        tone=tone,
        context=context,
        author=author,
        author_style_guidance=author_style_guidance,
        language=language,
        num_ideas=3,
        evaluation_criteria=[
            "Surprise factor",
            "Logical consistency with established facts",
            "Impact on future plot development",
            "Character reaction potential",
            "Reader engagement"
        ],
        strict_adherence=True
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
        
        "messages": [
            *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
            AIMessage(content=f"I've brainstormed creative elements and unexpected twists for scene {current_scene} of chapter {current_chapter}. Now I'll write the scene incorporating the most promising ideas.")
        ]
    }
@track_progress
def write_scene(state: StoryState) -> Dict:
    """Write a detailed scene based on the current chapter and scene."""
    # Extract state variables
    chapters = state["chapters"]
    characters = state["characters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    genre = state["genre"]
    tone = state["tone"]
    author = state["author"]
    author_style_guidance = state["author_style_guidance"]
    language = state.get("language", DEFAULT_LANGUAGE)
    global_story = state["global_story"]
    revelations = state["revelations"]
    creative_elements = state.get("creative_elements", {})
    
    # Get showing vs. telling parameters
    showing_ratio = state.get("showing_ratio", 8)  # Default to 8/10 showing vs telling
    post_process_showing = state.get("post_process_showing", True)  # Default to post-processing
    
    # Get the current chapter and scene data
    chapter = chapters[current_chapter]
    scene = chapter["scenes"][current_scene]
    
    # Get worldbuilding elements if available
    world_elements = state.get("world_elements", {})
    
    # Integrate pacing, dialogue, and exposition improvements
    from storyteller_lib.integration import integrate_improvements
    integrated_guidance = integrate_improvements(state)
    
    # Extract guidance components
    pacing_guidance = integrated_guidance.get("pacing_guidance", "")
    dialogue_guidance = integrated_guidance.get("dialogue_guidance", "")
    exposition_guidance = integrated_guidance.get("exposition_guidance", "")
    concepts_to_introduce = integrated_guidance.get("concepts_to_introduce", [])
    scene_purpose = integrated_guidance.get("scene_purpose", "")
    
    # Get scene elements key and scene surprises key
    scene_elements_key = f"scene_elements_ch{current_chapter}_sc{current_scene}"
    scene_surprises_key = f"scene_surprises_ch{current_chapter}_sc{current_scene}"
    
    # Use helper functions to prepare guidance sections
    style_section = _prepare_author_style_guidance(author, author_style_guidance)
    language_section = _prepare_language_guidance(language)
    creative_guidance = _prepare_creative_guidance(creative_elements, current_chapter, current_scene)
    
    # Identify which characters are likely to appear in this scene
    scene_characters = _identify_scene_characters(chapter.get('outline', ''), characters)
    
    # Create emotional guidance based on character arcs and inner conflicts
    emotional_guidance = _prepare_emotional_guidance(characters, scene_characters, tone, genre)
    
    # Create worldbuilding guidance
    worldbuilding_guidance = _prepare_worldbuilding_guidance(world_elements, chapter.get('outline', ''))
    
    # Get active plot threads for this scene
    active_plot_threads = get_active_plot_threads_for_scene(state)
    
    # Create plot thread guidance
    plot_thread_guidance = _prepare_plot_thread_guidance(active_plot_threads)
    
    # Create showing vs. telling guidance
    showing_telling_guidance = (
        f"SHOWING VS TELLING BALANCE:\n"
        f"- Aim for a showing:telling ratio of {showing_ratio}:10\n"
        f"- Minimum sensory details per paragraph: 2\n"
        f"- Convert explanations into experiences, observations, or interactions\n"
        f"- Show emotions through physical reactions rather than naming them\n\n"
        f"SHOW, DON'T TELL GUIDELINES:\n"
        f"- Convert every explanation into a sensory experience or character interaction\n"
        f"- Replace statements about emotions with physical manifestations of those emotions\n"
        f"- Demonstrate world elements through how characters interact with them\n"
        f"- Use specific, concrete details rather than general descriptions\n"
        f"- Create scenes where characters discover information rather than being told it\n\n"
        f"BEFORE AND AFTER EXAMPLE:\n\n"
        f"TELLING: \"The Sulfmeister were resentful of the Patrizier's power over the salt trade.\"\n\n"
        f"SHOWING: \"Muller's knuckles whitened around his salt measure as the Patrizier's tax collector approached. "
        f"The other Sulfmeister exchanged glances, their shoulders tensing beneath salt-crusted coats. "
        f"No one spoke, but their silence carried the weight of generations of resentment.\""
    )
    # Generate a comprehensive summary of previous chapters and scenes
    previous_scenes_summary = _generate_previous_scenes_summary(state)
    
    # Create a prompt for scene writing
    prompt = f"""
    Write a detailed scene for Chapter {current_chapter}: "{chapter['title']}" (Scene {current_scene}).
    
    Story context:
    - Genre: {genre}
    - Tone: {tone}
    - Chapter outline: {chapter['outline']}
    - Scene purpose: {scene_purpose}
    
    Characters present:
    {characters}
    
    Previously revealed information:
    {revelations.get('reader', [])}
    
    PREVIOUS CONTENT SUMMARY:
    {previous_scenes_summary}
    
    {worldbuilding_guidance}
    {worldbuilding_guidance}
    
    {creative_guidance}
    
    {emotional_guidance}
    
    {plot_thread_guidance}
    
    {pacing_guidance}
    
    {dialogue_guidance}
    
    {exposition_guidance}
    
    {showing_telling_guidance}
    
    {integrated_guidance.get("consistency_guidance", "")}
    
    {integrated_guidance.get("variation_guidance", "")}
    Your task is to write an engaging, vivid scene of 2100-3360 words that advances the story according to the chapter outline.
    Use rich descriptions, meaningful dialogue, and show character development.
    Ensure consistency with established character traits and previous events.
    
    Make sure to incorporate the brainstormed creative elements in compelling ways that enhance the scene.
    Use unexpected elements and surprising twists to keep readers engaged while maintaining narrative coherence.
    
    Write the scene in third-person perspective with a {tone} style appropriate for {genre} fiction.
    {style_section}
    {language_section}
    
    CRITICAL LANGUAGE INSTRUCTION:
    This scene MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
    ALL content - including narrative, dialogue, descriptions, and character thoughts - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
    DO NOT switch to any other language at ANY point in the scene.
    DO NOT include ANY English text in your response.
    
    This is a STRICT requirement. The ENTIRE scene must be written ONLY in {SUPPORTED_LANGUAGES[language.lower()]}.
    
    CRITICAL INSTRUCTION: Return ONLY the actual scene content. Do NOT include any explanations, comments, notes, or meta-information about your writing process or choices. Do NOT include any text like "Here's the scene" or "Key improvements" or any other commentary. The output should be ONLY the narrative text that will appear in the final story.
    IMPORTANT: If the language is set to {SUPPORTED_LANGUAGES[language.lower()]}, you MUST write the ENTIRE scene in {SUPPORTED_LANGUAGES[language.lower()]}. Do not include any text in English or any other language. The complete scene must be written only in {SUPPORTED_LANGUAGES[language.lower()]}.
    """
    
    # Try to use structured output first, but fall back to regular output if it fails
    try:
        # Define a Pydantic model for structured scene content
        from pydantic import BaseModel, Field
        
        class SceneContent(BaseModel):
            """Model for structured scene content."""
            content: str = Field(
                description="The actual scene content that will be included in the story. This should be the narrative text only, without any explanations, comments, or meta-information."
            )
        
        # Use LangChain's structured output capabilities
        structured_llm = llm.with_structured_output(SceneContent)
        
        # Generate the scene content with structured output
        structured_response = structured_llm.invoke(prompt)
        
        # Check if we got a valid response
        if structured_response and hasattr(structured_response, 'content'):
            scene_content = structured_response.content
            print(f"Successfully used structured output for scene {current_chapter}_{current_scene}")
        else:
            # Fall back to regular output
            print(f"Structured output failed for scene {current_chapter}_{current_scene}, falling back to regular output")
            scene_content = llm.invoke([HumanMessage(content=prompt)]).content
    except Exception as e:
        # Log the error and fall back to regular output
        print(f"Error using structured output for scene {current_chapter}_{current_scene}: {str(e)}")
        print("Falling back to regular output")
        scene_content = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Apply post-processing for showing vs. telling if enabled
    if post_process_showing:
        try:
            # Import the necessary functions from exposition.py
            from storyteller_lib.exposition import identify_telling_passages, convert_exposition_to_sensory
            
            # Identify telling passages
            telling_passages = identify_telling_passages(scene_content)
            
            # Convert each passage to showing
            if telling_passages:
                print(f"Post-processing {len(telling_passages)} telling passages to showing for scene {current_chapter}_{current_scene}")
                
                # Track original and converted passages for analysis
                conversion_tracking = []
                
                # Process each telling passage
                for passage in telling_passages:
                    if len(passage) > 20:  # Only process substantial passages
                        # Convert to sensory description
                        sensory_version = convert_exposition_to_sensory(passage)
                        
                        # Replace in the scene content if conversion was successful
                        if sensory_version and sensory_version != passage:
                            # Track the conversion
                            conversion_tracking.append({
                                "original": passage,
                                "converted": sensory_version
                            })
                            
                            # Replace in the scene content
                            scene_content = scene_content.replace(passage, sensory_version)
                
                # Store conversion tracking in memory for analysis
                if conversion_tracking:
                    manage_memory_tool.invoke({
                        "action": "create",
                        "key": f"showing_telling_conversions_ch{current_chapter}_sc{current_scene}",
                        "value": conversion_tracking,
                        "namespace": MEMORY_NAMESPACE
                    })
        except Exception as e:
            print(f"Error in showing vs. telling post-processing: {str(e)}")
    
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
    
    # Update state with the new scene using targeted updates
    # Instead of copying the entire chapters dictionary
    scene_update = {
        current_scene: {
            "content": scene_content
        }
    }
    
    # Get initial idea from state
    initial_idea = state.get("initial_idea", "")
    
    return {
        "chapters": {
            current_chapter: {
                "scenes": scene_update
            }
        },
        
        "messages": [
            *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
            AIMessage(content=f"I've written scene {current_scene} of chapter {current_chapter} incorporating creative elements and surprising twists. Now I'll reflect on it to ensure quality and consistency.")
        ]
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
    
    # Get worldbuilding elements if available
    world_elements = state.get("world_elements", {})
    
    # Get previously addressed issues if available
    previously_addressed_issues = chapters[current_chapter]["scenes"][current_scene].get("issues_addressed", [])
    # Update plot threads based on this scene
    from storyteller_lib.plot_threads import update_plot_threads
    plot_thread_updates = update_plot_threads(state)
    
    # Check scene closure
    from storyteller_lib.scene_closure import check_and_improve_scene_closure
    needs_improved_closure, closure_analysis, improved_scene = check_and_improve_scene_closure(state)
    
    # Update scene content if closure improvement is needed
    if needs_improved_closure:
        scene_content = improved_scene
        # Update the scene content in the state
        chapters[current_chapter]["scenes"][current_scene]["content"] = improved_scene
        print(f"Improved scene closure for Chapter {current_chapter}, Scene {current_scene}")
    
    world_elements = state.get("world_elements", {})
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
    
    # We're using a JSON-based approach rather than structured output with Pydantic models
    
    # Prepare worldbuilding context
    worldbuilding_context = ""
    if world_elements:
        # Format the world elements for the prompt
        worldbuilding_sections = []
        for category, elements in world_elements.items():
            category_section = f"{category.upper()}:\n"
            for key, value in elements.items():
                if isinstance(value, list) and value:
                    # For lists, include a summary
                    category_section += f"- {key.replace('_', ' ').title()}: {', '.join(value[:3])}\n"
                elif value:
                    # For strings or other values
                    category_section += f"- {key.replace('_', ' ').title()}: {value}\n"
            worldbuilding_sections.append(category_section)
        
        worldbuilding_context = "Established World Elements:\n" + "\n".join(worldbuilding_sections)
    
    # Format previously addressed issues if any
    previously_addressed_section = ""
    if previously_addressed_issues:
        issues_text = "\n".join([f"- {issue.get('type', 'unknown').upper()}: {issue.get('description', 'No description')}"
                               for issue in previously_addressed_issues])
        previously_addressed_section = f"""
        IMPORTANT - Previously Addressed Issues:
        The following issues have already been identified and addressed in previous revisions.
        DO NOT report these issues again unless they still exist in the current version:
        
        {issues_text}
        """
    
    # Get language from state
    language = state.get("language", DEFAULT_LANGUAGE)
    
    # Prepare language validation section
    language_validation_section = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_validation_section = f"""
        LANGUAGE VALIDATION:
        The story is supposed to be written in {SUPPORTED_LANGUAGES[language.lower()]}.
        You MUST check if the scene is actually written in {SUPPORTED_LANGUAGES[language.lower()]} or if it was mistakenly written in English or another language.
        
        If the scene is NOT written in {SUPPORTED_LANGUAGES[language.lower()]}, you MUST:
        1. Create an issue with type "language_mismatch"
        2. Set the severity to 10 (highest)
        3. Provide a recommendation to rewrite the scene entirely in {SUPPORTED_LANGUAGES[language.lower()]}
        4. Set needs_revision to true
        """
    
    # Prompt for structured reflection
    prompt = (
        f"Analyze this scene from Chapter {current_chapter}, Scene {current_scene}:\n\n"
        f"{scene_content}\n\n"
        f"Story context:\n"
        f"{global_story[:500]}...\n\n"
        f"Previous scenes (summaries):\n"
        f"{previous_context}\n\n"
        f"Current character profiles:\n"
        f"{characters}\n\n"
        f"Previously revealed information:\n"
        f"{revelations['reader'] if 'reader' in revelations else []}\n\n"
        f"{worldbuilding_context}\n\n"
        f"Scene Closure Analysis:\n"
        f"Status: {closure_analysis['closure_status']}\n"
        f"Score: {closure_analysis['closure_score']}/10\n"
        f"Issues: {', '.join(closure_analysis['issues']) if closure_analysis['issues'] else 'None'}\n\n"
        f"{previously_addressed_section}\n\n"
        f"{language_validation_section}\n\n"
        f"Evaluate the scene on these criteria and include in criteria_ratings:\n"
        f"- character_consistency: Consistency with established character traits and motivations\n"
        f"- plot_advancement: Advancement of the plot according to the chapter outline\n"
        f"- writing_quality: Quality of writing (descriptions, dialogue, pacing)\n"
        f"- tone_appropriateness: Tone and style appropriateness\n"
        f"- information_management: Information management (revelations and secrets)\n"
        f"- continuity: Continuity with previous scenes and the overall story arc\n"
        f"- worldbuilding_consistency: Consistency with established world elements (geography, culture, politics, etc.)\n"
        f"- emotional_depth: Depth and authenticity of emotional content and resonance\n"
        f"- character_relatability: How relatable and human the characters feel to readers\n"
        f"- inner_conflict_development: Development of characters' inner struggles and dilemmas\n"
        f"- scene_closure: How well the scene concludes with proper narrative closure\n\n"
        f"Identify:\n"
        f"- Any new information revealed to the reader that should be tracked\n"
        f"- Any character developments or relationship changes\n"
        f"- Any emotional developments or shifts in characters\n"
        f"- Any progress in character arcs or inner conflicts\n"
        f"- Any world elements introduced or expanded upon in this scene\n"
        f"- Any changes to the established world (geography, culture, politics, etc.)\n"
        f"- Any NEW inconsistencies or continuity errors (e.g., contradictions with previous scenes, plot holes)\n"
        f"- Any NEW worldbuilding inconsistencies (e.g., contradictions with established world elements)\n"
        f"- Any NEW areas that need improvement in emotional depth or character development\n"
        f"- Any NEW areas that need improvement in worldbuilding integration\n"
        f"- Any NEW areas that need improvement\n\n"
        f"DO NOT report issues that have already been addressed in previous revisions (listed above).\n"
        f"Focus ONLY on identifying NEW issues that still exist in the current version of the scene.\n\n"
        f"IMPORTANT: For each NEW issue you identify, you MUST provide:\n"
        f"1. A SPECIFIC and DETAILED description of the issue (not just \"plot hole\" or \"pacing issue\")\n"
        f"2. A CONCRETE example from the scene that demonstrates the issue\n"
        f"3. A SPECIFIC recommendation for how to fix the issue\n\n"
        f"For example, instead of \"Plot hole detected\", write \"Plot hole: The detective claims he's never been to Lüneburg before, but in the previous scene he mentioned growing up there. This contradicts his established backstory.\"\n\n"
        f"Remember to ONLY report NEW issues that haven't been addressed in previous revisions.\n\n"
        f"For severity ratings:\n"
        f"- 8-10: Critical issues that significantly impact story coherence or reader experience\n"
        f"- 6-7: Moderate issues that should be addressed but don't break the story\n"
        f"- 3-5: Minor issues that would improve the story if fixed\n"
        f"- 1-2: Nitpicks or stylistic preferences\n\n"
        f"DO NOT default to a middle severity - evaluate each issue carefully and assign a specific severity.\n"
        f"DO NOT use generic descriptions like \"Unspecified plot hole\" - be specific and detailed about each issue.\n"
        f"DO NOT report issues that have already been addressed in previous revisions - focus only on NEW issues.\n\n"
        f"CRITICAL INSTRUCTION: You MUST set 'needs_revision' to true if ANY of these conditions are met:\n"
        f"- Any criteria score is 5 or below\n"
        f"- There are any NEW continuity errors, character inconsistencies, plot holes, or worldbuilding inconsistencies\n"
        f"- There is a language mismatch (scene not written in the specified language)\n"
        f"- There are multiple NEW issues of any type\n"
        f"- The overall quality of the scene is significantly below the standards of the story\n"
        f"- The scene contradicts established world elements in significant ways\n"
        f"- The scene_closure score is 4 or below, indicating an abrupt or incomplete ending\n\n"
        f"If you identify ANY NEW issues at all, you should carefully consider whether revision is needed.\n"
        f"Do not report issues that have already been addressed in previous revisions unless they still exist.\n"
        f"Do not leave NEW issues unaddressed - if you find NEW problems, set needs_revision=true."
    )
    
    # Add language instruction for reflection
    if language.lower() != DEFAULT_LANGUAGE:
        prompt += (
            f"\nCRITICAL LANGUAGE INSTRUCTION:\n"
            f"Your analysis MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.\n"
            f"ALL content - including your analysis, comments, and recommendations - must be in {SUPPORTED_LANGUAGES[language.lower()]}.\n"
            f"DO NOT switch to any other language at ANY point in your analysis.\n"
            f"DO NOT include ANY English text in your response.\n\n"
            f"This is a STRICT requirement. The ENTIRE analysis must be written ONLY in {SUPPORTED_LANGUAGES[language.lower()]}.\n"
        )
    
    # Use Pydantic for structured output
    from typing import List, Dict, Optional, Literal, Any, Union
    from pydantic import BaseModel, Field, field_validator
    # Define Pydantic models for the nested structure
    class CriteriaRating(BaseModel):
        """Rating for a specific criteria."""
        score: int = Field(ge=1, le=10, default=7, description="Score from 1-10")
        comments: str = Field(default="", description="Comments explaining the score")
        
        class Config:
            """Configuration for the model."""
            extra = "ignore"  # Ignore extra fields
    
    class Issue(BaseModel):
        """An issue identified in the scene."""
        type: str = Field(
            default="other",
            description="Type of issue (continuity_error, character_inconsistency, plot_hole, pacing_issue, tone_mismatch, language_mismatch, other)"
        )
        description: str = Field(default="", description="Description of the issue")
        severity: int = Field(ge=1, le=10, default=5, description="Severity from 1-10")
        recommendation: str = Field(default="", description="Recommendation to fix the issue")
        recommendation: str = Field(default="", description="Recommendation to fix the issue")
        
        def __init__(self, **data):
            """Initialize with dynamic severity based on issue type if not provided."""
            # If severity is not provided, calculate based on issue type
            if 'severity' not in data:
                issue_type = data.get('type', 'other').lower()
                # Assign higher default severity to critical issues
                if issue_type == 'language_mismatch':
                    data['severity'] = 10  # Highest severity for language mismatch
                elif issue_type in ['plot_hole', 'continuity_error', 'character_inconsistency']:
                    data['severity'] = 8
                elif issue_type in ['pacing_issue', 'tone_mismatch']:
                    data['severity'] = 6
                else:
                    data['severity'] = 5
            
            # Ensure description is not empty and is specific
            if 'description' not in data or not data['description'] or data['description'].strip() == "":
                issue_type = data.get('type', 'other')
                # Provide more specific default descriptions based on issue type
                if issue_type == 'language_mismatch':
                    data['description'] = "The scene is not written in the specified language"
                elif issue_type == 'plot_hole':
                    data['description'] = "A logical inconsistency or contradiction in the plot that needs to be resolved"
                elif issue_type == 'continuity_error':
                    data['description'] = "An inconsistency with previously established facts or events"
                elif issue_type == 'character_inconsistency':
                    data['description'] = "Character behavior that contradicts their established traits or motivations"
                elif issue_type == 'pacing_issue':
                    data['description'] = "Problems with the scene's rhythm, speed, or flow that affect reader engagement"
                elif issue_type == 'tone_mismatch':
                    data['description'] = "Elements that don't match the established tone or style of the story"
                else:
                    data['description'] = f"An issue with the scene that needs attention"
                
                # Flag this as a generic description
                data['is_generic_description'] = True
            else:
                data['is_generic_description'] = False
                
            # Ensure recommendation is not empty and is specific
            if 'recommendation' not in data or not data['recommendation'] or data['recommendation'].strip() == "":
                issue_type = data.get('type', 'other')
                # Provide more specific default recommendations based on issue type
                if issue_type == 'language_mismatch':
                    data['recommendation'] = "Rewrite the entire scene in the specified language"
                elif issue_type == 'plot_hole':
                    data['recommendation'] = "Revise the scene to ensure logical consistency with the established plot"
                elif issue_type == 'continuity_error':
                    data['recommendation'] = "Align this scene with previously established facts and events"
                elif issue_type == 'character_inconsistency':
                    data['recommendation'] = "Adjust character actions and dialogue to match their established traits"
                elif issue_type == 'pacing_issue':
                    data['recommendation'] = "Adjust the scene's rhythm by adding or removing content as needed"
                elif issue_type == 'tone_mismatch':
                    data['recommendation'] = "Revise elements that don't match the story's established tone"
                else:
                    data['recommendation'] = "Review the scene carefully and make appropriate adjustments"
                
            super().__init__(**data)
        
        class Config:
            """Configuration for the model."""
            extra = "ignore"  # Ignore extra fields
    
    class SceneReflection(BaseModel):
        """Reflection on a scenes quality and issues."""
        criteria_ratings: Union[Dict[str, CriteriaRating], str, Dict[str, Dict[str, Any]]] = Field(
            default_factory=dict,
            description="Ratings for different criteria (e.g., character_consistency, plot_advancement, etc.)"
        )
        issues: List[Issue] = Field(
            default_factory=list,
            description="List of issues identified in the scene"
        )
        strengths: List[str] = Field(
            default_factory=list,
            description="List of strengths in the scene"
        )
        needs_revision: bool = Field(
            default=False,
            description="Whether the scene needs revision"
        )
        revision_priority: str = Field(
            default="low",
            description="Priority of revision (low, medium, high)"
        )
        overall_assessment: str = Field(
            default="Scene appears functional but needs further analysis.",
            description="Overall assessment of the scene"
        )
        
        @field_validator('criteria_ratings')
        @classmethod
        def parse_criteria_ratings(cls, v):
            """Parse criteria ratings from various formats."""
            # If it's already a dictionary, return it
            if isinstance(v, dict):
                return v
                
            # If it's a string, try to parse it
            if isinstance(v, str):
                try:
                    # Create a default dictionary
                    ratings = {}
                    
                    # Split by newlines or commas
                    lines = v.replace(',', '\n').split('\n')
                    
                    for line in lines:
                        line = line.strip()
                        if not line or ':' not in line:
                            continue
                            
                        # Split by colon
                        parts = line.split(':', 1)
                        if len(parts) != 2:
                            continue
                            
                        criteria = parts[0].strip()
                        value = parts[1].strip()
                        
                        # Try to extract score and comments
                        score = 7  # Default score
                        comments = value
                        
                        # If value starts with a number, use it as score
                        if value and value[0].isdigit():
                            score_str = value.split()[0]
                            try:
                                score = int(score_str)
                                comments = value[len(score_str):].strip()
                            except ValueError:
                                pass
                        
                        ratings[criteria] = {
                            "score": score,
                            "comments": comments
                        }
                    
                    return ratings
                except Exception as e:
                    print(f"Error parsing criteria_ratings string: {e}")
                    return {}
            
            # Default empty dictionary
            return {}
        
        class Config:
            """Configuration for the model."""
            extra = "ignore"  # Ignore extra fields
    
    # Create default reflection data as fallback
    default_reflection = {
        "criteria_ratings": {
            "character_consistency": {"score": 7, "comments": "Appears consistent but needs verification"},
            "plot_advancement": {"score": 7, "comments": "Advances the plot appropriately"},
            "writing_quality": {"score": 7, "comments": "Acceptable quality"},
            "tone_appropriateness": {"score": 7, "comments": "Tone seems appropriate"},
            "information_management": {"score": 7, "comments": "Information is managed well"},
            "continuity": {"score": 7, "comments": "No obvious continuity issues"}
        },
        "issues": [],
        "strengths": ["The scene appears to be functional"],
        "needs_revision": False,
        "revision_priority": "low",
        "overall_assessment": "Scene appears functional but needs further analysis."
    }
    
    # Create a structured LLM that outputs a SceneReflection object
    structured_llm = llm.with_structured_output(SceneReflection)
    
    # Generate the reflection using the structured LLM
    try:
        # Use the structured LLM to get the reflection
        reflection = structured_llm.invoke(prompt)
        
        # Convert Pydantic model to dictionary
        reflection_dict = reflection.dict()
        
        # Additional logic to ensure needs_revision is set correctly based on criteria and issues
        # Check for low scores in criteria ratings
        low_criteria_scores = []
        for criteria_name, rating in reflection_dict.get("criteria_ratings", {}).items():
            score = rating.get("score", 10)  # Default high if not specified
            if score <= 5:  # Score of 5 or lower indicates a problem
                low_criteria_scores.append(f"{criteria_name}: {score}/10")
        
        # Check for issues with high severity
        severe_issues = []
        for issue in reflection_dict.get("issues", []):
            severity = issue.get("severity", 0)
            if severity >= 5:  # Severity of 5 or higher indicates a serious issue
                issue_type = issue.get("type", "unknown")
                severe_issues.append(f"{issue_type} (severity: {severity}/10)")
        
        # Set needs_revision to true if any low scores or severe issues exist
        if low_criteria_scores or severe_issues:
            if not reflection_dict.get("needs_revision"):
                print(f"Overriding needs_revision to TRUE for Ch:{current_chapter}/Sc:{current_scene} due to:")
                if low_criteria_scores:
                    print(f"  - Low criteria scores: {', '.join(low_criteria_scores)}")
                if severe_issues:
                    print(f"  - Severe issues: {', '.join(severe_issues)}")
                reflection_dict["needs_revision"] = True
                
                # Set appropriate revision priority based on severity
                if any(score <= 3 for criteria_name, rating in reflection_dict.get("criteria_ratings", {}).items()
                       if rating.get("score", 10) <= 3):
                    reflection_dict["revision_priority"] = "high"
                else:
                    reflection_dict["revision_priority"] = "medium"
        
        # Log success
        print(f"Successfully generated reflection for Ch:{current_chapter}/Sc:{current_scene}")
    except Exception as e:
        print(f"Error generating reflection for Ch:{current_chapter}/Sc:{current_scene}: {e}")
        print(f"Using default reflection data")
        reflection_dict = default_reflection
    
    # Extract new revelations directly from the scene content
    revelation_prompt = (
        f"Based on this scene:\n\n"
        f"{scene_content}\n\n"
        f"Extract a list of any new information revealed to the reader that wasn't known before.\n"
        f"Each item should be a specific fact or revelation that's now known to the reader.\n"
        f"Format as a simple bulleted list."
    )
    
    # Get new revelations
    new_revelations_text = llm.invoke([HumanMessage(content=revelation_prompt)]).content
    
    # Convert to list (simplified)
    new_revelations = [line.strip().replace("- ", "") for line in new_revelations_text.split("\n") if line.strip().startswith("- ")]
    
    # Update revelations in state
    updated_revelations = state["revelations"].copy()
    updated_revelations["reader"] = updated_revelations.get("reader", []) + new_revelations
    # Create a summary of the reflection for display
    reflection_summary = reflection_dict.get("overall_assessment", "No summary available")
    
    # Print debug information about the issues
    print(f"\nDEBUG BEFORE STORAGE: Found {len(reflection_dict.get('issues', []))} issues in reflection_dict")
    for i, issue in enumerate(reflection_dict.get('issues', [])):
        print(f"DEBUG BEFORE STORAGE: Issue {i+1} - Type: {issue.get('type', 'unknown')}, Severity: {issue.get('severity', 'N/A')}")
        print(f"DEBUG BEFORE STORAGE: Description: '{issue.get('description', '')}'")
    
    # Create a list of issues for quick reference
    issues_summary = []
    
    # If we have issues in reflection_dict, use them to create the summary
    if reflection_dict.get("issues", []):
        for issue in reflection_dict.get("issues", []):
            issue_type = issue.get("type", "unknown")
            description = issue.get("description", "No description")
            severity = issue.get("severity", 0)
            issues_summary.append(f"{issue_type.upper()} (Severity: {severity}/10): {description}")
    else:
        # Check if we can extract issues from the overall assessment
        overall_assessment = reflection_dict.get("overall_assessment", "")
        if "issue" in overall_assessment.lower() or "problem" in overall_assessment.lower() or "concern" in overall_assessment.lower():
            print("WARNING: Issues mentioned in overall assessment but not in structured data. Attempting to extract...")
            # Use a simple approach to extract issues from the overall assessment
            sentences = overall_assessment.split(". ")
            for sentence in sentences:
                if "issue" in sentence.lower() or "problem" in sentence.lower() or "concern" in sentence.lower():
                    issues_summary.append(f"EXTRACTED (Severity: 5/10): {sentence.strip()}")
            
            # Reconstruct issues from the extracted sentences
            if issues_summary:
                print(f"Extracted {len(issues_summary)} potential issues from overall assessment")
                reconstructed_issues = []
                for summary in issues_summary:
                    if "Severity:" in summary:
                        parts = summary.split("(Severity:", 1)
                        issue_type = parts[0].strip()
                        rest = parts[1].split(")", 1)
                        try:
                            severity = int(rest[0].strip().split("/")[0])
                        except:
                            severity = 5
                        description = rest[1].strip(": ") if len(rest) > 1 else "Unspecified issue"
                        
                        reconstructed_issues.append({
                            "type": issue_type.lower(),
                            "description": description,
                            "severity": severity,
                            "recommendation": "Review and address this issue"
                        })
                
                if reconstructed_issues:
                    print(f"Reconstructed {len(reconstructed_issues)} issues from assessment")
                    reflection_dict["issues"] = reconstructed_issues
                    # Also set needs_revision to True since we found issues
                    reflection_dict["needs_revision"] = True
                    reflection_dict["revision_priority"] = "medium"
    
    # If no issues were found after all attempts, note that
    if not issues_summary:
        issues_summary.append("No significant issues detected")
    
    # Format for storage - now we store the entire structured reflection directly
    # since we're using proper structured output
    reflection_formatted = {
        "criteria_ratings": reflection_dict.get("criteria_ratings", {}),
        "issues": reflection_dict.get("issues", []),
        "strengths": reflection_dict.get("strengths", []),
        "formatted_issues": issues_summary,  # For easy display
        "needs_revision": reflection_dict.get("needs_revision", False) or bool(reflection_dict.get("issues", [])),  # Set needs_revision to True if there are issues
        "revision_priority": reflection_dict.get("revision_priority", "low"),
        "overall_assessment": reflection_summary,
        "scene_closure": {
            "status": closure_analysis["closure_status"],
            "score": closure_analysis["closure_score"],
            "issues": closure_analysis["issues"],
            "improved": needs_improved_closure
        }
    }
    
    # Store the structured reflection in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"reflection_chapter_{current_chapter}_scene_{current_scene}",
        "value": reflection_formatted
    })
    
    # Store original reflection text for reference if it exists
    if "original_text" in reflection_dict:
        manage_memory_tool.invoke({
            "action": "create",
            "key": f"reflection_text_chapter_{current_chapter}_scene_{current_scene}",
            "value": reflection_dict["original_text"]
        })
    
    # Print the scene analysis in a structured format
    print(f"\n------ SCENE ANALYSIS [Ch:{current_chapter}/Sc:{current_scene}] ------")
    print(f"Analysis of scene {current_scene} in chapter {current_chapter}:")
    print(f"1. {reflection_summary}")
    
    # Print issues with proper formatting
    if issues_summary:
        print("2. " + issues_summary[0])
        for i in range(1, len(issues_summary)):
            print(issues_summary[i])
    else:
        print("2. No significant issues detected")
    
    print("-----------------------------\n")
    
    # Create readable reflection notes for the chapter data structure
    reflection_notes = [
        reflection_summary,
        "\n".join(issues_summary)
    ]
    
    # With our reducers, we can now be more declarative and specific about updates
    # Instead of copying the entire chapters dictionary, we just specify the updates
    
    # Update state with structured reflection data
    # Get initial idea from state
    initial_idea = state.get("initial_idea", "")
    
    # Apply post-generation improvements (pacing and dialogue)
    from storyteller_lib.integration import post_scene_improvements, update_concept_introduction_statuses
    
    # Apply pacing and dialogue improvements
    improvement_updates = post_scene_improvements(state)
    
    # Update concept introduction statuses
    concept_updates = update_concept_introduction_statuses(state)
    
    # Merge the plot thread updates with our reflection updates
    updates = {
        # Update the reflection notes and add structured reflection data for this specific scene
        "chapters": {
            current_chapter: {
                "scenes": {
                    current_scene: {
                        "reflection_notes": reflection_notes,
                        "structured_reflection": reflection_formatted
                    }
                }
            }
        },
        "revelations": {
            "reader": new_revelations  # The reducer will combine this with existing revelations
        },
        
        # Add memory usage tracking
        "memory_usage": {
            f"reflect_scene_{current_chapter}_{current_scene}": {
                "timestamp": "now",
                "scene_size": len(scene_content) if scene_content else 0,
                "reflection_size": len(str(reflection_formatted)) if reflection_formatted else 0
            }
        },
        
        "messages": [
            *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
            AIMessage(content=f"I've analyzed scene {current_scene} of chapter {current_chapter} for quality and consistency, tracked plot threads, " +
                     (f"improved scene closure to address abrupt ending (closure score: {closure_analysis['closure_score']}/10), "
                      if needs_improved_closure else
                      f"verified proper scene closure (closure score: {closure_analysis['closure_score']}/10), ") +
                     f"and optimized pacing and dialogue.")
        ]
    }
    
    # Add improvement updates if available
    if improvement_updates.get("pacing_optimized", False) or improvement_updates.get("dialogue_improved", False):
        # If scene content was improved, update it
        if "chapters" in improvement_updates and current_chapter in improvement_updates["chapters"]:
            if "scenes" in improvement_updates["chapters"][current_chapter]:
                if current_scene in improvement_updates["chapters"][current_chapter]["scenes"]:
                    scene_updates = improvement_updates["chapters"][current_chapter]["scenes"][current_scene]
                    
                    # Update content if available
                    if "content" in scene_updates:
                        updates["chapters"][current_chapter]["scenes"][current_scene]["content"] = scene_updates["content"]
                    
                    # Add analysis results
                    if "pacing_analysis" in scene_updates:
                        updates["chapters"][current_chapter]["scenes"][current_scene]["pacing_analysis"] = scene_updates["pacing_analysis"]
                    
                    if "dialogue_analysis" in scene_updates:
                        updates["chapters"][current_chapter]["scenes"][current_scene]["dialogue_analysis"] = scene_updates["dialogue_analysis"]
    
    # Add concept introduction updates if available
    if concept_updates and "concept_introductions" in concept_updates:
        updates["concept_introductions"] = concept_updates["concept_introductions"]
    
    # Add improvement flags
    updates["pacing_optimized"] = improvement_updates.get("pacing_optimized", False)
    updates["dialogue_improved"] = improvement_updates.get("dialogue_improved", False)
    
    # If we have plot thread updates, include them in our state updates
    if plot_thread_updates:
        # Update the plot_threads in state
        if "plot_threads" in plot_thread_updates:
            updates["plot_threads"] = plot_thread_updates["plot_threads"]
        
        # Update the scene's plot_threads if they exist
        if "chapters" in plot_thread_updates and current_chapter in plot_thread_updates["chapters"]:
            if "scenes" in plot_thread_updates["chapters"][current_chapter]:
                if current_scene in plot_thread_updates["chapters"][current_chapter]["scenes"]:
                    scene_updates = plot_thread_updates["chapters"][current_chapter]["scenes"][current_scene]
                    if "plot_threads" in scene_updates:
                        updates["chapters"][current_chapter]["scenes"][current_scene]["plot_threads"] = scene_updates["plot_threads"]
    
    return updates

@track_progress
def revise_scene_if_needed(state: StoryState) -> Dict:
    """Determine if the scene needs revision based on structured reflection data."""
    chapters = state["chapters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    characters = state["characters"]
    global_story = state["global_story"]
    revelations = state["revelations"]
    
    # Get the scene content
    scene_content = chapters[current_chapter]["scenes"][current_scene]["content"]
    
    # Get structured reflection data
    structured_reflection = chapters[current_chapter]["scenes"][current_scene].get("structured_reflection", {})
    
    # Check revision count to prevent infinite loops
    revision_count = state.get("revision_count", {}).get(f"{current_chapter}_{current_scene}", 0)
    
    # Default to not needing revision if we've revised three times already
    if revision_count >= 3:
        print(f"Scene {current_scene} of Chapter {current_chapter} has been revised {revision_count} times. No further revisions will be made.")
        needs_revision = False
        return {
            "current_chapter": current_chapter,
            "current_scene": current_scene,
            
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content=f"Scene {current_scene} of Chapter {current_chapter} has already been revised {revision_count} times (maximum of 3 revisions allowed). No further revisions will be made.")
            ]
        }
    
    # Use the structured data's explicit needs_revision flag
    needs_revision = structured_reflection.get("needs_revision", False)
    revision_priority = structured_reflection.get("revision_priority", "low")
    issues = structured_reflection.get("issues", [])
    
    # Automatically set needs_revision to True if issues are found
    # Print detailed debug information about the issues
    print(f"\nDEBUG: Found {len(issues)} issues in structured_reflection")
    for i, issue in enumerate(issues):
        print(f"DEBUG: Issue {i+1} - Type: {issue.get('type', 'unknown')}, Severity: {issue.get('severity', 'N/A')}")
        print(f"DEBUG: Description: '{issue.get('description', '')}'")
    
    # Check if issues exist and have meaningful content
    valid_issues = [issue for issue in issues
                   if issue.get('description') and len(issue.get('description', '').strip()) > 0]
    
    print(f"DEBUG: Found {len(valid_issues)} valid issues with descriptions")
    
    if valid_issues and not needs_revision:
        needs_revision = True
        revision_priority = "medium"  # Default to medium priority
        print("Auto-setting needs_revision to True because valid issues were found")
    elif issues and not valid_issues and not needs_revision:
        # Issues exist but have empty descriptions
        needs_revision = True
        revision_priority = "medium"
        print("Auto-setting needs_revision to True because issues were found (even with empty descriptions)")
    
    # Log detailed revision decision with more diagnostic information
    print(f"\n==== REVISION DECISION FOR Ch:{current_chapter}/Sc:{current_scene} ====")
    print(f"needs_revision flag: {needs_revision}")
    print(f"revision_priority: {revision_priority}")
    
    # Print criteria ratings if available
    if structured_reflection.get("criteria_ratings"):
        print("Criteria ratings:")
        for criteria, rating in structured_reflection.get("criteria_ratings", {}).items():
            score = rating.get("score", "N/A")
            print(f"  - {criteria}: {score}/10")
    
    # Print issues if available
    if issues:
        print("Issues found:")
        for idx, issue in enumerate(issues):
            issue_type = issue.get("type", "unknown")
            severity = issue.get("severity", "N/A")
            description = issue.get("description", "No description")
            recommendation = issue.get("recommendation", "No recommendation")
            # Check if description is empty or just whitespace
            if not description or description.strip() == "":
                description = "[EMPTY DESCRIPTION]"
            
            # Check if this is a generic description
            is_generic = issue.get("is_generic_description", False)
            if is_generic:
                print(f"  {idx+1}. {issue_type.upper()} (Severity: {severity}/10): {description[:100]}... [GENERIC DESCRIPTION - LLM FAILED TO PROVIDE SPECIFICS]")
                print(f"     Recommendation: {recommendation[:100]}... [GENERIC RECOMMENDATION]")
            else:
                print(f"  {idx+1}. {issue_type.upper()} (Severity: {severity}/10): {description[:100]}...")
                print(f"     Recommendation: {recommendation[:100]}...")
            print(f"     Recommendation: {recommendation[:100]}...")
    
    # Print the final decision
    if needs_revision:
        print(f"✅ DECISION: Revision needed - Priority: {revision_priority}")
    else:
        print(f"✓ DECISION: No revision needed")
    print(f"====================================================\n")
        
    # Track the revision count in state
    revised_counts = state.get("revision_count", {}).copy()
    if f"{current_chapter}_{current_scene}" not in revised_counts:
        revised_counts[f"{current_chapter}_{current_scene}"] = 0
    
    if needs_revision:
        # Create a detailed prompt for scene revision using structured data
        
        # Format issues as bullet points
        formatted_issues = []
        for issue in structured_reflection.get("issues", []):
            issue_type = issue.get("type", "unknown")
            description = issue.get("description", "")
            recommendation = issue.get("recommendation", "")
            formatted_issues.append(f"- {issue_type.upper()}: {description}\n  Suggestion: {recommendation}")
        
        # Format criteria ratings with comments
        formatted_ratings = []
        for criteria, rating in structured_reflection.get("criteria_ratings", {}).items():
            score = rating.get("score", 0)
            comments = rating.get("comments", "")
            formatted_ratings.append(f"- {criteria.replace('_', ' ').title()}: {score}/10\n  {comments}")
        
        # Combine all feedback
        all_issues = "\n".join(formatted_issues)
        all_ratings = "\n".join(formatted_ratings)
        overall_assessment = structured_reflection.get("overall_assessment", "")
        
        # Get language from state
        language = state.get("language", DEFAULT_LANGUAGE)
        
        # Prepare language guidance
        language_section = ""
        if language.lower() != DEFAULT_LANGUAGE:
            language_section = f"""
            LANGUAGE REQUIREMENTS:
            This scene MUST be written entirely in {SUPPORTED_LANGUAGES[language.lower()]}.
            Do not include any text in English or any other language.
            The complete scene must be written only in {SUPPORTED_LANGUAGES[language.lower()]}.
            """
        # Get active plot threads for this scene
        active_plot_threads = get_active_plot_threads_for_scene(state)
        
        # Create plot thread guidance
        plot_thread_guidance = ""
        if active_plot_threads:
            plot_thread_sections = []
            
            # Group threads by importance
            major_threads = [t for t in active_plot_threads if t["importance"] == "major"]
            minor_threads = [t for t in active_plot_threads if t["importance"] == "minor"]
            background_threads = [t for t in active_plot_threads if t["importance"] == "background"]
            
            # Format major threads
            if major_threads:
                major_section = "MAJOR PLOT THREADS (must be addressed):\n"
                for thread in major_threads:
                    major_section += f"- {thread['name']}: {thread['description']}\n  Status: {thread['status']}\n  Last development: {thread['last_development']}\n"
                plot_thread_sections.append(major_section)
            
            # Format minor threads
            if minor_threads:
                minor_section = "MINOR PLOT THREADS (should be addressed if relevant):\n"
                for thread in minor_threads:
                    minor_section += f"- {thread['name']}: {thread['description']}\n  Status: {thread['status']}\n"
                plot_thread_sections.append(minor_section)
            
            # Format background threads
            if background_threads:
                background_section = "BACKGROUND THREADS (can be referenced):\n"
                for thread in background_threads:
                    background_section += f"- {thread['name']}: {thread['description']}\n"
                plot_thread_sections.append(background_section)
            
            # Combine all sections
            joined_sections = "\n".join(plot_thread_sections)
            plot_thread_guidance = (
                f"ACTIVE PLOT THREADS:\n\n"
                f"{joined_sections}\n\n"
                f"Ensure that major plot threads are meaningfully advanced in this scene.\n"
                f"Minor threads should be addressed if they fit naturally with the scene's purpose.\n"
                f"Background threads can be referenced to maintain continuity."
            )
        # Generate a comprehensive summary of previous chapters and scenes
        previous_scenes_summary = _generate_previous_scenes_summary(state)
        
        # Prompt for scene revision
        prompt = f"""
        Revise this scene based on the following structured feedback:
        
        ORIGINAL SCENE:
        {scene_content}
        
        ISSUES REQUIRING ATTENTION:
        {all_issues}
        
        EVALUATION OF CURRENT SCENE:
        {all_ratings}
        
        OVERALL ASSESSMENT:
        {overall_assessment}
        
        STORY CONTEXT:
        {global_story[:300]}...
        
        CHARACTER INFORMATION:
        {characters}
        
        PREVIOUSLY REVEALED INFORMATION:
        {revelations.get('reader', [])}
        
        PREVIOUS CONTENT SUMMARY:
        {previous_scenes_summary}
        
        {plot_thread_guidance}
        {plot_thread_guidance}
        
        YOUR REVISION TASK:
        1. Rewrite the scene to address ALL identified issues, especially those marked with higher severity.
        2. Ensure consistency with previous events, character traits, and established facts.
        3. Maintain the same general plot progression and purpose of the scene.
        4. Improve the quality, style, and flow as needed.
        5. Ensure no NEW continuity errors are introduced.
        6. Properly address and advance all major plot threads, and incorporate minor threads where relevant.
        7. If a language mismatch was identified, ensure the ENTIRE scene is written in the specified language.
        
        {language_section}
        
        Provide a complete, polished scene that can replace the original.
        Provide a complete, polished scene that can replace the original.
        
        CRITICAL INSTRUCTION: Return ONLY the actual revised scene content. Do NOT include any explanations, comments, notes, or meta-information about your revision process or choices. Do NOT include any text like "Here's the revised scene" or "Key improvements" or any other commentary. The output should be ONLY the narrative text that will appear in the final story.
        """
        
        # Try to use structured output first, but fall back to regular output if it fails
        try:
            # Use the same Pydantic model for structured scene content
            # (SceneContent should already be defined in the write_scene function)
            from pydantic import BaseModel, Field
            
            # Define the model again here to avoid potential scope issues
            class SceneContent(BaseModel):
                """Model for structured scene content."""
                content: str = Field(
                    description="The actual scene content that will be included in the story. This should be the narrative text only, without any explanations, comments, or meta-information."
                )
            
            # Use LangChain's structured output capabilities
            structured_llm = llm.with_structured_output(SceneContent)
            
            # Generate the revised scene content with structured output
            structured_response = structured_llm.invoke(prompt)
            
            # Check if we got a valid response
            if structured_response and hasattr(structured_response, 'content'):
                revised_scene = structured_response.content
                print(f"Successfully used structured output for revised scene {current_chapter}_{current_scene}")
            else:
                # Fall back to regular output
                print(f"Structured output failed for revised scene {current_chapter}_{current_scene}, falling back to regular output")
                revised_scene = llm.invoke([HumanMessage(content=prompt)]).content
        except Exception as e:
            # Log the error and fall back to regular output
            print(f"Error using structured output for revised scene {current_chapter}_{current_scene}: {str(e)}")
            print("Falling back to regular output")
            revised_scene = llm.invoke([HumanMessage(content=prompt)]).content
        # Increment revision count
        revised_counts[f"{current_chapter}_{current_scene}"] = revision_count + 1
        # Log that an improved scene was generated based on the reflection
        print(f"\n==== IMPROVED SCENE GENERATED FOR Ch:{current_chapter}/Sc:{current_scene} ====")
        print(f"Based on the reflection analysis, an improved scene was generated (revision #{revision_count + 1})")
        print(f"Issues that were addressed in this revision:")
        for i, issue in enumerate(issues):
            issue_type = issue.get("type", "unknown")
            severity = issue.get("severity", "N/A")
            description = issue.get("description", "No description")
            if description:
                description = description[:100]
            print(f"  {i+1}. {issue_type.upper()} (Severity: {severity}/10): {description}... [ADDRESSED]")
            print(f"  {i+1}. {issue_type.upper()} (Severity: {severity}/10): {description}...")
        print(f"====================================================\n")
        # Store revision information in memory
        manage_memory_tool.invoke({
            "action": "create",
            "key": f"chapter_{current_chapter}_scene_{current_scene}_revision_reason",
            "value": {
                "structured_reflection": structured_reflection,
                "revision_number": revision_count + 1,
                "timestamp": "now",
                "plot_threads_addressed": [
                    {"name": thread["name"], "importance": thread["importance"], "status": thread["status"]}
                    for thread in active_plot_threads
                ] if active_plot_threads else []
            }
        })
        
        # Store revised scene in memory
        manage_memory_tool.invoke({
            "action": "create",
            "key": f"chapter_{current_chapter}_scene_{current_scene}_revised",
            "value": revised_scene
        })
        
        # Clear the structured reflection data to force a fresh analysis after revision
        # This ensures we don't keep the same analysis for the new content
        scene_update = {
            current_scene: {
                "content": revised_scene,
                "reflection_notes": [f"Scene has been revised (revision #{revision_count + 1})"],
                "structured_reflection": None,  # Clear structured reflection to trigger fresh analysis
                "issues_addressed": [
                    {
                        "type": issue.get("type", "unknown"),
                        "description": issue.get("description", "No description"),
                        "revision_number": revision_count + 1
                    }
                    for issue in issues
                ]
            }
        }
        
        # Check if this was the last scene in the chapter that needed revision
        # If so, the chapter is now complete and can be written to the output file
        chapter_complete = True
        for scene_num, scene_data in chapters[current_chapter]["scenes"].items():
            # Skip the current scene since we just revised it
            if scene_num == current_scene:
                continue
            # A scene is only complete if it has both content and reflection notes
            if not scene_data.get("content") or not scene_data.get("reflection_notes"):
                chapter_complete = False
                break
        
        # If this is the last scene in the chapter and it's now complete, mark the chapter as ready to write
        if chapter_complete:
            print(f"\n==== CHAPTER {current_chapter} COMPLETED ====")
            print(f"All scenes in Chapter {current_chapter} have been written and revised.")
            print(f"The chapter is now ready to be written to the output file.")
            print(f"=================================\n")
            
            # Store in memory that this chapter is complete
            manage_memory_tool.invoke({
                "action": "create",
                "key": f"chapter_{current_chapter}_complete",
                "value": True,
                "namespace": MEMORY_NAMESPACE
            })
        
        return {
            "chapters": {
                current_chapter: {
                    "scenes": scene_update
                }
            },
            "revision_count": {
                f"{current_chapter}_{current_scene}": revision_count + 1  # Only update this specific count
            },
            "current_chapter": current_chapter,
            "current_scene": current_scene,
            "chapter_complete": chapter_complete,  # Add this flag to indicate if the chapter is complete
            
            # Add memory tracking
            "memory_usage": {
                f"revise_scene_{current_chapter}_{current_scene}": {
                    "timestamp": "now",
                    "original_size": len(scene_content) if scene_content else 0,
                    "revised_size": len(revised_scene) if revised_scene else 0,
                    "revision_number": revision_count + 1,
                    "plot_threads_count": len(active_plot_threads) if active_plot_threads else 0,
                    "major_threads_count": len([t for t in active_plot_threads if t["importance"] == "major"]) if active_plot_threads else 0
                }
            },
            
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content=f"I've revised scene {current_scene} of chapter {current_chapter} to address the identified issues and plot threads (revision #{revision_count + 1}).")
            ]
        }

@track_progress
def process_showing_telling(state: StoryState) -> Dict:
    """
    Process the scene to enhance showing vs. telling balance.
    
    This node analyzes the current scene for instances of "telling" rather than "showing"
    and converts them to more sensory, experiential descriptions.
    
    Args:
        state: The current state
        
    Returns:
        Updates to the state
    """
    # Extract state variables
    chapters = state["chapters"]
    current_chapter = state["current_chapter"]
    current_scene = state["current_scene"]
    
    # Get the current scene content
    scene_content = chapters[current_chapter]["scenes"][current_scene]["content"]
    
    # Get showing vs. telling parameters
    showing_ratio = state.get("showing_ratio", 8)  # Default to 8/10 showing vs telling
    
    # Analyze showing vs. telling balance
    showing_telling_analysis = analyze_showing_vs_telling(scene_content)
    
    # Store analysis in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"showing_telling_analysis_ch{current_chapter}_sc{current_scene}",
        "value": showing_telling_analysis,
        "namespace": MEMORY_NAMESPACE
    })
    
    # Check if improvement is needed
    current_ratio = showing_telling_analysis.get("overall_showing_ratio", 0)
    improvement_needed = current_ratio < showing_ratio
    
    # If improvement is needed, process the scene
    if improvement_needed:
        # Get telling instances
        telling_instances = showing_telling_analysis.get("telling_instances", [])
        
        # Convert each telling instance to showing
        conversion_tracking = []
        improved_content = scene_content
        
        for instance in telling_instances:
            text = instance.get("text", "")
            if text and len(text) > 20:  # Only process substantial passages
                # Convert to sensory description
                sensory_version = convert_exposition_to_sensory(text)
                
                # Replace in the scene content if conversion was successful
                if sensory_version and sensory_version != text:
                    # Track the conversion
                    conversion_tracking.append({
                        "original": text,
                        "converted": sensory_version,
                        "issue": instance.get("issue", ""),
                        "improvement": instance.get("improvement_suggestion", "")
                    })
                    
                    # Replace in the scene content
                    improved_content = improved_content.replace(text, sensory_version)
        
        # Store conversion tracking in memory for analysis
        if conversion_tracking:
            manage_memory_tool.invoke({
                "action": "create",
                "key": f"showing_telling_conversions_ch{current_chapter}_sc{current_scene}",
                "value": conversion_tracking,
                "namespace": MEMORY_NAMESPACE
            })
            
            # Update the scene content
            return {
                "chapters": {
                    current_chapter: {
                        "scenes": {
                            current_scene: {
                                "content": improved_content,
                                "showing_telling_improved": True
                            }
                        }
                    }
                },
                
                "messages": [
                    *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                    AIMessage(content=f"I've improved the showing vs. telling balance in scene {current_scene} of chapter {current_chapter}, converting {len(conversion_tracking)} instances of telling to showing.")
                ]
            }
    
    # If no improvement needed or no conversions made
    return {
        "showing_telling_analysis": showing_telling_analysis,
        
        "messages": [
            *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
            AIMessage(content=f"Scene {current_scene} of chapter {current_chapter} already has a good showing vs. telling balance (ratio: {current_ratio}/10).")
        ]
    }