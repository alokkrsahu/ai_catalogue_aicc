# IntelliDoc — AI Builder for Multi-Agent Workflows

IntelliDoc generates validated, operator-editable multi-agent workflows from a single natural-language request. The canonical use case is transparent Deep Research: given a prompt, the AI Builder synthesises a workflow that retrieves relevant documents, searches the web, delegates subtasks to specialised agents, and compiles a structured report — without writing code. MIT licensed.

---

## Key features

- **AI Builder (Plan → Build → Verify → Self-Critique)** — synthesises a complete workflow graph, validates it against structural invariants, then critiques and repairs its own output before presenting it.
- **Visual workflow designer** — drag-and-drop canvas with nine node types: Start, End, Assistant, UserProxy (human-in-the-loop), GroupChatManager, Delegate, Classifier, Splitter, MCP Server. Edits autosave to the database.
- **Per-agent RAG via Milvus** — seven configurable search strategies against project-scoped collections, with per-agent folder/file scoping.
- **Format-adaptive web search** — URL, domain and general modes. URL content is extracted with layered fallbacks (DOM, JSON-LD, SPA hydration state, `<noscript>`, text density, markdown alternates) and cached in Redis.
- **Reference-based evaluation** — CSV-driven ROUGE / BLEU / BERTScore / semantic-similarity scoring.
- **Embeddable chatbot deployment** — publish any workflow as a public endpoint with optional password protection, per-origin allowlists and rate limits.
- **Multi-provider LLMs per agent** — mix OpenAI, Anthropic and Google models in one workflow, with per-node temperature.
- **Grounded citations** — `[N]` markers reconciled end to end so numbering is always consecutive and every marker is backed by a real source.
- **MCP server integration** and **human-in-the-loop** pause/resume, streamed live over SSE.

---

## Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.13 |
| Backend | Django ≥5.2 + Django REST Framework |
| Database | PostgreSQL 15 |
| Vector DB | Milvus 2.6 |
| Cache | Redis 7 |
| Frontend | SvelteKit 2 + Svelte 5, TypeScript, Tailwind 3, Vite 6 |
| Auth | JWT via SimpleJWT (Bearer tokens) |
| Real-time | Server-Sent Events |
| Reverse proxy | Nginx |
| Containers | Docker Compose — **10 services** |
| Embeddings | `all-MiniLM-L6-v2` (384-dim, SentenceTransformers) |

> Note: `celery` and `channels` appear in `requirements.txt` but are **not wired up** — there is no Celery app, worker or task dispatch, and no WebSocket routing. Background work uses threads; real-time uses SSE.

### Services

```
                        ┌──────────┐
     public :80/:443 ───│  nginx   │
                        └────┬─────┘
                 ┌───────────┴───────────┐
          ┌──────▼──────┐         ┌──────▼───────┐
          │   backend    │         │   frontend   │
          │    :8000     │         │ :3000 / :5173│
          └──────┬───────┘         └──────────────┘
                 │
   ┌─────────┬───┴─────┬──────────┬───────────┐
┌──▼───┐ ┌───▼───┐ ┌───▼────┐ ┌───▼────┐
│postgres│ │ redis │ │ milvus │ │ minio  │
│ :5432  │ │ :6379 │ │ :19530 │ │(unused)│   all loopback-only
└────────┘ └───────┘ └───┬────┘ └────────┘
                     ┌───▼───┐
                     │ etcd  │      plus: pgadmin :8080, attu :3001
                     └───────┘
```

---

## Quick start

Prerequisites: Docker ≥ 24, Docker Compose ≥ 2.20, 8 GB RAM (16 GB recommended), and at least one LLM API key.

```bash
git clone <repo-url> && cd ai_catalogue
cp .env.example .env

# Generate the required secrets
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"   # DJANGO_SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"                    # PROJECT_API_KEY_ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"                    # API_KEY_ENCRYPTION_KEY

./scripts/start-dev.sh          # first run: 8–12 min (images + embedding model)
./scripts/bootstrap.sh          # rotate Milvus password, seed providers, create an admin
open http://localhost
```

Then, in the app: create a project from a template, upload documents, run **Start Processing**, and add a provider API key under the project's API-key settings.

> **API keys are per project.** There is no environment-variable fallback on the workflow path — a project with no configured `ProjectAPIKey` cannot execute any LLM node.

`.env.example` documents every variable the stack reads. Those without a compose default will stop startup if unset — deliberately, so a deployment never falls back to a value published in this repository. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

### Required configuration

| Variable | Why |
|---|---|
| `PROJECT_API_KEY_ENCRYPTION_KEY` | No default. Encrypts per-project provider keys. |
| `API_KEY_ENCRYPTION_KEY` | No default. The previous compose default is public in git history and has been rotated. |
| `MILVUS_ROOT_USER`, `MILVUS_ROOT_PASSWORD` | No default; startup scripts abort without them. |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | Same startup guard, though MinIO is currently unused. |
| `DJANGO_SECRET_KEY` | No default; required whenever `DEBUG=False`. |
| `DB_PASSWORD` | No default; the previous default is public in this repository. |
| `REDIS_PASSWORD` | No default; Redis runs with `requirepass`. |
| One of `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` | Needed for platform-level features. |

