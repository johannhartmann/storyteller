"""
StoryCraft Agent - Initialization nodes.
"""

from typing import Dict

from storyteller_lib.config import llm, manage_memory_tool, search_memory_tool, MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState
from storyteller_lib.memory_manager import manage_memory, search_memory
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.messages.modifier import RemoveMessage
from storyteller_lib import track_progress

@track_progress
def initialize_state(state: StoryState) -> Dict:
    """Initialize the story state with user input."""
    messages = state["messages"]
    
    # Use the genre, tone, author, language, and initial idea values already passed in the state
    # If not provided, use defaults
    genre = state.get("genre") or "fantasy"
    tone = state.get("tone") or "epic"
    author = state.get("author") or ""
    initial_idea = state.get("initial_idea") or ""
    author_style_guidance = state.get("author_style_guidance", "")
    language = state.get("language") or DEFAULT_LANGUAGE
    
    # Validate language and default to English if not supported
    if language.lower() not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE
    
    # Get initial idea elements from state or extract them if needed
    idea_elements = state.get("initial_idea_elements", {})
    
    # If we have an initial idea but no elements, parse it
    if initial_idea and not idea_elements:
        # Import the parsing function from storyteller.py
        from storyteller_lib.storyteller import parse_initial_idea
        idea_elements = parse_initial_idea(initial_idea)
    
    # Ensure the idea elements are stored in memory for consistency checks
    if initial_idea:
        # Store the structured idea elements in memory for reference
        manage_memory(action="create", key="initial_idea_elements", value=idea_elements,
            namespace=MEMORY_NAMESPACE)
        
        # Also store the raw initial idea for reference
        manage_memory(action="create", key="initial_idea_raw", value=initial_idea,
            namespace=MEMORY_NAMESPACE)
        
        # Create a strong memory anchor for the initial idea to ensure it's preserved
        manage_memory_tool.invoke({
            "action": "create",
            "key": "initial_idea_anchor",
            "value": {
                "idea": initial_idea,
                "importance": "critical",
                "must_be_followed": True,
                "elements": idea_elements  # Include elements in the anchor
            },
            "namespace": MEMORY_NAMESPACE
        })
    
    # If author guidance wasn't provided in the initial state, but we have an author, get it now
    if author and not author_style_guidance:
        # See if we have cached guidance
        try:
            # Use search_memory_tool to retrieve the author style
            results = search_memory_tool.invoke({
                "query": f"author_style_{author.lower().replace(' ', '_')}"
            })
            
            # Extract the author style from the results
            author_style_object = None
            if results and len(results) > 0:
                for item in results:
                    if hasattr(item, 'key') and item.key == f"author_style_{author.lower().replace(' ', '_')}":
                        author_style_object = {"key": item.key, "value": item.value}
                        break
            
            if author_style_object and "value" in author_style_object:
                author_style_guidance = author_style_object["value"]
        except Exception:
            # If error, we'll generate it later
            pass
    
    # Prepare response message
    author_mention = f" in the style of {author}" if author else ""
    idea_mention = f" implementing the idea: '{initial_idea}'" if initial_idea else ""
    language_mention = f" in {SUPPORTED_LANGUAGES[language.lower()]}" if language.lower() != DEFAULT_LANGUAGE else ""
    response_message = f"I'll create a {tone} {genre} story{author_mention}{language_mention}{idea_mention} for you. Let me start planning the narrative..."
    
    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]
    
    # Initialize language-specific naming and cultural elements if not English
    if language.lower() != DEFAULT_LANGUAGE:
        language_elements_prompt = f"""
        Create a comprehensive guide for generating story elements in {SUPPORTED_LANGUAGES[language.lower()]} that will ensure consistency throughout the story.
        
        Provide the following:
        
        1. NAMING CONVENTIONS:
           - Common first names for male characters in {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures
           - Common first names for female characters in {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures
           - Common family/last names in {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures
           - Naming patterns or traditions (e.g., patronymics, compound names)
           
        2. PLACE NAMES:
           - Types of place names common in {SUPPORTED_LANGUAGES[language.lower()]}-speaking regions
           - Common prefixes/suffixes for cities, towns, villages
           - Geographical feature naming patterns (mountains, rivers, forests)
           
        3. CULTURAL REFERENCES:
           - Common idioms and expressions in {SUPPORTED_LANGUAGES[language.lower()]}
           - Cultural traditions and customs specific to {SUPPORTED_LANGUAGES[language.lower()]}-speaking regions
           - Historical references that would be familiar to {SUPPORTED_LANGUAGES[language.lower()]} speakers
           
        4. NARRATIVE ELEMENTS:
           - Storytelling traditions in {SUPPORTED_LANGUAGES[language.lower()]} literature
           - Common literary devices or techniques in {SUPPORTED_LANGUAGES[language.lower()]} writing
           - Dialogue patterns or speech conventions in {SUPPORTED_LANGUAGES[language.lower()]}
           
        Format your response as a structured JSON object with these categories as keys.
        """
        
        try:
            # Generate language-specific elements
            language_elements_response = llm.invoke([HumanMessage(content=language_elements_prompt)]).content
            
            # Parse the response into structured data
            from storyteller_lib.creative_tools import parse_json_with_langchain
            language_elements = parse_json_with_langchain(language_elements_response, "language elements")
            
            # Store language elements in memory for reference throughout story generation
            manage_memory_tool.invoke({
                "action": "create",
                "key": f"language_elements_{language.lower()}",
                "value": language_elements,
                "namespace": MEMORY_NAMESPACE
            })
            
            # Create a specific instruction to ensure language consistency
            language_consistency_instruction = f"""
            CRITICAL LANGUAGE CONSISTENCY INSTRUCTION:
            
            This story MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
            ALL content - including outlines, character descriptions, scene elements, reflections, and revisions - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
            DO NOT switch to any other language at ANY point in the story generation process.
            
            When writing in {SUPPORTED_LANGUAGES[language.lower()]}, ensure that:
            1. ALL text is in {SUPPORTED_LANGUAGES[language.lower()]} without ANY English phrases or words
            2. Character names must be authentic {SUPPORTED_LANGUAGES[language.lower()]} names
            3. Place names must follow {SUPPORTED_LANGUAGES[language.lower()]} naming conventions
            4. Cultural references must be appropriate for {SUPPORTED_LANGUAGES[language.lower()]}-speaking audiences
            5. Dialogue must use expressions and idioms natural to {SUPPORTED_LANGUAGES[language.lower()]}
            6. ALL planning, outlining, and internal notes are also in {SUPPORTED_LANGUAGES[language.lower()]}
            
            CRITICAL: Maintain {SUPPORTED_LANGUAGES[language.lower()]} throughout ALL parts of the story and ALL stages of the generation process without ANY exceptions.
            
            REMINDER: Even if you are analyzing, planning, or reflecting on the story, you MUST do so in {SUPPORTED_LANGUAGES[language.lower()]}.
            """
            
            manage_memory(action="create", key="language_consistency_instruction", value=language_consistency_instruction,
                namespace=MEMORY_NAMESPACE)
        except Exception as e:
            print(f"Error generating language elements: {str(e)}")
            # If there's an error, we'll proceed without the language elements
    
    # Initialize the state
    result_state = {
        "genre": genre,
        "tone": tone,
        "author": author,
        "initial_idea": initial_idea,
        "initial_idea_elements": idea_elements,  # Add structured idea elements
        "author_style_guidance": author_style_guidance,
        "language": language,
        "global_story": "",
        "chapters": {},
        "characters": {},
        "plot_threads": {},  # Initialize plot threads
        "revelations": {"reader": [], "characters": []},
        "current_chapter": "",
        "current_scene": "",
        "current_scene_content": "",
        "scene_reflection": {},
        "completed": False,
        "messages": [
            *[RemoveMessage(id=msg_id) for msg_id in message_ids],
            AIMessage(content=response_message)
        ]
    }
    
    return result_state

