# Gap Analysis: Project Description vs. Codebase

This document compares the described AICC-IntelliDoc behavior with the actual implementation. Findings are grouped by feature area with location, expected vs. actual, severity, and recommended fix.

---

## 1. Overview / Document Processing

### 1.1 Legacy processing/status endpoints lack project access check

| Field | Detail |
|-------|--------|
| **Location** | `backend/vector_search/consolidated_api_views.py`: `process_unified_consolidated` (lines 69–180), `get_vector_status_consolidated` (lines 354–479) |
| **Expected** | Only the project owner or authorized users can start processing or read vector status for a project. |
| **Actual** | Both functions use `get_object_or_404(IntelliDocProject, project_id=project_id)` with no `has_user_access(request.user)` check. Any authenticated user can POST to the legacy `digest/` or GET the legacy `vector-status/` for any project by UUID. The ViewSet actions (`process_documents`, `vector_status`) do enforce access via `get_object()`; the legacy paths do not. |
| **Severity** | **High** |
| **Recommended fix** | In `process_unified_consolidated` and `get_vector_status_consolidated`, after loading the project, add: `if not project.has_user_access(request.user): return Response(..., status=403)`. Alternatively, remove or deprecate the legacy routes and route all traffic through the ViewSet. |

### 1.2 DocAware “search method not implemented” fallback

| Field | Detail |
|-------|--------|
| **Location** | `backend/agent_orchestration/docaware/service.py` lines 125–127 |
| **Expected** | All configured DocAware search methods are implemented. |
| **Actual** | If an unknown or unsupported `search_method` is passed (e.g. a new enum value without a branch), the code logs a warning and returns `[]`. All current `SearchMethod` enum values have branches; this is a defensive else. |
| **Severity** | **Low** |
| **Recommended fix** | No change required for current enums. If adding new search methods, add a corresponding `elif` branch and a test; consider raising a clear error for unknown methods in development. |

### 1.3 Processing status response shape

| Field | Detail |
|-------|--------|
| **Location** | `backend/vector_search/consolidated_api_views.py` lines 458–472 (response structure); `frontend/.../project/[id]/+page.svelte` lines 395–421, 915–926 |
| **Expected** | Frontend and backend agree on status fields (e.g. `vector_status.is_processing`, `processing_status`, `ready_documents`, `total_documents`). |
| **Actual** | Backend returns `vector_status` with `collection_status`, `processing_status`, `is_processing`, etc. Frontend reads `processingStatus?.vector_status?.is_processing` and `processingStatus?.vector_status?.processing_status || processingStatus?.vector_status?.collection_status`. Fallback is consistent; no mismatch found. |
| **Severity** | N/A (no gap) |

---

## 2. Agent Orchestration (DocAware, WebSearch, File Attachments)

### 2.1 WebSearch cache is per-project

| Field | Detail |
|-------|--------|
| **Location** | `backend/agent_orchestration/websearch/cache_service.py` (all cache key helpers and methods); `backend/agent_orchestration/websearch_handler.py` (e.g. lines 172, 191, 224, 237, 263, 276) |
| **Expected** | WebSearch caching is per-project so one project does not see another’s cache. |
| **Actual** | All cache methods take `project_id` and use it in key construction (`_make_url_cache_key`, `_make_search_cache_key`). Handler passes `project_id` into every cache call. |
| **Severity** | N/A (no gap) |

### 2.2 DocAware content filter expression for “file_” prefix

| Field | Detail |
|-------|--------|
| **Location** | `backend/agent_orchestration/docaware/service.py` lines 256–328 (`_build_content_filter_expression`) |
| **Expected** | Content filters for specific files (e.g. `file_<id>`) produce a valid Milvus filter so only those documents are searched. |
| **Actual** | Code handles `folder_*` (path prefix). For `file_*` the snippet shown builds a filter; full logic for document_id and escaping should be verified against Milvus schema and any edge cases (e.g. empty or invalid id). |
| **Severity** | **Low** |
| **Recommended fix** | Review the `file_` branch (and any `document_id` handling) for correctness and add a unit test for content_filter → filter_expression. |

### 2.3 File attachment preparation errors

| Field | Detail |
|-------|--------|
| **Location** | `backend/agent_orchestration/docaware_handler.py` lines 22–38 (`FileAttachmentPreparationError`), and call sites that use file attachments |
| **Expected** | When file refs cannot be prepared (e.g. missing upload for provider), the user sees a clear error and the run does not silently proceed with wrong/missing files. |
| **Actual** | `FileAttachmentPreparationError` exists and is raised; call sites (e.g. chat manager / deployment executor) should catch it and return a clear error to the user. Not fully traced here. |
| **Severity** | **Medium** |
| **Recommended fix** | Ensure all code paths that call file-attachment preparation catch `FileAttachmentPreparationError` and return a user-facing error (and do not send request to LLM with missing refs). |

