"""
Narrative structure definitions and selection logic for StoryCraft Agent.

This module provides different narrative structures that can be selected
based on genre, tone, and story concept.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from pydantic import BaseModel, Field


class StoryLength(Enum):
    """Story length categories with chapter ranges."""
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    EPIC = "epic"


@dataclass
class ChapterDistribution:
    """Defines how chapters are distributed across story sections."""
    sections: List[Tuple[str, float]]  # (section_name, percentage)
    
    def get_chapter_counts(self, total_chapters: int) -> Dict[str, int]:
        """Calculate chapter counts for each section."""
        counts = {}
        remaining = total_chapters
        
        for i, (section, percentage) in enumerate(self.sections):
            if i == len(self.sections) - 1:
                # Last section gets remaining chapters
                counts[section] = remaining
            else:
                count = round(total_chapters * percentage)
                counts[section] = count
                remaining -= count
                
        return counts


@dataclass
class SceneTypeDistribution:
    """Defines the distribution of different scene types."""
    action: float = 0.2
    dialogue: float = 0.2
    exploration: float = 0.2
    revelation: float = 0.1
    character_moment: float = 0.1
    transition: float = 0.1
    conflict: float = 0.05
    resolution: float = 0.05
    
    def validate(self):
        """Ensure distributions sum to 1.0."""
        total = (self.action + self.dialogue + self.exploration + 
                self.revelation + self.character_moment + self.transition +
                self.conflict + self.resolution)
        assert abs(total - 1.0) < 0.01, f"Scene type distribution must sum to 1.0, got {total}"


class NarrativeStructure(ABC):
    """Base class for all narrative structures."""
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.best_genres: List[str] = []
        self.best_tones: List[str] = []
        self.length_ranges: Dict[StoryLength, Tuple[int, int]] = {}
        self.default_scenes_per_chapter: Dict[StoryLength, int] = {
            StoryLength.SHORT: 3,
            StoryLength.MEDIUM: 5,
            StoryLength.LONG: 6,
            StoryLength.EPIC: 7
        }
        self.words_per_scene_range: Tuple[int, int] = (600, 800)
    
    @abstractmethod
    def get_chapter_distribution(self) -> ChapterDistribution:
        """Return how chapters should be distributed across the story."""
        pass
    
    @abstractmethod
    def get_scene_type_distribution(self) -> SceneTypeDistribution:
        """Return the ideal distribution of scene types."""
        pass
    
    @abstractmethod
    def get_tension_curve(self, num_chapters: int) -> List[float]:
        """Return tension levels (0-1) for each chapter."""
        pass
    
    @abstractmethod
    def get_structure_description(self) -> str:
        """Return a description of this narrative structure."""
        pass
    
    def get_optimal_chapter_count(self, length: StoryLength) -> int:
        """Get the optimal chapter count for this structure and length."""
        min_chapters, max_chapters = self.length_ranges[length]
        return (min_chapters + max_chapters) // 2
    
    def get_chapter_range(self, length: StoryLength) -> Tuple[int, int]:
        """Get the valid chapter range for this structure and length."""
        return self.length_ranges[length]


class HeroJourneyStructure(NarrativeStructure):
    """The classic Hero's Journey narrative structure."""
    
    def __init__(self):
        super().__init__()
        self.best_genres = ["fantasy", "adventure", "science fiction", "epic fantasy"]
        self.best_tones = ["adventurous", "epic", "inspirational", "heroic"]
        self.length_ranges = {
            StoryLength.SHORT: (8, 10),
            StoryLength.MEDIUM: (12, 18),
            StoryLength.LONG: (20, 28),
            StoryLength.EPIC: (30, 40)
        }
        self.words_per_scene_range = (600, 900)
    
    def get_chapter_distribution(self) -> ChapterDistribution:
        return ChapterDistribution([
            ("Ordinary World", 0.15),
            ("Call to Adventure", 0.10),
            ("Refusal & Mentor", 0.15),
            ("Crossing Threshold", 0.10),
            ("Tests & Allies", 0.20),
            ("Ordeal", 0.10),
            ("Reward & Road Back", 0.10),
            ("Resurrection & Return", 0.10)
        ])
    
    def get_scene_type_distribution(self) -> SceneTypeDistribution:
        return SceneTypeDistribution(
            action=0.25,
            dialogue=0.20,
            exploration=0.20,
            revelation=0.10,
            character_moment=0.10,
            transition=0.05,
            conflict=0.05,
            resolution=0.05
        )
    
    def get_tension_curve(self, num_chapters: int) -> List[float]:
        """Hero's Journey has multiple peaks with the highest at the ordeal."""
        curve = []
        for i in range(num_chapters):
            progress = i / (num_chapters - 1)
            
            if progress < 0.15:  # Ordinary world
                tension = 0.2 + 0.1 * (progress / 0.15)
            elif progress < 0.25:  # Call to adventure
                tension = 0.3 + 0.2 * ((progress - 0.15) / 0.10)
            elif progress < 0.40:  # Refusal and mentor
                tension = 0.5 - 0.1 * ((progress - 0.25) / 0.15)
            elif progress < 0.50:  # Crossing threshold
                tension = 0.4 + 0.2 * ((progress - 0.40) / 0.10)
            elif progress < 0.70:  # Tests and allies
                tension = 0.6 + 0.1 * ((progress - 0.50) / 0.20)
            elif progress < 0.80:  # Ordeal (climax)
                tension = 0.7 + 0.3 * ((progress - 0.70) / 0.10)
            elif progress < 0.90:  # Reward and road back
                tension = 1.0 - 0.3 * ((progress - 0.80) / 0.10)
            else:  # Resurrection and return
                tension = 0.7 - 0.5 * ((progress - 0.90) / 0.10)
            
            curve.append(min(1.0, max(0.1, tension)))
        
        return curve
    
    def get_structure_description(self) -> str:
        return """The Hero's Journey follows a protagonist who ventures from their ordinary world into an extraordinary one, faces challenges, achieves victory, and returns transformed. This structure includes distinct phases: departure, initiation, and return, with mentors, allies, and enemies along the way."""


