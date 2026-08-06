# Architecture

**Audience:** engineers working on the platform.
**Method:** every statement here was derived by reading the code, not from prior documentation. Where the code contradicts a reasonable expectation, this document says so and points at the file.

---

## 1. What the system is

IntelliDoc is a Django + SvelteKit platform for building and deploying multi-agent LLM workflows over a project's documents and web sources. An operator creates a **project**, uploads documents, designs a **workflow** on a visual canvas, and can then publish that workflow as an embeddable public chatbot.

### Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.13 |
| Backend | Django ≥5.2, Django REST Framework ≥3.15 |
| Database | PostgreSQL 15 |
| Vector DB | Milvus 2.6 |
| Cache | Redis 7 (Django cache backend; **not** a task broker) |
| Frontend | SvelteKit 2, Svelte 5, TypeScript, Tailwind 3, Vite 6, `adapter-node` |
| Auth | JWT (SimpleJWT) bearer tokens |
| Embeddings | `all-MiniLM-L6-v2`, 384 dimensions, SentenceTransformers |
| Real-time | **Server-Sent Events** (see §7) |

**Not used, despite being present in `requirements.txt`:**

- **Celery** — there is no `core/celery.py`, no `CELERY_*` setting, no worker service, and zero `.delay()`/`.apply_async()` calls. `SimulationRun.celery_task_id` is residue. Background work is done with `threading` instead.
- **Django Channels / WebSockets** — `channels` is not in `INSTALLED_APPS`, `core/asgi.py` is plain `get_asgi_application()`, and no `routing.py` exists anywhere. `agent_orchestration/consumers.py` is dead code and the frontend's `workflowWebSocket.ts` can never connect.

---

## 2. Django apps

| App | Responsibility | Models |
|---|---|---|
| `users` | Data-model app only — no views, no urls. Holds the custom `User` plus ~30 models (projects, documents, workflows, executions, evaluations, keys, metrics). | 30 |
| `api` | Auth (register/reset/change password), user & group admin, dashboard icons, permissions, and `UniversalProjectViewSet` — the real project/document/workflow surface. | 0 |
| `agent_orchestration` | The largest app: workflow engine, DocAware RAG, web search, LLM provider abstraction, human-in-the-loop, evaluation, AI workflow generation, and public deployment. | 7 |
| `vector_search` | Milvus ingestion: parsing, chunking, embedding, per-project collections, summarization. | 0 |
| `templates` | Filesystem-based project-template registry (scans `template_definitions/*/definition.py`). | 1 |
| `llm_eval` | Side-by-side multi-provider LLM comparison + shared model catalogue. | 0 |
| `project_api_keys` | Per-project encrypted BYO provider keys. | 0 |
| `mcp_servers` | Per-project encrypted MCP credentials. | 0 |
| `django_milvus_search` | Vendored Milvus client library. | 0 |

Note that most models live in `users` even when the behaviour lives elsewhere — e.g. `AgentWorkflow` is in `users.models` but is operated on entirely by `agent_orchestration`.

---

## 3. Domain model

### `IntelliDocProject` — the central aggregate

Almost everything is owned by a project. Its external identity is `project_id` (UUID), which appears in every URL. A project is created by **cloning a filesystem template**: the template's configuration (navigation pages, capabilities, validation rules, UI config, instructions) is copied into the project row, so the project is thereafter independent of the template files.

Two behavioural toggles matter:

- `rag_enabled` (default `True`) — when false, document processing only generates summaries and **all DocAware searches return empty**, regardless of per-agent flags.
- `preserve_original_folder_structure` (default `False`) — LLM-driven folder organization instead of filename/path classification.

Access is decided by `has_user_access(user)`: creator, superuser, `role == ADMIN`, a direct `UserProjectPermission`, or a `GroupProjectPermission`.

Owned directly by a project:

- **`ProjectDocument`** — unique per `(project, original_filename)`. Optionally has one `ProjectDocumentSummary` (long/short summaries, plus `memory` and `citation` JSON), one `ProjectDocumentFolderOrganization`, and one `DocumentVectorStatus`, which owns many `DocumentChunk`s.
- **`ProjectVectorCollection`** — one per project; `collection_name` is derived deterministically from name + UUID.
- **`ProjectAPIKey`** — at most one per provider (`openai`/`google`/`anthropic`), encrypted with a per-project-derived key.
- **`MCPServerCredential`** — at most one per server type.
- **`WebSearchUrlSummary`** — unique per `(project, url)`; the short summary becomes a per-URL LLM tool description.
- **`ExperimentMetric`** — a schema-less metrics sink keyed by `experiment_type`.
- **`AgentWorkflow`** — unique per `(project, name)`.

