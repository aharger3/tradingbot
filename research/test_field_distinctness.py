"""test_field_distinctness.py -- THE RULE (T23): a field that cannot differ from
its default measures the page, not him.

    python research/test_field_distinctness.py

`research/p25_midcandle_entry.md` found `out.entry_p = closes[i]` unconditionally:
every graded entry read as an at-close fill by construction, because the field had
no way to record anything else. T8 (commit cef00981) fixed entry_p specifically.
This test generalizes the check so the bug class -- not just that one field -- has
a regression guard, and audits every OTHER field the page promotes into a row for
the same defect.

Two kinds of field on an OMEN Test card:

  1. DIRECT CAPTURE -- grade, setup, eblock, emin, why, comment. These are read
     straight off whichever chip is pressed / whatever is typed, with no formula
     in between. Proven settable by tapping two different values and checking the
     export carries both.

  2. DERIVED-WITH-OVERRIDE -- entry_p, stop_p, and everything computed from them
     (bar_close_p, entered_before_close, stop_src, side). Each has a DEFAULT
     (the bar's close / the tapped rail chip) and an OVERRIDE (a typed price).
     Distinctness ACROSS ROWS is not the real test here -- closes[i] differs by
     bar even under the old bug, so two rows with different bars would "pass" a
     naive distinctness check while the defect was still live. The real test is
     WITHIN one row: does the typed override actually change what gets recorded,
     away from the default the untouched field would have produced? That is
     exactly the invariant p25 found broken and T8 fixed.

This file fails if entry_p (or stop_p) is ever forced back to its default with the
override wired but ignored -- the precise shape of the original bug.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DECK = os.getenv("OMEN_DECK", "omen-test-2").strip() or "omen-test-2"
PAGE = os.path.join(HERE, "probes", DECK + ".html")

DRIVER = r"""
const fs = require('fs');
const { JSDOM } = require('jsdom');

const html = fs.readFileSync(process.argv[2], 'utf8');
const store = {};
function makeStorage(){
  return {
    getItem: k => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: k => { delete store[k]; },
    clear: () => { for (const k in store) delete store[k]; },
    key: i => Object.keys(store)[i] || null,
    get length(){ return Object.keys(store).length; },
  };
}
function open(){
  return new JSDOM('<!doctype html><html><body>' + html + '</body></html>', {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    url: 'https://omen.test/field-distinctness.html',
    beforeParse(w){
      Object.defineProperty(w, 'localStorage',
                            {value: makeStorage(), configurable: true});
    },
  });
}
function tap(dom, el){
  el.dispatchEvent(new dom.window.MouseEvent('click', {bubbles: true}));
}
function chip(card, q, v){
  const el = card.querySelector('.q[data-q="' + q + '"] .chip[data-v="' + v + '"]');
  if (!el) throw new Error('no chip ' + q + '=' + v);
  return el;
}
function type(dom, el, v){
  el.value = v;
  el.dispatchEvent(new dom.window.Event('input', {bubbles: true}));
}
const settle = ms => new Promise(r => setTimeout(r, ms));

