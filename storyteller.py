"""
StoryCraft Agent - Autonomous Story-Writing with Dynamic Memory & State.

This agent generates engaging, multi-chapter stories using the hero's journey structure.
It manages the overall story arc, chapters, scenes, characters, and revelations.
"""

import os
from typing import Annotated, Dict, List, Optional, Union
from typing_extensions import TypedDict
from operator import add
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# Import centralized config
from storyteller_lib.config import (
    llm, 
    MEMORY_NAMESPACE, 
    manage_memory_tool, 
    search_memory_tool
)
from storyteller_lib.memory_manager import manage_memory, search_memory

# Import from creative_tools module
from storyteller_lib.creative_tools import generate_structured_json, parse_json_with_langchain, creative_brainstorm
from storyteller_lib.integration import integrate_improvements, post_scene_improvements, update_concept_introduction_statuses

# Define the state schema
class CharacterProfile(TypedDict):
    name: str
    role: str
    backstory: str
    evolution: List[str]
    known_facts: List[str]
    secret_facts: List[str]
    revealed_facts: List[str]
    relationships: Dict[str, str]

class SceneState(TypedDict):
    content: str
    reflection_notes: List[str]

class ChapterState(TypedDict):
    title: str
    outline: str
    scenes: Dict[str, SceneState]
    reflection_notes: List[str]

class StoryState(TypedDict):
    messages: Annotated[List[Union[HumanMessage, AIMessage]], add_messages]
    genre: str
    tone: str
    author: str  # Author whose style to emulate
    author_style_guidance: str  # Specific notes on author's style
    global_story: str  # Overall storyline and hero's journey phases
    chapters: Dict[str, ChapterState]  # Keyed by chapter number or identifier
    characters: Dict[str, CharacterProfile]  # Profiles for each character
    revelations: Dict[str, List[str]]  # e.g., {"reader": [...], "characters": [...]}
    creative_elements: Dict[str, Dict]  # Storage for brainstormed ideas
    current_chapter: str  # Track which chapter is being written
    current_scene: str  # Track which scene is being written
    completed: bool  # Flag to indicate if the story is complete

# Note: LLM and memory tools are now imported from storyteller_lib.config

# creative_brainstorm function is now imported from creative_tools

# Define agent nodes

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
        "last_node": "initialize_state",  # Track which node was last executed for routing
        "messages": [AIMessage(content=response_message)]
    }

def brainstorm_story_concepts(state: StoryState) -> Dict:
    """Brainstorm creative story concepts before generating the outline."""
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
        "last_node": "brainstorm_story_concepts",
        "messages": [AIMessage(content=f"I've brainstormed several creative concepts for your {tone} {genre} story. Now I'll develop a cohesive outline based on the most promising ideas.")]
    }

