"""H2 referee, pass 3 (repair round) -- independent verification.

Refereeing builder commit a32eacd8 ("H2 repair: one-click undo/clear control on
the tap readout, restore() merges stored tap blobs over defaultTap(), touch-action
on tap hit surfaces"), which repairs the three code defects pass 2 (90a3f9dd) found.

Nothing here reuses the builder's driver (build_tap_selftest.py's second inline
script) or either earlier referee script. The self-test page's own driver script is
STRIPPED before loading, so only the shared shell (probe_page.py's CSS+JS, as
served) is exercised, and every expected value is re-derived in Python from the
served SVG's own data-* attributes before the browser runs.

Run:  python research/h2_referee_pass3.py
Needs node with jsdom (same dependency the earlier passes used).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "research" / "probes" / "tap_selftest.html"


def strip_driver(html: str) -> str:
    """Remove the LAST inline <script> block (the self-test's own driver)."""
    spans = [(m.start(), m.end()) for m in re.finditer(r"<script>.*?</script>", html, re.S)]
    if len(spans) != 2:
        raise SystemExit(f"expected exactly 2 inline scripts, found {len(spans)}")
    s, e = spans[-1]
    return html[:s] + html[e:]


def svg_attrs(html: str) -> dict:
    m = re.search(r'<svg class="chart"[^>]*>', html)
    if not m:
        raise SystemExit("no chart svg found")
    tag = m.group(0)
    out = {}
    for k in ("n", "padl", "padt", "plotw", "ploth", "lo", "hi", "w", "h"):
        mm = re.search(r'data-%s="([^"]+)"' % k, tag)
        out[k] = float(mm.group(1)) if mm else None
    mm = re.search(r'data-ohlc="([^"]+)"', tag) or re.search(r"data-ohlc='([^']+)'", tag)
    out["ohlc"] = json.loads(mm.group(1))
    return out


NODE = r"""
const fs = require('fs');
const {JSDOM} = require('jsdom');
const cfg = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const html = fs.readFileSync(cfg.page, 'utf8');
const out = {errors: []};

function mk(storage, mutate){
  const dom = new JSDOM(html, {
    runScripts: 'dangerously', url: 'https://example.org/tap',
    beforeParse(w){
      // seed localStorage before the shell's restore() runs during parse
      for (const k in storage) w.localStorage.setItem(k, storage[k]);
      w.Element.prototype.scrollIntoView = function(){};
      if (mutate) w.document.addEventListener('DOMContentLoaded', function(){});
    },
    virtualConsole: new (require('jsdom').VirtualConsole)().on('jsdomError', e => {
      out.errors.push(String(e && e.message || e));
    })
  });
  return dom;
}

// mutate the raw HTML to make a 2-card deck (clone the card, new data-cid)
function twoCardHtml(){
  const dom = new JSDOM(html);
  const d = dom.window.document;
  const card = d.querySelector('.card');
  const clone = card.cloneNode(true);
  clone.setAttribute('data-cid', 'selftest-2');
  clone.setAttribute('data-export', '{"symbol":"TEST2","date":"2026-01-06"}');
  card.parentNode.insertBefore(clone, card.nextSibling);
  return dom.serialize();
}

function domFrom(rawHtml, storage){
  const {VirtualConsole} = require('jsdom');
  const vc = new VirtualConsole();
  const errs = [];
  vc.on('jsdomError', e => errs.push(String(e && e.message || e)));
  const dom = new JSDOM(rawHtml, {
    runScripts: 'dangerously', url: 'https://example.org/tap',
    beforeParse(w){
      for (const k in storage) w.localStorage.setItem(k, storage[k]);
      w.Element.prototype.scrollIntoView = function(){};
    },
    virtualConsole: vc
  });
  dom._errs = errs;
  return dom;
}

function tap(win, el, x, y){
  const ev = new win.MouseEvent('pointerdown', {bubbles:true, cancelable:true, clientX:x, clientY:y});
  el.dispatchEvent(ev);
}
function overlay(doc, root){
  const q = s => { const n = (root||doc).querySelector(s);
    return n ? (n.hasAttribute('hidden') ? null : n.textContent) : 'MISSING'; };
  return {entry:q('.tap-entry-t'), stop:q('.tap-stop-t'),
          pt0:q('.tap-pt0-t'), pt1:q('.tap-pt1-t'), pt2:q('.tap-pt2-t')};
}
function exportText(doc){
  doc.getElementById('exportbtn').dispatchEvent(new doc.defaultView.MouseEvent('click',{bubbles:true}));
  return doc.getElementById('out').value;
}

const K1='omen-probe:tap-selftest:selftest-1';
const K2='omen-probe:tap-selftest:selftest-2';
const G = cfg.geom;
const X = i => G.padl + (i + 0.5) * G.plotw / G.n;
const Y = p => G.padt + (G.hi - p) * G.ploth / (G.hi - G.lo);

/* ---------- phase A: mark 3 things, sync save, export ---------- */
{
  const dom = domFrom(html, {});
  const w = dom.window, d = w.document;
  const svg = d.querySelector('svg.chart');
  const th = svg.querySelector('.taphit'), rh = svg.querySelector('.railhit');
  const before = w.localStorage.length;
  tap(w, th, X(cfg.entry_bar), G.padt + 5);
  out.A_sync_keys_same_tick = w.localStorage.length - before;
  out.A_sync_blob = w.localStorage.getItem(K1);
  tap(w, th, X(cfg.stop_bar), G.padt + G.ploth - 2);
  cfg.pt_prices.forEach(p => tap(w, rh, G.padl + G.plotw + 2, Y(p)));
  const slider = d.querySelector('input.runner');
  slider.value = '42';
  slider.dispatchEvent(new w.Event('input', {bubbles:true}));
  out.A_overlay = overlay(d);
  out.A_readout = d.querySelector('[data-role="tapout"]').textContent;
  out.A_export = exportText(d);
  out.A_storage = w.localStorage.getItem(K1);
  out.A_errors = dom._errs.slice();

  /* ---------- phase B: reload same storage, overlay + export identical ---- */
  const dom2 = domFrom(html, {[K1]: out.A_storage});
  out.B_overlay = overlay(dom2.window.document);
  out.B_readout = dom2.window.document.querySelector('[data-role="tapout"]').textContent;
  out.B_export = exportText(dom2.window.document);
  out.B_slider = dom2.window.document.querySelector('input.runner').value;
  out.B_errors = dom2._errs.slice();

  /* ---------- phase C: ONE click on the readout clears the card ---------- */
  const dom3 = domFrom(html, {[K1]: out.A_storage});
  const w3 = dom3.window, d3 = w3.document;
  out.C_slider_before = d3.querySelector('input.runner').value;
  const ro = d3.querySelector('[data-role="tapout"]');
  ro.dispatchEvent(new w3.MouseEvent('click', {bubbles:true}));
  out.C_overlay = overlay(d3);
  out.C_readout = ro.textContent;
  out.C_storage = w3.localStorage.getItem(K1);
  out.C_slider_after = d3.querySelector('input.runner').value;
  // second click on an already-clear card = no-op
  const snap = out.C_storage;
  ro.dispatchEvent(new w3.MouseEvent('click', {bubbles:true}));
  out.C_storage2 = w3.localStorage.getItem(K1);
  out.C_noop = (snap === out.C_storage2);
  // and the card is markable again straight after the clear
  const svg3 = d3.querySelector('svg.chart');
  tap(w3, svg3.querySelector('.taphit'), X(3), G.padt + 5);
  out.C_remark = d3.querySelector('[data-role="tapout"]').textContent;
  out.C_errors = dom3._errs.slice();
}

/* ---------- phase D: partial blob on card 1 of a 2-card deck ------------- */
{
  const two = twoCardHtml();
  const partial = JSON.stringify({picked:{}, notes:{}, tap:{entry_i:2}});
  const good = JSON.stringify({picked:{}, notes:{},
      tap:{entry_i:5, stop_p:99.7, pt:[101.0], runner_pct:33}});
  const dom = domFrom(two, {[K1]: partial, [K2]: good});
  const d = dom.window.document;
  const cards = d.querySelectorAll('.card');
  out.D_ncards = cards.length;
  out.D_card1_overlay = overlay(d, cards[0]);
  out.D_card1_readout = cards[0].querySelector('[data-role="tapout"]').textContent;
  out.D_card2_overlay = overlay(d, cards[1]);
  out.D_card2_readout = cards[1].querySelector('[data-role="tapout"]').textContent;
  out.D_card2_slider = cards[1].querySelector('input.runner').value;
  out.D_errors = dom._errs.slice();
  out.D_export = exportText(d);
}

/* ---------- phase E: a pre-H2 blob with no tap key at all --------------- */
{
  const old = JSON.stringify({picked:{q1:['yes']}, notes:{q1:'old note'}});
  const dom = domFrom(html, {[K1]: old});
  const d = dom.window.document;
  out.E_readout = d.querySelector('[data-role="tapout"]').textContent;
  out.E_overlay = overlay(d);
  out.E_export = exportText(d);
  out.E_errors = dom._errs.slice();
}

/* ---------- phase F: static properties of the served page --------------- */
{
  out.F_canvas = (html.match(/<canvas/g) || []).length;
  out.F_ext_script = (html.match(/<script[^>]+src=/g) || []).length;
  out.F_inline_script = (html.match(/<script>/g) || []).length;
  out.F_pointerdown = (html.match(/pointerdown/g) || []).length;
  out.F_touchaction = (html.match(/touch-action\s*:\s*none/g) || []).length;
  out.F_touchaction_rule = (html.match(/\.chart \.taphit, \.chart \.railhit\{[^}]*\}/) || [null])[0];
  out.F_file_input = (html.match(/type="file"/g) || []).length;
  out.F_tapout_markup = (html.match(/<div class="tapout"[^>]*>/g) || []);
}

console.log(JSON.stringify(out));
"""


def main() -> int:
    html = PAGE.read_text(encoding="utf-8")
    g = svg_attrs(html)
    stripped = strip_driver(html)

    entry_bar, stop_bar = 7, 3
    lo, hi = g["lo"], g["hi"]
    pt_fracs = [0.60, 0.72, 0.88]
    pt_prices = [lo + (hi - lo) * f for f in pt_fracs]
    # expected stop: bar 3's LOW, because the tap sits below the entry bar's close
    exp_stop = g["ohlc"][stop_bar][2]

    tmp = Path(tempfile.mkdtemp(prefix="h2ref3_"))
    page = tmp / "page.html"
    page.write_text(stripped, encoding="utf-8")
    cfg = tmp / "cfg.json"
    cfg.write_text(json.dumps({
        "page": str(page),
        "geom": {k: g[k] for k in ("n", "padl", "padt", "plotw", "ploth", "lo", "hi")},
        "entry_bar": entry_bar, "stop_bar": stop_bar, "pt_prices": pt_prices,
    }), encoding="utf-8")
    js = tmp / "drive.js"
    js.write_text(NODE, encoding="utf-8")

    r = subprocess.run(["node", str(js), str(cfg)], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(r.stdout[-4000:])
        print(r.stderr[-4000:], file=sys.stderr)
        return 2
    o = json.loads(r.stdout.strip().splitlines()[-1])

    checks: list[tuple[str, bool, str]] = []

    def chk(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    # --- A: the 3-mark round trip, expectations derived in Python -----------
    chk("A1 one tap writes localStorage in the same tick",
        o["A_sync_keys_same_tick"] == 1 and o["A_sync_blob"] and
        json.loads(o["A_sync_blob"])["tap"]["entry_i"] == entry_bar,
        f"keys+{o['A_sync_keys_same_tick']} blob={o['A_sync_blob']}")
    chk("A2 entry line = tapped bar",
        o["A_overlay"]["entry"] == f"ENTRY i={entry_bar}", str(o["A_overlay"]["entry"]))
    chk("A3 stop = tapped candle's low (hand-derived %.2f)" % exp_stop,
        o["A_overlay"]["stop"] == "STOP %.2f" % exp_stop, str(o["A_overlay"]["stop"]))
    for i, p in enumerate(pt_prices):
        chk("A4.%d PT%d = rail price %.4f" % (i + 1, i + 1, p),
            o["A_overlay"]["pt%d" % i] == "PT%d %.2f" % (i + 1, p),
            str(o["A_overlay"]["pt%d" % i]))
    st = json.loads(o["A_storage"])["tap"]
    chk("A5 stored pt[] matches to 1e-6",
        len(st["pt"]) == 3 and all(abs(a - b) < 1e-6 for a, b in zip(st["pt"], pt_prices)),
        str(st["pt"]))
    chk("A6 runner slider recorded", st["runner_pct"] in (42, "42"), str(st["runner_pct"]))
    chk("A7 no jsdom error while marking", not o["A_errors"], str(o["A_errors"]))

    # --- B: reload rebuilds the SVG overlay, not just the data --------------
    chk("B1 reload rebuilds the SVG overlay identically",
        o["B_overlay"] == o["A_overlay"], f"{o['B_overlay']} vs {o['A_overlay']}")
    chk("B2 export byte-identical after reload", o["B_export"] == o["A_export"])
    chk("B3 slider restores to 42", o["B_slider"] == "42", o["B_slider"])
    chk("B4 no jsdom error on restore", not o["B_errors"], str(o["B_errors"]))

    # --- the repair itself: one-click clear ---------------------------------
    chk("C1 readout advertises the clear control",
        "(tap here to clear)" in o["A_readout"], o["A_readout"])
    chk("C2 ONE click clears the whole overlay",
        all(v is None for v in o["C_overlay"].values()), str(o["C_overlay"]))
    chk("C3 readout returns to the untapped prompt",
        o["C_readout"] == "tap a candle for entry", o["C_readout"])
    cstore = json.loads(o["C_storage"])["tap"]
    chk("C4 stored tap state cleared synchronously",
        cstore["entry_i"] is None and cstore["stop_p"] is None and cstore["pt"] == [],
        o["C_storage"])
    chk("C5 second click on a clear card is a no-op", o["C_noop"], o["C_storage2"])
    chk("C6 card is markable again straight after the clear",
        o["C_remark"].startswith("entry bar 3"), o["C_remark"])
    chk("C7 no jsdom error through clear + re-mark", not o["C_errors"], str(o["C_errors"]))
    # side effect, reported not gated:
    runner_side_effect = (o["C_slider_before"], o["C_slider_after"])

    # --- D: partial blob no longer kills the rest of the deck ---------------
    chk("D0 two-card deck built", o["D_ncards"] == 2, str(o["D_ncards"]))
    chk("D1 partial blob throws nothing inside restore()",
        not [e for e in o["D_errors"] if "length" in e or "TypeError" in e], str(o["D_errors"]))
    chk("D2 card 1 renders its partial state",
        o["D_card1_readout"].startswith("entry bar 2"), o["D_card1_readout"])
    chk("D3 the NEXT card still restores (the pass-2 blast radius)",
        o["D_card2_overlay"]["entry"] == "ENTRY i=5"
        and o["D_card2_overlay"]["stop"] == "STOP 99.70"
        and o["D_card2_overlay"]["pt0"] == "PT1 101.00",
        str(o["D_card2_overlay"]))
    chk("D4 the next card's runner restores too", o["D_card2_slider"] == "33", o["D_card2_slider"])

    # --- E: a pre-H2 export/blob with no new fields still loads -------------
    chk("E1 pre-H2 blob (no tap key) restores without throwing", not o["E_errors"], str(o["E_errors"]))
    chk("E2 pre-H2 blob draws no overlay",
        all(v is None for v in o["E_overlay"].values()), str(o["E_overlay"]))
    prekeys = {"type", "probe", "card_id", "grade", "answers", "notes", "symbol", "date"}
    # The self-test card carries no question blocks, so a pre-H2 blob's `picked`/`notes`
    # have nowhere to land and the card exports as unanswered. What matters is that the
    # old blob neither throws nor fabricates a row; field preservation is checked on E4.
    chk("E3 pre-H2 blob neither throws nor fabricates a row",
        o["E_export"].strip() == "(nothing answered yet)", o["E_export"][:200])
    arows = [json.loads(l) for l in o["A_export"].strip().splitlines()
             if l.strip().startswith("{")]
    newkeys = {"entry_i", "stop_p", "pt", "runner_pct"}
    chk("E4 export adds the new fields on a marked card",
        bool(arows) and prekeys <= set(arows[0]) and newkeys <= set(arows[0]),
        str(sorted(arows[0])) if arows else o["A_export"][:200])

    # --- F: static shape ----------------------------------------------------
    chk("F1 no <canvas>", o["F_canvas"] == 0, str(o["F_canvas"]))
    chk("F2 no external <script src>", o["F_ext_script"] == 0, str(o["F_ext_script"]))
    chk("F3 pointer events present", o["F_pointerdown"] >= 1, str(o["F_pointerdown"]))
    chk("F4 touch-action:none on both hit rects",
        o["F_touchaction"] >= 1 and "touch-action:none" in (o["F_touchaction_rule"] or ""),
        str(o["F_touchaction_rule"]))
    chk("F5 no file-import path exists (so 'clear + re-import' is untestable by design)",
        o["F_file_input"] == 0, str(o["F_file_input"]))

    npass = sum(1 for _, ok, _ in checks if ok)
    for name, ok, detail in checks:
        print(("PASS  " if ok else "FAIL  ") + name + (("   [%s]" % detail) if (detail and not ok) else ""))
    print()
    print("observation (not a gate): clicking clear also resets the runner slider "
          f"{runner_side_effect[0]}% -> {runner_side_effect[1]}%")
    print("observation (not a gate): the clear control's markup "
          f"{o['F_tapout_markup']} is emitted by build_tap_selftest.py, not by the shared shell")
    print()
    print(f"{npass}/{len(checks)} checks pass")
    return 0 if npass == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
