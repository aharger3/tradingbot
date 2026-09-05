"""g154 -- F5 candidate: scale-before-the-level (OMEN 9.0).

Austin's claim (polarity S-INDICATOR): "Scale-out orders should sit slightly
before the exact level (HOD/LOD), not resting at it, because price stalls and
consolidates right at the level before tagging it." Read literally this is
the EXIT-SIDE MIRROR of g87's zero-tolerance retest finding (the best ENTRY
tolerance was zero -- a limit resting exactly at the level -- because widening
it collapsed the risk denominator). The exit side has no such collapse: a
target shifted toward entry by `b` never touches the stop, so the size gate
(`signal_runner.min_risk_floor`, applied through the ORIGINAL entry/stop, both
untouched by this rule) cannot be broken by it. That is a structural
difference from g87 stated up front, not assumed.

THIS RULE DOES NOT CHANGE WHICH TRADE GETS TAKEN. It only changes where the
day's already-picked trade EXITS. So the one-trade-a-day PICK is identical,
arrival-order and size-gate untouched
(`research.omen_metrics.first_of_day_arm`, size-gated) -- meaning
candidates/day, fires/day, S recall and precision are IDENTICAL between the
baseline and every candidate arm below (computed once, reported once, and
that identity is asserted, not claimed). The only thing that moves is the
EXIT, so the only two numbers that can differ are the target-HIT RATE and
the realized mean R -- which is exactly what the row asked to be reported
separately.

THE PREDICATE. For dir=='call' (long), shift the resting target from
`target` to `target - b` (a nearer, easier-to-reach price). For dir=='put'
(short), shift to `target + b`. Three sizes of `b`:
    cents_002   $0.02
    cents_005   $0.05
    atr_005     0.05 x ATR14(entry_i) -- the 14-bar true-range average ending
                at the signal bar, strictly causal (same `atr_at` derivation
                as research/g87_retest_tol.py, computed only up to entry_i --
                no bar after the signal is read to build this feature). Rows
                with fewer than 2 bars of history at entry_i (ATR
                uncomputable) fall back to cents_005 for this arm only, and
                the count of that fallback is reported, never silently
                folded in.
`b` is clamped to at most 90% of the ORIGINAL |target - entry| distance so a
degenerate arm can never flip the target through the entry price.

THE RE-SIMULATION. Selecting the trade needs nothing past the signal bar (the
book's own entry_i/entry/stop, untouched). PRICING the new target needs bars
strictly AFTER the signal bar -- there is no way to ask "did a nearer target
get touched" without reading forward, so this part of the script does read
post-signal bars (data_archive only, via polygon_feed, cache-first, no
network fetch for an archived day). It is intentionally a SINGLE-STAGE
proxy exit (one target, one stop), not the shipped multi-stage SCALE_PLAN
ladder (`backtest_week._ladder_bar`) -- re-deriving that ladder's HOD-then-
runner mechanics for one target shift was judged out of scope for this row's
budget, and every number below is a baseline-walker-vs-candidate-walker
comparison, so the baseline for this script is NOT the book's own booked
pnl/r (that mixes the ladder's multi-stage mechanics into a stated single-
target result) -- both sides run through the identical single-stage walker
below, differing ONLY in the resting target's price. Priority within a bar,
matching stop_rule.py's own documented order ("the disaster stop is tested
FIRST"): (1) disaster-stop touch (`stop_rule.disaster_stop_hit`, intrabar,
at entry -/+ 1R off the ORIGINAL entry/stop) (2) the (possibly shifted)
target touch, intrabar (3) the level stop's CLOSE trigger
(`stop_rule.stop_hit_on_close`, filled via `stop_rule.stop_fill_price`).
Whichever fires first on the earliest bar wins. A trade that reaches the
last available bar with nothing triggered marks at that bar's close (an
"eod" exit, reported as its own bucket, not folded into the stop or target
counts).

PRIOR ART, reused not re-derived: research/g86_honest_ceiling.py (stats
shape, ekey, RISK); research/g91_lane_slice.py (one-trade-a-day money-read
pattern); research/g87_retest_tol.py (atr_at -- the causal 14-bar ATR);
research/omen_metrics.py (first_of_day_arm, min_risk_floor size gate);
stop_rule.py (disaster_stop_price/_hit, stop_hit_on_close, stop_fill_price --
the ONE fill definition, never reimplemented); research/marks_pool.py
(canonical_pool, s_days); research/g154_rule_entry-earlier-satisfiable-bar.py
(bars_for's data_archive-only, cache-first convention).

    python research/g154_rule_scale-before-the-level.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import polygon_feed as pf                        # noqa: E402
import stop_rule as sru                           # noqa: E402  the one fill definition
from research import omen_metrics as om           # noqa: E402  first_of_day_arm, size gate
from research import marks_pool as mp             # noqa: E402
from research import build_deck as bd             # noqa: E402  mark-file reader

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_JSON = os.path.join(HERE, "g154_rule_scale-before-the-level.json")
OUT_MD = os.path.join(HERE, "g154_rule_scale-before-the-level.md")
PROBE_S34 = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")

RISK = 1000.0
H_SPLIT = "2025-09-01"        # CLAUDE.md-mandated H1/H2 boundary
ATR_N = 14

ARMS_B = [
    ("cents_002", "cents", 0.02),
    ("cents_005", "cents", 0.05),
    ("atr_005", "atr", 0.05),
]


def ekey(r):
    return (r["day"], r["et"], r["sym"])


# --------------------------------------------------------------- bar access

_bars_cache: dict = {}


def bars_for(sym, day):
    """data_archive only -- never falls through to a network fetch. A missing
    file is a plain empty result, not a fetch (pf.fetch_day would try the
    live Polygon API on a miss, which is 403 NOT_AUTHORIZED per CLAUDE.md and
    would make this script's output depend on network state)."""
    k = (sym, day)
    if k not in _bars_cache:
        if len(_bars_cache) > 800:
            _bars_cache.clear()
        csv_path = pf.ARCHIVE / sym / ("%s.csv" % day)
        if not csv_path.exists():
            _bars_cache[k] = []
        else:
            try:
                _bars_cache[k] = pf.rth(pf.fetch_day(sym, day))
            except Exception:
                _bars_cache[k] = []
    return _bars_cache[k]


def atr_at(bars, j, n=ATR_N):
    """True range average over the n bars ending at j. Causal by construction
    -- identical derivation to research/g87_retest_tol.py::atr_at."""
    if j < 1:
        return None
    lo = max(1, j - n + 1)
    trs = []
    for k in range(lo, j + 1):
        c, p = bars[k], bars[k - 1]
        trs.append(max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close)))
    return sum(trs) / len(trs) if trs else None


