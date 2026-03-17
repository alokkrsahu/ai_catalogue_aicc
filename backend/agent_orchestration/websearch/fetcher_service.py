"""
Website Fetcher Service
=======================

Provides parallel URL fetching with content extraction using aiohttp and BeautifulSoup.
Designed for efficient retrieval of multiple web pages concurrently.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup
from django.conf import settings

logger = logging.getLogger('agent_orchestration')


@dataclass
class PageSection:
    """
    Single section of a web page. This is part of the canonical
    PageCapture representation – not a secondary cache layer.
    """
    type: str  # heading|paragraph|list|table|code|other
    level: Optional[int] = None  # for headings
    text: str = ""
    html_snippet: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PageCapture:
    """
    Canonical, single-source-of-truth representation of a fetched URL.
    All downstream views (LLM context, summaries, etc.) are derived
    from this structure and not stored separately.
    """
    url: str
    final_url: Optional[str] = None
    domain: Optional[str] = None
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    title: Optional[str] = None
    meta_description: Optional[str] = None
    raw_html: Optional[str] = None
    raw_html_size: int = 0
    raw_html_truncated: bool = False
    sections: List[PageSection] = field(default_factory=list)
    word_count: int = 0
    truncated: bool = False  # text-level truncation flag
    extraction_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert PageCapture to a JSON-serialisable dict for caching.
        """
        data = asdict(self)
        # dataclasses.asdict already converts nested dataclasses
        return data