---

## 3. Evaluation

### 3.1 Evaluation backend and similarity scores

| Field | Detail |
|-------|--------|
| **Location** | `backend/agent_orchestration/workflow_views.py` (e.g. `evaluate` around line 848); `frontend/.../WorkflowEvaluation.svelte` |
| **Expected** | User can upload a dataset, run the workflow, and see evaluation outputs with similarity scores. |
| **Actual** | Backend has `evaluate` action; frontend loads workflows, supports CSV upload, and calls evaluation APIs. Similarity scoring logic may live in workflow_views or a dedicated evaluation module; not fully traced. |
| **Severity** | **Low** (assumed implemented; no stub found) |
| **Recommended fix** | If “similarity scores” are not yet computed or displayed, add a small spec and implement scoring + UI display. |

---

## 4. Deploy (Session Handling, Human Input, Limitations)

### 4.1 Session persistence on chat failure (non-stream)

| Field | Detail |
|-------|--------|
| **Location** | `backend/agent_orchestration/deployment_views.py` lines 805–810 (append user message), 882–907 (exception path), 930–947 (background save) |
| **Expected** | If a chat turn fails (workflow error, no response, or awaiting human input), the user message is still saved to the session. |
| **Actual** | User message is appended to `conversation_history` before execution. On exception, `_save_deployment_data_async` is called with that `conversation_history`, so the user message is persisted. On success/awaiting_human_input/error, background save again receives the updated `conversation_history`. Behavior matches description. |
| **Severity** | N/A (no gap) |

### 4.2 Session persistence on stream failure

| Field | Detail |
|-------|--------|
| **Location** | `backend/agent_orchestration/deployment_views.py` lines 1095–1099 (append user), 1139–1160 (exception during execution), 1164–1203 (awaiting_human_input / non-success), 1208–1227 (no response) |
| **Expected** | Same as non-stream: user message is not lost when the stream turn fails. |
| **Actual** | User message is appended before execution. On workflow exception or non-success result, a background thread calls `_save_deployment_data_async` with the current `conversation_history`, so the user message is saved. |
| **Severity** | N/A (no gap) |

### 4.3 Human input persisted when resume fails

| Field | Detail |
|-------|--------|
| **Location** | `backend/agent_orchestration/deployment_views.py` lines 1450–1466 (append in thread), 1515–1531 (main request: if resume failed and thread did not append, append and save) |
| **Expected** | If submit-input resume fails (e.g. execution not found or wrong state), the human input message is still stored in the session. |
| **Actual** | Background thread appends human input before resuming. If the thread raises before that (e.g. execution not found), `appended_input` stays False and the main request appends the human input and saves (1517–1528). Matches description. |
| **Severity** | N/A (no gap) |

### 4.4 No user file upload in embed chat

| Field | Detail |
|-------|--------|
| **Location** | `backend/agent_orchestration/deployment_views.py` (public_chat_endpoint, public_chat_endpoint_stream): body parsing; `DEPLOYMENT_CHAT_LIMITATIONS.md` |
| **Expected** | Deploy chat API accepts only `user_query` and `session_id`; no end-user file upload. |
| **Actual** | Endpoints parse `user_query` and `session_id` only; no file upload handling. Limitation doc is accurate. |
| **Severity** | N/A (no gap) |

### 4.5 Simulated streaming

| Field | Detail |
|-------|--------|
| **Location** | `backend/agent_orchestration/deployment_views.py` lines 1125–1244 (run to completion, then word-by-word yield with delay) |
| **Expected** | Stream runs workflow to completion then simulates streaming; not token-level LLM streaming. |
| **Actual** | `asyncio.run(executor.execute_deployment_workflow(...))` runs to completion; then words are yielded with `time.sleep(0.02)`. Limitation is accurate. |
| **Severity** | N/A (no gap) |

### 4.6 Concurrent same-session overwrites

| Field | Detail |
|-------|--------|
| **Location** | `backend/agent_orchestration/deployment_views.py` lines 778–780 (comment), 781–790 (get_or_create session); `DEPLOYMENT_CHAT_LIMITATIONS.md` |
| **Expected** | No per-session locking; two requests with the same session_id can overwrite each other (last save wins). |
| **Actual** | Sessions are get_or_create; no locking. Comment and doc state that embed UI should disable send while a request is in flight. Accurate. |
| **Severity** | N/A (no gap) |