def generate_story_outline(state: StoryState) -> Dict:
    """Generate the overall story outline using the hero's journey structure."""
    genre = state["genre"]
    tone = state["tone"]
    author = state["author"]
    author_style_guidance = state["author_style_guidance"]
    creative_elements = state.get("creative_elements", {})
    
    # Initialize key concepts tracker for exposition clarity
    from storyteller_lib.exposition import track_key_concepts
    
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
    
    # Get language from state
    language = state.get("language", DEFAULT_LANGUAGE)
    
    # Prepare language guidance
    language_guidance = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_guidance = f"""
        LANGUAGE REQUIREMENTS:
        This story outline, including the title and all content, MUST be written entirely in {SUPPORTED_LANGUAGES[language.lower()]}.
        Do not include any text in English or any other language.
        The complete outline must be written only in {SUPPORTED_LANGUAGES[language.lower()]}.
        """
    
    # Prompt for story generation
    prompt = f"""
    Create a compelling story outline for a {tone} {genre} narrative following the hero's journey structure.
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
    
    {creative_guidance}
    
    {style_guidance}
    
    {language_guidance}
    """
    
    # Generate the story outline
    story_outline = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Store in memory
    manage_memory(action="create", key="story_outline", value=story_outline)
    
    # Store in procedural memory that this was a result of initial generation
    manage_memory(action="create", key="procedural_memory_outline_generation", value={
            "timestamp": "initial_creation",
            "method": "hero's_journey_structure"
        })
    
    # Initialize key concepts tracker for exposition clarity
    key_concepts_result = track_key_concepts(state)
    
    # Update the state
    return {
        "global_story": story_outline,
        "key_concepts_tracker": key_concepts_result.get("key_concepts_tracker", {}),
        "last_node": "generate_story_outline",
        "messages": [AIMessage(content="I've created a story outline following the hero's journey structure and identified key concepts that will need clear exposition. Now I'll develop the characters in more detail.")]
    }

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
    
    # Get language from state
    language = state.get("language", DEFAULT_LANGUAGE)
    
    # Prepare language guidance
    language_guidance = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_guidance = f"""
        LANGUAGE REQUIREMENTS:
        All character names, backstories, and other details MUST be appropriate for {SUPPORTED_LANGUAGES[language.lower()]} speakers and culture.
        Character names should be typical for {SUPPORTED_LANGUAGES[language.lower()]}-speaking regions.
        All text must be written entirely in {SUPPORTED_LANGUAGES[language.lower()]}.
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
    
    {language_guidance}
    """
    
    # Generate character profiles
    character_profiles_text = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Parse character profiles with a second LLM call to ensure structured data
    parsing_prompt = f"""
    Convert these character profiles into structured data:
    
    {character_profiles_text}
    
    For each character, return a JSON object with these fields:
    - name: The character's name
    - role: Their role in the story
    - backstory: Their detailed backstory
    - evolution: List of character development points (starting with initial state)
    - known_facts: List of facts known to the character and reader at the start
    - secret_facts: List of facts hidden from the reader initially
    - revealed_facts: Empty list (will be populated as the story progresses)
    - relationships: Object mapping other character names to relationship descriptions
    
    Format as a valid, parseable JSON object where keys are character names (slugified, lowercase) and values are their profiles.
    Your response should contain ONLY the JSON object, nothing else. No explanation, no markdown formatting.
    """
    
    # Get structured character data as JSON
    character_data_text = llm.invoke([HumanMessage(content=parsing_prompt)]).content
    
    # Use the imported parsing functions
    
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
    
    # First try using LangChain's JSON parser directly
    characters = parse_json_with_langchain(character_data_text, default_characters)
    
    # If that failed, try generating structured JSON with the LLM
    if not characters or characters == default_characters:
        characters = generate_structured_json(
            character_profiles_text,
            character_schema,
            "character profiles"
        )
        
    # If all parsing attempts failed, use the default fallback data
    if not characters:
        print("Using default character data as JSON generation and parsing failed.")
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
    return {
        "characters": characters,
        "last_node": "generate_characters",
        "messages": [AIMessage(content="I've developed detailed character profiles with interconnected backgrounds and motivations. Now I'll plan the chapters.")]
    }

