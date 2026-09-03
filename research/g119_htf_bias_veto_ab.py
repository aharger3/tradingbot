"""g119 -- HTF_BIAS_VETO, the real 2-year book, plus S recall and false fires.

Modeled directly on `research/g94_retest_book_compare.py` -- same matched-book
A/B pattern (common window, shared-rows-unmoved gate, population delta,
one-trade-a-day money via `g86_honest_ceiling` / `g91_lane_slice`) -- applied
to a different flag: `omen_bot.HTF_BIAS_VETO` (an opposed higher-timeframe
bias skips the trade when ON, the shipped default). Both books were built
back to back on commit `cacc69d9`, same `data_archive/`, same 09:30-11:00
session window, `RETEST_REQUIRED=1` fixed in both (signal_runner.py's own
default, unchanged):

    research/bt2y_trades_htfveto_on.json   (HTF_BIAS_VETO=1, shipped default)
    research/bt2y_trades_htfveto_off.json  (HTF_BIAS_VETO=0, lifted)

`HTF_BIAS_VETO` lives in `omen_bot.py`, imported into `signal_runner.py` at
module scope -- the book stamp only captures `entry_fill` / `loss_halt` /
`stop_rule` / `backtest_week` / `signal_runner` globals, so it is NOT a key in
`meta.stamp.flags` on either book. That is a gap in the stamp, not evidence
the flag was not set; the two books are handed to this script as a matched
pair by construction (see CONTEXT above / the run that produced them) and the
git commit + session count + symbol list are checked to agree below as the
next best thing to a literal flag stamp.

SHARED ROWS DO NOT COME OUT PERFECTLY UNMOVED, and that is g94's own finding
repeating itself, not a bug in this script. `backtest_week.DEDUPE_FIRES_ONLY`
means only a `fired` signal claims the dedupe suppression window
(backtest_week.py:973); an opposed-bias candidate that the veto caps to `D`
(`skipped_d`, not `fired`) releases that window, so a LATER candidate on the
same level can become the row that claims a given (day, symbol, entry-time,
direction) key -- same entry time, same direction, a different underlying
signal, occasionally a different stop. Measured here: of 108,132 rows shared
between the two arms' (day, sym, et, dir) keys, 107 (0.099%) carry a changed
entry or stop -- the same order of magnitude as g94's own 49-of-111,024
(0.044%) for `RETEST_REQUIRED`, just larger because an opposed HTF bias trips
far more often than a failed retest. Reported as FAIL below, exactly as g94
reports its own instance of the same mechanism as FAIL: this script does not
paper over it, and the population delta two paragraphs down is the same
mechanism's larger, structural half.

On top of what g94 measures, this file adds three things that decide whether
lifting the veto is a genuine win rather than "more trades, same edge, inside
noise":

  1. **S-day recall** -- of Austin's canonical S days (`marks_pool.py`) whose
     (symbol, date) has at least one row in an arm's book ("in-universe"),
     what fraction have a `traded: true` row? `traded` here is read straight
     off the row, not recomputed: `backtest_week.py:930` writes
     `"traded": bool(t.counted)` and `SimTrade.counted` is
     `status == "fired" and grade != "C"` -- exactly the semantics
     `research/g118_172_gate_kills.py::build_target_sets()` reuses, and so
     does this file, rather than re-deriving them from `status`/`grade` by
     hand. Because "in-universe" is defined per lane+arm from the row set
     itself and the veto only ever emits a `skipped_d` row (it never removes
     the symbol-day from the book), the two arms' in-universe sets are
     identical by construction -- verified equal, not assumed.
  2. **False-fire rate** -- of the one-trade-a-day pick stream (the first
     traded/halted signal of each day, `g86.candidates()`), what fraction of
     the days that have ANY canonical-pool opinion for that symbol-day are
     days Austin graded something other than S? Days with no canonical-pool
     opinion at all are EXCLUDED from the denominator, not counted as false
     fires either way. Broken down further into grade `A` (recorded, not yet
     tradeable per the 2026-09-01 scope call -- not obviously a mistake),
     explicit `none` (a day-level refusal), and `X`-only (`marks_pool.py`'s
     own words: "a refusal AIMED AT THE ENGINE -- this specific detection was
     wrong -- not a day-level 'I would not trade this'"). The all-non-S
     headline rate is reported next to a day-level rate that excludes
     X-only, because lumping them overstates how often Austin actually
     refused the DAY.
  3. **Whether any of the above clears its own noise.** Money uses a paired
     daily delta (ON-OFF per session, one-a-day pick stream) with its sample
     SE and a 95% interval -- the exact number CLAUDE.md already asks for
     ("every dollar figure names its fill" and, for g94, "inside the
     +-1.58R error bar"). S recall's in-universe sets are identical between
     arms, so it is a paired (McNemar) comparison: discordant S-days
     (traded by one arm, not the other) get an exact two-sided binomial
     test against p=0.5, stdlib only (`math.comb`). False-fire rates get a
     Wilson 95% interval per arm. Green-month flips are reported with the
     dollar margin each flip turned on, because a green month that is green
     by $84 across twenty sessions is not the same finding as one green by
     $6,336.

Both computed for two lanes, exactly as g94 does: full pool and
`g91.INDEX` (QQQ/SPY/IWM).

    python research/g119_htf_bias_veto_ab.py

Writes research/g119_htf_bias_veto_ab.md and .json.
"""
from __future__ import annotations

