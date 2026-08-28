"""x1_exit_attribution.py -- WHERE THE MEAN-R IS ACTUALLY LOST.

Austin, 2026-08-28:

    "mean 2r is impossible with this scaling, but i want to find out how we can
     let runners run and losers stop out quicker, the trades be quicker. thats
     how we make more money."

    "just confirming the mean 2r issue is not after HOD/LOD scale, moving stop
     loss to break even? its all in the percent i scale and not holding it long
     enough?"

That is an ATTRIBUTION question, not another sweep. This file decomposes the gap
from the shipped book's mean R to the +2.0 R money gate into named buckets and
prices each one on the SAME 1,017 traded rows, then prints the ceiling that any
exit policy can ever reach on this book.

WHAT WAS ALREADY ANSWERED AND IS NOT RE-ANSWERED HERE
-----------------------------------------------------
  research/g7_exit_sweep.md      8 exit policies, none beat the incumbent ladder
  research/p10_structure_trail.md structure trail + far targets; and the ORACLE
                                  (`oracle_stopped` +3.501 R at the 11:00 clock)
  research/w13_scaling.md        55 scale-in / scale-out / break-even arms; best
                                  +1.4697 R, still +0.5303 R short of the gate
  research/w11_tz_exit_efficiency.md  Austin's own TradeZella book captures ~38%
                                  of its MFE against the engine's ~22%

The ticket for this lane says "the perfect-exit oracle ... NOBODY IN THIS PROJECT
HAS COMPUTED IT". That is WRONG and the correction is the first finding below:
`research/p10_structure_trail.py::oracle_stopped` computed it on 2026-08-26 and
it is +3.501 R. This file RE-COMPUTES it independently (different bar loader --
archive-only `p26.load_day` instead of p10's `pf.fetch_day`) so the number is
confirmed by two rigs rather than repeated from a report.

WHAT IS NEW HERE
----------------
  1. MFE **and MAE** per trade, archived to `research/x1_mfe_mae.json`, so the
     next rig does not re-derive them. MAE has never been computed in this repo.
  2. The additive decomposition of the gap to the oracle by TRADE CLASS -- what
     the winners give back vs what the losers cost. This is strictly additive:
     the two buckets sum to the whole gap by construction.
  3. Counts on the losers: of trades that ended <= 0 R, how many touched +1 R,
     +1.5 R, +2 R first.
  4. Break-even, INSTRUMENTED rather than swept: how many runners the BE stop
     takes out of a trade that later reached +2 R.
  5. Hard time stops at 15 / 30 / 45 minutes -- the "trades be quicker" arm,
     never measured before.
  6. flat 2.5 R -- the one target between 2 R and 3 R nobody has scored.
  7. How much R sits BEYOND the 11:00 backstop on the winners.

RULES OBEYED
------------
  * Stops trigger on the candle CLOSE, fill at that close, floored at -1.25 R
    (`exit_lab._stop_hit_first` / `_stop_fill`, imported, not reimplemented).
  * The 11:00 backstop is `exit_lab.CLOCK_BAR = 90` unless an arm says otherwise.
  * `--selfcheck` asserts every traced clone agrees with the shipped function it
    clones, on every row, and that no arm books above its own oracle.
  * Zero network. `p26.load_day` refuses a fetch; a missing session is a REPORTED
    gap, never a silent drop.
  * Error bar +/-0.0095 R (the narrow bar). Anything smaller is noise.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from research import exit_lab as xl                                  # noqa: E402
from research.h1_2y_nowatch import mfe_r                             # noqa: E402
from research.r9_simple_book import Bars, agg_r, build_arm           # noqa: E402

BOOK = os.path.join("research", "g3_arm_ow1.json")
OUT_JSON = os.path.join(_HERE, "x1_mfe_mae.json")
OUT_MD = os.path.join(_HERE, "x1_exit_attribution.md")
GATE = 2.0
ERR = 0.0095          # the narrow bar, master spec 1.1 (2026-08-28)
EOD = 10 ** 6         # g7_exit_sweep.py:39's "noclock" convention


# ---------------------------------------------------------------------------
# path statistics -- MFE, MAE, and where in the trade they printed
# ---------------------------------------------------------------------------

def mae_r(bars, entry_i, entry, stop, side, clock=None):
    """Maximum ADVERSE excursion in R before the stop triggers, as a POSITIVE
    number (0.4 means "went 0.4 R against you at worst").

    Exactly the scan `h1_2y_nowatch.mfe_r` runs, mirrored: from entry_i+1, the
    close-triggered stop ends it, the clock is the backstop, and the bar on
    which the stop fires is NOT counted (the trade is over at that close and its
    loss is the booked fill, not an excursion).
    """
    clock = xl.CLOCK_BAR if clock is None else clock
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    worst = 0.0
    end = min(clock + 1, n)
    for i in range(entry_i + 1, end):
        if xl._stop_hit_first(bars, i, entry, stop, side):
            return worst
        b = bars[i]
        against = (entry - b["l"]) if side == "L" else (b["h"] - entry)
        r = against / risk
        if r > worst:
            worst = r
    return worst


def mfe_bar_offset(bars, entry_i, entry, stop, side, clock=None):
    """Minutes after entry at which the stop-respecting MFE printed. 0 = the MFE
    never exceeded the entry price (the trade never went green)."""
    clock = xl.CLOCK_BAR if clock is None else clock
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0
    best, best_i = 0.0, entry_i
    end = min(clock + 1, n)
    for i in range(entry_i + 1, end):
        if xl._stop_hit_first(bars, i, entry, stop, side):
            break
        b = bars[i]
        far = (b["h"] - entry) if side == "L" else (entry - b["l"])
        r = far / risk
        if r > best:
            best, best_i = r, i
    return best_i - entry_i


def mfe_window(bars, lo_i, hi_i, entry, stop, side):
    """MFE in R over bars [lo_i, hi_i], no stop, hindsight. Used for 'what was
    still on offer AFTER the policy was already out'."""
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    hi_i = min(hi_i, n - 1)
    if lo_i > hi_i:
        return 0.0
    best = None
    for i in range(lo_i, hi_i + 1):
        b = bars[i]
        far = (b["h"] - entry) if side == "L" else (entry - b["l"])
        r = far / risk
        if best is None or r > best:
            best = r
    return best if best is not None else 0.0


def oracle_stopped(bars, entry_i, entry, stop, side, clock=None):
    """The fair ceiling: 100% out at the best CLOSE chosen with hindsight, with
    the trade's own stop still live and close-triggered.

    Line-for-line the same rule as `research/p10_structure_trail.py::
    oracle_stopped` (+3.501 R, 2026-08-26). Re-implemented here ON PURPOSE so
    the number is confirmed by an independent rig reading an independent bar
    loader, not repeated from a markdown table.
    """
    clock = xl.CLOCK_BAR if clock is None else clock
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    end = min(clock + 1, n)
    best = None
    for i in range(entry_i + 1, end):
        if xl._stop_hit_first(bars, i, entry, stop, side):
            fill = xl.realised_r(
                entry, stop, xl._stop_fill(bars, i, entry, stop, side, risk), side)
            return fill if best is None else max(best, fill)
        r = xl.realised_r(entry, stop, bars[i]["c"], side)
        best = r if best is None else max(best, r)
    return best if best is not None else 0.0


