"""g111 -- the retest tolerance, derived from Austin's own marked entry minutes.

Austin's R4 ruling, 2026-09-03: "Close enough by eye, go with the marks I've
made as your reference for coding." He has given entry minutes on marks across
the corpus (not just research/marks/). Measure the ACTUAL distance between the
bar he named and the level his setup was keyed to, on the real tape, and let
the distribution of those distances BE the tolerance. This settles the
standing contradiction between his own words ("within a few cents give or
take") and g87_retest_tol.py's swept answer of zero.

WHY g98's harvest() ISN'T ENOUGH, AND WHAT THIS ONE DOES DIFFERENTLY
----------------------------------------------------------------------
g98_his_minute_vs_engine.harvest() globs research/marks/*.jsonl only (14
files) and reads exactly two shapes: a top-level `entry_minute` field, or a
prose HH:MM caught by regex in `notes`. That found 177 marks. A full scan of
every `answers.*` key across the canonical mark corpus (`build_deck.mark_
sources()` -- marks/*.jsonl + every LEGACY_MARK_FILE, the same list build_
deck.py's no-repeat guarantee reads) turns up no missed answer-key minute
(eblock/emin are chip INDICES that already collapse into a top-level entry_t
on the one file that uses them; entry/direction fields are call/put, not a
clock). What IS missed is two top-level FIELDS entirely outside `answers`,
and outside research/marks/:

    entry_t     371 rows total, across 8 files
    entry_time   42 rows, recovered_reviews.jsonl
    entry_i    1160 rows -- an index, not a clock time; only useful paired
               with a same-row entry_t/entry_time, never trusted alone

Each file's `entry_t`/`et` was checked against its own builder, because two of
them are NOT his mark -- they are the engine's own entry, copied onto the
exported row for context, and reading them as "his minute" would silently
re-measure the engine's already-known distance and call it his eye:

    marks/probe_master_2026-08-29.jsonl      et == sig.get("et") -- the
        (build_master_homework.py:131,187)   ENGINE's signal minute, shown to
                                              him so he can grade/veto it.
    marks/probe_trade_anatomy_2026-09-01.jsonl  et == bars[fill_i].timestamp --
        (g89_trade_anatomy.py:134-199)       the engine's own FILLED entry, on
                                              trades he is critiquing, not
                                              re-marking.

Confirmed genuinely self-marked, and used here:

    entry_minute   probe_g84_all_in_one_*.jsonl -- an explicit "what minute"
                   tap section (build_g84... front end), entry_minute_given
                   flags whether he answered.
    entry_t        blind_marks_all.jsonl / marks_clean.jsonl -- a BLIND pass:
                   entry/stop/target/entry_i/entry_t are all his own picks,
                   no engine proposal shown at all.
    entry_t        marks/deck_marks_index_2026-08-19.jsonl,
                   marks/deck_marks_tsla_2026-08-20.jsonl -- LEDGER.md: "trade
                   rows" are "execution detail... for the subset of days
                   Austin would actually trade" -- his own entry/stop/exit.
    entry_t        marks/probe_omen_test1_2026-08-27.jsonl -- build_omen_
                   test1.py's own JS: eblock+emin are TAP-SELECTED by him
                   (quarter-hour then minute-inside-block), combined into
                   entry_i/entry_t client-side. The chart shades the engine's
                   proposed entry for reference but the exported entry_t is
                   the block+minute HE tapped.
    entry_t        marks/probe_autopsy_2026-08-23.jsonl -- silent-day autopsy:
                   the engine never fired on these days at all, so there is no
                   engine entry to copy; entry_t can only be his own read.
    entry_time     recovered_reviews.jsonl -- a BLIND re-grade of old chat
                   transcripts; `align` separately records whether his named
                   entry matched an engine replay, which is how we know
                   entry_time is his independent call, not a copy.

Excluded on purpose: `austin_marks_v7.jsonl`, `austin_verdicts.json`,
`mark_batch_02/03_*.jsonl`, `derived_marks_v{1,2}.jsonl` carry `entry_i` with
NO companion clock field. `marks/LEDGER.md` shows v7 is a lossy re-export of
marks_clean/blind_marks_all (same rows, entry_t dropped) -- nothing is lost by
skipping v7's bare `entry_i`, because the entry_t-bearing originals are read
directly, and the two collapse into the same (symbol, day, minute) key anyway.

THE LEVEL, CAUSALLY, AS backtest_week AND signal_runner DERIVE IT
--------------------------------------------------------------------
`backtest_week._named_level_pool(candles, i, pdh, pdl, pmh, pml)` is the
engine's own causal level pool (PDH/PDL/PMH/PML, opening range from the first
5 bars, and `signal_runner.pivot_levels(..., as_of=i)` so no pivot needing
bars past `i` leaks in) -- reused here unmodified, not reimplemented, and
`research/g80_ordertype_grid.day_pack()` sources pdh/pdl/pmh/pml the same way
`backtest_2y.py` does before calling it. For each of his marked bars, every
level in that pool is scored by how far the bar's own [low, high] sits from
it -- 0 if the level fell inside the bar's range (a real wick touch), the gap
to the nearer wick otherwise -- and the NEAREST level is "the level his setup
was keyed to". No engine candidate lookup, no assumption about which level the
engine happened to pick that day: geometry alone, which is what "close enough
by eye" is a claim about.

Run:  python research/g111_retest_tol_from_marks.py
"""
from __future__ import annotations