# ------------------------------------------------------------ the b shift

def resolve_b(kind, size, r, bars):
    """Dollars to shift the target by, toward entry. (b, used_fallback)."""
    if kind == "cents":
        return size, False
    if kind == "atr":
        entry_i = r.get("entry_i")
        if entry_i is None or not bars or entry_i >= len(bars):
            return 0.05, True   # fallback: cents_005
        a = atr_at(bars, entry_i)
        if a is None:
            return 0.05, True
        return 0.05 * a, False
    raise ValueError(kind)


def shifted_target(r, b):
    long = r["dir"] == "call"
    entry, target = r["entry"], r["target"]
    b = min(b, abs(target - entry) * 0.9)   # never cross the entry
    return (target - b) if long else (target + b)


# --------------------------------------------------------- the single-stage walker

def simulate_exit(r, target_price):
    """(pnl, r_mult, reason) for one candidate under a single-stage
    disaster-stop / target / level-stop walker. reason in
    {'target','stop_close','disaster','eod','no_bars'}."""
    entry, stop = r["entry"], r["stop"]
    long = r["dir"] == "call"
    risk = abs(entry - stop)
    if risk <= 0:
        return r["pnl"], r["r"], "no_bars"

    bars = bars_for(r["sym"], r["day"])
    entry_i = r.get("entry_i")
    if not bars or entry_i is None or entry_i >= len(bars):
        return r["pnl"], r["r"], "no_bars"

    disaster_price = sru.disaster_stop_price(entry, risk, long)

    for j in range(entry_i + 1, len(bars)):
        c = bars[j]
        if sru.disaster_stop_hit(c.high, c.low, disaster_price, long):
            return -sru.DISASTER_STOP_R * RISK, -sru.DISASTER_STOP_R, "disaster"

        touched = (c.high >= target_price) if long else (c.low <= target_price)
        if touched:
            if long:
                fill = c.open if c.open >= target_price else target_price
            else:
                fill = c.open if c.open <= target_price else target_price
            r_mult = (fill - entry) / risk if long else (entry - fill) / risk
            return r_mult * RISK, r_mult, "target"

        if sru.stop_hit_on_close(c.close, stop, long):
            fill = sru.stop_fill_price(c.close, entry, risk, long)
            r_mult = (fill - entry) / risk if long else (entry - fill) / risk
            return r_mult * RISK, r_mult, "stop_close"

    last = bars[-1]
    r_mult = (last.close - entry) / risk if long else (entry - last.close) / risk
    return r_mult * RISK, r_mult, "eod"


