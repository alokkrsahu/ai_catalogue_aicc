"""
WebSearch Package
=================

Provides web search and URL fetching capabilities for agent orchestration.
Includes caching, parallel fetching, and DuckDuckGo search integration.
"""

from .cache_service import WebSearchCacheService
from .fetcher_service import WebsiteFetcherService
from .duckduckgo_service import DuckDuckGoService

__all__ = [
    'WebSearchCacheService',
    'WebsiteFetcherService',
    'DuckDuckGoService',
]
