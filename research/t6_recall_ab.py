"""T6 A/B harness: run t4_engine_recall.py twice over austin_marks_v2.jsonl
against the post-T1 archive, once with DETECT_WIDE OFF (shipped default, the
baseline arm) and once ON, flipping the module global at runtime the same way
signal_runner.py's dry-run flips BNR_DISPLACEMENT_GATE (set the module global
before the replay loop; _retest_tol() reads it live at each detect_signals
call, so no caching). Captures each arm's console summary + report to disk.
"""
from __future__ import annotations
import io, os, sys, contextlib, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import signal_runner  # the module, so we can flip its global
import t4_engine_recall as t4


def run_arm(wide: bool, md_name: str, sig_name: str, ent_name: str):
    signal_runner.DETECT_WIDE = wide
    t4.OUT_MD = os.path.join(HERE, md_name)
    t4.OUT_SIGNALS = os.path.join(HERE, sig_name)
    t4.OUT_ENTRIES = os.path.join(HERE, ent_name)
    buf = io.StringIO()
    t0 = time.time()
    with contextlib.redirect_stdout(buf):
        t4.main()
    elapsed = time.time() - t0
    return buf.getvalue(), elapsed


def main():
    signal_runner.DETECT_WIDE = False  # be explicit
    off_out, off_t = run_arm(False, "recall_off.md",
                             "engine_signals_off.jsonl", "engine_entries_off.jsonl")
    on_out, on_t = run_arm(True, "recall_on.md",
                           "engine_signals_on.jsonl", "engine_entries_on.jsonl")
    signal_runner.DETECT_WIDE = False  # restore shipped default

    with open(os.path.join(HERE, "recall_ab_console_off.txt"), "w") as f:
        f.write(off_out)
    with open(os.path.join(HERE, "recall_ab_console_on.txt"), "w") as f:
        f.write(on_out)

    print("=== OFF (DETECT_WIDE=False) ===")
    print(off_out)
    print(f"(elapsed {off_t:.1f}s)")
    print("=== ON (DETECT_WIDE=True) ===")
    print(on_out)
    print(f"(elapsed {on_t:.1f}s)")
    print(f"DETECT_WIDE restored to {signal_runner.DETECT_WIDE}")


if __name__ == "__main__":
    main()
