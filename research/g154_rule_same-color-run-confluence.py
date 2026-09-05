"""g154 -- F5: "same-color-run-confluence" (S-indicator, but two-sided).

Austin's words (spec row): "A run of 2-3 consecutive same-coloured candles
into the entry reads as strength -- additive to break-leg displacement --
but one of his own cards prefers an isolated candle in trend, so it is
two-sided." NVDA_2026-06-25: two green candles at the open read as LESS
clean to him -- an additive "more same-color = more confidence" feature
gets that card backwards. So this script does NOT build a score. It reports
three buckets SEPARATELY -- isolated / short-run / long-run -- against S
rate and realized R, and only THEN builds one candidate arm off the
spec's stated default reading (run_len in {2,3} keeps, i.e. the
"additive to displacement" hypothesis), so the arm's own $/day and
recall numbers are on the table next to the bucket table that undercuts it.

    run_len = count of consecutive bars ending at entry_i-1 with the same
    sign(close-open), walking backward from entry_i-1. Index <= entry_i-1
    only -- the entry/signal bar itself (entry_i) is never included, so
    this is not lookahead: the run is fully printed before the signal bar
    the candidate fires on.

Buckets:
    isolated   run_len in {0, 1}   -- 0 or 1 same-colour bar immediately before
    short_run  run_len in {2, 3}   -- the "additive" case the row names
    long_run   run_len >= 4        -- overextended into the entry

Bars are read from data_archive (via polygon_feed, cache-only for every
symbol/day this book already contains), for bars strictly BEFORE the
signal bar only.

Unit: research/omen_metrics.first_of_day_arm (one trade a day, arrival
order across ALL symbols, size-gated on signal_runner.min_risk_floor) --
same unit as research/g86_honest_ceiling.py and research/g91_lane_slice.py.

    python research/g154_rule_same-color-run-confluence.py

Writes research/g154_rule_same-color-run-confluence.{json,md}.
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
OUT_JSON = os.path.join(HERE, "g154_rule_same-color-run-confluence.json")
OUT_MD = os.path.join(HERE, "g154_rule_same-color-run-confluence.md")

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


def bar_sign(b):
    """+1 green, -1 red, 0 doji (close == open) -- a doji breaks any run."""
    if b.close > b.open:
        return 1
    if b.close < b.open:
        return -1
    return 0


def run_len(row):
    """None if entry_i is missing/unreadable or there is no bar before it
    (entry_i <= 0). Otherwise the count of consecutive bars, walking
    backward from entry_i-1, sharing entry_i-1's sign. A doji at
    entry_i-1 itself gives run_len == 0 (its own sign is 0, nothing
    "matches" it going further back)."""
    bars = get_bars(row["sym"], row["day"])
    i = row.get("entry_i")
    if i is None or i <= 0 or i > len(bars):
        return None
    last = i - 1
    if last >= len(bars):
        return None
    s0 = bar_sign(bars[last])
    if s0 == 0:
        return 0
    n = 0
    j = last
    while j >= 0 and bar_sign(bars[j]) == s0:
        n += 1
        j -= 1
    return n


def bucket_of(rl):
    if rl is None:
        return None
    if rl <= 1:
        return "isolated"
    if rl <= 3:
        return "short_run"
    return "long_run"


BUCKETS = ("isolated", "short_run", "long_run")


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
    """First-of-day, size-gated, optionally restricted to rows whose
    bucket keep_fn(bucket) accepts (bucket may be None if entry_i can't
    be read -- treated as non-droppable/kept, so an unreadable bar never
    silently vanishes a day). Mirrors omen_metrics.first_of_day_arm's
    pick-then-gate fix: the gate runs INSIDE selection so a
    dropped/unsizeable first candidate falls through to the next one on
    the same day, never skips the day."""
    firsts = []
    for day in sorted(byday):
        v = byday[day]
        pick = None
        for r in v:
            if _row_is_sizeable(r) is False:
                continue
            if keep_fn is not None:
                b = bucket_of(run_len(r))
                if b is not None and not keep_fn(b):
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


# ------------------------------------------------------------- bucket profile

def bucket_profile(all_cands, pool):
    """For each of the three buckets, over EVERY candidate in the book
    (not just first-of-day): n, share of candidates, mean realized R
    (pnl/RISK on that candidate's own trade), S rate among graded-any
    candidates in that bucket, and how many had no readable run_len."""
    by_bucket = defaultdict(list)
    unreadable = 0
    for r in all_cands:
        b = bucket_of(run_len(r))
        if b is None:
            unreadable += 1
            continue
        by_bucket[b].append(r)
    total_readable = sum(len(v) for v in by_bucket.values())
    out = {}
    for b in BUCKETS:
        rows = by_bucket.get(b, [])
        n = len(rows)
        mean_r = (round(statistics.fmean(r["pnl"] for r in rows) / RISK, 4)
                  if rows else 0.0)
        graded_s = graded_any = 0
        for r in rows:
            key = "%s_%s" % (r["sym"], r["day"])
            entry = pool.get(key)
            if entry is None:
                continue
            graded_any += 1
            if entry.grade == "S":
                graded_s += 1
        s_rate = round(graded_s / graded_any * 100, 1) if graded_any else None
        out[b] = {
            "n": n,
            "share_pct": round(n / total_readable * 100, 1) if total_readable else 0.0,
            "mean_r": mean_r,
            "s_rate_pct": s_rate,
            "graded_s": graded_s,
            "graded_any": graded_any,
        }
    out["_unreadable"] = unreadable
    out["_total_readable"] = total_readable
    return out


# --------------------------------------------------------------------------- main

def main():
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    byday = by_day_candidates(rows)
    n_days_total = meta.get("sessions") or len({r["day"] for r in rows})
    cand_per_day = round(sum(len(v) for v in byday.values()) / n_days_total, 2)
    all_cands = [r for v in byday.values() for r in v]

    s_pairs_100 = load_sweep_s_days()
    pool = marks_pool.canonical_pool()
    all_s_pairs = []
    for k in marks_pool.s_days(pool):
        sym, day = k.split("_", 1)
        all_s_pairs.append((sym, day))

    # ---- the three buckets, reported separately, no sum, no score ----
    buckets = bucket_profile(all_cands, pool)

    # ---- baseline arm ----
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

    # ---- candidate arm: the spec's stated default reading -- keep only
    # short_run (2-3), i.e. "additive to displacement" -- S-indicator ----
    keep_fn = lambda b: b == "short_run"           # noqa: E731
    firsts = pick_first_of_day(byday, keep_fn=keep_fn)
    h1, h2 = split_h1_h2(firsts)
    dropped = sum(1 for r in all_cands
                  if bucket_of(run_len(r)) not in (None, "short_run"))
    dropped_pct = round(dropped / len(all_cands) * 100, 2) if all_cands else 0.0
    primary = {
        "keep": "short_run (run_len in {2,3})",
        "candidates_dropped_pct": dropped_pct,
        "overall": score(firsts), "H1": score(h1), "H2": score(h2),
        "fires_per_day": round(len(firsts) / n_days_total, 3),
    }
    p_r100, p_hit100, p_n100 = recall(firsts, s_pairs_100)
    p_rall, p_hitall, p_nall = recall(firsts, all_s_pairs)
    p_prec, p_gs, p_ga = precision(firsts, pool)
    primary["s_recall_100"] = {"pct": p_r100, "hit": p_hit100, "n": p_n100}
    primary["s_recall_all_bar_backed"] = {"pct": p_rall, "hit": p_hitall, "n": p_nall}
    primary["precision"] = {"pct": p_prec, "graded_s": p_gs, "graded_any": p_ga}

    h1_delta_usd = primary["H1"]["usd_day"] - baseline["H1"]["usd_day"]
    h2_delta_usd = primary["H2"]["usd_day"] - baseline["H2"]["usd_day"]
    usd_improves = h1_delta_usd > 0 and h2_delta_usd > 0
    prec_improves = primary["precision"]["pct"] > baseline["precision"]["pct"]
    recall_ok = primary["s_recall_100"]["pct"] >= baseline["s_recall_100"]["pct"]
    survivor = bool((usd_improves or prec_improves) and recall_ok)

    out = {
        "row": "F5",
        "slug": "same-color-run-confluence",
        "predicate": "run_len = count of consecutive bars ending at entry_i-1 "
                     "with the same sign(close-open), walking backward, index "
                     "<= entry_i-1 only. Buckets: isolated {0,1}, short_run "
                     "{2,3}, long_run >=4.",
        "polarity": "S-indicator (spec's stated default reading), but flagged "
                    "two-sided by the row itself -- NVDA_2026-06-25 grades two "
                    "green candles at the open as LESS clean, the opposite of "
                    "this arm's hypothesis. NOT summed into any score.",
        "n_days_total": n_days_total,
        "candidates_per_day": cand_per_day,
        "buckets": buckets,
        "baseline": baseline,
        "primary_arm": primary,
        "h1_delta_usd_day": round(h1_delta_usd, 2),
        "h2_delta_usd_day": round(h2_delta_usd, 2),
        "survivor": survivor,
        "notes": ("Three buckets reported separately (isolated / short_run / "
                  "long_run), never summed into a score -- see 'buckets' "
                  "above for S rate and mean R per bucket. The candidate arm "
                  "tests only the spec's stated default reading: keep the "
                  "day's first candidate only if it falls in short_run "
                  "(run_len 2-3), i.e. the 'additive to displacement' "
                  "hypothesis, else fall through to the next candidate that "
                  "day (same pick-then-gate logic as omen_metrics."
                  "first_of_day_arm). survivor = True only if H1 AND H2 both "
                  "improve $/day (or precision improves) and S-recall-100 "
                  "does not fall below baseline. The isolated-candle "
                  "counter-reading from NVDA_2026-06-25 is NOT separately "
                  "armed here -- one card is a hint, not a rule, per the "
                  "no-oversell instruction -- but the bucket table lets that "
                  "counter-reading be checked against the whole book's S "
                  "rate and realized R."),
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
    lines.append("# g154 -- F5 same-color-run-confluence\n")
    lines.append("**What is different now:** measured Austin's rule that a "
                 "run of 2-3 same-coloured candles into the entry reads as "
                 "strength -- against the one-trade-a-day book, in three "
                 "SEPARATE buckets (no summed score), because one of his own "
                 "cards (NVDA_2026-06-25) says the opposite for two green "
                 "candles at the open.\n")

    lines.append("## Bucket profile -- every candidate in the book, no filtering\n")
    lines.append("| bucket | n | share | mean R | S rate | graded S/any |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    names = {"isolated": "isolated (run_len 0-1)",
             "short_run": "short_run (run_len 2-3)",
             "long_run": "long_run (run_len >=4)"}
    for b in BUCKETS:
        d = out["buckets"][b]
        s_rate = "%s%%" % d["s_rate_pct"] if d["s_rate_pct"] is not None else "n/a"
        lines.append("| %s | %d | %s%% | %s | %s | %d/%d |" %
                      (names[b], d["n"], d["share_pct"], d["mean_r"], s_rate,
                       d["graded_s"], d["graded_any"]))
    lines.append("")
    lines.append("unreadable run_len (entry_i missing/bar unavailable): %d "
                 "of %d total candidates\n" %
                 (out["buckets"]["_unreadable"],
                  out["buckets"]["_unreadable"] + out["buckets"]["_total_readable"]))

    b = out["baseline"]
    lines.append("## Baseline (no filter, one-trade-a-day arm)\n")
    lines.append("| pop | n | $/day | mean R | win | green/mo | max DD |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    lines.append(_fmt_row("overall", b))
    lines.append(_fmt_row("H1", {"overall": b["H1"]}))
    lines.append(_fmt_row("H2", {"overall": b["H2"]}))
    lines.append("")
    lines.append("candidates/day: %s -- fires/day: %s" %
                  (out["candidates_per_day"], b["fires_per_day"]))
    lines.append("S recall (100-card deck, 34 S): %s%% (%d/%d)" %
                  (b["s_recall_100"]["pct"], b["s_recall_100"]["hit"],
                   b["s_recall_100"]["n"]))
    lines.append("S recall (all bar-backed S days): %s%% (%d/%d)" %
                  (b["s_recall_all_bar_backed"]["pct"],
                   b["s_recall_all_bar_backed"]["hit"],
                   b["s_recall_all_bar_backed"]["n"]))
    lines.append("precision (fired-day graded S / fired-day graded any): "
                 "%s%% (%d/%d)\n" % (b["precision"]["pct"], b["precision"]["graded_s"],
                                    b["precision"]["graded_any"]))

    p = out["primary_arm"]
    lines.append("## Candidate arm: keep only %s\n" % p["keep"])
    lines.append("| pop | n | $/day | mean R | win | green/mo | max DD |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    lines.append(_fmt_row("overall", p))
    lines.append(_fmt_row("H1", {"overall": p["H1"]}))
    lines.append(_fmt_row("H2", {"overall": p["H2"]}))
    lines.append("")
    lines.append("candidates/day: %s -- fires/day: %s -- candidates dropped: %s%%" %
                  (out["candidates_per_day"], p["fires_per_day"],
                   p["candidates_dropped_pct"]))
    lines.append("S recall (100-card): %s%% (%d/%d) -- baseline %s%%" %
                  (p["s_recall_100"]["pct"], p["s_recall_100"]["hit"],
                   p["s_recall_100"]["n"], b["s_recall_100"]["pct"]))
    lines.append("S recall (all bar-backed): %s%% (%d/%d) -- baseline %s%%" %
                  (p["s_recall_all_bar_backed"]["pct"],
                   p["s_recall_all_bar_backed"]["hit"],
                   p["s_recall_all_bar_backed"]["n"],
                   b["s_recall_all_bar_backed"]["pct"]))
    lines.append("precision: %s%% (%d/%d) -- baseline %s%%\n" %
                  (p["precision"]["pct"], p["precision"]["graded_s"],
                   p["precision"]["graded_any"], b["precision"]["pct"]))

    lines.append("## Survivor verdict\n")
    lines.append("H1 delta $/day: %s -- H2 delta $/day: %s" %
                  (out["h1_delta_usd_day"], out["h2_delta_usd_day"]))
    lines.append("**survivor = %s**\n" % out["survivor"])
    lines.append(out["notes"])
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
