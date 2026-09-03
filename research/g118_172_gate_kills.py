"""g118 -- the 172 gate kill: which gate ate each of Austin's un-traded S days.

`research/MORNING_REPORT.md` section 3 rule 4: of 347 canonical S days
(`research/marks_pool.canonical_pool()`), 227 have no traded candidate.
11 are off-universe, 44 are outside the 498-session window, and 172 are IN
the book (`research/bt2y_trades_retest_on.json`, the honest close-fill book
RETEST_REQUIRED currently ships with) with candidates that existed and never
became the day's trade. This script rebuilds that 172 from the data, attributes
each day's BEST candidate to the specific gate that killed it, and prices what
that candidate would have booked under a plain -1R stop / flat 2R target.

THE 227 SPLIT, exactly as the report states it
------------------------------------------------
  off-universe        symbol not among the 28 the book was built on
  outside window      symbol in-universe, but ZERO signal rows exist for that
                       exact (symbol, day) anywhere in the book -- before the
                       archive's start, after its end, no archived bars that
                       day, or a valid session on which nothing ever set up
  the 172              symbol in-universe, at least one signal row exists for
                       that day, but NONE of them is `traded: true`

`traded` in this book is not "first signal of the day" -- it is
`status=="fired" and grade != "C"` (`backtest_week.SimTrade.counted`). A `C`
that never gets the day's with-trend floor promotion is `alert`, not `traded`,
so the 172 is a mix of: a `C` that reached the tape and stalled there, a
would-be `A`/`B` that a portfolio-wide loss-halt reclassified to `halted`
(another SYMBOL's two straight losses, not this one's), and a candidate that
never left `X` at all.

ATTRIBUTION METHOD -- reuses `research/g4_dropped_s.py`, does not re-derive it
--------------------------------------------------------------------------
Two things are recomputable straight off the committed row, no replay needed:

  * HTF bias opposed -- the row's own `bias` field IS the `htf_bias` argument
    `grade_trade` was called with (`backtest_2y.py`: `"bias": bias or "none"`),
    so `bias in (bullish,bearish) and (bias=="bullish") != (dir=="call")`
    reproduces the veto exactly.
  * The two `skipped_tight_stop` causes -- `MIN_STOP_PCT` (stop under 0.08% of
    price, scoped off OCR) is pure arithmetic on `entry`/`stop`; the only other
    branch left, once `NO_REPEAT_ENTRIES`/`LEVEL_RETIRE_TOUCHES`/repeat-idea
    are confirmed OFF in this book's own flag stamp, is the C-grade
    `_min_viable_stop` structural floor.
  * A `fired`-but-not-traded row is, by the `counted` property above, always
    grade `C` -- so it is either capped before promotion (its `reason` string
    literally carries `[capped C: ...]`) or it just never was the day's first
    with-trend signal.

Colour gate / never-touched-level / the B&R and OCR min-stop demotions are
NOT recoverable from the exported row (no candle OHLC, no `close`) -- exactly
the gap `g4_dropped_s.py` exists to close. So this script imports it and reuses
its `pa_branch` / `kill_branch` / `install_patches` verbatim, restricted to a
REPLAY OF ONLY THE 172 TARGET DAYS (not the full two-year window): each
relevant symbol's full archive is still walked to build correct trailing HTF
bias, but `simulate_day` -- the expensive part -- is only called on days this
script actually needs. Same instrumentation, same verdicts, a few minutes
instead of the full two-year run.

THE COUNTERFACTUAL
-------------------
Austin's ask, verbatim: "the candidate's own would-be outcome if it had traded
at the close fill with a -1R stop and flat 2R target." Simple by design, and
DELIBERATELY NOT the shipped engine's own R (`bt2y_trades_retest_on.json`'s
`r` runs the full ladder / scale-out / disaster-stop machinery -- see
`research/g4_dropped_s.md` Sec 4 for why that number is a different question).
Here: entry = the row's own `entry` (the honest close fill, unchanged), stop =
the row's own `stop`, target = entry +/- 2x risk. Walk the archived RTH bars
forward from the entry bar: target fires on an intrabar touch, the stop fires
only on a CLOSE beyond it (this project's one stop rule, CLAUDE.md), first one
to trigger wins; unresolved by the session's last bar exits at that close,
R clipped to [-1, +2]. No -1.25R floor, no ladder, no breakeven -- Austin asked
for the plain version so the gate's own cost is legible without the exit
machinery's fingerprints on it.

Usage:
    python research/g118_172_gate_kills.py                 # replay + report
    python research/g118_172_gate_kills.py --cache-only     # reuse replay cache
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import marks_pool as mp                                  # noqa: E402
import g4_dropped_s as g4                                # noqa: E402  the branch-attribution rig
import signal_runner as sr                                # noqa: E402

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")
CACHE = os.path.join(HERE, "_g118_branches.json")
OUT_MD = os.path.join(HERE, "g118_172_gate_kills.md")
OUT_ROWS = os.path.join(HERE, "g118_172_gate_kills_rows.json")

MIN_STOP_PCT = getattr(sr, "MIN_STOP_PCT", 0.08)

# gate labels -- kept short, used as table keys and in the per-row export
G_HALT = "portfolio loss-halt (another symbol's 2 consecutive losses blocked this A/B candidate)"
G_CcapS = "graded C, capped before promotion"
G_Cfloor = "graded C, never promoted (not the day's first with-trend signal)"
G_MINPCT = "MIN_STOP_PCT -- stop under 0.08% of price"
G_MINVI = "C-grade tight stop -- _min_viable_stop (structural floor)"
G_BIAS = "HTF bias opposed"
G_COLOUR = "colour gate -- entry candle is the wrong colour"
G_NEVER = "candle never traded back to the level"
G_BNRMIN = "B&R min-stop -- risk < max($0.10, 0.15% of price)"
G_OCRMIN = "OCR min-stop -- risk < $0.50"
G_OCRWIDE = "OCR stop wider than 0.4% of price"
G_UNMATCHED = "skipped_d, unmatched to replay (unattributed)"

DETECTION_MISS = "detection miss (no candidate this session)"
GATE_KILL = "gate kill (a candidate existed and was killed)"


def _r(v, n=4):
    return round(v, n) if isinstance(v, float) else v


# --------------------------------------------------------------- the 227 split

def build_target_sets():
    blob = json.loads(Path(BOOK_PATH).read_text(encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    pool = mp.canonical_pool()
    S = {k: e for k, e in pool.items() if e.grade == "S"}
    book_syms = set(meta["symbols"])
    first, last = meta["first"], meta["last"]

    by_symday = defaultdict(list)
    for r in rows:
        by_symday[(r["sym"], r["day"])].append(r)

    off_universe = {k: e for k, e in S.items() if e.symbol not in book_syms}
    in_universe = {k: e for k, e in S.items() if e.symbol in book_syms}
    outside_window = {k: e for k, e in in_universe.items()
                       if (e.symbol, e.date) not in by_symday}
    has_rows = {k: e for k, e in in_universe.items()
                if (e.symbol, e.date) in by_symday}
    traded = {k: e for k, e in has_rows.items()
              if any(r["traded"] for r in by_symday[(e.symbol, e.date)])}
    the_172 = {k: e for k, e in has_rows.items() if k not in traded}

    return {
        "meta": meta, "book_syms": book_syms, "first": first, "last": last,
        "by_symday": by_symday, "S": S, "off_universe": off_universe,
        "outside_window": outside_window, "has_rows": has_rows,
        "traded": traded, "the_172": the_172,
    }


# ------------------------------------------------------------------- replay

def restricted_replay(target_syms, target_days_by_sym, days=760):
    """g4_dropped_s's own instrumentation, `simulate_day` called only on the
    days this script needs. Builds correct trailing HTF bias by walking each
    symbol's FULL archive (cheap: cached CSVs), but skips the expensive
    detect-and-grade pass on every day outside the target set."""
    g4.install_patches()
    last = max((g4.archive_days(s) or ["1970-01-01"])[-1] for s in target_syms)
    start = (date.fromisoformat(last) - timedelta(days=days)).isoformat()
    window = sorted({d for s in target_syms for d in g4.archive_days(s) if d >= start})
    print("g118 replay: %d symbols, qqq window %d sessions %s..%s"
          % (len(target_syms), len(window), window[0], window[-1]))
    t0 = time.time()
    qqq_brk = g4.qqq_level_breaks(window)
    print("  qqq_level_breaks: %.1fs" % (time.time() - t0))

    n_sim = 0
    for si, sym in enumerate(target_syms, 1):
        t1 = time.time()
        day_bars, hourly = {}, []
        for d in [x for x in g4.archive_days(sym) if x >= start]:
            try:
                bars = g4.pf.fetch_day(sym, d)
            except Exception:
                continue
            if not bars:
                continue
            r = g4.pf.rth(bars)
            if len(r) < 30:
                continue
            day_bars[d] = (bars, r)
            hourly += g4.hourly_from_1m(d, r)
        prev = None
        wanted = target_days_by_sym.get(sym, set())
        for d in sorted(day_bars):
            bars, rth = day_bars[d]
            if prev:
                _, prth = day_bars[prev]
                pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
                pdo, pdc = prth[0].open, prth[-1].close
            else:
                pdh = pdl = pdo = pdc = None
            pmh, pml = g4.pf.premarket_hi_lo(bars)
            g4.CURRENT["sym"], g4.CURRENT["day"] = sym, d
            if d in wanted:
                g4.simulate_day(sym, d, rth, pdh, pdl, g4.htf_bias_for(hourly, d),
                                 pmh, pml, pdo, pdc, qqq=qqq_brk.get(d))
                n_sim += 1
            prev = d
        print("  [%d/%d] %s: %d archived days, %d simulated, %.1fs"
              % (si, len(target_syms), sym, len(day_bars), len(wanted), time.time() - t1))
    print("g118 replay: %d simulate_day calls, %d branch keys, %.1fs total"
          % (n_sim, len(g4.BRANCHES), time.time() - t0))
    return {k: v for k, v in g4.BRANCHES.items()}


# ------------------------------------------------------------ the -1R/2R sim

def counterfactual(rth_by_symday, sym, day, et, entry, stop, direction):
    """Entry = the row's own close fill. Stop fires on a CLOSE beyond it.
    Target fires on an intrabar touch, checked first within a bar (this
    project has no data to order intrabar events the other way). Unresolved
    by the last archived bar of the session exits at that close. R clipped to
    [-1, +2] -- a "-1R stop" that stops you out worse than -1R is not the
    stop this counterfactual was asked for."""
    rth = rth_by_symday.get((sym, day))
    if not rth:
        return None
    idx = next((i for i, c in enumerate(rth) if c.timestamp[:5] == et), None)
    if idx is None or idx + 1 >= len(rth):
        return None
    is_long = direction == "call"
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    target = entry + 2 * risk if is_long else entry - 2 * risk
    for c in rth[idx + 1:]:
        if is_long:
            if c.high >= target:
                return {"r": 2.0, "out": "win", "exit_et": c.timestamp[:5]}
            if c.close <= stop:
                return {"r": -1.0, "out": "loss", "exit_et": c.timestamp[:5]}
        else:
            if c.low <= target:
                return {"r": 2.0, "out": "win", "exit_et": c.timestamp[:5]}
            if c.close >= stop:
                return {"r": -1.0, "out": "loss", "exit_et": c.timestamp[:5]}
    last = rth[-1]
    raw = (last.close - entry) / risk if is_long else (entry - last.close) / risk
    r = max(-1.0, min(2.0, raw))
    out = "win" if r > 1e-9 else ("loss" if r < -1e-9 else "scratch")
    return {"r": round(r, 4), "out": out, "exit_et": last.timestamp[:5]}


# ------------------------------------------------------------- classification

def opposed(bias, is_long):
    return bias in ("bullish", "bearish") and (bias == "bullish") != is_long


_CAP_RE = re.compile(r"\[capped C: ([^\]]+)\]")


def classify(row, branches):
    """(gate_label, bucket) for ONE candidate row. bucket is DETECTION_MISS
    (never applicable here -- every row IS a generated candidate) or
    GATE_KILL, kept as a field so the aggregate table can filter on it."""
    st = row["status"]
    if st == "halted":
        return G_HALT, GATE_KILL
    if st == "fired":
        m = _CAP_RE.search(row.get("reason", ""))
        if m:
            return "%s (%s)" % (G_CcapS, m.group(1)), GATE_KILL
        return G_Cfloor, GATE_KILL
    if st == "skipped_tight_stop":
        if (row["setup"] != "one_candle_rule" and row["entry"]
                and abs(row["entry"] - row["stop"]) / abs(row["entry"]) * 100 < MIN_STOP_PCT):
            return G_MINPCT, GATE_KILL
        return G_MINVI, GATE_KILL
    if st == "skipped_d":
        is_long = row["dir"] == "call"
        if opposed(row.get("bias"), is_long):
            return G_BIAS, GATE_KILL
        key = g4.keyof(row)
        recs = branches.get(key)
        if not recs:
            return G_UNMATCHED, GATE_KILL
        rec = recs[0]
        b = rec["branch"]
        if row["setup"] == "one_candle_rule":
            if b == "colour_gate":
                return G_COLOUR, GATE_KILL
            if rec["risk"] is not None and rec["risk"] < 0.50:
                return G_OCRMIN, GATE_KILL
            if rec["risk"] is not None and rec["close"] and rec["risk"] / rec["close"] > 0.004:
                return G_OCRWIDE, GATE_KILL
            return G_UNMATCHED, GATE_KILL
        if b == "colour_gate":
            return G_COLOUR, GATE_KILL
        if rec["minstop"]:
            return G_BNRMIN, GATE_KILL
        if b == "never_touched_level":
            return G_NEVER, GATE_KILL
        return G_UNMATCHED, GATE_KILL
    return "unknown status: %s" % st, GATE_KILL


# tier used to pick each day's BEST candidate -- closest to actually trading
_TIER = {"halted": 0, "fired": 1, "skipped_tight_stop": 2, "skipped_d": 3}


def best_candidate(rows):
    return sorted(rows, key=lambda r: (_TIER.get(r["status"], 9), r["et"]))[0]


# --------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cache", default=CACHE)
    ap.add_argument("--cache-only", action="store_true")
    ap.add_argument("--days", type=int, default=760)
    args = ap.parse_args()

    T = build_target_sets()
    the_172 = T["the_172"]
    by_symday = T["by_symday"]

    print("S days: %d | off-universe: %d | outside window: %d | in book: %d "
          "(traded %d, the-172 %d)"
          % (len(T["S"]), len(T["off_universe"]), len(T["outside_window"]),
             len(T["has_rows"]), len(T["traded"]), len(the_172)))
    if len(the_172) != 172:
        print("*** COUNT DID NOT MATCH THE MORNING REPORT'S 172 -- see the "
              "'count check' section of the .md for why ***")

    target_syms = sorted({e.symbol for e in the_172.values()})
    target_days_by_sym = defaultdict(set)
    for e in the_172.values():
        target_days_by_sym[e.symbol].add(e.date)

    if args.cache_only and os.path.exists(args.cache):
        branches = json.loads(Path(args.cache).read_text(encoding="utf-8"))
        print("branch cache: %d keys (reused)" % len(branches))
    else:
        branches = restricted_replay(target_syms, target_days_by_sym, days=args.days)
        Path(args.cache).write_text(json.dumps(branches, separators=(",", ":")),
                                     encoding="utf-8")
        print("branch cache: %d keys -> %s" % (len(branches), args.cache))

    # ---- fetch RTH bars for the counterfactual sim (reuses the cached CSVs
    # the replay above already pulled through polygon_feed's cache-first read)
    rth_by_symday = {}
    for sym in target_syms:
        for d in target_days_by_sym[sym]:
            try:
                bars = g4.pf.fetch_day(sym, d)
            except Exception:
                continue
            rth_by_symday[(sym, d)] = g4.pf.rth(bars)

    # ---- classify every candidate row + price the counterfactual ----------
    all_rows_out = []
    day_rows = {}   # key -> [decorated rows]
    for k, e in the_172.items():
        rows = sorted(by_symday[(e.symbol, e.date)], key=lambda r: r["et"])
        decorated = []
        for r in rows:
            gate, bucket = classify(r, branches)
            cf = counterfactual(rth_by_symday, r["sym"], r["day"], r["et"],
                                 r["entry"], r["stop"], r["dir"])
            dr = dict(r)
            dr["gate"] = gate
            dr["bucket"] = bucket
            dr["cf_r"] = cf["r"] if cf else None
            dr["cf_out"] = cf["out"] if cf else None
            dr["cf_exit_et"] = cf["exit_et"] if cf else None
            decorated.append(dr)
        day_rows[k] = decorated
        all_rows_out.extend(decorated)

    # per-day best-candidate attribution
    day_verdict = {}
    for k, rows in day_rows.items():
        b = best_candidate(rows)
        day_verdict[k] = b

    # ---- join-rate check on the skipped_d subset (same discipline as g4) --
    # 'gate' was already resolved by classify() above using this exact
    # logic; re-read it rather than recomputing so the two can never disagree.
    skd = [r for r in all_rows_out if r["status"] == "skipped_d"]
    skd_bias = [r for r in skd if r["gate"] == G_BIAS]
    skd_needs_replay = [r for r in skd if r["gate"] != G_BIAS]
    skd_matched = sum(1 for r in skd_needs_replay if r["gate"] != G_UNMATCHED)
    skd_unmatched = len(skd_needs_replay) - skd_matched

    write_outputs(T, day_rows, day_verdict, all_rows_out,
                  skd, skd_bias, skd_needs_replay, skd_matched, skd_unmatched)


# ------------------------------------------------------------------- output

def agg(rows):
    rs = [r["cf_r"] for r in rows if r["cf_r"] is not None]
    if not rs:
        return 0, None, None
    wins = sum(1 for r in rs if r > 1e-9)
    dec = [r for r in rs if abs(r) > 1e-9]
    wr = 100.0 * wins / len(dec) if dec else 0.0
    return len(rs), round(statistics.fmean(rs), 4), round(wr, 1)


def write_outputs(T, day_rows, day_verdict, all_rows_out, skd, skd_bias,
                   skd_needs_replay, skd_matched, skd_unmatched):
    the_172 = T["the_172"]

    Path(OUT_ROWS).write_text(
        json.dumps({
            "generated_from": os.path.basename(BOOK_PATH),
            "book_meta": T["meta"],
            "n_S": len(T["S"]), "n_off_universe": len(T["off_universe"]),
            "n_outside_window": len(T["outside_window"]),
            "n_has_rows": len(T["has_rows"]), "n_traded": len(T["traded"]),
            "n_the_172": len(the_172),
            "days": {
                k: {"symbol": e.symbol, "date": e.date,
                    "best_candidate_gate": day_verdict[k]["gate"],
                    "candidates": day_rows[k]}
                for k, e in the_172.items()
            },
        }, indent=1, default=str),
        encoding="utf-8")
    print("wrote %s" % OUT_ROWS)

    # ---- gate -> count of DAYS killed (best candidate), mean R, win count -
    by_gate_days = defaultdict(list)
    for k, v in day_verdict.items():
        by_gate_days[v["gate"]].append(v)
    gate_rows = []
    for gate, vs in sorted(by_gate_days.items(), key=lambda kv: -len(kv[1])):
        n, mean_r, wr = agg(vs)
        n_priced = n
        wins = sum(1 for v in vs if v["cf_r"] is not None and v["cf_r"] > 1e-9)
        gate_rows.append((gate, len(vs), n_priced,
                           "%+.3f" % mean_r if mean_r is not None else "n/a",
                           wins,
                           "%.1f%%" % wr if wr is not None else "n/a"))

    # ---- setup-type split ---------------------------------------------
    n_ocr_or_84 = sum(
        1 for k in the_172
        if any(r["setup"] in ("one_candle_rule", "reentry_84_rule") for r in day_rows[k]))
    n_ocr = sum(1 for k in the_172
                if any(r["setup"] == "one_candle_rule" for r in day_rows[k]))
    n_84 = sum(1 for k in the_172
               if any(r["setup"] == "reentry_84_rule" for r in day_rows[k]))
    n_confluence = sum(1 for k in the_172
                        if any(r.get("confluence") == "yes" for r in day_rows[k]))
    n_br_only = sum(1 for k in the_172
                     if all(r["setup"] == "break_and_retest" for r in day_rows[k]))

    setup_of_best = Counter()
    for k, v in day_verdict.items():
        setup_of_best[v["setup"]] += 1

    # ---- best-candidate setup breakdown --------------------------------
    L = []
    A = L.append
    A("# G118 -- the 172 gate kill")
    A("")
    A("Generated by `research/g118_172_gate_kills.py` from "
      "`research/marks_pool.canonical_pool()` (%d S days) and "
      "`research/bt2y_trades_retest_on.json` (%s..%s, %d sessions, %d symbols)."
      % (len(T["S"]), T["first"], T["last"], T["meta"]["sessions"], len(T["book_syms"])))
    A("")
    A("## 1. The 227 split, rebuilt")
    A("")
    A("| bucket | days | definition |")
    A("|---|---:|---|")
    A("| off-universe | %d | symbol not among the book's %d symbols |"
      % (len(T["off_universe"]), len(T["book_syms"])))
    A("| outside the session window | %d | in-universe, but zero signal rows "
      "exist for that exact day anywhere in the book |" % len(T["outside_window"]))
    A("| **the 172** | **%d** | in-universe, at least one candidate row "
      "exists, none is `traded: true` |" % len(the_172))
    A("| (for reference) traded | %d | in-universe, has a `traded: true` row "
      "-- not part of the 227 |" % len(T["traded"]))
    total_227 = len(T["off_universe"]) + len(T["outside_window"]) + len(the_172)
    A("")
    A("Off-universe + outside-window + the-172 = %d. Morning report says 227."
      % total_227)
    if total_227 != 227 or len(the_172) != 172:
        A("")
        A("**COUNT MISMATCH -- read before trusting anything below.** This "
          "run got %d off-universe / %d outside-window / %d in-the-172 "
          "against the report's 11 / 44 / 172. `marks_pool.canonical_pool()` "
          "is re-read live every run (`research/marks/*.jsonl` grows), so a "
          "mark file written since the report was generated is the most "
          "likely cause -- check `git log -1 --format=%%ci research/marks` "
          "against the report's own generation date before assuming this "
          "script is wrong."
          % (len(T["off_universe"]), len(T["outside_window"]), len(the_172)))
    else:
        A("")
        A("Matches the morning report exactly: 11 / 44 / 172.")
    A("")
    A("`traded` here is not \"first signal of the day\" -- it is "
      "`status==\"fired\" and grade != \"C\"` "
      "(`backtest_week.SimTrade.counted`). A `C` that never won the day's "
      "with-trend floor promotion is `alert`, not `traded`, which is why "
      "the 172 is not all `X`-grade misses -- see the gate table below.")

    A("")
    A("## 2. Detection miss vs. gate kill")
    A("")
    A("Every one of the 172 has at least one candidate row -- by "
      "construction, a day with zero rows is in the 44 outside-window bucket, "
      "not here. So within the 172 there is no \"no candidate generated\" "
      "day; the detection-miss / gate-kill line sits ABOVE the 172, at the "
      "227 level:")
    A("")
    A("| | days | what it means |")
    A("|---|---:|---|")
    A("| detection miss | %d | off-universe (%d) + outside window (%d) -- "
      "no session replayed, so no candidate could exist |"
      % (len(T["off_universe"]) + len(T["outside_window"]),
         len(T["off_universe"]), len(T["outside_window"])))
    A("| gate kill | %d | the 172 -- a candidate existed and something in "
      "the engine killed or capped it |" % len(the_172))
    A("")
    A("`GOVERNOR_S_CAP` does not exist anywhere in this codebase (checked: "
      "`grep -rn GOVERNOR_S_CAP` over every `.py`/`.md` file, zero hits). The "
      "real mechanism closest to that name is the portfolio-wide loss-halt "
      "below -- it is a cap, just not a per-symbol S cap.")

    A("")
    A("## 3. Gate that killed each day's BEST candidate")
    A("")
    A("\"Best candidate\" = the one closest to actually trading: rank "
      "`halted` (was grade A/B, blocked only by another symbol's losses) "
      "above `fired` (reached grade C) above `skipped_tight_stop` above "
      "`skipped_d` (never left X); ties broken by earliest time. One row "
      "per day.")
    A("")
    A("| gate | S days killed | n priced | mean R (−1R/2R counterfactual) | "
      "winners | win rate |")
    A("|---|---:|---:|---:|---:|---:|")
    for gate, n, n_priced, mean_r, wins, wr in gate_rows:
        A("| %s | %d | %d | %s | %d | %s |" % (gate, n, n_priced, mean_r, wins, wr))
    n_all, mean_all, wr_all = agg(list(day_verdict.values()))
    A("")
    A("**All 172, one row each: n=%d priced, mean R %+.3f, win rate %s%%.**"
      % (n_all, mean_all if mean_all is not None else 0.0, wr_all))
    A("")
    A("Read the mean-R column as \"was the gate right to kill it,\" not as a "
      "trading result -- n per gate is thin (see counts above), the "
      "counterfactual is the plain −1R/2R version Austin asked for (no "
      "ladder, no −1.25R floor, no breakeven), and every row here overlaps "
      "with every other dropped-S measurement already in this repo "
      "(`g4_dropped_s.md`, `g85_recall_honest.md`) on the SAME underlying "
      "signals, just a different denominator (his S marks, not the whole "
      "S-graded book).")

    A("")
    A("## 4. Setup type")
    A("")
    A("Counts any candidate of that setup appearing among the day's rows "
      "(a day can have more than one setup type fire).")
    A("")
    A("| setup fired on the day | S days |")
    A("|---|---:|")
    A("| break-and-retest only (no OCR, no 84%%, no confluence) | %d |" % n_br_only)
    A("| BR+OCR confluence tag present | %d |" % n_confluence)
    A("| one-candle-rule (OCR) candidate present | %d |" % n_ocr)
    A("| 84%% re-entry candidate present | %d |" % n_84)
    A("| **OCR or 84%% candidate present (either)** | **%d** |" % n_ocr_or_84)
    A("")
    A("Setup of the day's BEST candidate specifically (the row the gate "
      "table above actually charges):")
    A("")
    A("| setup | days |")
    A("|---|---:|")
    for s, n in setup_of_best.most_common():
        A("| %s | %d |" % (s, n))

    A("")
    A("## 5. Replay join-rate (skipped_d subset only)")
    A("")
    A("HTF bias opposed is recomputed straight off the row (`bias` field is "
      "the exact `htf_bias` `grade_trade` saw) -- no replay needed for it. "
      "Everything else on the X-graded rows needs candle OHLC, which the "
      "exported book does not carry, so it goes through the restricted "
      "`g4_dropped_s` replay.")
    A("")
    A("| | rows |")
    A("|---|---:|")
    A("| skipped_d rows across the 172's candidates | %d |" % len(skd))
    A("| ...attributed straight from `bias` (no replay needed) | %d |" % len(skd_bias))
    A("| ...needing the replay | %d |" % len(skd_needs_replay))
    A("| ...matched | %d |" % skd_matched)
    A("| ...unmatched (`%s`) | %d |" % (G_UNMATCHED, skd_unmatched))

    Path(OUT_MD).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote %s (%d lines)" % (OUT_MD, len(L)))


if __name__ == "__main__":
    main()