class ThreeActStructure(NarrativeStructure):
    """The classic three-act structure common in Western storytelling."""
    
    def __init__(self):
        super().__init__()
        self.best_genres = ["mystery", "thriller", "romance", "drama", "crime"]
        self.best_tones = ["suspenseful", "romantic", "dramatic", "mysterious", "gritty"]
        self.length_ranges = {
            StoryLength.SHORT: (6, 9),
            StoryLength.MEDIUM: (12, 15),
            StoryLength.LONG: (18, 24),
            StoryLength.EPIC: (27, 36)
        }
        self.words_per_scene_range = (500, 800)
    
    def get_chapter_distribution(self) -> ChapterDistribution:
        return ChapterDistribution([
            ("Act 1 - Setup", 0.25),
            ("Act 2 - Confrontation", 0.50),
            ("Act 3 - Resolution", 0.25)
        ])
    
    def get_scene_type_distribution(self) -> SceneTypeDistribution:
        return SceneTypeDistribution(
            action=0.20,
            dialogue=0.25,
            exploration=0.15,
            revelation=0.15,
            character_moment=0.10,
            transition=0.05,
            conflict=0.05,
            resolution=0.05
        )
    
    def get_tension_curve(self, num_chapters: int) -> List[float]:
        """Three-act structure builds to climax in late Act 2."""
        curve = []
        for i in range(num_chapters):
            progress = i / (num_chapters - 1)
            
            if progress < 0.25:  # Act 1
                tension = 0.2 + 0.3 * (progress / 0.25)
            elif progress < 0.75:  # Act 2
                # Build steadily with midpoint spike
                act2_progress = (progress - 0.25) / 0.50
                if act2_progress < 0.5:
                    tension = 0.5 + 0.2 * (act2_progress / 0.5)
                else:
                    tension = 0.7 + 0.3 * ((act2_progress - 0.5) / 0.5)
            else:  # Act 3
                # Climax then resolution
                act3_progress = (progress - 0.75) / 0.25
                if act3_progress < 0.4:
                    tension = 1.0
                else:
                    tension = 1.0 - 0.6 * ((act3_progress - 0.4) / 0.6)
            
            curve.append(min(1.0, max(0.1, tension)))
        
        return curve
    
    def get_structure_description(self) -> str:
        return """The three-act structure divides the story into setup (25%), confrontation (50%), and resolution (25%). Act 1 establishes characters and conflict, Act 2 develops complications and raises stakes, and Act 3 provides climax and resolution."""


