"""
Tests for WebsiteFetcherService — covers the HTML extraction pipeline
(content-root detection, REMOVE_PATTERNS junk removal, fragment-anchor
scoping, SPA detection) without hitting the network.
"""
from django.test import TestCase

from agent_orchestration.websearch.fetcher_service import (
    PageCapture,
    WebsiteFetcherService,
)


def _capture(url: str = 'https://example.com/') -> PageCapture:
    return PageCapture(url=url, final_url=url, status_code=200, content_type='text/html')


class RemovePatternsPreCompiledTests(TestCase):
    """P4 — patterns are pre-compiled once at class load, not per call."""

    def test_patterns_match_count_matches_raw(self):
        self.assertEqual(
            len(WebsiteFetcherService._REMOVE_PATTERNS_COMPILED),
            len(WebsiteFetcherService.REMOVE_PATTERNS),
        )

    def test_patterns_are_compiled_regex_objects(self):
        import re
        for p in WebsiteFetcherService._REMOVE_PATTERNS_COMPILED:
            self.assertIsInstance(p, re.Pattern)


class ContentExtractionTests(TestCase):
    def setUp(self):
        self.fetcher = WebsiteFetcherService()

    def test_extracts_article_body_and_strips_nav(self):
        html = """
        <!doctype html><html><head><title>The Post</title></head><body>
            <nav class="site-nav"><a href="/">Home</a></nav>
            <article>
                <h1>Main Heading</h1>
                <p>Body paragraph with enough text to exceed the chunk minimum.</p>
            </article>
            <div class="sidebar">Widgets</div>
        </body></html>
        """
        cap = _capture()
        self.fetcher._populate_from_html(cap, html)

        self.assertEqual(cap.title, 'The Post')
        section_types = [s.type for s in cap.sections]
        self.assertIn('heading', section_types)
        self.assertIn('paragraph', section_types)
        flat = ' '.join(s.text for s in cap.sections)
        self.assertIn('Body paragraph', flat)
        # Nav and sidebar must not leak in.
        self.assertNotIn('Home', flat)
        self.assertNotIn('Widgets', flat)

    def test_fragment_anchor_narrows_to_heading_section(self):
        html = """
        <html><body>
            <main>
                <h2 id="first">First Section</h2>
                <p>First section body content that is long enough to appear.</p>
                <h2 id="second">Second Section</h2>
                <p>Second section body content that should not be included.</p>
            </main>
        </body></html>
        """
        cap = _capture('https://example.com/page#first')
        self.fetcher._populate_from_html(cap, html, fragment='first')

        flat = ' '.join(s.text for s in cap.sections)
        self.assertIn('First section body', flat)
        # The #first → h2 → stop-at-same-level rule must exclude the second h2.
        self.assertNotIn('Second section body', flat)

    def test_spa_warning_set_when_only_mount_point(self):
        """Empty body + SPA mount + many scripts → warnings only, never a
        blocking extraction_error. An unreadable page must not fail the
        surrounding fetch/index/answer flow; it is traceable via the logs and
        the spa_warning / quality_warning fields instead."""
        html = """
        <html><head><title>App</title></head><body>
            <div id="__next"></div>
            <script src="/app.js"></script>
            <script src="/vendor.js"></script>
            <script src="/runtime.js"></script>
        </body></html>
        """
        cap = _capture()
        self.fetcher._populate_from_html(cap, html)

        self.assertIsNotNone(cap.spa_warning)
        self.assertIn('SPA', cap.spa_warning)
        # Non-fatal: the flow continues even with zero extracted sections.
        self.assertIsNone(cap.extraction_error)
        self.assertIsNotNone(cap.quality_warning)

    def test_spa_warning_surfaced_on_partial_extract(self):
        """I — when SPA detected AND some sections extracted, spa_warning is
        set but extraction_error stays None so downstream still indexes the
        partial content."""
        html = """
        <html><head><title>App</title></head><body>
            <div id="__next">
                <article>
                    <h1>Pre-rendered Heading</h1>
                    <p>A few lines of server-rendered content that should survive.</p>
                </article>
            </div>
            <script src="/app.js"></script>
            <script src="/vendor.js"></script>
            <script src="/runtime.js"></script>
        </body></html>
        """
        cap = _capture()
        self.fetcher._populate_from_html(cap, html)

        # Partial content survived.
        self.assertTrue(cap.sections)
        # SPA warning IS set (body text < 300 chars post-cleanup + mount + 3 scripts)…
        self.assertIsNotNone(cap.spa_warning)
        self.assertIn('SPA', cap.spa_warning)
        # …but not promoted to extraction_error because we have sections.
        self.assertIsNone(cap.extraction_error)

    def test_no_spa_warning_on_content_heavy_page(self):
        """Guard: a page with plenty of static content must not be flagged
        as an SPA even if it has script tags + a mount-id-named element."""
        long_body = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. ' * 20
        html = f"""
        <html><head><title>Post</title></head><body>
            <article>
                <h1>Article Heading Line</h1>
                <p>{long_body}</p>
            </article>
            <script src="/app.js"></script>
            <script src="/vendor.js"></script>
            <script src="/runtime.js"></script>
        </body></html>
        """
        cap = _capture()
        self.fetcher._populate_from_html(cap, html)
        self.assertTrue(cap.sections)
        self.assertIsNone(cap.spa_warning)
        self.assertIsNone(cap.extraction_error)

    def test_url_normalizer_strips_fragment_and_trailing_slash(self):
        self.assertEqual(
            self.fetcher.normalize_url('https://Example.com/path/#intro'),
            'https://Example.com/path',
        )

    def test_is_valid_url_rejects_non_http(self):
        self.assertFalse(self.fetcher.is_valid_url('javascript:alert(1)'))
        self.assertFalse(self.fetcher.is_valid_url('ftp://x.example/'))
        self.assertTrue(self.fetcher.is_valid_url('https://x.example/'))


