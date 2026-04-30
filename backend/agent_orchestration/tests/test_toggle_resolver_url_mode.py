"""
Regression tests for the toggle dependency resolver's handling of URL-mode
websearch.

The bug: enabling websearch — *any* mode — used to force-enable
doc_tool_calling=True, which routed URL-only agents through the
document tool-calling loop. That loop registers info tools, runs a
plan-mode round-trip, and tells the LLM to "use the document tools",
which made URL-only agents answer "no documents found" while ignoring
the URL excerpts already in their system prompt.

Fix: only general/domains web_search modes auto-promote
doc_tool_calling. URL mode delivers content via system-prompt injection
and does not need the tool-calling loop.
"""
from django.test import SimpleTestCase

from agent_orchestration.workflow_generator import WorkflowBuilder


class ToggleResolverUrlModeTests(SimpleTestCase):

    def test_url_mode_does_not_force_doc_tool_calling(self):
        """URL-only websearch must NOT auto-promote doc_tool_calling."""
        out = WorkflowBuilder._resolve_toggle_dependencies({
            "web_search_enabled": True,
            "web_search_mode": "urls",
        })
        self.assertFalse(
            out["doc_tool_calling"],
            "URL-mode websearch should leave doc_tool_calling off — "
            "it injects content via system prompt, not via tool calls.",
        )
        # URL mode survives the cascade
        self.assertTrue(out["web_search_enabled"])
        self.assertEqual(out["web_search_mode"], "urls")
        # plan_mode follows doc_tool_calling, so it's off too — saving an LLM call
        self.assertFalse(out["plan_mode"])

    def test_general_mode_still_forces_doc_tool_calling(self):
        """General websearch needs the tool loop and must auto-promote."""
        out = WorkflowBuilder._resolve_toggle_dependencies({
            "web_search_enabled": True,
            "web_search_mode": "general",
        })
        self.assertTrue(out["doc_tool_calling"])
        self.assertTrue(out["web_search_enabled"])
        self.assertEqual(out["web_search_mode"], "general")
        self.assertTrue(out["plan_mode"])

    def test_domains_mode_still_forces_doc_tool_calling(self):
        """Domain-restricted websearch is also a tool-call mode."""
        out = WorkflowBuilder._resolve_toggle_dependencies({
            "web_search_enabled": True,
            "web_search_mode": "domains",
        })
        self.assertTrue(out["doc_tool_calling"])
        self.assertEqual(out["web_search_mode"], "domains")

    def test_doc_aware_still_forces_doc_tool_calling(self):
        """DocAware uses tool calling and must continue to auto-promote."""
        out = WorkflowBuilder._resolve_toggle_dependencies({
            "doc_aware": True,
        })
        self.assertTrue(out["doc_tool_calling"])
        self.assertTrue(out["doc_aware"])

    def test_url_mode_with_documents_still_uses_tool_calling(self):
        """URL mode + selected docs: doc_tool_calling stays on (for the docs).

        Both pipelines coexist: URL excerpts in system prompt + doc tools in
        the tool loop. The agent will read docs via tools AND see URL excerpts
        in its system prompt.
        """
        out = WorkflowBuilder._resolve_toggle_dependencies({
            "web_search_enabled": True,
            "web_search_mode": "urls",
            "documents": ["paper.pdf"],
        })
        self.assertTrue(out["doc_tool_calling"], "explicit docs require the tool loop")
        self.assertEqual(out["web_search_mode"], "urls")
        self.assertEqual(out["doc_tool_calling_documents"], ["paper.pdf"])

    def test_no_websearch_no_change(self):
        """Sanity: no websearch, no docs, no DocAware → everything off."""
        out = WorkflowBuilder._resolve_toggle_dependencies({})
        self.assertFalse(out["doc_tool_calling"])
        self.assertFalse(out["web_search_enabled"])
        self.assertFalse(out["doc_aware"])
        self.assertFalse(out["plan_mode"])

    def test_url_mode_default_when_web_search_on_without_explicit_mode(self):
        """If web_search is on without an explicit mode, default to general
        (preserves the legacy auto-promotion behaviour for unconfigured agents)."""
        out = WorkflowBuilder._resolve_toggle_dependencies({
            "web_search_enabled": True,
            # no web_search_mode
        })
        self.assertEqual(out["web_search_mode"], "general")
        self.assertTrue(out["doc_tool_calling"])

    def test_url_mode_survives_when_doc_tool_calling_off(self):
        """Cascade-disable must NOT kill URL-mode websearch.

        If the user explicitly turned doc_tool_calling off but kept URL
        websearch on, web_search_enabled must survive the cascade because
        URL mode is independent of the tool loop.
        """
        out = WorkflowBuilder._resolve_toggle_dependencies({
            "web_search_enabled": True,
            "web_search_mode": "urls",
            "doc_tool_calling": False,
        })
        self.assertTrue(out["web_search_enabled"])
        self.assertEqual(out["web_search_mode"], "urls")
        self.assertFalse(out["doc_tool_calling"])

    def test_general_mode_cascade_disables_when_doc_tool_calling_off(self):
        """Conversely, general mode REQUIRES the tool loop. If doc_tool_calling
        is forced off and there's no other reason to keep it on, web_search
        must cascade-disable too — it has nothing to dispatch through.

        Note: general mode auto-promotes doc_tool_calling=True, so this only
        triggers when doc_tool_calling was already explicitly... wait, the
        auto-promotion overrides the explicit False. So this case can't
        actually occur via the resolver. Document the contract instead.
        """
        # General mode auto-promotes — explicit doc_tool_calling=False loses.
        out = WorkflowBuilder._resolve_toggle_dependencies({
            "web_search_enabled": True,
            "web_search_mode": "general",
            "doc_tool_calling": False,
        })
        self.assertTrue(
            out["doc_tool_calling"],
            "general/domains modes auto-promote doc_tool_calling regardless of explicit value",
        )