import glob
import json
import os
import re
import statistics
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import build_deck as deck                        # noqa: E402
import backtest_week as bw                        # noqa: E402
from research import g80_ordertype_grid as G       # noqa: E402

OUT_JSON = os.path.join(HERE, "g111_retest_tol_from_marks.json")
OUT_MD = os.path.join(HERE, "g111_retest_tol_from_marks.md")
MINUTE = re.compile(r"\b((?:9|10|11):[0-5][0-9])\b")

# entry_t/entry_time is confirmed HIS OWN mark on these files (see module
# docstring for the per-file check against each one's own builder).
TRUSTED_ET_FILES = {
    "blind_marks_all.jsonl", "marks_clean.jsonl",
    "deck_marks_index_2026-08-19.jsonl", "deck_marks_tsla_2026-08-20.jsonl",
    "probe_omen_test1_2026-08-27.jsonl", "probe_autopsy_2026-08-23.jsonl",
    "recovered_reviews.jsonl",
}
# entry_t/et is confirmed the ENGINE's own entry, copied onto the row for
# context -- reading it as "his minute" would just re-measure the engine.
EXCLUDE_ET_FILES = {
    "probe_master_2026-08-29.jsonl", "probe_trade_anatomy_2026-09-01.jsonl",
}


def notestr(r):
    n = r.get("notes")
    if isinstance(n, dict):
        return " ".join(str(v) for v in n.values())
    if n:
        return str(n)
    return str(r.get("note") or "")


def _norm_minute(m):
    m = str(m).strip()[:5]
    if len(m) == 4:
        m = "0" + m
    if not re.match(r"^(0[9]|1[01]):[0-5][0-9]$", m):
        return None
    return m


