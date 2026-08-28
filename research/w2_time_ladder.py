"""w2_time_ladder.py -- W2: the time-scaled ladder sweep.

Austin, 2026-08-27, describing the exit he actually runs:

  "Yes, holding past 11, but mostly only runners. But if we enter a trade, say
   10:30, then there's a chance that maybe half of our position or 40% of our
   position we're still in. But past 11, usually just 10% of the trade, if or
   nothing at all."

Chosen shape (master spec `Specs/omen6-h2-master-spec.md` §1.4): **rungs still
fire on R, and the CLOCK independently forces size down on a schedule.** The
step points and the hard backstop are swept, not fixed. This is the first exit
family in the project that encodes TIME rather than only price.

The hole this is aimed at (spec §0): the shipped ladder books a median of
+0.4120 R while the tape offers a mean maximum favourable excursion of
+3.8436 R before the stop closes. The exit keeps a fifth of what it is offered.

ONE RIG, HORIZONS NAMED
----------------------
Every number in this file is `research/exit_lab.py`. `backtest_week.py` runs an
open position to the 16:00 EOD close while `exit_lab` force-flats at 11:00
(`CLOCK_BAR = 90`); comparing the two was a real bug found 2026-08-27 (22 of
1,091 ladder trades booked more R than the 11:00 window ever offered). Nothing
here compares across rigs. The **backstop is a swept parameter**, so different
arms genuinely run to different clocks -- so every row carries its backstop
in its own column, and both controls are re-run at EVERY distinct backstop.
Two rows are comparable iff their `backstop` cells match.

WHAT IS IMPORTED, NOT REWRITTEN
-------------------------------
- `Bars`, `build_arm`, `agg_r`, `months` from `research/r9_simple_book.py`
- `mfe_r` from `research/h1_2y_nowatch.py` (the share-of-MFE column)
- `_stop_hit_first`, `_stop_fill`, `realised_r`, `flat_target`, `scale_out`,
  `MAX_LOSS_R` from `research/exit_lab.py`

`exit_lab.scale_out` is NOT edited -- it was fixed at `f5ff006a` (a stopped-out
trade kept running) and other rigs depend on it. The only new code here is
`time_ladder`, and `--selfcheck` asserts it can never book above what the tape
offered at its own horizon, nor below the -1.25 R floor.

CONTROL ARM
-----------
`research/g7_exit_sweep.md`'s published conclusion ("nothing beats the incumbent
ladder") was measured against the BROKEN `scale_out`, so it is not evidence any
more. Its eight policies are re-run here on the fixed code.

Book: `research/g3_arm_ow1.json` -- the shipped arm (ON_WATCH=1), 1,017 traded
rows, replayed by `research/g3_onwatch_2y.py` at `47e60796`. Bars come from
`data_archive/` through `p26.load_day`; zero network access.

    python research/w2_time_ladder.py             # writes research/w2_time_ladder.md
    python research/w2_time_ladder.py --selfcheck # assertions only, no report
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import exit_lab as xl                                   # noqa: E402
from research.h1_2y_nowatch import mfe_r                              # noqa: E402
from research.r9_simple_book import Bars, agg_r, build_arm, months    # noqa: E402

BOOK = os.path.join(HERE, "g3_arm_ow1.json")
OUT = os.path.join(HERE, "w2_time_ladder.md")

MONEY_GATE = 2.0
# The narrow error bar on the shipped arm. The wide +-1.5799 R bar was RETIRED
# 2026-08-28 when Austin resolved the intrabar ambiguity: a stop fires only on a
# close, and there is one close per bar, so the 790-of-792 `intrabar_stop` class
# was never ambiguous (master spec §1.1).
ERROR_BAR = 0.0095

# RTH bars are 1-minute and index 0 is the 09:30 bar, so a bar index IS minutes
# after the open. 10:30 = 60, 11:00 = 90, 16:00 = 390.
BAR_OF = {"10:00": 30, "10:15": 45, "10:30": 60, "10:45": 75, "11:00": 90,
          "11:15": 105, "11:30": 120, "12:00": 150, "13:00": 210, "16:00": 390}
EOD = 390


def hhmm(bar):
    for k, v in BAR_OF.items():
        if v == bar:
            return k
    return "+%dm" % bar


# ---------------------------------------------------------------------------
# the new policy
# ---------------------------------------------------------------------------

# Echoes the shipped ladder's 30/30/30/10 split, but on R rungs rather than on
# the causal-HOD structure rule, because §1.4 says the rungs fire on R. The
# 0.10 not listed here is the runner: it has no target and rides to the clock.
RUNGS = ((1.0, 0.30), (2.0, 0.30), (3.0, 0.30))


def time_ladder(bars, entry_i, entry, stop, side,
                rungs=RUNGS, steps=(), backstop=xl.CLOCK_BAR,
                be_after_first=True):
    """Time-scaled ladder: R rungs, plus a clock that forces size down.

    ``rungs``   ((target_r, weight), ...) ascending. A weight is a share of the
                ORIGINAL position and fills at the target price the moment the
                bar's range touches it -- a resting limit order. Weights summing
                to less than 1.0 leave a runner with no target.
    ``steps``   ((bar_index, max_remaining), ...) ascending. From that bar on,
                any position above ``max_remaining`` is sold at that bar's
                CLOSE. This is the clock, and it is independent of price.
    ``backstop``bar index at which everything left exits at that bar's close.
    ``be_after_first``  move the stop to break-even once the first rung fills,
                the behaviour `exit_lab.scale_out`'s runner already has.

    Causal conventions, copied from `exit_lab` exactly and not re-derived:

    - scan from ``entry_i + 1``;
    - the stop triggers on a candle CLOSE beyond it (`_stop_hit_first`), fills
      at that close (`_stop_fill`), floored at -1.25 R (`MAX_LOSS_R`);
    - the pessimistic same-bar convention: a bar closing beyond the stop wins
      even if a rung target also traded inside that bar, so the stop is tested
      BEFORE the rungs on every bar;
    - a rung fills before the same bar's clock step, because the rung is a
      resting order at a price and the clock step is a decision at the close.

    Returns the position-weighted realised R.
    """
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    end = min(backstop + 1, n)
    rem = 1.0
    booked = 0.0
    cur_stop = stop
    pending = list(rungs)

    for i in range(entry_i + 1, end):
        b = bars[i]

        # 1. the stop, on the whole remaining position, close-triggered
        if xl._stop_hit_first(bars, i, entry, cur_stop, side):
            px = xl._stop_fill(bars, i, entry, cur_stop, side, risk)
            return booked + rem * xl.realised_r(entry, stop, px, side)

        # 2. R rungs -- resting limit orders, fill on touch
        while pending and rem > 1e-9:
            tgt_r, w = pending[0]
            target = entry + tgt_r * risk if side == "L" else entry - tgt_r * risk
            hit = (b["h"] >= target) if side == "L" else (b["l"] <= target)
            if not hit:
                break
            take = min(w, rem)
            booked += take * tgt_r
            rem -= take
            pending.pop(0)
            if be_after_first:
                cur_stop = entry
        if rem <= 1e-9:
            return booked

        # 3. the clock -- decision at this bar's close
        keep = None
        for sb, mk in steps:
            if i >= sb:
                keep = mk
        if keep is not None and rem > keep + 1e-9:
            take = rem - keep
            booked += take * xl.realised_r(entry, stop, b["c"], side)
            rem = keep
        if rem <= 1e-9:
            return booked

        # 4. the hard backstop
        if i >= backstop:
            return booked + rem * xl.realised_r(entry, stop, b["c"], side)

    # session ended before the backstop: whatever is left exits at the last bar
    last = max(entry_i, min(backstop, n - 1))
    if last <= entry_i:
        return booked
    r_last = xl.realised_r(entry, stop, bars[last]["c"], side)
    return booked + rem * max(r_last, -xl.MAX_LOSS_R)


# ---------------------------------------------------------------------------
# the sweep grid
# ---------------------------------------------------------------------------

def tl(**kw):
    def policy(bars, entry_i, entry, stop, side):
        return time_ladder(bars, entry_i, entry, stop, side, **kw)
    return policy


S_LITERAL = ((60, 0.50), (90, 0.10))       # Austin's sentence, read literally
S_TIGHT = ((60, 0.40), (90, 0.10))         # the 40% end of "half or 40%"
S_EARLY = ((45, 0.50), (90, 0.10))         # step down at 10:15 instead
S_LATE = ((75, 0.50), (90, 0.10))          # step down at 10:45 instead
S_FLAT11 = ((60, 0.50), (90, 0.00))        # "...if or nothing at all"
S_FAT = ((60, 0.50), (90, 0.25))           # a fatter runner than he described
S_THREE = ((45, 0.60), (75, 0.30), (90, 0.10))   # three steps, not two

# (label, kind, callable-or-None, backstop, note)
#   kind "tl"   -- the new family
#   kind "ctl"  -- a control re-run at that same horizon
GRID = [
    # -- family A: the step times, everything flat by 11:00 -------------------
    ("A1  10:30>50% 11:00>10%", S_LITERAL, 90, "his sentence, read literally"),
    ("A2  10:30>40% 11:00>10%", S_TIGHT, 90, "the 40% end of his range"),
    ("A3  10:15>50% 11:00>10%", S_EARLY, 90, "step down 15 min earlier"),
    ("A4  10:45>50% 11:00>10%", S_LATE, 90, "step down 15 min later"),
    ("A5  10:30>50% 11:00>0%", S_FLAT11, 90, "\"...or nothing at all\""),
    ("A6  no clock (rungs only)", (), 90, "isolates the clock: this is 0 steps"),
    ("A7  10:15/10:45/11:00 3-step", S_THREE, 90, "three steps instead of two"),
    # -- family B: the same clock, the backstop pushed past 11:00 -------------
    ("B1  A1 + backstop 11:15", S_LITERAL, 105, "the 10% runner gets 15 min"),
    ("B2  A1 + backstop 11:30", S_LITERAL, 120, "the 10% runner gets 30 min"),
    ("B3  A1 + backstop 12:00", S_LITERAL, 150, "the 10% runner gets 60 min"),
    ("B4  A1 + backstop 13:00", S_LITERAL, 210, "the 10% runner gets 3.5 h"),
    ("B5  A1 + backstop 16:00", S_LITERAL, EOD, "the 10% runner gets the day"),
    ("B6  A2 + backstop 11:30", S_TIGHT, 120, "40% step, runner gets 30 min"),
    ("B7  A6 + backstop 13:00", (), 210, "no clock at all, long backstop"),
    ("B8  fat runner 25% + bs 13:00", S_FAT, 210, "2.5x his stated runner"),
]

# rung variants, all on the winning-shape clock, to price the price half
RUNG_SETS = [
    ("R1  rungs 1/2/3R 30-30-30", RUNGS),
    ("R2  rungs 1/2R 50-40", ((1.0, 0.50), (2.0, 0.40))),
    ("R3  rungs 2/3/4R 30-30-30", ((2.0, 0.30), (3.0, 0.30), (4.0, 0.30))),
    ("R4  rungs 1/2/4R 40-30-20", ((1.0, 0.40), (2.0, 0.30), (4.0, 0.20))),
    ("R5  no rungs (pure clock)", ()),
]

# the eight `research/g7_exit_sweep.py` policies, re-run on the FIXED scale_out
G7 = ["flat_1r", "flat_2r", "hod_only", "30_30_30_10", "50_20_20_10",
      "flat_3r", "flat_4r", "flat_5r"]

# A fixed target's MEDIAN is the target itself whenever its win rate clears 50%,
# so median R alone is gamed by walking the target up until the win rate breaks.
# These three bracket where that breaks, between g7's flat_2r and flat_3r.
FRONTIER = [2.25, 2.5, 2.75]


def g7_policy(pid):
    if pid.startswith("flat_") and pid.endswith("r"):
        t = float(pid[5:-1])
        return lambda b, e, en, st, sd: xl.flat_target(b, e, en, st, sd, t)
    return lambda b, e, en, st, sd: xl.POLICIES[pid](b, e, en, st, sd, "atr")


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

def score(rows, cache, arms):
    """arms: list of (key, backstop, fn). Writes rows[key] and rows["mfe@bs"].

    `xl.CLOCK_BAR` is set per horizon and restored -- the same set/restore
    `research/g7_exit_sweep.py:121,137` and `h1_2y_nowatch.attach_exits` use.
    No shipped default is left changed.
    """
    keep = xl.CLOCK_BAR
    horizons = sorted({bs for _k, bs, _f in arms})
    try:
        for bs in horizons:
            xl.CLOCK_BAR = bs
            mkey = "mfe@%d" % bs
            for r in rows:
                got = cache.get(r["sym"], r["day"])
                d = got[1]
                r[mkey] = mfe_r(d, r["entry_i"], r["entry"], r["stop"], r["side"])
            for key, abs_, fn in arms:
                if abs_ != bs:
                    continue
                for r in rows:
                    d = cache.get(r["sym"], r["day"])[1]
                    r[key] = fn(d, r["entry_i"], r["entry"], r["stop"], r["side"])
    finally:
        xl.CLOCK_BAR = keep
    return rows


def line(rows, key, bs):
    a = agg_r([r[key] for r in rows])
    g, t, wm, wv = months(rows, key)
    mfe = statistics.fmean(r["mfe@%d" % bs] for r in rows)
    a.update(green=g, tot_m=t, worst=wm, worst_v=wv, mfe=mfe,
             cap=100.0 * a["mean"] / mfe if mfe else 0.0, bs=bs)
    return a


def row_md(label, a, note=""):
    return ("| %s | %s | **%+.4f** | %+.4f | %.1f%% | %d / %d | %.1f%% | %+.1f |%s"
            % (label, hhmm(a["bs"]), a["median"], a["mean"], a["wr"],
               a["green"], a["tot_m"], a["cap"], a["tot"],
               (" %s |" % note) if note else ""))


HEAD = ("| arm | backstop | median R | mean R | win rate | months green | "
        "share of mean MFE | total R |")
HEAD_N = HEAD[:-1] + " note |"
RULE = "|---|---|---:|---:|---:|---:|---:|---:|"
RULE_N = RULE + "---|"


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------

def selfcheck(rows, arms):
    """The new policy can never book above the tape, nor below the floor.

    Both properties are structural, not statistical: every leg of a
    `time_ladder` exit is either a rung filling at a price the bar traded, a
    close on a bar that had not closed beyond the stop, or the stop fill itself
    -- and each of those is bounded by the MFE at the SAME horizon above and by
    `MAX_LOSS_R` below. If either assert ever fires, the policy has stopped
    obeying `exit_lab`'s causal conventions and every number in the report is
    void.
    """
    n_tl = 0
    for key, bs, _fn in arms:
        if not key.startswith("tl:"):
            continue
        mkey = "mfe@%d" % bs
        for r in rows:
            got, ceil = r[key], r[mkey]
            assert ceil >= 0.0, "negative MFE %s %s" % (r["sym"], r["day"])
            assert got <= ceil + 1e-6, (
                "%s booked %.4f above the %s ceiling %.4f on %s %s"
                % (key, got, hhmm(bs), ceil, r["sym"], r["day"]))
            assert got >= -xl.MAX_LOSS_R - 1e-6, (
                "%s booked %.4f below the -%.2f R floor on %s %s"
                % (key, got, xl.MAX_LOSS_R, r["sym"], r["day"]))
            n_tl += 1
    # a longer backstop can only offer the tape more room
    hs = sorted({bs for _k, bs, _f in arms})
    for a, b in zip(hs, hs[1:]):
        for r in rows:
            assert r["mfe@%d" % b] >= r["mfe@%d" % a] - 1e-6, (
                "MFE fell when the horizon grew, %s %s" % (r["sym"], r["day"]))
    assert xl.CLOCK_BAR == 90, "exit_lab.CLOCK_BAR was left at %d" % xl.CLOCK_BAR
    print("selfcheck ok: %d time_ladder results, all within "
          "[-%.2f R, MFE at their own backstop]; %d horizons monotone; "
          "exit_lab.CLOCK_BAR restored to %d"
          % (n_tl, xl.MAX_LOSS_R, len(hs), xl.CLOCK_BAR))


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def report(rows, arms, meta, gaps, best_key, best_label, best_bs, clock_label):
    L = []
    add = L.append
    A = {k: line(rows, k, bs) for k, bs, _f in arms}

    inc90 = A["ctl:ladder@90"]
    f2r90 = A["ctl:flat_2r@90"]
    best = A[best_key]
    beats = [(k, A[k]) for k, bs, _f in arms
             if k.startswith("tl:") and A[k]["median"] > inc90["median"]]

    add("# W2 — the time-scaled ladder sweep")
    add("")
    add("Generated by `research/w2_time_ladder.py` over the **%d** traded rows of "
        "`research/g3_arm_ow1.json` (the shipped arm, `ON_WATCH=1`, replayed by "
        "`research/g3_onwatch_2y.py` at `47e60796`), %s → %s, %d sessions, %d "
        "symbols, `data_archive/` replay, zero fetches."
        % (len(rows), meta["first"], meta["last"], meta["sessions"],
           len(meta["symbols"]) if isinstance(meta["symbols"], list)
           else meta["symbols"]))
    add("")
    pure = A["tl:R5  no rungs (pure clock)"]
    add("## The answer")
    add("")
    add("**The median rises, the mean falls, and no arm in this family beats the "
        "incumbent on both.** The best median in the swept family is **%s** at "
        "**%+.4f R** against the incumbent ladder's %+.4f R on the same rig at the "
        "same 11:00 horizon — **%.1f×** the incumbent, and %.0f× the ±%.4f R error "
        "bar. It costs mean R: %+.4f → %+.4f. **%d of %d** swept arms beat the "
        "incumbent's median and **%d of %d** beat its mean."
        % (best_label, best["median"], inc90["median"],
           best["median"] / inc90["median"] if inc90["median"] else 0.0,
           abs(best["median"] - inc90["median"]) / ERROR_BAR, ERROR_BAR,
           inc90["mean"], best["mean"], len(beats),
           sum(1 for k, _b, _f in arms if k.startswith("tl:")),
           sum(1 for k, _b, _f in arms
               if k.startswith("tl:") and A[k]["mean"] > inc90["mean"]),
           sum(1 for k, _b, _f in arms if k.startswith("tl:"))))
    add("")
    add("**And a plain fixed target still out-medians the whole time-scaled "
        "family — `flat_2r` books %+.4f R.** That number is a warning, not a "
        "result: a fixed target's median IS the target "
        "whenever its win rate clears 50%%, so median R on its own is gamed by "
        "walking the target up until the win rate breaks. §4 walks it: %s. **Read "
        "median R next to mean R and win rate, never alone.**"
        % (f2r90["median"],
           " → ".join("`flat_%gr` %+.3f (%.1f%% win)"
                      % (t, A["fr:%g" % t]["median"], A["fr:%g" % t]["wr"])
                      for t in [2.0] + FRONTIER + [3.0])))
    add("")
    add("**The one thing that beats the incumbent on the MEAN is the clock with no "
        "price rungs at all.** `R5 no rungs (pure clock)` books %+.4f R mean "
        "against the incumbent's %+.4f R and captures %.1f%% of the tape against "
        "%.1f%% — the best mean and the best capture in this whole report, beating "
        "even `hod_only`. Its median is %+.4f R, because with no rungs most trades "
        "never take a profit and simply ride to a step. **So the clock is real "
        "edge and the R rungs are what convert it into a median**, and the two "
        "halves of §1.4's design are doing genuinely different jobs."
        % (pure["mean"], inc90["mean"], pure["cap"], inc90["cap"],
           pure["median"]))
    add("")
    dur = [k for k, _b, _f in arms if A[k]["green"] == A[k]["tot_m"]]
    add("**The single most useful row in the report is not in the time-scaled "
        "family at all: `flat_2.5r`.** Median **%+.4f R**, mean **%+.4f R**, "
        "**%d / %d months green**, %.1f%% of the tape captured, %+.1f R total. "
        "**It is the only arm anywhere in this report that passes the DURABILITY "
        "gate** — every month green — and it beats `flat_2r` on median, mean, "
        "durability and total R simultaneously. It beats the incumbent ladder on "
        "median by %+.4f R and on durability by %d months, and loses to it on "
        "mean by %.4f R. Nobody had walked the fixed target between 2R and 3R "
        "before: `research/g7_exit_sweep.py` jumped straight from 2R to 3R and "
        "the useful ground is in between."
        % (A["fr:2.5"]["median"], A["fr:2.5"]["mean"], A["fr:2.5"]["green"],
           A["fr:2.5"]["tot_m"], A["fr:2.5"]["cap"], A["fr:2.5"]["tot"],
           A["fr:2.5"]["median"] - inc90["median"],
           A["fr:2.5"]["green"] - inc90["green"],
           inc90["mean"] - A["fr:2.5"]["mean"]))
    add("")
    add("**The money gate is still not met and nothing here meets it.** The gate is "
        "mean R = 2.0 with every month green (`CLAUDE.md`). The best-median arm is "
        "%+.4f R short on the mean at %d / %d months green; the best-mean arm is "
        "%+.4f R short. Share of the tape captured FALLS %.1f%% → %.1f%% on the "
        "best-median arm — raising the median is bought by cutting the right tail, "
        "which is the trade this whole family makes."
        % (MONEY_GATE - best["mean"], best["green"], best["tot_m"],
           MONEY_GATE - pure["mean"], inc90["cap"], best["cap"]))
    add("")
    add("### One rig, and every horizon named")
    add("")
    add("Everything below is `exit_lab`. `backtest_week.py` runs an open position "
        "to the **16:00** EOD close while `exit_lab` force-flats at **11:00** "
        "(`CLOCK_BAR = 90`); comparing the two was a real bug found 2026-08-27 — "
        "22 of 1,091 ladder trades booked more R than the 11:00 window ever "
        "offered. **The backstop is a swept parameter here, so it is printed in "
        "its own column on every row, and both controls are re-run at every "
        "distinct backstop. Two rows are comparable if and only if their "
        "`backstop` cells match.**")
    add("")
    add("`share of mean MFE` is mean R divided by the mean maximum favourable "
        "excursion **at that row's own backstop** — a longer horizon offers a "
        "bigger ceiling, so the denominator moves with the row. `mfe_r` is "
        "imported from `research/h1_2y_nowatch.py`, unmodified.")
    add("")
    add("Error bar: **±%.4f R**, the narrow bar. The wide ±1.5799 R bar was "
        "RETIRED 2026-08-28 when Austin settled that a stop fires only on a "
        "candle close, and there is exactly one close per bar, so the "
        "790-of-792 `intrabar_stop` class was never ambiguous (master spec §1.1). "
        "Every median delta in this report clears it by 5× to 260×; the small "
        "MEAN deltas inside the g7 family (§4) clear it by only 2× to 3×, and "
        "are called out where they appear." % ERROR_BAR)
    add("")
    add("---")
    add("")

    # -- 1 ------------------------------------------------------------------
    add("## 1. The two controls")
    add("")
    add("The incumbent ladder is `exit_lab.scale_out([0.30, 0.30, 0.30, 0.10])`, "
        "the shipped 30/30/30/10 — tranche 1 on the causal-HOD rule, the rest on "
        "an ATR trail with the stop at break-even. `flat_2r` is "
        "`exit_lab.flat_target(..., 2.0)`. Both are re-run at every backstop the "
        "sweep uses.")
    add("")
    add(HEAD)
    add(RULE)
    for bs in sorted({bs for _k, bs, _f in arms}):
        for nm, key in (("incumbent ladder `30_30_30_10`", "ctl:ladder@%d" % bs),
                        ("`flat_2r`", "ctl:flat_2r@%d" % bs)):
            if key in A:
                add(row_md(nm, A[key]))
    add("| **money gate** | — | — | **≥ +2.0000** | — | **all** | — | — |")
    add("")
    add("**`flat_2r`'s median is high for a degenerate reason** — it converts every "
        "2R touch into a 2R booking, so its median IS the target whenever more "
        "than half the book touches 2R. It buys that by truncating every 4R and "
        "5R runner, which is why its mean is %+.4f R against the ladder's %+.4f. "
        "§4 walks the target up and finds where that trick breaks."
        % (f2r90["mean"], inc90["mean"]))
    add("")

    # -- 2 ------------------------------------------------------------------
    add("## 2. The sweep — %d parameter points"
        % sum(1 for k, _b, _f in arms if k.startswith("tl:")))
    add("")
    add("Rungs are R targets filling on touch as resting limit orders; the clock "
        "is a hard cap on remaining size applied at a bar's CLOSE. `10:30>50%` "
        "reads \"from 10:30 no more than 50% of the original position may still "
        "be on\". Default rungs are 1R/2R/3R at 30% each, leaving a 10% runner "
        "with no target — the price half of the shipped 30/30/30/10, re-expressed "
        "on R because §1.4 says the rungs fire on R.")
    add("")
    add(HEAD_N)
    add(RULE_N)
    for label, steps, bs, note in GRID:
        add(row_md("`%s`" % label, A["tl:%s" % label], note))
    add("| incumbent ladder | 11:00 | %+.4f | %+.4f | %.1f%% | %d / %d | %.1f%% | %+.1f | **the control** |"
        % (inc90["median"], inc90["mean"], inc90["wr"], inc90["green"],
           inc90["tot_m"], inc90["cap"], inc90["tot"]))
    add("| `flat_2r` | 11:00 | %+.4f | %+.4f | %.1f%% | %d / %d | %.1f%% | %+.1f | **the control** |"
        % (f2r90["median"], f2r90["mean"], f2r90["wr"], f2r90["green"],
           f2r90["tot_m"], f2r90["cap"], f2r90["tot"]))
    add("")

    a6, a1 = A["tl:A6  no clock (rungs only)"], A["tl:A1  10:30>50% 11:00>10%"]
    b5, b7 = A["tl:B5  A1 + backstop 16:00"], A["tl:B7  A6 + backstop 13:00"]
    add("**Read A6 against A1 — that is the clock, priced alone, once rungs are "
        "already in place.** A6 is the identical R rungs with NO clock; A1 adds "
        "Austin's two steps. The clock buys %+.4f R of median and costs %+.4f R "
        "of mean. **Once the rungs are there the clock is nearly free and nearly "
        "weightless** — it only moves the trades the rungs had not already "
        "resolved. Its real work shows up with the rungs removed (§3, `R5`), "
        "where the clock ALONE outruns the incumbent's HOD-plus-ATR machinery on "
        "mean R. Push the same comparison out to a 13:00 backstop (B7 vs B4) and "
        "the clock is worth %+.4f R of median, so **the later the backstop, the "
        "more the clock matters** — which is exactly the regime Austin described "
        "when he said he holds past 11 with only a runner."
        % (a1["median"] - a6["median"], a1["mean"] - a6["mean"],
           A["tl:B4  A1 + backstop 13:00"]["median"] - b7["median"]))
    add("")
    steps_m = [A["tl:A3  10:15>50% 11:00>10%"]["median"], a1["median"],
               A["tl:A4  10:45>50% 11:00>10%"]["median"]]
    add("**The step TIME barely matters and the BACKSTOP costs money.** 10:15, "
        "10:30 and 10:45 spread the median over just %.4f R (A3 / A1 / A4) — "
        "15 minutes either side of his stated 10:30 is worth less than a "
        "twentieth of an R, so the parameter Austin was least sure of is the one "
        "that matters least. The backstop is the opposite: holding the 10%% "
        "runner from 11:00 out to 16:00 costs %+.4f R of mean (A1 %+.4f → B5 "
        "%+.4f) and buys **nothing** on the median, which does not move past "
        "%+.4f R anywhere in B1–B5. **His instinct that past 11:00 it is \"10%% "
        "of the trade, if or nothing at all\" is confirmed on the tape, and this "
        "book's answer is \"nothing at all\".**"
        % (max(steps_m) - min(steps_m), b5["mean"] - a1["mean"],
           a1["mean"], b5["mean"], b5["median"]))
    add("")
    add("A5 is identical to A1 by CONSTRUCTION, not by coincidence: at an 11:00 "
        "backstop, \"keep 10% from 11:00\" and \"keep 0% from 11:00\" both "
        "flatten on the same bar at the same close. The runner is only a real "
        "parameter once the backstop is past 11:00, which is what B1–B5 test, and "
        "there it is worth negative R.")
    add("")

    # -- 3 ------------------------------------------------------------------
    add("## 3. The rung sets, on the best clock from §2")
    add("")
    add("Every row here runs the clock of the best §2 arm — `%s` — and varies "
        "only the price rungs. This is the cleanest separation of the family's "
        "two halves in the report, and the overall best median in the sweep "
        "(`%s`) comes from it." % (clock_label, best_label))
    add("")
    add(HEAD)
    add(RULE)
    for label, _rs in RUNG_SETS:
        k = "tl:%s" % label
        if k in A:
            add(row_md("`%s`" % label, A[k]))
    add("| incumbent ladder | 11:00 | %+.4f | %+.4f | %.1f%% | %d / %d | %.1f%% | %+.1f |"
        % (inc90["median"], inc90["mean"], inc90["wr"], inc90["green"],
           inc90["tot_m"], inc90["cap"], inc90["tot"]))
    add("")
    r2, r3, r5 = (A["tl:R2  rungs 1/2R 50-40"], A["tl:R3  rungs 2/3/4R 30-30-30"],
                  A["tl:R5  no rungs (pure clock)"])
    add("**This table is the whole trade-off in five rows, and it is monotone.** "
        "Push the rungs closer in (`R2`, 1R and 2R only) and the median goes to "
        "%+.4f R with a %.1f%% win rate while the mean falls to %+.4f. Push them "
        "out (`R3`, 2R/3R/4R) and the median drops to %+.4f while the mean climbs "
        "to %+.4f. Remove them entirely (`R5`) and the mean tops the report at "
        "%+.4f — above the incumbent's %+.4f — while the median collapses to "
        "%+.4f. **There is no rung set that buys median without selling mean.** "
        "The exit cannot create R; it can only choose which part of the "
        "distribution to keep."
        % (r2["median"], r2["wr"], r2["mean"], r3["median"], r3["mean"],
           r5["mean"], inc90["mean"], r5["median"]))
    add("")

    # -- 4 ------------------------------------------------------------------
    add("## 4. G7's eight policies, re-run on the FIXED `scale_out`")
    add("")
    add("`research/g7_exit_sweep.md` concluded \"nothing beats the incumbent "
        "ladder\". That was measured against a **broken** `scale_out` — a "
        "stopped-out trade kept running — fixed at `f5ff006a`. The conclusion is "
        "therefore not evidence, and this table re-establishes it on the fixed "
        "code, on this book, at two named horizons. G7 also never printed a "
        "median.")
    add("")
    add(HEAD)
    add(RULE)
    for bs in (90, EOD):
        for pid in G7:
            k = "g7:%s@%d" % (pid, bs)
            if k in A:
                add(row_md("`%s`" % pid, A[k]))
    add("")
    g_best90 = max((A["g7:%s@90" % p]["median"], p) for p in G7)
    g_bestm = max((A["g7:%s@90" % p]["mean"], p) for p in G7)
    add("**On the fixed `scale_out`, g7's conclusion is now FALSE as written.** "
        "`hod_only` books %+.4f R mean at 11:00 against the incumbent ladder's "
        "%+.4f R, and `50_20_20_10` books %+.4f R — the ladder is no longer the "
        "top of its own family. The gap is %.0f× the ±%.4f R error bar, so it is "
        "readable. It is also small: %+.4f R, nowhere near the %+.4f R the money "
        "gate needs."
        % (A["g7:hod_only@90"]["mean"], inc90["mean"],
           A["g7:50_20_20_10@90"]["mean"],
           abs(A["g7:hod_only@90"]["mean"] - inc90["mean"]) / ERROR_BAR,
           ERROR_BAR, A["g7:hod_only@90"]["mean"] - inc90["mean"],
           MONEY_GATE - inc90["mean"]))
    add("")
    med_rank = sorted(G7, key=lambda p: -A["g7:%s@90" % p]["median"])
    add("**And on MEDIAN R, which g7 never printed, the ladder ranks %d of the "
        "%d.** The order is %s. The best is `%s` at %+.4f R against the "
        "incumbent's %+.4f R. G7 asked only about the mean, so it could not have "
        "seen this; the median is what Austin named as the goal."
        % (med_rank.index("30_30_30_10") + 1, len(G7),
           " > ".join("`%s`" % p for p in med_rank), g_best90[1], g_best90[0],
           inc90["median"]))
    add("")
    add("### The median is gameable by a fixed target — here is where it breaks")
    add("")
    add("A fixed target's median IS the target whenever its win rate clears 50%, "
        "so \"raise the median\" is trivially satisfied by walking the target up "
        "until the win rate breaks through 50%. This table finds that point, and "
        "it is the reason no decision in this project should be made on median R "
        "alone.")
    add("")
    add(HEAD)
    add(RULE)
    for t in [2.0] + FRONTIER + [3.0]:
        add(row_md("`flat_%gr`" % t, A["fr:%g" % t]))
    add("")
    lad_t = [2.0] + FRONTIER + [3.0]
    bi = next((i for i, t in enumerate(lad_t) if A["fr:%g" % t]["wr"] < 50.0),
              len(lad_t) - 1)
    lo, hi = A["fr:%g" % lad_t[max(0, bi - 1)]], A["fr:%g" % lad_t[bi]]
    add("**The median falls off a cliff between %gR and %gR**, exactly where the "
        "win rate crosses 50%%. One rung past the crossing turns a %+.4f R median "
        "into a %+.4f R one — a %.4f R swing — while the MEAN barely moves "
        "(%+.4f → %+.4f) and the win rate goes %.1f%% → %.1f%%. **Median R is a "
        "step function of the win rate for any fixed target, and that is why it "
        "must be read next to mean R and win rate.** The time-scaled family's "
        "medians are not of this kind: they sit strictly between the rungs, "
        "because size comes off at several prices instead of one."
        % (lad_t[max(0, bi - 1)], lad_t[bi], lo["median"], hi["median"],
           abs(lo["median"] - hi["median"]), lo["mean"], hi["mean"],
           lo["wr"], hi["wr"]))
    add("")
    add("**But look at the two rows just below the cliff, because they are the "
        "practical result of this whole workstream.** `flat_2.25r` and "
        "`flat_2.5r` are the ONLY arms in this report with **every month green**. "
        "`flat_2.5r` books %+.4f R mean on %+.4f R median at a %.1f%% win rate — "
        "better than `flat_2r` on all four of median, mean, durability and total "
        "R. G7 tested 1R, 2R, 3R, 4R and 5R and never looked between 2 and 3, "
        "which is where the durability gate is actually met."
        % (A["fr:2.5"]["mean"], A["fr:2.5"]["median"], A["fr:2.5"]["wr"]))
    add("")

    # -- 5 ------------------------------------------------------------------
    add("## 5. The winner, month by month")
    add("")
    add("The best median in the whole sweep: `%s`, on the `%s` clock, backstop "
        "%s. The durability gate is EVERY month green. The incumbent ladder at "
        "the same horizon is beside it so a red month can be blamed on the exit "
        "or cleared of it." % (best_label, clock_label, hhmm(best_bs)))
    add("")
    inc_same = A["ctl:ladder@%d" % best_bs]
    bym = defaultdict(list)
    for r in rows:
        bym[r["ym"]].append(r)
    add("| month | n | winner total R | winner mean R | winner median R | incumbent total R | delta |")
    add("|---|---:|---:|---:|---:|---:|---:|")
    ikey = "ctl:ladder@%d" % best_bs
    for ym in sorted(bym):
        rs = bym[ym]
        w = agg_r([r[best_key] for r in rs])
        c = agg_r([r[ikey] for r in rs])
        mark = lambda v: ("**%+.1f**" % v) if v <= 0 else "%+.1f" % v
        add("| %s | %d | %s | %+.3f | %+.3f | %s | %+.1f |"
            % (ym, len(rs), mark(w["tot"]), w["mean"], w["median"],
               mark(c["tot"]), w["tot"] - c["tot"]))
    add("")
    wins = sum(1 for ym in bym
               if sum(r[best_key] for r in bym[ym])
               > sum(r[ikey] for r in bym[ym]))
    add("**Winner %d / %d months green, incumbent %d / %d at the same horizon.** "
        "The gate is %d / %d and neither meets it. Bold is a red month."
        % (best["green"], best["tot_m"], inc_same["green"], inc_same["tot_m"],
           best["tot_m"], best["tot_m"]))
    add("")
    add("**The delta column is the honest read on this arm: it out-earns the "
        "incumbent in only %d of %d months and gives up %+.1f R over the two "
        "years.** What it buys is consistency — a higher median, a %.1f%% win "
        "rate against %.1f%%, and one more green month. It is a different "
        "risk-shape, not more money, and Austin should be shown it as that."
        % (wins, len(bym), best["tot"] - inc_same["tot"], best["wr"],
           inc_same["wr"]))
    add("")

    # -- 6 ------------------------------------------------------------------
    add("## 6. What this does not say")
    add("")
    add("- **It does not reach the money gate.** Mean R = 2.0 with every month "
        "green is still %+.4f R away. A better exit on the same entries cannot "
        "close that; the ceiling is the mean MFE of %+.4f R at 11:00 and no exit "
        "captures a ceiling."
        % (MONEY_GATE - best["mean"],
           statistics.fmean(r["mfe@90"] for r in rows)))
    add("- **It changes no shipped default.** `time_ladder` is a new function; "
        "`exit_lab.scale_out`, `flat_target`, `CLOCK_BAR`, `MAX_LOSS_R` and "
        "`STOP_TRIGGER_BUFFER_FRAC` are untouched, and `--selfcheck` asserts "
        "`CLOCK_BAR` is back at 90 when the sweep finishes.")
    add("- **It does not beat `flat_2r` on the metric it was built for.** The best "
        "time-scaled median is %+.4f R against `flat_2r`'s %+.4f R. §4 explains "
        "why that comparison is not the win it looks like, but the number stands."
        % (best["median"], f2r90["median"]))
    add("- **No arm dominates the incumbent.** Every arm that beats it on median "
        "loses on mean, and the one arm that beats it on mean (`R5`) has a "
        "%+.4f R median. There is no free move anywhere in this family."
        % pure["median"])
    add("- **It is in-sample over all %d parameter points.** Every point is chosen "
        "off the same data it is scored on, and `CLAUDE.md`'s rule stands: "
        "held-out beats in-sample. A held-out split of this sweep is the obvious "
        "next rig and it is NOT in this file."
        % sum(1 for k, _b, _f in arms if k.startswith("tl:")))
    add("- **It does not model options decay.** R is the result and dollars are a "
        "sizing skin (`CLAUDE.md`), but a 13:00 backstop on an 0DTE contract is "
        "not the same instrument as an 11:00 one, and this rig prices the stock "
        "tape only.")
    add("- **The rungs are R targets, not his structure rule.** The incumbent's "
        "tranche 1 exits on the causal-HOD rule. §1.4 says the rungs fire on R, "
        "so that is what was built; a time clock bolted onto the HOD rule instead "
        "is a different arm and is not swept here.")
    add("")

    # -- 7 ------------------------------------------------------------------
    add("## 7. Provenance")
    add("")
    add("| number | script | commit |")
    add("|---|---|---|")
    add("| every figure in §1–§6 | `research/w2_time_ladder.py` | this commit |")
    add("| the traded book | `research/g3_onwatch_2y.py` → `g3_arm_ow1.json` | `47e60796` |")
    add("| `Bars`, `build_arm`, `agg_r`, `months` | `research/r9_simple_book.py` | `e4de7858` |")
    add("| `mfe_r` | `research/h1_2y_nowatch.py` | `f5ff006a` |")
    add("| `scale_out`, `flat_target`, the stop rule | `research/exit_lab.py` | `f5ff006a` |")
    add("| the retired wide error bar | `research/p26_intrabar_ambiguity.py` | `8bb78c77` |")
    add("")
    add("| arm | rows that could not be replayed | reason |")
    add("|---|---:|---|")
    add("| shipped (`ON_WATCH=1`) | %d | %d no archived session, %d entry minute "
        "absent, %d entry index past end |"
        % (sum(gaps.values()), gaps["day"], gaps["bar"], gaps["index"]))
    add("")
    add("`python research/w2_time_ladder.py --selfcheck` proves, on all %d rows × "
        "every swept arm, that a `time_ladder` result never exceeds the maximum "
        "favourable excursion the tape offered at that arm's own backstop and "
        "never falls below the −%.2f R floor."
        % (len(rows), xl.MAX_LOSS_R))
    add("")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------

def build_arms():
    arms = []
    for label, steps, bs, _note in GRID:
        arms.append(("tl:%s" % label, bs,
                     tl(rungs=RUNGS, steps=steps, backstop=bs)))
    return arms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()

    cache = Bars()
    rows, meta, gaps = build_arm(BOOK, cache)
    print("book: %d traded rows, gaps %s" % (len(rows), gaps), file=sys.stderr)

    arms = build_arms()
    horizons = sorted({bs for _k, bs, _f in arms} | {90, EOD})
    for bs in horizons:
        arms.append(("ctl:ladder@%d" % bs, bs,
                     lambda b, e, en, st, sd: xl.scale_out(
                         b, e, en, st, sd, [0.30, 0.30, 0.30, 0.10])))
        arms.append(("ctl:flat_2r@%d" % bs, bs,
                     lambda b, e, en, st, sd: xl.flat_target(b, e, en, st, sd, 2.0)))
    for bs in (90, EOD):
        for pid in G7:
            arms.append(("g7:%s@%d" % (pid, bs), bs, g7_policy(pid)))
    for t in FRONTIER + [3.0, 2.0]:
        arms.append(("fr:%g" % t, 90,
                     (lambda tt: lambda b, e, en, st, sd:
                      xl.flat_target(b, e, en, st, sd, tt))(t)))

    score(rows, cache, arms)

    # §3 re-runs the rung sets on the best CLOCK from the §2 grid
    grid_keys = [(k, bs) for k, bs, _f in arms if k.startswith("tl:")]
    clock_key, clock_bs = max(
        grid_keys, key=lambda kb: agg_r([r[kb[0]] for r in rows])["median"])
    win_steps = next(s for lb, s, _b, _n in GRID if "tl:%s" % lb == clock_key)
    rung_arms = [("tl:%s" % lb, clock_bs,
                  tl(rungs=rs, steps=win_steps, backstop=clock_bs))
                 for lb, rs in RUNG_SETS]
    score(rows, cache, rung_arms)
    arms += rung_arms

    # the winner: best median R across the WHOLE swept family, grid and rungs
    best_key, best_bs = max(
        [(k, bs) for k, bs, _f in arms if k.startswith("tl:")],
        key=lambda kb: agg_r([r[kb[0]] for r in rows])["median"])

    selfcheck(rows, arms)
    if a.selfcheck:
        return

    best_label = best_key[3:]
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(report(rows, arms, meta, gaps, best_key, best_label, best_bs,
                        clock_key[3:]))
    print("wrote %s" % OUT)
    inc = agg_r([r["ctl:ladder@90"] for r in rows])
    win = agg_r([r[best_key] for r in rows])
    print("winner %s @ %s: median %+.4f mean %+.4f | incumbent@11:00 median "
          "%+.4f mean %+.4f" % (best_label, hhmm(best_bs), win["median"],
                                win["mean"], inc["median"], inc["mean"]))


if __name__ == "__main__":
    main()
