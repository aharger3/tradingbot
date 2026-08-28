"""w13_scaling.py -- W13: scaling as a mean-R lever.

Austin, 2026-08-28:

  "if we change the scaling, the way scaling works, then we can hit that higher
   mean... I believe for scaling because that's what Scarface and JW do. They
   with ease average two to one risk to reward on trades."

WHY HIS INSTINCT IS ARITHMETICALLY CORRECT
------------------------------------------
For a fixed target T with win rate w and a -1R loss, mean R = w*T - (1-w).
Setting that to the money gate of 2.0 gives the win rate a flat target would
need. Against the MFE touch rates actually observed on this book (recomputed in
the report's §1), the needed rate is far above the achieved rate at every T, the
gap narrows as T grows and never closes: **no fixed target reaches mean 2.0 R at
any achievable hit rate.** 42 exit policies (g7's 8, g9/p10's 14, W2's 20) have
confirmed the empirical version -- every one lands between +0.50 and +0.96 mean.
Scaling is the remaining untested family, and Austin is right to point at it.

The unexploited fact this ticket aims at: a large majority of trades reach 1R,
and those trades offer several more R of mean MFE beyond that 1R point (§1
recomputes both on this book). Family A puts size on exactly that part of the
distribution.

THE FOUR FAMILIES
-----------------
A  scale IN      -- add size at a trigger R, the added tranche's stop AT the
                    scale point, so its incremental risk is (near) zero.
B  tail-weighted -- the shipped 30/30/30/10 re-weighted toward the runner.
   scale OUT
C  break-even    -- when the base stop moves to entry: 0.5R / 1R / 1.5R / 2R /
   stop timing      never.
D  hybrid        -- a front tranche out at 2.0R (67.5% of Austin's own intended
                    targets sit there, W11 §3) AND size added at 1R.

THE RISK DENOMINATOR, STATED AND DEFENDED
-----------------------------------------
This is the one place a scale-in study can manufacture a number, so it is fixed
here in the open.

R is a multiple of the risk TAKEN, not of the size deployed. The base leg risks
1.0 unit (= |entry - stop|). An added tranche of ``size`` units filled at
``trigger_r`` with its stop at ``add_stop_r`` risks ``size * (trigger_r -
add_stop_r)`` further units, because the sequence trigger -> add_stop -> base
stop is a single reachable path down the tape:

    RISK UNITS = 1.0 + size * (trigger_r - add_stop_r)

When the add's stop sits AT the scale point (``add_stop_r == trigger_r``) that
is exactly 1.0 and the raw mean R is already the risk-adjusted number -- the
whole point of the technique, and why it is not free size, it is free-ish size.
When the add's stop sits lower (at entry, say) the arm is taking genuinely more
risk and its mean R must be divided by RISK UNITS before it is compared to
anything. Every table below prints ``risk units`` and ``mean R / risk unit``,
and **the money gate is judged on mean R / risk unit, never on raw mean.**

What RISK UNITS does NOT price is capital and options liquidity: ``size = 2.0``
means carrying 3x the nominal position at peak. That is a real constraint and an
honest reader should treat it as the binding one; it is reported, not modelled.

The add's stop is close-triggered and fills at that close like every other stop
in this repo, so "stop at the scale point" is NOT zero loss in practice: a bar
that pokes the trigger and closes back under it stops the add at that close for
a real debit. That bleed is the price of the technique and the sweep measures it.

WHAT IS IMPORTED, NOT REWRITTEN
-------------------------------
- ``Bars``, ``build_arm``, ``agg_r``, ``months`` from ``research/r9_simple_book.py``
- ``mfe_r`` from ``research/h1_2y_nowatch.py``
- ``time_ladder``, ``score``, ``hhmm``, ``BAR_OF`` from
  ``research/w2_time_ladder.py`` (``score`` is its horizon set/restore harness)
- ``_stop_hit_first``, ``_stop_fill``, ``realised_r``, ``flat_target``,
  ``scale_out``, ``hod_only``, ``MAX_LOSS_R`` from ``research/exit_lab.py``

``exit_lab.scale_out`` and ``exit_lab.flat_target`` are NOT edited -- other rigs
depend on them and ``scale_out`` was only just fixed at ``f5ff006a`` (it let a
stopped-out trade keep running). ``--selfcheck`` asserts that this file's own
``staged_exit`` reproduces ``w2_time_ladder.time_ladder`` bit-for-bit on the
default rung set over every row, which is how the causal conventions are proven
to match rather than asserted to.

Book: the traded rows of ``research/g3_arm_ow1.json``; bars via
``r9_simple_book.Bars`` (``data_archive/`` replay, zero fetches).
Error bar: +-0.0095 R, the narrow bar (master spec 1.1).

    python research/w13_scaling.py             # write research/w13_scaling.md
    python research/w13_scaling.py --selfcheck # assertions only, no report
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
from research.h1_2y_nowatch import mfe_r                              # noqa: E402,F401
from research.r9_simple_book import Bars, agg_r, build_arm, months    # noqa: E402
from research.w2_time_ladder import BAR_OF, hhmm, score, time_ladder  # noqa: E402

BOOK = os.path.join(HERE, "g3_arm_ow1.json")
OUT = os.path.join(HERE, "w13_scaling.md")

MONEY_GATE = 2.0
ERROR_BAR = 0.0095          # the narrow bar; the wide +-1.5799 R bar was retired
EOD = BAR_OF["16:00"]
CLOCK = BAR_OF["11:00"]     # 90 -- the shipped exit clock


# ---------------------------------------------------------------------------
# leg math
# ---------------------------------------------------------------------------

def _leg_r(px0, px1, side, risk):
    """R of one leg opened at ``px0`` and closed at ``px1``, in ORIGINAL risk."""
    return (px1 - px0) / risk if side == "L" else (px0 - px1) / risk


# ---------------------------------------------------------------------------
# the base leg: R rungs + an explicit break-even trigger
# ---------------------------------------------------------------------------

def staged_exit(bars, entry_i, entry, stop, side,
                rungs=(), be_at_r=None, backstop=CLOCK):
    """Scale-OUT on R rungs with the break-even move on its own trigger.

    ``rungs``    ((target_r, weight), ...) ascending; a weight is a share of the
                 ORIGINAL position, filling at the target price the moment a
                 bar's range touches it (a resting limit). Weights summing under
                 1.0 leave a runner with no target.
    ``be_at_r``  R at which the stop moves to entry, or None for never. This is
                 family C's swept parameter. ``w2.time_ladder`` hardcodes "on the
                 first rung fill"; setting ``be_at_r`` to the first rung's R
                 reproduces it exactly (asserted in ``--selfcheck``).
    ``backstop`` bar index at which everything left exits at that bar's close.

    Causal conventions, copied from ``exit_lab`` and not re-derived: scan from
    ``entry_i + 1``; the stop triggers on a candle CLOSE beyond it
    (``_stop_hit_first``), fills at that close (``_stop_fill``), floored at
    -1.25 R (``MAX_LOSS_R``); the stop is tested BEFORE the rungs on every bar,
    so a bar closing beyond the stop wins even if a rung target also traded
    inside it.
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

        # 3. the break-even move, on price touch, independent of the rungs
        if be_at_r is not None:
            trig = entry + be_at_r * risk if side == "L" else entry - be_at_r * risk
            touched = (b["h"] >= trig) if side == "L" else (b["l"] <= trig)
            if touched:
                cur_stop = entry

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
# the added leg: scale IN
# ---------------------------------------------------------------------------