class WebsiteFetcherService:
    """
    Service for fetching and extracting content from web pages.
    Supports parallel fetching of multiple URLs using asyncio.
    """
    
    # Default configuration
    DEFAULT_TIMEOUT = 30  # seconds
    DEFAULT_MAX_CONTENT_LENGTH = 100000  # characters (LLM-oriented text cap)
    DEFAULT_MAX_HTML_BYTES = 2_000_000  # 2 MB raw HTML cap
    
    # User agent to avoid being blocked
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    # Tags to remove from content (only for derived text, not raw_html)
    REMOVE_TAGS = [
        'script', 'style', 'noscript'
    ]
    
    # CSS classes/IDs often associated with non-content elements
    REMOVE_PATTERNS = [
        'advertisement',
        'ad-', 'ads-',
        'cookie',
        'popup'
    ]
    
    def __init__(self):
        """Initialize fetcher with settings from Django config."""
        websearch_config = getattr(settings, 'WEBSEARCH_CONFIG', {})
        self.timeout = websearch_config.get('REQUEST_TIMEOUT', self.DEFAULT_TIMEOUT)
        self.max_content_length = websearch_config.get('MAX_CONTENT_LENGTH', self.DEFAULT_MAX_CONTENT_LENGTH)
        self.max_html_bytes = websearch_config.get('MAX_HTML_BYTES', self.DEFAULT_MAX_HTML_BYTES)
        logger.info(
            f"🌐 WEBSITE FETCHER: Initialized "
            f"(timeout: {self.timeout}s, max_content: {self.max_content_length} chars, "
            f"max_html_bytes: {self.max_html_bytes})"
        )
    
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
            List of PageCapture dicts, one per URL, in the same order
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
        processed_results: List[Dict[str, Any]] = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                logger.error(f"❌ WEBSITE FETCHER: Failed to fetch {url}: {result}")
                capture = PageCapture(
                    url=url,
                    extraction_error=str(result),
                )
                processed_results.append(capture.to_dict())
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
            PageCapture dict
        """
        results = await self.fetch_urls_parallel([url], timeout)
        if results:
            return results[0]
        capture = PageCapture(
            url=url,
            extraction_error='No results returned',
        )
        return capture.to_dict()
    
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
            PageCapture dict with extracted data
        """
        try:
            logger.debug(f"🌐 FETCHING: {url}")
            
            async with session.get(url, allow_redirects=True) as response:
                status = response.status
                content_type = response.headers.get('Content-Type', '')
                final_url = str(response.url)
                
                capture = PageCapture(
                    url=url,
                    final_url=final_url,
                    status_code=status,
                    content_type=content_type,
                    domain=urlparse(url).netloc,
                )
                
                # Non-200 responses: record metadata but do not attempt extraction
                if status != 200:
                    capture.extraction_error = f"HTTP {status}: {response.reason}"
                    return capture.to_dict()
                
                # Only handle HTML/XHTML for now
                if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                    capture.extraction_error = f"Non-HTML content type: {content_type}"
                    return capture.to_dict()
                
                # Read raw HTML (with byte cap)
                raw_bytes = await response.read()
                capture.raw_html_size = len(raw_bytes)
                if len(raw_bytes) > self.max_html_bytes:
                    capture.raw_html_truncated = True
                    raw_bytes = raw_bytes[: self.max_html_bytes]
                try:
                    html = raw_bytes.decode(response.charset or 'utf-8', errors='replace')
                except Exception:
                    html = raw_bytes.decode('utf-8', errors='replace')
                capture.raw_html = html
                
                # Parse HTML and populate sections + derived text metadata
                self._populate_from_html(capture, html)
                
                return capture.to_dict()
                
        except asyncio.TimeoutError:
            capture = PageCapture(
                url=url,
                extraction_error='Request timed out',
            )
            return capture.to_dict()
        except aiohttp.ClientError as e:
            capture = PageCapture(
                url=url,
                extraction_error=f"Client error: {str(e)}",
            )
            return capture.to_dict()
        except Exception as e:
            capture = PageCapture(
                url=url,
                extraction_error=f"Unexpected error: {str(e)}",
            )
            logger.error(f"❌ CONTENT FETCH: Failed for {url}: {e}")
            return capture.to_dict()
    
    def _populate_from_html(self, capture: PageCapture, html: str) -> None:
        """
        Populate a PageCapture instance from raw HTML.
        This function is responsible for building the single canonical
        representation (sections + derived text metadata).
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Title
            title = ''
            if soup.title:
                title = soup.title.get_text(strip=True)
            elif soup.find('h1'):
                title = soup.find('h1').get_text(strip=True)
            capture.title = (title[:500] if title else capture.domain)
            
            # Meta description
            meta_description = ''
            meta_tag = soup.find('meta', attrs={'name': 'description'})
            if meta_tag and meta_tag.get('content'):
                meta_description = meta_tag['content']
            capture.meta_description = meta_description[:500] if meta_description else None
            
            # Remove only obviously non-content tags globally
            for tag_name in self.REMOVE_TAGS:
                for tag in soup.find_all(tag_name):
                    tag.decompose()
            
            # Remove elements with known junk patterns (ad/cookie/popups)
            for pattern in self.REMOVE_PATTERNS:
                for element in soup.find_all(class_=re.compile(pattern, re.I)):
                    element.decompose()
                for element in soup.find_all(id=re.compile(pattern, re.I)):
                    element.decompose()
            
            sections: List[PageSection] = []
            
            # Headings
            for level in range(1, 7):
                for h in soup.find_all(f'h{level}'):
                    text = h.get_text(strip=True)
                    if not text:
                        continue
                    sections.append(
                        PageSection(
                            type='heading',
                            level=level,
                            text=text,
                            html_snippet=str(h)[:1000],
                        )
                    )
            
            # Paragraphs
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if not text:
                    continue
                sections.append(
                    PageSection(
                        type='paragraph',
                        text=text,
                        html_snippet=str(p)[:1000],
                    )
                )
            
            # Lists (ul/ol)
            for lst in soup.find_all(['ul', 'ol']):
                items = [li.get_text(strip=True) for li in lst.find_all('li')]
                items = [i for i in items if i]
                if not items:
                    continue
                sections.append(
                    PageSection(
                        type='list',
                        text='\n'.join(f"- {item}" for item in items),
                        html_snippet=str(lst)[:1000],
                        metadata={'item_count': len(items)},
                    )
                )
            
            # Tables
            for tbl in soup.find_all('table'):
                rows = []
                for tr in tbl.find_all('tr'):
                    cells = [c.get_text(strip=True) for c in tr.find_all(['th', 'td'])]
                    if cells:
                        rows.append(cells)
                if not rows:
                    continue
                sections.append(
                    PageSection(
                        type='table',
                        text='\n'.join(' | '.join(row) for row in rows),
                        html_snippet=str(tbl)[:1000],
                        metadata={'row_count': len(rows)},
                    )
                )
            
            # Code/pre blocks
            for code_block in soup.find_all(['pre', 'code']):
                text = code_block.get_text('\n', strip=True)
                if not text:
                    continue
                sections.append(
                    PageSection(
                        type='code',
                        text=text,
                        html_snippet=str(code_block)[:1000],
                    )
                )
            
            capture.sections = sections
            
            # Build a flattened text view for metrics and eventual LLM context
            # (not cached separately – always derived from this capture).
            parts: List[str] = []
            for sec in sections:
                if sec.type == 'heading':
                    prefix = '#' * (sec.level or 1)
                    parts.append(f"{prefix} {sec.text}")
                else:
                    parts.append(sec.text)
            flat_text = '\n\n'.join(parts).strip()
            
            # Clean whitespace
            flat_text = re.sub(r'\n\s*\n', '\n\n', flat_text)
            flat_text = re.sub(r' +', ' ', flat_text)
            flat_text = flat_text.strip()
            
            # Truncate for metrics/LLM usage but keep flag
            if len(flat_text) > self.max_content_length:
                capture.truncated = True
                flat_text = flat_text[: self.max_content_length] + "... [truncated]"
            
            capture.word_count = len(flat_text.split()) if flat_text else 0
            
        except Exception as e:
            logger.error(f"❌ CONTENT EXTRACTION: Failed for {capture.url}: {e}")
            capture.extraction_error = str(e)
    
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
