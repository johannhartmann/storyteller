"""
StoryCraft Agent - Story outline and planning nodes.
"""

from typing import Dict

from storyteller_lib.config import llm, manage_memory_tool, MEMORY_NAMESPACE, log_memory_usage
from storyteller_lib.models import StoryState
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from storyteller_lib.creative_tools import generate_structured_json, parse_json_with_langchain
from storyteller_lib import track_progress

@track_progress
def generate_story_outline(state: StoryState) -> Dict:
    """Generate the overall story outline using the hero's journey structure."""
    genre = state["genre"]
    tone = state["tone"]
    author = state["author"]
    initial_idea = state.get("initial_idea", "")
    author_style_guidance = state["author_style_guidance"]
    creative_elements = state.get("creative_elements", {})
    
    # Prepare author style guidance
    style_guidance = ""
    if author:
        # If we don't have author guidance yet, generate it now
        if not author_style_guidance:
            author_prompt = f"""
            Analyze the writing style of {author} in detail.
            
            Describe:
            1. Narrative techniques and point of view
            2. Typical sentence structure and paragraph organization
            3. Dialogue style and character voice
            4. Description style and level of detail
            5. Pacing and plot development approaches
            6. Themes and motifs commonly explored
            7. Unique stylistic elements or literary devices frequently used
            8. Tone and atmosphere typically created
            
            Focus on providing specific, actionable guidance that could help emulate this author's style
            when writing a new story.
            """
            
            author_style_guidance = llm.invoke([HumanMessage(content=author_prompt)]).content
            
            # Store this for future use
            manage_memory_tool.invoke({
                "action": "create",
                "key": f"author_style_{author.lower().replace(' ', '_')}",
                "value": author_style_guidance,
                "namespace": MEMORY_NAMESPACE
            })
        
        style_guidance = f"""
        AUTHOR STYLE GUIDANCE:
        You will be emulating the writing style of {author}. Here's guidance on this author's style:
        
        {author_style_guidance}
        
        Incorporate these stylistic elements into your story outline while maintaining the hero's journey structure.
        """
    
    # Include brainstormed creative elements if available
    creative_guidance = ""
    if creative_elements:
        # Extract recommended story concept
        story_concept = ""
        if "story_concepts" in creative_elements and creative_elements["story_concepts"].get("recommended_ideas"):
            story_concept = creative_elements["story_concepts"]["recommended_ideas"]
            
        # Extract recommended world building elements
        world_building = ""
        if "world_building" in creative_elements and creative_elements["world_building"].get("recommended_ideas"):
            world_building = creative_elements["world_building"]["recommended_ideas"]
            
        # Extract recommended central conflict
        conflict = ""
        if "central_conflicts" in creative_elements and creative_elements["central_conflicts"].get("recommended_ideas"):
            conflict = creative_elements["central_conflicts"]["recommended_ideas"]
        
        # Compile creative guidance
        creative_guidance = f"""
        BRAINSTORMED CREATIVE ELEMENTS:
        
        Recommended Story Concept:
        {story_concept}
        
        Recommended World Building Elements:
        {world_building}
        
        Recommended Central Conflict:
        {conflict}
        
        Incorporate these brainstormed elements into your story outline, adapting them as needed to fit the hero's journey structure.
        """
    # Prepare initial idea guidance
    idea_guidance = ""
    if initial_idea:
        idea_guidance = f"""
        INITIAL STORY IDEA:
        {initial_idea}
        
        Use this initial idea as the foundation for your story outline. Incorporate its key elements,
        characters, setting, and premise while adapting it to fit the hero's journey structure.
        """
    
    # Prompt for story generation
    prompt = f"""
    Create a compelling story outline for a {tone} {genre} narrative following the hero's journey structure.
    {f"Based on this initial idea: '{initial_idea}'" if initial_idea else ""}
    
    Include all major phases:
    Include all major phases:
    1. The Ordinary World
    2. The Call to Adventure
    3. Refusal of the Call
    4. Meeting the Mentor
    5. Crossing the Threshold
    6. Tests, Allies, and Enemies
    7. Approach to the Inmost Cave
    8. The Ordeal
    9. Reward (Seizing the Sword)
    10. The Road Back
    11. Resurrection
    12. Return with the Elixir
    
    For each phase, provide a brief description of what happens.
    Also include:
    - A captivating title for the story
    - 3-5 main characters with brief descriptions
    - A central conflict or challenge
    - The world/setting of the story
    - Key themes or messages
    
    Format your response as a structured outline with clear sections.
    
    {idea_guidance}
    
    {creative_guidance}
    
    {style_guidance}
    """
    
    # Generate the story outline
    story_outline = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Store in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": "story_outline",
        "value": story_outline
    })
    
    # Store in procedural memory that this was a result of initial generation
    manage_memory_tool.invoke({
        "action": "create",
        "key": "procedural_memory_outline_generation",
        "value": {
            "timestamp": "initial_creation",
            "method": "hero's_journey_structure"
        }
    })
    
    # Update the state
    
    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]
    
    # Create message for the user
    new_msg = AIMessage(content="I've created a story outline following the hero's journey structure. Now I'll develop the characters in more detail.")
    
    return {
        "global_story": story_outline,
        "messages": [
            *[RemoveMessage(id=msg_id) for msg_id in message_ids],
            new_msg
        ]
    }


