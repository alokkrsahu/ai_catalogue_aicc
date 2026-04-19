"""
Classifier Executor
===================

Executes a ``ClassifierAgent`` node: given an input text and a list of
user-defined categories, force the LLM (via tool-calling with
``tool_choice=required``) to pick exactly one category. The caller is
responsible for pruning the downstream subgraphs of the non-selected
categories — see ``WorkflowExecutor._prune_unselected_branches``.

Design notes
------------
* **Strict single-select** — one tool per category, ``tool_choice=required``.
  The LLM physically cannot return "no match" or pick outside the list.
* **Retry once** on provider-level failures (no tool call, malformed
  arguments, unknown tool name). On second failure we raise
  ``ClassifierSelectionError``; the workflow fails with a clear message.
* **Pure router** — the node's output to downstream is the *original*
  input text, unchanged. The decision is surfaced via the returned dict
  for logging/streaming only.
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger('conversation_orchestrator')


MAX_TOOL_NAME_LEN = 60

# Marker stored in ``executed_nodes`` for every downstream node that is pruned
# because the classifier did not pick that branch. Downstream aggregators detect
# this value and ignore the input; the main executor's ``_find_ready_nodes``
# treats the node as "already done" so it is never dispatched.
CLASSIFIER_SKIPPED_SENTINEL = "__CLASSIFIER_BRANCH_SKIPPED__"


class ClassifierSelectionError(Exception):
    """Raised when the classifier LLM fails to pick a valid category after retry."""


def _sanitize_category_name(name: str) -> str:
    """
    Turn a human category name into a valid OpenAI/Anthropic tool name fragment.

    Tool names must be ``[a-zA-Z0-9_-]{1,64}`` in practice. We lowercase, collapse
    whitespace to underscores, drop anything else, and clamp length.
    """
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", (name or "").strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        slug = "category"
    return slug[:MAX_TOOL_NAME_LEN]


def build_classifier_tools(
    categories: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    Build one function tool per category (OpenAI/Anthropic/Gemini common shape).

    Parameters
    ----------
    categories : list[dict]
        Each dict has ``id`` (UUID), ``name`` (str), and optional ``description``.

    Returns
    -------
    tools : list[dict]
        Tool schema passed to ``llm_provider.generate_response(tools=...)``.
    tool_map : dict[str, dict]
        Mapping tool_name → original category dict. Used to resolve which
        category the LLM picked from the returned tool call.
    """
    tools: List[Dict[str, Any]] = []
    tool_map: Dict[str, Dict[str, Any]] = {}
    seen_names: set = set()

    for idx, cat in enumerate(categories):
        cat_name = (cat.get("name") or f"Category {idx + 1}").strip()
        base_slug = _sanitize_category_name(cat_name)
        tool_name = f"classify_as_{base_slug}"

        # De-dup: if two categories sanitize to the same slug, suffix with index.
        unique_name = tool_name
        counter = 2
        while unique_name in seen_names:
            suffix = f"_{counter}"
            unique_name = tool_name[: 64 - len(suffix)] + suffix
            counter += 1
        seen_names.add(unique_name)

        description = (cat.get("description") or "").strip()
        if not description:
            description = f"Pick this if the input best fits: {cat_name}."
        # OpenAI caps tool descriptions at 1024 chars.
        description = description[:1024]

        tools.append({
            "type": "function",
            "function": {
                "name": unique_name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reasoning": {
                            "type": "string",
                            "description": (
                                "One-sentence justification for picking this "
                                "category. Shown in logs; keep it concise."
                            ),
                        },
                    },
                    "required": ["reasoning"],
                },
            },
        })
        tool_map[unique_name] = cat

    logger.info(
        f"🧭 CLASSIFIER TOOLS: Built {len(tools)} category tools "
        f"({[t['function']['name'] for t in tools]})"
    )
    return tools, tool_map


def build_classifier_system_prompt(categories: List[Dict[str, Any]]) -> str:
    """
    Auto-generate the classifier's system prompt from its category list. This is
    not user-editable per the design — the classifier is a narrow routing node.
    """
    lines = [
        "You are a strict classifier. Read the input and pick exactly ONE "
        "category that best fits it by calling exactly ONE tool.",
        "",
        "Rules:",
        "- You MUST call exactly one tool. Do not answer in prose.",
        "- Do not call more than one tool, and do not call none.",
        "- Pick the single best match even if the fit is imperfect.",
        "",
        "Categories:",
    ]
    for idx, cat in enumerate(categories, start=1):
        name = (cat.get("name") or f"Category {idx}").strip()
        desc = (cat.get("description") or "").strip()
        if desc:
            lines.append(f"  {idx}. {name} — {desc}")
        else:
            lines.append(f"  {idx}. {name}")
    return "\n".join(lines)


