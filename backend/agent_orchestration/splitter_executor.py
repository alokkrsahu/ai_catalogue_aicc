"""
Splitter Executor
=================

Executes a ``SplitterAgent`` node: given an input text and the list of
downstream agents directly connected to the splitter, force the LLM (via
tool-calling with ``tool_choice=required``) to produce a structured
allocation — a subtask string for each downstream agent that has real
work to do. Agents not allocated a subtask are treated as pruned
branches, same mechanism ClassifierAgent uses.

Design notes
------------
* **One forced tool call** returning the FULL allocation in a single
  structured output. No multi-tool dance — simpler to parse, easier for
  the LLM to produce coherently.
* **Strict partition by default, overlap_allowed toggle** — the system
  prompt wording changes based on the ``overlap_allowed`` flag on the
  SplitterAgent node. Strict mode tells the LLM "each piece of the
  input should go to exactly one agent"; overlap mode allows the same
  content to appear in multiple subtasks.
* **Pruning** — downstream agents that aren't given a subtask are
  reported in the ``pruned_target_ids`` set and the caller marks their
  ``executed_nodes`` entries with the branch-skipped sentinel. Same
  downstream aggregation logic that already handles classifier pruning
  filters them out.
* **Per-target output** — the splitter's own entry in ``executed_nodes``
  is a structured dict ``{"__per_target__": {target_id: subtask},
  "__input__": original}`` so the aggregator can pull the right
  subtask when a downstream agent asks for the splitter's output.
* **Pure router** — the splitter produces no text output of its own.
  Its "output" is the allocation. Downstream agents execute with their
  allocated subtask as input.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("conversation_orchestrator")


# Same sentinel the ClassifierAgent uses — downstream aggregator already
# knows how to filter it out (workflow_parser.aggregate_multiple_inputs).
from .classifier_executor import CLASSIFIER_SKIPPED_SENTINEL as BRANCH_SKIPPED_SENTINEL


class SplitterAllocationError(Exception):
    """Raised when the splitter LLM fails to produce a valid allocation after retry."""


def _build_allocation_tool(downstream_agents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the single ``allocate_subtasks`` tool that the splitter LLM is
    forced to call. The schema encodes the list of downstream agents so
    the LLM knows exactly which names are allowed."""
    allowed_names = [a.get("name", "") for a in downstream_agents]
    return {
        "type": "function",
        "function": {
            "name": "allocate_subtasks",
            "description": (
                "Emit the task allocation for all downstream agents that should "
                "receive work. Agents omitted from this list are pruned for this "
                "input (their branch will not execute)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "allocations": {
                        "type": "array",
                        "description": (
                            "One entry per downstream agent that should do work. "
                            "Omit agents with no relevant subtask — they'll be "
                            "pruned. Names MUST match the agent names from the "
                            "system prompt EXACTLY."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "agent_name": {
                                    "type": "string",
                                    "description": f"Must be one of: {', '.join(repr(n) for n in allowed_names)}",
                                },
                                "subtask": {
                                    "type": "string",
                                    "description": (
                                        "The specific piece of work this agent "
                                        "should do. Write it as if you were "
                                        "briefing the agent — they see this as "
                                        "their input message."
                                    ),
                                },
                                "reasoning": {
                                    "type": "string",
                                    "description": (
                                        "One short sentence explaining why this "
                                        "subtask fits this agent's role. Shown "
                                        "in logs only."
                                    ),
                                },
                            },
                            "required": ["agent_name", "subtask"],
                        },
                    },
                },
                "required": ["allocations"],
            },
        },
    }


