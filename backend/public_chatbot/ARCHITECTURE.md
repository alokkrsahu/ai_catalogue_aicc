# Public Chatbot — Technical Architecture

**Module:** `backend/public_chatbot/`
**Audience:** Engineers, DevOps, security reviewers
**Scope:** A self-contained, unauthenticated Q&A API that answers visitor questions from an admin-curated knowledge base, using ChromaDB retrieval + a pluggable LLM backend. It is deliberately isolated from the main AI Catalogue platform.

---

## 1. Design goals & the isolation principle

The public chatbot is reachable by anonymous internet traffic, so it is engineered as a **blast-radius-contained subsystem**. Every architectural choice follows from one rule: *public traffic must never be able to reach private platform data (Milvus collections, user/project records, project API keys).*

Isolation is enforced at four layers:

| Layer | Main platform | Public chatbot |
|---|---|---|
| Vector store | Milvus (`vector_search/`) | **ChromaDB** (separate service/collection) |
| Relational tables | shared app tables w/ FKs to `users.User` | **4 dedicated tables**, `db_table` explicitly set, **no foreign keys** to platform models |
| LLM credentials | per-project Fernet-encrypted keys (`project_api_keys/`) | **system-level env keys only** (dedicated `AICC_CHATBOT_OPENAI_API_KEY`) |
| Ingress | JWT-authenticated DRF views | **unauthenticated**, own CORS middleware + own URL include |

> The only intentional cross-app import is `agent_orchestration.message_converter` (message-format helper). There is **no** call path into Milvus, project key storage, or authenticated viewsets.

---

## 2. Module layout

```
public_chatbot/
├── urls.py                 # 3 routes (chat, stream, health)
├── views.py                # request lifecycle, CORS helpers, IP tracking
├── services.py             # PublicKnowledgeService (ChromaDB) + ChatbotSecurityService
├── llm_integration.py      # PublicLLMService — OpenAI / Gemini / Anthropic
├── models.py               # 4 isolated models
├── chunking.py             # AdvancedTextChunker (chunk strategies)
├── embedding_strategies.py # LargeChunkEmbedder (sliding-window etc.)
├── document_processor.py   # ingestion pipeline for admin docs
├── security.py             # extended security helpers
├── signals.py              # pre_delete → ChromaDB cleanup
├── admin.py                # Django admin management UI
├── middleware/cors.py      # PublicChatbotCORSMiddleware
└── management/commands/    # sync_public_knowledge, init_sample_knowledge, test_bulk_upload
```

App bootstrap (`apps.py::ready()`) imports signals and **eagerly instantiates the `PublicKnowledgeService` singleton** so the ChromaDB connection + embedding model are warmed at process start (failures are logged, not fatal).

---

## 3. Data model

All tables are prefixed/namespaced and carry no FKs to platform models.

| Model | Table | Purpose |
|---|---|---|
| `PublicChatRequest` | `public_chatbot_requests` | Per-request audit & analytics (timing, ChromaDB metrics, LLM provider/model/tokens, status, error) |
| `IPUsageLimit` | `public_chatbot_ip_limits` | Per-IP counters (daily/hourly), blocking state, security-violation tally |
| `PublicKnowledgeDocument` | `public_chatbot_knowledge` | Admin-managed KB source-of-truth + ChromaDB sync state + approval workflow |
| `ChatbotConfiguration` | `public_chatbot_config` | **Singleton** (`pk=1`) runtime config |

Key model behaviours:
- `PublicChatRequest.save()` auto-generates `request_id` (`pub_<ts>_<uuid8>`) and derives `response_time_ms`; runs `full_clean()`.
- `IPUsageLimit.increment_usage()` rolls daily/hourly counters with auto-reset on date/hour boundaries.
- `PublicKnowledgeDocument.save()` auto-computes `content_preview` + SHA-256 `content_hash` (dedupe).
- `ChatbotConfiguration.get_config()` is the singleton accessor; `save()` rejects creation of a second row.

### `ChatbotConfiguration` fields that drive runtime behaviour

| Field | Default | Effect |
|---|---|---|
| `is_enabled` | `True` | Global kill switch (→ 503) |
| `maintenance_mode` / `maintenance_message` | `False` / "" | Returns 503 with custom message |
| `daily_requests_per_ip` | `100` | Per-IP daily cap |
| `hourly_requests_per_ip` | `20` | Per-IP hourly cap (tracked on the model) |
| `max_message_length` | `500` | (Validation hard-codes 500 — see §6) |
| `max_search_results` | `5` | Upper bound on `context_limit` |
| `similarity_threshold` | `0.7` | Min cosine-similarity to keep a retrieved chunk |
| `default_llm_provider` / `default_model` | `openai` / `gpt-3.5-turbo` | Provider routing |
| `max_response_tokens` | `300` | LLM output cap |
| `system_prompt` | generic | Persona/system instruction |
| `enable_vector_search` | `True` | Toggle RAG entirely |
| `enable_query_rephrasing` | `True` | LLM query rewrite on follow-ups |

