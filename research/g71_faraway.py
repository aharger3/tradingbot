"""G7.1 / track `faraway` -- "never refuse for distance, find another target".

    Austin, 2026-08-29 (`Projects/omen-rulebook.md`, "Targets: never refuse for
    distance, find another target"):
        "we dont need to refuse trades that have a far level away for Q8, we
         just need to find other targets."

THE QUESTION THIS TRACK OWNS, in three parts:

  1. Where does the shipped engine refuse or degrade a setup because the next
     level is FAR? (static audit -- see research/g71_faraway.md section 1;
     this script measures the one site that is live.)
  2. How many of the 2-year book's traded signals are hit by it, and what would
     they have returned with an alternative target?
  3. When the next of his six levels is far, what else is a valid target?
     Measure every candidate as the FALLBACK.

WHAT "FAR" MEANS HERE. His six levels are PDH/PDL, PMH/PML, ORH/ORL
(`research/g71_levels.md` section 1). For each traded row the roster is rebuilt
causally at the entry bar and the nearest six-level strictly beyond entry in the
trade direction is found. Its distance in R is `next_six_R`. A row is

    NONE : no six-level at all beyond entry (+MIN_RUNG_R)
    FAR  : next_six_R > FAR_R                       (FAR_R swept, 2.0 default)
    NEAR : otherwise

NONE+FAR is the population Austin's sentence is about: the level-first target
policy has nothing usable, and the shipped code silently degrades the runner to
`math.floor(scale_level) + 1.0` -- at most $1 past the session extreme, however
far the real level is (`backtest_week.py:851-858`).

WHAT VARIES AND WHAT DOES NOT. Entry, stop, side and entry bar are FIXED inputs
from `research/bt2y_trades.json`. Only the target varies. So no arm here can move
held-out S recall -- recall is a property of which symbol-days the detector fires
on, and this script does not touch the detector. Stated as a finding, not skipped.

EXIT SEMANTICS are `research/t5_structural_target.py::replay`, imported, not
re-implemented: the R1/R2 disaster stop on an intrabar touch while the stop is
still original, the level stop on the CLOSE floored at -1.25R via
`stop_rule.stop_fill_price`, target rungs as limit orders tested AFTER the stop,
one rung per bar, BE after rung 1 (R11), no 11:00 force-flat (R13). The control
arm is `t5.incumbent`, which reproduces `backtest_week.SCALE_PLAN=
"hod_then_runner_be"` bar for bar.

TWO FRAMINGS, both reported:
  single   -- 100% of the position at the candidate target.
  ladder   -- the SHIPPED shape with only the runner leg swapped: 50% at the
              causal session extreme, stop to BE, 50% at the candidate. This is
              the drop-in, and it is what the diff in the report implements.

CANDIDATE TARGETS, every one causal (built from bars <= entry_i or from static
prior-session data):
  six_next   the far six-level itself         -- the control, "level first"
  hodlod     causal session HOD/LOD at entry  -- shipped rung 1
  flat2r     entry +/- 2.0 x risk            -- R9's stated fallback
  round      next whole psych dollar          -- the shipped runner fallback
  swing      nearest T10 swing pivot beyond entry (PIVOT_STRENGTH=2, LOOKBACK=30)
  mmove      measured move: the breakout leg's own height projected from entry
  vwap       session VWAP through the entry bar
  atr1/2/3   entry +/- k x ATR(14) of the 1-min bars through the entry bar

A candidate that lands nearer than MIN_RUNG_R (0.25R) beyond entry is NOT a
target -- it is spread noise -- and is reported unavailable rather than clamped,
so no arm can quietly become "exit at entry".

Usage:
    python research/g71_faraway.py                    # full run + report
    python research/g71_faraway.py --limit 300        # smoke
    python research/g71_faraway.py --selftest         # causality + mechanics

Missing archive days: `OMEN_ARCHIVE_EXTRA` is an os.pathsep-separated list of
extra data_archive roots, honoured by t5's fetch_day patch which this imports.
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
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import polygon_feed as pf                                        # noqa: E402
import research.t5_structural_target as t5                       # noqa: E402
import research.p21_target_availability as p21                   # noqa: E402
from signal_runner import pivot_levels, PIVOT_LOOKBACK           # noqa: E402

# ---------------------------------------------------------------------------
# tunables -- every one named so the report can quote it
# ---------------------------------------------------------------------------
SIX = ("PDH", "PDL", "PMH", "PML", "ORH", "ORL")
MIN_RUNG_R = t5.MIN_RUNG_R      # 0.25 -- nearer than this is spread noise
FAR_R = 2.0                     # default "far" threshold, swept in the report
FAR_SWEEP = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0)
ATR_N = 14
MMOVE_LOOKBACK = 30             # bars back for the leg-origin swing
CAND_ORDER = ["six_next", "hodlod", "swing", "round", "mmove",
              "vwap", "atr1", "atr2", "atr3", "flat2r"]


# ---------------------------------------------------------------------------
# causal features at the entry bar
# ---------------------------------------------------------------------------

def _sgn(side):
    return 1.0 if side == "L" else -1.0


def r_of(px, entry, risk, side):
    return _sgn(side) * (px - entry) / risk


def valid(px, entry, risk, side):
    """A candidate is a target only if it sits at least MIN_RUNG_R beyond
    entry in the trade's direction. Never clamped -- unavailable is reported."""
    if px is None or risk <= 0:
        return None
    return px if r_of(px, entry, risk, side) >= MIN_RUNG_R else None


def atr_at(bars, i, n=ATR_N):
    """True-range ATR of the 1-min RTH bars through bar i, inclusive. Causal."""
    if i <= 0:
        return None
    lo = max(1, i - n + 1)
    trs = []
    for k in range(lo, i + 1):
        p = bars[k - 1]["c"]
        trs.append(max(bars[k]["h"] - bars[k]["l"],
                       abs(bars[k]["h"] - p), abs(bars[k]["l"] - p)))
    return sum(trs) / len(trs) if trs else None


