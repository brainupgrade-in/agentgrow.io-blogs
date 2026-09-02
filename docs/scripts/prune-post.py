#!/usr/bin/env python3
"""prune-post.py — take a post out of the index without taking it off the site.

Why (2026-09-03, todo/agentgrow-blog-traffic-recovery.md Phase 2): Google had
refused to index 22 of 90 posts ("Crawled — currently not indexed", a quality
verdict) and the corpus carried near-duplicate pairs splitting one query. A
smaller corpus that is fully indexed signals more than a large one that is a
quarter rejected. Nothing is deleted: a deleted URL 404s every LinkedIn post,
Telegram message and email that ever linked it.

Two operations, both idempotent:

  --canonical-to <keeper-slug>   consolidate: point <link rel="canonical"> at the
                                 keeper (the page stays live and readable; Google
                                 credits the keeper). Use when a sibling covers
                                 the same intent.
  --noindex                      keep the page reachable, tell Google not to
                                 index it: <meta name="robots" content="noindex,follow">.
                                 Use when no sibling covers the intent.
  --undo                         remove both (canonical back to self, robots meta
                                 removed) — the exit path every gate needs (#140).

regenerate_indexes.py drops a post from posts-data.json / sitemap.xml / the
static index when its canonical points elsewhere or it carries noindex, so
related-links.py stops offering it as a candidate on the next --all run.

Usage:
  python3 docs/scripts/prune-post.py <slug> --canonical-to <keeper-slug>
  python3 docs/scripts/prune-post.py <slug> --noindex
  python3 docs/scripts/prune-post.py <slug> --undo
"""
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent
POSTS = DOCS / "posts"
BASE = "https://agentgrow.io/blog/posts/"

CANON_RE = re.compile(r'<link\b(?=[^>]*\brel="canonical")[^>]*>', re.I)   # attribute order agnostic (#144a)
ROBOTS_RE = re.compile(r'\s*<meta\b(?=[^>]*\bname="robots")[^>]*>', re.I)
VIEWPORT_RE = re.compile(r'<meta\b[^>]*\bname="viewport"[^>]*>', re.I)
NOINDEX_TAG = '<meta name="robots" content="noindex,follow">'


def canonical_of(html):
    m = CANON_RE.search(html)
    if not m:
        return None
    h = re.search(r'href="([^"]*)"', m.group(0))
    return h.group(1) if h else None


def set_canonical(html, url):
    tag = f'<link rel="canonical" href="{url}">'
    if CANON_RE.search(html):
        return CANON_RE.sub(tag, html, count=1)
    return VIEWPORT_RE.sub(lambda m: m.group(0) + "\n  " + tag, html, count=1)


def set_noindex(html, on):
    html = ROBOTS_RE.sub("", html)
    if on:
        html = VIEWPORT_RE.sub(lambda m: m.group(0) + "\n  " + NOINDEX_TAG, html, count=1)
    return html


def main():
    args = sys.argv[1:]
    if not args or args[0].startswith("--"):
        print(__doc__)
        return 2
    slug = args[0].replace(".html", "").split("/")[-1]
    path = POSTS / f"{slug}.html"
    if not path.exists():
        print(f"prune-post: no such post {path}", file=sys.stderr)
        return 2
    html = path.read_text(encoding="utf-8")
    self_url = BASE + slug + ".html"

    if "--undo" in args:
        new = set_noindex(set_canonical(html, self_url), False)
        action = "undo → canonical self, no robots meta"
    elif "--noindex" in args:
        new = set_noindex(set_canonical(html, self_url), True)
        action = "noindex,follow"
    elif "--canonical-to" in args:
        keeper = args[args.index("--canonical-to") + 1].replace(".html", "").split("/")[-1]
        kpath = POSTS / f"{keeper}.html"
        if not kpath.exists():
            print(f"prune-post: keeper {kpath} does not exist", file=sys.stderr)
            return 2
        khtml = kpath.read_text(encoding="utf-8")
        kc = canonical_of(khtml)
        if kc and kc != BASE + keeper + ".html":
            print(f"prune-post: keeper {keeper} is itself canonicalised to {kc} — chain refused", file=sys.stderr)
            return 2
        if 'name="robots"' in khtml and "noindex" in khtml:
            print(f"prune-post: keeper {keeper} is noindexed — refused", file=sys.stderr)
            return 2
        new = set_noindex(set_canonical(html, BASE + keeper + ".html"), False)
        action = f"canonical → {keeper}"
    else:
        print(__doc__)
        return 2

    if new == html:
        print(f"prune-post: {slug}: unchanged ({action})")
        return 0
    path.write_text(new, encoding="utf-8")
    print(f"prune-post: {slug}: {action}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
