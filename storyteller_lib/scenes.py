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
    
    Identify:
    - Any new information revealed to the reader that should be tracked
    - Any character developments or relationship changes
    - Any inconsistencies or continuity errors (e.g., contradictions with previous scenes, plot holes)
    - Any areas that need improvement
    
    Set 'needs_revision' to true if ANY of these conditions are met:
    - Any criteria score is 5 or below
    - There are any continuity errors, character inconsistencies, or plot holes
    - There are multiple issues of any type
    - The overall quality of the scene is significantly below the standards of the story
    """
    
    # Instead of using structured output, let's use a more flexible approach with JSON parsing
    from storyteller_lib.creative_tools import parse_json_with_langchain
    
    # First, let's ensure our schema is clear in the prompt
    schema_description = """
    Schema:
    {
        "criteria_ratings": {
            "character_consistency": {"score": 1-10, "comments": "..."},
            "plot_advancement": {"score": 1-10, "comments": "..."},
            "writing_quality": {"score": 1-10, "comments": "..."},
            "tone_appropriateness": {"score": 1-10, "comments": "..."},
            "information_management": {"score": 1-10, "comments": "..."},
            "continuity": {"score": 1-10, "comments": "..."}
        },
        "issues": [
            {
                "type": "continuity_error|character_inconsistency|plot_hole|pacing_issue|tone_mismatch|other",
                "description": "...",
                "severity": 1-10,
                "recommendation": "..."
            }
        ],
        "strengths": ["...", "..."],
        "needs_revision": true|false,
        "revision_priority": "low|medium|high",
        "overall_assessment": "..."
    }
    """
    
    # Enhance the prompt to emphasize JSON output
    prompt_with_schema = f"""
    {prompt}
    
    Format your analysis as a valid JSON object following exactly this schema:
    {schema_description}
    
    Make sure to include ALL required fields and ensure your output is valid JSON.
    """
    
    # Generate the reflection using the LLM
    reflection_response = llm.invoke([HumanMessage(content=prompt_with_schema)]).content
    
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
    
    # Parse the JSON response
    try:
        # Use the parse_json_with_langchain function with our default as fallback
        reflection = parse_json_with_langchain(reflection_response, default_reflection)
        
        # Validate that all required fields are present, fill in defaults if missing
        for key in default_reflection:
            if key not in reflection or reflection[key] is None:
                reflection[key] = default_reflection[key]
                print(f"Warning: Missing '{key}' in reflection for Ch:{current_chapter}/Sc:{current_scene}, using default")
        
        # Additional logic to ensure needs_revision is set correctly based on criteria and issues
        # Check for low scores in criteria ratings
        low_criteria_scores = []
        for criteria_name, rating in reflection.get("criteria_ratings", {}).items():
            score = rating.get("score", 10)  # Default high if not specified
            if score <= 5:  # Score of 5 or lower indicates a problem
                low_criteria_scores.append(f"{criteria_name}: {score}/10")
        
        # Check for issues with high severity
        severe_issues = []
        for issue in reflection.get("issues", []):
            severity = issue.get("severity", 0)
            if severity >= 5:  # Severity of 5 or higher indicates a serious issue
                issue_type = issue.get("type", "unknown")
                severe_issues.append(f"{issue_type} (severity: {severity}/10)")
        
        # Set needs_revision to true if any low scores or severe issues exist
        if low_criteria_scores or severe_issues:
            if not reflection.get("needs_revision"):
                print(f"Overriding needs_revision to TRUE for Ch:{current_chapter}/Sc:{current_scene} due to:")
                if low_criteria_scores:
                    print(f"  - Low criteria scores: {', '.join(low_criteria_scores)}")
                if severe_issues:
                    print(f"  - Severe issues: {', '.join(severe_issues)}")
                reflection["needs_revision"] = True
                
                # Set appropriate revision priority based on severity
                if any(score <= 3 for criteria_name, rating in reflection.get("criteria_ratings", {}).items() 
                       if rating.get("score", 10) <= 3):
                    reflection["revision_priority"] = "high"
                else:
                    reflection["revision_priority"] = "medium"
        
        # Log success
        print(f"Successfully generated reflection for Ch:{current_chapter}/Sc:{current_scene}")
    except Exception as e:
        print(f"Error generating reflection for Ch:{current_chapter}/Sc:{current_scene}: {e}")
        print(f"Using default reflection data")
        reflection = default_reflection
    
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
    reflection_summary = reflection.get("overall_assessment", "No summary available")
    
    # Create a list of issues for quick reference
    issues_summary = []
    for issue in reflection.get("issues", []):
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
        "criteria_ratings": reflection.get("criteria_ratings", {}),
        "issues": reflection.get("issues", []),
        "strengths": reflection.get("strengths", []),
        "formatted_issues": issues_summary,  # For easy display
        "needs_revision": reflection.get("needs_revision", False),
        "revision_priority": reflection.get("revision_priority", "low"),
        "overall_assessment": reflection_summary
    }
    
    # Store the structured reflection in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": f"reflection_chapter_{current_chapter}_scene_{current_scene}",
        "value": reflection_formatted
    })
    
    # Store original reflection text for reference if it exists
    if "original_text" in reflection:
        manage_memory_tool.invoke({
            "action": "create",
            "key": f"reflection_text_chapter_{current_chapter}_scene_{current_scene}",
            "value": reflection["original_text"]
        })
    
    # Create readable reflection notes for the chapter data structure
    reflection_notes = [
        reflection_summary,
        "\n".join(issues_summary)
    ]
    
    # With our reducers, we can now be more declarative and specific about updates
    # Instead of copying the entire chapters dictionary, we just specify the updates
    
    # Update state with structured reflection data
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
        
        "messages": [AIMessage(content=f"I've analyzed scene {current_scene} of chapter {current_chapter} for quality and consistency.")]
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
            
            "messages": [AIMessage(content=f"Scene {current_scene} of Chapter {current_chapter} has already been revised {revision_count} times. No further revisions needed.")]
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
        
        # Return updates
        return {
            "chapters": {
                current_chapter: {
                    "scenes": scene_update
                }
            },
            "revision_count": revised_counts,  # Update the revision count in state
            "current_chapter": current_chapter,
            "current_scene": current_scene,
            
            "messages": [AIMessage(content=f"I've revised scene {current_scene} of chapter {current_chapter} to address the identified issues (revision #{revision_count + 1}).")]
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
            
            "messages": [AIMessage(content=f"Scene {current_scene} of chapter {current_chapter} is consistent and well-crafted, no revision needed.")]
        }