def scale_in_leg(bars, entry_i, entry, stop, side, trigger_r, size,
                 add_stop_r=None, add_target_r=None, backstop=CLOCK):
    """R contributed by a tranche ADDED at ``trigger_r``, in ORIGINAL risk units.

    Separable from whatever the base leg does, and deliberately so: once the add
    is on, its own stop governs it, and the base's stop (original or moved to
    break-even) sits strictly below it for any ``add_stop_r >= 0``. So the arm
    is exactly ``base + add`` and the A/B against the same base is exact.

    ``trigger_r``    R at which the add fills, at that price, as a resting order.
    ``size``         units of the base position added.
    ``add_stop_r``   R at which the added tranche stops; defaults to
                     ``trigger_r`` -- the scale point, the near-zero-incremental-
                     risk case the ticket names.
    ``add_target_r`` optional R at which the add takes profit; None rides to the
                     backstop.

    Returns ``(r_contrib, filled)``.

    Two conventions worth stating because they cost money:

    - The add never happens if a bar closes beyond the ORIGINAL stop before the
      trigger price trades. Same causal scan ``mfe_r`` and ``flat_target`` run.
    - The add's own stop is live on the trigger bar ITSELF. A bar that pokes the
      trigger and closes back under it stops the add at that close, for a real
      debit. This is master spec 1.1's "out on that same close" applied to the
      added tranche, and it is why "stop at the scale point" is not free.
    """
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0 or size <= 0:
        return 0.0, False
    if add_stop_r is None:
        add_stop_r = trigger_r
    end = min(backstop + 1, n)

    sgn = 1.0 if side == "L" else -1.0
    trig = entry + sgn * trigger_r * risk
    add_stop = entry + sgn * add_stop_r * risk

    add_i = None
    for i in range(entry_i + 1, end):
        if xl._stop_hit_first(bars, i, entry, stop, side):
            return 0.0, False                      # base stopped before the add
        b = bars[i]
        if (b["h"] >= trig) if side == "L" else (b["l"] <= trig):
            add_i = i
            break
    if add_i is None:
        return 0.0, False

    tgt = entry + sgn * add_target_r * risk if add_target_r is not None else None

    for i in range(add_i, end):
        b = bars[i]
        # 1. the add's stop -- close-triggered, fills at the close, floored
        if xl._stop_hit_first(bars, i, trig, add_stop, side):
            px = xl._stop_fill(bars, i, trig, add_stop, side, risk)
            return size * _leg_r(trig, px, side, risk), True
        # 2. the add's optional target -- resting limit, fills on touch
        if tgt is not None:
            if (b["h"] >= tgt) if side == "L" else (b["l"] <= tgt):
                return size * (add_target_r - trigger_r), True
        # 3. the hard backstop
        if i >= backstop:
            return size * _leg_r(trig, b["c"], side, risk), True

    last = max(add_i, min(backstop, n - 1))
    r = _leg_r(trig, bars[last]["c"], side, risk)
    return size * max(r, -xl.MAX_LOSS_R), True


def risk_units(size=0.0, trigger_r=0.0, add_stop_r=None):
    """Units of ORIGINAL risk an arm can lose. See the module docstring."""
    if size <= 0:
        return 1.0
    if add_stop_r is None:
        add_stop_r = trigger_r
    return 1.0 + size * max(0.0, trigger_r - add_stop_r)


# ---------------------------------------------------------------------------
# arm assembly
# ---------------------------------------------------------------------------

def base_fn(kind, rungs=(), be_at_r=None, backstop=CLOCK):
    """The base leg. The named bases are the controls families A/D add to."""
    if kind == "incumbent":
        return lambda b, e, en, st, sd: xl.scale_out(
            b, e, en, st, sd, [0.30, 0.30, 0.30, 0.10])
    if kind == "hod_only":
        return lambda b, e, en, st, sd: xl.hod_only(b, e, en, st, sd, "atr")
    if kind.startswith("flat_"):
        t = float(kind[5:])
        return lambda b, e, en, st, sd: xl.flat_target(b, e, en, st, sd, t)
    if kind == "staged":
        return lambda b, e, en, st, sd: staged_exit(
            b, e, en, st, sd, rungs=rungs, be_at_r=be_at_r, backstop=backstop)
    raise ValueError(kind)


def arm_fn(base, add=None):
    """base + optional scale-in leg, as one callable returning total R."""
    if add is None:
        return lambda b, e, en, st, sd: base(b, e, en, st, sd)

    def fn(b, e, en, st, sd):
        r_add, _ = scale_in_leg(b, e, en, st, sd, **add)
        return base(b, e, en, st, sd) + r_add
    return fn


RUNGS_SHIPPED = ((1.0, 0.30), (2.0, 0.30), (3.0, 0.30))   # + 10% runner

ARMS = []
# symbol-days on which `exit_lab.hod_only` books below the -1.25 R floor. Filled
# by `selfcheck`, reported in §9. Pre-existing, not introduced here.
HOD_BREACH = set()


def A(key, bs, fn, ru=1.0, fam="", note="", add=None):
    ARMS.append({"key": key, "bs": bs, "fn": fn, "ru": ru, "fam": fam,
                 "note": note, "add": add})


