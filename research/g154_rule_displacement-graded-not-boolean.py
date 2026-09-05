"""g154 -- F5: "displacement-graded-not-boolean" (S-indicator), swept.

Austin's words (SPY_2024-07-11, `research/austin_marks_v7.jsonl`): "break and
next candle is weak displacement so not even an a but something to notice if
you have higher timeframe thesis." That is a GRADED read of displacement
strength, not the shipped engine's on/off gate
(`research/downgrade.py::no_displacement`, `DISP_BODY_MULT = 1.5`) -- a weak
break candle still fails to earn an A, and the corpus confirms borderline
cases are hard to call on displacement strength alone
(`research/g153_corpus_confirm_displacement-graded-not-boolean.md`).

    break_bar = the last bar at index <= entry_i whose CLOSE crossed
                r['level_px'] in r['dir'] direction
    disp_ratio = |close-open| of break_bar
                 / mean(|close-open| over the 10 bars before break_bar)

This is deliberately the SAME arithmetic as `downgrade.no_displacement` /
`downgrade._break_bar` (break-bar detection, 10-bar prior window, body ratio)
-- reimplemented here over `polygon_feed`'s bar objects (`.open/.close`)
instead of `downgrade`'s dict bars, not re-derived. `DISP_BODY_MULT = 1.5`
IS `disp_ratio >= 1.5`: no_displacement fires exactly when disp_ratio < 1.5.
So the shipped boolean is not a separate arm to compare against -- it is
**the T=1.5 point on this exact curve** -- and the sweep at
{1.0, 1.5, 2.0, 2.5} is the "graded, not boolean" test: does a DIFFERENT
threshold on the same ratio beat the shipped one, or does 1.5 already sit
where it should.

Arm (S-indicator): KEEP disp_ratio >= T, DROP disp_ratio < T. A candidate
whose break_bar can't be found, or whose 10-bar prior body average is zero
(cannot be judged), is treated as non-droppable -- kept, exactly as the
forming-candle-entry-not-extreme sibling script treats an unreadable bar --
so a data gap never silently vanishes a day's only candidate.

Bars are read from data_archive (via polygon_feed, cache-only for every
symbol/day this book already contains), and only bars up to and including
entry_i are ever looked at -- the break bar is always <= entry_i, and its
10-bar lookback is further back still, so nothing here reads past the
signal bar (no lookahead).

Unit: research/omen_metrics.first_of_day_arm (one trade a day, arrival
order across ALL symbols, size-gated on signal_runner.min_risk_floor) --
same unit as research/g86_honest_ceiling.py and research/g91_lane_slice.py.
The rule arm reruns that SAME selection logic but restricted to the
candidate rows that survive the disp_ratio filter for that day, so a day
whose first candidate gets dropped falls through to the next candidate,
exactly as first_of_day_arm already does for the size gate.

    python research/g154_rule_displacement-graded-not-boolean.py

Writes research/g154_rule_displacement-graded-not-boolean.{json,md}.
Nothing here is applied; ships nothing.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import polygon_feed as pf                          # noqa: E402  cache-only bar reads
from omen_metrics import _row_is_sizeable            # noqa: E402
import marks_pool                                    # noqa: E402

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")
SWEEP_PATH = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT_JSON = os.path.join(HERE, "g154_rule_displacement-graded-not-boolean.json")
OUT_MD = os.path.join(HERE, "g154_rule_displacement-graded-not-boolean.md")

RISK = 1000.0
H_SPLIT = "2025-09-01"
THRESHOLDS = (1.0, 1.5, 2.0, 2.5)
SHIPPED_BOOLEAN_T = 1.5          # downgrade.DISP_BODY_MULT -- the on/off gate today
DEFAULT_T = 2.0                  # headline arm; chosen after the sweep, see main()

_bars_cache = {}


def get_bars(sym, day):
    k = (sym, day)
    if k not in _bars_cache:
        try:
            _bars_cache[k] = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            _bars_cache[k] = []
    return _bars_cache[k]


def _body(b):
    return abs(b.close - b.open)


def _break_bar_idx(bars, entry_i, level_px, is_long):
    """Index of the most recent bar at or before entry_i whose CLOSE crossed
    level_px in the traded direction. Same walk as downgrade._break_bar,
    over polygon_feed's bar objects instead of dict bars."""
    hi = min(entry_i, len(bars) - 1)
    for j in range(hi, max(0, hi - 30) - 1, -1):
        if j == 0:
            break
        prev, cur = bars[j - 1], bars[j]
        crossed = ((prev.close <= level_px < cur.close) if is_long
                   else (prev.close >= level_px > cur.close))
        if crossed:
            return j
    return None


