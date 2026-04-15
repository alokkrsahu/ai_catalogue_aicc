"""
Smoke-test the ClassifierAgent plumbing end-to-end without hitting real LLMs:

* ``build_classifier_tools`` produces the expected tool schema / tool_map
* ``build_classifier_system_prompt`` includes all category names/descriptions
* ``execute_classifier`` picks the correct category on a stubbed happy path
* ``execute_classifier`` retries once and then raises on provider failure
* ``_prune_unselected_branches`` handles fan-out, joins, and nested classifiers
* ``_validate_classifier_nodes`` catches the documented error conditions

Run::

    python manage.py test_classifier
"""

import asyncio
import sys
from typing import Any, Dict, List

from django.core.management.base import BaseCommand

from agent_orchestration.classifier_executor import (
    CLASSIFIER_SKIPPED_SENTINEL,
    ClassifierSelectionError,
    build_classifier_system_prompt,
    build_classifier_tools,
    execute_classifier,
)
from agent_orchestration.workflow_executor import WorkflowExecutor


# -----------------------------------------------------------------------------
# Test doubles
# -----------------------------------------------------------------------------

class _StubLLMResponse:
    def __init__(self, tool_calls=None, error=None, text=""):
        self.tool_calls = tool_calls
        self.error = error
        self.text = text


class _ScriptedLLM:
    """LLM provider stub that returns queued responses in order."""

    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = []

    async def generate_response(self, messages=None, tools=None, tool_choice=None, **kwargs):
        self.calls.append({
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
        })
        if not self._scripted:
            return _StubLLMResponse(error="no more scripted responses")
        return self._scripted.pop(0)


def _ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def _fail(msg: str) -> None:
    print(f"  ❌ {msg}")
    raise SystemExit(1)


# -----------------------------------------------------------------------------
# Test cases
# -----------------------------------------------------------------------------

def test_tool_schema_and_prompt() -> None:
    print("\n▸ Tool schema + system prompt")
    cats = [
        {"id": "uuid-1", "name": "Technical Question", "description": "Code, bugs, APIs."},
        {"id": "uuid-2", "name": "Billing Question", "description": ""},
        {"id": "uuid-3", "name": "Billing Question", "description": "dup name forces suffix"},
    ]
    tools, tool_map = build_classifier_tools(cats)
    assert len(tools) == 3, f"expected 3 tools, got {len(tools)}"
    names = [t["function"]["name"] for t in tools]
    assert "classify_as_technical_question" in names, names
    # Duplicate name should be de-duped (suffix applied).
    assert len(set(names)) == 3, f"tool names not unique: {names}"
    _ok(f"tool names unique & sane: {names}")

    # tool_map keys match names; values match source categories.
    for tname, expected_cat in zip(names, cats):
        assert tool_map[tname]["id"] == expected_cat["id"], (tname, tool_map[tname])
    _ok("tool_map maps each tool name to its category")

    # Empty description falls back to a sensible default; non-empty preserved.
    assert "Code, bugs, APIs" in tools[0]["function"]["description"]
    assert "Billing Question" in tools[1]["function"]["description"]
    _ok("descriptions populated correctly")

    prompt = build_classifier_system_prompt(cats)
    for cat in cats:
        assert cat["name"] in prompt, cat
    assert "pick exactly ONE" in prompt or "pick exactly one" in prompt.lower()
    _ok("system prompt includes every category + strict-single-select instruction")


def test_execute_classifier_happy_path() -> None:
    print("\n▸ execute_classifier happy path (Claude-style tool_choice)")
    cats = [
        {"id": "uuid-a", "name": "Bug Report", "description": "Crashes, errors."},
        {"id": "uuid-b", "name": "Feature Request", "description": "New capability."},
    ]
    node = {"id": "clf1", "type": "ClassifierAgent", "data": {"name": "Router", "categories": cats}}
    llm = _ScriptedLLM([
        _StubLLMResponse(tool_calls=[{
            "name": "classify_as_bug_report",
            "arguments": {"reasoning": "The user reports a crash."},
        }]),
    ])

    result = asyncio.run(execute_classifier(
        classifier_node=node,
        input_text="My app crashes when I click save.",
        llm_provider=llm,
        provider_name="anthropic",
    ))
    assert result["category_id"] == "uuid-a", result
    assert result["category_name"] == "Bug Report"
    assert "crash" in result["reasoning"].lower()
    _ok(f"picked '{result['category_name']}' with reasoning '{result['reasoning']}'")

    # Verify provider-specific tool_choice translation.
    assert llm.calls[0]["tool_choice"] == {"type": "any"}, llm.calls[0]["tool_choice"]
    _ok("tool_choice mapped to Anthropic's {'type': 'any'}")