class KishotenketsuStructure(NarrativeStructure):
    """Four-act structure from East Asian storytelling tradition."""
    
    def __init__(self):
        super().__init__()
        self.best_genres = ["literary fiction", "slice of life", "magical realism", "contemporary"]
        self.best_tones = ["contemplative", "philosophical", "intimate", "whimsical", "melancholic"]
        self.length_ranges = {
            StoryLength.SHORT: (8, 8),
            StoryLength.MEDIUM: (12, 16),
            StoryLength.LONG: (20, 24),
            StoryLength.EPIC: (28, 32)
        }
        self.words_per_scene_range = (700, 1000)
    
    def get_chapter_distribution(self) -> ChapterDistribution:
        return ChapterDistribution([
            ("Ki (Introduction)", 0.25),
            ("Shō (Development)", 0.25),
            ("Ten (Twist)", 0.25),
            ("Ketsu (Conclusion)", 0.25)
        ])
    
    def get_scene_type_distribution(self) -> SceneTypeDistribution:
        return SceneTypeDistribution(
            action=0.10,
            dialogue=0.25,
            exploration=0.25,
            revelation=0.15,
            character_moment=0.15,
            transition=0.05,
            conflict=0.03,
            resolution=0.02
        )
    
    def get_tension_curve(self, num_chapters: int) -> List[float]:
        """Kishōtenketsu has a different rhythm with the twist in the third act."""
        curve = []
        for i in range(num_chapters):
            progress = i / (num_chapters - 1)
            
            if progress < 0.25:  # Ki - Introduction
                tension = 0.2 + 0.1 * (progress / 0.25)
            elif progress < 0.50:  # Shō - Development
                tension = 0.3 + 0.2 * ((progress - 0.25) / 0.25)
            elif progress < 0.75:  # Ten - Twist
                # Sudden spike for the twist
                ten_progress = (progress - 0.50) / 0.25
                if ten_progress < 0.3:
                    tension = 0.5 + 0.4 * (ten_progress / 0.3)
                else:
                    tension = 0.9 - 0.2 * ((ten_progress - 0.3) / 0.7)
            else:  # Ketsu - Conclusion
                tension = 0.7 - 0.5 * ((progress - 0.75) / 0.25)
            
            curve.append(min(1.0, max(0.1, tension)))
        
        return curve
    
    def get_structure_description(self) -> str:
        return """Kishōtenketsu is a four-act structure without conventional conflict. Ki introduces, Shō develops, Ten provides an unexpected twist or new perspective, and Ketsu concludes by synthesizing all elements. The twist doesn't create conflict but recontextualizes everything."""


class InMediasResStructure(NarrativeStructure):
    """Structure that begins in the middle of action."""
    
    def __init__(self):
        super().__init__()
        self.best_genres = ["thriller", "action", "noir", "science fiction", "mystery"]
        self.best_tones = ["action-packed", "suspenseful", "gritty", "dark", "mysterious"]
        self.length_ranges = {
            StoryLength.SHORT: (8, 10),
            StoryLength.MEDIUM: (12, 18),
            StoryLength.LONG: (20, 28),
            StoryLength.EPIC: (30, 36)
        }
        self.words_per_scene_range = (400, 700)
    
    def get_chapter_distribution(self) -> ChapterDistribution:
        return ChapterDistribution([
            ("Opening Action", 0.10),
            ("Backstory & Context", 0.30),
            ("Present Conflict Development", 0.40),
            ("Climax & Resolution", 0.20)
        ])
    
    def get_scene_type_distribution(self) -> SceneTypeDistribution:
        return SceneTypeDistribution(
            action=0.30,
            dialogue=0.20,
            exploration=0.15,
            revelation=0.15,
            character_moment=0.08,
            transition=0.05,
            conflict=0.05,
            resolution=0.02
        )
    
    def get_tension_curve(self, num_chapters: int) -> List[float]:
        """Start high, dip for backstory, then build to climax."""
        curve = []
        for i in range(num_chapters):
            progress = i / (num_chapters - 1)
            
            if progress < 0.10:  # Opening action
                tension = 0.8 - 0.2 * (progress / 0.10)
            elif progress < 0.40:  # Backstory
                tension = 0.6 - 0.2 * ((progress - 0.10) / 0.30)
            elif progress < 0.80:  # Present conflict
                tension = 0.4 + 0.6 * ((progress - 0.40) / 0.40)
            else:  # Resolution
                resolution_progress = (progress - 0.80) / 0.20
                if resolution_progress < 0.3:
                    tension = 1.0
                else:
                    tension = 1.0 - 0.7 * ((resolution_progress - 0.3) / 0.7)
            
            curve.append(min(1.0, max(0.1, tension)))
        
        return curve
    
    def get_structure_description(self) -> str:
        return """In Medias Res begins in the middle of action, then uses flashbacks to provide context. This creates immediate engagement and mystery about how characters reached this point, before returning to resolve the opening situation."""