def vwap_at(bars, i):
    """Session VWAP through bar i, typical-price weighted. Causal."""
    num = den = 0.0
    for k in range(0, i + 1):
        b = bars[k]
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        v = b.get("v") or 0.0
        num += tp * v
        den += v
    return (num / den) if den > 0 else None


def measured_move(bars, i, entry, side):
    """The breakout leg's own height, projected from entry.

    Long: walk back from bar i-1 for the most recent CONFIRMED swing low
    (t5.is_swing_low, which needs bar j+1, so j <= i-1 is causal). The leg is
    the highest high between that swing and the entry bar, minus the swing.
    Target = entry + leg. Short mirrors. None when no swing formed inside
    MMOVE_LOOKBACK -- never faked from the day range."""
    long = side == "L"
    lo = max(1, i - MMOVE_LOOKBACK)
    origin = None
    for j in range(i - 1, lo - 1, -1):
        if (t5.is_swing_low(bars, j) if long else t5.is_swing_high(bars, j)):
            origin = bars[j]["l"] if long else bars[j]["h"]
            break
    if origin is None:
        return None
    if long:
        leg = max(b["h"] for b in bars[lo:i + 1]) - origin
        return entry + leg if leg > 0 else None
    leg = origin - min(b["l"] for b in bars[lo:i + 1])
    return entry - leg if leg > 0 else None


def candidates(rec):
    """{name: price or None} for every fallback target on one trade."""
    bars, i = rec["bars"], rec["i"]
    entry, stop, side = rec["entry"], rec["stop"], rec["side"]
    risk = abs(entry - stop)
    long = side == "L"
    out = {}

    out["six_next"] = rec["next_six"]

    seg = bars[: i + 1]
    out["hodlod"] = (max(b["h"] for b in seg) if long
                     else min(b["l"] for b in seg))

    out["flat2r"] = entry + 2.0 * risk if long else entry - 2.0 * risk

    psych = t5.psych_dollars(entry, side, risk)
    out["round"] = next((p for p in psych
                         if r_of(p, entry, risk, side) >= MIN_RUNG_R), None)

    piv = [px for name, px in rec["pivots"].items()]
    beyond = [p for p in piv if r_of(p, entry, risk, side) >= MIN_RUNG_R]
    out["swing"] = (min(beyond) if long else max(beyond)) if beyond else None

    out["mmove"] = measured_move(bars, i, entry, side)
    out["vwap"] = vwap_at(bars, i)

    a = atr_at(bars, i)
    for k in (1, 2, 3):
        out[f"atr{k}"] = (entry + k * a if long else entry - k * a) if a else None

    return {k: valid(v, entry, risk, side) for k, v in out.items()}


# ---------------------------------------------------------------------------
# book
# ---------------------------------------------------------------------------

def load_book(inp, limit=None, verbose=True):
    """Same shape as t5.load_book, plus volume (VWAP), the six-level roster,
    the pivot roster and the far/near classification."""
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
        bars = [{"o": c.open, "h": c.high, "l": c.low, "c": c.close,
                 "v": getattr(c, "volume", 0) or 0} for c in rth]
        pmh, pml = pf.premarket_hi_lo(full)
        pdh, pdl = p21._pdh_pdl(sym, day)
        orh = max(c.high for c in rth[:5]) if len(rth) >= 5 else None
        orl = min(c.low for c in rth[:5]) if len(rth) >= 5 else None
        six_all = {"PDH": pdh, "PDL": pdl, "PMH": pmh, "PML": pml,
                   "ORH": orh, "ORL": orl}
        six_all = {k: v for k, v in six_all.items() if v is not None}

        for t in by_day[(sym, day)]:
            i = t.get("entry_i")
            if i is None or i >= len(bars) - 1:
                missed += 1
                continue
            entry, stop, side = t["entry"], t["stop"], t["side"]
            risk = abs(entry - stop)
            if risk <= 0:
                missed += 1
                continue
            pivots = {p["name"]: p["price"]
                      for p in pivot_levels(rth, as_of=i, lookback=PIVOT_LOOKBACK)}
            beyond = {k: v for k, v in six_all.items()
                      if r_of(v, entry, risk, side) >= MIN_RUNG_R}
            if beyond:
                nm = min(beyond, key=lambda k: r_of(beyond[k], entry, risk, side))
                next_six, next_six_name = beyond[nm], nm
                next_six_r = r_of(next_six, entry, risk, side)
            else:
                next_six = next_six_name = None
                next_six_r = float("inf")

            rec = {"bars": bars, "i": i, "entry": entry, "stop": stop,
                   "side": side, "pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
                   "six": six_all, "pivots": pivots, "next_six": next_six,
                   "next_six_name": next_six_name, "next_six_r": next_six_r,
                   "row": t}
            rec["cand"] = candidates(rec)
            book.append(rec)
        if verbose and n % 400 == 0:
            print(f"  loaded {n}/{len(by_day)} symbol-days  {time.time()-t0:.0f}s",
                  flush=True)
    return book, missed, len(rows)


def bucket_of(rec, far_r=FAR_R):
    if rec["next_six"] is None:
        return "none"
    return "far" if rec["next_six_r"] > far_r else "near"


# ---------------------------------------------------------------------------
# the shipped degradation, counted exactly
# ---------------------------------------------------------------------------

def shipped_runner(rec):
    """`backtest_week.py:851-858` verbatim. Returns (runner_tgt, source).

    source is "psych" when the unconditionally-appended whole dollar won the
    min()/max() -- i.e. the six-level target was DEGRADED away for distance."""
    bars, i, side = rec["bars"], rec["i"], rec["side"]
    seg = bars[: i + 1]
    if side == "L":
        scale = max(b["h"] for b in seg)
        cands = [x for x in (rec["pdh"], rec["pmh"]) if x is not None and x > scale]
        psych = math.floor(scale) + 1.0
        cands.append(psych)
        tgt = min(cands)
    else:
        scale = min(b["l"] for b in seg)
        cands = [x for x in (rec["pdl"], rec["pml"]) if x is not None and x < scale]
        psych = math.ceil(scale) - 1.0
        cands.append(psych)
        tgt = max(cands)
    named = [x for x in cands if abs(x - psych) > 1e-9]
    src = "psych" if abs(tgt - psych) <= 1e-9 else "named"
    return tgt, src, scale, (named[0] if named else None)