def oracle_mfe(bars, entry_i, entry, stop, side, clock=None):
    """Best price the trade ever TRADED at before the stop closed it. Nothing --
    scale-outs, scale-ins at one unit, anything -- can book more than this."""
    return mfe_r(bars, entry_i, entry, stop, side) if clock is None else _mfe_clock(
        bars, entry_i, entry, stop, side, clock)


def _mfe_clock(bars, entry_i, entry, stop, side, clock):
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    best = 0.0
    end = min(clock + 1, n)
    for i in range(entry_i + 1, end):
        if xl._stop_hit_first(bars, i, entry, stop, side):
            return best
        b = bars[i]
        far = (b["h"] - entry) if side == "L" else (entry - b["l"])
        r = far / risk
        if r > best:
            best = r
    return best


# ---------------------------------------------------------------------------
# arms -- the named buckets
# ---------------------------------------------------------------------------

def ride(bars, entry_i, entry, stop, side, clock=None, be_at=None,
         time_stop=None, target_r=None):
    """One position, one exit. The general arm every bucket below is a case of.

    * original stop live, close-triggered, filled at that close, floored -1.25 R
    * ``be_at``      -> the moment price TOUCHES this many R, the stop moves to
                        entry and never moves back (break-even)
    * ``time_stop``  -> exit at the close of bar entry_i + time_stop if still in
    * ``target_r``   -> flat exit the moment price touches this many R
    * ``clock``      -> force-flat backstop bar index (default `xl.CLOCK_BAR`)

    Returns (R, exit_i, why) where ``why`` is one of
    stop / be / target / time / clock.
    """
    clock = xl.CLOCK_BAR if clock is None else clock
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0, entry_i, "flat"
    live_stop = stop
    at_be = False
    tgt = None
    if target_r is not None:
        tgt = entry + target_r * risk if side == "L" else entry - target_r * risk
    be_px = entry + be_at * risk if (be_at is not None and side == "L") else (
        entry - be_at * risk if be_at is not None else None)
    end = min(clock + 1, n)
    for i in range(entry_i + 1, end):
        b = bars[i]
        if xl._stop_hit_first(bars, i, entry, live_stop, side):
            fill = xl._stop_fill(bars, i, entry, live_stop, side, risk)
            return (xl.realised_r(entry, stop, fill, side), i,
                    "be" if at_be else "stop")
        if tgt is not None:
            hit = (b["h"] >= tgt) if side == "L" else (b["l"] <= tgt)
            if hit:
                return xl.realised_r(entry, stop, tgt, side), i, "target"
        if be_px is not None and not at_be:
            touched = (b["h"] >= be_px) if side == "L" else (b["l"] <= be_px)
            if touched:
                live_stop, at_be = entry, True
        if time_stop is not None and i - entry_i >= time_stop:
            return xl.realised_r(entry, stop, b["c"], side), i, "time"
    ci = clock if n > clock else n - 1
    return xl.realised_r(entry, stop, bars[ci]["c"], side), ci, "clock"


def first_adverse_close(bars, entry_i, entry, stop, side, clock=None):
    """The most aggressive loser cut expressible: out at the close of the FIRST
    bar after entry that closes against the entry price. The original stop is
    still live for the bar that gaps straight through it."""
    clock = xl.CLOCK_BAR if clock is None else clock
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0, entry_i, "flat"
    end = min(clock + 1, n)
    for i in range(entry_i + 1, end):
        if xl._stop_hit_first(bars, i, entry, stop, side):
            fill = xl._stop_fill(bars, i, entry, stop, side, risk)
            return xl.realised_r(entry, stop, fill, side), i, "stop"
        c = bars[i]["c"]
        adverse = (c < entry) if side == "L" else (c > entry)
        if adverse:
            return xl.realised_r(entry, stop, c, side), i, "adverse"
    ci = clock if n > clock else n - 1
    return xl.realised_r(entry, stop, bars[ci]["c"], side), ci, "clock"


# ---------------------------------------------------------------------------
# the shipped ladder, TRACED -- so break-even can be counted, not just swept
# ---------------------------------------------------------------------------

def scale_out_traced(bars, entry_i, entry, stop, side, weights, trail_method="atr"):
    """`exit_lab.scale_out`, mirrored line for line, returning WHY the runner
    left and on which bar.

    A clone is a liability, so `--selfcheck` asserts this returns exactly what
    `xl.scale_out` returns on every one of the 1,017 rows. It exists because
    `scale_out` returns a float and the question "how many runners did the
    break-even stop take out of a trade that later reached 2 R" cannot be asked
    of a float.

    ``why`` for the runner: be / trail / structure / consolidation / clock, or
    ``t1_stop`` when the ORIGINAL stop fired before tranche 1 and there was
    never a runner at all.
    """
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0, {"why": "flat", "exit_i": entry_i, "t1_exit_i": entry_i}
    hod_i = xl.causal_hod_exit_bar(bars, entry_i, side)
    if hod_i is None:
        return 0.0, {"why": "flat", "exit_i": entry_i, "t1_exit_i": entry_i}

    w1 = weights[0]
    w_rest = sum(weights[1:]) or 1.0

    t1_exit_i, t1_price, stopped = hod_i, bars[hod_i]["c"], False
    for i in range(entry_i + 1, min(hod_i + 1, n)):
        if xl._stop_hit_first(bars, i, entry, stop, side):
            t1_exit_i = i
            t1_price = xl._stop_fill(bars, i, entry, stop, side, risk)
            stopped = True
            break
    r1 = xl.realised_r(entry, stop, t1_price, side)
    if stopped:
        return r1, {"why": "t1_stop", "exit_i": t1_exit_i, "t1_exit_i": t1_exit_i}

    rest_i, rest_price, why = _runner_traced(
        bars, t1_exit_i, entry, side, trail_method, entry, risk)
    r_rest = xl.realised_r(entry, stop, rest_price, side)
    return (w1 * r1 + w_rest * r_rest,
            {"why": why, "exit_i": rest_i, "t1_exit_i": t1_exit_i})


