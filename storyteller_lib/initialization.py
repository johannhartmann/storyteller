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
    author_style_guidance = state.get("author_style_guidance", "")
    language = state.get("language") or DEFAULT_LANGUAGE
    
    # Validate language and default to English if not supported
    if language.lower() not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE
    
    # Process the initial idea to extract key elements
    idea_elements = {}
    if initial_idea:
        # Create a structured representation of the initial idea
        idea_prompt = f"""
        Analyze this initial story idea and extract key elements:
        
        "{initial_idea}"
        
        Extract and structure the following elements:
        1. Main setting (e.g., "zoo", "space station", "medieval kingdom")
        2. Main characters (e.g., "orangutan detective", "space captain", "young wizard")
        3. Central conflict or plot (e.g., "murder investigation", "alien invasion", "quest for artifact")
        4. Any specific themes or motifs mentioned
        5. Any specific genre elements that should be emphasized
        
        Format your response as a structured JSON object with these fields.
        """
        
        try:
            idea_analysis = llm.invoke([HumanMessage(content=idea_prompt)]).content
            
            # Try to parse the JSON response
            from storyteller_lib.creative_tools import parse_json_with_langchain
            idea_elements = parse_json_with_langchain(idea_analysis, {
                "setting": "Unknown",
                "characters": [],
                "plot": "Unknown",
                "themes": [],
                "genre_elements": []
            })
            
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
        except Exception as e:
            print(f"Error processing initial idea: {str(e)}")
    
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
    idea_mention = f" based on your idea: '{initial_idea}'" if initial_idea else ""
    language_mention = f" in {SUPPORTED_LANGUAGES[language.lower()]}" if language.lower() != DEFAULT_LANGUAGE else ""
    response_message = f"I'll create a {tone} {genre} story{author_mention}{language_mention}{idea_mention} for you. Let me start planning the narrative..."
    
    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]
    
    # Initialize the state
    return {
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

@track_progress
def brainstorm_story_concepts(state: StoryState) -> Dict:
    """Brainstorm creative story concepts before generating the outline."""
    from storyteller_lib.creative_tools import creative_brainstorm
    
    genre = state["genre"]
    tone = state["tone"]
    author = state["author"]
    initial_idea = state.get("initial_idea", "")
    initial_idea_elements = state.get("initial_idea_elements", {})
    author_style_guidance = state["author_style_guidance"]
    language = state.get("language", DEFAULT_LANGUAGE)
    
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
        manage_memory_tool.invoke({
            "action": "create",
            "key": "initial_idea_constraint",
            "value": {
                "original_idea": initial_idea,
                "must_include": [
                    f"Setting: {initial_idea_elements.get('setting', '')}",
                    f"Characters: {', '.join(initial_idea_elements.get('characters', []))}",
                    f"Plot: {initial_idea_elements.get('plot', '')}"
                ],
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
    
    # Create messages to add and remove
    idea_mention = f" based on your idea" if initial_idea else ""
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