"""
Category-specific research strategies for world building.

This module defines research strategies for each world building category,
including focus areas, query templates, and evaluation criteria.
"""


from storyteller_lib.universe.world.research_models import CategoryResearchStrategy

# Define research strategies for each category
CATEGORY_STRATEGIES = {
    "geography": CategoryResearchStrategy(
        category_name="geography",
        focus_areas=[
            "Physical landscapes and terrain",
            "Climate patterns and weather",
            "Natural resources and ecosystems",
            "Geographic barriers and connections",
            "Settlement patterns",
        ],
        query_templates=[
            "[region] geography climate characteristics",
            "[terrain_type] landscape formation geology",
            "[climate_zone] weather patterns seasons",
            "[ecosystem] flora fauna biodiversity",
            "geographic features [similar_to_story_setting]",
        ],
        evaluation_criteria=[
            "Specific geographic details",
            "Climate accuracy",
            "Ecological consistency",
            "Impact on human settlement",
        ],
        min_sources=3,
    ),
    "history": CategoryResearchStrategy(
        category_name="history",
        focus_areas=[
            "Historical periods and timelines",
            "Major events and turning points",
            "Social and political changes",
            "Technological progression",
            "Cultural evolution",
        ],
        query_templates=[
            "[time_period] historical events timeline",
            "[civilization_type] rise fall history",
            "[conflict_type] historical wars causes outcomes",
            "social transitions [era] to [era]",
            "[region] [time_period] historical context",
        ],
        evaluation_criteria=[
            "Chronological accuracy",
            "Cause and effect relationships",
            "Social impact",
            "Historical parallels",
        ],
        min_sources=4,
    ),
    "culture": CategoryResearchStrategy(
        category_name="culture",
        focus_areas=[
            "Customs and traditions",
            "Language and communication",
            "Arts and entertainment",
            "Social hierarchies",
            "Values and beliefs",
        ],
        query_templates=[
            "[culture_type] traditions customs rituals",
            "[language_family] linguistic features",
            "[art_form] cultural significance history",
            "social structure [society_type]",
            "[culture] values belief systems",
        ],
        evaluation_criteria=[
            "Cultural authenticity",
            "Internal consistency",
            "Social dynamics",
            "Artistic expression",
        ],
        min_sources=3,
    ),
    "politics": CategoryResearchStrategy(
        category_name="politics",
        focus_areas=[
            "Government structures",
            "Power dynamics",
            "Political ideologies",
            "Legal systems",
            "International relations",
        ],
        query_templates=[
            "[government_type] political system structure",
            "political power dynamics [context]",
            "[ideology] political philosophy principles",
            "legal system [culture/period] justice",
            "[region] political factions conflicts",
        ],
        evaluation_criteria=[
            "System coherence",
            "Power balance",
            "Legal consistency",
            "Political realism",
        ],
        min_sources=3,
    ),
    "economics": CategoryResearchStrategy(
        category_name="economics",
        focus_areas=[
            "Economic systems",
            "Trade and commerce",
            "Resource distribution",
            "Labor and production",
            "Wealth inequality",
        ],
        query_templates=[
            "[economic_system] trade commerce history",
            "resource management [context] strategies",
            "[time_period] economic structure",
            "wealth distribution [society_type]",
            "[region] trade routes commodities",
        ],
        evaluation_criteria=[
            "Economic viability",
            "Trade logic",
            "Resource realism",
            "Social impact",
        ],
        min_sources=3,
    ),
    "technology_magic": CategoryResearchStrategy(
        category_name="technology_magic",
        focus_areas=[
            "Technological capabilities",
            "Scientific principles",
            "Innovation patterns",
            "Limitations and constraints",
            "Social impact of technology",
        ],
        query_templates=[
            "[technology_type] development history",
            "emerging technologies [field] possibilities",
            "[time_period] technological capabilities",
            "technology limitations constraints [context]",
            "[innovation] social impact consequences",
        ],
        evaluation_criteria=[
            "Scientific plausibility",
            "Technological consistency",
            "Innovation logic",
            "Social integration",
        ],
        min_sources=4,
    ),
    "religion": CategoryResearchStrategy(
        category_name="religion",
        focus_areas=[
            "Belief systems",
            "Religious practices",
            "Sacred texts and mythology",
            "Religious institutions",
            "Spiritual experiences",
        ],
        query_templates=[
            "[religion_type] beliefs core tenets",
            "religious rituals [context] practices",
            "[mythology_type] sacred stories",
            "religious organizations hierarchy [period]",
            "[belief_system] spiritual practices",
        ],
        evaluation_criteria=[
            "Theological coherence",
            "Ritual authenticity",
            "Institutional structure",
            "Spiritual depth",
        ],
        min_sources=3,
    ),
    "daily_life": CategoryResearchStrategy(
        category_name="daily_life",
        focus_areas=[
            "Food and cuisine",
            "Clothing and fashion",
            "Housing and architecture",
            "Work and leisure",
            "Social interactions",
        ],
        query_templates=[
            "[time/place] daily life customs",
            "traditional cuisine [region/culture]",
            "[period] clothing fashion trends",
            "architectural styles [context]",
            "[society] work leisure activities",
        ],
        evaluation_criteria=[
            "Lifestyle authenticity",
            "Material culture accuracy",
            "Social realism",
            "Period appropriateness",
        ],
        min_sources=3,
    ),
}


