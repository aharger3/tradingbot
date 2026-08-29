"""T4 -- index parity (R7, spec omen-7.1).

R7: "Should be firing more..." -- indices (QQQ/SPY/IWM) trade 18 of 1,017 in the
pre-T0 book. Two questions, in order:

  1. WHERE is the index signal actually lost -- gate rejection stage by stage,
     vs equities, on the ratified (post-T0) engine. Don't assume it's the
     minimum-stop gates.
  2. If it IS the min-stop gates (research/t51_index_funnel.md found the
     B&R_MIN_RISK price-scaled floor benches 93-98% of index D-grades), scale
     the floor to the symbol's own prior-20-session range instead of a flat
     % of price, and measure index trades / mean R / month-greenness before
     vs after -- and confirm equities aren't flooded with tiny-stop trades.

This script does (2): the A/B. (1) is answered by re-running
research/t51_index_funnel.py against the current (ratified) engine -- see
research/t4_index_parity.md for that re-run's numbers; this script does not
duplicate its instrumentation.

Usage:
  python research/t4_index_parity.py --arm off --out research/t4_arm_off.json
  python research/t4_index_parity.py --arm on  --out research/t4_arm_on.json

The ON arm sets ENABLE_ATR_SCALED_MIN_RISK=1 in-process (before importing
signal_runner, so the flag read at import time is live) and, for every
symbol/day, passes `min_risk_dollars = MIN_RISK_ATR_MULT * prior_20_session_
avg_daily_range` into simulate_day. The OFF arm passes nothing and leaves the
flag off -- byte-identical to the committed engine's default path.
"""
import argparse, json, os, sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

