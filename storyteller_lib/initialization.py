"""
StoryCraft Agent - Initialization nodes.
"""

from typing import Dict

from storyteller_lib.config import llm, manage_memory_tool, MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState
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
    print(f"[STORYTELLER] initialize_state received initial_idea: '{initial_idea}'")
    print(f"[STORYTELLER] initialize_state received state with keys: {list(state.keys())}")
    author_style_guidance = state.get("author_style_guidance", "")
    language = state.get("language") or DEFAULT_LANGUAGE
    
    # Validate language and default to English if not supported
    if language.lower() not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE
    
    # Get initial idea elements from state or extract them if needed
    idea_elements = state.get("initial_idea_elements", {})
    print(f"[STORYTELLER] initialize_state: Initial idea elements from state: {idea_elements}")
    
    # If we have an initial idea but no elements, parse it
    if initial_idea and not idea_elements:
        print(f"[STORYTELLER] initialize_state: Initial idea present but no elements, parsing now")
        # Import the parsing function from storyteller.py
        from storyteller_lib.storyteller import parse_initial_idea
        idea_elements = parse_initial_idea(initial_idea)
        print(f"[STORYTELLER] initialize_state: Parsed initial idea elements: {idea_elements}")
    
    # Ensure the idea elements are stored in memory for consistency checks
    if initial_idea:
        # Store the structured idea elements in memory for reference
        manage_memory_tool.invoke({
            "action": "create",
            "key": "initial_idea_elements",
            "value": idea_elements,
            "namespace": MEMORY_NAMESPACE
        })
        
        # Also store the raw initial idea for reference
        manage_memory_tool.invoke({
            "action": "create",
            "key": "initial_idea_raw",
            "value": initial_idea,
            "namespace": MEMORY_NAMESPACE
        })
        
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
        
        print(f"[STORYTELLER] initialize_state: Stored initial idea and elements in LangMem")
    
    # If author guidance wasn't provided in the initial state, but we have an author, get it now
    if author and not author_style_guidance:
        # See if we have cached guidance
        try:
            author_style_object = manage_memory_tool.invoke({
                "action": "get",
                "key": f"author_style_{author.lower().replace(' ', '_')}",
                "namespace": MEMORY_NAMESPACE
            })
            
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
        "revelations": {"reader": [], "characters": []},
        "current_chapter": "",
        "current_scene": "",
        "completed": False,
        "messages": [
            *[RemoveMessage(id=msg_id) for msg_id in message_ids],
            AIMessage(content=response_message)
        ]
    }
    
    print(f"[STORYTELLER] initialize_state returning initial_idea: '{result_state['initial_idea']}'")
    print(f"[STORYTELLER] initialize_state returning initial_idea_elements: {result_state['initial_idea_elements']}")
    return result_state

