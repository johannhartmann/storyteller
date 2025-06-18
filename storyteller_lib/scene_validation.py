"""Scene validation module for preventing repetition and ensuring consistency."""

from typing import Dict, List, Any, Optional, Tuple
from storyteller_lib.logger import get_logger
from storyteller_lib.database_integration import get_db_manager

logger = get_logger(__name__)


def validate_scene_prerequisites(
    chapter_num: int, 
    scene_num: int, 
    scene_spec: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Validate that a scene's prerequisites are met before writing.
    
    Args:
        chapter_num: Chapter number
        scene_num: Scene number
        scene_spec: Scene specification dictionary with prerequisites, forbidden elements, etc.
        
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    db_manager = get_db_manager()
    
    if not db_manager:
        logger.warning("No database manager available for validation")
        return True, []
    
    # Get existing plot progressions
    existing_progressions = db_manager.get_plot_progressions()
    existing_progression_keys = [p['progression_key'] for p in existing_progressions]
    
    # Check prerequisites
    prerequisites = scene_spec.get('prerequisites', [])
    for prereq in prerequisites:
        if prereq not in existing_progression_keys:
            issues.append(f"Prerequisite not met: '{prereq}' must happen before this scene")
    
    # Check that plot progressions haven't already happened
    plot_progressions = scene_spec.get('plot_progressions', [])
    for prog in plot_progressions:
        if prog in existing_progression_keys:
            issues.append(f"Plot progression already occurred: '{prog}' should not be repeated")
    
    # Check character knowledge to prevent duplicate revelations
    character_knowledge_changes = scene_spec.get('character_knowledge_changes', {})
    if character_knowledge_changes and db_manager._db:
        with db_manager._db._get_connection() as conn:
            cursor = conn.cursor()
            
            for char_name, knowledge_list in character_knowledge_changes.items():
                # Get character ID
                cursor.execute(
                    "SELECT id FROM characters WHERE identifier = ? OR name = ?",
                    (char_name, char_name)
                )
                char_result = cursor.fetchone()
                
                if char_result:
                    char_id = char_result['id']
                    
                    # Check existing knowledge
                    cursor.execute(
                        "SELECT knowledge_content FROM character_knowledge WHERE character_id = ?",
                        (char_id,)
                    )
                    existing_knowledge = [row['knowledge_content'] for row in cursor.fetchall()]
                    
                    for knowledge in knowledge_list:
                        if knowledge in existing_knowledge:
                            issues.append(f"Character already knows: {char_name} already knows '{knowledge}'")
    
    # Check forbidden repetitions against plot progressions
    forbidden_repetitions = scene_spec.get('forbidden_repetitions', [])
    for forbidden in forbidden_repetitions:
        if forbidden not in existing_progression_keys:
            logger.warning(f"Forbidden repetition '{forbidden}' hasn't occurred yet - may be misconfigured")
    
    is_valid = len(issues) == 0
    return is_valid, issues


def check_scene_for_repetitions(
    scene_content: str,
    chapter_num: int,
    scene_num: int
) -> List[str]:
    """
    Check a written scene for potential repetitions of plot points.
    
    Args:
        scene_content: The written scene content
        chapter_num: Chapter number
        scene_num: Scene number
        
    Returns:
        List of potential repetition warnings
    """
    warnings = []
    db_manager = get_db_manager()
    
    if not db_manager:
        return warnings
    
    # Get plot progressions
    existing_progressions = db_manager.get_plot_progressions()
    
    # Check for common repetition patterns
    repetition_patterns = {
        'hero_learns_about_quest': [
            'learns about the mission',
            'told about the quest',
            'discovers their purpose',
            'informed of the task'
        ],
        'villain_revealed': [
            'villain is revealed',
            'antagonist appears',
            'enemy shows themselves',
            'true villain emerges'
        ],
        'mentor_gives_advice': [
            'mentor advises',
            'sage provides wisdom',
            'teacher explains',
            'guide offers counsel'
        ]
    }
    
    content_lower = scene_content.lower()
    
    for progression_key, patterns in repetition_patterns.items():
        # Check if this progression already exists
        if any(p['progression_key'] == progression_key for p in existing_progressions):
            # Check if the scene contains patterns suggesting repetition
            for pattern in patterns:
                if pattern in content_lower:
                    existing_occurrence = next(
                        p for p in existing_progressions 
                        if p['progression_key'] == progression_key
                    )
                    warnings.append(
                        f"Potential repetition detected: '{progression_key}' "
                        f"already occurred in Ch{existing_occurrence['chapter_number']}/"
                        f"Sc{existing_occurrence['scene_number']}, "
                        f"but this scene contains '{pattern}'"
                    )
                    break
    
    return warnings


def suggest_plot_progression_keys(
    scene_description: str,
    genre: str,
    existing_keys: List[str]
) -> List[str]:
    """
    Suggest appropriate plot progression keys for a scene.
    
    Args:
        scene_description: Description of what happens in the scene
        genre: Story genre
        existing_keys: Already used progression keys
        
    Returns:
        List of suggested progression keys
    """
    suggestions = []
    
    # Common progression patterns by genre
    genre_progressions = {
        'fantasy': [
            'hero_discovers_powers',
            'ancient_prophecy_revealed',
            'magical_artifact_found',
            'dark_force_awakens',
            'mentor_sacrifices_self'
        ],
        'sci-fi': [
            'technology_malfunction',
            'alien_first_contact',
            'ship_systems_fail',
            'conspiracy_uncovered',
            'ai_becomes_sentient'
        ],
        'mystery': [
            'first_clue_discovered',
            'witness_interrogated',
            'false_lead_pursued',
            'real_culprit_suspected',
            'motive_revealed'
        ],
        'romance': [
            'first_meeting',
            'misunderstanding_occurs',
            'feelings_confessed',
            'conflict_arises',
            'reconciliation_happens'
        ]
    }
    
    # Get genre-specific progressions
    base_progressions = genre_progressions.get(genre.lower(), [])
    
    # Filter out already used keys
    available_progressions = [p for p in base_progressions if p not in existing_keys]
    
    # Add universal progressions
    universal_progressions = [
        'protagonist_accepts_challenge',
        'ally_joins_quest',
        'betrayal_revealed',
        'hope_seems_lost',
        'truth_discovered',
        'sacrifice_made',
        'victory_achieved'
    ]
    
    available_progressions.extend([
        p for p in universal_progressions 
        if p not in existing_keys and p not in available_progressions
    ])
    
    # Parse scene description for key events
    description_lower = scene_description.lower()
    
    # Match keywords to suggest appropriate keys
    if 'learns' in description_lower or 'discovers' in description_lower:
        suggestions.append('information_revealed')
    if 'fight' in description_lower or 'battle' in description_lower:
        suggestions.append('combat_occurs')
    if 'escape' in description_lower or 'flee' in description_lower:
        suggestions.append('narrow_escape')
    if 'meet' in description_lower or 'encounter' in description_lower:
        suggestions.append('new_character_introduced')
    
    # Combine suggestions with available progressions
    all_suggestions = list(set(suggestions + available_progressions[:5]))
    
    return all_suggestions


def validate_chapter_plan_consistency(chapter_plan: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate that a chapter plan has consistent plot progressions.
    
    Args:
        chapter_plan: The chapter plan dictionary
        
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    used_progressions = set()
    
    # Check each chapter
    for chapter_num, chapter_data in chapter_plan.items():
        if 'scenes' not in chapter_data:
            continue
            
        for scene_num, scene_data in chapter_data['scenes'].items():
            plot_progressions = scene_data.get('plot_progressions', [])
            
            # Check for duplicate progressions
            for prog in plot_progressions:
                if prog in used_progressions:
                    issues.append(
                        f"Duplicate plot progression '{prog}' in "
                        f"Chapter {chapter_num}, Scene {scene_num}"
                    )
                used_progressions.add(prog)
            
            # Check prerequisites are met
            prerequisites = scene_data.get('prerequisites', [])
            for prereq in prerequisites:
                if prereq not in used_progressions:
                    issues.append(
                        f"Prerequisite '{prereq}' for Chapter {chapter_num}, "
                        f"Scene {scene_num} not found in earlier scenes"
                    )
            
            # Check forbidden repetitions make sense
            forbidden = scene_data.get('forbidden_repetitions', [])
            for f in forbidden:
                if f not in used_progressions:
                    logger.warning(
                        f"Forbidden repetition '{f}' in Chapter {chapter_num}, "
                        f"Scene {scene_num} hasn't occurred yet"
                    )
    
    is_valid = len(issues) == 0
    return is_valid, issues