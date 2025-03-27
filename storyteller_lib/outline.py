"""
StoryCraft Agent - Story outline and planning nodes.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from storyteller_lib.config import llm, manage_memory_tool, search_memory_tool, MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from storyteller_lib.creative_tools import parse_json_with_langchain
from storyteller_lib import track_progress

@track_progress
def generate_story_outline(state: StoryState) -> Dict:
    """Generate the overall story outline using the hero's journey structure."""
    genre = state["genre"]
    tone = state["tone"]
    author = state["author"]
    initial_idea = state.get("initial_idea", "")
    initial_idea_elements = state.get("initial_idea_elements", {})
    author_style_guidance = state["author_style_guidance"]
    language = state.get("language", DEFAULT_LANGUAGE)
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
    # Prepare language guidance
    language_guidance = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_guidance = f"""
        LANGUAGE CONSIDERATIONS:
        This story will be written in {SUPPORTED_LANGUAGES[language.lower()]}.
        
        When creating the story outline:
        1. Use character names that are authentic and appropriate for {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures
        2. Include settings, locations, and cultural references that resonate with {SUPPORTED_LANGUAGES[language.lower()]}-speaking audiences
        3. Consider storytelling traditions, folklore elements, and narrative structures common in {SUPPORTED_LANGUAGES[language.lower()]} literature
        4. Incorporate cultural values, social dynamics, and historical contexts relevant to {SUPPORTED_LANGUAGES[language.lower()]}-speaking regions
        5. Ensure that idioms, metaphors, and symbolic elements will translate well to {SUPPORTED_LANGUAGES[language.lower()]}
        
        The story should feel authentic to readers of {SUPPORTED_LANGUAGES[language.lower()]} rather than like a translated work.
        """
    
    # Prepare enhanced initial idea guidance using structured elements
    idea_guidance = ""
    if initial_idea:
        # Extract structured elements for more detailed guidance
        setting = initial_idea_elements.get("setting", "Unknown")
        characters = initial_idea_elements.get("characters", [])
        plot = initial_idea_elements.get("plot", "Unknown")
        themes = initial_idea_elements.get("themes", [])
        genre_elements = initial_idea_elements.get("genre_elements", [])
        
        idea_guidance = f"""
        INITIAL STORY IDEA (HIGH PRIORITY):
        {initial_idea}
        
        This initial idea forms the foundation of the story. The outline should incorporate these key elements:
        
        1. SETTING: {setting}
           - This is the primary setting where the story takes place
           - Major events should occur within or be connected to this setting
           - Maintain consistency with this established setting
        
        2. MAIN CHARACTERS: {', '.join(characters) if characters else 'To be determined based on the initial idea'}
           - These characters should be central to the story
           - Their characteristics and roles should align with the initial idea
           - Preserve the essential nature of these characters
        
        3. CENTRAL PLOT: {plot}
           - This is the main storyline that drives the narrative
           - Other plot elements should support this central conflict
           - Maintain the core nature of this conflict
        
        4. THEMES: {', '.join(themes) if themes else 'To be determined based on the initial idea'}
           - These themes should be woven throughout the story
        
        5. GENRE ELEMENTS: {', '.join(genre_elements) if genre_elements else 'To be determined based on the initial idea'}
           - These elements should be incorporated to maintain genre consistency
        
        The hero's journey structure should be use to create a long version of this initial idea, not the other way around.
        If any conflict arises between the hero's journey structure and the initial idea, extend the initial idea as needed.
        
        FINAL CHECK: Before finalizing the outline, verify that the key elements from the initial idea and the hero's journey are present and well-integrated into the story.
        """
    
    # Prompt for story generation with emphasis on initial idea
    language_instruction = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_instruction = f"""
        !!!CRITICAL LANGUAGE INSTRUCTION!!!
        This outline MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL content - including the title, character descriptions, plot elements, and setting details - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
        DO NOT translate the hero's journey structure - create the outline directly in {SUPPORTED_LANGUAGES[language.lower()]}.
        
        I will verify that your response is completely in {SUPPORTED_LANGUAGES[language.lower()]} and reject any outline that contains English.
        """
    
    prompt = f"""
    {language_instruction}
    
    Create a compelling story outline for a {tone} {genre} narrative following the hero's journey structure.
    {f"This story should be based on this initial idea: '{initial_idea}'" if initial_idea else ""}
    
    Include all major phases of the hero's journey, adapted to fit the initial idea:
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
    - A captivating title for the story that reflects the initial idea
    - 3-5 main characters with brief descriptions (include those specified in the initial idea)
    - A central conflict or challenge (aligned with the plot from the initial idea)
    - The world/setting of the story (consistent with the setting from the initial idea)
    - Key themes or messages (should include those from the initial idea)
    
    Format your response as a structured outline with clear sections.
    
    {language_instruction if language.lower() != DEFAULT_LANGUAGE else ""}
    
    VERIFICATION STEP: After completing the outline, review it to ensure that:
    1. The setting from the initial idea is well-integrated throughout
    2. The characters from the initial idea are included with appropriate roles
    3. The plot/conflict from the initial idea is central to the story
    4. The key elements from the initial idea are preserved and developed
    
    {idea_guidance}
    
    {creative_guidance}
    
    {style_guidance}
    
    {language_guidance}
    """
    
    # Generate the story outline
    story_outline = llm.invoke([HumanMessage(content=prompt)]).content
    # Perform multiple validation checks on the story outline
    validation_results = {}
    
    # Validate language if not English
    if language.lower() != DEFAULT_LANGUAGE:
        language_validation_prompt = f"""
        LANGUAGE VALIDATION: Check if this text is written entirely in {SUPPORTED_LANGUAGES[language.lower()]}.
        
        Text to validate:
        {story_outline}
        
        Provide:
        1. A YES/NO determination if the text is completely in {SUPPORTED_LANGUAGES[language.lower()]}
        2. If NO, identify which parts are not in {SUPPORTED_LANGUAGES[language.lower()]}
        3. A score from 1-10 on language authenticity (does it feel like it was written by a native speaker?)
        
        Your response should be in English for this validation only.
        """
        
        language_validation_result = llm.invoke([HumanMessage(content=language_validation_prompt)]).content
        validation_results["language"] = language_validation_result
        
        # Store the validation result in memory
        manage_memory_tool.invoke({
            "action": "create",
            "key": "outline_language_validation",
            "value": language_validation_result,
            "namespace": MEMORY_NAMESPACE
        })
    
    # 1. Validate that the outline adheres to the initial idea if one was provided
    if initial_idea and initial_idea_elements:
        idea_validation_prompt = f"""
        VALIDATION: Evaluate whether this story outline effectively incorporates the initial story idea:
        
        Initial Idea: "{initial_idea}"
        
        Key Elements to Check:
        - Setting: {initial_idea_elements.get('setting', 'Unknown')}
        - Characters: {', '.join(initial_idea_elements.get('characters', []))}
        - Plot: {initial_idea_elements.get('plot', 'Unknown')}
        - Themes: {', '.join(initial_idea_elements.get('themes', []))}
        - Genre Elements: {', '.join(initial_idea_elements.get('genre_elements', []))}
        
        Story Outline:
        {story_outline}
        
        VALIDATION CRITERIA:
        1. The setting should be consistent with what was specified in the initial idea
        2. The characters should maintain their essential nature and roles as described in the initial idea
        3. The plot should align with the central conflict described in the initial idea
        
        Provide:
        1. A score from 1-10 on how well the outline adheres to the initial idea
        2. An analysis of how well each key element is incorporated
        3. Specific feedback on what elements could be better integrated
        4. A YES/NO determination if the outline is acceptable
        
        If the score is below 8 or the determination is NO, provide specific guidance on how to improve it.
        """
        
        idea_validation_result = llm.invoke([HumanMessage(content=idea_validation_prompt)]).content
        validation_results["initial_idea"] = idea_validation_result
        
        # Store the validation result in memory
        manage_memory_tool.invoke({
            "action": "create",
            "key": "outline_idea_validation",
            "value": idea_validation_result,
            "namespace": MEMORY_NAMESPACE
        })
    
    # 2. Validate that the outline adheres to the specified genre
    genre_validation_prompt = f"""
    Evaluate whether this story outline properly adheres to the {genre} genre with a {tone} tone:
    
    Story Outline:
    {story_outline}
    
    Key elements that should be present in a {genre} story:
    """
    
    # Generate genre-specific validation criteria using the LLM
    from storyteller_lib.creative_tools import generate_genre_guidance
    
    # Extract just the bullet points from the genre guidance
    genre_guidance = generate_genre_guidance(genre, tone)
    
    # Extract the bullet points from the guidance
    if "Key elements that must be present" in genre_guidance:
        elements_section = genre_guidance.split("Key elements that must be present")[1]
        genre_validation_prompt += elements_section
    else:
        # Fallback if the format is unexpected
        genre_validation_prompt += f"""
        - Elements typical of {genre} stories
        - Appropriate pacing and structure for {genre}
        - Character types commonly found in {genre}
        - Themes and motifs associated with {genre}
        - Reader expectations for a {genre} story
        """
    
    genre_validation_prompt += f"""
    
    Tone considerations for a {tone} story:
    - Appropriate language and narrative style for {tone} tone
    - Consistent mood and atmosphere
    - Character interactions that reflect the {tone} tone
    
    Provide:
    1. A score from 1-10 on how well the outline adheres to the {genre} genre
    2. A score from 1-10 on how well the outline maintains a {tone} tone
    3. Specific feedback on what genre elements are missing or need adjustment
    4. A YES/NO determination if the outline is acceptable as a {genre} story with {tone} tone
    
    If either score is below 8 or the determination is NO, provide specific guidance on how to improve it.
    """
    
    genre_validation_result = llm.invoke([HumanMessage(content=genre_validation_prompt)]).content
    validation_results["genre"] = genre_validation_result
    
    # Store the validation result in memory
    manage_memory_tool.invoke({
        "action": "create",
        "key": "outline_genre_validation",
        "value": genre_validation_result,
        "namespace": MEMORY_NAMESPACE
    })
    
    # 3. Validate that the outline adheres to the specified setting if one was provided
    if initial_idea_elements and initial_idea_elements.get('setting'):
        setting = initial_idea_elements.get('setting')
        setting_validation_prompt = f"""
        Evaluate whether this story outline properly incorporates the required setting: "{setting}"
        
        Story Outline:
        {story_outline}
        
        A story set in "{setting}" should:
        - Have most or all scenes take place in this setting
        - Include details and descriptions specific to this setting
        - Have plot elements that naturally arise from or connect to this setting
        - Feature characters whose roles make sense within this setting
        
        Provide:
        1. A score from 1-10 on how well the outline incorporates the "{setting}" setting
        2. Specific feedback on how the setting is used or could be better utilized
        3. A YES/NO determination if the setting is adequately incorporated
        
        If the score is below 8 or the determination is NO, provide specific guidance on how to improve it.
        """
        
        setting_validation_result = llm.invoke([HumanMessage(content=setting_validation_prompt)]).content
        validation_results["setting"] = setting_validation_result
        
        # Store the validation result in memory
        manage_memory_tool.invoke({
            "action": "create",
            "key": "outline_setting_validation",
            "value": setting_validation_result,
            "namespace": MEMORY_NAMESPACE
        })
    # Determine if we need to regenerate the outline based on validation results
    needs_regeneration = False
    improvement_guidance = ""
    
    # Check language validation first if not English
    if language.lower() != DEFAULT_LANGUAGE and "language" in validation_results:
        result = validation_results["language"]
        if "NO" in result:
            needs_regeneration = True
            improvement_guidance += "LANGUAGE ISSUES:\n"
            improvement_guidance += "The outline must be written ENTIRELY in " + SUPPORTED_LANGUAGES[language.lower()] + ".\n"
            if "parts are not in" in result:
                parts_section = result.split("parts are not in")[1].strip() if "parts are not in" in result else ""
                improvement_guidance += "The following parts were not in the correct language: " + parts_section + "\n"
            improvement_guidance += "\n\n"
    
    # Check initial idea validation
    if "initial_idea" in validation_results:
        result = validation_results["initial_idea"]
        # Regenerate if score is below 8 or NO determination
        if "NO" in result or any(f"score: {i}" in result.lower() for i in range(1, 8)):
            needs_regeneration = True
            improvement_guidance += "INITIAL IDEA INTEGRATION ISSUES:\n"
            improvement_guidance += result.split("guidance on how to improve it")[-1].strip() if "guidance on how to improve it" in result else result
            improvement_guidance += "\n\n"
    
    # Check genre validation
    if "genre" in validation_results:
        result = validation_results["genre"]
        if "NO" in result or any(f"score: {i}" in result.lower() for i in range(1, 8)):
            needs_regeneration = True
            improvement_guidance += f"GENRE ({genre}) ISSUES:\n"
            improvement_guidance += result.split("guidance on how to improve it:")[-1].strip() if "guidance on how to improve it:" in result else result
            improvement_guidance += "\n\n"
    
    # Check setting validation
    if "setting" in validation_results:
        result = validation_results["setting"]
        if "NO" in result or any(f"score: {i}" in result.lower() for i in range(1, 8)):
            needs_regeneration = True
            improvement_guidance += "SETTING ISSUES:\n"
            improvement_guidance += result.split("guidance on how to improve it:")[-1].strip() if "guidance on how to improve it:" in result else result
            improvement_guidance += "\n\n"
    
    # If any validation failed, regenerate the outline
    if needs_regeneration:
        # Create a revised prompt with the improvement guidance
        language_instruction = ""
        if language.lower() != DEFAULT_LANGUAGE:
            language_instruction = f"""
            !!!CRITICAL LANGUAGE INSTRUCTION!!!
            This outline MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
            ALL content - including the title, character descriptions, plot elements, and setting details - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
            DO NOT translate the hero's journey structure - create the outline directly in {SUPPORTED_LANGUAGES[language.lower()]}.
            
            I will verify that your response is completely in {SUPPORTED_LANGUAGES[language.lower()]} and reject any outline that contains English.
            """
            
        revised_prompt = f"""
        {language_instruction}
        
        REVISION NEEDED: Your previous story outline needs improvement. Please revise it based on this feedback:
        
        AREAS NEEDING IMPROVEMENT:
        {improvement_guidance}
        
        Initial Idea: "{initial_idea}"
        
        KEY ELEMENTS TO INCORPORATE:
        - Setting: {initial_idea_elements.get('setting', 'Unknown') if initial_idea_elements else 'Not specified'}
           * This setting should be the primary location of the story
           * Ensure the setting is well-integrated throughout the narrative
        
        - Characters: {', '.join(initial_idea_elements.get('characters', [])) if initial_idea_elements else 'Not specified'}
           * These characters should be central to the story
           * Maintain their essential nature and roles as described
        
        - Plot: {initial_idea_elements.get('plot', 'Unknown') if initial_idea_elements else 'Not specified'}
           * This plot should be the central conflict
           * Ensure the story revolves around this core conflict
        - Themes: {', '.join(initial_idea_elements.get('themes', [])) if initial_idea_elements else 'Not specified'}
        - Genre Elements: {', '.join(initial_idea_elements.get('genre_elements', [])) if initial_idea_elements else 'Not specified'}
        
        Genre Requirements: This MUST be a {genre} story with a {tone} tone.
        
        {language_instruction if language.lower() != DEFAULT_LANGUAGE else ""}
        
        {prompt}
        """
        
        # Regenerate the outline
        story_outline = llm.invoke([HumanMessage(content=revised_prompt)]).content
        # Perform a final verification check to ensure the regenerated outline meets the requirements
        final_verification_prompt = f"""
        VERIFICATION CHECK: Evaluate whether this revised story outline meets all requirements.
        
        Initial Idea: "{initial_idea}"
        
        Key Elements:
        - Setting: {initial_idea_elements.get('setting', 'Unknown') if initial_idea_elements else 'Not specified'}
        - Characters: {', '.join(initial_idea_elements.get('characters', [])) if initial_idea_elements else 'Not specified'}
        - Plot: {initial_idea_elements.get('plot', 'Unknown') if initial_idea_elements else 'Not specified'}
        
        Revised Story Outline:
        {story_outline}
        
        Check the following:
        1. Does the outline effectively incorporate the initial idea? (YES/NO)
        2. Does the outline adhere to the {genre} genre with a {tone} tone? (YES/NO)
        {f'3. Is the outline written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]} without any English text? (YES/NO)' if language.lower() != DEFAULT_LANGUAGE else ''}
        
        Provide a YES/NO determination for each question.
        If any answer is NO, specify what still needs improvement.
        If NO, specify what still needs improvement.
        """
        
        final_verification_result = llm.invoke([HumanMessage(content=final_verification_prompt)]).content
        # If the outline still doesn't meet requirements, try one more time with additional guidance
        if "NO" in final_verification_result:
            language_instruction = ""
            if language.lower() != DEFAULT_LANGUAGE:
                language_instruction = f"""
                !!!CRITICAL LANGUAGE INSTRUCTION!!!
                This outline MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
                ALL content - including the title, character descriptions, plot elements, and setting details - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
                DO NOT translate the hero's journey structure - create the outline directly in {SUPPORTED_LANGUAGES[language.lower()]}.
                
                I will verify that your response is completely in {SUPPORTED_LANGUAGES[language.lower()]} and reject any outline that contains English.
                """
                
            final_attempt_prompt = f"""
            {language_instruction}
            
            FINAL REVISION NEEDED:
            
            The story outline still needs improvement:
            
            Initial Idea: "{initial_idea}"
            
            What still needs improvement:
            {final_verification_result}
            
            Please create an outline that:
            1. Uses "{initial_idea_elements.get('setting', 'Unknown')}" as the primary setting
            2. Features "{', '.join(initial_idea_elements.get('characters', []))}" as central characters
            3. Centers around "{initial_idea_elements.get('plot', 'Unknown')}" as the main conflict
            4. Adheres to the {genre} genre with a {tone} tone
            {f'5. Is written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]} without ANY English text' if language.lower() != DEFAULT_LANGUAGE else ''}
            
            Maintain the essence of the initial idea while crafting a compelling narrative.
            
            {language_instruction if language.lower() != DEFAULT_LANGUAGE else ""}
            Maintain the essence of the initial idea while crafting a compelling narrative.
            """
            
            # Final regeneration attempt
            story_outline = llm.invoke([HumanMessage(content=final_attempt_prompt)]).content
        
        # Store the revised outline
        manage_memory_tool.invoke({
            "action": "create",
            "key": "story_outline_revised",
            "value": story_outline,
            "namespace": MEMORY_NAMESPACE
        })
        
        # Store the combined validation results
        manage_memory_tool.invoke({
            "action": "create",
            "key": "outline_validation_combined",
            "value": {
                "initial_validation": validation_results,
                "improvement_guidance": improvement_guidance,
                "final_verification": final_verification_result,
                "regenerated": True
            },
            "namespace": MEMORY_NAMESPACE
        })
        
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
            "method": "hero's_journey_structure",
            "initial_idea_used": bool(initial_idea),
            "validation_performed": bool(initial_idea and initial_idea_elements)
        }
    })
    
    # Update the state
    
    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]
    
    # Create message for the user
    idea_mention = f" based on your idea about {initial_idea_elements.get('setting', 'the specified setting')}" if initial_idea else ""
    new_msg = AIMessage(content=f"I've created a story outline following the hero's journey structure{idea_mention}. Now I'll develop the characters in more detail.")
    
    return {
        "global_story": story_outline,
        "messages": [
            *[RemoveMessage(id=msg_id) for msg_id in message_ids],
            new_msg
        ]
    }


    
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class Scene(BaseModel):
    """Simple model for a scene in a chapter."""
    description: str = Field(..., description="Brief description of what happens in this scene")

