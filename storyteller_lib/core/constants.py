"""Constants and magic strings used throughout the storyteller application.

This module centralizes all constant values to avoid magic strings
scattered throughout the codebase.
"""


# Node names in the story generation graph
class NodeNames:
    """Constants for workflow node names.

    These constants define the names of nodes in the story generation graph.
    They are used for edge definitions and flow control.
    """

    INITIALIZE = "initialize_state"
    CREATIVE_BRAINSTORM = "creative_brainstorm"
    OUTLINE_STORY = "outline_story"
    CREATE_WORLD = "create_world"
    CREATE_CHARACTERS = "create_characters"
    CREATE_CHARACTER_ARCS = "create_character_arcs"
    PLAN_CHAPTER = "plan_chapter"
    PLAN_CHAPTER_SCENES = "plan_chapter_scenes"
    SCENE_SELECTOR = "scene_selector"
    BRAINSTORM_SCENE = "brainstorm_scene"
    WRITE_SCENE = "write_scene"
    REFLECT_ON_SCENE = "reflect_on_scene"
    REVISE_SCENE = "revise_scene"
    INTEGRATE_SCENE = "integrate_scene"
    CHAPTER_CLOSURE = "chapter_closure"
    CHAPTER_SELECTOR = "chapter_selector"
    COMPILE_STORY = "compile_story"
    FINAL_QUALITY_CHECK = "final_quality_check"
    REGENERATE_ELEMENT = "regenerate_element"
    END = "__end__"
    # Additional node names used by graph_with_db
    WORLDBUILDING = "worldbuilding"
    SCENE_BRAINSTORM = "scene_brainstorm"
    SCENE_WRITING = "scene_writing"
    SHOWING_TELLING = "showing_telling"
    SCENE_REFLECTION = "scene_reflection"
    SCENE_REVISION = "scene_revision"
    WORLD_UPDATE = "world_update"
    CHARACTER_EVOLUTION = "character_evolution"
    CONTINUITY_REVIEW = "continuity_review"
    CONTINUITY_RESOLUTION = "continuity_resolution"
    PROGRESSION = "progression"
    STORY_COMPILATION = "story_compilation"
    REVIEW_AND_POLISH_MANUSCRIPT = "review_and_polish_manuscript"


# Memory namespaces
class MemoryNamespaces:
    """Constants for memory system namespaces.

    These namespaces organize different types of information in the
    memory storage system.
    """

    STORY = "story_memory"
    CHARACTER = "character_memory"
    WORLD = "world_memory"
    PLOT = "plot_memory"


# Story stages
class StoryStages:
    """Constants for story generation stages.

    These constants represent the major phases of the story
    generation workflow.
    """

    INITIALIZATION = "initialization"
    BRAINSTORMING = "brainstorming"
    OUTLINING = "outlining"
    WORLDBUILDING = "worldbuilding"
    CHARACTER_CREATION = "character_creation"
    CHAPTER_PLANNING = "chapter_planning"
    SCENE_WRITING = "scene_writing"
    COMPILATION = "compilation"
    QUALITY_CHECK = "quality_check"


# Quality check thresholds
class QualityThresholds:
    """Constants for quality assessment thresholds.

    These thresholds determine when content needs revision based on
    quality scores. All scores are on a 0-10 scale.
    """

    MIN_OVERALL_SCORE = 7
    MIN_COHERENCE_SCORE = 7
    MIN_CHARACTER_SCORE = 7
    MIN_PACING_SCORE = 6
    MIN_ENGAGEMENT_SCORE = 7
    MIN_PLOT_RESOLUTION_SCORE = 7


# Revision types
class RevisionTypes:
    """Constants for different types of revisions.

    These constants categorize the severity and scope of revisions
    needed for generated content.
    """

    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    COMPLETE_REWRITE = "complete_rewrite"


