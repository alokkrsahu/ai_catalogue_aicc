# Security

**This repository is public.** Anything committed here is world-readable the moment it is pushed, and permanently — deleting a file or rewriting history does not reach clones, forks, or GitHub's own caches. The only remedy for an exposed credential is to **rotate it**.

---

## Never commit

| Category | Examples |
|---|---|
| Environment files | `.env`, `.env.local`, `backend/.env` (only `.env.example` belongs in git) |
| Provider API keys | OpenAI `sk-…`, Anthropic `sk-ant-…`, Google `AIza…` |
| Encryption keys | `API_KEY_ENCRYPTION_KEY`, `PROJECT_API_KEY_ENCRYPTION_KEY` (Fernet: 43 chars + `=`) |
| Django | `DJANGO_SECRET_KEY` |
| Infrastructure | `DB_PASSWORD`, `REDIS_PASSWORD`, `MILVUS_ROOT_PASSWORD`, `MINIO_ROOT_PASSWORD`, `PGADMIN_PASSWORD` |
| Certificates & keys | `*.pem`, `*.key`, `id_rsa`, `*.p12`, `*.pfx` |
| Data | database dumps (`*.sql`, `*.dump`), anything under `backup/`, uploaded `media/` |

Configuration belongs in `.env` (git-ignored) and is read with `os.getenv()`. Compose files reference variables — `${VAR:?message}` when required, `${VAR:-default}` only when the default is genuinely non-sensitive.

## Install the pre-commit hook

Git does not version `.git/hooks`, so **every clone must do this once**:

```bash
./scripts/install-git-hooks.sh
```

The hook inspects only staged content and blocks the commit if it finds an environment file, a private key, a database dump, a `backup/` path, or a value shaped like a provider key, Fernet key, AWS key or hardcoded credential. It prints the offending line with the value redacted.

It is a safety net, not a guarantee — it cannot recognise every secret format. If you are certain a match is a false positive: `git commit --no-verify`.

## If a secret is exposed

Assume it is compromised from the moment of the push. Do not start by deleting it.

1. **Rotate it immediately** at the source (provider console, `ALTER USER`, new Fernet key).
2. **Re-encrypt if required.** `PROJECT_API_KEY_ENCRYPTION_KEY` cannot simply be swapped — stored ciphertext must be re-encrypted. Use the documented procedure: [`docs/DEPLOYMENT.md` §11](docs/DEPLOYMENT.md#11-rotating-encryption-keys).
3. **Remove the value** from the working tree and replace it with an env lookup.
4. **Check the blast radius** — what did that credential unlock, and was it used?

### Known historical exposure

A Fernet key was committed as the default for `API_KEY_ENCRYPTION_KEY` in `docker-compose.yml` and is present in five commits in this repository's history. It has been **rotated** (2026-08-05) and the default removed; the variable is now required. At the time of rotation it encrypted zero rows, so nothing was decryptable with it. It must never be reintroduced.

## Reporting a vulnerability

Please report privately rather than opening a public issue: **aimlcompetencycentre@it.ox.ac.uk**.

## Operational notes

- Only nginx (ports 80/443) is published on all interfaces. PostgreSQL, Redis, Milvus, the Django port, pgAdmin, Attu and the frontends bind `127.0.0.1`; reach them with an SSH tunnel.
- Redis enforces `requirepass`. The cache holds fetched web-page content, so write access to it can influence LLM answers.
- LLM keys are stored **per project**, encrypted at rest with a key derived from `PROJECT_API_KEY_ENCRYPTION_KEY` and the project id. There is no environment-variable fallback on the workflow path.
- `DEBUG` defaults to `False`. With `DEBUG=False`, a missing or publicly-known `DJANGO_SECRET_KEY` stops startup rather than being used silently.

Verified defects that are still open are tracked in [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md).
