"""test_tape.py -- T1 verify: the tape's R3-default selection equals R3's
baseline to the dollar, the duplicate self-check reports the real count on
the spec's own (source, fillmode, sym, day, et) key (not a false zero), the
word "phantom" is labelled in the static page shell, and it opens on a
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

    # Referee (pass 2 + 3): a self-check keyed to always report 0 cannot
    # fail, so it isn't one. Report the real count on the spec's key
    # (source, fillmode, sym, day, et) -- non-zero and documented, not
    # silently swept -- rather than asserting a number this file cannot
    # honestly claim.
    n_keys, n_extra, examples = check_no_repeats(rows)
    print("PASS (informational, not a hard gate -- see check_no_repeats() "
          "docstring): %d duplicate keys / %d extra rows on (source, "
          "fillmode, sym, day, et). Examples: %s" % (n_keys, n_extra, examples))

    got = compute_default_selection_stats(rows)
    for field, want in R3_BASELINE.items():
        g = got.get(field)
        tol = 0.001 if field == "mean_r" else 0
        if g is None or abs(g - want) > tol:
            fail("default selection %s: got %r, R3 baseline says %r" % (field, g, want))
    print("PASS: R3-default selection (source=baseline, fillmode=close, "
          "lane=core11, policy=up_to_3) matches R3 baseline exactly: %s"
          % R3_BASELINE)

    if not HTML.exists():
        fail("%s does not exist -- run python research/build_tape.py first" % HTML)
    html = HTML.read_text(encoding="utf-8")
    if "<canvas" in html.lower():
        fail("the page contains <canvas> -- must render as static SVG")
    print("PASS: no <canvas>")
    for m in re.finditer(r'<script[^>]*\bsrc=', html, re.IGNORECASE):
        fail("the page loads an external script: %s" % html[m.start():m.start() + 120])
    print("PASS: no external <script src>")

    shell = html.split('<script id="data"', 1)[0]
    if "phantom" not in shell.lower():
        fail("the static page shell (before the data payload) never says "
             "'phantom' -- a reader meets the phantom fill mode unlabelled")
    print("PASS: 'phantom' is labelled in the static page shell")

    if "EXCLUSIVE_SELECT" not in html:
        fail("source/fillmode are not exclusive-select -- picking two book "
             "variant chips would silently union two different books")
    print("PASS: source/fillmode are exclusive-select (no cross-book union)")

    if 'getElementById("clear").onclick=function(){ defaultSel();' not in html:
        fail("Clear does not fall back to the R3 default -- one click would "
             "sum every merged source into one meaningless KPI row")
    print("PASS: Clear falls back to the R3 default selection")

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
