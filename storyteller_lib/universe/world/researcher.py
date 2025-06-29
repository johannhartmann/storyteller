"""
World Building Researcher - Orchestrates research for world building elements.

This module provides the main researcher class that manages the research
process for each world building category, including query generation,
search execution, and result synthesis.
"""

import asyncio
from typing import Dict, Any, List, Optional
from storyteller_lib.core.config import llm
from storyteller_lib.core.logger import get_logger
from storyteller_lib.prompts.renderer import render_prompt
from storyteller_lib.universe.world.research_config import WorldBuildingResearchConfig
from storyteller_lib.universe.world.research_models import (
    ResearchResults, ResearchContext, CategoryResearchStrategy,
    SearchResult, Citation, ResearchInsight
)
from storyteller_lib.universe.world.search_utils import (
    execute_parallel_searches, filter_results_by_relevance,
    deduplicate_results
)
from storyteller_lib.universe.world.research_strategies import get_category_strategy

logger = get_logger(__name__)


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
        
        # Execute searches with iteration
        all_results = []
        for iteration in range(self.config.max_search_iterations):
            logger.info(f"Search iteration {iteration + 1} for {category}")
            
            # Execute searches
            search_results = await execute_parallel_searches(
                queries,
                search_api=self.config.search_apis[0],
                max_results_per_query=self.config.get_depth_params()["max_results_per_query"]
            )
            
            # Collect results
            for query_results in search_results.values():
                all_results.extend(query_results)
            
            # Refine queries based on results if not last iteration
            if iteration < self.config.max_search_iterations - 1:
                queries = await self._refine_queries(
                    category, strategy, context, all_results
                )
        
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
        summary = await self._create_research_summary(
            category, synthesized_insights, examples
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
            prompt = render_prompt(
                "research_initial_queries",
                "english",
                genre=genre,
                tone=tone,
                initial_idea=initial_idea,
                story_outline=story_outline or "Not yet developed",
                num_queries=self.config.queries_per_category
            )
        except:
            # Fallback if template doesn't exist
            prompt = f"""
            Generate {self.config.queries_per_category} search queries to research context for a {genre} story with {tone} tone.
            
            Story idea: {initial_idea}
            
            Create specific, searchable queries that would help understand:
            - Real-world parallels and inspiration
            - Historical or contemporary context
            - Cultural and geographic settings
            
            Return only the queries, one per line.
            """
        
        response = await llm.ainvoke(prompt)
        queries = [q.strip() for q in response.content.strip().split('\n') if q.strip()]
        return queries[:self.config.queries_per_category]
    
    async def _generate_category_queries(
        self,
        category: str,
        strategy: CategoryResearchStrategy,
        context: ResearchContext,
        existing_research: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Generate search queries for a specific category."""
        try:
            # Get language from context or use default
            language = context.language if hasattr(context, 'language') else context.get('language', 'english')
            
            prompt = render_prompt(
                f"research_queries_{category}",
                language,
                context=context,
                strategy=strategy,
                existing_research=existing_research or {},
                num_queries=self.config.queries_per_category
            )
        except:
            # Fallback using strategy templates
            base_queries = []
            for template in strategy.query_templates[:self.config.queries_per_category]:
                # Simple template substitution
                query = template
                if "[genre]" in query:
                    query = query.replace("[genre]", context.genre)
                if "[tone]" in query:
                    query = query.replace("[tone]", context.tone)
                if "[time_period]" in query:
                    query = query.replace("[time_period]", context.time_period or "contemporary")
                base_queries.append(query)
            
            return base_queries
        
        response = await llm.ainvoke(prompt)
        queries = [q.strip() for q in response.content.strip().split('\n') if q.strip()]
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
            prompt = render_prompt(
                "research_synthesis_initial",
                "english",
                research_findings=results_text,
                genre=genre,
                tone=tone,
                initial_idea=initial_idea
            )
        except:
            # Fallback prompt
            prompt = f"""
            Based on these research findings, synthesize key insights for a {genre} story with {tone} tone:
            
            {results_text}
            
            Story idea: {initial_idea}
            
            Extract insights about:
            1. Real-world settings or parallels
            2. Historical or cultural context
            3. Interesting details that could enrich the story
            
            Format as key: insight pairs.
            """
        
        response = await llm.ainvoke(prompt)
        
        # Parse insights
        insights = {}
        for line in response.content.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                insights[key.strip()] = value.strip()
        
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
            prompt = render_prompt(
                f"research_synthesis_{category}",
                "english",
                category=category,
                research_findings=results_text,
                context=context
            )
        except:
            # Fallback prompt
            prompt = f"""
            Synthesize research findings for {category} elements in a {context.genre} story:
            
            Research findings:
            {results_text}
            
            Story context: {context.initial_idea}
            
            Extract key insights specifically relevant to {category} that would:
            - Add authenticity and depth
            - Support the {context.tone} tone
            - Fit the {context.genre} genre
            
            Format as focused insights for worldbuilding.
            """
        
        response = await llm.ainvoke(prompt)
        
        # Parse insights specific to category
        insights = {}
        for line in response.content.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                insights[key.strip()] = value.strip()
        
        return insights
    
    def _format_results_for_synthesis(self, results: List[SearchResult]) -> str:
        """Format search results for LLM synthesis."""
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(f"{i}. {result.title}")
            formatted.append(f"   {result.content[:500]}...")
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
        
        prompt = f"""
        Based on initial research for {category} in a {context.genre} story:
        
        Current findings:
        {results_summary}
        
        Focus areas needed: {', '.join(strategy.focus_areas)}
        
        Generate {self.config.queries_per_category} refined search queries to fill gaps and get more specific information.
        Return only the queries, one per line.
        """
        
        response = await llm.ainvoke(prompt)
        queries = [q.strip() for q in response.content.strip().split('\n') if q.strip()]
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
        examples: List[Dict[str, Any]]
    ) -> str:
        """Create a summary of research findings."""
        insights_text = '\n'.join([f"- {k}: {v}" for k, v in insights.items()])
        examples_text = '\n'.join([f"- {e['title']}: {e['description']}" for e in examples[:5]])
        
        prompt = f"""
        Summarize research findings for {category} worldbuilding:
        
        Key insights:
        {insights_text}
        
        Notable examples:
        {examples_text}
        
        Create a concise paragraph summarizing the most valuable findings for worldbuilding.
        """
        
        response = await llm.ainvoke(prompt)
        return response.content.strip()
    
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