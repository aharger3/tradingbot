"""w12_reach.py -- W12: empirical branch reachability over the 2-year book.

WHY THIS EXISTS
---------------
This repo has a documented, repeating bug class: *a real rule that became a
branch which can never be true*. Confirmed instances so far -- `before11` in
the 84%-rule block (kills 0 of 318 dead armings, and cannot kill any), the 84%
re-entry rule (3 fires in two years), `break_then_rejection` (never trips).
Every one of them was found by hand, one at a time, after the rule had already
been believed for months.

Reading the code is how they got missed. So this file does not read anything:
it runs the SHIPPED rig -- `backtest_2y.py`, 28 symbols x ~500 sessions, the
same replay `research/g3_arm_ow1.json` came out of -- under `coverage.py` with
branch measurement on, and reports, for the grade-and-gate path only:

  * every LINE that never executed in 45k signals              (dead by data)
  * every BRANCH ARC that was never taken                      (a condition
    that never evaluated True, or never evaluated False)

A branch arc that is missing after two years of tape is the signature. It does
not by itself prove the branch is dead *by construction* -- that is the second
question, and it is answered by reading the code at the line this file names.
The point is that this file produces the CANDIDATE LIST without anyone having
to guess which rule to be suspicious of.

SCOPE
-----
The grade and gate path, per the W12 brief:

    signal_runner.py        grading, skip logic, the two minimum-risk floors
    omen_bot.py             grade_trade / _grade_pa and the HTF veto
    research/downgrade.py   the eight downgrade variables
    backtest_week.py        the grade-consuming logic

Exit policy is NOT in scope (`research/exit_lab.py` was swept by W2/W9).

WHAT THE ARMS ARE
-----------------
One arm, shipped defaults. Every flag in the file ships OFF except
`HTF_BIAS_VETO` (which ships ON -- see W12 finding 4), so "never executed"
under shipped defaults includes the OFF-flag bodies. Those are reported
separately, in `flagged_off`, and are NOT findings: a flag body that does not
run when its flag is off is the flag working.

USAGE
-----
    python research/w12_reach.py run           # ~40 min, writes _w12/cov.json
    python research/w12_reach.py report        # read the json, print the table

The file hashes of all four in-scope modules are recorded in the output. If a
concurrent agent edits one mid-run the line numbers in this report are void and
`report` says so.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "_w12", "cov.json")

SCOPE = ["signal_runner.py", "omen_bot.py", "backtest_week.py",
         os.path.join("research", "downgrade.py")]

# Flags that ship OFF. A line inside one of these blocks being unexecuted is
# the flag being off, not a dead rule. Matched textually against the source
# line and the enclosing `if` so the report can bucket them out.
OFF_FLAGS = [
    "ENABLE_SAC_LADDER", "SAC_LADDER_REGRADE_ALL", "S_GATE", "RULE_710_ENABLED",
    "BNR_DISPLACEMENT_GATE", "HTF_BIAS_GATE", "CONFLUENCE_SETUP_ROUTES",
    "ENABLE_STRUCTURAL_RISK_FLOOR", "ENABLE_DOWNGRADE_GRADER", "ON_WATCH",
    "TRADE_RETIRED_SETUPS", "AUSTIN_TIER_ENABLED", "PIVOT_LEVELS",
    "LEVEL_RETIRE_TOUCHES", "TRADE_S_ONLY", "SCRATCH_", "OMEN_",
]


def hashes() -> dict:
    out = {}
    for rel in SCOPE:
        p = os.path.join(ROOT, rel)
        with open(p, "rb") as fh:
            out[rel.replace("\\", "/")] = hashlib.sha256(fh.read()).hexdigest()
    return out


def run(days: int) -> int:
    """Replay under coverage in a CHILD process.

    `backtest_2y.py` is invoked as-is, not reimplemented: the whole point is
    which lines the SHIPPED rig executes, and a private replay loop would be a
    different rig wearing its name. Output goes to a scratch path -- never over
    `research/bt2y_trades.json`, the canonical book."""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pre = hashes()
    data = os.path.join(ROOT, "research", "_w12", ".coverage")
    trades = os.path.join("research", "_w12", "w12_trades.json")
    env = dict(os.environ, COVERAGE_FILE=data)
    incl = ",".join(os.path.join(ROOT, p) for p in SCOPE)
    cmd = [sys.executable, "-m", "coverage", "run", "--branch",
           "--include=" + incl,
           os.path.join(ROOT, "backtest_2y.py"),
           "--days", str(days), "--out", trades]
    print(" ".join(cmd[:6]) + " ...")
    rc = subprocess.call(cmd, cwd=ROOT, env=env)
    if rc:
        return rc

    import coverage
    cov = coverage.Coverage(data_file=data, branch=True)
    cov.load()
    res = {"days": days, "pre_hashes": pre, "post_hashes": hashes(),
           "files": {}}
    for rel in SCOPE:
        p = os.path.join(ROOT, rel)
        _, stmts, excl, missing, _ = cov.analysis2(p)
        arcs = cov.get_data().arcs(p) or []
        anl = cov._analyze(p)
        part = sorted(anl.missing_branch_arcs().items())
        src = open(p, encoding="utf-8").read().splitlines()
        res["files"][rel.replace("\\", "/")] = {
            "n_stmts": len(stmts),
            "missing_lines": sorted(missing),
            "missing_line_src": {str(n): src[n - 1].strip()
                                 for n in sorted(missing) if n <= len(src)},
            "partial_branches": [
                {"line": ln, "src": src[ln - 1].strip() if ln <= len(src) else "",
                 "never_taken_to": sorted(dests)}
                for ln, dests in part],
            "n_arcs": len(arcs),
        }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    print("wrote %s" % OUT)
    return 0


def _off_flag(text: str) -> bool:
    return any(f in text for f in OFF_FLAGS)


def report() -> int:
    with open(OUT, encoding="utf-8") as fh:
        res = json.load(fh)
    if res["pre_hashes"] != res["post_hashes"]:
        print("!! a scoped file CHANGED during the run -- line numbers are void")
        for k in res["pre_hashes"]:
            if res["pre_hashes"][k] != res["post_hashes"][k]:
                print("   changed: %s" % k)
    print("2-year replay, shipped defaults, %d days\n" % res["days"])
    for rel, f in res["files"].items():
        dead = [(n, s) for n, s in f["missing_line_src"].items()
                if not _off_flag(s)]
        print("%-24s %4d stmts  %3d never ran  %3d partial branches"
              % (rel, f["n_stmts"], len(f["missing_lines"]),
                 len(f["partial_branches"])))
        for ln, dests in [(b["line"], b["never_taken_to"])
                          for b in f["partial_branches"]]:
            src = next((b["src"] for b in f["partial_branches"]
                        if b["line"] == ln), "")
            if _off_flag(src):
                continue
            print("   L%-5s partial -> %s   %s" % (ln, dests, src[:88]))
        for n, s in dead[:400]:
            print("   L%-5s dead      %s" % (n, s[:96]))
        print()
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["run", "report"])
    ap.add_argument("--days", type=int, default=730)
    a = ap.parse_args()
    sys.exit(run(a.days) if a.cmd == "run" else report())


if __name__ == "__main__":
    main()
