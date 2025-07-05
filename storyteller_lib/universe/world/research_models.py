"""
Data models for research results in world building.

This module defines the structure for research findings,
citations, and synthesized insights used in research-driven
world building.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Individual search result from a web search."""

    title: str = Field(description="Title of the search result")
    url: str | None = Field(default=None, description="URL of the source")
    content: str = Field(description="Content excerpt from the source")
    relevance_score: float = Field(
        default=0.0, description="Relevance score for this result (0-1)"
    )
    source_type: str | None = Field(
        default="web", description="Type of source (web, academic, book, etc.)"
    )
    metadata: dict[str, Any] | None = Field(
        default=None, description="Additional metadata about the source"
    )


class Citation(BaseModel):
    """Source citation for research findings."""

    source_name: str = Field(description="Name of the source")
    source_url: str | None = Field(default=None, description="URL if available")
    relevant_quote: str = Field(description="Relevant quote from the source")
    relevance_score: float = Field(
        default=0.0, description="How relevant this citation is (0-1)"
    )
    accessed_date: datetime | None = Field(
        default_factory=datetime.now, description="When this source was accessed"
    )


class ResearchInsight(BaseModel):
    """Synthesized insight from research."""

    insight: str = Field(description="The synthesized insight")
    supporting_sources: list[Citation] = Field(
        default_factory=list, description="Citations supporting this insight"
    )
    confidence: float = Field(
        default=0.0, description="Confidence in this insight (0-1)"
    )
    category_relevance: str = Field(
        description="Which world building category this relates to"
    )


class ResearchResults(BaseModel):
    """Complete results from research for a world building category."""

    category: str = Field(description="World building category researched")
    search_queries: list[str] = Field(
        default_factory=list, description="Search queries used"
    )
    raw_findings: list[SearchResult] = Field(
        default_factory=list, description="Raw search results"
    )
    synthesized_insights: dict[str, str] = Field(
        default_factory=dict, description="Key insights synthesized from research"
    )
    relevant_examples: list[dict[str, Any]] = Field(
        default_factory=list, description="Concrete examples found in research"
    )
    source_citations: list[Citation] = Field(
        default_factory=list, description="All citations for transparency"
    )
    research_summary: str | None = Field(
        default=None, description="Overall summary of research findings"
    )
    confidence_score: float = Field(
        default=0.0, description="Overall confidence in research quality (0-1)"
    )


class CategoryResearchStrategy(BaseModel):
    """Strategy for researching a specific world building category."""

    category_name: str = Field(description="Name of the category")
    focus_areas: list[str] = Field(description="Key areas to focus research on")
    query_templates: list[str] = Field(description="Template queries for this category")
    evaluation_criteria: list[str] = Field(
        description="Criteria for evaluating research quality"
    )
    min_sources: int = Field(
        default=3, description="Minimum number of quality sources needed"
    )


class ResearchContext(BaseModel):
    """Context for conducting research."""

    genre: str = Field(description="Story genre")
    tone: str = Field(description="Story tone")
    initial_idea: str = Field(description="Initial story idea")
    story_outline: str | None = Field(
        default=None, description="Story outline if available"
    )
    existing_world_elements: dict[str, Any] | None = Field(
        default=None, description="Already generated world elements"
    )
    language: str = Field(description="Target language for the story")
    cultural_context: str | None = Field(
        default=None, description="Specific cultural context to consider"
    )
    time_period: str | None = Field(
        default=None, description="Time period for historical stories"
    )
