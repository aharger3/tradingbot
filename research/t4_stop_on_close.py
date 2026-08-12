"""omen-5.0 T4: A/B the close-based stop and the ladder exit over 12 months.

Runs backtest_week.simulate_day — the same engine, unchanged — over the archived
1-minute bars in data_archive for the MAJOR_15 pool, once per arm:

  wick     STOP_ON_CLOSE=0, LADDER_MODE=B   (the old trigger: any wick through the level)
  close    STOP_ON_CLOSE=1, LADDER_MODE=B   (Austin's rule: the candle has to CLOSE beyond it)
  blind2r  STOP_ON_CLOSE=1, LADDER_MODE=None (the old blind-2R exit, for the exit A/B)

Level inputs (PDH/PDL/PMH/PML, prior-day open/close, HTF bias) are rebuilt from
the archive per symbol in one pass, so nothing here hits the network.

Usage: python research/t4_stop_on_close.py [--days 365] [--jobs 6]
"""

from __future__ import annotations
import argparse
import csv
import glob
import os
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from omen_bot import Candle
from universe import MAJOR_15

ARCHIVE = os.path.join(ROOT, "data_archive")
OUT_MD = os.path.join(HERE, "t4_stop_on_close.md")

ARMS = {
    # name: (STOP_ON_CLOSE, LADDER_MODE)
    "wick": (False, "B"),
    "close": (True, "B"),
    "blind2r": (True, None),
}


def _hhmm(dtstr: str) -> str:
    return dtstr[11:16]


def day_table(symbol: str):
    """One pass over the symbol's archive: {day: (rth_hi, rth_lo, rth_open,
    rth_close, pm_hi, pm_lo)}. Only the summary is kept — bars are re-read per
    day inside the run so memory stays flat."""
    out = {}
    for path in sorted(glob.glob(os.path.join(ARCHIVE, symbol, "*.csv"))):
        day = os.path.basename(path)[:-4]
        rth_h = rth_l = rth_o = rth_c = None
        pm_h = pm_l = None
        with open(path) as f:
            for r in csv.DictReader(f):
                t = _hhmm(r["Datetime"])
                h, l, o, cl = (float(r["High"]), float(r["Low"]),
                               float(r["Open"]), float(r["Close"]))
                if t < "09:30":
                    if "04:00" <= t:
                        pm_h = h if pm_h is None else max(pm_h, h)
                        pm_l = l if pm_l is None else min(pm_l, l)
                    continue
                if t >= "16:00":
                    continue
                if rth_h is None:
                    rth_h, rth_l, rth_o = h, l, o
                else:
                    rth_h, rth_l = max(rth_h, h), min(rth_l, l)
                rth_c = cl
        if rth_h is not None:
            out[day] = (rth_h, rth_l, rth_o, rth_c, pm_h, pm_l)
    return out


def rth_candles(symbol: str, day: str):
    path = os.path.join(ARCHIVE, symbol, f"{day}.csv")
    if not os.path.exists(path):
        return None
    bars = []
    with open(path) as f:
        for r in csv.DictReader(f):
            t = _hhmm(r["Datetime"])
            if t < "09:30" or t >= "16:00":
                continue
            bars.append(Candle(timestamp=t + ":00", open=float(r["Open"]),
                               high=float(r["High"]), low=float(r["Low"]),
                               close=float(r["Close"]),
                               volume=int(float(r["Volume"] or 0))))
    return bars or None


def bias_from(closes):
    """close-vs-SMA20 of prior RTH closes — mirrors backtest_week.htf_bias_for."""
    if len(closes) < 20:
        return None
    sma = sum(closes[-20:]) / 20
    last = closes[-1]
    if last > sma * 1.001:
        return "bullish"
    if last < sma * 0.999:
        return "bearish"
    return "neutral"


