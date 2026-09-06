"""test_tape.py -- T1 verify: the tape's unfiltered default equals R3's
baseline to the dollar, the page has 0 duplicate rows, and it opens on a
phone (no <canvas>, no external <script src>).

Run: python research/test_tape.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.build_tape import (           # noqa: E402
    load_rich_sources, check_no_repeats, compute_default_selection_stats,
    FACETS as TAPE_FACETS,
)

# the exact picks research/build_tape.py's patched defaultSel() makes --
# every one of these must resolve to a real dict entry, or the page throws
# TypeError on load before it ever draws the rail (referee finding, T1 v1).
DEFAULT_PICKS = {"source": "baseline", "fillmode": "close",
                 "lane": "core11", "policy": "up_to_3"}

TAPE = ROOT / "research" / "tape"
HTML = TAPE / "omen-tape.html"

# research/tape/loop.json's baseline_figures.whole -- the number R3 already
# published and this page must reproduce, not re-derive.
R3_BASELINE = {"trades": 769, "per_day": -52, "mean_r": -0.0335,
               "months_green": 11, "months": 25}


def fail(msg):
    print("FAIL: " + msg)
    sys.exit(1)


def main():
    rows, _notes = load_rich_sources()

    n_dupes, examples = check_no_repeats(rows)
    if n_dupes != 0:
        fail("duplicate count is %d, not 0. Examples: %s" % (n_dupes, examples))
    print("PASS: duplicate count 0")

    got = compute_default_selection_stats(rows)
    for field, want in R3_BASELINE.items():
        g = got.get(field)
        tol = 0.001 if field == "mean_r" else 0
        if g is None or abs(g - want) > tol:
            fail("default selection %s: got %r, R3 baseline says %r" % (field, g, want))
    print("PASS: unfiltered honest selection matches R3 baseline exactly: %s" % R3_BASELINE)

    if not HTML.exists():
        fail("%s does not exist -- run python research/build_tape.py first" % HTML)
    html = HTML.read_text(encoding="utf-8")
    if "<canvas" in html.lower():
        fail("the page contains <canvas> -- must render as static SVG")
    print("PASS: no <canvas>")
    for m in re.finditer(r'<script[^>]*\bsrc=', html, re.IGNORECASE):
        fail("the page loads an external script: %s" % html[m.start():m.start() + 120])
    print("PASS: no external <script src>")

    # Open the embedded payload and check every declared facet actually has
    # data, and that the page's own default picks resolve -- catches the
    # v1 defect (facets declared, never encoded; defaultSel() throws).
    m = re.search(
        r'<script id="data" type="application/json">(.*?)</script>',
        html, re.DOTALL)
    if not m:
        fail("no embedded data payload found (script#data)")
    payload = json.loads(m.group(1))
    dicts = payload.get("dicts", {})
    cols = payload.get("cols", {})
    declared = [f for f, _ in TAPE_FACETS]
    for f in declared:
        if f not in dicts or f not in cols:
            fail("facet %r is declared in FACETS but missing from the "
                 "embedded dicts/cols -- the page will throw on load" % f)
        if len(dicts[f]) == 0:
            fail("facet %r has an empty dict -- no values were ever encoded" % f)
    print("PASS: all %d declared facets have dicts/cols with data" % len(declared))

    for field, value in DEFAULT_PICKS.items():
        if value not in dicts.get(field, []):
            fail("default pick %s=%r does not resolve in dicts[%r]=%r -- "
                 "defaultSel() will silently (or loudly) fail to select it"
                 % (field, value, field, dicts.get(field)))
    print("PASS: all %d default picks resolve: %s" % (len(DEFAULT_PICKS), DEFAULT_PICKS))

    print("\nALL PASS")


if __name__ == "__main__":
    main()
