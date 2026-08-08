"""T6 harness: run t4_engine_recall.py twice over austin_marks_v2.jsonl --
once with signal_runner.DETECT_WIDE OFF (shipped default, the baseline arm) and
once ON, flipping the module global at runtime exactly as the dry-run in
signal_runner.main flips BNR_DISPLACEMENT_GATE (sys.modules copy, not a fresh
`import`, so the toggle lands on the live module _retest_tol reads).

Patches t4's OUT_* output paths per arm so the OFF/ON reports and dumps land in
research/recall_off.* / recall_on.* and never overwrite each other or the 3.6
artifacts. Captures each arm's console summary to recall_<arm>_console.log so
the raw/fired signal counts (the mechanism check) are on the page beside the md.

Does NOT run backtest_12mo.py. P&L is not this version's question.
"""
from __future__ import annotations
import os, sys, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import signal_runner        # live module object — _retest_tol reads its globals
import t4_engine_recall as t4

assert signal_runner.DETECT_WIDE is False, "DETECT_WIDE must default to False"


def run_arm(arm: str, wide: bool):
    signal_runner.DETECT_WIDE = wide
    assert signal_runner._retest_tol() == (signal_runner.DETECT_WIDE_RETEST_MULT
                                           if wide else 0.0), \
        f"flag did not take effect for arm {arm} (wide={wide})"
    # per-arm output paths so arms never collide
    t4.OUT_MD = os.path.join(HERE, f"recall_{arm}.md")
    t4.OUT_SIGNALS = os.path.join(HERE, f"recall_{arm}_signals.jsonl")
    t4.OUT_ENTRIES = os.path.join(HERE, f"recall_{arm}_entries.jsonl")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        t4.main()
    signal_runner.DETECT_WIDE = False  # restore default between arms
    log = os.path.join(HERE, f"recall_{arm}_console.log")
    with open(log, "w") as f:
        f.write(f"DETECT_WIDE = {wide}\n_retest_tol() = {signal_runner.DETECT_WIDE_RETEST_MULT if wide else 0.0}\n\n")
        f.write(buf.getvalue())
    print(f"=== arm {arm} (DETECT_WIDE={wide}) -> {t4.OUT_MD} ===")
    print(buf.getvalue())


if __name__ == "__main__":
    run_arm("off", False)
    run_arm("on", True)
    signal_runner.DETECT_WIDE = False
    print("restored DETECT_WIDE =", signal_runner.DETECT_WIDE)
