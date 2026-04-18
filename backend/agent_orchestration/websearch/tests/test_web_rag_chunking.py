"""
Tests for WebRAGService chunking — pure logic, no Milvus required.
"""
from django.test import TestCase

from agent_orchestration.websearch.web_rag_service import (
    MAX_CHUNK_CHARS,
    MIN_CHUNK_CHARS,
    _chunk_page_capture,
    _split_text,
    _url_hash,
)


def _page(sections, title='Example Title'):
    return {'title': title, 'sections': sections}


class SplitTextTests(TestCase):
    def test_splits_at_sentence_boundary(self):
        text = 'Alpha. Beta? Gamma! Delta.'
        parts = _split_text(text, max_len=10)
        # Each part should end at a sentence boundary where possible.
        self.assertTrue(all(len(p) <= 10 for p in parts))

    def test_returns_single_part_when_short(self):
        parts = _split_text('Short.', max_len=50)
        self.assertEqual(parts, ['Short.'])


class ChunkPageCaptureTests(TestCase):
    def test_attaches_url_title_and_hash_to_every_chunk(self):
        page = _page([
            {'type': 'heading', 'text': 'Intro to Widgets Manufacturing Process'},
            {'type': 'paragraph', 'text': 'Widgets are small devices used for many purposes in daily life.'},
        ])
        chunks = _chunk_page_capture(page, 'https://example.com/widgets')
        self.assertTrue(chunks)
        expected_hash = _url_hash('https://example.com/widgets')
        for c in chunks:
            self.assertEqual(c['url'], 'https://example.com/widgets')
            self.assertEqual(c['url_hash'], expected_hash)
            self.assertEqual(c['title'], 'Example Title')
            self.assertIn('word_count', c)

    def test_heading_context_prepended_to_non_heading_sections(self):
        page = _page([
            {'type': 'heading', 'text': 'Section Title About Widget Internals'},
            {'type': 'paragraph', 'text': 'This paragraph discusses how widgets are assembled internally.'},
        ])
        chunks = _chunk_page_capture(page, 'https://example.com/')
        para_chunks = [c for c in chunks if c['section_type'] == 'paragraph']
        self.assertEqual(len(para_chunks), 1)
        self.assertIn('Section Title About Widget Internals', para_chunks[0]['content'])
        self.assertIn('This paragraph', para_chunks[0]['content'])

    def test_skips_too_short_sections(self):
        page = _page([
            {'type': 'paragraph', 'text': 'x' * (MIN_CHUNK_CHARS - 1)},
        ])
        chunks = _chunk_page_capture(page, 'https://example.com/')
        self.assertEqual(chunks, [])

    def test_long_section_split_into_multiple_chunks(self):
        long_text = '. '.join(
            f'Sentence number {i} with extra words to fill out the line' for i in range(100)
        )
        page = _page([
            {'type': 'paragraph', 'text': long_text},
        ])
        chunks = _chunk_page_capture(page, 'https://example.com/')
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c['content']), MAX_CHUNK_CHARS)

    def test_empty_page_produces_no_chunks(self):
        self.assertEqual(_chunk_page_capture({'sections': []}, 'https://example.com/'), [])
        self.assertEqual(_chunk_page_capture({}, 'https://example.com/'), [])
