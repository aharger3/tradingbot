"""24-month archive replay -> one flat per-trade JSON for the interactive report.

Same engine as backtest_12mo.py (backtest_week.simulate_day, cache-first
polygon_feed = data_archive on disk), only the window is 2 years and the output
is a row per signal with every slicing dimension attached, so the HTML report
can filter without re-running anything.

Usage:  python backtest_2y.py [--days 730] [--out research/bt2y_trades.json]
"""
import argparse, json, re, statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import polygon_feed as pf
from backtest_week import simulate_day, htf_bias_for, RISK_DOLLARS
from backtest_12mo import hourly_from_1m, qqq_level_breaks
from universe import (ALL_SYMS, INDEX_POOL, CORE_SYMBOLS, EXPERIMENTAL_SYMBOLS,
                      pool_for, has_archive)

ROOT = Path(__file__).parent
ETFS = set(INDEX_POOL)                       # the only ETFs in the archive
TAG_RE = re.compile(r"\[([a-z0-9]+)\]")
S_RE = re.compile(r" S(\d+)")
LEVEL_RE = re.compile(r"(?:above|below) (PDH|PDL|PMH|PML|OR high|OR low|pivot high|pivot low)")


def archive_days(sym):
    d = ROOT / "data_archive" / sym
    return sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []


def daily_ohlc(sym):
    """day -> (open, close, high, low) from the archived RTH bars."""
    out = {}
    for d in archive_days(sym):
        try:
            rth = pf.rth(pf.fetch_day(sym, d))
        except Exception:
            continue
        if len(rth) < 30:
            continue
        out[d] = (rth[0].open, rth[-1].close,
                  max(c.high for c in rth), min(c.low for c in rth))
    return out


