"""ADVERSARIAL VERIFY of track `samplesize`.

Question: does "1,096 days replay with ZERO errors" mean the days are correctly
measurable? `research/t4_engine_recall.run_day` feeds the engine PDH/PDL from
`levels._prior_day` = the previous ARCHIVED csv, with no calendar-adjacency
check (research/levels.py:159-165), and htf_bias from the previous 40 ARCHIVED
files (research/t4_engine_recall.py:112-124). data_archive is a sparse,
marks-driven cache, so on a day whose neighbours were never pulled the engine is
handed prior-day levels from an arbitrarily distant session and raises nothing.

This script measures the calendar gap between each replayed day and the
"prior day" the harness actually used, split sweep-100 vs the rest of the corpus.

Read-only. Writes only its own json.
Usage: python research/g71_vsamplesize_priorday.py
"""
from __future__ import annotations
import json, os, sys, glob
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import levels  # noqa: E402

AUDIT = os.path.join(HERE, "g71_samplesize_corpus.json")
SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT = os.path.join(HERE, "g71_vsamplesize_priorday.json")


def d(s):
    y, m, dd = s.split("-")
    return date(int(y), int(m), int(dd))


def top(r):
    for g in ("S", "A", "C", "none"):
        if r["austin"].get(g):
            return g
    return None


def main():
    audit = json.load(open(AUDIT, encoding="utf-8"))
    rows = [r for r in audit["rows"] if r["bars"] and r["austin"]]
    sweep = set()
    for ln in open(SWEEP, encoding="utf-8"):
        ln = ln.strip()
        if ln:
            j = json.loads(ln)
            sweep.add("%s_%s" % (j["symbol"], j["date"]))

    names_by_sym = {}
    for r in rows:
        s = r["symbol"]
        if s not in names_by_sym:
            names_by_sym[s] = sorted(
                os.path.basename(f)[:-4]
                for f in glob.glob(os.path.join(levels.ARCHIVE, s, "*.csv")))

    def bucket(gap):
        if gap is None:
            return "no_prior_day_at_all"
        if gap <= 4:
            return "ok_<=4d"          # Fri->Mon is 3, a single holiday 4
        if gap <= 10:
            return "stale_5-10d"
        if gap <= 40:
            return "stale_11-40d"
        return "stale_>40d"

    res = {}
    detail_bad = []
    for lane in ("sweep100", "rest_of_corpus"):
        sel = [r for r in rows if (r["key"] in sweep) == (lane == "sweep100")]
        c = Counter(); cs = Counter()
        hb = Counter(); hbs = Counter()
        for r in sel:
            ns = names_by_sym[r["symbol"]]
            i = ns.index(r["day"]) if r["day"] in ns else -1
            gap = None
            if i > 0:
                gap = (d(r["day"]) - d(ns[i - 1])).days
            b = bucket(gap)
            c[b] += 1
            if top(r) == "S":
                cs[b] += 1
            # htf_bias: needs >=20 of the prior 40 ARCHIVED files; measure the
            # calendar span those 40 files cover (should be ~56 days, not years)
            prior = ns[max(0, i - 40):i] if i >= 0 else []
            if len(prior) >= 20:
                span = (d(r["day"]) - d(prior[-20])).days
                k = "sma20_span_ok_<=40d" if span <= 40 else (
                    "sma20_span_41-120d" if span <= 120 else "sma20_span_>120d")
            else:
                k = "sma20_unavailable(None)"
            hb[k] += 1
            if top(r) == "S":
                hbs[k] += 1
            if b != "ok_<=4d" and lane == "rest_of_corpus" and top(r) == "S":
                detail_bad.append({"key": r["key"], "gap_days": gap,
                                   "prior_used": ns[i - 1] if i > 0 else None})
        res[lane] = {"n": len(sel), "prior_day_gap": dict(c),
                     "prior_day_gap_S_only": dict(cs),
                     "htf_sma20_span": dict(hb),
                     "htf_sma20_span_S_only": dict(hbs)}

    tot_bad = sum(v for k, v in res["rest_of_corpus"]["prior_day_gap"].items()
                  if k != "ok_<=4d")
    res["headline"] = {
        "replayed_days": len(rows),
        "rest_of_corpus_days_with_wrong_prior_day": tot_bad,
        "rest_of_corpus_pct_wrong_prior_day": round(
            tot_bad / max(1, res["rest_of_corpus"]["n"]) * 100, 1),
        "sweep100_days_with_wrong_prior_day": sum(
            v for k, v in res["sweep100"]["prior_day_gap"].items() if k != "ok_<=4d"),
    }
    res["worst_S_examples"] = sorted(detail_bad,
                                     key=lambda x: -(x["gap_days"] or 0))[:15]
    print(json.dumps({k: v for k, v in res.items()
                      if k != "worst_S_examples"}, indent=2))
    print(json.dumps(res["worst_S_examples"][:10], indent=2))
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=2)
    print("wrote " + OUT)


if __name__ == "__main__":
    main()
