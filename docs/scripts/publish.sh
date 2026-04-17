#!/bin/bash
# =============================================================================
# AGENTGROW BLOG PUBLISH SCRIPT
# Run after creating/editing a post. Rebuilds indexes, commits, pushes.
# Usage: ./docs/scripts/publish.sh "Commit message"
# =============================================================================
#
# STEP 1 rebuilds docs/posts-data.json and docs/sitemap.xml from the HTML
# files in docs/posts/ (the source of truth). Never hand-edit those two
# files — they will be clobbered. Edit docs/posts/<slug>.html + run this.
# =============================================================================

set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_DIR"

PYTHON="${PYTHON:-python3}"
BLOG_BASE="https://agentgrow.io/blog"

COMMIT_MSG="${1:-Auto-publish blog update}"
shift 2>/dev/null || true

echo "=========================================="
echo "📝 AGENTGROW BLOG PUBLISH PIPELINE"
echo "=========================================="

echo ""
echo "1️⃣  Regenerating posts-data.json + sitemap.xml from disk..."
$PYTHON docs/scripts/regenerate_indexes.py

# Capture HEAD before commit so we can diff against it to find new posts.
PREV_HEAD="$(git rev-parse HEAD)"

echo ""
echo "2️⃣  Git commit & push..."
git pull origin main --rebase 2>&1 | tail -2
git add -A
git commit -m "$COMMIT_MSG" 2>/dev/null && echo "   ✅ Committed: $COMMIT_MSG" || echo "   ℹ️  Nothing new to commit"
git push origin main 2>&1 | tail -2

# ─── STEP 3: Collect URLs to submit ──────────────────────────────────────────
# CLI args after the commit message take priority; else diff against PREV_HEAD.
URLS=("$@")
if [ ${#URLS[@]} -eq 0 ]; then
    echo ""
    echo "3️⃣  Auto-detecting new/modified post URLs..."
    while IFS= read -r file; do
        if [[ "$file" == docs/posts/*.html ]]; then
            stem="${file#docs/posts/}"
            URLS+=("${BLOG_BASE}/posts/${stem}")
        fi
    done < <(git diff --name-only "$PREV_HEAD" HEAD -- 'docs/posts/*.html' 2>/dev/null)
fi

if [ ${#URLS[@]} -eq 0 ]; then
    echo "   ℹ️  No new post URLs detected. Skipping indexing."
else
    echo "   Found ${#URLS[@]} URL(s) to submit"
    echo ""
    echo "4️⃣  Submitting to IndexNow + Google Indexing API..."
    $PYTHON docs/scripts/submit_indexing.py "${URLS[@]}" || echo "   ⚠️  Indexing submission had errors (non-blocking)"
fi

echo ""
echo "=========================================="
echo "✅ PUBLISH PIPELINE COMPLETE"
echo "=========================================="
