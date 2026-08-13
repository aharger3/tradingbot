"""TEMP probe: count the same-bar collision types in the ladder-B path."""
import os, sys, json
from collections import Counter
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

from universe import ALL_SYMS
from t8_two_year import ARCHIVE, day_table, rth_candles, bias_from


def run_symbol(args):
    symbol, start_day, end_day = args
    import backtest_week as bw
    bw.STOP_ON_CLOSE, bw.LADDER_MODE, bw.PESSIMISTIC_FILL = True, "B", False
    C = Counter()
    orig = bw._ladder_bar

    def probe(t, c, i, open_trades, runner):
        long = t.direction == "call"
        touch = lambda lv: (c.high >= lv) if long else (c.low <= lv)
        beyond = lambda lv: (c.close <= lv) if long else (c.close >= lv)
        if not t.scaled:
            if touch(t.scale_level) and beyond(t.stop):
                C["rung1_scale_touch_and_close_beyond_stop"] += 1
        else:
            if touch(t.runner_target) and beyond(t.stop):
                C["rung2_target_touch_and_close_beyond_ORIG_stop"] += 1
                C["rung2_ORIGstop_status_%s_grade_%s" % (t.status, t.grade)] += 1
            if touch(t.runner_target) and beyond(t.entry):
                C["rung2_BEstop_status_%s_grade_%s" % (t.status, t.grade)] += 1
            if touch(t.runner_target) and beyond(t.entry):
                C["rung2_target_touch_and_close_beyond_BE_stop"] += 1
            if beyond(t.stop) and not touch(t.runner_target):
                C["rung2_close_beyond_ORIG_stop_no_target_touch"] += 1
        before = t.outcome
        orig(t, c, i, open_trades, runner)
        if t.outcome != before and t.outcome != "open":
            C["exit_" + t.outcome] += 1
            if t.scaled and beyond(t.stop):
                C["exit_after_scale_bar_closed_beyond_ORIG_stop_" + t.outcome] += 1
        return

    bw._ladder_bar = probe
    table = day_table(symbol); days = sorted(table)
    for i, day in enumerate(days):
        if day < start_day or day > end_day:
            continue
        candles = rth_candles(symbol, day)
        if not candles or len(candles) < 60:
            continue
        prev = days[i - 1] if i else None
        pdh = pdl = pdo = pdc = None
        if prev:
            pdh, pdl, pdo, pdc = table[prev][:4]
        pmh, pml = table[day][4], table[day][5]
        bias = bias_from([table[d][3] for d in days[max(0, i - 40):i]])
        trades = bw.simulate_day(symbol, day, candles, pdh, pdl, bias, pmh, pml, pdo, pdc, None)
        for t in trades:
            if t.counted:
                C["traded"] += 1
                C["traded_scaled"] += bool(t.scaled)
                C["traded_" + t.outcome] += 1
                if t.scaled and t.outcome == "win":
                    C["scaled_win"] += 1
                    b = candles[t.exit_idx]
                    long = t.direction == "call"
                    if (b.close <= t.stop) if long else (b.close >= t.stop):
                        C["scaled_win_exit_bar_closed_beyond_ORIG_stop"] += 1
    bw._ladder_bar = orig
    return symbol, dict(C)


if __name__ == "__main__":
    syms = [s for s in ALL_SYMS if os.path.isdir(os.path.join(ARCHIVE, s))]
    tot = Counter()
    with Pool(4) as p:
        for sym, c in p.imap_unordered(run_symbol, [(s, "2024-08-12", "2026-08-11") for s in syms]):
            tot.update(c)
    for k, v in sorted(tot.items()):
        print(f"{k}: {v}")