class CircularStructure(NarrativeStructure):
    """Structure where the ending mirrors or returns to the beginning."""
    
    def __init__(self):
        super().__init__()
        self.best_genres = ["literary fiction", "philosophical", "magical realism", "contemporary"]
        self.best_tones = ["philosophical", "contemplative", "melancholic", "whimsical", "intimate"]
        self.length_ranges = {
            StoryLength.SHORT: (8, 10),
            StoryLength.MEDIUM: (12, 18),
            StoryLength.LONG: (20, 25),
            StoryLength.EPIC: (28, 35)
        }
        self.words_per_scene_range = (700, 1000)
    
    def get_chapter_distribution(self) -> ChapterDistribution:
        return ChapterDistribution([
            ("Beginning/Setup", 0.20),
            ("Journey Outward", 0.30),
            ("Transformation", 0.30),
            ("Return/Mirror", 0.20)
        ])
    
    def get_scene_type_distribution(self) -> SceneTypeDistribution:
        return SceneTypeDistribution(
            action=0.15,
            dialogue=0.25,
            exploration=0.20,
            revelation=0.10,
            character_moment=0.20,
            transition=0.05,
            conflict=0.03,
            resolution=0.02
        )
    
    def get_tension_curve(self, num_chapters: int) -> List[float]:
        """Builds to middle, then mirrors back with transformation."""
        curve = []
        for i in range(num_chapters):
            progress = i / (num_chapters - 1)
            
            if progress < 0.20:  # Beginning
                tension = 0.3 + 0.2 * (progress / 0.20)
            elif progress < 0.50:  # Journey outward
                tension = 0.5 + 0.3 * ((progress - 0.20) / 0.30)
            elif progress < 0.80:  # Transformation
                tension = 0.8 - 0.2 * ((progress - 0.50) / 0.30)
            else:  # Return/Mirror
                tension = 0.6 - 0.3 * ((progress - 0.80) / 0.20)
            
            curve.append(min(1.0, max(0.1, tension)))
        
        return curve
    
    def get_structure_description(self) -> str:
        return """Circular narrative returns to where it began, but with transformed meaning. The journey changes the protagonist's perspective, making the familiar strange or the strange familiar. The ending recontextualizes the beginning."""


class NonlinearMosaicStructure(NarrativeStructure):
    """Structure with interconnected vignettes or time jumps."""
    
    def __init__(self):
        super().__init__()
        self.best_genres = ["literary fiction", "mystery", "psychological", "contemporary"]
        self.best_tones = ["mysterious", "contemplative", "philosophical", "dark", "intimate"]
        self.length_ranges = {
            StoryLength.SHORT: (10, 12),
            StoryLength.MEDIUM: (15, 20),
            StoryLength.LONG: (25, 30),
            StoryLength.EPIC: (35, 45)
        }
        self.words_per_scene_range = (600, 900)
    
    def get_chapter_distribution(self) -> ChapterDistribution:
        # Mosaic doesn't have traditional acts, but thematic groupings
        return ChapterDistribution([
            ("Introduction Fragments", 0.20),
            ("Deepening Connections", 0.30),
            ("Revelation Patterns", 0.30),
            ("Synthesis", 0.20)
        ])
    
    def get_scene_type_distribution(self) -> SceneTypeDistribution:
        return SceneTypeDistribution(
            action=0.10,
            dialogue=0.20,
            exploration=0.25,
            revelation=0.20,
            character_moment=0.15,
            transition=0.05,
            conflict=0.03,
            resolution=0.02
        )
    
    def get_tension_curve(self, num_chapters: int) -> List[float]:
        """Varies by vignette with overall rising pattern."""
        curve = []
        for i in range(num_chapters):
            progress = i / (num_chapters - 1)
            
            # Base rising tension
            base_tension = 0.3 + 0.5 * progress
            
            # Add variation for vignette structure
            vignette_variation = 0.2 * ((i % 3) - 1)
            
            tension = base_tension + vignette_variation
            curve.append(min(1.0, max(0.1, tension)))
        
        return curve
    
    def get_structure_description(self) -> str:
        return """Nonlinear/Mosaic structure presents the story through interconnected vignettes, time jumps, or multiple perspectives. The full picture emerges as pieces connect, creating a puzzle-like reading experience where meaning accumulates through patterns."""