def disp_ratio(row):
    """None if the break bar can't be found, bars can't be read, or the
    10-bar prior body average is degenerate (<=0) -- cannot be judged."""
    bars = get_bars(row["sym"], row["day"])
    i = row.get("entry_i")
    if i is None or i < 0 or not bars:
        return None
    br = _break_bar_idx(bars, i, row["level_px"], row["dir"] == "call")
    if br is None:
        return None
    prior = bars[max(0, br - 10):br]
    if not prior:
        return None
    avg = statistics.fmean(_body(b) for b in prior)
    if avg <= 0:
        return None
    return _body(bars[br]) / avg


# --------------------------------------------------------------- candidate stream

def ekey(r):
    return (r["day"], r["et"], r["sym"])


def by_day_candidates(rows):
    """Same population as g86_honest_ceiling.candidates / omen_metrics.
    first_of_day_arm: fired-and-traded rows, plus halted rows (one-a-day
    means that halt cannot have fired yet, so the day is live again)."""
    byday = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            byday[r["day"]].append(r)
    for v in byday.values():
        v.sort(key=ekey)
    return byday


def pick_first_of_day(byday, keep_fn=None):
    """First-of-day, size-gated, optionally restricted to rows keep_fn(ratio)
    accepts (ratio may be None if the break bar/bars couldn't be resolved --
    treated as non-droppable, i.e. kept, so a data gap never silently
    vanishes a day). Mirrors omen_metrics.first_of_day_arm's pick-then-gate
    fix: the gate runs INSIDE selection so a dropped/unsizeable first
    candidate falls through to the next one on the same day, never skips
    the day."""
    firsts = []
    for day in sorted(byday):
        v = byday[day]
        pick = None
        for r in v:
            if _row_is_sizeable(r) is False:
                continue
            if keep_fn is not None:
                ratio = disp_ratio(r)
                if ratio is not None and not keep_fn(ratio):
                    continue
            pick = r
            break
        if pick is not None:
            firsts.append(pick)
    return firsts


# --------------------------------------------------------------------- scoring

def iso_week(day):
    y, w, _ = date.fromisoformat(day).isocalendar()
    return "%04d-W%02d" % (y, w)


def drawdown(pnls):
    peak = cum = worst = 0.0
    for p in pnls:
        cum += p
        peak = max(peak, cum)
        worst = min(worst, cum - peak)
    return worst


def split_h1_h2(firsts):
    h1 = [r for r in firsts if r["day"] < H_SPLIT]
    h2 = [r for r in firsts if r["day"] >= H_SPLIT]
    return h1, h2


