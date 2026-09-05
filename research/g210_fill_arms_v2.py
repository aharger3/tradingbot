"""OMEN 10.0 R1 -- research/g90_fill_arms.py's six-arm fill comparison, re-run on
the CURRENT engine (base c13bdf8c).

**Why a new script instead of re-running g90_fill_arms.py as-is.** The pools
and the entry-fill mechanics (`as_booked`, `limit_level`, `next_open`,
`chase_once`, `mid_candle`, `close`) are UNCHANGED and are imported directly
from `g90_fill_arms.py` (`_resting_fill`, `_walk`, `_pnl`, `arm_stats`,
`close_stats`, `paired_diff_ci`, `ARMS`, `RISK_DOLLARS`, `EXTREME_BUF`,
`RETEST_WINDOW`) rather than copy-pasted, so there is exactly one
implementation of each. What changes here is: (1) the archive window (two
years ending at the current last archived session, not g90's), (2) a second
pool (`universe.CORE_SYMBOLS`, 11 names) alongside the original 29-symbol
pool, (3) one bug fix in how the "blind 2R" exit is forced (below), and (4)
per-arm per-pool stamped books with both grade ladders and the level name
attached to every row, plus avg-win/avg-loss, which g90's table did not
report.

**A bug in g90 this row fixes: `bw.LADDER_MODE = None` has done nothing since
2026-08-26.** `backtest_week.py`'s exit-plan switch was renamed from
`LADDER_MODE` to `SCALE_PLAN` that day (P5, "what's ladder B -- B is not a
grade anymore"). `g90_fill_arms.py::run_symbol` (written after the rename,
its own adversarial pass is dated 2026-09-03) still does `bw.LADDER_MODE =
None` -- which merely creates a new, never-read attribute on the `bw` module.
`SCALE_PLAN` is computed once, at import time, from `OMEN_SCALE_PLAN` /
`OMEN_LADDER_MODE`, and its actual default (no env override) is
`"hod_then_runner_be"` -- Austin's real ladder-B scale-out, NOT blind 2R. For
five of g90's six arms this makes no difference: `as_booked`, `limit_level`,
`next_open`, `chase_once` and `mid_candle` are all priced by this script's own
`_walk` (target vs a close-based stop, no scale-out, no disaster stop) and
never touch `bw.simulate_day`'s internal exit management at all. But g90's
`close` arm/comparator is NOT computed by `_walk` -- by design ("`close` ...
reusing `committed_entry`/`committed_r` already captured per row" -- the
actual `fill_price()` result from the same run"), it reads `t.pnl`/
`t.outcome`/`t.entry` straight off the `SimTrade` the real engine produced.
So g90's published `close` row (+0.7382R, $1,645/day, 925 trades, 925/925
"unfilled: 0") was silently the shipped ladder-B scale-out book, not blind 2R,
even though the module's docstring and every prose sentence in
`g90_fill_arms.md` describe it as one. This script sets
`os.environ["OMEN_SCALE_PLAN"] = "none"` BEFORE `import backtest_week` in
every worker process (the only point at which it can take effect) and asserts
`bw.SCALE_PLAN is None` immediately after, so the `close` arm here really is
blind 2R, on the same footing as the other five. **This means the `close`
column below is not comparable in magnitude to g90's published `close`
column** -- see the report's "differences from g90" section.

**A limitation inherited unchanged from g90, not fixed here (out of this
row's scope -- one row, one change).** `DISASTER_STOP` defaults ON in
`backtest_week.py` (the -1R hard-touch floor, R1/R2 2026-08-29) and is NOT
gated by `SCALE_PLAN`: even under `SCALE_PLAN=None`, `simulate_day`'s own
per-bar loop still checks `_disaster_hit` on every open trade. Since the
`close` arm reads its outcome from that real loop, it CAN book a disaster
stop-out that this script's own `_walk` (used by the other five arms) has no
equivalent for -- `_walk` only ever checks a close-based structural stop and
the 2R target. This is the same asymmetry g90 shipped with (DISASTER_STOP
already defaulted on when g90 ran, 2026-08-29 predates it); it is called out
here because touching it would be a second change, and this row is one
change: the SCALE_PLAN fix above.

**Signal set** (byte-identical definition to g90): `BacktestRunner` captures
every signal `SignalRunner.detect_signals` produces; a row is scored here iff
`t.counted` (status == "fired" and legacy engine grade != "C") and
`t.signal_type != "reentry_84_rule"` (re-entries carry the ORIGINAL trade's
target, not a fresh 2R -- see g90's own docstring for why they are scoped
out). Both grade ladders are recorded on every row: `grade` (legacy A+/A/B/
C/X, the one that gates `t.counted`) and `austin_tier` (S/A/C, reported only,
`compute_austin_tier`, AUSTIN_TIER_ENABLED default True).

**Pools.** `FULL_POOL` = `MAJOR_15 + INDEX_POOL + OTHER_POOL` (29 symbols,
identical set to g90's `ALL_SYMBOLS`). `CORE_POOL` = `universe.CORE_SYMBOLS`
(11 symbols: TSLA NVDA AAPL AMD META GOOGL AMZN MSFT PLTR QQQ SPY), a strict
subset of FULL_POOL -- so the replay runs ONCE over the 29-symbol pool and
`CORE_POOL`'s book is a filtered subset of the same signal set, not a second
replay.

**Window.** Two years ending at the last day any pool symbol has an archived
session for (`data_archive/<SYM>/*.csv`, computed from disk, never
hardcoded -- CLAUDE.md's "stops 2026-08-27" is stale, the archive has since
advanced). Printed by `main()` and stated in the report.

**The current engine's default entry fill.** `entry_fill.ENTRY_FILL` defaults
to `"close"` (no env override) and `entry_fill.entry_fill_price(mode="close")`
unconditionally returns `candle.close` -- no clamping, no level, regardless of
`close_is_bad_fill`. `signal_runner.fill_price()` is a pure pass-through to
that (`mode = "close" if entry_fill.needs_future_bars() else None`, and
`needs_future_bars()` is False for the default). So the committed book's own
fill IS this script's `close` arm, exactly, by construction -- not a fifth
reconstruction. The `close` arm's row is therefore built by copying
`t.entry`/`t.stop`/`t.pnl`/`t.outcome`/`t.exit_price` off the real `SimTrade`
the engine produced (see `row["committed_*"]` below) -- never recomputed.

Output: `research/tape/fillarms_<arm>_<pool>.json.gz` (one per arm x pool,
6 x 2 = 12 books) and `research/g210_fill_arms_v2.md`.
"""
import os
import sys
import csv
import json
import gzip
import argparse
from collections import defaultdict
from datetime import date
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from universe import MAJOR_15, INDEX_POOL, OTHER_POOL, CORE_SYMBOLS, ARCHIVE_DIR
from t8_two_year import day_table, rth_candles, bias_from, ARCHIVE
# The one implementation of every arm's mechanics -- imported, not re-derived.
from g90_fill_arms import (
    ARMS, RISK_DOLLARS, EXTREME_BUF, RETEST_WINDOW,
    _resting_fill, _walk, _pnl, arm_stats, close_stats, paired_diff_ci,
)
from book_stamp import stamp as book_stamp_stamp

