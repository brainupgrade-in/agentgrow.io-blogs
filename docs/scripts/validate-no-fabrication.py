#!/usr/bin/env python3
"""
validate-no-fabrication.py — pre-publish gate against fabricated client
attribution + invented case studies (issue/gotcha #88).

AgentGrow / Friday variant. Scans docs/posts/*.html and exits NON-ZERO if any
post contains a HIGH-CONFIDENCE fabrication signature. Signatures are
deliberately conservative (low false-positive): they target the families that
got Friday posts deleted (2026-04-22/23, 2026-05-29), NOT every number or
company mention.

AgentGrow has NO client case studies, quotes, savings figures, reply rates, or
conversion numbers — it is a newer product. So anything that reads as a
specific real engagement we ran is fabrication.

What is allowed to stay (TRUE anchors — never flagged):
  * "rated 4.91/5.0 on Oracle University" / "4.91/5.0 at Oracle"
  * Rajesh Gheware's employment history (JPMorgan / Deutsche Bank /
    Morgan Stanley) when in a "25+ years" / bio / background context.
  * "5,000+ trained" / "119 labs" as standalone numbers.
  * Stats attributed to real third parties (Gartner, Forrester, HubSpot,
    Salesforce, McKinsey, Statista, IBM) — those are cited claims.
  * 2nd-person ICP framing ("if you run a 12-person consulting firm…") —
    a hypothetical addressed to the reader, not a 3rd-person result story.

What is flagged (fabrication):
  1. The "used by Fortune 500 teams" lead-magnet boilerplate.
  2. A named non-founder enterprise within ~60 chars of a client/usage verb.
     The founder trio is excluded ONLY in a bio/background context.
  3. Invented-study / survey phrases (our survey of N, we polled N, State of
     ... report surveying N).
  4. The fabricated persona token "FinTrust".
  5. AgentGrow-specific invented case studies: an Nn-person / N-employee firm
     within ~80 chars of a result verb (saved / went from / Day 90 / Nx /
     after N days / closed / grew), and "₹N lakh/crore saved" outcome claims.

Skipped: _template.html and http-equiv=refresh redirect stubs.

Exit code: 0 if clean, 1 otherwise (prints file + matched text).
Usage: python3 docs/scripts/validate-no-fabrication.py [posts_dir]
"""

import re
import sys
from pathlib import Path

# Companies that have NO legitimate use as a client in this blog.
# (Oracle handled separately: legit only as the rating.)
NON_FOUNDER = (
    "Deloitte", "Ericsson", "Comcast", "Bank of America", "Goldman Sachs",
    "Goldman", "Standard Chartered", "ADNOC", "Infosys", "TCS", "Wipro",
    "HCL", "Accenture", "Cognizant", "HDFC", "ICICI", "Reliance",
    "Snowflake", "Stripe", "Walmart", "MetLife", "Citibank", "Citigroup",
    "Citi",
)
# Founder employers — TRUE as background, fabricated as clients.
FOUNDER = ("JPMorgan", "JP Morgan", "Deutsche Bank", "Morgan Stanley")

# Client / trainee / usage verbs.
CLIENT_CTX = re.compile(
    r"(trained|training rooms?|trainees?|trusted by|workshops?\s+for|"
    r"clients?\b|customers?\b|deployed|rolled out|roll(ing)? out|"
    r"teams?\s+at|teams?\s+like|are using|is using|we (built|rebuilt|"
    r"deployed|ran|helped|onboarded)|running\s+\w+\s+for|batches?\s+at|"
    r"engineers?\s+(at|from)|by engineers from|across .{0,20}batches)",
    re.IGNORECASE,
)
# Bio / background context that legitimises the founder trio.
BIO_CTX = re.compile(
    r"(25\+?\s*years|\d+\s*years (at|building|of)|years at|background|"
    r"past employ|career|building .{0,40}(systems?|platforms?|gateways?)|"
    r"payment gateway|architect.{0,20}at|spent .{0,20}at|formerly|"
    r"ex-|veteran)",
    re.IGNORECASE,
)
# Oracle rating context that legitimises Oracle.
ORACLE_OK = re.compile(r"(4\.91|Oracle University|rating|rated)", re.IGNORECASE)

# Invented surveys / studies (broadened for AgentGrow's families).
STUDY_PHRASES = re.compile(
    r"(our survey of|we surveyed \d+|we polled \d+|survey of \d+\+?\s*"
    r"(indian\s+)?(b2b\s+)?(founders?|ceos?|smbs?|owners?|leaders?)|"
    r"research we conducted|State of (SMB|B2B|LLM) .{0,30}report|"
    r"surveying \d+|\d+-month study of|analysis of \d+ (production )?"
    r"(deployments?|companies|firms))",
    re.IGNORECASE,
)