def _build_system_prompt(
    downstream_agents: List[Dict[str, Any]],
    overlap_allowed: bool,
) -> str:
    """Auto-generated system prompt for the splitter LLM. Lists each
    downstream agent's name + role (from their system_message) so the
    LLM can reason about which agent should handle what piece of work."""
    lines = [
        "You are a task splitter. Your job is to read the input and allocate "
        "one specific subtask to each downstream agent based on their role.",
        "",
        "Rules:",
        "- You MUST call exactly ONE tool: `allocate_subtasks`. Do not answer in prose.",
        "- Each allocation's `agent_name` MUST match one of the agents listed below.",
    ]
    if overlap_allowed:
        lines.append(
            "- Overlap is ALLOWED: the same piece of content may appear in multiple "
            "subtasks if it benefits from multiple perspectives."
        )
    else:
        lines.append(
            "- STRICT PARTITION: each piece of the input should go to exactly ONE "
            "agent. Do not duplicate content across subtasks."
        )
    lines.append(
        "- If a downstream agent has NO relevant subtask for this input, OMIT them "
        "from the allocation list — their branch will be pruned for this turn."
    )
    lines.append(
        "- Each subtask should be written as a clear brief the receiving agent "
        "can act on directly (it becomes their input message)."
    )
    lines.append("")
    lines.append("Downstream agents available for allocation:")
    for idx, agent in enumerate(downstream_agents, start=1):
        name = agent.get("name", f"Agent {idx}")
        role = (agent.get("system_message") or agent.get("description") or "").strip()
        role_snippet = role[:400] + ("…" if len(role) > 400 else "")
        lines.append(f"  {idx}. {name}")
        if role_snippet:
            lines.append(f"     Role: {role_snippet}")
    return "\n".join(lines)


def _tool_choice_for_provider(provider_name: str) -> Any:
    """Provider-specific ``tool_choice`` value that forces the LLM to call exactly one tool."""
    p = (provider_name or "").lower()
    if p in ("anthropic", "claude"):
        return {"type": "any"}
    if p in ("google", "gemini"):
        return {"type": "any"}
    return "required"


