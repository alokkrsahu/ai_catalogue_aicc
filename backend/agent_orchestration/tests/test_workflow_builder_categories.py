"""
Regression tests for WorkflowBuilder classifier-category handling.

Covers the doom-loop bug where `update_node_property` replaced the
categories list without preserving UUIDs, silently orphaning every
outgoing classifier edge (source_handle pointing to dead category ids)
and causing `_check_router_wiring` to report false-positive
"missing category" issues on every verifier/self-critique pass.
"""
from django.test import SimpleTestCase

from agent_orchestration.workflow_generator import (
    WorkflowBuilder,
    _check_router_wiring,
)


def _build_classifier_graph() -> WorkflowBuilder:
    """Minimal graph: Start → Classifier(2 cats) → A/B → End."""
    b = WorkflowBuilder(available_documents=[], available_providers=["openai"])
    b.execute_tool_call("add_start_node", {"prompt": "go"})
    b.execute_tool_call("add_end_node", {})
    b.execute_tool_call("add_classifier_agent", {
        "name": "Router",
        "categories": [
            {"name": "Alpha", "description": "alpha route"},
            {"name": "Beta", "description": "beta route"},
        ],
    })
    b.execute_tool_call("add_assistant_agent", {
        "name": "Alpha Handler", "system_message": "handles alpha",
    })
    b.execute_tool_call("add_assistant_agent", {
        "name": "Beta Handler", "system_message": "handles beta",
    })
    b.execute_tool_call("connect_nodes", {
        "source_name": "Start 1", "target_name": "Router",
    })
    b.execute_tool_call("connect_nodes", {
        "source_name": "Router", "target_name": "Alpha Handler",
        "source_category": "Alpha",
    })
    b.execute_tool_call("connect_nodes", {
        "source_name": "Router", "target_name": "Beta Handler",
        "source_category": "Beta",
    })
    b.execute_tool_call("connect_nodes", {
        "source_name": "Alpha Handler", "target_name": "End 1",
    })
    b.execute_tool_call("connect_nodes", {
        "source_name": "Beta Handler", "target_name": "End 1",
    })
    return b


