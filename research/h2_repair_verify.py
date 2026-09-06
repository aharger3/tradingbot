"""h2_repair_verify.py -- confirms the H2 repair's undo/clear control works.

Independent of build_tap_selftest.py's own driver: strips the self-driver off the
built self-test page (same technique as h2_referee_pass2.py) and drives a wrong
entry tap, then a click on the tapout readout, and checks the card returns to its
untapped state in one click (not the three junk rail taps the referee measured).

    python research/h2_repair_verify.py
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
PAGE = os.path.join(SCRATCH, "h2_repair_page.html")
DRV = os.path.join(SCRATCH, "h2_repair_driver.js")

NODE = r"""
const fs = require('fs');
const { JSDOM } = require('jsdom');
const html = fs.readFileSync(process.argv[2], 'utf8');

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

const dom = new JSDOM('<!doctype html><html><body>' + html + '</body></html>', {
  runScripts: 'dangerously', pretendToBeVisual: true,
  url: 'https://omen.test/repair.html',
  beforeParse(w){
    Object.defineProperty(w, 'localStorage', {value: mk(store), configurable: true});
    Object.defineProperty(w, 'sessionStorage', {value: mk({}), configurable: true});
  },
});
const win = dom.window, doc = win.document;

function svgOf(){ return doc.querySelector('svg.chart[data-tappable="1"]'); }
function geom(svg){
  const g = {};
  for (const k of ['n','padl','padt','plotw','ploth','lo','hi'])
    g[k] = +svg.getAttribute('data-' + k);
  return g;
}
function Xc(g, i){ return g.padl + (i + 0.5) * g.plotw / g.n; }
function tap(el, x, y){
  const Evt = win.PointerEvent || win.MouseEvent;
  el.dispatchEvent(new Evt('pointerdown', {clientX: x, clientY: y, bubbles: true, cancelable: true}));
}
function overlayShown(svg){
  const hit = sel => { const el = svg.querySelector(sel); return el && !el.hasAttribute('hidden'); };
  return hit('.tap-entry') || hit('.tap-stop') || hit('.tap-pt0');
}

(async () => {
  await new Promise(r => setTimeout(r, 30));
  const svg = svgOf();
  const g = geom(svg);
  const hit = svg.querySelector('.taphit');

  // Tap a wrong candle for entry (bar 9).
  tap(hit, Xc(g, 9), g.padt + 5);
  const cid = doc.querySelector('.card').getAttribute('data-cid');
  const beforeClear = JSON.parse(store['probe_selftest' + cid] || store[Object.keys(store).find(k => k.endsWith(cid))]);

  const out = {};
  out.entry_after_tap = beforeClear && beforeClear.tap ? beforeClear.tap.entry_i : undefined;
  out.overlay_after_tap = overlayShown(svg);

  // Click the readout to clear (the repair's undo control).
  const readout = doc.querySelector('[data-role="tapout"]');
  readout.dispatchEvent(new win.MouseEvent('click', {bubbles: true, cancelable: true}));

  const key = Object.keys(store).find(k => k.endsWith(cid));
  const afterClear = JSON.parse(store[key]);
  out.entry_after_clear = afterClear.tap.entry_i;
  out.stop_after_clear = afterClear.tap.stop_p;
  out.pt_after_clear = afterClear.tap.pt;
  out.overlay_after_clear = overlayShown(svg);
  out.readout_text_after_clear = readout.textContent;

  // A second click on an already-clear card must be a no-op (idempotent).
  const before = JSON.stringify(store[key]);
  readout.dispatchEvent(new win.MouseEvent('click', {bubbles: true, cancelable: true}));
  out.idempotent_on_clear_card = (JSON.stringify(store[key]) === before);

  console.log(JSON.stringify(out));
})();
"""


def main():
    html = builder.build()
    # Strip the self-driver (same lines as build_tap_selftest.DRIVER) so nothing
    # auto-taps the card before we drive it ourselves.
    marker = "<script>\n(function(){\n"
    idx = html.rfind(marker)
    served = html[:idx] if idx > 0 else html
    with open(PAGE, "w", encoding="utf-8") as fh:
        fh.write(served)
    with open(DRV, "w", encoding="utf-8") as fh:
        fh.write(NODE)

    proc = subprocess.run(
        ["node", DRV, PAGE], capture_output=True, text=True, timeout=30
    )
    if proc.returncode != 0:
        print("NODE FAILED:\n" + proc.stderr, file=sys.stderr)
        sys.exit(1)
    out = json.loads(proc.stdout.strip().splitlines()[-1])

    checks = [
        ("wrong entry tap recorded (bar 9)", out.get("entry_after_tap") == 9),
        ("overlay shows the mark before clearing", out.get("overlay_after_tap") is True),
        ("one click on the readout clears entry_i", out.get("entry_after_clear") is None),
        ("...and stop_p", out.get("stop_after_clear") is None),
        ("...and pt[]", out.get("pt_after_clear") == []),
        ("overlay hidden after clear", out.get("overlay_after_clear") is False),
        ("readout returns to the untapped prompt", "tap a candle for entry" in (out.get("readout_text_after_clear") or "")),
        ("clicking an already-clear card is a no-op", out.get("idempotent_on_clear_card") is True),
    ]
    fails = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(("PASS" if ok else "FAIL") + "  " + name)
    print()
    print(json.dumps(out, indent=2))
    if fails:
        print("\nFAILED: " + "; ".join(fails), file=sys.stderr)
        sys.exit(1)
    print("\nall checks passed")


if __name__ == "__main__":
    main()
