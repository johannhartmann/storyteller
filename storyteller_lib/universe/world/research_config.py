"""
Configuration models for research-driven world building.

This module provides configuration classes for the research-based
world building system, allowing customization of search APIs,
research depth, and other parameters.
"""

import os
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


class WorldBuildingResearchConfig(BaseModel):
    """Configuration for research-driven world building."""
    
    enable_research: bool = Field(
        default=False,
        description="Enable research-driven world building"
    )
    
    search_apis: List[str] = Field(
        default=["tavily"],
        description="Search APIs to use for research (tavily, arxiv, pubmed, etc.)"
    )
    
    research_depth: Literal["shallow", "medium", "deep"] = Field(
        default="medium",
        description="How extensive the research should be"
    )
    
    queries_per_category: int = Field(
        default=3,
        description="Number of search queries per world building category"
    )
    
    max_search_iterations: int = Field(
        default=2,
        description="Maximum refinement iterations for search"
    )
    
    include_sources: bool = Field(
        default=True,
        description="Include source citations in world elements"
    )
    
    parallel_research: bool = Field(
        default=True,
        description="Execute category research in parallel"
    )
    
    language: str = Field(
        default="english",
        description="Language for prompts and templates"
    )
    
    cache_results: bool = Field(
        default=True,
        description="Cache research results for reuse"
    )
    
    search_api_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional configuration for search APIs"
    )
    
    tavily_cache_enabled: bool = Field(
        default=True,
        description="Enable caching of Tavily API calls"
    )
    
    tavily_cache_ttl_days: int = Field(
        default=30,
        description="TTL for Tavily cache entries in days"
    )
    
    tavily_cache_path: Optional[str] = Field(
        default=None,
        description="Path to Tavily cache database"
    )
    
    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "WorldBuildingResearchConfig":
        """Create configuration from story config dictionary."""
        research_config = config.get("world_building_research", {})
        # Add language from story config
        research_config["language"] = config.get("language", "english")
        
        # Load cache settings from environment if not in config
        if "tavily_cache_enabled" not in research_config:
            research_config["tavily_cache_enabled"] = os.getenv("TAVILY_CACHE_ENABLED", "true").lower() == "true"
        
        if "tavily_cache_ttl_days" not in research_config:
            research_config["tavily_cache_ttl_days"] = int(os.getenv("TAVILY_CACHE_TTL_DAYS", "30"))
        
        if "tavily_cache_path" not in research_config:
            cache_path = os.getenv("TAVILY_CACHE_PATH")
            if cache_path:
                research_config["tavily_cache_path"] = cache_path
        
        return cls(**research_config)
    
    def get_depth_params(self) -> Dict[str, int]:
        """Get parameters based on research depth."""
        depth_map = {
            "shallow": {
                "queries_per_category": 2,
                "max_results_per_query": 3,
                "max_search_iterations": 1
            },
            "medium": {
                "queries_per_category": 3,
                "max_results_per_query": 5,
                "max_search_iterations": 2
            },
            "deep": {
                "queries_per_category": 5,
                "max_results_per_query": 10,
                "max_search_iterations": 3
            }
        }
        return depth_map.get(self.research_depth, depth_map["medium"])