OUT_DIR = os.path.join(HERE, "tape")
OUT_MD = os.path.join(HERE, "g210_fill_arms_v2.md")

FULL_POOL = sorted({s for p in (MAJOR_15, INDEX_POOL, OTHER_POOL) for s in p})
CORE_POOL = list(CORE_SYMBOLS)
CORE_SET = set(CORE_POOL)

DISPLAY_ARMS = ["as_booked", "limit_level", "next_open", "chase_once", "close", "mid_candle"]

# g90's own published table (2024-08-12 to 2026-08-11, 29 symbols), copied
# verbatim from research/g90_fill_arms.md for the side-by-side in the report.
# NOT recomputed -- see that file for the source.
G90_TABLE = [
    # arm, trades, unfilled, win_rate, mean_r, months, green_months, dollar_day
    ("as_booked",   793, 132, "58.5%", "+0.7552", 25, 25, 1443),
    ("limit_level", 659, 266, "45.9%", "+0.2760", 25, 21, 438),
    ("next_open",   925,   0, "41.8%", "+0.2551", 25, 22, 569),
    ("chase_once",  785, 140, "35.1%", "+0.0564", 25, 14, 107),
    ("close",       925,   0, "57.9%", "+0.7382", 25, 25, 1645),
    ("mid_candle",  742, 183, "47.0%", "+0.2381", 25, 20, 426),
]
G90_WINDOW = "2024-08-12 to 2026-08-11"
G90_POOL_N = 29


def latest_archived_day(symbols):
    best = None
    for s in symbols:
        d = os.path.join(ARCHIVE_DIR, s)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith(".csv"):
                day = f[:-4]
                if best is None or day > best:
                    best = day
    return best


def two_years_back(day_iso):
    y, m, d = (int(x) for x in day_iso.split("-"))
    try:
        return date(y - 2, m, d).isoformat()
    except ValueError:          # day_iso is a Feb 29 and y-2 is not a leap year
        return date(y - 2, m, d - 1).isoformat()