class UpdateNodePropertyCategoryPreservationTests(SimpleTestCase):

    def test_baseline_router_wiring_clean(self):
        """Baseline: freshly-built graph has no router wiring issues."""
        b = _build_classifier_graph()
        issues = _check_router_wiring(b)
        self.assertEqual(issues, [], f"Unexpected baseline issues: {issues}")

    def test_update_categories_preserves_ids_by_name(self):
        """
        Primary fix: LLM calls update_node_property with categories lacking
        ids — builder must match incoming entries to existing ones by name
        and keep the original id so every source_handle on existing edges
        stays valid.
        """
        b = _build_classifier_graph()
        classifier = next(n for n in b.nodes if n["type"] == "ClassifierAgent")
        old_ids = {c["name"]: c["id"] for c in classifier["data"]["categories"]}

        # LLM-style update: same category names, no ids, updated descriptions.
        result = b.execute_tool_call("update_node_property", {
            "node_name": "Router",
            "categories": [
                {"name": "Alpha", "description": "alpha route (updated)"},
                {"name": "Beta", "description": "beta route (updated)"},
            ],
        })
        self.assertNotIn("Error", result)

        classifier = next(n for n in b.nodes if n["type"] == "ClassifierAgent")
        new_ids = {c["name"]: c["id"] for c in classifier["data"]["categories"]}
        self.assertEqual(
            old_ids, new_ids,
            "Category UUIDs must be preserved when the LLM updates "
            "categories by name without providing ids.",
        )
        # Descriptions did get updated.
        for cat in classifier["data"]["categories"]:
            self.assertIn("(updated)", cat["description"])

        # And — the whole point — router wiring is still clean.
        issues = _check_router_wiring(b)
        self.assertEqual(
            issues, [],
            f"Router wiring should remain clean after category update; got: {issues}",
        )

    def test_update_categories_renames_category_cascade_deletes_orphan_edge(self):
        """
        Removing a category via update_node_property must cascade-delete any
        outgoing edge whose source_handle referenced it (matches the behavior
        of the surgical `remove_category` tool).
        """
        b = _build_classifier_graph()
        # Need three categories to be allowed to drop to 2.
        b.execute_tool_call("add_category", {
            "classifier_name": "Router", "name": "Gamma", "description": "gamma route",
        })
        b.execute_tool_call("connect_nodes", {
            "source_name": "Router", "target_name": "End 1", "source_category": "Gamma",
        })
        gamma_edges_before = [
            e for e in b.edges
            if e.get("source_handle") and any(
                c["name"] == "Gamma" and c["id"] == e["source_handle"]
                for n in b.nodes if n["type"] == "ClassifierAgent"
                for c in n["data"]["categories"]
            )
        ]
        self.assertEqual(len(gamma_edges_before), 1)

        # LLM drops Gamma via update_node_property.
        result = b.execute_tool_call("update_node_property", {
            "node_name": "Router",
            "categories": [
                {"name": "Alpha", "description": "alpha"},
                {"name": "Beta", "description": "beta"},
            ],
        })
        self.assertNotIn("Error", result)
        self.assertIn("cascade-deleted", result)

        # No edge should still carry the Gamma UUID as source_handle.
        classifier = next(n for n in b.nodes if n["type"] == "ClassifierAgent")
        kept_ids = {c["id"] for c in classifier["data"]["categories"]}
        for e in b.edges:
            if e.get("source") == classifier["id"] and e.get("source_handle"):
                self.assertIn(e["source_handle"], kept_ids)

    def test_update_categories_below_minimum_rejects(self):
        """A category update that would leave < 2 categories is an error."""
        b = _build_classifier_graph()
        result = b.execute_tool_call("update_node_property", {
            "node_name": "Router",
            "categories": [{"name": "Alpha", "description": "alpha"}],
        })
        self.assertIn("Error", result)
        self.assertIn("at least 2 categories", result)
        # Original 2 categories survive.
        classifier = next(n for n in b.nodes if n["type"] == "ClassifierAgent")
        self.assertEqual(len(classifier["data"]["categories"]), 2)

    def test_update_categories_non_list_rejects(self):
        """Passing a non-list for categories is an error, not silent coerce."""
        b = _build_classifier_graph()
        result = b.execute_tool_call("update_node_property", {
            "node_name": "Router",
            "categories": {"name": "Alpha"},  # dict, not list
        })
        self.assertIn("Error", result)

    def test_update_categories_ignores_non_classifier(self):
        """Non-classifier agents shouldn't get the category cascade path."""
        b = _build_classifier_graph()
        # Squirrel a `categories` key onto an AssistantAgent via
        # update_node_property — behaves as a plain merge (no cascade logic).
        result = b.execute_tool_call("update_node_property", {
            "node_name": "Alpha Handler",
            "system_message": "new mission",
        })
        self.assertNotIn("Error", result)


class ConnectNodesSourceHandleGuardTests(SimpleTestCase):

    def test_connect_nodes_refuses_when_category_has_no_id(self):
        """
        Secondary fix: connect_nodes must refuse to create a classifier edge
        with source_handle=None. That would make the edge invisible to the
        router-wiring check and cause a false-positive doom loop.
        """
        b = _build_classifier_graph()
        classifier = next(n for n in b.nodes if n["type"] == "ClassifierAgent")
        # Simulate corruption: strip the id from one category.
        classifier["data"]["categories"][0].pop("id")

        result = b.execute_tool_call("connect_nodes", {
            "source_name": "Router",
            "target_name": "End 1",
            "source_category": classifier["data"]["categories"][0]["name"],
        })
        self.assertIn("Error", result)
        self.assertIn("missing its stable id", result)

        # No edge with source_handle=None slipped through.
        for e in b.edges:
            if e.get("source") == classifier["id"]:
                self.assertTrue(
                    e.get("source_handle"),
                    "Classifier edges must never have empty source_handle",
                )