@track_progress
def brainstorm_story_concepts(state: StoryState) -> Dict:
    """Brainstorm creative story concepts before generating the outline."""
    from storyteller_lib.creative_tools import creative_brainstorm
    from storyteller_lib.story_progress_logger import log_progress
    
    # Try to recover from memory if initial_idea is not in state
    if "initial_idea" not in state:
        try:
            initial_idea_obj = memory_store.get("initial_idea_raw", MEMORY_NAMESPACE)
        except Exception:
            pass
    
    genre = state["genre"]
    tone = state["tone"]
    author = state["author"]
    # Get initial_idea from state, with memory as fallback
    initial_idea = state.get("initial_idea", "")
    if not initial_idea:
        try:
            # Use search_memory_tool to retrieve the initial idea
            results = search_memory(query="initial_idea_raw")
            
            # Extract the initial idea from the results
            initial_idea_obj = None
            if results and len(results) > 0:
                for item in results:
                    if hasattr(item, 'key') and item.key == "initial_idea_raw":
                        initial_idea_obj = {"key": item.key, "value": item.value}
                        break
            if initial_idea_obj and "value" in initial_idea_obj:
                initial_idea = initial_idea_obj["value"]
        except Exception:
            pass
    
    # Get initial_idea_elements from state, with memory as fallback
    initial_idea_elements = state.get("initial_idea_elements", {})
    
    # If we have an initial idea but no elements, try to get them from memory
    if not initial_idea_elements and initial_idea:
        try:
            elements_obj = search_memory(query="initial_idea_elements", namespace=MEMORY_NAMESPACE)
            if elements_obj and "value" in elements_obj:
                if "extracted_elements" in elements_obj["value"]:
                    initial_idea_elements = elements_obj["value"]["extracted_elements"]
                else:
                    initial_idea_elements = elements_obj["value"]
        except Exception:
            pass
            
    # If we still don't have elements but have an initial idea, parse it now
    if not initial_idea_elements and initial_idea:
        from storyteller_lib.storyteller import parse_initial_idea
        initial_idea_elements = parse_initial_idea(initial_idea)
    
    author_style_guidance = state["author_style_guidance"]
    language = state.get("language", DEFAULT_LANGUAGE)
    
    # Generate enhanced context based on genre, tone, language, and initial idea
    
    # Generate enhanced context based on genre, tone, language, and initial idea
    idea_context = ""
    if initial_idea:
        # Create a more detailed context using the structured idea elements
        setting = initial_idea_elements.get("setting", "Unknown")
        characters = initial_idea_elements.get("characters", [])
        plot = initial_idea_elements.get("plot", "Unknown")
        themes = initial_idea_elements.get("themes", [])
        genre_elements = initial_idea_elements.get("genre_elements", [])
        
        # Build a rich context that emphasizes the initial idea
        idea_context = f"""
        IMPORTANT: The story MUST be based on this initial idea: '{initial_idea}'
        
        Key elements that MUST be incorporated:
        - Setting: {setting}
        - Main Characters: {', '.join(characters) if characters else 'To be determined based on the initial idea'}
        - Central Plot: {plot}
        - Themes: {', '.join(themes) if themes else 'To be determined based on the initial idea'}
        - Genre Elements: {', '.join(genre_elements) if genre_elements else 'To be determined based on the initial idea'}
        
        These elements are non-negotiable and must form the foundation of the story.
        """
        
        # Store the elements in memory again to ensure consistency
        manage_memory_tool.invoke({
            "action": "create",
            "key": "brainstorm_context_elements",
            "value": {
                "initial_idea": initial_idea,
                "setting": setting,
                "characters": characters,
                "plot": plot,
                "themes": themes,
                "genre_elements": genre_elements
            },
            "namespace": MEMORY_NAMESPACE
        })
    else:
        print(f"[STORYTELLER] WARNING: No idea_context created - story will be generated without specific initial idea guidance")
        print(f"[STORYTELLER] Story will only use genre '{genre}' and tone '{tone}' as guidance, which may result in generic output")
    
    language_context = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_context = f"\nThe story should be written in {SUPPORTED_LANGUAGES[language.lower()]} with character names, places, and cultural references appropriate for {SUPPORTED_LANGUAGES[language.lower()]}-speaking audiences."
    
    context = f"""
    We're creating a {tone} {genre} story that follows the hero's journey structure.
    The story should be engaging, surprising, and emotionally resonant with readers.
    {idea_context}
    {language_context}
    """
    
    # Create custom evaluation criteria that emphasize adherence to the initial idea
    
    # Create custom evaluation criteria that emphasize adherence to the initial idea
    custom_evaluation_criteria = [
        "Adherence to the initial idea and its key elements (setting, characters, plot)",
        "Preservation of the essential nature of specified characters and their roles",
        "Maintenance of the specified setting as the primary location",
        "Development of the central conflict as described in the initial idea",
        "Originality and surprise factor while respecting the initial concept",
        "Coherence with the established narrative requirements",
        "Reader engagement and emotional impact",
        "Feasibility within the specified story world"
    ]
    
    # Create constraints dictionary from initial idea elements
    constraints = {}
    
    if initial_idea_elements:
        constraints = {
            "setting": initial_idea_elements.get("setting", ""),
            "characters": ", ".join(initial_idea_elements.get("characters", [])),
            "plot": initial_idea_elements.get("plot", "")
        }
        
        # Create memory anchors for key elements to ensure persistence throughout generation
        for key, value in constraints.items():
            if value:
                manage_memory_tool.invoke({
                    "action": "create",
                    "key": f"constraint_{key}",
                    "value": value,
                    "namespace": MEMORY_NAMESPACE
                })
        
        # Create a genre validation memory anchor
        manage_memory_tool.invoke({
            "action": "create",
            "key": "genre_requirement",
            "value": {
                "genre": genre,
                "tone": tone,
                "required_elements": f"This story must adhere to {genre} genre conventions with a {tone} tone"
            },
            "namespace": MEMORY_NAMESPACE
        })
        
        # Create a strong initial idea constraint
        must_include = [
            f"Setting: {initial_idea_elements.get('setting', '')}",
            f"Characters: {', '.join(initial_idea_elements.get('characters', []))}",
            f"Plot: {initial_idea_elements.get('plot', '')}"
        ]
        
        manage_memory_tool.invoke({
            "action": "create",
            "key": "initial_idea_constraint",
            "value": {
                "original_idea": initial_idea,
                "must_include": must_include,
                "importance": "These elements are the foundation of the story and must be preserved throughout generation."
            },
            "namespace": MEMORY_NAMESPACE
        })
        
        # Add a direct instruction to ensure the initial idea is followed
        manage_memory_tool.invoke({
            "action": "create",
            "key": "story_directive",
            "value": f"This story must be based on the initial idea: '{initial_idea}'. The key elements (setting, characters, plot) must be preserved.",
            "namespace": MEMORY_NAMESPACE
        })
    
    # Brainstorm different high-level story concepts
    brainstorm_results = creative_brainstorm(
        topic="Story Concept",
        genre=genre,
        tone=tone,
        context=context,
        author=author,
        author_style_guidance=author_style_guidance,
        language=language,
        num_ideas=5,
        evaluation_criteria=custom_evaluation_criteria,
        constraints=constraints,
        strict_adherence=True
    )
    
    # Brainstorm unique world-building elements
    world_building_results = creative_brainstorm(
        topic="World Building Elements",
        genre=genre,
        tone=tone,
        context=context,
        author=author,
        author_style_guidance=author_style_guidance,
        language=language,
        num_ideas=4,
        evaluation_criteria=custom_evaluation_criteria,
        constraints=constraints,
        strict_adherence=True
    )
    
    # Brainstorm central conflicts
    conflict_results = creative_brainstorm(
        topic="Central Conflict",
        genre=genre,
        tone=tone,
        context=context,
        author=author,
        author_style_guidance=author_style_guidance,
        language=language,
        num_ideas=3,
        evaluation_criteria=custom_evaluation_criteria,
        constraints=constraints,
        strict_adherence=True
    )
    
    # Validate that the brainstormed ideas adhere to the initial idea
    if initial_idea:
        validation_prompt = f"""
            Evaluate whether these brainstormed ideas properly incorporate the initial story idea:
            
            Initial Idea: "{initial_idea}"
            
            Story Concepts:
            {brainstorm_results.get("recommended_ideas", "No recommendations available")}
            
            World Building Elements:
            {world_building_results.get("recommended_ideas", "No recommendations available")}
            
            Central Conflicts:
            {conflict_results.get("recommended_ideas", "No recommendations available")}
            
            For each category, provide:
            1. A score from 1-10 on how well it adheres to the initial idea
            2. Specific feedback on what elements are missing or need adjustment
            3. A YES/NO determination if the ideas are acceptable
            
            If any category scores below 7 or receives a NO, provide specific guidance on how to improve it.
            """
            
        validation_result = llm.invoke([HumanMessage(content=validation_prompt)]).content
        
        # Store the validation result in memory
        manage_memory(action="create", key="brainstorm_validation", value=validation_result,
            namespace=MEMORY_NAMESPACE)
    
    # Store all creative elements
    creative_elements = {
        "story_concepts": brainstorm_results,
        "world_building": world_building_results,
        "central_conflicts": conflict_results
    }
    
    # Store the initial idea elements with the creative elements for easy reference
    if initial_idea_elements:
        creative_elements["initial_idea_elements"] = initial_idea_elements
    
    # Create messages to add and remove
    idea_mention = f" based on your idea" if initial_idea else ""
    
    new_msg = AIMessage(content=f"I've brainstormed several creative concepts for your {tone} {genre} story{idea_mention}. Now I'll develop a cohesive outline based on the most promising ideas.")
    
    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]
    
    # Log creative concepts
    log_progress("creative_concepts", concepts={
        "story_concept": brainstorm_results.get("recommended_ideas", ""),
        "worldbuilding_ideas": world_building_results.get("recommended_ideas", ""),
        "central_conflict": conflict_results.get("recommended_ideas", "")
    })
    
    # Update state with brainstormed ideas
    return {
        "creative_elements": creative_elements,
        "messages": [
            *[RemoveMessage(id=msg_id) for msg_id in message_ids],
            new_msg
        ]
    }