def harvest():
    """Every mark carrying (symbol, day, minute), across the FULL canonical
    corpus -- research/marks/*.jsonl plus every file in build_deck.
    LEGACY_MARK_FILES, exactly the set build_deck.mark_sources() (the
    no-repeat guarantee) reads. Field precedence per row: entry_minute ->
    entry_t/entry_time (only on TRUSTED_ET_FILES) -> a clock-time caught in
    free-text notes. Later files win on a collision (the standing export
    supersedes an earlier partial), matching g98's rule."""
    out = {}
    for path in deck.mark_sources():
        base = os.path.basename(path)
        if base in EXCLUDE_ET_FILES and base not in TRUSTED_ET_FILES:
            trusted = False
        else:
            trusted = base in TRUSTED_ET_FILES
        for r in deck._rows(path):
            sym, day = r.get("symbol"), r.get("date") or r.get("day")
            if not sym or not day:
                cid = r.get("card_id") or r.get("id") or ""
                if "_" in cid:
                    sym, day = cid.rsplit("_", 1)
            if not sym or not day or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(day)[:10]):
                continue
            day = str(day)[:10]

            m = None
            if r.get("entry_minute"):
                m = _norm_minute(r["entry_minute"])
            if m is None and trusted:
                for k in ("entry_t", "entry_time"):
                    if r.get(k):
                        m = _norm_minute(r[k])
                        if m:
                            break
            if m is None:
                hit = MINUTE.search(notestr(r))
                if hit:
                    m = _norm_minute(hit.group(1))
            if m is None:
                continue
            out[(sym, day, m)] = {"sym": sym, "day": day, "et": m, "src": base}
    return list(out.values())


# ---------------------------------------------------------------------------
# the level, causally, as of his bar
# ---------------------------------------------------------------------------

LEVEL_ORDER = ["PDH", "PDL", "PMH", "PML", "ORH", "ORL", "pivot high", "pivot low"]


def _kind(name):
    if name.startswith("pivot high"):
        return "pivot high"
    if name.startswith("pivot low"):
        return "pivot low"
    return name


def nearest_level(bars, hi, pdh, pdl, pmh, pml):
    """(kind, price, touch_dist) for the level nearest to bars[hi]'s own
    [low, high], out of backtest_week's own causal pool. touch_dist is 0 if
    the level sits inside the bar's wick range."""
    if len(bars) < 5 or hi < 5:
        # backtest_week._named_level_pool's own OR is candles[:5] regardless
        # of i, and its own comment marks it "causal for every i >= 5" -- at
        # i < 5 the bar being scored would be inside the OR window that
        # defines the level, an unusable comparison, not a causal one.
        return None
    pool = bw._named_level_pool(bars, hi, pdh, pdl, pmh, pml)
    if not pool:
        return None
    b = bars[hi]
    lo, hicandle = b.low, b.high
    best = None
    for name, price in pool.items():
        if price is None:
            continue
        if lo <= price <= hicandle:
            dist = 0.0
        elif price < lo:
            dist = lo - price
        else:
            dist = price - hicandle
        key = (dist, name)
        if best is None or key < best[0]:
            best = (key, name, price, dist)
    if best is None:
        return None
    _, name, price, dist = best
    return _kind(name), price, dist


def bar_at(bars, hhmm):
    for i, b in enumerate(bars):
        if b.timestamp[:5] == hhmm:
            return i
    return None