# AgentGrow-specific invented case studies. High-precision persona/firm shape:
# either "<verb> a N-person …" (Vikram runs a 15-person agency) or
# "N-person <type> firm/agency/startup". Deliberately NOT the bare
# "N employees" / "N–N employees" form — those are lead-segment ranges and
# third-party-cited stats ("under 100 employees", "11–50 employees"), not
# case studies. 2nd-person hypotheticals are further excluded by requiring a
# 3rd-person result verb in the window.
HEADCOUNT = re.compile(
    r"((runs?|run|founded|leads?|owns?|heads?|started|manages?)\s+(a\s+)?"
    r"\d+[- ]person\b|"
    r"\d+[- ]person\s+[\w-]+(\s+[\w-]+)?\s*"
    r"(firm|agency|startup|company|consultancy|practice|studio|shop|business)\b)",
    re.IGNORECASE,
)
RESULT_CTX = re.compile(
    r"(saved|went from|after \d+\s*days?|Day\s*90|in \d+\s*days?|\d+x\b|"
    r"increased|grew|closed \d+|generated|₹\s?\d|lakh|crore|cut .{0,15}by|"
    r"reduced .{0,15}by|\d+%|in Q[1-4])",
    re.IGNORECASE,
)
# Direct money-saved outcome claim.
MONEY_SAVED = re.compile(
    r"(saved\s*(₹|rs\.?|inr)?\s*\d|₹\s?\d[\d,]*\s*(lakh|crore|l\b|cr\b)"
    r".{0,15}saved|\d+\s*(lakh|crore)\s+(saved|in savings))",
    re.IGNORECASE,
)

WINDOW = 60   # chars on each side of a company mention
BIO_WINDOW = 140  # wider for the founder trio — bio listings span a clause
HC_WINDOW = 80  # wider for headcount→result correlation


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s)


def find_violations(text: str):
    """Return list of (label, snippet) high-confidence fabrication hits."""
    hits = []
    plain = _strip_tags(text)

    # 1. Fortune 500 boilerplate
    for m in re.finditer(r"used by Fortune 500 teams", plain, re.IGNORECASE):
        hits.append(("fortune500", plain[max(0, m.start() - 30): m.end() + 20]))

    # 2a. Non-founder enterprises near a client verb
    for company in NON_FOUNDER:
        for m in re.finditer(re.escape(company), plain):
            lo, hi = max(0, m.start() - WINDOW), m.end() + WINDOW
            window = plain[lo:hi]
            if CLIENT_CTX.search(window):
                hits.append(("named-client", window.strip()))
                break

    # 2b. Oracle near a client verb but NOT in the rating context
    for m in re.finditer(r"Oracle", plain):
        lo, hi = max(0, m.start() - WINDOW), m.end() + WINDOW
        window = plain[lo:hi]
        if CLIENT_CTX.search(window) and not ORACLE_OK.search(window):
            hits.append(("oracle-client", window.strip()))
            break

    # 2c. Founder trio in client (non-bio) context. Wider bio window: a bio
    # clause ("25+ years building enterprise systems at JPMorgan, Deutsche
    # Bank, and Morgan Stanley") spans well past 60 chars.
    for company in FOUNDER:
        for m in re.finditer(re.escape(company), plain):
            lo, hi = max(0, m.start() - WINDOW), m.end() + WINDOW
            window = plain[lo:hi]
            bio_window = plain[max(0, m.start() - BIO_WINDOW): m.end() + BIO_WINDOW]
            if CLIENT_CTX.search(window) and not BIO_CTX.search(bio_window):
                hits.append(("founder-as-client", window.strip()))
                break

    # 3. Invented studies / surveys
    for m in STUDY_PHRASES.finditer(plain):
        hits.append(("invented-study", plain[max(0, m.start() - 25): m.end() + 25]))

    # 4. Persona token
    for m in re.finditer(r"FinTrust", plain):
        hits.append(("persona", plain[max(0, m.start() - 25): m.end() + 25]))

    # 5a. Headcount-firm case study near a result verb
    for m in HEADCOUNT.finditer(plain):
        lo, hi = max(0, m.start() - HC_WINDOW), m.end() + HC_WINDOW
        window = plain[lo:hi]
        if RESULT_CTX.search(window):
            hits.append(("invented-case-study", window.strip()))
            break

    # 5b. Money-saved outcome claim
    for m in MONEY_SAVED.finditer(plain):
        hits.append(("money-saved", plain[max(0, m.start() - 25): m.end() + 25]))

    return hits


def is_redirect_stub(text: str) -> bool:
    return 'http-equiv="refresh"' in text


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    posts_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else repo_root / "docs" / "posts"

    if not posts_dir.is_dir():
        print(f"ERROR: posts dir not found: {posts_dir}", file=sys.stderr)
        return 1

    offenders = []
    for path in sorted(posts_dir.glob("*.html")):
        if path.name == "_template.html":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if is_redirect_stub(text):
            continue
        hits = find_violations(text)
        if hits:
            offenders.append((path.name, hits))

    if offenders:
        print("Fabrication check FAILED — posts with #88 client-attribution signatures:\n",
              file=sys.stderr)
        for name, hits in offenders:
            print(f"  {name}", file=sys.stderr)
            for label, snippet in hits:
                snip = re.sub(r"\s+", " ", snippet)[:160]
                print(f"      [{label}] …{snip}…", file=sys.stderr)
        print(f"\n{len(offenders)} post(s) flagged. Neutralise per #88 "
              "(strip the client roster / invented metric / fabricated case study; "
              "keep real anchors).", file=sys.stderr)
        return 1

    print(f"No-fabrication check OK — all posts in {posts_dir} clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
