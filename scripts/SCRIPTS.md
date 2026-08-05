# Scripts Guide

Every shell script in this directory, verified against its source. Deeper context lives in [`../docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md).

> **All of these except `production.sh` run the development stack.** `docker-compose.override.yml` sits in the repository root, so Docker Compose auto-merges it into any bare `docker compose …` command — which means `runserver`, `DEBUG=True`, and the Vite dev server. Only `production.sh` passes `-f docker-compose.yml -f docker-compose.prod.yml` to exclude it.

---

## Which script to use?

| Scenario | Script | Downtime |
|---|---|---|
| Code changes (`.py`, `.svelte`, `.ts`) | `quick-deploy.sh` | ~2 s |
| New migrations | `quick-deploy.sh` | ~2 s |
| nginx config changes | `quick-deploy.sh` | 0 s |
| New pip/npm packages | `rebuild-deploy.sh` | ~10 s |
| Dockerfile changes | `rebuild-deploy.sh` | ~10 s |
| Restart everything, no rebuild | `restart-dev.sh` | ~1–2 min |
| Fresh install / infra changes | `start-dev.sh` | ~8–12 min |
| Production mode | `production.sh` | see the warning below |
| First-time TLS certificate | `setup-ssl.sh` | interactive |
| Renew TLS certificate | `renew-ssl.sh` | 0 s |
| Reclaim disk (keeps data) | `docker-cleanup.sh` | full stop |
| Destroy everything | `reset.sh` | irreversible |

---

## Day-to-day

### `quick-deploy.sh` — the common case

```bash
./scripts/quick-deploy.sh
```

`git pull` → `migrate` → `collectstatic` → `touch /app/core/settings.py` to trigger Django's autoreload → `nginx -s reload`. Every exec step is `|| true`, so a partial failure will not abort it.

This works only because the backend runs `runserver` against a bind mount. It is a development deploy path, not a production one.

### `rebuild-deploy.sh` — dependency or image changes

```bash
./scripts/rebuild-deploy.sh
```

`git pull` → builds `backend` and `frontend-dev` while the old containers keep serving → migrates → force-recreates both → polls `http://localhost:8000/admin/` for up to 180 s → reloads nginx. Databases stay up throughout.

### `restart-dev.sh` — bounce the stack

Same ordered, health-gated startup as `start-dev.sh` but with no build and no image pull. This is the everyday "turn it off and on again".

### `start-dev.sh` — full rebuild

Validates that `.env` exists and that `MILVUS_ROOT_*` and `MINIO_ROOT_*` are non-empty, creates `./volumes` and `./logs`, prunes builders older than 24 h, builds with `--no-cache`, then starts nine groups in dependency order with health gates: postgres → etcd + minio → milvus (240 s) → chromadb → redis → backend → frontend-dev → nginx → pgadmin + attu.

Two stale pointers in its closing output: it recommends `start.sh` for production (superseded by `production.sh`) and references a `README-DOCKER.md` that does not exist.

---

## Production and TLS

### `production.sh`

The only script that runs the production overlay:

```bash
./scripts/production.sh [--ssl] [--rebuild]
```

Sets `ENVIRONMENT=production`, `DEBUG=False`, and starts with `-f docker-compose.yml -f docker-compose.prod.yml`.

> **This path does not currently work.** `Dockerfile.prod` runs `gunicorn ai_catalogue.wsgi:application`, but the Django project package is `core` — there is no `ai_catalogue` module, so Gunicorn exits immediately. The health gate also polls `/health/`, which is not a registered route. Both are tracked as B1 and B2 in [`../docs/KNOWN_ISSUES.md`](../docs/KNOWN_ISSUES.md).

### `setup-ssl.sh`

Interactive first-time Let's Encrypt issuance. Writes `DOMAIN_NAME` and `SSL_EMAIL` into `.env`, checks DNS against your public IP, brings up nginx with the SSL overlay, runs `certbot certonly --webroot` (dry run first), then **rewrites `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` and `ALLOWED_HOSTS` in `.env`** and restarts.

### `renew-ssl.sh`

Renews using the **host's** certbot, not the container — and hardcodes `/home/alokkrsahu/ai_catalogue`. It relies on a `deploy_hook` in the renewal config to copy certificates into `nginx/ssl/` and reload nginx. Note that its success check always reports 0 because of `set -e`.

---

## Maintenance

| Script | What it does |
|---|---|
| `docker-cleanup.sh` | Interactive. Stops the stack, removes exited containers, dangling images, unused networks and build cache. **Never touches volumes.** Its claim that `./volumes/*` holds preserved data is wrong — those directories are mounted by nothing. |
| `stop.sh` | Stops frontend, nginx, backend, milvus, postgres, etcd, minio, pgadmin. **Leaves `redis`, `chromadb`, `attu` and `frontend-dev` running** — use `docker compose stop` if you want everything down. |
| `fix-frontend-cache.sh` | Deletes the Vite caches to clear stale-chunk 404s. |
| `fix-dependencies.sh` | Wipes `node_modules` and `package-lock.json`, reinstalls, runs `npm audit fix --force`. Note that deleting the lockfile breaks the production image's `npm ci` until it is regenerated. |
| `reset.sh` | **Destructive.** `docker compose down -v`, deletes `./volumes` and `./logs`, wipes frontend and backend caches. Destroys the database, every uploaded document, and all vector data. There is no backup tooling in this repository — take a dump first (see DEPLOYMENT.md §9). |

---

## Superseded

Kept for reference; prefer the alternatives above.

| Script | Why |
|---|---|
| `start.sh` | Old production script. Uses the legacy hyphenated `docker-compose` binary, fixed `sleep` waits instead of health checks, no credential validation, and starts the prod `frontend` service. Use `production.sh`. |
| `start-local.sh` | Near-duplicate of `start-dev.sh`. |
| `git-pull.sh` / `git-push.sh` | Interactive git wrappers. `git-push.sh` does `git add .`, renames the branch to `main` and force-sets upstream — use git directly. |
| `debug_model_cache.sh`, `test_cache_detection.sh` | Diagnostics for the sentence-transformers cache. |
| `start-dev-updated.sh.backup` | Dead file. |

Also here, and not deployment-related: `analyze_experiment_logs.py`, `extract_experiment_metrics.py`, `check_evaluation_times.py` — research utilities that bootstrap Django and query the evaluation models.

## Scripts in `backend/`

**All of them are legacy and non-functional on this host.** `check_and_migrate.sh`, `run_migration.sh`, `run_migration_fixed.sh`, `cleanup_milvus_files.sh` and `test_setup.sh` hardcode a macOS developer path (`/Users/alok/Documents/AICC/...`) and a `venv` that does not exist. `setup_postgres.sh` predates Docker. `workflow_complete_fix.sh` and `workflow_fix_applied.sh` only echo text and execute nothing.

Use `docker compose exec backend python manage.py <command>` instead.