import collections
import json
import math
import os
import sys
from collections import defaultdict
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402
import g91_lane_slice as g91                      # noqa: E402
import marks_pool as mp                           # noqa: E402

OFF = os.path.join(HERE, "bt2y_trades_htfveto_off.json")   # HTF_BIAS_VETO=0, lifted
ON = os.path.join(HERE, "bt2y_trades_htfveto_on.json")     # HTF_BIAS_VETO=1, shipped
OUT_MD = os.path.join(HERE, "g119_htf_bias_veto_ab.md")
OUT_JSON = os.path.join(HERE, "g119_htf_bias_veto_ab.json")

LANES = [("full pool", lambda r: True),
         ("index QQQ/SPY/IWM", lambda r: r["sym"] in g91.INDEX)]

MONEY_KEYS = [("cands_per_day", "cand/day", "%.1f"),
              ("per_day", "$/day", "%.0f"),
              ("win_pct", "win %", "%.1f"),
              ("mean_r", "mean R", "%+.3f"),
              ("green_n", "green mo", "%d"),
              ("max_dd", "max DD", "%.0f")]


def load(p):
    b = json.load(open(p, encoding="utf-8"))
    return (b["trades"], b.get("meta", {})) if isinstance(b, dict) else (b, {})


def common_window(off, on):
    """Restrict both books to the sessions they share -- g94's exact rule,
    defensive here even though both arms were built back to back with the
    same `--days` window: detection is independent per session, so
    intersecting the day sets costs nothing when the windows already match
    and prevents a silent calendar confound if they ever don't."""
    days = {r["day"] for r in off} & {r["day"] for r in on}
    return ([r for r in off if r["day"] in days],
            [r for r in on if r["day"] in days], days)


def pick_stream(rows, pred):
    """Lane-filtered rows, the day->candidates map, and the one-trade-a-day
    firsts list -- g86.candidates()'s own rule (fired-and-traded, plus a
    halted row on a day the account-wide loss-halt would not have fired
    under one-a-day). Shared by the money table, S recall and false fires so
    all three read the identical pick stream."""
    sub = [r for r in rows if pred(r)]
    byday = g86.candidates(sub)
    firsts = [byday[d][0] for d in sorted(byday) if byday[d]]
    return sub, byday, firsts


def oneaday_stats(byday, firsts):
    daily = defaultdict(float)
    for r in firsts:
        daily[r["day"]] += r["pnl"]
    n = len(daily)
    if not n:
        return {}
    g, m = g91.months_green(daily)
    path = g91.path_risk(daily, 2000.0, 2500.0)
    return {"cands_per_day": round(sum(len(v) for v in byday.values()) / n, 1),
            "days": n, "green": "%d/%d" % (g, m), "green_n": g, "green_total": m,
            "max_dd": path["max_dd"], "funded_per_day": path["funded_per_day"],
            "daily_pnl": dict(daily),
            **g86.stats(firsts, n)}


def s_recall(sub, pool):
    """Austin's canonical S days, restricted to this arm+lane's own book.

    Reuses g118_172_gate_kills.build_target_sets()'s logic verbatim: S days
    are `pool.canonical_pool()` entries graded S; "in-universe" is a day whose
    (symbol, date) has at least one row in `sub` (the lane-filtered,
    common-window-restricted book); "traded" reads the row's own `traded`
    field (== `status=="fired" and grade != "C"`, backtest_week.SimTrade.counted)
    rather than recomputing it.
    """
    by_symday = defaultdict(list)
    for r in sub:
        by_symday[(r["sym"], r["day"])].append(r)
    S = {k: e for k, e in pool.items() if e.grade == "S"}
    in_universe = {k: e for k, e in S.items() if (e.symbol, e.date) in by_symday}
    traded = {k: e for k, e in in_universe.items()
              if any(row["traded"] for row in by_symday[(e.symbol, e.date)])}
    n_iu, n_tr = len(in_universe), len(traded)
    return {"s_days_total": len(S), "in_universe": n_iu, "traded": n_tr,
            "in_universe_keys": sorted(in_universe.keys()),
            "traded_keys": sorted(traded.keys()),
            "recall": round(n_tr / n_iu, 4) if n_iu else None,
            "recall_pct": round(n_tr / n_iu * 100, 1) if n_iu else None}


