"""
World Building Researcher - Orchestrates research for world building elements.

This module provides the main researcher class that manages the research
process for each world building category, including query generation,
search execution, and result synthesis.
"""

import asyncio
from typing import Dict, Any, List, Optional
from storyteller_lib.core.config import llm, get_current_provider
from storyteller_lib.core.logger import get_logger
from storyteller_lib.prompts.renderer import render_prompt
from storyteller_lib.universe.world.research_config import WorldBuildingResearchConfig
from storyteller_lib.universe.world.research_models import (
    ResearchResults, ResearchContext, CategoryResearchStrategy,
    SearchResult, Citation, ResearchInsight
)
from pydantic import BaseModel, Field
from typing import List as ListType
from storyteller_lib.universe.world.search_utils import (
    execute_parallel_searches, filter_results_by_relevance,
    deduplicate_results
)
from storyteller_lib.universe.world.research_strategies import get_category_strategy

logger = get_logger(__name__)


# Pydantic models for structured output
class SearchQueriesList(BaseModel):
    """Search queries for research as a flattened list."""
    query1: str = Field(description="First search query")
    query2: str = Field(description="Second search query")
    query3: str = Field(description="Third search query")
    query4: Optional[str] = Field(default="", description="Fourth search query (optional)")
    query5: Optional[str] = Field(default="", description="Fifth search query (optional)")


class ResearchInsightsFlat(BaseModel):
    """Flattened insights from research synthesis."""
    insight_keys: str = Field(
        description="Pipe-separated list of insight category names (e.g. 'historical_parallel|cultural_detail|geographic_inspiration')"
    )
    insight_values: str = Field(
        description="Pipe-separated list of insight descriptions corresponding to the keys"
    )


class ResearchSummary(BaseModel):
    """Summary of research findings."""
    summary: str = Field(
        description="Concise paragraph summarizing the most valuable findings"
    )


