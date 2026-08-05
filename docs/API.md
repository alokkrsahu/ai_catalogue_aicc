# API Reference

Derived by following `core/urls.py` and every `include()`/router from it. Endpoints not listed here are not routed.

---

## Conventions

- **Base**: all application endpoints live under `/api/`.
- **Auth**: JWT bearer — `Authorization: Bearer <access_token>`. Obtain via `POST /api/token/`.
- **DRF settings**: `DEFAULT_AUTHENTICATION_CLASSES` is JWT only. There is **no `DEFAULT_PERMISSION_CLASSES`**, so DRF's fallback is `AllowAny` — any view that omits `permission_classes` is unauthenticated. There is no default pagination (list endpoints are unpaginated) and no default renderer override, so **the Browsable API HTML renderer is active on every DRF URL**.
- **Admin**: `IsAdminUser` in this codebase is the project's own class (`api/permissions.py`), which checks `user.role == 'ADMIN'` — not Django's `is_staff`. Note `templates/security_views.py` and some others import DRF's version, so the two semantics coexist.
- **Router lookups** use the regex `[^/.]+`, not typed converters, so router-generated detail routes accept non-UUID strings. Hand-written paths in `core/urls.py` do use `<uuid:...>`.

---

## Authentication and accounts

| Endpoint | Method | Auth | Notes |
|---|---|---|---|
| `/api/token/` | POST | public | `{email, password}` → `{access, refresh}` |
| `/api/token/refresh/` | POST | public | `{refresh}` → `{access}` |
| `/api/register/` | POST | public | `{email, password, password2, first_name, last_name}` → user + both tokens |
| `/api/password-reset/` | POST | public | `{email}` → **returns `uid`, `token` and `reset_url` in the response body**; no email is sent. See KNOWN_ISSUES. |
| `/api/password-reset/confirm/` | POST | public | `{uid, token, new_password}` |
| `/api/change-password/` | POST | authenticated | `{current_password, new_password}` |

JWT lifetimes: access 60 min, refresh 1440 min. `BLACKLIST_AFTER_ROTATION` is set but inert (`token_blacklist` is not installed, and rotation is off).

---

## Users, groups, icons, permissions

Main router at `/api/`. All require authentication; write operations require admin.

| Endpoint | Methods | Notes |
|---|---|---|
| `/api/users/` · `/api/users/{pk}/` | GET, POST, PUT, PATCH, DELETE | admin |
| `/api/users/me/` | GET | authenticated (not admin) |
| `/api/dashboard-icons/` · `/{pk}/` | GET, POST, PUT, PATCH, DELETE | read authenticated, write admin |
| `/api/dashboard-icons/my_icons/` | GET | authenticated |
| `/api/dashboard-icons/choices/` | GET | authenticated (its declared admin requirement is discarded — see KNOWN_ISSUES) |
| `/api/groups/` · `/{pk}/` | GET | admin, read-only |
| `/api/icon-permissions/` · `/{pk}/` | GET, POST, PUT, PATCH, DELETE | admin |
| `/api/icon-permissions/bulk_update/` | POST | admin. `{user_id, icon_ids[]}` — **deletes that user's existing rows first** |
| `/api/icon-permissions/by_user/` | GET | admin. `?user_id=` |
| `/api/group-icon-permissions/…` | as above | admin, `bulk_update` + `by_group` |
| `/api/user-project-permissions/` | GET, POST, … | admin. Body uses the **integer** project pk |
| `/api/user-project-permissions/bulk_update/` | POST | admin. `{project_id: uuid, user_ids[]}` — replaces all |
| `/api/user-project-permissions/by_project/` | GET | admin. `?project_id=<uuid>` |
| `/api/group-project-permissions/…` | GET, POST, … | admin. Has `bulk_update` but **no `by_project`** |

---

## Projects, documents, processing

`UniversalProjectViewSet`, `permission_classes=[IsAuthenticated]`, lookup kwarg `project_id`. Access is enforced by queryset scoping.

