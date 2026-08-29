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
    # The load-bearing one. blog.css defines EVERY body-copy rule (p, h2, h3, ul,
    # li, table, .callout) under `.article-body …` and has no bare `article`
    # selector — so the 4 posts using `<article class="container-narrow">` had
    # correct width and zero typography. container-narrow alone is not enough.
    (
        'article body wrapper (class="article-body")',
        lambda h: "article-body" in h,
    ),
    (
        'site-footer chrome (class="site-footer")',
        lambda h: "site-footer" in h,
    ),
    # Author bio (2026-08-29). Unconditional chrome emitted by apply-blog-shell.py,
    # so it is safe to hard-require. The table of contents deliberately is NOT
    # required: it is suppressed on posts with fewer than 3 <h2>s, and a gate that
    # demands what the pipeline cannot supply deadlocks against its own producer
    # (the #128 failure mode).
    (
        'author bio block (class="author-bio")',
        lambda h: "author-bio" in h,
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


# ── Undefined-class check (2026-08-29) ──────────────────────────────────────
#
# Every check above is a MARKER check: it asks whether a string is present. That is
# structurally blind, and it is how three separate unstyled-body outages shipped
# green — #141 (right markup, missing stylesheet), #142 (right stylesheet, no
# markup), #144 (both right, another site's class vocabulary). A marker check
# cannot see that `.post-content` means nothing to THIS stylesheet.
#
# So this one inverts the question: every class the post actually uses must be
# defined in the CSS it actually loads. That is the property all three outages
# violated, and none of the marker checks could express.
CSS_FILE = Path(__file__).resolve().parent.parent / "css" / "blog.css"

# Styled inline, or supplied by the page's own <style>. Kept explicit and short:
# a long exemption list is how this check would rot into a no-op.
EXEMPT_CLASSES = {
    "logo", "logo-icon", "brand", "addr", "copy", "inner", "cta-btn",
    "sr-only", "excerpt", "author",
}


def _css_classes():
    if not CSS_FILE.exists():
        return None
    return set(re.findall(r"\.([a-zA-Z][\w-]*)", CSS_FILE.read_text(encoding="utf-8")))


def undefined_classes(html, defined):
    """Classes used by the post but absent from blog.css.

    Two exemptions, both learned from #141b's false positives: a post carrying its
    own inline <style>, and a post loading the Tailwind CDN, both legitimately use
    class names blog.css has never heard of.
    """
    if defined is None:
        return []
    if re.search(r"<style[\s>]", html) or "cdn.tailwindcss.com" in html:
        return []
    # The related-posts renderer builds markup by string concatenation, so a naive
    # class= scan over the raw file picks up JavaScript fragments, not class names.
    markup = re.sub(r"<script\b.*?</script>", " ", html, flags=re.S | re.I)
    used = set()
    for attr in re.findall(r'class="([^"]+)"', markup):
        used.update(attr.split())
    return sorted(c for c in used - EXEMPT_CLASSES if c not in defined)


def main():
    failures = []
    warnings = []
    checked = 0
    defined = _css_classes()
    for post in sorted(POSTS_DIR.glob("*.html")):
        html = post.read_text(encoding="utf-8")
        if is_redirect_stub(html):
            continue
        checked += 1
        missing = [label for label, test in CHECKS if not test(html)]
        if missing:
            failures.append((post.name, missing))
        # WARN, not fail — deliberately. The check found 37 distinct undefined classes
        # already live across the corpus (internal-links on 33 posts, toc on 31), all
        # pre-dating it. Hard-failing on day one would block every publish for a
        # backlog this check did not cause — #134a, where a blocked hook became a
        # silent 3-week outage. It fails loudly for NEW drift once the backlog is
        # cleared; until then it reports.
        undefined = undefined_classes(html, defined)
        if undefined:
            warnings.append((post.name, undefined))

    if warnings:
        total = len({c for _, cs in warnings for c in cs})
        print(f"Template lint: {len(warnings)} post(s) use {total} class(es) not defined "
              f"in blog.css — these render unstyled (warning, not a failure):",
              file=sys.stderr)
        for name, cs in warnings[:10]:
            print(f"  WARN  {name}: {', '.join(cs)}", file=sys.stderr)
        if len(warnings) > 10:
            print(f"  … and {len(warnings) - 10} more", file=sys.stderr)

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
