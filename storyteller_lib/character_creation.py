"""
StoryCraft Agent - Character creation and management.
"""

from typing import Dict, List, Any

from storyteller_lib.config import llm, manage_memory_tool, search_memory_tool, MEMORY_NAMESPACE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from storyteller_lib.models import StoryState, CharacterProfile
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from storyteller_lib.creative_tools import generate_structured_json, parse_json_with_langchain
from storyteller_lib import track_progress

# Default character data
DEFAULT_CHARACTERS = {
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
    },
    "ally": {
        "name": "Loyal Ally",
        "role": "Supporting Character",
        "backstory": "Childhood friend or chance encounter with shared goals",
        "personality": {
            "traits": ["Loyal", "Practical", "Resourceful"],
            "strengths": ["Street-smart", "Adaptable"],
            "flaws": ["Stubborn", "Overprotective"],
            "fears": ["Abandonment", "Inadequacy"],
            "desires": ["Belonging", "Proving worth"],
            "values": ["Loyalty", "Honesty"]
        },
        "emotional_state": {
            "initial": "Enthusiastic and supportive",
            "current": "Enthusiastic and supportive",
            "journey": []
        },
        "inner_conflicts": [
            {
                "description": "Desire to help vs. feeling overshadowed",
                "resolution_status": "unresolved",
                "impact": "Occasional resentment that is quickly overcome"
            }
        ],
        "character_arc": {
            "type": "growth",
            "stages": ["Loyal follower", "Finding own path", "True partnership"],
            "current_stage": "Loyal follower"
        },
        "evolution": ["Joins hero's quest", "Provides crucial support"],
        "known_facts": ["Skilled in practical matters", "Has local connections"],
        "secret_facts": ["Harbors insecurities", "Has hidden talent"],
        "revealed_facts": [],
        "relationships": {
            "hero": {
                "type": "friend",
                "dynamics": "Supportive but occasionally challenging",
                "evolution": ["Initial bond", "Tested friendship"],
                "conflicts": ["Different approaches to problems"]
            }
        }
    },
    "trickster": {
        "name": "Trickster",
        "role": "Wild Card",
        "backstory": "Mysterious figure with unclear motives",
        "personality": {
            "traits": ["Unpredictable", "Clever", "Amoral"],
            "strengths": ["Quick-witted", "Adaptable"],
            "flaws": ["Selfish", "Unreliable"],
            "fears": ["Commitment", "Being controlled"],
            "desires": ["Freedom", "Entertainment"],
            "values": ["Self-preservation", "Chaos"]
        },
        "emotional_state": {
            "initial": "Amused and detached",
            "current": "Amused and detached",
            "journey": []
        },
        "inner_conflicts": [
            {
                "description": "Self-interest vs. growing attachment to heroes",
                "resolution_status": "unresolved",
                "impact": "Unpredictable shifts between helping and hindering"
            }
        ],
        "character_arc": {
            "type": "transformation",
            "stages": ["Self-serving", "Conflicted loyalty", "Unexpected sacrifice"],
            "current_stage": "Self-serving"
        },
        "evolution": ["Appears at crucial moment", "Provides unexpected aid"],
        "known_facts": ["Has valuable skills", "Appears when least expected"],
        "secret_facts": ["Hidden connection to story", "True motivations unclear"],
        "revealed_facts": [],
        "relationships": {
            "hero": {
                "type": "complicated",
                "dynamics": "Alternates between helping and hindering",
                "evolution": ["Initial distrust", "Uneasy alliance"],
                "conflicts": ["Unpredictability", "Questionable methods"]
            }
        }
    }
}