| Endpoint | Methods | Notes |
|---|---|---|
| `/api/projects/` | GET | Envelope `{projects[], total_count, …}`, unpaginated |
| `/api/projects/` | POST | **admin gate in the body** (non-admin → 403). Requires `template_id`, `name` |
| `/api/projects/{project_id}/` | GET, PUT, PATCH | update is **authenticated only, no admin gate** |
| `/api/projects/{project_id}/` | DELETE | admin **and** `{"password": …}` in the DELETE body. Returns 200 |
| `/api/projects/health/` | GET | static payload but still requires a JWT |
| `/api/projects/preview_template_clone/` | POST | `{template_id}` |
| `/api/projects/{project_id}/documents/` | GET | includes `download_url` and per-provider `llm_upload_status` |
| `/api/projects/{project_id}/upload_document/` | POST (multipart) | field `file`. Duplicate filename → **409**. No size/MIME validation |
| `/api/projects/{project_id}/upload_bulk_files/` | POST (multipart) | any field names; per-file result buckets |
| `/api/projects/{project_id}/upload_zip_file/` | POST (multipart) | `.zip`; extracts `.pdf .doc .docx .txt .md .rtf` |
| `/api/projects/{project_id}/documents/{document_id}/download/` | GET | `FileResponse`, inline disposition |
| `/api/projects/{project_id}/documents/{document_id}/summary/` | GET | requires canonical UUIDs (explicit route wins over the router twin) |
| `/api/projects/{project_id}/documents/upload-to-llm/` | POST | `{document_ids?, providers?}` |
| `/api/projects/{project_id}/process_documents/` | POST | `{llm_provider, llm_model, enable_summary}`; runs in a background thread |
| `/api/projects/{project_id}/vector_status/` | GET | |
| `/api/projects/{project_id}/rag-setting/` | **PATCH** | `{rag_enabled}`. Turning it off cascades `doc_aware=False` across every workflow |
| `/api/projects/{project_id}/folder-structure-setting/` | **PATCH** | `{preserve_original_folder_structure}` |
| `/api/projects/{project_id}/bulk_delete_documents/` | **DELETE with body** | `{document_ids[]}` |
| `/api/projects/{project_id}/delete_document/` | DELETE | id from body or `?document_id=` |
| `/api/projects/{project_id}/experiment-metrics/` | GET | `?execution_id=`, `?evaluation_id=` |
| `/api/projects/{project_id}/recent-executions/` | GET | `?limit=` (default 50, max 200) |
| `/api/projects/{project_id}/analytics/` | GET | planning time, tool breakdown, websearch, cache tiers, volume, wordcloud |
| `/api/projects/{project_id}/agent_workflows/` | GET, POST | POST validated by the schema validator |
| `/api/projects/{project_id}/agent_workflow/` | GET, PUT, DELETE | target from **`?workflow_id=`**, not the path. This is the only working workflow-delete path |

### Legacy aliases (declared before the router, so they win)

| Endpoint | Method | Notes |
|---|---|---|
| `/api/projects/{project_id}/search/` | POST | `{query, limit, filters, search_type}` |
| `/api/projects/{project_id}/vector-status/` | GET | hyphenated variant |
| `/api/projects/{project_id}/capabilities/` | GET | |
| `/api/projects/{project_id}/digest/` | ANY | **broken** — see KNOWN_ISSUES |

### Vector search / processing control — `/api/vector-search/`

All authenticated. Envelope `{success, data, message}`.

- `projects/{project_id}/processing/start/` POST — `{llm_provider, llm_model, enable_summary}`; 409 if already running
- `projects/{project_id}/processing/stop/` POST
- `projects/{project_id}/processing/status/` GET
- `projects/{project_id}/documents/statuses/` GET
- `projects/{project_id}/fix-documents/` POST · `fix-documents/` POST (all projects)
- `health/` GET (requires a JWT), `processing-modes/` GET
- `…/processing/{start,stop,status}-legacy/` — older equivalents

---

## Workflows — `/api/projects/<uuid:project_id>/workflows/`

`AgentWorkflowViewSet`, authenticated, gated by `has_user_access`.

| Endpoint | Methods | Notes |
|---|---|---|
| `…/workflows/` | GET, POST | GET returns a bare unpaginated array |
| `…/workflows/{workflow_id}/` | GET, PATCH | **PATCH is the only usable update** (PUT is unusable — see KNOWN_ISSUES). DELETE returns 405 |
| `…/workflows/{workflow_id}/execute/` | POST | **reads no request body**; blocking, non-streaming. Returns `status: success` \| `paused` \| `error` |
| `…/workflows/{workflow_id}/history/` | GET | last 20 executions |
| `…/workflows/{workflow_id}/validate/` | POST | `{valid, errors[], warnings[]}`; no cycle check |
| `…/workflows/{workflow_id}/conversation/` | GET | **requires `?execution_id=`** |
| `…/workflows/{workflow_id}/evaluate/` | POST (multipart) | field `csv_file` with columns `input`, `expected_output`; runs inline |
| `…/workflows/{workflow_id}/evaluation_history/` | GET | |
| `…/workflows/{workflow_id}/evaluation_results/` | GET | **requires `?evaluation_id=`** |
| `…/workflows/{workflow_id}/export/` | GET | JSON bundle, `schema_version: "1"` |
| `…/workflows/import/` | POST | requires `schema_version == "1"`; always creates a new workflow, forces status `draft`, strips file attachments |
| `…/workflows/{workflow_id}/nodes/{node_id}/upload-file-attachment/` | POST (multipart) | `file` + optional `provider` |
| `/api/debug/projects/<uuid:project_id>/workflows/` | GET, POST | **authenticated but does not check project access** — see KNOWN_ISSUES |

