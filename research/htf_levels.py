"""research/htf_levels.py -- 1h/4h pivot structure + whole-dollar psych levels.

Standalone, new-file scope for the exit-ladder lane (THE LADDER, MASTER SPEC
sec 5.4, `LADDER_HTF_PIVOTS`). This module owns HTF *structure* only -- it
builds 1h/4h swing highs/lows from the 1-minute archive and hands back the
nearest one beyond a price. It is not imported by any engine file yet
(backtest_week.py, signal_runner.py, levels_ladder.py are all untouched);
a future ladder wiring pass is the one that will call `htf_level_beyond()`.

STRICT CAUSALITY, and how it is enforced here (not just claimed):

  `htf_candles()` only ever reads 1-minute bars whose (day, HH:MM:SS) sorts
  strictly before the caller's (upto_day, upto_time) cursor. Full prior
  sessions (day < upto_day) contribute every HTF bucket they hold; the
  cursor day itself contributes only the bars that precede `upto_time`.
  Pivot confirmation on top of that (`signal_runner.pivot_levels`, run with
  `as_of` pinned to the last causal HTF candle) additionally requires
  `PIVOT_STRENGTH` bars on BOTH sides before a swing is "confirmed" --
  so a swing still forming at the cursor is correctly withheld, not just
  a swing past the cursor.

  `demo()` does not take that on faith: it turns on `debug=True`, which
  makes `htf_candles()` also return the raw-bar provenance (day, ts) of
  every 1-minute bar that fed a bucket, and asserts every one of them sorts
  before the cursor. That is the literal "no returned level was derived
  from a future bar" proof, run against real archived data.

Usage (once the ladder wants a level):

    from research.htf_levels import htf_level_beyond
    lvl = htf_level_beyond("AAPL", "2024-06-10", "10:15:00", price=192.40,
                           direction="up")
    # -> {"price": 193.0, "name": "whole $1"} or a "1h pivot high @HH:MM" /
    #    "4h pivot low @HH:MM", whichever sorts nearer `price` in `direction`.
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from omen_bot import Candle
import polygon_feed as pf
from signal_runner import pivot_levels, PIVOT_STRENGTH

ARCHIVE = ROOT / "data_archive"
SESSION_START_MIN = 9 * 60 + 30           # 09:30, matches polygon_feed.rth()
HTF_TIMEFRAMES = {"1h": 60, "4h": 240}    # minutes per bucket
PSYCH_STEP = 1.00                          # whole-dollar default


# --------------------------------------------------------------- archive I/O

def _archive_days(symbol: str) -> list:
    d = ARCHIVE / symbol
    return sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []


def _rth_bars(symbol: str, day_iso: str) -> list:
    try:
        return pf.rth(pf.fetch_day(symbol, day_iso))
    except Exception:
        return []


# ----------------------------------------------------------- HTF bucketing

def _minute_of_day(ts: str) -> int:
    h, m, _s = ts.split(":")
    return int(h) * 60 + int(m)


def _bucketize(bars: list, minutes: int, day_iso: str):
    """Session-anchored `minutes`-wide OHLC buckets from one day's RTH bars.

    A day boundary always closes every bucket it holds (the next session
    starts a fresh index 0), so nothing here needs a "is this bucket full
    yet" check -- only the caller's (day, time) cursor decides what is
    causal, which is enforced in `htf_candles` before bars ever reach here.

    Returns (candles, provenance): provenance[i] is the list of (day_iso, ts)
    for every raw 1-minute bar folded into candles[i], kept only so `demo()`
    can prove causality against the real archive rather than the same code
    path that built the buckets.
    """
    buckets = {}   # idx -> [ts, open, high, low, close, volume]
    prov = {}      # idx -> [(day, ts), ...]
    order = []
    for c in bars:
        idx = (_minute_of_day(c.timestamp) - SESSION_START_MIN) // minutes
        if idx not in buckets:
            buckets[idx] = [c.timestamp, c.open, c.high, c.low, c.close, c.volume]
            prov[idx] = [(day_iso, c.timestamp)]
            order.append(idx)
        else:
            b = buckets[idx]
            b[2] = max(b[2], c.high)
            b[3] = min(b[3], c.low)
            b[4] = c.close
            b[5] += c.volume
            prov[idx].append((day_iso, c.timestamp))
    order.sort()
    candles = [Candle(timestamp=buckets[i][0], open=buckets[i][1], high=buckets[i][2],
                      low=buckets[i][3], close=buckets[i][4], volume=buckets[i][5])
              for i in order]
    provenance = [prov[i] for i in order]
    return candles, provenance


def htf_candles(symbol: str, upto_day: str, upto_time: str, timeframe_minutes: int,
                lookback_days: int = 30, debug: bool = False):
    """1h/4h-bucketed Candles built ONLY from bars strictly before
    (upto_day, upto_time). Days before `upto_day` contribute in full; `upto_day`
    itself contributes only bars with `timestamp < upto_time`.

    `lookback_days` caps how many prior *archived* sessions are pulled (not
    calendar days) -- keeps a single call cheap; raise it if a symbol needs
    deeper history for a 4h pivot to confirm.

    With `debug=True` returns (candles, provenance) -- see `_bucketize`.
    Callers that just want levels (the normal path) get `candles` alone.
    """
    days = [d for d in _archive_days(symbol) if d <= upto_day]
    if lookback_days:
        days = days[-lookback_days:]

    all_candles, all_prov = [], []
    for d in days:
        bars = _rth_bars(symbol, d)
        if d == upto_day:
            bars = [c for c in bars if c.timestamp < upto_time]
        if not bars:
            continue
        candles, prov = _bucketize(bars, timeframe_minutes, d)
        all_candles.extend(candles)
        all_prov.extend(prov)

    return (all_candles, all_prov) if debug else all_candles


# ---------------------------------------------------------------- pivots

def htf_pivots(symbol: str, upto_day: str, upto_time: str, timeframe_minutes: int,
              strength: int = None, lookback_days: int = 30) -> list:
    """Confirmed swing highs/lows on the `timeframe_minutes` HTF series, as of
    (upto_day, upto_time). Each: {"index","usable_from","price","kind","name"}
    (see `signal_runner.pivot_levels`) -- `usable_from` is left in place so a
    caller can double-check causality itself; it is always <= the last index
    of the causal series this function builds, by construction.
    """
    k = PIVOT_STRENGTH if strength is None else strength
    candles = htf_candles(symbol, upto_day, upto_time, timeframe_minutes, lookback_days)
    if len(candles) < 2 * k + 1:
        return []
    return pivot_levels(candles, strength=k, as_of=len(candles) - 1)


# ------------------------------------------------------------ psych levels

def nearest_whole_dollar(price: float, direction: str, step: float = PSYCH_STEP) -> float:
    """Nearest multiple of `step` strictly beyond `price` in `direction`
    ('up'/'down'). Needs no bars, no archive -- pure arithmetic, so it is
    always available even when `named_levels` and every HTF pivot are empty.
    """
    n = price / step
    k = math.floor(n) + 1 if direction == "up" else math.ceil(n) - 1
    return round(k * step, 2)


# ------------------------------------------------------- the one entry point

def htf_level_beyond(symbol: str, upto_day: str, upto_time: str, price: float,
                     direction: str, *, timeframes=("1h", "4h"), strength: int = None,
                     lookback_days: int = 30, include_psych: bool = True,
                     psych_step: float = PSYCH_STEP):
    """The nearest level strictly beyond `price` in `direction` ('up'/'down'),
    as of (upto_day, upto_time) -- across every requested HTF pivot timeframe
    plus the whole-dollar psych level. Causal: only pivots confirmable from
    bars strictly before the cursor are ever candidates.

    Returns {"price": float, "name": str} or None (no level exists that side --
    only possible when `include_psych=False` and no pivot qualifies).
    """
    if direction not in ("up", "down"):
        raise ValueError("direction must be 'up' or 'down'")

    candidates = []  # (price, name)
    for tf in timeframes:
        minutes = HTF_TIMEFRAMES[tf]
        for p in htf_pivots(symbol, upto_day, upto_time, minutes, strength, lookback_days):
            if direction == "up" and p["price"] > price:
                candidates.append((p["price"], f"{tf} {p['name']}"))
            elif direction == "down" and p["price"] < price:
                candidates.append((p["price"], f"{tf} {p['name']}"))

    if include_psych:
        wd = nearest_whole_dollar(price, direction, psych_step)
        candidates.append((wd, f"whole ${psych_step:g}"))

    if not candidates:
        return None
    best = min(candidates, key=lambda t: t[0]) if direction == "up" else \
           max(candidates, key=lambda t: t[0])
    return {"price": best[0], "name": best[1]}


# --------------------------------------------------------------------- demo

def _cursor_key(day_iso: str, ts: str) -> tuple:
    return (day_iso, ts)


def demo():
    """Self-check against real archived data. Proves, by direct provenance
    inspection (not by re-trusting the code that built the buckets):

      1. every raw 1-minute bar folded into an HTF candle sorts strictly
         before the (upto_day, upto_time) cursor;
      2. every pivot `htf_level_beyond` can return has `usable_from` at or
         before the last causal HTF candle -- i.e. pivot_levels' own
         no-lookahead gate is actually in effect on this series;
      3. moving the cursor earlier in the SAME session never adds a bar at
         or after the new cursor to the rebuilt buckets.

    Exits non-zero (via AssertionError) on any violation. Prints a summary
    and the levels found on success.
    """
    candidates = ["AAPL", "MSFT", "NVDA", "TSLA", "SPY", "QQQ"]
    symbol = next((s for s in candidates if len(_archive_days(s)) >= 60), None)
    if symbol is None:
        print("demo: no symbol with >=60 archived days found under data_archive/ -- skipped")
        return
    days = _archive_days(symbol)
    upto_day = days[len(days) // 2]           # a day with real history behind it
    upto_time = "10:15:00"                     # mid-window entry, matches the 09:30-11:00 lane

    day_bars = _rth_bars(symbol, upto_day)
    assert day_bars, f"demo: no RTH bars for {symbol} {upto_day}"
    price = day_bars[0].open                   # known at the open -- not a future value

    checked = 0
    for tf, minutes in HTF_TIMEFRAMES.items():
        candles, prov = htf_candles(symbol, upto_day, upto_time, minutes, debug=True)
        assert len(candles) == len(prov)
        cursor = _cursor_key(upto_day, upto_time)
        for sources in prov:
            for (d, ts) in sources:
                assert _cursor_key(d, ts) < cursor, (
                    f"CAUSALITY VIOLATION [{tf}]: bar {d} {ts} used to build a "
                    f"candle for cursor {cursor}")
                checked += 1

        # (2) pivot confirmation itself never reaches past the causal series
        k = PIVOT_STRENGTH
        if len(candles) >= 2 * k + 1:
            pivots = pivot_levels(candles, strength=k, as_of=len(candles) - 1)
            for p in pivots:
                assert p["usable_from"] <= len(candles) - 1, (
                    f"CAUSALITY VIOLATION [{tf}]: pivot {p['name']} usable_from="
                    f"{p['usable_from']} exceeds the causal series length "
                    f"{len(candles)}")

        # (3) an earlier cursor in the same session never picks up a later bar
        earlier_time = "09:50:00"
        if earlier_time < upto_time:
            _candles2, prov2 = htf_candles(symbol, upto_day, earlier_time, minutes, debug=True)
            earlier_cursor = _cursor_key(upto_day, earlier_time)
            for sources in prov2:
                for (d, ts) in sources:
                    assert _cursor_key(d, ts) < earlier_cursor, (
                        f"CAUSALITY VIOLATION [{tf}] (earlier cursor): bar {d} {ts} "
                        f"used to build a candle for cursor {earlier_cursor}")

    up = htf_level_beyond(symbol, upto_day, upto_time, price, "up")
    down = htf_level_beyond(symbol, upto_day, upto_time, price, "down")

    print(f"demo: {symbol} {upto_day} as-of {upto_time}, price={price:.2f}")
    print(f"  raw 1-minute bars provenance-checked (both timeframes): {checked}")
    print(f"  nearest level up:   {up}")
    print(f"  nearest level down: {down}")
    print("  causality: OK (no returned level traces to a bar at/after the cursor)")


if __name__ == "__main__":
    demo()