class ExtractionQualityTests(TestCase):
    """Covers the graceful-degradation guarantees: thin pages and failed
    anchor narrowing are recovered or flagged, never raised."""

    def setUp(self):
        self.fetcher = WebsiteFetcherService()

    # -- fragment handling ------------------------------------------------

    def _page_with_toc_anchor(self) -> str:
        body = ''.join(
            f'<h2>Section {i}</h2><p>{"Substantive prose for section %d. " % i * 12}</p>'
            for i in range(1, 6)
        )
        return f"""
        <html><head><title>Doc</title></head><body><main>
            <a id="TopOfPage"></a>
            <p>Table of contents:</p>
            <ul><li>Section 1</li><li>Section 2</li></ul>
            {body}
        </main></body></html>
        """

    def test_whole_page_anchor_is_ignored(self):
        """#TopOfPage must not narrow extraction to the table of contents."""
        cap = _capture('https://example.com/doc#TopOfPage')
        self.fetcher._populate_from_html(cap, self._page_with_toc_anchor(), 'TopOfPage')
        flat = ' '.join(s.text for s in cap.sections)
        self.assertIn('Substantive prose for section 1', flat)
        self.assertIn('Substantive prose for section 5', flat)

    def test_thin_fragment_falls_back_to_full_page(self):
        """An anchor resolving to a near-empty region recovers the full page
        rather than shipping a handful of characters."""
        html = """
        <html><head><title>Doc</title></head><body><main>
            <h2 id="stub">Stub</h2>
            <h2>Real Content</h2>
            <p>%s</p>
        </main></body></html>
        """ % ('Long body of genuine documentation text. ' * 30)
        cap = _capture('https://example.com/doc#stub')
        self.fetcher._populate_from_html(cap, html, 'stub')
        flat = ' '.join(s.text for s in cap.sections)
        self.assertIn('genuine documentation text', flat)

    def test_good_fragment_narrowing_is_preserved(self):
        """Fallback must not fire when narrowing yields substantial content."""
        html = """
        <html><head><title>Doc</title></head><body><main>
            <h2 id="first">First</h2>
            <p>%s</p>
            <h2>Second</h2>
            <p>%s</p>
        </main></body></html>
        """ % ('First section content. ' * 40, 'SECOND_MARKER body. ' * 40)
        cap = _capture('https://example.com/doc#first')
        self.fetcher._populate_from_html(cap, html, 'first')
        flat = ' '.join(s.text for s in cap.sections)
        self.assertIn('First section content', flat)
        self.assertNotIn('SECOND_MARKER', flat)

    # -- thin extraction --------------------------------------------------

    def test_thin_page_flagged_but_not_failed(self):
        """Large HTML yielding almost no text is flagged, never errored."""
        cap = _capture('https://example.com/js-page')
        cap.raw_html_size = 360_000
        html = '<html><head><title>App</title></head><body><main><p>Hi</p></main></body></html>'
        self.fetcher._populate_from_html(cap, html)
        self.assertIsNone(cap.extraction_error)
        self.assertIsNotNone(cap.quality_warning)

    def test_healthy_page_has_no_quality_warning(self):
        cap = _capture('https://example.com/good')
        cap.raw_html_size = 40_000
        html = (
            '<html><head><title>Good</title></head><body><main><h1>T</h1><p>'
            + ('Real content here. ' * 100)
            + '</p></main></body></html>'
        )
        self.fetcher._populate_from_html(cap, html)
        self.assertIsNone(cap.extraction_error)
        self.assertIsNone(cap.quality_warning)

    # -- chrome removal ---------------------------------------------------

    def test_framework_chrome_is_dropped(self):
        html = """
        <html><head><title>Doc</title></head><body><main>
            <h2>Heading</h2>
            <p>%s</p>
            <p>Was this helpful?</p>
            <p>Last updated18 days ago</p>
            <p>On this page</p>
        </main></body></html>
        """ % ('Genuine documentation body. ' * 30)
        cap = _capture()
        self.fetcher._populate_from_html(cap, html)
        texts = [s.text.strip() for s in cap.sections]
        self.assertIn('Genuine documentation body.', ' '.join(texts))
        for chrome in ('Was this helpful?', 'Last updated18 days ago', 'On this page'):
            self.assertNotIn(chrome, texts)

    def test_chrome_patterns_do_not_eat_real_prose(self):
        """Only near-exact chrome matches are dropped."""
        html = """
        <html><head><title>Doc</title></head><body><main>
            <p>Was this helpful information about updating your record accurate?</p>
            <p>%s</p>
        </main></body></html>
        """ % ('Body text. ' * 40)
        cap = _capture()
        self.fetcher._populate_from_html(cap, html)
        flat = ' '.join(s.text for s in cap.sections)
        self.assertIn('helpful information about updating', flat)


