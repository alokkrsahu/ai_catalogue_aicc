"""
Website Fetcher Service
=======================

Provides parallel URL fetching with content extraction using aiohttp and BeautifulSoup.
Designed for efficient retrieval of multiple web pages concurrently.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import aiohttp
from bs4 import BeautifulSoup, NavigableString, Tag
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
    # Informational warning (non-fatal) — set when the page appears to be a
    # JavaScript SPA. Surfaced even when some content was still extracted so
    # downstream consumers can flag the page as potentially incomplete.
    spa_warning: Optional[str] = None
    anchor_fragment: Optional[str] = None  # the #fragment from the original URL, if any
    # Informational, never fatal. Set when extraction succeeded mechanically but
    # produced suspiciously little text (JS-rendered page, failed narrowing).
    # Deliberately NOT extraction_error: the pipeline must keep flowing, and a
    # thin page is still allowed to contribute whatever it has. Grep the logs
    # for "THIN EXTRACT" / "FRAGMENT FALLBACK" to trace these.
    quality_warning: Optional[str] = None

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
        'script', 'style', 'noscript',
        # Structural chrome — never contain primary article content
        'nav', 'header', 'footer', 'aside',
        'form',        # search boxes, login forms
        'menu',
        'figure',      # image captions fragment LLM context
        'figcaption',
    ]

    # CSS classes/IDs often associated with non-content elements.
    REMOVE_PATTERNS = [
        r'advertisement', r'\bad[-_]', r'\bads[-_]', r'[-_]ads\b',
        r'cookie', r'popup', r'modal', r'overlay',
        r'nav(igation|bar)?[-_\s]', r'[-_]nav\b',
        r'sidebar', r'side[-_]bar',
        r'widget[-_](area|zone|section|sidebar)',  # scoped — r'widget' alone was too broad
        r'breadcrumb', r'site[-_]header', r'site[-_]footer',
        r'social[-_]', r'share[-_]', r'sharing',
        r'related[-_]', r'recommended[-_]', r'also[-_]read',
        r'comment(s)?[-_]', r'discussion[-_]',
        r'menu[-_]', r'[-_]menu\b',
        r'banner[-_]', r'promo[-_]',
        r'toc\b', r'table[-_]of[-_]contents',
    ]
    # Pre-compiled once at import; avoids re-compiling 25 regexes per page parse.
    _REMOVE_PATTERNS_COMPILED = [re.compile(p, re.I) for p in REMOVE_PATTERNS]

    # Minimum heading text length — reduced to 3 to preserve short but valid headings
    # like "API", "FAQ", "Usage", "Setup", "Overview", "Reference", etc.
    MIN_HEADING_LEN = 3

    # -------------------------------------------------------------------------
    # Extraction-quality thresholds
    #
    # None of these ever raise or set extraction_error — they only populate the
    # non-fatal `quality_warning` field so a thin page stays usable while
    # remaining greppable in the logs (marker: THIN EXTRACT / FRAGMENT FALLBACK).
    # -------------------------------------------------------------------------

    # Anchors that mark the top of a page / a whole-page wrapper rather than a
    # real subsection. Narrowing to these yields just the table of contents, so
    # they are ignored and the full page is extracted instead.
    NON_CONTENT_ANCHORS = {
        'topofpage', 'top', 'content', 'main', 'start',
        'begin', 'pagetop', 'page-top', 'top-of-page', 'maincontent',
    }

    # A fragment-scoped extraction shorter than this is treated as a failed
    # narrowing and falls back to the whole page.
    FRAGMENT_MIN_CHARS = 500
    # ...or shorter than this fraction of what the whole page yields.
    FRAGMENT_MIN_RATIO = 0.20

    # Below this many extracted characters, run the format-adaptive recovery
    # strategies (JSON-LD, hydrated SPA state, noscript, text density). Set
    # comfortably above THIN_TEXT_CHARS so partially-extracted pages — a heading
    # plus one stray paragraph — also get a chance at a fuller reading.
    RECOVERY_TRIGGER_CHARS = 1000

    # Absolute floor for a "we got essentially nothing" page.
    THIN_TEXT_CHARS = 200
    # Ratio floor: text extracted vs raw HTML size. 17 chars from 358 KB of HTML
    # must never be reported as a clean success (observed on JS-rendered GitBook
    # pages whose nav sidebar defeats the SPA body-text heuristic).
    THIN_TEXT_HTML_RATIO = 0.0005
    # Only apply the ratio test to pages with a substantial HTML payload.
    THIN_RATIO_MIN_HTML_BYTES = 50_000

    # How many machine-readable alternate URLs to try for an unreadable page.
    # Kept small: this costs one extra request each, only on pages that already
    # failed, and the first candidate is almost always the right one.
    MAX_MARKDOWN_ALTERNATES = 2

    # Framework chrome that survives structural cleanup because it sits inside
    # the content container (GitBook feedback widget / timestamp footer).
    CHROME_TEXT_PATTERNS = [
        r'^was this (helpful|page helpful)\??$',
        # GitBook renders this with no separating space ("Last updated18 days
        # ago"), so no \b after "updated".
        r'^last updated.{0,40}ago$',
        r'^(previous|next)$',
        r'^on this page$',
        r'^edit (on|this) (github|page)$',
        r'^copy(\s+to\s+clipboard)?$',
    ]
    _CHROME_TEXT_COMPILED = [re.compile(p, re.I) for p in CHROME_TEXT_PATTERNS]

    # Element-type sets used in single-pass traversal
    HEADING_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
    BLOCK_EXTRACT_TAGS = {'ul', 'ol', 'table', 'pre', 'dl'}
    # <summary> labels a <details> disclosure — semantically the heading of the
    # collapsed block. Standard HTML used for FAQs, glossaries and per-term
    # documentation; without this the label text is dropped entirely.
    DISCLOSURE_HEADING_TAGS = {'summary'}
    DISCLOSURE_HEADING_LEVEL = 4
    # Paragraph tags inside these block parents are captured via the parent
    INLINE_SKIP_PARENTS = {'li', 'td', 'th', 'pre'}

    # Known SPA mount-point IDs (client-side-rendered pages)
    SPA_MOUNT_IDS = {'__next', '__nuxt', '__gatsby', 'app', 'root', '__app'}

    # -------------------------------------------------------------------------
    # Content-root detection regexes
    # Expanded to cover common documentation frameworks:
    #   Docusaurus, MkDocs/Material, GitBook, VitePress, Sphinx,
    #   GitHub markdown, Confluence, Notion, ReadTheDocs, Hexo, Hugo
    # -------------------------------------------------------------------------
    _CONTENT_ID_RE = re.compile(
        r'\b('
        # Generic
        r'content|main|article|post[-_]?body|entry[-_]?content'
        r'|story[-_]?body|article[-_]?body|page[-_]?content'
        # GitBook / generic
        r'|page[-_]?body|page[-_]?inner|article[-_]?inner'
        # Doc frameworks
        r'|doc[-_]?content|doc[-_]?body|doc[-_]?main'
        r')\b',
        re.I,
    )
    _CONTENT_CLASS_RE = re.compile(
        r'(^|\s)('
        # ---- Existing ----
        r'article|entry|post|story|prose|richtext'
        r'|article[-_]body|post[-_]body|entry[-_]content'
        r'|main[-_]content|page[-_]content|content[-_]body'
        # ---- Docusaurus v2/v3 ----
        r'|theme[-_]doc[-_]markdown|docMainContainer|docItemContainer|docItemCol'
        # ---- MkDocs / Material for MkDocs ----
        r'|md[-_]content|md[-_]main__inner|md[-_]typeset'
        # ---- GitBook ----
        r'|page[-_]body|page[-_]inner|gitbook[-_]root'
        # ---- VitePress ----
        r'|vp[-_]doc'
        # ---- Sphinx ----
        r'|documentwrapper|bodywrapper'
        # ---- GitHub rendered markdown ----
        r'|markdown[-_]body|blob[-_]wrapper'
        # ---- Confluence ----
        r'|wiki[-_]content|aui[-_]page[-_]panel[-_]content'
        # ---- Notion (public pages, not SPA) ----
        r'|notion[-_]page[-_]content'
        # ---- ReadTheDocs / RST ----
        r'|rstdoc|rst[-_]content'
        # ---- Hexo / Hugo ----
        r'|article[-_]inner|article[-_]content|single'
        r')(\s|$)',
        re.I,
    )

    # Default concurrency cap for parallel fetching — prevents DNS floods and
    # target-host throttling when a URL list is large.
    DEFAULT_FETCH_CONCURRENCY = 10

    def __init__(self):
        """Initialize fetcher with settings from Django config."""
        websearch_config = getattr(settings, 'WEBSEARCH_CONFIG', {})
        self.timeout = websearch_config.get('REQUEST_TIMEOUT', self.DEFAULT_TIMEOUT)
        self.max_content_length = websearch_config.get('MAX_CONTENT_LENGTH', self.DEFAULT_MAX_CONTENT_LENGTH)
        self.max_html_bytes = websearch_config.get('MAX_HTML_BYTES', self.DEFAULT_MAX_HTML_BYTES)
        self.fetch_concurrency = websearch_config.get('FETCH_CONCURRENCY', self.DEFAULT_FETCH_CONCURRENCY)
        logger.info(
            f"🌐 WEBSITE FETCHER: Initialized "
            f"(timeout: {self.timeout}s, max_content: {self.max_content_length} chars, "
            f"max_html_bytes: {self.max_html_bytes}, fetch_concurrency: {self.fetch_concurrency})"
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

        # Bound concurrency so large URL lists don't trigger DNS floods or
        # target-host throttling. Small lists pay no overhead.
        sem = asyncio.Semaphore(max(1, self.fetch_concurrency))

        async with aiohttp.ClientSession(timeout=client_timeout, headers=headers) as session:
            async def _bounded_fetch(u: str):
                async with sem:
                    return await self._fetch_single(session, u)

            tasks = [_bounded_fetch(url) for url in urls]
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

        # Count successes by absence of extraction_error (PageCapture never sets a 'success' key)
        successful = sum(1 for r in processed_results if not r.get('extraction_error'))
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
            url: URL to fetch (may include a #fragment)

        Returns:
            PageCapture dict with extracted data
        """
        try:
            logger.debug(f"🌐 FETCHING: {url}")

            # Parse fragment before the HTTP request — browsers never send fragments
            # to the server, but we use them post-parse to narrow extraction scope.
            parsed_url = urlparse(url)
            fragment = parsed_url.fragment or None
            fetch_url = urlunparse(parsed_url._replace(fragment='')) if fragment else url

            async with session.get(fetch_url, allow_redirects=True) as response:
                status = response.status
                content_type = response.headers.get('Content-Type', '')
                final_url = str(response.url)

                capture = PageCapture(
                    url=url,
                    final_url=final_url,
                    status_code=status,
                    content_type=content_type,
                    domain=urlparse(url).netloc,
                    anchor_fragment=fragment,
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

                # Parse HTML and populate sections + derived text metadata.
                # BeautifulSoup + DOM walk is pure CPU work — run in a worker
                # thread so concurrent page parses don't serialise on the
                # asyncio event loop.
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None, self._populate_from_html, capture, html, fragment
                )

                # Last resort: the page itself is unreadable as HTML, but many
                # doc platforms publish a text/markdown rendering of the same
                # page (rel="alternate", or the llms.txt `<page>.md` convention).
                # Fetching that recovers content no amount of HTML parsing can.
                if capture.quality_warning:
                    await self._try_markdown_alternate(session, capture, html)

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

    async def _try_markdown_alternate(
        self, session: aiohttp.ClientSession, capture: PageCapture, html: str
    ) -> None:
        """Fetch a markdown rendering of an unreadable page and adopt it if it
        beats what HTML parsing managed. Best-effort and silent on failure —
        the capture is returned unchanged if anything goes wrong."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            candidates = self._markdown_alternate_urls(soup, capture.final_url or capture.url)
        except Exception:
            return

        current_len = self._sections_text_len(capture.sections or [])

        for alt_url in candidates[: self.MAX_MARKDOWN_ALTERNATES]:
            try:
                async with session.get(alt_url, allow_redirects=True) as resp:
                    if resp.status != 200:
                        continue
                    ctype = (resp.headers.get('Content-Type') or '').lower()
                    if not any(t in ctype for t in ('text/markdown', 'text/plain', 'text/x-markdown')):
                        continue
                    raw = await resp.read()
                    if len(raw) > self.max_html_bytes:
                        raw = raw[: self.max_html_bytes]
                    md = raw.decode(resp.charset or 'utf-8', errors='replace')

                loop = asyncio.get_running_loop()
                sections = await loop.run_in_executor(None, self._sections_from_markdown, md)
                new_len = self._sections_text_len(sections)
                if new_len > current_len:
                    capture.sections = sections
                    capture.word_count = len(
                        ' '.join(s.text for s in sections).split()
                    )
                    capture.quality_warning = None
                    logger.info(
                        f"📝 MARKDOWN ALTERNATE: recovered {new_len} chars for "
                        f"{capture.url[:80]} via {alt_url[-60:]} (HTML gave {current_len})"
                    )
                    return
            except Exception as exc:
                logger.debug(f"markdown alternate {alt_url[:70]} unavailable: {exc}")
                continue

    # =========================================================================
    # Content Root Detection
    # =========================================================================

    def _find_content_root(self, soup: BeautifulSoup):
        """
        Return the most specific main-content container in the soup.

        Detection tiers (first match wins):
          Tier 1 — semantic/ARIA: <article>, <main>, role="main", id/class regexes
          Tier 2 — Schema.org:    itemprop="articleBody"
          Fallback — <body> or the full soup
        """
        # Tier 1: semantic tags + ARIA + id/class regexes
        candidate = (
            soup.find('article')
            or soup.find('main')
            or soup.find(attrs={'role': 'main'})
            or soup.find(id=self._CONTENT_ID_RE)
            or soup.find(class_=self._CONTENT_CLASS_RE)
        )
        if candidate:
            return candidate

        # Tier 2: Schema.org structured data (used by many CMS platforms)
        candidate = soup.find(attrs={'itemprop': 'articleBody'})
        if candidate:
            return candidate

        return soup.body or soup

    # =========================================================================
    # SPA / JavaScript Detection
    # =========================================================================

    def _detect_spa(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Return a descriptive warning string if the page appears to be a
        JavaScript SPA that rendered no meaningful content server-side.

        Heuristics (all must match):
          1. Body visible text < 300 chars
          2. >= 3 external <script src=...> tags (bundled JS app)
          3. A known SPA mount-point id is present
        """
        body = soup.body
        if not body:
            return None

        script_tags = soup.find_all('script', src=True)
        if len(script_tags) < 3:
            return None

        body_text = body.get_text(separator=' ', strip=True)
        if len(body_text) >= 300:
            return None  # Enough static content — not a blocking SPA

        # Check for known SPA mount points
        for spa_id in self.SPA_MOUNT_IDS:
            if soup.find(id=spa_id):
                return (
                    f"Page appears to be a JavaScript SPA (found #{spa_id} mount point "
                    f"with {len(script_tags)} script bundles but only {len(body_text)} chars "
                    f"of visible text). Static extraction returned no content. "
                    f"The page requires JavaScript execution to render its content."
                )

        # Generic fallback: many scripts + almost no text
        if len(body_text) < 100:
            return (
                f"Page appears to require JavaScript to render "
                f"({len(script_tags)} script bundles, {len(body_text)} chars visible text). "
                f"Static extraction returned no content."
            )

        return None

    # =========================================================================
    # Anchor Fragment Narrowing
    # =========================================================================

    def _find_fragment_root(
        self,
        soup: BeautifulSoup,
        content_root,
        fragment: str,
    ) -> Tuple[Optional[Any], Optional[int], Optional[Any]]:
        """
        Locate the element identified by #fragment and return a 3-tuple
        (start_node, stop_level, sibling_anchor_parent) that controls the
        single-pass traversal scope.

        Cases handled:
          1. Anchor IS a heading: <h2 id="...">Title</h2>
          2. Anchor inside a heading: <h2>Title <a id="...">¶</a></h2>  (Sphinx/Hugo)
          3. Non-empty container: <div id="..."><h2>...</h2><p>...</p></div>
          4. Empty anchor marker (Oxford/CMS): <a id="..."></a> before content block
          5. No heading in siblings — use first non-empty sibling as content_root
          6. Fallback to anchor's parent
          7. Fragment not found — full-page fallback

        Returns:
            (start_node, stop_level, sibling_anchor_parent)
            - stop_level=None + start_node set → replace content_root with start_node
            - stop_level set → traverse from start_node, stop at heading of that level
            - sibling_anchor_parent set → also stop at next empty <a id=...> at that parent
            - (None, None, None) → fragment not found, fall back to full page
        """
        # 1. Find by id= (most common)
        anchor = soup.find(id=fragment)
        if anchor is None:
            # Legacy: <a name="fragment"> — use a_tag itself (NOT a_tag.parent)
            a_tag = soup.find('a', attrs={'name': fragment})
            anchor = a_tag if a_tag else None
        if anchor is None:
            logger.debug(f"🔍 FRAGMENT: #{fragment} not found in page, using full page")
            return None, None, None

        # 2. Anchor IS a heading: <h2 id="...">Title</h2>
        if anchor.name in self.HEADING_TAGS:
            level = int(anchor.name[1])
            logger.debug(f"🔍 FRAGMENT: #{fragment} is heading h{level}")
            return anchor, level, None

        # 3. Anchor INSIDE a heading: <h2>Title <a id="...">¶</a></h2>  (Sphinx/Hugo)
        parent = anchor.parent
        if parent and parent.name in self.HEADING_TAGS:
            level = int(parent.name[1])
            logger.debug(f"🔍 FRAGMENT: #{fragment} is inside heading h{level}")
            return parent, level, None

        # 4. Non-empty container: <div id="..."><h2>...</h2><p>...</p></div>
        if anchor.get_text(strip=True):
            logger.debug(f"🔍 FRAGMENT: #{fragment} is non-empty <{anchor.name}>, using as content_root")
            return anchor, None, None

        # 5. Empty anchor marker (Oxford/CMS pattern):
        #    <a id="Section"></a> placed BEFORE the content block.
        #    Search following siblings for the first heading, stopping at the next marker.
        sibling_anchor_parent = anchor.parent
        for sibling in anchor.next_siblings:
            if not isinstance(sibling, Tag):
                continue
            # Stop searching at the next empty anchor marker (next section boundary)
            if (sibling.name == 'a'
                    and sibling.get('id')
                    and not sibling.get_text(strip=True)):
                break
            # Direct heading sibling
            if sibling.name in self.HEADING_TAGS:
                logger.debug(
                    f"🔍 FRAGMENT: #{fragment} is empty marker, "
                    f"found direct heading <{sibling.name}>"
                )
                return sibling, int(sibling.name[1]), sibling_anchor_parent
            # Heading nested inside a sibling container (e.g. <div class="faqmodule"><h2>)
            h = sibling.find(list(self.HEADING_TAGS))
            if h:
                logger.debug(
                    f"🔍 FRAGMENT: #{fragment} is empty marker, "
                    f"found nested heading <{h.name}> inside <{sibling.name}>"
                )
                return h, int(h.name[1]), sibling_anchor_parent

        # 6. No heading found in siblings — use first non-empty sibling as new content_root
        for sibling in anchor.next_siblings:
            if isinstance(sibling, Tag) and sibling.get_text(strip=True):
                logger.debug(f"🔍 FRAGMENT: #{fragment} no heading found, using first content sibling")
                return sibling, None, None

        # 7. Fallback: use anchor's parent if it has content
        if parent and parent.get_text(strip=True):
            logger.debug(f"🔍 FRAGMENT: #{fragment} fallback to parent <{parent.name}>")
            return parent, None, None

        logger.debug(f"🔍 FRAGMENT: #{fragment} no usable anchor found, using full page")
        return None, None, None

    # =========================================================================
    # Block Extraction Helper
    # =========================================================================

    def _extract_block(self, node: Tag, tag: str) -> Optional[PageSection]:
        """
        Extract a PageSection from a block-level container (ul, ol, table, pre).
        Returns None if the element has no meaningful content.
        """
        if tag in ('ul', 'ol'):
            items = [li.get_text(strip=True) for li in node.find_all('li')]
            items = [i for i in items if i]
            if not items:
                return None
            return PageSection(
                type='list',
                text='\n'.join(f"- {item}" for item in items),
                html_snippet=str(node)[:1000],
                metadata={'item_count': len(items)},
            )

        if tag == 'table':
            rows = []
            for tr in node.find_all('tr'):
                cells = [c.get_text(strip=True) for c in tr.find_all(['th', 'td'])]
                if cells:
                    rows.append(cells)
            if not rows:
                return None
            return PageSection(
                type='table',
                text='\n'.join(' | '.join(row) for row in rows),
                html_snippet=str(node)[:1000],
                metadata={'row_count': len(rows)},
            )

        if tag == 'pre':
            text = node.get_text('\n', strip=True)
            if not text:
                return None
            return PageSection(
                type='code',
                text=text,
                html_snippet=str(node)[:1000],
            )

        if tag == 'dl':
            # Definition lists carry glossary/field documentation on many doc
            # sites; pair each term with its definition.
            pairs: List[str] = []
            term: Optional[str] = None
            for child in node.find_all(['dt', 'dd']):
                text = child.get_text(' ', strip=True)
                if not text:
                    continue
                if child.name == 'dt':
                    if term:
                        pairs.append(term)
                    term = text
                else:
                    pairs.append(f"{term}: {text}" if term else text)
                    term = None
            if term:
                pairs.append(term)
            if not pairs:
                return None
            return PageSection(
                type='list',
                text='\n'.join(f"- {p}" for p in pairs),
                html_snippet=str(node)[:1000],
                metadata={'item_count': len(pairs)},
            )

        return None

    # =========================================================================
    # Single-Pass Document-Order Traversal
    # =========================================================================

    def _single_pass_traverse(
        self,
        content_root,
        start_node: Optional[Tag] = None,
        stop_at_heading_level: Optional[int] = None,
        stop_at_sibling_parent: Optional[Any] = None,
    ) -> List[PageSection]:
        """
        Walk content_root's descendants in document order, extracting PageSections
        without duplicating nested content.

        Args:
            content_root: BeautifulSoup element to traverse
            start_node: If set, skip all nodes before this one (anchor fragment support)
            stop_at_heading_level: If set, stop when a heading at this level or
                higher is encountered (used together with start_node for heading anchors)
            stop_at_sibling_parent: If set, stop when an empty <a id=...> whose
                .parent is this element is encountered — detects the next CMS-style
                section boundary (e.g. the next <a id="Codex"></a> marker)

        Returns:
            List of PageSection in document order — no type-grouping, no duplicates
        """
        sections: List[PageSection] = []
        # Track id() of already-captured Tag objects to avoid re-processing nested elements
        processed_ids: set = set()

        # Fragment activation: skip nodes until start_node is reached
        active = start_node is None

        for node in content_root.descendants:
            if not isinstance(node, Tag):
                continue  # skip NavigableString, Comment, ProcessingInstruction

            tag = node.name
            if not tag:
                continue

            # --- Fragment: activate on reaching start_node ---
            if not active:
                if node is start_node:
                    active = True
                else:
                    continue

            # --- Fragment: stop at a heading at same or higher level ---
            if stop_at_heading_level is not None and tag in self.HEADING_TAGS:
                level = int(tag[1])
                if level <= stop_at_heading_level and node is not start_node:
                    break

            # --- Fragment: stop at the next CMS-style empty anchor marker ---
            # e.g. <a id="Codex"></a> placed at the same parent level as the
            # original <a id="AdvancedFeatures"></a> that started this traversal
            if (stop_at_sibling_parent is not None
                    and tag == 'a'
                    and node is not start_node
                    and node.get('id')
                    and not node.get_text(strip=True)
                    and node.parent is stop_at_sibling_parent):
                break

            # --- Skip already-processed subtrees ---
            if id(node) in processed_ids:
                continue

            # =================================================================
            # Headings — always extracted, at document position
            # =================================================================
            if tag in self.HEADING_TAGS or tag in self.DISCLOSURE_HEADING_TAGS:
                text = node.get_text(strip=True)
                if text and len(text) >= self.MIN_HEADING_LEN:
                    sections.append(PageSection(
                        type='heading',
                        level=(
                            self.DISCLOSURE_HEADING_LEVEL
                            if tag in self.DISCLOSURE_HEADING_TAGS
                            else int(tag[1])
                        ),
                        text=text,
                        html_snippet=str(node)[:1000],
                    ))
                # Mark heading + all its descendants as processed
                processed_ids.add(id(node))
                for desc in node.descendants:
                    if isinstance(desc, Tag):
                        processed_ids.add(id(desc))
                continue

            # =================================================================
            # Paragraphs — skip if inside a list item, table cell, or pre block
            # (those are captured as part of their parent block container)
            # =================================================================
            if tag == 'p':
                parent = node.parent
                skip = False
                while parent and parent is not content_root:
                    if parent.name in self.INLINE_SKIP_PARENTS:
                        skip = True
                        break
                    parent = parent.parent
                if skip:
                    continue
                text = node.get_text(strip=True)
                if text:
                    sections.append(PageSection(
                        type='paragraph',
                        text=text,
                        html_snippet=str(node)[:1000],
                    ))
                processed_ids.add(id(node))
                for desc in node.descendants:
                    if isinstance(desc, Tag):
                        processed_ids.add(id(desc))
                continue

            # =================================================================
            # Block containers (ul, ol, table, pre) — capture whole subtree
            # =================================================================
            if tag in self.BLOCK_EXTRACT_TAGS:
                section = self._extract_block(node, tag)
                if section:
                    sections.append(section)
                # Mark entire subtree as processed (prevents double-extraction
                # of nested <p>, <li>, <code>, etc.)
                processed_ids.add(id(node))
                for desc in node.descendants:
                    if isinstance(desc, Tag):
                        processed_ids.add(id(desc))
                continue

            # =================================================================
            # Inline <code> — skip if inside <pre> (already captured with pre block)
            # Also skip standalone inline code (sub-sentence fragments are too noisy)
            # =================================================================
            if tag == 'code':
                processed_ids.add(id(node))
                continue

        return sections

    # =========================================================================
    # HTML Parsing and Section Population
    # =========================================================================

    def _populate_from_html(
        self,
        capture: PageCapture,
        html: str,
        fragment: Optional[str] = None,
    ) -> None:
        """
        Populate a PageCapture instance from raw HTML using a single document-order
        traversal. Handles anchor fragments, SPA detection, and framework-specific
        content root detection.

        Args:
            capture: PageCapture instance to populate in-place
            html: Raw HTML string
            fragment: URL fragment (#anchor) to narrow extraction scope, or None
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # --- Title ---
            title = ''
            if soup.title:
                title = soup.title.get_text(strip=True)
            elif soup.find('h1'):
                title = soup.find('h1').get_text(strip=True)
            capture.title = (title[:500] if title else capture.domain)

            # --- Meta description ---
            meta_description = ''
            meta_tag = soup.find('meta', attrs={'name': 'description'})
            if meta_tag and meta_tag.get('content'):
                meta_description = meta_tag['content']
            capture.meta_description = meta_description[:500] if meta_description else None

            # --- Detect SPA before cleanup (needs script tags intact) ---
            spa_warning = self._detect_spa(soup)

            # --- Remove obviously non-content tags globally ---
            for tag_name in self.REMOVE_TAGS:
                for tag in soup.find_all(tag_name):
                    tag.decompose()

            # --- Find main content root ---
            content_root = self._find_content_root(soup)
            logger.debug(
                f"🔍 CONTENT EXTRACT: content_root=<{getattr(content_root, 'name', '?')}> "
                f"for {capture.url}"
            )

            # --- Pattern-based junk removal (ads, sidebars, etc.) ---
            # Runs after content_root isolation to protect content containers.
            _full_body_fallback = content_root is soup.body or content_root is soup
            _protected_ids: set = {id(content_root)}
            for _anc in content_root.parents:
                if _anc.name:
                    _protected_ids.add(id(_anc))

            for pat in self._REMOVE_PATTERNS_COMPILED:
                for element in list(soup.find_all(class_=pat)):
                    if _full_body_fallback:
                        element.decompose()
                    elif id(element) in _protected_ids:
                        pass
                    elif not element.find_parent(lambda t: t is content_root):  # noqa: B023
                        element.decompose()
                for element in list(soup.find_all(id=pat)):
                    if _full_body_fallback:
                        element.decompose()
                    elif id(element) in _protected_ids:
                        pass
                    elif not element.find_parent(lambda t: t is content_root):  # noqa: B023
                        element.decompose()

            # --- Anchor fragment narrowing ---
            traverse_start: Optional[Tag] = None
            traverse_stop_level: Optional[int] = None
            traverse_stop_sibling_parent = None
            # Kept so a failed narrowing can fall back to the whole page.
            full_page_root = content_root
            narrowed = False

            if fragment and fragment.strip().lower() in self.NON_CONTENT_ANCHORS:
                # e.g. #TopOfPage — narrowing here captures only the table of
                # contents, so treat the URL as if it had no fragment at all.
                logger.info(
                    f"🔎 FRAGMENT SKIP: '#{fragment}' is a whole-page anchor — "
                    f"extracting full page for {capture.url[:90]}"
                )
            elif fragment:
                start_node, stop_level, sibling_anchor_parent = self._find_fragment_root(
                    soup, content_root, fragment
                )
                if start_node is not None:
                    narrowed = True
                    if stop_level is None:
                        # Non-empty container or headingless sibling: replace content_root
                        content_root = start_node
                    else:
                        # Heading anchor or empty-marker anchor: traverse mode
                        traverse_start = start_node
                        traverse_stop_level = stop_level
                        traverse_stop_sibling_parent = sibling_anchor_parent  # may be None

            # --- Single-pass document-order traversal ---
            sections = self._single_pass_traverse(
                content_root,
                start_node=traverse_start,
                stop_at_heading_level=traverse_stop_level,
                stop_at_sibling_parent=traverse_stop_sibling_parent,
            )
            sections = self._drop_chrome_sections(sections)

            # --- Fragment fallback -------------------------------------------
            # A narrowed extraction that yields almost nothing means the anchor
            # pointed at a wrapper/TOC rather than a real subsection. Recover the
            # whole page instead of shipping a near-empty capture. Never fatal.
            # True while `sections` still represents a specific subsection of the
            # page. A deliberately-scoped section is allowed to be short, so the
            # whole-page recovery below must not second-guess it.
            fragment_scoped = narrowed

            if narrowed:
                narrowed_len = self._sections_text_len(sections)
                if narrowed_len < self.FRAGMENT_MIN_CHARS:
                    full_sections = self._drop_chrome_sections(
                        self._single_pass_traverse(full_page_root)
                    )
                    full_len = self._sections_text_len(full_sections)
                    if full_len > narrowed_len and (
                        narrowed_len < self.FRAGMENT_MIN_RATIO * full_len
                        or narrowed_len == 0
                    ):
                        logger.warning(
                            f"🔁 FRAGMENT FALLBACK: '#{fragment}' yielded only "
                            f"{narrowed_len} chars vs {full_len} for the full page — "
                            f"using full page for {capture.url[:90]}"
                        )
                        sections = full_sections
                        fragment_scoped = False

            # --- Format-adaptive recovery ------------------------------------
            # The DOM traversal above assumes server-rendered markup. When it
            # comes back thin the page is some other shape — JSON-LD, hydrated
            # SPA state, noscript-only, or markup matching none of the known
            # content-root patterns — so try each of those in turn and keep the
            # richest result. Purely additive: a healthy page never gets here,
            # and a page still scoped to a #fragment is left alone — a short
            # subsection is a correct result, not a failed extraction.
            if (
                not fragment_scoped
                and self._sections_text_len(sections) < self.RECOVERY_TRIGGER_CHARS
            ):
                recovered, strategy = self._recover_thin_content(html, sections, capture.url)
                if strategy:
                    logger.info(
                        f"♻️ EXTRACT RECOVERED: {capture.url[:85]} via '{strategy}' — "
                        f"{self._sections_text_len(sections)} → "
                        f"{self._sections_text_len(recovered)} chars"
                    )
                    sections = recovered

            capture.sections = sections

            # Surface SPA detection as an informational warning. This is
            # deliberately never promoted to extraction_error, even with zero
            # sections: a page we cannot read must not fail the surrounding
            # fetch/index/answer flow. It is logged loudly instead.
            if spa_warning:
                capture.spa_warning = spa_warning
                if not sections:
                    logger.warning(
                        f"🚧 SPA NO CONTENT: {capture.url[:90]} — {spa_warning} "
                        f"(continuing with empty content, not failing the batch)"
                    )
                else:
                    # Partial extraction: keep content but flag the page so
                    # callers (UI, indexer) know it may be incomplete.
                    logger.info(
                        f"⚠️ CONTENT EXTRACT: SPA detected but partial content "
                        f"extracted for {capture.url[:80]} — "
                        f"{len(sections)} sections kept"
                    )

            # --- Build flattened text for metrics and LLM context ---
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

            # Truncate for LLM usage but keep flag
            if len(flat_text) > self.max_content_length:
                capture.truncated = True
                flat_text = flat_text[: self.max_content_length] + "... [truncated]"

            capture.word_count = len(flat_text.split()) if flat_text else 0

            # --- Thin-extraction detection (non-fatal) ------------------------
            # Catches pages that parse cleanly but yield almost no text — the
            # failure mode the SPA heuristic misses when a nav sidebar pushes
            # body text past its 300-char threshold. Recorded as a warning so
            # the page still flows through, but never reported as a clean success.
            thin_reason = self._assess_thinness(flat_text, capture)
            if thin_reason:
                capture.quality_warning = thin_reason
                logger.warning(
                    f"🪧 THIN EXTRACT: {capture.url[:95]} — {thin_reason}"
                )

        except Exception as e:
            # Extraction is best-effort: log with a traceable marker and leave
            # whatever was gathered so far in place instead of failing the page.
            logger.warning(
                f"🧩 EXTRACT DEGRADED: {capture.url[:95]} — {type(e).__name__}: {e} "
                f"(keeping {len(capture.sections or [])} section(s), continuing)"
            )
            capture.quality_warning = f"Extraction incomplete: {type(e).__name__}: {e}"

    def _sections_text_len(self, sections: List[PageSection]) -> int:
        """Total characters of text across sections — used for fallback decisions."""
        return sum(len((s.text or '')) for s in sections)

    def _drop_chrome_sections(self, sections: List[PageSection]) -> List[PageSection]:
        """Drop framework chrome that sits *inside* the content container and so
        survives structural cleanup (GitBook's "Was this helpful?" widget,
        "Last updated N days ago", prev/next links). Text-level, exact-ish
        matches only — never touches substantive prose."""
        kept: List[PageSection] = []
        for s in sections:
            text = (s.text or '').strip()
            if text and any(rx.match(text) for rx in self._CHROME_TEXT_COMPILED):
                continue
            kept.append(s)
        return kept

    # =========================================================================
    # Format-adaptive extraction fallbacks
    #
    # Layered strategies tried in order, cheapest and most-structured first,
    # only when the primary DOM traversal came back thin. Each returns a
    # (sections, strategy_name) pair or (None, None); none of them raise.
    # =========================================================================

    def _recover_thin_content(
        self, html: str, current: List[PageSection], url: str
    ) -> Tuple[List[PageSection], Optional[str]]:
        """Try every fallback strategy and keep whichever yields the most text.

        Re-parses the ORIGINAL html: the main extraction pass decomposes
        <script>/<noscript>, which is exactly where JSON-LD, framework
        hydration state and noscript copies live. Only runs on pages that
        already came back thin, so the extra parse is rare.

        Returns the winning sections and the strategy name, or the original
        sections and None when nothing beat them. Individual strategy failures
        are logged and skipped — never propagated.
        """
        best_sections, best_name = current, None
        best_len = self._sections_text_len(current)

        try:
            soup = BeautifulSoup(html, 'html.parser')
        except Exception as exc:
            logger.warning(f"🧪 FALLBACK ERROR: could not re-parse {url[:70]}: {exc}")
            return best_sections, best_name

        # Script-reading strategies first, while the tags are still present.
        # Density scoring runs last, after script/style noise is removed so it
        # cannot mistake a JS bundle for prose.
        staged = [
            ('json-ld', self._extract_from_jsonld, False),
            ('embedded-state', self._extract_from_embedded_state, False),
            ('noscript', self._extract_from_noscript, False),
            ('text-density', self._extract_by_density, True),
        ]

        for name, strategy, needs_clean_soup in staged:
            if needs_clean_soup:
                try:
                    for tag_name in ('script', 'style', 'noscript', 'template'):
                        for tag in soup.find_all(tag_name):
                            tag.decompose()
                except Exception:
                    pass
            try:
                candidate = strategy(soup)
            except Exception as exc:  # a broken strategy must not sink the page
                logger.warning(
                    f"🧪 FALLBACK ERROR: strategy '{name}' failed on {url[:70]} — "
                    f"{type(exc).__name__}: {exc} (trying next strategy)"
                )
                continue
            if not candidate:
                continue
            candidate = self._drop_chrome_sections(candidate)
            cand_len = self._sections_text_len(candidate)
            if cand_len > best_len:
                best_sections, best_name, best_len = candidate, name, cand_len

        return best_sections, best_name

    def _sections_from_text_blocks(self, blocks: List[str]) -> List[PageSection]:
        """Wrap plain text blocks as paragraph sections, dropping tiny noise."""
        out: List[PageSection] = []
        for raw in blocks:
            text = re.sub(r'[ \t]+', ' ', (raw or '')).strip()
            if len(text) < 25:
                continue
            out.append(PageSection(type='paragraph', text=text[:20000]))
        return out

    # -- strategy: schema.org JSON-LD -----------------------------------------

    def _extract_from_jsonld(self, soup: BeautifulSoup) -> Optional[List[PageSection]]:
        """Pull article text from schema.org JSON-LD blocks — emitted by
        WordPress, Ghost, most news CMSes and many static-site generators.
        Complements the existing microdata (itemprop) support."""
        text_keys = ('articleBody', 'text', 'description', 'abstract')
        found: List[str] = []

        def walk(node):
            if isinstance(node, dict):
                for key in text_keys:
                    val = node.get(key)
                    if isinstance(val, str) and len(val.strip()) >= 100:
                        found.append(val.strip())
                headline = node.get('headline') or node.get('name')
                if isinstance(headline, str) and found and len(headline) < 300:
                    found.insert(max(len(found) - 1, 0), headline.strip())
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        for tag in soup.find_all('script', attrs={'type': re.compile(r'ld\+json', re.I)}):
            raw = tag.string or tag.get_text() or ''
            if not raw.strip():
                continue
            try:
                walk(json.loads(raw))
            except (ValueError, TypeError):
                continue  # malformed JSON-LD is common; ignore quietly

        if not found:
            return None
        # De-duplicate while preserving order (description often repeats the body)
        seen, blocks = set(), []
        for t in found:
            k = t[:200]
            if k not in seen:
                seen.add(k)
                blocks.append(t)
        # JSON-LD bodies may contain HTML — strip it.
        cleaned = [
            BeautifulSoup(b, 'html.parser').get_text(' ', strip=True) if '<' in b else b
            for b in blocks
        ]
        return self._sections_from_text_blocks(cleaned) or None

    # -- strategy: embedded SPA state ----------------------------------------

    def _extract_from_embedded_state(self, soup: BeautifulSoup) -> Optional[List[PageSection]]:
        """Recover content from the JSON state that JS frameworks inline into
        the HTML (Next.js __NEXT_DATA__, Nuxt, Gatsby, Remix, GitBook, etc.).

        This is what lets a client-side-rendered page be read without running a
        browser: the framework ships the same content as JSON so it can hydrate.
        """
        candidates: List[str] = []

        for tag in soup.find_all('script'):
            tag_id = (tag.get('id') or '').lower()
            tag_type = (tag.get('type') or '').lower()
            raw = tag.string or tag.get_text() or ''
            if not raw or len(raw) < 200:
                continue
            is_state = (
                tag_id in {'__next_data__', '__nuxt_data__', 'gatsby-page-data', '__remix_context'}
                or 'application/json' in tag_type
                or re.match(r'\s*(window\.)?(__NUXT__|__INITIAL_STATE__|__APOLLO_STATE__|__remixContext)\s*=', raw)
            )
            if not is_state:
                continue
            payload = raw.strip()
            # Strip a `window.X = ...;` wrapper down to the JSON object.
            m = re.match(r'\s*(?:window\.)?[A-Za-z_$][\w$]*\s*=\s*(.*?);?\s*$', payload, re.S)
            if m and m.group(1).lstrip().startswith(('{', '[')):
                payload = m.group(1)
            try:
                data = json.loads(payload)
            except (ValueError, TypeError):
                continue
            candidates.extend(self._harvest_prose_strings(data))

        if not candidates:
            return None
        return self._sections_from_text_blocks(candidates) or None

    def _harvest_prose_strings(self, node, depth: int = 0, budget: int = 4000) -> List[str]:
        """Collect human-prose-looking strings from an arbitrary JSON structure.

        Heuristic: long strings containing sentence punctuation and spaces, that
        do not look like URLs, ids, CSS, code or base64 blobs. Depth- and
        count-bounded so a huge state tree cannot stall the parse.
        """
        out: List[str] = []
        if depth > 12 or len(out) >= budget:
            return out
        if isinstance(node, str):
            s = node.strip()
            if len(s) < 80 or ' ' not in s:
                return out
            if re.match(r'^(https?://|data:|/|#|\.|[\w-]+\.(js|css|png|jpe?g|svg|woff))', s):
                return out
            if not re.search(r'[.!?:;]', s):
                return out
            # reject id/hash/base64-ish and markup-heavy blobs
            letters = sum(c.isalpha() or c.isspace() for c in s)
            if letters / max(len(s), 1) < 0.65:
                return out
            out.append(BeautifulSoup(s, 'html.parser').get_text(' ', strip=True) if '<' in s else s)
        elif isinstance(node, dict):
            for k, v in node.items():
                if str(k).lower() in {'css', 'style', 'script', 'svg', 'base64', 'buildid'}:
                    continue
                out.extend(self._harvest_prose_strings(v, depth + 1, budget))
                if len(out) >= budget:
                    break
        elif isinstance(node, list):
            for v in node:
                out.extend(self._harvest_prose_strings(v, depth + 1, budget))
                if len(out) >= budget:
                    break
        return out

    # -- strategy: <noscript> -------------------------------------------------

    def _extract_from_noscript(self, soup: BeautifulSoup) -> Optional[List[PageSection]]:
        """Some JS sites ship a static copy of the content inside <noscript>.
        (REMOVE_TAGS strips noscript from the main pass, so re-parse it here.)"""
        blocks: List[str] = []
        for tag in soup.find_all('noscript'):
            inner = tag.decode_contents() if hasattr(tag, 'decode_contents') else str(tag)
            text = BeautifulSoup(inner, 'html.parser').get_text('\n', strip=True)
            if len(text) >= 200:
                blocks.append(text)
        return self._sections_from_text_blocks(blocks) or None

    # -- strategy: text density (works on unknown markup) --------------------

    def _extract_by_density(self, soup: BeautifulSoup) -> Optional[List[PageSection]]:
        """Readability-style fallback for pages whose markup matches none of the
        known content-root patterns: score every block container by how much
        non-link prose it holds and traverse the winner.

        This is the generic safety net — it needs no knowledge of the site's
        framework, CSS naming, or structure.
        """
        best, best_score = None, 0.0
        for el in soup.find_all(['div', 'section', 'article', 'main', 'td']):
            text = el.get_text(' ', strip=True)
            n = len(text)
            if n < 200:
                continue
            link_chars = sum(len(a.get_text(' ', strip=True)) for a in el.find_all('a'))
            link_density = link_chars / max(n, 1)
            if link_density > 0.5:
                continue  # navigation / link farm, not prose
            para_count = len(el.find_all(['p', 'li', 'pre', 'h2', 'h3']))
            score = n * (1.0 - link_density) * (1.0 + min(para_count, 20) / 20.0)
            if score > best_score:
                best, best_score = el, score

        if best is None:
            return None
        sections = self._single_pass_traverse(best)
        if not sections:
            # Container held prose but no recognised block tags — take its text.
            return self._sections_from_text_blocks([best.get_text('\n', strip=True)]) or None
        return sections

    # =========================================================================
    # Machine-readable alternates (llms.txt / rel=alternate conventions)
    # =========================================================================

    def _markdown_alternate_urls(self, soup: BeautifulSoup, url: str) -> List[str]:
        """Candidate URLs serving a text/markdown rendering of this page.

        Two sources, both open conventions rather than site-specific hacks:
          1. <link rel="alternate" type="text/markdown"> declared by the page.
          2. The llms.txt convention of exposing `<page>.md` (GitBook, Mintlify
             and other doc platforms), which returns clean markdown and so
             sidesteps client-side rendering entirely.
        """
        out: List[str] = []
        try:
            for link in soup.find_all('link', rel=True, href=True):
                rels = link.get('rel') or []
                rels = [r.lower() for r in (rels if isinstance(rels, list) else [rels])]
                ltype = (link.get('type') or '').lower()
                if 'alternate' in rels and ('markdown' in ltype or 'text/plain' in ltype):
                    out.append(urljoin(url, link['href']))

            parsed = urlparse(url)
            path = parsed.path or '/'
            if not re.search(r'\.(md|txt|html?|json|xml|pdf)$', path, re.I) and path not in ('', '/'):
                out.append(urlunparse(parsed._replace(path=path.rstrip('/') + '.md', fragment='')))
        except Exception:
            return out
        # preserve order, drop dupes
        return list(dict.fromkeys(out))

    # Block-level HTML tags that routinely appear inside markdown (MDX, GitBook,
    # Docusaurus). Their contents must be parsed as HTML, not treated as prose.
    _MD_HTML_BLOCK_TAGS = (
        'table', 'details', 'div', 'section', 'figure', 'blockquote',
        'ul', 'ol', 'dl', 'aside', 'article', 'picture', 'video',
    )

    def _clean_md_inline(self, text: str) -> str:
        """Normalise a markdown text run: drop directives/entities, unwrap links,
        strip emphasis markers, and remove any inline HTML tags via a real parser
        (never by deleting '<'/'>' characters, which mangles embedded markup)."""
        text = re.sub(r'\{%[^%]*%\}', ' ', text)          # GitBook/Liquid directives
        text = re.sub(r'<!--.*?-->', ' ', text, flags=re.S)
        text = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', text)  # images
        text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)  # links → label
        text = re.sub(r'<(https?://[^>]+)>', r'\1', text)     # autolinks
        if '<' in text and '>' in text:
            text = BeautifulSoup(text, 'html.parser').get_text(' ', strip=True)
        text = re.sub(r'&#x[0-9A-Fa-f]+;|&[a-z]{2,8};', ' ', text)
        text = re.sub(r'(\*\*|__|~~|`+)', '', text)
        text = re.sub(r'^\s*>+\s?', '', text)             # blockquote markers
        return re.sub(r'\s{2,}', ' ', text).strip()

    def _sections_from_html_fragment(self, fragment: str) -> List[PageSection]:
        """Parse an HTML block embedded in markdown into sections, preserving
        tables and <details>/<summary> disclosure structure."""
        out: List[PageSection] = []
        try:
            frag = BeautifulSoup(fragment, 'html.parser')
        except Exception:
            return out

        for det in frag.find_all('details'):
            summary = det.find('summary')
            if summary:
                label = summary.get_text(' ', strip=True)
                if len(label) >= self.MIN_HEADING_LEN:
                    # The disclosure label is the term being defined — keep it as
                    # a heading so it stays searchable and scannable.
                    out.append(PageSection(type='heading', level=4, text=label[:500]))
                summary.decompose()
            body = det.get_text('\n', strip=True)
            if body:
                out.extend(self._sections_from_text_blocks([body]))
            det.decompose()

        for tbl in frag.find_all('table'):
            rows = []
            for tr in tbl.find_all('tr'):
                cells = [c.get_text(' ', strip=True) for c in tr.find_all(['th', 'td'])]
                if any(cells):
                    rows.append(' | '.join(cells))
            if rows:
                out.append(PageSection(type='table', text='\n'.join(rows)[:20000]))
            tbl.decompose()

        remainder = frag.get_text('\n', strip=True)
        if remainder:
            out.extend(self._sections_from_text_blocks([remainder]))
        return out

    def _sections_from_markdown(self, md: str) -> List[PageSection]:
        """Structural parse of markdown into PageSections (headings, lists,
        code, tables, paragraphs), including raw HTML blocks embedded in the
        markdown. Deliberately dependency-free — it only needs to preserve
        structure well enough for LLM context and citation."""
        sections: List[PageSection] = []
        lines = (md or '').replace('\r\n', '\n').split('\n')
        buf: List[str] = []
        code_buf: List[str] = []
        html_buf: List[str] = []
        in_code = False
        html_tag: Optional[str] = None
        html_depth = 0

        def flush_para():
            if not buf:
                return
            text = self._clean_md_inline(' '.join(buf))
            buf.clear()
            if len(text) >= 25:
                sections.append(PageSection(type='paragraph', text=text[:20000]))

        def flush_html():
            nonlocal html_tag, html_depth
            if html_buf:
                sections.extend(self._sections_from_html_fragment('\n'.join(html_buf)))
                html_buf.clear()
            html_tag, html_depth = None, 0

        for raw in lines:
            line = raw.rstrip()

            # --- inside an embedded HTML block ---
            if html_tag:
                html_buf.append(line)
                html_depth += len(re.findall(rf'<{html_tag}\b', line, re.I))
                html_depth -= len(re.findall(rf'</{html_tag}\s*>', line, re.I))
                if html_depth <= 0:
                    flush_html()
                continue

            # --- fenced code ---
            if re.match(r'^\s*(```|~~~)', line):
                if in_code:
                    if code_buf:
                        sections.append(PageSection(type='code', text='\n'.join(code_buf)[:20000]))
                    code_buf, in_code = [], False
                else:
                    flush_para()
                    in_code = True
                continue
            if in_code:
                code_buf.append(line)
                continue

            # --- start of an embedded HTML block ---
            html_open = re.match(
                rf'^\s*<({"|".join(self._MD_HTML_BLOCK_TAGS)})\b', line, re.I
            )
            if html_open:
                flush_para()
                html_tag = html_open.group(1).lower()
                html_buf.append(line)
                html_depth = (
                    len(re.findall(rf'<{html_tag}\b', line, re.I))
                    - len(re.findall(rf'</{html_tag}\s*>', line, re.I))
                )
                if html_depth <= 0:
                    flush_html()
                continue

            # --- markdown headings ---
            heading = re.match(r'^(#{1,6})\s+(.*)$', line)
            if heading:
                flush_para()
                htext = self._clean_md_inline(heading.group(2))
                if len(htext) >= self.MIN_HEADING_LEN:
                    sections.append(
                        PageSection(type='heading', level=len(heading.group(1)), text=htext[:500])
                    )
                continue

            # --- list items / table rows accumulate into the current block ---
            if re.match(r'^\s*([-*+]|\d+\.)\s+', line):
                buf.append(re.sub(r'^\s*([-*+]|\d+\.)\s+', '- ', line))
                continue
            if line.strip().startswith('|') and line.count('|') >= 2:
                buf.append(re.sub(r'\s*\|\s*', ' | ', line).strip())
                continue

            if not line.strip():
                flush_para()
                continue

            buf.append(line.strip())

        if in_code and code_buf:
            sections.append(PageSection(type='code', text='\n'.join(code_buf)[:20000]))
        flush_html()
        flush_para()
        return self._drop_chrome_sections(sections)

    def _assess_thinness(self, flat_text: str, capture: PageCapture) -> Optional[str]:
        """Return a human-readable reason when a capture looks empty/near-empty,
        else None. Pure assessment — sets nothing, raises nothing."""
        n = len(flat_text)
        if n == 0:
            return (
                f"no text extracted from {capture.raw_html_size} bytes of HTML "
                f"(page content is likely rendered client-side)"
            )
        if n < self.THIN_TEXT_CHARS:
            return (
                f"only {n} chars of text extracted from "
                f"{capture.raw_html_size} bytes of HTML"
            )
        if (
            capture.raw_html_size >= self.THIN_RATIO_MIN_HTML_BYTES
            and n < capture.raw_html_size * self.THIN_TEXT_HTML_RATIO
        ):
            return (
                f"{n} chars of text from {capture.raw_html_size} bytes of HTML "
                f"(ratio {n / max(capture.raw_html_size, 1):.5f} below "
                f"{self.THIN_TEXT_HTML_RATIO}) — likely client-side rendered"
            )
        return None

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
        Normalize a URL for consistent cache key generation.
        Note: the #fragment (if any) is intentionally dropped here — the server
        serves the same document regardless of the fragment, and all project-scoped
        cache keys should share one entry per page URL.

        Args:
            url: URL to normalize

        Returns:
            Normalized URL string (fragment stripped)
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

        # Reconstruct URL (fragment intentionally omitted)
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        if parsed.query:
            normalized += f"?{parsed.query}"

        return normalized