@track_progress
def generate_characters(state: StoryState) -> Dict:
    """Generate detailed character profiles based on the story outline."""
    global_story = state["global_story"]
    genre = state["genre"]
    tone = state["tone"]
    author = state["author"]
    author_style_guidance = state["author_style_guidance"]
    
    # Prepare character style guidance
    char_style_section = ""
    if author:
        # Extract character-specific guidance
        character_prompt = f"""
        Based on the writing style of {author}, extract specific guidance for character development.
        Focus on:
        
        1. How the author typically develops characters
        2. Types of characters frequently used
        3. Character archetypes common in their work
        4. How the author handles character flaws and growth
        5. Character dialogue and voice patterns
        6. Character relationships and dynamics
        
        Provide concise, actionable guidance for creating characters in the style of {author}.
        """
        
        if not "character development" in author_style_guidance.lower():
            # Only generate if we don't already have character info in our guidance
            character_guidance = llm.invoke([HumanMessage(content=character_prompt)]).content
            
            # Store this specialized guidance
            manage_memory_tool.invoke({
                "action": "create",
                "key": f"author_character_style_{author.lower().replace(' ', '_')}",
                "value": character_guidance,
                "namespace": MEMORY_NAMESPACE
            })
            
            char_style_section = f"""
            CHARACTER STYLE GUIDANCE:
            When creating characters in the style of {author}, follow these guidelines:
            
            {character_guidance}
            """
        else:
            # Use the general guidance if it already contains character info
            char_style_section = f"""
            CHARACTER STYLE GUIDANCE:
            When creating characters in the style of {author}, follow these guidelines from the author's general style:
            
            {author_style_guidance}
            """
    
    # Prompt for character generation
    prompt = f"""
    Based on this story outline:
    
    {global_story}
    
    Create detailed profiles for 4-6 characters in this {tone} {genre} story.
    For each character, include:
    
    1. Name
    2. Role in the story (protagonist, antagonist, mentor, etc.)
    3. Detailed backstory
    4. Initial known facts (what the character and reader know at the start)
    5. Secret facts (information hidden from the reader initially)
    6. Key relationships with other characters
    
    Format each character profile clearly and ensure they have interconnected relationships and histories.
    
    {char_style_section}
    """
    
    # Generate character profiles
    character_profiles_text = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Define the schema for character data
    character_schema = """
    {
      "character_slug": {
        "name": "Character Name",
        "role": "Role in story (protagonist, antagonist, etc)",
        "backstory": "Detailed character backstory",
        "evolution": ["Initial state", "Future development point"],
        "known_facts": ["Known fact 1", "Known fact 2"],
        "secret_facts": ["Secret fact 1", "Secret fact 2"],
        "revealed_facts": [],
        "relationships": {
          "other_character_slug": "Relationship description"
        }
      }
    }
    """
    
    # Default fallback data in case JSON generation fails
    default_characters = {
        "hero": {
            "name": "Hero",
            "role": "Protagonist",
            "backstory": "Ordinary person with hidden potential",
            "evolution": ["Begins journey", "Faces first challenge"],
            "known_facts": ["Lived in small village", "Dreams of adventure"],
            "secret_facts": ["Has a special lineage", "Possesses latent power"],
            "revealed_facts": [],
            "relationships": {"mentor": "Student", "villain": "Adversary"}
        },
        "mentor": {
            "name": "Mentor",
            "role": "Guide",
            "backstory": "Wise figure with past experience",
            "evolution": ["Introduces hero to new world"],
            "known_facts": ["Has many skills", "Traveled widely"],
            "secret_facts": ["Former student of villain", "Hiding a prophecy"],
            "revealed_facts": [],
            "relationships": {"hero": "Teacher", "villain": "Former student"}
        },
        "villain": {
            "name": "Villain",
            "role": "Antagonist",
            "backstory": "Once good, corrupted by power",
            "evolution": ["Sends minions after hero"],
            "known_facts": ["Rules with fear", "Seeks ancient artifact"],
            "secret_facts": ["Was once good", "Has personal connection to hero"],
            "revealed_facts": [],
            "relationships": {"hero": "Enemy", "mentor": "Former mentor"}
        }
    }
    
    # Use the new function to generate structured JSON
    try:
        from storyteller_lib.creative_tools import generate_structured_json
        characters = generate_structured_json(
            character_profiles_text,
            character_schema,
            "character profiles"
        )
        
        # If generation failed, use the default fallback data
        if not characters:
            print("Using default character data as JSON generation failed.")
            characters = default_characters
    except Exception as e:
        print(f"Error parsing character data: {str(e)}")
        # Fallback structure defined above in parse_structured_data call
        characters = default_characters
        
    # Validate the structure
    for char_name, profile in characters.items():
        required_fields = ["name", "role", "backstory", "evolution", "known_facts", 
                         "secret_facts", "revealed_facts", "relationships"]
        for field in required_fields:
            if field not in profile:
                profile[field] = [] if field in ["evolution", "known_facts", "secret_facts", "revealed_facts"] else {}
                if field == "name":
                    profile[field] = char_name.capitalize()
                elif field == "role":
                    profile[field] = "Supporting Character"
                elif field == "backstory":
                    profile[field] = "Unknown background"
    
    # Store character profiles in memory
    for char_name, profile in characters.items():
        manage_memory_tool.invoke({
            "action": "create",
            "key": f"character_{char_name}",
            "value": profile
        })
    
    # Update state
    
    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]
    
    # Create message for the user
    new_msg = AIMessage(content="I've developed detailed character profiles with interconnected backgrounds and motivations. Now I'll plan the chapters.")
    
    return {
        "characters": characters,
        "messages": [
            *[RemoveMessage(id=msg_id) for msg_id in message_ids],
            new_msg
        ]
    }


