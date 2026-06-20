#!/usr/bin/env python3
"""Structural template lint for docs/posts/*.html.

Every content post must ship the canonical blog chrome so it renders inside the
shared site shell instead of a self-contained inline-styled page. This catches
off-template drift (the 12-post backlog fixed 2026-06-20) before it lands.

A content post MUST contain:
  - the shared stylesheet  ../css/blog.css
  - a <nav> element        (site-header navigation)
  - a <footer> element     (site-footer chrome)
  - a BlogPosting JSON-LD block

Redirect stubs (files with <meta http-equiv="refresh">) are exempt.

Exit non-zero on any violation, printing the offending file + missing markers.
Run by .github/workflows/validate-indexes.yml; safe to run locally anytime.
"""
import re
import sys
from pathlib import Path

# docs/scripts/validate-template.py -> docs/posts
POSTS_DIR = Path(__file__).resolve().parent.parent / "posts"

# (label, compiled test) — each must be present in a content post.
CHECKS = [
    ("../css/blog.css", lambda h: "../css/blog.css" in h),
    ("<nav> element", lambda h: re.search(r"<nav[\s>]", h) is not None),
    ("<footer> element", lambda h: re.search(r"<footer[\s>]", h) is not None),
    (
        'BlogPosting JSON-LD',
        lambda h: re.search(r'"@type"\s*:\s*"BlogPosting"', h) is not None,
    ),
]


def is_redirect_stub(html):
    return bool(re.search(r'<meta\s+http-equiv="refresh"', html[:500], re.IGNORECASE))


def main():
    failures = []
    checked = 0
    for post in sorted(POSTS_DIR.glob("*.html")):
        html = post.read_text(encoding="utf-8")
        if is_redirect_stub(html):
            continue
        checked += 1
        missing = [label for label, test in CHECKS if not test(html)]
        if missing:
            failures.append((post.name, missing))

    if failures:
        print(
            f"Template lint: {len(failures)} off-template post(s) of {checked} checked:",
            file=sys.stderr,
        )
        for name, missing in failures:
            prefix = (
                f"::error file=docs/posts/{name}::"
                if __import__("os").environ.get("GITHUB_ACTIONS")
                else f"  FAIL  {name}: "
            )
            print(f"{prefix}missing {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    print(f"Template lint: clean ✓ ({checked} content posts)")


if __name__ == "__main__":
    main()
