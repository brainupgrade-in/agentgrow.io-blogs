#!/usr/bin/env python3
"""Regenerate docs/posts-data.json and docs/sitemap.xml from docs/posts/*.html.

The HTML files are the source of truth; every index artefact is derived. Run
this after creating/editing/deleting any post. docs/scripts/publish.sh does
this automatically; .github/workflows/validate-indexes.yml enforces it in CI.

Safe to run repeatedly — output is deterministic for a given input tree.
"""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# docs/scripts/regenerate_indexes.py -> docs/
DOCS = Path(__file__).resolve().parent.parent
POSTS_DIR = DOCS / "posts"
JSON_PATH = DOCS / "posts-data.json"
SITEMAP_PATH = DOCS / "sitemap.xml"

BASE = "https://agentgrow.io/blog"


def extract_meta(html, attr, value):
    pat1 = rf'<meta\s+{attr}="{re.escape(value)}"\s+content="([^"]*)"'
    pat2 = rf'<meta\s+content="([^"]*)"\s+{attr}="{re.escape(value)}"'
    m = re.search(pat1, html) or re.search(pat2, html)
    return m.group(1) if m else None


def html_unescape(s):
    if s is None:
        return s
    return (
        s.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&#x27;", "'")
    )


def extract_date(html):
    """Try every known date location. Returns ISO YYYY-MM-DD or None."""
    # JSON-LD datePublished
    m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
    if m:
        return m.group(1)[:10]
    # article:published_time meta
    iso = extract_meta(html, "property", "article:published_time")
    if iso:
        return iso[:10]
    return None


def extract_category(html, existing=None):
    """Extract category. Priority order:
    1. existing JSON entry (preserve hand-curated taxonomy — avoids 1-post
       singleton categories appearing on the UI when a post's
       article:section meta disagrees with what the owner categorized it as)
    2. badge CSS class (legacy agentgrow template)
    3. article:section meta tag (fallback for posts not yet in JSON)
    4. "Strategy" fallback
    """
    if existing:
        if existing.get("category") and existing["category"] not in (
            "ca-marketing",
            "seo-guide",
        ):
            return existing["category"]
        cats = existing.get("categories")
        if cats and isinstance(cats, list):
            return cats[0].replace("-", " ").title()

    m = re.search(r'class="badge\s+badge-([a-z0-9-]+)"', html)
    if m:
        slug = m.group(1)
        if slug == "how-to":
            return "How-To"
        return " ".join(w.capitalize() for w in slug.split("-"))

    section = extract_meta(html, "property", "article:section")
    if section:
        return html_unescape(section).strip()

    return "Strategy"


def extract_read_time(html, existing=None):
    if existing and existing.get("readTime"):
        return existing["readTime"]
    # Try rendered markup like "7 min read"
    m = re.search(r"(\d+)\s*min\s*read", html, re.IGNORECASE)
    if m:
        return f"{m.group(1)} min read"
    # Estimate from word count
    text = re.sub(r"<script[\s\S]*?</script>", " ", html)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    words = len(re.findall(r"\w+", text))
    return f"{max(3, round(words / 220))} min read"


def extract_tags(html, existing=None):
    if existing and existing.get("tags"):
        return existing["tags"]
    # Try meta keywords
    kw = extract_meta(html, "name", "keywords")
    if kw:
        return [k.strip() for k in kw.split(",") if k.strip()]
    return []


def format_published(iso_date):
    """Convert 2026-04-01 -> 'Apr 1, 2026' (matches existing schema)."""
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return dt.strftime("%b %-d, %Y")
    except ValueError:
        return iso_date


def load_existing_by_slug():
    if not JSON_PATH.exists():
        return {}
    with open(JSON_PATH) as f:
        data = json.load(f)
    result = {}
    for p in data:
        slug = p.get("slug")
        if slug:
            result[slug] = p
    return result