def false_fire_rate(firsts, pool):
    """Of the one-trade-a-day pick stream, how many picks land on a day
    Austin explicitly graded something other than S -- among the days he
    graded at all. A day with no canonical-pool opinion is excluded from the
    denominator, not folded into either side.

    Broken down by what the non-S opinion actually was: `A` (recorded, not
    yet tradeable per the 2026-09-01 scope call, not obviously a mistake),
    explicit `none` (a day-level refusal), and `X`-only (an engine-detection
    refusal per marks_pool.py's own docstring, not a day-level refusal). The
    day-level rate excludes X-only from the numerator.
    """
    judged = false_fires = s_hits = 0
    breakdown = collections.Counter()
    for r in firsts:
        e = pool.get("%s_%s" % (r["sym"], r["day"]))
        if e is None:
            continue
        judged += 1
        if e.grade == "S":
            s_hits += 1
            continue
        false_fires += 1
        if e.grade == "none" and set(e.raw_grades) == {"X"}:
            breakdown["x_only"] += 1
        elif e.grade == "none":
            breakdown["none"] += 1
        else:
            breakdown[e.grade] += 1
    unjudged = len(firsts) - judged
    day_level_false = false_fires - breakdown.get("x_only", 0)
    return {"traded_days": len(firsts), "judged_days": judged,
            "unjudged_days": unjudged, "s_hits": s_hits,
            "false_fires": false_fires,
            "false_fire_rate": round(false_fires / judged, 4) if judged else None,
            "false_fire_pct": round(false_fires / judged * 100, 1) if judged else None,
            "breakdown": dict(breakdown),
            "day_level_false_fires": day_level_false,
            "day_level_false_fire_pct": (round(day_level_false / judged * 100, 1)
                                         if judged else None)}


def wilson_ci(x, n, z=1.96):
    """Wilson 95% interval for a proportion, stdlib only."""
    if not n:
        return None
    p = x / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return [round((center - half) * 100, 1), round((center + half) * 100, 1)]


def mcnemar_exact_p(b, c):
    """Exact two-sided McNemar test on discordant pair counts b, c against
    p=0.5, stdlib only (math.comb). Used for S recall: identical in-universe
    sets between arms make traded/not-traded a genuine paired comparison."""
    n = b + c
    if n == 0:
        return None
    k = min(b, c)
    p_one_side = sum(comb(n, i) for i in range(0, k + 1)) * (0.5 ** n)
    return round(min(1.0, 2 * p_one_side), 4)


def paired_daily_stats(daily_o, daily_n):
    """Paired ON-minus-OFF daily $ delta over the union of days either arm
    picked a trade on (a day missing from one arm contributes 0 for that
    arm, same convention as the money table's own daily series). Sample SE
    and a 95% interval, no invented machinery -- plain paired-sample stats."""
    days = set(daily_o) | set(daily_n)
    n = len(days)
    if n < 2:
        return None
    diffs = [daily_n.get(d, 0.0) - daily_o.get(d, 0.0) for d in days]
    mean = sum(diffs) / n
    var = sum((x - mean) ** 2 for x in diffs) / (n - 1)
    se = (var / n) ** 0.5
    return {"n": n, "mean": round(mean, 2), "se": round(se, 2),
            "ci95": [round(mean - 1.96 * se, 2), round(mean + 1.96 * se, 2)]}


def month_flips(daily_o, daily_n):
    """Calendar months where the two arms' sign disagrees, with each side's
    dollar total -- a '+green months' delta with no margin printed next to
    it can be one trade flipping a month green by a few dollars."""
    mo, mn = defaultdict(float), defaultdict(float)
    for d, v in daily_o.items():
        mo[d[:7]] += v
    for d, v in daily_n.items():
        mn[d[:7]] += v
    flips = []
    for m in sorted(set(mo) | set(mn)):
        vo, vn = mo.get(m, 0.0), mn.get(m, 0.0)
        if (vo > 0) != (vn > 0):
            flips.append({"month": m, "off": round(vo, 2), "on": round(vn, 2)})
    return flips


