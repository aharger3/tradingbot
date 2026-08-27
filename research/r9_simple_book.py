"""r9_simple_book.py -- T10/R9+A4: `flat_2r` as its own book, and whether the
fill is what makes 2R reachable.

WHY THIS EXISTS
---------------
Austin, asked what "simpler" means for the exit, picked `flat_2r` as a STANDALONE
BOOK rather than another column in a sweep, and tied it to the entry in the same
breath:

    "option 1, and stocks that dont fit that enter as candle forming concern and
     have better 2r probability"

Two claims, and the second is the interesting one:

  1. a flat 2R exit is simple enough to trust -- so show it as a book that could
     be traded on its own, against the 2.0R money gate and the every-month-green
     durability gate.
  2. the names that do NOT fit that book are the ones you have to enter on a
     candle that is still forming, and those have BETTER 2R probability.

Claim 2 is a statement about the FILL. `research/g7_exit_sweep.md` already swept
eight exit policies and none beat the incumbent ladder, so the exit is not where
the money gate is lost. Claim 2 says the fill might be. This file measures that.

WHAT THE TWO FILL ARMS ACTUALLY ARE -- READ BEFORE READING A DELTA
------------------------------------------------------------------
There is NO close-fill arm in this engine, and this file does not pretend to one.
`research/g3_onwatch_2y.md` (T3) established it: `signal_runner.fill_price`
back-dates a fill to the level when EITHER of two predicates is true, and
`ON_WATCH` gates only ONE of them, at 2 of `fill_price`'s 10 call sites:

    bar_extreme_veto      always live, never gated, reachable from all 10 sites
    near_session_extreme  gated by ON_WATCH, reachable from 2 sites (the long and
                          short break-and-retest fills)

So `ON_WATCH=0` leaves 74.7% of traded fills still intrabar. The arms this file
carries are therefore named for what they DO, not for what the flag is called:

    arm A  "bar-extreme back-dating only"        (ON_WATCH=0, research/g3_arm_ow0.json)
    arm B  "+ session-extreme back-dating"       (ON_WATCH=1, SHIPPED, g3_arm_ow1.json)

Arm B is arm A plus one extra class of intrabar fill: break-and-retest bars that
close jammed against the SESSION extreme without sitting at their own bar's
extreme. That extra class IS "the candle was still forming and you took it
anyway", which is the closest this engine gets to Austin's sentence. B-minus-A is
therefore the honest test of claim 2, and it is a test of MORE intrabar fill vs
LESS, never of intrabar vs close.

Both books were replayed by `research/g3_onwatch_2y.py`; this file re-reads them
and never re-runs the engine. Nothing here changes a default or adds a flag.

THE METRIC
----------
P(2R) is reported per policy, because the two policies convert the same path
differently:

    flat_2r          share of the traded book that REACHES the 2R target before a
                     close beyond the stop. This is the PATH rate -- it is a
                     property of entry/stop/tape and identical for any exit.
    incumbent ladder share of the traded book that BOOKS >= +2.0R. The ladder can
                     touch 2R and give it back, so this is the path rate after
                     the shipped exit has had its say.

`flat_2r`'s reach test is `research/exit_lab.flat_target(..., 2.0)` unchanged --
the shipped 11:00 clock, the shipped -1.25R floor, the shipped close-triggered
stop. `--selfcheck` asserts the boolean this file computes agrees with that
function returning exactly +2.0 on every traded row, so the path rate is not a
second implementation of the policy.

THE ERROR BAR
-------------
Carried inline on every cell, one-directional, built exactly the way
`research/g3_onwatch_2y.py::error_bars` builds the mean-R bar and using T2's
classification (`research/p26_intrabar_ambiguity.py`) rather than restating it.

An ambiguous row is an intrabar fill whose entry bar ALSO contains the trade's
stop; OHLCV cannot say which price traded first and the engine assumes
fill-then-stop every time. Repriced the other way the trade never happened, so
it never reached 2R and it books its stop. Hence:

    wide (carried)   every ambiguous intrabar row is repriced; the manufactured
                     `intrabar_stop` class included.
    narrow (floor)   only rows whose stop is NOT the entry bar's own extreme.

Both are DEDUCTIONS. The booked number is a ceiling, never a midpoint. Mean R is
repriced to `min(booked, -1.0)` rather than a flat -1.0: `exit_lab` floors a loss
at -1.25R where the backtest floors at the stop, so a flat -1.0 would IMPROVE
some rows and break the one-directionality the bar depends on. `--selfcheck`
asserts every pessimistic arm is <= its optimistic arm.

THE SAMPLE FLOOR
----------------
`universe.MIN_SAMPLE_N` (20, settled in `research/p12_sample_floor.md`). Per-symbol
rows below it are MARKED thin and excluded from the fit/does-not-fit verdict --
never dropped, and never excluded from a whole-book total.

USAGE
-----
    python research/r9_simple_book.py              # -> research/r9_simple_book.md
    python research/r9_simple_book.py --selfcheck

Bars are read from `data_archive/` only, through `p26.load_day`, whose guard
makes a network fetch impossible -- so this can never touch POLYGON_API_KEY.
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

# T2's rig: the intrabar marker with its 2dp rounding correction, the two
# trigger predicates, and the ambiguity test. Imported, never restated.
from research import p26_intrabar_ambiguity as p26          # noqa: E402
# The shipped exit policies. `flat_target` is used unmodified.
from research import exit_lab as xl                         # noqa: E402
# The whole-book money read every other 2-year report in this repo prints.
from research.a2_bt2y_summary import book as money          # noqa: E402
# The single source of truth for symbols and for the sample floor.
from universe import CORE_SYMBOLS, INDEX_POOL, MIN_SAMPLE_N, pool_for   # noqa: E402

OUT = os.path.join(HERE, "r9_simple_book.md")

# The two fill arms, replayed by research/g3_onwatch_2y.py. Labels say what the
# arm DOES; the flag name is kept beside it so the join back to T3 is obvious.
ARMS = [
    ("A", "bar-extreme back-dating only", "ON_WATCH=0",
     os.path.join(HERE, "g3_arm_ow0.json")),
    ("B", "+ session-extreme back-dating", "ON_WATCH=1, shipped",
     os.path.join(HERE, "g3_arm_ow1.json")),
]
SHIPPED_ARM = "B"

# Austin's 12-name roster. CORE_SYMBOLS + INDEX_POOL, imported, never retyped.
# QQQ is in both; the union is 12 names.
ROSTER = sorted(set(CORE_SYMBOLS) | set(INDEX_POOL))

TARGET_R = 2.0
MONEY_GATE = 2.0


# ---------------------------------------------------------------------------
# bars -- one load per symbol-day, archive only
# ---------------------------------------------------------------------------

class Bars:
    """Per-symbol-day cache of everything both rigs need from the tape.

    `exit_lab` wants `{t,o,h,l,c}` dicts; `p26.classify` wants the candle object
    plus the running session extremes at the entry bar. Both come off ONE read
    of the same archived session, so the two rigs can never disagree about the
    tape."""

    def __init__(self):
        self._c = {}
        self.missing_day = 0
        self.missing_bar = 0

    def get(self, sym, day):
        key = (sym, day)
        if key not in self._c:
            rth = p26.load_day(sym, day)
            if not rth:
                self._c[key] = None
            else:
                idx, run_hi, run_lo = p26.index_day(rth)
                dicts = [{"t": c.timestamp[:5], "o": c.open, "h": c.high,
                          "l": c.low, "c": c.close} for c in rth]
                self._c[key] = (rth, dicts, idx, run_hi, run_lo)
        return self._c[key]


# ---------------------------------------------------------------------------
# the path rate: does the trade reach 2R before a close beyond the stop
# ---------------------------------------------------------------------------

def reaches_target(bars, entry_i, entry, stop, side, target_r=TARGET_R):
    """True iff the ``target_r`` target trades before the stop triggers.

    Deliberately the SAME loop `exit_lab.flat_target` runs -- same causal scan
    from entry_i+1, same 11:00 clock backstop, same close-triggered stop, same
    pessimistic same-bar convention (a bar that closes beyond the stop wins even
    if the target also traded in it). It exists only to name the outcome, and
    `selfcheck` asserts it agrees with `flat_target(...) == +2.0` on every row.
    Reimplementing the policy is exactly the mistake it is asserted against."""
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return False
    target = entry + target_r * risk if side == "L" else entry - target_r * risk
    end = min(xl.CLOCK_BAR + 1, n)
    for i in range(entry_i + 1, end):
        if xl._stop_hit_first(bars, i, entry, stop, side):
            return False
        b = bars[i]
        if (b["h"] >= target) if side == "L" else (b["l"] <= target):
            return True
    return False


# ---------------------------------------------------------------------------
# build one arm
# ---------------------------------------------------------------------------

def build_arm(path, cache):
    """Every traded row of one arm, with its flat_2r result and its T2 class.

    Returns (rows, meta, gaps). A row that cannot be replayed -- no archived
    session, or an entry minute with no bar -- is REPORTED as a gap, never
    silently dropped into a denominator."""
    with open(path, encoding="utf-8") as fh:
        blob = json.load(fh)
    meta = blob["meta"]
    gaps = {"day": 0, "bar": 0, "index": 0}
    rows = []
    for r in blob["trades"]:
        if not r["traded"]:
            continue
        got = cache.get(r["sym"], r["day"])
        if got is None:
            gaps["day"] += 1
            continue
        rth, dicts, idx, run_hi, run_lo = got
        i = idx.get(r["et"])
        if i is None:
            gaps["bar"] += 1
            continue
        ei = r["entry_i"]
        if ei >= len(dicts):
            gaps["index"] += 1
            continue
        side = r.get("side") or ("L" if r["dir"] == "call" else "S")
        entry, stop = float(r["entry"]), float(r["stop"])
        cls = p26.classify(r, rth[i], run_hi[i], run_lo[i])
        f2 = xl.flat_target(dicts, ei, entry, stop, side, TARGET_R)
        rows.append({
            "sym": r["sym"], "day": r["day"], "ym": r["ym"],
            "pool": pool_for(r["sym"]), "sgrade": r.get("sgrade"),
            "side": side, "entry_i": ei, "bar_i": i,
            "setup": r["setup"], "entry": entry, "stop": stop,
            "ladder_r": float(r["r"]),          # backtest_2y ladder B, as booked
            "flat2r_r": f2,                     # exit_lab flat_2r, shipped clock
            "reach2r": reaches_target(dicts, ei, entry, stop, side),
            # T2's classification, for the error bar
            "intrabar": cls["intrabar"],
            "amb": cls["intrabar"] and cls["amb_possible"],
            "at_extreme": cls["at_extreme"],
            "ow_only": cls["on_watch"] and not cls["bar_extreme"],
        })
    return rows, meta, gaps


# ---------------------------------------------------------------------------
# aggregation
# ---------------------------------------------------------------------------

def agg_r(rs):
    """(n, mean, median, win%, total). Win rate is of DECIDED rows -- scratches
    (R == 0) excluded -- the convention `research/a2_bt2y_summary.py::book`
    prints and every other 2-year table in this repo follows."""
    rs = [x for x in rs if x is not None]
    if not rs:
        return {"n": 0, "mean": 0.0, "median": 0.0, "wr": 0.0, "tot": 0.0}
    w = sum(1 for x in rs if x > 0)
    dec = sum(1 for x in rs if x != 0)
    return {"n": len(rs), "mean": statistics.fmean(rs),
            "median": statistics.median(rs),
            "wr": 100.0 * w / dec if dec else 0.0, "tot": sum(rs)}


def months(rows, key):
    """(green, total, worst month) over calendar months present in the slice."""
    by = defaultdict(float)
    for r in rows:
        by[r["ym"]] += r[key]
    if not by:
        return 0, 0, None, 0.0
    worst = min(by.items(), key=lambda kv: kv[1])
    return (sum(1 for v in by.values() if v > 0), len(by),
            worst[0], worst[1])


def mean_bar(rows, key):
    """Optimistic mean R and its two one-directional deductions.

    Pessimistic repricing is `min(booked, -1.0)`: the trade never happened, so
    it books its stop. The `min` keeps the bar strictly one-directional even
    though `exit_lab` floors a loss at -1.25R (the backtest floors at the stop),
    which a flat -1.0 would silently IMPROVE."""
    if not rows:
        return {"opt": 0.0, "wide": 0.0, "narrow": 0.0}
    opt = statistics.fmean(r[key] for r in rows)
    wide = statistics.fmean(min(r[key], -1.0) if r["amb"] else r[key] for r in rows)
    narrow = statistics.fmean(
        min(r[key], -1.0) if (r["amb"] and not r["at_extreme"]) else r[key]
        for r in rows)
    return {"opt": opt, "wide": opt - wide, "narrow": opt - narrow}


def matched(arms):
    """The same trade in both arms, so the fill can be A/B'd without survivorship.

    Arm B's traded book is 74 rows SMALLER than arm A's: a fill back-dated to the
    level lands on or through the level-stop, and the trade leaves the book
    through `signal_runner.intrabar_stop` or the minimum-risk gate. Any statistic
    computed on each arm's own book therefore compares different trades, and the
    trades arm B is missing are the ones the back-dated fill killed -- the
    direction that FLATTERS arm B. This joins the two books instead.

    Key is (sym, day, entry_i, side, setup). Keys that are not unique within an
    arm are excluded and counted, never silently collapsed.

    Returns (both, moved, same, dupes) where each is a list of (a_row, b_row):
      both   the trade exists in both arms
      moved  ... and its entry or stop differs -- the fill actually moved
      same   ... and both are identical, so the replay MUST agree bit for bit
             (`selfcheck` asserts exactly that)
    """
    def index(rows):
        by = defaultdict(list)
        for r in rows:
            by[(r["sym"], r["day"], r["entry_i"], r["side"], r["setup"])].append(r)
        return by

    ia, ib = index(arms["A"]), index(arms["B"])
    dupes = sum(1 for by in (ia, ib) for v in by.values() if len(v) > 1)
    both, moved, same = [], [], []
    for k in ia:
        if k not in ib or len(ia[k]) != 1 or len(ib[k]) != 1:
            continue
        a, b = ia[k][0], ib[k][0]
        both.append((a, b))
        if abs(a["entry"] - b["entry"]) > 1e-9 or abs(a["stop"] - b["stop"]) > 1e-9:
            moved.append((a, b))
        else:
            same.append((a, b))
    return both, moved, same, dupes


def candidates(arms):
    """The FIXED candidate set, and what each arm does with it.

    This is the only construction in the file that is not contaminated by
    survivorship, and it is the one the ticket turns on.

    The candidate set is arm A's rows where `near_session_extreme` is the ONLY
    predicate that could have moved the price -- i.e. every signal the extra
    intrabar-fill class can reach, taken at the close in A and back-dated to the
    level in B. The denominator is then held FIXED at that set for both arms.

    A candidate that does not appear in arm B's traded book did not become a
    better trade; it stopped being a trade. The back-dated fill landed on or
    through its own level-stop, so `signal_runner.intrabar_stop` or the
    minimum-risk gate removed it. It reached no target, so it counts as a
    non-hit in B rather than vanishing from the denominator -- which is what
    every per-arm table in this repo silently does.

    Returns (cand, surv, killed): the candidate rows, the (a_row, b_row) pairs
    that survive into B, and the candidates B never traded.
    """
    def keyf(r):
        return (r["sym"], r["day"], r["entry_i"], r["side"], r["setup"])
    kb = {}
    for r in arms["B"]:
        kb.setdefault(keyf(r), r)
    cand = [r for r in arms["A"] if r["ow_only"]]
    surv = [(r, kb[keyf(r)]) for r in cand if keyf(r) in kb]
    killed = [r for r in cand if keyf(r) not in kb]
    assert len(surv) + len(killed) == len(cand)
    return cand, surv, killed


def p2r(rows, kind):
    """P(2R) with its two one-directional deductions, in percentage points.

    kind='flat'   the PATH rate: reaches the 2R target before a close beyond the
                  stop. Identical for any exit policy on the same entry/stop.
    kind='ladder' the BOOKED rate: the shipped ladder B actually books >= +2.0R.

    An ambiguous row may have been stopped before the fill ever happened, so it
    reached nothing. Both deductions therefore strike hits, never add them."""
    n = len(rows)
    if not n:
        return {"n": 0, "opt": 0.0, "wide": 0.0, "narrow": 0.0, "hits": 0}
    hit = ((lambda r: r["reach2r"]) if kind == "flat"
           else (lambda r: r["ladder_r"] >= TARGET_R))
    hits = [r for r in rows if hit(r)]
    opt = 100.0 * len(hits) / n
    wide = 100.0 * sum(1 for r in hits if not r["amb"]) / n
    narrow = 100.0 * sum(1 for r in hits
                         if not (r["amb"] and not r["at_extreme"])) / n
    return {"n": n, "opt": opt, "wide": opt - wide, "narrow": opt - narrow,
            "hits": len(hits)}


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------

def report(arms, gaps, metas):
    ship = arms[SHIPPED_ARM]
    other = arms["A"]
    L = []
    add = L.append

    b_ship = mean_bar(ship, "flat2r_r")
    a_ship = agg_r([r["flat2r_r"] for r in ship])
    mg, mt, worst_m, worst_v = months(ship, "flat2r_r")
    lad = agg_r([r["ladder_r"] for r in ship])
    lmg, lmt, _, _ = months(ship, "ladder_r")

    p_flat = {k: p2r(v, "flat") for k, v in arms.items()}
    p_lad = {k: p2r(v, "ladder") for k, v in arms.items()}
    d_flat = p_flat["B"]["opt"] - p_flat["A"]["opt"]
    d_lad = p_lad["B"]["opt"] - p_lad["A"]["opt"]

    both, moved, same, dupes = matched(arms)
    cand, surv, killed = candidates(arms)
    # The risk unit on the pairs whose fill genuinely moved. R is denominated in
    # |entry - stop|, so a back-dated fill that tightens the stop moves the 2R
    # target nearer in PRICE -- the metric's own denominator changes with the arm.
    _rr = [abs(b["entry"] - b["stop"]) / abs(a["entry"] - a["stop"])
           for a, b in moved if abs(a["entry"] - a["stop"]) > 0]
    risk_med = statistics.median(_rr) if _rr else 1.0
    risk_mean = statistics.fmean(_rr) if _rr else 1.0
    risk_smaller = sum(1 for x in _rr if x < 1.0 - 1e-9)
    per_sym = symbol_rows(ship)
    thick = [s for s in per_sym if s["n"] >= MIN_SAMPLE_N]
    misfit = [s for s in thick if s["delta"] < 0]
    fit = [s for s in thick if s["delta"] >= 0]
    thin = [s for s in per_sym if s["n"] < MIN_SAMPLE_N]

    # ---- headline -------------------------------------------------------
    add("# R9 / A4 — `flat_2r` as its own book, and what the fill is worth")
    add("")
    add("**A flat 2R exit is a real book and it is not the shipped one: %d trades, "
        "mean %+.4f R, %d of %d months green — it fails the 2.0R money gate by "
        "%.4f R and fails durability, and it books %.4f R LESS than the incumbent "
        "ladder on the identical entry set.** Its one genuine advantage is the one "
        "Austin asked about: it reaches 2R on **%.1f%%** of trades where the shipped "
        "ladder only KEEPS 2R on %.1f%%."
        % (a_ship["n"], a_ship["mean"], mg, mt, MONEY_GATE - a_ship["mean"],
           lad["mean"] - a_ship["mean"], p_flat[SHIPPED_ARM]["opt"],
           p_lad[SHIPPED_ARM]["opt"]))
    add("")
    _ca = p2r(cand, "flat")
    _cb_hits = sum(1 for _, b in surv if b["reach2r"])
    _itt = 100.0 * _cb_hits / len(cand) if cand else 0.0
    _pp = 100.0 * _cb_hits / len(surv) if surv else 0.0
    add("**The intrabar fill does NOT raise P(2R). It halves it.** Take the %d "
        "signals the extra intrabar-fill class can actually reach — the closest this "
        "engine gets to \"enter as the candle is forming\" — and hold the denominator "
        "fixed. Filled at the close they reach 2R **%.2f%%** of the time. Back-dated "
        "into the still-forming candle, **%.2f%%**. The %.2f%% you get by scoring "
        "only the %d that survive is survivorship: **%d of the %d never reach the "
        "traded book at all**, because the earlier fill puts them on or through "
        "their own stop. And on the survivors the earlier fill shrinks the risk unit "
        "to a median %.0f%% of its close-fill value, so \"2R\" is a %.0f%% smaller "
        "price move — the goalposts move with the metric."
        % (len(cand), _ca["opt"], _itt, _pp, len(surv), len(killed), len(cand),
           100.0 * risk_med, 100.0 * (1.0 - risk_med)))
    add("")
    add("That sends the question back to entry SELECTION, which is where "
        "`research/g7_exit_sweep.md` (eight exit policies, none beat the ladder) and "
        "the G4/G9 line already pointed. **The exit was not the constraint and "
        "neither is the fill.**")
    add("")
    add("Read-only. No default changed, no flag added, no bar fetched — both books "
        "were replayed by `research/g3_onwatch_2y.py` and are re-read here.")
    add("")

    # ---- the two arms, named -------------------------------------------
    add("## The two fill arms, named for what they do")
    add("")
    add("There is **no close-fill arm in this engine** and this file does not pretend "
        "to one. `research/g3_onwatch_2y.md` (T3) settled it: `signal_runner.fill_price` "
        "back-dates a fill on EITHER of two predicates, and `ON_WATCH` gates only one "
        "of them, at 2 of that function's 10 call sites. Turning the flag off still "
        "leaves 74.7% of traded fills intrabar. So the arms are named for what they "
        "do:")
    add("")
    add("| arm | what back-dates a fill | flag | traded | intrabar fills | of traded |")
    add("|---|---|---|---:|---:|---:|")
    for code, label, flag, _ in ARMS:
        rs = arms[code]
        ib = sum(1 for r in rs if r["intrabar"])
        add("| **%s** — %s | %s | `%s` | %s | %s | %.1f%% |"
            % (code, label,
               "`bar_extreme_veto` only" if code == "A" else
               "`bar_extreme_veto` **plus** break-and-retest bars closing jammed "
               "against the session extreme",
               flag, f"{len(rs):,}", f"{ib:,}", 100.0 * ib / len(rs)))
    add("")
    ow_b = sum(1 for r in arms["B"] if r["ow_only"])
    ow_a = sum(1 for r in arms["A"] if r["ow_only"])
    add("**B is A plus one extra class of intrabar fill, and that class is the whole "
        "experiment.** %d rows of arm B's %s traded (%d of arm A's %s) have "
        "`near_session_extreme` as the ONLY predicate that could have moved their "
        "price — those are the rows where B fills at the level and A fills at the "
        "close. Everything else fills identically in both arms. So B−A is a test of "
        "MORE intrabar fill against LESS, never of intrabar against close, and a "
        "delta measured across the whole book is diluted by every row the two arms "
        "agree on."
        % (ow_b, f"{len(arms['B']):,}", ow_a, f"{len(arms['A']):,}"))
    add("")

    # ---- Deliverable 1 --------------------------------------------------
    add("## Deliverable 1 — `flat_2r` as a standalone book")
    add("")
    add("The shipped fill arm (**B**), the shipped 11:00 ET force-flat "
        "(`exit_lab.CLOCK_BAR = 90`), the shipped close-triggered stop floored at "
        "−1.25R (`exit_lab.MAX_LOSS_R`). 100% of the position out at +2.0R, nothing "
        "else: no tranches, no trail, no break-even move, no HOD rule. `research/"
        "g7_exit_sweep.md` already showed the no-clock arm is worse for every "
        "trailing policy and worth +0.000 R to `flat_2r` itself, so only the clock "
        "arm is carried here.")
    add("")
    add("Win rate is of DECIDED trades (R = 0 scratches excluded), the convention "
        "`research/a2_bt2y_summary.py::book` prints. The incumbent row is "
        "`backtest_2y.py`'s own ladder-B result on the identical entry set — same "
        "entries, same stops, same sides, only the exit differs.")
    add("")
    add("| book | n | mean R | median R | win rate | total R | months green | worst month |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|")
    add("| **`flat_2r`** (this ticket) | %s | **%+.4f** | %+.4f | %.1f%% | %+.1f | "
        "**%d / %d** | %s %+.1f |"
        % (f"{a_ship['n']:,}", a_ship["mean"], a_ship["median"], a_ship["wr"],
           a_ship["tot"], mg, mt, worst_m, worst_v))
    lworst_m, lworst_v = months(ship, "ladder_r")[2:]
    add("| incumbent ladder B (shipped) | %s | %+.4f | %+.4f | %.1f%% | %+.1f | "
        "**%d / %d** | %s %+.1f |"
        % (f"{lad['n']:,}", lad["mean"], lad["median"], lad["wr"], lad["tot"],
           lmg, lmt, lworst_m, lworst_v))
    add("| **gate** | — | **≥ +2.0000** | — | — | — | **%d / %d** | > 0 |" % (mt, mt))
    add("")
    add("**It fails both gates, and it fails the money gate by more than the ladder "
        "does.** Mean R is %+.4f against a gate of %+.4f — short by %.4f R, where the "
        "ladder is short by %.4f R. Durability needs EVERY month green and `flat_2r` "
        "delivers %d of %d; the ladder delivers %d of %d. The trade `flat_2r` makes "
        "is %.1f points of win rate for %.4f R of mean R, which is the same trade "
        "every fixed target in `research/g7_exit_sweep.md` makes and the same one it "
        "loses."
        % (a_ship["mean"], MONEY_GATE, MONEY_GATE - a_ship["mean"],
           MONEY_GATE - lad["mean"], mg, mt, lmg, lmt,
           a_ship["wr"] - lad["wr"], a_ship["mean"] - lad["mean"]))
    add("")
    add("### Per pool")
    add("")
    add("`universe.pool_for`, imported. `index` is QQQ/SPY/IWM, `equity` is the "
        "MAJOR_15, `other` is the rest of the 28-symbol replay. Rows under "
        "`universe.MIN_SAMPLE_N` (%d) are marked thin — marked, not dropped, and "
        "still inside every whole-book total above." % MIN_SAMPLE_N)
    add("")
    add("| pool | n | mean R `flat_2r` | mean R ladder | delta | win rate | "
        "months green | P(2R) |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|")
    for pool in ("index", "equity", "other"):
        rs = [r for r in ship if r["pool"] == pool]
        if not rs:
            continue
        f = agg_r([r["flat2r_r"] for r in rs])
        l = agg_r([r["ladder_r"] for r in rs])
        g, t, _, _ = months(rs, "flat2r_r")
        p = p2r(rs, "flat")
        thin_m = " _(thin)_" if f["n"] < MIN_SAMPLE_N else ""
        add("| `%s`%s | %s | %+.4f | %+.4f | %+.4f | %.1f%% | %d / %d | %.1f%% |"
            % (pool, thin_m, f"{f['n']:,}", f["mean"], l["mean"],
               f["mean"] - l["mean"], f["wr"], g, t, p["opt"]))
    add("")
    add("### Per grade")
    add("")
    add("| Austin grade | n | mean R `flat_2r` | mean R ladder | delta | P(2R) |")
    add("|---|---:|---:|---:|---:|---:|")
    for gr in ("S", "A", "C"):
        rs = [r for r in ship if r["sgrade"] == gr]
        if not rs:
            continue
        f = agg_r([r["flat2r_r"] for r in rs])
        l = agg_r([r["ladder_r"] for r in rs])
        p = p2r(rs, "flat")
        add("| %s | %s | %+.4f | %+.4f | %+.4f | %.1f%% |"
            % (gr, f"{f['n']:,}", f["mean"], l["mean"], f["mean"] - l["mean"],
               p["opt"]))
    add("")

    # ---- Deliverable 2 --------------------------------------------------
    add("## Deliverable 2 — P(2R), four ways")
    add("")
    add("**The metric.** `flat_2r`'s row is the PATH rate: the 2R target trades "
        "before a close beyond the stop. It is a property of entry, stop and tape, "
        "so it is what ANY exit has available to it. The ladder's row is the BOOKED "
        "rate: ladder B actually finishes at ≥ +2.0R. The gap between them is what "
        "the shipped exit gives back after 2R has already printed.")
    add("")
    add("**The error bar is inline and it is one-directional.** An ambiguous row is "
        "an intrabar fill whose entry bar also contains the trade's stop; OHLCV "
        "cannot say which traded first and the engine assumes fill-then-stop every "
        "time. Priced the other way the trade never happened, so it reached nothing "
        "— every deduction strikes hits and none adds any. Wide strikes the whole "
        "ambiguous class; narrow strikes only rows whose stop is not the entry bar's "
        "own extreme (T3: 2 rows of 913 on the shipped arm). **These are ceilings, "
        "not midpoints.**")
    add("")
    add("| policy | fill arm | n | **P(2R)** | error bar (wide / narrow) | "
        "P(2R) at the wide floor | mean R | mean R error bar |")
    add("|---|---|---:|---:|---:|---:|---:|---:|")
    for kind, key, name in (("flat", "flat2r_r", "`flat_2r`"),
                            ("ladder", "ladder_r", "incumbent ladder B")):
        for code, label, flag, _ in ARMS:
            rs = arms[code]
            p = p2r(rs, kind)
            mb = mean_bar(rs, key)
            star = " (shipped)" if code == SHIPPED_ARM else ""
            add("| %s | **%s** %s%s | %s | **%.2f%%** | ∓%.2f pts / ∓%.2f pts | "
                "%.2f%% | %+.4f | ∓%.4f / ∓%.4f |"
                % (name, code, label, star, f"{p['n']:,}", p["opt"], p["wide"],
                   p["narrow"], p["opt"] - p["wide"], mb["opt"], mb["wide"],
                   mb["narrow"]))
    add("")
    add("| delta (B − A), each arm's own book | P(2R) | vs the WIDE bar (carried) | "
        "vs the NARROW floor |")
    add("|---|---:|---|---|")
    add("| `flat_2r` (path) | **%+.2f pts** | %s | %s |"
        % (d_flat, _verdict(d_flat, p_flat["B"]["wide"]),
           _verdict(d_flat, p_flat["B"]["narrow"])))
    add("| incumbent ladder B (booked) | **%+.2f pts** | %s | %s |"
        % (d_lad, _verdict(d_lad, p_lad["B"]["wide"]),
           _verdict(d_lad, p_lad["B"]["narrow"])))
    add("")
    add("**Both bars are reported and the split is the same one T3 hit.** The wide "
        "bar strikes the `intrabar_stop` class, which is manufactured by a stop rule "
        "rather than found in the tape — but manufactured is not resolved, and "
        "whether a stop resting on the entry bar's own wick is reachable inside that "
        "bar is **Austin's call and he has not made it**. Against the wide bar this "
        "delta is noise; against the narrow floor it clears. Neither answers the "
        "ticket, because both are computed on **each arm's own book** and those are "
        "different sets of trades. The next table removes that.")
    add("")

    # ---- the matched subset --------------------------------------------
    add("### First correction — the same trade in both arms")
    add("")
    add("Everything above compares each arm's own book, and those are **not the same "
        "trades**. Arm B's traded book is %d rows smaller than arm A's, and the "
        "missing rows are not random: a fill back-dated to the level lands on or "
        "through the level-stop, so the trade is re-stopped on its own entry bar by "
        "`signal_runner.intrabar_stop` or dropped by the minimum-risk gate. **The "
        "trades the intrabar fill kills never appear in arm B at all.** That is "
        "survivorship, and it runs in the direction that FLATTERS arm B — so a "
        "whole-book delta cannot separate \"the fill is better\" from \"the losers "
        "were deleted\"."
        % (len(arms["A"]) - len(arms["B"])))
    add("")
    add("So the two books are joined on `(sym, day, entry_i, side, setup)` and the "
        "delta is taken only where the SAME trade exists in both arms:")
    add("")
    add("| set | pairs | P(2R) arm A | P(2R) arm B | **delta** | mean R A | "
        "mean R B | delta |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|")
    for name, pairs, note in (
            ("all matched pairs", both, ""),
            ("**of those, the fill actually MOVED**", moved,
             " — B fills at the level, A at the close"),
            ("of those, entry and stop identical", same, " — must agree exactly")):
        if not pairs:
            add("| %s%s | 0 | — | — | — | — | — | — |" % (name, note))
            continue
        pa = p2r([a for a, _ in pairs], "flat")
        pb = p2r([b for _, b in pairs], "flat")
        fa = agg_r([a["flat2r_r"] for a, _ in pairs])
        fb = agg_r([b["flat2r_r"] for _, b in pairs])
        thin_m = " _(thin, n<%d)_" % MIN_SAMPLE_N if len(pairs) < MIN_SAMPLE_N else ""
        add("| %s%s%s | %s | %.1f%% | %.1f%% | **%+.2f pts** | %+.4f | %+.4f | "
            "%+.4f |"
            % (name, note, thin_m, f"{len(pairs):,}", pa["opt"], pb["opt"],
               pb["opt"] - pa["opt"], fa["mean"], fb["mean"],
               fb["mean"] - fa["mean"]))
    add("")
    mp_a = p2r([a for a, _ in moved], "flat") if moved else {"opt": 0.0}
    mp_b = p2r([b for _, b in moved], "flat") if moved else {"opt": 0.0}
    mv = mp_b["opt"] - mp_a["opt"]
    fm_a = agg_r([a["flat2r_r"] for a, _ in moved]) if moved else {"mean": 0.0}
    fm_b = agg_r([b["flat2r_r"] for _, b in moved]) if moved else {"mean": 0.0}
    add("The bottom row is the control and it is why the rest can be believed: %s "
        "pairs whose entry and stop are identical in both arms must replay "
        "identically, and `--selfcheck` asserts they do — same P(2R), same mean R, "
        "to 1e-9. Any drift there would mean the two books disagree about the tape "
        "rather than about the fill." % f"{len(same):,}")
    add("")
    add("**The middle row looks like Austin is right, and it is the wrong number.** "
        "%+.2f points of P(2R) and %+.4f R, on %d pairs. It is wrong for a reason "
        "that is visible from the join itself: **matching on trades that exist in "
        "BOTH arms still conditions on surviving arm B.** The pair only exists "
        "because the back-dated fill did not kill the trade. That is the same "
        "survivorship, one level down."
        % (mv, fm_b["mean"] - fm_a["mean"], len(moved)))
    add("")

    # ---- the ITT table, the load-bearing one ----------------------------
    ca = p2r(cand, "flat")
    cb_hits = sum(1 for _, b in surv if b["reach2r"])
    surv_a = p2r([a for a, _ in surv], "flat")
    itt = 100.0 * cb_hits / len(cand) if cand else 0.0
    pp = 100.0 * cb_hits / len(surv) if surv else 0.0
    add("### The fixed candidate set — the only view that is not survivorship")
    add("")
    add("So the denominator is nailed down. The candidate set is **every one of arm "
        "A's %d signals where `near_session_extreme` is the only predicate that "
        "could move the price** — the complete population the extra intrabar-fill "
        "class can reach, filled at the close in A and back-dated to the level in B. "
        "Both arms are then scored over that SAME %d, and a candidate arm B never "
        "traded counts as a non-hit rather than disappearing: **it did not become a "
        "better trade, it stopped being a trade.** The back-dated fill landed on or "
        "through its own level-stop and `signal_runner.intrabar_stop` or the "
        "minimum-risk gate removed it." % (len(cand), len(cand)))
    add("")
    add("| view | denominator | 2R hits | **P(2R)** | vs arm A |")
    add("|---|---:|---:|---:|---:|")
    add("| **A** — filled at the close | %d | %d | **%.2f%%** | — |"
        % (len(cand), ca["hits"], ca["opt"]))
    add("| **B** — back-dated into the forming candle, **intention-to-treat** | %d | "
        "%d | **%.2f%%** | **%+.2f pts** |"
        % (len(cand), cb_hits, itt, itt - ca["opt"]))
    add("| _B, survivors only (per-protocol)_ | %d | %d | _%.2f%%_ | _%+.2f pts_ |"
        % (len(surv), cb_hits, pp, pp - surv_a["opt"]))
    add("| _A, on those same survivors_ | %d | %d | _%.2f%%_ | _—_ |"
        % (len(surv), surv_a["hits"], surv_a["opt"]))
    add("")
    add("**%d of the %d candidates — %.0f%% — never reach arm B's traded book at "
        "all.** Held to the fixed denominator, back-dating the fill takes P(2R) from "
        "**%.2f%% to %.2f%%**: it does not raise the odds of reaching 2R, it **more "
        "than halves them**. The %.2f%% per-protocol figure is what you get by "
        "scoring only the %d that lived."
        % (len(killed), len(cand), 100.0 * len(killed) / len(cand),
           ca["opt"], itt, pp, len(surv)))
    add("")
    kf = agg_r([r["flat2r_r"] for r in killed])
    add("And the trades it removes are not disasters it saved you from. Under the "
        "close fill those %d killed candidates book a mean **%+.4f R** under "
        "`flat_2r` — roughly flat. The earlier fill does not cut a tail off the "
        "book; it converts %.0f%% of a break-even population into no-trades and "
        "keeps the %d that were already working."
        % (len(killed), kf["mean"], 100.0 * len(killed) / len(cand), len(surv)))
    add("")
    add("**There is a second reason the per-protocol number cannot be read as an "
        "edge, and it is arithmetic.** R is denominated in `|entry − stop|`, and "
        "back-dating the entry to the level shrinks exactly that. On the %d surviving "
        "moved pairs arm B's risk unit is a **median %.0f%% of arm A's** (mean %.0f%%; "
        "smaller in %d of %d). So arm B's 2R target sits about **%.0f%% nearer in "
        "price** than arm A's on the same trade. A nearer target is hit more often "
        "whether or not the fill was better — the goalposts moved with the metric."
        % (len(moved), 100.0 * risk_med, 100.0 * risk_mean, risk_smaller, len(moved),
           100.0 * (1.0 - risk_med)))
    add("")
    add("For completeness, the un-matched view — each arm's own rows where "
        "`near_session_extreme` is the ONLY predicate that could have moved the "
        "price. **This is the table survivorship ruins**, kept only so the size of "
        "that ruin is visible:")
    add("")
    add("| arm | rows where session-extreme is the only trigger | P(2R) path | "
        "mean R `flat_2r` | mean R ladder |")
    add("|---|---:|---:|---:|---:|")
    for code, label, flag, _ in ARMS:
        rs = [r for r in arms[code] if r["ow_only"]]
        p = p2r(rs, "flat")
        f = agg_r([r["flat2r_r"] for r in rs])
        l = agg_r([r["ladder_r"] for r in rs])
        thin_m = " _(thin, n<%d)_" % MIN_SAMPLE_N if len(rs) < MIN_SAMPLE_N else ""
        add("| **%s** — %s%s | %d | %.1f%% | %+.4f | %+.4f |"
            % (code, label, thin_m, len(rs), p["opt"], f["mean"], l["mean"]))
    add("")
    sub_a = p2r([r for r in arms["A"] if r["ow_only"]], "flat")
    sub_b = p2r([r for r in arms["B"] if r["ow_only"]], "flat")
    add("That reads as %+.1f points of P(2R) and it is **an artefact**: arm A's %d "
        "rows include every trade the back-dated fill would have killed, and arm B's "
        "%d do not. The fixed-denominator table above is the same question with those "
        "rows held in place, and it answers %+.2f points."
        % (sub_b["opt"] - sub_a["opt"], sub_a["n"], sub_b["n"], itt - ca["opt"]))
    add("")

    # ---- Deliverable 2b: per symbol -------------------------------------
    add("## Which names do not fit a flat 2R exit")
    add("")
    add("Austin's roster: `universe.CORE_SYMBOLS` + `universe.INDEX_POOL`, imported "
        "— %d names (QQQ is in both). The shipped fill arm. **The rule is stated "
        "before the numbers: a name FITS if swapping the incumbent ladder for "
        "`flat_2r` does not lose money on it — `delta = mean R flat_2r − mean R "
        "ladder ≥ 0`.** That is the actual decision the ticket is about; P(2R) is "
        "shown beside it as the mechanism, not as the test. Rows under "
        "`universe.MIN_SAMPLE_N` (%d) are marked **thin** and are excluded from the "
        "verdict — they are shown, not dropped, and they remain in every whole-book "
        "total above." % (len(ROSTER), MIN_SAMPLE_N))
    add("")
    add("| symbol | pool | n | **P(2R)** | error bar | mean R `flat_2r` | "
        "mean R ladder | delta | months green | verdict |")
    add("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for s in per_sym:
        if s["n"] == 0:
            add("| **%s** | %s | 0 | — | — | — | — | — | — | _no traded rows_ |"
                % (s["sym"], s["pool"]))
            continue
        if s["n"] < MIN_SAMPLE_N:
            verdict = "**thin** — n < %d, no verdict" % MIN_SAMPLE_N
        elif s["delta"] >= 0:
            verdict = "fits"
        else:
            verdict = "**does NOT fit**"
        add("| **%s** | %s | %d | %.1f%% | ∓%.1f pts | %+.4f | %+.4f | %+.4f | "
            "%d / %d | %s |"
            % (s["sym"], s["pool"], s["n"], s["p2r"], s["p2r_bar"], s["flat"],
               s["ladder"], s["delta"], s["mg"], s["mt"], verdict))
    tot_thick = agg_r([r["flat2r_r"] for r in ship if r["sym"] in
                       {s["sym"] for s in thick}])
    add("| _roster total_ | — | %d | %.1f%% | — | %+.4f | %+.4f | %+.4f | — | — |"
        % (sum(s["n"] for s in per_sym),
           p2r([r for r in ship if r["sym"] in ROSTER], "flat")["opt"],
           agg_r([r["flat2r_r"] for r in ship if r["sym"] in ROSTER])["mean"],
           agg_r([r["ladder_r"] for r in ship if r["sym"] in ROSTER])["mean"],
           agg_r([r["flat2r_r"] for r in ship if r["sym"] in ROSTER])["mean"] -
           agg_r([r["ladder_r"] for r in ship if r["sym"] in ROSTER])["mean"]))
    add("")
    add("**The list, which is the answer to his question.**")
    add("")
    add("- **Does not fit a flat 2R exit** (%d of %d names above the floor): %s"
        % (len(misfit), len(thick),
           ", ".join("**%s** (%+.4f R)" % (s["sym"], s["delta"]) for s in misfit)
           or "_none_"))
    add("- **Fits** (%d): %s"
        % (len(fit), ", ".join("**%s** (%+.4f R)" % (s["sym"], s["delta"])
                               for s in fit) or "_none_"))
    add("- **Thin, no verdict** (%d, n < %d): %s"
        % (len(thin), MIN_SAMPLE_N,
           ", ".join("%s (n=%d)" % (s["sym"], s["n"]) for s in thin) or "_none_"))
    add("")
    neg = [s for s in thick if s["flat"] < 0]
    add("A second cut of the same table, because \"fits\" above is relative to the "
        "ladder and a name can beat the ladder while still losing money: **%d "
        "roster names book a NEGATIVE mean R under `flat_2r`** — %s. %s"
        % (len(neg), ", ".join("%s (%+.4f R)" % (s["sym"], s["flat"]) for s in neg)
           or "_none_",
           "Those are not \"names that need a different exit\", they are names that "
           "need a different entry." if neg else
           "Every thick roster name is at least profitable under a flat 2R exit."))
    add("")

    # ---- what this does not say ----------------------------------------
    add("## What this does not say")
    add("")
    add("- **It does not say the fill is irrelevant.** It says the fill DIFFERENCE "
        "this engine can express — one predicate at 2 of 10 call sites — is smaller "
        "than the doubt the fill assumption already carries. A genuine close-fill "
        "arm would need `fill_price` itself changed, and this ticket changes nothing.")
    add("- **It does not say `flat_2r` is worthless.** It is the simplest exit in the "
        "lab and it books %.1f%% wins. It is worth %.4f R of mean R less than the "
        "ladder, and that is the price of the simplicity, stated so Austin can decide "
        "whether he wants to pay it." % (a_ship["wr"], lad["mean"] - a_ship["mean"]))
    add("- It does not re-open the stop rule. Stops trigger on the candle CLOSE, fill "
        "at that close, floored at −1.25R; wicks stop nothing out.")
    add("- **`exit_lab` and `backtest_2y` floor losses differently and that is on "
        "purpose.** `exit_lab` floors at −1.25R (`MAX_LOSS_R`); the backtest floors "
        "at the stop. So the `flat_2r` and ladder columns measure slightly different "
        "downside, exactly as `research/g7_exit_sweep.md` states. The delta column is "
        "biased AGAINST `flat_2r` by that difference and it is not corrected for.")
    add("- The intrabar marker can only UNDER-count: `backtest_2y.py:169` stores entry "
        "at 2dp, so a clamped level that rounds into the close's own cent is recorded "
        "as a close fill. Every intrabar and ambiguity count here is a floor.")
    add("- P(2R) is not win rate and the two must not be swapped. A trade that reaches "
        "2R and is booked at +2.0 is one row of both; a trade that books +0.3 is a win "
        "and not a 2R.")
    add("- **The intention-to-treat table makes one choice and it is stated, not "
        "hidden: a candidate arm B never traded counts as a non-hit.** The "
        "alternative — dropping it — is what every per-arm table in this repo does "
        "implicitly, and it is what produces the %.2f%% figure. Neither is a "
        "measurement; the choice is between two denominators, and the ITT one is the "
        "question a trader asks (*if I adopt this fill, what happens to the %d setups "
        "I would otherwise have taken?*). It does NOT claim those %d trades lost "
        "money — under the close fill they book %+.4f R, roughly flat."
        % (pp, len(cand), len(killed), kf["mean"]))
    add("- **The candidate set is %d signals and the surviving arm is %d.** That is "
        "above `universe.MIN_SAMPLE_N` but it is not large, and the per-symbol cut of "
        "it would be far below the floor, so it is not attempted. The direction of "
        "the ITT result is a %.0f-point move and would survive a good deal of noise; "
        "the exact figure would not." % (len(cand), len(surv), ca["opt"] - itt))
    add("- **`moved` is measured from the stored 2dp entry and stop, so it is a "
        "floor.** A back-dated fill whose clamped level rounds into the close's own "
        "cent is recorded as unmoved — the same under-count as the intrabar marker. "
        "The true number of moved fills is at least the %d counted here." % len(moved))
    add("- Nothing here is a walk-forward. Every number is in-sample over the same 500 "
        "sessions every other 2-year table in this repo reads.")
    add("")

    # ---- provenance -----------------------------------------------------
    add("## Provenance")
    add("")
    add("Produced by `research/r9_simple_book.py` at _this commit_, over the two fill "
        "arms `research/g3_arm_ow0.json` and `research/g3_arm_ow1.json` replayed by "
        "`research/g3_onwatch_2y.py` (T3, commit `47e60796`): %s → %s, %d sessions, "
        "%s signals per arm. Regenerate with `python research/r9_simple_book.py`; "
        "verify the rig with `python research/r9_simple_book.py --selfcheck`."
        % (metas["B"]["first"], metas["B"]["last"], metas["B"]["sessions"],
           f"{metas['B']['signals']:,}"))
    add("")
    add("**Nothing is re-derived that another rig already derived.** `flat_2r` is "
        "`research/exit_lab.flat_target` called unmodified at 2.0R with "
        "`CLOCK_BAR = 90` and `MAX_LOSS_R = 1.25` untouched. The intrabar marker, its "
        "2dp rounding correction, the two fill predicates and the ambiguity test are "
        "imported from `research/p26_intrabar_ambiguity.py` (T2). The whole-book money "
        "read is `research/a2_bt2y_summary.py::book`. The symbol roster and the sample "
        "floor are imported from `universe.py`. What this file adds is the JOIN "
        "between the two arms — `matched()` and `candidates()` — and one boolean "
        "naming whether the 2R target was reached; `--selfcheck` asserts that boolean "
        "agrees with `flat_target(...) == +2.0` on all %s traded rows of both arms, "
        "and that the %s pairs with identical entry and stop replay bit-identically."
        % (f"{len(arms['A']) + len(arms['B']):,}", f"{len(same):,}"))
    add("")
    add("Bars were read from `data_archive/` only, through `p26.load_day`, whose guard "
        "makes a network fetch impossible. Gaps: %d rows with no archived session, %d "
        "with an entry minute that has no bar, %d with an `entry_i` past the end of "
        "the session — across both arms, out of %s traded rows."
        % (gaps["day"], gaps["bar"], gaps["index"],
           f"{len(arms['A']) + len(arms['B']) + gaps['day'] + gaps['bar'] + gaps['index']:,}"))
    add("")
    add("`python research/regression_gate.py` is RED at HEAD and was red before this "
        "ticket, which adds only new files under `research/` and edits no engine "
        "module. It is being bisected separately. Re-run after this file landed, it "
        "drops the SAME six `s_grade` marks and no others — `GOOGL|2024-10-15|32`, "
        "`IWM|2025-04-10|16`, `IWM|2025-12-01|11`, `IWM|2025-12-04|56`, "
        "`QQQ|2025-02-25|16`, `UBER|2025-09-11|15` — so this ticket added no new "
        "drop. `python research/test_provenance.py` passes.")
    return "\n".join(L) + "\n"


def _verdict(delta, bar):
    if abs(delta) >= bar:
        return "**clears it** — %.1f× the bar" % (abs(delta) / bar) if bar else "clears it"
    return ("**inside it** — the bar is %.0f× larger, so this is unresolved"
            % (bar / abs(delta)) if delta else "**inside it** — the delta is zero")


def symbol_rows(rows):
    """One row per roster symbol, in the roster's own order."""
    out = []
    for sym in ROSTER:
        rs = [r for r in rows if r["sym"] == sym]
        f = agg_r([r["flat2r_r"] for r in rs])
        l = agg_r([r["ladder_r"] for r in rs])
        p = p2r(rs, "flat")
        g, t, _, _ = months(rs, "flat2r_r")
        out.append({"sym": sym, "pool": pool_for(sym), "n": len(rs),
                    "p2r": p["opt"], "p2r_bar": p["wide"],
                    "flat": f["mean"], "ladder": l["mean"],
                    "delta": f["mean"] - l["mean"], "wr": f["wr"],
                    "mg": g, "mt": t})
    return out


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------

