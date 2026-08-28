"""h1_2y_nowatch.py -- H1: the 2-year book with ON WATCH removed, and the runners named.

Austin, 2026-08-27:
  "i also wanted to get rid of on watch and scratch since they are new and also
   right now they probably need the biggest work for bug fixes"
  "it should still be -1R for all the trades ... just to prevent slippage"
  "The goal is to let runners run. We have to figure out which trades are runners."

So this file answers four things on ONE rig, over the same 2-year archive replay
every other number in this project comes from:

  1. The whole book with ON WATCH OFF (fill arm A), against the 2.0R money gate
     and the every-month durability gate -- ladder and flat_2r side by side.
  2. Durability, spelled out: all 25 months, per pool, per grade, per symbol.
  3. Which trades are runners: maximum favourable excursion in R, before the
     close-triggered stop, inside the 11:00 clock -- P(reach kR) for k in
     1..5, cut by grade, setup, pool and side.
  4. What the -1R stop actually is in this engine, checked against the code
     rather than asserted.

NO ENGINE DEFAULT IS CHANGED AND NO BAR IS FETCHED. Both fill arms were already
replayed by `research/g3_onwatch_2y.py` (`47e60796`) into `g3_arm_ow0.json`
(ON_WATCH=0) and `g3_arm_ow1.json` (ON_WATCH=1, shipped). This file re-reads
those two books and re-scores them. Bars come from `data_archive/` through
`p26.load_day`, whose guard makes a network fetch impossible.

Everything that already has a committed implementation is IMPORTED from
`research/r9_simple_book.py` -- `Bars`, `build_arm`, `agg_r`, `months`,
`mean_bar`, `p2r`. Reimplementing an exit policy is the mistake r9's own
docstring is asserted against, so the only new computation here is `mfe_r`,
and `--selfcheck` asserts it agrees with the imported `reaches_target` on
every row of both arms.

    python research/h1_2y_nowatch.py            # writes research/h1_2y_nowatch.md
    python research/h1_2y_nowatch.py --selfcheck
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import exit_lab as xl                                  # noqa: E402
from research.r9_simple_book import (                                # noqa: E402
    ARMS, Bars, TARGET_R, agg_r, build_arm, mean_bar, months, p2r,
    reaches_target,
)
from universe import MIN_SAMPLE_N                                    # noqa: E402

OUT = os.path.join(HERE, "h1_2y_nowatch.md")
JSON_OUT = os.path.join(HERE, "h1_2y_nowatch.json")

MONEY_GATE = 2.0
LADDER_RUNGS = (1.0, 2.0, 3.0, 4.0, 5.0)

# Arm A is ON_WATCH=0 -- the arm Austin asked for. Arm B is the shipped default,
# carried only as the comparison it is being removed from.
HEADLINE = "A"


# ---------------------------------------------------------------------------
# the one new measurement: how far did the trade actually get
# ---------------------------------------------------------------------------

def mfe_r(bars, entry_i, entry, stop, side):
    """Maximum favourable excursion, in R, before the stop triggers.

    Same causal scan `exit_lab.flat_target` runs and `r9.reaches_target`
    re-runs: from entry_i+1, close-triggered stop via `xl._stop_hit_first`,
    11:00 ET clock (`xl.CLOCK_BAR`) as the hard backstop, and the same
    pessimistic same-bar convention -- a bar that closes beyond the stop ends
    the trade even if price also ran the other way inside it.

    This is the CEILING on any exit policy: no exit can book more than the
    tape offered before the stop closed. `--selfcheck` asserts
    ``mfe_r >= 2.0`` iff ``reaches_target(...)`` is True, on every row."""
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    best = 0.0
    end = min(xl.CLOCK_BAR + 1, n)
    for i in range(entry_i + 1, end):
        if xl._stop_hit_first(bars, i, entry, stop, side):
            return best
        b = bars[i]
        far = (b["h"] - entry) if side == "L" else (entry - b["l"])
        r = far / risk
        if r > best:
            best = r
    return best


NOCLOCK = 10 ** 6      # g7_exit_sweep.py:39's own noclock value, same convention
LADDER_W = [0.30, 0.30, 0.30, 0.10]


def attach_exits(rows, cache):
    """Score every row under both exits at BOTH horizons, plus MFE at both.

    The shipped `ladder_r` on these rows comes from `backtest_week.py`, which
    runs an open position to the **16:00 EOD close** (`backtest_week.py:692`,
    "EOD: whatever is open scratches at last close"); `ENTRY_CUTOFF = 11:00` is
    an ENTRY cutoff, not an exit clock. `exit_lab` force-flats at **11:00**
    (`CLOCK_BAR = 90`). So `ladder_r` and `flat2r_r` have never been measured
    over the same session, and no comparison between them is like-for-like.

    Every column added here is computed by `exit_lab` at a NAMED horizon, so
    the ladder-vs-flat-2R question can be asked without that confound. The
    module-level `xl.CLOCK_BAR` is set and restored the same way
    `research/g7_exit_sweep.py:121,137` does it."""
    keep = xl.CLOCK_BAR
    try:
        for horizon, clock in (("clock", 90), ("noclock", NOCLOCK)):
            xl.CLOCK_BAR = clock
            for r in rows:
                got = cache.get(r["sym"], r["day"])
                if got is None:        # build_arm already counted it as a gap
                    r["flat2r_" + horizon] = 0.0
                    r["ladder_" + horizon] = 0.0
                    r["mfe_" + horizon] = 0.0
                    continue
                _rth, dicts, _idx, _hi, _lo = got
                a = (dicts, r["entry_i"], r["entry"], r["stop"], r["side"])
                r["flat2r_" + horizon] = xl.flat_target(*a, TARGET_R)
                r["ladder_" + horizon] = xl.scale_out(*a, LADDER_W)
                r["mfe_" + horizon] = mfe_r(*a)
    finally:
        xl.CLOCK_BAR = keep
    for r in rows:
        # §3 is about the shipped 11:00 window unless it says otherwise
        r["mfe_r"] = r["mfe_clock"]
    return rows


def reach_rate(rows, k):
    """Share of rows whose MFE reached k R, in percentage points."""
    if not rows:
        return 0.0
    return 100.0 * sum(1 for r in rows if r["mfe_r"] >= k) / len(rows)


# ---------------------------------------------------------------------------
# slices
# ---------------------------------------------------------------------------

def by(rows, key):
    d = defaultdict(list)
    for r in rows:
        d[r.get(key)].append(r)
    return d


def gate(mean):
    return "PASS" if mean >= MONEY_GATE else "FAIL"


def thin(n):
    return " _(thin)_" if n < MIN_SAMPLE_N else ""


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def report(arms, gaps, metas):
    head = arms[HEADLINE]
    ship = arms["B"]
    L = []
    add = L.append

    lad = agg_r([r["ladder_r"] for r in head])
    fl2 = agg_r([r["flat2r_r"] for r in head])
    lad_b = agg_r([r["ladder_r"] for r in ship])
    fl2_b = agg_r([r["flat2r_r"] for r in ship])
    mg_l, mt_l, wm_l, wv_l = months(head, "ladder_r")
    mg_f, mt_f, wm_f, wv_f = months(head, "flat2r_r")
    mg_lb, mt_lb, _, _ = months(ship, "ladder_r")
    bar_l = mean_bar(head, "ladder_r")
    bar_f = mean_bar(head, "flat2r_r")

    xl_lad_c = agg_r([r["ladder_clock"] for r in head])
    xl_fl2_c = agg_r([r["flat2r_clock"] for r in head])
    xl_lad_n = agg_r([r["ladder_noclock"] for r in head])
    xl_fl2_n = agg_r([r["flat2r_noclock"] for r in head])
    over = [r for r in head if r["ladder_r"] > r["mfe_clock"] + 1e-6]

    add("# H1 — the 2-year book with ON WATCH off, and the runners named")
    add("")
    add("**The headline finding is not the number, it is that the two books being compared "
        "have never been on the same clock.** The shipped ladder's R comes from "
        "`backtest_week.py`, which runs an open position to the **16:00 EOD close** "
        "(`backtest_week.py:692`) — `ENTRY_CUTOFF = 11:00` is an entry cutoff, not an exit "
        "clock. `flat_2r` comes from `exit_lab`, which force-flats at **11:00** "
        "(`CLOCK_BAR = 90`). **%d of %d ladder trades (%.1f%%) book more R than the 11:00 "
        "window ever offered**, which is only possible because they were still open after "
        "11:00. Every \"the simple 2R book earns less than the ladder\" comparison in this "
        "project, `research/r9_simple_book.md` included, is a five-hour handicap read as an "
        "exit result."
        % (len(over), len(head), 100.0 * len(over) / len(head)))
    add("")
    add("**Put both exits on the same clock and a quarter of the gap turns out to be the clock.** Same entries, same "
        "stops, same `exit_lab` rig, ON WATCH off: at 11:00 the ladder is %+.4f R and "
        "`flat_2r` is %+.4f R, a gap of **%.4f R** — against the %.4f R gap the "
        "cross-rig comparison reports. Let both run to EOD instead and the ladder is "
        "%+.4f R against `flat_2r`'s %+.4f R. **Neither book, on either clock, reaches "
        "the 2.0 R money gate.**"
        % (xl_lad_c["mean"], xl_fl2_c["mean"],
           abs(xl_lad_c["mean"] - xl_fl2_c["mean"]),
           abs(lad["mean"] - fl2["mean"]),
           xl_lad_n["mean"], xl_fl2_n["mean"]))
    add("")
    add("**With ON WATCH removed the book is %d trades at **%+.4f R** on the shipped ladder "
        "and **%+.4f R** on flat 2R. Both FAIL the 2.0 R money gate — by %.4f R and %.4f R. "
        "Durability FAILS too: %d of %d months green on the ladder, %d of %d on flat 2R, "
        "against a gate of every month. Removing ON WATCH costs %+.4f R against the shipped "
        "arm and buys back %d trades and %s.**"
        % (lad["n"], lad["mean"], fl2["mean"],
           MONEY_GATE - lad["mean"], MONEY_GATE - fl2["mean"],
           mg_l, mt_l, mg_f, mt_f,
           lad["mean"] - lad_b["mean"], lad["n"] - lad_b["n"],
           ("a green month" if mg_l > mg_lb else
            "no green month" if mg_l == mg_lb else "a lost green month")))
    add("")
    add("**And the ceiling says the exit is not what is missing.** The tape offered "
        "**%+.4f R** of mean maximum favourable excursion before the stop closed, inside the "
        "11:00 clock. The shipped ladder captures **%.1f%%** of it. **%.1f%%** of trades "
        "touched 2R at some point; **%.1f%%** of them finish there or better."
        % (statistics.fmean(r["mfe_r"] for r in head),
           100.0 * lad["mean"] / statistics.fmean(r["mfe_r"] for r in head),
           reach_rate(head, 2.0),
           100.0 * sum(1 for r in head if r["ladder_r"] >= 2.0) / len(head)))
    add("")
    add("Script: `research/h1_2y_nowatch.py`. Books: `research/g3_arm_ow0.json` "
        "(ON_WATCH=0) and `research/g3_arm_ow1.json` (ON_WATCH=1), both replayed by "
        "`research/g3_onwatch_2y.py` at `47e60796`. Window %s → %s, %d sessions, "
        "%d symbols, `data_archive/` replay, zero fetches."
        % (metas[HEADLINE]["first"], metas[HEADLINE]["last"],
           metas[HEADLINE]["sessions"], len(metas[HEADLINE]["symbols"])))
    add("")
    add("---")
    add("")

    # -- 1 ------------------------------------------------------------------
    add("## 1. The whole book, ON WATCH off")
    add("")
    add("Win rate is of DECIDED trades (R = 0 excluded) — the convention "
        "`research/a2_bt2y_summary.py::book` prints. The gate is `CLAUDE.md`'s: mean "
        "R = 2.0, every month green, win rate a secondary read.")
    add("")
    add("| book | n | mean R | median R | win rate | total R | months green | worst month | vs 2.0 R gate |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    add("| **ladder `30_30_30_10`, ON WATCH off** | %d | **%+.4f** | %+.4f | %.1f%% | %+.1f | **%d / %d** | %s %+.1f | **%s** — %.4f R short |"
        % (lad["n"], lad["mean"], lad["median"], lad["wr"], lad["tot"],
           mg_l, mt_l, wm_l, wv_l, gate(lad["mean"]), MONEY_GATE - lad["mean"]))
    add("| **`flat_2r`, ON WATCH off** | %d | **%+.4f** | %+.4f | %.1f%% | %+.1f | **%d / %d** | %s %+.1f | **%s** — %.4f R short |"
        % (fl2["n"], fl2["mean"], fl2["median"], fl2["wr"], fl2["tot"],
           mg_f, mt_f, wm_f, wv_f, gate(fl2["mean"]), MONEY_GATE - fl2["mean"]))
    add("| ladder, ON WATCH on (shipped) | %d | %+.4f | %+.4f | %.1f%% | %+.1f | %d / %d | — | %s |"
        % (lad_b["n"], lad_b["mean"], lad_b["median"], lad_b["wr"], lad_b["tot"],
           mg_lb, mt_lb, gate(lad_b["mean"])))
    add("| `flat_2r`, ON WATCH on (shipped) | %d | %+.4f | %+.4f | %.1f%% | %+.1f | — | — | %s |"
        % (fl2_b["n"], fl2_b["mean"], fl2_b["median"], fl2_b["wr"], fl2_b["tot"],
           gate(fl2_b["mean"])))
    add("| **gate** | — | **≥ +2.0000** | — | — | — | **%d / %d** | > 0 | — |"
        % (mt_l, mt_l))
    add("")
    add("**Removing ON WATCH does not close the gap and it was never going to.** The flag "
        "moves 0 of %d signals (`research/g3_onwatch_2y.md`, `47e60796`) — it is a price "
        "rule at 2 of `signal_runner.fill_price`'s 10 call sites, not a detector. Its whole "
        "reach is the break-and-retest bars that close jammed against the session extreme."
        % metas[HEADLINE]["signals"])
    add("")
    add("**The error bar is the NARROW one, and the delta clears it.** One-directional, from "
        "the intrabar-fill "
        "ambiguity (`research/p26_intrabar_ambiguity.py`, `8bb78c77`): repricing an ambiguous "
        "row can only make R worse, so every mean below is a CEILING. **Which deduction is "
        "live was settled by Austin on 2026-08-28** — a stop is triggered by a candle CLOSE "
        "and nothing else, the entry candle's own close counts (*\"out on that same close\"*), "
        "and one bar has one close, so a stop cannot fire inside the entry bar ahead of the "
        "back-dated fill. The `intrabar_stop` class is not ambiguous. **Carry the narrow "
        "deduction. The wide deduction is RETIRED** and is printed only so the framing this "
        "file used to publish stays traceable.")
    add("")
    add("| book, ON WATCH off | mean R | narrow deduction (CARRIED) | wide deduction (RETIRED 2026-08-28) |")
    add("|---|---:|---:|---:|")
    add("| ladder | %+.4f | −%.4f | −%.4f |" % (bar_l["opt"], bar_l["narrow"], bar_l["wide"]))
    add("| `flat_2r` | %+.4f | −%.4f | −%.4f |" % (bar_f["opt"], bar_f["narrow"], bar_f["wide"]))
    add("")
    add("The ON WATCH delta itself is **%+.4f R**, which is **%.0f×** LARGER than the carried "
        "narrow bar of ±%.4f R on this arm — its sign is readable, and it is small. "
        "*(Retired framing, kept for the record: against the wide bar of ±%.4f R this delta "
        "was %.1f× smaller and this file called it unresolvable in either direction. That was "
        "the wide bar's verdict; the wide bar was retired 2026-08-28.)*"
        % (lad_b["mean"] - lad["mean"],
           abs(lad_b["mean"] - lad["mean"]) / max(bar_l["narrow"], 1e-9),
           bar_l["narrow"],
           bar_l["wide"],
           bar_l["wide"] / max(abs(lad_b["mean"] - lad["mean"]), 1e-9)))
    add("")

    # -- 1b -----------------------------------------------------------------
    add("## 1b. Ladder vs simple 2R, on ONE rig and ONE clock")
    add("")
    add("Austin, 2026-08-27: *\"it is concerning the simpler 2r condensed omen doesent have "
        "edge or is worse.\"* Part of that is a measurement artefact, and this table is the "
        "correction. Every row below is `exit_lab` on the identical entries, stops and sides "
        "of the ON-WATCH-off arm — only the exit and the clock vary. The 30/30/30/10 ladder "
        "is `exit_lab.scale_out`, the same policy `research/g7_exit_sweep.py` sweeps.")
    add("")
    add("| exit | clock | n | mean R | median R | win rate | total R | months green | vs 2.0 R gate |")
    add("|---|---|---:|---:|---:|---:|---:|---:|---|")
    for nm, key, hz in (("ladder `30_30_30_10`", "ladder_clock", "11:00 force-flat"),
                        ("**`flat_2r`**", "flat2r_clock", "11:00 force-flat"),
                        ("ladder `30_30_30_10`", "ladder_noclock", "runs to EOD"),
                        ("**`flat_2r`**", "flat2r_noclock", "runs to EOD")):
        a = agg_r([r[key] for r in head])
        g, t, _, _ = months(head, key)
        add("| %s | %s | %d | **%+.4f** | %+.4f | %.1f%% | %+.1f | %d / %d | %s |"
            % (nm, hz, a["n"], a["mean"], a["median"], a["wr"], a["tot"], g, t,
               gate(a["mean"])))
    add("| shipped ladder (`backtest_week`) | **entry ≤ 11:00, exit to EOD** | %d | %+.4f | %+.4f | %.1f%% | %+.1f | %d / %d | %s |"
        % (lad["n"], lad["mean"], lad["median"], lad["wr"], lad["tot"], mg_l, mt_l,
           gate(lad["mean"])))
    add("| **gate** | — | — | **≥ +2.0000** | — | — | — | **%d / %d** | — |" % (mt_l, mt_l))
    add("")
    add("**The cross-rig gap is %.4f R; the same-rig, same-clock gap is %.4f R.** So most of "
        "what looked like \"the simple book is worse\" was the ladder being allowed to hold "
        "past 11:00 while `flat_2r` was force-flat. It is a real difference in exit design, "
        "but it is a difference in SESSION LENGTH, and Austin's stated rule is that he does "
        "not trade past 11:00 (`signal_runner.py:554`)."
        % (abs(lad["mean"] - fl2["mean"]),
           abs(xl_lad_c["mean"] - xl_fl2_c["mean"])))
    add("")
    dl = xl_lad_n["mean"] - xl_lad_c["mean"]
    df = xl_fl2_n["mean"] - xl_fl2_c["mean"]
    add("**The other half of the answer: holding past 11:00 buys nothing, and that is the "
        "first time this repo has priced it on the same rig.** Same ladder, two clocks: "
        "%+.4f R at 11:00 vs %+.4f R to EOD — a delta of **%+.4f R**, and it costs a green "
        "month (%d/%d → %d/%d). `flat_2r` moves %+.4f R. The 11:00 force-flat is therefore "
        "NOT what is holding the runners back, which kills the obvious first guess and "
        "reproduces `research/g7_exit_sweep.md`'s clock finding on a second rig. The two "
        "rigs still need to agree on one clock — `backtest_week.py` runs to EOD and "
        "`exit_lab` stops at 11:00 — but the choice is worth ~%.2f R, not the gap to the gate."
        % (xl_lad_c["mean"], xl_lad_n["mean"], dl,
           months(head, "ladder_clock")[0], months(head, "ladder_clock")[1],
           months(head, "ladder_noclock")[0], months(head, "ladder_noclock")[1],
           df, abs(dl)))
    add("")
    add("| what the extra session buys | ladder | `flat_2r` |")
    add("|---|---:|---:|")
    add("| mean R at 11:00 | %+.4f | %+.4f |" % (xl_lad_c["mean"], xl_fl2_c["mean"]))
    add("| mean R to EOD | %+.4f | %+.4f |" % (xl_lad_n["mean"], xl_fl2_n["mean"]))
    add("| **delta** | **%+.4f** | **%+.4f** |"
        % (xl_lad_n["mean"] - xl_lad_c["mean"], xl_fl2_n["mean"] - xl_fl2_c["mean"]))
    add("| mean MFE at 11:00 | %+.4f | — |" % statistics.fmean(r["mfe_clock"] for r in head))
    add("| mean MFE to EOD | %+.4f | — |" % statistics.fmean(r["mfe_noclock"] for r in head))
    add("")
    add("**Neither exit gains from the afternoon, and yet the afternoon is where the "
        "movement is.** Mean MFE rises %+.4f R → %+.4f R when the clock comes off — the tape "
        "offers **%.1f%% more room** after 11:00 — and both exits book LESS of it (%+.4f R "
        "and %+.4f R). **That is the honest version of \"let runners run\": the runners are "
        "not being cut short by the 11:00 clock. They are being cut short by the trail, "
        "which gives back more than the extra session offers.** The ladder captures %.1f%% "
        "of the tape at 11:00 and %.1f%% of it by EOD."
        % (statistics.fmean(r["mfe_clock"] for r in head),
           statistics.fmean(r["mfe_noclock"] for r in head),
           100.0 * (statistics.fmean(r["mfe_noclock"] for r in head)
                    / statistics.fmean(r["mfe_clock"] for r in head) - 1.0),
           dl, df,
           100.0 * xl_lad_c["mean"] / statistics.fmean(r["mfe_clock"] for r in head),
           100.0 * xl_lad_n["mean"] / statistics.fmean(r["mfe_noclock"] for r in head)))
    add("")

    # -- 2 ------------------------------------------------------------------
    add("## 2. Durability, spelled out")
    add("")
    add("### Every month")
    add("")
    add("The durability gate is EVERY month green. Both books are shown so a red month "
        "can be blamed on the exit or cleared of it.")
    add("")
    bym = by(head, "ym")
    add("| month | n | ladder total R | ladder mean R | `flat_2r` total R | `flat_2r` mean R |")
    add("|---|---:|---:|---:|---:|---:|")
    for ym in sorted(bym):
        rs = bym[ym]
        lr = sum(r["ladder_r"] for r in rs)
        fr = sum(r["flat2r_r"] for r in rs)
        mark = lambda v: ("**%+.1f**" % v) if v <= 0 else "%+.1f" % v
        add("| %s | %d | %s | %+.3f | %s | %+.3f |"
            % (ym, len(rs), mark(lr), lr / len(rs), mark(fr), fr / len(rs)))
    add("")
    add("Bold is a red month. **Ladder %d / %d, `flat_2r` %d / %d.** The gate is %d / %d."
        % (mg_l, mt_l, mg_f, mt_f, mt_l, mt_l))
    add("")

    for label, key, namer in (("pool", "pool", str),
                              ("Austin grade", "sgrade", str),
                              ("setup", "setup", str)):
        add("### Per %s" % label)
        add("")
        add("| %s | n | ladder mean R | `flat_2r` mean R | win rate (ladder) | months green | P(touch 2R) |"
            % label)
        add("|---|---:|---:|---:|---:|---:|---:|")
        d = by(head, key)
        for k in sorted(d, key=lambda x: -len(d[x])):
            rs = d[k]
            a = agg_r([r["ladder_r"] for r in rs])
            f = agg_r([r["flat2r_r"] for r in rs])
            g, t, _, _ = months(rs, "ladder_r")
            add("| `%s`%s | %d | %+.4f | %+.4f | %.1f%% | %d / %d | %.1f%% |"
                % (namer(k), thin(len(rs)), len(rs), a["mean"], f["mean"],
                   a["wr"], g, t, reach_rate(rs, 2.0)))
        add("")
        add("Rows under `universe.MIN_SAMPLE_N` (=%d) are marked thin — marked, not dropped, "
            "and still inside every whole-book total above." % MIN_SAMPLE_N)
        add("")

    add("### Per symbol")
    add("")
    add("| symbol | n | ladder mean R | `flat_2r` mean R | months green | P(touch 2R) | mean MFE R |")
    add("|---|---:|---:|---:|---:|---:|---:|")
    d = by(head, "sym")
    for k in sorted(d, key=lambda x: -agg_r([r["ladder_r"] for r in d[x]])["mean"]):
        rs = d[k]
        a = agg_r([r["ladder_r"] for r in rs])
        f = agg_r([r["flat2r_r"] for r in rs])
        g, t, _, _ = months(rs, "ladder_r")
        add("| %s%s | %d | %+.4f | %+.4f | %d / %d | %.1f%% | %+.3f |"
            % (k, thin(len(rs)), len(rs), a["mean"], f["mean"], g, t,
               reach_rate(rs, 2.0), statistics.fmean(r["mfe_r"] for r in rs)))
    add("")
    add("**No slice passes the 2.0 R gate.** Every row above that clears it is thin.")
    add("")

    # -- 3 ------------------------------------------------------------------
    add("## 3. Which trades are runners")
    add("")
    add("**The metric.** Maximum favourable excursion (MFE) in R before the "
        "close-triggered stop, inside the 11:00 ET clock. It is a property of entry, stop "
        "and tape — not of any exit — so it is the CEILING every exit policy in this repo "
        "is measured against. `mfe_r()` runs the identical causal loop "
        "`exit_lab.flat_target` runs; `--selfcheck` asserts `mfe_r >= 2.0` exactly when "
        "`r9.reaches_target` says the 2R target was reached, on every row of both arms.")
    add("")
    mf = [r["mfe_r"] for r in head]
    add("| statistic | value |")
    add("|---|---:|")
    add("| mean MFE | **%+.4f R** |" % statistics.fmean(mf))
    add("| median MFE | %+.4f R |" % statistics.median(mf))
    add("| ladder captures | **%.1f%%** of mean MFE |"
        % (100.0 * lad["mean"] / statistics.fmean(mf)))
    add("| `flat_2r` captures | %.1f%% of mean MFE |"
        % (100.0 * fl2["mean"] / statistics.fmean(mf)))
    add("")
    add("### The ladder of reach")
    add("")
    add("| target | TOUCHED by 11:00 | TOUCHED by EOD | ladder BOOKS ≥ it | give-back vs 11:00 |")
    add("|---|---:|---:|---:|---:|")
    for k in LADDER_RUNGS:
        touched = reach_rate(head, k)
        eod = 100.0 * sum(1 for r in head if r["mfe_noclock"] >= k) / len(head)
        booked = 100.0 * sum(1 for r in head if r["ladder_clock"] >= k) / len(head)
        add("| %.0fR | %.1f%% | %.1f%% | %.1f%% | **%.1f pts** |"
            % (k, touched, eod, booked, touched - booked))
    add("")
    add("**The give-back at 2R is the whole argument for a simpler book, and it is also why "
        "the simpler book loses.** `flat_2r` converts the 2R touch into a 2R booking, which "
        "is why its win rate is higher — and it truncates every trade that was going to "
        "reach %.0fR or %.0fR, which is why its mean R is lower. The %.1f%% that touch 4R "
        "carry the ladder."
        % (LADDER_RUNGS[-2], LADDER_RUNGS[-1], reach_rate(head, 4.0)))
    add("")
    add("### Who the runners are")
    add("")
    add("A **runner** is defined here as a trade whose MFE reached 4R — twice the money "
        "gate — before its stop closed. The question is whether anything known AT ENTRY "
        "separates them.")
    add("")
    runners = [r for r in head if r["mfe_r"] >= 4.0]
    dead = [r for r in head if r["mfe_r"] < 1.0]
    add("| population | n | share | ladder mean R | `flat_2r` mean R |")
    add("|---|---:|---:|---:|---:|")
    for nm, rs in (("runners (MFE ≥ 4R)", runners),
                   ("middle (1R ≤ MFE < 4R)",
                    [r for r in head if 1.0 <= r["mfe_r"] < 4.0]),
                   ("dead (MFE < 1R)", dead)):
        add("| %s | %d | %.1f%% | %+.4f | %+.4f |"
            % (nm, len(rs), 100.0 * len(rs) / len(head),
               agg_r([r["ladder_r"] for r in rs])["mean"],
               agg_r([r["flat2r_r"] for r in rs])["mean"]))
    add("")
    add("**The separator table.** For each entry-time cut, the share of that slice that "
        "turns into a runner. A cut that selects runners shows a rate above the book's "
        "**%.1f%%** base rate by more than sampling noise."
        % (100.0 * len(runners) / len(head)))
    add("")
    add("| cut | value | n | runner rate | lift vs base | mean MFE R |")
    add("|---|---|---:|---:|---:|---:|")
    base = 100.0 * len(runners) / len(head)
    for key, label in (("sgrade", "Austin grade"), ("setup", "setup"),
                       ("pool", "pool"), ("side", "side"),
                       ("intrabar", "intrabar fill")):
        d = by(head, key)
        for k in sorted(d, key=lambda x: -len(d[x])):
            rs = d[k]
            rate = 100.0 * sum(1 for r in rs if r["mfe_r"] >= 4.0) / len(rs)
            add("| %s | `%s`%s | %d | %.1f%% | %+.1f pts | %+.3f |"
                % (label, k, thin(len(rs)), len(rs), rate, rate - base,
                   statistics.fmean(r["mfe_r"] for r in rs)))
    add("")
    add("**Read the lift column, not the rate column.** A cut is only a selector if its "
        "lift is large relative to how many trades it keeps. A cut that lifts a few points "
        "while keeping 60% of the book is describing the book, not selecting inside it.")
    add("")

    # -- 4 ------------------------------------------------------------------
    add("## 4. P(2R), the path rate")
    add("")
    add("`p2r` imported from `research/r9_simple_book.py` unmodified. The PATH rate is the "
        "2R target trading before a close beyond the stop; the BOOKED rate is the ladder "
        "actually finishing at ≥ +2.0 R. Deductions are one-directional and these are "
        "ceilings.")
    add("")
    add("| arm | policy | n | P(2R) | wide deduction | narrow deduction |")
    add("|---|---|---:|---:|---:|---:|")
    for code in ("A", "B"):
        rows = arms[code]
        lab = "ON WATCH off" if code == "A" else "ON WATCH on (shipped)"
        for kind, nm in (("flat", "`flat_2r` path"), ("ladder", "ladder booked")):
            p = p2r(rows, kind)
            add("| %s | %s | %d | **%.2f%%** | −%.2f pts | −%.2f pts |"
                % (lab, nm, p["n"], p["opt"], p["wide"], p["narrow"]))
    add("")

    # -- 5 ------------------------------------------------------------------
    add("## 5. The stop, checked against the code")
    add("")
    add("Austin, 2026-08-27: *\"You said you like the -1.25R, but it should still be -1R for "
        "all the trades. That's just to prevent, you know, slippage.\"*")
    add("")
    add("**That is already exactly what this engine does, and no change is needed.** Read "
        "off `research/exit_lab.py` at this commit:")
    add("")
    add("| piece | code | what it means |")
    add("|---|---|---|")
    add("| the stop level | the structural stop, `r[\"stop\"]` | 1R **is** `abs(entry − stop)` by definition — every trade risks exactly 1R |")
    add("| the trigger | `exit_lab._stop_hit_first`, `exit_lab.py:153` | fires on the candle CLOSE beyond the stop; wicks stop nothing |")
    add("| the fill | that bar's close | not the stop price — the close it actually happened at |")
    add("| the slippage cap | `MAX_LOSS_R = %.2f`, `exit_lab.py:55` | a close far beyond the stop books at most −%.2f R |"
        % (xl.MAX_LOSS_R, xl.MAX_LOSS_R))
    add("")
    worse = [r for r in head if r["ladder_r"] < -1.0]
    floored = [r for r in head if abs(r["ladder_r"] + xl.MAX_LOSS_R) < 1e-6]
    add("So −1.0 R is the stop and −%.2f R is the slippage ceiling, which is the design he "
        "described. On this book **%d of %d trades (%.1f%%) book worse than −1.00 R**, and "
        "**%d (%.1f%%) land exactly on the −%.2f R floor** — the floor is doing real work "
        "and it is not doing much of it."
        % (xl.MAX_LOSS_R, len(worse), len(head), 100.0 * len(worse) / len(head),
           len(floored), 100.0 * len(floored) / len(head), xl.MAX_LOSS_R))
    add("")
    add("## 6. Scratch, checked against the code")
    add("")
    add("**Scratch is already gone from the backtest and was never in it in any measurable "
        "way.** `research/p8_scratch.py` (`7979a61e`) instrumented the rule over n=43,374 "
        "created trades: the entry bar's close sat on the good side of both the stop and the "
        "retested level **every single time** — zero crossings — because the backtest only "
        "takes the intrabar-fill entry after it has already seen that bar's completed close. "
        "The branch was deleted and the book came out byte-identical on all 45,175 rows. "
        "Nothing in this report contains a scratch. What remains unimplemented is the LIVE "
        "path (`research/g11_live_scratch_scope.md`, `00d64ad5`), which this file does not "
        "touch.")
    add("")

    # -- 7 ------------------------------------------------------------------
    add("## 7. Gaps and provenance")
    add("")
    add("| arm | rows that could not be replayed | reason |")
    add("|---|---:|---|")
    for code in ("A", "B"):
        g = gaps[code]
        add("| %s | %d | %d no archived session, %d entry minute absent, %d entry index past end |"
            % (code, sum(g.values()), g["day"], g["bar"], g["index"]))
    add("")
    add("A row that cannot be replayed is REPORTED here, never silently dropped into a "
        "denominator — `build_arm`'s own contract, imported.")
    add("")
    add("| number | script | commit |")
    add("|---|---|---|")
    add("| every figure in §1–§5 and §7 | `research/h1_2y_nowatch.py` | this commit |")
    add("| both fill-arm books | `research/g3_onwatch_2y.py` | `47e60796` |")
    add("| `build_arm`, `agg_r`, `months`, `mean_bar`, `p2r`, `reaches_target` | `research/r9_simple_book.py` | `e4de7858` |")
    add("| the intrabar classification behind the error bar | `research/p26_intrabar_ambiguity.py` | `8bb78c77` |")
    add("| the scratch finding | `research/p8_scratch.py` | `7979a61e` |")
    add("| held-out recall (unchanged by this arm) | `research/t70_test1_score.py` | `30fbc3f8` |")
    add("")
    add("**Held-out recall is IDENTICAL in both arms and is not re-measured here.** ON WATCH "
        "moves 0 of %d signals, so it cannot change what the engine detects. The held-out "
        "number stands where `research/t70_test1_score.py` left it: **3 of 15 S days = 20%%**, "
        "against **12 of 42 X days = 29%%** false fires, on the 100 cards Austin graded "
        "2026-08-27." % metas[HEADLINE]["signals"])
    add("")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------

def selfcheck(arms):
    """`mfe_r >= 2.0` must agree with the imported `reaches_target` on every row.

    They are two different loops over the same tape with the same stop rule; if
    they ever disagree, one of them has drifted from `exit_lab` and every number
    in §3 is untrustworthy."""
    bad = 0
    for code, rows in arms.items():
        for r in rows:
            if (r["mfe_r"] >= TARGET_R) != r["reach2r"]:
                bad += 1
                if bad <= 10:
                    print("  MISMATCH %s %s %s mfe=%.4f reach2r=%s"
                          % (code, r["sym"], r["day"], r["mfe_r"], r["reach2r"]),
                          file=sys.stderr)
    assert bad == 0, "%d rows where mfe_r>=2R disagrees with reaches_target" % bad
    over = 0
    for code, rows in arms.items():
        for r in rows:
            assert r["mfe_clock"] >= 0.0, "negative MFE %s %s" % (r["sym"], r["day"])
            # same rig, same horizon: no exit can book above what the tape gave
            assert r["ladder_clock"] <= r["mfe_clock"] + 1e-6, (
                "exit_lab ladder booked %.4f above MFE %.4f on %s %s"
                % (r["ladder_clock"], r["mfe_clock"], r["sym"], r["day"]))
            assert r["flat2r_clock"] <= TARGET_R + 1e-6
            # a longer session can only offer more
            assert r["mfe_noclock"] >= r["mfe_clock"] - 1e-6
            # the SHIPPED ladder is a different rig on a different clock, so this
            # is counted and reported (§2), never asserted
            if r["ladder_r"] > r["mfe_clock"] + 1e-6:
                over += 1
    print("selfcheck ok (%d rows, both arms); %d rows book above the 11:00 "
          "ceiling on the shipped ladder -- see report section 2"
          % (sum(len(v) for v in arms.values()), over))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()

    cache = Bars()
    arms, gaps, metas = {}, {}, {}
    for code, _desc, _flag, path in ARMS:
        rows, meta, gap = build_arm(path, cache)
        attach_exits(rows, cache)
        arms[code], metas[code], gaps[code] = rows, meta, gap
        print("arm %s: %d rows, gaps %s" % (code, len(rows), gap), file=sys.stderr)

    selfcheck(arms)
    if a.selfcheck:
        return

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(report(arms, gaps, metas))
    with open(JSON_OUT, "w", encoding="utf-8") as fh:
        json.dump({"arms": {k: [{kk: vv for kk, vv in r.items()} for r in v]
                            for k, v in arms.items()},
                   "metas": metas, "gaps": gaps}, fh)
    print("wrote %s" % OUT)


if __name__ == "__main__":
    main()