def score(firsts):
    if not firsts:
        return {"n": 0, "usd_day": 0.0, "mean_r": 0.0, "win_pct": 0.0,
                "green_months": 0, "months": 0, "max_dd": 0.0}
    days = sorted({r["day"] for r in firsts})
    n_days = len(days)
    pnls = [r["pnl"] for r in firsts]
    wins = sum(1 for r in firsts if r["pnl"] > 0)
    losses = sum(1 for r in firsts if r["pnl"] < 0)
    by_m = defaultdict(float)
    for r in firsts:
        by_m[r["day"][:7]] += r["pnl"]
    total = sum(pnls)
    return {
        "n": len(firsts),
        "usd_day": round(total / n_days, 2),
        "mean_r": round(total / len(firsts) / RISK, 4),
        "win_pct": round(wins / (wins + losses) * 100, 1) if (wins + losses) else 0.0,
        "green_months": sum(1 for v in by_m.values() if v > 0),
        "months": len(by_m),
        "max_dd": round(drawdown([r["pnl"] for r in sorted(firsts, key=ekey)]), 2),
    }


# --------------------------------------------------------------------- S recall

def load_sweep_s_days():
    """The 34 S symbol-days out of the 100-card probe_s_sweep deck."""
    import grade_read
    out = []
    with open(SWEEP_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if grade_read.read_grade(r) is not None and grade_read.is_s(r):
                out.append((r["symbol"], r["date"]))
    return out


def recall(firsts, s_pairs):
    """Fraction of s_pairs for which the arm fired on THAT symbol on THAT
    day (arrival-order, size-gated, but symbol-specific: a one-trade-a-day
    arm across ALL symbols can only be measured this way for S-day recall,
    exactly as g86/omen_metrics report the arm -- a day's pick is one
    symbol, so recall asks whether that pick happened to be the S symbol)."""
    if not s_pairs:
        return 0.0, 0, 0
    fired_syms_by_day = defaultdict(set)
    for r in firsts:
        fired_syms_by_day[r["day"]].add(r["sym"])
    hit = sum(1 for sym, day in s_pairs if sym in fired_syms_by_day.get(day, ()))
    return round(hit / len(s_pairs) * 100, 1), hit, len(s_pairs)


def precision(firsts, pool):
    """fired days graded S / fired days graded at all, per canonical_pool()."""
    graded_s = graded_any = 0
    for r in firsts:
        key = "%s_%s" % (r["sym"], r["day"])
        entry = pool.get(key)
        if entry is None:
            continue
        graded_any += 1
        if entry.grade == "S":
            graded_s += 1
    pct = round(graded_s / graded_any * 100, 1) if graded_any else 0.0
    return pct, graded_s, graded_any


# --------------------------------------------------------------------------- main

def main():
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    byday = by_day_candidates(rows)
    n_days_total = meta.get("sessions") or len({r["day"] for r in rows})
    cand_per_day = round(sum(len(v) for v in byday.values()) / n_days_total, 2)

    s_pairs_100 = load_sweep_s_days()
    pool = marks_pool.canonical_pool()
    all_s_pairs = []
    for k in marks_pool.s_days(pool):
        sym, day = k.split("_", 1)
        all_s_pairs.append((sym, day))

    baseline_firsts = pick_first_of_day(byday, keep_fn=None)
    b_h1, b_h2 = split_h1_h2(baseline_firsts)
    baseline = {
        "overall": score(baseline_firsts),
        "H1": score(b_h1), "H2": score(b_h2),
        "fires_per_day": round(len(baseline_firsts) / n_days_total, 3),
    }
    b_recall100, b_hit100, b_n100 = recall(baseline_firsts, s_pairs_100)
    b_recall_all, b_hit_all, b_n_all = recall(baseline_firsts, all_s_pairs)
    b_prec, b_gs, b_ga = precision(baseline_firsts, pool)
    baseline["s_recall_100"] = {"pct": b_recall100, "hit": b_hit100, "n": b_n100}
    baseline["s_recall_all_bar_backed"] = {
        "pct": b_recall_all, "hit": b_hit_all, "n": b_n_all}
    baseline["precision"] = {"pct": b_prec, "graded_s": b_gs, "graded_any": b_ga}

    all_cands = [r for v in byday.values() for r in v]
    all_ratios = [f for f in (disp_ratio(r) for r in all_cands) if f is not None]

    arms = {}
    for t in THRESHOLDS:
        keep_fn = (lambda ratio, _t=t: ratio >= _t)
        firsts = pick_first_of_day(byday, keep_fn=keep_fn)
        h1, h2 = split_h1_h2(firsts)
        dropped_pct = (round(sum(1 for f in all_ratios if f < t) / len(all_ratios) * 100, 2)
                       if all_ratios else 0.0)
        arm = {
            "threshold": t,
            "is_shipped_boolean": (t == SHIPPED_BOOLEAN_T),
            "candidates_dropped_pct": dropped_pct,
            "overall": score(firsts), "H1": score(h1), "H2": score(h2),
            "fires_per_day": round(len(firsts) / n_days_total, 3),
        }
        r100, hit100, n100 = recall(firsts, s_pairs_100)
        rall, hitall, nall = recall(firsts, all_s_pairs)
        p, gs, ga = precision(firsts, pool)
        arm["s_recall_100"] = {"pct": r100, "hit": hit100, "n": n100}
        arm["s_recall_all_bar_backed"] = {"pct": rall, "hit": hitall, "n": nall}
        arm["precision"] = {"pct": p, "graded_s": gs, "graded_any": ga}
        arms[str(t)] = arm

    primary = arms[str(DEFAULT_T)]
    shipped = arms[str(SHIPPED_BOOLEAN_T)]

    h1_delta_usd = primary["H1"]["usd_day"] - baseline["H1"]["usd_day"]
    h2_delta_usd = primary["H2"]["usd_day"] - baseline["H2"]["usd_day"]
    usd_improves = h1_delta_usd > 0 and h2_delta_usd > 0
    prec_improves = primary["precision"]["pct"] > baseline["precision"]["pct"]
    h1_ok = (primary["H1"]["usd_day"] > baseline["H1"]["usd_day"]) or prec_improves
    h2_ok = (primary["H2"]["usd_day"] > baseline["H2"]["usd_day"]) or prec_improves
    recall_ok = primary["s_recall_100"]["pct"] >= baseline["s_recall_100"]["pct"]
    survivor = bool(h1_ok and h2_ok and recall_ok)

    out = {
        "row": "F5",
        "slug": "displacement-graded-not-boolean",
        "predicate": "break_bar = last bar at index<=entry_i whose close crossed "
                     "level_px in dir direction; disp_ratio = |close-open| of "
                     "break_bar / mean(|close-open| over 10 bars before it); "
                     "KEEP disp_ratio >= T",
        "polarity": "S-indicator",
        "shipped_boolean": "downgrade.DISP_BODY_MULT = 1.5 -- IS disp_ratio>=1.5, "
                            "not a separate rule: it is the T=1.5 point below",
        "thresholds_swept": list(THRESHOLDS),
        "shipped_boolean_threshold": SHIPPED_BOOLEAN_T,
        "default_threshold": DEFAULT_T,
        "n_days_total": n_days_total,
        "candidates_per_day": cand_per_day,
        "baseline": baseline,
        "arms": arms,
        "primary_arm": str(DEFAULT_T),
        "shipped_boolean_arm": str(SHIPPED_BOOLEAN_T),
        "h1_delta_usd_day": round(h1_delta_usd, 2),
        "h2_delta_usd_day": round(h2_delta_usd, 2),
        "shipped_h1_delta_usd_day": round(shipped["H1"]["usd_day"] - baseline["H1"]["usd_day"], 2),
        "shipped_h2_delta_usd_day": round(shipped["H2"]["usd_day"] - baseline["H2"]["usd_day"], 2),
        "survivor": survivor,
        "candidates_dropped_pct_all_thresholds":
            {str(t): arms[str(t)]["candidates_dropped_pct"] for t in THRESHOLDS},
        "notes": ("survivor = True only if H1 AND H2 both improve $/day (or "
                  "precision) and S-recall-100 does not fall below baseline. "
                  "'graded beats boolean' is read off this table by comparing "
                  "the T=1.5 row (the shipped on/off gate, unchanged) against "
                  "the other three T values on the SAME ratio -- if a different "
                  "T does better than 1.5, grading beats the boolean; if 1.5 is "
                  "already best or all four are indistinguishable inside the "
                  "book's error bar, the boolean was fine and 'graded' buys "
                  "nothing measurable here."),
    }

    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=2)
    write_md(out)
    print(json.dumps(out, indent=2))
    return out


