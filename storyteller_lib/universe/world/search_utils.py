"""
Search utilities for research-driven world building.

This module provides functions for executing web searches
using various APIs like Tavily, and processing the results.
"""

import os
import asyncio
from typing import List, Dict, Any, Optional
from tavily import AsyncTavilyClient
from storyteller_lib.core.logger import get_logger
from storyteller_lib.universe.world.research_models import SearchResult
from storyteller_lib.universe.world.cache import TavilyCache

logger = get_logger(__name__)


class SearchAPIError(Exception):
    """Error raised when search API fails."""

    pass


async def search_with_tavily(
    query: str,
    max_results: int = 5,
    api_key: Optional[str] = None,
    use_cache: Optional[bool] = None,
) -> List[SearchResult]:
    """
    Execute a search using Tavily API with two-step approach:
    1. Search for relevant pages
    2. Extract full content from top 3 pages

    Args:
        query: Search query
        max_results: Maximum number of results
        api_key: Tavily API key (uses env var if not provided)
        use_cache: Whether to use cache (defaults to env var TAVILY_CACHE_ENABLED)

    Returns:
        List of SearchResult objects
    """
    try:
        # Get API key
        api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise SearchAPIError(
                "Tavily API key not found. Set TAVILY_API_KEY environment variable."
            )

        # Check if caching is enabled
        if use_cache is None:
            use_cache = os.getenv("TAVILY_CACHE_ENABLED", "true").lower() == "true"

        # Initialize cache if enabled
        cache = None
        if use_cache:
            cache_path = os.getenv("TAVILY_CACHE_PATH")
            cache_ttl = int(os.getenv("TAVILY_CACHE_TTL_DAYS", "30"))
            cache = TavilyCache(cache_path=cache_path, ttl_days=cache_ttl)

        # Initialize Tavily client
        client = AsyncTavilyClient(api_key=api_key)

        # Step 1: Search (only get snippets, not full content)
        search_depth = "advanced"

        # Check cache first
        response = None
        if cache:
            response = cache.get_search_cache(query, max_results, search_depth)

        if not response:
            # Cache miss - make API call
            response = await client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_raw_content=False,  # Don't get raw content in search
            )

            # Cache the response
            if cache and response:
                cache.set_search_cache(query, max_results, search_depth, response)

        # Extract results array from the response
        results = response.get("results", [])

        # Convert to SearchResult objects
        search_results = []
        urls_to_extract = []

        for idx, result in enumerate(results):
            url = result.get("url")
            if url:
                urls_to_extract.append(url)
                search_results.append(
                    SearchResult(
                        title=result.get("title", f"Result {idx + 1}"),
                        url=url,
                        content=result.get("content", ""),  # Initial snippet
                        relevance_score=result.get("score", 0.5),
                        source_type="web",
                        metadata={
                            "snippet": result.get("content", ""),
                            "published_date": result.get("published_date"),
                        },
                    )
                )

        # Step 2: Extract full content from top 3 URLs
        if urls_to_extract and len(search_results) > 0:
            # Only extract from top 3 most relevant results
            extract_urls = urls_to_extract[:3]
            extract_format = "markdown"

            try:
                # Check cache first for extract
                extract_response = None
                if cache:
                    extract_response = cache.get_extract_cache(
                        extract_urls, extract_format
                    )

                if not extract_response:
                    # Cache miss - make API call
                    extract_response = await client.extract(
                        urls=extract_urls,
                        format=extract_format,  # Get content in markdown format
                    )

                    # Cache the response
                    if cache and extract_response:
                        cache.set_extract_cache(
                            extract_urls, extract_format, extract_response
                        )

                # Process extracted content
                extracted_results = extract_response.get("results", [])

                for i, extracted in enumerate(extracted_results):
                    if i < len(search_results) and extracted.get("success", False):
                        # Update the corresponding search result with full content
                        full_content = extracted.get("raw_content", "")
                        if full_content:
                            search_results[i].content = full_content
                            search_results[i].metadata["raw_content"] = full_content
                            search_results[i].metadata["content_format"] = "markdown"
                            logger.info(
                                f"Extracted {len(full_content)} chars from {search_results[i].url}"
                            )

            except Exception as e:
                logger.warning(f"Failed to extract full content: {str(e)}")
                # Continue with snippet content if extraction fails

        return search_results

    except Exception as e:
        logger.error(f"Tavily search failed for query '{query}': {str(e)}")
        raise SearchAPIError(f"Tavily search failed: {str(e)}")


