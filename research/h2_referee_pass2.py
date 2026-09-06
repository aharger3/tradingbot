"""h2_referee_pass2.py -- independent refutation harness for row H2 (tap-on-chart marking).

    python research/h2_referee_pass2.py

Builder commit under review: 7eb6aec7 ("H2: tap-on-chart marks -- self-test 3 marks
round-trip"). First referee: 7a9defa4 (upheld). This is the second referee pass and it
does NOT reuse either the builder's page driver or the first referee's script.

Why a second harness at all: research/build_tap_selftest.py's page drives itself, and
research/test_tap_marks.py drives that page. Both therefore share one script's idea of
what a tap means. This file strips the self-driver off the built page (keeping the real
shell CSS/JS and the real tappable SVG untouched) and drives the handlers from outside,
so nothing the builder wrote decides what "correct" is here.

What it checks, each independently:
  A  a tap writes localStorage SYNCHRONOUSLY -- storage is read back in the same tick as
     the dispatch, with no timer allowed to fire
  A2 the stop price is re-derived from the Python candle list by hand, not from the page
  A3 the 4th rail tap resets the card
  B  a fresh document over the same storage rebuilds the SVG OVERLAY (the <text> nodes
     inside the chart), not merely the data, and re-exports byte-identically
  C  cleared storage yields a clean page: overlay hidden, export empty, no throw
  D  an OLD stored blob with no `tap` key (a pre-H2 card) still restores its notes/chips
  E  a MALFORMED tap blob (entry_i only, no pt/stop_p/runner_pct) -- does restore throw?
  F  the served page has no <canvas>, no external <script>, and pointer events present
  G  touch-action is (or is not) declared on the tap hit surfaces
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_tap_selftest as builder  # noqa: E402

SCRATCH = os.environ.get("TMP", HERE)
PAGE = os.path.join(SCRATCH, "h2_ref2_page.html")
DRV = os.path.join(SCRATCH, "h2_ref2_driver.js")

NODE = r"""
const fs = require('fs');
const { JSDOM, VirtualConsole } = require('jsdom');
const html = fs.readFileSync(process.argv[2], 'utf8');

/* jsdom reports an uncaught error inside an inline <script> to the virtual
   console, NOT to a window 'error' listener we attach after construction --
   restore() runs during parse, before any listener of ours exists. So sink
   jsdomError here; that is the only way to see a throw inside restore(). */
let sink = [];

let store = {};
function mk(o){
  return {
    getItem: k => (k in o ? o[k] : null),
    setItem: (k, v) => { o[k] = String(v); },
    removeItem: k => { delete o[k]; },
    clear: () => { for (const k in o) delete o[k]; },
    key: i => Object.keys(o)[i] || null,
    get length(){ return Object.keys(o).length; },
  };
}
function open(){
  sink = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', e => sink.push(String(e.message || e)));
  return new JSDOM('<!doctype html><html><body>' + html + '</body></html>', {
    runScripts: 'dangerously', pretendToBeVisual: true, virtualConsole: vc,
    url: 'https://omen.test/ref2.html',
    beforeParse(w){
      Object.defineProperty(w, 'localStorage', {value: mk(store), configurable: true});
      Object.defineProperty(w, 'sessionStorage', {value: mk({}), configurable: true});
    },
  });
}
const settle = ms => new Promise(r => setTimeout(r, ms));

function svgOf(doc){ return doc.querySelector('svg.chart[data-tappable="1"]'); }
function geom(svg){
  const g = {};
  for (const k of ['n','padl','padt','plotw','ploth','lo','hi'])
    g[k] = +svg.getAttribute('data-' + k);
  return g;
}
function Xc(g, i){ return g.padl + (i + 0.5) * g.plotw / g.n; }
function Yc(g, p){ return g.padt + (g.hi - p) * g.ploth / ((g.hi - g.lo) || 1); }

function tap(win, el, x, y){
  const Evt = win.PointerEvent || win.MouseEvent;
  el.dispatchEvent(new Evt('pointerdown',
    {clientX: x, clientY: y, bubbles: true, cancelable: true}));
}
/* overlay = what the chart actually DRAWS, read off the SVG text nodes. */
function overlay(svg){
  const grab = sel => {
    const el = svg.querySelector(sel);
    return el && !el.hasAttribute('hidden') ? el.textContent : null;
  };
  return {entry: grab('.tap-entry-t'), stop: grab('.tap-stop-t'),
          pt0: grab('.tap-pt0-t'), pt1: grab('.tap-pt1-t'), pt2: grab('.tap-pt2-t')};
}
function exportRows(doc){
  doc.getElementById('exportbtn').click();
  return doc.getElementById('out').value.split('\n').filter(l => l.trim());
}

