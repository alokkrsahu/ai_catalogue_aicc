# IntelliDoc — AI Builder for Multi-Agent Workflows

IntelliDoc is an open-source system that generates validated, operator-editable multi-agent workflows from a single natural-language request. The canonical use case is transparent Deep Research: given a prompt, the AI Builder synthesises a workflow that retrieves relevant documents, searches the web, delegates subtasks to specialised agents, and compiles a structured report — all without writing a line of code. MIT licensed.

---

## Key Features

- **AI Builder (Plan → Build → Verify → Self-Critique)** — four-phase pipeline that synthesises a complete workflow graph, validates it against structural invariants, then critiques and repairs its own output before presenting it to the operator
- **Visual Workflow Designer** — drag-and-drop canvas with 9 agent node types: LLM, DocAware, WebSearch, Classifier, Splitter, Aggregator, Evaluator, MCP, Human-in-the-Loop
- **Per-agent RAG via Milvus** — 7 configurable search strategies (semantic, hybrid, contextual, and more) against project-scoped Milvus collections
- **Web search with Redis caching** — external search results cached to avoid redundant requests
- **Reference-based evaluation** — BLEU / ROUGE / BERTScore + LLM-as-judge scoring for systematic quality measurement
- **Embeddable chatbot deployment** — publish any workflow as a public chatbot endpoint
- **Multi-provider LLM per agent** — mix OpenAI, Anthropic, and Google models within a single workflow; per-node temperature control
- **MCP server integration** — attach Model Context Protocol servers to individual agent nodes
- **Human-in-the-loop** — pause execution, request operator input, and resume — streamed live via WebSocket

---

## Architecture

### Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | Django 5.2 + Django REST Framework |
| Database | PostgreSQL 15 |
| Vector database | Milvus 2.6 |
| Cache / broker | Redis 7 |
| Frontend framework | SvelteKit 2 + Svelte 5, TypeScript, Tailwind CSS |
| Build tool | Vite 6 |
| Auth | JWT via SimpleJWT (Bearer tokens) |
| Realtime | Django Channels (WebSocket) |
| Reverse proxy | Nginx |
| Containerisation | Docker Compose (9 services) |
| Embedding model | `all-MiniLM-L6-v2` (384-dim, SentenceTransformers) |

### Docker Services

```
┌─────────────────────────────────────────────────────────────────┐
│                    ai_catalogue_network (172.20.0.0/16)         │
│                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌─────────────┐  │
│  │ postgres │   │  redis   │   │  minio   │   │    etcd     │  │
│  │  :5432   │   │  :6379   │   │  :9000   │   │   :2379     │  │
│  └──────────┘   └──────────┘   └──────────┘   └─────────────┘  │
│                                                      │           │
│  ┌──────────────────────────────────────────────┐   │           │
│  │                   milvus                     │◄──┘           │
│  │                  :19530                      │               │
│  └──────────────────────────────────────────────┘               │
│                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                     │
│  │ chromadb │   │ backend  │   │ frontend │                     │
│  │  :8001   │   │  :8000   │   │  :3000   │                     │
│  └──────────┘   └──────────┘   └──────────┘                     │
│                        ▲              ▲                          │
│                        └──────┬───────┘                         │
│                         ┌─────┴────┐                            │
│                         │  nginx   │ ← public :80 / :443        │
│                         └──────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- Docker ≥ 24
- Docker Compose ≥ 2.20
- At least one LLM API key (OpenAI, Anthropic, or Google)
- 8 GB RAM (16 GB recommended when running all 9 services)
- macOS, Linux, or WSL2 on Windows

---

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url>
cd ai_catalogue_aicc

# 2. Copy and configure the environment file
cp .env.example .env

# 3. Fill in your API keys and generate the required secret keys
#    Django secret key:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

#    Fernet encryption keys (run twice — one for each variable):
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 4. Start all services with hot reload
./scripts/start-dev.sh

# 5. Open the app
open http://localhost
```

