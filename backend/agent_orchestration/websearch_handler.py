"""
WebSearch Handler
=================

Handles WebSearch integration and context management for conversation orchestration.
Provides web search and URL fetching capabilities with caching support.
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Any, Optional
from asgiref.sync import sync_to_async

# Import WebSearch services
from .websearch import WebSearchCacheService, WebsiteFetcherService, DuckDuckGoService

logger = logging.getLogger('agent_orchestration')


class WebSearchHandler:
    """
    Handles WebSearch integration and web context retrieval.
    Supports three modes:
    - General search: DuckDuckGo search with no restrictions
    - Domain search: DuckDuckGo search restricted to specific domains
    - URL fetch: Direct fetching of specific URLs with content extraction
    """
    
    def __init__(self, llm_provider_manager=None):
        """
        Initialize WebSearchHandler with services.
        
        Args:
            llm_provider_manager: Optional LLMProviderManager instance for query refinement
        """
        self.llm_provider_manager = llm_provider_manager
        self.cache_service = WebSearchCacheService()
        self.fetcher_service = WebsiteFetcherService()
        self.search_service = DuckDuckGoService()
        logger.info("🌐 WEBSEARCH HANDLER: Initialized with cache, fetcher, and search services")
    
    # =========================================================================
    # Public API
    # =========================================================================
    
    def is_websearch_enabled(self, agent_node: Dict[str, Any]) -> bool:
        """
        Check if WebSearch is enabled for this agent.
        
        Args:
            agent_node: Agent node configuration
            
        Returns:
            True if web_search_enabled is set in agent data
        """
        agent_data = agent_node.get('data', {})
        return agent_data.get('web_search_enabled', False)
    
    def get_websearch_mode(self, agent_node: Dict[str, Any]) -> str:
        """
        Get the WebSearch mode for this agent.
        
        Args:
            agent_node: Agent node configuration
            
        Returns:
            Mode string: 'general', 'domains', or 'urls'
        """
        agent_data = agent_node.get('data', {})
        return agent_data.get('web_search_mode', 'general')
    
    async def get_websearch_context(
        self, 
        agent_node: Dict[str, Any], 
        conversation_history: str, 
        project_id: str
    ) -> str:
        """
        Retrieve web search context based on agent configuration.
        
        This is the main entry point for getting web context. It determines the
        search mode and delegates to the appropriate handler.
        
        Args:
            agent_node: Agent configuration with websearch settings
            conversation_history: Conversation history for query extraction
            project_id: Project ID for logging and metrics
            
        Returns:
            Formatted web context string for agent consumption
        """
        if not self.is_websearch_enabled(agent_node):
            return ""
        
        agent_data = agent_node.get('data', {})
        mode = self.get_websearch_mode(agent_node)
        cache_ttl = agent_data.get('web_search_cache_ttl', 3600)
        max_results = agent_data.get('web_search_max_results', 5)
        
        logger.info(f"🌐 WEBSEARCH: Starting web search (mode: {mode}, cache_ttl: {cache_ttl}s, max_results: {max_results})")
        
        start_time = time.time()
        
        try:
            if mode == 'urls':
                # Direct URL fetching mode
                urls = agent_data.get('web_search_urls', [])
                if not urls:
                    logger.warning("🌐 WEBSEARCH: URL mode enabled but no URLs configured")
                    return ""
                context = await self._get_url_context(urls, cache_ttl, project_id)
                
            elif mode == 'domains':
                # Domain-restricted search mode
                domains = agent_data.get('web_search_domains', [])
                query = self.extract_query_from_conversation(conversation_history)
                if not query:
                    logger.warning("🌐 WEBSEARCH: Could not extract query from conversation")
                    return ""
                context = await self._get_domain_search_context(query, domains, max_results, cache_ttl, project_id)
                
            else:
                # General search mode (default)
                query = self.extract_query_from_conversation(conversation_history)
                if not query:
                    logger.warning("🌐 WEBSEARCH: Could not extract query from conversation")
                    return ""
                context = await self._get_general_search_context(query, max_results, cache_ttl, project_id)
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"🌐 WEBSEARCH: Completed in {duration_ms:.2f}ms, context length: {len(context)} chars")
            
            # Log experiment metrics
            await self._log_websearch_metrics(
                project_id=project_id,
                agent_node=agent_node,
                mode=mode,
                duration_ms=duration_ms,
                context_length=len(context),
                success=bool(context)
            )
            
            return context
            
        except Exception as e:
            logger.error(f"❌ WEBSEARCH: Error retrieving web context: {e}")
            import traceback
            logger.error(f"❌ WEBSEARCH: Traceback: {traceback.format_exc()}")
            return f"⚠️ Web search failed: {str(e)}"
    
    # =========================================================================
    # Search Mode Handlers
    # =========================================================================
    
    async def _get_url_context(self, urls: List[str], cache_ttl: int, project_id: str) -> str:
        """
        Fetch content from specific URLs with per-project caching.
        
        Args:
            urls: List of URLs to fetch
            cache_ttl: Cache time-to-live in seconds
            project_id: Project ID for per-project cache isolation
            
        Returns:
            Formatted context string from fetched URLs
        """
        logger.info(f"🌐 WEBSEARCH URL MODE: Fetching {len(urls)} URLs")
        
        # Check cache for each URL (per-project)
        cached_results = self.cache_service.get_cached_urls_batch(urls, project_id)
        
        # Identify URLs that need fetching
        urls_to_fetch = [url for url, content in cached_results.items() if content is None]
        cached_count = len(urls) - len(urls_to_fetch)
        
        logger.info(f"🌐 WEBSEARCH URL MODE: {cached_count} cached, {len(urls_to_fetch)} to fetch")
        
        # Fetch uncached URLs in parallel
        if urls_to_fetch:
            fetch_results = await self.fetcher_service.fetch_urls_parallel(urls_to_fetch)
            
            # Cache all fetched PageCapture objects per project
            to_cache = {}
            for result in fetch_results:
                url = result.get('url')
                if not url:
                    continue
                to_cache[url] = result
            
            if to_cache:
                self.cache_service.cache_urls_batch(to_cache, project_id, ttl=cache_ttl)
            
            # Merge fetched results with cached results
            for result in fetch_results:
                url = result.get('url')
                if url:
                    cached_results[url] = result
        
        # Format results for context (derived view over PageCapture)
        return self._format_url_results(urls, cached_results)
    
    async def _get_domain_search_context(
        self,
        query: str,
        domains: List[str],
        max_results: int,
        cache_ttl: int,
        project_id: str
    ) -> str:
        """
        Perform DuckDuckGo search restricted to specific domains (per-project cache).
        
        Args:
            query: Search query
            domains: List of domains to restrict search to
            max_results: Maximum number of results
            cache_ttl: Cache time-to-live in seconds
            project_id: Project ID for per-project cache isolation
            
        Returns:
            Formatted context string from search results
        """
        logger.info(f"🌐 WEBSEARCH DOMAIN MODE: Searching '{query[:50]}...' in domains: {domains}")
        
        # Check cache first (per-project)
        cached_results = self.cache_service.get_cached_search(query, project_id, domains=domains)
        if cached_results:
            logger.info(f"🌐 WEBSEARCH DOMAIN MODE: Using cached search results")
            return self.search_service.format_results_for_context(cached_results)
        
        # Perform search (synchronous, run in thread pool)
        def do_search():
            return self.search_service.search(query, max_results=max_results, domains=domains)
        
        results = await sync_to_async(do_search)()
        
        # Cache results (per-project)
        if results:
            self.cache_service.cache_search(query, results, project_id, domains=domains, ttl=cache_ttl)
        
        return self.search_service.format_results_for_context(results)
    
    async def _get_general_search_context(
        self,
        query: str,
        max_results: int,
        cache_ttl: int,
        project_id: str
    ) -> str:
        """
        Perform general DuckDuckGo search (per-project cache).
        
        Args:
            query: Search query
            max_results: Maximum number of results
            cache_ttl: Cache time-to-live in seconds
            project_id: Project ID for per-project cache isolation
            
        Returns:
            Formatted context string from search results
        """
        logger.info(f"🌐 WEBSEARCH GENERAL MODE: Searching '{query[:50]}...'")
        
        # Check cache first (per-project)
        cached_results = self.cache_service.get_cached_search(query, project_id, domains=None)
        if cached_results:
            logger.info(f"🌐 WEBSEARCH GENERAL MODE: Using cached search results")
            return self.search_service.format_results_for_context(cached_results)
        
        # Perform search (synchronous, run in thread pool)
        def do_search():
            return self.search_service.search(query, max_results=max_results)
        
        results = await sync_to_async(do_search)()
        
        # Cache results (per-project)
        if results:
            self.cache_service.cache_search(query, results, project_id, ttl=cache_ttl)
        
        return self.search_service.format_results_for_context(results)
    
    # =========================================================================
    # Query Extraction
    # =========================================================================
    
    def extract_query_from_conversation(self, conversation_history: str) -> str:
        """
        Extract a search query from the conversation history.
        
        This uses the same logic as DocAwareHandler for consistency.
        
        Args:
            conversation_history: Full conversation history
            
        Returns:
            Extracted search query string
        """
        logger.info(f"🌐 WEBSEARCH QUERY EXTRACTION: Starting with conversation: '{conversation_history[:200]}...'")
        
        if not conversation_history.strip():
            logger.warning("🌐 WEBSEARCH QUERY EXTRACTION: Empty conversation history")
            return ""
        
        # Split conversation into lines
        lines = conversation_history.strip().split('\n')
        
        # Look for the last user message (most relevant for search)
        user_query = None
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            
            line_lower = line.lower()
            
            # SPECIAL CASE: "Start Node:" contains the user's initial query
            if line_lower.startswith('start node:'):
                user_query = line.split(':', 1)[1].strip() if ':' in line else line
                logger.info(f"🌐 WEBSEARCH QUERY EXTRACTION: Found query from Start Node")
                break
            
            # Skip assistant/agent responses
            if any(skip in line_lower for skip in ['assistant:', 'ai assistant', 'end node:']):
                continue
            
            # Check for explicit "User:" prefix
            if line_lower.startswith('user:'):
                user_query = line.split(':', 1)[1].strip() if ':' in line else line
                logger.info(f"🌐 WEBSEARCH QUERY EXTRACTION: Found user message with 'User:' prefix")
                break
            
            # Check for query-like content
            if ':' in line:
                prefix = line.split(':', 1)[0].strip().lower()
                if 'assistant' not in prefix and 'ai' not in prefix and 'start' not in prefix and 'end' not in prefix:
                    potential_query = line.split(':', 1)[1].strip() if ':' in line else line
                    if any(word in potential_query.lower() for word in ['what', 'how', 'tell', 'explain', 'find', 'search', 'about', '?']):
                        user_query = potential_query
                        logger.info(f"🌐 WEBSEARCH QUERY EXTRACTION: Found potential user query")
                        break
        
        if user_query:
            query_text = user_query
        else:
            # Fallback: get the last few meaningful lines
            recent_lines = []
            for line in reversed(lines[-10:]):
                line = line.strip()
                if not line:
                    continue
                line_lower = line.lower()
                if any(skip in line_lower for skip in ['assistant:', 'ai assistant', 'start node:', 'end node:']):
                    continue
                recent_lines.insert(0, line)
                if len(recent_lines) >= 3:
                    break
            
            if recent_lines:
                query_text = " ".join(recent_lines)
                logger.info(f"🌐 WEBSEARCH QUERY EXTRACTION: Using fallback - combined {len(recent_lines)} lines")
            else:
                logger.warning("🌐 WEBSEARCH QUERY EXTRACTION: No user query found")
                return ""
        
        # Limit query length for web search (unlike DocAware, web search benefits from shorter queries)
        max_query_length = 500
        if len(query_text) > max_query_length:
            # Try to break at sentence boundary
            truncated = query_text[:max_query_length]
            last_sentence_end = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))
            
            if last_sentence_end > max_query_length * 0.7:
                query_text = truncated[:last_sentence_end + 1]
            else:
                query_text = truncated.rsplit(' ', 1)[0] + "..."
            
            logger.info(f"🌐 WEBSEARCH QUERY EXTRACTION: Truncated to {len(query_text)} chars for web search")
        
        logger.info(f"🌐 WEBSEARCH QUERY EXTRACTION: Final query: '{query_text[:100]}...'")
        return query_text
    
    # =========================================================================
    # Result Formatting
    # =========================================================================
    
    def _format_url_results(self, urls: List[str], results: Dict[str, Any]) -> str:
        """
        Format URL fetch results into context string.
        
        Args:
            urls: Original list of URLs (to preserve order)
            results: Dict mapping URL to fetch result
            
        Returns:
            Formatted context string
        """
        if not results:
            return "No content could be retrieved from the specified URLs."
        
        parts: List[str] = []
        successful = 0
        
        for i, url in enumerate(urls, 1):
            capture = results.get(url) or {}
            
            error = capture.get('extraction_error')
            status_code = capture.get('status_code')
            title = capture.get('title') or capture.get('domain') or 'Untitled'
            meta_description = capture.get('meta_description') or ''
            truncated = bool(capture.get('truncated'))
            word_count = capture.get('word_count', 0)
            
            if error:
                parts.append(f"[{i}] ❌ Failed to fetch: {url}")
                parts.append(f"    Error: {error}")
                if status_code is not None:
                    parts.append(f"    Status code: {status_code}")
                parts.append("")
                continue
            
            successful += 1
            parts.append(f"[{i}] {title}")
            parts.append(f"    URL: {url}")
            if meta_description:
                parts.append(f"    Description: {meta_description}")
            if status_code is not None:
                parts.append(f"    Status code: {status_code}")
            if word_count:
                parts.append(f"    Approximate word count: {word_count}")
            if truncated:
                parts.append("    Note: Content truncated for context length limits.")
            
            # Build a flattened preview from sections for this URL
            preview_lines: List[str] = []
            sections = capture.get('sections') or []
            for section in sections:
                sec_type = section.get('type')
                text = section.get('text') or ''
                if not text:
                    continue
                if sec_type == 'heading':
                    level = section.get('level') or 1
                    prefix = '#' * max(1, min(level, 6))
                    preview_lines.append(f"{prefix} {text}")
                else:
                    preview_lines.append(text)
            
            preview_text = "\n\n".join(preview_lines).strip()
            if preview_text:
                parts.append("    Content:")
                # Indent content block for readability
                indented = "\n".join(f"{line}" for line in preview_text.splitlines())
                parts.append(indented)
            
            parts.append("")
        
        header = f"Retrieved content from {successful}/{len(urls)} URLs:\n\n"
        return header + "\n".join(parts)
    
    # =========================================================================
    # Metrics Logging
    # =========================================================================
    
    async def _log_websearch_metrics(
        self,
        project_id: str,
        agent_node: Dict[str, Any],
        mode: str,
        duration_ms: float,
        context_length: int,
        success: bool
    ):
        """
        Log WebSearch experiment metrics for analysis.
        
        Args:
            project_id: Project ID
            agent_node: Agent configuration
            mode: WebSearch mode used
            duration_ms: Time taken in milliseconds
            context_length: Length of returned context
            success: Whether search was successful
        """
        try:
            agent_data = agent_node.get('data', {})
            agent_name = agent_data.get('name', 'UnknownAgent')
            
            configuration = {
                "agent_name": agent_name,
                "mode": mode,
                "cache_ttl": agent_data.get('web_search_cache_ttl', 3600),
                "max_results": agent_data.get('web_search_max_results', 5),
            }
            
            exp_payload = {
                "experiment": "websearch",
                "project_id": project_id,
                "agent_name": agent_name,
                "mode": mode,
                "duration_ms": duration_ms,
                "context_length": context_length,
                "success": success,
            }
            
            # Add mode-specific data
            if mode == 'urls':
                exp_payload['url_count'] = len(agent_data.get('web_search_urls', []))
            elif mode == 'domains':
                exp_payload['domain_count'] = len(agent_data.get('web_search_domains', []))
            
            logger.info(f"EXP_METRIC_WEBSEARCH | {json.dumps(exp_payload, default=str)}")
            
            # Store in database
            if project_id:
                try:
                    from users.models import IntelliDocProject, ExperimentMetric
                    
                    def save_metric():
                        try:
                            project_obj = IntelliDocProject.objects.get(project_id=project_id)
                            metric = ExperimentMetric.objects.create(
                                project=project_obj,
                                experiment_type='websearch',
                                metric_data=exp_payload,
                                configuration=configuration,
                            )
                            logger.info(f"✅ Stored WebSearch experiment metric: id={metric.id}")
                            return metric.id
                        except IntelliDocProject.DoesNotExist:
                            logger.warning(f"⚠️ Could not save WebSearch metric: Project {project_id} not found")
                            return None
                        except Exception as e:
                            logger.error(f"❌ Failed to save WebSearch metric: {e}")
                            return None
                    
                    await sync_to_async(save_metric)()
                except Exception as db_error:
                    logger.warning(f"⚠️ Failed to store WebSearch metric in database: {db_error}")
                    
        except Exception as metric_error:
            logger.error(f"❌ EXP_METRIC_WEBSEARCH: Failed to log metrics: {metric_error}")
    
    # =========================================================================
    # Aggregated Input Support (for multi-agent workflows)
    # =========================================================================
    
    def extract_search_query_from_aggregated_input(
        self, 
        aggregated_context: Dict[str, Any]
    ) -> str:
        """
        Extract search query from aggregated input context (all connected agent outputs).
        
        Args:
            aggregated_context: Output from aggregate_multiple_inputs
            
        Returns:
            Search query string extracted from aggregated inputs
        """
        logger.info(f"🌐 WEBSEARCH AGGREGATED INPUT: Extracting query from {aggregated_context.get('input_count', 0)} inputs")
        
        query_parts = []
        
        # Add primary input
        if aggregated_context.get('primary_input'):
            primary_input = str(aggregated_context['primary_input'])
            query_parts.append(primary_input)
        
        # Add secondary inputs
        for secondary in aggregated_context.get('secondary_inputs', []):
            if secondary.get('content'):
                query_parts.append(str(secondary['content']))
        
        combined_query = " ".join(query_parts).strip()
        
        if not combined_query:
            logger.warning("🌐 WEBSEARCH AGGREGATED INPUT: Empty combined query")
            return ""
        
        # Limit for web search
        max_query_length = 500
        if len(combined_query) > max_query_length:
            truncated = combined_query[:max_query_length]
            last_sentence_end = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))
            
            if last_sentence_end > max_query_length * 0.7:
                combined_query = truncated[:last_sentence_end + 1]
            else:
                combined_query = truncated.rsplit(' ', 1)[0] + "..."
        
        logger.info(f"🌐 WEBSEARCH AGGREGATED INPUT: Final query ({len(combined_query)} chars)")
        return combined_query
    
    async def get_websearch_context_from_query(
        self, 
        agent_node: Dict[str, Any], 
        search_query: str, 
        project_id: str
    ) -> str:
        """
        Retrieve web search context using a specific search query (from aggregated input).
        
        Args:
            agent_node: Agent configuration
            search_query: Search query extracted from aggregated inputs
            project_id: Project ID for logging
            
        Returns:
            Formatted web context string
        """
        if not self.is_websearch_enabled(agent_node):
            return ""
        
        agent_data = agent_node.get('data', {})
        mode = self.get_websearch_mode(agent_node)
        cache_ttl = agent_data.get('web_search_cache_ttl', 3600)
        max_results = agent_data.get('web_search_max_results', 5)
        
        logger.info(f"🌐 WEBSEARCH FROM QUERY: mode={mode}, query='{search_query[:50]}...'")
        
        start_time = time.time()
        
        try:
            if mode == 'urls':
                # URL mode ignores the query and just fetches configured URLs
                urls = agent_data.get('web_search_urls', [])
                if not urls:
                    return ""
                context = await self._get_url_context(urls, cache_ttl, project_id)
                
            elif mode == 'domains':
                domains = agent_data.get('web_search_domains', [])
                context = await self._get_domain_search_context(search_query, domains, max_results, cache_ttl, project_id)
                
            else:
                context = await self._get_general_search_context(search_query, max_results, cache_ttl, project_id)
            
            duration_ms = (time.time() - start_time) * 1000
            
            await self._log_websearch_metrics(
                project_id=project_id,
                agent_node=agent_node,
                mode=mode,
                duration_ms=duration_ms,
                context_length=len(context),
                success=bool(context)
            )
            
            return context
            
        except Exception as e:
            logger.error(f"❌ WEBSEARCH FROM QUERY: Error: {e}")
            return f"⚠️ Web search failed: {str(e)}"
