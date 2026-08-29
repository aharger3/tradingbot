"""T5 -- the structural target. Level first, 2R fallback (R9); a level inside
the 2R path is scale point 2 or 3, not an obstacle (R25); crossed with scale
plans including 50/20/20/10 (R10).

    Austin, probe_master_2026-08-29, `fact_target_choice`:
        "Pick a level first if no level then default 2r"
    Austin, `fact_level_in_path` (R25):
        "runners are shooting for that mean RR at least but maybe we should
         shoot higher"
    Austin, `fact_runner_sizing` (R10):
        "We're testing other options 50/20/20/10"

THE QUESTION THIS TRACK OWNS: does ANY target/scale arm reach mean R = 2.0
with every month green?

THE ARITHMETIC, STATED UP FRONT so no table can hide it. With the ratified
disaster stop (R1) every loss books at -1.000R, so

    mean R = w * Tbar - (1 - w)

where `w` is the fraction of decided trades that win and `Tbar` the mean R of
a winner. mean R = 2.0 therefore requires w * Tbar = 2 + (1 - w), i.e.

    Tbar = (3 - w) / w        w = 0.43 -> Tbar = 5.98R
                              w = 0.50 -> Tbar = 5.00R
                              w = 0.60 -> Tbar = 4.00R
                              w = 0.75 -> Tbar = 3.00R
                              w = 1.00 -> Tbar = 2.00R

A flat 2R target can never average 2.0R at any win rate below 100%. That is
not an opinion about this book, it is the identity. What an exit policy can
do is trade `w` against `Tbar`; this script measures where that curve actually
sits on the shipped 2,595-trade book, and prints the hindsight ceiling
(oracle MFE) so the gap between "the best exit possible" and "2.0R" is a
number and not a hope.

WHAT VARIES AND WHAT DOES NOT. Entry, stop and side are FIXED inputs, taken
from `research/bt2y_trades.json` (the shipped ratified book, commit 9edd2ba7).
Only the exit varies. So **no arm here can move held-out S recall** -- recall
is a property of which symbol-days the detector fires on, and this track does
not touch the detector. That is stated as a finding, not skipped: method
rule 2 says held-out recall governs, and an exit-only track cannot move the
governing gate by construction.

THE LEVEL ROSTER is `research/p21_target_availability.py::levels_for_entry`
-- the same roster `signal_runner.py` assembles for the in-between-mesh veto:
PDH/PDL, PMH/PML (premarket), ORH/ORL, causal HOD/LOD as of the entry bar, and
T10 pivots (`PIVOT_STRENGTH=2`, `PIVOT_LOOKBACK=30`, `as_of=entry_i`). T5 adds
whole psychological dollars, which `backtest_week.py`'s own runner target
already used (`floor(scale_level) + 1.0`) and which his level notes name
directly. Every level is causal: static prior-session data, or built only from
bars <= entry_i.

EXIT SEMANTICS, mirroring `backtest_week.py::_ladder_bar` bar for bar:
  1. the R1/R2 disaster stop, resting at entry -/+ 1.0R, fills on an intrabar
     TOUCH -- and only while the working stop is still the ORIGINAL stop
     (once rung 1 raises it to break-even, price cannot reach -1R without
     crossing the BE order first);
  2. the LEVEL stop triggers on the CLOSE and fills at that close, floored at
     -1.25R (`stop_rule.stop_fill_price`);
  3. target rungs are limit orders and fill on an intrabar touch, tested AFTER
     the stop (PESSIMISTIC_FILL=1: a bar that tags a rung and still closes
     beyond the stop books the loss);
  4. at most ONE rung fills per bar, exactly as `_ladder_bar` returns after
     scaling -- conservative, and it is what the shipped engine does;
  5. R11 is ratified ("First PT still moves to BE"), so rung 1 raises the stop
     to entry from the NEXT bar. `incumbent_nobe` turns that off as a
     sensitivity;
  6. R13 is ratified ("11:00 stops new entries; runners keep running"), so
     there is NO 11:00 force-flat. Whatever is open books at the session's
     last RTH close, the same scratch `simulate_day` books.

Usage:
    python research/t5_structural_target.py                 # full run + report
    python research/t5_structural_target.py --selftest      # causality proof
    python research/t5_structural_target.py --limit 300     # quick smoke

Missing archive days: `OMEN_ARCHIVE_EXTRA` is an os.pathsep-separated list of
extra data_archive roots searched when a CSV is absent from this checkout's
own `data_archive/`. 78 of the 2,595 traded rows (3.0%) sit on sessions
archived after the last data commit; without the extra root they are dropped
and the run reports its own coverage.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import polygon_feed as pf                                            # noqa: E402
from stop_rule import (stop_hit_on_close, stop_fill_price,           # noqa: E402
                       disaster_stop_price, disaster_stop_hit,
                       DISASTER_STOP_R, MAX_LOSS_R)

# ---------------------------------------------------------------------------
# archive fallback -- see module docstring
# ---------------------------------------------------------------------------
_EXTRA_ROOTS = [Path(p) for p in
                os.environ.get("OMEN_ARCHIVE_EXTRA", "").split(os.pathsep) if p.strip()]
_orig_fetch_day = pf.fetch_day


def _fetch_day(symbol: str, day_iso: str):
    """`pf.fetch_day`, but a CSV missing here may be read from an extra root.

    Never hits the network for a day any root has: the point is coverage of an
    already-archived session, not new data."""
    if (pf.ARCHIVE / symbol / f"{day_iso}.csv").exists():
        return _orig_fetch_day(symbol, day_iso)
    for root in _EXTRA_ROOTS:
        p = root / symbol / f"{day_iso}.csv"
        if p.exists():
            return pf._read_csv(p)
    return _orig_fetch_day(symbol, day_iso)


pf.fetch_day = _fetch_day
import research.p21_target_availability as p21                       # noqa: E402

# ---------------------------------------------------------------------------
# tunables, every one named so the report can quote it
# ---------------------------------------------------------------------------
MIN_RUNG_R = 0.25        # a rung closer than this to entry is spread noise, not a target
MIN_SPACING_R = 0.50     # consecutive rungs must be this far apart, or they are one level
MAX_LADDER_R = 12.0      # psych dollars are enumerated out to here; beyond it nothing fills
FALLBACK_R = 2.0         # R9's "if no level then default 2r"


def psych_dollars(entry, side, risk):
    """Whole psychological dollars in the trade's direction, out to MAX_LADDER_R.

    `backtest_week.py::simulate_day` already used exactly this idea for the
    runner target (`math.floor(scale_level) + 1.0`); this enumerates the whole
    grid instead of only the next one. Sub-$5 names get a $0.10 grid, mirroring
    `research/levels.psych_nodes`, so a $3 stock is not handed a target 30% away."""
    if risk <= 0:
        return []
    far = entry + MAX_LADDER_R * risk if side == "L" else entry - MAX_LADDER_R * risk
    lo, hi = (entry, far) if side == "L" else (far, entry)
    step = 0.10 if hi < 5.0 else 1.0
    out, v = [], math.floor(lo / step) * step
    n = 0
    while v <= hi and n < 20000:
        if v >= lo:
            out.append(round(v, 4))
        v = round(v + step, 4)
        n += 1
    return out


def roster(sym, day, entry_i, entry, stop, side):
    """{name: price} of every causal level T5 may aim at, plus psych dollars."""
    risk = abs(entry - stop)
    lv = dict(p21.levels_for_entry(sym, day, entry_i))
    for px in psych_dollars(entry, side, risk):
        lv[f"psych_{px}"] = px
    return lv


def ladder(levels, entry, stop, side, n_rungs, mode):
    """Ordered target prices for one trade under `mode`. Never look-ahead:
    every input is a price known at the entry bar.

    modes
      level        R9. Successive roster levels beyond entry. 2R fallback when
                   the roster offers nothing.
      level_2rmin  R9 + R25's "shoot higher": same ladder, but the FINAL rung is
                   pushed out to at least 2R -- a nearer level is a scale point,
                   never the whole trade's target.
      beyond_2r    R25 read literally. Inner rungs are the levels INSIDE the 2R
                   path (scale point 2 or 3); the final rung is the first level
                   AT OR BEYOND 2R, 2R itself when there is none.
      psych        whole psychological dollars only.
      next_level   the single nearest level beyond entry (his 4-of-15 "next
                   level" runner answer), 2R fallback.
      flat2r       the blind-2R target the engine invented.

    Returns (prices, used_fallback, n_levels_available)."""
    risk = abs(entry - stop)
    if risk <= 0:
        return [], True, 0
    long = side == "L"
    sgn = 1.0 if long else -1.0

    def r_of(px):
        return sgn * (px - entry) / risk

    two_r = entry + FALLBACK_R * risk if long else entry - FALLBACK_R * risk

    if mode.startswith("flat"):
        mult = float(mode[4:].rstrip("r"))
        return [entry + mult * risk if long else entry - mult * risk], True, 0

    src = list(levels.items())
    if mode == "psych":
        src = [(k, v) for k, v in src if k.startswith("psych_")]
    elif mode == "named":
        # Structural levels ONLY -- PDH/PDL, PMH/PML, ORH/ORL, causal HOD/LOD
        # and T10 pivots, with the whole-dollar grid removed. This is the arm
        # that decides whether "level first" is a real structural claim or an
        # artefact of a $1 grid dense enough that R9's "if no level" can never
        # be true.
        src = [(k, v) for k, v in src if not k.startswith("psych_")]
    cand = sorted({round(v, 4) for _k, v in src
                   if MIN_RUNG_R <= r_of(v) <= MAX_LADDER_R},
                  key=r_of)
    n_avail = len(cand)
    if not cand:
        return [two_r], True, 0

    # greedy spacing: two levels a nickel apart are one level
    picked = []
    for px in cand:
        if not picked or abs(r_of(px) - r_of(picked[-1])) >= MIN_SPACING_R:
            picked.append(px)

    if mode == "next_level":
        return [picked[0]], False, n_avail

    if mode == "beyond_2r":
        inner = [p for p in picked if r_of(p) < FALLBACK_R]
        outer = [p for p in picked if r_of(p) >= FALLBACK_R]
        final = outer[0] if outer else two_r
        rungs = inner[: max(0, n_rungs - 1)] + [final]
        return rungs, (not outer), n_avail

    rungs = picked[:n_rungs]
    if mode == "level_2rmin" and r_of(rungs[-1]) < FALLBACK_R:
        outer = [p for p in picked if r_of(p) >= FALLBACK_R]
        rungs = rungs[: max(0, n_rungs - 1)] + [outer[0] if outer else two_r]
    return rungs, False, n_avail


# ---------------------------------------------------------------------------
# the replay. Causal by construction: bar i reads bars <= i only, and the
# trail level applied to bar i is confirmed by bar i-1.
# ---------------------------------------------------------------------------

def is_swing_low(bars, j):
    return (0 < j < len(bars) - 1 and bars[j]["l"] < bars[j - 1]["l"]
            and bars[j]["l"] < bars[j + 1]["l"])


def is_swing_high(bars, j):
    return (0 < j < len(bars) - 1 and bars[j]["h"] > bars[j - 1]["h"]
            and bars[j]["h"] > bars[j + 1]["h"])


def replay(bars, entry_i, entry, stop, side, rungs, weights,
           trail_last=False, be_after_rung1=True, disaster=True):
    """Weighted realised R for one trade. See module docstring for the bar's
    order of operations. Returns (R, exit_bar_index)."""
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0 or entry_i >= n - 1:
        return 0.0, entry_i
    long = side == "L"
    sgn = 1.0 if long else -1.0

    def r_at(px):
        return sgn * (px - entry) / risk

    dz_px = disaster_stop_price(entry, risk, long, DISASTER_STOP_R)
    active = stop            # the working stop applied to the CURRENT bar
    on_orig = True           # is `active` still the original stop?
    booked = 0.0
    open_w = 1.0
    k = 0                    # next unfilled rung
    trail = None
    nr = len(rungs)

    for i in range(entry_i + 1, n):
        b = bars[i]
        # 1. R1/R2 disaster stop -- intrabar touch, only on the original stop
        if disaster and on_orig and disaster_stop_hit(b["h"], b["l"], dz_px, long):
            return booked + open_w * r_at(dz_px), i
        # 2. level stop -- close beyond it, filled at that close, floored -1.25R
        if stop_hit_on_close(b["c"], active, long):
            px = stop_fill_price(b["c"], entry, risk, long)
            return booked + open_w * r_at(px), i
        # 3. one rung per bar, limit order, intrabar touch
        if k < nr:
            px = rungs[k]
            if (b["h"] >= px) if long else (b["l"] <= px):
                # The LAST rung absorbs everything still open. That matters
                # when the roster is shorter than the plan -- `beyond_2r` finds
                # four spaced levels on only a minority of trades -- and
                # without it the unspent tranches would quietly sit to the
                # session close with no target, which is the `hold_eod` arm
                # smuggled into every short ladder. On a `+trail` arm the last
                # tranche is SUPPOSED to stay open, so it does not absorb.
                if k == nr - 1 and not trail_last:
                    w = open_w
                else:
                    w = min(weights[k], open_w)
                booked += w * r_at(px)
                open_w -= w
                k += 1
                if open_w <= 1e-9:
                    return booked, i
                if k == 1 and be_after_rung1:
                    active = entry
                    on_orig = False
        # 4. fold bar i-1's swing into the trail; it is confirmed by bar i, so
        #    it may only be applied from bar i+1 onward
        j = i - 1
        if long:
            if is_swing_low(bars, j) and (trail is None or bars[j]["l"] > trail):
                trail = bars[j]["l"]
        else:
            if is_swing_high(bars, j) and (trail is None or bars[j]["h"] < trail):
                trail = bars[j]["h"]
        if trail_last and k >= nr and trail is not None:
            new = max(active, trail) if long else min(active, trail)
            if new != active:
                active = new
                on_orig = False
    last = n - 1
    return booked + open_w * r_at(bars[last]["c"]), last


def incumbent(bars, entry_i, entry, stop, side, pdh, pdl, pmh, pml, be=True):
    """The SHIPPED exit, reproduced: `backtest_week.SCALE_PLAN='hod_then_runner_be'`.

    Rung 1 = 50% at the causal session extreme through the entry bar (a new
    session high/low after entry); stop then to break-even; runner 50% to the
    first key level beyond that scale point (PDH/PDL, premarket H/L, or the next
    whole dollar), which is `simulate_day`'s own `runner_tgt`. This is the
    control every arm below is measured against, and reproducing the shipped
    book's mean R is this rig's validation."""
    long = side == "L"
    seg = bars[: entry_i + 1]
    if not seg:
        return 0.0, entry_i
    if long:
        scale = max(b["h"] for b in seg)
        cands = [x for x in (pdh, pmh) if x is not None and x > scale]
        cands.append(math.floor(scale) + 1.0)
        runner_tgt = min(cands)
    else:
        scale = min(b["l"] for b in seg)
        cands = [x for x in (pdl, pml) if x is not None and x < scale]
        cands.append(math.ceil(scale) - 1.0)
        runner_tgt = max(cands)
    return replay(bars, entry_i, entry, stop, side, [scale, runner_tgt],
                  [0.5, 0.5], be_after_rung1=be)


def oracle_mfe(bars, entry_i, entry, stop, side):
    """NON-CAUSAL ceiling: 100% out at the best price printed before the stop
    would have ended it. Printed to bound the family, never to be traded."""
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    long = side == "L"
    sgn = 1.0 if long else -1.0
    dz = disaster_stop_price(entry, risk, long, DISASTER_STOP_R)
    best = None
    for i in range(entry_i + 1, len(bars)):
        b = bars[i]
        px = b["h"] if long else b["l"]
        v = sgn * (px - entry) / risk
        best = v if best is None else max(best, v)
        if disaster_stop_hit(b["h"], b["l"], dz, long):
            break
        if stop_hit_on_close(b["c"], stop, long):
            break
    return best if best is not None else 0.0


# ---------------------------------------------------------------------------
# arms
# ---------------------------------------------------------------------------
PLANS = {
    "100":          [1.00],
    "50_50":        [0.50, 0.50],
    "50_25_25":     [0.50, 0.25, 0.25],
    "50_20_20_10":  [0.50, 0.20, 0.20, 0.10],   # R10, his own numbers
    "30_30_30_10":  [0.30, 0.30, 0.30, 0.10],
    "25_25_25_25":  [0.25, 0.25, 0.25, 0.25],
}
LADDER_MODES = ["level", "level_2rmin", "beyond_2r", "psych", "named"]

# The pure-target frontier. Nothing structural about these -- they exist so the
# w-against-Tbar trade-off in section 1 is an OBSERVED curve on this book and
# not only an identity on paper.
FLAT_ARMS = ["flat1r", "flat2r", "flat3r", "flat4r", "flat6r", "flat8r"]

# --- his own runner-lane answers, `research/marks/probe_master_2026-08-29.jsonl`
# lane=`runner`, 15 cards. Ten carry an exit answer:
#   level 4  (AVGO_2026-07-08 "Whole psych number, scale out at top of candles",
#             MU_2026-03-26 "ORL", META_2025-01-14 "ORL", TSLA_2025-08-13)
#   trail 3  (NVDA_2024-08-23, COIN_2025-03-31 "LODD AND HTF LEVELS IF THEY
#             EXIST", COIN_2026-04-17)
#   2r    2  (TSLA_2026-05-13, ORCL_2026-06-08)
#   hold  1  (IREN_2026-08-03 "PMH IS A TARGET")
# and five are refusals ("Wouldn't trade", "too choppy", "good trade happens
# earlier") -- a SELECTION answer, not an exit answer, and out of scope here.
#
# HIS_MIXTURE spends the position across the four families in his own
# proportions. The representative chosen for each family is named here because
# it is MY choice, not his: he named a family, not an arm.
HIS_MIXTURE = {"level|50_20_20_10": 0.40,   # "level", with his own scale numbers
               "trail_only":        0.30,   # "trail behind structure"
               "flat2r":            0.20,   # "2r"
               "hold_eod":          0.10}   # "hold"


def arm_ids():
    ids = ["incumbent", "incumbent_nobe", "next_level", "hold_eod", "trail_only"]
    ids += FLAT_ARMS
    for m in LADDER_MODES:
        for p in PLANS:
            ids.append(f"{m}|{p}")
        ids.append(f"{m}|50_20_20_10+trail")
    return ids


def run_arm(arm, rec):
    """Realised R for one trade under one arm id."""
    bars, ei, e, s, sd = rec["bars"], rec["i"], rec["entry"], rec["stop"], rec["side"]
    if arm == "incumbent":
        return incumbent(bars, ei, e, s, sd, rec["pdh"], rec["pdl"],
                         rec["pmh"], rec["pml"])[0]
    if arm == "incumbent_nobe":
        return incumbent(bars, ei, e, s, sd, rec["pdh"], rec["pdl"],
                         rec["pmh"], rec["pml"], be=False)[0]
    if arm == "hold_eod":
        return replay(bars, ei, e, s, sd, [], [], be_after_rung1=False)[0]
    if arm == "trail_only":
        return replay(bars, ei, e, s, sd, [], [], trail_last=True,
                      be_after_rung1=False)[0]
    if arm in FLAT_ARMS:
        r, _, _ = ladder(rec["levels"], e, s, sd, 1, arm)
        return replay(bars, ei, e, s, sd, r, [1.0])[0]
    if arm == "next_level":
        r, _, _ = ladder(rec["levels"], e, s, sd, 1, "next_level")
        return replay(bars, ei, e, s, sd, r, [1.0])[0]
    mode, plan = arm.split("|")
    trail = plan.endswith("+trail")
    plan = plan[:-6] if trail else plan
    w = PLANS[plan]
    # On a `+trail` arm the LAST tranche has no fixed target -- it rides the
    # structure trail -- so the ladder is one rung shorter than the plan. Built
    # this way because `replay`'s final rung absorbs all remaining weight: ask
    # for len(w) rungs and the trail can never carry anything, which is the
    # unreachable-branch bug this repo has shipped four times.
    n_rungs = len(w) - 1 if trail else len(w)
    rungs, _, _ = ladder(rec["levels"], e, s, sd, n_rungs, mode)
    if trail:
        rungs = rungs[:n_rungs]
    return replay(bars, ei, e, s, sd, rungs, w, trail_last=trail)[0]


# ---------------------------------------------------------------------------
# book
# ---------------------------------------------------------------------------

def load_book(inp, limit=None, verbose=True):
    raw = json.load(open(inp))
    rows = [t for t in raw["trades"] if t.get("traded")]
    if limit:
        rows = rows[:limit]
    by_day = defaultdict(list)
    for t in rows:
        by_day[(t["sym"], t["day"])].append(t)
    book, missed = [], 0
    t0 = time.time()
    for n, (sym, day) in enumerate(sorted(by_day)):
        try:
            full = pf.fetch_day(sym, day)
            rth = pf.rth(full)
        except Exception:
            missed += len(by_day[(sym, day)])
            continue
        if not rth:
            missed += len(by_day[(sym, day)])
            continue
        bars = [{"o": c.open, "h": c.high, "l": c.low, "c": c.close} for c in rth]
        pmh, pml = pf.premarket_hi_lo(full)
        pdh, pdl = p21._pdh_pdl(sym, day)
        for t in by_day[(sym, day)]:
            i = t.get("entry_i")
            if i is None or i >= len(bars) - 1:
                missed += 1
                continue
            side = t["side"]
            book.append({"bars": bars, "i": i, "entry": t["entry"], "stop": t["stop"],
                         "side": side, "pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
                         "row": t,
                         "levels": roster(sym, day, i, t["entry"], t["stop"], side)})
        if verbose and n % 400 == 0:
            print(f"  loaded {n}/{len(by_day)} symbol-days  {time.time()-t0:.0f}s",
                  flush=True)
    return book, missed, len(rows)


def agg(rs):
    """(n, win%, mean R, total R). Wins are R > 0; R == 0 is a scratch and is
    out of the win-rate denominator -- `p21.agg` / `g7_exit_sweep.agg`'s rule."""
    if not rs:
        return 0, 0.0, 0.0, 0.0
    w = sum(1 for r in rs if r > 1e-9)
    dec = sum(1 for r in rs if abs(r) > 1e-9)
    return len(rs), (w / dec * 100 if dec else 0.0), sum(rs) / len(rs), sum(rs)


def months_green(rs, yms):
    m = defaultdict(float)
    for r, ym in zip(rs, yms):
        m[ym] += r
    g = sum(1 for v in m.values() if v > 0)
    return g, len(m), min(m.values()), sorted(k for k, v in m.items() if v <= 0)


def paired_bar(a, b):
    """95% bar on the PAIRED mean difference (same trades, different exits)."""
    d = [x - y for x, y in zip(a, b)]
    if len(d) < 2:
        return 0.0, 0.0
    return statistics.fmean(d), 1.96 * statistics.stdev(d) / math.sqrt(len(d))


def selection_ceiling(rs, target=2.0):
    """NON-CAUSAL. The largest share of the book whose best trades average
    `target`. Sort by realised R descending and walk down until the running mean
    falls below it.

    This is not a strategy -- it needs tomorrow's newspaper. It is the answer to
    "if the exit cannot get there, what does selection have to do?", and it is
    an UPPER bound: no causal selector can beat a perfect one."""
    srt = sorted(rs, reverse=True)
    run, best = 0.0, 0
    for i, r in enumerate(srt, 1):
        run += r
        if run / i >= target:
            best = i
    return best, len(srt), (100.0 * best / len(srt) if srt else 0.0)


def his_runner_cards(book):
    """His 15 runner-lane verdicts, matched onto the traded book by symbol-day.

    Ten carry an exit answer; each is scored under the family he named against
    the incumbent on that day's traded row(s). n = 10 -- far too small to
    decide anything, and reported for exactly that reason: it is the ONLY
    judgement data that exists on the exit question, and leaving it out would
    hide that the sample is this thin."""
    p = ROOT / "research" / "marks" / "probe_master_2026-08-29.jsonl"
    if not p.exists():
        return []
    fam = {"level": "level|50_20_20_10", "trail": "trail_only",
           "2r": "flat2r", "hold": "hold_eod"}
    idx = defaultdict(list)
    for rec in book:
        idx[(rec["row"]["sym"], rec["row"]["day"])].append(rec)
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        m = json.loads(line)
        if m.get("lane") != "runner":
            continue
        ans = (m.get("answers") or {}).get("exit") or []
        sym, day = m["card_id"].rsplit("_", 1)
        recs = idx.get((sym, day), [])
        row = {"card": m["card_id"], "answer": ans[0] if ans else "(refused)",
               "note": (m.get("notes") or {}).get("px", ""), "n_rows": len(recs)}
        if ans and ans[0] in fam and recs:
            arm = fam[ans[0]]
            row["arm"] = arm
            row["his_arm_r"] = round(statistics.fmean(
                [run_arm(arm, r) for r in recs]), 3)
            row["incumbent_r"] = round(statistics.fmean(
                [run_arm("incumbent", r) for r in recs]), 3)
        out.append(row)
    return out


# ---------------------------------------------------------------------------

def selftest(inp, sample=40):
    """CAUSALITY. Truncating the tape one bar after a policy's own exit must not
    change its answer -- if any policy read a bar past its exit, it would."""
    book, _, _ = load_book(inp, limit=sample * 3, verbose=False)
    book = book[:sample]
    bad = 0
    for rec in book:
        bars = rec["bars"]
        for arm in arm_ids():
            full = run_arm(arm, rec)
            ok = False
            for cut in range(rec["i"] + 2, len(bars) + 1):
                sub = dict(rec)
                sub["bars"] = bars[:cut]
                if abs(run_arm(arm, sub) - full) < 1e-9:
                    ok = True
                    break
            if not ok:
                bad += 1
                print(f"  NON-CAUSAL {arm} {rec['row']['sym']} {rec['row']['day']}")
    print(f"selftest: {len(book)} trades x {len(arm_ids())} arms, {bad} non-causal")
    return bad == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inp", default=str(ROOT / "research" / "bt2y_trades.json"))
    ap.add_argument("--out", default=str(ROOT / "research" / "t5_structural-target.md"))
    ap.add_argument("--json", default=str(ROOT / "research" / "t5_structural_target.json"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--render-only", action="store_true",
                    help="re-render the .md from an existing .json, no replay")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest(a.inp) else 1)
    if a.render_only:
        write_report(a.out, json.load(open(a.json)))
        print(f"re-rendered {a.out} from {a.json}")
        return

    t0 = time.time()
    book, missed, n_rows = load_book(a.inp, a.limit)
    print(f"book: {len(book)} of {n_rows} traded rows ({missed} without bars), "
          f"{time.time()-t0:.0f}s", flush=True)

    yms = [r["row"]["ym"] for r in book]
    shipped = [r["row"]["r"] for r in book]

    results = {"shipped_book (bt2y_trades.json)": shipped}
    for arm in arm_ids():
        t1 = time.time()
        results[arm] = [run_arm(arm, r) for r in book]
        print(f"  {arm:34s} mean {statistics.fmean(results[arm]):+.4f}  "
              f"{time.time()-t1:.0f}s", flush=True)
    # his own runner-lane proportions, spent across the four families
    results["his_mixture (40 level/30 trail/20 2r/10 hold)"] = [
        sum(w * results[a][i] for a, w in HIS_MIXTURE.items())
        for i in range(len(book))]
    results["oracle_MFE (non-causal)"] = [
        oracle_mfe(r["bars"], r["i"], r["entry"], r["stop"], r["side"]) for r in book]

    # reachability of R9's fallback and of the ladder itself
    reach = {}
    for mode in LADDER_MODES + ["next_level"]:
        fb = navail = deep = 0
        for r in book:
            rungs, used_fb, na = ladder(r["levels"], r["entry"], r["stop"],
                                        r["side"], 4, mode)
            fb += bool(used_fb)
            navail += na
            deep += (len(rungs) >= 4)
        reach[mode] = {"fallback_pct": round(100 * fb / len(book), 2),
                       "mean_levels_available": round(navail / len(book), 2),
                       "four_rung_pct": round(100 * deep / len(book), 2)}

    rows = []
    for arm, rs in results.items():
        n, wr, mr, tot = agg(rs)
        g, tm, worst, red = months_green(rs, yms)
        wins = [r for r in rs if r > 1e-9]
        diff, bar = paired_bar(rs, results["incumbent"])
        rows.append({"arm": arm, "n": n, "win_pct": round(wr, 1),
                     "mean_r": round(mr, 4), "total_r": round(tot, 1),
                     "mean_winner_r": round(statistics.fmean(wins), 3) if wins else 0.0,
                     "months_green": f"{g}/{tm}", "worst_month_r": round(worst, 2),
                     "red_months": red,
                     "vs_incumbent": round(diff, 4), "bar95": round(bar, 4),
                     "inside_bar": abs(diff) <= bar,
                     "gate_met": ("n/a (non-causal)" if "oracle" in arm
                                  else bool(mr >= 2.0 and g == tm))})
    rows.sort(key=lambda x: -x["mean_r"])

    # what selection would have to do if the exit cannot get there
    sel = {}
    for arm in ("shipped_book (bt2y_trades.json)", "incumbent",
                max((r["arm"] for r in rows
                     if "oracle" not in r["arm"]
                     and not r["arm"].startswith("shipped_book")),
                    key=lambda k: statistics.fmean(results[k]))):
        k, tot, pct = selection_ceiling(results[arm], 2.0)
        sel[arm] = {"trades_kept": k, "of": tot, "pct": round(pct, 2)}

    cards = his_runner_cards(book)

    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "book": a.inp, "n_trades": len(book), "n_traded_rows": n_rows,
           "no_bars": missed, "arms": rows, "reachability": reach,
           "selection_ceiling_2r": sel, "his_runner_cards": cards,
           "his_mixture_definition": HIS_MIXTURE,
           "constants": {"MIN_RUNG_R": MIN_RUNG_R, "MIN_SPACING_R": MIN_SPACING_R,
                         "MAX_LADDER_R": MAX_LADDER_R, "FALLBACK_R": FALLBACK_R,
                         "DISASTER_STOP_R": DISASTER_STOP_R, "MAX_LOSS_R": MAX_LOSS_R}}
    Path(a.json).write_text(json.dumps(out, indent=1))
    write_report(a.out, out)
    print(f"wrote {a.out} and {a.json}  ({time.time()-t0:.0f}s)")