First run downloads Docker images and the embedding model (~8–12 minutes). Subsequent starts are much faster.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in every value marked below as required.

| Variable | Required | Description | How to generate |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | Yes | Django cryptographic signing key | `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `API_KEY_ENCRYPTION_KEY` | Yes | Fernet key for encrypting stored API keys | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `PROJECT_API_KEY_ENCRYPTION_KEY` | Yes | Fernet key for per-project API keys | Same command as above |
| `DB_NAME` | Yes | PostgreSQL database name | Any string, e.g. `ai_catalogue_db` |
| `DB_USER` | Yes | PostgreSQL username | Any string |
| `DB_PASSWORD` | Yes | PostgreSQL password | Any strong password |
| `DB_HOST` | Yes | PostgreSQL host | `postgres` (Docker) or `localhost` (standalone) |
| `DB_PORT` | Yes | PostgreSQL port | `5432` |
| `MILVUS_HOST` | Yes | Milvus host | `milvus` (Docker) or `localhost` (standalone) |
| `MILVUS_PORT` | Yes | Milvus port | `19530` |
| `MILVUS_ROOT_USER` | Yes | Milvus admin username | `milvusadmin` |
| `MILVUS_ROOT_PASSWORD` | Yes | Milvus admin password | Any strong password |
| `MINIO_ROOT_USER` | Yes | MinIO username (Milvus storage) | `minioadmin` |
| `MINIO_ROOT_PASSWORD` | Yes | MinIO password | Any strong password |
| `OPENAI_API_KEY` | At least one | OpenAI API key | [platform.openai.com](https://platform.openai.com) |
| `ANTHROPIC_API_KEY` | At least one | Anthropic API key | [console.anthropic.com](https://console.anthropic.com) |
| `GOOGLE_API_KEY` | At least one | Google Gemini API key | [aistudio.google.com](https://aistudio.google.com) |
| `CORS_ALLOWED_ORIGINS` | Yes (prod) | Comma-separated allowed origins | e.g. `https://yourdomain.com` |
| `CSRF_TRUSTED_ORIGINS` | Yes (prod) | Comma-separated trusted origins | e.g. `https://yourdomain.com` |
| `DEBUG` | No | Set `False` in production | `True` for development |

---

## Deployment Scripts

All scripts live in `scripts/`. See `scripts/SCRIPTS.md` for the full decision table.

