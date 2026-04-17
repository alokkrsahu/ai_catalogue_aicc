"""
Smoke-test the SplitterAgent plumbing end-to-end without hitting real LLMs.

Run::
    python manage.py test_splitter
"""

import asyncio
from typing import Any, Dict, List

from django.core.management.base import BaseCommand

from agent_orchestration.splitter_executor import (
    BRANCH_SKIPPED_SENTINEL,
    SplitterAllocationError,
    _build_allocation_tool,
    _build_system_prompt,
    execute_splitter,
)


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
        self.calls.append({"messages": messages, "tools": tools, "tool_choice": tool_choice})
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
    agents = [
        {"id": "a1", "name": "Researcher", "system_message": "You research primary sources."},
        {"id": "a2", "name": "Writer",     "system_message": "You write prose based on research."},
        {"id": "a3", "name": "Editor",     "system_message": "You polish prose for clarity."},
    ]

    tool = _build_allocation_tool(agents)
    fn = tool["function"]
    assert fn["name"] == "allocate_subtasks"
    assert set(fn["parameters"]["properties"]["allocations"]["items"]["required"]) == {"agent_name", "subtask"}
    _ok("allocate_subtasks tool shape is correct")

    prompt = _build_system_prompt(agents, overlap_allowed=False)
    for a in agents:
        assert a["name"] in prompt, f"{a['name']} missing from prompt"
    assert "STRICT PARTITION" in prompt
    assert "Overlap is ALLOWED" not in prompt
    _ok("strict-partition prompt lists all agents + strict wording")

    prompt_overlap = _build_system_prompt(agents, overlap_allowed=True)
    assert "Overlap is ALLOWED" in prompt_overlap
    assert "STRICT PARTITION" not in prompt_overlap
    _ok("overlap-allowed prompt uses overlap wording")


def test_execute_happy_path() -> None:
    print("\n▸ execute_splitter happy path — partial allocation prunes unassigned")
    splitter_node = {"id": "s1", "data": {"name": "Task Splitter", "overlap_allowed": False}}
    agents = [
        {"id": "a1", "name": "Researcher", "system_message": "research"},
        {"id": "a2", "name": "Writer",     "system_message": "write"},
        {"id": "a3", "name": "Editor",     "system_message": "edit"},
    ]

    scripted = [
        _StubLLMResponse(tool_calls=[{
            "name": "allocate_subtasks",
            "arguments": {
                "allocations": [
                    {"agent_name": "Researcher", "subtask": "Find 3 sources on X.", "reasoning": "primary sources"},
                    {"agent_name": "Writer", "subtask": "Write a 300-word summary.", "reasoning": "prose"},
                    # Editor is intentionally omitted — should be pruned.
                ]
            },
        }]),
    ]
    llm = _ScriptedLLM(scripted)

    result = asyncio.run(execute_splitter(
        splitter_node=splitter_node,
        input_text="Some research topic",
        downstream_agents=agents,
        llm_provider=llm,
        provider_name="openai",
    ))

    assert result["per_target"] == {
        "a1": "Find 3 sources on X.",
        "a2": "Write a 300-word summary.",
    }, f"per_target wrong: {result['per_target']}"
    assert result["pruned_target_ids"] == ["a3"], f"pruned wrong: {result['pruned_target_ids']}"
    _ok(f"allocated Researcher + Writer, pruned Editor (result: {result['per_target']})")


def test_retry_then_recover() -> None:
    print("\n▸ execute_splitter retry → recover")
    splitter_node = {"id": "s1", "data": {"name": "T", "overlap_allowed": False}}
    agents = [
        {"id": "a", "name": "A", "system_message": "alpha"},
        {"id": "b", "name": "B", "system_message": "beta"},
    ]
    scripted = [
        _StubLLMResponse(tool_calls=[]),  # first attempt — no tool call
        _StubLLMResponse(tool_calls=[{
            "name": "allocate_subtasks",
            "arguments": {"allocations": [
                {"agent_name": "A", "subtask": "do alpha"},
                {"agent_name": "B", "subtask": "do beta"},
            ]},
        }]),
    ]
    llm = _ScriptedLLM(scripted)
    result = asyncio.run(execute_splitter(
        splitter_node=splitter_node, input_text="x",
        downstream_agents=agents, llm_provider=llm, provider_name="openai",
    ))
    assert result["per_target"] == {"a": "do alpha", "b": "do beta"}
    assert len(llm.calls) == 2
    _ok("recovered on second attempt with full allocation")