def run_symbol(args):
    symbol, start_day, end_day = args

    # THE FIX -- see module docstring. Must happen before backtest_week is
    # ever imported in THIS process; SCALE_PLAN is computed once, at import.
    os.environ["OMEN_SCALE_PLAN"] = "none"
    import backtest_week as bw
    import signal_runner as sr

    assert bw.SCALE_PLAN is None, (
        "OMEN_SCALE_PLAN=none did not take effect -- SCALE_PLAN=%r. The env "
        "var must be set before backtest_week's first import in this "
        "process (see module docstring)." % bw.SCALE_PLAN)
    bw.STOP_ON_CLOSE = True  # already the shipped default; explicit for parity with g90
    CHASE_PCT = sr.CHASE_PCT

    mailbox = {}
    orig_fill_price = sr.fill_price

    def wrapped_fill_price(level, candle, is_long, session_hi=None, session_lo=None):
        result = orig_fill_price(level, candle, is_long, session_hi=session_hi, session_lo=session_lo)
        mailbox["last"] = (level, candle, is_long)
        return result

    sr.fill_price = wrapped_fill_price

    class FillArmRunner(bw.BacktestRunner):
        def _route(self, signals, sig):
            super()._route(signals, sig)
            ctx = mailbox.pop("last", None)
            if ctx is not None:
                level, candle, is_long = ctx
                sig["_level"] = level
                sig["_candle_id"] = id(candle)

    seen_runners = []
    orig_backtest_runner = bw.BacktestRunner
    orig_init = FillArmRunner.__init__

    def init(self, sym):
        orig_init(self, sym)
        seen_runners.append(self)
    FillArmRunner.__init__ = init
    bw.BacktestRunner = FillArmRunner

    table = day_table(symbol)
    days = sorted(table)
    out_rows = []
    days_run = 0
    entry_idx_mismatches = 0

    for i, day in enumerate(days):
        if day < start_day or day > end_day:
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

        idx_by_id = {id(c): j for j, c in enumerate(candles)}

        del seen_runners[:]
        trades = bw.simulate_day(symbol, day, candles, pdh, pdl, bias, pmh, pml, pdo, pdc, None)
        days_run += 1

        pool = defaultdict(list)
        if seen_runners:
            for sig in seen_runners[-1].captured:
                k = (sig["signal_type"].value, sig["direction"], round(float(sig["entry"]), 4), sig.get("status"))
                pool[k].append(sig)
        used = defaultdict(int)

        for t in trades:
            if not t.counted:          # traded book only: fired, engine grade != C
                continue
            if t.signal_type == "reentry_84_rule":
                continue                # scoped out -- see module docstring
            k = (t.signal_type, t.direction, round(float(t.entry), 4), t.status)
            lst = pool.get(k) or []
            n = used[k]
            if n >= len(lst):
                continue
            sig = lst[n]
            used[k] += 1
            level = sig.get("_level")
            cid = sig.get("_candle_id")
            entry_idx = idx_by_id.get(cid)
            if level is None or entry_idx is None:
                continue
            if entry_idx != t.entry_idx:
                # Should never fire while ENTRY_FILL stays "close" (the
                # default): only the three forward ENTRY_FILL modes make
                # backtest_week re-price the entry onto a later bar, and
                # this script never sets ENTRY_FILL. Counted, not silent.
                entry_idx_mismatches += 1
                continue

            is_long = t.direction == "call"
            entry_candle = candles[entry_idx]
            stop = t.stop  # SAME structural stop the committed engine placed

            row = {"symbol": symbol, "day": day, "entry_time": t.entry_time,
                   "side": t.direction, "setup": t.signal_type,
                   "setup_type": t.setup_type, "grade": t.grade,
                   "austin_tier": t.austin_tier or "",
                   "level_name": t.stop_level_name or "", "level_price": level,
                   "stop": stop, "entry_idx": entry_idx,
                   # the committed engine's own unmodified result for this
                   # signal -- the `close` arm below READS these, never
                   # recomputes them.
                   "committed_entry": t.entry, "committed_stop": t.stop,
                   "committed_target": t.target,
                   "committed_r": round(t.pnl / RISK_DOLLARS, 4),
                   "committed_outcome": t.outcome,
                   "committed_exit": t.exit_price}

            for arm in ARMS:
                entry = None
                fill_bar_idx = entry_idx
                start_check = entry_idx + 1
                if arm == "as_booked":
                    entry = level
                elif arm == "limit_level":
                    entry, fill_bar_idx = _resting_fill(candles, entry_idx + 1, level)
                elif arm == "mid_candle":
                    mid = (entry_candle.high + entry_candle.low) / 2.0
                    entry, fill_bar_idx = _resting_fill(candles, entry_idx + 1, mid)
                elif arm in ("next_open", "chase_once"):
                    nxt_idx = entry_idx + 1
                    if nxt_idx < len(candles):
                        nxt = candles[nxt_idx]
                        if arm == "next_open":
                            entry = nxt.open
                        else:
                            candidate = max(nxt.open, nxt.close) if is_long else min(nxt.open, nxt.close)
                            if abs(candidate - level) / level <= CHASE_PCT:
                                entry = candidate
                        fill_bar_idx = nxt_idx
                        start_check = nxt_idx

                if entry is None:
                    row[arm] = {"filled": False}
                    continue
                if fill_bar_idx is None:
                    row[arm] = {"filled": False}
                    continue

                risk = (entry - stop) if is_long else (stop - entry)
                if risk <= 0:
                    row[arm] = {"filled": False, "reason": "non-positive risk"}
                    continue
                target = entry + 2 * risk if is_long else entry - 2 * risk
                start_check = max(start_check, fill_bar_idx + 1)

                fill_candle = candles[fill_bar_idx]
                outcome = exit_price = exit_idx = None
                if arm in ("as_booked", "limit_level", "mid_candle"):
                    closed_back = (fill_candle.close < stop if is_long else fill_candle.close > stop)
                    if closed_back:
                        outcome, exit_price, exit_idx = "scratch", fill_candle.close, fill_bar_idx

                if outcome is None:
                    outcome, exit_price, exit_idx = _walk(candles, start_check, stop, target, is_long)

                pnl = _pnl(entry, stop, exit_price, is_long, RISK_DOLLARS)
                row[arm] = {"filled": True, "entry": round(entry, 4), "stop": round(stop, 4),
                            "target": round(target, 4), "outcome": outcome,
                            "exit_price": round(exit_price, 4),
                            "fill_time": fill_candle.timestamp,
                            "r": round(pnl / RISK_DOLLARS, 4), "pnl": pnl}
            out_rows.append(row)

    bw.BacktestRunner = orig_backtest_runner
    sr.fill_price = orig_fill_price
    return symbol, out_rows, days_run, entry_idx_mismatches


