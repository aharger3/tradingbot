"""test_tap_marks.py -- prove tap-on-chart marking (H2) actually works.

    python research/test_tap_marks.py

Renders research/probes/tap_selftest.html via research/build_tap_selftest.py
(the Python builder), then, matching research/test_omen_test1_page.py's
pattern, opens it in jsdom TWICE sharing one localStorage/sessionStorage --
"reload" without needing jsdom's unimplemented navigation. The page's own
embedded driver taps entry / stop / three PTs / the runner slider through the
SAME pointerdown/input handlers the real deck uses, exports, and (on the
second open) checks the restored marks and a second export are identical.

Also checks the export row format directly against a fixture: entry_i is an
int, stop_p a float, pt a list of floats, runner_pct an int.

Two known-harmless jsdom gaps show up on stderr and are not failures: jsdom
does not implement Element.scrollIntoView (probe_page.js's export-drawer
scroll -- the exception is isolated to that one listener per the DOM event
spec and does not stop the page), and it does not implement navigation, so
`location.reload()` is a logged no-op -- which is exactly why this test opens
a second jsdom document sharing storage instead of relying on it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_tap_selftest as builder    # noqa: E402

PAGE = builder.OUT

DRIVER = r"""
const fs = require('fs');
const { JSDOM } = require('jsdom');

const html = fs.readFileSync(process.argv[2], 'utf8');
const store = {}, sess = {};
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
const out = {};

(async () => {

// ---- phase 1: page taps itself on load, exports, "reloads" ---------------
let dom = open();
await settle(200);
let doc = dom.window.document;
out.title1 = doc.title;
out.result1 = doc.getElementById('result').textContent;
out.export1 = doc.getElementById('out').value;
out.keys_after_phase1 = Object.keys(store).length;
dom.window.close();

// ---- phase 2: fresh document, same storage --------------------------------
dom = open();
await settle(200);
doc = dom.window.document;
out.title2 = doc.title;
out.result2 = doc.getElementById('result').textContent;
dom.window.close();

process.stdout.write(JSON.stringify(out));

})().catch(e => { console.error(e); process.exit(1); });
"""


def render_page():
    """Renders the self-test page via the Python builder -- the file under
    test is always the one this run just produced, never a stale copy."""
    html = builder.build()
    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    with open(PAGE, "w", encoding="utf-8") as fh:
        fh.write(html)
    return html


def run():
    drv = os.path.join(HERE, "_tap_marks_driver.js")
    with open(drv, "w", encoding="utf-8") as fh:
        fh.write(DRIVER)
    try:
        proc = subprocess.run(["node", drv, PAGE], capture_output=True, text=True, timeout=60)
    finally:
        os.remove(drv)
    if proc.returncode != 0:
        print(proc.stderr[-4000:])
        raise SystemExit("jsdom driver failed")
    return json.loads(proc.stdout)


def check_fixture(row, verbose=True):
    """The export contract: entry_i int, stop_p float, pt list of floats,
    runner_pct int -- beside whatever the row already carried."""
    ok = True
    if not isinstance(row.get("entry_i"), int) or isinstance(row.get("entry_i"), bool):
        if verbose:
            print("  FAIL entry_i is %r, want int" % (row.get("entry_i"),))
        ok = False
    if not isinstance(row.get("stop_p"), (int, float)):
        if verbose:
            print("  FAIL stop_p is %r, want float" % (row.get("stop_p"),))
        ok = False
    pt = row.get("pt")
    if not (isinstance(pt, list) and len(pt) == 3
            and all(isinstance(p, (int, float)) for p in pt)):
        if verbose:
            print("  FAIL pt is %r, want a 3-element list of floats" % (pt,))
        ok = False
    if not isinstance(row.get("runner_pct"), int) or isinstance(row.get("runner_pct"), bool):
        if verbose:
            print("  FAIL runner_pct is %r, want int" % (row.get("runner_pct"),))
        ok = False
    return ok


def main():
    html = render_page()
    fails = []

    def check(name, cond, detail=""):
        print("%-42s %s%s" % (name, "PASS" if cond else "FAIL",
                               ("  " + str(detail)) if detail else ""))
        if not cond:
            fails.append(name)

    check("page renders", len(html) > 0)
    check("no <canvas> (static SVG only)", "<canvas" not in html)
    check("chart is tappable", 'data-tappable="1"' in html)
    check("hit surfaces present", "taphit" in html and "railhit" in html)
    check("runner slider present", 'class="runner"' in html)

    # The fixture check is independent of node: a canned row proves the
    # format-checking logic itself is right even with no browser available.
    fixture_row = {"entry_i": 5, "stop_p": 99.7, "pt": [100.84, 101.04, 101.24],
                   "runner_pct": 35}
    check("fixture row matches the export contract", check_fixture(fixture_row))
    check("fixture check rejects a bad row (entry_i as float)",
          not check_fixture(dict(fixture_row, entry_i=5.0), verbose=False))

    node_ok = True
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        node_ok = False

    if not node_ok:
        print("browser run not verified here -- node is not on PATH")
    else:
        r = run()
        # jsdom does not implement navigation, so location.reload() in phase 1
        # is a logged no-op -- the page never gets to call report() on its own
        # document there (a real browser's reload makes this moot). Phase 1's
        # job here is only to drive the taps and leave a real export + a real
        # localStorage write for phase 2 -- checked below.
        check("phase 1 left the title unset (no real reload under jsdom)",
              r["title1"] == "tap self-test", r["title1"])
        check("phase 2 (reload) reports PASS",
              r["title2"].startswith("PASS"), r["title2"])
        check("phase 2 result body says PASS", r["result2"].startswith("PASS"))
        check("something was actually saved to localStorage",
              r["keys_after_phase1"] > 0, r["keys_after_phase1"])

        lines1 = [l for l in r["export1"].split("\n") if l.strip()]
        check("phase 1 export is exactly one row", len(lines1) == 1, len(lines1))
        row1 = json.loads(lines1[0]) if lines1 else {}
        check("phase 1 export matches the fixture shape", check_fixture(row1))
        check("phase 1 entry_i == 5", row1.get("entry_i") == 5, row1.get("entry_i"))
        check("phase 1 runner_pct == 35", row1.get("runner_pct") == 35,
              row1.get("runner_pct"))

        # Failed sub-checks inside the page's own driver would still leave the
        # outer title/result as FAIL and get printed above; nothing further
        # to assert here once both phases read PASS.
        if any(r[k].startswith("FAIL") for k in ("title1", "title2")):
            print()
            print(r["result1"])
            print(r["result2"])

    print()
    if fails:
        print("FAILED: %s" % ", ".join(fails))
        return 1
    print("all checks passed" + ("" if node_ok else " (fixture only -- no browser run)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
