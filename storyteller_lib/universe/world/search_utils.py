"""
Search utilities for research-driven world building.

This module provides functions for executing web searches
using various APIs like Tavily, and processing the results.
"""

import os
import asyncio
from typing import List, Dict, Any, Optional
from tavily import AsyncTavilyClient
from langchain_tavily import TavilySearchAPIRetriever, TavilyExtractAPITool
from storyteller_lib.core.logger import get_logger
from storyteller_lib.universe.world.research_models import SearchResult

logger = get_logger(__name__)


class SearchAPIError(Exception):
    """Error raised when search API fails."""
    pass


async def search_with_tavily(
    query: str,
    max_results: int = 5,
    api_key: Optional[str] = None
) -> List[SearchResult]:
    """
    Execute a search using Tavily API with two-step approach:
    1. Search for relevant pages
    2. Extract full content from top 3 pages
    
    Args:
        query: Search query
        max_results: Maximum number of results
        api_key: Tavily API key (uses env var if not provided)
        
    Returns:
        List of SearchResult objects
    """
    try:
        # Get API key
        api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise SearchAPIError("Tavily API key not found. Set TAVILY_API_KEY environment variable.")
        
        # Set API key in environment for langchain_tavily
        os.environ["TAVILY_API_KEY"] = api_key
        
        # Step 1: Search (only meta-info)
        search_retriever = TavilySearchAPIRetriever(
            k=max_results,
            search_depth="advanced",  # Better relevance
            include_raw_content=False  # Content in step 2
        )
        
        # Execute search synchronously in async context
        loop = asyncio.get_event_loop()
        docs = await loop.run_in_executor(None, search_retriever.invoke, query)
        
        # Extract URLs from search results
        urls = []
        search_results = []
        
        for idx, doc in enumerate(docs):
            url = doc.metadata.get("source")
            if url:
                urls.append(url)
                # Create initial SearchResult with basic info
                search_results.append(SearchResult(
                    title=doc.metadata.get("title", f"Result {idx + 1}"),
                    url=url,
                    content=doc.page_content,  # Initial snippet
                    relevance_score=doc.metadata.get("score", 0.5),
                    source_type="web",
                    metadata={
                        "snippet": doc.page_content,
                        "published_date": doc.metadata.get("published_date")
                    }
                ))
        
        # Step 2: Extract full content from top 3 URLs
        if urls:
            extract_tool = TavilyExtractAPITool(
                format="markdown",
                extract_depth="advanced"  # Robust parser
            )
            
            # Extract content from top 3 URLs
            urls_to_extract = urls[:3]
            try:
                extracted_pages = await loop.run_in_executor(
                    None, 
                    extract_tool.invoke, 
                    {"urls": urls_to_extract}
                )
                
                # Update SearchResults with extracted content
                for i, extracted_content in enumerate(extracted_pages):
                    if i < len(search_results) and extracted_content:
                        # Update the content with full extracted markdown text
                        search_results[i].content = extracted_content
                        search_results[i].metadata["raw_content"] = extracted_content
                        search_results[i].metadata["content_format"] = "markdown"
                        
            except Exception as e:
                logger.warning(f"Failed to extract content from URLs: {str(e)}")
                # Continue with snippet content if extraction fails
        
        return search_results
        
    except Exception as e:
        logger.error(f"Tavily search failed for query '{query}': {str(e)}")
        raise SearchAPIError(f"Tavily search failed: {str(e)}")


async def search_with_arxiv(
    query: str,
    max_results: int = 5,
    **kwargs
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
                    search_results.append(SearchResult(
                        title=f"ArXiv Paper {idx + 1}",
                        url=None,
                        content=paper.strip(),
                        relevance_score=0.7,
                        source_type="academic",
                        metadata={"source": "arxiv"}
                    ))
        
        return search_results
        
    except ImportError:
        logger.warning("ArXiv search not available - langchain_community not installed")
        return []
    except Exception as e:
        logger.error(f"ArXiv search failed for query '{query}': {str(e)}")
        return []


async def search_with_pubmed(
    query: str,
    max_results: int = 5,
    **kwargs
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
                    search_results.append(SearchResult(
                        title=f"PubMed Article {idx + 1}",
                        url=None,
                        content=paper.strip(),
                        relevance_score=0.7,
                        source_type="medical",
                        metadata={"source": "pubmed"}
                    ))
        
        return search_results
        
    except ImportError:
        logger.warning("PubMed search not available - langchain_community not installed")
        return []
    except Exception as e:
        logger.error(f"PubMed search failed for query '{query}': {str(e)}")
        return []


async def execute_search(
    query: str,
    search_api: str = "tavily",
    max_results: int = 5,
    api_config: Optional[Dict[str, Any]] = None
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
    api_config: Optional[Dict[str, Any]] = None
) -> Dict[str, List[SearchResult]]:
    """
    Execute multiple searches in parallel.
    
    Args:
        queries: List of search queries
        search_api: Which search API to use
        max_results_per_query: Maximum results per query
        api_config: Additional API configuration
        
    Returns:
        Dictionary mapping queries to their results
    """
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
    results: List[SearchResult],
    min_relevance: float = 0.5
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