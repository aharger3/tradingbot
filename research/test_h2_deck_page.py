"""test_h2_deck_page.py -- prove the H2 three-lane page works before Austin opens it.

    python research/build_h2_deck.py && python research/test_h2_deck_page.py

Same shape as research/test_omen_test1_page.py: drive the real HTML in jsdom and
check the things that have each already failed once in this project.

The load-bearing check is the last family. **A field that cannot differ from its
default measures the page, not him.** So every option of every tap is pressed on
a real card and read back out of the export: all four grades in lane 1, all four
grades and all eight levels in lane 2, all four hold labels in lane 3. If a chip
is decorative -- wired to nothing, or overwritten by the page's own sync -- the
distinct-value count comes back short and this fails.

Also checked: static SVG and no <canvas>; taps survive a reload through a shared
localStorage; the export is one JSON object per line carrying enough to rejoin
bars without the page; lane 2's second tap is hidden until the first is not X,
and an X card still completes; and the page never leans on window.claude to
persist anything.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DECK = os.getenv("OMEN_DECK", "omen-h2-3lane").strip() or "omen-h2-3lane"
PAGE = os.path.join(HERE, "probes", DECK + ".html")

DRIVER = r"""
const fs = require('fs');
const { JSDOM } = require('jsdom');

const html = fs.readFileSync(process.argv[2], 'utf8');
const store = {};                       // shared across both documents = a reload
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
    url: 'https://omen.test/h2.html',
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
  if (!el) throw new Error('no chip ' + q + '=' + v + ' on ' + card.getAttribute('data-cid'));
  return el;
}
const out = {};
const settle = ms => new Promise(r => setTimeout(r, ms));