### `AgentWorkflow`

The entire workflow definition is the `graph_json` blob; relational structure stops at the workflow row. Three execution lineages hang off it:

1. **`WorkflowExecution` → `WorkflowExecutionMessage`** — the live path. `execution_id` is a *string* business key.
2. **`SimulationRun` → `AgentMessage`** — the legacy Celery path, now dormant.
3. **`WorkflowEvaluation` → `WorkflowEvaluationResult`** — CSV batch scoring (ROUGE-1/2/L, BLEU, BERTScore, semantic similarity).

### Deployment

`WorkflowDeployment` (in `agent_orchestration`) belongs to a project and nullably to a workflow. A partial unique constraint allows many inactive deployments but **only one active per project**. It owns `WorkflowAllowedOrigin` (CORS + per-origin rate limits), `WorkflowDeploymentRequest` (audit), `DeploymentPublicLoginAttempt`, and `DeploymentSession` — which holds the whole conversation as a JSON list and owns `DeploymentSessionFile` and `DeploymentExecution`.

### `public_chatbot` — removed

This app was removed on 2026-08-05 along with its ChromaDB backend. It provided an
unauthenticated Q&A API over an admin-curated knowledge base and had **zero foreign
keys** to any other app, which is why it could be removed without touching anything
else. Its ChromaDB volume was already empty when it was removed, so the feature was
non-functional in any case, and it had served no traffic since 2026-01-20.

The package, its four PostgreSQL tables and its `django_migrations` rows have all been
deleted. Everything was exported first to `backup/chromadb-removal-2026-08-05/` — 30
curated knowledge documents, 1,257 request records and 692 IP-usage rows — as a SQL
dump, a Django fixture and a JSON export, so the feature can be reconstructed if needed.


### Soft references

These are strings, not enforced FKs: `WorkflowEvaluationResult.execution_id`, `ExperimentMetric.execution_id`/`evaluation_id`, `DeploymentSession.paused_execution_id`, `AgentMessage.parent_message_id`.

---

## 4. `graph_json` — the workflow format

```json
{ "nodes": [ { "id": "...", "type": "...", "position": {...}, "data": {...} } ],
  "edges": [ { "source": "...", "target": "...", "type": "sequential" } ] }
```

**Node fields the backend reads:** `id`, `type` (the dispatch key), `data`. `position` is required by the create serializer but **never read by any backend module** — it is purely for the canvas.

**Edge fields the backend reads:** `source`, `target`, `type`, `source_handle`, and `data.max_iterations` / `data.reflection_prompt` (reflection only).

**Edge fields the frontend writes but the backend ignores entirely:** `label`, `description`, `condition`, `priority`, `retryCount`, `timeout`, `category_name`, and top-level duplicates of `max_iterations`/`reflection_prompt`. These round-trip but are inert.

Only three edge `type` values are meaningful — `sequential` (**the default when absent or empty**), `reflection`, and `delegate`. Values like `conditional`, `parallel` and `group_chat` appear in some validators and model properties but are neither produced by the canvas nor consumed by the executor.

---

## 5. Node types

Nine types exist. The authoritative list is the dispatch chain in `WorkflowExecutor.execute_workflow`; the canvas palette matches it exactly.

| Type | Purpose | Key `data` fields |
|---|---|---|
| `StartNode` | Seeds `conversation_history` with `prompt`. | `prompt` |
| `AssistantAgent` | Standard LLM agent; optional DocAware RAG, web search, document tool-calling, reflection. | `name`, `system_message`, `llm_provider`, `llm_model`, `temperature`, `doc_aware`, `search_method`, `content_filters`, `web_search_*`, `doc_tool_calling*`, `file_attachment*` |
| `UserProxyAgent` | Human-in-the-loop gate. | `require_human_input` (**default `True`**), `input_mode` (`user`/`admin`), `description` (used as the modal title) |
| `GroupChatManager` | Tool-based delegation to `DelegateAgent`s over `delegate` edges. | `name`, `system_message`, LLM fields |
| `DelegateAgent` | Specialist invoked by a GCM. Its `description` is what the GCM's tool schema advertises. | `name`, `description`, `system_message`, LLM fields |
| `ClassifierAgent` | Forced single-category selection, then prunes unchosen branches. Pass-through: emits its input unchanged. | `categories` (≥2, each `{id, name, description}`), LLM fields. **Its system prompt is auto-generated and not user-editable.** |
| `SplitterAgent` | One forced `allocate_subtasks` call producing per-agent subtasks, then prunes unallocated branches. | `overlap_allowed`, `system_message` (**the operator routing policy**, capped 8000 chars), LLM fields. Slots are not configured on the node — each outgoing edge's target agent *is* a slot, described by its own `name` + `system_message` (first 2000 chars). |
| `MCPServer` | Calls an MCP tool. | `server_type` (**required**), `selected_tools` |
| `EndNode` | Terminal marker. | `message` |