def test_execute_classifier_retry_then_fail() -> None:
    print("\n▸ execute_classifier retry-once-then-error")
    cats = [
        {"id": "uuid-a", "name": "A", "description": ""},
        {"id": "uuid-b", "name": "B", "description": ""},
    ]
    node = {"id": "clf2", "type": "ClassifierAgent", "data": {"name": "Strict", "categories": cats}}
    # Two consecutive empty/invalid responses → should raise.
    llm = _ScriptedLLM([
        _StubLLMResponse(tool_calls=None, text="I refuse to classify"),
        _StubLLMResponse(tool_calls=[{"name": "classify_as_not_a_real_category", "arguments": {}}]),
    ])
    try:
        asyncio.run(execute_classifier(
            classifier_node=node, input_text="whatever", llm_provider=llm, provider_name="openai",
        ))
        _fail("expected ClassifierSelectionError, got success")
    except ClassifierSelectionError as e:
        _ok(f"raised ClassifierSelectionError as expected: {e}")
    assert len(llm.calls) == 2, f"expected 2 attempts, got {len(llm.calls)}"
    _ok("exactly two attempts made before failing")


def test_execute_classifier_unknown_tool_then_recover() -> None:
    print("\n▸ execute_classifier retry → recover")
    cats = [
        {"id": "uuid-a", "name": "A", "description": ""},
        {"id": "uuid-b", "name": "B", "description": ""},
    ]
    node = {"id": "clf3", "type": "ClassifierAgent", "data": {"name": "Recovers", "categories": cats}}
    llm = _ScriptedLLM([
        _StubLLMResponse(tool_calls=None, text="hmm"),
        _StubLLMResponse(tool_calls=[{"name": "classify_as_b", "arguments": {"reasoning": "fits B"}}]),
    ])
    result = asyncio.run(execute_classifier(
        classifier_node=node, input_text="xyz", llm_provider=llm, provider_name="openai",
    ))
    assert result["category_id"] == "uuid-b", result
    _ok(f"recovered on second attempt, picked {result['category_name']}")


def test_prune_unselected_branches_basic() -> None:
    print("\n▸ _prune_unselected_branches: basic fan-out")
    # Graph:  Start → Clf(cat1, cat2) → [A, B] on cat1, [C] on cat2, all → End
    graph = {
        "nodes": [
            {"id": "start", "type": "StartNode"},
            {"id": "clf", "type": "ClassifierAgent", "data": {"categories": [
                {"id": "cat1", "name": "cat1"}, {"id": "cat2", "name": "cat2"},
            ]}},
            {"id": "A", "type": "AssistantAgent"},
            {"id": "B", "type": "AssistantAgent"},
            {"id": "C", "type": "AssistantAgent"},
            {"id": "End", "type": "EndNode"},
        ],
        "edges": [
            {"source": "start", "target": "clf", "type": "sequential"},
            {"source": "clf", "target": "A", "type": "sequential", "source_handle": "cat1"},
            {"source": "clf", "target": "B", "type": "sequential", "source_handle": "cat1"},
            {"source": "clf", "target": "C", "type": "sequential", "source_handle": "cat2"},
            {"source": "A", "target": "End", "type": "sequential"},
            {"source": "B", "target": "End", "type": "sequential"},
            {"source": "C", "target": "End", "type": "sequential"},
        ],
    }
    # Minimal executor shell — we only need the method.
    ex = WorkflowExecutor.__new__(WorkflowExecutor)
    skipped = ex._prune_unselected_branches(graph, "clf", "cat1")
    assert skipped == {"C"}, f"expected only C pruned, got {skipped}"
    _ok(f"chose cat1 → skipped = {sorted(skipped)} (C alone)")


