"""
Regression tests: save-time graph normalization must round-trip user
content fields.

The bug: resolve_toggle_dependencies() hardcoded web_search_urls=[] and
web_search_domains=[] (and reset cache_ttl/search_method), and commit
3caceac started running it on EVERY workflow save via the DRF
serializers' validate_graph_json — so each canvas save wiped the
configured URL/domain lists, and the post-save orphan cleanup then
deleted the cached per-URL summaries.

Contract under test: toggle resolution may enforce cross-field
consistency (the toggle cascade), but must never discard content fields
it doesn't model. Lists survive even while web_search is disabled so a
disable/re-enable cycle round-trips losslessly.
"""
from django.test import SimpleTestCase

from agent_orchestration.graph_invariants import (
    resolve_toggle_dependencies,
    validate_and_normalize_graph_json,
)


def _agent_node(node_id="n1", **data):
    base = {"name": "Agent", "description": ""}
    base.update(data)
    return {"id": node_id, "type": "AssistantAgent", "position": {"x": 0, "y": 0}, "data": base}


class ResolverContentPassThroughTests(SimpleTestCase):
    URLS = ["https://example.com/a", "https://example.com/b"]

    def test_urls_survive_resolution(self):
        out = resolve_toggle_dependencies({
            "web_search_enabled": True,
            "web_search_mode": "urls",
            "web_search_urls": self.URLS,
        })
        self.assertEqual(out["web_search_urls"], self.URLS)

    def test_domains_survive_resolution(self):
        out = resolve_toggle_dependencies({
            "web_search_enabled": True,
            "web_search_mode": "domains",
            "web_search_domains": ["wikipedia.org", "docs.python.org"],
        })
        self.assertEqual(out["web_search_domains"], ["wikipedia.org", "docs.python.org"])

    def test_urls_survive_while_web_search_disabled(self):
        """Disable/re-enable must round-trip: lists are inert while off
        (the runtime gates on web_search_enabled first) but must not be
        destroyed — wiping them also cascade-deletes cached URL summaries."""
        out = resolve_toggle_dependencies({
            "web_search_enabled": False,
            "web_search_urls": self.URLS,
            "web_search_domains": ["wikipedia.org"],
        })
        self.assertFalse(out["web_search_enabled"])
        self.assertEqual(out["web_search_urls"], self.URLS)
        self.assertEqual(out["web_search_domains"], ["wikipedia.org"])

    def test_urls_are_sanitised_not_just_copied(self):
        out = resolve_toggle_dependencies({
            "web_search_enabled": True,
            "web_search_mode": "urls",
            "web_search_urls": [
                "https://example.com/a",
                "https://example.com/a",   # duplicate
                "ftp://bad.example.com",   # invalid scheme
                "   ",                     # blank
                42,                        # not a string
                "https://example.com/b",
            ],
        })
        self.assertEqual(out["web_search_urls"], self.URLS)

    def test_custom_cache_ttl_preserved(self):
        out = resolve_toggle_dependencies({
            "web_search_enabled": True,
            "web_search_mode": "urls",
            "web_search_cache_ttl": 3600,
        })
        self.assertEqual(out["web_search_cache_ttl"], 3600)

    def test_zero_cache_ttl_is_a_legitimate_choice(self):
        """0 = no caching (a frontend option) — must not be 'corrected'."""
        out = resolve_toggle_dependencies({
            "web_search_enabled": True,
            "web_search_mode": "general",
            "web_search_cache_ttl": 0,
        })
        self.assertEqual(out["web_search_cache_ttl"], 0)

    def test_cache_ttl_defaults_when_absent(self):
        on = resolve_toggle_dependencies({"web_search_enabled": True, "web_search_mode": "general"})
        off = resolve_toggle_dependencies({})
        self.assertEqual(on["web_search_cache_ttl"], 2592000)
        self.assertEqual(off["web_search_cache_ttl"], 0)

    def test_explicit_search_method_preserved_when_doc_aware(self):
        out = resolve_toggle_dependencies({
            "doc_aware": True,
            "search_method": "semantic_search",
            "vector_collections": ["my_collection"],
        })
        self.assertEqual(out["search_method"], "semantic_search")
        self.assertEqual(out["vector_collections"], ["my_collection"])

    def test_search_method_defaults_when_doc_aware_without_explicit_choice(self):
        out = resolve_toggle_dependencies({"doc_aware": True})
        self.assertEqual(out["search_method"], "hybrid_search")
        self.assertEqual(out["vector_collections"], ["project_documents"])


class SaveTimeNormalizationRoundTripTests(SimpleTestCase):
    """End-to-end through the serializer entry point: a saved graph must
    come back with its websearch content intact."""

    def test_url_mode_node_round_trips_through_save_normalization(self):
        urls = ["https://example.com/a", "https://example.com/b"]
        graph = {
            "nodes": [_agent_node(
                web_search_enabled=True,
                web_search_mode="urls",
                web_search_urls=urls,
                web_search_cache_ttl=3600,
                web_search_top_k=7,
            )],
            "edges": [],
        }
        new_graph, meta = validate_and_normalize_graph_json(graph)
        data = new_graph["nodes"][0]["data"]
        self.assertEqual(data["web_search_urls"], urls)
        self.assertEqual(data["web_search_cache_ttl"], 3600)
        self.assertEqual(data["web_search_top_k"], 7)
        self.assertEqual(data["web_search_mode"], "urls")
        self.assertTrue(data["web_search_enabled"])

    def test_already_normalized_node_is_untouched(self):
        """A node whose data already matches the resolved values must not
        be flagged as changed — normalization is idempotent."""
        graph = {
            "nodes": [_agent_node(
                web_search_enabled=True,
                web_search_mode="urls",
                web_search_urls=["https://example.com/a"],
            )],
            "edges": [],
        }
        once, meta1 = validate_and_normalize_graph_json(graph)
        twice, meta2 = validate_and_normalize_graph_json(once)
        self.assertEqual(meta2["normalized_nodes"], 0)
        self.assertEqual(
            once["nodes"][0]["data"]["web_search_urls"],
            twice["nodes"][0]["data"]["web_search_urls"],
        )

    def test_domains_mode_node_round_trips(self):
        graph = {
            "nodes": [_agent_node(
                web_search_enabled=True,
                web_search_mode="domains",
                web_search_domains=["wikipedia.org"],
            )],
            "edges": [],
        }
        new_graph, _ = validate_and_normalize_graph_json(graph)
        self.assertEqual(
            new_graph["nodes"][0]["data"]["web_search_domains"],
            ["wikipedia.org"],
        )
