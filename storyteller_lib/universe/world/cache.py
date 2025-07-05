"""
Cache system for Tavily API calls.

This module provides persistent caching for Tavily search and extract API calls
to reduce costs and improve performance.
"""

import os
import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Any
from storyteller_lib.core.logger import get_logger

logger = get_logger(__name__)


class TavilyCache:
    """Persistent cache for Tavily API calls using SQLite."""

    def __init__(self, cache_path: Optional[str] = None, ttl_days: int = 30):
        """
        Initialize the Tavily cache.

        Args:
            cache_path: Path to cache database (defaults to ~/.storyteller/cache/tavily_cache.db)
            ttl_days: Time to live for cache entries in days
        """
        self.ttl_days = ttl_days

        # Set up cache path
        if cache_path:
            self.cache_path = Path(cache_path).expanduser()
        else:
            self.cache_path = Path.home() / ".storyteller" / "cache" / "tavily_cache.db"

        # Ensure directory exists
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

        # Clean old entries on init
        self.clear_old_entries()

    def _init_db(self):
        """Initialize the cache database schema."""
        with sqlite3.connect(self.cache_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS search_cache (
                    cache_key TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    max_results INTEGER NOT NULL,
                    search_depth TEXT NOT NULL,
                    response TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS extract_cache (
                    cache_key TEXT PRIMARY KEY,
                    urls TEXT NOT NULL,
                    format TEXT NOT NULL,
                    response TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create indexes for faster queries
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_search_created 
                ON search_cache(created_at)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_extract_created 
                ON extract_cache(created_at)
            """
            )

            conn.commit()

    def _generate_cache_key(self, *args) -> str:
        """Generate a stable cache key from arguments."""
        # Convert all arguments to strings and join
        key_parts = [str(arg) for arg in args]
        key_string = "|".join(key_parts)

        # Create hash for stable key
        return hashlib.sha256(key_string.encode()).hexdigest()

    def get_search_cache(
        self, query: str, max_results: int, search_depth: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached search response if available.

        Args:
            query: Search query
            max_results: Maximum number of results
            search_depth: Search depth parameter

        Returns:
            Cached response dict or None if not found/expired
        """
        cache_key = self._generate_cache_key("search", query, max_results, search_depth)

        try:
            with sqlite3.connect(self.cache_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Check for cache hit within TTL
                cursor.execute(
                    """
                    SELECT response, created_at 
                    FROM search_cache 
                    WHERE cache_key = ? 
                    AND created_at > datetime('now', '-{} days')
                """.format(
                        self.ttl_days
                    ),
                    (cache_key,),
                )

                row = cursor.fetchone()
                if row:
                    # Update access time
                    cursor.execute(
                        """
                        UPDATE search_cache 
                        SET accessed_at = CURRENT_TIMESTAMP 
                        WHERE cache_key = ?
                    """,
                        (cache_key,),
                    )
                    conn.commit()

                    logger.info(f"Cache hit for search query: {query[:50]}...")
                    return json.loads(row["response"])

                logger.debug(f"Cache miss for search query: {query[:50]}...")
                return None

        except Exception as e:
            logger.error(f"Error reading search cache: {e}")
            return None

    def set_search_cache(
        self, query: str, max_results: int, search_depth: str, response: Dict[str, Any]
    ):
        """
        Cache a search response.

        Args:
            query: Search query
            max_results: Maximum number of results
            search_depth: Search depth parameter
            response: API response to cache
        """
        cache_key = self._generate_cache_key("search", query, max_results, search_depth)

        try:
            with sqlite3.connect(self.cache_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO search_cache 
                    (cache_key, query, max_results, search_depth, response)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (cache_key, query, max_results, search_depth, json.dumps(response)),
                )
                conn.commit()

                logger.info(f"Cached search response for: {query[:50]}...")

        except Exception as e:
            logger.error(f"Error writing search cache: {e}")

    def get_extract_cache(
        self, urls: List[str], format: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached extract response if available.

        Args:
            urls: List of URLs to extract
            format: Format parameter (e.g., 'markdown')

        Returns:
            Cached response dict or None if not found/expired
        """
        # Sort URLs for consistent cache key
        sorted_urls = sorted(urls)
        cache_key = self._generate_cache_key("extract", *sorted_urls, format)

        try:
            with sqlite3.connect(self.cache_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Check for cache hit within TTL
                cursor.execute(
                    """
                    SELECT response, created_at 
                    FROM extract_cache 
                    WHERE cache_key = ? 
                    AND created_at > datetime('now', '-{} days')
                """.format(
                        self.ttl_days
                    ),
                    (cache_key,),
                )

                row = cursor.fetchone()
                if row:
                    # Update access time
                    cursor.execute(
                        """
                        UPDATE extract_cache 
                        SET accessed_at = CURRENT_TIMESTAMP 
                        WHERE cache_key = ?
                    """,
                        (cache_key,),
                    )
                    conn.commit()

                    logger.info(f"Cache hit for extract with {len(urls)} URLs")
                    return json.loads(row["response"])

                logger.debug(f"Cache miss for extract with {len(urls)} URLs")
                return None

        except Exception as e:
            logger.error(f"Error reading extract cache: {e}")
            return None

    def set_extract_cache(self, urls: List[str], format: str, response: Dict[str, Any]):
        """
        Cache an extract response.

        Args:
            urls: List of URLs that were extracted
            format: Format parameter used
            response: API response to cache
        """
        # Sort URLs for consistent cache key
        sorted_urls = sorted(urls)
        cache_key = self._generate_cache_key("extract", *sorted_urls, format)

        try:
            with sqlite3.connect(self.cache_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO extract_cache 
                    (cache_key, urls, format, response)
                    VALUES (?, ?, ?, ?)
                """,
                    (cache_key, json.dumps(sorted_urls), format, json.dumps(response)),
                )
                conn.commit()

                logger.info(f"Cached extract response for {len(urls)} URLs")

        except Exception as e:
            logger.error(f"Error writing extract cache: {e}")

    def clear_old_entries(self, days: Optional[int] = None):
        """
        Clear cache entries older than specified days.

        Args:
            days: Number of days to keep (defaults to ttl_days)
        """
        days = days or self.ttl_days

        try:
            with sqlite3.connect(self.cache_path) as conn:
                # Clear old search cache entries
                cursor = conn.execute(
                    """
                    DELETE FROM search_cache 
                    WHERE created_at < datetime('now', '-{} days')
                """.format(
                        days
                    )
                )
                search_deleted = cursor.rowcount

                # Clear old extract cache entries
                cursor = conn.execute(
                    """
                    DELETE FROM extract_cache 
                    WHERE created_at < datetime('now', '-{} days')
                """.format(
                        days
                    )
                )
                extract_deleted = cursor.rowcount

                conn.commit()

                if search_deleted > 0 or extract_deleted > 0:
                    logger.info(
                        f"Cleared {search_deleted} search and {extract_deleted} "
                        f"extract cache entries older than {days} days"
                    )

        except Exception as e:
            logger.error(f"Error clearing old cache entries: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache."""
        try:
            with sqlite3.connect(self.cache_path) as conn:
                # Get search cache stats
                cursor = conn.execute(
                    """
                    SELECT 
                        COUNT(*) as total_entries,
                        SUM(LENGTH(response)) as total_size,
                        MIN(created_at) as oldest_entry,
                        MAX(accessed_at) as latest_access
                    FROM search_cache
                """
                )
                row = cursor.fetchone()
                search_stats = {
                    "total_entries": row[0],
                    "total_size": row[1],
                    "oldest_entry": row[2],
                    "latest_access": row[3],
                }

                # Get extract cache stats
                cursor = conn.execute(
                    """
                    SELECT 
                        COUNT(*) as total_entries,
                        SUM(LENGTH(response)) as total_size,
                        MIN(created_at) as oldest_entry,
                        MAX(accessed_at) as latest_access
                    FROM extract_cache
                """
                )
                row = cursor.fetchone()
                extract_stats = {
                    "total_entries": row[0],
                    "total_size": row[1],
                    "oldest_entry": row[2],
                    "latest_access": row[3],
                }

                # Get database file size
                db_size = os.path.getsize(self.cache_path)

                return {
                    "search_cache": search_stats,
                    "extract_cache": extract_stats,
                    "database_size_bytes": db_size,
                    "cache_path": str(self.cache_path),
                }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}

    def clear_all(self):
        """Clear all cache entries."""
        try:
            with sqlite3.connect(self.cache_path) as conn:
                conn.execute("DELETE FROM search_cache")
                conn.execute("DELETE FROM extract_cache")
                conn.commit()

                logger.info("Cleared all cache entries")

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