# Structure selection functions

def get_all_structures() -> Dict[str, NarrativeStructure]:
    """Return all available narrative structures."""
    return {
        "hero_journey": HeroJourneyStructure(),
        "three_act": ThreeActStructure(),
        "kishotenketsu": KishotenketsuStructure(),
        "in_medias_res": InMediasResStructure(),
        "circular": CircularStructure(),
        "nonlinear_mosaic": NonlinearMosaicStructure()
    }


def get_structure_by_name(name: str) -> Optional[NarrativeStructure]:
    """Get a specific narrative structure by name."""
    structures = get_all_structures()
    return structures.get(name)


def recommend_structure(genre: str, tone: str, cultural_context: str = "western") -> List[Tuple[str, float]]:
    """Recommend narrative structures based on genre and tone.
    
    Returns a list of (structure_name, score) tuples, sorted by score descending.
    """
    structures = get_all_structures()
    recommendations = []
    
    for name, structure in structures.items():
        score = 0.0
        
        # Genre matching (most important)
        if genre.lower() in [g.lower() for g in structure.best_genres]:
            score += 0.6
        elif any(genre.lower() in g.lower() for g in structure.best_genres):
            score += 0.3
        
        # Tone matching
        if tone.lower() in [t.lower() for t in structure.best_tones]:
            score += 0.3
        elif any(tone.lower() in t.lower() for t in structure.best_tones):
            score += 0.15
        
        # Cultural context bonus
        if cultural_context == "eastern" and name == "kishotenketsu":
            score += 0.1
        elif cultural_context == "western" and name in ["three_act", "hero_journey"]:
            score += 0.05
        
        if score > 0:
            recommendations.append((name, score))
    
    # Sort by score descending
    recommendations.sort(key=lambda x: x[1], reverse=True)
    
    # If no strong matches, provide defaults
    if not recommendations or recommendations[0][1] < 0.3:
        if genre.lower() in ["fantasy", "adventure", "science fiction"]:
            recommendations.insert(0, ("hero_journey", 0.5))
        else:
            recommendations.insert(0, ("three_act", 0.5))
    
    return recommendations


def determine_story_length(
    structure: NarrativeStructure,
    complexity: str,
    subplot_count: int = 1,
    pov_count: int = 1
) -> Tuple[StoryLength, int, int]:
    """Determine appropriate story length based on various factors.
    
    Returns: (length_category, chapter_count, scenes_per_chapter)
    """
    # Base length on complexity
    if complexity == "simple":
        base_length = StoryLength.SHORT
    elif complexity == "moderate":
        base_length = StoryLength.MEDIUM
    elif complexity == "complex":
        base_length = StoryLength.LONG
    else:  # very complex
        base_length = StoryLength.EPIC
    
    # Adjust for subplots and POVs
    if subplot_count > 2 and base_length == StoryLength.SHORT:
        base_length = StoryLength.MEDIUM
    elif subplot_count > 3 and base_length == StoryLength.MEDIUM:
        base_length = StoryLength.LONG
    
    if pov_count > 2 and base_length == StoryLength.SHORT:
        base_length = StoryLength.MEDIUM
    elif pov_count > 3 and base_length == StoryLength.MEDIUM:
        base_length = StoryLength.LONG
    
    # Get chapter count
    chapter_count = structure.get_optimal_chapter_count(base_length)
    scenes_per_chapter = structure.default_scenes_per_chapter[base_length]
    
    return base_length, chapter_count, scenes_per_chapter


