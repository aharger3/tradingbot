"""test_build_s_sweep.py -- prove the S-sweep page before Austin opens it.

    python research/test_build_s_sweep.py

Two halves.

1. The no-repeat guarantee, at the real 250-card size: pick() must draw zero
   symbol-days that appear anywhere marked_card_ids() reads, and the draw must
   not repeat itself.

2. The field-settability check the track's CHECK line asks for -- driven in
   jsdom (node), the same rig test_omen_test1_page.py uses. Builds a small
   throwaway deck, taps two different cards to two DIFFERENT grades and two
   DIFFERENT downgrade sets, and proves:

     * no chip starts pre-pressed (the entry_p trap: a field that cannot
       differ from its default measures the page, not him)
     * grade is independently settable per card, and exported as `grade`
     * downgrades is independently settable per card (including "none tapped"
       on a third card, proving tap 2 is never forced)
     * the millisecond stamp differs across cards when spaced apart, is never
       hardcoded, and survives a reload
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

TEST_DECK = "s-sweep-selftest"
PAGE = os.path.join(HERE, "probes", TEST_DECK + ".html")

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
    url: 'https://omen.test/omen-s-sweep.html',
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
const settle = ms => new Promise(r => setTimeout(r, ms));
const out = {};

(async () => {

let dom = open();
let doc = dom.window.document;
const cards = doc.querySelectorAll('.card');
out.n_cards = cards.length;
out.n_canvas = doc.querySelectorAll('canvas').length;
out.n_svg = doc.querySelectorAll('svg.chart').length;

const c0 = cards[0], c1 = cards[1], c2 = cards[2];
out.cid0 = c0.getAttribute('data-cid');
out.cid1 = c1.getAttribute('data-cid');
out.cid2 = c2.getAttribute('data-cid');

// -- default state: nothing pre-pressed anywhere (the entry_p trap) --------
out.any_prepressed = doc.querySelectorAll('.chip[aria-pressed="true"]').length;

// c0: grade S, no downgrades tapped -- tap 2 must survive being skipped
tap(dom, chip(c0, 'grade', 'S'));
await settle(30);

// c1: grade A, WITH two downgrades -- proves grade and downgrades are each
// independently settable to a second, different value
tap(dom, chip(c1, 'grade', 'A'));
tap(dom, chip(c1, 'downgrades', 'stale_retest'));
tap(dom, chip(c1, 'downgrades', 'no_retest'));

// c2: grade none, single downgrade tag
tap(dom, chip(c2, 'grade', 'none'));
tap(dom, chip(c2, 'downgrades', 'exhausted'));

await settle(30);

out.g0 = c0.getAttribute('data-g') || null;
out.done0 = c0.getAttribute('data-done');
out.done1 = c1.getAttribute('data-done');

tap(dom, doc.getElementById('exportbtn'));
out.export_text = doc.getElementById('out').value;
out.keys_written = Object.keys(store).length;
dom.window.close();

// -- reload: same storage, fresh document -----------------------------------
dom = open();
doc = dom.window.document;
const r0 = doc.querySelectorAll('.card')[0];
const r1 = doc.querySelectorAll('.card')[1];
out.restored_grade0 = !!r0.querySelector('.q[data-q="grade"] .chip[data-v="S"][aria-pressed="true"]');
out.restored_grade1 = !!r1.querySelector('.q[data-q="grade"] .chip[data-v="A"][aria-pressed="true"]');
tap(dom, doc.getElementById('exportbtn'));
out.export_after_reload = doc.getElementById('out').value;
dom.window.close();

process.stdout.write(JSON.stringify(out));

})().catch(e => { console.error(e); process.exit(1); });
"""


def build_test_deck():
    import build_s_sweep
    cards, probed, nseen, per_source = build_s_sweep.pick(6, seed=1, max_probe=4000)
    assert len(cards) == 6, "test deck needs 6 cards to probe, got %d (probed %d)" % (
        len(cards), probed)
    return build_s_sweep.write_page(cards, TEST_DECK)


def run():
    build_test_deck()
    assert os.path.exists(PAGE)
    drv = os.path.join(HERE, "_s_sweep_driver.js")
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
    fails = []

    def check(name, cond, detail=""):
        print("%-42s %s%s" % (name, "PASS" if cond else "FAIL",
                              ("  " + str(detail)) if detail else ""))
        if not cond:
            fails.append(name)

    # ---- 1. the no-repeat guarantee, at real size ----
    import build_s_sweep
    marked = build_s_sweep.marked_card_ids()
    cards, probed, nseen, per_source = build_s_sweep.pick(
        build_s_sweep.N_CARDS, build_s_sweep.SEED, build_s_sweep.MAX_PROBE_DEFAULT)
    ids = ["%s_%s" % (c["symbol"], c["day"]) for c in cards]
    check("draws the requested 250", len(cards) == build_s_sweep.N_CARDS, len(cards))
    check("no duplicate inside the draw", len(set(ids)) == len(ids))
    check("zero repeats against marked_card_ids()",
          not (set(ids) & marked), sorted(set(ids) & marked)[:5])

    # ---- 2. field settability, driven in jsdom ----
    r = run()
    check("no <canvas>, static SVG only",
          r["n_canvas"] == 0 and r["n_svg"] == r["n_cards"],
          "%d svg / %d canvas" % (r["n_svg"], r["n_canvas"]))
    check("nothing pre-pressed on load (the entry_p trap)",
          r["any_prepressed"] == 0, r["any_prepressed"])
    check("grade tap marks the card done", r["done0"] == "1", r["done0"])
    check("card without downgrades still completes",
          r["done0"] == "1", "tap-2-optional")

    lines = [l for l in r["export_text"].split("\n") if l.strip()]
    rows = {json.loads(l)["card_id"]: json.loads(l) for l in lines}
    a, b, c = rows.get(r["cid0"], {}), rows.get(r["cid1"], {}), rows.get(r["cid2"], {})
    check("grade field: two DIFFERENT values recorded",
          a.get("grade") == "S" and b.get("grade") == "A" and a.get("grade") != b.get("grade"),
          "%s vs %s" % (a.get("grade"), b.get("grade")))
    check("grade field: a third, DIFFERENT value too (none)",
          c.get("grade") == "none", c.get("grade"))
    check("downgrades field: settable, and skippable",
          "downgrades" not in a and sorted(b.get("downgrades", [])) ==
          ["no_retest", "stale_retest"],
          "a=%s b=%s" % (a.get("downgrades"), b.get("downgrades")))
    check("downgrades field: a second distinct set (c != b)",
          c.get("downgrades") == ["exhausted"] and c.get("downgrades") != b.get("downgrades"))
    check("ms field present and numeric on every graded card",
          all(isinstance(x.get("ms"), (int, float)) for x in (a, b, c)),
          [a.get("ms"), b.get("ms"), c.get("ms")])
    check("ms field is not a hardcoded constant across cards",
          len({a.get("ms"), b.get("ms"), c.get("ms")}) > 1,
          [a.get("ms"), b.get("ms"), c.get("ms")])
    check("card_id/symbol/date present on every row",
          all(k in a for k in ("card_id", "symbol", "date")))

    check("reload keeps card 0's grade", r["restored_grade0"])
    check("reload keeps card 1's grade", r["restored_grade1"])
    check("export identical after reload",
          r["export_after_reload"] == r["export_text"])

    print()
    if fails:
        print("FAILED: %s" % ", ".join(fails))
        return 1
    print("all checks passed (%d cards probed for the 250-draw, %d judged excluded)"
          % (probed, nseen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
