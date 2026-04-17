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

COMMIT_MSG="${1:-Auto-publish blog update}"

echo "=========================================="
echo "📝 AGENTGROW BLOG PUBLISH PIPELINE"
echo "=========================================="

echo ""
echo "1️⃣  Regenerating posts-data.json + sitemap.xml from disk..."
$PYTHON docs/scripts/regenerate_indexes.py

echo ""
echo "2️⃣  Git commit & push..."
git pull origin main --rebase 2>&1 | tail -2
git add -A
git commit -m "$COMMIT_MSG" 2>/dev/null && echo "   ✅ Committed: $COMMIT_MSG" || echo "   ℹ️  Nothing new to commit"
git push origin main 2>&1 | tail -2

echo ""
echo "=========================================="
echo "✅ PUBLISH PIPELINE COMPLETE"
echo "=========================================="