class Chapter(BaseModel):
    """Simple model for a chapter in the story."""
    number: str = Field(..., description="The chapter number (as a string)")
    title: str = Field(..., description="The title of the chapter")
    outline: str = Field(..., description="Detailed summary of the chapter (200-300 words)")
    key_scenes: List[Scene] = Field(..., description="List of key scenes in this chapter")

class ChapterPlan(BaseModel):
    """Simple model for the entire chapter plan."""
    chapters: List[Chapter] = Field(..., description="List of chapters in the story")

@track_progress
def plan_chapters(state: StoryState) -> Dict:
    """Divide the story into chapters with detailed outlines."""
    global_story = state["global_story"]
    characters = state["characters"]
    genre = state["genre"]
    tone = state["tone"]
    language = state.get("language", DEFAULT_LANGUAGE)
    # Prepare language instruction and guidance
    language_instruction = ""
    language_guidance = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_instruction = f"""
        !!!CRITICAL LANGUAGE INSTRUCTION!!!
        This chapter plan MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL content - including chapter titles, summaries, scene descriptions, and character development - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
        DO NOT translate the hero's journey structure - create the chapter plan directly in {SUPPORTED_LANGUAGES[language.lower()]}.
        
        I will verify that your response is completely in {SUPPORTED_LANGUAGES[language.lower()]} and reject any plan that contains English.
        """
        
        language_guidance = f"""
        CHAPTER LANGUAGE CONSIDERATIONS:
        Plan chapters appropriate for a story written in {SUPPORTED_LANGUAGES[language.lower()]}.
        
        1. Use chapter titles that resonate with {SUPPORTED_LANGUAGES[language.lower()]}-speaking audiences
        2. Include settings, locations, and cultural references authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking regions
        3. Consider storytelling traditions, pacing, and narrative structures common in {SUPPORTED_LANGUAGES[language.lower()]} literature
        4. Incorporate cultural events, holidays, or traditions relevant to {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures when appropriate
        5. Ensure that scenes reflect social norms, customs, and daily life authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking societies
        
        The chapter structure should feel natural to {SUPPORTED_LANGUAGES[language.lower()]}-speaking readers rather than like a translated work.
        """
    
    # Prompt for chapter planning
    prompt = f"""
    {language_instruction if language.lower() != DEFAULT_LANGUAGE else ""}
    
    Based on this story outline:
    
    {global_story}
    
    And these characters:
    
    {characters}
    
    Create a plan for 8-15 chapters that cover the entire hero's journey for this {tone} {genre} story.
    IMPORTANT: THERE SHOULD NEVER BE LESS THAN 8 CHAPTERS. A COMPLETE STORY REQUIRES AT LEAST 8 CHAPTERS TO PROPERLY DEVELOP.
    
    For each chapter, provide:
    1. Chapter number and title
    2. A summary of major events (200-300 words)
    3. Which characters appear and how they develop
    4. 3-6 key scenes that should be included
    5. Any major revelations or plot twists
    
    Ensure the chapters flow logically and maintain the arc of the hero's journey.
    
    {language_guidance}
    
    {language_instruction if language.lower() != DEFAULT_LANGUAGE else ""}
    {language_guidance}
    """
    # Generate chapter plan
    chapter_plan_text = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Validate language if not English
    if language.lower() != DEFAULT_LANGUAGE:
        language_validation_prompt = f"""
        LANGUAGE VALIDATION: Check if this text is written entirely in {SUPPORTED_LANGUAGES[language.lower()]}.
        
        Text to validate:
        {chapter_plan_text}
        
        Provide:
        1. A YES/NO determination if the text is completely in {SUPPORTED_LANGUAGES[language.lower()]}
        2. If NO, identify which parts are not in {SUPPORTED_LANGUAGES[language.lower()]}
        3. A score from 1-10 on language authenticity (does it feel like it was written by a native speaker?)
        
        Your response should be in English for this validation only.
        """
        
        language_validation_result = llm.invoke([HumanMessage(content=language_validation_prompt)]).content
        
        # Store the validation result in memory
        manage_memory_tool.invoke({
            "action": "create",
            "key": "chapter_plan_language_validation",
            "value": language_validation_result,
            "namespace": MEMORY_NAMESPACE
        })
        
        # If language validation fails, regenerate with stronger language instruction
        if "NO" in language_validation_result:
            stronger_language_instruction = f"""
            !!!CRITICAL LANGUAGE INSTRUCTION - PREVIOUS ATTEMPT FAILED!!!
            
            Your previous response contained English text. This is NOT acceptable.
            
            This chapter plan MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
            ALL content - including chapter titles, summaries, scene descriptions, and character development - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
            DO NOT translate the hero's journey structure - create the chapter plan directly in {SUPPORTED_LANGUAGES[language.lower()]}.
            
            I will verify that your response is completely in {SUPPORTED_LANGUAGES[language.lower()]} and reject any plan that contains English.
            
            The following parts were not in {SUPPORTED_LANGUAGES[language.lower()]}:
            {language_validation_result.split("which parts are not in")[1].strip() if "which parts are not in" in language_validation_result else "Some parts of the text"}
            """
            
            # Regenerate with stronger language instruction
            revised_prompt = f"""
            {stronger_language_instruction}
            
            {prompt}
            
            {stronger_language_instruction}
            """
            
            chapter_plan_text = llm.invoke([HumanMessage(content=revised_prompt)]).content
    
    # Use direct LLM structured output with simplified Pydantic model
    try:
        # Create a structured output prompt that explicitly asks for chapter data with scenes
        structured_prompt = f"""
        Based on the chapter plan you've created, I need you to extract a list of chapters with their key scenes.
        
        For each chapter, provide:
        1. The chapter number (as a string)
        2. A title
        3. A detailed outline (200-300 words)
        4. 3-5 key scenes that should be included in this chapter (with a brief description for each)
        
        For the key scenes, focus on the most important moments that advance the plot or develop characters.
        
        Format your response as a list of chapters, each with these properties.
        
        Chapter plan:
        {chapter_plan_text}
        """
        
        # Use LLM with structured output directly
        structured_output_llm = llm.with_structured_output(ChapterPlan)
        
        # Get structured output
        result = structured_output_llm.invoke(structured_prompt)
        
        # Convert the list of chapters to a dictionary with chapter numbers as keys
        chapters_dict = {}
        for chapter in result.chapters:
            chapter_num = chapter.number
            # Ensure chapter number is a string
            if not isinstance(chapter_num, str):
                chapter_num = str(chapter_num)
                
            # Create a complete chapter entry with scenes from the key_scenes list
            chapter_entry = {
                "title": chapter.title,
                "outline": chapter.outline,
                "scenes": {},
                "reflection_notes": []
            }
            
            # Add scenes from the key_scenes list
            for i, scene in enumerate(chapter.key_scenes, 1):
                scene_num = str(i)
                chapter_entry["scenes"][scene_num] = {
                    "content": "",  # Content will be filled in later
                    "description": scene.description,  # Store the scene description
                    "reflection_notes": []
                }
            
            # Ensure at least 3 scenes
            for i in range(len(chapter.key_scenes) + 1, 4):
                scene_num = str(i)
                chapter_entry["scenes"][scene_num] = {
                    "content": "",
                    "description": f"Additional scene for chapter {chapter_num}",
                    "reflection_notes": []
                }
            
            chapters_dict[chapter_num] = chapter_entry
        
        # Use the dictionary as our chapters
        chapters = chapters_dict
        
        # If we don't have enough chapters, create empty ones
        if len(chapters) < 8:
            print(f"Only {len(chapters)} chapters were generated. Adding empty chapters to reach at least 8.")
            for i in range(1, 9):
                chapter_num = str(i)
                if chapter_num not in chapters:
                    chapters[chapter_num] = {
                        "title": f"Chapter {i}",
                        "outline": f"Events of chapter {i}",
                        "scenes": {
                            "1": {"content": "", "description": f"First scene of chapter {i}", "reflection_notes": []},
                            "2": {"content": "", "description": f"Second scene of chapter {i}", "reflection_notes": []},
                            "3": {"content": "", "description": f"Third scene of chapter {i}", "reflection_notes": []}
                        },
                        "reflection_notes": []
                    }
    except Exception as e:
        print(f"Error generating chapter data with Pydantic: {str(e)}")
        
        # If structured output fails, try to parse the text directly
        try:
            # Create empty chapters dictionary
            chapters = {}
            
            # Parse the chapter plan text to extract chapters
            import re
            
            # Look for chapter patterns like "Chapter 1:", "Chapter One:", etc.
            chapter_matches = re.finditer(r'(?:Chapter|Kapitel|Chapitre)\s+(\d+|[A-Za-z]+)[:\s-]+([^\n]+)', chapter_plan_text)
            
            current_chapter = None
            current_outline = []
            
            lines = chapter_plan_text.split('\n')
            for i, line in enumerate(lines):
                # Check if this line starts a new chapter
                match = re.match(r'(?:Chapter|Kapitel|Chapitre)\s+(\d+|[A-Za-z]+)[:\s-]+([^\n]+)', line)
                if match:
                    # If we were processing a previous chapter, save it
                    if current_chapter:
                        chapter_num = current_chapter['number']
                        chapters[chapter_num] = {
                            "title": current_chapter['title'],
                            "outline": '\n'.join(current_outline),
                            "scenes": {
                                "1": {"content": "", "description": f"First scene of chapter {chapter_num}", "reflection_notes": []},
                                "2": {"content": "", "description": f"Second scene of chapter {chapter_num}", "reflection_notes": []},
                                "3": {"content": "", "description": f"Third scene of chapter {chapter_num}", "reflection_notes": []}
                            },
                            "reflection_notes": []
                        }
                    
                    # Start a new chapter
                    chapter_num = match.group(1)
                    # Convert word numbers to digits if needed
                    if chapter_num.lower() == 'one': chapter_num = '1'
                    elif chapter_num.lower() == 'two': chapter_num = '2'
                    elif chapter_num.lower() == 'three': chapter_num = '3'
                    elif chapter_num.lower() == 'four': chapter_num = '4'
                    elif chapter_num.lower() == 'five': chapter_num = '5'
                    elif chapter_num.lower() == 'six': chapter_num = '6'
                    elif chapter_num.lower() == 'seven': chapter_num = '7'
                    elif chapter_num.lower() == 'eight': chapter_num = '8'
                    elif chapter_num.lower() == 'nine': chapter_num = '9'
                    elif chapter_num.lower() == 'ten': chapter_num = '10'
                    
                    current_chapter = {
                        'number': chapter_num,
                        'title': match.group(2).strip()
                    }
                    current_outline = []
                else:
                    # Add this line to the current chapter's outline
                    if current_chapter and line.strip():
                        current_outline.append(line.strip())
            
            # Don't forget to save the last chapter
            if current_chapter:
                chapter_num = current_chapter['number']
                chapters[chapter_num] = {
                    "title": current_chapter['title'],
                    "outline": '\n'.join(current_outline),
                    "scenes": {
                        "1": {"content": "", "description": f"First scene of chapter {chapter_num}", "reflection_notes": []},
                        "2": {"content": "", "description": f"Second scene of chapter {chapter_num}", "reflection_notes": []},
                        "3": {"content": "", "description": f"Third scene of chapter {chapter_num}", "reflection_notes": []}
                    },
                    "reflection_notes": []
                }
            
            # If we still don't have enough chapters, create empty ones
            if len(chapters) < 8:
                print(f"Only {len(chapters)} chapters were extracted. Adding empty chapters to reach at least 8.")
                for i in range(1, 9):
                    chapter_num = str(i)
                    if chapter_num not in chapters:
                        chapters[chapter_num] = {
                            "title": f"Chapter {i}",
                            "outline": f"Events of chapter {i}",
                            "scenes": {
                                "1": {"content": "", "description": f"First scene of chapter {i}", "reflection_notes": []},
                                "2": {"content": "", "description": f"Second scene of chapter {i}", "reflection_notes": []},
                                "3": {"content": "", "description": f"Third scene of chapter {i}", "reflection_notes": []}
                            },
                            "reflection_notes": []
                        }
        except Exception as e2:
            print(f"Error parsing chapter data directly: {str(e2)}")
            # Create empty chapters as a last resort
            chapters = {}
            for i in range(1, 9):
                chapters[str(i)] = {
                    "title": f"Chapter {i}",
                    "outline": f"Events of chapter {i}",
                    "scenes": {
                        "1": {"content": "", "description": f"First scene of chapter {i}", "reflection_notes": []},
                        "2": {"content": "", "description": f"Second scene of chapter {i}", "reflection_notes": []},
                        "3": {"content": "", "description": f"Third scene of chapter {i}", "reflection_notes": []}
                    },
                    "reflection_notes": []
                }
    
    # Validate the structure and ensure each chapter has the required fields
    for chapter_num, chapter in chapters.items():
        if "title" not in chapter:
            chapter["title"] = f"Chapter {chapter_num}"
        if "outline" not in chapter:
            chapter["outline"] = f"Events of chapter {chapter_num}"
        if "scenes" not in chapter:
            chapter["scenes"] = {
                "1": {"content": "", "description": f"First scene of chapter {chapter_num}", "reflection_notes": []},
                "2": {"content": "", "description": f"Second scene of chapter {chapter_num}", "reflection_notes": []}
            }
        if "reflection_notes" not in chapter:
            chapter["reflection_notes"] = []
            
        # Ensure all scenes have the required structure
        for scene_num, scene in chapter["scenes"].items():
            if "content" not in scene:
                scene["content"] = ""
            if "description" not in scene:
                scene["description"] = f"Scene {scene_num} of chapter {chapter_num}"
            if "reflection_notes" not in scene:
                scene["reflection_notes"] = []
    
    # Store chapter plans in memory
    for chapter_num, chapter_data in chapters.items():
        manage_memory_tool.invoke({
            "action": "create",
            "key": f"chapter_{chapter_num}",
            "value": chapter_data
        })
    
    # Get existing message IDs to delete
    message_ids = [msg.id for msg in state.get("messages", [])]
    
    # Create message for the user
    new_msg = AIMessage(content="I've planned out the chapters for the story. Now I'll begin writing the first scene of chapter 1.")
    
    return {
        "chapters": chapters,
        "current_chapter": "1",  # Start with the first chapter
        "current_scene": "1",    # Start with the first scene
        
        "messages": [
            *[RemoveMessage(id=msg_id) for msg_id in message_ids],
            new_msg
        ]
    }
