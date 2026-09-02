#!/usr/bin/env python3
"""add-posthog-snippet.py — put the PostHog snippet on every blog page. Idempotent.

Why (2026-09-03, todo/agentgrow-blog-traffic-recovery.md Phase 1a): the blog is
static HTML on GitHub Pages proxied under agentgrow.io/blog. Only the Next.js app
pages ever carried PostHog, so PostHog showed ZERO blog pageviews for three
months — not because nobody came, but because nothing could see them. Search
Console was the only instrument and it only sees Google.

What it does: inserts the snippet immediately before </head> in
  docs/posts/*.html   (skips redirect stubs)
  docs/index.html
  docs/guide/index.html
Skips any file that already contains `posthog.init(`, so re-running is a no-op.

Persistence: `sessionStorage` — no cookie is set, so the blog
needs no consent banner (the app gates its own snippet behind CookieConsent.tsx).
Same project token as the app; it is a public web token.

This file is the CANONICAL copy of the snippet. The blog shell emitter that
Friday uses for NEW posts (ai-business-agents/agents/rajeshgheware-gmail/
workspace/bin/apply-blog-shell.py, POSTHOG_SNIPPET) carries a byte-identical
string — change both or the corpus drifts.

Usage:  python3 docs/scripts/add-posthog-snippet.py [--check]
  --check   report what would change, exit 1 if anything would, write nothing.
"""
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent
TARGETS = [DOCS / "index.html", DOCS / "guide" / "index.html"]
TARGETS += sorted((DOCS / "posts").glob("*.html"))

SNIPPET = """  <!-- PostHog (blog readers; sessionStorage persistence: no cookie, no consent banner) -->
  <script>
    !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="init capture register register_once register_for_session unregister unregister_for_session getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey getNextSurveyStep identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset get_distinct_id getGroups get_session_id get_session_replay_url alias set_config startSessionRecording stopSessionRecording sessionRecordingStarted captureException loadToolbar get_property getSessionProperty createPersonProfile opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing debug".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
    posthog.init('phc_zSRBvacMmXH9RipmQ3q4hghYKeZRhTBAiTTUNkDYSXJm',{api_host:'https://us.i.posthog.com',person_profiles:'identified_only',persistence:'sessionStorage',capture_pageleave:true});
  </script>
"""

HEAD_END = re.compile(r"</head>", re.I)


def is_redirect_stub(html: str) -> bool:
    return 'http-equiv="refresh"' in html.lower()


def main() -> int:
    check = "--check" in sys.argv
    changed, skipped, already, missing = [], [], [], []
    for path in TARGETS:
        if not path.exists():
            missing.append(path)
            continue
        html = path.read_text(encoding="utf-8")
        if "posthog.init(" in html:
            already.append(path)
            continue
        if is_redirect_stub(html):
            skipped.append(path)
            continue
        m = HEAD_END.search(html)
        if not m:
            skipped.append(path)
            print(f"  SKIP  {path.relative_to(DOCS)}: no </head>", file=sys.stderr)
            continue
        new = html[: m.start()] + SNIPPET + html[m.start():]
        changed.append(path)
        if not check:
            path.write_text(new, encoding="utf-8")
    verb = "would add" if check else "added"
    print(f"posthog snippet: {verb} to {len(changed)}, already present {len(already)}, "
          f"skipped {len(skipped)} (stubs/no head), missing {len(missing)}")
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