def test_prune_join_not_skipped() -> None:
    print("\n▸ _prune_unselected_branches: join from live path is NOT skipped")
    # Clf → cat1 → A → End, Clf → cat2 → B → End, and End also has a live input
    # from a parallel independent branch (I) so it must remain runnable.
    graph = {
        "nodes": [
            {"id": "start", "type": "StartNode"},
            {"id": "clf", "type": "ClassifierAgent", "data": {"categories": [
                {"id": "cat1", "name": "cat1"}, {"id": "cat2", "name": "cat2"},
            ]}},
            {"id": "A", "type": "AssistantAgent"},
            {"id": "B", "type": "AssistantAgent"},
            {"id": "I", "type": "AssistantAgent"},  # independent
            {"id": "End", "type": "EndNode"},
        ],
        "edges": [
            {"source": "start", "target": "clf", "type": "sequential"},
            {"source": "start", "target": "I", "type": "sequential"},
            {"source": "clf", "target": "A", "type": "sequential", "source_handle": "cat1"},
            {"source": "clf", "target": "B", "type": "sequential", "source_handle": "cat2"},
            {"source": "A", "target": "End", "type": "sequential"},
            {"source": "B", "target": "End", "type": "sequential"},
            {"source": "I", "target": "End", "type": "sequential"},
        ],
    }
    ex = WorkflowExecutor.__new__(WorkflowExecutor)
    skipped = ex._prune_unselected_branches(graph, "clf", "cat1")
    assert "B" in skipped, f"expected B pruned, got {skipped}"
    assert "A" not in skipped and "I" not in skipped and "End" not in skipped, skipped
    _ok(f"B pruned, A/I/End live → skipped = {sorted(skipped)}")


def test_prune_chained_downstream() -> None:
    print("\n▸ _prune_unselected_branches: chained downstream on pruned branch")
    # Clf → cat1 → A → End, Clf → cat2 → B → C → D → End. Picking cat1 should
    # prune all of {B, C, D}.
    graph = {
        "nodes": [
            {"id": "start", "type": "StartNode"},
            {"id": "clf", "type": "ClassifierAgent", "data": {"categories": [
                {"id": "cat1", "name": "cat1"}, {"id": "cat2", "name": "cat2"},
            ]}},
            {"id": "A", "type": "AssistantAgent"},
            {"id": "B", "type": "AssistantAgent"},
            {"id": "C", "type": "AssistantAgent"},
            {"id": "D", "type": "AssistantAgent"},
            {"id": "End", "type": "EndNode"},
        ],
        "edges": [
            {"source": "start", "target": "clf", "type": "sequential"},
            {"source": "clf", "target": "A", "type": "sequential", "source_handle": "cat1"},
            {"source": "clf", "target": "B", "type": "sequential", "source_handle": "cat2"},
            {"source": "B", "target": "C", "type": "sequential"},
            {"source": "C", "target": "D", "type": "sequential"},
            {"source": "A", "target": "End", "type": "sequential"},
            {"source": "D", "target": "End", "type": "sequential"},
        ],
    }
    ex = WorkflowExecutor.__new__(WorkflowExecutor)
    skipped = ex._prune_unselected_branches(graph, "clf", "cat1")
    assert skipped == {"B", "C", "D"}, f"expected {{B,C,D}} pruned, got {skipped}"
    _ok(f"transitive closure pruned {sorted(skipped)}")