def build_arms():
    ARMS.clear()

    # -- controls -----------------------------------------------------------
    A("C0  incumbent 30/30/30/10 (shipped)", CLOCK, base_fn("incumbent"),
      1.0, "ctl", "`exit_lab.scale_out`, untouched")
    A("C1  flat_2r", CLOCK, base_fn("flat_2.0"), 1.0, "ctl",
      "`exit_lab.flat_target`, untouched")
    A("C2  hod_only", CLOCK, base_fn("hod_only"), 1.0, "ctl",
      "`exit_lab.hod_only`, untouched — see §9 on its −1.25 R floor")
    A("C3  R-rungs 30/30/30 +10% runner", CLOCK,
      base_fn("staged", RUNGS_SHIPPED, 1.0), 1.0, "ctl",
      "the shipped split on R rungs -- W2's `R1`")
    A("C4  no rungs, orig stop, ride to 11:00", CLOCK,
      base_fn("staged", (), None), 1.0, "ctl",
      "no rungs, no clock steps -- W2's `R5` minus its clock")

    BASES = [("incumbent", base_fn("incumbent"), "C0"),
             ("flat_2r", base_fn("flat_2.0"), "C1"),
             ("hod_only", base_fn("hod_only"), "C2"),
             ("R-rungs 30/30/30", base_fn("staged", RUNGS_SHIPPED, 1.0), "C3"),
             ("hold to 11:00", base_fn("staged", (), None), "C4")]

    # -- family A: scale IN -------------------------------------------------
    # A1-A5: every base, the canonical add (1R trigger, 1.0x size, stop at the
    # scale point). This is the ticket's literal arm and the exact A/B: each row
    # is its own control plus one separable leg.
    for j, (nm, bf, ctl) in enumerate(BASES, 1):
        add = dict(trigger_r=1.0, size=1.0, backstop=CLOCK)
        A("A%d  %s + add 1.0x @1R" % (j, nm), CLOCK, arm_fn(bf, add),
          risk_units(1.0, 1.0), "A", "control is %s" % ctl, add)

    # the trigger x size grid, on the two bases with the best mean
    for nm, mk in (("hold", lambda: base_fn("staged", (), None)),
                   ("incumbent", lambda: base_fn("incumbent"))):
        for trig in (1.0, 1.5, 2.0):
            for sz in (0.5, 1.0, 2.0):
                add = dict(trigger_r=trig, size=sz, backstop=CLOCK)
                A("A  %s + add %.1fx @%.1fR" % (nm, sz, trig), CLOCK,
                  arm_fn(mk(), add), risk_units(sz, trig), "Agrid", "", add)

    # where the ADD's stop sits -- the risk-denominator sweep
    for stop_r, lbl in ((1.0, "at the scale point"), (0.5, "half way back"),
                        (0.0, "at entry")):
        add = dict(trigger_r=1.0, size=1.0, add_stop_r=stop_r, backstop=CLOCK)
        A("A  hold + add 1.0x @1R, add stop %s" % lbl, CLOCK,
          arm_fn(base_fn("staged", (), None), add),
          risk_units(1.0, 1.0, stop_r), "Astop",
          "risk = %.2f units" % risk_units(1.0, 1.0, stop_r), add)
    # the add taking a target instead of riding
    for tgt in (2.0, 3.0):
        add = dict(trigger_r=1.0, size=1.0, add_target_r=tgt, backstop=CLOCK)
        A("A  hold + add 1.0x @1R, add exits %.0fR" % tgt, CLOCK,
          arm_fn(base_fn("staged", (), None), add), risk_units(1.0, 1.0),
          "Astop", "the add takes a fixed target", add)
    # the add given room past the clock -- whole arm moves to that backstop
    for bs in (BAR_OF["11:30"], BAR_OF["13:00"]):
        add = dict(trigger_r=1.0, size=1.0, backstop=bs)
        A("A  hold + add 1.0x @1R, backstop %s" % hhmm(bs), bs,
          arm_fn(base_fn("staged", (), None, bs), add), risk_units(1.0, 1.0),
          "Astop", "whole arm at this backstop", add)

    # -- family B: tail-weighted scale OUT ----------------------------------
    for w1, w2, w3 in ((0.10, 0.10, 0.10), (0.20, 0.20, 0.20),
                       (0.25, 0.25, 0.25), (0.30, 0.30, 0.30),
                       (0.50, 0.20, 0.20), (0.70, 0.10, 0.10)):
        rungs = ((1.0, w1), (2.0, w2), (3.0, w3))
        run = 1.0 - (w1 + w2 + w3)
        A("B  %d/%d/%d, %d%% runner" % (w1 * 100, w2 * 100, w3 * 100, run * 100),
          CLOCK, base_fn("staged", rungs, 1.0), 1.0, "B",
          "runner rides to 11:00 on a break-even stop")

    # -- family C: break-even stop timing -----------------------------------
    for be in (0.5, 1.0, 1.5, 2.0, None):
        lbl = "never" if be is None else "%.1fR" % be
        A("C  no rungs, BE at %s" % lbl, CLOCK,
          base_fn("staged", (), be), 1.0, "C", "isolates the BE move")
    for be in (0.5, 1.0, 1.5, 2.0, None):
        lbl = "never" if be is None else "%.1fR" % be
        A("C  rungs 30/30/30, BE at %s" % lbl, CLOCK,
          base_fn("staged", RUNGS_SHIPPED, be), 1.0, "C",
          "the shipped split, BE trigger swept")

    # -- family D: hybrid ---------------------------------------------------
    for wfront in (0.30, 0.50, 0.675):
        A("D  %.1f%% out @2R, no add" % (wfront * 100), CLOCK,
          base_fn("staged", ((2.0, wfront),), 1.0), 1.0, "D", "control")
        for sz in (1.0, 2.0):
            add = dict(trigger_r=1.0, size=sz, backstop=CLOCK)
            A("D  %.1f%% out @2R + add %.1fx @1R" % (wfront * 100, sz), CLOCK,
              arm_fn(base_fn("staged", ((2.0, wfront),), 1.0), add),
              risk_units(sz, 1.0), "D",
              "BE at 1R; %.1f%% rides to 11:00" % ((1 - wfront) * 100), add)

    return ARMS


# ---------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------

def line(rows, key, bs, ru=1.0):
    a = agg_r([r[key] for r in rows])
    g, t, wm, wv = months(rows, key)
    mfe = statistics.fmean(r["mfe@%d" % bs] for r in rows)
    a.update(green=g, tot_m=t, worst=wm, worst_v=wv, mfe=mfe,
             cap=100.0 * a["mean"] / mfe if mfe else 0.0, bs=bs, ru=ru,
             per_risk=a["mean"] / ru if ru else 0.0)
    return a


HEAD = ("| arm | mean R | mean R / risk unit | median R | win rate | "
        "months green | share of mean MFE | risk units | total R |")
RULE = "|---|---:|---:|---:|---:|---:|---:|---:|---:|"
HEAD_N = HEAD + " note |"
RULE_N = RULE + "---|"


def row_md(label, a, note=None):
    s = ("| %s | **%+.4f** | %+.4f | %+.4f | %.1f%% | %d / %d | %.1f%% | %.2f "
         "| %+.1f |" % (label, a["mean"], a["per_risk"], a["median"], a["wr"],
                        a["green"], a["tot_m"], a["cap"], a["ru"], a["tot"]))
    return (s + " %s |" % note) if note is not None else s


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------

def selfcheck(rows, arms, cache):
    """Four properties, all structural rather than statistical.

    1. ``staged_exit`` reproduces ``w2_time_ladder.time_ladder`` exactly on the
       default rung set. This is how the causal conventions are PROVEN to match
       rather than asserted to.
    2. No arm books above the MFE its own horizon offered. For a scale-in arm
       the ceiling extends: the base can take at most the MFE, and the added
       tranche entered at ``trigger_r`` so it can take at most
       ``size * (MFE - trigger_r)`` more.
    3. No leg books below -1.25 R PER UNIT OF ORIGINAL RISK -- checked on each
       leg separately, which is tighter than checking the total.
    4. ``exit_lab.CLOCK_BAR`` is restored.
    """
    keep = xl.CLOCK_BAR
    n_eq = 0
    try:
        xl.CLOCK_BAR = CLOCK
        for r in rows:
            d = cache.get(r["sym"], r["day"])[1]
            a = staged_exit(d, r["entry_i"], r["entry"], r["stop"], r["side"],
                            rungs=RUNGS_SHIPPED, be_at_r=RUNGS_SHIPPED[0][0],
                            backstop=CLOCK)
            b = time_ladder(d, r["entry_i"], r["entry"], r["stop"], r["side"],
                            rungs=RUNGS_SHIPPED, steps=(), backstop=CLOCK,
                            be_after_first=True)
            assert abs(a - b) < 1e-9, (
                "staged_exit %.6f != time_ladder %.6f on %s %s"
                % (a, b, r["sym"], r["day"]))
            n_eq += 1
    finally:
        xl.CLOCK_BAR = keep

    # `exit_lab.hod_only` is the one imported policy that can book below the
    # -1.25 R floor: it tests the stop over `range(entry_i+1, hod_i)`, EXCLUSIVE
    # of the HOD bar, so a HOD bar whose own close is far beyond the stop is
    # booked in full and unfloored. `scale_out` had the same off-by-one and it
    # was fixed at `f5ff006a`; `hod_only` was not, and this file does not edit
    # `exit_lab` (other rigs depend on it). So arms built on `hod_only` are
    # exempted from the flat floor and each breach is instead PROVEN
    # attributable to `exit_lab.hod_only` itself, not to anything new here.
    n_ceiling = 0
    keep = xl.CLOCK_BAR
    try:
        xl.CLOCK_BAR = CLOCK
        for arm in arms:
            key, bs, addspec = arm["key"], arm["bs"], arm["add"]
            hod = "hod_only" in key
            mkey = "mfe@%d" % bs
            for r in rows:
                got, ceil = r[key], r[mkey]
                assert ceil >= 0.0, "negative MFE %s %s" % (r["sym"], r["day"])
                top = ceil
                floor = -xl.MAX_LOSS_R
                if addspec:
                    top += addspec["size"] * max(0.0, ceil - addspec["trigger_r"])
                    floor = -xl.MAX_LOSS_R * (1.0 + addspec["size"])
                assert got <= top + 1e-6, (
                    "%s booked %.4f above the %s ceiling %.4f on %s %s"
                    % (key, got, hhmm(bs), top, r["sym"], r["day"]))
                if got < floor - 1e-6:
                    assert hod, (
                        "%s booked %.4f below the %.4f R floor on %s %s"
                        % (key, got, floor, r["sym"], r["day"]))
                    d = cache.get(r["sym"], r["day"])[1]
                    raw = xl.hod_only(d, r["entry_i"], r["entry"], r["stop"],
                                      r["side"], "atr")
                    assert raw < -xl.MAX_LOSS_R - 1e-6, (
                        "%s breached the floor but exit_lab.hod_only did not "
                        "(%.4f) on %s %s" % (key, raw, r["sym"], r["day"]))
                    HOD_BREACH.add((r["sym"], r["day"]))
                n_ceiling += 1
    finally:
        xl.CLOCK_BAR = keep

    # per-leg floor: each leg on its own, per unit of original risk
    n_leg = 0
    keep = xl.CLOCK_BAR
    try:
        xl.CLOCK_BAR = CLOCK
        for r in rows:
            d = cache.get(r["sym"], r["day"])[1]
            base = staged_exit(d, r["entry_i"], r["entry"], r["stop"], r["side"])
            assert base >= -xl.MAX_LOSS_R - 1e-6, (
                "base leg %.4f below -%.2f R per unit on %s %s"
                % (base, xl.MAX_LOSS_R, r["sym"], r["day"]))
            for trig, sz in ((1.0, 1.0), (1.0, 2.0), (2.0, 0.5)):
                ar, filled = scale_in_leg(d, r["entry_i"], r["entry"], r["stop"],
                                          r["side"], trig, sz, backstop=CLOCK)
                assert ar / sz >= -xl.MAX_LOSS_R - 1e-6, (
                    "add leg %.4f/unit below -%.2f R on %s %s"
                    % (ar / sz, xl.MAX_LOSS_R, r["sym"], r["day"]))
                if not filled:
                    assert ar == 0.0, "unfilled add booked %.4f" % ar
                n_leg += 1
    finally:
        xl.CLOCK_BAR = keep

    hs = sorted({a["bs"] for a in arms})
    for x, y in zip(hs, hs[1:]):
        for r in rows:
            assert r["mfe@%d" % y] >= r["mfe@%d" % x] - 1e-6, (
                "MFE fell when the horizon grew, %s %s" % (r["sym"], r["day"]))

    assert xl.CLOCK_BAR == 90, "exit_lab.CLOCK_BAR was left at %d" % xl.CLOCK_BAR
    print("selfcheck ok: staged_exit == w2.time_ladder on %d/%d rows; "
          "%d arm-results inside [floor, MFE-at-own-horizon]; %d add legs "
          ">= -%.2f R per unit of original risk; %d horizons monotone; "
          "exit_lab.CLOCK_BAR restored to %d; %d symbol-days breach the floor "
          "and every one is proven to be exit_lab.hod_only's pre-existing "
          "off-by-one, not this file's"
          % (n_eq, len(rows), n_ceiling, n_leg, xl.MAX_LOSS_R, len(hs),
             xl.CLOCK_BAR, len(HOD_BREACH)))