| Scenario | Script | Approx. downtime |
|---|---|---|
| First run / fresh infrastructure | `./scripts/start-dev.sh` | N/A (first boot) |
| Code-only changes (`.py`, `.svelte`, `.ts`) | `./scripts/quick-deploy.sh` | ~2 s |
| New pip/npm packages or Dockerfile changes | `./scripts/rebuild-deploy.sh` | ~10 s |
| Production with SSL (Let's Encrypt) | `./scripts/setup-ssl.sh` then `./scripts/production.sh` | N/A |
| Renew SSL certificate | `./scripts/renew-ssl.sh` | 0 (hot reload) |
| Full reset and clean restart | `./scripts/reset.sh` | Full restart |

### Docker Compose variants

| File | Purpose |
|---|---|
| `docker-compose.yml` | Core 9-service stack (baseline) |
| `docker-compose.override.yml` | Dev hot-reload overlay (auto-merged by Docker Compose) |
| `docker-compose.prod.yml` | Production overlay — no dev mounts |
| `docker-compose.ssl.yml` | SSL / Let's Encrypt overlay |
| `docker-compose-chroma-addon.yml` | Optional isolated ChromaDB addon |

---

## Development Without Docker

### Backend (standalone)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Point .env DB_HOST=localhost, MILVUS_HOST=localhost, etc.
python manage.py migrate
python manage.py setup_container_data   # loads demo data
python manage.py runserver 0.0.0.0:8000

# Start Celery worker (separate terminal)
celery -A core worker -l info
```

### Frontend (standalone)

```bash
cd frontend/my-sveltekit-app
npm install
npm run dev        # dev server at http://localhost:5173
npm run build      # production build
npm run check      # svelte-check type checking
npm run lint       # ESLint
```

The Vite dev server proxies `/api` requests to the backend. Set the `BACKEND_URL` env var to change the target (default `http://localhost:8000`).

---

## Project Structure

```
.
├── backend/                        # Django backend
│   ├── agent_orchestration/        # Core orchestration engine
│   │   ├── workflow_executor.py    # Sequential workflow execution
│   │   ├── parallel_executor.py    # Parallel branch execution
│   │   ├── chat_manager.py         # LLM interaction layer
│   │   ├── consumers.py            # WebSocket consumers (streaming)
│   │   ├── deployment_executor.py  # Public deployment execution
│   │   ├── workflow_generator.py   # AI Builder (Plan→Build→Verify→Critique)
│   │   ├── docaware/               # Per-agent RAG (Milvus integration)
│   │   └── websearch/              # Web search with Redis caching
│   ├── api/                        # Core REST views and serializers
│   ├── core/                       # Settings, URL routing, ASGI/WSGI
│   ├── llm_eval/                   # LLM evaluation framework
│   ├── mcp_servers/                # MCP server integration
│   ├── project_api_keys/           # Encrypted per-project API key storage
│   ├── public_chatbot/             # Public-facing chatbot (isolated CORS)
│   ├── templates/                  # Project template system
│   ├── users/                      # Custom User model
│   └── vector_search/              # Milvus indexing and search
├── frontend/my-sveltekit-app/
│   └── src/
│       ├── routes/                 # SvelteKit pages
│       │   └── features/intellidoc/  # Main project UI
│       └── lib/
│           ├── components/         # Svelte 5 UI components
│           ├── services/           # API clients and WebSocket
│           ├── stores/             # Svelte state stores
│           └── types.ts            # Shared TypeScript types
├── nginx/                          # Nginx reverse proxy config
├── scripts/                        # Deployment and utility scripts
├── docker-compose.yml              # Core service definitions
├── docker-compose.override.yml     # Dev hot-reload overlay
├── docker-compose.prod.yml         # Production overlay
├── docker-compose.ssl.yml          # SSL overlay
├── docker-compose-chroma-addon.yml # ChromaDB addon
└── .env.example                    # Environment variable template
```

---

## API Overview

All endpoints are under `/api/`. Authentication uses JWT Bearer tokens — obtain tokens via `/api/token/` and pass them as `Authorization: Bearer <token>`.

| Group | Base path | Description |
|---|---|---|
| Projects | `/api/projects/` | Create, list, update, delete projects |
| Workflows | `/api/projects/{id}/workflows/` | Workflow CRUD and execution |
| Workflow execution | `/api/projects/{id}/workflows/{id}/execute/` | Trigger a workflow run |
| Document processing | `/api/projects/{id}/process_documents/` | Upload and index documents |
| Vector search | `/api/projects/{id}/search/` | Search indexed documents |
| LLM configuration | `/api/llm/` | Multi-provider LLM settings |
| Per-project API keys | `/api/project-api-keys/` | Encrypted API key management |
| DocAware / RAG | `/api/agent-orchestration/` | DocAware search and orchestration |
| Public chatbot | `/api/public-chatbot/` | Unauthenticated chatbot endpoint |
| Workflow deployment | `/api/workflow-deploy/{project_id}/` | Public deployment (no auth) |
| MCP servers | `/api/mcp-servers/` | MCP server configuration |
| Templates | `/api/templates/` | Dynamic project template registry |
| Auth | `/api/token/`, `/api/token/refresh/` | JWT obtain and refresh |

WebSocket endpoint: `ws://localhost/ws/agent-orchestration/{project_id}/` — used for streaming execution updates, human-in-the-loop messages, and keep-alive pings.

---

## License

MIT License — see `LICENSE` for details.
