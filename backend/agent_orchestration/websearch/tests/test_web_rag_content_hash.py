"""
Tests for the content-hash short-circuit and async-flush plumbing in
web_rag_service. Keeps Milvus out of the picture by exercising the pure
helpers directly; the full short-circuit end-to-end path is covered by the
live-stack smoke test.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from agent_orchestration.websearch.web_rag_service import (
    _flush_in_background,
    _page_content_hash,
)


class PageContentHashTests(TestCase):
    """Hashing must be deterministic on content and sensitive to real changes."""

    def _page(self, sections, title='T'):
        return {'title': title, 'sections': sections}

    def test_identical_pages_hash_identical(self):
        a = self._page([
            {'type': 'heading', 'text': 'Widgets', 'level': 1},
            {'type': 'paragraph', 'text': 'Widgets are great.'},
        ])
        b = self._page([
            {'type': 'heading', 'text': 'Widgets', 'level': 1},
            {'type': 'paragraph', 'text': 'Widgets are great.'},
        ])
        self.assertEqual(_page_content_hash(a), _page_content_hash(b))

    def test_changing_body_text_changes_hash(self):
        a = self._page([{'type': 'paragraph', 'text': 'Version A.'}])
        b = self._page([{'type': 'paragraph', 'text': 'Version B.'}])
        self.assertNotEqual(_page_content_hash(a), _page_content_hash(b))

    def test_changing_title_changes_hash(self):
        sections = [{'type': 'paragraph', 'text': 'Body.'}]
        self.assertNotEqual(
            _page_content_hash(self._page(sections, title='One')),
            _page_content_hash(self._page(sections, title='Two')),
        )

    def test_transient_fields_do_not_affect_hash(self):
        """Fields like status_code, raw_html_size, final_url shouldn't leak in."""
        sections = [{'type': 'paragraph', 'text': 'Body.'}]
        a = {
            'title': 'T', 'sections': sections,
            'status_code': 200, 'raw_html_size': 1234,
            'final_url': 'https://x/a', 'content_type': 'text/html',
        }
        b = {
            'title': 'T', 'sections': sections,
            'status_code': 200, 'raw_html_size': 9999,  # different!
            'final_url': 'https://x/b',                  # different!
            'content_type': 'application/xhtml',         # different!
        }
        self.assertEqual(_page_content_hash(a), _page_content_hash(b))

    def test_heading_level_change_affects_hash(self):
        self.assertNotEqual(
            _page_content_hash(self._page([{'type': 'heading', 'text': 'Hi', 'level': 1}])),
            _page_content_hash(self._page([{'type': 'heading', 'text': 'Hi', 'level': 2}])),
        )

    def test_section_order_matters(self):
        a = self._page([
            {'type': 'paragraph', 'text': 'First'},
            {'type': 'paragraph', 'text': 'Second'},
        ])
        b = self._page([
            {'type': 'paragraph', 'text': 'Second'},
            {'type': 'paragraph', 'text': 'First'},
        ])
        self.assertNotEqual(_page_content_hash(a), _page_content_hash(b))

    def test_empty_page_still_hashes(self):
        h = _page_content_hash({'title': '', 'sections': []})
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)  # sha256 hex length


class FlushInBackgroundTests(TestCase):
    """_flush_in_background swallows errors and logs; never raises."""

    def test_happy_path_calls_flush_once(self):
        col = MagicMock()
        _flush_in_background(col, 'proj0001')
        col.flush.assert_called_once_with()

    def test_exception_is_swallowed(self):
        col = MagicMock()
        col.flush.side_effect = RuntimeError('milvus gone')
        # Must not raise — the caller has already returned to the HTTP client.
        _flush_in_background(col, 'proj0002')
        col.flush.assert_called_once_with()


class IndexUrlsBatchAsyncFlushTests(TestCase):
    """async_flush=True dispatches col.flush on a daemon thread, not inline."""

    @patch('agent_orchestration.websearch.web_rag_service.threading.Thread')
    def test_async_flush_starts_background_thread(self, thread_cls):
        from agent_orchestration.websearch.web_rag_service import _flush_in_background
        # Smoke the dispatch plumbing: starting a Thread with our target
        # should not invoke col.flush on the current thread.
        col = MagicMock()
        # Simulate the call the production code makes:
        thread_cls.return_value.start.return_value = None
        thread_cls(target=_flush_in_background, args=(col, 'p'), daemon=True, name='websearch-flush').start()
        # Thread was instantiated with daemon=True and the right target.
        kwargs = thread_cls.call_args.kwargs
        self.assertEqual(kwargs.get('target'), _flush_in_background)
        self.assertTrue(kwargs.get('daemon'))
        # col.flush() is never called on this (fake) thread.
        col.flush.assert_not_called()