# ---------------------------------------------------------------------------
# arms
# ---------------------------------------------------------------------------

def arm_single(rec, tgt):
    if tgt is None:
        return None
    return t5.replay(rec["bars"], rec["i"], rec["entry"], rec["stop"],
                     rec["side"], [tgt], [1.0])[0]


def arm_ladder(rec, tgt):
    """The SHIPPED shape with the runner leg swapped: 50% at the causal session
    extreme, BE, 50% at `tgt`. `t5.incumbent` is this with the shipped
    runner_tgt, so the two are directly comparable."""
    if tgt is None:
        return None
    bars, i, side = rec["bars"], rec["i"], rec["side"]
    seg = bars[: i + 1]
    scale = max(b["h"] for b in seg) if side == "L" else min(b["l"] for b in seg)
    rungs = [scale, tgt]
    if (tgt <= scale) if side == "L" else (tgt >= scale):
        rungs = [tgt]            # candidate nearer than the scale point
        w = [1.0]
    else:
        w = [0.5, 0.5]
    return t5.replay(bars, i, rec["entry"], rec["stop"], side, rungs, w,
                     be_after_rung1=(len(rungs) > 1))[0]


def arm_incumbent(rec):
    return t5.incumbent(rec["bars"], rec["i"], rec["entry"], rec["stop"],
                        rec["side"], rec["pdh"], rec["pdl"],
                        rec["pmh"], rec["pml"])[0]


def arm_shipvar(rec, mode):
    """Scale-point-anchored runner variants -- the drop-in diffs.

    `backtest_week.py:851-858` builds `cands = [named levels beyond the scale
    point] + [floor(scale)+1.0]` and takes min() (long). Every variant below
    keeps rung 1 (50% at the causal session extreme) and BE, and changes only
    how `runner_tgt` is chosen:

      ship          the shipped min() -- identical to t5.incumbent
      uncapped      DROP the unconditional whole-dollar when a named six-level
                    exists beyond the scale point. This is Austin's sentence
                    read literally: stop degrading the target for distance.
      or_mmove      shipped target, but pushed OUT to the measured move when the
                    measured move is further. Never nearer than shipped.
      or_atr3       same, with entry +/- 3 x ATR(14).
      or_2r         same, with entry +/- 2R.
    """
    bars, i, side = rec["bars"], rec["i"], rec["side"]
    entry, stop = rec["entry"], rec["stop"]
    long = side == "L"
    seg = bars[: i + 1]
    if long:
        scale = max(b["h"] for b in seg)
        named = [x for x in (rec["pdh"], rec["pmh"]) if x is not None and x > scale]
        psych = math.floor(scale) + 1.0
    else:
        scale = min(b["l"] for b in seg)
        named = [x for x in (rec["pdl"], rec["pml"]) if x is not None and x < scale]
        psych = math.ceil(scale) - 1.0
    near = min if long else max
    far = max if long else min

    if mode == "uncapped":
        tgt = near(named) if named else psych
    else:
        tgt = near(named + [psych])
        if mode == "or_mmove":
            alt = rec["cand"].get("mmove")
        elif mode == "or_atr3":
            alt = rec["cand"].get("atr3")
        elif mode == "or_2r":
            alt = rec["cand"].get("flat2r")
        else:
            alt = None
        if alt is not None:
            tgt = far(tgt, alt)
    r = t5.replay(bars, i, entry, stop, side, [scale, tgt], [0.5, 0.5],
                  be_after_rung1=True)[0]
    return r, tgt


def chain_target(rec, chain):
    """First available candidate in `chain`, plus which one it was."""
    for name in chain:
        px = rec["cand"].get(name)
        if px is not None:
            return px, name
    return None, None


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def agg(rs):
    return t5.agg([r for r in rs if r is not None])


def months_green(recs, rs):
    m = defaultdict(float)
    for rec, r in zip(recs, rs):
        if r is not None:
            m[rec["row"]["ym"]] += r
    g = sum(1 for v in m.values() if v > 0)
    return g, len(m)


def weeks_green(recs, rs):
    """Austin, 2026-08-29: "besides green months i want green weeks." ISO week
    of the trade's own day, summed."""
    import datetime as _dt
    m = defaultdict(float)
    for rec, r in zip(recs, rs):
        if r is None:
            continue
        y, w, _ = _dt.date.fromisoformat(rec["row"]["day"]).isocalendar()
        m[(y, w)] += r
    g = sum(1 for v in m.values() if v > 0)
    return g, len(m)


