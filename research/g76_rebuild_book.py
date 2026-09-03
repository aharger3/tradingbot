"""G76 — rebuild the two-year book under one fill model.

Same replay as `backtest_2y.py` (same symbols, same 500 sessions, same archive,
same R31 loss halt) with ONE substitution: entries are priced by
`research/g76_rebuild_engine.simulate_day`, which chooses the fill BEFORE the
minimum-risk floor, the wide-stop gate, the 2R target and the R denominator.
So this is a rebuild — which trades fire changes, not only what they earn.

Output is deliberately slim (the fired / halted / unfilled rows only, no reason
prose): `backtest_2y.py`'s own output is 138 MB and seven of those is not a
sensible thing to leave on disk. Every field `research/g72_suppress_price.py`
prices a book on is present and means exactly what it means there.

Usage:
    python research/g76_rebuild_book.py --model close
    python research/g76_rebuild_book.py --model limit --out research/g76_book_limit.json
    python research/g76_rebuild_book.py --model head --days 730 --jobs 10
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

import loss_halt                                            # noqa: E402
import polygon_feed as pf                                   # noqa: E402
from backtest_week import htf_bias_for, RISK_DOLLARS        # noqa: E402
from backtest_12mo import hourly_from_1m, qqq_level_breaks  # noqa: E402
from universe import ALL_SYMS, has_archive                  # noqa: E402

from g76_rebuild_engine import FILL_MODELS, fill_model, simulate_day  # noqa: E402

S_RE = re.compile(r" S(\d+)")


def archive_days(sym):
    d = ROOT / "data_archive" / sym
    return sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []


def run_symbol(args):
    """One symbol, one model -> its rows. Runs in a worker process."""
    sym, model, start, qqq_brk = args
    rows = []
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

    prev = None
    with fill_model(model):
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
                                  qqq=qqq_brk.get(d), model=model)
            for t in trades:
                sm = S_RE.search(t.reason)
                rows.append({
                    "sym": sym, "day": d, "ym": d[:7],
                    "setup": t.signal_type, "dir": t.direction,
                    "setup_label": t.setup_type or t.signal_type,
                    "grade": t.grade, "status": t.status,
                    "sig_status": getattr(t, "sig_status", t.status),
                    "traded": bool(t.counted), "alert": bool(t.is_alert),
                    "et": t.entry_time[:5],
                    "sig_et": getattr(t, "signal_time", t.entry_time)[:5],
                    "sig_i": getattr(t, "signal_idx", t.entry_idx),
                    "entry_i": t.entry_idx,
                    "lag": t.entry_idx - getattr(t, "signal_idx", t.entry_idx),
                    "entry": round(t.entry, 2), "stop": round(t.stop, 2),
                    "target": round(t.target, 2), "exit": round(t.exit_price, 2),
                    "out": t.outcome, "pnl": t.pnl,
                    "r": round(t.pnl / RISK_DOLLARS, 3),
                    "bars": max(0, t.exit_idx - t.entry_idx),
                    "level_name": t.stop_level_name or "",
                    "s": int(sm.group(1)) if sm else -1,
                    "reason": "",
                })
            prev = d
    return sym, len(day_bars), rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True, choices=list(FILL_MODELS))
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--out", default=None)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--syms", default=None, help="comma list, for a smoke test")
    args = ap.parse_args()

    out_path = Path(args.out) if args.out else (
        ROOT / "research" / ("g76_book_%s.json" % args.model))

    syms = [s for s in ALL_SYMS if has_archive(s, 100)]
    if args.syms:
        want = {s.strip().upper() for s in args.syms.split(",")}
        syms = [s for s in syms if s in want]
    last = max((archive_days(s) or ["1970-01-01"])[-1] for s in syms)
    start = (date.fromisoformat(last) - timedelta(days=args.days)).isoformat()
    window = sorted({d for s in syms for d in archive_days(s) if d >= start})
    print("model=%s  %d symbols, %d sessions %s..%s"
          % (args.model, len(syms), len(window), window[0], window[-1]), flush=True)

    qqq_brk = qqq_level_breaks(window)
    print("QQQ key-level breaks on %d days" % len(qqq_brk), flush=True)

    jobs = [(s, args.model, start, qqq_brk) for s in syms]
    rows, sessions = [], set()
    if args.jobs > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            for sym, nd, rr in ex.map(run_symbol, jobs):
                rows += rr
                sessions |= {r["day"] for r in rr}
                print("[%s] %d sessions, %d signals" % (sym, nd, len(rr)), flush=True)
    else:
        for j in jobs:
            sym, nd, rr = run_symbol(j)
            rows += rr
            sessions |= {r["day"] for r in rr}
            print("[%s] %d sessions, %d signals" % (sym, nd, len(rr)), flush=True)
    sessions |= set(window)

    halted = loss_halt.apply_to_book(rows)
    print("R31 loss halt: %d trades blocked (%s)"
          % (halted, "ON" if loss_halt.LOSS_HALT else "OFF"), flush=True)

    hist = Counter(r["status"] for r in rows)
    keep = [r for r in rows if r["status"] in ("fired", "halted", "unfilled")]
    for r in keep:
        r.pop("reason", None)

    meta = {"generated": datetime.now().isoformat(timespec="seconds"),
            "model": args.model,
            "fill_bar_live": os.getenv("G76_FILL_BAR_LIVE", "0"),
            "first": min(sessions), "last": max(sessions),
            "sessions": len(sessions), "symbols": syms,
            "risk_dollars": RISK_DOLLARS, "signals": len(rows),
            "status_hist": dict(hist),
            "loss_halt": bool(loss_halt.LOSS_HALT), "halted": halted,
            "unfilled": hist.get("unfilled", 0),
            "traded": sum(1 for r in keep if r["traded"])}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"meta": meta, "trades": keep},
                                   separators=(",", ":")), encoding="utf-8")
    print("wrote %s (%.1f MB) — %d signals, %d kept, %d traded, %d unfilled, %d sessions"
          % (out_path, out_path.stat().st_size / 1e6, len(rows), len(keep),
             meta["traded"], meta["unfilled"], meta["sessions"]), flush=True)


if __name__ == "__main__":
    main()