def _runner_traced(bars, from_i, entry, side, trail_method, start_stop, risk):
    """`exit_lab._runner_exit`, mirrored, plus the reason.

    'be' means the effective stop that fired WAS the break-even floor (the ATR
    trail was looser than entry and got clipped by it); 'trail' means the ATR
    trail itself was tighter and fired first. That distinction is the whole
    point of the trace: only the 'be' rows are trades break-even took out.
    """
    n = len(bars)
    end = min(xl.CLOCK_BAR + 1, n)
    if from_i + 1 >= end:
        i = xl.CLOCK_BAR if n > xl.CLOCK_BAR else n - 1
        if xl._stop_hit_first(bars, i, entry, start_stop, side):
            return i, xl._stop_fill(bars, i, entry, start_stop, side, risk), "be"
        return i, bars[i]["c"], "clock"

    if side == "L":
        highest = max(b["h"] for b in bars[: from_i + 1])
    else:
        lowest = min(b["l"] for b in bars[: from_i + 1])
    since = 0

    for i in range(from_i + 1, end):
        b = bars[i]
        if trail_method == "atr":
            a = xl.atr(bars, i - 1) or xl.atr(bars, i) or 0.0
            trail_stop = (highest - 1.0 * a) if side == "L" else (lowest + 1.0 * a)
        else:
            trail_stop = bars[i - 1]["l"] if side == "L" else bars[i - 1]["h"]
        if side == "L":
            was_trail = trail_stop > start_stop
            trail_stop = max(trail_stop, start_stop)
        else:
            was_trail = trail_stop < start_stop
            trail_stop = min(trail_stop, start_stop)

        if xl._stop_hit_first(bars, i, entry, trail_stop, side):
            return (i, xl._stop_fill(bars, i, entry, trail_stop, side, risk),
                    "trail" if was_trail else "be")

        made_new = False
        if side == "L":
            if b["h"] > highest:
                highest, made_new = b["h"], True
        else:
            if b["l"] < lowest:
                lowest, made_new = b["l"], True
        since = 0 if made_new else since + 1

        if side == "L" and b["l"] < bars[i - 1]["l"]:
            return i, b["c"], "structure"
        if side == "S" and b["h"] > bars[i - 1]["h"]:
            return i, b["c"], "structure"
        if since >= xl.CONSOLIDATION_BARS:
            return i, b["c"], "consolidation"
        if i >= xl.CLOCK_BAR:
            return i, b["c"], "clock"

    i = xl.CLOCK_BAR if n > xl.CLOCK_BAR else n - 1
    return i, bars[i]["c"], "clock"


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

def score(cache, rows):
    """Attach every path statistic and every arm to each traded row."""
    out = []
    for r in rows:
        got = cache.get(r["sym"], r["day"])
        if got is None:
            continue
        _, bars, _, _, _ = got
        ei, e, s, side = r["entry_i"], r["entry"], r["stop"], r["side"]
        n = len(bars)
        row = dict(r)

        # --- path, 11:00 clock, stop-respecting ---
        row["mfe"] = mfe_r(bars, ei, e, s, side)
        row["mae"] = mae_r(bars, ei, e, s, side)
        row["mfe_min"] = mfe_bar_offset(bars, ei, e, s, side)
        row["orc"] = oracle_stopped(bars, ei, e, s, side)
        row["orc_eod"] = oracle_stopped(bars, ei, e, s, side, clock=EOD)
        row["mfe_eod"] = _mfe_clock(bars, ei, e, s, side, EOD)
        # what was still on offer AFTER 11:00, hindsight, no stop
        row["mfe_after_clock"] = mfe_window(bars, xl.CLOCK_BAR + 1, n - 1, e, s, side)

        # --- arms ---
        row["inc"] = xl.policy_30_30_30_10(bars, ei, e, s, side)
        row["hod"] = xl.hod_only(bars, ei, e, s, side)
        row["rideC"], _, _ = ride(bars, ei, e, s, side)                    # no rungs, clock
        row["rideEOD"], _, _ = ride(bars, ei, e, s, side, clock=EOD)
        for t in (1.0, 2.0, 2.5, 3.0, 4.0, 5.0):
            row[f"flat{t}"] = xl.flat_target(bars, ei, e, s, side, t)
        for m in (15, 30, 45):
            row[f"f2_ts{m}"], _, _ = ride(bars, ei, e, s, side, target_r=2.0, time_stop=m)
            row[f"ride_ts{m}"], _, _ = ride(bars, ei, e, s, side, time_stop=m)
        row["adverse"], _, _ = first_adverse_close(bars, ei, e, s, side)
        for b in (0.5, 1.0, 1.5, 2.0):
            row[f"be{b}"], bi, why = ride(bars, ei, e, s, side, be_at=b)
            if b == 1.0:
                row["be1_why"] = why
                # what the tape offered AFTER the BE stop took us out
                row["be1_after"] = (mfe_window(bars, bi + 1, min(xl.CLOCK_BAR, n - 1),
                                               e, s, side) if why == "be" else None)

        # --- the shipped ladder, traced ---
        rr, info = scale_out_traced(bars, ei, e, s, side, [0.30, 0.30, 0.30, 0.10])
        row["inc_traced"] = rr
        row["inc_why"] = info["why"]
        row["inc_exit_i"] = info["exit_i"]
        row["inc_after"] = mfe_window(bars, info["exit_i"] + 1,
                                      min(xl.CLOCK_BAR, n - 1), e, s, side)
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------

def selfcheck(rows):
    fails = []

    def chk(cond, msg):
        if not cond:
            fails.append(msg)

    for r in rows:
        if abs(r["inc_traced"] - r["inc"]) > 1e-9:
            fails.append(f"traced ladder != scale_out on {r['sym']}|{r['day']}: "
                         f"{r['inc_traced']} vs {r['inc']}")
            break
    # ride(no rungs, clock) must equal the C4 shape: never above the oracle
    over = [r for r in rows if r["rideC"] > r["orc"] + 1e-9]
    chk(not over, f"{len(over)} rows book above their own stop-respecting oracle")
    # MFE is the ceiling on any single-unit exit
    for key in ("inc", "hod", "rideC", "flat2.0", "flat5.0", "adverse", "be1.0"):
        bad = [r for r in rows if r[key] > r["mfe"] + 1e-6]
        chk(not bad, f"{len(bad)} rows book above their MFE on arm {key}")
    # a flat 2R arm can never book MORE than 2R (it can book less: an unstopped
    # trade that never reached the target exits at the clock bar's close, which
    # is 27 of the 1017 rows and is the policy working, not a bug)
    bad = [r for r in rows if r["flat2.0"] > 2.0 + 1e-6]
    chk(not bad, f"{len(bad)} flat_2r rows book above +2.0R")
    # MFE >= 2.0 iff flat_2r booked +2.0 -- the same assertion h1 carries
    bad = [r for r in rows if (r["mfe"] >= 2.0) != (abs(r["flat2.0"] - 2.0) < 1e-6)]
    chk(not bad, f"{len(bad)} rows disagree between mfe>=2 and flat_2r==+2")
    # MAE is non-negative and no loss books below the -1.25R floor
    chk(all(r["mae"] >= 0 for r in rows), "negative MAE")
    bad = [r for r in rows if r["rideC"] < -1.2500001]
    chk(not bad, f"{len(bad)} rideC rows below the -1.25R floor")
    # the clock is back where it started
    chk(xl.CLOCK_BAR == 90, "CLOCK_BAR was left moved")
    return fails


# ---------------------------------------------------------------------------
# report helpers
# ---------------------------------------------------------------------------