async def execute_splitter(
    splitter_node: Dict[str, Any],
    input_text: str,
    downstream_agents: List[Dict[str, Any]],
    llm_provider,
    provider_name: str = "",
    event_callback=None,
) -> Dict[str, Any]:
    """Run the splitter: force a structured tool call, parse the allocation,
    return per-target subtasks + pruned target ids.

    Parameters
    ----------
    splitter_node : dict
        The SplitterAgent node (needs ``data.name`` and ``data.overlap_allowed``).
    input_text : str
        The aggregated upstream input the splitter must decompose.
    downstream_agents : list of dict
        Each entry must have ``id``, ``name``, and ``system_message`` (or
        ``description``). These are the agents directly connected to the
        splitter as targets.
    llm_provider, provider_name, event_callback
        Same semantics as classifier_executor.

    Returns
    -------
    dict
        {
          "per_target": {target_id: subtask_str, ...},  # only for allocated targets
          "pruned_target_ids": [target_id, ...],        # targets NOT in allocation
          "raw_allocations": [...],                     # the LLM's allocation array (for logging)
        }

    Raises
    ------
    SplitterAllocationError
        After one retry, if the LLM still fails to return a valid allocation.
    """
    data = splitter_node.get("data", {}) or {}
    splitter_name = data.get("name", splitter_node.get("id", "Splitter"))
    overlap_allowed = bool(data.get("overlap_allowed", False))

    if len(downstream_agents) < 2:
        raise SplitterAllocationError(
            f"SplitterAgent '{splitter_name}' must have at least 2 downstream "
            f"agents connected (got {len(downstream_agents)})."
        )

    # Build a name → target_id map so we can translate the LLM's allocation
    # back to node ids. Names can repeat in theory (user mistake), so we keep
    # only the first occurrence and log a warning if duplicates are found.
    name_to_id: Dict[str, str] = {}
    for a in downstream_agents:
        name = (a.get("name") or "").strip()
        if not name:
            continue
        if name in name_to_id:
            logger.warning(
                f"🪓 SPLITTER: downstream agents have duplicate name '{name}' — "
                "only the first occurrence will receive work via splitter allocation."
            )
            continue
        name_to_id[name] = a.get("id")

    tools = [_build_allocation_tool(downstream_agents)]
    system_prompt = _build_system_prompt(downstream_agents, overlap_allowed)
    tool_choice = _tool_choice_for_provider(provider_name)

    base_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "Split the following input into subtasks for the downstream "
                "agents listed above. Remember: call exactly ONE tool "
                "(`allocate_subtasks`) with your complete allocation.\n\n"
                "Input:\n"
                f"{input_text}"
            ),
        },
    ]

    async def _attempt(attempt_idx: int, messages: List[Dict[str, Any]]):
        logger.info(
            f"🪓 SPLITTER: attempt {attempt_idx + 1} "
            f"(provider={provider_name}, tool_choice={tool_choice!r}, overlap={overlap_allowed})"
        )
        return await llm_provider.generate_response(
            messages=messages, tools=tools, tool_choice=tool_choice,
        )

    last_error: str = ""
    for attempt in range(2):
        messages = base_messages if attempt == 0 else base_messages + [
            {
                "role": "system",
                "content": (
                    "Your previous response did not produce a valid "
                    "`allocate_subtasks` tool call. Try again — call exactly "
                    "one tool with a well-formed `allocations` array."
                ),
            },
        ]
        response = await _attempt(attempt, messages)
        if response.error:
            last_error = response.error
            logger.warning(f"🪓 SPLITTER: provider error on attempt {attempt + 1}: {response.error}")
            continue

        tool_calls = response.tool_calls or []
        if not tool_calls:
            last_error = "LLM did not return a tool call"
            logger.warning(f"🪓 SPLITTER: {last_error} on attempt {attempt + 1}")
            continue

        tc = tool_calls[0]
        tool_name = tc.get("name") or ""
        if tool_name != "allocate_subtasks":
            last_error = f"LLM called unexpected tool '{tool_name}'"
            logger.warning(f"🪓 SPLITTER: {last_error}")
            continue

        args = tc.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                last_error = "allocate_subtasks arguments were not valid JSON"
                logger.warning(f"🪓 SPLITTER: {last_error}")
                continue

        if not isinstance(args, dict):
            last_error = "allocate_subtasks arguments were not an object"
            logger.warning(f"🪓 SPLITTER: {last_error}")
            continue

        allocations = args.get("allocations") or []
        if not isinstance(allocations, list) or not allocations:
            last_error = "allocations array is empty or not a list"
            logger.warning(f"🪓 SPLITTER: {last_error}")
            continue

        # Validate the allocation — every referenced name must exist in
        # the downstream list. Unknown names are dropped with a warning
        # (the branch will simply be pruned).
        per_target: Dict[str, str] = {}
        raw_allocations: List[Dict[str, Any]] = []
        for entry in allocations:
            if not isinstance(entry, dict):
                continue
            agent_name = (entry.get("agent_name") or "").strip()
            subtask = (entry.get("subtask") or "").strip()
            reasoning = (entry.get("reasoning") or "").strip()
            if not agent_name or not subtask:
                continue
            target_id = name_to_id.get(agent_name)
            if not target_id:
                logger.warning(
                    f"🪓 SPLITTER: LLM allocated to unknown agent '{agent_name}' — "
                    "dropped. Known names: " + ", ".join(repr(n) for n in name_to_id.keys())
                )
                continue
            if target_id in per_target:
                # Same agent named twice; concatenate subtasks so nothing is lost.
                per_target[target_id] = per_target[target_id] + "\n\n" + subtask
            else:
                per_target[target_id] = subtask
            raw_allocations.append({"agent_name": agent_name, "subtask": subtask, "reasoning": reasoning})

        if not per_target:
            last_error = "no valid allocations produced — all agent names were unknown"
            logger.warning(f"🪓 SPLITTER: {last_error}")
            continue

        # Pruned = every downstream agent NOT in the allocation
        allocated_ids = set(per_target.keys())
        pruned_target_ids = [
            a.get("id") for a in downstream_agents if a.get("id") not in allocated_ids
        ]

        logger.info(
            f"✅ SPLITTER '{splitter_name}': allocated {len(per_target)} subtask(s), "
            f"pruned {len(pruned_target_ids)} branch(es)"
        )
        if event_callback:
            try:
                event_callback("splitter_decision", {
                    "agent": splitter_name,
                    "allocations": raw_allocations,
                    "pruned_count": len(pruned_target_ids),
                    "overlap_allowed": overlap_allowed,
                })
            except Exception:
                pass  # never let callback errors fail the split

        return {
            "per_target": per_target,
            "pruned_target_ids": pruned_target_ids,
            "raw_allocations": raw_allocations,
        }

    raise SplitterAllocationError(
        f"Splitter '{splitter_name}' failed to produce a valid allocation after retry: {last_error}"
    )


# ── Sentinel / helpers for executor integration ───────────────────────

__all__ = [
    "BRANCH_SKIPPED_SENTINEL",
    "SplitterAllocationError",
    "execute_splitter",
    "_build_allocation_tool",
    "_build_system_prompt",
]