def get_category_strategy(category: str) -> CategoryResearchStrategy:
    """
    Get the research strategy for a specific category.

    Args:
        category: Category name

    Returns:
        CategoryResearchStrategy object
    """
    strategy = CATEGORY_STRATEGIES.get(category.lower())
    if not strategy:
        # Return a generic strategy for unknown categories
        return CategoryResearchStrategy(
            category_name=category,
            focus_areas=["General information", "Key characteristics", "Examples"],
            query_templates=[
                f"{category} characteristics features",
                f"{category} examples types",
                f"{category} information overview",
            ],
            evaluation_criteria=["Relevance", "Accuracy", "Completeness"],
            min_sources=2,
        )
    return strategy


def get_all_strategies() -> dict[str, CategoryResearchStrategy]:
    """Get all category research strategies."""
    return CATEGORY_STRATEGIES.copy()


def customize_strategy_for_genre(
    strategy: CategoryResearchStrategy, genre: str
) -> CategoryResearchStrategy:
    """
    Customize a research strategy based on genre.

    Args:
        strategy: Base strategy
        genre: Story genre

    Returns:
        Customized strategy
    """
    # Genre-specific adjustments
    genre_adjustments = {
        "sci-fi": {
            "technology_magic": {
                "focus_areas": strategy.focus_areas
                + ["Future technologies", "Space exploration"],
                "query_templates": strategy.query_templates
                + ["theoretical physics [concept]", "space colonization technology"],
            }
        },
        "fantasy": {
            "technology_magic": {
                "focus_areas": [
                    "Magic systems",
                    "Mythological precedents",
                    "Magical limitations",
                ],
                "query_templates": [
                    "mythology magic systems",
                    "[culture] magical traditions",
                    "fantasy magic limitations",
                ],
            }
        },
        "historical": {
            "history": {
                "focus_areas": strategy.focus_areas
                + ["Primary sources", "Historical accuracy"],
                "min_sources": 5,
            }
        },
        "mystery": {
            "daily_life": {
                "focus_areas": strategy.focus_areas
                + ["Investigative procedures", "Forensics"],
                "query_templates": strategy.query_templates
                + [
                    "detective investigation methods [period]",
                    "forensic science [time_period]",
                ],
            }
        },
    }

    # Apply genre-specific adjustments if available
    if genre.lower() in genre_adjustments:
        adjustments = genre_adjustments[genre.lower()].get(strategy.category_name, {})

        # Create a new strategy with adjustments
        new_data = strategy.model_dump()
        new_data.update(adjustments)
        return CategoryResearchStrategy(**new_data)

    return strategy
