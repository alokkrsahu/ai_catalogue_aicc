# Deployment & Operations

**Audience:** engineers and operators running IntelliDoc.
**Scope:** Docker Compose stack, configuration, nginx, scripts, ports, persistence.

Everything below was verified against the compose files, Dockerfiles, nginx configs and scripts in this repository. Where the repository contains something that does not work, this document says so rather than describing the intent.

---

## 1. Compose file layout — read this first

| File | Role |
|---|---|
| `docker-compose.yml` | Base stack, **11 services** |
| `docker-compose.override.yml` | Development overlay — **auto-loaded by every bare `docker compose` command** |
| `docker-compose.prod.yml` | Production overlay (see the warning in §7) |
| `docker-compose.ssl.yml` | Certbot / Let's Encrypt overlay |
| `docker-compose-chroma-addon.yml` | Legacy; superseded by the base `chromadb` service |

> **The single most important operational fact:** because `docker-compose.override.yml` sits in the repository root, Docker Compose merges it automatically. Any plain `docker compose …` command therefore runs the **development** configuration — Django `runserver`, `DEBUG=True`, the Vite dev server, and `nginx.dev.conf`. The only way to exclude it is to name files explicitly:
>
> ```bash
> docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
> ```
>
> `scripts/production.sh` is the only script that does this.

### Services in the base stack

| Service | Image | Container |
|---|---|---|
| `postgres` | `postgres:15-alpine` | `ai_catalogue_postgres` |
| `redis` | `redis:7-alpine` | `ai_catalogue_redis` |
| `etcd` | `quay.io/coreos/etcd:v3.5.12` | `ai_catalogue_etcd` |
| `minio` | `minio/minio:RELEASE.2024-12-18T13-15-44Z` | `ai_catalogue_minio` |
| `milvus` | `milvusdb/milvus:v2.6.0` | `ai_catalogue_milvus` |
| `chromadb` | `chromadb/chroma:1.0.20` | `ai_catalogue_chromadb` |
| `backend` | build `./backend` | `ai_catalogue_backend` |
| `frontend` | build `./frontend` | `ai_catalogue_frontend` |
| `nginx` | `nginx:alpine` | `ai_catalogue_nginx` |
| `pgadmin` | `dpage/pgadmin4:latest` | `ai_catalogue_pgadmin` |
| `attu` | `zilliz/attu:latest` | `ai_catalogue_attu` |

The dev overlay adds a twelfth service, `frontend-dev` (`ai_catalogue_frontend_dev`), and replaces `frontend` in practice — when the overlay is active, `frontend` is not started.

Network: `ai_catalogue_network`, bridge driver, subnet `172.20.0.0/16` (Docker names it `ai_catalogue_ai_catalogue_network`).

---

## 2. Ports

Every published port binds `0.0.0.0`. Only the host firewall or cloud security group stands between these and the internet.

| Host port | Service | Notes |
|---|---|---|
| **80** | nginx | Primary entry point |
| **443** | nginx | TLS |
| 8000 | backend | Django direct, including `/admin/` |
| 5173 | frontend-dev | Vite dev server + HMR (dev overlay only) |
| 3000 | frontend | Production Node server (prod overlay only) |
| 5432 | postgres | Raw database access |
| 6379 | redis | **No password or ACL is configured** |
| 8001 | chromadb | Container port 8000; no auth, CORS `*` |
| 19530 | milvus | gRPC; authentication enabled |
| 9091 | milvus | HTTP — `/healthz`, `/webui/` |
| 8080 | pgadmin | Container port 80 |
| 3001 | attu | Milvus web UI; credentials must be entered manually |
| — | etcd, minio | Not published; container network only |

**Hardening note:** in a deployment reachable from the internet, only 80 and 443 should be exposed. Postgres, Redis, ChromaDB, Milvus, pgAdmin, Attu, the Django port and the Vite dev server should all be firewalled.

---

## 3. Configuration

Copy `.env.example` to `.env`. Note that **`.env.example` is currently incomplete** — it omits variables the compose stack reads, including `AICC_CHATBOT_OPENAI_API_KEY`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `CHROMADB_PORT`, `REDIS_PORT`, `DB_AUTH_METHOD`, `ENVIRONMENT`, `DOMAIN_NAME`, `SSL_EMAIL`, `PGADMIN_*`, `ATTU_*`, `VITE_BACKEND_URL` and `VITE_API_BASE_URL`. All of those have working defaults in `docker-compose.yml`, so the stack starts without them.