def main():
    marks = harvest()
    print("marks carrying (symbol, day, minute), full corpus: %d" % len(marks))
    by_src = Counter(m["src"] for m in marks)
    for src, n in sorted(by_src.items(), key=lambda x: -x[1]):
        print("  %-46s %d" % (src, n))

    rows, skipped = [], Counter()
    for m in marks:
        bars, pdh, pdl, pmh, pml = G.day_pack(m["sym"], m["day"])
        if not bars:
            skipped["no archived bars"] += 1
            continue
        hi = bar_at(bars, m["et"])
        if hi is None:
            skipped["minute not on the tape"] += 1
            continue
        lv = nearest_level(bars, hi, pdh, pdl, pmh, pml)
        if lv is None:
            skipped["no level candidates this early/day"] += 1
            continue
        kind, price, dist = lv
        b = bars[hi]
        rng = b.high - b.low
        rows.append({
            "sym": m["sym"], "day": m["day"], "et": m["et"], "src": m["src"],
            "level_kind": kind, "level_px": round(price, 4),
            "bar_close": round(b.close, 4), "bar_low": round(b.low, 4),
            "bar_high": round(b.high, 4),
            "dist_cents": round(dist * 100, 3),
            "dist_pct_price": round(dist / b.close * 100, 5) if b.close else None,
            "dist_pct_range": (round(dist / rng * 100, 3) if rng > 0 else None),
            "touched": dist == 0.0,
        })

    print("\nusable (symbol, day, minute, level) rows: %d" % len(rows))
    for k, v in sorted(skipped.items(), key=lambda x: -x[1]):
        print("  skipped %-38s %d" % (k, v))
    if len(rows) < 20:
        raise SystemExit("too few rows to say anything")

    cents = [r["dist_cents"] for r in rows]
    pct_price = [r["dist_pct_price"] for r in rows if r["dist_pct_price"] is not None]
    pct_range = [r["dist_pct_range"] for r in rows if r["dist_pct_range"] is not None]
    touched = sum(1 for r in rows if r["touched"])

    def q(vals, p):
        return statistics.quantiles(vals, n=100, method="inclusive")[p - 1]

    def summarize(name, vals, unit):
        med = statistics.median(vals)
        p25, p75 = q(vals, 25), q(vals, 75)
        mean = statistics.mean(vals)
        cv = (statistics.pstdev(vals) / mean) if mean else float("inf")
        print("\n  %-22s median %8.4f%s   IQR [%8.4f, %8.4f]%s   mean %8.4f%s   n=%d"
              % (name, med, unit, p25, p75, unit, mean, unit, len(vals)))
        return {"median": round(med, 5), "p25": round(p25, 5), "p75": round(p75, 5),
                "mean": round(mean, 5), "cv": round(cv, 4), "n": len(vals)}

    print("\n=== DISTANCE FROM HIS MARKED BAR TO THE NEAREST CAUSAL LEVEL ===")
    print("  literally touched (level inside the bar's wick, dist=0): %d/%d (%.1f%%)"
          % (touched, len(rows), 100 * touched / len(rows)))
    s_cents = summarize("cents", cents, "c")
    s_pp = summarize("% of stock price", pct_price, "%")
    s_pr = summarize("% of bar's own range", pct_range, "%")

    kinds = Counter(r["level_kind"] for r in rows)
    print("\n  level kind picked as nearest:")
    for k, n in kinds.most_common():
        print("    %-12s %3d (%.1f%%)" % (k, n, 100 * n / len(rows)))

    tightest = min((("cents", s_cents["cv"]), ("% of price", s_pp["cv"]),
                    ("% of bar range", s_pr["cv"])), key=lambda x: x[1])
    print("\n  tightest distribution overall (lowest CV, dominated by the %.1f%%"
          " zero-mass -- not very informative by itself): %s (cv=%.3f)"
          % (100 * touched / len(rows), tightest[0], tightest[1]))

    # THE REAL TEST OF "within a few cents give or take": restricted to the
    # rows that did NOT literally touch -- his own words describe exactly
    # this subset, not the ones that already hit.
    miss = [r for r in rows if not r["touched"]]
    print("\n=== THE NEAR-MISS SUBSET (n=%d, %.1f%% of rows) -- what \"close but"
          " didn't touch\" costs, per unit ===" % (len(miss), 100 * len(miss) / len(rows)))
    mc = summarize("cents", [r["dist_cents"] for r in miss], "c")
    mp = summarize("% of stock price", [r["dist_pct_price"] for r in miss
                                        if r["dist_pct_price"] is not None], "%")
    mr = summarize("% of bar's own range",
                    [r["dist_pct_range"] for r in miss if r["dist_pct_range"] is not None],
                    "%")
    tightest_miss = min((("cents", mc["cv"]), ("% of price", mp["cv"]),
                        ("% of bar range", mr["cv"])), key=lambda x: x[1])
    print("\n  tightest distribution ON THE NEAR-MISS SUBSET (this is the real"
          " test of \"a few cents give or take\"): %s (cv=%.3f)" % tightest_miss)

    # g87 answer: a limit resting exactly at the level, tolerance zero.
    # His words: "close enough by eye ... within a few cents give or take."
    within_5c = sum(1 for c in cents if c <= 5.0)
    within_10c = sum(1 for c in cents if c <= 10.0)
    print("\n=== HIS WORDS VS THE g87 SWEEP, QUANTIFIED ===")
    print("  g87_retest_tol.py's answer: tolerance ZERO (a resting limit exactly at")
    print("  the level beats every widened tolerance on the book).")
    print("  On his own marked entries: %d/%d (%.1f%%) literally touch (dist=0);"
          % (touched, len(rows), 100 * touched / len(rows)))
    print("  %d/%d (%.1f%%) are within 5 cents; %d/%d (%.1f%%) within 10 cents."
          % (within_5c, len(rows), 100 * within_5c / len(rows),
             within_10c, len(rows), 100 * within_10c / len(rows)))
    print("  Median distance (all rows) is %.2f cents / %.4f%% of price / %.3f%% of"
          " that bar's own range -- the median IS zero because the majority"
          " literally touch." % (s_cents["median"], s_pp["median"], s_pr["median"]))
    print("  On the %d rows that did NOT touch, median distance is %.2fc / %.4f%%"
          " of price / %.3f%% of range -- THIS is what \"a few cents give or"
          " take\" is a claim about, and cents (median %.2fc) is closer to his"
          " words than the sweep's flat zero, even though zero is the modal"
          " (and majority) answer." % (len(miss), mc["median"], mp["median"],
                                        mr["median"], mc["median"]))

    out = {"n_marks": len(marks), "n_rows": len(rows),
           "touched": touched, "touched_pct": round(100 * touched / len(rows), 2),
           "within_5c": within_5c, "within_10c": within_10c,
           "cents": s_cents, "pct_price": s_pp, "pct_range": s_pr,
           "tightest_unit_overall": tightest[0],
           "near_miss_n": len(miss),
           "near_miss_cents": mc, "near_miss_pct_price": mp, "near_miss_pct_range": mr,
           "tightest_unit_near_miss": tightest_miss[0],
           "level_kinds": dict(kinds),
           "skipped": dict(skipped), "rows": rows}
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = ["# g111 -- the retest tolerance, derived from his marks", "",
          "%d marked (symbol, day, minute) triples across the full corpus, %d "
          "resolved to a real bar with a causal level candidate."
          % (len(marks), len(rows)), "",
          "| unit | median | IQR | mean | touched (dist=0) |",
          "|---|---:|---:|---:|---:|",
          "| cents | %.2f | [%.2f, %.2f] | %.2f | %d/%d (%.1f%%) |"
          % (s_cents["median"], s_cents["p25"], s_cents["p75"], s_cents["mean"],
             touched, len(rows), 100 * touched / len(rows)),
          "| %% of stock price | %.4f | [%.4f, %.4f] | %.4f | -- |"
          % (s_pp["median"], s_pp["p25"], s_pp["p75"], s_pp["mean"]),
          "| %% of bar's own range | %.3f | [%.3f, %.3f] | %.3f | -- |"
          % (s_pr["median"], s_pr["p25"], s_pr["p75"], s_pr["mean"]),
          "",
          "Near-miss subset (the %d/%d rows that did NOT literally touch -- this is"
          " what \"a few cents give or take\" is a claim about):"
          % (len(miss), len(rows)), "",
          "| unit | median | IQR | mean |", "|---|---:|---:|---:|",
          "| cents | %.2f | [%.2f, %.2f] | %.2f |"
          % (mc["median"], mc["p25"], mc["p75"], mc["mean"]),
          "| %% of stock price | %.4f | [%.4f, %.4f] | %.4f |"
          % (mp["median"], mp["p25"], mp["p75"], mp["mean"]),
          "| %% of bar's own range | %.3f | [%.3f, %.3f] | %.3f |"
          % (mr["median"], mr["p25"], mr["p75"], mr["mean"]),
          "", "Tightest distribution, all rows (lowest CV): **%s**. Tightest on the"
          " near-miss subset: **%s**." % (tightest[0], tightest_miss[0])]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n  -> %s\n  -> %s\n" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