---

## Agent orchestration — `/api/agent-orchestration/`

### DocAware

- `docaware/search_methods/` GET — the authoritative method registry
- `docaware/validate_parameters/` POST — `{method, parameters}`
- `docaware/test_search/` POST — `{project_id, method, query, parameters, content_filters}`. Rejects placeholder queries such as `"test query"` with 400
- `docaware/collections/` GET — `?project_id=`
- `docaware/hierarchical_paths/` GET — `?project_id=&include_files=`
- `docaware/uploaded_hierarchical_paths/` GET — derived from Postgres, works before vectorization

### Prompt generation and workflow generation

- `generate-prompt/generate/` POST — `{description (10–10000 chars), agent_type, doc_aware, project_id, llm_provider, llm_model}`
- `projects/<uuid:project_id>/generate-workflow/` POST — JSON or multipart. `{message, conversation_history, current_graph}` plus up to 5 files/turn. Returns `{graph_json, explanation, tool_calls, errors, plan, diff}`; **408** after a 120 s timeout

### Human input

- `human-input/pending/` GET — **side effect**: pauses older than 1 hour are force-completed on every call
- `human-input/submit/` POST — `{execution_id, human_input, action}`; blocks for the whole resumed run
- `human-input/history/` GET — last 50

### Deployment management (authenticated)

- `projects/<uuid:project_id>/deployment/` GET — **mutates state**: `get_or_create` on a GET
- `projects/<uuid:project_id>/deployment/` POST — `{workflow_id (required), rate_limit_per_minute, initial_greeting (≤2500), chatbot_title, chatbot_subtitle, primary_color, secondary_color, font_color, logo_url, file_uploads_enabled, public_url_enabled, public_url_auth_enabled, public_url_username, public_url_password}`
- `…/deployment/toggle/` PATCH
- `…/deployment/origins/` GET, POST · `…/origins/<int:origin_id>/` DELETE, PATCH
- `…/deployment/activity/` GET — `?session_id=&limit=&offset=`
- `projects/<uuid:project_id>/summarize-urls/` POST — 202 on start, **409** if a job is already running
- `…/url-summaries/` GET · `…/clear-websearch-cache/` POST · `…/sync-websearch-index/` POST

---

## LLM configuration — `/api/llm/`

All authenticated. `project_id` resolution falls back to the caller's first accessible project when omitted.

- `providers/` GET, `models/` GET, `bulk-load/` GET, `refresh/<provider_id>/` POST, `clear-cache/` DELETE
- `validate/` POST — `{project_id (required), llm_provider, llm_model, temperature, max_tokens, …}`
- `defaults/<agent_type>/` GET, `cost-estimate/` POST
- `projects/<pid>/agents/<aid>/config/` GET and `…/config/update/` PUT — **stubs that persist nothing**

## Project API keys — `/api/project-api-keys/`

- `providers/` GET
- `project/<project_id>/status/` GET
- `project/<project_id>/keys/` GET, POST — `{provider_type, api_key, key_name, validate_key}`
- `project/<project_id>/keys/<provider_type>/validate/` POST · `project/<project_id>/keys/<provider_type>/` DELETE

## MCP servers — `/api/mcp-servers/`

- `types/` GET
- `projects/<uuid:project_id>/credentials/` GET
- `projects/<uuid:project_id>/credentials/<server_type>/` GET, POST, DELETE
- `…/credentials/<server_type>/test/` POST · `…/tools/` GET

## Templates

- `/api/project-templates/` GET · `/{pk}/` GET · `/{pk}/configuration/` GET · `discover/` GET
- `/api/project-templates/duplicate/` POST, `cache_stats/` GET, `cache_management/` POST — **admin**
- `/api/enhanced-project-templates/…` — the same viewset re-registered with hyphenated action names

## LLM evaluation

- `/api/llm-providers/` GET (auth), writes admin · `/{pk}/models/` GET
- `/api/llm-providers/available/` GET
- `/api/api-keys/` — **admin only, all methods**
- `/api/llm-comparisons/` GET, POST (scoped to the caller) · `/{pk}/responses/` GET

