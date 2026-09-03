"""G71/samplesize -- how many of the 1,057 judged symbol-days are MEASURABLE today.

Read-only. Touches no mark file except to read it. Uses build_deck.mark_sources()
and build_deck._judgement_key() rather than reimplementing the corpus walk.

For every judged symbol-day it records:
  * which corpora carry it
  * the human grade(s) attached, normalised onto Austin's S/A/C/none ladder
    (engine-ladder tokens A+/B/X are kept separate and NEVER merged)
  * whether the day's own RTH bars are archived (data_archive/<SYM>/<DAY>.csv)
  * whether the PRIOR archived trading day exists (PDH/PDL inputs), and whether
    >=20 prior archived days exist (htf_bias input) -- run_day degrades rather
    than fails on those two, so they are reported but not counted as blockers.

Usage: python research/g71_samplesize_corpus_audit.py --out research/g71_samplesize_corpus.json
"""
from __future__ import annotations
import argparse, json, os, sys, glob
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)

import build_deck as bd  # noqa: E402

ARCHIVE = os.path.join(ROOT, "data_archive")

# Every file walked here is a HUMAN mark corpus, so an "X" in austin_tier /
# tier / verdict / grade is Austin's OLD fourth level -- "I would not take this"
# -- the label that later became "none". It is NOT the engine's X (a detection
# error). austin_marks_v2..v7, the batches, recovered_reviews, austin_verdicts
# and the two 2026-08-2x decks all offered S/A/C/X as the four buttons.
AUSTIN = {"s": "S", "a": "A", "c": "C", "none": "none", "no": "none",
          "n": "none", "skip": "none", "pass": "none", "x": "none"}
# "B" appears 17 times (austin_marks_v7 x3, recovered_reviews x14) -- legacy
# engine ladder leaking into a human file. Kept out of the Austin tally.
ENGINE = {"a+": "A+", "b": "B", "d": "D"}


def norm_grade(raw):
    """-> ('austin', G) | ('engine', G) | ('other', raw) | None"""
    if raw is None:
        return None
    t = str(raw).strip().lower()
    if not t:
        return None
    if t in ENGINE:
        return ("engine", ENGINE[t])
    if t in AUSTIN:
        return ("austin", AUSTIN[t])
    return ("other", t)


def row_grades(row):
    out = []
    for k in bd._GRADE_KEYS:
        g = norm_grade(row.get(k))
        if g:
            out.append(g)
    ans = row.get("answers")
    if isinstance(ans, dict):
        for k, v in ans.items():
            vals = v if isinstance(v, list) else [v]
            for vv in vals:
                if k in ("grade", "tier", "s", "s_call", "austin_grade"):
                    g = norm_grade(vv)
                    if g:
                        out.append(g)
    if row.get("_no_trade"):
        out.append(("austin", "none"))
    return out


def archived(sym, day):
    return os.path.exists(os.path.join(ARCHIVE, sym, day + ".csv"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "g71_samplesize_corpus.json"))
    a = ap.parse_args()

    per_key = defaultdict(lambda: {"sources": set(), "austin": Counter(),
                                   "engine": Counter(), "other": Counter()})
    per_source = {}
    for path in bd.mark_sources():
        n = 0
        for row in bd._rows(path):
            key = bd._judgement_key(row)
            if not key:
                continue
            n += 1
            rec = per_key[key]
            rec["sources"].add(os.path.relpath(path, ROOT).replace("\\", "/"))
            for lane, g in row_grades(row):
                rec[lane][g] += 1
        per_source[os.path.relpath(path, ROOT).replace("\\", "/")] = n

    # archive index per symbol for prior-day / htf checks
    days_by_sym = {}
    for sd in sorted(os.listdir(ARCHIVE)) if os.path.isdir(ARCHIVE) else []:
        p = os.path.join(ARCHIVE, sd)
        if os.path.isdir(p):
            days_by_sym[sd] = sorted(os.path.basename(f)[:-4]
                                     for f in glob.glob(os.path.join(p, "*.csv")))

    rows = []
    for key, rec in per_key.items():
        sym, _, day = key.rpartition("_")
        has = archived(sym, day)
        ds = days_by_sym.get(sym, [])
        idx = ds.index(day) if day in ds else -1
        rows.append({
            "key": key, "symbol": sym, "day": day,
            "sources": sorted(rec["sources"]),
            "austin": dict(rec["austin"]), "engine": dict(rec["engine"]),
            "other": dict(rec["other"]),
            "bars": has,
            "prior_day": idx > 0,
            "hist20": idx >= 20,
            "symbol_in_archive": sym in days_by_sym,
        })
    rows.sort(key=lambda r: r["key"])

    def top_austin(r):
        """Best (most severe / highest) Austin grade on the day; S > A > C > none."""
        order = ["S", "A", "C", "none"]
        for g in order:
            if r["austin"].get(g):
                return g
        return None

    n = len(rows)
    with_bars = [r for r in rows if r["bars"]]
    austin_graded = [r for r in rows if r["austin"]]
    s_days = [r for r in rows if top_austin(r) == "S"]
    s_days_bars = [r for r in s_days if r["bars"]]
    no_sym = sorted({r["symbol"] for r in rows if not r["symbol_in_archive"]})
    missing = [r for r in rows if not r["bars"]]
    miss_by_sym = Counter(r["symbol"] for r in missing)
    miss_in_universe = [r for r in missing if r["symbol_in_archive"]]
    miss_by_year = Counter(r["day"][:4] for r in missing)

    summary = {
        "distinct_judged_symbol_days": n,
        "with_archived_bars": len(with_bars),
        "without_archived_bars": len(missing),
        "symbol_never_archived": {"n_days": n - sum(1 for r in rows if r["symbol_in_archive"]),
                                  "symbols": no_sym},
        "missing_bars_symbol_is_archived": len(miss_in_universe),
        "missing_by_symbol": dict(miss_by_sym.most_common()),
        "missing_by_year": dict(sorted(miss_by_year.items())),
        "austin_ladder_graded_days": len(austin_graded),
        "austin_grade_mix": dict(Counter(top_austin(r) for r in austin_graded).most_common()),
        "S_days_total": len(s_days),
        "S_days_with_bars": len(s_days_bars),
        "S_base_rate_of_austin_graded": round(len(s_days) / max(1, len(austin_graded)), 4),
        "prior_day_missing_among_with_bars": sum(1 for r in with_bars if not r["prior_day"]),
        "hist20_missing_among_with_bars": sum(1 for r in with_bars if not r["hist20"]),
        "rows_per_source": per_source,
    }
    print(json.dumps(summary, indent=2)[:6000])
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "rows": rows}, fh, indent=2)
    print("wrote " + a.out)


if __name__ == "__main__":
    main()