def _tool_choice_for_provider(provider_name: str) -> Any:
    """
    Build a provider-specific ``tool_choice`` value that forces the LLM to call
    exactly one tool. Falls back to ``"required"`` for unknown providers.

    * OpenAI: ``"required"``
    * Anthropic: ``{"type": "any"}``
    * Google (Gemini): ``{"type": "any"}`` — our gemini_provider maps this to
      ``functionCallingConfig.mode = "ANY"``.
    """
    p = (provider_name or "").lower()
    if p == "anthropic" or p == "claude":
        return {"type": "any"}
    if p == "google" or p == "gemini":
        return {"type": "any"}
    # openai and default
    return "required"


async def execute_classifier(
    classifier_node: Dict[str, Any],
    input_text: str,
    llm_provider,
    provider_name: str = "",
    event_callback=None,
    project_id: Optional[str] = None,
    execution_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the classifier: force a tool call, map it back to a category, return
    the decision. Retries once on provider-level failure.

    Returns
    -------
    dict
        ``{category_id, category_name, reasoning, tool_name}``.

    Raises
    ------
    ClassifierSelectionError
        After one retry, if the LLM still fails to return a valid tool call
        for a known category.
    """
    data = classifier_node.get("data", {}) or {}
    classifier_name = data.get("name", classifier_node.get("id", "Classifier"))
    categories = data.get("categories") or []
    if len(categories) < 2:
        raise ClassifierSelectionError(
            f"Classifier '{classifier_name}' must have at least 2 categories (got {len(categories)})."
        )
    t_start = time.time()

    tools, tool_map = build_classifier_tools(categories)
    system_prompt = build_classifier_system_prompt(categories)
    tool_choice = _tool_choice_for_provider(provider_name)

    base_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "Classify the following input. Call exactly one tool "
                "corresponding to the best-fit category.\n\nInput:\n"
                f"{input_text}"
            ),
        },
    ]

    async def _attempt(attempt_idx: int, messages: List[Dict[str, Any]]):
        logger.info(
            f"🧭 CLASSIFIER: attempt {attempt_idx + 1} "
            f"(provider={provider_name}, tool_choice={tool_choice!r})"
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
                    "Your previous response did not call exactly one tool. "
                    "You MUST call exactly one of the provided tools now. "
                    "Do not produce prose."
                ),
            },
        ]
        response = await _attempt(attempt, messages)
        if response.error:
            last_error = response.error
            logger.warning(
                f"🧭 CLASSIFIER: provider error on attempt {attempt + 1}: {response.error}"
            )
            continue

        tool_calls = response.tool_calls or []
        if not tool_calls:
            last_error = "LLM did not return a tool call"
            logger.warning(f"🧭 CLASSIFIER: {last_error} on attempt {attempt + 1}")
            continue

        # Use the first tool call; if more than one, drop the rest.
        tc = tool_calls[0]
        tool_name = tc.get("name") or ""
        cat = tool_map.get(tool_name)
        if cat is None:
            last_error = f"LLM called unknown tool '{tool_name}'"
            logger.warning(f"🧭 CLASSIFIER: {last_error} on attempt {attempt + 1}")
            continue

        args = tc.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        reasoning = (args.get("reasoning") if isinstance(args, dict) else "") or ""

        logger.info(
            f"✅ CLASSIFIER: picked category '{cat.get('name')}' "
            f"(id={cat.get('id')}) via tool '{tool_name}'"
        )
        if event_callback:
            try:
                event_callback("classifier_decision", {
                    "category_name": cat.get("name"),
                    "category_id": cat.get("id"),
                    "reasoning": reasoning,
                })
            except Exception:  # never let callback errors fail classification
                pass

        # Persist an ExperimentMetric row so the analytics dashboard can
        # show per-workflow classifier decisions. Best-effort.
        try:
            from .metrics_logger import log_experiment_metric
            duration_ms = round((time.time() - t_start) * 1000, 1)
            await log_experiment_metric(
                project_id=project_id,
                experiment_type='classifier',
                metric_data={
                    'experiment': 'classifier',
                    'project_id': project_id,
                    'agent_name': classifier_name,
                    'duration_ms': duration_ms,
                    'attempt': attempt + 1,
                    'category_id': cat.get('id'),
                    'category_name': cat.get('name'),
                    'reasoning': reasoning,
                    'tool_name': tool_name,
                    'category_count': len(categories),
                },
                configuration={
                    'agent_name': classifier_name,
                    'category_count': len(categories),
                },
                execution_id=execution_id,
                log_tag='EXP_METRIC_CLASSIFIER',
            )
        except Exception as exc:
            logger.warning(f"🧭 CLASSIFIER: metric logging failed: {exc}")

        return {
            "category_id": cat.get("id"),
            "category_name": cat.get("name"),
            "reasoning": reasoning,
            "tool_name": tool_name,
        }

    raise ClassifierSelectionError(
        f"Classifier failed to pick a valid category after retry: {last_error}"
    )