def spy_context():
    """day -> {spy_trend, spy_ret, vol_regime} from SPY's own archive."""
    spy = daily_ohlc("SPY")
    keys = sorted(spy)
    closes = [spy[k][1] for k in keys]
    ctx, rets = {}, []
    for i, k in enumerate(keys):
        prev = closes[i - 1] if i else closes[i]
        rets.append((closes[i] - prev) / prev * 100 if prev else 0.0)
        sma = statistics.fmean(closes[max(0, i - 19):i + 1])
        vol = statistics.pstdev(rets[max(0, i - 19):i + 1]) if i >= 5 else 0.0
        ctx[k] = {"spy_trend": "bull" if closes[i] >= sma else "bear",
                  "spy_ret": round(rets[i], 2), "_vol": vol}
    vols = sorted(v["_vol"] for v in ctx.values() if v["_vol"])
    lo = vols[len(vols) // 3] if vols else 0
    hi = vols[2 * len(vols) // 3] if vols else 0
    for v in ctx.values():
        v["vol_regime"] = ("calm" if v["_vol"] <= lo else
                           "normal" if v["_vol"] <= hi else "wild")
        v.pop("_vol")
    return ctx


def bucket(x, edges, names):
    for e, n in zip(edges, names):
        if x <= e:
            return n
    return names[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--out", default="research/bt2y_trades.json")
    args = ap.parse_args()

    syms = [s for s in ALL_SYMS if has_archive(s, 100)]
    last = max((archive_days(s) or ["1970-01-01"])[-1] for s in syms)
    start = (date.fromisoformat(last) - timedelta(days=args.days)).isoformat()
    window = sorted({d for s in syms for d in archive_days(s) if d >= start})
    print("%d symbols, %d sessions %s..%s" % (len(syms), len(window), window[0], window[-1]))

    ctx = spy_context()
    qqq_brk = qqq_level_breaks(window)
    print("QQQ key-level breaks on %d days" % len(qqq_brk))

    rows, sessions = [], set()
    for sym in syms:
        days = [d for d in archive_days(sym) if d >= start]
        day_bars, hourly = {}, []
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
            hourly += hourly_from_1m(d, r)

        n0, prev = len(rows), None
        for d in sorted(day_bars):
            bars, rth = day_bars[d]
            if prev:
                _, prth = day_bars[prev]
                pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
                pdo, pdc = prth[0].open, prth[-1].close
            else:
                pdh = pdl = pdo = pdc = None
            pmh, pml = pf.premarket_hi_lo(bars)
            bias = htf_bias_for(hourly, d)
            trades = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml, pdo, pdc,
                                  qqq=qqq_brk.get(d))
            sessions.add(d)

            dopen, dclose = rth[0].open, rth[-1].close
            dhi, dlo = max(c.high for c in rth), min(c.low for c in rth)
            gap = (dopen - pdc) / pdc * 100 if pdc else 0.0
            drange = (dhi - dlo) / dopen * 100 if dopen else 0.0
            dret = (dclose - dopen) / dopen * 100 if dopen else 0.0
            cx = ctx.get(d, {})
            dow = datetime.fromisoformat(d).strftime("%a")
            seq = defaultdict(int)

            for t in trades:
                risk = abs(t.entry - t.stop)
                lv = LEVEL_RE.search(t.reason)
                sm = S_RE.search(t.reason)
                stop_pct = risk / t.entry * 100 if t.entry else 0.0
                key = "fired" if t.status == "fired" else "skip"
                seq[key] += 1
                rows.append({
                    "sym": sym,
                    "cls": "etf" if sym in ETFS else "stock",
                    "pool": pool_for(sym),
                    "tier": ("core" if sym in CORE_SYMBOLS else
                             "experimental" if sym in EXPERIMENTAL_SYMBOLS else "other"),
                    "day": d, "ym": d[:7], "yr": d[:4], "dow": dow,
                    "setup": t.signal_type, "dir": t.direction,
                    "grade": t.grade, "status": t.status,
                    "traded": bool(t.counted), "alert": bool(t.is_alert),
                    "et": t.entry_time[:5],
                    "slot": t.entry_time[:2] + (":00" if t.entry_time[3:5] < "30" else ":30"),
                    "entry": round(t.entry, 2), "stop": round(t.stop, 2),
                    "target": round(t.target, 2), "exit": round(t.exit_price, 2),
                    "out": t.outcome, "pnl": t.pnl, "r": round(t.pnl / RISK_DOLLARS, 3),
                    "bars": max(0, t.exit_idx - t.entry_idx),
                    "stop_pct": round(stop_pct, 3),
                    "stopb": bucket(stop_pct, [0.15, 0.35, 0.7],
                                    ["tight", "mid", "wide", "very wide"]),
                    "bias": bias or "none",
                    "aligned": ("n/a" if not bias else
                                "with" if (bias == "bull") == (t.direction == "call")
                                else "against"),
                    "level": lv.group(1) if lv else "other",
                    "s": int(sm.group(1)) if sm else -1,
                    "tags": TAG_RE.findall(t.reason),
                    "seq": seq[key],
                    "gap": round(gap, 2),
                    "gapb": bucket(abs(gap), [0.25, 1.0], ["flat", "small gap", "big gap"]),
                    "drange": round(drange, 2),
                    "rangeb": bucket(drange, [1.5, 3.0], ["quiet", "normal", "big range"]),
                    "dret": round(dret, 2),
                    "scaled": bool(t.scaled),
                    "spy_trend": cx.get("spy_trend", "n/a"),
                    "vol_regime": cx.get("vol_regime", "n/a"),
                    "reason": t.reason,
                })
            prev = d
        print("[%s] %d sessions, %d signals" % (sym, len(day_bars), len(rows) - n0))

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = {"generated": datetime.now().isoformat(timespec="seconds"),
            "first": min(sessions), "last": max(sessions),
            "sessions": len(sessions), "symbols": syms,
            "risk_dollars": RISK_DOLLARS, "signals": len(rows),
            "traded": sum(1 for r in rows if r["traded"])}
    out.write_text(json.dumps({"meta": meta, "trades": rows}, separators=(",", ":")),
                   encoding="utf-8")
    print("wrote %s (%.1f MB) — %d signals, %d traded, %d sessions"
          % (out, out.stat().st_size / 1e6, len(rows), meta["traded"], meta["sessions"]))


if __name__ == "__main__":
    main()