---

## 4. Request lifecycle

### 4.1 Standard endpoint — `POST /api/public-chatbot/`

```mermaid
sequenceDiagram
    participant C as Client
    participant MW as PublicChatbotCORSMiddleware
    participant V as public_chat_api
    participant Cfg as ChatbotConfiguration
    participant Sec as ChatbotSecurityService
    participant KS as PublicKnowledgeService
    participant Chr as ChromaDB
    participant LLM as PublicLLMService
    participant DB as Postgres (isolated tables)

    C->>MW: POST (Origin header)
    MW->>MW: OPTIONS preflight? → allow/deny by origin
    MW->>V: pass through (chat path)
    V->>Cfg: get_config()
    alt disabled / maintenance
        V-->>C: 503
    end
    V->>DB: create PublicChatRequest (immediate save)
    V->>Sec: validate_input(message)  %% empty/length/injection/charset
    alt invalid
        V->>DB: status=security_violation; bump IP violations
        V-->>C: 400
    end
    V->>Sec: check_rate_limit_exceeded(ip)
    alt over daily cap / blocked
        V-->>C: 429 (retry_after)
    end
    opt enable_vector_search
        V->>KS: search_knowledge(msg, limit, conversation)
        KS->>Chr: query(top-k) → distances
        Chr-->>KS: docs+metadata
        KS-->>V: chunks above similarity_threshold
    end
    V->>LLM: generate_response(messages, provider, model, system+KB)
    LLM-->>V: {response, provider, model, tokens}
    V->>DB: update request (timing, chroma metrics, tokens, status)
    V->>DB: IPUsageLimit.increment_usage()
    V-->>C: 200 {response, metadata, sources[top3]}
```

Pre-LLM gates fail **fast and cheap** — a rejected request never reaches an LLM provider. Tracking rows are written *before* processing so even crashes leave an audit trail.

### 4.2 Streaming endpoint — `POST /api/public-chatbot/stream/`