def plan_chapters(state: StoryState) -> Dict:
    """Divide the story into chapters with detailed outlines."""
    global_story = state["global_story"]
    characters = state["characters"]
    genre = state["genre"]
    tone = state["tone"]
    
    # Get language from state
    language = state.get("language", DEFAULT_LANGUAGE)
    
    # Prepare language guidance
    language_guidance = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_guidance = f"""
        LANGUAGE REQUIREMENTS:
        All chapter titles and content MUST be written entirely in {SUPPORTED_LANGUAGES[language.lower()]}.
        Do not include any text in English or any other language.
        """
    
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
    
    {language_guidance}
    """
    
    # Generate chapter plan
    chapter_plan_text = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Parse chapter plan into structured data
    parsing_prompt = f"""
    Convert this chapter plan into structured data:
    
    {chapter_plan_text}
    
    For each chapter, return a JSON object with these fields:
    - title: The chapter title
    - outline: Detailed summary of the chapter
    - scenes: Object where keys are scene numbers (e.g., "1", "2") and values are objects
      with "content" (empty string) and "reflection_notes" (empty array)
    - reflection_notes: Empty array
    
    Format as a valid, parseable JSON object where keys are chapter numbers (as strings) and values are chapter objects.
    Your response should contain ONLY the JSON object, nothing else. No explanation, no markdown formatting.
    """
    
    # Get structured chapter data
    chapter_data_text = llm.invoke([HumanMessage(content=parsing_prompt)]).content
    
    # Use the imported parsing functions
    
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
    
    # First try using LangChain's JSON parser directly
    chapters = parse_json_with_langchain(chapter_data_text, default_chapters)
    
    # If that failed, try generating structured JSON with the LLM
    if not chapters or chapters == default_chapters:
        chapters = generate_structured_json(
            chapter_plan_text,
            chapter_schema,
            "chapter plan"
        )
        
    # If all parsing attempts failed, use the default fallback data
    if not chapters:
        print("Using default chapter data as JSON generation and parsing failed.")
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
    
    # Update state
    return {
        "chapters": chapters,
        "current_chapter": "1",  # Start with the first chapter
        "current_scene": "1",    # Start with the first scene
        "last_node": "plan_chapters",
        "messages": [AIMessage(content="I've planned out the chapters for the story. Now I'll begin writing the first scene of chapter 1.")]
    }

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
        
        # Store revision information in memory for procedural tracking
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
            "current_chapter": current_chapter,
            "current_scene": current_scene,
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
        
        # We don't need the APPROVED marker anymore since router doesn't check for it
        # Make sure to return current_chapter and current_scene to maintain state
        return {
            "current_chapter": current_chapter,
            "current_scene": current_scene,
            "last_node": "revise_scene_if_needed",
            "messages": [AIMessage(content=f"Scene {current_scene} of chapter {current_chapter} is consistent and well-crafted, no revision needed.")]
        }

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
    # Extract and store key information from completed content
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
                
        # Note: Prompt optimization has been removed as it was not being used effectively
        # The continuity review is stored for future reference
    except Exception as e:
        # Log the error but don't halt execution
        print(f"Background memory processing error: {str(e)}")
    
    return {
        "revelations": updated_revelations,
        "last_node": "review_continuity",
        "messages": [AIMessage(content=f"I've performed a comprehensive continuity review after completing chapter {max(completed_chapters)}.")]
    }

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
    manage_memory(action="create", key="final_continuity_check", value=final_continuity_check)
    
    # Compile the story
    story = []
    
    # Extract title from global story
    story_title = state['global_story'].split('\n')[0]
    # Clean up title if needed (remove any "Title: " prefix)
    if ":" in story_title and len(story_title.split(":")) > 1:
        story_title = story_title.split(":", 1)[1].strip()
        # Add title only
        story.append(f"# {story_title}")
        
        # Add each chapter without scene headlines
        for chapter_num in sorted(chapters.keys(), key=int):
            chapter = chapters[chapter_num]
            story.append(f"\n## Chapter {chapter_num}: {chapter['title']}\n")
            
            # Add each scene without scene headlines
            for scene_num in sorted(chapter["scenes"].keys(), key=int):
                scene = chapter["scenes"][scene_num]
                story.append(scene["content"])
                story.append("\n\n")
            story.append("\n\n")
    
    # Join the story parts
    complete_story = "\n".join(story)
    
    # Store the complete story in memory
    manage_memory(action="create", key="complete_story", value=complete_story)
    
    # Final message to the user
    return {
        "last_node": "compile_final_story",
        "messages": [AIMessage(content="I've compiled the complete story. Here's a summary of what I created:"),
                    AIMessage(content=f"A {state['tone']} {state['genre']} story with {len(chapters)} chapters and {sum(len(chapter['scenes']) for chapter in chapters.values())} scenes. The story follows the hero's journey structure and features {len(state['characters'])} main characters. I've maintained consistency throughout the narrative and carefully managed character development and plot revelations.")]
    }

def router(state: StoryState) -> Dict:
    """Route to the appropriate next node based on the current state."""
    next_node = ""
    
    # Safety check - if we're in an invalid state that might cause infinite recursion
    # terminate the execution by going to the compile_final_story node
    if "router_count" not in state:
        state["router_count"] = 0
    else:
        state["router_count"] += 1
        
    # If we've hit the router too many times, something is wrong - go to final node
    if state["router_count"] > 50:
        print("WARNING: Router has been called too many times. Terminating execution.")
        state["completed"] = True
        return {"next": "compile_final_story"}
    
    # Normal routing logic
    if "global_story" not in state or not state["global_story"]:
        if "creative_elements" not in state or not state.get("creative_elements"):
            next_node = "brainstorm_story_concepts"
        else:
            next_node = "generate_story_outline"
    
    elif "characters" not in state or not state["characters"]:
        next_node = "generate_characters"
    
    elif "chapters" not in state or not state["chapters"]:
        next_node = "plan_chapters"
    
    elif state.get("completed", False):
        next_node = "compile_final_story"
    
    else:
        # Get the current chapter and scene - add safety checks
        current_chapter = state.get("current_chapter", "")
        current_scene = state.get("current_scene", "")
        
        # Safety check - if current_chapter or current_scene are not set, go to plan_chapters
        if not current_chapter or not current_scene:
            print("WARNING: Current chapter or scene not set. Going back to planning.")
            return {"next": "plan_chapters"}
            
        # Safety check - make sure the chapter exists in the chapters dictionary
        if current_chapter not in state.get("chapters", {}):
            print(f"WARNING: Chapter {current_chapter} not found. Going back to planning.")
            return {"next": "plan_chapters"}
            
        chapter = state["chapters"][current_chapter]
        
        # Safety check - make sure the scene exists in the chapter
        if current_scene not in chapter.get("scenes", {}):
            print(f"WARNING: Scene {current_scene} not found in chapter {current_chapter}. Moving to next chapter.")
            return {"next": "advance_to_next_scene_or_chapter"}
        
        # Check if we need to brainstorm for the current scene
        scene_creative_key = f"scene_elements_ch{current_chapter}_sc{current_scene}"
        if "creative_elements" not in state or scene_creative_key not in state.get("creative_elements", {}):
            next_node = "brainstorm_scene_elements"
        
        # Check if the current scene has content
        elif not chapter["scenes"][current_scene].get("content"):
            next_node = "write_scene"
        
        # Check if the current scene has reflection notes
        elif not chapter["scenes"][current_scene].get("reflection_notes"):
            next_node = "reflect_on_scene"
        
        # Check if character profiles need updating (always do this after reflection)
        else:
            last_node = state.get("last_node", "")
            
            # After reflection or revision, update character profiles
            if last_node == "reflect_on_scene" or last_node == "revise_scene_if_needed":
                next_node = "update_character_profiles"
            
            # Check if we've updated characters and need to move to the next scene/chapter
            elif last_node == "update_character_profiles":
                # Time to check if we've completed a chapter
                all_scenes_complete = True
                for scene in chapter["scenes"].values():
                    if not scene.get("content") or not scene.get("reflection_notes"):
                        all_scenes_complete = False
                        break
                
                if all_scenes_complete and last_node != "review_continuity":
                    # If we've completed all scenes in the chapter, run a continuity review
                    next_node = "review_continuity"
                else:
                    # Otherwise, move to the next scene or chapter
                    next_node = "advance_to_next_scene_or_chapter"
            
            # If we just did a continuity review, now we can advance
            elif last_node == "review_continuity":
                next_node = "advance_to_next_scene_or_chapter"
            
            # Default to writing the next scene
            else:
                next_node = "write_scene"
    
    # Safety check - if we somehow haven't set a next node, default to compile_final_story
    if not next_node:
        print("WARNING: No next node determined. Terminating execution.")
        state["completed"] = True
        next_node = "compile_final_story"
    
    return {"next": next_node}

# Build the graph
def build_story_graph():
    """Build and compile the story generation graph."""
    # Create a state graph
    graph_builder = StateGraph(StoryState)
    
    # Add nodes
    graph_builder.add_node("initialize_state", initialize_state)
    graph_builder.add_node("brainstorm_story_concepts", brainstorm_story_concepts)
    graph_builder.add_node("generate_story_outline", generate_story_outline)
    graph_builder.add_node("generate_characters", generate_characters)
    graph_builder.add_node("plan_chapters", plan_chapters)
    graph_builder.add_node("brainstorm_scene_elements", brainstorm_scene_elements)
    graph_builder.add_node("write_scene", write_scene)
    graph_builder.add_node("reflect_on_scene", reflect_on_scene)
    graph_builder.add_node("revise_scene_if_needed", revise_scene_if_needed)
    graph_builder.add_node("update_character_profiles", update_character_profiles)
    graph_builder.add_node("review_continuity", review_continuity)
    graph_builder.add_node("advance_to_next_scene_or_chapter", advance_to_next_scene_or_chapter)
    graph_builder.add_node("compile_final_story", compile_final_story)
    graph_builder.add_node("router", router)
    
    # Add edges
    graph_builder.add_edge(START, "initialize_state")
    graph_builder.add_edge("initialize_state", "router")
    graph_builder.add_edge("brainstorm_story_concepts", "generate_story_outline")
    graph_builder.add_edge("generate_story_outline", "generate_characters")
    graph_builder.add_edge("generate_characters", "plan_chapters")
    graph_builder.add_edge("plan_chapters", "router")
    graph_builder.add_edge("brainstorm_scene_elements", "write_scene")
    graph_builder.add_edge("write_scene", "router")
    graph_builder.add_edge("reflect_on_scene", "revise_scene_if_needed")
    graph_builder.add_edge("revise_scene_if_needed", "router")
    graph_builder.add_edge("update_character_profiles", "router")
    graph_builder.add_edge("review_continuity", "router")
    graph_builder.add_edge("advance_to_next_scene_or_chapter", "router")
    graph_builder.add_edge("compile_final_story", END)
    
    # Add conditional edge for routing based on the 'next' field in router output
    def route_to_next_node(state):
        return state["next"]
        
    graph_builder.add_conditional_edges(
        "router",
        route_to_next_node,
        {
            "brainstorm_story_concepts": "brainstorm_story_concepts",
            "generate_story_outline": "generate_story_outline",
            "generate_characters": "generate_characters",
            "plan_chapters": "plan_chapters",
            "brainstorm_scene_elements": "brainstorm_scene_elements",
            "write_scene": "write_scene",
            "reflect_on_scene": "reflect_on_scene",
            "revise_scene_if_needed": "revise_scene_if_needed",
            "update_character_profiles": "update_character_profiles",
            "review_continuity": "review_continuity",
            "advance_to_next_scene_or_chapter": "advance_to_next_scene_or_chapter",
            "compile_final_story": "compile_final_story"
        }
    )
    
    # Build and compile the graph - we don't need a checkpointer for basic usage
    graph = graph_builder.compile()
    
    return graph

# Create a function to run the story generation
def generate_story(genre: str = "fantasy", tone: str = "epic", author: str = ""):
    """
    Generate a complete story using the StoryCraft agent.
    
    Args:
        genre: The genre of the story (e.g., fantasy, sci-fi, mystery)
        tone: The tone of the story (e.g., epic, dark, humorous)
        author: Optional author whose style to emulate (e.g., Tolkien, Rowling, Martin)
    """
    # Build the graph
    graph = build_story_graph()
    
    # Initial user prompt
    author_str = f", Author Style: {author}" if author else ""
    user_message = f"Please write a story for me. Genre: {genre}, Tone: {tone}{author_str}"
    
    # Configure the thread
    config = {"configurable": {"thread_id": "story-generation-thread"}}
    
    # Get author style guidance if an author is specified
    author_style_guidance = ""
    if author:
        # Try to retrieve from memory first
        author_guidance = search_memory_tool.invoke({
            "query": f"writing style of {author}",
            "namespace": MEMORY_NAMESPACE
        })
        
        if not author_guidance:
            # Generate new author style guidance
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
        else:
            # Use the retrieved guidance
            author_style_guidance = author_guidance
    
    # Run the graph
    result = graph.invoke(
        {
            "messages": [HumanMessage(content=user_message)],
            "genre": "",
            "tone": "",
            "author": author,
            "author_style_guidance": author_style_guidance,
            "global_story": "",
            "chapters": {},
            "characters": {},
            "revelations": {},
            "creative_elements": {},  # Initialize creative elements field
            "current_chapter": "",
            "current_scene": "",
            "completed": False,
            "last_node": ""
        },
        config
    )
    
    # Try to retrieve the complete story using semantic search first
    complete_story = search_memory(query="complete final story with all chapters and scenes", namespace=MEMORY_NAMESPACE)
    
    # If semantic search doesn't yield good results, try direct key lookup
    if not complete_story or complete_story.strip() == "":
        try:
            complete_story = manage_memory_tool.invoke({
                "action": "get",
                "key": "complete_story",
                "namespace": MEMORY_NAMESPACE
            }).get("value", "")
        except Exception:
            complete_story = ""
            
    # If direct key also fails, try searching for chapters and compile them
    if not complete_story or complete_story.strip() == "":
        try:
            # Search for chapters using semantic search
            chapter_results = search_memory(query="chapter content scenes story", namespace=MEMORY_NAMESPACE)
            
            if chapter_results:
                # This is a simplified approach - in a real implementation,
                # you'd parse the results more carefully
                return f"Story generated but not fully compiled. Found partial content: {chapter_results[:1000]}..."
            else:
                return "Story generation in progress or not completed yet."
        except Exception as e:
            return f"Error retrieving story: {str(e)}"
    
    return complete_story

# If run directly, generate a story
if __name__ == "__main__":
    # dotenv is already loaded at the module level
    import argparse
    from storyteller_lib.config import setup_cache
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Generate a story using the StoryCraft agent")
    parser.add_argument("--genre", type=str, default="fantasy", 
                      help="Genre of the story (e.g., fantasy, sci-fi, mystery)")
    parser.add_argument("--tone", type=str, default="epic", 
                      help="Tone of the story (e.g., epic, dark, humorous)")
    parser.add_argument("--author", type=str, default="", 
                      help="Author whose style to emulate (e.g., Tolkien, Rowling, Martin)")
    parser.add_argument("--cache", type=str, choices=["memory", "sqlite", "none"], default="sqlite",
                      help="LLM cache type to use (default: sqlite)")
    args = parser.parse_args()
    
    # Check if API key is set
    if not os.environ.get("OPENAI_API_KEY"):
        print("Please set your OPENAI_API_KEY in your .env file")
        exit(1)
    
    # Set up caching
    cache = setup_cache(args.cache)
    print(f"LLM caching: {args.cache}")
        
    # Generate a story with the specified parameters
    story = generate_story(genre=args.genre, tone=args.tone, author=args.author)
    print(story)