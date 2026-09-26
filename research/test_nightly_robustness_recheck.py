"""Plain asserts for nightly_loop.py's run_propfirm_overlay_search()/
run_edge_slices() (omen-nightly-robustness-recheck, 2026-09-26) -- synthetic
data only, no market data, no committed book, no subprocess actually spawned.

    python research/test_nightly_robustness_recheck.py

PR #27's own body says "Re-run the script on any new book" -- that re-run
was manual. This checks the WIRING that made it automatic, not the research
scripts themselves (research/propfirm_overlay_search.py and
research/edge_slices.py already have their own selfcheck()/check_stream()
assertions, run as part of the scripts themselves): both hooks are patched
to a fast synthetic `_run_research_script()` so this test runs in well under
a second, never touches the real ~100s/~80s grid searches, and never needs
the book file bt2y_trades_retest_on.json.gz this Mac may not have.

Checks:
 1. off the cadence day: both hooks skip without calling the (patched, and
    made to raise if called) research script, and still write an
    ok:true/skipped compact log.
 2. on the cadence day: both hooks call the (patched) research script, and
    turn its synthetic report into the compact summary the real nightly
    loop is meant to write to logs/*_latest.json, next to
    logs/propfirm_gate_latest.json.
 3. MUST NOT FAIL THE TASK: a research script that raises (timeout,
    non-zero exit, bad json -- _run_research_script raises for all three)
    is caught by both hooks; neither one re-raises, and both still write an
    ok:false log with the error recorded.
"""
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import nightly_loop


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="nightly_robustness_recheck_test_"))
    orig_logs = nightly_loop.LOGS
    orig_weekday = nightly_loop.ROBUSTNESS_RECHECK_WEEKDAY
    orig_runner = nightly_loop._run_research_script
    today_weekday = date.today().weekday()
    off_day = (today_weekday + 1) % 7  # guaranteed != today_weekday
    nightly_loop.LOGS = tmp

    try:
        # 1. off the cadence day -- must not call the research script at all.
        nightly_loop.ROBUSTNESS_RECHECK_WEEKDAY = off_day

        def _boom(*a, **k):
            raise AssertionError("research script called on an off day")

        nightly_loop._run_research_script = _boom
        nightly_loop.run_propfirm_overlay_search()
        nightly_loop.run_edge_slices()
        overlay = _read(tmp / "propfirm_overlay_search_latest.json")
        slices = _read(tmp / "edge_slices_latest.json")
        assert overlay["ok"] is True and overlay["skipped"], "overlay should skip off-cadence: %r" % overlay
        assert slices["ok"] is True and slices["skipped"], "edge slices should skip off-cadence: %r" % slices
        print("ok   off the cadence weekday, both hooks skip without touching the research script")

        # 2. on the cadence day -- a synthetic report becomes a compact summary.
        nightly_loop.ROBUSTNESS_RECHECK_WEEKDAY = today_weekday

        def _fake_overlay(script_name, raw_out_path, timeout_sec):
            return {
                "book": "research/bt2y_trades_retest_on.json.gz", "book_sessions": 498,
                "n_configs": 23976,
                "firms": {
                    "Topstep 50K Combine": {"best": {"overlay": "S+A, $250/R", "min_pass": 12.0, "robust": False}},
                    "Apex 50K": {"best": {"overlay": "all, $300/R", "min_pass": 66.9, "robust": True}},
                },
            }

        def _fake_edge(script_name, raw_out_path, timeout_sec):
            return {
                "book": "research/bt2y_trades_retest_on.json.gz", "n_trades": 6889,
                "n_slices": 1105, "n_bh_q05": 0, "n_bh_q10": 0, "n_survivors": 0,
                "slices": [{"slice": "sgrade=S", "bh_q": 0.177, "avg_r": -0.085, "survives": False}],
            }

        nightly_loop._run_research_script = _fake_overlay
        nightly_loop.run_propfirm_overlay_search()
        overlay = _read(tmp / "propfirm_overlay_search_latest.json")
        assert overlay["ok"] is True and "skipped" not in overlay, "should have actually run: %r" % overlay
        assert overlay["n_firms"] == 2 and overlay["n_robust"] == 1, \
            "expected 1/2 firms robust from the synthetic report: %r" % overlay
        assert overlay["firms"]["Apex 50K"]["robust"] is True

        nightly_loop._run_research_script = _fake_edge
        nightly_loop.run_edge_slices()
        slices = _read(tmp / "edge_slices_latest.json")
        assert slices["ok"] is True and "skipped" not in slices, "should have actually run: %r" % slices
        assert slices["n_survivors"] == 0 and slices["top_slice"]["slice"] == "sgrade=S", \
            "expected the synthetic top slice to come through: %r" % slices
        print("ok   on the cadence weekday, both hooks run and write a compact "
              "summary of the (synthetic) report")

        # 3. MUST NOT FAIL THE TASK -- a raising research script never
        # propagates out of either hook.
        def _fail(*a, **k):
            raise RuntimeError("propfirm_overlay_search.py exited 1: boom")

        nightly_loop._run_research_script = _fail
        nightly_loop.run_propfirm_overlay_search()  # must not raise
        nightly_loop.run_edge_slices()               # must not raise
        overlay = _read(tmp / "propfirm_overlay_search_latest.json")
        slices = _read(tmp / "edge_slices_latest.json")
        assert overlay["ok"] is False and "boom" in overlay["error"], \
            "overlay failure should be recorded, not raised: %r" % overlay
        assert slices["ok"] is False and "boom" in slices["error"], \
            "edge slices failure should be recorded, not raised: %r" % slices
        print("ok   a raising research script is caught by both hooks -- "
              "logged as ok:false, never raised")

        print("\nPASS: all nightly robustness-recheck wiring checks held.")
    finally:
        nightly_loop.LOGS = orig_logs
        nightly_loop.ROBUSTNESS_RECHECK_WEEKDAY = orig_weekday
        nightly_loop._run_research_script = orig_runner


if __name__ == "__main__":
    main()