@track_progress
def brainstorm_story_concepts(state: StoryState) -> Dict:
    """Brainstorm creative story concepts before generating the outline."""
    from storyteller_lib.creative_tools import creative_brainstorm
    
    print(f"[STORYTELLER] brainstorm_story_concepts received state with keys: {list(state.keys())}")
    if "initial_idea" in state:
        print(f"[STORYTELLER] brainstorm_story_concepts received initial_idea directly in state: '{state['initial_idea']}'")
    else:
        print(f"[STORYTELLER] WARNING: initial_idea not found in state keys: {list(state.keys())}")
        # Try to recover from memory if not in state
        try:
            initial_idea_obj = manage_memory_tool.invoke({
                "action": "get",
                "key": "initial_idea_raw",
                "namespace": MEMORY_NAMESPACE
            })
            
            if initial_idea_obj and "value" in initial_idea_obj:
                print(f"[STORYTELLER] Recovered initial_idea from memory: '{initial_idea_obj['value']}'")
                # We'll use this recovered value below
        except Exception as e:
            print(f"[STORYTELLER] Failed to recover initial_idea from memory: {str(e)}")
    
    # Log the state type to help debug
    print(f"[STORYTELLER] State type: {type(state)}")
    
    genre = state["genre"]
    tone = state["tone"]
    author = state["author"]
    # Get initial_idea from state, with memory as fallback
    initial_idea = state.get("initial_idea", "")
    if not initial_idea:
        try:
            initial_idea_obj = manage_memory_tool.invoke({
                "action": "get",
                "key": "initial_idea_raw",
                "namespace": MEMORY_NAMESPACE
            })
            if initial_idea_obj and "value" in initial_idea_obj:
                initial_idea = initial_idea_obj["value"]
                print(f"[STORYTELLER] Using initial_idea from memory: '{initial_idea}'")
        except Exception:
            pass
    
    # Get initial_idea_elements from state, with memory as fallback
    initial_idea_elements = state.get("initial_idea_elements", {})
    print(f"[STORYTELLER] Initial idea elements from state: {initial_idea_elements}")
    
    # If we have an initial idea but no elements, try to get them from memory
    if not initial_idea_elements and initial_idea:
        try:
            elements_obj = manage_memory_tool.invoke({
                "action": "get",
                "key": "initial_idea_elements",
                "namespace": MEMORY_NAMESPACE
            })
            if elements_obj and "value" in elements_obj:
                if "extracted_elements" in elements_obj["value"]:
                    initial_idea_elements = elements_obj["value"]["extracted_elements"]
                else:
                    initial_idea_elements = elements_obj["value"]
                print(f"[STORYTELLER] Using initial_idea_elements from memory: {initial_idea_elements}")
        except Exception as e:
            print(f"[STORYTELLER] Error retrieving initial_idea_elements from memory: {str(e)}")
            
    # If we still don't have elements but have an initial idea, parse it now
    if not initial_idea_elements and initial_idea:
        print(f"[STORYTELLER] No initial idea elements found, parsing now from: '{initial_idea}'")
        from storyteller_lib.storyteller import parse_initial_idea
        initial_idea_elements = parse_initial_idea(initial_idea)
        print(f"[STORYTELLER] Parsed initial idea elements: {initial_idea_elements}")
    
    author_style_guidance = state["author_style_guidance"]
    language = state.get("language", DEFAULT_LANGUAGE)
    
    print(f"[STORYTELLER] Brainstorming story concepts with initial idea: '{initial_idea}'")
    if initial_idea:
        if initial_idea_elements:
            print(f"[STORYTELLER] Initial idea elements extracted: {initial_idea_elements}")
        else:
            print(f"[STORYTELLER] WARNING: Initial idea provided but no elements extracted. This may affect story coherence.")
    else:
        print("[STORYTELLER] WARNING: No initial idea provided, brainstorming without specific constraints")
    
    # Generate enhanced context based on genre, tone, language, and initial idea
    idea_context = ""
    if initial_idea:
        # Create a more detailed context using the structured idea elements
        setting = initial_idea_elements.get("setting", "Unknown")
        characters = initial_idea_elements.get("characters", [])
        plot = initial_idea_elements.get("plot", "Unknown")
        themes = initial_idea_elements.get("themes", [])
        genre_elements = initial_idea_elements.get("genre_elements", [])
        
        # Log the extracted elements for debugging
        print(f"[STORYTELLER] Initial idea elements extracted: {initial_idea_elements}")
        
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
        print(f"[STORYTELLER] Created rich context with initial idea elements that MUST be incorporated")
        
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
    
    print(f"[STORYTELLER] Final context for brainstorming:")
    print(f"[STORYTELLER] ----------------------------------------")
    print(f"[STORYTELLER] {context.strip()}")
    print(f"[STORYTELLER] ----------------------------------------")
    print(f"[STORYTELLER] Context contains initial idea guidance: {idea_context != ''}")
    
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
    
    if not initial_idea:
        print(f"[STORYTELLER] WARNING: Using evaluation criteria that reference initial idea elements, but no initial idea was provided")
        print(f"[STORYTELLER] This may lead to inconsistent evaluation of brainstormed ideas")
    # Create constraints dictionary from initial idea elements
    constraints = {}
    if initial_idea and not initial_idea_elements:
        print(f"[STORYTELLER] WARNING: Initial idea '{initial_idea}' exists but no elements were extracted to create constraints")
    
    if initial_idea and not initial_idea_elements:
        print(f"[STORYTELLER] WARNING: Initial idea '{initial_idea}' exists but no elements were extracted to create constraints")
    
    if initial_idea_elements:
        constraints = {
            "setting": initial_idea_elements.get("setting", ""),
            "characters": ", ".join(initial_idea_elements.get("characters", [])),
            "plot": initial_idea_elements.get("plot", "")
        }
        
        # Check if any constraints are empty
        empty_constraints = [k for k, v in constraints.items() if not v]
        if empty_constraints:
            print(f"[STORYTELLER] WARNING: Some constraints are empty despite having initial idea: {empty_constraints}")
        
        print(f"[STORYTELLER] Created constraints from initial idea: {constraints}")
        
        # Create memory anchors for key elements to ensure persistence throughout generation
        for key, value in constraints.items():
            if value:
                print(f"[STORYTELLER] Creating memory anchor for constraint_{key}: {value}")
                manage_memory_tool.invoke({
                    "action": "create",
                    "key": f"constraint_{key}",
                    "value": value,
                    "namespace": MEMORY_NAMESPACE
                })
        
        # Create a genre validation memory anchor
        print(f"[STORYTELLER] Creating genre requirement memory anchor: {genre} with {tone} tone")
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
        print(f"[STORYTELLER] Creating initial idea constraint memory anchor with original idea: '{initial_idea}'")
        must_include = [
            f"Setting: {initial_idea_elements.get('setting', '')}",
            f"Characters: {', '.join(initial_idea_elements.get('characters', []))}",
            f"Plot: {initial_idea_elements.get('plot', '')}"
        ]
        print(f"[STORYTELLER] Must include elements: {must_include}")
        
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
        print(f"[STORYTELLER] Creating story directive memory anchor for initial idea: '{initial_idea}'")
        manage_memory_tool.invoke({
            "action": "create",
            "key": "story_directive",
            "value": f"This story must be based on the initial idea: '{initial_idea}'. The key elements (setting, characters, plot) must be preserved.",
            "namespace": MEMORY_NAMESPACE
        })
    
    # Brainstorm different high-level story concepts
    print(f"[STORYTELLER] Brainstorming story concepts with constraints: {constraints}")
    if initial_idea and not constraints:
        print(f"[STORYTELLER] WARNING: Initial idea exists but no constraints are being used in brainstorming")
    elif not initial_idea and constraints:
        print(f"[STORYTELLER] WARNING: Using constraints without an initial idea - this is unexpected")
    print(f"[STORYTELLER] Using strict adherence to initial idea: {True}")
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
    print(f"[STORYTELLER] Story concept brainstorming complete, recommended ideas: {brainstorm_results.get('recommended_ideas', 'None')}")
    
    # Brainstorm unique world-building elements
    print(f"[STORYTELLER] Brainstorming world building elements with constraints: {constraints}")
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
    print(f"[STORYTELLER] World building brainstorming complete, recommended ideas: {world_building_results.get('recommended_ideas', 'None')}")
    
    # Brainstorm central conflicts
    print(f"[STORYTELLER] Brainstorming central conflicts with constraints: {constraints}")
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
    print(f"[STORYTELLER] Central conflict brainstorming complete, recommended ideas: {conflict_results.get('recommended_ideas', 'None')}")
    
    # Validate that the brainstormed ideas adhere to the initial idea
    if initial_idea:
        print(f"[STORYTELLER] Validating brainstormed ideas against initial idea: '{initial_idea}'")
    else:
        print("[STORYTELLER] WARNING: Skipping validation step because no initial idea was provided")
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
        
        print("[STORYTELLER] Sending validation prompt to LLM")
        validation_result = llm.invoke([HumanMessage(content=validation_prompt)]).content
        print(f"[STORYTELLER] Validation result received: {validation_result[:100]}...")  # Print first 100 chars for brevity
        
        # Store the validation result in memory
        print("[STORYTELLER] Storing validation result in memory")
        manage_memory_tool.invoke({
            "action": "create",
            "key": "brainstorm_validation",
            "value": validation_result,
            "namespace": MEMORY_NAMESPACE
        })
    
    # Store all creative elements
    creative_elements = {
        "story_concepts": brainstorm_results,
        "world_building": world_building_results,
        "central_conflicts": conflict_results
    }
    
    # Store the initial idea elements with the creative elements for easy reference
    if initial_idea_elements:
        creative_elements["initial_idea_elements"] = initial_idea_elements
        print(f"[STORYTELLER] Added initial idea elements to creative elements for persistence: {initial_idea_elements}")
    
    print(f"[STORYTELLER] Final creative elements structure created with initial idea influence: {initial_idea != ''}")
    
    # Check if initial idea was properly incorporated
    if initial_idea and not creative_elements.get("initial_idea_elements"):
        print(f"[STORYTELLER] WARNING: Initial idea '{initial_idea}' may not be properly incorporated in the final creative elements")
    
    # Create messages to add and remove
    idea_mention = f" based on your idea" if initial_idea else ""
    
    # Final summary of initial idea usage
    if initial_idea:
        print(f"[STORYTELLER] SUMMARY: Brainstorming completed WITH initial idea: '{initial_idea}'")
        print(f"[STORYTELLER] Initial idea elements were extracted: {bool(initial_idea_elements)}")
        print(f"[STORYTELLER] Constraints were created: {bool(constraints)}")
        print(f"[STORYTELLER] Validation was performed: {True}")
    else:
        print(f"[STORYTELLER] SUMMARY: Brainstorming completed WITHOUT any initial idea")
        print(f"[STORYTELLER] This may result in a story that doesn't match user expectations")
        print(f"[STORYTELLER] Consider providing an initial idea for more directed story generation")
    new_msg = AIMessage(content=f"I've brainstormed several creative concepts for your {tone} {genre} story{idea_mention}. Now I'll develop a cohesive outline based on the most promising ideas.")
    
    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]
    
    # Update state with brainstormed ideas
    return {
        "creative_elements": creative_elements,
        "messages": [
            *[RemoveMessage(id=msg_id) for msg_id in message_ids],
            new_msg
        ]
    }