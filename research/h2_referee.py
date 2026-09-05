"""h2_referee.py -- independent re-derivation of H2 (tap-on-chart marking, 7eb6aec7).

    python research/h2_referee.py

Nothing here trusts the builder's test. It:

  1. renders probe_chart with the PRE-H2 module and the post-H2 module and
     byte-compares both the default call and the `interactive=True` call, to
     test the docstring claim that "every existing caller's SVG is
     byte-identical";
  2. recomputes entry_i / stop_p / pt[] from the synthetic candles and the
     SVG's own scale attributes, by hand, and compares them to what the page
     actually exports under jsdom;
  3. seeds localStorage with an OLD-format card blob (no `tap` key) and checks
     the page restores and re-exports without losing the old fields;
  4. greps the served page for canvas / external <script src> / pointer
     handlers / touch-action.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SCRATCH = os.environ.get("H2_SCRATCH", HERE)

import build_tap_selftest as builder      # noqa: E402
import probe_chart as pc_new              # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print("%-52s %s%s" % (name, "PASS" if cond else "FAIL",
                          ("  " + str(detail)) if detail else ""))
    if not cond:
        FAILS.append(name)


def load_old_probe_chart():
    """The pre-H2 probe_chart.py, extracted from git, imported under its own name."""
    path = os.path.join(SCRATCH, "_probe_chart_preh2.py")
    src = subprocess.run(["git", "show", "7eb6aec7^:research/probe_chart.py"],
                         cwd=os.path.dirname(HERE), capture_output=True, text=True,
                         timeout=60)
    if src.returncode != 0:
        raise SystemExit("git show failed: %s" % src.stderr[-500:])
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(src.stdout)
    spec = importlib.util.spec_from_file_location("probe_chart_preh2", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NODE_DRIVER = r"""
const fs = require('fs');
const { JSDOM } = require('jsdom');
const html = fs.readFileSync(process.argv[2], 'utf8');
const seed = JSON.parse(process.argv[3] || '{}');
const store = Object.assign({}, seed), sess = {};
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
  return new JSDOM('<!doctype html><html><body>' + html + '</body></html>', {
    runScripts: 'dangerously', pretendToBeVisual: true, url: 'https://omen.test/tap.html',
    beforeParse(w){
      Object.defineProperty(w, 'localStorage', {value: mk(store), configurable: true});
      Object.defineProperty(w, 'sessionStorage', {value: mk(sess), configurable: true});
    },
  });
}
const settle = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const out = {};
  let dom = open(); await settle(200);
  out.export1 = dom.window.document.getElementById('out').value;
  out.stored1 = JSON.stringify(store);
  dom.window.close();
  dom = open(); await settle(200);
  out.title2 = dom.window.document.title;
  out.export2 = dom.window.document.getElementById('out').value;
  out.result2 = dom.window.document.getElementById('result').textContent;
  dom.window.close();
  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""


def run_node(page, seed):
    drv = os.path.join(SCRATCH, "_h2_referee_driver.js")
    with open(drv, "w", encoding="utf-8") as fh:
        fh.write(NODE_DRIVER)
    try:
        proc = subprocess.run(["node", drv, page, json.dumps(seed)],
                              capture_output=True, text=True, timeout=120)
    finally:
        try:
            os.remove(drv)
        except OSError:
            pass
    if proc.returncode != 0:
        print(proc.stderr[-3000:])
        raise SystemExit("node driver failed")
    return json.loads(proc.stdout)