# backtest_week imports yfinance at top level; the archive replay never calls
# fetch_week, so a bare stub satisfies the import (same trick t51 uses).
import types as _types
if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = _types.ModuleType("yfinance")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arm", choices=["off", "on"], required=True)
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mult", type=float, default=None,
                    help="override MIN_RISK_ATR_MULT for calibration sweeps")
    ap.add_argument("--pools", default="all", choices=["all", "index_equity"],
                    help="index_equity restricts the run to INDEX_POOL + "
                         "MAJOR_15 -- OTHER_POOL never lands in the 'index' or "
                         "'equity' aggregation bucket (pool_for()), so this "
                         "only cuts runtime, not what gets measured")
    ap.add_argument("--index-only", action="store_true",
                    help="only prime min_risk_dollars for INDEX_POOL symbols -- "
                         "equities always pass None, so their gate is untouched "
                         "regardless of the flag/mult")
    args = ap.parse_args()

    if args.arm == "on":
        os.environ["ENABLE_ATR_SCALED_MIN_RISK"] = "1"

    import polygon_feed as pf
    from backtest_week import simulate_day, htf_bias_for, RISK_DOLLARS
    from backtest_12mo import hourly_from_1m, qqq_level_breaks
    import signal_runner as sr
    from universe import (ALL_SYMS, INDEX_POOL, MAJOR_15, pool_for, has_archive,
                          MIN_SAMPLE_N)

    mult = args.mult if args.mult is not None else sr.MIN_RISK_ATR_MULT
    print("arm=%s ENABLE_ATR_SCALED_MIN_RISK=%s mult=%.4f pools=%s"
          % (args.arm, sr.ENABLE_ATR_SCALED_MIN_RISK, mult, args.pools))

    def archive_days(sym):
        d = Path(ROOT) / "data_archive" / sym
        return sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []

    pool_syms = ALL_SYMS if args.pools == "all" else (INDEX_POOL + MAJOR_15)
    syms = [s for s in pool_syms if has_archive(s, 100)]
    last = max((archive_days(s) or ["1970-01-01"])[-1] for s in syms)
    start = (date.fromisoformat(last) - timedelta(days=args.days)).isoformat()
    window = sorted({d for s in syms for d in archive_days(s) if d >= start})
    print("%d symbols, %d sessions %s..%s" % (len(syms), len(window), window[0], window[-1]))

    qqq_brk = qqq_level_breaks(window)

    rows = []
    for sym in syms:
        days = [d for d in archive_days(sym) if d >= start]
        day_bars, hourly = {}, []
        rth_of = {}
        for d in days:
            try:
                bars = pf.fetch_day(sym, d)
            except Exception:
                continue
            if not bars:
                continue
            r = pf.rth(bars)
            if len(r) < 30:
                continue
            day_bars[d] = (bars, r)
            rth_of[d] = r
            hourly += hourly_from_1m(d, r)

        sorted_days = sorted(day_bars)
        # prior-20-session avg daily range (high-low over RTH), strictly
        # trailing -- day d's floor never sees day d's own range.
        daily_range = {d: max(c.high for c in rth_of[d]) - min(c.low for c in rth_of[d])
                       for d in sorted_days}
        prior20 = {}
        window_ranges = []
        for d in sorted_days:
            prior20[d] = (sum(window_ranges[-20:]) / len(window_ranges[-20:])
                          if window_ranges else None)
            window_ranges.append(daily_range[d])

        prev = None
        for d in sorted_days:
            bars, rth = day_bars[d]
            if prev:
                _, prth = day_bars[prev]
                pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
                pdo, pdc = prth[0].open, prth[-1].close
            else:
                pdh = pdl = pdo = pdc = None
            pmh, pml = pf.premarket_hi_lo(bars)
            bias = htf_bias_for(hourly, d)
            eligible = (not args.index_only) or (sym in INDEX_POOL)
            mrd = (mult * prior20[d]) if (args.arm == "on" and prior20[d] and eligible) else None
            trades = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml, pdo, pdc,
                                  qqq=qqq_brk.get(d), min_risk_dollars=mrd)
            for t in trades:
                if t.status != "fired" or t.grade == "C":
                    continue  # not counted -- same definition as t8_two_year/bt2y
                risk = abs(t.entry - t.stop)
                rows.append({
                    "sym": sym, "pool": pool_for(sym), "day": d, "ym": d[:7],
                    "r": round(t.pnl / RISK_DOLLARS, 4),
                    "win": t.pnl > 0,
                    "stop_pct": round(risk / t.entry * 100, 3) if t.entry else 0.0,
                    "grade": t.grade,
                })
            prev = d

    # ---- aggregate ----
    def summarize(rowset):
        n = len(rowset)
        if n == 0:
            return {"n": 0, "mean_r": None, "win_rate": None}
        mean_r = sum(r["r"] for r in rowset) / n
        win_rate = sum(1 for r in rowset if r["win"]) / n * 100
        months = defaultdict(float)
        for r in rowset:
            months[r["ym"]] += r["r"]
        green = sum(1 for v in months.values() if v > 0)
        return {"n": n, "mean_r": round(mean_r, 4), "win_rate": round(win_rate, 2),
                "months_total": len(months), "months_green": green,
                "median_stop_pct": (sorted(r["stop_pct"] for r in rowset)[n // 2]),
                "pct_stop_under_015": round(
                    100 * sum(1 for r in rowset if r["stop_pct"] < 0.15) / n, 2)}

    by_pool = defaultdict(list)
    for r in rows:
        by_pool[r["pool"]].append(r)
    by_sym = defaultdict(list)
    for r in rows:
        by_sym[r["sym"]].append(r)

    out = {
        "arm": args.arm,
        "mult": mult,
        "total_traded": len(rows),
        "by_pool": {p: summarize(rs) for p, rs in by_pool.items()},
        "by_symbol_index": {s: summarize(rs) for s, rs in by_sym.items() if s in INDEX_POOL},
        "equity_stop_under_015_pct": summarize(by_pool.get("equity", [])).get(
            "pct_stop_under_015"),
    }
    outp = Path(ROOT) / args.out
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out["by_pool"], indent=1))
    print("wrote", outp)


if __name__ == "__main__":
    main()