def calculate_story_parameters_from_pages(
    pages: int,
    structure: NarrativeStructure,
    words_per_page: int = 250
) -> Tuple[StoryLength, int, int, int]:
    """Calculate story parameters from target page count.
    
    Args:
        pages: Target number of pages
        structure: The narrative structure to use
        words_per_page: Average words per page (default: 250)
        
    Returns:
        Tuple of (length_category, chapter_count, scenes_per_chapter, words_per_scene)
    """
    # Calculate total target words
    total_words = pages * words_per_page
    
    # Determine story length category based on page count
    if pages <= 100:
        length_category = StoryLength.SHORT
    elif pages <= 250:
        length_category = StoryLength.MEDIUM
    elif pages <= 400:
        length_category = StoryLength.LONG
    else:
        length_category = StoryLength.EPIC
    
    # Get base chapter count for this length
    min_chapters, max_chapters = structure.get_chapter_range(length_category)
    
    # Calculate optimal chapter count based on structure preferences
    if structure.name == "NonlinearMosaicStructure":
        # Mosaic structures tend toward more chapters
        chapter_count = int(min_chapters + (max_chapters - min_chapters) * 0.7)
    elif structure.name == "KishotenketsuStructure":
        # Kishotenketsu works best with multiples of 4
        base = (min_chapters + max_chapters) // 2
        chapter_count = ((base + 3) // 4) * 4  # Round to nearest multiple of 4
    else:
        # Default to middle of range
        chapter_count = (min_chapters + max_chapters) // 2
    
    # Get scenes per chapter for this length
    scenes_per_chapter = structure.default_scenes_per_chapter[length_category]
    
    # Calculate total scenes
    total_scenes = chapter_count * scenes_per_chapter
    
    # Calculate words per scene to hit target
    words_per_scene = total_words // total_scenes
    
    # Apply structure-specific adjustments to words per scene
    min_words, max_words = structure.words_per_scene_range
    words_per_scene = max(min_words, min(max_words, words_per_scene))
    
    # If we're outside the range, adjust scenes per chapter
    if words_per_scene == max_words and total_words > total_scenes * max_words:
        # Need more scenes
        scenes_per_chapter = min(10, scenes_per_chapter + 2)
    elif words_per_scene == min_words and total_words < total_scenes * min_words:
        # Need fewer scenes
        scenes_per_chapter = max(2, scenes_per_chapter - 1)
    
    return length_category, chapter_count, scenes_per_chapter, words_per_scene


# Pydantic models for LLM structured output

from typing import Literal
from pydantic import field_validator

class NarrativeStructureAnalysis(BaseModel):
    """Analysis result for narrative structure selection."""
    primary_structure: Literal["hero_journey", "three_act", "kishotenketsu", "in_medias_res", "circular", "nonlinear_mosaic"] = Field(
        description="The recommended narrative structure (must be one of: hero_journey, three_act, kishotenketsu, in_medias_res, circular, nonlinear_mosaic)"
    )
    structure_reasoning: str = Field(
        description="Detailed explanation of why this structure best serves the story"
    )
    story_complexity: Literal["simple", "moderate", "complex", "very_complex"] = Field(
        description="Complexity assessment (must be one of: simple, moderate, complex, very_complex)"
    )
    complexity_reasoning: str = Field(
        description="Explanation of the complexity assessment"
    )
    story_length: Literal["short", "medium", "long", "epic"] = Field(
        description="Recommended length (must be one of: short, medium, long, epic)"
    )
    
    @field_validator('primary_structure', mode='before')
    @classmethod
    def normalize_structure(cls, v):
        """Normalize structure name to lowercase with underscores."""
        if isinstance(v, str):
            # Convert to lowercase and replace spaces with underscores
            normalized = v.lower().replace(' ', '_')
            # Handle specific cases
            if normalized == "in_medias_res":
                return "in_medias_res"
            elif normalized == "nonlinear/mosaic" or normalized == "nonlinear_mosaic":
                return "nonlinear_mosaic"
            return normalized
        return v
    
    @field_validator('story_complexity', mode='before')
    @classmethod
    def normalize_complexity(cls, v):
        """Normalize complexity to lowercase."""
        if isinstance(v, str):
            normalized = v.lower().replace(' ', '_')
            # Handle "very complex" -> "very_complex"
            if normalized == "very_complex":
                return "very_complex"
            return normalized
        return v
    
    @field_validator('story_length', mode='before')
    @classmethod
    def normalize_length(cls, v):
        """Normalize length to lowercase."""
        if isinstance(v, str):
            return v.lower()
        return v
    
    length_reasoning: str = Field(
        description="Explanation of the length recommendation"
    )
    structure_customization: str = Field(
        description="How the structure should be adapted for this specific story"
    )
    chapter_count: int = Field(
        description="Recommended total number of chapters",
        ge=5, le=50
    )
    scenes_per_chapter: int = Field(
        description="Recommended average scenes per chapter",
        ge=2, le=10
    )
    words_per_scene: int = Field(
        description="Recommended target words per scene",
        ge=300, le=2000
    )
    subplot_count: int = Field(
        description="Estimated number of subplots",
        ge=0, le=10
    )
    pov_count: int = Field(
        description="Estimated number of POV characters",
        ge=1, le=10
    )