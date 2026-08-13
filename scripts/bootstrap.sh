#!/usr/bin/env bash
#
# First-run bootstrap for a fresh clone.
#
#   ./scripts/bootstrap.sh
#
# Brings a newly-started stack to a working, sensibly-secured state. Everything it
# does is idempotent: run it as often as you like. It never prints a secret except
# the generated admin password, which is shown exactly once.
#
# What it does, and why each step is not already covered by `docker compose up`:
#
#   1. Milvus root password — Milvus ships with the public default "Milvus" and
#      creates no other user. Nothing in the codebase rotates it, so without this
#      step every install shares a documented password.
#   2. LLM provider registry — the llm_eval comparison feature reads LLMProvider
#      rows that no migration or seeder creates, leaving the feature inert.
#   3. Administrator account — avoids the hardcoded admin@example.com /
#      adminpassword fallback that would otherwise be created.
#   4. Dashboard icons — delegates to the existing management command.
#
# Safe on an existing install: each step detects work already done and skips it.

set -uo pipefail

GRN=$'\033[0;32m'; YEL=$'\033[0;33m'; RED=$'\033[0;31m'; NC=$'\033[0m'
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

step()  { printf '\n%s==>%s %s\n' "$YEL" "$NC" "$1"; }
ok()    { printf '   %sok%s   %s\n' "$GRN" "$NC" "$1"; }
skip()  { printf '   --   %s\n' "$1"; }
fail()  { printf '   %sfail%s %s\n' "$RED" "$NC" "$1"; }

if [ ! -f .env ]; then
    fail ".env not found. Copy .env.example to .env and fill it in first."
    exit 1
fi
# shellcheck disable=SC1091
set -a; . ./.env; set +a

dc() { docker compose "$@"; }
bmanage() { docker compose exec -T backend python manage.py "$@"; }

step "Checking the stack is up"
if ! dc ps --status running --services 2>/dev/null | grep -q '^backend$'; then
    fail "backend is not running. Start the stack first (./scripts/start-dev.sh)."
    exit 1
fi
ok "backend is running"

# ---------------------------------------------------------------------------
# 1. Milvus root password
# ---------------------------------------------------------------------------
step "Milvus root password"
if [ "${MILVUS_ROOT_PASSWORD:-}" = "Milvus" ] || [ -z "${MILVUS_ROOT_PASSWORD:-}" ]; then
    NEW_MILVUS_PW="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
    if bmanage shell -c "
from pymilvus import connections, utility
connections.connect(alias='bs', host='${MILVUS_HOST:-milvus}', port='${MILVUS_PORT:-19530}', user='root', password='Milvus')
utility.reset_password('root', 'Milvus', '${NEW_MILVUS_PW}', using='bs')
print('ROTATED')
" 2>/dev/null | grep -q ROTATED; then
        if grep -q '^MILVUS_ROOT_PASSWORD=' .env; then
            python3 - "$NEW_MILVUS_PW" <<'PY'
import sys, re, pathlib
p = pathlib.Path('.env'); t = p.read_text()
p.write_text(re.sub(r'^MILVUS_ROOT_PASSWORD=.*$', f'MILVUS_ROOT_PASSWORD={sys.argv[1]}', t, flags=re.M))
PY
        else
            printf '\nMILVUS_ROOT_PASSWORD=%s\n' "$NEW_MILVUS_PW" >> .env
        fi
        ok "rotated away from the public default and written to .env"
        echo "        restart the backend so it picks up the new value:"
        echo "        docker compose up -d --no-deps backend"
    else
        skip "could not rotate (already changed, or Milvus unreachable) — verify manually"
    fi
else
    skip "already set to a non-default value"
fi

# ---------------------------------------------------------------------------
# 2. LLM provider registry
# ---------------------------------------------------------------------------
step "LLM provider registry (llm_eval)"
bmanage shell -c "
from users.models import LLMProvider
seed = [
    ('OpenAI',    'openai',    'https://api.openai.com/v1'),
    ('Anthropic', 'claude',    'https://api.anthropic.com/v1'),
    ('Google',    'gemini',    'https://generativelanguage.googleapis.com/v1beta'),
]
created = 0
for name, ptype, endpoint in seed:
    _, made = LLMProvider.objects.get_or_create(
        provider_type=ptype,
        defaults={'name': name, 'api_endpoint': endpoint, 'is_active': True,
                  'max_tokens': 4000, 'timeout_seconds': 30},
    )
    created += made
print(f'SEEDED {created} new, {LLMProvider.objects.count()} total')
" 2>/dev/null | grep SEEDED | sed 's/^/   ok   /' || skip "seeding failed — check the backend logs"

# ---------------------------------------------------------------------------
# 3. Administrator account
# ---------------------------------------------------------------------------
step "Administrator account"
ADMIN_EMAIL="${BOOTSTRAP_ADMIN_EMAIL:-admin@localhost}"
if bmanage shell -c "
from django.contrib.auth import get_user_model
print('EXISTS' if get_user_model().objects.filter(is_superuser=True).exists() else 'NONE')
" 2>/dev/null | grep -q EXISTS; then
    skip "a superuser already exists"
else
    ADMIN_PW="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
    if bmanage shell -c "
from django.contrib.auth import get_user_model
U = get_user_model()
u = U.objects.create_superuser(email='${ADMIN_EMAIL}', password='${ADMIN_PW}')
print('CREATED')
" 2>/dev/null | grep -q CREATED; then
        ok "created ${ADMIN_EMAIL}"
        printf '\n   %sSave this now — it is not stored and will not be shown again:%s\n' "$YEL" "$NC"
        printf '     email:    %s\n     password: %s\n\n' "$ADMIN_EMAIL" "$ADMIN_PW"
    else
        fail "could not create the administrator"
    fi
fi

# ---------------------------------------------------------------------------
# 4. Dashboard icons
# ---------------------------------------------------------------------------
step "Dashboard icons"
if bmanage restore_icons >/dev/null 2>&1; then
    ok "icons restored"
else
    skip "restore_icons failed — run it manually to see the error"
fi

printf '\n%sBootstrap complete.%s Open http://localhost and sign in.\n' "$GRN" "$NC"
echo "Next: create a project from a template, upload documents, run Start Processing,"
echo "then add a provider API key under the project's API key settings — LLM nodes"
echo "read per-project keys and there is no environment-variable fallback."