async def search_with_arxiv(
    query: str, max_results: int = 5, **kwargs
) -> List[SearchResult]:
    """
    Execute a search using ArXiv API for academic papers.

    Args:
        query: Search query
        max_results: Maximum number of results
        **kwargs: Additional parameters

    Returns:
        List of SearchResult objects
    """
    try:
        from langchain_community.tools.arxiv.tool import ArxivQueryRun

        # Initialize ArXiv search tool
        arxiv_tool = ArxivQueryRun()

        # Execute search
        results_text = await asyncio.to_thread(arxiv_tool.run, query)

        # Parse results (ArXiv returns text format)
        # This is a simplified parser - could be improved
        search_results = []
        if results_text:
            # Split by double newlines to separate papers
            papers = results_text.split("\n\n")
            for idx, paper in enumerate(papers[:max_results]):
                if paper.strip():
                    search_results.append(
                        SearchResult(
                            title=f"ArXiv Paper {idx + 1}",
                            url=None,
                            content=paper.strip(),
                            relevance_score=0.7,
                            source_type="academic",
                            metadata={"source": "arxiv"},
                        )
                    )

        return search_results

    except ImportError:
        logger.warning("ArXiv search not available - langchain_community not installed")
        return []
    except Exception as e:
        logger.error(f"ArXiv search failed for query '{query}': {str(e)}")
        return []


async def search_with_pubmed(
    query: str, max_results: int = 5, **kwargs
) -> List[SearchResult]:
    """
    Execute a search using PubMed API for biomedical literature.

    Args:
        query: Search query
        max_results: Maximum number of results
        **kwargs: Additional parameters

    Returns:
        List of SearchResult objects
    """
    try:
        from langchain_community.tools.pubmed.tool import PubmedQueryRun

        # Initialize PubMed search tool
        pubmed_tool = PubmedQueryRun()

        # Execute search
        results_text = await asyncio.to_thread(pubmed_tool.run, query)

        # Parse results (similar to ArXiv)
        search_results = []
        if results_text:
            # Split by double newlines to separate papers
            papers = results_text.split("\n\n")
            for idx, paper in enumerate(papers[:max_results]):
                if paper.strip():
                    search_results.append(
                        SearchResult(
                            title=f"PubMed Article {idx + 1}",
                            url=None,
                            content=paper.strip(),
                            relevance_score=0.7,
                            source_type="medical",
                            metadata={"source": "pubmed"},
                        )
                    )

        return search_results

    except ImportError:
        logger.warning(
            "PubMed search not available - langchain_community not installed"
        )
        return []
    except Exception as e:
        logger.error(f"PubMed search failed for query '{query}': {str(e)}")
        return []


async def execute_search(
    query: str,
    search_api: str = "tavily",
    max_results: int = 5,
    api_config: Optional[Dict[str, Any]] = None,
) -> List[SearchResult]:
    """
    Execute a search using the specified API.

    Args:
        query: Search query
        search_api: Which search API to use
        max_results: Maximum number of results
        api_config: Additional API configuration

    Returns:
        List of SearchResult objects
    """
    api_config = api_config or {}

    search_functions = {
        "tavily": search_with_tavily,
        "arxiv": search_with_arxiv,
        "pubmed": search_with_pubmed,
    }

    search_func = search_functions.get(search_api.lower())
    if not search_func:
        raise SearchAPIError(f"Unsupported search API: {search_api}")

    return await search_func(query, max_results, **api_config)


async def execute_parallel_searches(
    queries: List[str],
    search_api: str = "tavily",
    max_results_per_query: int = 5,
    api_config: Optional[Dict[str, Any]] = None,
    use_cache: Optional[bool] = None,
) -> Dict[str, List[SearchResult]]:
    """
    Execute multiple searches in parallel.

    Args:
        queries: List of search queries
        search_api: Which search API to use
        max_results_per_query: Maximum results per query
        api_config: Additional API configuration
        use_cache: Whether to use cache (for Tavily API)

    Returns:
        Dictionary mapping queries to their results
    """
    # Add cache setting to api_config if using Tavily
    if search_api.lower() == "tavily" and use_cache is not None:
        api_config = api_config or {}
        api_config["use_cache"] = use_cache

    # Create tasks for parallel execution
    tasks = []
    for query in queries:
        task = execute_search(query, search_api, max_results_per_query, api_config)
        tasks.append(task)

    # Execute all searches in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Build results dictionary
    query_results = {}
    for query, result in zip(queries, results):
        if isinstance(result, Exception):
            logger.error(f"Search failed for query '{query}': {str(result)}")
            query_results[query] = []
        else:
            query_results[query] = result

    return query_results


def filter_results_by_relevance(
    results: List[SearchResult], min_relevance: float = 0.5
) -> List[SearchResult]:
    """
    Filter search results by relevance score.

    Args:
        results: List of search results
        min_relevance: Minimum relevance score (0-1)

    Returns:
        Filtered list of search results
    """
    return [r for r in results if r.relevance_score >= min_relevance]


def deduplicate_results(results: List[SearchResult]) -> List[SearchResult]:
    """
    Remove duplicate search results based on content similarity.

    Args:
        results: List of search results

    Returns:
        Deduplicated list of search results
    """
    seen_content = set()
    unique_results = []

    for result in results:
        # Simple deduplication based on first 200 chars of content
        content_key = result.content[:200].lower().strip()
        if content_key not in seen_content:
            seen_content.add(content_key)
            unique_results.append(result)

    return unique_results