def test_retry_then_fail() -> None:
    print("\n▸ execute_splitter retry-once-then-error")
    splitter_node = {"id": "s1", "data": {"name": "T", "overlap_allowed": False}}
    agents = [
        {"id": "a", "name": "A", "system_message": "a"},
        {"id": "b", "name": "B", "system_message": "b"},
    ]
    scripted = [
        _StubLLMResponse(tool_calls=[]),  # attempt 1 — empty
        _StubLLMResponse(tool_calls=[{
            "name": "allocate_subtasks",
            "arguments": {"allocations": [  # all names unknown
                {"agent_name": "Ghost", "subtask": "nothing"},
            ]},
        }]),
    ]
    llm = _ScriptedLLM(scripted)
    try:
        asyncio.run(execute_splitter(
            splitter_node=splitter_node, input_text="x",
            downstream_agents=agents, llm_provider=llm, provider_name="openai",
        ))
        _fail("expected SplitterAllocationError, got none")
    except SplitterAllocationError as e:
        assert len(llm.calls) == 2, f"expected 2 attempts, got {len(llm.calls)}"
        _ok(f"raised SplitterAllocationError after retry: {e}")


def test_under_two_downstream_rejected() -> None:
    print("\n▸ fewer than 2 downstream agents → error")
    splitter_node = {"id": "s1", "data": {"name": "Solo", "overlap_allowed": False}}
    agents = [{"id": "a", "name": "A", "system_message": "a"}]
    llm = _ScriptedLLM([])
    try:
        asyncio.run(execute_splitter(
            splitter_node=splitter_node, input_text="x",
            downstream_agents=agents, llm_provider=llm, provider_name="openai",
        ))
        _fail("expected SplitterAllocationError for <2 agents")
    except SplitterAllocationError as e:
        _ok(f"rejected single-agent splitter: {e}")


def test_duplicate_agent_name_in_allocation() -> None:
    print("\n▸ same agent allocated twice → subtasks concatenated")
    splitter_node = {"id": "s1", "data": {"name": "T", "overlap_allowed": True}}
    agents = [
        {"id": "a", "name": "A", "system_message": "a"},
        {"id": "b", "name": "B", "system_message": "b"},
    ]
    scripted = [
        _StubLLMResponse(tool_calls=[{
            "name": "allocate_subtasks",
            "arguments": {"allocations": [
                {"agent_name": "A", "subtask": "First piece"},
                {"agent_name": "A", "subtask": "Second piece"},
                {"agent_name": "B", "subtask": "Other piece"},
            ]},
        }]),
    ]
    llm = _ScriptedLLM(scripted)
    result = asyncio.run(execute_splitter(
        splitter_node=splitter_node, input_text="x",
        downstream_agents=agents, llm_provider=llm, provider_name="openai",
    ))
    assert result["per_target"]["a"] == "First piece\n\nSecond piece", result["per_target"]
    assert result["per_target"]["b"] == "Other piece"
    _ok("duplicate allocations concatenated for the same target")


def test_event_callback() -> None:
    print("\n▸ event_callback receives splitter_decision")
    events: List[tuple] = []
    splitter_node = {"id": "s1", "data": {"name": "Ev", "overlap_allowed": True}}
    agents = [
        {"id": "a", "name": "A", "system_message": "a"},
        {"id": "b", "name": "B", "system_message": "b"},
    ]
    scripted = [
        _StubLLMResponse(tool_calls=[{
            "name": "allocate_subtasks",
            "arguments": {"allocations": [
                {"agent_name": "A", "subtask": "x"},
            ]},
        }]),
    ]
    llm = _ScriptedLLM(scripted)
    asyncio.run(execute_splitter(
        splitter_node=splitter_node, input_text="y",
        downstream_agents=agents, llm_provider=llm, provider_name="openai",
        event_callback=lambda t, d: events.append((t, d)),
    ))
    assert len(events) == 1 and events[0][0] == "splitter_decision"
    assert events[0][1]["pruned_count"] == 1
    assert events[0][1]["overlap_allowed"] is True
    _ok(f"splitter_decision emitted: {events[0][1]}")


class Command(BaseCommand):
    help = "Smoke-test the SplitterAgent plumbing."

    def handle(self, *args, **options):
        print("🪓 Splitter plumbing smoke test")
        test_tool_schema_and_prompt()
        test_execute_happy_path()
        test_retry_then_recover()
        test_retry_then_fail()
        test_under_two_downstream_rejected()
        test_duplicate_agent_name_in_allocation()
        test_event_callback()
        print("\n🎉 All splitter smoke tests passed.")