Legacy type names with no executor branch (`DocumentAnalyzerAgent`, `HierarchicalProcessorAgent`, `CategoryClassifierAgent`, `ContentReconstructorAgent`, `FunctionTool`) appear in some template definitions and validators. They do nothing.

---

## 6. Execution

`WorkflowExecutor.execute_workflow(workflow, executed_by, deployment_context=None, event_callback=None)`.

1. **Parse** — `parse_workflow_graph` does a Kahn topological sort over `sequential` edges. `delegate` edges never create dependencies; `reflection` edges create one only into a human-input `UserProxyAgent`. `DelegateAgent`s whose every incoming edge is `delegate` are excluded from the main sequence. All `EndNode`s are moved to the tail.
2. **Create the `WorkflowExecution` row immediately** with `status=RUNNING`, so a pause has something to attach to.
3. **Run the StartNode**, seeding `conversation_history`.
4. **Loop**: `_find_ready_nodes` returns nodes whose dependencies are all present in `executed_nodes`. One ready node → sequential execution; several → `asyncio.gather`. Routers (`ClassifierAgent`, `SplitterAgent`) are deliberately **serialized** — only the first is returned per round — so pruning completes before the next readiness computation.
5. **Finish** — update stats with `save(update_fields=[...])` (a full-row save would clobber canvas edits made during the run), merge messages, write `WorkflowExecutionMessage` rows, emit an `ExperimentMetric`.

### Two output channels

- **`executed_nodes: {node_id → value}`** — the structural channel. A value is a plain string, or `{"text": ..., "citations": [...]}` when citations exist, or the splitter's `{"__kind__": "splitter", "__per_target__": {...}}`, or the skip sentinel.
- **`conversation_history`** — one flat string that agents append to. Classifier and Splitter deliberately append nothing (pure routers).

Which channel an agent receives depends on its input count: **more than one input** → inputs are aggregated (with citations renumbered globally to avoid `[1]` collisions); **one or zero inputs** → the agent receives the whole flat `conversation_history` and its upstream node's actual output is ignored.

> **Consequence worth knowing:** a Splitter's downstream agent normally has exactly one input, so it takes the single-input path and receives `conversation_history` — which the Splitter never writes to. The allocated subtask is therefore dropped unless the target has multiple inputs or is reached via a `GroupChatManager`.

### Branch pruning

Both routers use one mechanism: the sentinel string `__CLASSIFIER_BRANCH_SKIPPED__` is written into `executed_nodes[skipped_id]`, which makes the node look "done" to the readiness check and makes aggregation drop it as an input.

Pruning then iterates to a fixpoint: a node is skipped only if **every** incoming edge is either a pruned router edge or comes from an already-skipped node. This is join-safe — one live path keeps a node alive. Classifier pruning keys on `source_handle` (the category UUID); Splitter pruning keys on target id.

### Human-in-the-loop

There is **no paused status in the database.** A paused execution stays `RUNNING` with `human_input_required=True`; `human_input_agent_id` (the node id) is the authoritative resume key. `'awaiting_human_input'` exists only as an API-level string.

Resume rebuilds the executor and calls `continue_workflow_execution`, which is a **near-duplicate of the main loop** with important differences: no parallelism, no `_find_ready_nodes`, and it handles only a subset of node types — a `SplitterAgent` or `MCPServer` encountered after a pause is silently skipped.

### LLM provider selection

Per-node, from flat `data` keys. Providers: `openai`, `anthropic`, `google`. Defaults differ by path — agents default to `openai`/`gpt-3.5-turbo`, Classifier to `anthropic`/`claude-3-5-haiku-20241022`, Splitter to `openai`/`gpt-4o-mini`.

