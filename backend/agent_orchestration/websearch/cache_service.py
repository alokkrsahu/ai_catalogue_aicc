"""
WebSearch Cache Service
=======================

Provides per-project caching for web search results and fetched URL content
using Django's cache framework (backed by Redis).

Cache scope: Per-project only. Every cache key includes project_id so that
no cache entry is shared across projects. project_id is required for all
cache operations.
"""

import hashlib
import logging
import json
from typing import Dict, List, Any, Optional
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger('agent_orchestration')


def _normalize_project_id(project_id: str) -> str:
    """Normalize project_id for use in cache keys (e.g. UUID with underscores)."""
    return str(project_id).replace('-', '_') if project_id else ''


class WebSearchCacheService:
    """
    Per-project caching service for web search results and URL content.
    Uses Django cache (Redis) with configurable TTL.
    All keys include project_id; cache is never shared across projects.
    """
    
    # Default TTL values
    DEFAULT_URL_TTL = 3600  # 1 hour for URL content
    DEFAULT_SEARCH_TTL = 1800  # 30 minutes for search results

    # TTL applied to captures that failed to fetch/extract. A transient timeout
    # must not blank a URL for the full content TTL (observed: three pages stuck
    # empty for days after one slow response), so failures are cached only long
    # enough to stop a hot retry loop within a single conversation.
    FAILED_FETCH_TTL = 300  # 5 minutes
    
    # Cache key prefixes (keys will be {prefix}{project_id}_{hash})
    URL_PREFIX = "websearch_url_"
    SEARCH_PREFIX = "websearch_query_"
    INDEX_FLAG_PREFIX = "websearch_milvus_idx_"
    EMBED_PREFIX = "websearch_emb_"
    CONTENT_HASH_PREFIX = "websearch_chash_"
    # Short-lived flag (no hash suffix) marking an in-flight summarise-urls
    # job for the project — prevents double-starts and lets the UI show a
    # "generating in background" status.
    SUMMARY_GEN_PREFIX = "websearch_summary_gen_"
    
    def __init__(self):
        """Initialize cache service with settings from Django config."""
        websearch_config = getattr(settings, 'WEBSEARCH_CONFIG', {})
        self.default_ttl = websearch_config.get('DEFAULT_CACHE_TTL', self.DEFAULT_URL_TTL)
        logger.info(f"🔄 WEBSEARCH CACHE: Initialized with default TTL: {self.default_ttl}s (per-project)")
    
    # =========================================================================
    # URL Content Caching
    # =========================================================================
    
    def get_cached_url(self, url: str, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached content for a URL (per-project).
        
        Args:
            url: The URL to retrieve cached content for
            project_id: Project ID so cache is isolated per project
            
        Returns:
            Cached content dict or None if not cached
        """
        cache_key = self._make_url_cache_key(url, project_id)
        cached = cache.get(cache_key)
        
        if cached:
            logger.debug(f"✅ WEBSEARCH CACHE HIT: URL {url[:50]}... (project {project_id[:8]})")
            return cached
        
        logger.debug(f"❌ WEBSEARCH CACHE MISS: URL {url[:50]}... (project {project_id[:8]})")
        return None
    
    def cache_url(self, url: str, content: Dict[str, Any], project_id: str, ttl: Optional[int] = None) -> bool:
        """
        Cache content for a URL (per-project).
        
        Args:
            url: The URL being cached
            content: The content dict to cache (title, text, metadata)
            project_id: Project ID so cache is isolated per project
            ttl: Time-to-live in seconds (uses default if not specified)
            
        Returns:
            True if cached successfully
        """
        cache_key = self._make_url_cache_key(url, project_id)
        timeout = ttl if ttl is not None else self.default_ttl
        
        try:
            cache.set(cache_key, content, timeout=timeout)
            logger.info(f"💾 WEBSEARCH CACHE: Cached URL {url[:50]}... (project {project_id[:8]}, TTL: {timeout}s)")
            return True
        except Exception as e:
            logger.error(f"❌ WEBSEARCH CACHE: Failed to cache URL {url}: {e}")
            return False
    
    def get_cached_urls_batch(self, urls: List[str], project_id: str) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get cached content for multiple URLs at once (per-project).
        
        Args:
            urls: List of URLs to check cache for
            project_id: Project ID so cache is isolated per project
            
        Returns:
            Dict mapping URL to cached content (or None if not cached)
        """
        results = {}
        cache_keys = {url: self._make_url_cache_key(url, project_id) for url in urls}
        
        # Use cache.get_many for efficiency
        try:
            cached_values = cache.get_many(list(cache_keys.values()))
            
            # Map back to URLs
            key_to_url = {v: k for k, v in cache_keys.items()}
            for key, value in cached_values.items():
                url = key_to_url.get(key)
                if url:
                    results[url] = value
            
            # Fill in None for cache misses
            for url in urls:
                if url not in results:
                    results[url] = None
            
            hits = sum(1 for v in results.values() if v is not None)
            logger.info(f"🔄 WEBSEARCH CACHE BATCH: {hits}/{len(urls)} cache hits (project {project_id[:8]})")
            
        except Exception as e:
            logger.error(f"❌ WEBSEARCH CACHE: Batch get failed: {e}")
            results = {url: None for url in urls}
        
        return results
    
    def cache_urls_batch(
        self,
        url_contents: Dict[str, Dict[str, Any]],
        project_id: str,
        ttl: Optional[int] = None
    ) -> int:
        """
        Cache multiple URL contents at once (per-project).
        
        Args:
            url_contents: Dict mapping URL to content dict
            project_id: Project ID so cache is isolated per project
            ttl: Time-to-live in seconds
            
        Returns:
            Number of URLs successfully cached
        """
        timeout = ttl if ttl is not None else self.default_ttl

        try:
            # Split failed captures out so a transient fetch error gets a short
            # TTL and is retried soon, instead of pinning an empty page for the
            # full content TTL. Callers stay unaware — nothing raises here.
            ok_items, failed_items = {}, {}
            for url, content in url_contents.items():
                target = failed_items if (content or {}).get('extraction_error') else ok_items
                target[self._make_url_cache_key(url, project_id)] = content

            if ok_items:
                cache.set_many(ok_items, timeout=timeout)
            if failed_items:
                cache.set_many(failed_items, timeout=self.FAILED_FETCH_TTL)
                logger.warning(
                    f"⏱️ WEBSEARCH CACHE: {len(failed_items)} failed capture(s) cached with "
                    f"short TTL {self.FAILED_FETCH_TTL}s (will retry) — project {project_id[:8]}"
                )

            logger.info(
                f"💾 WEBSEARCH CACHE BATCH: Cached {len(ok_items)} URLs "
                f"(project {project_id[:8]}, TTL: {timeout}s)"
                + (f" + {len(failed_items)} failed @ {self.FAILED_FETCH_TTL}s" if failed_items else "")
            )
            return len(url_contents)
        except Exception as e:
            # Caching is an optimisation — never let it break the fetch flow.
            logger.warning(f"⚠️ WEBSEARCH CACHE: Batch cache failed (continuing uncached): {e}")
            return 0
    
    # =========================================================================
    # Per-URL Chunk Embedding Caching
    # =========================================================================

    def _make_embed_cache_key(self, url: str, project_id: str) -> str:
        pid = _normalize_project_id(project_id)
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        return f"{self.EMBED_PREFIX}{pid}_{url_hash}"

    def get_cached_embeddings(
        self, url: str, project_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached chunk-with-embedding list for a URL.
        Each entry is a dict with content/section_heading/section_type/
        chunk_index/word_count/url/url_hash/title/embedding.
        """
        return cache.get(self._make_embed_cache_key(url, project_id))

    def cache_embeddings(
        self,
        url: str,
        project_id: str,
        chunks_with_embeddings: List[Dict[str, Any]],
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache the chunk+embedding list for a URL (per-project)."""
        timeout = ttl if ttl is not None else self.default_ttl
        try:
            cache.set(
                self._make_embed_cache_key(url, project_id),
                chunks_with_embeddings,
                timeout=timeout,
            )
            return True
        except Exception as e:
            logger.error(f"❌ WEBSEARCH CACHE: Failed to cache embeddings for {url[:50]}: {e}")
            return False

    def get_cached_embeddings_batch(
        self, urls: List[str], project_id: str
    ) -> Dict[str, Optional[List[Dict[str, Any]]]]:
        """Batch get cached embeddings for multiple URLs."""
        key_to_url = {self._make_embed_cache_key(url, project_id): url for url in urls}
        try:
            cached = cache.get_many(list(key_to_url.keys()))
        except Exception as e:
            logger.error(f"❌ WEBSEARCH CACHE: Batch embed get failed: {e}")
            return {url: None for url in urls}
        out: Dict[str, Optional[List[Dict[str, Any]]]] = {url: None for url in urls}
        for key, value in cached.items():
            url = key_to_url.get(key)
            if url is not None:
                out[url] = value
        return out

    def invalidate_embeddings(self, url: str, project_id: str) -> bool:
        try:
            cache.delete(self._make_embed_cache_key(url, project_id))
            return True
        except Exception:
            return False

    # =========================================================================
    # Per-URL Content-Hash Caching (skip re-embed when content unchanged)
    # =========================================================================

    def _make_content_hash_key(self, url: str, project_id: str) -> str:
        pid = _normalize_project_id(project_id)
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        return f"{self.CONTENT_HASH_PREFIX}{pid}_{url_hash}"

    def get_cached_content_hash(self, url: str, project_id: str) -> Optional[str]:
        return cache.get(self._make_content_hash_key(url, project_id))

    def cache_content_hash(
        self, url: str, project_id: str, content_hash: str, ttl: Optional[int] = None
    ) -> bool:
        timeout = ttl if ttl is not None else self.default_ttl
        try:
            cache.set(
                self._make_content_hash_key(url, project_id),
                content_hash,
                timeout=timeout,
            )
            return True
        except Exception:
            return False

    def get_cached_content_hashes_batch(
        self, urls: List[str], project_id: str
    ) -> Dict[str, Optional[str]]:
        key_to_url = {self._make_content_hash_key(url, project_id): url for url in urls}
        try:
            cached = cache.get_many(list(key_to_url.keys()))
        except Exception:
            return {url: None for url in urls}
        out: Dict[str, Optional[str]] = {url: None for url in urls}
        for key, value in cached.items():
            url = key_to_url.get(key)
            if url is not None:
                out[url] = value
        return out

    def invalidate_content_hash(self, url: str, project_id: str) -> bool:
        try:
            cache.delete(self._make_content_hash_key(url, project_id))
            return True
        except Exception:
            return False

    # =========================================================================
    # Search Results Caching
    # =========================================================================
    
    def get_cached_search(
        self,
        query: str,
        project_id: str,
        domains: Optional[List[str]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached search results (per-project).
        
        Args:
            query: Search query string
            project_id: Project ID so cache is isolated per project
            domains: Optional list of domains to restrict search
            
        Returns:
            Cached search results list or None if not cached
        """
        cache_key = self._make_search_cache_key(query, project_id, domains)
        cached = cache.get(cache_key)
        
        if cached:
            logger.debug(f"✅ WEBSEARCH CACHE HIT: Search '{query[:30]}...' (project {project_id[:8]})")
            return cached
        
        logger.debug(f"❌ WEBSEARCH CACHE MISS: Search '{query[:30]}...' (project {project_id[:8]})")
        return None
    
    def cache_search(
        self,
        query: str,
        results: List[Dict[str, Any]],
        project_id: str,
        domains: Optional[List[str]] = None,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache search results (per-project).
        
        Args:
            query: Search query string
            results: Search results to cache
            project_id: Project ID so cache is isolated per project
            domains: Optional list of domains the search was restricted to
            ttl: Time-to-live in seconds
            
        Returns:
            True if cached successfully
        """
        cache_key = self._make_search_cache_key(query, project_id, domains)
        timeout = ttl if ttl is not None else self.DEFAULT_SEARCH_TTL
        
        try:
            cache.set(cache_key, results, timeout=timeout)
            domain_str = f" (domains: {domains})" if domains else ""
            logger.info(f"💾 WEBSEARCH CACHE: Cached search '{query[:30]}...'{domain_str} (project {project_id[:8]}, TTL: {timeout}s)")
            return True
        except Exception as e:
            logger.error(f"❌ WEBSEARCH CACHE: Failed to cache search: {e}")
            return False
    
    # =========================================================================
    # Cache Key Generation
    # =========================================================================
    
    def _make_url_cache_key(self, url: str, project_id: str) -> str:
        """
        Generate a unique per-project cache key for a URL.
        """
        pid = _normalize_project_id(project_id)
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        return f"{self.URL_PREFIX}{pid}_{url_hash}"
    
    def _make_search_cache_key(
        self,
        query: str,
        project_id: str,
        domains: Optional[List[str]] = None
    ) -> str:
        """
        Generate a unique per-project cache key for a search query.
        """
        pid = _normalize_project_id(project_id)
        normalized_query = query.lower().strip()
        sorted_domains = sorted(domains) if domains else []
        key_data = json.dumps({
            'query': normalized_query,
            'domains': sorted_domains
        }, sort_keys=True)
        key_hash = hashlib.md5(key_data.encode('utf-8')).hexdigest()
        return f"{self.SEARCH_PREFIX}{pid}_{key_hash}"
    
    # =========================================================================
    # Cache Management
    # =========================================================================
    
    def invalidate_url(self, url: str, project_id: str) -> bool:
        """
        Invalidate cached content for a URL (per-project).
        """
        cache_key = self._make_url_cache_key(url, project_id)
        try:
            cache.delete(cache_key)
            logger.info(f"🗑️ WEBSEARCH CACHE: Invalidated URL {url[:50]}... (project {project_id[:8]})")
            return True
        except Exception as e:
            logger.error(f"❌ WEBSEARCH CACHE: Failed to invalidate URL: {e}")
            return False
    
    def invalidate_search(
        self,
        query: str,
        project_id: str,
        domains: Optional[List[str]] = None
    ) -> bool:
        """
        Invalidate cached search results (per-project).
        """
        cache_key = self._make_search_cache_key(query, project_id, domains)
        try:
            cache.delete(cache_key)
            logger.info(f"🗑️ WEBSEARCH CACHE: Invalidated search '{query[:30]}...' (project {project_id[:8]})")
            return True
        except Exception as e:
            logger.error(f"❌ WEBSEARCH CACHE: Failed to invalidate search: {e}")
            return False
    
    def clear_all_websearch_cache(self, project_id: str) -> bool:
        """
        Clear all websearch cache entries for a single project.

        Two-path implementation:
          Fast path  — django-redis: uses delete_pattern()
          Fallback   — Django built-in Redis backend: uses low-level SCAN + DELETE
                       via the redis-py client so only this project's keys are removed.
        """
        pid = _normalize_project_id(project_id)
        try:
            # Fast path: django-redis exposes delete_pattern()
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(f"{self.URL_PREFIX}{pid}_*")
                cache.delete_pattern(f"{self.SEARCH_PREFIX}{pid}_*")
                cache.delete_pattern(f"{self.INDEX_FLAG_PREFIX}{pid}_*")
                cache.delete_pattern(f"{self.EMBED_PREFIX}{pid}_*")
                cache.delete_pattern(f"{self.CONTENT_HASH_PREFIX}{pid}_*")
                # Single-key flag (no hash suffix) — wildcard still matches it.
                cache.delete(f"{self.SUMMARY_GEN_PREFIX}{pid}")
                logger.info(f"🗑️ WEBSEARCH CACHE: Cleared all websearch cache for project {project_id[:8]}")
                return True

            # Fallback: Django's built-in RedisCache (Django >= 4.0) exposes the
            # underlying redis-py client through cache._cache.get_client().
            # Django key format: {key_prefix}:{version}:{cache_key}
            try:
                client = cache._cache.get_client()
                key_prefix = getattr(cache, 'key_prefix', '')
                version = getattr(cache, 'version', 1)
                deleted = 0
                for prefix in (
                    self.URL_PREFIX,
                    self.SEARCH_PREFIX,
                    self.INDEX_FLAG_PREFIX,
                    self.EMBED_PREFIX,
                    self.CONTENT_HASH_PREFIX,
                ):
                    full_pattern = f"{key_prefix}:{version}:{prefix}{pid}_*"
                    cursor = 0
                    while True:
                        cursor, keys = client.scan(cursor, match=full_pattern, count=200)
                        if keys:
                            client.delete(*keys)
                            deleted += len(keys)
                        if cursor == 0:
                            break
                # Summary-gen flag is a single key (no hash suffix) — drop it too.
                try:
                    client.delete(f"{key_prefix}:{version}:{self.SUMMARY_GEN_PREFIX}{pid}")
                    deleted += 1
                except Exception:
                    pass
                logger.info(
                    f"🗑️ WEBSEARCH CACHE: Cleared {deleted} cache keys for project {project_id[:8]}"
                )
                return True
            except AttributeError:
                logger.warning(
                    "⚠️ WEBSEARCH CACHE: Cache backend does not support pattern deletion "
                    "or direct Redis client access. Cache was not cleared."
                )
                return False
        except Exception as e:
            logger.error(f"❌ WEBSEARCH CACHE: Failed to clear cache: {e}")
            return False