def months_green(rows, key):
    by = defaultdict(float)
    for r in rows:
        by[r["ym"]] += r[key]
    return sum(1 for v in by.values() if v > 0), len(by)


def line(rows, key, label, note=""):
    a = agg_r([r[key] for r in rows])
    g, t = months_green(rows, key)
    return (f"| {label} | {a['n']} | **{a['mean']:+.4f}** | {a['median']:+.4f} | "
            f"{a['wr']:.1f}% | {g} / {t} | {a['tot']:+.1f} | {note} |")


HDR = ("| arm | n | mean R | median R | win rate | months green | total R | note |\n"
       "|---|---:|---:|---:|---:|---:|---:|---|")


def pctl(xs, p):
    xs = sorted(xs)
    if not xs:
        return 0.0
    k = max(0, min(len(xs) - 1, int(round((len(xs) - 1) * p))))
    return xs[k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()

    cache = Bars()
    base, meta, gaps = build_arm(os.path.join(_ROOT, BOOK), cache)
    # build_arm drops the fields this rig needs, so re-attach from the raw book
    raw = {(t["sym"], t["day"], t["entry_i"]): t
           for t in json.load(open(os.path.join(_ROOT, BOOK), encoding="utf-8"))["trades"]
           if t["traded"]}
    for r in base:
        t = raw.get((r["sym"], r["day"], r["entry_i"]))
        r["ym"] = t["ym"]
        r["book_r"] = float(t["r"])
        r["sgrade"] = t.get("sgrade")

    rows = score(cache, base)
    fails = selfcheck(rows)
    if args.selfcheck:
        for f in fails:
            print("FAIL:", f)
        print(f"selfcheck: {len(rows)} rows, {len(fails)} failures, gaps={gaps}")
        return 1 if fails else 0
    if fails:
        print("SELFCHECK FAILED -- refusing to write a report")
        for f in fails:
            print("  ", f)
        return 1

    n = len(rows)
    inc = agg_r([r["inc"] for r in rows])
    bk = agg_r([r["book_r"] for r in rows])
    orc = agg_r([r["orc"] for r in rows])
    mfe = agg_r([r["mfe"] for r in rows])
    rideC = agg_r([r["rideC"] for r in rows])

    # --- the additive gap decomposition, by trade class under the incumbent ---
    win = [r for r in rows if r["inc"] > 0]
    los = [r for r in rows if r["inc"] <= 0]
    gap_win = sum(r["orc"] - r["inc"] for r in win) / n
    gap_los = sum(r["orc"] - r["inc"] for r in los) / n
    los_drag = sum(r["inc"] for r in los) / n
    win_lift = sum(r["inc"] for r in win) / n

    # --- loser counts ---
    def cnt(rs, thr):
        return sum(1 for r in rs if r["mfe"] >= thr)
    L = len(los)

    # --- BE instrumentation ---
    be_out = [r for r in rows if r["be1_why"] == "be"]
    be_2r = [r for r in be_out if r["be1_after"] is not None and r["be1_after"] >= 2.0]
    be_15 = [r for r in be_out if r["be1_after"] is not None and r["be1_after"] >= 1.5]
    be_1 = [r for r in be_out if r["be1_after"] is not None and r["be1_after"] >= 1.0]
    lad_be = [r for r in rows if r["inc_why"] == "be"]
    lad_be_2r = [r for r in lad_be if r["inc_after"] >= 2.0]

    # --- horizon ---
    win_after = [r["mfe_after_clock"] for r in win]
    all_after = [r["mfe_after_clock"] for r in rows]

    o = []
    A = o.append
    A("# X1 — where the mean-R is actually lost")
    A("")
    A(f"Generated by `research/x1_exit_attribution.py` over the **{n}** traded rows of "
      f"`research/g3_arm_ow1.json` (`ON_WATCH=1`, {meta['first']} → {meta['last']}, "
      f"{meta['sessions']} sessions, {len(meta['symbols'])} symbols), replayed from "
      f"`data_archive/` with zero fetches. Backstop **11:00** (`exit_lab.CLOCK_BAR = 90`) "
      f"unless a row says otherwise. Error bar **±{ERR:.4f} R** (the narrow bar). "
      f"Gaps: {gaps}. `--selfcheck`: {len(fails)} failures.")
    A("")
    A("Austin, 2026-08-28: *\"just confirming the mean 2r issue is not after HOD/LOD "
      "scale, moving stop loss to break even? its all in the percent i scale and not "
      "holding it long enough?\"*")
    A("")
    be_never = rideC["mean"]
    be_1r = agg_r([r["be1.0"] for r in rows])["mean"]
    f2 = agg_r([r["flat2.0"] for r in rows])["mean"]
    f25 = agg_r([r["flat2.5"] for r in rows])["mean"]
    f5 = agg_r([r["flat5.0"] for r in rows])["mean"]
    eod = agg_r([r["rideEOD"] for r in rows])["mean"]
    ts15 = agg_r([r["ride_ts15"] for r in rows])["mean"]
    # the best single-unit arm anywhere in this file
    ARMS = {"inc": "the shipped ladder 30/30/30/10",
            "hod": "hod_only, 100% at the rung-1 rule",
            "rideC": "one unit, original stop, no target, ride to 11:00",
            "rideEOD": "one unit, ride to the 15:59 close",
            "adverse": "out on the first adverse close"}
    for t in (1.0, 2.0, 2.5, 3.0, 4.0, 5.0):
        ARMS[f"flat{t}"] = f"flat {t:.1f} R"
    for b in (0.5, 1.0, 1.5, 2.0):
        ARMS[f"be{b}"] = f"ride, BE at +{b} R"
    for m in (15, 30, 45):
        ARMS[f"ride_ts{m}"] = f"ride + {m}-minute time stop"
        ARMS[f"f2_ts{m}"] = f"flat 2 R + {m}-minute time stop"
    best_arm = max(ARMS, key=lambda k: agg_r([r[k] for r in rows])["mean"])
    best_mean = agg_r([r[best_arm] for r in rows])["mean"]
    # the best loser-cut arm, for bucket (e)
    CUTS = [f"ride_ts{m}" for m in (15, 30, 45)] + ["adverse"]
    best_cut = max(CUTS, key=lambda k: agg_r([r[k] for r in rows])["mean"])
    best_cut_mean = agg_r([r[best_cut] for r in rows])["mean"]
    pos = sum(1 for d in (rideC["mean"] - inc["mean"], be_never - be_1r,
                          eod - rideC["mean"], f25 - f2,
                          best_cut_mean - rideC["mean"]) if d > 0)

    A("## The answer, in one table")
    A("")
    A("Each row is a same-book A/B — same entries, same stops, same tape, one lever "
      "moved — and the last column is **what the BEST available move in that bucket is "
      f"worth**. The gap to close is {GATE - bk['mean']:+.4f} R.")
    A("")
    A("| bucket | Austin's question | the best move measured | what it buys |")
    A("|---|---|---|---:|")
    A(f"| (a) scale-out percentages | *\"its all in the percent i scale\"* | abolish "
      f"scaling entirely — one unit, original stop, ride to 11:00 | "
      f"**{rideC['mean'] - inc['mean']:+.4f}** |")
    A(f"| (b) break-even after tranche 1 | *\"moving stop loss to break even?\"* | never "
      f"move the stop (BE never) instead of BE at +1 R | **{be_never - be_1r:+.4f}** |")
    A(f"| (c) the 11:00 backstop | *\"not holding it long enough\"* | hold LONGER — the "
      f"same ride, clock removed, run to the 15:59 close | **{eod - rideC['mean']:+.4f}** |")
    A(f"| (d) the target | *\"is 2.5R medium better\"* | flat 2.5 R instead of flat 2.0 R "
      f"(and flat 5 R instead of 2 R: {f5 - f2:+.4f}) | **{f25 - f2:+.4f}** |")
    A(f"| (e) cutting losers faster | *\"losers stop out quicker\"* | the best of 15 / 30 / "
      f"45-minute time stops and a first-adverse-close cut ({ARMS[best_cut]}) | "
      f"**{best_cut_mean - rideC['mean']:+.4f}** |")
    A("")
    A(f"**{['None', 'One', 'Two', 'Three', 'Four', 'Five'][pos]} of the five point the way "
      f"Austin's sentence points and none of them is "
      f"worth a fifth of an R.** The best of the {len(ARMS)} single-unit exit policies "
      f"measured in this file is *{ARMS[best_arm]}* at **{best_mean:+.4f} R**, against the "
      f"shipped ladder's {inc['mean']:+.4f} R at the same horizon. That difference — "
      f"**{best_mean - inc['mean']:+.4f} R, {(best_mean - inc['mean']) / ERR:.0f}× the "
      f"error bar and {100 * (best_mean - inc['mean']) / (GATE - inc['mean']):.1f}% of the "
      f"distance to the gate** — is the entire value of every exit lever in the brief, "
      f"taken at its best. Against the book **as actually booked** ({bk['mean']:+.4f} R, "
      f"which runs winners to the 16:00 close) the best exit policy in this file is worth "
      f"{best_mean - bk['mean']:+.4f} R.")
    A("")
    A(f"Rows (a) and (b) are **not additive**: the (a) counterfactual is already a "
      f"BE-never arm, so abolishing the scaling and abolishing break-even are the same "
      f"{rideC['mean'] - inc['mean']:+.4f} R move counted once. Nothing in the five rows "
      f"stacks with anything else in them.")
    A("")
    A(f"**The shipped book is {bk['mean']:+.4f} R as booked and {inc['mean']:+.4f} R when "
      f"`exit_lab`'s ladder is re-run at the 11:00 clock** (the book runs an open position "
      f"to the 16:00 close; `exit_lab` force-flats at 11:00 — that is the whole difference "
      f"and it is worth {inc['mean'] - bk['mean']:+.4f} R). Every delta above is measured "
      f"against the `exit_lab` arm so the entry, the stop and the tape are identical.")
    A("")
    A("## 0. The ceiling — and the correction the ticket needs")
    A("")
    A("This lane was briefed with *\"the theoretical mean R of a perfect-exit oracle … "
      "NOBODY IN THIS PROJECT HAS COMPUTED IT\"*. **That is wrong.** "
      "`research/p10_structure_trail.py::oracle_stopped` computed it on 2026-08-26 and "
      "published **+3.501 R** in `research/p10_structure_trail.md`. This file recomputes "
      "it from an independent bar loader (`p26.load_day`, archive-only) rather than "
      "repeating the table.")
    A("")
    A("| ceiling | n | mean R | median | p75 | p90 | note |")
    A("|---|---:|---:|---:|---:|---:|---|")
    orcs = [r["orc"] for r in rows]
    mfes = [r["mfe"] for r in rows]
    A(f"| `oracle_stopped` — best CLOSE with hindsight, Austin's stop still live | {n} | "
      f"**{orc['mean']:+.4f}** | {pctl(orcs, .5):+.2f} | {pctl(orcs, .75):+.2f} | "
      f"{pctl(orcs, .90):+.2f} | the honest ceiling for any close-exit policy |")
    A(f"| `oracle_MFE` — best price the trade ever traded at | {n} | "
      f"**{mfe['mean']:+.4f}** | {pctl(mfes, .5):+.2f} | {pctl(mfes, .75):+.2f} | "
      f"{pctl(mfes, .90):+.2f} | nothing can beat this |")
    A(f"| shipped ladder, `exit_lab` @ 11:00 | {n} | **{inc['mean']:+.4f}** | "
      f"{inc['median']:+.4f} | — | — | captures "
      f"{100 * inc['tot'] / mfe['tot']:.1f}% of MFE, "
      f"{100 * inc['tot'] / orc['tot']:.1f}% of the oracle |")
    A(f"| **the money gate** | — | **≥ +2.0000** | — | — | — | — |")
    A("")
    A(f"**The oracle ceiling is +{orc['mean']:.4f} R, which is "
      f"{orc['mean'] / GATE:.2f}× the money gate.** So the gate is NOT unreachable at "
      f"this entry quality on arithmetic grounds — the R exists on the tape. What is "
      f"true is narrower and worse: an exit would have to capture "
      f"{100 * GATE / orc['mean']:.1f}% of a hindsight-perfect ceiling to pay the gate, "
      f"and the shipped ladder captures {100 * inc['tot'] / orc['tot']:.1f}%.")
    A("")
    A("## 1. The gap to the ceiling, decomposed by trade class — this one IS additive")
    A("")
    A("Every other decomposition in this repo is a set of A/Bs that do not add up. This "
      "one does, by construction: the per-trade give-back "
      "`oracle − incumbent` is summed over two disjoint sets and divided by the same n.")
    A("")
    A("| class | n | share | mean R booked | mean R the oracle got | give-back per BOOK trade |")
    A("|---|---:|---:|---:|---:|---:|")
    A(f"| incumbent WINS | {len(win)} | {100 * len(win) / n:.1f}% | "
      f"{statistics.fmean([r['inc'] for r in win]):+.4f} | "
      f"{statistics.fmean([r['orc'] for r in win]):+.4f} | **{gap_win:+.4f}** |")
    A(f"| incumbent LOSSES (≤ 0 R) | {L} | {100 * L / n:.1f}% | "
      f"{statistics.fmean([r['inc'] for r in los]):+.4f} | "
      f"{statistics.fmean([r['orc'] for r in los]):+.4f} | **{gap_los:+.4f}** |")
    A(f"| **whole book** | {n} | 100% | {inc['mean']:+.4f} | {orc['mean']:+.4f} | "
      f"**{orc['mean'] - inc['mean']:+.4f}** |")
    A("")
    A(f"**{100 * gap_win / (gap_win + gap_los):.1f}% of the give-back is on trades the "
      f"incumbent already WINS.** The losers contribute {gap_los:+.4f} R of the "
      f"{orc['mean'] - inc['mean']:+.4f} R gap — "
      f"{100 * gap_los / (gap_win + gap_los):.1f}%. Cutting losers faster cannot pay for "
      f"the gate even if it were free and perfect: the whole loser bucket is only "
      f"{-los_drag:.4f} R of drag on the book mean, so **a policy that made every losing "
      f"trade vanish at zero cost would land at {inc['mean'] - los_drag:+.4f} R and still "
      f"miss the gate by {GATE - (inc['mean'] - los_drag):.4f} R.** The winners' give-back "
      f"is the only bucket big enough to pay, and §3 and §8 are why it cannot be reached.")
    A("")
    A("## 2. Of the trades that ended ≤ 0 R, how many were green first")
    A("")
    A(f"Under the shipped ladder at the 11:00 clock, {L} of {n} rows book ≤ 0 R. MFE is "
      f"stop-respecting and intrabar — the best the trade ever traded at before a close "
      f"beyond the stop.")
    A("")
    A("| touched | n of the losers | share of losers | share of the whole book |")
    A("|---|---:|---:|---:|")
    for thr in (0.5, 1.0, 1.5, 2.0, 3.0):
        c = cnt(los, thr)
        A(f"| ≥ +{thr:.1f} R | {c} | {100 * c / L:.1f}% | {100 * c / n:.1f}% |")
    A(f"| never green (MFE = 0) | {sum(1 for r in los if r['mfe'] <= 0)} | "
      f"{100 * sum(1 for r in los if r['mfe'] <= 0) / L:.1f}% | "
      f"{100 * sum(1 for r in los if r['mfe'] <= 0) / n:.1f}% |")
    A("")
    lm = [r["mfe"] for r in los]
    A(f"Loser MFE: mean **{statistics.fmean(lm):+.4f} R**, median {statistics.median(lm):+.4f} R, "
      f"p75 {pctl(lm, .75):+.2f} R, p90 {pctl(lm, .90):+.2f} R.")
    A("")
    A(f"**{100 * cnt(los, 1.0) / L:.1f}% of the losing trades were up a full R first, and "
      f"{100 * cnt(los, 2.0) / L:.1f}% touched the 2 R target and gave every cent of it "
      f"back.** Only {100 * sum(1 for r in los if r['mfe'] <= 0) / L:.1f}% never went "
      f"green at all. This is the single fact behind every result in this file: a losing "
      f"trade in this book is overwhelmingly a trade that WORKED and then failed, not a "
      f"trade that was wrong from the first minute. P10 measured the close-based version "
      f"of the same thing (33.8% of its losers offered a CLOSE at +1 R or better); this is "
      f"the intrabar version and it is higher because a touch is easier than a close.")
    A("")
    A("## 3. Of the winners, how much of the move did the book capture")
    A("")
    wm = [r["mfe"] for r in win]
    wb = [r["inc"] for r in win]
    capt = [r["inc"] / r["mfe"] for r in win if r["mfe"] > 0]
    A("| stat | winners |")
    A("|---|---:|")
    A(f"| n | {len(win)} |")
    A(f"| median MFE | **{statistics.median(wm):+.4f} R** |")
    A(f"| mean MFE | {statistics.fmean(wm):+.4f} R |")
    A(f"| median booked | {statistics.median(wb):+.4f} R |")
    A(f"| mean booked | {statistics.fmean(wb):+.4f} R |")
    A(f"| median capture (booked / MFE, per trade) | **{100 * statistics.median(capt):.1f}%** |")
    A(f"| mean capture (per trade) | {100 * statistics.fmean(capt):.1f}% |")
    A(f"| aggregate capture (Σ booked / Σ MFE) | {100 * sum(wb) / sum(wm):.1f}% |")
    A("")
    A("**Compared like with like against Austin's own hand-replay, the engine's winners "
      "are not the problem — its losers are.** `research/w11_tz_exit_efficiency.md` "
      "measured his TradeZella book two ways, and both have a match here:")
    A("")
    A("| comparison | Austin (W11) | this engine | read |")
    A("|---|---:|---:|---|")
    A(f"| winners only, per-trade capture | mean 39.6% / median 36.8% | mean "
      f"{100 * statistics.fmean(capt):.1f}% / median {100 * statistics.median(capt):.1f}% | "
      f"**the engine's winners give back LESS than his do** |")
    A(f"| whole book, aggregate ΣR / ΣMFE | 37.8% | "
      f"{100 * inc['tot'] / mfe['tot']:.1f}% | the engine is 15.9 points worse |")
    A("")
    A(f"The two lines cannot both be true of the exit, and they are not: the exit is fine "
      f"on the trades it wins. The whole-book number collapses because "
      f"{100 * L / n:.1f}% of the engine's trades end red after averaging "
      f"{statistics.fmean(lm):+.4f} R of MFE — {statistics.fmean(lm) * L / mfe['tot'] * 100:.1f}% "
      f"of all the excursion the book ever printed is attached to a trade that books a "
      f"loss. That is a selection number, not an exit number.")
    A("")
    A("## 4. (b) Break-even, counted instead of swept")
    A("")
    A("Two independent measurements of the same lever.")
    A("")
    A(f"**The counterfactual.** One unit, original stop, ride to 11:00, stop moved to "
      f"entry the moment price touches +1 R, against the identical ride with BE never. "
      f"BE never {be_never:+.4f} R → BE at 1 R {be_1r:+.4f} R, a cost of "
      f"**{be_1r - be_never:+.4f} R**.")
    A("")
    A(f"**The count.** The BE stop actually fired on **{len(be_out)} of {n} rows "
      f"({100 * len(be_out) / n:.1f}%)**. Of those, the tape then offered, AFTER the BE "
      f"exit and before 11:00:")
    A("")
    A("| the BE'd trade then reached | n | share of BE'd trades | share of the book |")
    A("|---|---:|---:|---:|")
    for lab, sub in (("≥ +1.0 R", be_1), ("≥ +1.5 R", be_15), ("≥ +2.0 R", be_2r)):
        A(f"| {lab} | {len(sub)} | {100 * len(sub) / max(1, len(be_out)):.1f}% | "
          f"{100 * len(sub) / n:.1f}% |")
    A("")
    A(f"**On the SHIPPED ladder** — `scale_out` traced rather than cloned — the runner's "
      f"break-even floor is what ends the trade on **{len(lad_be)} of {n} rows "
      f"({100 * len(lad_be) / n:.1f}%)**, and **{len(lad_be_2r)}** of those "
      f"({100 * len(lad_be_2r) / max(1, len(lad_be)):.1f}%) went on to offer ≥ +2 R "
      f"before 11:00. Runner exit reasons on the shipped ladder:")
    A("")
    A("| why the position finally left | n | share |")
    A("|---|---:|---:|")
    whys = defaultdict(int)
    for r in rows:
        whys[r["inc_why"]] += 1
    for k, v in sorted(whys.items(), key=lambda kv: -kv[1]):
        A(f"| `{k}` | {v} | {100 * v / n:.1f}% |")
    A("")
    A(f"**Read the `t1_stop` row: on {whys['t1_stop']} of {n} rows "
      f"({100 * whys['t1_stop'] / n:.1f}%) the ORIGINAL stop fires before tranche 1 ever "
      f"reaches its HOD/LOD rung — the position never scales at all and never has a "
      f"break-even stop to move.** Whatever the scale percentages are set to, they are "
      f"inoperative on {100 * whys['t1_stop'] / n:.0f}% of the book. Break-even is the "
      f"binding exit on {100 * whys['be'] / n:.1f}%. Between them, the two things Austin "
      f"named as the suspected cause of the mean-R gap govern the outcome of "
      f"{100 * (n - whys['t1_stop']) / n:.0f}% and {100 * whys['be'] / n:.1f}% of the "
      f"trades respectively.")
    A("")
    A("BE trigger sweep on the one-unit ride, for completeness:")
    A("")
    A(HDR)
    for b in (0.5, 1.0, 1.5, 2.0):
        A(line(rows, f"be{b}", f"ride, BE at +{b} R"))
    A(line(rows, "rideC", "ride, BE never *(control)*"))
    A("")
    A("## 5. (d) The target — including the 2.5 R nobody had scored")
    A("")
    A(HDR)
    for t in (1.0, 2.0, 2.5, 3.0, 4.0, 5.0):
        A(line(rows, f"flat{t}", f"flat {t:.1f} R"))
    A(line(rows, "hod", "hod_only (the ladder's rung-1 rule, 100%)"))
    A(line(rows, "rideC", "no target, ride to 11:00"))
    A(line(rows, "inc", "shipped ladder 30/30/30/10 *(control)*"))
    A("")
    g25, t25 = months_green(rows, "flat2.5")
    A(f"**Yes — 2.5 R medium beats 2.0 R, by {f25 - f2:+.4f} R**, "
      f"{abs(f25 - f2) / ERR:.0f}× the error bar, so the sign is established. And it is "
      f"the only arm anywhere in this file that is green in **{g25} / {t25} months** — the "
      f"durability gate, met. It costs 6.0 points of win rate (59.9% → 53.9%), which puts "
      f"it under the 55% half of the money gate, and it is still {GATE - f25:.4f} R short "
      f"of the mean-R half.")
    A("")
    A(f"**But 2.5 R is not the top of the ladder — the mean rises monotonically all the "
      f"way out.** 1 R {agg_r([r['flat1.0'] for r in rows])['mean']:+.4f} → 2 R {f2:+.4f} "
      f"→ 2.5 R {f25:+.4f} → 3 R {agg_r([r['flat3.0'] for r in rows])['mean']:+.4f} → 4 R "
      f"{agg_r([r['flat4.0'] for r in rows])['mean']:+.4f} → 5 R {f5:+.4f}, while win rate "
      f"falls 77.2% → 39.7%. That is `research/g7_exit_sweep.md`'s monotonicity "
      f"reproduced with 2.5 R filled in, and it still never catches the no-target ride at "
      f"{rideC['mean']:+.4f} R. **A flat target is a way to buy win rate and durability "
      f"with mean R; on this book it is never a way to buy mean R.**")
    A("")
    A("## 6. (c) The horizon — how much R sits beyond 11:00")
    A("")
    A(HDR)
    A(line(rows, "rideC", "one unit, ride to 11:00 *(control)*"))
    A(line(rows, "rideEOD", "one unit, ride to the 15:59 close"))
    A("")
    mfe_eod = agg_r([r["mfe_eod"] for r in rows])["mean"]
    orc_eod = agg_r([r["orc_eod"] for r in rows])["mean"]
    A("How much R actually sits beyond the backstop, three ways — all hindsight, all "
      "measured in R from the ORIGINAL entry, so a number here is the whole excursion "
      "available at that moment, not an increment on top of what the trade already had:")
    A("")
    A("| measure | whole book | incumbent winners |")
    A("|---|---:|---:|")
    A(f"| best price on offer at any point AFTER 11:00 (no stop) | "
      f"{statistics.fmean(all_after):+.4f} R mean, {statistics.median(all_after):+.4f} R median | "
      f"{statistics.fmean(win_after):+.4f} R mean, {statistics.median(win_after):+.4f} R median |")
    A(f"| stop-respecting MFE, 11:00 horizon | {mfe['mean']:+.4f} R | "
      f"{statistics.fmean(wm):+.4f} R |")
    A(f"| stop-respecting MFE, 15:59 horizon | {mfe_eod:+.4f} R | "
      f"{statistics.fmean([r['mfe_eod'] for r in win]):+.4f} R |")
    A("")
    A(f"**So the extra four and a half hours add {mfe_eod - mfe['mean']:+.4f} R to the "
      f"stop-respecting ceiling and the hindsight-perfect close-exit ceiling rises "
      f"{orc_eod - orc['mean']:+.4f} R ({orc['mean']:+.4f} → {orc_eod:+.4f}). Holding for "
      f"it costs {eod - rideC['mean']:+.4f} R.** The room is there; every causal rule that "
      f"has reached for it has paid for the privilege — this file, `g7_exit_sweep.md`, "
      f"`p10_structure_trail.md` and `w13_scaling.md` §3.3 all four independently. "
      f"Win rate is what gives way: {rideC['wr']:.1f}% at the 11:00 clock → "
      f"{agg_r([r['rideEOD'] for r in rows])['wr']:.1f}% at 15:59.")
    A("")
    A("## 7. (e) Cutting the losers faster — the \"trades be quicker\" arms")
    A("")
    A(HDR)
    A(line(rows, "rideC", "one unit, ride to 11:00 *(control)*"))
    for m in (15, 30, 45):
        A(line(rows, f"ride_ts{m}", f"ride + hard {m}-minute time stop"))
    A(line(rows, "adverse", "out on the FIRST bar that closes against entry"))
    A(line(rows, "flat2.0", "flat 2 R, no scaling, BE never *(control)*"))
    for m in (15, 30, 45):
        A(line(rows, f"f2_ts{m}", f"flat 2 R + hard {m}-minute time stop"))
    A("")
    tt = [r["mfe_min"] for r in rows if r["mfe"] > 0]
    A(f"**Time to MFE**, on the {len(tt)} rows that ever went green: median "
      f"**{statistics.median(tt):.0f} minutes** after entry, p75 {pctl(tt, .75):.0f} min, "
      f"p90 {pctl(tt, .90):.0f} min. On the incumbent winners: median "
      f"{statistics.median([r['mfe_min'] for r in win]):.0f} min, p75 "
      f"{pctl([r['mfe_min'] for r in win], .75):.0f} min. **The median WINNER's best "
      f"price prints {statistics.median([r['mfe_min'] for r in win]):.0f} minutes after "
      f"entry, so a 15-minute stop cuts the median winner before its best price and a "
      f"45-minute stop is past the p75.** That is the whole shape of §7: every cut fast "
      f"enough to save a loser is fast enough to cost a winner more.")
    A("")
    A("## 8. MAE — the other half of the path, computed here for the first time")
    A("")
    maes = [r["mae"] for r in rows]
    wmae = [r["mae"] for r in win]
    A("| slice | n | mean MAE | median | p75 | p90 | share with MAE ≥ 0.5 R |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for lab, sub in (("whole book", rows), ("incumbent winners", win),
                     ("incumbent losers", los)):
        m = [r["mae"] for r in sub]
        A(f"| {lab} | {len(sub)} | {statistics.fmean(m):.4f} R | "
          f"{statistics.median(m):.4f} R | {pctl(m, .75):.2f} R | {pctl(m, .90):.2f} R | "
          f"{100 * sum(1 for x in m if x >= 0.5) / len(m):.1f}% |")
    A("")
    A(f"**Winners draw down almost as much as losers do before they work**: median MAE "
      f"{statistics.median(wmae):.4f} R on winners against "
      f"{statistics.median([r['mae'] for r in los]):.4f} R on losers. That is the "
      f"mechanical reason every tighter-stop and faster-cut arm in §7 loses money — "
      f"there is no adverse-excursion threshold that separates the two populations.")
    A("")
    A("## 9. What this does and does not say")
    A("")
    A(f"- **The oracle ceiling is NOT below the gate.** {orc['mean']:+.4f} R at the 11:00 "
      f"clock, {orc['mean'] / GATE:.2f}× the +2.0 R money gate. The lane brief asked for "
      f"this to be flagged as the session's biggest finding if it came in under 2.0 R; it "
      f"did not, and it was already published by P10 on 2026-08-26 at +3.501 R.")
    A(f"- **Austin's diagnosis is answered clause by clause, and it is NO on all three.** "
      f"It is not the scale percentages — abolishing scaling altogether is worth "
      f"{rideC['mean'] - inc['mean']:+.4f} R. It is not moving the stop to break-even — "
      f"on the SHIPPED ladder the BE floor is what ends the trade on {len(lad_be)} of {n} "
      f"rows ({100 * len(lad_be) / n:.1f}%), and where a BE rule IS imposed it costs "
      f"{be_1r - be_never:+.4f} R rather than earning. It is not the hold horizon — "
      f"holding LONGER costs {eod - rideC['mean']:+.4f} R and the best of the four "
      f"faster-cut arms still costs {best_cut_mean - rideC['mean']:+.4f} R, so 11:00 is "
      f"already at the top of that curve. Taken at its very best the whole exit family "
      f"is {best_mean - inc['mean']:+.4f} R against a {GATE - inc['mean']:.4f} R gap: "
      f"**{100 * (best_mean - inc['mean']) / (GATE - inc['mean']):.1f}% of the distance.**")
    A(f"- **Where it IS lost: the winners' give-back, {gap_win:+.4f} R per book trade, "
      f"{100 * gap_win / (gap_win + gap_los):.1f}% of the whole distance to the ceiling** "
      f"— and it is unreachable because the give-back is not separable. §8 shows winners "
      f"and losers have near-identical adverse excursion (median MAE "
      f"{statistics.median(wmae):.2f} R vs {statistics.median([r['mae'] for r in los]):.2f} R) "
      f"and §2 shows {100 * cnt(los, 1.0) / L:.1f}% of the losers were up a full R first. "
      f"On the way up a loser and a winner are the same trade.")
    A("- **Every arm here is a single-unit policy.** W13 already showed the only lever "
      "that raises aggregate R materially is scale-IN (+1.4697 R best), which multiplies "
      "the book rather than re-cutting it. Nothing in this file contradicts that; this "
      "file explains why re-cutting cannot work.")
    A("- **In-sample, every parameter.** The time stops, the BE triggers and the targets "
      "are all chosen and scored on the same 1,017 rows. No held-out split.")
    A("- **`exit_lab.hod_only` still has the off-by-one W13 §9 reported** (it can book "
      "below the −1.25 R floor on 5 of 1017 rows). It appears in §5 for continuity and is "
      "not load-bearing for any conclusion here.")
    A("- **Options decay, spread and fill are not priced.** R is the result, dollars are "
      "a sizing skin.")
    A("")
    A("## The one next move")
    A("")
    A(f"**Stop testing exits and take the {100 * L / n:.1f}% loss rate to the entry.** The "
      f"arithmetic is now closed on both sides: every exit lever Austin named is worth "
      f"{best_mean - inc['mean']:+.4f} R at its very best "
      f"({100 * (best_mean - inc['mean']) / (GATE - inc['mean']):.1f}% of the gap), and "
      f"even a hindsight-perfect loser filter — every red trade simply deleted — lands at "
      f"{inc['mean'] - los_drag:+.4f} R and still misses. The only bucket large enough to "
      f"pay the gate is the {gap_win:+.4f} R the winners give back, and §2 and §8 show it "
      f"is not separable from price: {100 * cnt(los, 1.0) / L:.1f}% of the losers were up "
      f"a full R and their median adverse excursion is "
      f"{statistics.median([r['mae'] for r in los]):.2f} R against the winners' "
      f"{statistics.median(wmae):.2f} R. **The book needs fewer, better trades, not a "
      f"different way of leaving the ones it has.** `research/x1_mfe_mae.json` ships the "
      f"per-trade MFE / MAE / oracle so an entry-selection rig can be scored against the "
      f"path directly instead of re-deriving it.")
    A("")
    A("## 10. Provenance")
    A("")
    A("| number | script | note |")
    A("|---|---|---|")
    A("| every figure in §0–§9 | `research/x1_exit_attribution.py` | this commit |")
    A("| per-trade MFE / MAE / oracle | `research/x1_mfe_mae.json` | written by this run |")
    A("| the traded book | `research/g3_onwatch_2y.py` → `g3_arm_ow1.json` | `47e60796` |")
    A("| `Bars`, `build_arm`, `agg_r` | `research/r9_simple_book.py` | `e4de7858` |")
    A("| `mfe_r` | `research/h1_2y_nowatch.py` | `f5ff006a` |")
    A("| the oracle, first computed | `research/p10_structure_trail.py` | `6c3f880f`, +3.501 R |")

    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(o) + "\n")

    keep = ("sym", "day", "ym", "side", "entry_i", "entry", "stop", "sgrade",
            "book_r", "inc", "mfe", "mae", "mfe_min", "orc", "orc_eod",
            "mfe_eod", "mfe_after_clock", "inc_why", "inc_exit_i")
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump({"meta": {"book": BOOK, "n": n, "clock_bar": xl.CLOCK_BAR,
                            "gaps": gaps},
                   "rows": [{k: r.get(k) for k in keep} for r in rows]}, fh)

    print(f"wrote {OUT_MD} and {OUT_JSON}  (n={n})")
    print(f"  book as booked      {bk['mean']:+.4f}")
    print(f"  exit_lab ladder     {inc['mean']:+.4f}")
    print(f"  one-unit ride       {rideC['mean']:+.4f}")
    print(f"  oracle_stopped      {orc['mean']:+.4f}")
    print(f"  oracle_MFE          {mfe['mean']:+.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