### Genuinely required

| Variable | Why |
|---|---|
| `PROJECT_API_KEY_ENCRYPTION_KEY` | No default. Fernet key encrypting per-project API keys at rest. |
| `MILVUS_ROOT_USER`, `MILVUS_ROOT_PASSWORD` | No default; `start-dev.sh` and `production.sh` abort if empty. |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | Same startup guards — see the note below. |
| `DJANGO_SECRET_KEY` | Has an insecure placeholder default; must be set for any real deployment. |
| At least one of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` | Otherwise no LLM node can execute. |

Generate the keys:

```bash
# Django secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Fernet key for PROJECT_API_KEY_ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> **Security issue to fix:** `docker-compose.yml` supplies a **literal, committed Fernet key** as the default for `API_KEY_ENCRYPTION_KEY`. Any deployment that does not set that variable is encrypting with a key published in this repository. Set `API_KEY_ENCRYPTION_KEY` explicitly in `.env`.

> **MinIO is required but unused.** The startup scripts refuse to run without `MINIO_ROOT_*`, yet Milvus is configured with `MINIO_ADDRESS: ""` and `COMMON_STORAGETYPE: local`, so it stores segments on its own volume and never contacts MinIO. Set the variables to satisfy the guard; expect the `minio` service to sit idle.

### Other variable groups

- **Database** — `DB_NAME` (`ai_catalogue_db`), `DB_USER` (`ai_catalogue_user`), `DB_PASSWORD`, `DB_PORT` (`5432`), `DB_AUTH_METHOD` (`md5`). `DB_HOST` is forced to `postgres` for the backend container. Tuning: `DB_CONN_MAX_AGE` (`300`, `600` in prod), `DB_CONNECT_TIMEOUT` (`60`), `DB_SSL_MODE` (`prefer`).
- **Vector stores** — `MILVUS_HOST`/`MILVUS_PORT` (forced to `milvus`/`19530` for the backend). `CHROMADB_PORT` is overloaded: it sets the ChromaDB **host** port (default `8001`) while the backend always talks to `chromadb:8000` internally.
- **Redis** — `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB` (`0`). Used as the Django cache backend and the web-search cache.
- **Django** — `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `ENVIRONMENT`, `JWT_ACCESS_TOKEN_LIFETIME` (60 min), `JWT_REFRESH_TOKEN_LIFETIME` (1440 min).
- **LLM** — `OPENAI_API_KEY` / `OPENAI_MODEL` (`gpt-3.5-turbo`), `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` / `GEMINI_MODEL` (`gemini-1.5-flash`), and `AICC_CHATBOT_OPENAI_API_KEY` — a **separate** key used only by the public chatbot so that public traffic never consumes the platform key.
- **Frontend** — `BACKEND_URL` (server-side SvelteKit, `http://backend:8000`), `VITE_BACKEND_URL` and `VITE_API_BASE_URL` (browser-facing; point these at your public origin).
- **Nginx / SSL** — `NGINX_HTTP_PORT`, `NGINX_HTTPS_PORT`, `DOMAIN_NAME`, `SSL_EMAIL`.
- **Admin UIs** — `PGADMIN_EMAIL`, `PGADMIN_PASSWORD`, `PGADMIN_PORT`, `ATTU_PORT`, `ATTU_HOST_URL`.