const out = {phases: {}, errors: []};

(async () => {

// ---------------- phase A: drive the real handlers from outside --------------
let dom = open(); await settle(150);
let doc = dom.window.document, win = dom.window;
let svg = svgOf(doc), g = geom(svg);
const ohlc = JSON.parse(svg.getAttribute('data-ohlc'));
out.geom = g;
const taphit = svg.querySelector('.taphit'), railhit = svg.querySelector('.railhit');
const CID = svg.closest('.card').getAttribute('data-cid');

// A: one tap, then read storage in the SAME tick (no await) -> synchronous save?
tap(win, taphit, Xc(g, 7), g.padt + 4);
const keys = Object.keys(store);
out.sync_keys_same_tick = keys.length;
out.sync_blob_same_tick = keys.length ? JSON.parse(store[keys[0]]) : null;

// stop: tap bar 3 low in the plot; entry close is above, so "long" -> bar 3 LOW
tap(win, taphit, Xc(g, 3), g.padt + g.ploth - 3);
// three rail taps
const prices = [g.lo + (g.hi - g.lo) * 0.70,
                g.lo + (g.hi - g.lo) * 0.80,
                g.lo + (g.hi - g.lo) * 0.90];
for (const p of prices) tap(win, railhit, g.padl + g.plotw + 2, Yc(g, p));
out.after_five_taps = overlay(svg);

// A3: a 4th rail tap should reset the card
tap(win, railhit, g.padl + g.plotw + 2, Yc(g, prices[0]));
out.after_reset_tap = overlay(svg);
out.after_reset_blob = JSON.parse(store[CID ? Object.keys(store)[0] : Object.keys(store)[0]]);

// redo the marks so phases B/C have something to restore
tap(win, taphit, Xc(g, 7), g.padt + 4);
tap(win, taphit, Xc(g, 3), g.padt + g.ploth - 3);
for (const p of prices) tap(win, railhit, g.padl + g.plotw + 2, Yc(g, p));
const slider = doc.querySelector('input.runner');
slider.value = '42';
slider.dispatchEvent(new win.Event('input', {bubbles: true}));

out.phaseA_overlay = overlay(svg);
out.phaseA_export = exportRows(doc);
out.phaseA_store = JSON.parse(JSON.stringify(store));
dom.window.close();

// ---------------- phase B: fresh document, same storage ----------------------
dom = open(); await settle(150);
doc = dom.window.document;
out.phaseB_overlay = overlay(svgOf(doc));
out.phaseB_export = exportRows(doc);
out.phaseB_slider = doc.querySelector('input.runner').value;
dom.window.close();

// ---------------- phase C: cleared storage -----------------------------------
store = {};
dom = open(); await settle(150);
doc = dom.window.document;
out.phaseC_overlay = overlay(svgOf(doc));
out.phaseC_export = exportRows(doc);
out.phaseC_slider = doc.querySelector('input.runner').value;
dom.window.close();

// ---------------- phase D: OLD pre-H2 blob, no `tap` key ---------------------
const OLDKEY = Object.keys(out.phaseA_store)[0];
store = {}; store[OLDKEY] = JSON.stringify({picked: {q1: ['yes']}, notes: {q1: 'old note'}});
dom = open();
await settle(150);
out.phaseD_load_errors = sink.slice();     // errors from PARSE/restore only
doc = dom.window.document;
out.phaseD_overlay = overlay(svgOf(doc));
out.phaseD_readout = doc.querySelector('[data-role="tapout"]').textContent;
out.phaseD_export = exportRows(doc);
dom.window.close();

// ---------------- phase F: the mis-tap / correction path ---------------------
// He is marking on a phone. Suppose the FIRST tap lands on the wrong candle.
// What can he do about it without clearing site data?
store = {};
dom = open(); await settle(150);
doc = dom.window.document; win = dom.window;
svg = svgOf(doc); g = geom(svg);
const th2 = svg.querySelector('.taphit'), rh2 = svg.querySelector('.railhit');
tap(win, th2, Xc(g, 9), g.padt + 4);                    // oops -- meant bar 10
out.F_after_wrong_entry = overlay(svg);
tap(win, th2, Xc(g, 10), g.padt + 4);                   // tap the right candle
out.F_retap_candle = overlay(svg);                      // -> becomes the STOP, not a fix
tap(win, rh2, g.padl + g.plotw + 2, Yc(g, g.lo + (g.hi - g.lo) * 0.6));
out.F_rail_after = overlay(svg);                        // -> becomes PT1
out.F_taps_needed_to_reset = (function(){
  let k = 0;
  // keep tapping the rail until the card resets; cap so a bug cannot hang us
  while (k < 12){
    tap(win, rh2, g.padl + g.plotw + 2, Yc(g, g.lo + (g.hi - g.lo) * 0.6));
    k++;
    const o = overlay(svg);
    if (o.entry === null && o.stop === null) return k;
  }
  return -1;
})();
out.F_has_clear_button = !!doc.querySelector('[data-role="tapclear"], .tapclear, button.clear');
dom.window.close();

// ---------------- phase E: malformed tap blob (entry_i only) -----------------
store = {}; store[OLDKEY] = JSON.stringify({picked: {}, notes: {}, tap: {entry_i: 2}});
dom = open();
await settle(150);
out.phaseE_load_errors = sink.slice();     // errors from PARSE/restore only
doc = dom.window.document;
try { out.phaseE_overlay = overlay(svgOf(doc)); } catch (e) { out.phaseE_overlay = 'READ THREW: ' + e.message; }
out.phaseE_readout = doc.querySelector('[data-role="tapout"]').textContent;
try { out.phaseE_export = exportRows(doc); } catch (e) { out.phaseE_export = 'EXPORT THREW: ' + e.message; }
dom.window.close();

process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e.stack || e); process.exit(1); });
"""


def expected_candles():
    """Re-derive the self-test's candles independently of the page."""
    return builder.make_candles()


