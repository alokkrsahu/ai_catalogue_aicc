"""
Serialize / deserialize workflow node outputs stored in execution_record.executed_nodes.

Values are usually plain strings. When an agent produces structured citations (doc-tool
synthesis), we store {"text": str, "citations": [...]} so downstream agents can receive
grounding metadata while conversation_history stays plain text.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Keys for structured handoff (must match JSON stored in executed_nodes)
TEXT_KEY = "text"
CITATIONS_KEY = "citations"


def pack_executed_output(text: str, citations: Optional[List[Dict[str, Any]]] = None) -> Any:
    """
    Store node output for executed_nodes. Uses a dict only when citations are non-empty.
    """
    if citations:
        return {TEXT_KEY: text, CITATIONS_KEY: list(citations)}
    return text if text is not None else ""


def plain_executed_output(value: Any) -> str:
    """User-facing / conversation_history text."""
    if value is None:
        return ""
    if isinstance(value, dict) and TEXT_KEY in value:
        t = value.get(TEXT_KEY)
        return t if isinstance(t, str) else str(t)
    return str(value)


def citations_from_executed_output(value: Any) -> List[Dict[str, Any]]:
    """Structured citations from a packed executed_nodes value, or []."""
    if isinstance(value, dict):
        raw = value.get(CITATIONS_KEY)
        if isinstance(raw, list):
            return [x for x in raw if isinstance(x, dict)]
    return []


def renumber_citations_globally(inputs: List[Dict[str, Any]], start_ref: int = 1) -> int:
    """
    Renumber citations across multiple aggregated inputs so [N] markers never collide.
    Modifies inputs IN PLACE. Returns the next available ref number.

    Each input dict must have 'content_plain' (str with [N] markers) and 'citations' (list of dicts with 'ref').
    Uses two-pass placeholder approach to prevent collision: [old] → [__CITE_new__] → [new].
    """
    import re
    current_ref = start_ref

    for inp in inputs:
        cites = inp.get("citations", [])
        if not cites:
            continue

        content = inp.get("content_plain", "")

        # Build old→new mapping from citation objects
        old_refs = sorted({c.get("ref") for c in cites if c.get("ref") is not None})
        if not old_refs:
            continue

        old_to_new = {}
        for i, old in enumerate(old_refs):
            old_to_new[old] = current_ref + i

        # Pass 1: replace [old] with placeholder [__CITE_new__] (reverse order to avoid substring collision)
        for old in sorted(old_refs, reverse=True):
            content = content.replace(f"[{old}]", f"[__CITE_{old_to_new[old]}__]")

        # Pass 2: replace placeholders with final [new]
        for new in range(current_ref, current_ref + len(old_refs)):
            content = content.replace(f"[__CITE_{new}__]", f"[{new}]")

        # Update citation objects
        for c in cites:
            old = c.get("ref")
            if old in old_to_new:
                c["ref"] = old_to_new[old]

        inp["content_plain"] = content
        current_ref += len(old_refs)

    return current_ref


def format_upstream_citations_block(agent_name: str, citations: List[Dict[str, Any]]) -> str:
    """
    Human-readable block appended for downstream LLM prompts so [N] markers stay interpretable.
    """
    url_count = sum(1 for c in citations if c.get('url'))
    logger.info(
        f"🔗 CITE[4/UPSTREAM]: Formatting block from '{agent_name}' — "
        f"{len(citations)} citations ({url_count} with URL, {len(citations)-url_count} doc-only)"
    )
    if not citations:
        return ""
    lines = [
        "",
        f'=== Grounded source references from upstream agent "{agent_name}" '
        f"(maps to [N] markers in the text above) ===",
    ]
    for c in citations:
        ref = c.get("ref", "?")
        title = c.get("document_title") or "Document"
        qt = (c.get("quoted_text") or "").replace("\n", " ").strip()
        if len(qt) > 400:
            qt = qt[:400] + "…"
        loc_parts = []
        if c.get("page") is not None:
            loc_parts.append(f"p.{c['page']}")
        if c.get("section"):
            loc_parts.append(str(c["section"]))
        loc = f" ({', '.join(loc_parts)})" if loc_parts else ""
        url_part = f" | url: {c['url']}" if c.get("url") else ""
        source_part = f" | source: {c['source']}" if c.get("source") else ""
        lines.append(f'  [{ref}] {title}{loc}{url_part}{source_part}: "{qt}"')
    return "\n".join(lines)
