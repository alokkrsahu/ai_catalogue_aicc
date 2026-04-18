"""
Tests for WebSearchCacheService — covers the critical "per-project isolation"
invariant and the key format used by other parts of the system.
"""
from django.core.cache import cache
from django.test import TestCase

from agent_orchestration.websearch.cache_service import WebSearchCacheService


class CacheServiceKeyFormatTests(TestCase):
    """Key format contract — other services (e.g. sync_websearch_index)
    construct index-flag keys manually; drift here would break them."""

    def setUp(self):
        self.svc = WebSearchCacheService()
        cache.clear()

    def test_url_cache_key_includes_normalized_project_id(self):
        key = self.svc._make_url_cache_key(
            'https://example.com/', 'abc-123-def'
        )
        # Hyphens in project_id must be normalised to underscores so the
        # pattern-match fallback in clear_all_websearch_cache can rely on it.
        self.assertTrue(key.startswith('websearch_url_abc_123_def_'))

    def test_embed_cache_key_format(self):
        key = self.svc._make_embed_cache_key('https://x.example/', 'p-1')
        self.assertTrue(key.startswith('websearch_emb_p_1_'))

    def test_search_cache_key_includes_normalized_project(self):
        key = self.svc._make_search_cache_key(
            'python web scraping', 'proj-xyz', domains=['example.com']
        )
        self.assertTrue(key.startswith('websearch_query_proj_xyz_'))

    def test_search_cache_key_stable_across_domain_order(self):
        k1 = self.svc._make_search_cache_key(
            'q', 'p', domains=['a.example', 'b.example']
        )
        k2 = self.svc._make_search_cache_key(
            'q', 'p', domains=['b.example', 'a.example']
        )
        self.assertEqual(k1, k2)

    def test_search_cache_key_case_insensitive_query(self):
        k1 = self.svc._make_search_cache_key('Python WEB scraping', 'p')
        k2 = self.svc._make_search_cache_key('  python web scraping  ', 'p')
        self.assertEqual(k1, k2)


class CacheServiceIsolationTests(TestCase):
    """No cache entry may leak from one project to another."""

    def setUp(self):
        self.svc = WebSearchCacheService()
        cache.clear()

    def test_url_cache_scoped_by_project(self):
        self.svc.cache_url('https://x.example/', {'title': 'A'}, 'project-a', ttl=60)

        # Project A sees the entry.
        self.assertEqual(self.svc.get_cached_url('https://x.example/', 'project-a'), {'title': 'A'})

        # Project B reading the same URL must see a miss.
        self.assertIsNone(self.svc.get_cached_url('https://x.example/', 'project-b'))

    def test_embedding_cache_scoped_by_project(self):
        chunks = [{'content': 'c1', 'embedding': [0.1, 0.2]}]
        self.svc.cache_embeddings('https://x.example/', 'project-a', chunks, ttl=60)

        self.assertEqual(
            self.svc.get_cached_embeddings('https://x.example/', 'project-a'),
            chunks,
        )
        self.assertIsNone(self.svc.get_cached_embeddings('https://x.example/', 'project-b'))

    def test_search_cache_scoped_by_project(self):
        results = [{'title': 'Result 1', 'url': 'https://x.example/'}]
        self.svc.cache_search('python', results, 'project-a', ttl=60)

        self.assertEqual(self.svc.get_cached_search('python', 'project-a'), results)
        self.assertIsNone(self.svc.get_cached_search('python', 'project-b'))

    def test_batch_cache_and_fetch_round_trip(self):
        batch = {
            'https://a.example/': {'title': 'A'},
            'https://b.example/': {'title': 'B'},
        }
        n = self.svc.cache_urls_batch(batch, 'proj', ttl=60)
        self.assertEqual(n, 2)

        got = self.svc.get_cached_urls_batch(
            ['https://a.example/', 'https://b.example/', 'https://missing.example/'],
            'proj',
        )
        self.assertEqual(got['https://a.example/'], {'title': 'A'})
        self.assertEqual(got['https://b.example/'], {'title': 'B'})
        self.assertIsNone(got['https://missing.example/'])

    def test_invalidate_embeddings_drops_only_target(self):
        self.svc.cache_embeddings('https://keep.example/', 'p', [{'x': 1}], ttl=60)
        self.svc.cache_embeddings('https://drop.example/', 'p', [{'x': 2}], ttl=60)

        self.svc.invalidate_embeddings('https://drop.example/', 'p')

        self.assertIsNotNone(self.svc.get_cached_embeddings('https://keep.example/', 'p'))
        self.assertIsNone(self.svc.get_cached_embeddings('https://drop.example/', 'p'))