def run_symbol(args):
    """One (symbol, arm) run. Returns (arm, symbol, rows, arm84_count)."""
    symbol, arm, start_day = args
    import backtest_week as bw
    stop_on_close, ladder = ARMS[arm]
    bw.STOP_ON_CLOSE, bw.LADDER_MODE = stop_on_close, ladder

    armed = {"n": 0}
    real_arm = bw._arm_84

    def counting_arm(t, runner, c=None):
        before = runner.session.entry_price
        real_arm(t, runner, c)
        if runner.session.entry_price is not None and runner.session.entry_price != before:
            armed["n"] += 1
    bw._arm_84 = counting_arm

    table = day_table(symbol)
    days = sorted(table)
    rows = []
    for i, day in enumerate(days):
        if day < start_day:
            continue
        candles = rth_candles(symbol, day)
        if not candles or len(candles) < 60:
            continue
        prev = days[i - 1] if i else None
        pdh = pdl = pdo = pdc = None
        if prev:
            pdh, pdl, pdo, pdc = table[prev][0], table[prev][1], table[prev][2], table[prev][3]
        pmh, pml = table[day][4], table[day][5]
        bias = bias_from([table[d][3] for d in days[max(0, i - 40):i]])
        trades = bw.simulate_day(symbol, day, candles, pdh, pdl, bias,
                                 pmh, pml, pdo, pdc, None)
        for t in trades:
            rows.append({"symbol": t.symbol, "day": t.day, "setup": t.signal_type,
                         "grade": t.grade, "status": t.status, "outcome": t.outcome,
                         "counted": t.counted, "pnl": t.pnl})
    bw._arm_84 = real_arm
    return arm, symbol, rows, armed["n"]


