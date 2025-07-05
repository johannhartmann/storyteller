# Vulture whitelist for StoryCraft Agent
# This file contains false positives that vulture reports as dead code
# but are actually used in the project (e.g., called dynamically, from templates, etc.)

# Analysis functions called from templates or workflow
check_scene_consistency  # Called from templates
track_character_consistency  # Called from workflow
generate_consistency_guidance  # Called from templates
analyze_and_improve_dialogue  # Called from workflow
track_key_concepts  # Called from workflow
update_concept_introduction_status  # Called from workflow
analyze_concept_clarity  # Called from templates
check_and_generate_exposition_guidance  # Called from workflow
convert_exposition_to_sensory  # Called from templates
identify_telling_passages  # Called from templates
analyze_showing_vs_telling  # Called from templates
generate_pacing_guidance  # Called from templates
analyze_and_optimize_scene  # Called from workflow
track_story_repetition  # Called from workflow
analyze_scene_repetition  # Called from workflow
generate_variation_guidance  # Called from templates

# Story analysis methods - used for queries
analyze_story_structure  # Query method
analyze_character_arc  # Query method
analyze_scene_impact  # Query method
generate_dependency_graph  # Query method
get_story_timeline  # Query method

# Voice/SSML related
VoiceConfig  # Configuration class
get_repair_history  # Debugging method

# Pydantic validators and configs
validate_dialogue_purpose_map  # Pydantic validator
Config  # Pydantic config class
validate_lists  # Pydantic validator

# Internal helper functions
_generate_character_dialogue_patterns  # Helper function

# Methods that might be used in the future
concatenate_chapter_audio  # Placeholder for future feature

# Variables used in structured output
exposition_method  # Used in Pydantic model