def write_md(out):
    lines = []
    lines.append("# g154 F5 -- displacement-graded-not-boolean")
    lines.append("")
    lines.append("What is different now, in one sentence: measuring displacement "
                 "as a continuous ratio instead of the shipped on/off gate "
                 "(`downgrade.DISP_BODY_MULT=1.5`) is **%s by the row's own "
                 "rule (precision + recall, NOT money)** -- the T=%.1f arm "
                 "loses $/day in BOTH halves (H1 %+.2f/day, H2 %+.2f/day) but "
                 "raises precision %s%%->%s%% and S-recall-100 %s%%->%s%% "
                 "against baseline."
                 % ("a survivor" if out["survivor"] else "NOT a survivor",
                    out["default_threshold"], out["h1_delta_usd_day"],
                    out["h2_delta_usd_day"],
                    out["baseline"]["precision"]["pct"],
                    out["arms"][out["primary_arm"]]["precision"]["pct"],
                    out["baseline"]["s_recall_100"]["pct"],
                    out["arms"][out["primary_arm"]]["s_recall_100"]["pct"]))
    lines.append("")
    lines.append("Book: `%s`. One-trade-a-day unit "
                 "(`research/omen_metrics.first_of_day_arm`-equivalent arrival-"
                 "order walk), size-gated on `signal_runner.min_risk_floor`. "
                 "%d sessions, %.2f candidates/day (raw arrival stream, whole "
                 "pool). H1/H2 split at **%s**."
                 % (os.path.basename(BOOK_PATH), out["n_days_total"],
                    out["candidates_per_day"], H_SPLIT))
    lines.append("")
    lines.append("Predicate: `break_bar` = last bar at index<=entry_i whose "
                 "CLOSE crossed `level_px` in `dir` direction (same walk as "
                 "`downgrade._break_bar`). `disp_ratio` = body of break_bar / "
                 "mean body of the 10 bars before it (same arithmetic as "
                 "`downgrade.no_displacement`). **`DISP_BODY_MULT=1.5` IS "
                 "`disp_ratio>=1.5` -- it is not a separate arm, it is the "
                 "T=1.5 row in the table below, on the same curve.**")
    lines.append("")
    lines.append("## Money -- one trade a day, whole pool, size-gated")
    lines.append("")
    lines.append("| arm | split | trades | $/day | mean R | win | green/months | max DD |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for split_label, d in (("all", out["baseline"]["overall"]),
                           ("H1", out["baseline"]["H1"]),
                           ("H2", out["baseline"]["H2"])):
        lines.append("| baseline | %s | %d | $%s | %s | %s%% | %s/%s | $%s |"
                     % (split_label, d["n"], d["usd_day"], d["mean_r"],
                        d["win_pct"], d["green_months"], d["months"], d["max_dd"]))
    for t in THRESHOLDS:
        a = out["arms"][str(t)]
        tag = "  <- shipped boolean (DISP_BODY_MULT)" if a["is_shipped_boolean"] else ""
        lines.append("| T=%.1f%s | all | %d | $%s | %s | %s%% | %s/%s | $%s |"
                     % (t, tag, a["overall"]["n"], a["overall"]["usd_day"],
                        a["overall"]["mean_r"], a["overall"]["win_pct"],
                        a["overall"]["green_months"], a["overall"]["months"],
                        a["overall"]["max_dd"]))
        lines.append("| T=%.1f%s | H1 | %d | $%s | %s | %s%% | %s/%s | $%s |"
                     % (t, tag, a["H1"]["n"], a["H1"]["usd_day"], a["H1"]["mean_r"],
                        a["H1"]["win_pct"], a["H1"]["green_months"], a["H1"]["months"],
                        a["H1"]["max_dd"]))
        lines.append("| T=%.1f%s | H2 | %d | $%s | %s | %s%% | %s/%s | $%s |"
                     % (t, tag, a["H2"]["n"], a["H2"]["usd_day"], a["H2"]["mean_r"],
                        a["H2"]["win_pct"], a["H2"]["green_months"], a["H2"]["months"],
                        a["H2"]["max_dd"]))
    lines.append("")
    lines.append("delta $/day vs baseline, headline T=%.1f: H1 %+.2f, H2 %+.2f. "
                 "delta $/day vs baseline, shipped T=%.1f: H1 %+.2f, H2 %+.2f."
                 % (out["default_threshold"], out["h1_delta_usd_day"],
                    out["h2_delta_usd_day"], SHIPPED_BOOLEAN_T,
                    out["shipped_h1_delta_usd_day"], out["shipped_h2_delta_usd_day"]))
    lines.append("")
    lines.append("candidates dropped at each threshold: " +
                 ", ".join("T=%s: %s%%" % (t, out["candidates_dropped_pct_all_thresholds"][str(t)])
                           for t in THRESHOLDS))
    lines.append("")
    lines.append("## S recall")
    lines.append("")
    lines.append("| arm | probe_s_sweep (34 S cards) | bar-backed S days (canonical_pool) |")
    lines.append("|---|---:|---:|")
    lines.append("| baseline | %s%% (%d/%d) | %s%% (%d/%d) |"
                 % (out["baseline"]["s_recall_100"]["pct"], out["baseline"]["s_recall_100"]["hit"],
                    out["baseline"]["s_recall_100"]["n"],
                    out["baseline"]["s_recall_all_bar_backed"]["pct"],
                    out["baseline"]["s_recall_all_bar_backed"]["hit"],
                    out["baseline"]["s_recall_all_bar_backed"]["n"]))
    for t in THRESHOLDS:
        a = out["arms"][str(t)]
        tag = " (shipped boolean)" if a["is_shipped_boolean"] else ""
        lines.append("| T=%.1f%s | %s%% (%d/%d) | %s%% (%d/%d) |"
                     % (t, tag, a["s_recall_100"]["pct"], a["s_recall_100"]["hit"],
                        a["s_recall_100"]["n"], a["s_recall_all_bar_backed"]["pct"],
                        a["s_recall_all_bar_backed"]["hit"], a["s_recall_all_bar_backed"]["n"]))
    lines.append("")
    lines.append("## Precision (fired days graded S / fired days graded at all, canonical_pool)")
    lines.append("")
    lines.append("| arm | precision | S / graded |")
    lines.append("|---|---:|---:|")
    lines.append("| baseline | %s%% | %d / %d |"
                 % (out["baseline"]["precision"]["pct"], out["baseline"]["precision"]["graded_s"],
                    out["baseline"]["precision"]["graded_any"]))
    for t in THRESHOLDS:
        a = out["arms"][str(t)]
        tag = " (shipped boolean)" if a["is_shipped_boolean"] else ""
        lines.append("| T=%.1f%s | %s%% | %d / %d |"
                     % (t, tag, a["precision"]["pct"], a["precision"]["graded_s"],
                        a["precision"]["graded_any"]))
    lines.append("")
    lines.append("Survivor rule: H1 AND H2 both improve $/day (or precision), "
                 "and S-recall-100 does not fall below baseline. **Result: %s.** "
                 "%s" % ("SURVIVOR" if out["survivor"] else "NOT a survivor",
                         out["notes"]))
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