**API keys come only from per-project encrypted `ProjectAPIKey` rows. There is no environment-variable fallback on the workflow path** — a project with no key configured cannot execute any LLM node, and the failure surfaces as "check project API key configuration".

Known quirks: node-level `max_tokens` is inert on the main path; `temperature: 0` is silently coerced to `0.7` (`or 0.7`); the provider aliases `'claude'` and `'gemini'` reach class selection but always fail the key lookup, because `ProjectAPIKey.provider_type` only allows `openai`/`google`/`anthropic`.

### Validation

The live enforcement is `graph_invariants.validate_and_normalize_graph_json`, wired into the serializers' `validate_graph_json` and applied on **create and update**. It enforces two hard rules and one normalization:

1. **Sequential edges must form a DAG.** `reflection` and `delegate` are legal back-edges.
2. **Classifier `source_handle` integrity** — a *present* handle must match a current category id; a missing one is backfilled at runtime.
3. **Toggle cascade normalization** — documents imply `doc_tool_calling`; disabling `doc_tool_calling` cascades to `doc_aware` and web search (URL mode exempt). Content fields such as `web_search_urls` are sanitized but **never reset** — a regression test pins this, because an earlier version wiped configured URL lists on every canvas save.

Bypasses that write `graph_json` with no invariant check: workflow import, the doc-aware cascade, document-reference cleanup, and the in-memory StartNode prompt swaps used by deployment and evaluation.

Three other validators exist and disagree with each other. `agent_orchestration/validation.py` (386 lines) is **entirely dead code** and would reject legal reflection back-edges. `schemas/workflow_validator.py` *is* reachable but its node-type enum lists ten types the executor does not implement. The `validate` API action is a third, simpler checker with no cycle detection.

---

## 7. Real-time: SSE, not WebSockets

There is one streaming endpoint, Server-Sent Events over `StreamingHttpResponse`, both emitting `data: {json}\n\n` frames whose discriminator is a JSON `type` key:

- `POST /api/workflow-deploy/<project_id>/stream/`

The deployment stream returns **HTTP 200 always** — errors, including auth failures, are delivered in-band as an `error` frame. Frame types include `connected`, `thinking`, `content`, `citations`, `agent_started`, `planning`, `delegate_*`, `tool_result`, `splitter_decision`, `classifier_decision`, `awaiting_human_input`, `error`, and `done`. **Clients must prefer the `content` and `citations` in the final `done` frame**, because citation reconciliation can renumber markers after streaming has begun.

Streaming is only active when an `event_callback` is supplied *and* the target node is the single resolved final-response node (one `EndNode`, one predecessor, that predecessor an `AssistantAgent` with no outgoing reflection edge). The canvas test-run and the evaluation harness never stream.

There is no heartbeat/keep-alive on the deployment stream.

---

## 8. Retrieval

### Document ingestion

Upload → `ProjectDocument` row → `process_documents` starts a **background thread** (not Celery).

