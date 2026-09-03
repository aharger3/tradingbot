"""G76 — the two-year book rebuilt at fills that were actually obtainable.

WHY THIS FILE EXISTS
--------------------
`signal_runner.fill_price` (line 1330) books the entry at

    return min(max(level, candle.low), candle.high)

whenever the signal bar's close sits inside BAR_EXTREME_FRAC of the bar's own
extreme in the trade direction. `level` is the broken level being retested, and
the detector only fires when the bar CLOSED THROUGH it — so on a long,
`level < close`, and the booked fill is strictly BELOW the last price of the
minute. The close is by definition the minute's last trade, therefore any trade
at the booked price happened STRICTLY BEFORE the signal existed. Only an order
already resting at the level gets it. 83% of the two-year book fills this way.

`research/g76_rebuild_lookahead.py` proves that on the book itself, with a
worked example.

WHAT THIS FILE IS
-----------------
`simulate_day` is copied — deliberately, once — out of `backtest_week.py` so
that shipped code is not touched, and every RULE it calls (`_ladder_bar`,
`_arm_84`, `_stop_hit`, `_disaster_hit`, `_stop_fill_px`, `_entry_scratch`,
`SimTrade`, `BacktestRunner`, `dedupe_window`) is imported from the shipped
module rather than re-typed. Only two things are added:

 1. a FILL MODEL, patched into `signal_runner.fill_price` for the duration of
    the run (every one of the nine entry-fill call sites in the detectors goes
    through that one function, including `order_fill`, which calls it);
 2. a PENDING-FILL queue, so a trade whose order fills later than the signal
    bar enters the book at the bar it filled on — and a resting order that is
    never touched enters no book at all.

Because the fill price is chosen BEFORE the minimum-risk floor, the wide-stop
gate, the 2R target and the R denominator, this is a REBUILD and not a
re-pricing: it changes which trades fire, not only what they earn.

`g76_parity_check()` runs the copy in `head` mode against the shipped
`backtest_week.simulate_day` and asserts trade-for-trade identity. Run it before
believing anything else in this module.

THE MODELS
----------
  head       the book as published — `fill_price` untouched. Reference only.
  close      the signal minute's CLOSE. What a bot watching bar closes gets.
  next_open  the NEXT minute's OPEN. What a bot reacting to the close gets.
  late1/2/5  the open one, two, five minutes after that. A human tapping.
  limit      a resting limit AT THE LEVEL, filled only if price trades through
             it on a bar STRICTLY AFTER the signal. No later trade, no fill.

Management convention, uniform across models: the bar you were FILLED on is
never a management bar; the trade is live from the next bar. That is exactly
`backtest_week`'s own convention for a close-fill, applied to every model so the
comparison is like-for-like. `G76_FILL_BAR_LIVE=1` flips it for the limit model
(the rest of the fill minute is live) as a sensitivity — the two bracket the
truth for that model.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backtest_week as bw
import signal_runner as sr
from omen_bot import Candle

FILL_MODELS = ("head", "close", "next_open", "late1", "late2", "late5", "limit")

# minutes of delay past the signal bar, for the open-fill models
_OPEN_DELAY = {"next_open": 0, "late1": 1, "late2": 2, "late5": 5}

# Sensitivity switch for the limit model only: is the rest of the fill minute
# live? See the module docstring.
FILL_BAR_LIVE = os.getenv("G76_FILL_BAR_LIVE", "0").strip().lower() not in (
    "0", "false", "off", "no", "")

# ---------------------------------------------------------------- fill model

_CTX = {"model": "head", "candles": None, "i": 0, "cutoff_i": 0}
_ORIG_FILL_PRICE = sr.fill_price


def _model_fill(level, candle, is_long, session_hi=None, session_lo=None):
    """Replacement for `signal_runner.fill_price`. Same signature, same callers.

    Returns the price the entry books UNDER THE ACTIVE MODEL. For `limit` this
    is the resting order's price — the level itself — and WHEN (or whether) it
    fills is resolved by `_resolve_fill` once the signal has been emitted, which
    is the only place the future bars are visible.
    """
    m = _CTX["model"]
    if m == "head":
        return _ORIG_FILL_PRICE(level, candle, is_long, session_hi, session_lo)
    if candle is None:
        return level
    if level is None:
        return candle.close
    if m == "close":
        return candle.close
    if m == "limit":
        return level
    cs, j = _CTX["candles"], _CTX["i"] + 1 + _OPEN_DELAY[m]
    if j < len(cs):
        return cs[j].open
    return candle.close          # no bar left to fill on; _resolve_fill drops it


def _resolve_fill(entry: float, i: int, is_long: bool, candles, cutoff_i: int):
    """(fill_bar_index, fill_price) for a signal emitted on bar `i`, or None.

    `head` / `close`  — the signal bar itself; the price is already the close.
    open models       — the open of bar i+1+delay.
    `limit`           — a resting order at `entry`. It fills on the FIRST bar
                        strictly after `i` that trades through the price, at the
                        price, or better if that bar opened straight past it.
                        Rests until the entry cutoff and is then cancelled.
    """
    m = _CTX["model"]
    if m in ("head", "close"):
        return i, entry
    if m in _OPEN_DELAY:
        j = i + 1 + _OPEN_DELAY[m]
        return (j, candles[j].open) if j < len(candles) else None
    # limit
    last = min(cutoff_i, len(candles) - 1)
    # The order rests BELOW the market on a long (the retested level is under
    # the close that confirmed it) — a buy limit. The `else` branch is a
    # buy-stop above the market and cannot arise for break-and-retest, the one
    # candle rule or the 84% re-entry, all three of which require the bar to
    # close through the level; it is here so an FVG/flag row can never be
    # silently mispriced.
    below = (entry <= candles[i].close) if is_long else (entry >= candles[i].close)
    for j in range(i + 1, last + 1):
        c = candles[j]
        if is_long:
            hit = (c.low <= entry) if below else (c.high >= entry)
            if hit:
                return j, (min(entry, c.open) if below else max(entry, c.open))
        else:
            hit = (c.high >= entry) if below else (c.low <= entry)
            if hit:
                return j, (max(entry, c.open) if below else min(entry, c.open))
    return None


def _manage_from(fill_i: int) -> int:
    """First bar on which the filled trade is managed."""
    m = _CTX["model"]
    if m == "limit" and FILL_BAR_LIVE:
        return fill_i          # the rest of the fill minute is live
    return fill_i + 1          # the fill bar is never a management bar


# --------------------------------------------------------------- simulate_day
#
# Copied from backtest_week.simulate_day (2026-08-29, commit a0997963) with two
# additions, both marked `# G76`. Everything else is byte-for-byte the shipped
# loop; `g76_parity_check` proves it.

def simulate_day(symbol: str, day_iso: str, candles: List[Candle],
                 pdh: Optional[float], pdl: Optional[float], bias: Optional[str],
                 pmh: Optional[float] = None, pml: Optional[float] = None,
                 pdo: Optional[float] = None, pdc: Optional[float] = None,
                 qqq: Optional[dict] = None,
                 min_risk_dollars: Optional[float] = None,
                 model: str = "head") -> List[bw.SimTrade]:
    if model not in FILL_MODELS:
        raise ValueError("unknown fill model %r" % model)

    runner = bw.BacktestRunner(symbol)
    runner.pdh, runner.pdl, runner.htf_bias = pdh, pdl, bias
    runner.pmh, runner.pml = pmh, pml
    runner.pd_open, runner.pd_close = pdo, pdc
    runner.qqq_breaks = qqq
    runner.min_risk_dollars = min_risk_dollars

    trades: List[bw.SimTrade] = []
    open_trades: List[bw.SimTrade] = []
    seen = {}
    pending = defaultdict(list)          # G76: bar index -> trades that go live

    # G76: the last bar a resting order may fill on — the entry cutoff.
    cutoff_i = len(candles) - 1
    if bw.ENTRY_CUTOFF:
        for k, c in enumerate(candles):
            if c.timestamp >= bw.ENTRY_CUTOFF:
                cutoff_i = k
                break
    _CTX.update(model=model, candles=candles, i=0, cutoff_i=cutoff_i)

    for i in range(5, len(candles)):
        c = candles[i]
        _CTX["i"] = i

        # 1. update open sim positions against this bar
        for t in list(open_trades):
            if i == t.entry_idx + 1:
                px = bw._entry_scratch(t, c)
                if px is not None:
                    t.outcome, t.exit_price, t.exit_idx = "scratch", px, i
                    open_trades.remove(t)
                    continue
            if bw.SCALE_PLAN:
                bw._ladder_bar(t, c, i, open_trades, runner)
                continue
            if bw.RULE6_ENABLED and not t.be_taken and t.be_level > 0:
                if (t.direction == "call" and c.high >= t.be_level) or \
                   (t.direction == "put" and c.low <= t.be_level):
                    t.be_taken = True
                    t.runner_stop = t.entry
            lv = t.runner_stop if t.be_taken else t.stop
            dz = None if t.be_taken else bw._disaster_hit(t, c, t.direction == "call")
            stopped = bw._stop_hit(c, lv, t.direction == "call")
            targeted = c.high >= t.target if t.direction == "call" else c.low <= t.target
            if dz is not None:
                t.outcome, t.exit_price, t.exit_idx = "loss", dz, i
                open_trades.remove(t)
                bw._arm_84(t, runner, c)
                continue
            if stopped:
                t.outcome, t.exit_price, t.exit_idx = (
                    "loss", bw._stop_fill_px(t, c, t.direction == "call"), i)
                open_trades.remove(t)
                bw._arm_84(t, runner, c)
            elif targeted:
                t.outcome, t.exit_price, t.exit_idx = "win", t.target, i
                open_trades.remove(t)

        # 2. detect signals as of this bar
        if bw.ENTRY_CUTOFF and c.timestamp >= bw.ENTRY_CUTOFF:
            open_trades.extend(pending.pop(i, []))       # G76
            continue
        runner.candles = candles[:i + 1]
        before = len(runner.captured)
        runner.detect_signals()

        for sig in runner.captured[before:]:
            idea = (sig.get("stop_level_name")
                    if sig["signal_type"].value == "break_and_retest"
                    else round(sig["stop"], 2))
            key = (sig["signal_type"].value, sig["direction"], idea)
            claims = sig.get("status") == "fired" or not bw.DEDUPE_FIRES_ONLY
            if key in seen and i - seen[key] < bw.dedupe_window():
                if claims:
                    seen[key] = i
                continue
            if claims:
                seen[key] = i
            risk = abs(sig["entry"] - sig["stop"])
            target = sig.get("target") or (
                sig["entry"] + 2 * risk if sig["direction"] == "call" else sig["entry"] - 2 * risk)
            if bw.RULE6_ENABLED and risk > 0:
                if sig["direction"] == "call":
                    be_level = sig["entry"] + bw.RULE6_BE_MULT * risk
                else:
                    be_level = sig["entry"] - bw.RULE6_BE_MULT * risk
            else:
                be_level = 0.0
            scale_level = runner_tgt = 0.0
            if bw.SCALE_PLAN and risk > 0:
                if sig["direction"] == "call":
                    scale_level = max(cd.high for cd in candles[:i + 1])
                    cands = [x for x in (pdh, pmh) if x is not None and x > scale_level]
                    cands.append(bw.math.floor(scale_level) + 1.0)
                    runner_tgt = min(cands)
                else:
                    scale_level = min(cd.low for cd in candles[:i + 1])
                    cands = [x for x in (pdl, pml) if x is not None and x < scale_level]
                    cands.append(bw.math.ceil(scale_level) - 1.0)
                    runner_tgt = max(cands)

            _setup_type = sig.get("setup_type", sig["signal_type"])
            t = bw.SimTrade(symbol=symbol, day=day_iso,
                            signal_type=sig["signal_type"].value,
                            direction=sig["direction"], grade=sig["grade"],
                            status=sig["status"], entry_time=c.timestamp,
                            entry=sig["entry"], stop=sig["stop"], target=target,
                            reason=sig["reason"], entry_idx=i,
                            exit_idx=len(candles) - 1,
                            be_level=be_level, scale_level=scale_level,
                            runner_target=runner_tgt,
                            setup_type=getattr(_setup_type, "value", _setup_type),
                            stop_level_name=sig.get("stop_level_name") or "")
            trades.append(t)
            # G76: where the order actually filled, and when. A signal the
            # router already rejected (`risk <= 0`, or a skipped status) never
            # had an order in the market, so it is not asked to fill — exactly
            # as the shipped loop only appends the ones with risk.
            t.fill_idx = i
            t.signal_idx = i
            t.signal_time = c.timestamp
            if risk > 0:
                t.level_price = sig.get("level_price")
                if t.level_price is None:
                    t.level_price = sig["stop"]
                fill = _resolve_fill(t.entry, i, t.direction == "call",
                                     candles, cutoff_i)
                if fill is None:
                    # the resting order was never touched — no trade happened
                    t.sig_status, t.status = t.status, "unfilled"
                    t.outcome = "unfilled"
                    t.exit_price = t.entry
                    continue
                j, px = fill
                t.fill_idx = j
                if px != t.entry:
                    # a gap through the resting order pays better than the
                    # order's own price; the stop, target and 2R geometry were
                    # set when the bracket was placed and do not move
                    t.entry = px
                t.entry_idx = j
                t.entry_time = candles[j].timestamp
                pending[_manage_from(j) - 1].append(t)

        open_trades.extend(pending.pop(i, []))           # G76

    for t in open_trades:
        t.outcome, t.exit_price = "scratch", candles[-1].close
    return trades


# ------------------------------------------------------------------- context

class fill_model:
    """`with fill_model("close"): ...` — patches signal_runner.fill_price."""

    def __init__(self, model: str):
        if model not in FILL_MODELS:
            raise ValueError("unknown fill model %r" % model)
        self.model = model

    def __enter__(self):
        sr.fill_price = _model_fill
        _CTX["model"] = self.model
        return self

    def __exit__(self, *exc):
        sr.fill_price = _ORIG_FILL_PRICE
        _CTX["model"] = "head"
        return False


# -------------------------------------------------------------- parity check

def _key(t):
    return (t.day, t.entry_time, t.signal_type, t.direction, t.grade, t.status,
            round(t.entry, 4), round(t.stop, 4), round(t.target, 4),
            t.outcome, round(t.exit_price, 4), t.exit_idx, round(t.pnl, 2))


def g76_parity_check(n_days: int = 40, verbose: bool = True) -> bool:
    """Run the copy in `head` mode against the shipped simulate_day.

    Identical trade lists, or this module is not trustworthy and nothing else
    in G76 should be read.
    """
    import polygon_feed as pf
    from backtest_12mo import hourly_from_1m
    from universe import ALL_SYMS, has_archive
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    syms = [s for s in ALL_SYMS if has_archive(s, 100)][:4]
    bad = 0
    for sym in syms:
        days = sorted(f.stem for f in (root / "data_archive" / sym).glob("*.csv"))
        days = days[-n_days:]
        hourly, day_bars = [], {}
        for d in days:
            bars = pf.fetch_day(sym, d)
            if not bars:
                continue
            r = pf.rth(bars)
            if len(r) < 30:
                continue
            day_bars[d] = (bars, r)
            hourly += hourly_from_1m(d, r)
        prev = None
        for d in sorted(day_bars):
            bars, rth = day_bars[d]
            if prev:
                _, prth = day_bars[prev]
                pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
                pdo, pdc = prth[0].open, prth[-1].close
            else:
                pdh = pdl = pdo = pdc = None
            pmh, pml = pf.premarket_hi_lo(bars)
            bias = bw.htf_bias_for(hourly, d)
            a = bw.simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml, pdo, pdc)
            with fill_model("head"):
                b = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml, pdo, pdc,
                                 model="head")
            ka, kb = [_key(t) for t in a], [_key(t) for t in b]
            if ka != kb:
                bad += 1
                if verbose:
                    print("MISMATCH %s %s: %d vs %d rows" % (sym, d, len(ka), len(kb)))
                    for x, y in zip(ka, kb):
                        if x != y:
                            print("   shipped %s\n   g76     %s" % (x, y))
                            break
            prev = d
    if verbose:
        print("parity: %d mismatched sessions across %d symbols" % (bad, len(syms)))
    return bad == 0


if __name__ == "__main__":
    import sys
    ok = g76_parity_check()
    print("PARITY", "OK" if ok else "FAILED")
    sys.exit(0 if ok else 1)