(async () => {

let dom = open();
let doc = dom.window.document;
const all = Array.from(doc.querySelectorAll('.card'));
const L1 = all.filter(c => c.getAttribute('data-lane') === 'b_remap');
const L2 = all.filter(c => c.getAttribute('data-lane') === 'silent_day');
const L3 = all.filter(c => c.getAttribute('data-lane') === 'giveback');
out.n_cards = all.length;
out.n1 = L1.length; out.n2 = L2.length; out.n3 = L3.length;
out.n_canvas = doc.querySelectorAll('canvas').length;
out.n_svg = doc.querySelectorAll('svg.chart').length;
out.svg_ops = Array.from(doc.querySelectorAll('svg.chart'))
                   .reduce((a, s) => a + s.children.length, 0);
out.n_2r = doc.querySelectorAll('svg.chart .hrail.tgt').length;
out.n_clock = doc.querySelectorAll('svg.chart .vmark.clk').length;
out.n_sections = doc.querySelectorAll('.sec').length;
out.uses_claude = /window\.claude[\s\S]{0,400}(setItem|localStorage|persist)/.test(html);

/* ---- every option of every tap, on a real card ------------------------- */
const GRADES = ['S', 'A', 'C', 'X'];
const LEVELS = ['PMH', 'PDH', 'ORH', 'VWAP', 'PML', 'PDL', 'ORL', 'other'];
const HOLDS  = ['full', 'half', 'runner', 'flat'];

GRADES.forEach((g, i) => tap(dom, chip(L1[i], 'grade', g)));

// lane 2: one card per level, all with a non-X grade, plus one X card
LEVELS.forEach((lv, i) => {
  tap(dom, chip(L2[i], 'grade', GRADES[i % 3]));      // S/A/C, never X
  tap(dom, chip(L2[i], 'level', lv));
});
const xcard = L2[LEVELS.length];
out.level_hidden_before = xcard.getAttribute('data-g');
tap(dom, chip(xcard, 'grade', 'X'));
out.level_g_after_x = xcard.getAttribute('data-g');
out.na_pressed_on_x =
  chip(xcard, 'level', 'na').getAttribute('aria-pressed') === 'true';
out.x_card_done = xcard.getAttribute('data-done');
// and it must come back off when he changes his mind
tap(dom, chip(xcard, 'grade', 'C'));
out.na_released = chip(xcard, 'level', 'na').getAttribute('aria-pressed') !== 'true';
out.g_after_regrade = xcard.getAttribute('data-g');
tap(dom, chip(xcard, 'level', 'ORL'));

HOLDS.forEach((h, i) => tap(dom, chip(L3[i], 'hold', h)));

// a lane-2 card with a grade but no level must NOT count as done
const partial = L2[LEVELS.length + 1];
tap(dom, chip(partial, 'grade', 'S'));
out.partial_done = partial.getAttribute('data-done');

await settle(700);

out.count_after = doc.getElementById('count').textContent.trim();
out.saved_state = doc.getElementById('saved').getAttribute('data-state');
tap(dom, doc.getElementById('exportbtn'));
out.export_text = doc.getElementById('out').value;
out.export_readonly = doc.getElementById('out').hasAttribute('readonly');
out.keys_written = Object.keys(store).length;
out.cid_l1 = L1[0].getAttribute('data-cid');
out.cid_l2 = L2[0].getAttribute('data-cid');
out.cid_l3 = L3[0].getAttribute('data-cid');
dom.window.close();

/* ---- reload: new document, same storage -------------------------------- */
dom = open();
doc = dom.window.document;
const r = Array.from(doc.querySelectorAll('.card'));
const R1 = r.filter(c => c.getAttribute('data-lane') === 'b_remap');
const R2 = r.filter(c => c.getAttribute('data-lane') === 'silent_day');
const R3 = r.filter(c => c.getAttribute('data-lane') === 'giveback');
out.restored_grades = GRADES.map((g, i) =>
  !!R1[i].querySelector('.q[data-q="grade"] .chip[data-v="' + g + '"][aria-pressed="true"]'));
out.restored_levels = LEVELS.map((lv, i) =>
  !!R2[i].querySelector('.q[data-q="level"] .chip[data-v="' + lv + '"][aria-pressed="true"]'));
out.restored_holds = HOLDS.map((h, i) =>
  !!R3[i].querySelector('.q[data-q="hold"] .chip[data-v="' + h + '"][aria-pressed="true"]'));
out.restored_disclosure = R2[0].getAttribute('data-g');
out.restored_count = doc.getElementById('count').textContent.trim();
tap(dom, doc.getElementById('exportbtn'));
out.export_after_reload = doc.getElementById('out').value;
dom.window.close();

process.stdout.write(JSON.stringify(out));

})().catch(e => { console.error(e); process.exit(1); });
"""


def run():
    assert os.path.exists(PAGE), "build the page first: python research/build_h2_deck.py"
    drv = os.path.join(HERE, "_h2_deck_driver.js")
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
    fails = []

    def check(name, cond, detail=""):
        print("%-40s %s%s" % (name, "PASS" if cond else "FAIL",
                              ("  " + str(detail)) if detail else ""))
        if not cond:
            fails.append(name)

    # --- shape
    check("120 cards, 60/30/30",
          r["n_cards"] == 120 and (r["n1"], r["n2"], r["n3"]) == (60, 30, 30),
          "%d = %d/%d/%d" % (r["n_cards"], r["n1"], r["n2"], r["n3"]))
    check("three lane sections", r["n_sections"] == 3, r["n_sections"])
    check("static SVG, no canvas", r["n_canvas"] == 0 and r["n_svg"] == 120,
          "%d svg / %d canvas" % (r["n_svg"], r["n_canvas"]))
    check("charts are real markup", r["svg_ops"] > 18000, "%d svg children" % r["svg_ops"])
    check("lane 3 draws the 2R rail", r["n_2r"] == 30, r["n_2r"])
    check("lane 3 draws the 11:00 clock", r["n_clock"] == 30, r["n_clock"])
    check("persistence is the page's own, not window.claude", not r["uses_claude"])
    check("export box editable", not r["export_readonly"])
    check("save indicator fired", r["saved_state"] == "just", r["saved_state"])

    # --- lane 2 progressive disclosure
    check("tap 2 hidden until tap 1", r["level_hidden_before"] == "",
          repr(r["level_hidden_before"]))
    check("X sets the card's disclosure state", r["level_g_after_x"] == "X",
          r["level_g_after_x"])
    check("X auto-answers the hidden n/a level", r["na_pressed_on_x"])
    check("an X card still completes", r["x_card_done"] == "1", r["x_card_done"])
    check("regrading off X releases n/a", r["na_released"] and r["g_after_regrade"] == "C",
          r["g_after_regrade"])
    check("grade without level is NOT done", r["partial_done"] == "0", r["partial_done"])

    # --- THE check: every tap can record a value different from its default
    lines = [l for l in r["export_text"].split("\n") if l.strip()]
    rows, ok = [], True
    for l in lines:
        try:
            rows.append(json.loads(l))
        except ValueError:
            ok = False
    check("every export line is valid JSON", ok, "%d rows" % len(rows))

    def vals(lane, q):
        seen = []
        for x in rows:
            if x.get("lane") == lane:
                for v in (x.get("answers", {}).get(q) or []):
                    seen.append(v)
        return seen

    g1 = set(vals("b_remap", "grade"))
    check("lane 1 records all four grades", g1 == {"S", "A", "C", "X"}, sorted(g1))
    lv = set(vals("silent_day", "level")) - {"na"}
    check("lane 2 records all eight levels",
          lv == {"PMH", "PDH", "ORH", "VWAP", "PML", "PDL", "ORL", "other"}, sorted(lv))
    g2 = set(vals("silent_day", "grade"))
    check("lane 2 records S/A/C", {"S", "A", "C"} <= g2, sorted(g2))
    h3 = set(vals("giveback", "hold"))
    check("lane 3 records all four hold labels",
          h3 == {"full", "half", "runner", "flat"}, sorted(h3))

    # --- export rejoins to bars without the page
    by = {x["card_id"]: x for x in rows}
    a = by.get(r["cid_l1"], {})
    check("lane 1 row carries the engine proposal",
          all(k in a for k in ("symbol", "date", "eng_entry", "eng_stop",
                               "eng_side", "eng_entry_i", "n_downgrades")),
          "%s %s" % (a.get("symbol"), a.get("date")))
    b = by.get(r["cid_l2"], {})
    check("lane 2 row carries symbol/date/src",
          all(k in b for k in ("symbol", "date", "src")),
          "%s %s %s" % (b.get("symbol"), b.get("date"), b.get("src")))
    c = by.get(r["cid_l3"], {})
    check("lane 3 row carries entry/stop/2R/clock",
          all(k in c for k in ("entry", "stop", "two_r", "clock_bar_i",
                               "mfe_clock", "ladder_clock")),
          "2R=%s clock=%s" % (c.get("two_r"), c.get("clock_bar_i")))
    check("card_id joins back to SYMBOL_DATE",
          all(x["symbol"] in x["card_id"] and x["date"] in x["card_id"] for x in rows))

    # --- survives a reload
    check("reload keeps all four lane-1 grades", all(r["restored_grades"]),
          r["restored_grades"])
    check("reload keeps all eight lane-2 levels", all(r["restored_levels"]),
          r["restored_levels"])
    check("reload keeps all four lane-3 holds", all(r["restored_holds"]),
          r["restored_holds"])
    check("reload restores tap-2 disclosure", r["restored_disclosure"] in ("S", "A", "C"),
          r["restored_disclosure"])
    check("reload keeps progress", r["restored_count"] == r["count_after"],
          "%s vs %s" % (r["restored_count"], r["count_after"]))
    check("export identical after reload", r["export_after_reload"] == r["export_text"])

    print()
    if fails:
        print("FAILED: %s" % ", ".join(fails))
        return 1
    print("all checks passed (%d cards, %d rows exported, %d localStorage keys)"
          % (r["n_cards"], len(rows), r["keys_written"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