def main():
    candles = builder.make_candles()

    # ---- 1. byte-identity for existing callers ---------------------------
    old = load_old_probe_chart()
    a = old.render(candles, {}, label="x")
    b = pc_new.render(candles, {}, label="x")
    check("default render byte-identical to pre-H2", a == b,
          "" if a == b else "%d vs %d bytes" % (len(a), len(b)))

    a2 = old.render(candles, {}, label="x", interactive=True)
    b2 = pc_new.render(candles, {}, label="x", interactive=True)
    check("interactive=True render byte-identical to pre-H2", a2 == b2,
          "" if a2 == b2 else "new adds %r"
          % (re.findall(r'data-h="\d+"', b2) or "?",))

    # ---- 2. re-derive the marks by hand ----------------------------------
    page = builder.build()
    with open(builder.OUT, "w", encoding="utf-8") as fh:
        fh.write(page)

    lo = float(re.search(r'data-lo="([-\d.]+)"', page).group(1))
    hi = float(re.search(r'data-hi="([-\d.]+)"', page).group(1))
    ohlc = json.loads(re.search(r'data-ohlc="([^"]+)"', page).group(1)
                      .replace("&quot;", '"'))
    # the driver taps bar 5 for entry and bar 12 low-side for the stop
    want_entry = 5
    want_stop = ohlc[12][2]
    want_pt = [lo + (hi - lo) * f for f in (0.75, 0.85, 0.95)]
    # and the candles themselves say what bar 12's low is, with no SVG involved
    check("bar 12 low from raw candles == data-ohlc low",
          abs(candles[12]["l"] - want_stop) < 1e-9,
          "%s vs %s" % (candles[12]["l"], want_stop))

    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
        node_ok = True
    except (OSError, subprocess.CalledProcessError):
        node_ok = False
    if not node_ok:
        print("node not on PATH -- browser checks skipped")
        return 1 if FAILS else 0

    r = run_node(builder.OUT, {})
    lines = [l for l in r["export1"].split("\n") if l.strip()]
    check("export is exactly one row", len(lines) == 1, len(lines))
    row = json.loads(lines[0]) if lines else {}
    check("exported entry_i == hand-derived 5", row.get("entry_i") == want_entry,
          row.get("entry_i"))
    check("exported stop_p == hand-derived bar-12 low",
          isinstance(row.get("stop_p"), float)
          and abs(row["stop_p"] - want_stop) < 1e-6,
          "%s vs %s" % (row.get("stop_p"), want_stop))
    got_pt = row.get("pt") or []
    check("exported pt[] == hand-derived rail prices",
          len(got_pt) == 3 and all(abs(g - w) < 1e-6 for g, w in zip(got_pt, want_pt)),
          "%s vs %s" % (got_pt, [round(p, 5) for p in want_pt]))
    check("exported runner_pct == 35", row.get("runner_pct") == 35,
          row.get("runner_pct"))
    check("phase 2 (fresh document, same storage) reports PASS",
          r["title2"].startswith("PASS"), r["title2"])
    check("re-export after reload is byte-identical",
          r["export2"].strip() == r["export1"].strip())
    stored = json.loads(r["stored1"])
    check("every tap wrote localStorage (blob carries tap)",
          any("tap" in json.loads(v) for v in stored.values()), list(stored))

    # ---- 3. an OLD blob (no tap key) still restores and exports -----------
    old_blob = {"picked": {"q1": ["yes"]}, "notes": {"q1": "old note from before H2"}}
    seed = {"omen-probe:tap-selftest:selftest-1": json.dumps(old_blob)}
    r2 = run_node(builder.OUT, seed)
    lines2 = [l for l in r2["export1"].split("\n") if l.strip()]
    row2 = json.loads(lines2[0]) if lines2 else {}
    check("old blob (no tap field) does not break the page", bool(lines2), len(lines2))
    # The shell has always rebuilt `notes`/`answers` from the DOM, so a stored
    # note only survives where a matching question element exists; the self-test
    # page has no questions, so the right check is that the pre-H2 key set is
    # still fully present in the row.
    pre_h2_keys = {"type", "probe", "card_id", "grade", "answers", "notes",
                   "symbol", "date"}
    check("export still carries every pre-H2 field",
          pre_h2_keys.issubset(set(row2)), sorted(pre_h2_keys - set(row2)))
    check("old blob still gets the new fields once tapped",
          row2.get("entry_i") == 5 and len(row2.get("pt") or []) == 3,
          [row2.get("entry_i"), row2.get("pt")])

    # ---- 4. served-page hygiene ------------------------------------------
    check("no <canvas>", "<canvas" not in page)
    check("no external <script src>",
          not re.search(r"<script[^>]+src=", page))
    check("pointerdown handler present", "pointerdown" in page)
    check("touch-action set on the tap surfaces", "touch-action" in page,
          "absent -- a scroll gesture starting on the chart still fires a tap")

    print()
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
        return 1
    print("all referee checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
