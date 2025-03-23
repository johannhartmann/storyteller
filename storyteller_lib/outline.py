"""
StoryCraft Agent - Story outline and planning nodes.
"""

from typing import Dict

from storyteller_lib.config import llm, manage_memory_tool, MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
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
        
        The hero's journey structure should be adapted to fit this initial idea, not the other way around.
        If any conflict arises between the hero's journey structure and the initial idea, prioritize the initial idea.
        
        FINAL CHECK: Before finalizing the outline, verify that the key elements from the initial idea are present and well-integrated into the story.
        """
    
    # Prompt for story generation with emphasis on initial idea
    prompt = f"""
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
    
    # Add genre-specific elements based on the genre
    if genre.lower() == "mystery":
        genre_validation_prompt += """
        - A central mystery or puzzle to be solved
        - Clues and red herrings
        - Investigation and deduction
        - Suspects with motives, means, and opportunities
        - A resolution that explains the mystery
        """
    elif genre.lower() == "fantasy":
        genre_validation_prompt += """
        - Magical or supernatural elements
        - Worldbuilding with consistent rules
        - Fantastical creatures or beings
        - Epic conflicts or quests
        - Themes of good vs. evil, power, or destiny
        """
    elif genre.lower() == "sci-fi" or genre.lower() == "science fiction":
        genre_validation_prompt += """
        - Scientific or technological concepts
        - Futuristic or alternative settings
        - Exploration of the impact of science/technology on society
        - Speculative elements based on scientific principles
        - Themes of progress, ethics, or humanity's future
        """
    elif genre.lower() == "romance":
        genre_validation_prompt += """
        - Focus on a developing relationship between characters
        - Emotional connection and attraction
        - Obstacles to the relationship
        - Character growth through the relationship
        - Satisfying emotional resolution
        """
    elif genre.lower() == "horror":
        genre_validation_prompt += """
        - Elements designed to frighten or disturb
        - Building tension and suspense
        - Threats to characters' safety or sanity
        - Atmosphere of dread or unease
        - Exploration of fears and taboos
        """
    elif genre.lower() == "thriller":
        genre_validation_prompt += """
        - High stakes and tension
        - Danger and time pressure
        - Complex plot with twists
        - Protagonist facing formidable opposition
        - Themes of survival, justice, or moral dilemmas
        """
    else:
        # Generic genre guidance for other genres
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
    
    # Check initial idea validation
    if "initial_idea" in validation_results:
        result = validation_results["initial_idea"]
        # Regenerate if score is below 8 or NO determination
        if "NO" in result or any(f"score: {i}" in result.lower() for i in range(1, 8)):
            needs_regeneration = True
            improvement_guidance += "INITIAL IDEA INTEGRATION ISSUES:\n"
            improvement_guidance += result.split("guidance on how to improve it")[-1].strip() if "guidance on how to improve it" in result else result
            improvement_guidance += "\n\n"
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
        revised_prompt = f"""
        REVISION NEEDED: Your previous story outline needs improvement to better incorporate the initial idea. Please revise it based on this feedback:
        
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
        
        {prompt}
        """
        
        # Regenerate the outline
        story_outline = llm.invoke([HumanMessage(content=revised_prompt)]).content
        
        # Perform a final verification check to ensure the regenerated outline meets the requirements
        final_verification_prompt = f"""
        VERIFICATION CHECK: Evaluate whether this revised story outline effectively incorporates the initial idea.
        
        Initial Idea: "{initial_idea}"
        
        Key Elements:
        - Setting: {initial_idea_elements.get('setting', 'Unknown') if initial_idea_elements else 'Not specified'}
        - Characters: {', '.join(initial_idea_elements.get('characters', [])) if initial_idea_elements else 'Not specified'}
        - Plot: {initial_idea_elements.get('plot', 'Unknown') if initial_idea_elements else 'Not specified'}
        
        Revised Story Outline:
        {story_outline}
        
        Provide a YES/NO determination if the outline now effectively incorporates the initial idea.
        If NO, specify what still needs improvement.
        """
        
        final_verification_result = llm.invoke([HumanMessage(content=final_verification_prompt)]).content
        
        # If the outline still doesn't meet requirements, try one more time with additional guidance
        if "NO" in final_verification_result:
            final_attempt_prompt = f"""
            FINAL REVISION NEEDED:
            
            The story outline still needs improvement to better incorporate the initial idea:
            
            Initial Idea: "{initial_idea}"
            
            What still needs improvement:
            {final_verification_result}
            
            Please create an outline that:
            1. Uses "{initial_idea_elements.get('setting', 'Unknown')}" as the primary setting
            2. Features "{', '.join(initial_idea_elements.get('characters', []))}" as central characters
            3. Centers around "{initial_idea_elements.get('plot', 'Unknown')}" as the main conflict
            
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


@track_progress
def generate_characters(state: StoryState) -> Dict:
    """Generate detailed character profiles based on the story outline."""
    global_story = state["global_story"]
    genre = state["genre"]
    tone = state["tone"]
    author = state["author"]
    initial_idea = state.get("initial_idea", "")
    initial_idea_elements = state.get("initial_idea_elements", {})
    author_style_guidance = state["author_style_guidance"]
    language = state.get("language", DEFAULT_LANGUAGE)
    
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
    
    # Prepare language guidance for characters
    language_guidance = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_guidance = f"""
        CHARACTER LANGUAGE CONSIDERATIONS:
        Create characters appropriate for a story written in {SUPPORTED_LANGUAGES[language.lower()]}.
        
        1. Use character names that are authentic and common in {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures
        2. Ensure character backgrounds, professions, and social roles reflect {SUPPORTED_LANGUAGES[language.lower()]}-speaking societies
        3. Incorporate cultural values, beliefs, and traditions that resonate with {SUPPORTED_LANGUAGES[language.lower()]}-speaking audiences
        4. Consider family structures, social hierarchies, and interpersonal dynamics typical in {SUPPORTED_LANGUAGES[language.lower()]}-speaking regions
        5. Include character traits, expressions, and mannerisms that feel natural in {SUPPORTED_LANGUAGES[language.lower()]} culture
        6. Develop character speech patterns and dialogue styles that reflect {SUPPORTED_LANGUAGES[language.lower()]} communication norms
        
        Characters should feel authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking readers rather than like translated or foreign characters.
        """
    
    # Prepare initial idea character guidance
    initial_idea_guidance = ""
    required_characters = []
    if initial_idea and initial_idea_elements:
        characters_from_idea = initial_idea_elements.get("characters", [])
        if characters_from_idea:
            required_characters = characters_from_idea
            initial_idea_guidance = f"""
            REQUIRED CHARACTERS (HIGHEST PRIORITY):
            
            The following characters MUST be included in your character profiles as they are central to the initial story idea:
            {', '.join(characters_from_idea)}
            
            These characters are non-negotiable and must be developed in detail according to the initial idea: "{initial_idea}"
            
            For each required character, ensure their role, traits, and backstory align with the initial idea and the story outline.
            """
    
    # Prompt for character generation
    prompt = f"""
    Based on this story outline:
    
    {global_story}
    
    Create detailed profiles for 4-6 characters in this {tone} {genre} story that readers will find compelling and relatable.
    {f"You MUST include the following characters from the initial idea: {', '.join(required_characters)}" if required_characters else ""}
    
    For each character, include:
    
    1. Name and role in the story (protagonist, antagonist, mentor, etc.)
    2. Detailed backstory that explains their motivations and worldview
    3. Personality traits, including:
       - 3-5 defining character traits
       - 2-3 notable strengths that help them
       - 2-3 significant flaws or weaknesses that create obstacles
       - 1-2 core fears that drive their behavior
       - 1-2 deep desires or goals that motivate them
       - 1-2 values or principles they hold dear
    
    4. Emotional state at the beginning of the story
    5. Inner conflicts they struggle with (moral dilemmas, competing desires, etc.)
    6. Character arc type (redemption, fall, growth, etc.) and potential stages
    7. Key relationships with other characters, including:
       - Relationship dynamics (power balance, emotional connection)
       - Potential for conflict or growth within the relationship
    
    8. Initial known facts (what the character and reader know at the start)
    9. Secret facts (information hidden from the reader initially)
    
    {initial_idea_guidance}
    
    Make these characters:
    - RELATABLE: Give them universal hopes, fears, and struggles readers can empathize with
    - COMPLEX: Include contradictions and inner turmoil that make them feel authentic
    - DISTINCTIVE: Ensure each character has a unique voice, perspective, and emotional journey
    
    Format each character profile clearly and ensure they have interconnected relationships and histories.
    
    {char_style_section}
    
    {language_guidance}
    """
    
    # Generate character profiles
    character_profiles_text = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Validate that the characters are appropriate for the genre and setting
    if genre and initial_idea_elements and initial_idea_elements.get('setting'):
        setting = initial_idea_elements.get('setting')
        validation_prompt = f"""
        Evaluate whether these character profiles are appropriate for:
        1. A {genre} story with a {tone} tone
        2. A story set in "{setting}"
        
        Character Profiles:
        {character_profiles_text}
        
        For a {genre} story set in "{setting}", characters should:
        - Have roles, backgrounds, and motivations that make sense in a {genre} narrative
        - Have traits and abilities appropriate for the {setting} setting
        - Fulfill genre expectations for character types in {genre} stories
        - Have conflicts and relationships that drive a {genre} plot
        - Be consistent with the tone and atmosphere of a {tone} story
        
        Provide:
        1. A score from 1-10 on how well the characters fit the {genre} genre
        2. A score from 1-10 on how well the characters fit the "{setting}" setting
        3. Specific feedback on what character elements are missing or need adjustment
        4. A YES/NO determination if the characters are acceptable
        
        If either score is below 8 or the determination is NO, provide specific guidance on how to improve the characters.
        """
        
        validation_result = llm.invoke([HumanMessage(content=validation_prompt)]).content
        
        # Store the validation result in memory
        manage_memory_tool.invoke({
            "action": "create",
            "key": "character_genre_setting_validation",
            "value": validation_result,
            "namespace": MEMORY_NAMESPACE
        })
        
        # Check if we need to regenerate the characters
        if "NO" in validation_result or any(f"score: {i}" in validation_result.lower() for i in range(1, 8)):
            # Extract the improvement guidance
            improvement_guidance = validation_result.split("guidance on how to improve")[-1].strip() if "guidance on how to improve" in validation_result else validation_result
            
            # Create a revised prompt with the improvement guidance
            revised_prompt = f"""
            IMPORTANT: Your previous character profiles were not appropriate for a {genre} story set in "{setting}".
            Please revise them based on this feedback:
            
            {improvement_guidance}
            
            {prompt}
            """
            
            # Regenerate the character profiles
            character_profiles_text = llm.invoke([HumanMessage(content=revised_prompt)]).content
            
            # Store the revised character profiles
            manage_memory_tool.invoke({
                "action": "create",
                "key": "character_profiles_revised",
                "value": character_profiles_text,
                "namespace": MEMORY_NAMESPACE
            })
    
    # Define the schema for character data
    character_schema = """
    {
      "character_slug": {
        "name": "Character Name",
        "role": "Role in story (protagonist, antagonist, etc)",
        "backstory": "Detailed character backstory",
        "personality": {
          "traits": ["Trait 1", "Trait 2", "Trait 3"],
          "strengths": ["Strength 1", "Strength 2"],
          "flaws": ["Flaw 1", "Flaw 2"],
          "fears": ["Fear 1", "Fear 2"],
          "desires": ["Desire 1", "Desire 2"],
          "values": ["Value 1", "Value 2"]
        },
        "emotional_state": {
          "initial": "Character's emotional state at the beginning",
          "current": "Character's current emotional state",
          "journey": []
        },
        "inner_conflicts": [
          {
            "description": "Description of inner conflict",
            "resolution_status": "unresolved|in_progress|resolved",
            "impact": "How this conflict affects the character"
          }
        ],
        "character_arc": {
          "type": "redemption|fall|growth|flat|etc",
          "stages": [],
          "current_stage": "Current stage in the character arc"
        },
        "evolution": ["Initial state", "Future development point"],
        "known_facts": ["Known fact 1", "Known fact 2"],
        "secret_facts": ["Secret fact 1", "Secret fact 2"],
        "revealed_facts": [],
        "relationships": {
          "other_character_slug": {
            "type": "friend|enemy|mentor|etc",
            "dynamics": "Power dynamics, emotional connection",
            "evolution": ["Initial state", "Current state"],
            "conflicts": ["Conflict 1", "Conflict 2"]
          }
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
            "personality": {
                "traits": ["Brave", "Curious", "Determined"],
                "strengths": ["Quick learner", "Compassionate"],
                "flaws": ["Impulsive", "Naive"],
                "fears": ["Failure", "Losing loved ones"],
                "desires": ["Adventure", "Recognition"],
                "values": ["Friendship", "Justice"]
            },
            "emotional_state": {
                "initial": "Restless and unfulfilled",
                "current": "Restless and unfulfilled",
                "journey": []
            },
            "inner_conflicts": [
                {
                    "description": "Desire for adventure vs. fear of the unknown",
                    "resolution_status": "unresolved",
                    "impact": "Causes hesitation at critical moments"
                }
            ],
            "character_arc": {
                "type": "growth",
                "stages": ["Ordinary world", "Adventure begins", "Tests and trials"],
                "current_stage": "Ordinary world"
            },
            "evolution": ["Begins journey", "Faces first challenge"],
            "known_facts": ["Lived in small village", "Dreams of adventure"],
            "secret_facts": ["Has a special lineage", "Possesses latent power"],
            "revealed_facts": [],
            "relationships": {
                "mentor": {
                    "type": "student",
                    "dynamics": "Respectful but questioning",
                    "evolution": ["Initial meeting", "Growing trust"],
                    "conflicts": ["Resists mentor's advice"]
                },
                "villain": {
                    "type": "adversary",
                    "dynamics": "Fearful but defiant",
                    "evolution": ["Unaware of villain", "Direct confrontation"],
                    "conflicts": ["Opposing goals", "Personal vendetta"]
                }
            }
        },
        "mentor": {
            "name": "Mentor",
            "role": "Guide",
            "backstory": "Wise figure with past experience",
            "personality": {
                "traits": ["Wise", "Patient", "Mysterious"],
                "strengths": ["Experienced", "Knowledgeable"],
                "flaws": ["Secretive", "Overprotective"],
                "fears": ["History repeating itself", "Failing student"],
                "desires": ["Redemption", "Peace"],
                "values": ["Wisdom", "Balance"]
            },
            "emotional_state": {
                "initial": "Cautiously hopeful",
                "current": "Cautiously hopeful",
                "journey": []
            },
            "inner_conflicts": [
                {
                    "description": "Duty to guide vs. fear of leading hero to danger",
                    "resolution_status": "in_progress",
                    "impact": "Causes withholding of important information"
                }
            ],
            "character_arc": {
                "type": "redemption",
                "stages": ["Reluctant guide", "Opening up", "Sacrifice"],
                "current_stage": "Reluctant guide"
            },
            "evolution": ["Introduces hero to new world"],
            "known_facts": ["Has many skills", "Traveled widely"],
            "secret_facts": ["Former student of villain", "Hiding a prophecy"],
            "revealed_facts": [],
            "relationships": {
                "hero": {
                    "type": "teacher",
                    "dynamics": "Protective and guiding",
                    "evolution": ["Reluctant teacher", "Invested mentor"],
                    "conflicts": ["Withholding information"]
                },
                "villain": {
                    "type": "former student",
                    "dynamics": "Regretful and wary",
                    "evolution": ["Teacher-student", "Adversaries"],
                    "conflicts": ["Betrayal", "Opposing ideologies"]
                }
            }
        },
        "villain": {
            "name": "Villain",
            "role": "Antagonist",
            "backstory": "Once good, corrupted by power",
            "personality": {
                "traits": ["Intelligent", "Ruthless", "Charismatic"],
                "strengths": ["Strategic mind", "Powerful abilities"],
                "flaws": ["Arrogance", "Inability to trust"],
                "fears": ["Losing power", "Being forgotten"],
                "desires": ["Domination", "Validation"],
                "values": ["Order", "Control"]
            },
            "emotional_state": {
                "initial": "Coldly calculating",
                "current": "Coldly calculating",
                "journey": []
            },
            "inner_conflicts": [
                {
                    "description": "Lingering humanity vs. embraced darkness",
                    "resolution_status": "unresolved",
                    "impact": "Occasional moments of mercy or doubt"
                }
            ],
            "character_arc": {
                "type": "fall",
                "stages": ["Corruption complete", "Obsession grows", "Potential redemption"],
                "current_stage": "Corruption complete"
            },
            "evolution": ["Sends minions after hero"],
            "known_facts": ["Rules with fear", "Seeks ancient artifact"],
            "secret_facts": ["Was once good", "Has personal connection to hero"],
            "revealed_facts": [],
            "relationships": {
                "hero": {
                    "type": "enemy",
                    "dynamics": "Sees as threat and potential successor",
                    "evolution": ["Unaware of hero", "Growing obsession"],
                    "conflicts": ["Opposing goals", "Ideological differences"]
                },
                "mentor": {
                    "type": "former mentor",
                    "dynamics": "Betrayal and resentment",
                    "evolution": ["Student-teacher", "Betrayal"],
                    "conflicts": ["Ideological split", "Personal betrayal"]
                }
            }
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
        
        # Validate that required characters from the initial idea are included
        if initial_idea and initial_idea_elements and "characters" in initial_idea_elements:
            required_characters = initial_idea_elements.get("characters", [])
            if required_characters:
                # Check if all required characters are included
                character_names = [profile.get("name", "").lower() for profile in characters.values()]
                missing_characters = []
                
                for required_char in required_characters:
                    # Check if any character name contains the required character name
                    found = False
                    for name in character_names:
                        # Check if the required character appears in any character name
                        if required_char.lower() in name or name in required_char.lower():
                            found = True
                            break
                    
                    if not found:
                        missing_characters.append(required_char)
                
                # If any required characters are missing, regenerate with stronger emphasis
                if missing_characters:
                    # Log the issue
                    print(f"Missing required characters: {', '.join(missing_characters)}")
                    
                    # Create a revised prompt with stronger emphasis on required characters
                    revised_prompt = f"""
                    IMPORTANT: Your previous character profiles did not include all the required characters from the initial idea.
                    
                    You MUST include these specific characters that are central to the story:
                    {', '.join(missing_characters)}
                    
                    These characters are non-negotiable and must be developed in detail according to the initial idea: "{initial_idea}"
                    
                    {prompt}
                    """
                    
                    # Regenerate character profiles
                    character_profiles_text = llm.invoke([HumanMessage(content=revised_prompt)]).content
                    
                    # Try parsing again
                    try:
                        characters = generate_structured_json(
                            character_profiles_text,
                            character_schema,
                            "character profiles"
                        )
                        
                        # If generation failed, use the default fallback data
                        if not characters:
                            print("Using default character data as JSON generation failed.")
                            characters = default_characters
                            
                            # Add the missing required characters to the default set
                            for missing_char in missing_characters:
                                slug = missing_char.lower().replace(" ", "_")
                                characters[slug] = {
                                    "name": missing_char,
                                    "role": "Required Character from Initial Idea",
                                    "backstory": f"Important character from the initial idea: {initial_idea}",
                                    "personality": {
                                        "traits": ["To be developed"],
                                        "strengths": ["To be developed"],
                                        "flaws": ["To be developed"],
                                        "fears": ["To be developed"],
                                        "desires": ["To be developed"],
                                        "values": ["To be developed"]
                                    },
                                    "emotional_state": {
                                        "initial": "To be developed",
                                        "current": "To be developed",
                                        "journey": []
                                    },
                                    "inner_conflicts": [
                                        {
                                            "description": "To be developed",
                                            "resolution_status": "unresolved",
                                            "impact": "To be developed"
                                        }
                                    ],
                                    "character_arc": {
                                        "type": "To be determined",
                                        "stages": [],
                                        "current_stage": "Beginning"
                                    },
                                    "evolution": ["Initial state"],
                                    "known_facts": ["Required character from initial idea"],
                                    "secret_facts": [],
                                    "revealed_facts": [],
                                    "relationships": {}
                                }
                    except Exception as e:
                        print(f"Error parsing regenerated character data: {str(e)}")
                        # Add the missing required characters to the default set
                        characters = default_characters
                        for missing_char in missing_characters:
                            slug = missing_char.lower().replace(" ", "_")
                            characters[slug] = {
                                "name": missing_char,
                                "role": "Required Character from Initial Idea",
                                "backstory": f"Important character from the initial idea: {initial_idea}",
                                "personality": {
                                    "traits": ["To be developed"],
                                    "strengths": ["To be developed"],
                                    "flaws": ["To be developed"],
                                    "fears": ["To be developed"],
                                    "desires": ["To be developed"],
                                    "values": ["To be developed"]
                                },
                                "emotional_state": {
                                    "initial": "To be developed",
                                    "current": "To be developed",
                                    "journey": []
                                },
                                "inner_conflicts": [
                                    {
                                        "description": "To be developed",
                                        "resolution_status": "unresolved",
                                        "impact": "To be developed"
                                    }
                                ],
                                "character_arc": {
                                    "type": "To be determined",
                                    "stages": [],
                                    "current_stage": "Beginning"
                                },
                                "evolution": ["Initial state"],
                                "known_facts": ["Required character from initial idea"],
                                "secret_facts": [],
                                "revealed_facts": [],
                                "relationships": {}
                            }
                
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
    global_story = state["global_story"]
    characters = state["characters"]
    genre = state["genre"]
    tone = state["tone"]
    language = state.get("language", DEFAULT_LANGUAGE)
    
    # Prepare language guidance for chapters
    language_guidance = ""
    if language.lower() != DEFAULT_LANGUAGE:
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
    Based on this story outline:
    
    {global_story}
    
    And these characters:
    
    {characters}
    
    Create a plan for 5-10 chapters that cover the entire hero's journey for this {tone} {genre} story.
    
    For each chapter, provide:
    1. Chapter number and title
    2. A summary of major events (200-300 words)
    3. Which characters appear and how they develop
    4. 3-6 key scenes that should be included
    5. Any major revelations or plot twists
    
    Ensure the chapters flow logically and maintain the arc of the hero's journey.
    
    {language_guidance}
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
          },
          "3": {
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
                "2": {"content": "", "reflection_notes": []},
                "3": {"content": "", "reflection_notes": []}
            },
            "reflection_notes": []
        },
        "2": {
            "title": "The Call to Adventure",
            "outline": "Hero receives a call to adventure and initially hesitates.",
            "scenes": {
                "1": {"content": "", "reflection_notes": []},
                "2": {"content": "", "reflection_notes": []},
                "3": {"content": "", "reflection_notes": []}
            },
            "reflection_notes": []
        },
        "3": {
            "title": "Meeting the Mentor",
            "outline": "Hero meets a wise mentor who provides guidance and tools.",
            "scenes": {
                "1": {"content": "", "reflection_notes": []},
                "2": {"content": "", "reflection_notes": []},
                "3": {"content": "", "reflection_notes": []}
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