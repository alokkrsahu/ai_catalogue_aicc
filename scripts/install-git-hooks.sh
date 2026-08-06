#!/usr/bin/env bash
#
# Installs the repository's git hooks. Git does not version .git/hooks, so every
# clone must run this once.
#
#   ./scripts/install-git-hooks.sh
#
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
hooks_src="$repo_root/scripts/git-hooks"
hooks_dst="$(git -C "$repo_root" rev-parse --git-path hooks)"

mkdir -p "$hooks_dst"

installed=0
for hook in "$hooks_src"/*; do
    [ -f "$hook" ] || continue
    name="$(basename "$hook")"
    cp "$hook" "$hooks_dst/$name"
    chmod +x "$hooks_dst/$name"
    echo "installed: $name"
    installed=$((installed + 1))
done

echo
echo "$installed hook(s) installed into $hooks_dst"
echo "The pre-commit hook blocks commits containing secrets. This repository is"
echo "public, so a pushed secret is compromised permanently — rotate rather than"
echo "delete if one ever slips through."