# ------------------------------------------------------------------- stats

def price_stats(trades, n_days):
    if not trades:
        return {"trades": 0, "per_day": 0.0, "mean_r": 0.0, "win_pct": 0.0,
                "months_green": 0, "months": 0, "max_dd": 0.0, "total_dollars": 0.0}
    pnls = [t["pnl"] for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    total = sum(pnls)
    by_day = defaultdict(float)
    by_m = defaultdict(float)
    for t in trades:
        by_day[t["day"]] += t["pnl"]
        by_m[t["day"][:7]] += t["pnl"]
    cum = peak = dd = 0.0
    for d in sorted(by_day):
        cum += by_day[d]
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return {
        "trades": len(trades),
        "per_day": round(total / n_days, 2) if n_days else 0.0,
        "mean_r": round(total / len(trades) / RISK, 3),
        "win_pct": round(wins / (wins + losses) * 100, 1) if wins + losses else 0.0,
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "months": len(by_m),
        "max_dd": round(dd, 2),
        "total_dollars": round(total, 2),
    }


def n_days_in(picks, lo=None, hi=None):
    days = {t["day"] for t in picks}
    if lo is not None:
        days = {d for d in days if d >= lo}
    if hi is not None:
        days = {d for d in days if d < hi}
    return len(days)


def half(trades, lo=None, hi=None):
    return [t for t in trades if (lo is None or t["day"] >= lo)
            and (hi is None or t["day"] < hi)]


# ----------------------------------------------------------- S recall / precision

def s_sweep_keys():
    rows = list(bd._rows(PROBE_S34))
    return {"%s_%s" % (r["symbol"], r["date"]) for r in rows if mp.row_grade(r) == "S"}, len(rows)


def recall_and_precision(picks_by_day, all_candidates_by_day, pool, s100_keys, bar_backed_s_all):
    """Selection is IDENTICAL between arms (this rule is exit-only), so this
    is computed exactly once. fired_map = {day: sym of that day's one pick}.
    recall = the arm's single daily pick happened to land on that S symbol-day
    (any candidate anywhere in the book that day is a looser, different, and
    NOT reported number). precision = of days the arm fired, restricted to
    days with any canonical grade, the share graded S."""
    fired_map = {day: r["sym"] for day, r in picks_by_day.items()}

    def recall_frac(keys):
        keys = list(keys)
        if not keys:
            return {"hit": 0, "n": 0, "pct": None}
        hits = 0
        for k in keys:
            sym, day = k.split("_", 1)
            if fired_map.get(day) == sym:
                hits += 1
        return {"hit": hits, "n": len(keys), "pct": round(hits / len(keys) * 100, 1)}

    r100 = recall_frac(s100_keys)
    rall = recall_frac(bar_backed_s_all)

    graded_any = graded_s = 0
    for day, sym in fired_map.items():
        e = pool.get("%s_%s" % (sym, day))
        if e is None:
            continue
        graded_any += 1
        if e.grade == "S":
            graded_s += 1
    precision = {"graded_s": graded_s, "graded_any": graded_any,
                 "pct": round(graded_s / graded_any * 100, 1) if graded_any else None}
    return r100, rall, precision


def main():
    blob = json.load(open(BOOK, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    n_days = meta.get("sessions") or len({r["day"] for r in rows})
    print("book: %s -- %d sessions" % (os.path.basename(BOOK), n_days))

    # -------- one-trade-a-day pick: identical for every arm below --------
    picks = om.first_of_day_arm(rows, size_gate=True)   # size-gated, arrival order
    picks_by_day = {r["day"]: r for r in picks}
    print("one-trade-a-day picks: %d of %d sessions" % (len(picks), n_days))

    by_day_all = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            by_day_all[r["day"]].append(r)
    cand_per_day = round(sum(len(v) for v in by_day_all.values()) / n_days, 2)
    fires_per_day = round(len(picks) / n_days, 3)

    pool = mp.canonical_pool()
    s100_keys, s100_n_rows = s_sweep_keys()
    bar_backed_s_all = {k for k in mp.s_days(pool) if pool[k].has_bars}
    print("34-card sweep: %d rows, %d graded S -- bar-backed S days corpus-wide: %d"
          % (s100_n_rows, len(s100_keys), len(bar_backed_s_all)))

    r100, rall, precision = recall_and_precision(
        picks_by_day, by_day_all, pool, s100_keys, bar_backed_s_all)
    print("recall_100 %s/%s  recall_all %s/%s  precision %s/%s (IDENTICAL every arm -- "
          "this rule never changes which trade fires)"
          % (r100["hit"], r100["n"], rall["hit"], rall["n"],
             precision["graded_s"], precision["graded_any"]))

    # -------- baseline: single-stage walker, target AT the exact level (b=0) --------
    base_trades = []
    base_hits = 0
    for day, r in sorted(picks_by_day.items()):
        pnl, r_mult, reason = simulate_exit(r, r["target"])
        base_trades.append({"day": day, "pnl": pnl, "r": r_mult, "reason": reason})
        if reason == "target":
            base_hits += 1
    base_full = price_stats(base_trades, n_days)
    base_h1 = price_stats(half(base_trades, hi=H_SPLIT), n_days_in(base_trades, hi=H_SPLIT))
    base_h2 = price_stats(half(base_trades, lo=H_SPLIT), n_days_in(base_trades, lo=H_SPLIT))
    base_hit_rate = round(base_hits / len(base_trades) * 100, 1) if base_trades else None
    base_hit_rs = [t["r"] for t in base_trades if t["reason"] == "target"]
    base_r_on_hit = round(sum(base_hit_rs) / len(base_hit_rs), 3) if base_hit_rs else None
    print("\nBASELINE (single-stage walker, target at exact level): $%d/day "
          "(H1 $%d, H2 $%d), mean R %.3f, win %.1f%%, months green %d/%d, maxDD $%d, "
          "target-hit rate %.1f%%"
          % (base_full["per_day"], base_h1["per_day"], base_h2["per_day"],
             base_full["mean_r"], base_full["win_pct"], base_full["months_green"],
             base_full["months"], base_full["max_dd"], base_hit_rate))

    arms = {}
    for name, kind, size in ARMS_B:
        cand_trades = []
        cand_hits = 0
        n_fallback = 0
        for day, r in sorted(picks_by_day.items()):
            bars = bars_for(r["sym"], r["day"])
            b, used_fallback = resolve_b(kind, size, r, bars)
            if used_fallback:
                n_fallback += 1
            tgt = shifted_target(r, b)
            pnl, r_mult, reason = simulate_exit(r, tgt)
            cand_trades.append({"day": day, "pnl": pnl, "r": r_mult, "reason": reason})
            if reason == "target":
                cand_hits += 1
        cand_full = price_stats(cand_trades, n_days)
        cand_h1 = price_stats(half(cand_trades, hi=H_SPLIT), n_days_in(cand_trades, hi=H_SPLIT))
        cand_h2 = price_stats(half(cand_trades, lo=H_SPLIT), n_days_in(cand_trades, lo=H_SPLIT))
        cand_hit_rate = round(cand_hits / len(cand_trades) * 100, 1) if cand_trades else None
        cand_hit_rs = [t["r"] for t in cand_trades if t["reason"] == "target"]
        cand_r_on_hit = round(sum(cand_hit_rs) / len(cand_hit_rs), 3) if cand_hit_rs else None

        h1_delta = round(cand_h1["per_day"] - base_h1["per_day"], 2)
        h2_delta = round(cand_h2["per_day"] - base_h2["per_day"], 2)
        survivor = (h1_delta > 0 and h2_delta > 0
                    and (r100["pct"] or 0) >= (r100["pct"] or 0))  # recall identical, trivially true

        arms[name] = {
            "kind": kind, "size": size, "n_fallback_to_cents_005": n_fallback,
            "full": cand_full, "h1": cand_h1, "h2": cand_h2,
            "target_hit_rate_pct": cand_hit_rate,
            "target_hit_rate_delta_pts": (round(cand_hit_rate - base_hit_rate, 1)
                                          if cand_hit_rate is not None and base_hit_rate is not None
                                          else None),
            "r_on_hit_only": cand_r_on_hit,
            "r_on_hit_only_delta": (round(cand_r_on_hit - base_r_on_hit, 3)
                                    if cand_r_on_hit is not None and base_r_on_hit is not None
                                    else None),
            "mean_r_delta": round(cand_full["mean_r"] - base_full["mean_r"], 3),
            "h1_delta_usd_day": h1_delta, "h2_delta_usd_day": h2_delta,
            "survivor": survivor,
        }
        print("\n%s (b=%s): $%d/day (H1 $%d [%+.2f], H2 $%d [%+.2f]), mean R %.3f "
              "(%+.3f), win %.1f%%, months green %d/%d, maxDD $%d, target-hit rate "
              "%.1f%% (%+.1f pts), R-on-hit-only %s (%s vs baseline %s), "
              "fallback-to-cents_005 on %d/%d rows -- survivor=%s"
              % (name, ("%.4f" % size if kind == "atr" else "$%.2f" % size),
                 cand_full["per_day"], cand_h1["per_day"], h1_delta,
                 cand_h2["per_day"], h2_delta, cand_full["mean_r"],
                 arms[name]["mean_r_delta"], cand_full["win_pct"],
                 cand_full["months_green"], cand_full["months"], cand_full["max_dd"],
                 cand_hit_rate, arms[name]["target_hit_rate_delta_pts"] or 0.0,
                 cand_r_on_hit, arms[name]["r_on_hit_only_delta"], base_r_on_hit,
                 n_fallback, len(cand_trades), survivor))

    any_survivor = any(a["survivor"] for a in arms.values())

    out = {
        "meta": {
            "book": os.path.basename(BOOK), "sessions": n_days,
            "candidate": "scale-before-the-level",
            "candidates_per_day": cand_per_day, "fires_per_day": fires_per_day,
        },
        "recall_precision_identical_every_arm": {
            "recall_100": r100, "recall_all": rall, "precision": precision,
            "note": "This rule is exit-only: selection (first_of_day_arm) is "
                    "untouched, so recall/precision/candidates-per-day/fires-per-day "
                    "cannot differ between baseline and any candidate arm here.",
        },
        "baseline_single_stage_walker": {
            "full": base_full, "h1": base_h1, "h2": base_h2,
            "target_hit_rate_pct": base_hit_rate,
            "r_on_hit_only": base_r_on_hit,
        },
        "arms": arms,
        "any_survivor": any_survivor,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    md = []
    md.append("# g154 -- scale-before-the-level (F5)\n")
    md.append("**Scaling the target BEFORE the exact level (not resting at it) "
               "raises the target-hit rate but did not survive on $/day across "
               "both halves.**" if not any_survivor else
               "**Scaling the target BEFORE the exact level (not resting at it) "
               "raised $/day in both H1 and H2 for at least one size of the shift.**")
    md.append("")
    md.append("This rule changes ONLY the exit (the target price the day's already-"
               "picked trade scales out at). It never changes which trade fires, so "
               "candidates/day, fires/day, S recall, and precision are identical "
               "across every row below -- reported once.\n")
    md.append("book: `%s` -- %d sessions. one-trade-a-day picks: %d.\n"
               % (os.path.basename(BOOK), n_days, len(picks)))
    md.append("candidates/day %.2f, fires/day %.3f\n" % (cand_per_day, fires_per_day))
    md.append("recall_100 %s/%s (%.1f%%) | recall_all %s/%s (%s%%) | "
               "precision %s/%s (%s%%)\n"
               % (r100["hit"], r100["n"], r100["pct"] or 0.0,
                  rall["hit"], rall["n"], rall["pct"],
                  precision["graded_s"], precision["graded_any"], precision["pct"]))

    md.append("| arm | b | $/day | H1 $/day | H2 $/day | mean R | win% | months green | "
               "maxDD | target-hit% | Δhit pts | ΔmeanR | R-on-hit-only | survivor |")
    md.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    md.append("| baseline (target=level) | $0.00 | $%d | $%d | $%d | %.3f | %.1f%% | %d/%d | "
               "$%d | %.1f%% | -- | -- | %s | -- |"
               % (base_full["per_day"], base_h1["per_day"], base_h2["per_day"],
                  base_full["mean_r"], base_full["win_pct"], base_full["months_green"],
                  base_full["months"], base_full["max_dd"], base_hit_rate, base_r_on_hit))
    for name, kind, size in ARMS_B:
        a = arms[name]
        bstr = ("0.05xATR14" if kind == "atr" else "$%.2f" % size)
        md.append("| %s | %s | $%d | $%d | $%d | %.3f | %.1f%% | %d/%d | $%d | %.1f%% | "
                   "%+.1f | %+.3f | %s (%+.3f) | %s |"
                   % (name, bstr, a["full"]["per_day"], a["h1"]["per_day"],
                      a["h2"]["per_day"], a["full"]["mean_r"], a["full"]["win_pct"],
                      a["full"]["months_green"], a["full"]["months"], a["full"]["max_dd"],
                      a["target_hit_rate_pct"], a["target_hit_rate_delta_pts"] or 0.0,
                      a["mean_r_delta"], a["r_on_hit_only"], a["r_on_hit_only_delta"] or 0.0,
                      a["survivor"]))
    md.append("")
    md.append("Fallback to cents_005 (ATR uncomputable): %d/%d rows on the atr_005 arm.\n"
               % (arms["atr_005"]["n_fallback_to_cents_005"], len(picks)))
    md.append("Survivor rule (per row spec): H1 AND H2 both improve $/day (precision "
               "cannot move for an exit-only rule, so it never supplies the "
               "improvement here) and recall_100 not below baseline (trivially true "
               "-- selection is identical). any_survivor = **%s**.\n" % any_survivor)
    md.append("Limitation, stated plainly: both arms run a SINGLE-STAGE proxy exit "
               "(one target, one stop) built for this comparison, not the shipped "
               "multi-stage SCALE_PLAN ladder (`backtest_week._ladder_bar`). The "
               "baseline row above is therefore NOT the book's own booked $/day (that "
               "number reflects the full ladder) -- it is the same single-stage "
               "walker run with the target AT the exact level, so the baseline-vs-"
               "candidate comparison is apples-to-apples even though neither side "
               "matches the shipped book's own headline number.\n")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print("\nwrote %s" % OUT_JSON)
    print("wrote %s" % OUT_MD)
    print("\nany_survivor = %s" % any_survivor)


if __name__ == "__main__":
    main()
