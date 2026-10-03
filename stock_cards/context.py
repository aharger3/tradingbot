"""Per-symbol context the engine needs before the open: prior-day range, hourly closes for the HTF bias.

Source order for each prior session: the Polygon archive (read only), then Alpaca IEX history (cached to DATA_DIR).
Nothing here reads a bar from the day being scanned.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import polygon_feed as pf
from backtest_12mo import hourly_from_1m
from backtest_week import htf_bias_for
from omen_bot import Candle

from . import alpaca_bars
from .config import ARCHIVE, DATA_DIR, ET

PRIOR_SESSIONS = 5           # >=3 are needed for 20 hourly closes; 5 leaves room for a holiday
LOOKBACK_DAYS = 12


@dataclass
class Context:
    pdh: float | None = None
    pdl: float | None = None
    pdo: float | None = None
    pdc: float | None = None
    bias: str | None = None
    prev_day: str | None = None
    prev_rth: list = field(default_factory=list)      # kept for the QQQ key-level break calculation
    sources: dict = field(default_factory=dict)       # {day: 'archive' | 'alpaca'}


def weekdays_before(day: str, n_calendar: int = LOOKBACK_DAYS) -> list[str]:
    d0 = date.fromisoformat(day)
    out = []
    for k in range(1, n_calendar + 1):
        d = d0 - timedelta(days=k)
        if d.weekday() < 5:
            out.append(d.isoformat())
    return out                                       # newest first


def _cache_path(data_dir: Path, sym: str, day: str) -> Path:
    return data_dir / "cache" / sym / f"{day}.json"


def _alpaca_day(syms: list[str], day: str, *, fetch=alpaca_bars.fetch_bars, data_dir: Path = DATA_DIR) -> dict[str, list[Candle]]:
    """One multi-symbol request for a whole prior day (04:00-20:00 ET), cached per symbol."""
    start = datetime.fromisoformat(day + "T04:00:00").replace(tzinfo=ET)
    end = datetime.fromisoformat(day + "T20:00:00").replace(tzinfo=ET)
    need, out = [], {}
    for s in syms:
        cp = _cache_path(data_dir, s, day)
        if cp.exists():
            out[s] = alpaca_bars.to_candles(json.loads(cp.read_text(encoding="utf-8")))
        else:
            need.append(s)
    if need:
        raw = fetch(need, start, end)
        for s in need:
            rows = raw.get(s) or []
            cp = _cache_path(data_dir, s, day)
            cp.parent.mkdir(parents=True, exist_ok=True)
            cp.write_text(json.dumps(rows), encoding="utf-8")
            out[s] = alpaca_bars.to_candles(rows)
    return out


def load_prior(syms: list[str], day: str, *, archive: Path = ARCHIVE, fetch=alpaca_bars.fetch_bars,
               data_dir: Path = DATA_DIR) -> dict[str, dict[str, tuple[list, str]]]:
    """{sym: {prior_day: (all_candles, source)}} for the last PRIOR_SESSIONS real sessions before `day`."""
    got: dict[str, dict[str, tuple[list, str]]] = {s: {} for s in syms}
    for pd_ in weekdays_before(day):
        if all(len(got[s]) >= PRIOR_SESSIONS for s in syms):
            break
        missing = []
        for s in syms:
            if len(got[s]) >= PRIOR_SESSIONS:
                continue
            fp = archive / s / f"{pd_}.csv"
            c = pf._read_csv(fp) if fp.exists() else []
            if len(pf.rth(c)) >= 30:
                got[s][pd_] = (c, "archive")
            else:
                missing.append(s)
        if missing:
            alp = _alpaca_day(missing, pd_, fetch=fetch, data_dir=data_dir)
            for s in missing:
                c = alp.get(s) or []
                if len(pf.rth(c)) >= 30:
                    got[s][pd_] = (c, "alpaca")
    return got


def build_context(prior: dict[str, tuple[list, str]]) -> Context:
    """prior = {day: (all_candles, source)} for one symbol."""
    ctx = Context()
    days = sorted(prior)
    if not days:
        return ctx
    hourly = []
    for d in days:
        hourly += hourly_from_1m(d, pf.rth(prior[d][0]))
        ctx.sources[d] = prior[d][1]
    last = days[-1]
    prth = pf.rth(prior[last][0])
    ctx.prev_day, ctx.prev_rth = last, prth
    ctx.pdh, ctx.pdl = max(c.high for c in prth), min(c.low for c in prth)
    ctx.pdo, ctx.pdc = prth[0].open, prth[-1].close
    ctx.bias = htf_bias_for(hourly, "9999-12-31")      # every supplied close is from a prior session
    return ctx


def qqq_breaks(qqq_today: list[Candle], qqq_ctx: Context, pmh: float | None, pml: float | None) -> dict | None:
    """Same rule as backtest_12mo.qqq_level_breaks, on the bars seen so far: first RTH close above QQQ PDH/PMH
    ('up') and below PDL/PML ('dn'). A break that has not happened yet is None, which is what is known at the time."""
    if qqq_ctx.pdh is None:
        return None
    rth = pf.rth(qqq_today)
    ups = [x for x in (qqq_ctx.pdh, pmh) if x is not None]
    dns = [x for x in (qqq_ctx.pdl, pml) if x is not None]
    return {"up": next((c.timestamp for c in rth if any(c.close > l for l in ups)), None),
            "dn": next((c.timestamp for c in rth if any(c.close < l for l in dns)), None)}