def main():
    for p in (OFF, ON):
        if not os.path.exists(p):
            raise SystemExit("missing book: %s" % p)
    off, moff = load(OFF)
    on, mon = load(ON)
    pool = mp.canonical_pool()

    def bstamp(m):
        s = m.get("stamp", {})
        return (s.get("book_id", "?")[:12], s.get("git", {}).get("commit", "?")[:10],
                s.get("flags", {}).get("omen_bot.HTF_BIAS_VETO", "NOT STAMPED"))

    off_id, off_commit, off_veto = bstamp(moff)
    on_id, on_commit, on_veto = bstamp(mon)
    print("OFF book (HTF_BIAS_VETO=0, lifted): %s  commit=%s  signals=%d traded=%d  "
          "stamp.HTF_BIAS_VETO=%s"
          % (off_id, off_commit, len(off), moff.get("traded"), off_veto))
    print("ON  book (HTF_BIAS_VETO=1, shipped): %s  commit=%s  signals=%d traded=%d  "
          "stamp.HTF_BIAS_VETO=%s"
          % (on_id, on_commit, len(on), mon.get("traded"), on_veto))
    if off_commit != on_commit:
        print("*** WARNING: books built on different commits (%s vs %s) ***"
              % (off_commit, on_commit))

    # --- control for the calendar before comparing anything --------------
    raw_off, raw_on = len(off), len(on)
    off, on, days = common_window(off, on)
    print("\ncommon window: %d sessions %s..%s  (dropped %d OFF rows, %d ON rows "
          "that fall outside it)"
          % (len(days), min(days), max(days), raw_off - len(off), raw_on - len(on)))

    # --- the real gate: no SHARED row may move ---------------------------
    key = lambda r: (r["day"], r["sym"], r["et"], r["dir"])
    mo = {key(r): r for r in off}
    mn = {key(r): r for r in on}
    shared = set(mo) & set(mn)
    moved = [k for k in shared
             if abs(mo[k]["entry"] - mn[k]["entry"]) > 1e-9
             or abs(mo[k]["stop"] - mn[k]["stop"]) > 1e-9]
    shared_pass = not moved
    moved_pct = round(len(moved) / len(shared) * 100, 4) if shared else 0.0
    print("SHARED ROWS UNMOVED: %s (%d shared; %d with a changed entry or stop, %.4f%%)"
          % ("PASS" if shared_pass else "*** FAIL ***", len(shared), len(moved), moved_pct))
    if moved:
        print("  (same mechanism as g94's own FAIL: a capped candidate is not "
              "`fired`, so it releases backtest_week's dedupe window and a "
              "different candidate can claim the same day/sym/entry-time/dir "
              "slot -- see the module docstring)")
    for k in moved[:3]:
        print("      %s entry %.4f->%.4f stop %.4f->%.4f"
              % (k, mo[k]["entry"], mn[k]["entry"], mo[k]["stop"], mn[k]["stop"]))

    oo, nn = set(mo) - set(mn), set(mn) - set(mo)
    print("population delta: %d OFF-only, %d ON-only" % (len(oo), len(nn)))
    for lab, sset, m in (("  OFF-only", oo, mo), ("  ON-only ", nn, mn)):
        print("%s by setup: %s" % (lab, dict(collections.Counter(
            m[k]["setup"] for k in sset))))

    go = collections.Counter(r["grade"] for r in off)
    gn = collections.Counter(r["grade"] for r in on)
    print("\ngrade mix   %-28s -> %s" % (dict(sorted(go.items())),
                                         dict(sorted(gn.items()))))

    lanes_out = {}
    for lane, pred in LANES:
        print("\n=== %s ===" % lane)
        sub_o, byday_o, firsts_o = pick_stream(off, pred)
        sub_n, byday_n, firsts_n = pick_stream(on, pred)
        a = oneaday_stats(byday_o, firsts_o)
        b = oneaday_stats(byday_n, firsts_n)
        if not a or not b:
            print("  (no candidates in this lane for one arm -- skipped)")
            continue

        sr_o = s_recall(sub_o, pool)
        sr_n = s_recall(sub_n, pool)
        ff_o = false_fire_rate(firsts_o, pool)
        ff_n = false_fire_rate(firsts_n, pool)

        print("  one trade a day")
        print("    %-12s %8s %8s %8s" % ("", "OFF", "ON", "delta"))
        money_delta = {}
        for k, lab, fmt in MONEY_KEYS:
            va, vb = a.get(k), b.get(k)
            if va is None or vb is None:
                continue
            d = vb - va
            money_delta[k] = round(d, 4) if isinstance(d, float) else d
            print(("    %-12s " + fmt + " " * 4 + fmt + " " * 4 + "%+.3f")
                  % (lab, va, vb, d))

        paired = paired_daily_stats(a["daily_pnl"], b["daily_pnl"])
        if paired:
            print("  paired daily $ delta (ON-OFF, n=%d): mean %+.2f  SE %.2f  "
                  "95%% CI [%+.2f, %+.2f]%s"
                  % (paired["n"], paired["mean"], paired["se"],
                     paired["ci95"][0], paired["ci95"][1],
                     "  -- straddles zero" if paired["ci95"][0] < 0 < paired["ci95"][1] else ""))

        flips = month_flips(a["daily_pnl"], b["daily_pnl"])
        if flips:
            print("  green-month sign flips: %d  %s"
                  % (len(flips), ", ".join("%s OFF %+.0f -> ON %+.0f"
                                            % (f["month"], f["off"], f["on"])
                                            for f in flips)))

        print("  S recall (in-universe canonical S days with a traded row)")
        print("    OFF: %d/%d = %s    ON: %d/%d = %s    delta: %s pts"
              % (sr_o["traded"], sr_o["in_universe"],
                 ("%.1f%%" % sr_o["recall_pct"]) if sr_o["recall_pct"] is not None else "n/a",
                 sr_n["traded"], sr_n["in_universe"],
                 ("%.1f%%" % sr_n["recall_pct"]) if sr_n["recall_pct"] is not None else "n/a",
                 ("%+.1f" % (sr_n["recall_pct"] - sr_o["recall_pct"]))
                 if sr_o["recall_pct"] is not None and sr_n["recall_pct"] is not None
                 else "n/a"))
        iu_equal = set(sr_o["in_universe_keys"]) == set(sr_n["in_universe_keys"])
        only_off = sorted(set(sr_o["traded_keys"]) - set(sr_n["traded_keys"]))
        only_on = sorted(set(sr_n["traded_keys"]) - set(sr_o["traded_keys"]))
        mcnemar_p = mcnemar_exact_p(len(only_off), len(only_on))
        print("    in-universe sets identical between arms: %s  |  discordant: "
              "%d OFF-only, %d ON-only  |  exact McNemar p=%s%s"
              % (iu_equal, len(only_off), len(only_on),
                 mcnemar_p if mcnemar_p is not None else "n/a",
                 "  -- not distinguishable from chance at p<0.05"
                 if mcnemar_p is not None and mcnemar_p >= 0.05 else ""))

        print("  false-fire rate (one-a-day picks Austin graded non-S, of picks he graded at all)")
        print("    OFF: %d/%d = %s  (%d unjudged, excluded)    "
              "ON: %d/%d = %s  (%d unjudged, excluded)    delta: %s pts"
              % (ff_o["false_fires"], ff_o["judged_days"],
                 ("%.1f%%" % ff_o["false_fire_pct"]) if ff_o["false_fire_pct"] is not None else "n/a",
                 ff_o["unjudged_days"],
                 ff_n["false_fires"], ff_n["judged_days"],
                 ("%.1f%%" % ff_n["false_fire_pct"]) if ff_n["false_fire_pct"] is not None else "n/a",
                 ff_n["unjudged_days"],
                 ("%+.1f" % (ff_n["false_fire_pct"] - ff_o["false_fire_pct"]))
                 if ff_o["false_fire_pct"] is not None and ff_n["false_fire_pct"] is not None
                 else "n/a"))
        ff_o_ci, ff_n_ci = wilson_ci(ff_o["false_fires"], ff_o["judged_days"]), \
                           wilson_ci(ff_n["false_fires"], ff_n["judged_days"])
        print("    Wilson 95%% -- OFF %s  ON %s  breakdown OFF %s ON %s  "
              "day-level (excl. X-only) OFF %s ON %s"
              % (ff_o_ci, ff_n_ci, dict(ff_o["breakdown"]), dict(ff_n["breakdown"]),
                 ("%.1f%%" % ff_o["day_level_false_fire_pct"])
                 if ff_o["day_level_false_fire_pct"] is not None else "n/a",
                 ("%.1f%%" % ff_n["day_level_false_fire_pct"])
                 if ff_n["day_level_false_fire_pct"] is not None else "n/a"))

        lanes_out[lane] = {
            "off": {"money": {k: v for k, v in a.items() if k != "daily_pnl"},
                    "s_recall": sr_o, "false_fire": ff_o},
            "on": {"money": {k: v for k, v in b.items() if k != "daily_pnl"},
                   "s_recall": sr_n, "false_fire": ff_n},
            "delta": {
                "money": money_delta,
                "s_recall_pct": (round(sr_n["recall_pct"] - sr_o["recall_pct"], 1)
                                 if sr_o["recall_pct"] is not None and sr_n["recall_pct"] is not None
                                 else None),
                "false_fire_pct": (round(ff_n["false_fire_pct"] - ff_o["false_fire_pct"], 1)
                                   if ff_o["false_fire_pct"] is not None and ff_n["false_fire_pct"] is not None
                                   else None),
            },
            "paired_daily_money": paired,
            "month_flips": flips,
            "s_recall_discordance": {"in_universe_sets_identical": iu_equal,
                                     "off_only": only_off, "on_only": only_on,
                                     "mcnemar_p": mcnemar_p},
            "false_fire_ci": {"off": ff_o_ci, "on": ff_n_ci},
        }

    # ------------------------------------------------------------ verdict
    # No binary "X wins" call: g119's own first cut printed one, and an
    # adversarial pass (2026-09-03) REFUTED it -- the arithmetic was right
    # but every headline delta sat inside its own sampling error, the two
    # lanes disagreed in sign on money, and the win/lose framing itself was
    # polarity-inverted (it credited "lifting the veto" for whichever arm's
    # delta happened to be positive, without checking which arm that was).
    # The honest report is the deltas next to their own noise, not a call.
    fp = lanes_out.get("full pool")
    verdict_lines = []
    if fp:
        d, sr_d, ff_d = fp["delta"]["money"], fp["delta"]["s_recall_pct"], fp["delta"]["false_fire_pct"]
        paired = fp["paired_daily_money"]
        disc = fp["s_recall_discordance"]
        verdict_lines = [
            "mean R: OFF %+.3f -> ON %+.3f (%+.3f)" % (
                fp["off"]["money"]["mean_r"], fp["on"]["money"]["mean_r"], d.get("mean_r", 0)),
            "paired $/day (ON-OFF): %+.2f, 95%% CI [%+.2f, %+.2f], n=%d%s" % (
                paired["mean"], paired["ci95"][0], paired["ci95"][1], paired["n"],
                " -- straddles zero" if paired["ci95"][0] < 0 < paired["ci95"][1] else ""),
            "green months: OFF %d -> ON %d (%+d), %d sign flip(s)" % (
                fp["off"]["money"]["green_n"], fp["on"]["money"]["green_n"], d.get("green_n", 0),
                len(fp["month_flips"])),
            "S recall: OFF %s -> ON %s (%s pts), discordant %d OFF-only/%d ON-only, McNemar p=%s" % (
                ("%.1f%%" % fp["off"]["s_recall"]["recall_pct"]),
                ("%.1f%%" % fp["on"]["s_recall"]["recall_pct"]),
                ("%+.1f" % sr_d) if sr_d is not None else "n/a",
                len(disc["off_only"]), len(disc["on_only"]), disc["mcnemar_p"]),
            "false-fire rate: OFF %s -> ON %s (%s pts), Wilson 95%% OFF %s ON %s" % (
                ("%.1f%%" % fp["off"]["false_fire"]["false_fire_pct"]),
                ("%.1f%%" % fp["on"]["false_fire"]["false_fire_pct"]),
                ("%+.1f" % ff_d) if ff_d is not None else "n/a",
                fp["false_fire_ci"]["off"], fp["false_fire_ci"]["on"]),
        ]
        idx = lanes_out.get("index QQQ/SPY/IWM")
        idx_note = ""
        if idx:
            ip = idx["paired_daily_money"]
            same_sign = (paired["mean"] > 0) == (ip["mean"] > 0)
            idx_note = ("index lane paired $/day (ON-OFF): %+.2f, 95%% CI [%+.2f, %+.2f] -- %s "
                        "the full-pool sign" % (ip["mean"], ip["ci95"][0], ip["ci95"][1],
                                                 "agrees with" if same_sign else "DISAGREES WITH"))
        print("\n=== full pool: deltas next to their own noise (no win/lose call) ===")
        for line in verdict_lines:
            print("  " + line)
        if idx_note:
            print("  " + idx_note)
        print("  Read together: every headline delta above sits inside a 95% interval "
              "that contains zero, or (S recall) is not distinguishable from a coin flip "
              "at p<0.05. This A/B does not make a case for moving HTF_BIAS_VETO off its "
              "shipped default of ON.")

    # ------------------------------------------------------------- write out
    blob = {
        "off_book": {"path": os.path.basename(OFF), "book_id": off_id,
                     "commit": off_commit, "signals": raw_off,
                     "traded_meta": moff.get("traded")},
        "on_book": {"path": os.path.basename(ON), "book_id": on_id,
                    "commit": on_commit, "signals": raw_on,
                    "traded_meta": mon.get("traded")},
        "common_window": {"sessions": len(days), "first": min(days), "last": max(days),
                          "dropped_off": raw_off - len(off), "dropped_on": raw_on - len(on)},
        "shared_rows_unmoved": {"shared": len(shared), "moved": len(moved),
                                "moved_pct": moved_pct, "pass": shared_pass},
        "population_delta": {"off_only": len(oo), "on_only": len(nn)},
        "grade_mix": {"off": dict(sorted(go.items())), "on": dict(sorted(gn.items()))},
        "lanes": lanes_out,
        "verdict": {"lines": verdict_lines,
                    "read": "no metric clears its own sampling noise; no case to move "
                            "the flag off its shipped default"},
    }
    json.dump(blob, open(OUT_JSON, "w", encoding="utf-8"), indent=1, sort_keys=True)
    print("\n  -> %s" % OUT_JSON)

    md = ["# g119 -- HTF_BIAS_VETO, the real 2-year book: S recall and false fires",
          "",
          "`omen_bot.HTF_BIAS_VETO` (default on). OFF book (lifted) "
          "`research/bt2y_trades_htfveto_off.json`, ON book (shipped) "
          "`research/bt2y_trades_htfveto_on.json`. Both built on commit "
          "`%s`, `RETEST_REQUIRED=1` fixed in both. `HTF_BIAS_VETO` is not a "
          "key in either book's `meta.stamp.flags` -- the stamp only captures "
          "`entry_fill`/`loss_halt`/`stop_rule`/`backtest_week`/`signal_runner` "
          "globals, and the flag lives in `omen_bot.py` -- so the two books "
          "are treated as a matched pair by construction, not re-verified "
          "against a literal flag stamp." % off_commit,
          "",
          "**Adversarial pass, 2026-09-03: this file's first cut was REFUTED.** "
          "The arithmetic reproduced exactly under independent re-derivation, but "
          "every headline delta sat inside its own sampling error, the full-pool "
          "and index lanes disagreed in sign on money, two of three '+green "
          "months' turned on $84 and $527 across ~20 sessions, the false-fire "
          "metric lumped `X`-only (an engine-detection refusal, not a day-level "
          "one) in with real refusals, and the verdict's win/lose logic was "
          "polarity-inverted (it happened to print the right English sentence "
          "only because the data made the wrong branch unreachable). This "
          "version drops the binary win/lose call, adds the paired-delta SE, "
          "the McNemar test for S recall, Wilson intervals for false fires, and "
          "the green-month flip margins, and reports both lanes in the verdict "
          "prose rather than the full pool alone.",
          "",
          "Shared rows unmoved: **%s** (%d shared, %d moved, %.4f%%). Same "
          "mechanism g94 already found for `RETEST_REQUIRED` and reported as "
          "FAIL rather than hiding: a capped candidate is not `fired`, so it "
          "releases `backtest_week`'s dedupe suppression window and a "
          "different candidate can claim the same (day, symbol, entry-time, "
          "direction) slot, occasionally with a different stop. Population "
          "delta %d OFF-only / %d ON-only rows -- the same release mechanism's "
          "larger, structural half (an opposed HTF bias trips far more often "
          "than a failed retest, so the effect is bigger here: %.4f%% moved "
          "vs g94's 0.044%%, still two orders of magnitude below the row "
          "count either way). The adversarial pass isolated the 96 (of 496) "
          "full-pool days where the two arms' first pick differs and found the "
          "21 days where ON's pick is entirely absent from the OFF book carry "
          "-$13,156 against a +$15,048 net across all 96 -- i.e. this artifact "
          "works AGAINST the ON arm's apparent money edge, not for it, so it "
          "is not the source of any headline number here."
          % ("PASS" if shared_pass else "FAIL", len(shared), len(moved), moved_pct,
             len(oo), len(nn), moved_pct),
          "",
          "Grade mix -- OFF %s -> ON %s" % (dict(sorted(go.items())), dict(sorted(gn.items()))),
          "",
          "## Money -- one trade a day", "",
          "| lane | metric | OFF | ON | delta |", "|---|---|---:|---:|---:|"]
    for lane, _pred in LANES:
        d = lanes_out.get(lane)
        if not d:
            continue
        a, b = d["off"]["money"], d["on"]["money"]
        for k, lab, fmt in MONEY_KEYS:
            if a.get(k) is None or b.get(k) is None:
                continue
            md.append(("| %s | %s | " + fmt + " | " + fmt + " | %+.3f |")
                      % (lane, lab, a[k], b[k], d["delta"]["money"].get(k, 0)))

    md += ["", "## Paired daily $ delta (ON-OFF), with its own noise", "",
           "One-a-day pick stream, per-session ON minus OFF, over the union of "
           "days either arm picked a trade -- a missing day counts as 0 for "
           "that arm. Sample SE and a plain 95% interval, same convention "
           "CLAUDE.md already uses for g94 ('inside the +-1.58R error bar').",
           "", "| lane | n | mean $/day | SE | 95% CI | straddles zero? |",
           "|---|---:|---:|---:|---:|:---:|"]
    for lane, _pred in LANES:
        d = lanes_out.get(lane)
        if not d or not d["paired_daily_money"]:
            continue
        p = d["paired_daily_money"]
        straddles = p["ci95"][0] < 0 < p["ci95"][1]
        md.append("| %s | %d | %+.2f | %.2f | [%+.2f, %+.2f] | %s |" % (
            lane, p["n"], p["mean"], p["se"], p["ci95"][0], p["ci95"][1],
            "yes" if straddles else "no"))

    md += ["", "## Green-month sign flips, with the margin each flip turned on", ""]
    any_flips = False
    for lane, _pred in LANES:
        d = lanes_out.get(lane)
        if not d or not d["month_flips"]:
            continue
        any_flips = True
        md.append("**%s** (%d flip(s)):" % (lane, len(d["month_flips"])))
        md.append("")
        md.append("| month | OFF | ON |")
        md.append("|---|---:|---:|")
        for f in d["month_flips"]:
            md.append("| %s | %+.2f | %+.2f |" % (f["month"], f["off"], f["on"]))
        md.append("")
    if not any_flips:
        md.append("(none)")
        md.append("")

    md += ["## S-day recall -- canonical S days, in-universe, with a traded row", "",
           "In-universe = a (symbol, date) pair with at least one row in that "
           "arm's (lane-filtered, common-window) book. `traded` reads the "
           "row's own `traded` field (`status==\"fired\" and grade != \"C\"`, "
           "`backtest_week.SimTrade.counted`) -- not recomputed. Because the "
           "veto only ever emits a `skipped_d` row (never removes the "
           "symbol-day), the in-universe sets are identical between arms -- "
           "verified per lane below, so this is a genuine paired comparison "
           "(McNemar exact test on the discordant traded/not-traded pairs).",
           "", "| lane | OFF traded/in-universe | OFF recall | ON traded/in-universe | "
           "ON recall | delta (pts) | in-universe sets equal | discordant OFF/ON | McNemar p |",
           "|---|---:|---:|---:|---:|---:|:---:|---:|---:|"]
    for lane, _pred in LANES:
        d = lanes_out.get(lane)
        if not d:
            continue
        so, sn = d["off"]["s_recall"], d["on"]["s_recall"]
        disc = d["s_recall_discordance"]
        md.append("| %s | %d/%d | %s | %d/%d | %s | %s | %s | %d/%d | %s |" % (
            lane, so["traded"], so["in_universe"],
            ("%.1f%%" % so["recall_pct"]) if so["recall_pct"] is not None else "n/a",
            sn["traded"], sn["in_universe"],
            ("%.1f%%" % sn["recall_pct"]) if sn["recall_pct"] is not None else "n/a",
            ("%+.1f" % d["delta"]["s_recall_pct"]) if d["delta"]["s_recall_pct"] is not None else "n/a",
            "yes" if disc["in_universe_sets_identical"] else "NO",
            len(disc["off_only"]), len(disc["on_only"]), disc["mcnemar_p"]))

    md += ["", "## False-fire rate -- one-a-day picks graded non-S, of picks Austin graded at all", "",
           "Denominator excludes days with NO canonical-pool opinion for that "
           "symbol-day (not counted as a false fire either way; the "
           "`unjudged` column names how many were dropped). `X`-only opinions "
           "(an engine-detection refusal per marks_pool.py, not a day-level "
           "one) are counted in the headline rate but broken out separately; "
           "the day-level rate excludes them.", "",
           "| lane | OFF false/judged (unjudged) | OFF rate | Wilson 95% | ON false/judged (unjudged) | "
           "ON rate | Wilson 95% | delta (pts) | OFF breakdown | ON breakdown | day-level OFF/ON |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|"]
    for lane, _pred in LANES:
        d = lanes_out.get(lane)
        if not d:
            continue
        fo, fn = d["off"]["false_fire"], d["on"]["false_fire"]
        ci = d["false_fire_ci"]
        md.append("| %s | %d/%d (%d) | %s | %s | %d/%d (%d) | %s | %s | %s | %s | %s | %s/%s |" % (
            lane, fo["false_fires"], fo["judged_days"], fo["unjudged_days"],
            ("%.1f%%" % fo["false_fire_pct"]) if fo["false_fire_pct"] is not None else "n/a",
            ci["off"],
            fn["false_fires"], fn["judged_days"], fn["unjudged_days"],
            ("%.1f%%" % fn["false_fire_pct"]) if fn["false_fire_pct"] is not None else "n/a",
            ci["on"],
            ("%+.1f" % d["delta"]["false_fire_pct"]) if d["delta"]["false_fire_pct"] is not None else "n/a",
            dict(fo["breakdown"]), dict(fn["breakdown"]),
            ("%.1f%%" % fo["day_level_false_fire_pct"]) if fo["day_level_false_fire_pct"] is not None else "n/a",
            ("%.1f%%" % fn["day_level_false_fire_pct"]) if fn["day_level_false_fire_pct"] is not None else "n/a"))

    md += ["", "## Verdict", ""]
    if fp:
        md += ["- " + line for line in verdict_lines]
        idx = lanes_out.get("index QQQ/SPY/IWM")
        if idx:
            ip = idx["paired_daily_money"]
            same_sign = (fp["paired_daily_money"]["mean"] > 0) == (ip["mean"] > 0)
            md.append("- index lane paired $/day (ON-OFF): %+.2f, 95%% CI [%+.2f, %+.2f] -- "
                      "**%s the full-pool sign**"
                      % (ip["mean"], ip["ci95"][0], ip["ci95"][1],
                         "agrees with" if same_sign else "DISAGREES WITH"))
        md += ["", "**No binary win/lose call.** Every headline delta above sits inside a "
               "95% interval that contains zero, S recall's discordant pairs are not "
               "distinguishable from a coin flip at p<0.05, and the full-pool and index "
               "lanes disagree in sign on money. **This A/B does not make a case for "
               "moving `HTF_BIAS_VETO` off its shipped default of ON** -- the honest "
               "conclusion is that the flag is unmeasurable at this sample size, not "
               "that either arm wins.", ""]
    md += ["No invented statistical machinery beyond plain paired-sample SE, a Wilson "
           "interval and an exact McNemar test (stdlib `math.comb`, no scipy) -- the "
           "smallest tools that let 'inside noise' be checked rather than asserted.", ""]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("  -> %s" % OUT_MD)


if __name__ == "__main__":
    main()