---

## Public endpoints

### Deployed chatbot — `/api/workflow-deploy/<uuid:project_id>/…`

Plain Django views, all `@csrf_exempt`, no DRF. Five of them sit behind a per-deployment gate; three are wide open.

**The gate (`_enforce_public_chat_auth`)**, in order:

1. Allow if the request's `Origin` **or** its `Referer`'s origin is in `settings.CORS_ALLOWED_ORIGINS` (the "trusted admin app" bypass).
2. Allow if `public_url_auth_enabled` is false.
3. If a `pchat_*` cookie is present but `public_url_enabled` is false → **401** + cookie deleted (kill switch).
4. Allow on a valid `pchat` cookie or an allow-listed per-deployment origin; otherwise **401** `{authRequired: true}`.

The cookie is `pchat_<deployment_id>`, a `TimestampSigner` signature over `"<deployment_id>:<password_version>"`, 4-hour rolling, `HttpOnly`, `SameSite=Lax`, `Secure` outside DEBUG, path-scoped. Bumping the deployment password — or changing `public_url_enabled` / `public_url_auth_enabled` / `public_url_username` — increments `public_url_password_version` and instantly invalidates every live cookie.

| Endpoint | Methods | Gate | Notes |
|---|---|---|---|
| `/` | POST | gate + rate limit | `{user_query (≤1000 chars), session_id (required), file_ids[]}` → `{status, response, citations[], metadata}` or `awaiting_human_input`. **429** carries `retry_after` |
| `/stream/` | POST | gate + rate limit | **SSE**; always HTTP 200, errors in-band. The 1000-char cap is **not** enforced here |
| `/submit-input/` | POST | gate, no rate limit | `{session_id, user_input}`. Blocks up to 60 s, then returns `{status: 'processing'}` |
| `/upload-file/` | POST (multipart) | gate, no rate limit | Requires `file_uploads_enabled`. Max 50 MB, 10 files/session, per-provider extension allowlists |
| `/embed/` | ANY | gate | Returns a self-contained HTML chatbot page. `?hide_header=1`, `?session_id=` (server-side injects the last 100 messages) |
| `/public-config/` | GET, OPTIONS | **none** | Branding + `auth_required` + `is_logged_in`; 404 for anything unavailable (existence hiding) |
| `/public-auth/` | POST, OPTIONS | **none** (this is the login) | `{username, password}` → cookie. Brute-force limit 10 failures / 900 s per IP |
| `/public-logout/` | POST, OPTIONS | **none** | Always 200 + cookie deletion |

Rate limiting is per deployment-and-origin per minute (default 10), and **fails open on any exception**.

### Standalone public chatbot — `/api/public-chatbot/`

- `/` POST — `{message (required), session_id, context_limit, conversation}`. Three independent limiters: `django_ratelimit` 10/min per IP, `IPUsageLimit` daily/hourly counters, and the `ChatbotConfiguration` limits (100/day, 20/hour). Kill switches: `is_enabled`, `maintenance_mode` → 503
- `/stream/` POST — SSE, OpenAI only; falls back to a JSON 500 if streaming is unavailable
- `/health/` GET — 200/503 with component status

### Other unauthenticated endpoints

These have **no credential of any kind** and are reachable by anyone who can reach the port:

- `/api/milvus/search/`, `/api/milvus/collections/`, `/api/milvus/test/`, `/api/milvus/api/search/`, `/api/milvus/api/collections/`, `/api/milvus/api/health/` — plain Django views with no auth
- `/api/templates/discover/`, `/api/templates/endpoints/`, `/api/templates/refresh/` (**clears the Django cache**), `/api/templates/aicc-intellidoc/discover/`
- `/api/`, `/api/agent-orchestration/`, `/api/project-api-keys/` — DRF API-root views (AllowAny because no default permission class is configured)
- `/`, `/login/` — informational JSON
- `/media/<path>` — served by Django only when `DEBUG=True`, which is the current default

`/admin/` is Django admin (session auth, staff only), plus a custom bulk-upload view for the public knowledge base.

---

## Not routed / not usable

See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for the full list. The ones most likely to surprise a client developer:

- `DELETE /api/projects/{pid}/workflows/{wid}/` → **405**. Use `DELETE /api/projects/{pid}/agent_workflow/?workflow_id=…`.
- `PUT` on a workflow detail route cannot succeed; use `PATCH`.
- `/api/projects/{id}/digest/` is a broken plain-Django view.
- `/api/templates/legal/`, `/medical/`, `/history/` resolve to nothing.
- The per-agent LLM config GET/PUT endpoints are stubs.