def test_validate_classifier_nodes() -> None:
    print("\n▸ _validate_classifier_nodes: error surface")
    ex = WorkflowExecutor.__new__(WorkflowExecutor)

    # Happy case
    graph_ok = {
        "nodes": [
            {"id": "start", "type": "StartNode"},
            {"id": "clf", "type": "ClassifierAgent", "data": {
                "name": "Router",
                "llm_provider": "anthropic", "llm_model": "claude-3-5-haiku-20241022",
                "categories": [
                    {"id": "a", "name": "Alpha"}, {"id": "b", "name": "Beta"},
                ],
            }},
            {"id": "A", "type": "AssistantAgent"},
            {"id": "B", "type": "AssistantAgent"},
        ],
        "edges": [
            {"source": "start", "target": "clf", "type": "sequential"},
            {"source": "clf", "target": "A", "source_handle": "a", "type": "sequential"},
            {"source": "clf", "target": "B", "source_handle": "b", "type": "sequential"},
        ],
    }
    errs = ex._validate_classifier_nodes(graph_ok)
    assert errs == [], f"expected no errors, got {errs}"
    _ok("well-formed classifier → no errors")

    # Various broken configurations
    broken = {
        "nodes": [
            {"id": "clf1", "type": "ClassifierAgent", "data": {
                "name": "OnlyOne",
                "llm_provider": "anthropic", "llm_model": "claude-3-5-haiku-20241022",
                "categories": [{"id": "a", "name": "Alpha"}],  # < 2
            }},
            {"id": "clf2", "type": "ClassifierAgent", "data": {
                "name": "DupName",
                "llm_provider": "openai", "llm_model": "gpt-4o-mini",
                "categories": [
                    {"id": "x", "name": "Same"}, {"id": "y", "name": "same"},  # case-insensitive dup
                ],
            }},
            {"id": "clf3", "type": "ClassifierAgent", "data": {
                "name": "BadHandle",
                "llm_provider": "openai", "llm_model": "gpt-4o-mini",
                "categories": [
                    {"id": "p", "name": "P"}, {"id": "q", "name": "Q"},
                ],
            }},
            {"id": "clf4", "type": "ClassifierAgent", "data": {
                "name": "NoLLM",
                "categories": [
                    {"id": "p", "name": "P"}, {"id": "q", "name": "Q"},
                ],
            }},
            {"id": "clf5", "type": "ClassifierAgent", "data": {
                "name": "NoInput",
                "llm_provider": "openai", "llm_model": "gpt-4o-mini",
                "categories": [
                    {"id": "p", "name": "P"}, {"id": "q", "name": "Q"},
                ],
            }},
            {"id": "tgt", "type": "AssistantAgent"},
        ],
        "edges": [
            # clf3 has an edge with an unknown category id
            {"source": "clf3", "target": "tgt", "source_handle": "not-a-category", "type": "sequential"},
            # clf3 has another with a missing handle
            {"source": "clf3", "target": "tgt", "type": "sequential"},
        ],
    }
    errs = ex._validate_classifier_nodes(broken)
    joined = " | ".join(errs)
    for frag in [
        "must define at least 2 categories",
        "duplicate category name",
        "unknown category id",
        "missing 'source_handle'",
        "must specify both 'llm_provider' and 'llm_model'",
        "has no upstream input",
    ]:
        assert frag in joined, f"missing '{frag}' in errors:\n  {joined}"
    _ok(f"surfaced {len(errs)} validation errors covering all documented rules")


def test_skipped_sentinel_filter() -> None:
    print("\n▸ aggregate_multiple_inputs filters CLASSIFIER_SKIPPED_SENTINEL")
    from agent_orchestration.workflow_parser import WorkflowParser

    parser = WorkflowParser()
    input_sources = [
        {"source_id": "n_live", "name": "Live", "type": "AssistantAgent"},
        {"source_id": "n_skip", "name": "Pruned", "type": "AssistantAgent"},
    ]
    executed = {
        "n_live": "This is the real answer.",
        "n_skip": CLASSIFIER_SKIPPED_SENTINEL,
    }
    agg = parser.aggregate_multiple_inputs(input_sources, executed)
    names = [c["name"] for c in agg["all_inputs"]]
    assert names == ["Live"], names
    _ok("sentinel input filtered out of aggregation")


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------

class Command(BaseCommand):
    help = "Smoke-test ClassifierAgent plumbing without hitting real LLMs."

    def handle(self, *args, **options):
        print("🧭 Classifier plumbing smoke test")
        test_tool_schema_and_prompt()
        test_execute_classifier_happy_path()
        test_execute_classifier_retry_then_fail()
        test_execute_classifier_unknown_tool_then_recover()
        test_prune_unselected_branches_basic()
        test_prune_join_not_skipped()
        test_prune_chained_downstream()
        test_validate_classifier_nodes()
        test_skipped_sentinel_filter()
        self.stdout.write(self.style.SUCCESS("\n🎉 All classifier smoke tests passed."))