### 4.7 Stream endpoint outer exception does not save

| Field | Detail |
|-------|--------|
| **Location** | `backend/agent_orchestration/deployment_views.py` lines 1270–1272 |
| **Expected** | Any failure path should persist the user message when it has already been added to the in-memory list. |
| **Actual** | The outermost `except Exception` (1270–1272) only yields an error. It runs only for exceptions that occur outside the inner try (e.g. before appending the user message, or in very early setup). The user message is appended at 1095–1099; all failure paths after that (rate limit, execution exception, non-success, no response) start a background save. So the only risk is an exception between 1099 and the first place that calls _save_deployment_data_async (e.g. rate limit at 1118 or execution exception at 1140). If an exception occurs in that small window (e.g. “Send thinking indicator”), the user message would not be saved. |
| **Severity** | **Low** |
| **Recommended fix** | In the stream generator, wrap the block from “append user message” through “background save” in a try/except; in the except, call `_save_session_conversation_sync(deployment_session, conversation_history)` before yielding the error, so the user message is never lost. |

---

## 5. Activity Tracker

### 5.1 Activity Tracker URL trailing slash

| Field | Detail |
|-------|--------|
| **Location** | Frontend: `frontend/my-sveltekit-app/src/lib/services/cleanUniversalApi.ts` line 1115. Backend: `backend/agent_orchestration/deployment_urls.py` line 60 (`.../deployment/activity/`) |
| **Expected** | GET request for deployment activity reaches the backend route. |
| **Actual** | Frontend builds `.../deployment/activity` (no trailing slash); backend path is `.../deployment/activity/`. With APPEND_SLASH=True, Django may redirect GET to the slashed URL; behavior may depend on client. |
| **Severity** | **Low** |
| **Recommended fix** | Use a trailing slash in the frontend URL: `.../deployment/activity/?${queryParams}` so it matches the backend exactly and avoids redirects. |

### 5.2 Activity Tracker when deployment has no workflow

| Field | Detail |
|-------|--------|
| **Location** | `frontend/my-sveltekit-app/src/lib/components/DeploymentActivityTracker.svelte` lines 24–26 |
| **Expected** | When there is no deployment or no workflow, the Activity Tracker should not error and should show an empty or explanatory state. |
| **Actual** | `if (!deployment || !deployment.workflow_id) return;` so loadActivity exits without setting an error. UI may show empty list; no explicit “No deployment” message. |
| **Severity** | **Low** |
| **Recommended fix** | Optionally show a short message when `!deployment || !deployment.workflow_id` (e.g. “Deploy a workflow to see activity”). |

---

## 6. Cross-Cutting: Security, Isolation, State

### 6.1 Project access on legacy vector endpoints (duplicate of 1.1)

| Field | Detail |
|-------|--------|
| **Location** | `backend/vector_search/consolidated_api_views.py`: `process_unified_consolidated`, `get_vector_status_consolidated`. Legacy routes in `backend/core/urls.py`: `api/projects/<str:project_id>/digest/`, `api/projects/<str:project_id>/vector-status/`. |
| **Expected** | All project-scoped endpoints enforce project access. |
| **Actual** | Legacy paths call consolidated views directly; those views do not call `project.has_user_access(request.user)`. |
| **Severity** | **High** |
| **Recommended fix** | Same as 1.1: add access check in both consolidated functions or retire legacy routes. |

### 6.2 DocAware multi-collection search (project isolation)

| Field | Detail |
|-------|--------|
| **Location** | `backend/agent_orchestration/docaware/service.py` lines 656–685 |
| **Expected** | Only the project’s own Milvus collection is searchable; cross-project access is blocked. |
| **Actual** | `_multi_collection_search` allows only `"project_documents"` (mapped to `self.collection_name`) or the explicit `self.collection_name`; any other collection is rejected and logged. Matches description. |
| **Severity** | N/A (no gap) |

### 6.3 Frontend state cleared on project switch

| Field | Detail |
|-------|--------|
| **Location** | `frontend/my-sveltekit-app/src/routes/features/intellidoc/project/[id]/+page.svelte` lines 21–74 (reactive block on projectId change) |
| **Expected** | Switching project clears all project-specific state and remounts children so there is no cross-project leakage. |
| **Actual** | Reactive block clears uploadedDocuments, project, processingStatus, deployment, search state, llmConfig, navigation, workflowStore, stops polling, and calls loadProject/loadLLMModels. Child sections are wrapped in `{#key projectId}` so they remount. Matches description. |
| **Severity** | N/A (no gap) |