def main():
    full = builder.build()
    assert full.endswith(builder.DRIVER), "self-driver is not the page suffix any more"
    page = full[: -len(builder.DRIVER)]
    with open(PAGE, "w", encoding="utf-8") as fh:
        fh.write(page)
    with open(DRV, "w", encoding="utf-8") as fh:
        fh.write(NODE)

    fails, notes = [], []

    def check(name, cond, detail=""):
        print("%-52s %s%s" % (name, "PASS" if cond else "FAIL",
                              ("  " + str(detail)) if detail else ""))
        if not cond:
            fails.append(name)

    # ---- F/G: static properties of the SERVED page -------------------------
    check("no <canvas> in served page", "<canvas" not in page)
    check("no external <script src=>", "<script src" not in page.replace(" ", ""))
    check("pointerdown handler present", "pointerdown" in page)
    check("tap hit surfaces present", "taphit" in page and "railhit" in page)
    has_touch_action = "touch-action" in page
    print("%-52s %s" % ("touch-action declared on hit surfaces",
                        "yes" if has_touch_action else "NO  (defect candidate)"))
    if not has_touch_action:
        notes.append("no touch-action on .taphit/.railhit")
    has_import = ('type="file"' in page) or ("importbtn" in page)
    print("%-52s %s" % ("page has an IMPORT path at all",
                        "yes" if has_import else "NO  (export is one-way)"))
    if not has_import:
        notes.append("no import path exists in the shell; 'clear + re-import' is untestable")

    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        print("node not on PATH -- browser phases skipped")
        return 1

    proc = subprocess.run(["node", DRV, PAGE], capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        print(proc.stderr[-4000:])
        raise SystemExit("referee driver failed")
    r = json.loads(proc.stdout)
    os.remove(DRV)

    cs = expected_candles()
    # entry tapped at bar 7; stop tapped on bar 3 below the entry close -> long -> bar 3 LOW
    want_stop = cs[3]["l"]
    print("\nhand-derived from research/build_tap_selftest.make_candles():")
    print("  bar 3  o=%.2f h=%.2f l=%.2f c=%.2f   -> expected stop %.2f"
          % (cs[3]["o"], cs[3]["h"], cs[3]["l"], cs[3]["c"], want_stop))
    print("  bar 7  c=%.2f (the entry close the direction test uses)\n" % cs[7]["c"])

    # ---- A: synchronous save ------------------------------------------------
    check("A  one tap writes localStorage in the same tick",
          r["sync_keys_same_tick"] == 1, r["sync_keys_same_tick"])
    blob = r["sync_blob_same_tick"] or {}
    check("A  that first write already carries entry_i=7",
          (blob.get("tap") or {}).get("entry_i") == 7, (blob.get("tap") or {}))

    # ---- A2: stop re-derived by hand ---------------------------------------
    got_stop = r["after_five_taps"]["stop"]
    check("A2 stop label == hand-derived bar-3 low %.2f" % want_stop,
          got_stop == "STOP %.2f" % want_stop, got_stop)
    check("A2 three PT labels drawn",
          all(r["after_five_taps"][k] for k in ("pt0", "pt1", "pt2")),
          [r["after_five_taps"][k] for k in ("pt0", "pt1", "pt2")])

    # ---- A3: reset ----------------------------------------------------------
    ar = r["after_reset_tap"]
    check("A3 4th rail tap clears every overlay mark",
          all(ar[k] is None for k in ar), ar)

    # ---- B: overlay rebuilt on reload --------------------------------------
    check("B  reload rebuilds the SVG overlay (text nodes match)",
          r["phaseB_overlay"] == r["phaseA_overlay"],
          "%s vs %s" % (r["phaseB_overlay"], r["phaseA_overlay"]))
    check("B  reload re-exports an identical row",
          r["phaseB_export"] == r["phaseA_export"])
    check("B  reload restores the runner slider to 42",
          r["phaseB_slider"] == "42", r["phaseB_slider"])
    rowA = json.loads(r["phaseA_export"][0]) if r["phaseA_export"] else {}
    check("B  export keeps the pre-H2 fields (type/probe/card_id/answers/notes)",
          all(k in rowA for k in ("type", "probe", "card_id", "answers", "notes")),
          sorted(rowA.keys()))
    check("B  export adds entry_i/stop_p/pt/runner_pct",
          all(k in rowA for k in ("entry_i", "stop_p", "pt", "runner_pct")),
          {k: rowA.get(k) for k in ("entry_i", "stop_p", "pt", "runner_pct")})

    # ---- C: cleared storage -------------------------------------------------
    check("C  cleared storage -> no overlay marks",
          all(v is None for v in r["phaseC_overlay"].values()), r["phaseC_overlay"])
    # "(nothing answered yet)" is the shell's PRE-H2 placeholder (probe_page.py:574),
    # not an H2 regression -- the contract is "no data row", not "no text".
    check("C  cleared storage -> no data row exported",
          r["phaseC_export"] == ["(nothing answered yet)"], r["phaseC_export"])
    check("C  cleared storage -> slider back at its 10 default",
          r["phaseC_slider"] == "10", r["phaseC_slider"])

    # ---- D: old pre-H2 blob -------------------------------------------------
    # jsdom does not implement Element.scrollIntoView; the shell's export button
    # calls it (probe_page.py:576), so that one message is a harness artifact and
    # is discounted here -- anything else is a real throw.
    JSDOM_GAP = "scrollIntoView is not a function"
    d_err = [e for e in r["phaseD_load_errors"] if JSDOM_GAP not in e]
    check("D  a pre-H2 blob with no `tap` key restores without throwing",
          d_err == [], d_err)
    check("D  and draws no tap overlay",
          all(v is None for v in r["phaseD_overlay"].values()), r["phaseD_overlay"])
    check("D  and still exports its old answers row",
          len(r["phaseD_export"]) == 1, r["phaseD_export"])

    # ---- F: the mis-tap correction path ------------------------------------
    print()
    print("F  what happens when a tap lands on the wrong candle (phone reality):")
    print("     tap 1 wrong candle (bar 9) -> %r" % (r["F_after_wrong_entry"]["entry"],))
    print("     tap 2 the RIGHT candle     -> entry %r, stop %r"
          % (r["F_retap_candle"]["entry"], r["F_retap_candle"]["stop"]))
    print("     tap 3 the rail to fix it   -> pt0 %r" % (r["F_rail_after"]["pt0"],))
    print("     rail taps still needed to clear the card: %s"
          % (r["F_taps_needed_to_reset"],))
    print("     a clear/undo control on the card: %s"
          % ("yes" if r["F_has_clear_button"] else "NO"))
    if not r["F_has_clear_button"]:
        notes.append(
            "no undo and no clear control: a mis-tapped entry cannot be corrected. "
            "The second candle tap becomes the STOP, further candle taps are no-ops, "
            "and the only reset is a rail tap once all 3 PTs are filled -- measured at "
            "%s further rail taps from a wrong first tap." % (r["F_taps_needed_to_reset"],))

    # ---- E: malformed tap blob ---------------------------------------------
    e_err = [e for e in r["phaseE_load_errors"] if JSDOM_GAP not in e]
    e_clean = (e_err == [] and isinstance(r["phaseE_export"], list))
    print()
    print("%-52s %s" % ("E  malformed tap blob (entry_i only) survives",
                        "yes" if e_clean else "NO  (defect candidate)"))
    print("     restore-time errors : %r" % (e_err,))
    print("     readout after load  : %r" % (r["phaseE_readout"],))
    print("     overlay             : %r" % (r["phaseE_overlay"],))
    print("     export              : %r" % (r["phaseE_export"],))
    if not e_clean:
        notes.append("restore() assigns a stored tap blob verbatim with no default merge; "
                     "a blob missing pt/runner_pct throws inside paintTap and aborts the "
                     "rest of restore(): %r" % (e_err,))

    print()
    for n in notes:
        print("NOTE: " + n)
    print()
    if fails:
        print("FAILED: %s" % ", ".join(fails))
        return 1
    print("all blocking checks passed (%d notes)" % len(notes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