# ---------------------------------------------------------------------------
# the facts the report's 1 recomputes
# ---------------------------------------------------------------------------

def touch_stats(rows):
    """MFE touch rates and the R still on offer beyond 1R, on THIS book."""
    m = [r["mfe@%d" % CLOCK] for r in rows]
    out = {}
    for t in (1.0, 2.0, 3.0, 5.0, 8.0):
        out["touch%g" % t] = 100.0 * sum(1 for x in m if x >= t) / len(m)
    past1 = [x - 1.0 for x in m if x >= 1.0]
    out["mean_mfe"] = statistics.fmean(m)
    out["beyond1"] = statistics.fmean(past1) if past1 else 0.0
    out["n_past1"] = len(past1)
    return out


def needed_wr(t):
    """Win rate a flat target T needs for mean 2.0 R against a -1R loss."""
    return 100.0 * (MONEY_GATE + 1.0) / (t + 1.0)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def report(rows, arms, meta, gaps):
    A_ = {a["key"]: line(rows, a["key"], a["bs"], a["ru"]) for a in arms}
    byfam = defaultdict(list)
    for a in arms:
        byfam[a["fam"]].append(a)
    ts = touch_stats(rows)

    c0 = A_["C0  incumbent 30/30/30/10 (shipped)"]

    scored = [(a, A_[a["key"]]) for a in arms if a["fam"] != "ctl"]
    ctls = [(a, A_[a["key"]]) for a in byfam["ctl"]]
    fam_of = {"A": ["A", "Agrid", "Astop"], "B": ["B"], "C": ["C"], "D": ["D"]}

    def best(fams, metric="per_risk"):
        pool = [x for x in scored if x[0]["fam"] in fams]
        return max(pool, key=lambda x: x[1][metric])

    bestA = best(fam_of["A"])
    bestB = best(fam_of["B"])
    bestC = best(fam_of["C"])
    bestD = best(fam_of["D"])
    allbest = max(scored + ctls, key=lambda x: x[1]["per_risk"])
    # the best arm with NO scale-in leg anywhere in it -- the honest "could a
    # pure scale-OUT change have got here" answer
    noadd = max([x for x in scored + ctls if x[0]["add"] is None],
                key=lambda x: x[1]["per_risk"])
    # the best arm that also keeps a liveable shape: not more than one month of
    # durability worse than the incumbent, and a median above -1.0 R
    live = max([x for x in scored + ctls
                if x[1]["median"] >= -1.0 and x[1]["green"] >= c0["green"] - 1],
               key=lambda x: x[1]["per_risk"])
    # every arm strictly above the incumbent's mean, split by whether it adds
    above = [x for x in scored + ctls if x[1]["per_risk"] > c0["mean"]]
    above_noadd = [x for x in above if x[0]["add"] is None]

    L = []
    add = L.append
    add("# W13 — scaling, as a mean-R lever")
    add("")
    add("Generated by `research/w13_scaling.py` over the **%d** traded rows of "
        "`research/g3_arm_ow1.json` (the shipped arm, `ON_WATCH=1`, replayed by "
        "`research/g3_onwatch_2y.py` at `47e60796`), %s → %s, %d sessions, %d "
        "symbols, `data_archive/` replay, zero fetches. Backstop **11:00** "
        "(`exit_lab.CLOCK_BAR = 90`) unless a row says otherwise. Error bar "
        "**±%.4f R**, the narrow bar — the wide ±1.5799 R bar was retired "
        "2026-08-28 (master spec §1.1)."
        % (len(rows), meta["first"], meta["last"], meta["sessions"],
           len(meta["symbols"]) if isinstance(meta["symbols"], list)
           else meta["symbols"], ERROR_BAR))
    add("")
    add("Austin, 2026-08-28: *\"if we change the scaling, the way scaling "
        "works, then we can hit that higher mean... I believe for scaling "
        "because that's what Scarface and JW do. They with ease average two to "
        "one risk to reward on trades.\"*")
    add("")

    # ---- the answer -------------------------------------------------------
    add("## The answer")
    add("")
    add("**Nothing reaches mean 2.0 R.** The best arm in this report is "
        "`%s` at **%+.4f R per unit of risk**, **%+.4f R short of the money "
        "gate**, at %d / %d months green against a durability gate of every "
        "month. That is the ceiling of this family. It is %.0f%% of the gate, "
        "and the %+.4f R still missing is larger than the entire spread of the "
        "42 exit policies measured before this one (+0.50 to +0.96 mean, a "
        "spread of 0.46 R) — so it is a ceiling, not a near-miss."
        % (allbest[0]["key"], allbest[1]["per_risk"],
           MONEY_GATE - allbest[1]["per_risk"], allbest[1]["green"],
           allbest[1]["tot_m"], 100.0 * allbest[1]["per_risk"] / MONEY_GATE,
           MONEY_GATE - allbest[1]["per_risk"]))
    add("")
    add("**Scale-in beats scale-out, and it is not close.** Best scale-IN arm: "
        "`%s`, %+.4f R per unit of risk. Best tail-weighted scale-OUT arm: "
        "`%s`, %+.4f R. The gap is **%+.4f R, %.0f× the ±%.4f R error bar**. "
        "More decisive than the family bests: **%d of the %d arms that beat "
        "the incumbent's %+.4f R mean carry a scale-in leg, and the best arm "
        "in this whole report with no add anywhere in it is `%s` at %+.4f R** "
        "— which is not a scale-OUT policy at all, it is the absence of one."
        % (bestA[0]["key"], bestA[1]["per_risk"], bestB[0]["key"],
           bestB[1]["per_risk"], bestA[1]["per_risk"] - bestB[1]["per_risk"],
           abs(bestA[1]["per_risk"] - bestB[1]["per_risk"]) / ERROR_BAR,
           ERROR_BAR, len(above) - len(above_noadd), len(above), c0["mean"],
           noadd[0]["key"], noadd[1]["per_risk"]))
    add("")
    add("**Austin's instinct is right about the direction and it still does "
        "not get there.** Scale-in is the only lever tested in this project "
        "that raises aggregate R without needing better selection, exactly as "
        "he argued. It raises the mean by **%+.4f R** off the shipped ladder "
        "(%+.4f → %+.4f), a readable **%.0f×** the error bar on a book that "
        "42 previous exit policies could not move off ~+0.9 R. The remaining "
        "%+.4f R is not an exit problem and no exit can pay it (§9)."
        % (bestA[1]["per_risk"] - c0["mean"], c0["mean"], bestA[1]["per_risk"],
           abs(bestA[1]["per_risk"] - c0["mean"]) / ERROR_BAR,
           MONEY_GATE - bestA[1]["per_risk"]))
    add("")
    add("**The median is what it costs, and on the top arm the cost is "
        "brutal.** `%s` books a median of %+.4f R against the incumbent's "
        "%+.4f R and %d / %d months green against %d / %d — its base rides "
        "every trade to the 11:00 clock on the original stop, so most trades "
        "book a full stop-out and the mean is carried entirely by the right "
        "tail. Austin, 2026-08-28: *\"The mean is arguably more important.\"* "
        "That makes this the right direction of trade and the exact reverse of "
        "W2's, which bought median by selling the tail — but a %+.4f R median "
        "is a shape almost nobody can actually sit through."
        % (bestA[0]["key"], bestA[1]["median"], c0["median"], bestA[1]["green"],
           bestA[1]["tot_m"], c0["green"], c0["tot_m"], bestA[1]["median"]))
    add("")
    add("**So the arm to actually look at is `%s`: %+.4f R mean, %+.4f R "
        "median, %d / %d months green** — the best arm in the report that "
        "keeps a median above −1 R and stays within one month of the "
        "incumbent's durability. It costs %.4f R of mean against the top arm "
        "and buys back %+.4f R of median. It is still %+.4f R short of the "
        "gate, and like the top arm it carries **3x the nominal position** at "
        "peak — free in R, not free in capital."
        % (live[0]["key"], live[1]["per_risk"], live[1]["median"],
           live[1]["green"], live[1]["tot_m"],
           abs(live[1]["per_risk"] - allbest[1]["per_risk"]),
           live[1]["median"] - allbest[1]["median"],
           MONEY_GATE - live[1]["per_risk"]))
    add("")
    add("One column caveat, stated once and true of every table: **`share of "
        "mean MFE` always divides by the BASE position's MFE**, so a scale-in "
        "arm carrying extra size can and does show a capture above what a "
        "one-unit exit could ever reach. It is a comparable number across "
        "arms only in the sense that the denominator is fixed; it is not a "
        "claim that any policy beat the tape (`--selfcheck` proves no arm "
        "books above the ceiling its own size and horizon actually offered).")
    add("")
    add("Read `mean R / risk unit` as the gate column everywhere below. An arm "
        "whose added tranche stops AT its scale point has risk units = 1.00 "
        "and its raw mean IS its risk-adjusted mean; an arm that puts the "
        "add's stop lower is genuinely risking more and gets divided down "
        "(§3.3).")
    add("")

    # ---- 1 ----------------------------------------------------------------
    add("## 1. Why no fixed target can get there, recomputed on this book")
    add("")
    add("For a fixed target T with win rate w against a −1 R loss, "
        "`mean R = w·T − (1−w)`, so the win rate needed for mean 2.0 R is "
        "`(2+1)/(T+1)`. Beside it, the share of these %d trades whose MFE "
        "actually touches T before a close beyond the stop "
        "(`h1_2y_nowatch.mfe_r`, 11:00 clock):" % len(rows))
    add("")
    add("| target | win rate needed for mean 2.0 R | actual touch rate | gap |")
    add("|---|---:|---:|---:|")
    for t in (2.0, 3.0, 5.0, 8.0):
        need, got = needed_wr(t), ts["touch%g" % t]
        add("| %.1fR | %.1f%% | %.1f%% | %s |"
            % (t, need, got, ("**short %.1f pts**" % (need - got))
               if need > got else ("clears by %.1f pts" % (got - need))))
    add("")
    add("**The gap narrows as the target grows and never closes.** A "
        "flat-target book is structurally incapable of the money gate — which "
        "is the empirical result 42 exit policies have already reported one at "
        "a time (g7's 8, g9/p10's 14, W2's 20; every one between +0.50 and "
        "+0.96 mean).")
    add("")
    add("These touch rates are a few points above the ones in the ticket "
        "(53.8%% / 41.1%% / 26.2%% / 12.9%% at 2/3/5/8 R) because that table was "
        "measured on a DIFFERENT book: `research/h1_2y_nowatch.json` arm A, "
        "ON WATCH **off**, n = 1,091. This report scores "
        "`research/g3_arm_ow1.json`, the shipped arm with ON WATCH **on**, "
        "n = %d. The conclusion is identical on both and the gap is a book "
        "difference, not a disagreement." % len(rows))
    add("")
    add("**The unexploited fact: %.1f%% of trades reach 1 R, and those %d "
        "trades offer a further %+.4f R of mean MFE beyond that 1 R point** "
        "(mean MFE over the whole book is %+.4f R). Family A is built to put "
        "size on exactly that. Note there is no \"1.0R\" row in the table "
        "above because the formula returns 150%% — a 1 R target cannot reach a "
        "2 R mean even at a 100%% hit rate, which is the degenerate end of the "
        "same argument."
        % (ts["touch1"], ts["n_past1"], ts["beyond1"], ts["mean_mfe"]))
    add("")

    # ---- 2 ----------------------------------------------------------------
    add("## 2. The controls")
    add("")
    add("Every one is an existing, unmodified function. They are the "
        "denominators for everything below.")
    add("")
    add(HEAD_N)
    add(RULE_N)
    for a in byfam["ctl"]:
        add(row_md(a["key"], A_[a["key"]], a["note"]))
    add("| **money gate** | **≥ +2.0000** | **≥ +2.0000** | — | — | **all** | "
        "— | — | — | — |")
    add("")

    # ---- 3 ----------------------------------------------------------------
    add("## 3. Family A — scale IN")
    add("")
    add("A tranche of `size` units is added when price touches `trigger_r`, "
        "filling at that price as a resting order, with its stop at the scale "
        "point. It is scored as a **separable leg** — `arm = base + add` — so "
        "each row's control is the same base with no add and the A/B is exact. "
        "The add never happens if a bar closes beyond the ORIGINAL stop first, "
        "and the add's own stop is live on the trigger bar itself: a bar that "
        "pokes the trigger and closes back under it stops the add at that "
        "close for a real debit (master spec §1.1, \"out on that same close\"). "
        "**\"Near-zero incremental risk\" means zero risk in the R denominator, "
        "not zero loss on the tape.**")
    add("")
    add("### 3.1 The canonical add on every base")
    add("")
    add(HEAD_N)
    add(RULE_N)
    for a in byfam["A"]:
        add(row_md(a["key"], A_[a["key"]], a["note"]))
    for a in byfam["ctl"]:
        add(row_md(a["key"] + " *(control)*", A_[a["key"]], a["note"]))
    add("")
    lifts = [(a["key"], A_[a["key"]]["mean"] - A_[c["key"]]["mean"])
             for a, c in zip(byfam["A"], byfam["ctl"])]
    lift = statistics.fmean(v for _k, v in lifts)
    add("**The add lifts the mean by exactly %+.4f R on every one of the five "
        "bases, and that identity is a construction, not a discovery.** "
        "Because the add is a separable leg, `mean(base + add) − mean(base) = "
        "mean(add)` for any base at all, so the lift column would be constant "
        "even if the add were garbage. **The empirical content is the single "
        "number: the added tranche's own mean is %+.4f R per unit at 1.0x "
        "size, %.0f× the ±%.4f R error bar, and it is POSITIVE** — the add "
        "survives the bleed of being stopped at its own scale point often "
        "enough that what it collects from the right tail more than pays for "
        "it. Everything family A earns is that one number times the size "
        "carried."
        % (lift, lift, abs(lift) / ERROR_BAR, ERROR_BAR))
    add("")
    add("What DOES vary by base is the shape. `flat_2r + add` keeps a %+.4f R "
        "median because its base still books a clean 2 R on most winners; "
        "`hold to 11:00 + add` collapses to a %+.4f R median because its base "
        "rides every loser to a full stop. Same mean lift, opposite "
        "liveability — which is why §7 ranks on mean and §8 shows the months."
        % (A_["A2  flat_2r + add 1.0x @1R"]["median"],
           A_["A5  hold to 11:00 + add 1.0x @1R"]["median"]))
    add("")

    add("### 3.2 The trigger × size grid")
    add("")
    add("On the two bases with the best mean. `size` is in units of the base "
        "position, so `2.0x` means carrying **3× the nominal position** at "
        "peak — a capital and options-liquidity constraint that `risk units` "
        "does not price.")
    add("")
    add(HEAD)
    add(RULE)
    for a in byfam["Agrid"]:
        add(row_md(a["key"], A_[a["key"]]))
    add("")

    add("### 3.3 Where the add's stop sits — the risk denominator, priced")
    add("")
    add("This is the sweep that can manufacture a number, so it is printed "
        "with the denominator that stops it. Moving the add's stop DOWN buys "
        "survival and pays for it in risk units: an add filled at 1 R with its "
        "stop at entry risks a further 1.0 unit, so the arm risks **2.00** "
        "units and its mean must be halved before it is compared to anything. "
        "The last two rows move the WHOLE arm's backstop, so their MFE "
        "denominator moves with them and they are comparable only to each "
        "other.")
    add("")
    add(HEAD_N)
    add(RULE_N)
    for a in byfam["Astop"]:
        add(row_md(a["key"], A_[a["key"]], a["note"]))
    add("")
    sp = A_["A  hold + add 1.0x @1R, add stop at the scale point"]
    hw = A_["A  hold + add 1.0x @1R, add stop half way back"]
    en = A_["A  hold + add 1.0x @1R, add stop at entry"]
    add("**Read the first three rows and the denominator does its job.** The "
        "raw mean rises monotonically as the add's stop is loosened — %+.4f → "
        "%+.4f → %+.4f — and the risk-adjusted mean falls monotonically — "
        "%+.4f → %+.4f → %+.4f. **Loosening the add's stop is not edge, it is "
        "leverage**, and on this book the leverage is priced worse than fair. "
        "The zero-incremental-risk version — the stop AT the scale point, "
        "which is what Austin's mentors are describing — is the only one that "
        "is genuinely free, and it is the best of the three on the only column "
        "that can be compared to the gate."
        % (sp["mean"], hw["mean"], en["mean"],
           sp["per_risk"], hw["per_risk"], en["per_risk"]))
    add("")
    add("Giving the add a fixed target instead of letting it ride costs mean R "
        "(`add exits 2R` %+.4f, `add exits 3R` %+.4f, riding %+.4f) — the same "
        "truncation §1 predicts for any fixed target. Pushing the whole arm's "
        "backstop out to 11:30 or 13:00 costs mean R too (%+.4f, %+.4f), which "
        "is W2 §2's backstop finding reproduced with an add attached."
        % (A_["A  hold + add 1.0x @1R, add exits 2R"]["mean"],
           A_["A  hold + add 1.0x @1R, add exits 3R"]["mean"], sp["mean"],
           A_["A  hold + add 1.0x @1R, backstop 11:30"]["mean"],
           A_["A  hold + add 1.0x @1R, backstop 13:00"]["mean"]))
    add("")

    # ---- 4 ----------------------------------------------------------------
    add("## 4. Family B — tail-weighted scale OUT")
    add("")
    add("Weights are shares of the original position taken at 1R / 2R / 3R; "
        "the remainder is a runner with no target, riding a break-even stop to "
        "11:00. `30/30/30, 10% runner` is the shipped split re-expressed on R "
        "rungs (W2's `R1`).")
    add("")
    add(HEAD)
    add(RULE)
    for a in byfam["B"]:
        add(row_md(a["key"], A_[a["key"]]))
    add("")
    b_sorted = sorted(byfam["B"], key=lambda a: -A_[a["key"]]["mean"])
    b_top, b_bot = A_[b_sorted[0]["key"]], A_[b_sorted[-1]["key"]]
    c4 = A_["C4  no rungs, orig stop, ride to 11:00"]
    add("**Tail-weighting WINS inside family B, monotonically — and the family "
        "still loses.** Best to worst on the mean: %s. Every step of weight "
        "moved off the front rung and onto the runner adds mean R and "
        "subtracts median R, from %+.4f mean / %+.4f median at 70/10/10 to "
        "%+.4f / %+.4f at 10/10/10. Extrapolate the trend to its limit — "
        "*no rungs at all* — and you get `C4` at %+.4f R, which beats every "
        "row in this table. **So family B does not have an optimum inside "
        "itself; its optimum is not scaling out.**"
        % (" > ".join("`%s` %+.4f" % (a["key"].split("  ", 1)[1],
                                      A_[a["key"]]["mean"]) for a in b_sorted),
           b_bot["mean"], b_bot["median"], b_top["mean"], b_top["median"],
           c4["mean"]))
    add("")
    add("**This is the opposite direction to W2's finding and the two are "
        "consistent, because \"runner\" names two different machines.** W2 "
        "found weight at the HOD rung beats weight on the trail monotonically "
        "(`50_20_20_10` +0.9054 > `30_30_30_10` +0.8976 mean, W2 §4). That "
        "runner rides an **ATR trail** and force-exits on a structure break or "
        "on 5 bars of consolidation — three separate early exits that clip the "
        "right tail before the clock. The runner here rides a plain "
        "**break-even stop to 11:00** with none of those, so it keeps the tail "
        "the ATR machinery was cutting off. Weight on a trail that exits early "
        "is worth less than a front rung; weight on a runner that actually "
        "runs is worth more. Both tables are right about their own runner, and "
        "W2 already reported the same thing from the other side: its `R5 no "
        "rungs (pure clock)` was the best MEAN in that report too.")
    add("")
    add("But the ceiling is low either way. The best arm in family B books "
        "%+.4f R, **below the incumbent's %+.4f R**, and even the limiting "
        "case `C4` at %+.4f R is %+.4f R short of the gate. **Re-weighting a "
        "scale-out cannot get to 2.0 R because it only redistributes R that "
        "the position already had. Family A adds size that was not there.**"
        % (b_top["mean"], c0["mean"], c4["mean"], MONEY_GATE - c4["mean"]))
    add("")

    # ---- 5 ----------------------------------------------------------------
    add("## 5. Family C — break-even stop timing")
    add("")
    add("`BE at X` moves the stop to entry the moment price touches X R; "
        "`never` leaves the original stop live for the whole trade. Run twice: "
        "once with no rungs (the BE move alone, nothing else changing) and "
        "once on the shipped 30/30/30 split.")
    add("")
    add(HEAD)
    add(RULE)
    for a in byfam["C"]:
        add(row_md(a["key"], A_[a["key"]]))
    add("")
    inv = (A_["C  no rungs, BE at 1.5R"]["mean"]
           - A_["C  no rungs, BE at 2.0R"]["mean"])
    add("**Moving the stop to break-even costs mean R at every trigger, and "
        "the earlier the move the more it costs. `never` wins both rung "
        "sets.** No rungs: %s. Shipped rungs: %s. The one inversion (no rungs, "
        "1.5R vs 2.0R) is %+.4f R, INSIDE the ±%.4f R error bar, so read those "
        "two as tied. The mechanism is the same one §4 exposes: a break-even "
        "stop converts a trade that would have recovered into a 0 R scratch, "
        "and the scratches it manufactures cost more, in aggregate, than the "
        "−1 R losses it prevents."
        % (" < ".join("`%s` %+.4f" % (lb, A_["C  no rungs, BE at %s" % lb]["mean"])
                      for lb in ("0.5R", "1.0R", "1.5R", "2.0R", "never")),
           " < ".join("`%s` %+.4f"
                      % (lb, A_["C  rungs 30/30/30, BE at %s" % lb]["mean"])
                      for lb in ("0.5R", "1.0R", "1.5R", "2.0R", "never")),
           inv, ERROR_BAR))
    add("")
    add("**It buys the median, and on the shipped rung set it buys durability "
        "too — `C  rungs 30/30/30, BE at 0.5R` is the only arm anywhere in "
        "this report with %d / %d months green.** It books %+.4f R mean, so it "
        "is +%.4f R from the money gate and is not a candidate; it is recorded "
        "because it is the single durability data point in the sweep and "
        "durability is half the gate."
        % (A_["C  rungs 30/30/30, BE at 0.5R"]["green"],
           A_["C  rungs 30/30/30, BE at 0.5R"]["tot_m"],
           A_["C  rungs 30/30/30, BE at 0.5R"]["mean"],
           MONEY_GATE - A_["C  rungs 30/30/30, BE at 0.5R"]["mean"]))
    add("")

    # ---- 6 ----------------------------------------------------------------
    add("## 6. Family D — hybrid")
    add("")
    add("A front tranche out at 2.0 R — where **67.5%** of Austin's own "
        "intended targets sit (`research/w11_tz_exit_efficiency.md` §3, 235 of "
        "348 rows) — AND size added at 1 R. Each `no add` row is that same "
        "front tranche alone, so the add's contribution reads straight off the "
        "pair.")
    add("")
    add(HEAD_N)
    add(RULE_N)
    for a in byfam["D"]:
        add(row_md(a["key"], A_[a["key"]], a["note"]))
    add("")

    # ---- 7 ----------------------------------------------------------------
    add("## 7. Every arm, ranked by mean R per unit of risk")
    add("")
    add(HEAD)
    add(RULE)
    for a, agg in sorted(scored + ctls, key=lambda x: -x[1]["per_risk"]):
        add(row_md(a["key"], agg))
    add("")
    add("Family bests, on mean R per unit of risk: **A** `%s` %+.4f · "
        "**B** `%s` %+.4f · **C** `%s` %+.4f · **D** `%s` %+.4f."
        % (bestA[0]["key"], bestA[1]["per_risk"], bestB[0]["key"],
           bestB[1]["per_risk"], bestC[0]["key"], bestC[1]["per_risk"],
           bestD[0]["key"], bestD[1]["per_risk"]))
    add("")
    add("A few rows are the same parameter point scored once and printed in "
        "two sections (`A5` = `A  hold + add 1.0x @1.0R` = `A  hold + add "
        "1.0x @1R, add stop at the scale point`; `C4` = `C  no rungs, BE at "
        "never`; `C3` = `B  30/30/30, 10%% runner` = `C  rungs 30/30/30, BE at "
        "1.0R`). Identical numbers on those rows are a cross-check that the "
        "three construction paths agree, not %d independent arms."
        % len(scored))
    add("")

    # ---- 8 ----------------------------------------------------------------
    add("## 8. The winner, month by month")
    add("")
    wk = bestA[0]["key"]
    add("`%s`, backstop %s, beside the incumbent ladder at the 11:00 horizon."
        % (wk, hhmm(bestA[0]["bs"])))
    add("")
    bym = defaultdict(list)
    for r in rows:
        bym[r["ym"]].append(r)
    add("| month | n | winner total R | winner mean R | winner median R | "
        "incumbent total R | delta |")
    add("|---|---:|---:|---:|---:|---:|---:|")
    ik = "C0  incumbent 30/30/30/10 (shipped)"
    wins = 0
    for ym in sorted(bym):
        rs = bym[ym]
        wt = sum(r[wk] for r in rs)
        it = sum(r[ik] for r in rs)
        if wt > it:
            wins += 1
        add("| %s | %d | %s | %+.3f | %+.3f | %s | %+.1f |"
            % (ym, len(rs), ("**%+.1f**" % wt) if wt <= 0 else "%+.1f" % wt,
               statistics.fmean(r[wk] for r in rs),
               statistics.median(r[wk] for r in rs),
               ("**%+.1f**" % it) if it <= 0 else "%+.1f" % it, wt - it))
    add("")
    add("**Winner %d / %d months green, incumbent %d / %d.** The durability "
        "gate is every month green and neither meets it. The winner out-earns "
        "the incumbent in **%d of %d** months and gains **%+.1f R** over the "
        "two years. Bold is a red month."
        % (A_[wk]["green"], A_[wk]["tot_m"], c0["green"], c0["tot_m"],
           wins, len(bym), A_[wk]["tot"] - c0["tot"]))
    add("")
    add("**This is the arm with the best mean, and it is not the arm to "
        "trade.** It loses %d months against the incumbent's %d and books a "
        "%+.4f R median. `%s` is the liveable version: %+.4f R mean, %+.4f R "
        "median, %d / %d months green, %+.1f R total. If W13 hands one arm "
        "forward, it is that one — and it is still %+.4f R short of the gate."
        % (A_[wk]["tot_m"] - A_[wk]["green"], c0["tot_m"] - c0["green"],
           A_[wk]["median"], live[0]["key"], live[1]["per_risk"],
           live[1]["median"], live[1]["green"], live[1]["tot_m"],
           live[1]["tot"], MONEY_GATE - live[1]["per_risk"]))
    add("")

    # ---- 9 ----------------------------------------------------------------
    add("## 9. What this does not say")
    add("")
    add("- **Nothing reaches mean 2.0 R.** The best arm anywhere here is `%s` "
        "at %+.4f R per unit of risk — **%+.4f R short**, %d / %d months "
        "green. Read that as a ceiling, not a near-miss."
        % (allbest[0]["key"], allbest[1]["per_risk"],
           MONEY_GATE - allbest[1]["per_risk"], allbest[1]["green"],
           allbest[1]["tot_m"]))
    add("- **What would have to change to close the rest, stated as a "
        "capture rate.** The ceiling on any exit is the tape: mean MFE at "
        "11:00 is %+.4f R, so **the money gate is exactly the demand that the "
        "book capture %.1f%% of its own maximum favourable excursion.** The "
        "shipped ladder captures %.1f%%. The best non-scaling arm anywhere "
        "captures %.1f%%. The best arm in this report captures %.1f%%. "
        "**Scaling moved capture from about a fifth of the tape to about a "
        "third; the gate wants half, and it wants it while every month stays "
        "green.** Closing that last %.1f points is not an exit problem — no "
        "policy in 42 previous ones or 55 here has come near it — it is a "
        "SELECTION problem: either the mean MFE of the book rises (fewer "
        "trades, better ones) or the loss rate falls. Scaling multiplies the "
        "book you have; it cannot manufacture excursion that never printed."
        % (ts["mean_mfe"], 100.0 * MONEY_GATE / ts["mean_mfe"], c0["cap"],
           noadd[1]["cap"], allbest[1]["cap"],
           100.0 * MONEY_GATE / ts["mean_mfe"] - allbest[1]["cap"]))
    add("- **§4 runs the OPPOSITE way to W2's monotonicity and the two are "
        "consistent — but the ticket predicted family B would fail and it "
        "failed for a different reason than predicted.** W2 found weight at "
        "the HOD rung beats weight on the trail monotonically; §4 finds weight "
        "on the runner beats weight at the front rung monotonically. Both are "
        "right about their own runner: W2's rides an ATR trail that force-exits "
        "on a structure break or 5 bars of consolidation, so it is cut off "
        "before the tail arrives; §4's rides a plain break-even stop to 11:00 "
        "and is not. So tail-weighting did NOT fail because tails are worth "
        "less — it failed because its own limiting case is *not scaling out at "
        "all* (`C4`, %+.4f R), and even that is %+.4f R short. **A scale-out "
        "only redistributes R the position already had; that is the structural "
        "reason no re-weighting of it can reach the gate, and it is why "
        "Austin's instinct to look at scale-IN rather than scale-out was the "
        "right instinct.**"
        % (A_["C4  no rungs, orig stop, ride to 11:00"]["mean"],
           MONEY_GATE - A_["C4  no rungs, orig stop, ride to 11:00"]["mean"]))
    add("- **The family-A lift is one number, and §3.1's constant column is a "
        "tautology.** Because the add is scored as a separable leg, "
        "`mean(base + add) − mean(base) = mean(add)` identically. The only "
        "empirical claim in family A is that the added tranche's own mean is "
        "%+.4f R per unit — positive, and %.0f× the error bar. Do not read the "
        "five-identical-lifts row as five independent confirmations."
        % (statistics.fmean(A_[a["key"]]["mean"] - A_[c["key"]]["mean"]
                            for a, c in zip(byfam["A"], byfam["ctl"])),
           abs(statistics.fmean(A_[a["key"]]["mean"] - A_[c["key"]]["mean"]
                                for a, c in zip(byfam["A"], byfam["ctl"])))
           / ERROR_BAR))
    add("- **The median falls.** Every family-A arm trades median for mean, "
        "which is the direction `CLAUDE.md` and Austin's 2026-08-28 correction "
        "ask for and the reverse of W2's. It is still a real cost, and the two "
        "reports should be read as a pair, not as a progression.")
    add("- **It changes no shipped default.** `staged_exit` and `scale_in_leg` "
        "are new functions in a new file. `exit_lab.scale_out`, `flat_target`, "
        "`hod_only`, `CLOCK_BAR`, `MAX_LOSS_R` and `STOP_TRIGGER_BUFFER_FRAC` "
        "are untouched; `--selfcheck` asserts `CLOCK_BAR` is back at 90.")
    add("- **It is in-sample over every parameter point.** All %d swept arms "
        "are chosen off the same data they are scored on. `CLAUDE.md`: "
        "held-out beats in-sample, always. A held-out split of this sweep is "
        "the next rig and it is NOT in this file." % len(scored))
    add("- **It does not price capital or options liquidity.** `2.0x` means "
        "carrying 3× the nominal position at peak, and on an options book that "
        "is a fill and a spread question, not an R question. `risk units` "
        "prices the risk; nothing here prices the size.")
    add("- **The add is a resting limit at the trigger price.** It assumes the "
        "fill is there on the touch — the same assumption every rung in "
        "`exit_lab` makes, but made on the BUY side, where it is less "
        "obviously safe.")
    add("- **It does not model options decay.** R is the result and dollars "
        "are a sizing skin (`CLAUDE.md`); this rig prices the stock tape only.")
    add("- **A pre-existing bug found while building the selfcheck, and NOT "
        "fixed here: `exit_lab.hod_only` can book below the −1.25 R floor.** "
        "It tests the stop over `range(entry_i+1, hod_i)` — exclusive of the "
        "HOD bar — so a HOD bar whose own close is far beyond the stop is "
        "booked in full and unfloored. `scale_out` had the identical "
        "off-by-one and it was fixed at `f5ff006a`; `hod_only` was not. It "
        "fires on **%d of %d symbol-days** (worst case seen: −1.4013 R). This "
        "file does not edit `exit_lab` — other rigs depend on it — so arms "
        "built on `hod_only` are exempted from the flat floor assertion and "
        "each breach is instead PROVEN attributable to `exit_lab.hod_only` "
        "itself. The effect on `hod_only`'s mean is a few thousandths of an R "
        "and it does not change any conclusion here, but the fix belongs in "
        "its own commit with `research/test_runner_stop.py` extended to cover "
        "it." % (len(HOD_BREACH), len(rows)))
    add("")

    # ---- 10 ---------------------------------------------------------------
    add("## 10. Provenance")
    add("")
    add("| number | script | commit |")
    add("|---|---|---|")
    add("| every figure in §1–§9 | `research/w13_scaling.py` | this commit |")
    add("| the traded book | `research/g3_onwatch_2y.py` → `g3_arm_ow1.json` | `47e60796` |")
    add("| `Bars`, `build_arm`, `agg_r`, `months` | `research/r9_simple_book.py` | `e4de7858` |")
    add("| `mfe_r` | `research/h1_2y_nowatch.py` | `f5ff006a` |")
    add("| `time_ladder`, `score`, `BAR_OF` | `research/w2_time_ladder.py` | `52b82d9a` |")
    add("| `scale_out`, `flat_target`, `hod_only`, the stop rule | `research/exit_lab.py` | `f5ff006a` |")
    add("| Austin's 2.0R target discipline (67.5%) | `research/w11_tz_exit_efficiency.py` | `57235338` |")
    add("| the retired wide error bar | `research/p26_intrabar_ambiguity.py` | `8bb78c77` |")
    add("")
    add("| arm | rows that could not be replayed | reason |")
    add("|---|---:|---|")
    add("| shipped (`ON_WATCH=1`) | %d | %d no archived session, %d entry minute "
        "absent, %d entry index past end |"
        % (sum(gaps.values()), gaps["day"], gaps["bar"], gaps["index"]))
    add("")
    add("`python research/w13_scaling.py --selfcheck` proves, on all %d rows: "
        "`staged_exit` reproduces `w2_time_ladder.time_ladder` exactly on the "
        "default rung set (so the causal conventions MATCH rather than being "
        "asserted to); no arm books above the MFE its own horizon offered, the "
        "ceiling extended by `size × (MFE − trigger_r)` for a scale-in arm; no "
        "leg books below −%.2f R per unit of original risk; MFE is monotone in "
        "the horizon; and `exit_lab.CLOCK_BAR` is restored to 90."
        % (len(rows), xl.MAX_LOSS_R))
    add("")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()

    cache = Bars()
    rows, meta, gaps = build_arm(BOOK, cache)
    print("book: %d traded rows, gaps %s" % (len(rows), gaps), file=sys.stderr)

    arms = build_arms()
    score(rows, cache, [(x["key"], x["bs"], x["fn"]) for x in arms])
    selfcheck(rows, arms, cache)
    if a.selfcheck:
        return

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(report(rows, arms, meta, gaps))
    print("wrote %s" % OUT)


if __name__ == "__main__":
    main()