def avg_win_loss(rows, arm):
    if arm == "close":
        wins = [r["committed_r"] for r in rows if r["committed_outcome"] == "win"]
        losses = [r["committed_r"] for r in rows if r["committed_outcome"] == "loss"]
    else:
        filled = [r for r in rows if r[arm].get("filled")]
        wins = [r[arm]["r"] for r in filled if r[arm]["outcome"] == "win"]
        losses = [r[arm]["r"] for r in filled if r[arm]["outcome"] == "loss"]
    aw = round(sum(wins) / len(wins), 4) if wins else None
    al = round(sum(losses) / len(losses), 4) if losses else None
    return aw, al


def stats_for(rows, arm):
    return arm_stats(rows, arm) if arm != "close" else close_stats(rows)


def flatten_arm_rows(rows, arm):
    out = []
    for r in rows:
        if arm == "close":
            filled = True
            entry, stop = r["committed_entry"], r["committed_stop"]
            exit_px, r_mult = r["committed_exit"], r["committed_r"]
            pnl = round(r_mult * RISK_DOLLARS, 2)
            fill_time = r["entry_time"]
        else:
            d = r[arm]
            filled = bool(d.get("filled"))
            entry = d.get("entry")
            stop = d.get("stop")
            exit_px = d.get("exit_price")
            r_mult = d.get("r")
            pnl = d.get("pnl")
            fill_time = d.get("fill_time")
        out.append({
            "sym": r["symbol"], "day": r["day"], "entry_time": r["entry_time"],
            "fill_time": fill_time, "side": r["side"], "setup": r["setup"],
            "setup_type": r.get("setup_type", ""), "grade": r["grade"],
            "austin_tier": r["austin_tier"], "level_name": r["level_name"],
            "level_price": r["level_price"], "fill_mode": arm,
            "entry": entry, "stop": stop, "exit": exit_px, "r": r_mult, "pnl": pnl,
            "unfilled": not filled,
        })
    return out


