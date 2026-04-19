"""
Splitter Executor
=================

Executes a ``SplitterAgent`` node: given an input text and the set of
directly-connected downstream agents, force the LLM (via tool-calling with
``tool_choice=required``) to produce a structured allocation — a subtask
string for each agent that should receive work. Agents not allocated a
subtask are treated as pruned branches (same mechanism ClassifierAgent
uses with its categories).

Design intent
-------------
Each outgoing edge from the Splitter defines one allocation target.
The target agent's own ``name`` and ``system_message`` describe what
that slot does — there is no separate slot configuration on the
SplitterAgent node. "Slots inherit the config of the agents they're
connected to" — so the splitter just needs to look downstream.

Architecturally symmetric with ClassifierAgent:
  * ClassifierAgent has `categories` — LLM picks exactly ONE
  * SplitterAgent has `downstream_agents` (derived from outgoing edges)
    — LLM picks a SUBSET, each with a subtask

Design notes
------------
* **One forced tool call** returning the FULL allocation in a single
  structured output.
* **Strict partition by default, overlap_allowed toggle** — system-prompt
  wording differs based on the ``overlap_allowed`` flag.
* **Pruning** — agents not in the allocation contribute
  ``pruned_target_ids``; the caller marks their branches with the
  branch-skipped sentinel.
* **Per-target output** — the splitter's entry in ``executed_nodes`` is
  ``{"__kind__": "splitter", "__per_target__": {target_id: subtask},
  "__input__": ...}``. Downstream aggregators look up their own
  subtask via their node id.
* **Pure router** — splitter produces no content of its own.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("conversation_orchestrator")


# Reuse the ClassifierAgent skipped sentinel — downstream aggregator already
# knows how to filter it out. Exported as BRANCH_SKIPPED_SENTINEL for clarity.
from .classifier_executor import CLASSIFIER_SKIPPED_SENTINEL as BRANCH_SKIPPED_SENTINEL


class SplitterAllocationError(Exception):
    """Raised when the splitter LLM fails to produce a valid allocation after retry."""


def _build_allocation_tool(downstream_agents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the single ``allocate_subtasks`` tool that the splitter LLM is
    forced to call. The schema encodes the list of agent NAMES so the LLM
    knows exactly which names are allowed."""
    allowed_names = [a.get("name", "") for a in downstream_agents]
    return {
        "type": "function",
        "function": {
            "name": "allocate_subtasks",
            "description": (
                "Emit the task allocation for the agents that should receive "
                "work. Agents omitted from this list are pruned for this input "
                "(their branch will not execute)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "allocations": {
                        "type": "array",
                        "description": (
                            "One entry per agent that should do work. Omit "
                            "agents with no relevant subtask — they'll be "
                            "pruned. Agent names MUST match the names listed "
                            "in the system prompt EXACTLY."
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
                                        "should do. Written as a brief for "
                                        "the downstream agent — it becomes "
                                        "their input message."
                                    ),
                                },
                                "reasoning": {
                                    "type": "string",
                                    "description": (
                                        "One short sentence explaining why "
                                        "this subtask fits this agent. Logged."
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


def _build_system_prompt(downstream_agents: List[Dict[str, Any]], overlap_allowed: bool) -> str:
    """Auto-generated system prompt for the splitter LLM. Lists each downstream
    agent's name + role so the LLM knows what kind of work each agent handles.

    Role text comes exclusively from the agent's ``system_message``. The
    free-form ``description`` (a UI-surface field) is intentionally NOT
    consulted — the splitter must reason only from the operational prompt
    that will actually run on the downstream agent, not from UI copy that
    can drift from behaviour.
    """
    lines = [
        "You are a task splitter. Your job is to read the input and allocate "
        "one specific subtask to each relevant agent based on the agent's role.",
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
        "- If an agent has NO relevant subtask for this input, OMIT it from the "
        "allocation list — that agent's branch will be pruned for this turn."
    )
    lines.append(
        "- Each subtask should be written as a clear brief — it becomes the "
        "input message for that downstream agent."
    )
    lines.append(
        "- Provide a short `reasoning` string with each allocation explaining "
        "WHY that subtask fits that agent — this is logged and surfaced to "
        "operators."
    )
    lines.append("")
    lines.append("Downstream agents available for allocation:")
    for idx, agent in enumerate(downstream_agents, start=1):
        name = agent.get("name", f"Agent {idx}")
        # Only the system_message defines the agent's operational role.
        # Intentionally not falling back to `description` — that's UI copy
        # and can drift from behaviour.
        role = (agent.get("system_message") or "").strip()
        lines.append(f"  {idx}. {name}")
        if role:
            snippet = role[:400] + ("…" if len(role) > 400 else "")
            lines.append(f"     Role: {snippet}")
        else:
            lines.append("     Role: (no system_message configured)")
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
    project_id: Optional[str] = None,
    execution_id: Optional[str] = None,
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
        Each entry must have ``id``, ``name``, and optionally ``system_message``
        and ``description``. Derived at runtime from the splitter's outgoing
        edges by the workflow executor — the splitter has no independent
        "slot" configuration; each connected agent IS a slot.
    llm_provider, provider_name, event_callback
        Same semantics as classifier_executor.

    Returns
    -------
    dict
        {
          "per_target": {target_id: subtask_str, ...},   # only allocated targets
          "pruned_target_ids": [target_id, ...],         # targets NOT in allocation
          "raw_allocations": [...],                      # the LLM's allocation array (for logging)
        }

    Raises
    ------
    SplitterAllocationError
        After one retry, if the LLM still fails to return a valid allocation.
    """
    data = splitter_node.get("data", {}) or {}
    splitter_name = data.get("name", splitter_node.get("id", "Splitter"))
    overlap_allowed = bool(data.get("overlap_allowed", False))
    t_start = time.time()

    if len(downstream_agents) < 2:
        raise SplitterAllocationError(
            f"SplitterAgent '{splitter_name}' must have at least 2 downstream agents "
            f"(got {len(downstream_agents)})."
        )

    # Build a name → target_id map so the LLM's allocation can be translated back.
    name_to_target_id: Dict[str, str] = {}
    for a in downstream_agents:
        name = (a.get("name") or "").strip()
        if not name:
            continue
        if name in name_to_target_id:
            logger.warning(
                f"🪓 SPLITTER: duplicate agent name '{name}' downstream of '{splitter_name}' — "
                "only the first occurrence will receive work via allocation."
            )
            continue
        name_to_target_id[name] = a.get("id")

    tools = [_build_allocation_tool(downstream_agents)]
    system_prompt = _build_system_prompt(downstream_agents, overlap_allowed)
    tool_choice = _tool_choice_for_provider(provider_name)

    base_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "Split the following input into subtasks for the agents listed "
                "above. Call exactly ONE tool (`allocate_subtasks`) with your "
                "complete allocation.\n\n"
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

        # Validate each allocation — agent names must exist in the downstream list.
        per_target: Dict[str, str] = {}
        raw_allocations: List[Dict[str, Any]] = []
        for entry in allocations:
            if not isinstance(entry, dict):
                continue
            agent_name = (entry.get("agent_name") or entry.get("slot_name") or "").strip()
            subtask = (entry.get("subtask") or "").strip()
            reasoning = (entry.get("reasoning") or "").strip()
            if not agent_name or not subtask:
                continue
            target_id = name_to_target_id.get(agent_name)
            if not target_id:
                logger.warning(
                    f"🪓 SPLITTER: LLM allocated to unknown agent '{agent_name}' — "
                    "dropped. Known agents: " + ", ".join(repr(n) for n in name_to_target_id.keys())
                )
                continue
            if target_id in per_target:
                # Same target named twice; concatenate so nothing is lost.
                per_target[target_id] = per_target[target_id] + "\n\n" + subtask
            else:
                per_target[target_id] = subtask
            raw_allocations.append({"agent_name": agent_name, "subtask": subtask, "reasoning": reasoning})

        if not per_target:
            last_error = "no valid allocations produced — all agent names were unknown"
            logger.warning(f"🪓 SPLITTER: {last_error}")
            continue

        # Pruned = every downstream target NOT in the allocation
        allocated_target_ids = set(per_target.keys())
        pruned_targets = [a for a in downstream_agents if a.get("id") not in allocated_target_ids]
        pruned_target_ids = [a.get("id") for a in pruned_targets]

        logger.info(
            f"✅ SPLITTER '{splitter_name}': allocated {len(per_target)} agent(s), "
            f"pruned {len(pruned_target_ids)} branch(es) "
            f"(mode={'overlap' if overlap_allowed else 'strict-partition'})"
        )
        # Per-allocation reasoning log so operators can see WHY each subtask
        # was routed where, before the downstream agents start running.
        for entry in raw_allocations:
            agent_name = entry.get("agent_name", "?")
            reasoning = entry.get("reasoning") or "(no reasoning provided)"
            subtask_preview = entry.get("subtask", "").replace("\n", " ").strip()
            if len(subtask_preview) > 200:
                subtask_preview = subtask_preview[:197] + "..."
            logger.info(
                f"🪓 SPLITTER '{splitter_name}' → {agent_name}: {reasoning}"
            )
            logger.info(
                f"    ↪ subtask: {subtask_preview}"
            )
        # Log pruned agents by name so operators know which branches are
        # skipped this turn and why they got no input.
        if pruned_targets:
            pruned_names = ", ".join(
                (a.get("name") or a.get("id") or "?") for a in pruned_targets
            )
            logger.info(
                f"🪓 SPLITTER '{splitter_name}' pruned (no relevant subtask): {pruned_names}"
            )

        if event_callback:
            try:
                event_callback("splitter_decision", {
                    "agent": splitter_name,
                    "allocations": raw_allocations,
                    "pruned_count": len(pruned_target_ids),
                    "pruned_agent_names": [
                        (a.get("name") or a.get("id") or "") for a in pruned_targets
                    ],
                    "overlap_allowed": overlap_allowed,
                })
            except Exception:
                pass  # never let callback errors fail the split

        # Persist an ExperimentMetric row so the analytics dashboard can
        # show per-workflow splitter decisions (duration, allocation
        # distribution, pruned branches). Best-effort: never blocks the
        # caller if the DB write fails.
        try:
            from .metrics_logger import log_experiment_metric
            duration_ms = round((time.time() - t_start) * 1000, 1)
            await log_experiment_metric(
                project_id=project_id,
                experiment_type='splitter',
                metric_data={
                    'experiment': 'splitter',
                    'project_id': project_id,
                    'agent_name': splitter_name,
                    'duration_ms': duration_ms,
                    'attempt': attempt + 1,
                    'allocated_count': len(per_target),
                    'pruned_count': len(pruned_target_ids),
                    'allocated_agent_names': list({
                        a.get('agent_name') for a in raw_allocations
                    }),
                    'pruned_agent_names': [
                        (a.get('name') or a.get('id') or '') for a in pruned_targets
                    ],
                    'overlap_allowed': overlap_allowed,
                },
                configuration={
                    'agent_name': splitter_name,
                    'overlap_allowed': overlap_allowed,
                    'downstream_count': len(downstream_agents),
                },
                execution_id=execution_id,
                log_tag='EXP_METRIC_SPLITTER',
            )
        except Exception as exc:
            logger.warning(f"🪓 SPLITTER: metric logging failed: {exc}")

        return {
            "per_target": per_target,
            "pruned_target_ids": pruned_target_ids,
            "raw_allocations": raw_allocations,
        }

    raise SplitterAllocationError(
        f"Splitter '{splitter_name}' failed to produce a valid allocation after retry: {last_error}"
    )


__all__ = [
    "BRANCH_SKIPPED_SENTINEL",
    "SplitterAllocationError",
    "execute_splitter",
    "_build_allocation_tool",
    "_build_system_prompt",
]