def create_character(name: str, role: str, backstory: str = "", **kwargs) -> CharacterProfile:
    """
    Create a new character with the given attributes.
    
    Args:
        name: The character's name
        role: The character's role in the story (protagonist, antagonist, etc.)
        backstory: The character's backstory
        **kwargs: Additional character attributes
        
    Returns:
        A CharacterProfile dictionary with the character's attributes
    """
    # Create a basic character profile
    character = {
        "name": name,
        "role": role,
        "backstory": backstory,
        "personality": {
            "traits": kwargs.get("traits", []),
            "strengths": kwargs.get("strengths", []),
            "flaws": kwargs.get("flaws", []),
            "fears": kwargs.get("fears", []),
            "desires": kwargs.get("desires", []),
            "values": kwargs.get("values", [])
        },
        "emotional_state": {
            "initial": kwargs.get("initial_emotional_state", "Neutral"),
            "current": kwargs.get("current_emotional_state", "Neutral"),
            "journey": kwargs.get("emotional_journey", [])
        },
        "inner_conflicts": kwargs.get("inner_conflicts", []),
        "character_arc": {
            "type": kwargs.get("arc_type", "growth"),
            "stages": kwargs.get("arc_stages", []),
            "current_stage": kwargs.get("current_arc_stage", "Beginning")
        },
        "evolution": kwargs.get("evolution", []),
        "known_facts": kwargs.get("known_facts", []),
        "secret_facts": kwargs.get("secret_facts", []),
        "revealed_facts": kwargs.get("revealed_facts", []),
        "relationships": kwargs.get("relationships", {})
    }
    
    return character

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
    language_elements = None
    if language.lower() != DEFAULT_LANGUAGE:
        # Try to retrieve language elements from memory
        try:
            language_elements_result = search_memory_tool.invoke({
                "query": f"language_elements_{language.lower()}",
                "namespace": MEMORY_NAMESPACE
            })
            
            # Handle different return types from search_memory_tool
            if language_elements_result:
                if isinstance(language_elements_result, dict) and "value" in language_elements_result:
                    # Direct dictionary with value
                    language_elements = language_elements_result["value"]
                elif isinstance(language_elements_result, list):
                    # List of objects
                    for item in language_elements_result:
                        if hasattr(item, 'key') and item.key == f"language_elements_{language.lower()}":
                            language_elements = item.value
                            break
                elif isinstance(language_elements_result, str):
                    # Try to parse JSON string
                    try:
                        import json
                        language_elements = json.loads(language_elements_result)
                    except:
                        # If not JSON, use as is
                        language_elements = language_elements_result
        except Exception as e:
            print(f"Error retrieving language elements: {str(e)}")
        
        # Create language guidance with specific naming examples if available
        naming_examples = ""
        if language_elements and "NAMING CONVENTIONS" in language_elements:
            naming_conventions = language_elements["NAMING CONVENTIONS"]
            
            male_names = naming_conventions.get("Common first names for male characters", [])
            if isinstance(male_names, str):
                male_names = male_names.split(", ")
            
            female_names = naming_conventions.get("Common first names for female characters", [])
            if isinstance(female_names, str):
                female_names = female_names.split(", ")
            
            family_names = naming_conventions.get("Common family/last names", [])
            if isinstance(family_names, str):
                family_names = family_names.split(", ")
            
            # Create examples using the retrieved names
            if male_names and female_names and family_names:
                naming_examples = f"""
                Examples of authentic {SUPPORTED_LANGUAGES[language.lower()]} names:
                - Male names: {', '.join(male_names[:5] if len(male_names) > 5 else male_names)}
                - Female names: {', '.join(female_names[:5] if len(female_names) > 5 else female_names)}
                - Family/last names: {', '.join(family_names[:5] if len(family_names) > 5 else family_names)}
                """
        
        language_guidance = f"""
        CHARACTER LANGUAGE CONSIDERATIONS:
        Create characters appropriate for a story written in {SUPPORTED_LANGUAGES[language.lower()]}.
        
        1. Use character names that are authentic and common in {SUPPORTED_LANGUAGES[language.lower()]}-speaking cultures
        2. Ensure character backgrounds, professions, and social roles reflect {SUPPORTED_LANGUAGES[language.lower()]}-speaking societies
        3. Incorporate cultural values, beliefs, and traditions that resonate with {SUPPORTED_LANGUAGES[language.lower()]}-speaking audiences
        4. Consider family structures, social hierarchies, and interpersonal dynamics typical in {SUPPORTED_LANGUAGES[language.lower()]}-speaking regions
        5. Include character traits, expressions, and mannerisms that feel natural in {SUPPORTED_LANGUAGES[language.lower()]} culture
        6. Develop character speech patterns and dialogue styles that reflect {SUPPORTED_LANGUAGES[language.lower()]} communication norms
        
        {naming_examples}
        
        Characters should feel authentic to {SUPPORTED_LANGUAGES[language.lower()]}-speaking readers rather than like translated or foreign characters.
        
        IMPORTANT: Maintain consistency with any character names already established in the story outline.
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
    
    # Prepare language instruction
    language_instruction = ""
    if language.lower() != DEFAULT_LANGUAGE:
        language_instruction = f"""
        !!!CRITICAL LANGUAGE INSTRUCTION!!!
        These character profiles MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
        ALL content - including names, descriptions, backstories, and personality traits - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
        DO NOT translate character archetypes - create the profiles directly in {SUPPORTED_LANGUAGES[language.lower()]}.
        
        I will verify that your response is completely in {SUPPORTED_LANGUAGES[language.lower()]} and reject any profiles that contain English.
        """
    
    # Prompt for character generation
    prompt = f"""
    {language_instruction if language.lower() != DEFAULT_LANGUAGE else ""}
    
    Based on this story outline:
    
    {global_story}
    
    Create detailed profiles for 4-6 characters in this {tone} {genre} story that readers will find compelling and relatable.
    IMPORTANT: You must create at least 4 distinct characters with unique roles in the story.
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
    
    {language_instruction if language.lower() != DEFAULT_LANGUAGE else ""}
    
    {language_guidance}
    """
    # Generate character profiles
    character_profiles_text = llm.invoke([HumanMessage(content=prompt)]).content
    
    # Validate language if not English
    if language.lower() != DEFAULT_LANGUAGE:
        language_validation_prompt = f"""
        LANGUAGE VALIDATION: Check if this text is written entirely in {SUPPORTED_LANGUAGES[language.lower()]}.
        
        Text to validate:
        {character_profiles_text}
        
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
            "key": "character_profiles_language_validation",
            "value": language_validation_result,
            "namespace": MEMORY_NAMESPACE
        })
        
        # If language validation fails, regenerate with stronger language instruction
        if "NO" in language_validation_result:
            stronger_language_instruction = f"""
            !!!CRITICAL LANGUAGE INSTRUCTION - PREVIOUS ATTEMPT FAILED!!!
            
            Your previous response contained English text. This is NOT acceptable.
            
            These character profiles MUST be written ENTIRELY in {SUPPORTED_LANGUAGES[language.lower()]}.
            ALL content - including names, descriptions, backstories, and personality traits - must be in {SUPPORTED_LANGUAGES[language.lower()]}.
            DO NOT translate character archetypes - create the profiles directly in {SUPPORTED_LANGUAGES[language.lower()]}.
            
            I will verify that your response is completely in {SUPPORTED_LANGUAGES[language.lower()]} and reject any profiles that contain English.
            
            The following parts were not in {SUPPORTED_LANGUAGES[language.lower()]}:
            {language_validation_result.split("which parts are not in")[1].strip() if "which parts are not in" in language_validation_result else "Some parts of the text"}
            """
            
            # Regenerate with stronger language instruction
            revised_prompt = f"""
            {stronger_language_instruction}
            
            {prompt}
            
            {stronger_language_instruction}
            """
            
            character_profiles_text = llm.invoke([HumanMessage(content=revised_prompt)]).content
    
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
      "character1_slug": {
        "name": "Character 1 Name",
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
    default_characters = DEFAULT_CHARACTERS
    
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
        
        # Ensure we have at least 4 characters
        if len(characters) < 4:
            print(f"Only {len(characters)} characters were generated. Adding default characters to reach at least 4.")
            # Add missing default characters
            default_keys = list(default_characters.keys())
            for i in range(4 - len(characters)):
                if i < len(default_keys):
                    default_key = default_keys[i]
                    if default_key not in characters:
                        characters[default_key] = default_characters[default_key]
    except Exception as e:
        print(f"Error parsing character data: {str(e)}")
        # Fallback structure defined above in parse_structured_data call
        characters = default_characters
        
        # Ensure we have at least 4 characters
        if len(characters) < 4:
            print(f"Only {len(characters)} characters were generated. Adding default characters to reach at least 4.")
            # Add missing default characters
            default_keys = list(default_characters.keys())
            for i in range(4 - len(characters)):
                if i < len(default_keys):
                    default_key = default_keys[i]
                    if default_key not in characters:
                        characters[default_key] = default_characters[default_key]
    
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
