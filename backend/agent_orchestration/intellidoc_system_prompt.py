"""
IntelliDoc platform system prompt addendum (hybrid: global core + per node type).

Appended after the user's system_message / instructions in ChatManager; not exposed
or editable in the workflow UI. Edit this module to change platform-wide behavior.
"""
from __future__ import annotations

from typing import Any, Dict

# Visible delimiter so logs/debugging can spot the injection (not shown to end users in UI)
SECTION_HEADER = "\n\n=== IntelliDoc platform guidance ===\n"

INTELLIDOC_CORE = """You are operating inside AICC IntelliDoc. Obey the user and node instructions above first.
- Prioritize accuracy over completeness; if context is insufficient, say so clearly.
- When project documents, tool results, or retrieved context are provided, ground factual claims in them.
- Do not invent quotes, page numbers, section labels, or citations that are not supported by supplied content."""

# Per workflow node `type` (see WorkflowDesigner / graph JSON). Empty string = core only.
INTELLIDOC_BY_AGENT_TYPE: Dict[str, str] = {
    "AssistantAgent": (
        "When your workflow expects numbered source markers, use distinct [1], [2], … for distinct "
        "supporting passages; avoid reusing one marker for unrelated claims. If you revise an answer, "
        "preserve markers where the underlying claim remains."
    ),
    "UserProxyAgent": (
        "Represent the user or human input clearly and concisely for downstream agents; do not override "
        "workflow routing unless configured to do so."
    ),
    "DelegateAgent": (
        "Focus on your delegated subtask; synthesize inputs you are given without restating full "
        "workflow instructions from other agents."
    ),
    "GroupChatManager": (
        "Synthesize delegate outputs fairly; preserve critical constraints and conflicts from upstream "
        "context in your summary."
    ),
    "MCPServer": (
        "When invoking tools, follow the tool schema; return results in the shape downstream nodes expect."
    ),
    "StartNode": "",
    "EndNode": "",
}


def intellidoc_addendum_for_node(agent_node: Dict[str, Any]) -> str:
    """
    Build the full platform addendum for this graph node.

    Returns empty string if agent_node is missing (defensive); otherwise always includes CORE
    plus an extra paragraph when the node type has a non-empty template.
    """
    if not agent_node or not isinstance(agent_node, dict):
        return ""

    node_type = agent_node.get("type") or "AssistantAgent"
    parts = [INTELLIDOC_CORE.strip()]
    extra = INTELLIDOC_BY_AGENT_TYPE.get(node_type, "").strip()
    if extra:
        parts.append(extra)

    body = "\n\n".join(parts)
    return SECTION_HEADER + body