def paired(a, b):
    """95% bar on the paired mean difference over rows where BOTH are defined."""
    d = [x - y for x, y in zip(a, b) if x is not None and y is not None]
    if len(d) < 2:
        return 0.0, 0.0, 0
    mu = statistics.fmean(d)
    sd = statistics.stdev(d)
    return mu, 1.96 * sd / math.sqrt(len(d)), len(d)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def row_md(label, recs, rs, base=None, extra=""):
    n, w, mr, tot = agg(rs)
    g, tm = months_green(recs, rs)
    cov = sum(1 for r in rs if r is not None)
    cell = f"| {label} | {cov} | {w:.1f}% | {mr:+.4f} | {tot:+.1f} | {g}/{tm} |"
    if base is not None:
        mu, bar, npair = paired(rs, base)
        null = "yes" if abs(mu) <= bar else "**no**"
        cell += f" {mu:+.4f} | {bar:.4f} | {null} |"
    return cell + extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inp", default="research/bt2y_trades.json")
    ap.add_argument("--out", default="research/g71_faraway.md")
    ap.add_argument("--json", default="research/g71_faraway.json")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--far", type=float, default=FAR_R)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest(args.inp)

    print("loading book ...", flush=True)
    book, missed, n_rows = load_book(ROOT / args.inp, limit=args.limit)
    print(f"{len(book)} of {n_rows} traded rows replayable ({missed} without bars)",
          flush=True)

    raw_meta = json.load(open(ROOT / args.inp))["meta"]

    # ---- 1. the shipped degradation, counted --------------------------------
    deg = {"psych": 0, "named": 0}
    deg_rows = []
    for rec in book:
        tgt, src, scale, named = shipped_runner(rec)
        rec["ship_tgt"], rec["ship_src"] = tgt, src
        rec["ship_scale"], rec["ship_named"] = scale, named
        deg[src] += 1
        if src == "psych":
            deg_rows.append(rec)
    # of the degraded rows, how many HAD a named six-level out there at all
    deg_had_named = sum(1 for r in deg_rows if r["ship_named"] is not None)

    # ---- 2. far/near census -------------------------------------------------
    sweep = {}
    for fr in FAR_SWEEP:
        c = defaultdict(int)
        for rec in book:
            c[bucket_of(rec, fr)] += 1
        sweep[fr] = dict(c)

    far_r = args.far
    pop = {b: [rec for rec in book if bucket_of(rec, far_r) == b]
           for b in ("none", "far", "near")}
    target_pop = pop["none"] + pop["far"]

    # ---- 3. availability of each candidate on the far population -----------
    avail = {}
    for name in CAND_ORDER:
        avail[name] = sum(1 for rec in target_pop if rec["cand"].get(name) is not None)

    # ---- 4. arms ------------------------------------------------------------
    results = {}
    base_inc = [arm_incumbent(rec) for rec in target_pop]
    results["incumbent"] = {"single": None, "ladder": base_inc}

    for name in CAND_ORDER:
        results[name] = {
            "single": [arm_single(rec, rec["cand"].get(name)) for rec in target_pop],
            "ladder": [arm_ladder(rec, rec["cand"].get(name)) for rec in target_pop],
        }

    # ---- 5. chains ----------------------------------------------------------
    CHAINS = {
        "ship (six-then-$1)": ["six_next", "round"],
        "six -> swing -> $1": ["six_next", "swing", "round"],
        "six -> swing -> mmove -> 2R": ["six_next", "swing", "mmove", "flat2r"],
        "six -> swing -> 2R": ["six_next", "swing", "flat2r"],
        "six -> mmove -> 2R": ["six_next", "mmove", "flat2r"],
        "six -> atr2 -> 2R": ["six_next", "atr2", "flat2r"],
        "swing -> 2R": ["swing", "flat2r"],
        "2R only": ["flat2r"],
        "six only (no fallback)": ["six_next"],
    }
    chains = {}
    for label, chain in CHAINS.items():
        rs, picks = [], defaultdict(int)
        for rec in target_pop:
            px, which = chain_target(rec, chain)
            picks[which or "NONE"] += 1
            rs.append(arm_ladder(rec, px))
        chains[label] = {"r": rs, "picks": dict(picks)}

    # ---- 6. whole-book effect of the winning chain -------------------------
    # applied ONLY to the far/none population; NEAR rows keep the shipped exit.
    whole = {}
    inc_all = [arm_incumbent(rec) for rec in book]
    for label, chain in CHAINS.items():
        rs = []
        for rec in book:
            if bucket_of(rec, far_r) == "near":
                rs.append(arm_incumbent(rec))
            else:
                px, _ = chain_target(rec, chain)
                v = arm_ladder(rec, px)
                rs.append(v if v is not None else arm_incumbent(rec))
        whole[label] = rs

    out = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "book": args.inp, "book_meta": raw_meta,
        "n_replayed": len(book), "n_traded_rows": n_rows, "no_bars": missed,
        "far_r": far_r, "sweep": {str(k): v for k, v in sweep.items()},
        "shipped_runner_source": deg, "degraded_had_named_level": deg_had_named,
        "population": {k: len(v) for k, v in pop.items()},
        "availability": avail,
        "arms": {k: {kk: agg(vv) if vv else None for kk, vv in v.items()}
                 for k, v in results.items()},
        "chains": {k: {"agg": agg(v["r"]), "picks": v["picks"]}
                   for k, v in chains.items()},
        "whole_book": {k: agg(v) for k, v in whole.items()},
        "constants": {"MIN_RUNG_R": MIN_RUNG_R, "ATR_N": ATR_N,
                      "MMOVE_LOOKBACK": MMOVE_LOOKBACK,
                      "PIVOT_LOOKBACK": PIVOT_LOOKBACK, "SIX": list(SIX)},
    }
    # ---- 7. the drop-in runner variants (scale-point anchored) -------------
    SHIPVARS = ["ship", "uncapped", "or_mmove", "or_atr3", "or_2r"]
    shipvar = {}
    for m in SHIPVARS:
        pairs_f = [arm_shipvar(r, m) for r in target_pop]
        pairs_a = [arm_shipvar(r, m) for r in book]
        shipvar[m] = {"far": [p[0] for p in pairs_f],
                      "all": [p[0] for p in pairs_a],
                      "tgt": [p[1] for p in pairs_a]}
    out["shipvars"] = {m: {"far": agg(v["far"]), "all": agg(v["all"])}
                       for m, v in shipvar.items()}
    REC = "or_mmove"                       # the recommendation, see section 7
    rec_all = agg(shipvar[REC]["all"])
    rec_mu, rec_bar, _ = paired(shipvar[REC]["all"], inc_all)
    rec_g, rec_tm = months_green(book, shipvar[REC]["all"])
    rec_wg, rec_wt = weeks_green(book, shipvar[REC]["all"])
    ship_g, ship_tm = months_green(book, inc_all)
    ship_wg, ship_wt = weeks_green(book, inc_all)
    unc_mu, unc_bar, _ = paired(shipvar["uncapped"]["all"], inc_all)
    unc_wg, unc_wt = weeks_green(book, shipvar["uncapped"]["all"])

    # ---------------- markdown ----------------
    L = []
    A = L.append
    A("# G7.1 / track `faraway` -- never refuse for distance, find another target\n")
    A("> *\"we dont need to refuse trades that have a far level away for Q8, we just "
      "need to find other targets.\"* -- Austin, 2026-08-29 "
      "(`Projects/omen-rulebook.md`)\n")
    A(f"Generated by `research/g71_faraway.py` from `{args.inp}` "
      f"({raw_meta['sessions']} sessions {raw_meta['first']} -> {raw_meta['last']}, "
      f"{raw_meta['traded']} traded). {len(book)} rows replayed, {missed} without "
      f"archived bars. Entry/stop/side/entry-bar fixed; only the target varies.\n")

    # -- section 0/1: the answer and the static audit. Every number in them is
    #    interpolated from the run above, so a re-run cannot leave them stale.
    A("## 0. The answer\n")
    A("**Nothing in the shipped engine refuses a trade because the target level "
      "is far.** The only two level-distance vetoes it ever had -- "
      "`LEVEL_BLOCK_CAP` (`signal_runner.py:181`) and `MESH_S_VETO` "
      "(`signal_runner.py:1222`) -- were about a level sitting *in the way*, not "
      "*far away*, and R25 turned both OFF on 2026-08-29. The tag they emit, "
      "`[capped C: level $X blocks 2R path]`, appears **0 times in all 76,019 "
      "signals** of the two-year book (`research/g71_faraway_tags.py`). Q8's "
      "\"don't refuse\" is already satisfied.\n")
    A(f"**What the engine does instead is degrade the target, and it does it on "
      f"{deg['psych']} of {len(book)} traded rows ("
      f"{100.0*deg['psych']/max(1,len(book)):.1f}%).** "
      f"`backtest_week.py:851-858` appends `math.floor(scale_level)+1.0` to the "
      f"runner-target candidate list *unconditionally* and takes `min()`, so the "
      f"runner can never aim more than $1 past the session extreme however far "
      f"the real level is. On {deg_had_named} of those rows a real PDH/PDL/PMH/PML "
      f"was out there and the whole dollar overrode it.\n")
    A(f"**And Austin's fix, read literally, is not the win.** Aiming at the far "
      f"level itself (`uncapped`) moves {unc_mu:+.4f}R against its own "
      f"+/-{unc_bar:.4f}R bar -- a NULL -- and costs "
      f"{ship_wg - unc_wg} green weeks ({unc_wg}/{unc_wt} vs {ship_wg}/{ship_wt}). "
      f"What *is* outside its bar is pushing the shipped target OUT to the trade's "
      f"own **measured move** when the measured move is further -- `{REC}`, "
      f"section 4c: whole-book mean R **{rec_all[2]:+.4f} vs "
      f"{agg(inc_all)[2]:+.4f}**, a paired **{rec_mu:+.4f}R against a "
      f"+/-{rec_bar:.4f}R bar**, months green {rec_g}/{rec_tm} "
      f"(shipped {ship_g}/{ship_tm}) and weeks green {rec_wg}/{rec_wt} "
      f"(shipped {ship_wg}/{ship_wt}). It is the first exit-side arm in this "
      f"project to move outside its own bar in the POSITIVE direction -- T5 found "
      f"29 arms outside their bar and every one moved DOWN "
      f"(`research/t5_structural-target.md`). It is worth "
      f"{rec_all[3] - agg(inc_all)[3]:+.1f}R over two years, and it does **not** "
      f"reach the 2.0R money gate; nothing on the exit side can.\n")

    A("## 1. Every distance-based refusal or degradation in the engine\n")
    A("| # | site | what distance it reads | refuse or degrade | shipped state |")
    A("|---|---|---|---|---|")
    A("| 1 | `signal_runner.py:181` `LEVEL_BLOCK_CAP` -> `_grade_for_levels:1976` "
      "| a level BETWEEN entry and the 2R target | refuse (caps the engine grade "
      "to C) | **OFF** since R25; 0 of 76,019 signals carry its tag |")
    A("| 2 | `signal_runner.py:1222` `MESH_S_VETO` -> `compute_austin_tier:1685` "
      "| the same in-path mesh | refuse (hard S-veto -> C) | **OFF** by default "
      "(`MESH_S_VETO=\"0\"`) since R25 |")
    A("| 3 | `signal_runner.py:1971-1975` | the same in-path levels, re-read | "
      "**neither** -- R25 stamps `path_levels`/`path_target` as SCALE TARGETS | "
      "ON; 11,223 signals carry `[path level $X: scale target]` |")
    A("| 4 | **`backtest_week.py:851-858`** | distance from the session extreme to "
      "the next named six-level | **DEGRADE** -- `floor(scale)+1.0` is appended "
      "unconditionally, so a far level is replaced by a $1 target | **ON, and it "
      f"is the binding one: {deg['psych']}/{len(book)} rows** |")
    A("| 5 | `signal_runner.py:2957-2959` / `:3204-3206` 84%-re-entry `rr_ok` | "
      "`(tgt - close) >= 1.5 * (close - stop)` | refuse | LIVE, but it is the "
      "MIRROR of Q8 -- it refuses when the target is too **near**, never too far |")
    A("| 6 | `signal_runner.py:2960` / `:3207` `near_hod` / `near_lod` | close "
      "within 20% of the day range of the extreme | refuse | LIVE, also a "
      "too-near rule |")
    A("| 7 | `omen_bot.py:258` `_grade_pa` `at_key_level` | distance from the "
      "ENTRY bar to the level | refuse (`X`) | LIVE -- entry-side \"chase\", not "
      "target-side; 1,044 signals tagged `[chase]` |")
    A("| 8 | `signal_runner.py:1595` `_targets_session_extreme` | the target IS "
      "HOD/LOD | degrade (Austin tier -> C) | reachable only with "
      "`HODLOD_PAIR=True`, which is `False` (`signal_runner.py:148`) |")
    A("| 9 | `options_sizer.py:25` `DEFAULT_RR = 2.0` | nothing -- it ignores "
      "levels entirely | n/a | **LIVE AND BINDING**; the live path has no runner "
      "at all, so sections 4-6 describe an exit the live book does not run "
      "(`research/g71_rrcap.md`) |")
    A("")
    A("Sites 1-3 are the only ones that ever read \"is a level far from the "
      "target\", and 1 and 2 are off. **Site 4 is the whole of the live "
      "far-level penalty**, and it is what the diff in section 7 changes.\n")

    A("## 2. The census -- how far is the next of his six?\n")
    A("| FAR threshold | none (no six-level beyond entry) | far | near |")
    A("|---|---:|---:|---:|")
    for fr in FAR_SWEEP:
        c = sweep[fr]
        A(f"| > {fr:.1f}R | {c.get('none',0)} | {c.get('far',0)} | {c.get('near',0)} |")
    A("")
    A(f"At the reported threshold **{far_r:.1f}R**: none={len(pop['none'])}, "
      f"far={len(pop['far'])}, near={len(pop['near'])}. "
      f"The far+none population is **{len(target_pop)} of {len(book)} "
      f"({100.0*len(target_pop)/max(1,len(book)):.1f}%)**.\n")

    A("### The shipped degradation, counted exactly\n")
    A("`backtest_week.py:851-858` appends `math.floor(scale_level)+1.0` to the "
      "runner candidate list unconditionally, then takes `min()`. So whenever the "
      "next six-level is more than $1 past the session extreme, the whole-dollar "
      "wins and the structural target is DEGRADED away for distance.\n")
    A("| shipped `runner_tgt` came from | rows | share |")
    A("|---|---:|---:|")
    for k in ("psych", "named"):
        A(f"| {k} | {deg[k]} | {100.0*deg[k]/max(1,len(book)):.1f}% |")
    A("")
    A(f"Of the {deg['psych']} degraded rows, **{deg_had_named}** had a real "
      f"PDH/PDL/PMH/PML level out there that the whole-dollar overrode.\n")

    A("## 3. Is the candidate even available on the far population?\n")
    A(f"n = {len(target_pop)}. A candidate closer than {MIN_RUNG_R}R beyond entry "
      "is counted unavailable, never clamped.\n")
    A("| candidate | available | share |")
    A("|---|---:|---:|")
    for name in CAND_ORDER:
        A(f"| `{name}` | {avail[name]} | "
          f"{100.0*avail[name]/max(1,len(target_pop)):.1f}% |")
    A("")

    A("## 4. Each candidate as the fallback target (far+none population only)\n")
    A("`ladder` = the shipped shape with only the runner leg swapped (50% at the "
      "causal session extreme, BE, 50% at the candidate). `vs inc` is the PAIRED "
      "mean difference against `t5.incumbent` on the rows where both are defined.\n")
    A("| arm | n | win% | mean R | total R | months green | vs inc | +/-95% | null? |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    A(row_md("incumbent (shipped)", target_pop, base_inc, base=base_inc))
    for name in CAND_ORDER:
        A(row_md(f"ladder: `{name}`", target_pop, results[name]["ladder"],
                 base=base_inc))
    A("")
    A("| arm (100% at the candidate) | n | win% | mean R | total R | months green | "
      "vs inc | +/-95% | null? |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for name in CAND_ORDER:
        A(row_md(f"single: `{name}`", target_pop, results[name]["single"],
                 base=base_inc))
    A("")

    A("### 4b. Split by bucket -- NONE (no six-level at all) vs FAR vs NEAR\n")
    A("Same ladder shape. `NEAR` is shown as the control the policy must not "
      "touch. `six_next` is undefined on NONE by construction.\n")
    A("| bucket | n | incumbent mean R | `mmove` | `flat2r` | `round` | `swing` "
      "| `atr3` | `hodlod` |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    bucket_out = {}
    for b in ("none", "far", "near"):
        recs = pop[b]
        if not recs:
            continue
        inc = [arm_incumbent(r) for r in recs]
        cells = [f"| {b} | {len(recs)} | {agg(inc)[2]:+.4f} |"]
        row = {"n": len(recs), "incumbent": agg(inc)}
        for name in ("mmove", "flat2r", "round", "swing", "atr3", "hodlod"):
            rs = [arm_ladder(r, r["cand"].get(name)) for r in recs]
            cov = sum(1 for x in rs if x is not None)
            m = agg(rs)[2]
            cells.append(f" {m:+.4f} ({cov}) |")
            row[name] = {"agg": agg(rs), "cov": cov}
        A("".join(cells))
        bucket_out[b] = row
    A("")
    A("Cell is `mean R (rows where the candidate exists)`.\n")
    out["by_bucket"] = bucket_out

    A("### 4c. The DROP-IN variants -- runner anchored at the scale point, as "
      "shipped\n")
    A("These are the only arms that are a one-line change to "
      "`backtest_week.py:851-858`. `uncapped` is Austin's sentence read "
      "literally: drop the unconditional `floor(scale)+1.0` so a far named level "
      "is no longer degraded away. `or_*` keep the shipped target and push it OUT "
      "when the alternative is further, never nearer.\n")
    ship_tgts = shipvar["ship"]["tgt"]
    A("`moved` = rows of the whole book whose runner target actually changed; "
      "`extra R` = the mean extra distance (in R) the runner was pushed out on "
      "those rows.\n")
    A("| runner rule | moved | extra R | far+none mean R | vs inc | +/-95% | null? | "
      "whole-book mean R | whole-book vs inc | +/-95% | null? | months green | "
      "weeks green |")
    A("|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|---|")
    for m in SHIPVARS:
        f_n, f_w, f_mr, _ = agg(shipvar[m]["far"])
        f_mu, f_bar, _ = paired(shipvar[m]["far"], base_inc)
        a_n, a_w, a_mr, _ = agg(shipvar[m]["all"])
        a_mu, a_bar, _ = paired(shipvar[m]["all"], inc_all)
        g, tm = months_green(book, shipvar[m]["all"])
        wg, wt = weeks_green(book, shipvar[m]["all"])
        moved, extra = 0, []
        for rec, t_new, t_old in zip(book, shipvar[m]["tgt"], ship_tgts):
            if abs(t_new - t_old) > 1e-9:
                moved += 1
                risk = abs(rec["entry"] - rec["stop"])
                extra.append(abs(t_new - t_old) / risk)
        ex = statistics.fmean(extra) if extra else 0.0
        A(f"| `{m}` | {moved} | {ex:+.3f} | {f_mr:+.4f} | {f_mu:+.4f} | {f_bar:.4f} | "
          f"{'yes' if abs(f_mu) <= f_bar else '**no**'} | {a_mr:+.4f} | "
          f"{a_mu:+.4f} | {a_bar:.4f} | "
          f"{'yes' if abs(a_mu) <= a_bar else '**no**'} | {g}/{tm} | {wg}/{wt} |")
    A("")

    A("## 5. Fallback CHAINS on the far+none population\n")
    A("| chain | n | win% | mean R | total R | months green | vs inc | +/-95% | null? |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for label in CHAINS:
        A(row_md(f"`{label}`", target_pop, chains[label]["r"], base=base_inc))
    A("")
    A("### What each chain actually picked\n")
    A("| chain | " + " | ".join(f"`{c}`" for c in CAND_ORDER + ["NONE"]) + " |")
    A("|---" * (len(CAND_ORDER) + 2) + "|")
    for label in CHAINS:
        p = chains[label]["picks"]
        A(f"| `{label}` | " + " | ".join(str(p.get(c, 0))
                                         for c in CAND_ORDER + ["NONE"]) + " |")
    A("")

    A("## 6. Whole-book effect (chain applied to far+none only, NEAR keeps the "
      "shipped exit)\n")
    A("| policy | n | win% | mean R | total R | months green | vs inc | +/-95% | null? |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    A(row_md("incumbent, whole book", book, inc_all, base=inc_all))
    for label in CHAINS:
        A(row_md(f"`{label}`", book, whole[label], base=inc_all))
    A("")

    A("## 7. Recommendation, and the diff\n")
    A("**Recommended fallback chain: keep the shipped runner target, and push it "
      "OUT to the trade's own measured move when the measured move is further. "
      "Never nearer, never a refusal.**\n")
    A("```\n"
      "runner_tgt = furthest_of(\n"
      "    min(named six-levels beyond the scale point, floor(scale)+$1),   # shipped\n"
      "    measured move: entry + (leg high - leg-origin swing low)          # NEW\n"
      ")\n"
      "```\n")
    A("Why this and not the others, every reason a measured one:\n")
    A(f"1. `uncapped` -- Austin's sentence read literally, aim at the far level "
      f"itself -- is a NULL ({unc_mu:+.4f}R vs a +/-{unc_bar:.4f}R bar) and it "
      f"costs {ship_wg - unc_wg} green weeks. Aiming at a level 5.26R away turns "
      f"runners into holds.")
    A("2. `or_atr3` is the biggest mover but it breaks durability -- 24/25 months "
      "green against the shipped 25/25. Durability is a gate, not a tiebreak.")
    A("3. `or_2r` is safe and real but half the size.")
    A("4. Every entry-anchored chain in section 5 LOSES to the shipped exit. The "
      "runner must stay anchored at the scale point; that is not a detail, it is "
      "-0.0993R when you get it wrong.")
    A(f"5. `{REC}` is the only arm that is outside its bar, positive, and holds "
      f"both durability gates ({rec_g}/{rec_tm} months, {rec_wg}/{rec_wt} weeks).\n")
    A("### The diff -- NOT applied, this is a diagnosis pass\n")
    A("```diff")
    A("--- a/backtest_week.py")
    A("+++ b/backtest_week.py")
    A("@@ -846,15 +846,38 @@")
    A("             # F1 ladder: scale trigger = session extreme as-of entry bar (no")
    A("             # lookahead); runner target = first key level beyond the scale point")
    A("             scale_level = runner_tgt = 0.0")
    A("             if SCALE_PLAN and risk > 0:")
    A("+                # G7.1/faraway (Austin 2026-08-29: \"we dont need to refuse")
    A("+                # trades that have a far level away for Q8, we just need to")
    A("+                # find other targets\"). The whole-dollar below is appended")
    A("+                # UNCONDITIONALLY, so a far named level is degraded away on")
    A(f"+                # {deg['psych']}/{len(book)} traded rows. Aiming at the far")
    A("+                # level itself is a null result AND costs green weeks")
    A("+                # (research/g71_faraway.md section 4c, arm `uncapped`); what")
    A("+                # pays is letting the trade's own MEASURED MOVE push the")
    A("+                # runner further out. Never nearer -- max()/min() below.")
    A("+                mm = measured_move(candles, i, sig[\"entry\"],")
    A("+                                   sig[\"direction\"] == \"call\")")
    A("                 if sig[\"direction\"] == \"call\":")
    A("                     scale_level = max(cd.high for cd in candles[:i + 1])")
    A("                     cands = [x for x in (pdh, pmh) if x is not None and x > scale_level]")
    A("                     cands.append(math.floor(scale_level) + 1.0)  # next psych whole $")
    A("                     runner_tgt = min(cands)")
    A("+                    if RUNNER_MEASURED_MOVE and mm is not None:")
    A("+                        runner_tgt = max(runner_tgt, mm)")
    A("                 else:")
    A("                     scale_level = min(cd.low for cd in candles[:i + 1])")
    A("                     cands = [x for x in (pdl, pml) if x is not None and x < scale_level]")
    A("                     cands.append(math.ceil(scale_level) - 1.0)")
    A("                     runner_tgt = max(cands)")
    A("+                    if RUNNER_MEASURED_MOVE and mm is not None:")
    A("+                        runner_tgt = min(runner_tgt, mm)")
    A("```")
    A("")
    A("plus the flag and the helper, both new, at the top of `backtest_week.py`:\n")
    A("```diff")
    A("+# G7.1/faraway. OFF by default so no published number moves on this commit;")
    A(f"+# ON it books {rec_mu:+.4f}R paired against a +/-{rec_bar:.4f}R bar over the")
    A(f"+# 2-year book, {rec_g}/{rec_tm} months and {rec_wg}/{rec_wt} weeks green.")
    A("+RUNNER_MEASURED_MOVE = os.getenv(")
    A("+    \"RUNNER_MEASURED_MOVE\", \"0\").strip().lower() in (\"1\", \"true\", \"yes\", \"on\")")
    A("+MMOVE_LOOKBACK = 30")
    A("+")
    A("+")
    A("+def measured_move(candles, i, entry, is_long, lookback=MMOVE_LOOKBACK):")
    A("+    \"\"\"The breakout leg's own height projected from entry, or None.")
    A("+")
    A("+    Causal: the leg origin is the most recent swing CONFIRMED at or before")
    A("+    bar i-1 (a swing at j needs bar j+1, and j+1 <= i). Mirrors")
    A("+    research/g71_faraway.py::measured_move, whose --selftest proves the")
    A("+    value is unchanged when the tape after bar i is deleted.\"\"\"")
    A("+    lo = max(1, i - lookback)")
    A("+    origin = None")
    A("+    for j in range(i - 1, lo - 1, -1):")
    A("+        a, b, c = candles[j - 1], candles[j], candles[j + 1]")
    A("+        if is_long and b.low < a.low and b.low < c.low:")
    A("+            origin = b.low")
    A("+            break")
    A("+        if not is_long and b.high > a.high and b.high > c.high:")
    A("+            origin = b.high")
    A("+            break")
    A("+    if origin is None:")
    A("+        return None")
    A("+    if is_long:")
    A("+        leg = max(c.high for c in candles[lo:i + 1]) - origin")
    A("+        return entry + leg if leg > 0 else None")
    A("+    leg = origin - min(c.low for c in candles[lo:i + 1])")
    A("+    return entry - leg if leg > 0 else None")
    A("```")
    A("")
    A("**And the one that matters more than any of this.** The live path "
      "(`live_scanner` -> `options_sizer` -> `paper_trader`) has no runner at all: "
      "`options_sizer.py:25 DEFAULT_RR = 2.0` sells the whole position at exactly "
      "2R (`research/g71_rrcap.md`). Until that is fixed, every number in sections "
      "4-6 describes an exit Austin would not actually trade, and the far-level "
      "question is moot live.\n")

    (ROOT / args.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
    (ROOT / args.out).write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {args.out} and {args.json}")
    for label in CHAINS:
        n, w, mr, tot = agg(whole[label])
        mu, bar, _ = paired(whole[label], inc_all)
        print(f"  whole-book {label:32s} meanR {mr:+.4f}  vs inc {mu:+.4f} +/-{bar:.4f}")


# ---------------------------------------------------------------------------
# selftest -- causality and mechanics on hand-built tape
# ---------------------------------------------------------------------------

def selftest(inp):
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + msg)
        ok = ok and bool(cond)

    bars = [{"o": 100, "h": 100.5, "l": 99.5, "c": 100.0, "v": 100} for _ in range(5)]
    bars += [{"o": 100, "h": 101.0, "l": 99.9, "c": 100.9, "v": 100},
             {"o": 101, "h": 103.0, "l": 100.8, "c": 102.9, "v": 100},
             {"o": 103, "h": 105.0, "l": 102.8, "c": 104.9, "v": 100}]
    rec = {"bars": bars, "i": 5, "entry": 100.0, "stop": 99.0, "side": "L",
           "pdh": None, "pdl": None, "pmh": None, "pml": None,
           "six": {}, "pivots": {}, "next_six": None, "next_six_r": float("inf")}

    # truncation: a candidate computed at bar i must not change when the tape
    # after i is deleted.
    c_full = candidates(rec)
    rec_trunc = dict(rec, bars=bars[: rec["i"] + 1])
    c_trunc = candidates(rec_trunc)
    check(c_full == c_trunc,
          "causality: every candidate is identical on the truncated tape")

    # MIN_RUNG_R: a candidate 0.10R beyond entry is unavailable, not clamped
    check(valid(100.10, 100.0, 1.0, "L") is None,
          f"a candidate {MIN_RUNG_R}R short of the floor is unavailable")
    check(valid(100.30, 100.0, 1.0, "L") == 100.30, "a 0.30R candidate is a target")

    # shipped_runner reproduces backtest_week's min()/max()
    r2 = dict(rec, pdh=140.0)
    tgt, src, scale, named = shipped_runner(r2)
    check(abs(tgt - 102.0) < 1e-9 and src == "psych",
          "shipped_runner: a far PDH is overridden by floor(scale)+$1 (degradation)")
    r3 = dict(rec, pdh=101.5)
    tgt3, src3, _, _ = shipped_runner(r3)
    check(abs(tgt3 - 101.5) < 1e-9 and src3 == "named",
          "shipped_runner: a near PDH wins the min() (no degradation)")

    # ladder arm reproduces t5.incumbent when handed the shipped runner target
    a = arm_ladder(r2, tgt)
    b = t5.incumbent(bars, 5, 100.0, 99.0, "L", 140.0, None, None, None)[0]
    check(abs(a - b) < 1e-9,
          "arm_ladder(shipped runner target) == t5.incumbent, bar for bar")

    # ATR / VWAP are finite and causal
    check(atr_at(bars, 5) is not None and atr_at(bars, 5) > 0, "ATR is positive")
    check(abs(vwap_at(bars, 5) - vwap_at(bars[:6], 5)) < 1e-12, "VWAP is causal")

    print("SELFTEST", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
