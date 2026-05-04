#!/bin/bash
# Install repo-local git hooks into .git/hooks/.
# Idempotent — safe to re-run.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "Not a git repo: $PWD" >&2; exit 1; }
HOOK_SRC_DIR="$SCRIPT_DIR/git-hooks"
HOOK_DST_DIR="$REPO_ROOT/.git/hooks"

if [ ! -d "$HOOK_SRC_DIR" ]; then
    echo "Hook source dir missing: $HOOK_SRC_DIR" >&2
    exit 1
fi

mkdir -p "$HOOK_DST_DIR"
for hook in "$HOOK_SRC_DIR"/*; do
    [ -f "$hook" ] || continue
    name="$(basename "$hook")"
    cp "$hook" "$HOOK_DST_DIR/$name"
    chmod +x "$HOOK_DST_DIR/$name"
    echo "✓ installed $name → $HOOK_DST_DIR/$name"
done
