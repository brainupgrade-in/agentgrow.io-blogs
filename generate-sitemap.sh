#!/usr/bin/env bash
# Generates docs/sitemap.xml from docs/posts-data.json
# Run after adding a new blog post: bash generate-sitemap.sh

set -euo pipefail
cd "$(dirname "$0")"

OUT="docs/sitemap.xml"

cat > "$OUT" <<'HEADER'
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://agentgrow.io/blog/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://agentgrow.io/blog/guide/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
HEADER

python3 -c "
import json
from datetime import datetime

SITE = 'https://agentgrow.io/blog'

with open('docs/posts-data.json') as f:
    posts = json.load(f)

for p in posts:
    slug = p['slug']
    dt = datetime.strptime(p['publishedAt'], '%b %d, %Y')
    iso = dt.strftime('%Y-%m-%d')
    print(f'''  <url>
    <loc>{SITE}/posts/{slug}.html</loc>
    <lastmod>{iso}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>''')
" >> "$OUT"

echo '</urlset>' >> "$OUT"

echo "Generated $OUT with $(grep -c '<url>' "$OUT") URLs"