- **Parsing**: PDF via Gemini (only when the project's provider is Google) falling back to pdfplumber then PyPDF2; `.docx`/`.doc` via python-docx; `.txt`/`.md`/`.rtf` read raw (no RTF markup stripping). `.odt` is advertised but has no handler. No spreadsheet support.
- **Chunking**: `max_chunk_size = 35000` **characters**, split on paragraph boundaries, then sentences. **Overlap is zero** — there is no sliding window. Content is truncated to 60,000 chars at insert.
- **Embedding**: `all-MiniLM-L6-v2`, 384-dim, normalized, batch size 32.
- **Storage**: one Milvus collection per project, `IVF_FLAT` / inner-product / `nlist=1024`. No partitions — isolation is one collection per project.

### DocAware search methods

Seven, all implemented, exposed by `GET /api/agent-orchestration/docaware/search_methods/`: `semantic_search`, `hybrid_search` (**the default**), `keyword_search`, `contextual_search`, `similarity_threshold`, `multi_collection`, `hierarchical_search`.

Caveats that matter when reading results:

- **`index_type` has no runtime effect.** The search layer forwards only `metric_type`, so AUTOINDEX/HNSW/IVF_FLAT selections are cosmetic.
- **`metric_type` is also effectively ignored** — every method overrides it with the collection's actual index metric.
- **`source` is `"Unknown"` for six of the seven methods** and **`page` is always `1`**, because the Milvus schema has no `source` or `page` field. Only `hybrid_search` maps `file_name` into `source`.
- `keyword_search` advertises BM25 but performs a vector search followed by keyword rescoring.
- `hierarchical_search` filters on chunk types (`paragraph`, `chapter`, …) that ingestion never writes; only `section` can match.
- `multi_collection` accepts only the project's own collection — cross-project requests are rejected as an access attempt.

### Per-agent document scoping

`content_filters` is a list of strings with a tiny grammar: `folder_<path>` → `hierarchical_path like '<path>%'`, `file_<document_id>` → `document_id == '<id>'`. Multiple filters are OR-ed, then AND-ed with the method's own filter.

### Web search

Three modes: `general`, `domains` (both DuckDuckGo), and `urls`.

URL mode fetches pages, extracts content, chunks per section (max 2000 chars), embeds, indexes into a per-project `websearch_*` Milvus collection, then retrieves top-k. Extraction is format-adaptive: primary DOM traversal, then — only if the result is thin — JSON-LD, framework hydration state (`__NEXT_DATA__`, `__NUXT__`, …), `<noscript>`, and text-density scoring, and finally a `text/markdown` alternate (`rel="alternate"` or the `llms.txt` `<page>.md` convention). Pages that still yield nothing are flagged non-fatally via `quality_warning`; nothing raises.

Redis caching has several tiers, checked in order: Milvus index flag → content hash → chunk embeddings → cold fetch. Failed fetches get a short 300s TTL so a transient timeout cannot blank a URL for the full content TTL. The default agent-level content TTL is 30 days.

### Citations

The LLM emits a JSON array between `---CITATIONS---` and `---END_CITATIONS---`. **Numbering from the LLM is never trusted** — it is always recomputed from order-of-first-appearance of `[N]` in the final text, using a two-pass placeholder swap so rewrites cannot collide. Cross-agent aggregation renumbers globally, and a final `reconcile_citations` pass strips markers with no backing object, renumbers survivors consecutively, and drops unreferenced objects.

URL-mode agents bypass the tool loop, so their citations are built programmatically from the numbered prompt sources rather than parsed from the model output.

---

## 9. Frontend

SvelteKit 2 / Svelte 5, `adapter-node`, Tailwind 3, Vite 6. The Vite dev server proxies `/api` to `BACKEND_URL` (default `http://127.0.0.1:8000`) and routes HMR through nginx when accessed over HTTPS.

Key routes: `/login`, `/features/intellidoc` (project list), `/features/intellidoc/project/[id]` (the main workspace), `/features/llm-eval`, `/chat/[project_id]`, and an `/admin/*` section for users, groups, icons, and permissions.

The five components that matter most, by size:

| Component | LOC | Role |
|---|---|---|
| `NodePropertiesPanel.svelte` | 3,452 | Per-node configuration form; emits `nodeUpdate` |
| `WorkflowDesigner.svelte` | 3,248 | The canvas — nodes, edges, pan/zoom, autosave |
| `AgentOrchestrationInterface.svelte` | 1,744 | Workflow list, tab shell, execution controls |
| `WorkflowDeployment.svelte` | 1,084 | Deployment settings, branding, public URL, origins |
| `WorkflowEvaluation.svelte` | 1,011 | CSV upload and metric display |

Stores: `auth.ts` (JWT), `workflowStore.ts`, `workflowStatus.ts`, `llmModelsStore.ts`, `toast.ts`. API layer: `api.ts` (axios, token refresh) and `cleanUniversalApi.ts` (fetch-based, used by the newer surfaces).

**Canvas autosave**: every manual mutation routes through a single debounced `markDirtyAndSave()` (≈400 ms), which PATCHes the whole graph. A queued-retry flag ensures an edit arriving during an in-flight save is not dropped.

`workflowWebSocket.ts` exists and is imported by `WorkflowHistory.svelte`, but the backend has no WebSocket support — that path cannot connect.

---

## 10. Where to look next

- Deployment, configuration, ports, persistence → [`docs/DEPLOYMENT.md`](DEPLOYMENT.md)
- Complete endpoint reference → [`docs/API.md`](API.md)
- Verified defects and dead code → [`docs/KNOWN_ISSUES.md`](KNOWN_ISSUES.md)
- GroupChatManager delegation → [`backend/agent_orchestration/parallelization_analysis.md`](../backend/agent_orchestration/parallelization_analysis.md)
