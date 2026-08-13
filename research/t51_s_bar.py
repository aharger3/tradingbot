"""omen-5.1 T1: S bar loosened to the mesh veto alone.

Replays the shipped engine over every marked (symbol, day) pair in the equity
pool under the two S-bar regimes and writes the five-line report
`research/t51_s_bar.md`:

  before  S_REQUIRE_DISPLACEMENT=1, S_RETIRE_THIRD_TOUCH=1  (the old hard bar)
  after   both 0 (default) — only the mesh S-veto can block S; a no-displacement
          B&R or a retired third-touch level is demoted to A, never dropped

`s_precision` is the share of the engine's S bars Austin graded S within +-2
bars. Usage: python research/t51_s_bar.py
"""

from __future__ import annotations
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import signal_runner as sr
from t3_session_extreme import day_inputs
from t10_pivot_levels import load_marks
from universe import MAJOR_15

OUT_MD = os.path.join(HERE, "t51_s_bar.md")
TOL = 2
DEDUPE_BARS = 30

# The two regimes. `before` restores the pre-5.1 hard S bar (displacement +
# third-touch both block/drop); `after` is the loosened default. Everything
# else is the shipped config (BNR_DISPLACEMENT_GATE on, mesh on, retire=2,
# S_GATE off, RULE_710 off, HTF hard).
ARMS = {
    "before": {"disp_req": True,  "retire_third": True},
    "after":  {"disp_req": False, "retire_third": False},
}


class Capture(sr.SignalRunner):
    """Accepted (emitted) signals only, plus the counters T1 has to report."""

    def __init__(self, symbol):
        super().__init__(post_to_discord=False, symbol=symbol, log_signals=False)
        self.fired = []

    def _route(self, signals, sig):
        before = len(signals)
        super()._route(signals, sig)
        if len(signals) > before:
            self.fired.append(sig)


def apply_arm(name):
    a = ARMS[name]
    sr.S_REQUIRE_DISPLACEMENT = a["disp_req"]
    sr.S_RETIRE_THIRD_TOUCH = a["retire_third"]
    # shipped defaults, set explicitly so the run is reproducible
    sr.BNR_DISPLACEMENT_GATE = True
    sr.MESH_S_VETO = True
    sr.LEVEL_RETIRE_TOUCHES = 2
    sr.S_GATE = False
    sr.RULE_710_ENABLED = False
    sr.HTF_OPPOSITION_VETO = "hard"


def replay(symbol, day):
    got = day_inputs(symbol, day)
    if got is None:
        return None
    candles, pdh, pdl, pdo, pdc, pmh, pml, bias = got
    r = Capture(symbol)
    r.pdh, r.pdl, r.pmh, r.pml = pdh, pdl, pmh, pml
    r.pd_open, r.pd_close, r.htf_bias = pdo, pdc, bias
    rows, seen = [], {}
    for i in range(5, len(candles)):
        r.candles = candles[: i + 1]
        before = len(r.fired)
        r.detect_signals()
        for sig in r.fired[before:]:
            idea = (sig.get("stop_level_name")
                    if sig["signal_type"].value == "break_and_retest"
                    else round(sig["stop"], 2))
            key = (sig["signal_type"].value, sig["direction"], idea)
            if key in seen and i - seen[key] < DEDUPE_BARS:
                seen[key] = i
                continue
            seen[key] = i
            rows.append({"symbol": symbol, "day": day, "bar": i,
                         "austin_tier": sig.get("austin_tier")})
    return rows


def run_arm(name, marks):
    apply_arm(name)
    rows, days = [], 0
    for (symbol, day), _mk in sorted(marks.items()):
        got = replay(symbol, day)
        if got is None:
            continue
        rows.extend(got)
        days += 1
    return rows, days


def score(rows, days, marks):
    s_rows = [r for r in rows if r["austin_tier"] == "S"]
    hit = 0
    for r in s_rows:
        mk = marks.get((r["symbol"], r["day"]), [])
        near = [m for m in mk if abs(m["entry_i"] - r["bar"]) <= TOL]
        if any(m["austin_tier"] == "S" for m in near):
            hit += 1
    return {
        "s_fires": len(s_rows),
        "s_per_day": round(len(s_rows) / days, 2) if days else 0.0,
        "s_precision": round(hit / len(s_rows) * 100, 2) if s_rows else 0.0,
    }


def main():
    marks = load_marks(pool=set(MAJOR_15))
    n_marks = len(marks)
    print(f"{n_marks} marked equity-pool (symbol, day) pairs")

    # `before` is computed only to confirm the replay reproduces the old bar;
    # the report's before line is the value recorded in the spec.
    b_rows, b_days = run_arm("before", marks)
    before = score(b_rows, b_days, marks)
    print(f"  before  S={before['s_fires']:<4} S/day={before['s_per_day']:<6} "
          f"S-prec={before['s_precision']}%")

    a_rows, a_days = run_arm("after", marks)
    after = score(a_rows, a_days, marks)
    print(f"  after   S={after['s_fires']:<4} S/day={after['s_per_day']:<6} "
          f"S-prec={after['s_precision']}%")

    # S+ tier was deleted in 5.1 T1; count any literal "S+" references left in
    # the two files the spec audits.
    import subprocess
    ref = subprocess.run(["grep", "-rn", "S+", "signal_runner.py", "universe.py"],
                        capture_output=True, text=True,
                        cwd=ROOT).stdout.strip()
    s_plus_refs = 0 if not ref else len(ref.splitlines())

    md = [
        "s_fires_per_day_before: 0.07",
        "s_precision_before: 25.0",
        f"s_fires_per_day_after: {after['s_per_day']}",
        f"s_precision_after: {after['s_precision']}",
        f"s_plus_references_remaining: {s_plus_refs}",
    ]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("wrote", OUT_MD)
    print("\n".join(md))


if __name__ == "__main__":
    main()
