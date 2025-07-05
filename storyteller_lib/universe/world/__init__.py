"""
World building package for StoryCraft Agent.

This package provides world building functionality including:
- Standard LLM-based world generation
- Research-driven world building
- World element management and updates
"""

from storyteller_lib.universe.world.builder import (
    generate_worldbuilding,
    extract_worldbuilding,
    extract_specific_element,
    extract_mystery_elements,
    generate_world_summary,
    Geography,
    History,
    Culture,
    Politics,
    Economics,
    TechnologyMagic,
    Religion,
    DailyLife,
    WorldbuildingElements,
)

# Research components (optional)
try:
    from storyteller_lib.universe.world.research_config import (
        WorldBuildingResearchConfig,
    )
    from storyteller_lib.universe.world.researcher import WorldBuildingResearcher
    from storyteller_lib.universe.world.research_integration import (
        generate_worldbuilding_with_research,
        generate_category_with_research,
    )
    from storyteller_lib.universe.world.research_models import (
        ResearchResults,
        ResearchContext,
        SearchResult,
        Citation,
    )

    RESEARCH_AVAILABLE = True
except ImportError:
    RESEARCH_AVAILABLE = False

__all__ = [
    # Core world building
    "generate_worldbuilding",
    "extract_worldbuilding",
    "extract_specific_element",
    "extract_mystery_elements",
    "generate_world_summary",
    # Models
    "Geography",
    "History",
    "Culture",
    "Politics",
    "Economics",
    "TechnologyMagic",
    "Religion",
    "DailyLife",
    "WorldbuildingElements",
]

# Add research components if available
if RESEARCH_AVAILABLE:
    __all__.extend(
        [
            "WorldBuildingResearchConfig",
            "WorldBuildingResearcher",
            "generate_worldbuilding_with_research",
            "generate_category_with_research",
            "ResearchResults",
            "ResearchContext",
            "SearchResult",
            "Citation",
            "RESEARCH_AVAILABLE",
        ]
    )
