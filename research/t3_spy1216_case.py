"""T3 - the SPY 2024-12-16 case Austin flagged himself: "10:07 84 percent
happens btw" (research/marks/probe_master_2026-08-29.jsonl, card_id
SPY_2024-12-16).

Arms the session via the REAL backtest_week._arm_84 codepath, off the
engine's own candidate original entry (B&R above PMH $606.39, stop $606.38,
taken 10:05 — the engine's own numbers, printed by this script's --show-day
mode), at the exact bar it actually loses: the 10:06 wick to $606.275, which
trips the -1R disaster stop on TOUCH (R1/R2; the level stop's own CLOSE never
breaches $606.38 in this window — see the printed bars). This is exactly what
_arm_84 would do if that original setup cleared its price-action grade; it
doesn't today (X, weak retest PA -- T13/R19 territory, not this track, and
confirmed unaffected by BNR_DISPLACEMENT_GATE), so the full pipeline books
zero fires on this day regardless of the reclaim rule. This script isolates
the reclaim clause from that upstream gate to test it directly.

Usage:
    python research/t3_spy1216_case.py             # runs both arms, RULE84_SOURCE=0 and =1
    python research/t3_spy1216_case.py --show-day   # prints the engine's own signals that day
"""
from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import polygon_feed as pf                                        # noqa: E402
from backtest_week import BacktestRunner, SimTrade, simulate_day, htf_bias_for  # noqa: E402
from backtest_12mo import hourly_from_1m                         # noqa: E402

SYM, DAY, PREV_DAY = "SPY", "2024-12-16", "2024-12-13"


def show_day():
    bars = pf.fetch_day(SYM, DAY)
    rth = pf.rth(bars)
    pbars = pf.fetch_day(SYM, PREV_DAY)
    prth = pf.rth(pbars)
    pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
    pdo, pdc = prth[0].open, prth[-1].close
    pmh, pml = pf.premarket_hi_lo(bars)
    hourly = hourly_from_1m(DAY, rth)
    bias = htf_bias_for(hourly, DAY)
    trades = simulate_day(SYM, DAY, rth, pdh, pdl, bias, pmh, pml, pdo, pdc)
    print(f"{len(trades)} trades/signals on {SYM} {DAY}:")
    for t in trades:
        print(f"  {t.entry_time} {t.signal_type:24s} {t.direction:5s} grade={t.grade:3s} "
              f"status={t.status:8s} counted={t.counted} entry={t.entry:.2f} stop={t.stop:.2f} "
              f"out={t.outcome} reason={t.reason[:90]}")


def run_case(source_flag: str):
    os.environ["RULE84_SOURCE"] = source_flag
    for m in ("signal_runner", "backtest_week"):
        if m in sys.modules:
            del sys.modules[m]
    import importlib
    bw = importlib.import_module("backtest_week")

    bars = pf.fetch_day(SYM, DAY)
    rth = pf.rth(bars)
    pmh, pml = pf.premarket_hi_lo(bars)
    idx = {c.timestamp[:5]: i for i, c in enumerate(rth)}
    i_1005, i_1006 = idx["10:05"], idx["10:06"]
    c_1006 = rth[i_1006]

    runner = bw.BacktestRunner(SYM)
    runner.pdh = runner.pdl = runner.htf_bias = None
    runner.pmh, runner.pml = pmh, pml
    runner.candles = rth[:i_1005 + 1]

    # The engine's own real proposal at 10:05: B&R long above PMH $606.39,
    # entry 606.39, stop 606.38 (see show_day() output). Grade forced to a
    # real, counted trade here -- see the module docstring for why the
    # shipped grade (X) blocks this upstream of the reclaim rule entirely.
    t = bw.SimTrade(symbol=SYM, day=DAY, signal_type="break_and_retest", direction="call",
                    grade="B", status="fired", entry_time="10:05:00",
                    entry=606.39, stop=606.38, target=606.39 + 2 * (606.39 - 606.38),
                    reason="T3 fixture: the engine's own 10:05 B&R proposal",
                    entry_idx=i_1005, exit_idx=i_1005)
    assert t.counted

    t.outcome, t.exit_price, t.exit_idx = "loss", 606.38, i_1006
    bw._arm_84(t, runner, c_1006)

    fired = []
    for i in range(i_1006 + 1, len(rth)):
        if rth[i].timestamp[:5] > "10:30":
            break
        runner.candles = rth[:i + 1]
        before = len(runner.captured)
        runner.detect_signals()
        for sig in runner.captured[before:]:
            if sig["signal_type"].value == "reentry_84_rule":
                fired.append((rth[i].timestamp, sig))
    return fired


def main():
    if "--show-day" in sys.argv:
        show_day()
        return
    for flag, label in [("0", "shipped default (RULE84_SOURCE=0)"),
                        ("1", "T3 rewrite   (RULE84_SOURCE=1)")]:
        fired = run_case(flag)
        print(f"{label}: {len(fired)} REENTRY_84_RULE fire(s)")
        for ts, sig in fired:
            print(f"  {ts}  entry={sig['entry']:.2f} stop={sig['stop']:.2f} "
                  f"target={sig['target']:.2f} stop_level_name={sig['stop_level_name']!r}")
            print(f"    reason: {sig['reason']}")


if __name__ == "__main__":
    main()
