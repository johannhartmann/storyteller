"""
StoryCraft Agent - Initialization nodes.
"""

from typing import Dict

from storyteller_lib.config import llm, manage_memory_tool, MEMORY_NAMESPACE
from storyteller_lib.models import StoryState
from langchain_core.messages import AIMessage, HumanMessage
from storyteller_lib import track_progress

@track_progress
def initialize_state(state: StoryState) -> Dict:
    """Initialize the story state with user input."""
    messages = state["messages"]
    
    # Use the genre, tone, and author values already passed in the state
    # If not provided, use defaults
    genre = state.get("genre") or "fantasy"
    tone = state.get("tone") or "epic"
    author = state.get("author") or ""
    author_style_guidance = state.get("author_style_guidance", "")
    
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
    response_message = f"I'll create a {tone} {genre} story{author_mention} for you. Let me start planning the narrative..."
    
    # Initialize the state
    return {
        "genre": genre,
        "tone": tone,
        "author": author,
        "author_style_guidance": author_style_guidance,
        "global_story": "",
        "chapters": {},
        "characters": {},
        "revelations": {"reader": [], "characters": []},
        "current_chapter": "",
        "current_scene": "",
        "completed": False,
        "messages": [AIMessage(content=response_message)]
    }

@track_progress
def brainstorm_story_concepts(state: StoryState) -> Dict:
    """Brainstorm creative story concepts before generating the outline."""
    from storyteller_lib.creative_tools import creative_brainstorm
    
    genre = state["genre"]
    tone = state["tone"]
    author = state["author"]
    author_style_guidance = state["author_style_guidance"]
    
    # Generate initial context based on genre and tone
    context = f"""
    We're creating a {tone} {genre} story that follows the hero's journey structure.
    The story should be engaging, surprising, and emotionally resonant with readers.
    """
    
    # Brainstorm different high-level story concepts
    brainstorm_results = creative_brainstorm(
        topic="Story Concept",
        genre=genre,
        tone=tone,
        context=context,
        author=author,
        author_style_guidance=author_style_guidance,
        num_ideas=5
    )
    
    # Brainstorm unique world-building elements
    world_building_results = creative_brainstorm(
        topic="World Building Elements",
        genre=genre,
        tone=tone,
        context=context,
        author=author,
        author_style_guidance=author_style_guidance,
        num_ideas=4
    )
    
    # Brainstorm central conflicts
    conflict_results = creative_brainstorm(
        topic="Central Conflict",
        genre=genre,
        tone=tone,
        context=context,
        author=author,
        author_style_guidance=author_style_guidance,
        num_ideas=3
    )
    
    # Store all creative elements
    creative_elements = {
        "story_concepts": brainstorm_results,
        "world_building": world_building_results,
        "central_conflicts": conflict_results
    }
    
    # Update state with brainstormed ideas
    return {
        "creative_elements": creative_elements,
        "messages": [AIMessage(content=f"I've brainstormed several creative concepts for your {tone} {genre} story. Now I'll develop a cohesive outline based on the most promising ideas.")]
    }