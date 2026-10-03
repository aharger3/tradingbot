"""Candidate detector: the S2 engine candidate at the decision bar.

The S2 fit tape (research/tape/baseline_2026-09-13.json.gz) was built by backtest_week.simulate_day over a whole
archived day. That function only ever looks at candles[:i+1] when it asks "is there a signal on bar i", so running it
on the bars seen so far and keeping the signals whose signal bar is the newest bar gives the same candidates a
bar-by-bar live scan would see. Checked on real data: current main reproduces the tape exactly (NVDA, 41 days,
420 of 420 candidates, 0 extra), and test_detect.py checks the truncated-run equivalence and that bars after the
decision bar cannot change a candidate.

Decision = the close of the signal bar. `sig_t` is the signal bar's START minute (the tape's `et`).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

import polygon_feed as pf
from backtest_week import simulate_day

from .config import ET

TAG_RE = re.compile(r"\[([a-z0-9]+)\]")             # same regex backtest_2y used to build the tape's `tags`


def candidate_dict(t, day: str) -> dict:
    """One SimTrade -> the fields the feed needs. `side` is L/S as in s_trades.csv; `stop` is the engine stop."""
    sig_t = t.entry_time[:5]
    close_ts = datetime.fromisoformat(f"{day}T{t.entry_time[:5]}:00").replace(tzinfo=ET) + timedelta(minutes=1)
    return {
        "sym": t.symbol, "day": day, "sig_t": sig_t, "side": "L" if t.direction == "call" else "S",
        "stop": round(float(t.stop), 2), "entry": round(float(t.entry), 2),
        "level": round(float(t.level_price or t.stop), 2), "level_name": (t.stop_level_name or "").strip(),
        "status": t.status, "setup": t.signal_type, "tags": TAG_RE.findall(t.reason or ""),
        "sig_close_ts": close_ts.isoformat(timespec="seconds"),
        "key": f"{t.symbol}|{day}|{sig_t}|{'L' if t.direction == 'call' else 'S'}",
    }


def split_session(candles: list):
    """-> (premarket_high, premarket_low, rth_candles). Premarket is everything before 09:30."""
    pmh, pml = pf.premarket_hi_lo(candles)
    return pmh, pml, pf.rth(candles)


def detect_all(sym: str, day: str, candles: list, ctx, qqq: dict | None) -> list[dict]:
    """Every engine candidate on the bars given (premarket + RTH so far). Cheap: ~0.05 s for a full day."""
    pmh, pml, rth = split_session(candles)
    if len(rth) < 6:
        return []
    trades = simulate_day(sym, day, rth, ctx.pdh, ctx.pdl, ctx.bias, pmh, pml, ctx.pdo, ctx.pdc, qqq=qqq)
    return [candidate_dict(t, day) for t in trades]


def detect_at(sym: str, day: str, candles: list, ctx, qqq: dict | None) -> list[dict]:
    """Candidates whose signal bar is the newest RTH bar (the decision bar that just closed)."""
    rth = pf.rth(candles)
    if not rth:
        return []
    last = rth[-1].timestamp[:5]
    return [c for c in detect_all(sym, day, candles, ctx, qqq) if c["sig_t"] == last]
