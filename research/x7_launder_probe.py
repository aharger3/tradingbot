"""X7 -- does an untagged cap-to-C get laundered back to B by the first-of-day floor?

`signal_runner._calibration_grade` lifts a `C` to `B` when the signal is the
first with-trend signal of the day inside 90 minutes, guarded by a STRING test:

    sig["grade"] == "C" and "capped C" not in sig["reason"]

Four demotion sites write "capped C" into the reason (`_grade_for_levels`'
level-block, the counter-day-trend cap, S_GATE, RULE_710). Three do NOT:

    signal_runner.py  BNR_DISPLACEMENT_GATE   (both sides)
    signal_runner.py  PMH/PML alert-only cap  (both sides)
    signal_runner.py  order block `B -> C`    (both sides)

So a signal those three demoted is indistinguishable from a signal the grader
scored `C` on its own, and the floor lifts it straight back to `B` -- which is
tradeable. This probe counts how often that happens.

Method: subclass the SHIPPED router (`backtest_week.BacktestRunner`, which
delegates to `SignalRunner._route`), stash the base grade `_grade_trade`
returned, and record base -> grade-at-emit -> grade-after-route per signal.
Bars come from the archive via `research/t4_engine_recall.py`, the same reader
`build_deck` and `regression_gate` use. No file is written outside research/.

    python research/x7_launder_probe.py --days 40
"""
from __future__ import annotations
import argparse, json, os, random, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import t4_engine_recall as t4                      # noqa: E402
from backtest_week import BacktestRunner, DEDUPE_BARS, ENTRY_CUTOFF   # noqa: E402
from universe import BACKTEST_SYMBOLS              # noqa: E402


class ProbeRunner(BacktestRunner):
    def __init__(self, symbol):
        super().__init__(symbol)
        self._last_base = None
        self.probe = []

    def _grade_trade(self, *a, **k):
        g = super()._grade_trade(*a, **k)
        self._last_base = g.value
        return g

    def _emit(self, signals, sig):
        sig["_base"] = self._last_base
        sig["_at_emit"] = sig["grade"]
        super()._emit(signals, sig)
        self.probe.append({
            "base": sig["_base"], "at_emit": sig["_at_emit"],
            "final": sig["grade"], "status": sig.get("status"),
            "setup": sig["signal_type"].value,
            "level": sig.get("stop_level_name"),
            "floor": "[floor B" in sig.get("reason", ""),
            "tagged": "capped C" in sig.get("reason", ""),
            "nodisp": "[nodisp]" in sig.get("reason", ""),
        })


def run_day(symbol, day):
    candles = t4.rth_candles(symbol, day)
    if not candles:
        return []
    pdh, pdl, pdo, pdc = t4.prior_day_levels(symbol, day)
    pmh, pml = t4.premarket_extremes(symbol, day)
    r = ProbeRunner(symbol)
    r.pdh, r.pdl, r.pmh, r.pml = pdh, pdl, pmh, pml
    r.pd_open, r.pd_close = pdo, pdc
    r.htf_bias = t4.htf_bias(symbol, day)
    r.qqq_breaks = None
    for i in range(5, len(candles)):
        if ENTRY_CUTOFF and candles[i].timestamp >= ENTRY_CUTOFF:
            continue
        r.candles = candles[: i + 1]
        r.detect_signals()
    return r.probe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    random.seed(a.seed)
    pairs = []
    for sym in BACKTEST_SYMBOLS:
        d = os.path.join(t4.levels.ARCHIVE, sym)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith(".csv"):
                pairs.append((sym, f[:-4]))
    random.shuffle(pairs)
    rows, done = [], 0
    for sym, day in pairs:
        if done >= a.days:
            break
        got = run_day(sym, day)
        if got:
            rows += got
            done += 1
    c = Counter()
    for r in rows:
        c["signals"] += 1
        demoted_untagged = (r["base"] in ("A+", "A", "B")
                            and r["at_emit"] == "C" and not r["tagged"])
        if demoted_untagged:
            c["demoted_untagged"] += 1
            if r["floor"] and r["final"] == "B":
                c["laundered_to_B"] += 1
                if r["status"] == "fired":
                    c["laundered_and_fired"] += 1
        if r["floor"]:
            c["floor_lift"] += 1
        if r["status"] == "fired":
            c["fired"] += 1
    out = {"symbol_days": done, "counts": dict(c),
           "by_level_laundered": dict(Counter(
               r["level"] for r in rows
               if r["base"] in ("A+", "A", "B") and r["at_emit"] == "C"
               and not r["tagged"] and r["floor"] and r["final"] == "B"))}
    print(json.dumps(out, indent=2))
    with open(os.path.join(HERE, "_x7_launder.json"), "w") as f:
        json.dump({"meta": out, "rows": rows[:5000]}, f)


if __name__ == "__main__":
    main()
