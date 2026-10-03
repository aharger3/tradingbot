"""How different is the IEX feed from the Polygon archive, as far as the engine is concerned?

Runs the same engine, with the same prior-day context, once on the day's Alpaca IEX bars and once on the archive's
Polygon (consolidated) bars, and compares the candidate sets by (symbol, signal minute, side). Needs the archive to
hold the day (OmenArchiveRetry fills it at 18:15 ET).

  python -m stock_cards.compare 2026-10-02
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import polygon_feed as pf

from . import alpaca_bars, detect, policy
from .config import ARCHIVE, DATA_DIR, ET, LOG_DIR, load_watchlist
from .run_day import build_contexts, make_log
from .session import ReplayFetcher
from . import context
from datetime import datetime


def _keys(cands: list[dict], only_window: bool = True, only_eligible: bool = False) -> set:
    out = set()
    for c in cands:
        if only_window and not policy.in_window(c["sig_t"]):
            continue
        if only_eligible and not policy.eligible(c):
            continue
        out.add(c["key"])
    return out


def _detect_day(syms, day, full, ctxs):
    qqq = None
    if "QQQ" in full and "QQQ" in ctxs:
        pmh, pml, _ = detect.split_session(full["QQQ"])
        qqq = context.qqq_breaks(full["QQQ"], ctxs["QQQ"], pmh, pml)
    out = []
    for s in syms:
        if full.get(s) and ctxs[s].pdh is not None:
            out += detect.detect_all(s, day, full[s], ctxs[s], qqq)
    return out


def compare(day: str, log=print) -> dict:
    syms = load_watchlist()
    start = datetime.fromisoformat(day + "T04:00:00").replace(tzinfo=ET)
    end = datetime.fromisoformat(day + "T11:05:00").replace(tzinfo=ET)
    raw = alpaca_bars.fetch_bars(syms, start, end)
    iex = {s: alpaca_bars.to_candles(raw.get(s) or []) for s in syms}
    arc, have = {}, 0
    for s in syms:
        fp = ARCHIVE / s / f"{day}.csv"
        arc[s] = [c for c in pf._read_csv(fp) if c.timestamp < "11:05:00"] if fp.exists() else []
        have += bool(arc[s])
    if not have:
        raise SystemExit(f"archive has no bars for {day}")
    ctxs = build_contexts(syms, day, DATA_DIR / "compare", log)
    ci, ca = _detect_day(syms, day, iex, ctxs), _detect_day(syms, day, arc, ctxs)
    res = {"day": day, "symbols": len(syms), "archive_symbols_present": have}
    bars = {s: (len(pf.rth([c for c in iex[s] if c.timestamp < "11:00:00"])), len(pf.rth([c for c in arc[s] if c.timestamp < "11:00:00"]))) for s in syms}
    res["rth_bars_to_11_iex_vs_archive_median"] = [sorted(v[0] for v in bars.values())[len(syms) // 2],
                                                    sorted(v[1] for v in bars.values())[len(syms) // 2]]
    for label, ew in (("all_window", False), ("eligible_window", True)):
        a, b = _keys(ca, True, ew), _keys(ci, True, ew)
        res[label] = {"archive": len(a), "iex": len(b), "both": len(a & b), "archive_only": len(a - b), "iex_only": len(b - a),
                      "overlap_of_archive": round(len(a & b) / len(a), 3) if a else None}
    return res


if __name__ == "__main__":
    day = sys.argv[1]
    log = make_log(LOG_DIR / f"compare-{day}.log")
    r = compare(day, log)
    out = DATA_DIR / "compare" / f"feed-vs-archive-{day}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(r, indent=1), encoding="utf-8")
    log(json.dumps(r))