@track_progress
def plan_chapters(state: StoryState) -> Dict:
    """Divide the story into chapters with detailed outlines."""
    # Log memory usage at the start
    memory_before = log_memory_usage("plan_chapters_start")
    
    global_story = state["global_story"]
    characters = state["characters"]
    genre = state["genre"]
    tone = state["tone"]
    
    # Prompt for chapter planning
    prompt = f"""
    Based on this story outline:
    
    {global_story}
    
    And these characters:
    
    {characters}
    
    Create a plan for 5-10 chapters that cover the entire hero's journey for this {tone} {genre} story.
    
    For each chapter, provide:
    1. Chapter number and title
    2. A summary of major events (200-300 words)
    3. Which characters appear and how they develop
    4. 2-4 key scenes that should be included
    5. Any major revelations or plot twists
    
    Ensure the chapters flow logically and maintain the arc of the hero's journey.
    """
    
    # Generate chapter plan
    chapter_plan_text = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Define the schema for chapter data
    chapter_schema = """
    {
      "1": {
        "title": "Chapter Title",
        "outline": "Detailed summary of the chapter",
        "scenes": {
          "1": {
            "content": "",
            "reflection_notes": []
          },
          "2": {
            "content": "",
            "reflection_notes": []
          }
        },
        "reflection_notes": []
      }
    }
    """
    
    # Default fallback chapters in case JSON generation fails
    default_chapters = {
        "1": {
            "title": "The Ordinary World",
            "outline": "Introduction to the hero and their mundane life. Hints of adventure to come.",
            "scenes": {
                "1": {"content": "", "reflection_notes": []},
                "2": {"content": "", "reflection_notes": []}
            },
            "reflection_notes": []
        },
        "2": {
            "title": "The Call to Adventure",
            "outline": "Hero receives a call to adventure and initially hesitates.",
            "scenes": {
                "1": {"content": "", "reflection_notes": []},
                "2": {"content": "", "reflection_notes": []}
            },
            "reflection_notes": []
        },
        "3": {
            "title": "Meeting the Mentor",
            "outline": "Hero meets a wise mentor who provides guidance and tools.",
            "scenes": {
                "1": {"content": "", "reflection_notes": []},
                "2": {"content": "", "reflection_notes": []}
            },
            "reflection_notes": []
        }
    }
    
    # Use the new function to generate structured JSON
    try:
        from storyteller_lib.creative_tools import generate_structured_json
        chapters = generate_structured_json(
            chapter_plan_text,
            chapter_schema,
            "chapter plan"
        )
        
        # If generation failed, use the default fallback data
        if not chapters:
            print("Using default chapter data as JSON generation failed.")
            chapters = default_chapters
    except Exception as e:
        print(f"Error generating chapter data: {str(e)}")
        # Fall back to default chapters
        chapters = default_chapters
    
    # Validate the structure and ensure each chapter has the required fields
    for chapter_num, chapter in chapters.items():
        if "title" not in chapter:
            chapter["title"] = f"Chapter {chapter_num}"
        if "outline" not in chapter:
            chapter["outline"] = f"Events of chapter {chapter_num}"
        if "scenes" not in chapter:
            chapter["scenes"] = {"1": {"content": "", "reflection_notes": []}, 
                                "2": {"content": "", "reflection_notes": []}}
        if "reflection_notes" not in chapter:
            chapter["reflection_notes"] = []
            
        # Ensure all scenes have the required structure
        for scene_num, scene in chapter["scenes"].items():
            if "content" not in scene:
                scene["content"] = ""
            if "reflection_notes" not in scene:
                scene["reflection_notes"] = []
    
    # Store chapter plans in memory
    for chapter_num, chapter_data in chapters.items():
        manage_memory_tool.invoke({
            "action": "create",
            "key": f"chapter_{chapter_num}",
            "value": chapter_data
        })
    
    # Log memory usage after chapter planning
    memory_after = log_memory_usage("plan_chapters_end")
    
    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]
    
    # Create message for the user
    new_msg = AIMessage(content="I've planned out the chapters for the story. Now I'll begin writing the first scene of chapter 1.")
    
    return {
        "chapters": chapters,
        "current_chapter": "1",  # Start with the first chapter
        "current_scene": "1",    # Start with the first scene
        
        # Add memory usage tracking
        "memory_usage": {
            "plan_chapters": {
                "before": memory_before,
                "after": memory_after,
                "chapter_count": len(chapters),
                "timestamp": "now"
            }
        },
        
        "messages": [
            *[RemoveMessage(id=msg_id) for msg_id in message_ids],
            new_msg
        ]
    }