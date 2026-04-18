"""
Tests for websearch.url_validation.clean_url_list — covers the dedupe + cap
+ protocol-filter policy that both the sync-websearch-index and
summarize-urls endpoints rely on.
"""
from django.test import TestCase, override_settings

from agent_orchestration.websearch.url_validation import clean_url_list, get_max_urls_per_agent


class CleanUrlListTests(TestCase):
    def test_empty_input_returns_empty(self):
        urls, invalid, over = clean_url_list([])
        self.assertEqual(urls, [])
        self.assertEqual(invalid, 0)
        self.assertEqual(over, 0)

    def test_trims_whitespace_and_drops_empties(self):
        urls, invalid, over = clean_url_list([
            '  https://a.example  ',
            '',
            '   ',
            'https://b.example',
        ])
        self.assertEqual(urls, ['https://a.example', 'https://b.example'])
        self.assertEqual(invalid, 0)
        self.assertEqual(over, 0)

    def test_rejects_non_http_protocols(self):
        urls, invalid, over = clean_url_list([
            'ftp://evil.example',
            'javascript:alert(1)',
            'https://ok.example',
        ])
        self.assertEqual(urls, ['https://ok.example'])
        self.assertEqual(invalid, 2)
        self.assertEqual(over, 0)

    def test_rejects_non_string_entries(self):
        urls, invalid, over = clean_url_list([
            None,
            42,
            {'nested': 'object'},
            'https://ok.example',
        ])
        self.assertEqual(urls, ['https://ok.example'])
        self.assertEqual(invalid, 3)

    def test_order_preserving_dedupe(self):
        urls, invalid, over = clean_url_list([
            'https://a.example',
            'https://b.example',
            'https://a.example',  # dup of #1
            'https://c.example',
            'https://b.example',  # dup of #2
        ])
        self.assertEqual(urls, ['https://a.example', 'https://b.example', 'https://c.example'])
        self.assertEqual(invalid, 0)
        # dedupe is silent — over-cap counter is only for count-trimming
        self.assertEqual(over, 0)

    @override_settings(WEBSEARCH_CONFIG={'MAX_URLS_PER_AGENT': 3})
    def test_cap_truncates_with_over_count(self):
        urls, invalid, over = clean_url_list([
            f'https://{letter}.example' for letter in 'abcdefg'
        ])
        self.assertEqual(len(urls), 3)
        self.assertEqual(urls, ['https://a.example', 'https://b.example', 'https://c.example'])
        self.assertEqual(over, 4)

    @override_settings(WEBSEARCH_CONFIG={'MAX_URLS_PER_AGENT': 0})
    def test_invalid_cap_clamps_to_one(self):
        # get_max_urls_per_agent() refuses values below 1.
        self.assertEqual(get_max_urls_per_agent(), 1)

    @override_settings(WEBSEARCH_CONFIG={'MAX_URLS_PER_AGENT': 'not-a-number'})
    def test_bad_config_falls_back_to_default(self):
        self.assertEqual(get_max_urls_per_agent(), 50)

    def test_http_and_https_both_accepted(self):
        urls, _, _ = clean_url_list([
            'http://insecure.example',
            'https://secure.example',
        ])
        self.assertEqual(urls, ['http://insecure.example', 'https://secure.example'])