class WorldBuildingResearcher:
    """Orchestrates research for world building elements."""
    
    def __init__(self, config: WorldBuildingResearchConfig):
        """
        Initialize the researcher with configuration.
        
        Args:
            config: Research configuration
        """
        self.config = config
        self._cache = {} if config.cache_results else None
    
    async def research_initial_context(
        self,
        genre: str,
        tone: str,
        initial_idea: str,
        story_outline: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Research initial context for the story.
        
        Args:
            genre: Story genre
            tone: Story tone
            initial_idea: Initial story idea
            story_outline: Story outline if available
            
        Returns:
            Dictionary of initial research findings
        """
        logger.info("Starting initial context research")
        
        # Generate initial search queries
        queries = await self._generate_initial_queries(
            genre, tone, initial_idea, story_outline
        )
        
        # Execute searches
        search_results = await execute_parallel_searches(
            queries,
            search_api=self.config.search_apis[0],
            max_results_per_query=self.config.get_depth_params()["max_results_per_query"]
        )
        
        # Synthesize initial insights
        initial_insights = await self._synthesize_initial_insights(
            search_results, genre, tone, initial_idea
        )
        
        return {
            "queries": queries,
            "raw_results": search_results,
            "insights": initial_insights
        }
    
    async def research_category(
        self,
        category: str,
        context: ResearchContext,
        existing_research: Optional[Dict[str, Any]] = None
    ) -> ResearchResults:
        """
        Research a specific world building category.
        
        Args:
            category: Category name (e.g., "geography", "history")
            context: Research context
            existing_research: Previous research results
            
        Returns:
            ResearchResults object
        """
        logger.info(f"Researching category: {category}")
        
        # Check cache if enabled
        cache_key = f"{category}_{context.genre}_{context.tone}"
        if self._cache and cache_key in self._cache:
            logger.info(f"Using cached results for {category}")
            return self._cache[cache_key]
        
        # Get category-specific strategy
        strategy = get_category_strategy(category)
        
        # Generate search queries
        queries = await self._generate_category_queries(
            category, strategy, context, existing_research
        )
        
        # Execute searches (single iteration for simplicity and efficiency)
        logger.info(f"Executing search for {category}")
        
        # Execute searches
        search_results = await execute_parallel_searches(
            queries,
            search_api=self.config.search_apis[0],
            max_results_per_query=self.config.get_depth_params()["max_results_per_query"]
        )
        
        # Collect all results
        all_results = []
        for query_results in search_results.values():
            all_results.extend(query_results)
        
        # Process and filter results
        filtered_results = filter_results_by_relevance(all_results, min_relevance=0.5)
        unique_results = deduplicate_results(filtered_results)
        
        # Synthesize insights
        synthesized_insights = await self._synthesize_category_insights(
            category, unique_results, context
        )
        
        # Extract examples and citations
        examples = self._extract_relevant_examples(unique_results, category)
        citations = self._create_citations(unique_results, synthesized_insights)
        
        # Create research summary
        # Get language from context
        language = context.language
        summary = await self._create_research_summary(
            category, synthesized_insights, examples, language
        )
        
        # Build results
        results = ResearchResults(
            category=category,
            search_queries=queries,
            raw_findings=unique_results,
            synthesized_insights=synthesized_insights,
            relevant_examples=examples,
            source_citations=citations,
            research_summary=summary,
            confidence_score=self._calculate_confidence(unique_results, citations)
        )
        
        # Cache if enabled
        if self._cache:
            self._cache[cache_key] = results
        
        return results
    
    async def _generate_initial_queries(
        self,
        genre: str,
        tone: str,
        initial_idea: str,
        story_outline: Optional[str] = None
    ) -> List[str]:
        """Generate initial search queries."""
        try:
            # Get language from config (which comes from command line)
            language = self.config.language
            
            prompt = render_prompt(
                "research_initial_queries",
                language,
                genre=genre,
                tone=tone,
                initial_idea=initial_idea,
                story_outline=story_outline or "Not yet developed",
                num_queries=self.config.queries_per_category
            )
        except Exception as e:
            logger.error(f"Failed to render research_initial_queries template: {e}")
            raise
        
        structured_llm = llm.with_structured_output(SearchQueriesList)
        result = await structured_llm.ainvoke(prompt)
        # Convert to list
        queries = []
        for attr in ['query1', 'query2', 'query3', 'query4', 'query5']:
            query = getattr(result, attr, '')
            if query and query.strip():
                queries.append(query.strip())
        return queries[:self.config.queries_per_category]
    
    async def _generate_category_queries(
        self,
        category: str,
        strategy: CategoryResearchStrategy,
        context: ResearchContext,
        existing_research: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Generate search queries for a specific category."""
        # Get language from context
        language = context.language
        
        prompt = render_prompt(
            f"research_queries_{category}",
            language,
            context=context,
            strategy=strategy,
            existing_research=existing_research or {},
            num_queries=self.config.queries_per_category
        )
        
        structured_llm = llm.with_structured_output(SearchQueriesList)
        result = await structured_llm.ainvoke(prompt)
        # Convert to list
        queries = []
        for attr in ['query1', 'query2', 'query3', 'query4', 'query5']:
            query = getattr(result, attr, '')
            if query and query.strip():
                queries.append(query.strip())
        return queries[:self.config.queries_per_category]
    
    async def _synthesize_initial_insights(
        self,
        search_results: Dict[str, List[SearchResult]],
        genre: str,
        tone: str,
        initial_idea: str
    ) -> Dict[str, str]:
        """Synthesize initial insights from search results."""
        # Combine all results
        all_results = []
        for results in search_results.values():
            all_results.extend(results)
        
        if not all_results:
            return {"general": "No research findings available"}
        
        # Format results for synthesis
        results_text = self._format_results_for_synthesis(all_results[:10])
        
        try:
            # Get language from config (which comes from command line)
            language = self.config.language
            
            prompt = render_prompt(
                "research_synthesis_initial",
                language,
                research_findings=results_text,
                genre=genre,
                tone=tone,
                initial_idea=initial_idea
            )
        except Exception as e:
            logger.error(f"Failed to render research_synthesis_initial template: {e}")
            raise
        
        structured_llm = llm.with_structured_output(ResearchInsightsFlat)
        result = await structured_llm.ainvoke(prompt)
        
        # Convert flattened structure to dictionary
        keys = [k.strip() for k in result.insight_keys.split("|")]
        values = [v.strip() for v in result.insight_values.split("|")]
        
        insights = {}
        for key, value in zip(keys, values):
            if key and value:
                insights[key] = value
        
        return insights
    
    async def _synthesize_category_insights(
        self,
        category: str,
        results: List[SearchResult],
        context: ResearchContext
    ) -> Dict[str, str]:
        """Synthesize insights for a specific category."""
        if not results:
            return {f"{category}_general": f"No specific research findings for {category}"}
        
        # Format results
        results_text = self._format_results_for_synthesis(results[:15])
        
        try:
            # Get language from context or use default
            language = context.language if hasattr(context, 'language') else context.get('language', 'english')
            
            # Try category-specific template first, then fall back to generic
            try:
                prompt = render_prompt(
                    f"research_synthesis_{category}",
                    language,
                    category=category,
                    research_findings=results_text,
                    context=context,
                    initial_idea=context.initial_idea
                )
            except Exception as category_error:
                logger.warning(f"Category-specific template not found, using generic: {category_error}")
                prompt = render_prompt(
                    "research_synthesis",
                    language,
                    category=category,
                    research_findings=results_text,
                    context=context,
                    initial_idea=context.initial_idea
                )
        except Exception as e:
            logger.error(f"Failed to render research synthesis template: {e}")
            raise
        
        structured_llm = llm.with_structured_output(ResearchInsightsFlat)
        result = await structured_llm.ainvoke(prompt)
        
        # Convert flattened structure to dictionary
        keys = [k.strip() for k in result.insight_keys.split("|")]
        values = [v.strip() for v in result.insight_values.split("|")]
        
        insights = {}
        for key, value in zip(keys, values):
            if key and value:
                insights[key] = value
        
        return insights
    
    def _format_results_for_synthesis(self, results: List[SearchResult]) -> str:
        """Format search results for LLM synthesis."""
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(f"{i}. {result.title}")
            # Use full content from extraction if available, otherwise use snippet
            content = result.metadata.get("raw_content", result.content)
            # For extracted content (markdown), we want to preserve much more
            # Only limit if it's extremely long (>50k chars)
            if len(content) > 50000:
                # Keep first 45k chars to leave room for multiple results
                content = content[:45000] + "\n\n[Content truncated...]"
            formatted.append(f"   {content}")
            if result.url:
                formatted.append(f"   Source: {result.url}")
            formatted.append("")
        return '\n'.join(formatted)
    
    async def _refine_queries(
        self,
        category: str,
        strategy: CategoryResearchStrategy,
        context: ResearchContext,
        current_results: List[SearchResult]
    ) -> List[str]:
        """Refine search queries based on current results."""
        # Simple refinement - look for gaps in coverage
        results_summary = self._format_results_for_synthesis(current_results[:5])
        
        # Get language from context
        language = context.language if hasattr(context, 'language') else context.get('language', 'english')
        
        prompt = render_prompt(
            "research_refine_queries",
            language,
            category=category,
            context=context,
            strategy=strategy,
            results_summary=results_summary,
            num_queries=self.config.queries_per_category
        )
        
        structured_llm = llm.with_structured_output(SearchQueriesList)
        result = await structured_llm.ainvoke(prompt)
        # Convert to list
        queries = []
        for attr in ['query1', 'query2', 'query3', 'query4', 'query5']:
            query = getattr(result, attr, '')
            if query and query.strip():
                queries.append(query.strip())
        return queries[:self.config.queries_per_category]
    
    def _extract_relevant_examples(
        self,
        results: List[SearchResult],
        category: str
    ) -> List[Dict[str, Any]]:
        """Extract concrete examples from search results."""
        examples = []
        for result in results[:10]:  # Limit examples
            if result.relevance_score > 0.6:
                examples.append({
                    "title": result.title,
                    "description": result.content[:200],
                    "relevance_to_category": category,
                    "source": result.url or "Research finding"
                })
        return examples
    
    def _create_citations(
        self,
        results: List[SearchResult],
        insights: Dict[str, str]
    ) -> List[Citation]:
        """Create citations from search results."""
        citations = []
        
        # Create citations for high-relevance results
        for result in results:
            if result.relevance_score > 0.6:
                citations.append(Citation(
                    source_name=result.title,
                    source_url=result.url,
                    relevant_quote=result.content[:200],
                    relevance_score=result.relevance_score
                ))
        
        return citations[:20]  # Limit citations
    
    async def _create_research_summary(
        self,
        category: str,
        insights: Dict[str, str],
        examples: List[Dict[str, Any]],
        language: str
    ) -> str:
        """Create a summary of research findings."""
        insights_text = '\n'.join([f"- {k}: {v}" for k, v in insights.items()])
        examples_text = '\n'.join([f"- {e['title']}: {e['description']}" for e in examples[:5]])
        
        prompt = render_prompt(
            "research_create_summary",
            language,
            category=category,
            insights_text=insights_text,
            examples_text=examples_text
        )
        
        structured_llm = llm.with_structured_output(ResearchSummary)
        result = await structured_llm.ainvoke(prompt)
        return result.summary
    
    def _calculate_confidence(
        self,
        results: List[SearchResult],
        citations: List[Citation]
    ) -> float:
        """Calculate confidence score for research quality."""
        if not results:
            return 0.0
        
        # Factors: number of results, average relevance, citation quality
        num_results_score = min(len(results) / 20, 1.0)  # More results = higher confidence
        avg_relevance = sum(r.relevance_score for r in results) / len(results)
        citation_score = min(len(citations) / 10, 1.0)  # Good citation coverage
        
        # Weighted average
        confidence = (num_results_score * 0.3 + avg_relevance * 0.5 + citation_score * 0.2)
        
        return round(confidence, 2)