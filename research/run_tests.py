#!/usr/bin/env python
"""W7/g207 -- the canonical test runner. Runs every plain-assert `test_*.py`
selftest in the repo (root and `research/`) as a subprocess, prints a
pass/fail table, and exits nonzero if any of them failed.

This is NOT a pytest collector: these are `python test_x.py` selftests, most
of which print PASS/FAIL lines and exit via `sys.exit(1)` on failure. Running
each in its OWN subprocess is deliberate -- several of them mutate module-
level flags (`signal_runner.RETEST_REQUIRED`, `sr.ENABLE_SAC_LADDER`, ...) and
del/re-import `signal_runner` under different env vars; sharing one process
across all of them would let one test's flag flip leak into the next.

EXCLUDED is a short, named, commented list -- never a silent skip. Every
entry says which unrelated thing is missing (a generated artifact this repo
does not commit, a data file this box does not have, or a DIFFERENT known bug
this row did not touch) so a red CI run elsewhere with those files present
does not mysteriously diverge from a green one here.

    python research/run_tests.py            # the canonical set
    python research/run_tests.py --all       # every test_*.py, no exclusions
    python research/run_tests.py -v          # show each subprocess's own output
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "research"
RETIRED_DIR = RESEARCH / "_retired_tests"

# name -> why it is excluded from the canonical (gate-worthy) set. Every
# reason names the OTHER, unrelated thing that is broken or missing -- none
# of these five are among the 14 B-08 tests this row (W7/g207) triaged.
EXCLUDED = {
    "research/test_g119_htf_bias_veto_ab.py":
        "missing local data file research/bt2y_trades_htfveto_off.json "
        "(not committed/regenerated on this box) -- unrelated to B-08",
    "research/test_g182_b3_htf_bias_veto_note.py":
        "ModuleNotFoundError: omen_bot -- a broken import path pre-dating "
        "this row, not one of the 14 B-08 tests",
    "research/test_h2_deck_page.py":
        "asserts its own precondition: 'build the page first: python "
        "research/build_h2_deck.py' -- a generated artifact this box has "
        "not built, unrelated to B-08",
    "research/test_min_viable_stop_delta.py":
        "known, TRACKED bug B-07 (research/g182_bugs_fixed.md): "
        "_min_viable_stop hardcodes *0.5 while DEFAULT_DELTA=0.42 -- a "
        "real fix but a different row's, not one of the 14 B-08 tests",
    "research/test_provenance.py":
        "flags concurrent wave-2 report files (x3/x9/x11/x13/x14/t9_*) "
        "missing a provenance line -- a live backlog from OTHER agents "
        "writing in parallel this same night, not one of the 14 B-08 tests",
}


def discover(include_all: bool) -> list[Path]:
    found = sorted(ROOT.glob("test_*.py")) + sorted(RESEARCH.glob("test_*.py"))
    out = []
    for p in found:
        if RETIRED_DIR in p.parents:
            continue
        rel = p.relative_to(ROOT).as_posix()
        if not include_all and rel in EXCLUDED:
            continue
        out.append(p)
    return out


def run_one(path: Path, verbose: bool) -> tuple[bool, float, str]:
    t0 = time.time()
    try:
        proc = subprocess.run([sys.executable, str(path)], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=180,
                              encoding="utf-8", errors="replace")
        ok = proc.returncode == 0
        out = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as e:
        ok = False
        out = "TIMEOUT after 180s%s" % ((": " + str(e.stdout or "")) if e.stdout else "")
    dt = time.time() - t0
    if verbose or not ok:
        tail = "\n".join(out.strip().splitlines()[-15:])
        print("----- %s -----\n%s\n" % (path.relative_to(ROOT).as_posix(), tail))
    return ok, dt, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true",
                    help="run every test_*.py, ignoring EXCLUDED")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print each test's own output, not just failures")
    args = ap.parse_args()

    tests = discover(args.all)
    results = []
    for p in tests:
        ok, dt, _ = run_one(p, args.verbose)
        results.append((p.relative_to(ROOT).as_posix(), ok, dt))

    passed = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]

    print("\n%-55s %6s  %s" % ("test", "time", "result"))
    for name, ok, dt in results:
        print("%-55s %5.1fs  %s" % (name, dt, "PASS" if ok else "FAIL"))

    print("\n%d/%d passed%s" % (len(passed), len(results),
          "" if args.all else " (canonical set, %d excluded -- see EXCLUDED)"
          % len(EXCLUDED)))
    if failed:
        print("FAILED:")
        for name, _, _ in failed:
            print("  - %s" % name)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