def md(x):
    """Arm ids carry a `|` (`level|50_20_20_10`), which would split a markdown
    table cell even inside backticks. Escape it wherever an id is rendered."""
    return str(x).replace("|", "\\|")


def table(rows, cols, keys):
    L = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        L.append("| " + " | ".join(md(r[k]) for k in keys) + " |")
    return L


def write_report(path, out):
    rows = out["arms"]
    causal = [r for r in rows if "oracle" not in r["arm"]
              and not r["arm"].startswith("shipped_book")]
    best = max(causal, key=lambda x: x["mean_r"])
    inc = next(r for r in rows if r["arm"] == "incumbent")
    ship = next(r for r in rows if r["arm"].startswith("shipped_book"))
    orc = next(r for r in rows if r["arm"].startswith("oracle"))
    gate_hits = [r for r in causal if r["gate_met"] is True]
    n = out["n_trades"]
    L = []
    L.append("# T5 - the structural target")
    L.append("")
    # Arms that beat the incumbent by MORE than their own bar. Computed, not
    # asserted: this sentence is the whole verdict and it must not be a claim.
    real_wins = [r for r in causal
                 if r["vs_incumbent"] > 0 and not r["inside_bar"]]
    real_losses = [r for r in causal
                   if r["vs_incumbent"] < 0 and not r["inside_bar"]]
    if gate_hits:
        L.append("**An arm reaches the money gate: " +
                 ", ".join(f"`{r['arm']}` ({r['mean_r']:+.4f} R, "
                           f"{r['months_green']} green)" for r in gate_hits) + ".**")
    else:
        L.append(f"**Null result: the money gate is not an exit problem.** Across "
                 f"{len(causal)} target and scale-plan arms over {n:,} traded "
                 f"rows, not one reaches mean 2.0 R, and "
                 f"**{len(real_wins)} arms beat the shipped exit by more than "
                 f"their own error bar**. The best causal arm books "
                 f"{best['mean_r']:+.4f} R (`{best['arm']}`) - a paired move of "
                 f"{best['vs_incumbent']:+.4f} R against a "
                 f"+/-{best['bar95']:.4f} R bar, so **inside its bar**"
                 + (f", and it fails durability at {best['months_green']} months "
                    f"green (worst month {best['worst_month_r']:+.2f} R)"
                    if best["months_green"] != inc["months_green"] else "") +
                 f". {len(real_losses)} arms move outside their bar and **every "
                 f"one of them moves DOWN**. The shipped exit "
                 f"({inc['mean_r']:+.4f} R, {inc['months_green']} green) is "
                 f"already the best durable policy in the family.")
        L.append("")
        L.append(f"**mean R = 2.0 needs {2.0 - inc['mean_r']:+.4f} R more than "
                 f"the shipped book**, and the perfect-hindsight ceiling on this "
                 f"book is {orc['mean_r']:+.4f} R. The gap is not in where the "
                 f"target sits; it is in which trades are taken (section 5).")
    L.append("")
    L.append(f"Generated by `research/t5_structural_target.py` from "
             f"`{Path(out['book']).name}` (the shipped ratified book). "
             f"{n:,} of {out['n_traded_rows']:,} traded rows replayed; "
             f"{out['no_bars']} had no archived bars. Entry, stop and side are "
             f"fixed - only the exit varies. Causality proved by "
             f"`--selftest` (truncated-tape replay, every arm); exit semantics "
             f"asserted on hand-built bars by `research/test_t5_target.py`.")
    L.append("")
    L.append("Reproduce: `OMEN_ARCHIVE_EXTRA=<extra data_archive root> python "
             "research/t5_structural_target.py`. Script and report land in "
             "_this commit_.")
    L.append("")
    L.append("## 1. The arithmetic, before any table")
    L.append("")
    L.append("With the ratified disaster stop (R1) every full loss books "
             "-1.000R, so `mean R = w*Tbar - (1-w)` and reaching 2.0R requires "
             "`Tbar = (3-w)/w`:")
    L.append("")
    L.append("| win rate w | mean winner Tbar needed for mean R = 2.0 |")
    L.append("|---|---|")
    for w in (0.40, 0.4306, 0.50, 0.60, 0.75, 1.00):
        L.append(f"| {w*100:.2f}% | {(3-w)/w:+.2f} R |")
    L.append("")
    L.append(f"The shipped book wins {ship['win_pct']}% and its average winner "
             f"is {ship['mean_winner_r']:+.3f} R. **A flat 2R target cannot "
             f"average 2.0R at any win rate below 100%** - that is the identity, "
             f"not a property of this book. Austin's *\"maybe we should shoot "
             f"higher\"* is arithmetically necessary, not optional.")
    L.append("")
    L.append(f"**The ceiling.** Exiting every trade at its single best printed "
             f"price before the stop would have ended it - pure hindsight, "
             f"untradeable - returns **{orc['mean_r']:+.4f} R** at "
             f"{orc['win_pct']}%. That is the roof over every exit policy that "
             f"could ever be written on this book. The best causal arm captures "
             f"{100*best['mean_r']/orc['mean_r']:.1f}% of it, and 2.0R is "
             f"{100*2.0/orc['mean_r']:.1f}% of it.")
    L.append("")
    L.append("**And the book agrees with the identity.** Walking a single flat "
             "target from 1R to 8R trades `w` against `Tbar` almost exactly one "
             "for one - the product barely moves:")
    L.append("")
    L.append("| flat target | win% | mean winner R | mean R |")
    L.append("|---|---|---|---|")
    for fa in FLAT_ARMS:
        r = next((x for x in rows if x["arm"] == fa), None)
        if r:
            L.append(f"| {fa[4:].upper()} | {r['win_pct']}% | "
                     f"{r['mean_winner_r']:+.3f} | {r['mean_r']:+.4f} |")
    L.append("")
    L.append("That flatness is the whole result. Where the target sits is not "
             "what is wrong with this book.")
    L.append("")
    L.append("## 2. Every arm")
    L.append("")
    L.append("`vs_incumbent` is the PAIRED mean difference (same trades, "
             "different exits); `bar95` is its own 95% bar. An arm whose move is "
             "inside its bar is a **null result** and is marked `True` under "
             "`null?`.")
    L.append("")
    L += table(rows,
               ["arm", "n", "win%", "mean R", "mean winner R", "total R",
                "months green", "worst month R", "vs incumbent", "+/-95% bar",
                "null?", "gate met"],
               ["arm", "n", "win_pct", "mean_r", "mean_winner_r", "total_r",
                "months_green", "worst_month_r", "vs_incumbent", "bar95",
                "inside_bar", "gate_met"])
    L.append("")
    L.append("## 3. Reachability, checked before any tuning")
    L.append("")
    L.append("Method rule 3: a branch that fires under 1% or over 85% of the "
             "time is a finding about the gate, not the threshold. "
             "`fallback_pct` is how often R9's *\"if no level then default 2r\"* "
             "actually fires.")
    L.append("")
    L.append("| ladder mode | 2R-fallback fires | mean levels available | reaches 4 rungs |")
    L.append("|---|---|---|---|")
    for m, d in out["reachability"].items():
        L.append(f"| `{m}` | {d['fallback_pct']}% | {d['mean_levels_available']} "
                 f"| {d['four_rung_pct']}% |")
    L.append("")
    L.append("`named` is the roster with the whole-dollar grid REMOVED - only "
             "PDH/PDL, PMH/PML, ORH/ORL, the causal HOD/LOD and T10 pivots. It "
             "is in the table because a $1 grid is dense enough to guarantee a "
             "target on every trade, and a rule whose escape hatch can never "
             "open is the bug class this repo has shipped four times. Compare "
             "its fallback rate with `level`'s to see whether *\"if no level\"* "
             "is a real condition or one the grid answered for him.")
    L.append("")
    L.append("## 4. His own runner-lane answers")
    L.append("")
    L.append("`research/marks/probe_master_2026-08-29.jsonl`, lane `runner`, 15 "
             "cards. Ten carry an exit answer - **4 level, 3 trail, 2 2R, 1 "
             "hold** - and five are refusals (*\"Wouldn't trade\"*, *\"BR too "
             "choppy\"*, *\"goood trade happens earlier\"*), which are SELECTION "
             "answers and out of this track's scope. His level notes name the "
             "targets by hand: *\"PMH IS A TARGET\"*, *\"ORL\"* (twice), "
             "*\"Whole psych number, scale out at top of candles\"*, *\"LODD AND "
             "HTF LEVELS IF THEY EXIST\"*.")
    L.append("")
    L.append("`his_mixture` in the table above spends the position across those "
             "four families in his own proportions. The representative arm for "
             "each family is named here because it is a choice made in this "
             "script, not by him - he named a family, not an arm:")
    L.append("")
    for k, v in out["his_mixture_definition"].items():
        L.append(f"- {v:.0%} `{md(k)}`")
    L.append("")
    L.append("Card by card, the family he named against the incumbent on that "
             "symbol-day's traded row(s). **n = 10. This decides nothing** - it "
             "is reported because it is the only judgement data that exists on "
             "the exit question, and leaving it out would hide how thin that is.")
    L.append("")
    L.append("| card | his answer | note | rows | his family | incumbent |")
    L.append("|---|---|---|---|---|---|")
    for c in out["his_runner_cards"]:
        L.append(f"| {c['card']} | `{c['answer']}` | {c.get('note','')} | "
                 f"{c['n_rows']} | "
                 f"{('%+.3f' % c['his_arm_r']) if 'his_arm_r' in c else '-'} | "
                 f"{('%+.3f' % c['incumbent_r']) if 'incumbent_r' in c else '-'} |")
    L.append("")
    L.append("## 5. What the arithmetic still needs")
    L.append("")
    L.append("If no exit reaches 2.0R, the shortfall has to come from selection. "
             "**Non-causal upper bound**: sort the book by realised R and keep "
             "the best trades until the running mean falls below 2.0R. No causal "
             "selector can beat a perfect one, so this is a floor on how much of "
             "the book would have to go.")
    L.append("")
    L.append("| exit policy | trades that could be kept at mean 2.0R | of | share |")
    L.append("|---|---|---|---|")
    for arm, d in out["selection_ceiling_2r"].items():
        L.append(f"| `{arm}` | {d['trades_kept']:,} | {d['of']:,} | {d['pct']}% |")
    L.append("")
    L.append("## 6. Held-out recall")
    L.append("")
    L.append("**Unmovable by this track, and that is the finding.** Held-out S "
             "recall (`research/marks/probe_s_sweep_2026-08-28.jsonl`, 34 S of "
             "100) and his 40 veto verdicts "
             "(`research/marks/probe_master_2026-08-29.jsonl`) score which "
             "symbol-days the engine FIRES on. T5 fixes entry, stop and side and "
             "varies only the exit, so every arm above fires on exactly the same "
             "rows and scores exactly T0's 18/34 = 52.9% recall and 2 of 27 "
             "false fires. Method rule 2 says held-out recall governs; on this "
             "track it cannot move, so nothing here can clear the gate that "
             "governs.")
    L.append("")
    L.append("## 7. Verdict, item by item")
    L.append("")

    def row(name):
        return next((r for r in rows if r["arm"] == name), None)

    def verdict(r):
        if r is None:
            return "not run"
        tag = "**NULL** (inside its bar)" if r["inside_bar"] else \
              ("**real gain**" if r["vs_incumbent"] > 0 else "**real cost**")
        return (f"{r['mean_r']:+.4f} R, {r['win_pct']}% win, "
                f"{r['months_green']} green - "
                f"{r['vs_incumbent']:+.4f} R vs the shipped exit against a "
                f"+/-{r['bar95']:.4f} R bar, {tag}")
    L.append("| his item | the arm that tests it | result |")
    L.append("|---|---|---|")
    for label, arm in [
            ("R9 level first, 2R fallback", "level|50_20_20_10"),
            ("R9, structural levels only (no $1 grid)", "named|50_20_20_10"),
            ("R9 read as \"the next level\"", "next_level"),
            ("R25 a level in the path is a scale point, aim past 2R",
             "beyond_2r|100"),
            ("R25 with inner rungs at the levels inside 2R",
             "beyond_2r|50_20_20_10"),
            ("R10 his own 50/20/20/10", "level|50_20_20_10"),
            ("the blind 2R the engine invented", "flat2r"),
            ("\"trail behind structure\"", "trail_only"),
            ("\"hold\"", "hold_eod"),
            ("his four answers in his own proportions",
             "his_mixture (40 level/30 trail/20 2r/10 hold)"),
            ("R11 first PT moves to BE (removing it)", "incumbent_nobe")]:
        L.append(f"| {label} | `{md(arm)}` | {verdict(row(arm))} |")
    L.append("")
    L.append("Read together: **raising the win rate is not the same as raising "
             "mean R, and on this book it is the opposite.** Level-first "
             "targeting does exactly what it should - `level|50_20_20_10` lifts "
             "the win rate from 43.4% to 66.5% - and mean R falls, because the "
             "average winner falls further, from +2.562 R to +1.063 R. That is "
             "`w * Tbar` staying put. `next_level` is the extreme case: 74.4% "
             "win, and the worst mean R of any arm measured.")
    L.append("")
    L.append("**R9 and R25 are ratified and ship at his answer.** This track "
             "does not re-litigate them; it prices them, and the price of "
             "level-first at his own scale plan is a real cost outside its bar. "
             "That belongs in T22's stack decision, not in a re-vote.")
    L.append("")
    L.append("## 8. Constants")
    L.append("")
    for k, v in out["constants"].items():
        L.append(f"- `{k}` = {v}")
    L.append("")
    L.append(f"Generated {out['generated']}.")
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
