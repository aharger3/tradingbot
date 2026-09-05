"""g154 -- F5: "scratch-exit-direction-match" (S-indicator), descriptive split.

Candidate rule: "A scratch-exit rule should require the entry candle's
direction to match the prevailing trend before it can fire." Source: one
rule-ballot row, "im ok with implementing scratch" -- a CONDITIONAL yes on a
scratch-exit feature that does not exist anywhere in this codebase (grep for
"scratch" in backtest_week.py / stop_rule.py / signal_runner.py finds nothing
that exits a trade early on a partial-credit basis). There is therefore no
scratch exit to gate. This is a DESCRIPTIVE SPLIT ONLY: does the entry
candle's own direction (bullish/bearish close) agree with the signal's
trade direction (call/put), and if so does that split separate anything --
S-rate, realized R -- in the book we already have? If the split is flat, the
precondition the ballot conditioned its "yes" on is moot and the feature
should not be built on this basis.

    entry_dir  = sign(Close[entry_i] - Open[entry_i])   (bar's own candle color)
    trend_dir  = +1 for r["dir"] == "call", -1 for r["dir"] == "put"
    match      = entry_dir == trend_dir  (entry candle prints WITH the trade
                 direction: a green candle on a long, a red candle on a short)

Bars are read from data_archive (via polygon_feed, cache-only) for
bars[entry_i] ONLY -- the signal bar itself, already fully printed at
close-fill, so this is not lookahead.

Two things are reported:

  1. THE DESCRIPTIVE SPLIT (what the row actually asks for): S rate and mean
     realized R for entry_dir==trend_dir vs entry_dir!=trend_dir, over every
     candidate in the book (not just first-of-day), against marks_pool's
     canonical grades.
  2. A SELECTION ARM built the same way every other g154 script builds one,
     for comparability: S-indicator polarity keeps only match==True
     candidates (drops mismatches; a dropped first-of-day candidate falls
     through to the next one, same as omen_metrics.first_of_day_arm).

Unit: research/omen_metrics.first_of_day_arm (one trade a day, arrival
order across ALL symbols, size-gated on signal_runner.min_risk_floor) --
same unit as research/g86_honest_ceiling.py and research/g91_lane_slice.py.

    python research/g154_rule_scratch-exit-direction-match.py

Writes research/g154_rule_scratch-exit-direction-match.{json,md}.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import polygon_feed as pf                              # noqa: E402  cache-only bar reads
from omen_metrics import _row_is_sizeable               # noqa: E402
import marks_pool                                        # noqa: E402
import grade_read                                         # noqa: E402

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")
SWEEP_PATH = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT_JSON = os.path.join(HERE, "g154_rule_scratch-exit-direction-match.json")
OUT_MD = os.path.join(HERE, "g154_rule_scratch-exit-direction-match.md")

RISK = 1000.0
H_SPLIT = "2025-09-01"

_bars_cache = {}


def get_bars(sym, day):
    k = (sym, day)
    if k not in _bars_cache:
        try:
            _bars_cache[k] = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            _bars_cache[k] = []
    return _bars_cache[k]


def direction_match(row):
    """True/False if entry_dir and trend_dir compare, else None (bar
    unreadable, entry_i out of range, or a doji -- open==close, no
    direction to read)."""
    bars = get_bars(row["sym"], row["day"])
    i = row.get("entry_i")
    if i is None or i < 0 or i >= len(bars):
        return None
    b = bars[i]
    if b.close == b.open:
        return None
    entry_dir = 1 if b.close > b.open else -1
    trend_dir = 1 if row["dir"] == "call" else -1
    return entry_dir == trend_dir


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


def pick_first_of_day(byday, keep_matches_only):
    """First-of-day, size-gated, optionally restricted to candidates whose
    direction_match() is True (an unreadable/doji bar returns None and is
    never dropped, so an unreadable bar never silently vanishes a day).
    Mirrors omen_metrics.first_of_day_arm's pick-then-gate fix: the gate
    runs INSIDE selection so a dropped/unsizeable first candidate falls
    through to the next one on the same day, never skips the day."""
    firsts = []
    for day in sorted(byday):
        v = byday[day]
        pick = None
        for r in v:
            if _row_is_sizeable(r) is False:
                continue
            if keep_matches_only:
                m = direction_match(r)
                if m is False:
                    continue
            pick = r
            break
        if pick is not None:
            firsts.append(pick)
    return firsts


# --------------------------------------------------------------------- scoring

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
    out = []
    with open(SWEEP_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if grade_read.read_grade(r) == "S":
                out.append((r["symbol"], r["date"]))
    return out


def recall(firsts, s_pairs):
    """Fraction of s_pairs for which the arm fired on THAT symbol on THAT
    day (arrival-order, size-gated)."""
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


# --------------------------------------------------------------- descriptive split

def descriptive_split(all_cands, pool):
    """S rate and realized mean R for match==True vs match==False, over
    EVERY candidate in the book (not just first-of-day) -- this is what
    the row actually asks for: does the split separate anything at all."""
    buckets = {"match": [], "mismatch": [], "unreadable": 0}
    for r in all_cands:
        m = direction_match(r)
        if m is None:
            buckets["unreadable"] += 1
            continue
        (buckets["match"] if m else buckets["mismatch"]).append(r)

    def bucket_stats(rows):
        n = len(rows)
        if n == 0:
            return {"n": 0, "mean_r": 0.0, "s_rate_pct": None,
                     "graded_s": 0, "graded_any": 0}
        mean_r = round(sum(r["r"] for r in rows) / n, 4)
        gs = ga = 0
        for r in rows:
            key = "%s_%s" % (r["sym"], r["day"])
            entry = pool.get(key)
            if entry is None:
                continue
            ga += 1
            if entry.grade == "S":
                gs += 1
        s_rate = round(gs / ga * 100, 1) if ga else None
        return {"n": n, "mean_r": mean_r, "s_rate_pct": s_rate,
                 "graded_s": gs, "graded_any": ga}

    return {
        "match": bucket_stats(buckets["match"]),
        "mismatch": bucket_stats(buckets["mismatch"]),
        "unreadable_or_doji": buckets["unreadable"],
    }


# --------------------------------------------------------------------------- main

def main():
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    byday = by_day_candidates(rows)
    n_days_total = meta.get("sessions") or len({r["day"] for r in rows})
    all_cands = [r for v in byday.values() for r in v]
    cand_per_day = round(len(all_cands) / n_days_total, 2)

    pool = marks_pool.canonical_pool()
    s_pairs_100 = load_sweep_s_days()
    all_s_pairs = []
    for k in marks_pool.s_days(pool):
        sym, day = k.split("_", 1)
        all_s_pairs.append((sym, day))

    split = descriptive_split(all_cands, pool)

    def build_arm(keep_matches_only):
        firsts = pick_first_of_day(byday, keep_matches_only)
        h1, h2 = split_h1_h2(firsts)
        arm = {
            "overall": score(firsts), "H1": score(h1), "H2": score(h2),
            "fires_per_day": round(len(firsts) / n_days_total, 3),
        }
        r100, hit100, n100 = recall(firsts, s_pairs_100)
        rall, hitall, nall = recall(firsts, all_s_pairs)
        p, gs, ga = precision(firsts, pool)
        arm["s_recall_100"] = {"pct": r100, "hit": hit100, "n": n100}
        arm["s_recall_all_bar_backed"] = {"pct": rall, "hit": hitall, "n": nall}
        arm["precision"] = {"pct": p, "graded_s": gs, "graded_any": ga}
        return arm

    baseline = build_arm(keep_matches_only=False)
    arm_match = build_arm(keep_matches_only=True)

    matched_pct = (round(split["match"]["n"] /
                          (split["match"]["n"] + split["mismatch"]["n"]) * 100, 2)
                   if (split["match"]["n"] + split["mismatch"]["n"]) else 0.0)

    h1_delta_usd = arm_match["H1"]["usd_day"] - baseline["H1"]["usd_day"]
    h2_delta_usd = arm_match["H2"]["usd_day"] - baseline["H2"]["usd_day"]
    usd_improves = h1_delta_usd > 0 and h2_delta_usd > 0
    prec_improves = arm_match["precision"]["pct"] > baseline["precision"]["pct"]
    improves = usd_improves or prec_improves
    recall_ok = arm_match["s_recall_100"]["pct"] >= baseline["s_recall_100"]["pct"]
    survivor = bool(improves and recall_ok)

    # is the descriptive split itself flat? both S-rate and mean-R gaps small.
    m, mm = split["match"], split["mismatch"]
    s_rate_gap = (abs((m["s_rate_pct"] or 0) - (mm["s_rate_pct"] or 0))
                  if m["s_rate_pct"] is not None and mm["s_rate_pct"] is not None
                  else None)
    mean_r_gap = abs(m["mean_r"] - mm["mean_r"])
    flat = (mean_r_gap < 0.05 and (s_rate_gap is None or s_rate_gap < 3.0))

    out = {
        "row": "F5",
        "slug": "scratch-exit-direction-match",
        "predicate": ("entry_dir = sign(Close[entry_i]-Open[entry_i]) vs "
                      "trend_dir = +1 call/-1 put; match = entry_dir==trend_dir. "
                      "DESCRIPTIVE SPLIT ONLY -- no scratch exit exists in the "
                      "codebase to gate; source is a conditional ballot yes on "
                      "an unbuilt feature."),
        "polarity": "S-indicator",
        "predicate_is_moot_if_flat": True,
        "n_days_total": n_days_total,
        "candidates_per_day": cand_per_day,
        "n_candidates_total": len(all_cands),
        "matched_pct_of_candidates": matched_pct,
        "descriptive_split": split,
        "descriptive_split_flat": flat,
        "baseline": baseline,
        "arm_keep_match_only": arm_match,
        "h1_delta_usd_day": round(h1_delta_usd, 2),
        "h2_delta_usd_day": round(h2_delta_usd, 2),
        "survivor": survivor,
        "notes": (
            "There is no scratch exit anywhere in backtest_week.py / "
            "stop_rule.py / signal_runner.py -- the source is one rule-ballot "
            "row, a CONDITIONAL yes ('im ok with implementing scratch'), not a "
            "built feature to gate. This measures only the stated "
            "precondition: does the entry candle's own color agreeing with "
            "the trade direction separate anything in the book we already "
            "have. %s The descriptive split is %s (mean-R gap %.4f, S-rate "
            "gap %s) -- %s the precondition the ballot's conditional yes "
            "rested on. The selection arm (S-indicator: drop mismatched "
            "candidates, fall through to the next) is reported for "
            "comparability with every other g154 script, not because a "
            "scratch-exit feature exists to attach it to. CAVEAT ON THE "
            "survivor FLAG: the arm drops only %.2f%% of candidates, so its "
            "H1/H2 $/day deltas (%s / %s) are noise-sized, not a substantive "
            "improvement -- the survivor test passes technically but proves "
            "almost nothing on its own; the descriptive split above is the "
            "load-bearing result."
        ) % (
            "%.2f%% of all book candidates print an entry candle matching "
            "the trade direction." % matched_pct,
            "FLAT" if flat else "NOT flat",
            mean_r_gap,
            ("%.1fpp" % s_rate_gap) if s_rate_gap is not None else "n/a",
            "confirming" if flat else "not ruling out",
            100.0 - matched_pct,
            round(h1_delta_usd, 2),
            round(h2_delta_usd, 2),
        ),
    }

    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=2)
    write_md(out)
    print(json.dumps(out, indent=2))
    return out


def _fmt_row(label, d):
    o = d["overall"]
    return ("| %s | %d | $%s | %s | %s%% | %s/%s | $%s |" %
            (label, o["n"], o["usd_day"], o["mean_r"], o["win_pct"],
             o["green_months"], o["months"], o["max_dd"]))


def write_md(out):
    lines = []
    lines.append("# g154 -- F5 scratch-exit-direction-match\n")
    lines.append("**What is different now:** measured whether the entry "
                 "candle's own direction (bullish/bearish close) agreeing "
                 "with the trade direction (call/put) separates anything in "
                 "the book -- S rate, realized R -- since there is no scratch "
                 "exit built anywhere in this codebase for this precondition "
                 "to gate.\n")

    lines.append("## Descriptive split (the row's actual question)\n")
    lines.append("candidates total: %d -- %.2f%% match the trend direction\n" %
                  (out["n_candidates_total"], out["matched_pct_of_candidates"]))
    lines.append("| bucket | n | mean R | S rate |")
    lines.append("|---|---:|---:|---:|")
    for label, key in (("entry_dir == trend_dir", "match"),
                        ("entry_dir != trend_dir", "mismatch")):
        b = out["descriptive_split"][key]
        s = ("%.1f%% (%d/%d)" % (b["s_rate_pct"], b["graded_s"], b["graded_any"])
             if b["s_rate_pct"] is not None else "n/a (0 graded)")
        lines.append("| %s | %d | %s | %s |" % (label, b["n"], b["mean_r"], s))
    lines.append("")
    lines.append("unreadable/doji bars excluded: %d\n" %
                  out["descriptive_split"]["unreadable_or_doji"])
    lines.append("**split is %s** (mean-R gap and S-rate gap both small) -- "
                 "%s\n" % ("FLAT" if out["descriptive_split_flat"] else "NOT flat",
                            "the precondition the rule-ballot's conditional yes "
                            "rested on is moot; a scratch-exit feature should "
                            "not be built on this basis."
                            if out["descriptive_split_flat"] else
                            "there is a real gap; a scratch-exit built on this "
                            "basis is not ruled out by this split alone."))

    lines.append("## Selection arm (for comparability only -- no feature exists to attach it to)\n")
    b, a = out["baseline"], out["arm_keep_match_only"]
    lines.append("| pop | n | $/day | mean R | win | green/mo | max DD |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    lines.append(_fmt_row("baseline overall", b))
    lines.append(_fmt_row("baseline H1", {"overall": b["H1"]}))
    lines.append(_fmt_row("baseline H2", {"overall": b["H2"]}))
    lines.append(_fmt_row("arm overall", a))
    lines.append(_fmt_row("arm H1", {"overall": a["H1"]}))
    lines.append(_fmt_row("arm H2", {"overall": a["H2"]}))
    lines.append("")
    lines.append("candidates/day: %s -- fires/day baseline: %s -- arm: %s" %
                  (out["candidates_per_day"], b["fires_per_day"], a["fires_per_day"]))
    lines.append("S recall (100-card, baseline vs arm): %s%% (%d/%d) vs %s%% (%d/%d)" %
                  (b["s_recall_100"]["pct"], b["s_recall_100"]["hit"], b["s_recall_100"]["n"],
                   a["s_recall_100"]["pct"], a["s_recall_100"]["hit"], a["s_recall_100"]["n"]))
    lines.append("S recall (all bar-backed, baseline vs arm): %s%% (%d/%d) vs %s%% (%d/%d)" %
                  (b["s_recall_all_bar_backed"]["pct"], b["s_recall_all_bar_backed"]["hit"],
                   b["s_recall_all_bar_backed"]["n"],
                   a["s_recall_all_bar_backed"]["pct"], a["s_recall_all_bar_backed"]["hit"],
                   a["s_recall_all_bar_backed"]["n"]))
    lines.append("precision baseline vs arm: %s%% (%d/%d) vs %s%% (%d/%d)\n" %
                  (b["precision"]["pct"], b["precision"]["graded_s"], b["precision"]["graded_any"],
                   a["precision"]["pct"], a["precision"]["graded_s"], a["precision"]["graded_any"]))

    lines.append("## Survivor verdict\n")
    lines.append("H1 delta $/day: %s -- H2 delta $/day: %s" %
                  (out["h1_delta_usd_day"], out["h2_delta_usd_day"]))
    lines.append("**survivor = %s**\n" % out["survivor"])
    lines.append(out["notes"])
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