# Scene elements
class SceneElements:
    """Constants for scene components.

    These constants identify different narrative elements that can
    be included in a scene.
    """

    SETTING = "setting"
    CHARACTER_DYNAMICS = "character_dynamics"
    CONFLICT = "conflict"
    DIALOGUE = "dialogue"
    ACTION = "action"
    INTERNAL_THOUGHTS = "internal_thoughts"
    ATMOSPHERE = "atmosphere"
    SYMBOLISM = "symbolism"
    FORESHADOWING = "foreshadowing"
    CALLBACKS = "callbacks"


# Progress messages
class ProgressMessages:
    """Constants for progress reporting messages.

    These messages are displayed to users during story generation
    to indicate current progress.
    """

    GENERATING_STORY = "Generating story..."
    INITIALIZING = "Initializing story generation..."
    BRAINSTORMING = "Brainstorming creative elements..."
    OUTLINING = "Creating story outline..."
    WORLDBUILDING = "Building the story world..."
    CHARACTER_CREATION = "Creating characters..."
    WRITING_CHAPTER = "Writing Chapter {chapter_num}..."
    WRITING_SCENE = "Writing Scene {scene_num}..."
    COMPILING = "Compiling complete story..."
    QUALITY_CHECK = "Performing final quality check..."
    COMPLETE = "Story generation complete!"


# File operations
class FilePatterns:
    """Constants for file naming patterns.

    These patterns define how output files are named based on
    the story and format.
    """

    OUTPUT_MARKDOWN = "{base_name}.md"
    OUTPUT_JSON = "{base_name}.json"
    MEMORY_DB = "story_memory_{story_id}.db"


# Configuration defaults
class ConfigDefaults:
    """Default configuration values.

    These defaults are used when specific configuration values
    are not provided by the user.
    """

    DEFAULT_TEMPERATURE = 0.9
    DEFAULT_MAX_TOKENS = 32768
    DEFAULT_MODEL_PROVIDER = "gemini"
    DEFAULT_LANGUAGE = "english"
    DEFAULT_GENRE = "fantasy"
    DEFAULT_TONE = "adventurous"
    DEFAULT_LENGTH = "medium"
    DEFAULT_CHAPTERS = 10
    DEFAULT_SCENES_PER_CHAPTER = 5


# Supported languages
SUPPORTED_LANGUAGES = [
    "english",
    "spanish",
    "french",
    "german",
    "italian",
    "portuguese",
    "russian",
    "chinese",
    "japanese",
    "korean",
    "arabic",
    "hindi",
]

# Supported genres
SUPPORTED_GENRES = [
    "fantasy",
    "science fiction",
    "mystery",
    "thriller",
    "romance",
    "historical fiction",
    "horror",
    "adventure",
    "drama",
    "comedy",
    "dystopian",
    "urban fantasy",
    "epic fantasy",
    "cyberpunk",
    "steampunk",
    "magical realism",
    "literary fiction",
]

# Supported tones
SUPPORTED_TONES = [
    "adventurous",
    "mysterious",
    "romantic",
    "comedic",
    "dark",
    "epic",
    "intimate",
    "philosophical",
    "action-packed",
    "whimsical",
    "gritty",
    "lighthearted",
    "suspenseful",
    "melancholic",
    "inspirational",
]

# Story lengths
STORY_LENGTHS = {
    "short": {"chapters": 5, "scenes_per_chapter": 3},
    "medium": {"chapters": 10, "scenes_per_chapter": 5},
    "long": {"chapters": 20, "scenes_per_chapter": 7},
    "epic": {"chapters": 30, "scenes_per_chapter": 10},
}


# Retry configurations
class RetryConfig:
    """Constants for retry behavior.

    These constants control how the system handles failures and
    retries operations.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 1.0
    MAX_REGENERATION_ATTEMPTS = 3


# Validation patterns
class ValidationPatterns:
    """Regular expression patterns for validation.

    These regex patterns are used to extract and validate
    structured information from text.
    """

    SCENE_NUMBER = r"Scene (\d+)"
    CHAPTER_NUMBER = r"Chapter (\d+)"
    QUALITY_SCORE = r"(\d+)/10"