---

## Everyday commands

| Task | Command |
|---|---|
| Code-only change (`.py`, `.svelte`, `.ts`) | `./scripts/quick-deploy.sh` |
| New dependency or Dockerfile change | `./scripts/rebuild-deploy.sh` |
| Restart everything without rebuilding | `./scripts/restart-dev.sh` |
| Full rebuild from scratch | `./scripts/start-dev.sh` |
| Reclaim disk (keeps volumes) | `./scripts/docker-cleanup.sh` |

See [`scripts/SCRIPTS.md`](scripts/SCRIPTS.md) for the complete table.

> **`docker-compose.override.yml` is auto-loaded**, so any bare `docker compose …` command runs the *development* stack — `runserver`, `DEBUG=True`, the Vite dev server. Only `scripts/production.sh` opts out. Note that the production overlay does not currently start; see [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) (B1, B2).

---

## Development without Docker

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# point DB_HOST / MILVUS_HOST / REDIS_HOST at localhost in .env
python manage.py migrate
python manage.py setup_container_data      # seeds dashboard icons
python manage.py runserver 0.0.0.0:8000

# Frontend
cd frontend/my-sveltekit-app
npm install
npm run dev       # http://localhost:5173
npm run check     # svelte-check
npm run lint      # ESLint
```

The Vite dev server proxies `/api` to `BACKEND_URL` (default `http://127.0.0.1:8000`). There is no Celery worker to start.

---

## Repository layout

```
.
├── backend/
│   ├── agent_orchestration/      # workflow engine, deployment, RAG, web search
│   │   ├── workflow_executor.py  # the executor (sequential + parallel)
│   │   ├── chat_manager.py       # prompt crafting, GroupChatManager
│   │   ├── graph_invariants.py   # save-time graph validation
│   │   ├── workflow_generator.py # AI Builder
│   │   ├── deployment_views.py   # public chatbot endpoints + embed page
│   │   ├── docaware/             # per-agent RAG over Milvus
│   │   └── websearch/            # fetch, extract, cache, index
│   ├── api/                      # auth, permissions, UniversalProjectViewSet
│   ├── core/                     # settings, urls, wsgi/asgi
│   ├── users/                    # custom User + ~30 domain models
│   ├── vector_search/            # ingestion: parse → chunk → embed → Milvus
│   ├── llm_eval/                 # multi-provider comparison
│   ├── templates/                # filesystem template registry
│   ├── project_api_keys/         # encrypted per-project keys
│   └── mcp_servers/              # encrypted MCP credentials
├── frontend/my-sveltekit-app/src/
│   ├── routes/                   # SvelteKit pages
│   └── lib/{components,services,stores}/
├── docs/                         # architecture, API, deployment, known issues
├── nginx/                        # dev / prod / ssl configs
├── scripts/                      # deployment and utility scripts
└── docker-compose*.yml
```

---

## Documentation

| Document | Contents |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Apps, domain model, `graph_json` format, node types, execution semantics, retrieval, citations, frontend |
| [`docs/API.md`](docs/API.md) | Complete endpoint reference, including every public endpoint and its auth model |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Compose stack, configuration, nginx, scripts, ports, persistence, backup |
| [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) | Verified defects and dead code, triaged by severity |
| [`backend/agent_orchestration/parallelization_analysis.md`](backend/agent_orchestration/parallelization_analysis.md) | GroupChatManager / Delegate execution flow |

These documents are derived from the source rather than from earlier documentation, and they record defects as well as intended behaviour. Please keep them that way — if you change behaviour, update the corresponding section; if you fix something in `KNOWN_ISSUES.md`, remove the entry.

---

## Security

**This repository is public** — never commit secrets. Configuration lives in `.env` (git-ignored); a pre-commit hook blocks accidental exposure and must be installed once per clone:

```bash
./scripts/install-git-hooks.sh
```

See [`SECURITY.md`](SECURITY.md) for the full policy, what to do if a credential is exposed, and the known historical exposure.

## Security notes for operators

Only nginx (80/443) is published on all interfaces; every other service binds `127.0.0.1`. `DEBUG` defaults to `False`, and with `DEBUG=False` a missing or publicly-known `DJANGO_SECRET_KEY` fails startup rather than being used silently. `DB_PASSWORD`, `DJANGO_SECRET_KEY` and both encryption keys have no defaults and must be set.

Redis enforces `requirepass`. The remaining known gap — the deployment CORS middleware only blocks preflight — is tracked in [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md). Before rotating an encryption key, read [`docs/DEPLOYMENT.md` §11](docs/DEPLOYMENT.md#11-rotating-encryption-keys): `PROJECT_API_KEY_ENCRYPTION_KEY` cannot be changed without re-encrypting stored data.

---

## License

MIT — see [`LICENSE`](LICENSE).