Same gating, then **Server-Sent Events** (`text/event-stream`). Constraints:
- **OpenAI only** — non-OpenAI providers are rejected with 400 (`config.default_llm_provider != 'openai'`).
- Emits a `{type:"sources", sources:[...]}` event first (same schema as the non-streaming `sources[]`, so clients can render citation chips immediately), then `data: {type: "content", ...}` deltas, then a `{type:"completion", total_content, response_time_ms}` event, then `data: [DONE]`.
- Sets `X-Accel-Buffering: no` to defeat nginx buffering; CORS echoed inline on the streaming response (middleware can't post-process a streamed body cleanly).
- On stream-setup failure it falls back to a 500 JSON error and records `streaming_setup_error`.

### 4.3 Health — `GET /api/public-chatbot/health/`

Returns ChromaDB health (`PublicKnowledgeService.health_check()`), config snapshot, and `requests_last_5min`. `overall_healthy = is_enabled AND (not enable_vector_search OR chromadb healthy)`. Returns **200** healthy / **503** unhealthy — wire this to your liveness/readiness probe.

---

## 5. Knowledge / retrieval subsystem (`services.py`)

`PublicKnowledgeService` is a thread-safe singleton (double-checked lock in `__new__`).

**Connection.** `chromadb.HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)`; on failure it falls back to a local `PersistentClient(./chroma_public_db)`. Collection name: **`public_knowledge_base`** (created with `allow_reset=False`).

**Embeddings.** Default `SentenceTransformerEmbeddingFunction("sentence-transformers/all-MiniLM-L6-v2")` (384-dim, matches the platform embedder for cache reuse). The init path detects an existing HF cache (old/new layout) and sets `HF_HUB_OFFLINE=1` to skip network round-trips; otherwise it downloads with a 300s timeout. Falls back to Chroma's `DefaultEmbeddingFunction` if sentence-transformers is unavailable.

**Advanced ingestion (optional).** When `chunking.py` + `embedding_strategies.py` import cleanly:
- Chunking: `ChunkStrategy.LARGE_SEMANTIC` (~2048 tokens, 200 overlap; other strategies 512→4096 available).
- Embedding: `EmbeddingStrategy.SLIDING_WINDOW` with `use_enhanced_model=True` to handle chunks beyond the 256-token model window.

### 5.1 Retrieval flow (`search_knowledge`)

1. **Query construction** depends on conversation state:
   - *First turn:* use the raw message.
   - *Follow-up + `enable_query_rephrasing`:* `_rephrase_query_with_llm()` rewrites the (possibly elliptical) query into a standalone one — a short, low-temperature (0.3, 150-token) LLM call using the same provider/model.
   - *Follow-up, rephrasing off:* `_build_context_aware_query()` appends prior user turns: `"<latest>. [<prev queries>]"`.
2. `collection.query(query_texts=[q], n_results=min(limit,15))`.
3. Convert distance → similarity (`max(0, 1 - distance)`), **drop anything below `similarity_threshold`**.
4. Return formatted hits (content, metadata, score, title/category/source).

Downstream: top **10** hits are inlined into the system prompt as a `=== KNOWLEDGE BASE ===` block; top **3** are surfaced to the client as `sources[]` (title, category, relevance_score, 150-char excerpt, and `url` — the document's `source_url` when it is a real `http(s)` link, `''` otherwise, so blank values and `upload://` pseudo-URLs from bulk uploads never leak as broken links; clients render a hyperlink chip when `url` is non-empty, a plain chip otherwise). If retrieval errors or finds nothing, the request **degrades gracefully** to a no-context answer rather than failing.

### 5.2 Ingestion & lifecycle
- Admin creates/approves `PublicKnowledgeDocument` rows → `sync_public_knowledge` (or admin actions) chunk + embed + `smart_sync_knowledge()` into ChromaDB (idempotent: checks `document_exists_in_chromadb`, supports `force_update`).
- **Deletion is signal-driven:** `pre_delete` on `PublicKnowledgeDocument` calls `delete_knowledge(document_id)` to purge all chunks (`where={"document_id": ...}`) from ChromaDB before the row is removed — keeps the two stores consistent.

---

## 6. Security model

### 6.1 Input validation (`ChatbotSecurityService.validate_input`)
- Reject empty/whitespace.
- **Hard length cap 500 chars** (note: this is a literal in code, independent of `config.max_message_length`).
- **Prompt-injection screen:** 13 regex patterns (`ignore previous instructions`, `you are now`, `system:`, `<system>`, `pretend to be`, `disregard`, `override`, …). A match → `security_violation` (400) and increments the IP's violation counter.
- **Charset heuristic:** non-alphanumeric ratio > 0.3 → rejected as `suspicious_format`.

In `_generate_llm_response`, a hard-coded **English-only language guardrail** is appended after the admin `system_prompt`, ahead of the KB block, to suppress script-mixing from multilingual base models.

### 6.2 Rate limiting (defence in depth)
| Mechanism | Limit | Source |
|---|---|---|
| View decorator (django-ratelimit) | **10/min per IP** (POST), `block=True` | `_rate_limit_decorator()` |
| Cache fallback (if lib missing) | 10/min per IP | `_is_rate_limited()` |
| Per-IP daily cap | **100/day** → auto-block until 23:59 | `check_rate_limit_exceeded()` |
| Security auto-block | **5 violations → 24h block** | `_update_ip_security_violation()` |
| Model-tracked hourly | 20/hr (counters maintained) | `IPUsageLimit` |

Client IP is resolved through a proxy-aware header chain (`X-Forwarded-For` → `X-Real-IP` → `CF-Connecting-IP` → … → `REMOTE_ADDR`) with validation and private-IP skipping — **correct operation depends on the reverse proxy setting these headers and on `REMOTE_ADDR` not being spoofable from the edge.**

### 6.3 CORS architecture
Three pieces, in order of precedence:
1. `PublicChatbotCORSMiddleware` (`middleware/cors.py`) — runs **first in `MIDDLEWARE`** (before `WorkflowDeploymentCORSMiddleware` and `corsheaders.CorsMiddleware`). Handles `OPTIONS` preflight: allowlisted origin → echo; `null`/empty → `*` (no credentials); unknown origin → **403**.
2. `_add_cors_headers()` per-view helper — only adds headers if absent; unknown origins fall back to `*` (credentials false).
3. `add_cors_headers_immediate()` — legacy hotfix, currently unused.

**Allowlist** (origins): `oxfordcompetencycenters.github.io`, `aicc.uksouth.cloudapp.azure.com`, `eng.ox.ac.uk`, `oerc.ox.ac.uk`, and localhost dev ports.

> ⚠️ Reviewer note: middleware blocks unknown origins at preflight, but the per-view helper will still emit `Access-Control-Allow-Origin: *` on actual responses for non-allowlisted origins. This is intentional for an anonymous public API but worth knowing — it is *not* a private-data exposure because no auth/cookies are honoured (`Allow-Credentials: false` on the wildcard path).

---

## 7. LLM integration (`llm_integration.py`)

`PublicLLMService` initialises only from **system-level** credentials (never project keys):

| Provider | Key source | Default model | Streaming |
|---|---|---|---|
| OpenAI | `AICC_CHATBOT_OPENAI_API_KEY` (dedicated) | `gpt-3.5-turbo` | ✅ SSE |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-3-haiku-20240307` | ❌ (falls back to non-stream) |
| Gemini | `GOOGLE_API_KEY` | `gemini-pro` | ❌ |

`generate_response()` routes by `provider`, with an unknown-provider fallback to OpenAI. Implementation notes:
- **Messages-first contract:** prefers a structured `messages[]` array; `system_prompt` is injected as a leading system message (OpenAI/Gemini) or the dedicated `system=` param (Anthropic).
- **OpenAI token param switching:** GPT models use `max_completion_tokens`; GPT-5 triples the budget and omits `temperature` (reasoning-token + fixed-temp constraints); legacy models use `max_tokens`.
- **Gemini** flattens messages to a single prompt (handles both `google.genai` and legacy `google.generativeai`); token counts are *estimated*.
- 30s per-call timeout; structured fallback payloads on error (`success: False`, safe user-facing message) so the view always has something to record/return.

---

## 8. Configuration & operations

### 8.1 Environment / infra (docker-compose)
- `chromadb` service; container port `8000`, host-mapped `${CHROMADB_PORT:-8001}:8000`. Backend talks to it via `CHROMADB_HOST=chromadb`, `CHROMADB_PORT=8000` (in-network).
- `AICC_CHATBOT_OPENAI_API_KEY` passed to the backend service; `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY` shared with the platform.
- Python deps (`public_chatbot/requirements.txt`): `chromadb==0.4.24`, `django-ratelimit==4.1.0` (rest reused from the platform).

### 8.2 Management commands
```bash
# Sync approved KB docs → ChromaDB
python manage.py sync_public_knowledge [--force-sync] [--category X] [--limit N] [--dry-run]
python manage.py init_sample_knowledge      # seed sample KB
python manage.py test_bulk_upload           # ad-hoc ingestion test
```

### 8.3 Runtime controls (no deploy needed)
All via the `ChatbotConfiguration` singleton in Django admin: kill switch, maintenance mode + message, rate limits, similarity threshold, provider/model, system prompt, vector-search & rephrasing toggles.

---

## 9. Observability

- **Logging:** dedicated `public_chatbot` logger (+ `public_chatbot.chunking`, `.embeddings`). Emoji-tagged lines mark stages (`📨` request, `🔍` retrieval, `🚨` security, `✅` success). Note `middleware/cors.py` logs preflight at **ERROR** level for visibility — turn this down in production.
- **Per-request metrics** persisted on `PublicChatRequest`: `response_time_ms`, `chroma_search_time_ms`, `chroma_results_found`, `chroma_context_used`, `llm_provider/model/tokens`, `status`, `error_type/message`.
- **Health endpoint** for probes (§4.3).

---

## 10. Failure modes & resilience

| Failure | Behaviour |
|---|---|
| ChromaDB down | HttpClient → local `PersistentClient` fallback; if still not ready, retrieval skipped, answer generated without context |
| Embedding model missing | Falls back to Chroma `DefaultEmbeddingFunction` |
| Tracking row write fails | Logged; request still processed (tracking is best-effort, never blocks the answer) |
| LLM API error/timeout | Structured fallback payload, request marked `error`, safe message to client |
| Rephrasing LLM fails | Silently falls back to original/context-aware query |
| Unknown provider | Falls back to OpenAI |

---

## 11. Known limitations / extension points

- **Streaming is OpenAI-only.** Anthropic/Gemini streaming would need provider-specific SSE adapters in `_handle_*_stream`.
- **`max_message_length` config is not wired** into `validate_input` (500 is hard-coded) — unify if you expose the setting.
- **Hourly cap (20/hr)** is tracked on `IPUsageLimit` but `check_rate_limit_exceeded()` enforces only the daily cap + block state; the per-minute cap comes from the decorator. Consolidate if you want a single enforcement path.
- **Gemini token usage is estimated**, not metered — cost dashboards should account for this.
- **IP-based limits** are only as trustworthy as the proxy header chain; ensure the edge strips client-supplied `X-Forwarded-For`.
- The legacy `add_cors_headers_immediate()` and `cors_hotfix.py.removed` are dead code — safe to delete.

---

*Generated for the AICC-IntelliDoc platform. Cross-reference: root `CLAUDE.md` (platform overview), `core/settings.py` (MIDDLEWARE order, INSTALLED_APPS), `core/urls.py:228` (URL include).*