def selfcheck(arms, cache, metas):
    """Everything that could rot silently. Loud on the first failure."""
    ok = []

    # 1. Defaults are untouched. This ticket changes nothing and must prove it.
    assert xl.CLOCK_BAR == 90, "exit_lab.CLOCK_BAR moved: %r" % xl.CLOCK_BAR
    assert xl.MAX_LOSS_R == 1.25, "exit_lab.MAX_LOSS_R moved: %r" % xl.MAX_LOSS_R
    assert xl.STOP_TRIGGER_BUFFER_FRAC == 0.0
    ok.append("exit_lab defaults unchanged (CLOCK_BAR=90, MAX_LOSS_R=1.25)")

    # 2. The roster is imported, 12 names, and QQQ is the overlap.
    assert len(ROSTER) == 12, "roster is %d names, expected 12" % len(ROSTER)
    assert set(ROSTER) == set(CORE_SYMBOLS) | set(INDEX_POOL)
    assert "QQQ" in CORE_SYMBOLS and "QQQ" in INDEX_POOL
    ok.append("roster = CORE_SYMBOLS | INDEX_POOL = %d names" % len(ROSTER))

    # 3. Both arms are the same replay of the same tape -- T3's own check.
    assert metas["A"]["signals"] == metas["B"]["signals"], (
        "arms disagree on signal count: %d vs %d"
        % (metas["A"]["signals"], metas["B"]["signals"]))
    assert metas["A"]["sessions"] == metas["B"]["sessions"]
    ok.append("both arms replayed %s signals over %d sessions"
              % (f"{metas['A']['signals']:,}", metas["A"]["sessions"]))

    # 4. THE BIG ONE. The boolean this file adds is not a second implementation
    #    of the policy: it must agree with the shipped `flat_target` returning
    #    exactly +2.0 on every traded row of both arms.
    n_checked = mismatch = 0
    for code in ("A", "B"):
        for r in arms[code]:
            n_checked += 1
            booked_2r = abs(r["flat2r_r"] - TARGET_R) < 1e-9
            if booked_2r != r["reach2r"]:
                mismatch += 1
                if mismatch <= 5:
                    print("  MISMATCH %s %s %s entry_i=%d flat2r=%.6f reach=%s"
                          % (code, r["sym"], r["day"], r["entry_i"],
                             r["flat2r_r"], r["reach2r"]), file=sys.stderr)
    assert mismatch == 0, ("%d of %d rows disagree between reaches_target() and "
                           "exit_lab.flat_target(...)==+2.0" % (mismatch, n_checked))
    ok.append("reaches_target() == (flat_target(...)==+2.0) on all %s rows"
              % f"{n_checked:,}")

    # 5. `entry_i` and the `et` timestamp index the same bar list. If they ever
    #    diverge, flat_2r is replayed from a different bar than the one T2
    #    classified and every cell in the report is silently wrong.
    bad = [r for code in ("A", "B") for r in arms[code] if r["entry_i"] != r["bar_i"]]
    assert not bad, ("%d rows where entry_i != index(et); first: %s %s %d vs %d"
                     % (len(bad), bad[0]["sym"], bad[0]["day"],
                        bad[0]["entry_i"], bad[0]["bar_i"]))
    ok.append("entry_i == index(et) on every traded row -- one bar convention")

    # 6. The error bar is one-directional everywhere. A pessimistic arm that
    #    beats its optimistic arm is a repricing bug, not a result.
    for code in ("A", "B"):
        for key in ("flat2r_r", "ladder_r"):
            mb = mean_bar(arms[code], key)
            assert mb["wide"] >= -1e-12, "wide bar negative: %s %s %r" % (code, key, mb)
            assert mb["narrow"] >= -1e-12, "narrow bar negative: %s %s %r" % (code, key, mb)
            assert mb["wide"] >= mb["narrow"] - 1e-12, (
                "narrow bar exceeds wide: %s %s %r" % (code, key, mb))
        for kind in ("flat", "ladder"):
            p = p2r(arms[code], kind)
            assert p["wide"] >= -1e-12 and p["narrow"] >= -1e-12, (code, kind, p)
            assert p["wide"] >= p["narrow"] - 1e-12, (code, kind, p)
    ok.append("every error bar is one-directional and wide >= narrow")

    # 7. The pool label this file computes agrees with the one the backtest
    #    wrote, so `universe.pool_for` has not drifted from the replay.
    with open(ARMS[1][3], encoding="utf-8") as fh:
        raw = json.load(fh)["trades"]
    drift = [r for r in raw if pool_for(r["sym"]) != r["pool"]]
    assert not drift, ("%d rows where universe.pool_for disagrees with the book's "
                       "own pool label; first: %s -> %s vs %s"
                       % (len(drift), drift[0]["sym"], pool_for(drift[0]["sym"]),
                          drift[0]["pool"]))
    ok.append("universe.pool_for agrees with the book's pool label on all %s rows"
              % f"{len(raw):,}")

    # 8. P(2R) is a share of the traded book, so it can never exceed the win
    #    rate of a policy that books +2.0 on exactly those rows.
    for code in ("A", "B"):
        p = p2r(arms[code], "flat")
        a = agg_r([r["flat2r_r"] for r in arms[code]])
        assert p["hits"] <= a["n"], (code, p, a)
        assert 0.0 <= p["opt"] <= 100.0
    ok.append("P(2R) is bounded and consistent with the flat_2r book")

    # 9. THE CONTROL ON THE MATCHED PAIR. Pairs whose entry AND stop are
    #    identical in both arms are the same trade replayed twice against the
    #    same tape: every result must agree to the bit. If it does not, the two
    #    books disagree about the TAPE rather than about the FILL, and every
    #    delta in the matched table is measuring the wrong thing.
    both, moved, same, dupes = matched(arms)
    assert both, "no matched pairs at all -- the join key is wrong"
    for a, b in same:
        assert abs(a["flat2r_r"] - b["flat2r_r"]) < 1e-9, (
            "identical entry/stop replayed differently: %s %s %.9f vs %.9f"
            % (a["sym"], a["day"], a["flat2r_r"], b["flat2r_r"]))
        assert a["reach2r"] == b["reach2r"], (a["sym"], a["day"])
        assert abs(a["ladder_r"] - b["ladder_r"]) < 1e-9, (a["sym"], a["day"])
    # ... and the partition is exhaustive, so no pair is quietly uncounted.
    assert len(moved) + len(same) == len(both), (len(moved), len(same), len(both))
    ok.append("matched join: %s pairs, %s moved, %s identical and bit-identical "
              "on replay (%d non-unique keys excluded)"
              % (f"{len(both):,}", f"{len(moved):,}", f"{len(same):,}", dupes))

    for line in ok:
        print("  ok: " + line)
    print("selfcheck ok (%d assertions groups)" % len(ok))
    return 0


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    cache = Bars()
    arms, metas = {}, {}
    gaps = {"day": 0, "bar": 0, "index": 0}
    for code, label, flag, path in ARMS:
        rows, meta, g = build_arm(path, cache)
        arms[code], metas[code] = rows, meta
        for k in gaps:
            gaps[k] += g[k]
        print("arm %s (%s, %s): %d traded rows replayed, gaps=%r"
              % (code, label, flag, len(rows), g), flush=True)

    if args.selfcheck:
        return selfcheck(arms, cache, metas)

    text = report(arms, gaps, metas)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote %s (%d lines)" % (args.out, text.count("\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
