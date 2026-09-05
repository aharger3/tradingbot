"""g154/F5 -- "earlier is better, no new entries past ~11:00" (candidate:
entry-time-of-day-early), measured as a selection arm over the committed book.

Austin's claim: "S trades are things I take earlier in the day -- more
volatility, cleaner trends -- and I don't want new entries late in the window
(past ~11:00 is management only)." That is an S-INDICATOR polarity: keep a
candidate only if its entry time is early enough.

STALE-SOURCE CORRECTION (read before trusting the word "floor" anywhere in
this file's history): the claim's original citation was a 09:40 TRADE_FLOOR
that does not exist. `live_scanner.py:759` deleted it, and `backtest_week.py`
never had one -- grep confirms zero hits. Only 487 of this book's 10,830
fired rows fire before 09:40, so a 09:40 cutoff would touch under 5% of the
book. This script therefore does NOT test a floor (removing early entries).
It tests a CEILING: keep only candidates at or before T, for T in
{09:45, 10:00, 10:30}, plus an inert control at T=11:00 (the book's own
SESSION_END -- every entry in the book already has et <= 10:59, so T=11:00
must reproduce the baseline exactly; if it doesn't, this script is broken).

Two arms per T:
  - S-indicator (shipped direction): KEEP r if 09:30 <= r['et'] <= T, take the
    day's first SIZE-GATED survivor of that filtered stream. A day whose only
    candidates arrive after T trades nothing.
  - refusal-indicator (mirror, reported for completeness): the polarity this
    predicate would have if late times were the tell instead -- SKIP r if
    et > T is identical to the S-indicator arm above (there is only one way to
    read a "keep early" ceiling), so what's reported as "refusal" is the
    complementary policy Austin's words do NOT ask for: skip the day's early
    candidates and take the first one AFTER T instead. It exists so a T that
    only helps because late trades are bad on their own (see g110's finding
    below) doesn't get credited to "early is good" by omission.

PRIOR ART, reused not re-derived:
  - research/g86_honest_ceiling.py -- candidates(), stats(), ekey(), RISK.
  - research/g91_lane_slice.py -- the lane-slice pattern (predicate over book
    rows, one-trade-a-day money read).
  - research/g110_time_of_day.py -- already ran a threshold scan on this exact
    book and found the OPPOSITE-signed result: "first at/after 10:40" beat
    "first regardless" ($68/day vs $34/day baseline), i.e. on this book LATE
    candidates carry more edge than early ones, on money alone. That is a
    finding about $/day, not about his S-judgement -- this script's job is to
    check whether an early-only ceiling helps PRECISION/RECALL against his
    marks even if it costs money, which g110 never measured.
  - research/omen_metrics.py -- min_risk_floor size gate (via signal_runner,
    same predicate as g102.sized), first_of_day_arm as the baseline arm.

No lookahead: 'et' is stamped on the book row at signal time, nothing here
reads past the signal bar. No bars feature is computed (the predicate is a
plain field on the row), so "features read data_archive only up to the
signal bar" is satisfied trivially -- no data_archive read happens at all.

    python research/g154_rule_entry-time-of-day-early.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402  candidates/stats/ekey/RISK
import signal_runner as sr                        # noqa: E402  min_risk_floor, imported not reimplemented
from research import marks_pool as mp              # noqa: E402
from research import build_deck as bd              # noqa: E402  mark-file reader

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_JSON = os.path.join(HERE, "g154_rule_entry-time-of-day-early.json")
OUT_MD = os.path.join(HERE, "g154_rule_entry-time-of-day-early.md")
SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")

H_SPLIT = "2025-09-01"       # CLAUDE.md-mandated H1/H2 boundary
THRESHOLDS = ["09:45", "10:00", "10:30", "11:00"]   # 11:00 is the inert control


def sized(r):
    """Same size gate everywhere in this codebase: signal_runner.min_risk_floor,
    read live (g102.sized's own definition), never re-derived."""
    return abs(r["entry"] - r["stop"]) >= sr.min_risk_floor(r["entry"])


def s_indicator_pick(day_rows, T):
    """KEEP r if 09:30 <= et <= T. First sized survivor of the filtered stream,
    or None if the day has no early-enough sized candidate."""
    cands = [r for r in day_rows if sized(r) and "09:30" <= r["et"] <= T]
    return cands[0] if cands else None


def refusal_pick(day_rows, T):
    """Mirror policy: SKIP the early candidates, take the first sized survivor
    AFTER T. Reported for completeness (see module docstring) -- not the
    direction Austin's claim asks for."""
    cands = [r for r in day_rows if sized(r) and r["et"] > T]
    return cands[0] if cands else None


def build_arm(byday, pick_fn, T):
    picks = {}
    for day in sorted(byday):
        r = pick_fn(byday[day], T)
        if r is not None:
            picks[day] = r
    return picks


def baseline_pick(day_rows):
    cands = [r for r in day_rows if sized(r)]
    return cands[0] if cands else None


def n_days_in(rows, lo=None, hi=None):
    days = {r["day"] for r in rows}
    if lo is not None:
        days = {d for d in days if d >= lo}
    if hi is not None:
        days = {d for d in days if d < hi}
    return len(days)


def half_stats(picks, lo=None, hi=None, n_days=None):
    sub = [r for d, r in picks.items() if (lo is None or d >= lo) and (hi is None or d < hi)]
    return g86.stats(sub, n_days)


def s_sweep_keys():
    rows = list(bd._rows(SWEEP))
    return {"%s_%s" % (r["symbol"], r["date"]) for r in rows if mp.row_grade(r) == "S"}, len(rows)


def recall_and_precision(rows, bysd, T, pool, s100_keys, bar_backed_s_all, picks_global):
    """recall_100: of the 34 S cards, how many have a sized-and-early-enough
    candidate somewhere in the book that day (any symbol match to the card's
    own symbol -- the card names one symbol-day). recall_all: same test over
    every bar-backed S day the marks pool knows. precision: of the days the
    GLOBAL one-trade-a-day arm actually fired, what share of the ones graded
    at all were graded S (marks_pool.canonical_pool())."""
    def fires(key):
        rs = bysd.get(key, [])
        return any(sized(r) and "09:30" <= r["et"] <= T for r in rs)

    hit100 = sum(1 for k in s100_keys if fires(k))
    hitall = sum(1 for k in bar_backed_s_all if fires(k))

    grade_num = grade_den = 0
    for day, r in picks_global.items():
        key = "%s_%s" % (r["sym"], day)
        e = pool.get(key)
        if e is None:
            continue
        grade_den += 1
        if e.grade == "S":
            grade_num += 1

    return {
        "recall_100": round(hit100 / len(s100_keys), 4) if s100_keys else None,
        "recall_100_n": len(s100_keys), "recall_100_hits": hit100,
        "recall_all": round(hitall / len(bar_backed_s_all), 4) if bar_backed_s_all else None,
        "recall_all_n": len(bar_backed_s_all), "recall_all_hits": hitall,
        "precision": round(grade_num / grade_den, 4) if grade_den else None,
        "precision_num": grade_num, "precision_den": grade_den,
    }


def main():
    blob = json.load(open(BOOK, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    n_days = meta.get("sessions") or len({r["day"] for r in rows})
    n_days_h1 = n_days_in(rows, hi=H_SPLIT)
    n_days_h2 = n_days_in(rows, lo=H_SPLIT)
    print("book: %s -- %d sessions (H1 %d, H2 %d)"
          % (os.path.basename(BOOK), n_days, n_days_h1, n_days_h2))

    byday = g86.candidates(rows)               # day -> sorted candidate rows, all symbols
    bysd = defaultdict(list)                    # (sym_day key) -> candidate rows
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            bysd["%s_%s" % (r["sym"], r["day"])].append(r)
    for v in bysd.values():
        v.sort(key=g86.ekey)

    pool = mp.canonical_pool()
    s100_keys, s100_n_rows = s_sweep_keys()
    bar_backed_s_all = {k for k in mp.s_days(pool) if pool[k].has_bars}
    print("34-card sweep: %d rows, %d graded S -- bar-backed S days corpus-wide: %d"
          % (s100_n_rows, len(s100_keys), len(bar_backed_s_all)))

    # -------- baseline: first sized candidate of the day, any time --------
    base_picks = build_arm(byday, lambda drows, _T: baseline_pick(drows), None)
    base_full = g86.stats(list(base_picks.values()), n_days)
    base_h1 = half_stats(base_picks, hi=H_SPLIT, n_days=n_days_h1)
    base_h2 = half_stats(base_picks, lo=H_SPLIT, n_days=n_days_h2)
    base_cand_per_day = round(sum(len(v) for v in byday.values()) / n_days, 2)
    base_fires_per_day = round(len(base_picks) / n_days, 3)
    base_rp = recall_and_precision(rows, bysd, "10:59", pool, s100_keys,
                                    bar_backed_s_all, base_picks)

    print("\nBASELINE first-of-day (any time): $%d/day, mean R %.3f, win %.1f%%, "
          "months green %d/%d, maxDD $%d, cand/day %.1f, fires/day %.3f"
          % (base_full["per_day"], base_full["mean_r"], base_full["win_pct"],
             base_full["months_green"], base_full["months"], base_full["worst_drawdown"],
             base_cand_per_day, base_fires_per_day))
    print("  recall_100 %s/%d  recall_all %s/%d  precision %s/%d"
          % (base_rp["recall_100_hits"], base_rp["recall_100_n"],
             base_rp["recall_all_hits"], base_rp["recall_all_n"],
             base_rp["precision_num"], base_rp["precision_den"]))

    arms = {}
    for T in THRESHOLDS:
        s_picks = build_arm(byday, s_indicator_pick, T)
        r_picks = build_arm(byday, refusal_pick, T)

        s_full = g86.stats(list(s_picks.values()), n_days)
        s_h1 = half_stats(s_picks, hi=H_SPLIT, n_days=n_days_h1)
        s_h2 = half_stats(s_picks, lo=H_SPLIT, n_days=n_days_h2)
        r_full = g86.stats(list(r_picks.values()), n_days)

        cand_per_day = round(sum(1 for d in byday for r in byday[d]
                                  if "09:30" <= r["et"] <= T) / n_days, 2)
        fires_per_day = round(len(s_picks) / n_days, 3)
        rp = recall_and_precision(rows, bysd, T, pool, s100_keys, bar_backed_s_all, s_picks)

        h1_delta = (s_h1.get("per_day", 0) - base_h1.get("per_day", 0))
        h2_delta = (s_h2.get("per_day", 0) - base_h2.get("per_day", 0))
        prec_delta = ((rp["precision"] or 0) - (base_rp["precision"] or 0))
        survivor = (
            (h1_delta > 0 or prec_delta > 0) and (h2_delta > 0 or prec_delta > 0)
            and (rp["recall_100"] or 0) >= (base_rp["recall_100"] or 0)
        )

        arms[T] = {
            "T": T, "inert_control": T == "11:00",
            "s_indicator": {"full": s_full, "h1": s_h1, "h2": s_h2},
            "refusal_indicator": {"full": r_full},
            "candidates_per_day": cand_per_day, "fires_per_day": fires_per_day,
            "recall_precision": rp,
            "h1_delta_usd_day": round(h1_delta, 2), "h2_delta_usd_day": round(h2_delta, 2),
            "survivor": survivor,
        }
        print("\nT=%s  S-indicator: $%d/day (H1 $%d, H2 $%d), mean R %.3f, win %.1f%%, "
              "months green %d/%d, maxDD $%d, cand/day %.1f, fires/day %.3f"
              % (T, s_full["per_day"], s_h1.get("per_day", 0), s_h2.get("per_day", 0),
                 s_full["mean_r"], s_full["win_pct"], s_full["months_green"], s_full["months"],
                 s_full["worst_drawdown"], cand_per_day, fires_per_day))
        print("  refusal-indicator (mirror): $%s/day  |  recall_100 %s/%d  "
              "recall_all %s/%d  precision %s/%d  |  survivor=%s"
              % (r_full.get("per_day", "n/a"), rp["recall_100_hits"], rp["recall_100_n"],
                 rp["recall_all_hits"], rp["recall_all_n"], rp["precision_num"],
                 rp["precision_den"], survivor))

    # T=11:00 is the inert control -- must reproduce baseline exactly.
    ctrl = arms["11:00"]["s_indicator"]["full"]
    assert ctrl["per_day"] == base_full["per_day"] and ctrl["trades"] == base_full["trades"], \
        ("T=11:00 control did not reproduce baseline -- %s vs %s"
         % (ctrl, base_full))
    print("\ncontrol check OK: T=11:00 reproduces baseline exactly "
          "($%d/day, %d trades)" % (ctrl["per_day"], ctrl["trades"]))

    # pick the best non-control T as "the arm" for the headline verdict
    real_Ts = [t for t in THRESHOLDS if t != "11:00"]
    best_T = max(real_Ts, key=lambda t: arms[t]["s_indicator"]["full"]["per_day"])
    best = arms[best_T]

    out = {
        "book": os.path.basename(BOOK), "sessions": n_days,
        "sessions_h1": n_days_h1, "sessions_h2": n_days_h2,
        "baseline": {
            "full": base_full, "h1": base_h1, "h2": base_h2,
            "candidates_per_day": base_cand_per_day, "fires_per_day": base_fires_per_day,
            "recall_precision": base_rp,
        },
        "thresholds": arms,
        "best_T": best_T,
        "survivor": best["survivor"],
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = ["# g154/F5 -- entry-time-of-day-early", "",
          "**What is different now:** tested Austin's \"earlier in the day is better, "
          "no new entries past ~11:00\" claim as a selection ceiling (keep only "
          "candidates at or before T) over the honest book, and it is **not** the "
          "money-losing floor removal the claim's original 09:40 TRADE_FLOOR citation "
          "implied -- that flag is deleted (`live_scanner.py:759`, `backtest_week` "
          "never had one) and only 487 of 10,830 fired rows precede 09:40 anyway.", "",
          "Book `%s`, %d sessions (H1 %d / H2 %d), size-gated on "
          "`signal_runner.min_risk_floor`. 1R = $%d. H1/H2 split at %s."
          % (os.path.basename(BOOK), n_days, n_days_h1, n_days_h2, int(g86.RISK), H_SPLIT),
          "",
          "## Baseline -- first sized candidate of the day, any time", "",
          "| $/day | mean R | win | months green | max DD | cand/day | fires/day | "
          "recall_100 | recall_all | precision |",
          "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
          "| $%d | %+.3f | %.1f%% | %d/%d | $%d | %.1f | %.3f | %s/%d | %s/%d | %s/%d |"
          % (base_full["per_day"], base_full["mean_r"], base_full["win_pct"],
             base_full["months_green"], base_full["months"], base_full["worst_drawdown"],
             base_cand_per_day, base_fires_per_day,
             base_rp["recall_100_hits"], base_rp["recall_100_n"],
             base_rp["recall_all_hits"], base_rp["recall_all_n"],
             base_rp["precision_num"], base_rp["precision_den"]),
          "", "## S-indicator arm (keep candidates at or before T)", "",
          "| T | $/day | H1 $/day | H2 $/day | mean R | win | months green | max DD | "
          "cand/day | fires/day | recall_100 | recall_all | precision | survivor |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for T in THRESHOLDS:
        a = arms[T]; f = a["s_indicator"]["full"]
        h1p = a["s_indicator"]["h1"].get("per_day", 0); h2p = a["s_indicator"]["h2"].get("per_day", 0)
        rp = a["recall_precision"]
        md.append("| %s%s | $%d | $%d | $%d | %+.3f | %.1f%% | %d/%d | $%d | %.1f | %.3f | "
                  "%s/%d | %s/%d | %s/%d | %s |"
                  % (T, " (control)" if a["inert_control"] else "", f["per_day"], h1p, h2p,
                     f["mean_r"], f["win_pct"], f["months_green"], f["months"],
                     f["worst_drawdown"], a["candidates_per_day"], a["fires_per_day"],
                     rp["recall_100_hits"], rp["recall_100_n"], rp["recall_all_hits"],
                     rp["recall_all_n"], rp["precision_num"], rp["precision_den"],
                     a["survivor"]))
    md += ["", "## Refusal-indicator mirror (skip early, take first after T)", "",
          "Not the direction his claim asks for -- reported so a T that only helps "
          "because late trades are bad on their own isn't credited to \"early is good\".",
          "", "| T | $/day | mean R | win |", "|---|---:|---:|---:|"]
    for T in THRESHOLDS:
        r = arms[T]["refusal_indicator"]["full"]
        if r.get("trades"):
            md.append("| %s | $%d | %+.3f | %.1f%% |" % (T, r["per_day"], r["mean_r"], r["win_pct"]))
        else:
            md.append("| %s | n/a (0 trades) | -- | -- |" % T)
    md += ["", "## Verdict", "",
          "Best-performing non-control threshold: **T=%s**. Survivor "
          "(H1 and H2 both improve $/day or precision, recall_100 not below "
          "baseline): **%s**." % (best_T, best["survivor"]), "",
          "g110_time_of_day.py already scanned this same book for the best "
          "arrival threshold and found the OPPOSITE sign: \"first at/after 10:40\" "
          "beat \"first regardless\" ($68/day vs $34/day). That is evidence late "
          "candidates carry more edge, not that early ones do -- this table is "
          "the direct check of Austin's own claim on the same book, not a "
          "re-litigation of g110."]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n  -> %s\n  -> %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