class FormatAdaptiveExtractionTests(TestCase):
    """The extractor must read content out of whatever shape a page takes:
    server-rendered HTML, JSON-LD, hydrated SPA state, noscript, unknown
    markup, embedded HTML in markdown, and HTML disclosure widgets."""

    def setUp(self):
        self.fetcher = WebsiteFetcherService()

    def _text(self, cap) -> str:
        return ' '.join(s.text for s in cap.sections)

    # -- structured data ---------------------------------------------------

    def test_recovers_content_from_json_ld(self):
        body = 'The quick brown fox jumped over the lazy dog repeatedly. ' * 12
        html = """
        <html><head><title>News</title>
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"NewsArticle",
         "headline":"A Headline Worth Keeping","articleBody":"%s"}
        </script>
        </head><body><div id="shell"></div></body></html>
        """ % body
        cap = _capture('https://example.com/news')
        self.fetcher._populate_from_html(cap, html)
        self.assertIn('quick brown fox', self._text(cap))
        self.assertIsNone(cap.extraction_error)

    def test_malformed_json_ld_does_not_break_extraction(self):
        html = """
        <html><head><title>T</title>
        <script type="application/ld+json">{ this is not json </script>
        </head><body><main><p>%s</p></main></body></html>
        """ % ('Readable body content. ' * 40)
        cap = _capture()
        self.fetcher._populate_from_html(cap, html)
        self.assertIn('Readable body content', self._text(cap))
        self.assertIsNone(cap.extraction_error)

    # -- hydrated SPA state ------------------------------------------------

    def test_recovers_content_from_next_data_state(self):
        prose = ('This paragraph lives only in the hydration payload, '
                 'exactly as a client-rendered framework would ship it. ') * 6
        html = """
        <html><head><title>App</title></head><body>
            <div id="__next"></div>
            <script id="__NEXT_DATA__" type="application/json">
            {"props":{"pageProps":{"doc":{"title":"Doc","content":"%s"}}}}
            </script>
            <script src="/a.js"></script><script src="/b.js"></script>
            <script src="/c.js"></script>
        </body></html>
        """ % prose
        cap = _capture('https://example.com/spa')
        self.fetcher._populate_from_html(cap, html)
        self.assertIn('hydration payload', self._text(cap))
        self.assertIsNone(cap.extraction_error)

    def test_state_harvest_rejects_urls_and_ids(self):
        """Only prose is harvested — asset paths and hashes must not leak in."""
        junk = {
            'a': 'https://cdn.example.com/static/chunk.a1b2c3d4e5f6a7b8.js',
            'b': 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2',
            'c': '/assets/img/hero-image-2048x1024.png',
        }
        harvested = self.fetcher._harvest_prose_strings(junk)
        self.assertEqual(harvested, [])

    # -- noscript ----------------------------------------------------------

    def test_recovers_content_from_noscript(self):
        html = """
        <html><head><title>App</title></head><body>
            <div id="root"></div>
            <noscript><article><p>%s</p></article></noscript>
            <script src="/a.js"></script><script src="/b.js"></script>
            <script src="/c.js"></script>
        </body></html>
        """ % ('Static fallback copy for crawlers. ' * 12)
        cap = _capture()
        self.fetcher._populate_from_html(cap, html)
        self.assertIn('Static fallback copy', self._text(cap))

    # -- unknown markup ----------------------------------------------------

    def test_density_fallback_handles_unknown_markup(self):
        """No <article>/<main>, no recognised class names, nav-heavy page."""
        nav = ''.join(f'<a href="/p{i}">Link number {i}</a>' for i in range(40))
        html = f"""
        <html><head><title>Odd</title></head><body>
            <span class="zzz-top">{nav}</span>
            <span class="qqq-9">
                <p>{'Genuine article prose that should win on density. ' * 14}</p>
                <p>{'A second substantive paragraph of real content. ' * 10}</p>
            </span>
        </body></html>
        """
        cap = _capture()
        self.fetcher._populate_from_html(cap, html)
        text = self._text(cap)
        self.assertIn('Genuine article prose', text)
        self.assertIn('second substantive paragraph', text)

    # -- HTML disclosure widgets ------------------------------------------

    def test_details_summary_labels_are_captured(self):
        """<summary> is the heading of a disclosure block — dropping it loses
        the very term being defined (regression: object-type vocabulary)."""
        html = """
        <html><head><title>Glossary</title></head><body><main>
            <h2>Types</h2>
            <details><summary>terminology artifact</summary>
                <p>%s</p></details>
            <details><summary>software application</summary>
                <p>%s</p></details>
        </main></body></html>
        """ % ('A set of defined terms and categories. ' * 6,
               'An application or tool ready to run. ' * 6)
        cap = _capture()
        self.fetcher._populate_from_html(cap, html)
        text = self._text(cap)
        self.assertIn('terminology artifact', text)
        self.assertIn('software application', text)

    def test_definition_lists_are_captured(self):
        html = """
        <html><head><title>Fields</title></head><body><main>
            <h2>Fields</h2>
            <dl>
              <dt>Object Types</dt><dd>At least one is mandatory.</dd>
              <dt>Taxonomic Range</dt><dd>Controlled vocabulary field.</dd>
            </dl>
            <p>%s</p>
        </main></body></html>
        """ % ('Surrounding prose. ' * 30)
        cap = _capture()
        self.fetcher._populate_from_html(cap, html)
        text = self._text(cap)
        self.assertIn('Object Types', text)
        self.assertIn('mandatory', text)
        self.assertIn('Taxonomic Range', text)

    # -- markdown parsing --------------------------------------------------

    def test_markdown_parsed_into_structured_sections(self):
        md = """# Title

Intro paragraph with a [link](https://example.com) and **bold** text.

## Section Two

- first item
- second item

```python
print('code')
```
"""
        secs = self.fetcher._sections_from_markdown(md)
        types = [s.type for s in secs]
        text = ' '.join(s.text for s in secs)
        self.assertIn('heading', types)
        self.assertIn('code', types)
        self.assertIn('Intro paragraph with a link', text)
        # emphasis markers and link syntax must not survive
        self.assertNotIn('**', text)
        self.assertNotIn('](', text)

    def test_markdown_with_embedded_html_is_parsed(self):
        """MDX/GitBook markdown routinely embeds raw HTML blocks; their text
        must be extracted rather than mangled into character soup."""
        md = """# Object Types

Intro line that is long enough to be kept as a paragraph section.

<details>

<summary>terminology artifact</summary>

A set of defined terms, for example a glossary or ontology of some kind.

</details>

<table><thead><tr><th>Resource</th><th>Question</th></tr></thead>
<tbody><tr><td>Database</td><td>What content is stored?</td></tr></tbody></table>
"""
        secs = self.fetcher._sections_from_markdown(md)
        text = ' '.join(s.text for s in secs)
        self.assertIn('terminology artifact', text)
        self.assertIn('set of defined terms', text)
        self.assertIn('Database', text)
        self.assertIn('What content is stored?', text)
        self.assertNotIn('<td>', text)
        self.assertIn('table', [s.type for s in secs])

    def test_markdown_directives_are_stripped(self):
        md = """# T

{% hint style="info" %}
It is mandatory to provide at least one object type for all record types.
{% endhint %}
"""
        secs = self.fetcher._sections_from_markdown(md)
        text = ' '.join(s.text for s in secs)
        self.assertIn('mandatory to provide at least one object type', text)
        self.assertNotIn('{%', text)

    # -- alternates --------------------------------------------------------

    def test_markdown_alternate_candidates(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(
            '<html><head><link rel="alternate" type="text/markdown" href="/page.md">'
            '</head><body></body></html>', 'html.parser')
        cands = self.fetcher._markdown_alternate_urls(soup, 'https://example.com/docs/page')
        self.assertIn('https://example.com/page.md', cands)
        # llms.txt convention sibling is also offered
        self.assertIn('https://example.com/docs/page.md', cands)

    def test_markdown_alternate_not_offered_for_file_urls(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup('<html><head></head><body></body></html>', 'html.parser')
        cands = self.fetcher._markdown_alternate_urls(soup, 'https://example.com/a/file.json')
        self.assertEqual(cands, [])

    # -- no regression on healthy pages ------------------------------------

    def test_healthy_page_skips_all_fallbacks(self):
        html = """
        <html><head><title>Good</title></head><body>
            <nav><a href="/">Home</a></nav>
            <article><h1>Heading</h1><p>%s</p></article>
        </body></html>
        """ % ('Plenty of genuine server-rendered content here. ' * 40)
        cap = _capture()
        cap.raw_html_size = 60_000
        self.fetcher._populate_from_html(cap, html)
        self.assertIsNone(cap.quality_warning)
        self.assertIsNone(cap.extraction_error)
        self.assertNotIn('Home', self._text(cap))
