"""
StoryCraft Agent - Scene generation and management nodes.
"""

from typing import Dict

from storyteller_lib.config import llm, manage_memory_tool, search_memory_tool, MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
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
        print(f"[STORYTELLER] Using initial_idea from state in brainstorm_scene_elements: '{initial_idea}'")
        
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
    
    # Prepare language guidance
    language_section = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_section = f"""
        LANGUAGE CONSIDERATIONS:
        You are writing this scene in {SUPPORTED_LANGUAGES[language.lower()]}. Consider the following:
        
        1. Use dialogue, expressions, and idioms natural to {SUPPORTED_LANGUAGES[language.lower()]}-speaking characters
        2. Incorporate cultural references, settings, and descriptions authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking regions
        3. Consider social norms, customs, and interpersonal dynamics typical in {SUPPORTED_LANGUAGES[language.lower()]} culture
        4. Use narrative techniques, pacing, and stylistic elements common in {SUPPORTED_LANGUAGES[language.lower()]} literature
        5. Ensure names, places, and cultural elements are appropriate for {SUPPORTED_LANGUAGES[language.lower()]}-speaking audiences
        
        The scene should read as if it was originally written in {SUPPORTED_LANGUAGES[language.lower()]}, not translated.
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
    
    # Identify which characters are likely to appear in this scene based on the chapter outline
    scene_characters = []
    chapter_outline = chapter.get('outline', '')
    for char_name, char_data in characters.items():
        if char_name.lower() in chapter_outline.lower() or char_data.get('name', '').lower() in chapter_outline.lower():
            scene_characters.append(char_name)
    
    # If no characters were identified, include all characters
    if not scene_characters:
        scene_characters = list(characters.keys())
    
    # Create emotional guidance based on character arcs and inner conflicts
    emotional_guidance = f"""
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
    
    {emotional_guidance}
    
    Your task is to write an engaging, vivid scene of 500-800 words that advances the story according to the chapter outline.
    Use rich descriptions, meaningful dialogue, and show character development.
    Ensure consistency with established character traits and previous events.
    
    Make sure to incorporate the brainstormed creative elements in compelling ways that enhance the scene.
    Use unexpected elements and surprising twists to keep readers engaged while maintaining narrative coherence.
    
    Write the scene in third-person perspective with a {tone} style appropriate for {genre} fiction.
    {style_section}
    {language_section}
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
    
    # Prompt for structured reflection
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
    
    Evaluate the scene on these criteria and include in criteria_ratings:
    - character_consistency: Consistency with established character traits and motivations
    - plot_advancement: Advancement of the plot according to the chapter outline
    - writing_quality: Quality of writing (descriptions, dialogue, pacing)
    - tone_appropriateness: Tone and style appropriateness
    - information_management: Information management (revelations and secrets)
    - continuity: Continuity with previous scenes and the overall story arc
    - emotional_depth: Depth and authenticity of emotional content and resonance
    - character_relatability: How relatable and human the characters feel to readers
    - inner_conflict_development: Development of characters' inner struggles and dilemmas
    
    Identify:
    - Any new information revealed to the reader that should be tracked
    - Any character developments or relationship changes
    - Any emotional developments or shifts in characters
    - Any progress in character arcs or inner conflicts
    - Any inconsistencies or continuity errors (e.g., contradictions with previous scenes, plot holes)
    - Any areas that need improvement in emotional depth or character development
    - Any areas that need improvement
    
    Set 'needs_revision' to true if ANY of these conditions are met:
    - Any criteria score is 5 or below
    - There are any continuity errors, character inconsistencies, or plot holes
    - There are multiple issues of any type
    - The overall quality of the scene is significantly below the standards of the story
    """
    
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
            description="Type of issue (continuity_error, character_inconsistency, plot_hole, pacing_issue, tone_mismatch, other)"
        )
        description: str = Field(default="", description="Description of the issue")
        severity: int = Field(ge=1, le=10, default=5, description="Severity from 1-10")
        recommendation: str = Field(default="", description="Recommendation to fix the issue")
        
        class Config:
            """Configuration for the model."""
            extra = "ignore"  # Ignore extra fields
    
    class SceneReflection(BaseModel):
        """Reflection on a scene's quality and issues."""
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
    revelation_prompt = f"""
    Based on this scene:
    
    {scene_content}
    
    Extract a list of any new information revealed to the reader that wasn't known before.
    Each item should be a specific fact or revelation that's now known to the reader.
    Format as a simple bulleted list.
    """
    
    # Get new revelations
    new_revelations_text = llm.invoke([HumanMessage(content=revelation_prompt)]).content
    
    # Convert to list (simplified)
    new_revelations = [line.strip().replace("- ", "") for line in new_revelations_text.split("\n") if line.strip().startswith("- ")]
    
    # Update revelations in state
    updated_revelations = state["revelations"].copy()
    updated_revelations["reader"] = updated_revelations.get("reader", []) + new_revelations
    # Create a summary of the reflection for display
    reflection_summary = reflection_dict.get("overall_assessment", "No summary available")
    
    # Create a list of issues for quick reference
    issues_summary = []
    for issue in reflection_dict.get("issues", []):
        issue_type = issue.get("type", "unknown")
        description = issue.get("description", "No description")
        severity = issue.get("severity", 0)
        issues_summary.append(f"{issue_type.upper()} (Severity: {severity}/10): {description}")
    
    # If no issues were found, note that
    if not issues_summary:
        issues_summary.append("No significant issues detected")
    
    # Format for storage - now we store the entire structured reflection directly
    # since we're using proper structured output
    reflection_formatted = {
        "criteria_ratings": reflection_dict.get("criteria_ratings", {}),
        "issues": reflection_dict.get("issues", []),
        "strengths": reflection_dict.get("strengths", []),
        "formatted_issues": issues_summary,  # For easy display
        "needs_revision": reflection_dict.get("needs_revision", False),
        "revision_priority": reflection_dict.get("revision_priority", "low"),
        "overall_assessment": reflection_summary
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
    
    return {
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
            AIMessage(content=f"I've analyzed scene {current_scene} of chapter {current_chapter} for quality and consistency.")
        ]
    }

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
    
    # Default to not needing revision if we've revised twice already
    if revision_count >= 2:
        print(f"Scene {current_scene} of Chapter {current_chapter} has been revised {revision_count} times. No further revisions will be made.")
        needs_revision = False
        return {
            "current_chapter": current_chapter,
            "current_scene": current_scene,
            
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content=f"Scene {current_scene} of Chapter {current_chapter} has already been revised {revision_count} times. No further revisions needed.")
            ]
        }
    
    # Use the structured data's explicit needs_revision flag
    needs_revision = structured_reflection.get("needs_revision", False)
    revision_priority = structured_reflection.get("revision_priority", "low")
    issues = structured_reflection.get("issues", [])
    
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
            print(f"  {idx+1}. {issue_type.upper()} (Severity: {severity}/10): {description[:100]}...")
    
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
        
        YOUR REVISION TASK:
        1. Rewrite the scene to address ALL identified issues, especially those marked with higher severity.
        2. Ensure consistency with previous events, character traits, and established facts.
        3. Maintain the same general plot progression and purpose of the scene.
        4. Improve the quality, style, and flow as needed.
        5. Ensure no NEW continuity errors are introduced.
        
        Provide a complete, polished scene that can replace the original.
        """
        
        # Generate revised scene
        revised_scene = llm.invoke([HumanMessage(content=prompt)]).content
        
        # Increment revision count
        revised_counts[f"{current_chapter}_{current_scene}"] = revision_count + 1
        
        # Store revision information in memory
        manage_memory_tool.invoke({
            "action": "create",
            "key": f"chapter_{current_chapter}_scene_{current_scene}_revision_reason",
            "value": {
                "structured_reflection": structured_reflection,
                "revision_number": revision_count + 1,
                "timestamp": "now"
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
                "structured_reflection": None  # Clear structured reflection to trigger fresh analysis
            }
        }
        
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
            
            # Add memory tracking
            "memory_usage": {
                f"revise_scene_{current_chapter}_{current_scene}": {
                    "timestamp": "now",
                    "original_size": len(scene_content) if scene_content else 0,
                    "revised_size": len(revised_scene) if revised_scene else 0,
                    "revision_number": revision_count + 1
                }
            },
            
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content=f"I've revised scene {current_scene} of chapter {current_chapter} to address the identified issues (revision #{revision_count + 1}).")
            ]
        }
    else:
        # No revision needed
        manage_memory_tool.invoke({
            "action": "create",
            "key": f"chapter_{current_chapter}_scene_{current_scene}_revision_status",
            "value": "No revision needed - scene approved"
        })
        
        return {
            "current_chapter": current_chapter,
            "current_scene": current_scene,
            
            "messages": [
                *[RemoveMessage(id=msg.id) for msg in state.get("messages", [])],
                AIMessage(content=f"Scene {current_scene} of chapter {current_chapter} is consistent and well-crafted, no revision needed.")
            ]
        }