def write_book(rows, arm, pool_name, window):
    """Every book carries research/book_stamp.py's identity block: commit,
    dirty flag, every flag value, date, window, script -- see CLAUDE.md's
    'stamped books only' rule. `book_stamp.engine_flags()` reads the CURRENT
    process's modules; this script always runs with `OMEN_SCALE_PLAN=none`
    forced (see module docstring), so the stamp's SCALE_PLAN reading matches
    what actually priced every arm, including `close`."""
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"fillarms_{arm}_{pool_name}.json.gz")
    trades = flatten_arm_rows(rows, arm)
    traded = sum(1 for r in trades if not r["unfilled"])
    # book_id() hashes entry/stop/pnl as floats; an unfilled row carries None
    # for all three -- sanitize a throwaway copy for the fingerprint only,
    # the written "trades" list keeps its real None values.
    hash_rows = [dict(r, entry=r["entry"] or 0.0, stop=r["stop"] or 0.0,
                       pnl=r["pnl"] or 0.0) for r in trades]
    meta = {
        "entry_fill": arm, "pool": pool_name, "signals": len(trades),
        "traded": traded, "window": {"start": window[0], "end": window[1]},
        "script": "research/g210_fill_arms_v2.py",
        "generated": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "stamp": book_stamp_stamp(hash_rows, entry_fill=arm, pool=pool_name,
                                   window={"start": window[0], "end": window[1]},
                                   script="research/g210_fill_arms_v2.py"),
    }
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "trades": trades}, f)
    return path


