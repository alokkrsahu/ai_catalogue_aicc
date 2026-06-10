"""
Deterministic graph invariants for agent workflows.

These helpers were extracted from workflow_generator.py so they can run at
SAVE TIME (via the DRF serializer) in addition to AI-Builder build time.
Without save-time validation, a manual canvas edit can persist a graph the
executor cannot handle correctly — e.g. a sequential cycle that the
Kahn's-algorithm topological sort in `workflow_parser.py` silently re-orders.

Public API:
    detect_sequential_cycles(nodes, edges) -> List[str]
    resolve_toggle_dependencies(args)      -> Dict
    validate_classifier_handles(nodes, edges) -> List[str]
    normalize_node_toggles(nodes)          -> (new_nodes, changed_count)
    validate_and_normalize_graph_json(graph_json)
                                           -> (new_graph_json, meta)
    GraphValidationError(Exception)        -> raised on hard rejections
"""
from typing import Any, Dict, List, Tuple


# ── Cycle detection (sequential edges only) ───────────────────────────────

def detect_sequential_cycles(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> List[str]:
    """Run Kahn's algorithm on sequential edges only and report cycles.

    Sequential edges must form a DAG — the runtime executor topological-sorts
    them. Reflection edges are legal back-edges (bounded by max_iterations,
    excluded from the topological sort); delegate edges are also excluded.

    Returns human-readable issue strings that name the offending back-edge so
    a verifier LLM or save-time validator can convert it to
    ``edge_type="reflection"`` (with ``max_iterations`` / ``reflection_prompt``)
    or delete it.
    """
    if not nodes:
        return []

    name_by_id = {n["id"]: (n.get("data", {}) or {}).get("name", n["id"][:8]) for n in nodes}

    # Build adjacency on sequential edges only. Treat missing/empty type as
    # sequential (that's the default when edges come from older payloads).
    seq_edges = [
        e for e in edges
        if (e.get("type") or "sequential") == "sequential"
    ]

    adjacency: Dict[str, List[str]] = {n["id"]: [] for n in nodes}
    in_degree: Dict[str, int] = {n["id"]: 0 for n in nodes}
    for e in seq_edges:
        src, tgt = e.get("source"), e.get("target")
        if src in adjacency and tgt in in_degree:
            adjacency[src].append(tgt)
            in_degree[tgt] += 1

    queue = [nid for nid, d in in_degree.items() if d == 0]
    processed = 0
    while queue:
        nid = queue.pop(0)
        processed += 1
        for tgt in adjacency.get(nid, []):
            in_degree[tgt] -= 1
            if in_degree[tgt] == 0:
                queue.append(tgt)

    if processed == len(nodes):
        return []  # Pure DAG on sequential edges.

    stuck_ids = {nid for nid, d in in_degree.items() if d > 0}
    cycle_names = sorted({name_by_id.get(nid, nid[:8]) for nid in stuck_ids})
    back_edges = [
        f"'{name_by_id.get(e['source'], e['source'][:8])}' → "
        f"'{name_by_id.get(e['target'], e['target'][:8])}'"
        for e in seq_edges
        if e.get("source") in stuck_ids and e.get("target") in stuck_ids
    ]
    if not back_edges:
        back_edges = ["(could not isolate the specific back-edge)"]

    return [
        (
            f"Cycle detected in SEQUENTIAL edges among agents: {cycle_names}. "
            f"Sequential edges involved: {back_edges}. Sequential edges must "
            f"form a DAG — the topological-sort executor will break on a "
            f"cycle. Fix options, in order of preference: "
            f"(1) If this is an iterative-refinement loop, convert ONE "
            f"back-edge to edge_type='reflection' with max_iterations and "
            f"reflection_prompt. "
            f"(2) Otherwise delete the back-edge entirely. "
            f"Do NOT fake a revision loop with a ClassifierAgent branch that "
            f"points back to an earlier agent — that is the same cycle under "
            f"a different name."
        )
    ]


# ── Toggle dependency cascade ─────────────────────────────────────────────

def resolve_toggle_dependencies(args: Dict[str, Any]) -> Dict[str, Any]:
    """Enforce the agent-node toggle dependency chain.

    Semantics:
      - documents              → doc_tool_calling auto-enables
      - doc_aware              → doc_tool_calling auto-enables
      - web_search (non-URL)   → doc_tool_calling auto-enables
      - doc_tool_calling=false → cascade-disable doc_aware, web_search
        (except URL mode), search_method, vector_collections

    URL-mode web search is special: excerpts go straight into the system
    prompt, so it does not need the tool-calling loop and is not gated on
    doc_tool_calling.

    Content fields (web_search_urls, web_search_domains, cache TTL, an
    explicit search_method) are PASSED THROUGH, not reset. This resolver
    runs on every workflow save via the DRF serializers, so resetting them
    here would erase user configuration on each canvas save — and the
    post-save orphan cleanup would then delete the cached per-URL summaries
    too. The invariant: toggle resolution may enforce cross-field
    consistency, but must never discard content it doesn't model. Lists are
    preserved even while web_search is off so a disable/re-enable cycle
    round-trips losslessly.

    Returns a dict with the resolved toggle values. Callers merge it into
    the node's data block.
    """
    # Local import: keeps this module importable without the websearch
    # package being initialised (mirrors workflow_generator's style).
    from .websearch import clean_url_list

    docs_val = args.get("documents") or args.get("doc_tool_calling_documents", [])
    has_docs = bool(docs_val)
    doc_tool_calling = has_docs or args.get("doc_tool_calling", False)
    web_search = args.get("web_search_enabled", False)
    doc_aware = args.get("doc_aware", False)

    ws_mode = (args.get("web_search_mode") or "").lower()
    if web_search and not ws_mode:
        ws_mode = "general"
    ws_needs_tools = web_search and ws_mode != "urls"

    if ws_needs_tools or doc_aware:
        doc_tool_calling = True

    if not doc_tool_calling:
        if not (web_search and ws_mode == "urls"):
            web_search = False
        doc_aware = False

    # Pass-through sanitisation (validate/dedupe/cap, never reset).
    ws_urls, _dropped_invalid, _dropped_over_cap = clean_url_list(
        args.get("web_search_urls") or []
    )
    seen_domains = set()
    ws_domains = []
    for d in (args.get("web_search_domains") or []):
        if not isinstance(d, str):
            continue
        d = d.strip()
        if d and d not in seen_domains:
            seen_domains.add(d)
            ws_domains.append(d)

    cache_ttl = args.get("web_search_cache_ttl")
    if not isinstance(cache_ttl, int) or cache_ttl < 0:
        cache_ttl = 2592000 if web_search else 0
    cache_ttl = min(cache_ttl, 365 * 86400)

    return {
        "doc_tool_calling": doc_tool_calling,
        "doc_tool_calling_documents": docs_val,
        "plan_mode": args.get("plan_mode", True) if doc_tool_calling else False,
        "doc_aware": doc_aware,
        "search_method": (args.get("search_method") or "hybrid_search") if doc_aware else "",
        "vector_collections": (args.get("vector_collections") or ["project_documents"]) if doc_aware else [],
        "web_search_enabled": web_search,
        "web_search_mode": (ws_mode if ws_mode else "general") if web_search else "",
        "web_search_cache_ttl": cache_ttl,
        "web_search_max_results": min(max(args.get("web_search_max_results", 5), 1), 20) if web_search else 0,
        "web_search_top_k": min(max(args.get("web_search_top_k", 5), 1), 20) if web_search else 0,
        "web_search_urls": ws_urls,
        "web_search_domains": ws_domains,
    }


# ── Classifier source_handle integrity ────────────────────────────────────

def validate_classifier_handles(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> List[str]:
    """For every edge originating at a ClassifierAgent, confirm that any
    ``source_handle`` it carries resolves to an existing ``category.id`` on
    the source node.

    A source_handle that does NOT match any current category UUID indicates
    the classifier's categories were rewritten without preserving the
    original UUIDs (or the handle is stale from a removed category). The
    runtime would fall back to positional remapping in workflow_executor.py
    (silently wrong branch). Surface as a hard error at save time so the
    user can re-wire the edge explicitly.

    Missing ``source_handle`` is NOT an error here — the runtime auto-
    backfills missing handles positionally, which is fine for new classifier
    branches that have not yet been wired in the canvas.
    """
    issues: List[str] = []
    classifier_cats: Dict[str, set] = {}
    for n in nodes:
        if n.get("type") != "ClassifierAgent":
            continue
        cats = (n.get("data") or {}).get("categories") or []
        classifier_cats[n.get("id")] = {
            c.get("id") for c in cats if c.get("id")
        }
    if not classifier_cats:
        return issues

    name_by_id = {n["id"]: (n.get("data") or {}).get("name", n["id"][:8]) for n in nodes}
    for e in edges:
        src = e.get("source")
        if src not in classifier_cats:
            continue
        handle = e.get("source_handle")
        if not handle:
            continue  # Runtime backfills positionally — not a hard error.
        if handle in classifier_cats[src]:
            continue
        issues.append(
            f"Classifier edge from '{name_by_id.get(src, src)}' carries "
            f"source_handle='{handle}' which does not match any current "
            f"category UUID on that classifier. The category was likely "
            f"rewritten or removed without preserving its UUID. Re-wire "
            f"the edge from the canvas so it points to a real category, "
            f"then save again."
        )
    return issues


# ── Toggle normalisation across all nodes ─────────────────────────────────

# Node types whose ``data`` block participates in the doc_tool_calling /
# web_search toggle cascade. Static/router nodes are excluded because they
# don't run the tool-calling loop.
_TOGGLE_GATED_NODE_TYPES = (
    "AssistantAgent",
    "DelegateAgent",
    "UserProxyAgent",
    "GroupChatManager",
)


def normalize_node_toggles(
    nodes: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    """Apply ``resolve_toggle_dependencies`` to every gated node's data block.

    Returns ``(new_nodes, changed_count)`` — a copy of the nodes list where
    every gated node's toggle fields have been normalised, plus a count of
    how many nodes actually changed. Untouched nodes are passed through by
    reference; changed nodes are shallow-copied with a new ``data`` dict.
    """
    changed = 0
    out: List[Dict[str, Any]] = []
    for n in nodes:
        if n.get("type") not in _TOGGLE_GATED_NODE_TYPES:
            out.append(n)
            continue
        data = n.get("data") or {}
        resolved = resolve_toggle_dependencies(data)
        if any(data.get(k) != v for k, v in resolved.items()):
            new_data = dict(data)
            new_data.update(resolved)
            new_n = dict(n)
            new_n["data"] = new_data
            out.append(new_n)
            changed += 1
        else:
            out.append(n)
    return out, changed


# ── Combined save-time entry point ────────────────────────────────────────

class GraphValidationError(Exception):
    """Raised when graph_json contains a structural defect that must be
    rejected at save time."""

    def __init__(self, issues: List[str]):
        self.issues = list(issues)
        super().__init__("; ".join(issues))


def validate_and_normalize_graph_json(
    graph_json: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Run all save-time invariants on a graph_json dict.

    Returns ``(possibly modified graph_json, metadata)`` where metadata is
    suitable for logging:
        {"normalized_nodes": int}

    Raises ``GraphValidationError`` on hard rejections (cycles, bad
    classifier handles). Toggle inconsistencies are normalised silently
    rather than rejected — they're the canvas's implicit intent.
    """
    nodes = graph_json.get("nodes") or []
    edges = graph_json.get("edges") or []

    hard_issues: List[str] = []
    hard_issues.extend(detect_sequential_cycles(nodes, edges))
    hard_issues.extend(validate_classifier_handles(nodes, edges))
    if hard_issues:
        raise GraphValidationError(hard_issues)

    normalized_nodes, changed = normalize_node_toggles(nodes)
    new_graph = dict(graph_json)
    new_graph["nodes"] = normalized_nodes

    return new_graph, {"normalized_nodes": changed}