### 6.4 Parallel Start Processing across projects

| Field | Detail |
|-------|--------|
| **Location** | `backend/vector_search/consolidated_api_views.py`: `PROCESSING_THREADS` keyed by project_id, `run_processing_in_background(project_id, ...)`; `unified_services_fixed.py` uses only that project’s documents and collection. |
| **Expected** | Each project’s “Start Processing” runs independently and in parallel; no shared state between projects. |
| **Actual** | One thread per project; thread is keyed by project_id; processing uses only that project’s documents and collection. Duplicate start for the same project returns 409. Matches description. |
| **Severity** | N/A (no gap) |

### 6.5 Deployment endpoints unauthenticated

| Field | Detail |
|-------|--------|
| **Location** | `backend/agent_orchestration/deployment_urls.py`: public_chat_endpoint, public_chat_endpoint_stream, submit_deployment_human_input; `DEPLOYMENT_CHAT_LIMITATIONS.md` |
| **Expected** | Deploy chat and submit-input are unauthenticated; access controlled by allowed origins and rate limits. |
| **Actual** | Views are function-based with no permission_classes; CORS and rate limiting are applied. Matches description. |
| **Severity** | N/A (no gap) |

---

## 7. Frontend–Backend Contract

### 7.1 process_documents request body

| Field | Detail |
|-------|--------|
| **Location** | Frontend: `cleanUniversalApi.ts` processDocuments (body: llm_provider, llm_model, enable_summary). Backend: `api/universal_project_views.py` process_documents (request.data.get for same keys). |
| **Expected** | Frontend sends the parameters the backend expects. |
| **Actual** | Body and backend keys align. ViewSet route is used (not legacy digest), so project access is enforced. |
| **Severity** | N/A (no gap) |

### 7.2 Vector status URL

| Field | Detail |
|-------|--------|
| **Location** | Frontend: `cleanUniversalApi.ts` getProcessingStatus uses `.../vector-status/`. Backend: legacy path `.../vector-status/` and ViewSet action `vector_status` (underscore). |
| **Expected** | Frontend hits a valid, access-controlled endpoint. |
| **Actual** | Frontend uses hyphenated `vector-status/`, which matches the legacy path in urls.py. That path does not enforce project access (see 1.1). |
| **Severity** | **High** (same as 1.1: legacy path lacks access check) |

---

## 8. Partial Implementations / TODOs (Other)

| Location | What’s there | Severity | Note |
|----------|--------------|----------|------|
| `backend/agent_orchestration/consumers.py` ~172, 180 | WebSocket: pause/resume/stop “not implemented”; execution control not implemented over WebSocket | Low | Documented; deployment uses HTTP submit-input. |
| `frontend/.../WorkflowHistory.svelte` line 67 | “WebSocket updates are not implemented; history is fetched when the panel loads” | Low | Acceptable if history is only on load. |
| `backend/public_chatbot/views.py` line 1039 | `chroma_search_time = 0  # TODO: Calculate from context search` | Low | Public chatbot feature. |
| `backend/mcp_servers/services.py` line 222 | `# TODO: Add actual connection test when MCP clients are implemented` | Low | MCP, not core IntelliDoc. |
| `backend/templates/performance.py` line 66 | `error_count=0  # TODO: Implement error tracking` | Low | Template performance. |
| `backend/templates/management/commands/validate_templates.py` lines 120, 157 | “Automatic security/validation fixes not implemented yet” | Low | Validation command. |

---

## 9. Summary Table

| # | Area | Finding | Severity |
|---|------|---------|----------|
| 1.1 / 6.1 / 7.2 | Document Processing / Security / Contract | Legacy `digest/` and `vector-status/` do not check project access | **High** |
| 2.2 | DocAware | Verify file_ content filter and document_id handling | Low |
| 2.3 | File attachments | Ensure FileAttachmentPreparationError is handled everywhere | Medium |
| 4.7 | Deploy | Stream outer exception could skip saving user message in rare window | Low |
| 5.1 | Activity Tracker | Trailing slash on deployment/activity URL | Low |
| 5.2 | Activity Tracker | Optional “No deployment” message when no workflow | Low |
| 1.2, 3.1, 8 | Various | DocAware else branch, evaluation completeness, TODOs in other modules | Low |

**Recommended priority:** Fix 1.1/6.1 (project access on legacy vector endpoints) first; then 2.3 (file attachment error handling); then 4.7, 5.1, 5.2, and 2.2 as needed.