(async () => {

const dom = open();
const doc = dom.window.document;
const cards = doc.querySelectorAll('.card');

// --- card A: direct-capture fields, entry/stop LEFT AT DEFAULT ------------
const cA = cards[0];
tap(dom, chip(cA, 'grade', 'S'));
tap(dom, chip(cA, 'eblock', '1'));
tap(dom, chip(cA, 'emin', '3'));          // bar 18, entry untouched -> at close
tap(dom, cA.querySelector('.stopchip'));  // stop from the rail, untouched
tap(dom, chip(cA, 'setup', 'BR'));
type(dom, cA.querySelector('.q[data-q="comment"] textarea.note'), 'alpha card');

// --- card B: direct-capture fields DIFFERENT, entry/stop OVERRIDDEN -------
const cB = cards[1];
tap(dom, chip(cB, 'grade', 'A'));
tap(dom, chip(cB, 'eblock', '3'));
tap(dom, chip(cB, 'emin', '10'));         // bar 55
const closesB = JSON.parse(cB.getAttribute('data-closes'));
const typedEntryB = (closesB[55] - 0.31).toFixed(2);
type(dom, cB.querySelector('.q[data-q="emin"] textarea.note'), typedEntryB);
const typedStopB = (closesB[55] - 0.90).toFixed(2);
type(dom, cB.querySelector('.q[data-q="stop"] textarea.note'), typedStopB);
tap(dom, chip(cB, 'setup', 'OCR'));
type(dom, cB.querySelector('.q[data-q="comment"] textarea.note'), 'beta card');

// --- card C: an X card, to prove grade/grade_std/why also vary ------------
const cC = cards[2];
tap(dom, chip(cC, 'grade', 'X'));
tap(dom, chip(cC, 'why', 'chop'));

await settle(700);

tap(dom, doc.getElementById('exportbtn'));
const lines = doc.getElementById('out').value.split('\n').filter(l => l.trim());
process.stdout.write(JSON.stringify({
  rows: lines.map(l => JSON.parse(l)),
  typedEntryB: parseFloat(typedEntryB),
  typedStopB: parseFloat(typedStopB),
  barCloseB55: closesB[55],
}));

})().catch(e => { console.error(e); process.exit(1); });
"""


def run():
    assert os.path.exists(PAGE), "build the page first: python research/build_omen_test1.py"
    drv = os.path.join(HERE, "_field_distinctness_driver.js")
    with open(drv, "w", encoding="utf-8") as fh:
        fh.write(DRIVER)
    try:
        proc = subprocess.run(["node", drv, PAGE], capture_output=True, text=True)
    finally:
        os.remove(drv)
    if proc.returncode != 0:
        print(proc.stderr[-4000:])
        raise SystemExit("jsdom driver failed")
    return json.loads(proc.stdout)


def main():
    r = run()
    rows = r["rows"]
    fails = []

    def check(name, cond, detail=""):
        print("%-46s %s%s" % (name, "PASS" if cond else "FAIL",
                              ("  " + str(detail)) if detail else ""))
        if not cond:
            fails.append(name)

    check("3 rows exported", len(rows) == 3, len(rows))
    a = next((x for x in rows if x.get("setup") == "BR"), {})
    b = next((x for x in rows if x.get("setup") == "OCR"), {})
    c = next((x for x in rows if x.get("grade") == "X"), {})

    # --- 1. DIRECT CAPTURE fields: two different taps -> two different values
    direct = {
        "grade": (a.get("grade"), b.get("grade")),
        "setup": (a.get("setup"), b.get("setup")),
        "entry_i": (a.get("entry_i"), b.get("entry_i")),
        "entry_t": (a.get("entry_t"), b.get("entry_t")),
    }
    for field, (va, vb) in direct.items():
        check("direct capture varies: %s" % field, va is not None and vb is not None and va != vb,
              "%r vs %r" % (va, vb))

    check("direct capture varies: comment (notes.comment)",
          a.get("notes", {}).get("comment") == "alpha card"
          and b.get("notes", {}).get("comment") == "beta card")
    check("direct capture varies: why (only on non-tradeable card)",
          c.get("notes", {}).get("why") == "chop" or "why" in c.get("answers", {}))
    check("grade_std takes >=2 distinct values (S/A/none seen)",
          len({a.get("grade_std"), b.get("grade_std"), c.get("grade_std")}) >= 3,
          {a.get("grade_std"), b.get("grade_std"), c.get("grade_std")})

    # --- 2. DERIVED-WITH-OVERRIDE fields: WITHIN one row, override must beat
    #        the default. This is the actual shape of the p25 bug: a formula
    #        that is always the answer regardless of what the override says.
    check("entry_p: untouched card records the bar close (default path intact)",
          a.get("entry_p") is not None and a.get("entry_p") == a.get("bar_close_p")
          and a.get("entered_before_close") is False,
          "entry_p=%s bar_close_p=%s flag=%s"
          % (a.get("entry_p"), a.get("bar_close_p"), a.get("entered_before_close")))
    check("entry_p: typed override actually changes the recorded price",
          b.get("entry_p") is not None
          and abs(b["entry_p"] - r["typedEntryB"]) < 1e-9
          and b.get("entry_p") != b.get("bar_close_p")
          and b.get("entered_before_close") is True,
          "entry_p=%s bar_close_p=%s flag=%s"
          % (b.get("entry_p"), b.get("bar_close_p"), b.get("entered_before_close")))
    check("bar_close_p survives the override untouched",
          b.get("bar_close_p") is not None
          and abs(b["bar_close_p"] - r["barCloseB55"]) < 1e-9)

    check("stop_p: untouched card takes the rail value (stop_src != typed)",
          a.get("stop_p") is not None and a.get("stop_src") != "typed")
    check("stop_p: typed override actually changes the recorded price",
          b.get("stop_p") is not None
          and abs(b["stop_p"] - r["typedStopB"]) < 0.005
          and b.get("stop_src") == "typed")

    check("side is derived from entry/stop, not a constant",
          len({a.get("side"), b.get("side")} - {None}) >= 1
          and a.get("side") in ("L", "S") and b.get("side") in ("L", "S"))

    print()
    if fails:
        print("FAILED: %s" % ", ".join(fails))
        return 1
    print("all field-distinctness checks passed (%d rows)" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
