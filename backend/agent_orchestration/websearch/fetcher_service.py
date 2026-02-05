"""
Website Fetcher Service
=======================

Provides parallel URL fetching with content extraction using aiohttp and BeautifulSoup.
Designed for efficient retrieval of multiple web pages concurrently.
"""

import asyncio
import logging
import re
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
import aiohttp
from bs4 import BeautifulSoup
from django.conf import settings

logger = logging.getLogger('agent_orchestration')


class WebsiteFetcherService:
    """
    Service for fetching and extracting content from web pages.
    Supports parallel fetching of multiple URLs using asyncio.
    """
    
    # Default configuration
    DEFAULT_TIMEOUT = 30  # seconds
    DEFAULT_MAX_CONTENT_LENGTH = 100000  # characters
    
    # User agent to avoid being blocked
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    # Tags to remove from content
    REMOVE_TAGS = [
        'script', 'style', 'nav', 'footer', 'header', 'aside',
        'form', 'noscript', 'iframe', 'svg', 'canvas', 'video', 'audio'
    ]
    
    # CSS classes/IDs often associated with non-content elements
    REMOVE_PATTERNS = [
        'nav', 'menu', 'sidebar', 'footer', 'header', 'advertisement',
        'ad-', 'ads-', 'social', 'share', 'comment', 'cookie', 'popup'
    ]
    
    def __init__(self):
        """Initialize fetcher with settings from Django config."""
        websearch_config = getattr(settings, 'WEBSEARCH_CONFIG', {})
        self.timeout = websearch_config.get('REQUEST_TIMEOUT', self.DEFAULT_TIMEOUT)
        self.max_content_length = websearch_config.get('MAX_CONTENT_LENGTH', self.DEFAULT_MAX_CONTENT_LENGTH)
        logger.info(f"🌐 WEBSITE FETCHER: Initialized (timeout: {self.timeout}s, max_content: {self.max_content_length} chars)")
    
    # =========================================================================
    # Main Public Methods
    # =========================================================================
    
    async def fetch_urls_parallel(
        self, 
        urls: List[str], 
        timeout: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch multiple URLs in parallel using aiohttp.
        
        Args:
            urls: List of URLs to fetch
            timeout: Optional timeout override per request
            
        Returns:
            List of result dicts, one per URL, in the same order
        """
        if not urls:
            return []
        
        effective_timeout = timeout or self.timeout
        logger.info(f"🌐 WEBSITE FETCHER: Fetching {len(urls)} URLs in parallel (timeout: {effective_timeout}s)")
        
        # Create timeout configuration
        client_timeout = aiohttp.ClientTimeout(total=effective_timeout)
        
        # Configure headers
        headers = {
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        async with aiohttp.ClientSession(timeout=client_timeout, headers=headers) as session:
            # Create tasks for all URLs
            tasks = [self._fetch_single(session, url) for url in urls]
            
            # Execute all tasks in parallel, capturing exceptions
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results, converting exceptions to error dicts
        processed_results = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                logger.error(f"❌ WEBSITE FETCHER: Failed to fetch {url}: {result}")
                processed_results.append({
                    'url': url,
                    'success': False,
                    'error': str(result),
                    'title': '',
                    'content': '',
                    'metadata': {}
                })
            else:
                processed_results.append(result)
        
        # Log summary
        successful = sum(1 for r in processed_results if r.get('success', False))
        logger.info(f"✅ WEBSITE FETCHER: Completed {successful}/{len(urls)} URLs successfully")
        
        return processed_results
    
    async def fetch_single_url(self, url: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Fetch a single URL.
        
        Args:
            url: URL to fetch
            timeout: Optional timeout override
            
        Returns:
            Result dict with url, success, title, content, metadata, error
        """
        results = await self.fetch_urls_parallel([url], timeout)
        return results[0] if results else {
            'url': url,
            'success': False,
            'error': 'No results returned',
            'title': '',
            'content': '',
            'metadata': {}
        }
    
    # =========================================================================
    # Internal Methods
    # =========================================================================
    
    async def _fetch_single(self, session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
        """
        Fetch a single URL using the provided session.
        
        Args:
            session: aiohttp ClientSession
            url: URL to fetch
            
        Returns:
            Result dict with extracted content
        """
        try:
            logger.debug(f"🌐 FETCHING: {url}")
            
            async with session.get(url, allow_redirects=True) as response:
                # Check response status
                if response.status != 200:
                    return {
                        'url': url,
                        'success': False,
                        'error': f"HTTP {response.status}: {response.reason}",
                        'title': '',
                        'content': '',
                        'metadata': {'status_code': response.status}
                    }
                
                # Check content type
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                    return {
                        'url': url,
                        'success': False,
                        'error': f"Non-HTML content type: {content_type}",
                        'title': '',
                        'content': '',
                        'metadata': {'content_type': content_type}
                    }
                
                # Read content
                html = await response.text()
                
                # Extract content using BeautifulSoup
                extracted = self.extract_content(html, url)
                
                return {
                    'url': url,
                    'success': True,
                    'error': None,
                    'title': extracted['title'],
                    'content': extracted['content'],
                    'metadata': {
                        'status_code': response.status,
                        'content_type': content_type,
                        'content_length': len(extracted['content']),
                        'final_url': str(response.url),
                        **extracted['metadata']
                    }
                }
                
        except asyncio.TimeoutError:
            return {
                'url': url,
                'success': False,
                'error': 'Request timed out',
                'title': '',
                'content': '',
                'metadata': {}
            }
        except aiohttp.ClientError as e:
            return {
                'url': url,
                'success': False,
                'error': f"Client error: {str(e)}",
                'title': '',
                'content': '',
                'metadata': {}
            }
        except Exception as e:
            return {
                'url': url,
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'title': '',
                'content': '',
                'metadata': {}
            }
    
    def extract_content(self, html: str, url: str) -> Dict[str, Any]:
        """
        Extract main content from HTML using BeautifulSoup.
        Removes navigation, scripts, styles, and other boilerplate.
        
        Args:
            html: Raw HTML content
            url: Source URL (for context)
            
        Returns:
            Dict with title, content, and metadata
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract title
            title = ''
            if soup.title:
                title = soup.title.get_text(strip=True)
            elif soup.find('h1'):
                title = soup.find('h1').get_text(strip=True)
            
            # Extract meta description
            meta_description = ''
            meta_tag = soup.find('meta', attrs={'name': 'description'})
            if meta_tag and meta_tag.get('content'):
                meta_description = meta_tag['content']
            
            # Remove unwanted tags
            for tag_name in self.REMOVE_TAGS:
                for tag in soup.find_all(tag_name):
                    tag.decompose()
            
            # Remove elements with common non-content class/id patterns
            for pattern in self.REMOVE_PATTERNS:
                for element in soup.find_all(class_=re.compile(pattern, re.I)):
                    element.decompose()
                for element in soup.find_all(id=re.compile(pattern, re.I)):
                    element.decompose()
            
            # Try to find main content area
            main_content = None
            
            # Check for common content containers
            for selector in ['main', 'article', '[role="main"]', '.content', '#content', '.post', '.article']:
                if selector.startswith('.') or selector.startswith('#'):
                    # CSS class or ID selector
                    if selector.startswith('.'):
                        main_content = soup.find(class_=selector[1:])
                    else:
                        main_content = soup.find(id=selector[1:])
                elif selector.startswith('['):
                    # Attribute selector
                    attr_match = re.match(r'\[(\w+)="(\w+)"\]', selector)
                    if attr_match:
                        main_content = soup.find(attrs={attr_match.group(1): attr_match.group(2)})
                else:
                    main_content = soup.find(selector)
                
                if main_content:
                    break
            
            # Fall back to body if no main content area found
            if not main_content:
                main_content = soup.find('body') or soup
            
            # Extract text content
            text_content = main_content.get_text(separator='\n', strip=True)
            
            # Clean up whitespace
            text_content = re.sub(r'\n\s*\n', '\n\n', text_content)
            text_content = re.sub(r' +', ' ', text_content)
            text_content = text_content.strip()
            
            # Truncate if too long
            if len(text_content) > self.max_content_length:
                text_content = text_content[:self.max_content_length] + "... [truncated]"
            
            # Extract some metadata
            domain = urlparse(url).netloc
            
            return {
                'title': title[:500] if title else domain,  # Limit title length
                'content': text_content,
                'metadata': {
                    'domain': domain,
                    'description': meta_description[:500] if meta_description else '',
                    'word_count': len(text_content.split()),
                    'truncated': len(text_content) >= self.max_content_length
                }
            }
            
        except Exception as e:
            logger.error(f"❌ CONTENT EXTRACTION: Failed for {url}: {e}")
            return {
                'title': urlparse(url).netloc,
                'content': '',
                'metadata': {'extraction_error': str(e)}
            }
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def is_valid_url(self, url: str) -> bool:
        """
        Check if a URL is valid and fetchable.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid
        """
        try:
            parsed = urlparse(url)
            return all([
                parsed.scheme in ('http', 'https'),
                parsed.netloc,
                len(url) < 2048  # Reasonable URL length limit
            ])
        except Exception:
            return False
    
    def normalize_url(self, url: str) -> str:
        """
        Normalize a URL for consistent handling.
        
        Args:
            url: URL to normalize
            
        Returns:
            Normalized URL string
        """
        # Add scheme if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Parse and reconstruct
        parsed = urlparse(url)
        
        # Remove trailing slash from path (unless it's just /)
        path = parsed.path
        if path.endswith('/') and len(path) > 1:
            path = path[:-1]
        
        # Reconstruct URL
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        
        return normalized
