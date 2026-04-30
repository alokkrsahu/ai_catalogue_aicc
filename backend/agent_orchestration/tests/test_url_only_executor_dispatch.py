"""
Integration test for the URL-only websearch dispatch fix.

Verifies that an URL-only agent (web_search_mode='urls', no docs, no DocAware)
routes through `_execute_doc_tool_calling` BYPASS path — falling through to a
direct LLM call. The previous bug routed through the tool-calling loop, where
the LLM was told "MUST use document tools" and reported "no documents found".

Tests the boolean predicate in isolation (matches exactly the predicate at
workflow_executor.py:743-767 sequential and :3870-3893 parallel).
"""
from django.test import SimpleTestCase

from agent_orchestration.workflow_generator import WorkflowBuilder


def _evaluate_dispatch(node_data, ws_enabled, ws_mode, da_enabled):
    """Mirror the executor's dispatch predicate so we can unit-test it.

    Both the sequential (:743) and parallel (:3870) executors compute the
    same boolean structure; this helper recreates it bit-for-bit.
    """
    ws_needs_tool_loop = ws_enabled and ws_mode != 'urls'
    doc_selected = node_data.get('doc_tool_calling_documents')
    no_project_docs = isinstance(doc_selected, list) and len(doc_selected) == 0
    url_only_websearch = (
        ws_enabled
        and not ws_needs_tool_loop
        and no_project_docs
        and not da_enabled
    )
    needs_tool_calling = (
        (node_data.get('doc_tool_calling') or ws_needs_tool_loop or da_enabled)
        and not url_only_websearch
    )
    return {
        'url_only_websearch': url_only_websearch,
        'needs_tool_calling': needs_tool_calling,
        'ws_needs_tool_loop': ws_needs_tool_loop,
    }


class UrlOnlyDispatchTests(SimpleTestCase):
    """Each scenario builds a node via the resolver and asserts the dispatch."""

    def _build_node(self, **args):
        """Resolver-driven node-data factory."""
        toggles = WorkflowBuilder._resolve_toggle_dependencies(args)
        return {**toggles, 'web_search_urls': args.get('web_search_urls', [])}

    def test_url_only_agent_skips_tool_loop(self):
        """The bug-repro case: URL-only agent must skip the tool loop."""
        nd = self._build_node(
            web_search_enabled=True,
            web_search_mode='urls',
            web_search_urls=['https://example.com/a'],
        )
        result = _evaluate_dispatch(
            nd, ws_enabled=True, ws_mode='urls', da_enabled=False,
        )
        self.assertTrue(result['url_only_websearch'])
        self.assertFalse(result['needs_tool_calling'])
        # And the resolver itself should not have promoted doc_tool_calling
        self.assertFalse(nd['doc_tool_calling'])
        self.assertFalse(nd['plan_mode'])

    def test_url_plus_documents_uses_tool_loop(self):
        """URL mode + selected docs: tool loop runs to read the docs."""
        nd = self._build_node(
            web_search_enabled=True,
            web_search_mode='urls',
            documents=['paper.pdf'],
        )
        result = _evaluate_dispatch(
            nd, ws_enabled=True, ws_mode='urls', da_enabled=False,
        )
        self.assertFalse(result['url_only_websearch'])
        self.assertTrue(result['needs_tool_calling'])
        self.assertTrue(nd['doc_tool_calling'])

    def test_general_websearch_uses_tool_loop(self):
        """General websearch must still go through the tool loop."""
        nd = self._build_node(
            web_search_enabled=True,
            web_search_mode='general',
        )
        result = _evaluate_dispatch(
            nd, ws_enabled=True, ws_mode='general', da_enabled=False,
        )
        self.assertFalse(result['url_only_websearch'])
        self.assertTrue(result['needs_tool_calling'])
        self.assertTrue(result['ws_needs_tool_loop'])

    def test_domains_websearch_uses_tool_loop(self):
        """Domain-restricted websearch is also a tool-call mode."""
        nd = self._build_node(
            web_search_enabled=True,
            web_search_mode='domains',
        )
        result = _evaluate_dispatch(
            nd, ws_enabled=True, ws_mode='domains', da_enabled=False,
        )
        self.assertFalse(result['url_only_websearch'])
        self.assertTrue(result['needs_tool_calling'])

    def test_docaware_only_uses_tool_loop(self):
        """DocAware (no websearch) still uses the tool loop."""
        nd = self._build_node(doc_aware=True)
        result = _evaluate_dispatch(
            nd, ws_enabled=False, ws_mode='', da_enabled=True,
        )
        self.assertFalse(result['url_only_websearch'])
        self.assertTrue(result['needs_tool_calling'])

    def test_url_mode_plus_docaware_uses_tool_loop(self):
        """URL + DocAware: tool loop runs for DocAware; URL excerpts ride along
        in the system prompt."""
        nd = self._build_node(
            web_search_enabled=True,
            web_search_mode='urls',
            doc_aware=True,
        )
        result = _evaluate_dispatch(
            nd, ws_enabled=True, ws_mode='urls', da_enabled=True,
        )
        self.assertFalse(result['url_only_websearch'])
        self.assertTrue(result['needs_tool_calling'])

    def test_no_websearch_no_docs_uses_direct_call(self):
        """Plain agent (nothing) → direct call (not tool loop, not URL bypass)."""
        nd = self._build_node()
        result = _evaluate_dispatch(
            nd, ws_enabled=False, ws_mode='', da_enabled=False,
        )
        self.assertFalse(result['url_only_websearch'])
        self.assertFalse(result['needs_tool_calling'])

    def test_url_only_with_explicit_doc_tool_calling_off_still_bypassed(self):
        """User explicitly turned off doc_tool_calling on a URL-only agent.

        The resolver leaves doc_tool_calling=False; the predicate still
        recognises this as URL-only and bypasses the loop.
        """
        nd = self._build_node(
            web_search_enabled=True,
            web_search_mode='urls',
            doc_tool_calling=False,
        )
        self.assertFalse(nd['doc_tool_calling'])
        self.assertTrue(nd['web_search_enabled'])  # URL mode survives
        result = _evaluate_dispatch(
            nd, ws_enabled=True, ws_mode='urls', da_enabled=False,
        )
        self.assertTrue(result['url_only_websearch'])
        self.assertFalse(result['needs_tool_calling'])