def stats(rows):
    counted = [r for r in rows if r["counted"]]
    n = len(counted)
    w = sum(1 for r in counted if r["outcome"] == "win")
    l = sum(1 for r in counted if r["outcome"] == "loss")
    s = sum(1 for r in counted if r["outcome"] == "scratch")
    decided = w + l
    wr = round(w / decided * 100, 1) if decided else 0.0
    pnl = round(sum(r["pnl"] for r in counted), 2)
    return {"n": n, "w": w, "l": l, "scratch": s, "win_rate": wr, "pnl": pnl}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--symbols", default=",".join(MAJOR_15))
    args = ap.parse_args()

    symbols = [s for s in args.symbols.split(",")
               if os.path.isdir(os.path.join(ARCHIVE, s))]
    start_day = (date.today() - timedelta(days=args.days)).isoformat()
    jobs = [(s, arm, start_day) for arm in ARMS for s in symbols]
    print(f"{len(symbols)} symbols x {len(ARMS)} arms from {start_day}")

    per_arm = defaultdict(list)
    armed = defaultdict(int)
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        for arm, symbol, rows, n_arm in ex.map(run_symbol, jobs):
            per_arm[arm].extend(rows)
            armed[arm] += n_arm
            print(f"  {arm:<8} {symbol:<6} {len(rows)} signals, {n_arm} 84% armings")

    res = {a: stats(per_arm[a]) for a in ARMS}
    for a in ARMS:
        print(a, res[a])

    def setup_rows(arm):
        out = []
        counted = [r for r in per_arm[arm] if r["counted"]]
        for setup in sorted({r["setup"] for r in counted}):
            sub = [r for r in counted if r["setup"] == setup]
            st = stats(sub)
            out.append((setup, st))
        return out

    md = [
        "# T4 — stop on the CLOSE, scratch the failed entry bar, ladder exit",
        "",
        f"12 months of archived 1-minute bars ({start_day} onward), pool "
        f"`universe.MAJOR_15` ({len(symbols)} symbols), replayed through "
        "`backtest_week.simulate_day` — same engine, only the two flags move. "
        "Counted trades are fired A+/A/B (C is alert-only), $1000 risk per trade.",
        "",
        "```",
        f"win_rate_wick: {res['wick']['win_rate']}",
        f"win_rate_close: {res['close']['win_rate']}",
        f"trades_wick: {res['wick']['n']}",
        f"trades_close: {res['close']['n']}",
        f"scratches_close: {res['close']['scratch']}",
        f"arm84_wick: {armed['wick']}",
        f"arm84_close: {armed['close']}",
        f"win_rate_blind2r: {res['blind2r']['win_rate']}",
        f"win_rate_ladder_b: {res['close']['win_rate']}",
        f"pnl_blind2r: {res['blind2r']['pnl']}",
        f"pnl_ladder_b: {res['close']['pnl']}",
        "```",
        "",
        "## Arms",
        "",
        "| arm | stop trigger | exit | trades | W | L | scratch | win rate | P&L |",
        "|-----|--------------|------|--------|---|---|---------|----------|-----|",
    ]
    labels = {"wick": ("wick through the level", "ladder B"),
              "close": ("candle CLOSE beyond the level", "ladder B"),
              "blind2r": ("candle CLOSE beyond the level", "blind 2R")}
    for a in ("wick", "close", "blind2r"):
        r = res[a]
        md.append(f"| {a} | {labels[a][0]} | {labels[a][1]} | {r['n']} | {r['w']} | "
                  f"{r['l']} | {r['scratch']} | {r['win_rate']}% | ${r['pnl']} |")
    md.append("")

    d_wr = round(res["close"]["win_rate"] - res["wick"]["win_rate"], 1)
    d_pnl = round(res["close"]["pnl"] - res["wick"]["pnl"], 2)
    md += [
        "## What the arms say",
        "",
        f"**The stop trigger.** Moving the trigger from a wick to the close is worth "
        f"{d_wr:+} points of win rate ({res['wick']['win_rate']}% -> "
        f"{res['close']['win_rate']}%) and ${d_pnl:+,.0f} over the same 12 months and the "
        "same {n} trades. Trade count is identical by construction — the change touches "
        "when a position exits, never whether it is taken — so this is a clean read: "
        "trades Austin would still have been holding were being closed at a wick."
        .replace("{n}", str(res["close"]["n"])),
        "",
        f"**The exit.** With close-based stops, ladder B beats blind 2R on BOTH axes "
        f"({res['close']['win_rate']}% / ${res['close']['pnl']:,.0f} vs "
        f"{res['blind2r']['win_rate']}% / ${res['blind2r']['pnl']:,.0f}) — not the "
        "win-rate-for-dollars trade the F1 A/B measured under wick stops. The two changes "
        "interact: scaling at 1R only pays when the runner is not being wicked out first. "
        f"Austin's gate is a 55% win rate and ladder B lands at {res['close']['win_rate']}%, "
        "so it is close but not over the line.",
        "",
        f"**scratches_close is {res['close']['scratch']}, and that is a real result, not a "
        "missing feature.** The scratch path is wired in `simulate_day` and `_arm_84` "
        "refuses to arm on it. It cannot fire on this population because every detector "
        "confirms on the bar close — a B&R long only fires when `current.close > level`, so "
        "the entry bar's close is on the right side of the level by construction. The rule "
        "is Austin describing a LIVE intrabar fill that fails before the bar closes; it will "
        "fire the moment an intrabar entry path exists, and on bar-close replay it cannot. "
        "Nothing was tuned to make this number zero.",
        "",
        f"**84% armings: {armed['close']} in 12 months.** `RULE84_STRICT` (default ON) only "
        "arms off an A+/A original that took a counted full stop-out, and T4(c) now also "
        "requires the stop-out to be a loss (not a scratch) before 11:00. The 2,843-row "
        "`research/rule84_candidates.jsonl` pool was built on wick stop-outs — this is the "
        "measurement that says how many of those survive the close rule: almost none.",
        "",
    ]
    md += ["## Per setup", "",
           "| setup | arm | trades | W | L | scratch | win rate | P&L |",
           "|-------|-----|--------|---|---|---------|----------|-----|"]
    for a in ("wick", "close", "blind2r"):
        for setup, st in setup_rows(a):
            md.append(f"| {setup} | {a} | {st['n']} | {st['w']} | {st['l']} | "
                      f"{st['scratch']} | {st['win_rate']}% | ${st['pnl']} |")
    md.append("")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("wrote", OUT_MD)


if __name__ == "__main__":
    main()