def build_entry(slug, html, existing=None):
    """Build one posts-data.json entry from post HTML."""
    existing = existing or {}

    og_title = extract_meta(html, "property", "og:title")
    if not og_title:
        # JSON-LD headline
        m = re.search(r'"headline"\s*:\s*"([^"]+)"', html)
        og_title = m.group(1) if m else existing.get("title", slug)
    title = html_unescape(og_title).strip()

    desc = extract_meta(html, "name", "description") or extract_meta(
        html, "property", "og:description"
    )
    if not desc:
        m = re.search(r'"description"\s*:\s*"([^"]+)"', html)
        desc = m.group(1) if m else existing.get("excerpt") or existing.get("description", "")
    desc = html_unescape(desc) if desc else ""

    iso_date = extract_date(html) or existing.get("date") or "2026-01-01"

    og_image = extract_meta(html, "property", "og:image")
    if og_image:
        # Normalize to blog-relative path: strip BASE prefix if present
        image = og_image.replace(f"{BASE}/", "").replace("https://agentgrow.io/blog/", "")
    else:
        image = existing.get("image") or f"images/{slug}.jpg"

    category = extract_category(html, existing)
    read_time = extract_read_time(html, existing)
    tags = extract_tags(html, existing)

    return {
        "title": title,
        "slug": slug,
        "category": category,
        "excerpt": desc,
        "description": desc,
        "publishedAt": format_published(iso_date),
        "date": iso_date,
        "readTime": read_time,
        "image": image,
        "tags": tags,
        "url": f"posts/{slug}.html",
    }


def is_redirect_stub(html):
    return bool(re.search(r'<meta\s+http-equiv="refresh"', html[:500], re.IGNORECASE))


def regenerate_posts_json():
    existing_by_slug = load_existing_by_slug()
    entries = []
    for post_file in sorted(POSTS_DIR.glob("*.html")):
        slug = post_file.stem
        html = post_file.read_text(encoding="utf-8")
        if is_redirect_stub(html):
            continue
        entries.append(build_entry(slug, html, existing_by_slug.get(slug)))
    # Sort newest-first by ISO date (the frontend re-sorts by publishedAt but
    # sorted JSON is easier to diff and review)
    entries.sort(key=lambda e: e["date"], reverse=True)
    JSON_PATH.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return entries


def regenerate_sitemap(entries):
    newest = entries[0]["date"] if entries else "2026-01-01"
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        "  <url>",
        f"    <loc>{BASE}/</loc>",
        f"    <lastmod>{newest}</lastmod>",
        "    <changefreq>weekly</changefreq>",
        "    <priority>1.0</priority>",
        "  </url>",
        "  <url>",
        f"    <loc>{BASE}/guide/</loc>",
        "    <changefreq>monthly</changefreq>",
        "    <priority>0.8</priority>",
        "  </url>",
    ]
    for e in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{BASE}/posts/{e['slug']}.html</loc>")
        lines.append(f"    <lastmod>{e['date']}</lastmod>")
        lines.append("    <changefreq>monthly</changefreq>")
        lines.append("    <priority>0.7</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    lines.append("")
    SITEMAP_PATH.write_text("\n".join(lines), encoding="utf-8")


def main():
    entries = regenerate_posts_json()
    regenerate_sitemap(entries)

    required = ("slug", "title", "category", "excerpt", "publishedAt", "readTime", "date")
    missing = [
        (e["slug"], [k for k in required if not e.get(k)])
        for e in entries
        if not all(e.get(k) for k in required)
    ]
    if missing:
        print("ERROR: entries missing required fields:", file=sys.stderr)
        for slug, miss in missing:
            print(f"  {slug}: {miss}", file=sys.stderr)
        sys.exit(2)

    # Catch future-dated datePublished typos. inconsistent-content-smb.html
    # was committed 2026-03-05 with datePublished 2026-06-01 and pinned the
    # blog index top slot for 6 weeks before anyone noticed. Hard fail so
    # the publish.sh / CI drift check stops the push.
    today = datetime.now().strftime("%Y-%m-%d")
    future = [(e["slug"], e["date"]) for e in entries if e["date"] > today]
    if future:
        print(f"ERROR: {len(future)} post(s) have date in the future (today={today}):", file=sys.stderr)
        for slug, date in future:
            print(f"  {date}  {slug}", file=sys.stderr)
        print("Fix the article:published_time / JSON-LD datePublished in the post HTML.", file=sys.stderr)
        sys.exit(2)

    print(f"posts-data.json: {len(entries)} entries (newest {entries[0]['date']})")
    print(f"sitemap.xml    : {len(entries)} post URLs + blog + guide")


if __name__ == "__main__":
    main()