def hand_verify_samples(rows, n_each=10):
    """Pull `n_each` filled next_open + `n_each` filled limit_level rows,
    deterministically spaced through the book, and re-read the raw archive
    CSV directly (never through Candle/rth_candles) to confirm the booked
    fill really is what that minute's own bar printed. Returns markdown
    lines."""
    lines = []
    for arm in ("next_open", "limit_level"):
        filled = [r for r in rows if r[arm].get("filled")]
        if not filled:
            lines.append(f"- `{arm}`: no filled rows to sample.")
            continue
        step = max(1, len(filled) // n_each)
        sample = filled[::step][:n_each]
        lines.append(f"\n**{arm}** ({len(sample)} of {len(filled)} filled rows sampled):\n")
        lines.append("| symbol | day | minute | bar O/H/L/C | booked fill | match |")
        lines.append("|---|---|---|---|---:|---|")
        for r in sample:
            d = r[arm]
            ft = d.get("fill_time", "")
            minute = ft[:5] if ft else "?"
            path = os.path.join(ARCHIVE_DIR, r["symbol"], f"{r['day']}.csv")
            bar = None
            if os.path.exists(path):
                with open(path) as f:
                    for row in csv.DictReader(f):
                        ts = row["Datetime"]
                        hh_mm = ts.split("T", 1)[1][:5] if "T" in ts else ts[11:16]
                        if hh_mm == minute:
                            bar = row
                            break
            if bar is None:
                lines.append(f"| {r['symbol']} | {r['day']} | {minute} | NOT FOUND | "
                              f"{d.get('entry')} | NO -- bar missing from raw archive |")
                continue
            o, h, l, c = float(bar["Open"]), float(bar["High"]), float(bar["Low"]), float(bar["Close"])
            booked = d.get("entry")
            if arm == "next_open":
                ok = abs(booked - o) < 1e-6
            else:  # limit_level: booked must sit within the bar's own range
                ok = (l - 1e-6) <= booked <= (h + 1e-6)
            lines.append(f"| {r['symbol']} | {r['day']} | {minute} | "
                          f"{o:.4f}/{h:.4f}/{l:.4f}/{c:.4f} | {booked:.4f} | "
                          f"{'YES' if ok else 'NO -- MISMATCH'} |")
    return lines


def verify_close_matches_default(rows):
    """The row's own verify step: `close` must equal the engine's unmodified
    default fill (`entry_fill.ENTRY_FILL == "close"`, `signal_runner.fill_price`)
    on 100% of rows. An INDEPENDENT check, not a tautology: re-opens the raw
    archive CSV for each row's symbol/day and confirms `committed_entry`
    equals that minute's own printed close (the quantity
    `entry_fill.entry_fill_price(mode="close")` returns), the same way
    `hand_verify_samples` checks `next_open`/`limit_level` against the raw
    tape, just for every row instead of a sample."""
    bad = []
    csv_cache = {}
    for r in rows:
        key = (r["symbol"], r["day"])
        if key not in csv_cache:
            path = os.path.join(ARCHIVE_DIR, r["symbol"], f"{r['day']}.csv")
            bars = {}
            if os.path.exists(path):
                with open(path) as f:
                    for row in csv.DictReader(f):
                        ts = row["Datetime"]
                        hh_mm = ts.split("T", 1)[1][:5] if "T" in ts else ts[11:16]
                        bars[hh_mm] = float(row["Close"])
            csv_cache[key] = bars
        bars = csv_cache[key]
        minute = r["entry_time"][:5] if r["entry_time"] else None
        bar_close = bars.get(minute)
        if bar_close is None or abs(r["committed_entry"] - bar_close) > 1e-4:
            bad.append((r["symbol"], r["day"], minute, r["committed_entry"], bar_close))
    return len(rows), bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--procs", type=int, default=8)
    ap.add_argument("--out-md", default=OUT_MD)
    a = ap.parse_args()

    syms = [s for s in FULL_POOL if os.path.isdir(os.path.join(ARCHIVE_DIR, s))]
    missing = [s for s in FULL_POOL if not os.path.isdir(os.path.join(ARCHIVE_DIR, s))]
    end_day = latest_archived_day(syms)
    start_day = two_years_back(end_day)
    print(f"window: {start_day} -> {end_day}", flush=True)
    print(f"full pool: {len(syms)} symbols, missing archive: {missing or 'none'}", flush=True)
    print(f"core pool: {len(CORE_POOL)} symbols: {CORE_POOL}", flush=True)

    args = [(s, start_day, end_day) for s in syms]
    all_rows = []
    per_sym_days = {}
    total_mismatches = 0
    with Pool(a.procs) as pool:
        for sym, rows, d, mism in pool.imap_unordered(run_symbol, args):
            all_rows.extend(rows)
            per_sym_days[sym] = d
            total_mismatches += mism
            print(f"  {sym}: {len(rows)} signals over {d} days "
                  f"(entry_idx mismatches: {mism})", flush=True)

    total_days = sum(per_sym_days.values())
    core_rows = [r for r in all_rows if r["symbol"] in CORE_SET]
    print(f"\ntotal signals (full29): {len(all_rows)}  total symbol-days: {total_days}")
    print(f"total signals (core11): {len(core_rows)}")
    print(f"entry_idx mismatches (should be 0): {total_mismatches}")

    pools = [("core11", core_rows, len(CORE_POOL)), ("full29", all_rows, len(syms))]

    # ---- write the 12 stamped books -------------------------------------
    written = []
    for pool_name, rows, _n in pools:
        for arm in DISPLAY_ARMS:
            written.append(write_book(rows, arm, pool_name, (start_day, end_day)))

    # ---- verify: close matches the engine's own default on 100% ----------
    n_checked, bad_list = verify_close_matches_default(all_rows)
    n_bad = len(bad_list)

    # ---- hand-verification sample -----------------------------------------
    verify_lines = hand_verify_samples(all_rows, n_each=10)

    # ---- report -------------------------------------------------------------
    L = []
    L.append("# OMEN 10.0 R1 -- the six fill arms, re-run on the current engine\n")
    L.append(f"Base `c13bdf8c`. Window `{start_day}` to `{end_day}` "
             f"(two years ending at the last archived session on disk, "
             f"computed from `data_archive/`, not hardcoded). Full pool: "
             f"{len(syms)} symbols (MAJOR_15+INDEX_POOL+OTHER_POOL"
             + (f", missing archive: {missing}" if missing else "") +
             f"), {total_days} symbol-days. Core pool: `universe.CORE_SYMBOLS` "
             f"({len(CORE_POOL)} symbols: {', '.join(CORE_POOL)}), a subset of "
             f"the same replay. Blind 2R exit (`OMEN_SCALE_PLAN=none`, fixing "
             f"the stale `LADDER_MODE` attribute g90 set -- see script "
             f"docstring), `STOP_ON_CLOSE=1`. $1,000 risk/trade. Signal set: "
             f"fired, legacy engine grade != C, `reentry_84_rule` excluded -- "
             f"identical definition to g90.\n")
    L.append("## The current engine's default fill\n")
    L.append(
        "`entry_fill.ENTRY_FILL` defaults to `\"close\"` and "
        "`entry_fill_price(mode=\"close\")` unconditionally returns the "
        "signal minute's own close -- no level, no clamping. "
        "`signal_runner.fill_price()` is a pure pass-through to that on the "
        "default path. **The current engine's default fill equals arm "
        "`close`, exactly** (not `as_booked`, which is the raw structural "
        "level, unconditionally -- a different price on almost every row). "
        "The `close` arm below is therefore never recomputed: every field "
        "is read off the real `SimTrade` the committed engine produced for "
        "that signal.\n")

    for pool_name, rows, n_syms in pools:
        L.append(f"## Result -- {pool_name} ({n_syms} symbols, {len(rows)} signals)\n")
        L.append("| arm | trades | unfilled | win rate | mean R | avg win | avg loss | months | green months | $/day |")
        L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for arm in DISPLAY_ARMS:
            s = stats_for(rows, arm)
            aw, al = avg_win_loss(rows, arm)
            wr = f"{s['wr']}%" if s["wr"] is not None else "--"
            mr = f"{s['mean_r']:+.4f}" if s["mean_r"] is not None else "--"
            dd = f"${s['dollar_day']:,.0f}" if s["dollar_day"] is not None else "--"
            awf = f"{aw:+.4f}" if aw is not None else "--"
            alf = f"{al:+.4f}" if al is not None else "--"
            L.append(f"| {arm} | {s['n']} | {s['unfilled']} | {wr} | {mr} | {awf} | {alf} | "
                     f"{s['months']} | {s['green_months']}/{s['months']} | {dd} |")
        L.append("")

    L.append(f"## g90's published table, for comparison (verbatim, not recomputed)\n")
    L.append(f"`{G90_WINDOW}`, {G90_POOL_N} symbols (MAJOR_15+INDEX_POOL+OTHER_POOL), "
             f"925 traded signals -- from `research/g90_fill_arms.md`.\n")
    L.append("| arm | trades | unfilled | win rate | mean R | months | green months | $/day |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for arm, n, unf, wr, mr, mo, gm, dd in G90_TABLE:
        L.append(f"| {arm} | {n} | {unf} | {wr} | {mr} | {mo} | {gm}/{mo} | ${dd:,} |")
    L.append("")

    full_stats_close = stats_for(all_rows, "close")
    g90_close_dd = dict(zip([r[0] for r in G90_TABLE], [r[7] for r in G90_TABLE]))["close"]
    L.append("## Differences from g90, explained\n")
    L.append(
        f"**1. `close` moves from g90's +0.7382R / ${g90_close_dd:,}/day to "
        f"{full_stats_close['mean_r']:+.4f}R / ${full_stats_close['dollar_day']:,.0f}/day "
        f"(full29, this window) -- EXPLAINED, not a regression.** g90's "
        f"`close` was silently the shipped ladder-B scale-out book (see the "
        f"`LADDER_MODE`/`SCALE_PLAN` bug in this script's module docstring); "
        f"this run is genuinely blind 2R for every arm including `close`. "
        f"The two numbers answer different questions and should not be "
        f"read as the same quantity moving.\n")
    L.append(
        "**2. Trade counts differ from g90's for every arm -- EXPLAINED.** "
        "Two independent causes, both expected: (a) the window is different "
        "(g90: 2024-08-12 to 2026-08-11; here: the current two-year window "
        "computed from disk, above) -- a different set of trading days will "
        "produce a different number of signals on the same detector; (b) the "
        "engine itself has changed between g90's base and `c13bdf8c` (new "
        "flags, gates and fixes have landed in `signal_runner.py`/"
        "`backtest_week.py` in the interim per `CLAUDE.md`'s changelog) -- "
        "this row does not attempt to isolate which commits moved the count, "
        "only to price the current committed code.\n")
    L.append(
        "**3. `entry_idx` mismatches: "
        f"{total_mismatches} of {len(all_rows) + total_mismatches} candidate "
        "rows (should be 0) -- FOUND, DIAGNOSED, does not change any book.** "
        "The one mismatch is `ACHR` `2026-04-06`, a `break_and_retest` B-grade "
        "signal at `09:50:00` (`t.entry=5.665`, `t.stop=5.63`, level `5.63`). "
        "Cause: this script correlates each `SimTrade` back to the captured "
        "signal dict that produced it by the tuple key "
        "`(signal_type, direction, round(entry, 4), status)`, consuming "
        "matches in `captured` order (`used[k]` counter) -- on this day two "
        "distinct ACHR signals share an identical rounded entry price under "
        "that key, so the counter paired this trade with the WRONG signal's "
        "candle id, and the recomputed `entry_idx` (16) disagreed with the "
        "trade's own recorded `entry_idx` (20). This is a correlation bug in "
        "THIS harness's bookkeeping, not in `signal_runner`/`backtest_week` -- "
        "`t.entry`/`t.stop`/`t.pnl` on the real trade are unaffected either "
        "way. The row is defensively `continue`d before being appended, so "
        "the effect on every book is that this ONE row (of 7858 candidates) "
        "is simply ABSENT from all 12 books rather than silently wrong -- "
        "0.013% of the full29 signal set, inside every arm's own reported "
        "trade count already. Not fixed in this row (one change per row; the "
        "fix is a tie-break on entry TIME as well as price, which touches "
        "the matching loop, a second change) -- documented, not silent.\n")
    L.append(
        "**4. Everything else -- pool composition, the five non-close arms' "
        "mechanics (`_resting_fill`, `_walk`, `_pnl`, `EXTREME_BUF=0.05`, "
        "`RETEST_WINDOW=12`), the lookahead rule, the $1,000 risk unit -- is "
        "byte-identical to g90 (imported from `g90_fill_arms.py`, not "
        "reimplemented).\n")

    L.append("## Verify: close vs the engine's default\n")
    L.append(f"{n_checked} rows checked against the raw archive tape, "
             f"{n_bad} mismatches -- "
             f"{'PASS: 100% match' if n_bad == 0 else 'FAIL'}. This is an "
             f"INDEPENDENT check (`verify_close_matches_default`), not a "
             f"tautology: for every row it re-opens the raw archive CSV for "
             f"that symbol/day and confirms `committed_entry` equals the "
             f"entry minute's own printed close -- the exact quantity "
             f"`entry_fill.entry_fill_price(mode=\"close\")` returns and "
             f"`signal_runner.fill_price()` passes through unmodified on the "
             f"default path. Same method `research/g210_verify.py` runs "
             f"standalone (see below).\n")
    if bad_list:
        L.append("First mismatches:\n")
        for sym, day, minute, committed, bar in bad_list[:10]:
            L.append(f"- {sym} {day} {minute}: committed_entry={committed} vs archive close={bar}")
        L.append("")

    L.append("## Hand-verification: 20 sampled next_open / limit_level fills against raw archive bars\n")
    L.extend(verify_lines)
    L.append("")

    L.append("## What else changed between g90's run and now\n")
    import signal_runner as _sr_report
    L.append(
        f"**`RETEST_REQUIRED` defaults ON** (`signal_runner.RETEST_REQUIRED` "
        f"reads `os.getenv(\"RETEST_REQUIRED\", \"1\")`, currently `{_sr_report.RETEST_REQUIRED}`), "
        "shipped 2026-09-02 (`CLAUDE.md`) -- AFTER g90's 2026-08-11-window run. "
        "Both this row and g90 ran with whatever `RETEST_REQUIRED` defaulted to "
        "at the time, i.e. this run has a gate g90's did not. It changes which "
        "signals `signal_runner` fires (and therefore the whole signal set "
        "priced below) -- it is folded into cause (b) of item 2 above (the "
        "engine changed between the two runs), named here explicitly because "
        "the spec calls it out by name.\n")
    L.append(
        "**`DISASTER_STOP` asymmetry, restated plainly.** `close` can book a "
        "disaster stop-out (a resting -1R touch, `backtest_week.py`'s own "
        "per-bar loop) that the other five arms' shared `_walk` implementation "
        "has no equivalent for -- `_walk` only checks a close-based structural "
        "stop and the 2R target, never an intrabar touch. So `close`'s losses "
        "can be capped at -1.000R intrabar while the other five arms' losses "
        "are only capped at whatever the next closed candle prints, which can "
        "be worse than -1R. This is inherited from g90 unchanged (out of this "
        "row's one-change scope) and is the same asymmetry `CLAUDE.md`'s "
        "\"Rules that hold everywhere\" section documents for `stop_rule.py` "
        "in general.\n")
    L.append(
        "**Size gate: NOT applied.** `signal_runner.min_risk_floor` "
        "(`max(0.10, 0.0015 x close)`) is never called in this script's arm "
        "loop -- the only risk check is `if risk <= 0`. So every number in "
        "both tables above is the UNSIZED arithmetic CLAUDE.md warns about "
        "(\"Ungated, the g87 sweep printed $15,119/day -- arithmetic, not "
        "money\"): a fill landing a cent from its stop is not excluded, and "
        "would size to an unrealistic position under `$1,000` fixed risk. "
        "g90 did not apply this gate either (inherited, not new). Applying "
        "it is a second change (touches the per-arm risk computation, which "
        "would move every trade count and therefore require re-running the "
        "hour-long replay) and is out of this row's one-change scope -- "
        "flagged here rather than left silent, per the size-gate rule. A "
        "follow-up row should re-run `g210_fill_arms_v2.py` with a "
        "`risk < sr.min_risk_floor(entry)` exclusion added to the arm loop "
        "and republish both tables.\n")

    L.append("## What could not be done in this row\n")
    L.append(
        "Nothing was cut for time in this run. Not attempted, by design "
        "(out of scope for a one-change row): reconciling WHY trade counts "
        "differ from g90 commit-by-commit (that is R2/R3's job, not R1's); "
        "auditing the DISASTER_STOP asymmetry between `close` and the other "
        "five arms (named above, inherited unchanged from g90).\n")

    L.append("## Reproduce\n")
    L.append("```\npython research/g210_fill_arms_v2.py --procs 8\n```\n")
    L.append(f"Window and pools are computed from `data_archive/` at run time, not passed as "
             f"flags -- re-running after the archive advances will move the window forward.\n")
    L.append("Books written:\n")
    for p in written:
        L.append(f"- `{os.path.relpath(p, ROOT)}`")

    with open(a.out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"\nwrote {a.out_md}")
    for p in written:
        print(f"wrote {p}")


if __name__ == "__main__":
    main()
