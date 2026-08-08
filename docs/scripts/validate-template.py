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
  - the structural shell classes site-header / container-narrow / site-footer
  - a well-formed viewport meta

The last two were added 2026-08-08. The marker checks above are satisfiable by a
two-line skeleton — `<nav>` matches ANY nav, `<footer>` ANY footer, and the
stylesheet check is a substring test — so this lint passed
`flat-rate-vs-usage-pricing-marketing-automation.html` even though it shipped
live with no site chrome, no `.container-narrow` wrapper (so blog.css styled
nothing) and a mangled `content="width=device-1.0"` viewport. Checking for the
class names blog.css actually keys off is what makes this lint mean what its
docstring always claimed.

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
    # Brand suffix in <title> — the tab/SERP title must end with "AgentGrow"
    # (any separator; an optional trailing "Blog" is fine). Added 2026-07-20
    # after 10 posts shipped with no branding suffix.
    (
        '<title> "… — AgentGrow" brand suffix',
        lambda h: re.search(r'AgentGrow(?:\s+Blog)?\s*</title>', h) is not None,
    ),
    # JSON-LD author must be the founder (Person / Rajesh Gheware), never the
    # Organization. Added 2026-07-20 after 17 posts drifted to Organization/
    # AgentGrow (one malformed as Person/AgentGrow). Publisher stays Organization.
    (
        'JSON-LD author = Person/Rajesh Gheware',
        lambda h: re.search(r'"@type"\s*:\s*"Person"\s*,\s*"name"\s*:\s*"Rajesh Gheware"', h) is not None,
    ),
    # Structural shell (2026-08-08). blog.css keys off these class names — a post
    # without them renders as unstyled raw HTML even though it links the
    # stylesheet. `bin/apply-blog-shell.py` guarantees them pre-gate; this is the
    # fail-loud backstop at pre-commit + CI.
    (
        'site-header chrome (class="site-header")',
        lambda h: "site-header" in h,
    ),
    (
        'article width wrapper (class="container-narrow")',
        lambda h: "container-narrow" in h,
    ),
    (
        'site-footer chrome (class="site-footer")',
        lambda h: "site-footer" in h,
    ),
    # A model-mangled viewport ("width=device-1.0") breaks mobile rendering and
    # nothing else in the pipeline looks at it.
    (
        'viewport meta "width=device-width"',
        lambda h: re.search(
            r'<meta\s+name="viewport"\s+content="[^"]*width=device-width', h) is not None,
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