**Declared but read by nothing:** `DEVELOPMENT_MODE`, `FRONTEND_DEV_PORT`, `BACKEND_DEV_PORT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, and the whole Kubernetes/Azure block (`K8S_*`, `AZURE_*`, `AKS_*`, `ACR_*`, `HPA_*`, `PROMETHEUS_*`, `GRAFANA_*`) which only feeds the abandoned `k8s/` scripts (§8).

---

## 4. Images

| Dockerfile | Used by | Base | Runs |
|---|---|---|---|
| `backend/Dockerfile` | base `backend` | `python:3.13-slim-bookworm` | collectstatic → migrate → `setup_container_data` → **`runserver`** |
| `backend/Dockerfile.dev` | dev overlay | `python:3.13-slim` | `runserver`; no `COPY` — relies on the `./backend:/app` bind mount |
| `backend/Dockerfile.prod` | prod overlay | `python:3.13-slim` | collectstatic → migrate → **gunicorn (broken, §7)** |
| `frontend/Dockerfile` | base `frontend` | `node:20-alpine`, 2-stage | `node build/index.js` (`adapter-node`) |
| `frontend/Dockerfile.dev` | dev overlay | `node:20-alpine` | `npm run dev -- --host 0.0.0.0 --port 5173` |

Note that even the *base* (non-dev) backend image runs Django's development server. There is no Gunicorn path that currently works.

The backend image installs OCR/document tooling (poppler-utils, tesseract-ocr, antiword, unrtf) and audio tooling (ffmpeg, sox, flac) in best-effort layers that swallow failures — a build can succeed with those tools missing, which silently disables the corresponding extraction paths.

---

## 5. Nginx

There are four configs; three are ever mounted. **`nginx/nginx.conf` is dead** — the base compose `nginx` service mounts no configuration at all, so a base-only start serves nginx's stock page.

| Config | Mounted by | Notes |
|---|---|---|
| `nginx.dev.conf` | `docker-compose.override.yml` | The config in normal use |
| `nginx.prod.conf` | `docker-compose.prod.yml` | Rate limiting, gzip, asset caching, HSTS |
| `nginx.ssl.conf` | `docker-compose.ssl.yml` | Certbot webroot + real HTTP→HTTPS redirect |
| `nginx.conf` | *nothing* | Dead |

Routing (consistent across dev and prod):

| Path | Upstream | Timeout |
|---|---|---|
| `/` | frontend (`frontend-dev:5173` in dev) | 86400s on HTTP for HMR |
| `/api/public-chatbot*` | backend, **buffering off** for SSE streaming | 300s |
| `/api/workflow-deploy*` | backend (CORS handled by Django middleware) | 300s |
| all other `/api/*` | backend | **1500s (25 min)** for long document processing |
| `/admin/`, `/static/`, `/media/` | backend | default |
| `/health` | answered by nginx itself | — |

Body size limits: 500 MB in dev, 100 MB in prod.

Known nginx issues:

- **CORS wildcard fallback.** Both `nginx.dev.conf` and `nginx.prod.conf` map a `null` or empty `Origin` to `*`.
- **`nginx.ssl.conf` omits the 1500s timeouts**, so switching to the SSL overlay would break long document-processing calls at nginx's 60s default. It also sets `Access-Control-Allow-Origin: *` on `/api/public-chatbot/`.
- **Neither the dev nor prod config redirects HTTP to HTTPS** (the prod file has a comment claiming it does). Only `nginx.ssl.conf` does.
- **`nginx.dev.conf` couples this repo to a different project** — it declares `chatgpt_analytics_frontend` / `chatgpt_analytics_backend` upstreams and nginx will not start if those containers are absent from the shared network.
- Two cert layouts coexist: flat `nginx/ssl/{fullchain,privkey}.pem` (dev/prod) versus the Let's Encrypt `live/<domain>/` tree (`nginx.ssl.conf`).

---

## 6. Scripts

`scripts/SCRIPTS.md` holds the short decision table. Day-to-day:

| Task | Script | Effect |
|---|---|---|
| Code-only change (`.py`, `.svelte`, `.ts`) | `./scripts/quick-deploy.sh` | `git pull`, migrate, collectstatic, touch `core/settings.py` to trigger autoreload, reload nginx. ~2s. **Depends on `runserver` + bind mount, so it is a dev-mode path.** |
| New dependency or Dockerfile change | `./scripts/rebuild-deploy.sh` | Rebuilds `backend` + `frontend-dev`, recreates them, waits for health, reloads nginx. ~10s downtime. |
| First run / full rebuild | `./scripts/start-dev.sh` | Validates `.env`, prunes builders, `build --no-cache`, then nine health-gated startup steps. 8–12 min. |
| Restart without rebuilding | `./scripts/restart-dev.sh` | Same ordering, no build or pull. |
| Production mode | `./scripts/production.sh` | The only script that excludes the dev overlay. See §7. |
| First-time TLS issuance | `./scripts/setup-ssl.sh` | Interactive certbot webroot flow; rewrites CORS/CSRF/ALLOWED_HOSTS in `.env`. |
| Renew TLS | `./scripts/renew-ssl.sh` | Uses the **host** certbot, not the container. Hardcodes `/home/alokkrsahu/ai_catalogue`. |
| Reclaim disk | `./scripts/docker-cleanup.sh` | Prunes containers/images/networks/builders. Never touches volumes. |
| Destroy everything | `./scripts/reset.sh` | `down -v`, deletes `./volumes`, `./logs`, node_modules, caches. **Irreversible.** |

Caveats worth knowing:

- `scripts/stop.sh` is incomplete — it never stops `redis`, `chromadb`, `attu` or `frontend-dev`.
- `scripts/start.sh` and `scripts/start-local.sh` are superseded (`start.sh` still uses the legacy hyphenated `docker-compose` binary). `start-dev.sh` unhelpfully points readers at `start.sh` for production and at a `README-DOCKER.md` that does not exist.
- Several scripts poll ChromaDB's **deprecated `/api/v1/heartbeat`** while the compose healthcheck uses `/api/v2/heartbeat`.
- **Everything under `backend/*.sh` is legacy and non-functional here** — they hardcode a macOS path (`/Users/alok/Documents/AICC/...`) and a `venv` that does not exist. `workflow_complete_fix.sh` and `workflow_fix_applied.sh` only echo text.
- **There is no backup script anywhere in the repository** — no `pg_dump`, no volume export. See §9.

---

## 7. Production mode — current state

`docker-compose.prod.yml` and `Dockerfile.prod` describe a real production posture: Gunicorn with 4 workers, `DEBUG=False`, `SECURE_SSL_REDIRECT`, HSTS, tuned Postgres, resource limits. **That path does not currently start**, for two independent reasons:

1. **Wrong WSGI module.** `Dockerfile.prod` runs `gunicorn ai_catalogue.wsgi:application`. The Django project package is `core` — the file is `backend/core/wsgi.py` and `manage.py` sets `DJANGO_SETTINGS_MODULE=core.settings`. There is no `ai_catalogue` package, so Gunicorn exits with `ModuleNotFoundError`. Gunicorn itself is installed (`requirements.txt`), so the fix is the module path: `core.wsgi:application`.
2. **`/health/` is not a route.** `Dockerfile.prod`'s healthcheck, `docker-compose.prod.yml`, and `production.sh` all poll `http://localhost:8000/health/`, which is not registered in `core/urls.py` and returns 404. (nginx answers `/health` without a trailing slash itself, which does not help the container healthcheck.) Either add the route or point the healthcheck at `/admin/`.

Additionally, `deploy.replicas: 2` in the prod overlay is ignored by `docker compose` (it is a Swarm directive) and would in any case conflict with the fixed `8000:8000` and `3000:3000` host port bindings.

**Consequence:** the running deployment is the **development** stack — `Dockerfile.dev`, Django `runserver`, `DEBUG=True`, `DJANGO_DEBUG_TOOLBAR=True`, the Vite dev server, and `nginx.dev.conf`. Setting `DEBUG=False` in `.env` has no effect, because `docker-compose.override.yml` sets `DEBUG: "True"` in the service `environment` block, which takes precedence over `env_file`.

If you need a genuine production deployment, the minimum work is: fix the Gunicorn module path, add or redirect the health endpoint, and always start with `-f docker-compose.yml -f docker-compose.prod.yml`.

---

## 8. Kubernetes

`k8s/` contains a complete-looking manifest set (namespaces, Deployments, Services, PVCs, HPAs, Ingresses) plus `k8s/scripts/`. **It is abandoned and should not be used as-is:**

- `k8s/` is listed in `.gitignore`, so it is not tracked. Last touched 2025-09-03, while compose files have changed as recently as 2026-02-05.
- Image drift: Milvus `v2.5.15` vs `v2.6.0` in compose; etcd `v3.5.5` vs `v3.5.12`; MinIO an older release.
- **No Redis and no ChromaDB anywhere in the manifests**, though the backend now depends on Redis for health and the public chatbot requires ChromaDB.
- `k8s/base/configmap.yaml` carries a Milvus 2.4-era config with `mq.type: rocksmq`, a duplicated `common:` key, and a **plaintext MinIO password**.

The `K8S_*` / `AZURE_*` variables in `.env` exist only for these scripts.

---

## 9. Persistence and backup

Twelve named volumes (all `driver: local`):

| Volume | Holds |
|---|---|
| `postgres_data` | **All relational data** — users, projects, workflows, deployments, evaluations, encrypted API keys |
| `backend_media` / `backend_media_dev` | **Uploaded documents** (the dev volume is the one in use under the default overlay) |
| `milvus_data` | Project vector segments and indexes |
| `etcd_data` | Milvus metadata — losing this orphans every collection |
| `chromadb_data` | Public-chatbot knowledge base and embeddings |
| `redis_data` | AOF-persisted cache (web-search cache, rate limits) |
| `milvus_volumes` | Backend-side Milvus working files |
| `backend_logs` / `backend_logs_dev` | Application and error logs |
| `minio_data` | MinIO object store — effectively unused |
| `pgadmin_data` | pgAdmin server list and preferences |

`docker compose down -v` destroys all of them: the database, every uploaded document, all vectors and their metadata, and the chatbot index.

> **There is no backup tooling in this repository.** Before any destructive operation, take your own dump, e.g.:
>
> ```bash
> docker exec ai_catalogue_postgres pg_dump -U "$DB_USER" "$DB_NAME" > backup.sql
> docker run --rm -v ai_catalogue_backend_media_dev:/data -v "$PWD":/out alpine \
>   tar czf /out/media-backup.tar.gz -C /data .
> ```

The directories `./volumes/{postgres,milvus,etcd,minio}` are created by the startup scripts but **mounted by no compose file** — they are leftovers from an earlier bind-mount design and contain nothing. `docker-cleanup.sh` still describes them as preserved data, which is misleading.

---

## 10. Known infrastructure defects

Collected for triage; each is verifiable in the file cited.

| # | Issue | Location |
|---|---|---|
| 1 | Live deployment runs the dev stack with `DEBUG=True` and `runserver` | `docker-compose.override.yml` |
| 2 | `gunicorn ai_catalogue.wsgi` — module does not exist | `backend/Dockerfile.prod` |
| 3 | `/health/` healthcheck target is not a registered route | `Dockerfile.prod`, `docker-compose.prod.yml`, `production.sh` |
| 4 | Literal Fernet key committed as `API_KEY_ENCRYPTION_KEY` default | `docker-compose.yml` |
| 5 | Redis exposed on `0.0.0.0:6379` with no password | `docker-compose.yml` |
| 6 | ChromaDB exposed on `0.0.0.0:8001`, no auth, CORS `*` | `docker-compose.yml` |
| 7 | `nginx/nginx.conf` mounted by nothing; base nginx has no config | `docker-compose.yml` |
| 8 | Duplicate mount target `/etc/nginx/ssl` from two sources | `docker-compose.yml` |
| 9 | CORS maps `null`/empty Origin to `*` | `nginx.dev.conf`, `nginx.prod.conf` |
| 10 | `nginx.ssl.conf` lacks the long AI timeouts | `nginx.ssl.conf` |
| 11 | ChromaDB v1 vs v2 heartbeat mismatch between scripts and compose | `start-dev.sh`, `restart-dev.sh` |
| 12 | MinIO credentials gate startup but MinIO is unused | `start-dev.sh`, `production.sh` |
| 13 | `stop.sh` leaves redis, chromadb, attu, frontend-dev running | `scripts/stop.sh` |
| 14 | `backend/*.sh` hardcode a macOS path; two are echo-only | `backend/*.sh` |
| 15 | `deploy.replicas` is a no-op and conflicts with fixed host ports | `docker-compose.prod.yml` |
| 16 | `.env.example` missing ~14 variables the stack reads | `.env.example` |
| 17 | No backup tooling for any volume | repository-wide |
| 18 | `k8s/` drifted and untracked | `k8s/` |
| 19 | Port 8001 claimed by both `chromadb` and the legacy chroma addon | `docker-compose-chroma-addon.yml` |
| 20 | `nginx.dev.conf` requires another project's containers to be present | `nginx.dev.conf` |
