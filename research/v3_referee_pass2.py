"""v3_referee_pass2.py -- second referee pass on row V3 (builder commit b5267e46).

Independent re-derivation of every headline cell in research/g215_precision.md.
Imports NOTHING from g215_precision.py, marks_pool.py or omen_metrics.py: the
mark corpora are read through build_deck.mark_sources()/_rows()/_judgement_key()
and grade_read.grade_opinions() (the two canonical readers the row names, and
the ones the referee brief mandates), but the cross-corpus resolution, the
ninth-spelling handling, the size gate, the first-of-day pick, the all-fires
reduction and the Wilson interval are all re-implemented here from their
definitions.

    python research/v3_referee_pass2.py
"""
from __future__ import annotations

import gzip
import json
import math
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import build_deck as bd          # noqa: E402
import grade_read as gr          # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
ARCHIVE = os.path.join(ROOT, "data_archive")
Z = 1.959963985

RANK = {"S": 0, "A": 1, "B": 2, "C": 3, "none": 4, "X": 4}
IS_S_YES = {"yes", "y", "true", "1", "s"}
IS_S_NO = {"no", "n", "false", "0"}


# ------------------------------------------------------------------ Wilson
def wilson(k, n, z=Z):
    if n <= 0:
        return None, None
    p = k / n
    d = 1.0 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round(max(0.0, (c - m) / d) * 100, 1), round(min(1.0, (c + m) / d) * 100, 1)


def cell(k, n):
    lo, hi = wilson(k, n)
    return "%s/%s = %s%% [%s-%s]" % (
        k, n, (round(k / n * 100, 1) if n else "n/a"), lo, hi)


# ------------------------------------------------------- my own mark pool
def ninth(row):
    """answers.is_s -- the spelling marks_pool adds on top of grade_read."""
    a = row.get("answers")
    if not isinstance(a, dict) or "is_s" not in a:
        return None
    v = a["is_s"]
    if isinstance(v, (list, tuple)):
        v = v[0] if v else None
    if v is None:
        return None
    t = str(v).strip().lower()
    if t in IS_S_YES:
        return "S"
    if t in IS_S_NO:
        return "none"
    return None


def row_grade(row, use_ninth=True):
    ops = [g for _f, g in gr.grade_opinions(row)]
    if use_ninth:
        n9 = ninth(row)
        if n9 is not None:
            ops.append(n9)
    if not ops:
        return None
    if "S" in ops:
        return "S"
    for g in ops:
        if g != "none":
            return g
    return "none"


def build_pool(use_ninth=True):
    """key -> (resolved_grade, raw_grades set, n_opinions, contested, has_bars)."""
    by_key = defaultdict(list)
    for path in bd.mark_sources():
        for row in bd._rows(path):
            key = bd._judgement_key(row)
            if not key:
                continue
            g = row_grade(row, use_ninth)
            if g is None:
                continue
            by_key[key].append(g)
    pool = {}
    for key, ops in by_key.items():
        sym, date = key.split("_", 1)
        buckets = {("none" if g in ("none", "X") else g) for g in ops}
        best = min(buckets, key=lambda b: RANK[b])
        pool[key] = {
            "grade": best,
            "raw": sorted(set(ops)),
            "n": len(ops),
            "contested": len(buckets) > 1,
            "has_bars": os.path.exists(os.path.join(ARCHIVE, sym, date + ".csv")),
        }
    return pool


# --------------------------------------------------------------- the book
def load_book(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            b = json.load(fh)
    else:
        with gzip.open(path + ".gz", "rt", encoding="utf-8") as fh:
            b = json.load(fh)
    return b["trades"], b["meta"]


def min_risk_floor(close):
    """signal_runner.min_risk_floor, verbatim from its own docstring
    (max(0.10, 0.0015 * close)) -- re-stated here rather than imported so this
    referee does not share a code path with the builder."""
    return max(0.10, 0.0015 * close)


def sizeable(row):
    e, s = row.get("entry"), row.get("stop")
    if e is None or s is None:
        return None
    return abs(e - s) >= min_risk_floor(row.get("close", e))


def real_candidates(rows):
    return [r for r in rows
            if ((r["status"] == "fired" and r.get("traded")) or r["status"] == "halted")
            and sizeable(r) is not False]


def unit1_keys(rows):
    """One pick per calendar day: earliest (et, sym) among size-gated real
    candidates. Re-implemented, not imported."""
    by_day = defaultdict(list)
    for r in real_candidates(rows):
        by_day[r["day"]].append(r)
    out = []
    for day in sorted(by_day):
        pick = sorted(by_day[day], key=lambda r: (r["et"], r["sym"]))[0]
        out.append("%s_%s" % (pick["sym"], pick["day"]))
    return out


def unit2_keys(rows):
    return sorted({"%s_%s" % (r["sym"], r["day"]) for r in real_candidates(rows)})


# ------------------------------------------------------------------- main
def score(keys, pool, bar_s, label, sessions):
    graded = [(k, pool[k]["grade"]) for k in keys if k in pool]
    s = sum(1 for _k, g in graded if g == "S")
    hit = bar_s & set(keys)
    print("  %-22s n=%-5d fires/day=%-7.3f precision %s  recall %s"
          % (label, len(keys), len(keys) / sessions, cell(s, len(graded)),
             cell(len(hit), len(bar_s))))
    return s, len(graded), len(hit)


def main():
    rows, meta = load_book(BOOK)
    sessions = meta.get("sessions") or len({r["day"] for r in rows})
    print("book %s  sessions=%s  %s -> %s  RETEST=%s"
          % (os.path.basename(BOOK), sessions, meta.get("first"), meta.get("last"),
             meta.get("stamp", {}).get("flags", {}).get("signal_runner.RETEST_REQUIRED")))

    pool = build_pool(use_ninth=True)
    judged = bd.marked_card_ids()
    s_all = {k for k, v in pool.items() if v["grade"] == "S"}
    bar_s = {k for k in s_all if pool[k]["has_bars"]}
    contested = [k for k, v in pool.items() if v["contested"]]
    print("judged(marked_card_ids)=%d  graded pool=%d  ungraded=%d"
          % (len(judged), len(pool), len(judged) - len(pool)))
    print("S days total=%d  bar-backed S=%d  contested=%d (%d opinion rows)"
          % (len(s_all), len(bar_s), len(contested),
             sum(pool[k]["n"] for k in contested)))
    print("grade distribution:", dict(Counter(v["grade"] for v in pool.values())))

    print("\n=== headline ===")
    u1 = unit1_keys(rows)
    u2 = unit2_keys(rows)
    s1, g1, h1 = score(u1, pool, bar_s, "unit1 one-a-day", sessions)
    s2, g2, h2 = score(u2, pool, bar_s, "unit2 all-fires", sessions)

    print("\n=== cross-checks ===")
    # every fired symbol-day graded S -- are they all bar-backed?
    u2set = set(u2)
    s_fired = {k for k in u2set if pool.get(k, {}).get("grade") == "S"}
    print("  unit2 S-graded fires=%d   of which bar-backed=%d   (precision numerator"
          " == recall numerator only if these are equal)"
          % (len(s_fired), sum(1 for k in s_fired if pool[k]["has_bars"])))
    # unit1 picks are a subset of unit2 symbol-days?
    print("  unit1 picks not in unit2 pool: %d" % len(set(u1) - u2set))
    # duplicate days in unit1?
    print("  unit1 distinct days=%d of %d picks" % (len({k.split('_', 1)[1] for k in u1}), len(u1)))

    print("\n=== sensitivity: drop the ninth spelling ===")
    pool8 = build_pool(use_ninth=False)
    s_all8 = {k for k, v in pool8.items() if v["grade"] == "S"}
    bar_s8 = {k for k in s_all8 if pool8[k]["has_bars"]}
    print("  graded pool=%d  bar-backed S=%d" % (len(pool8), len(bar_s8)))
    score(u1, pool8, bar_s8, "unit1 (8 spellings)", sessions)
    score(u2, pool8, bar_s8, "unit2 (8 spellings)", sessions)

    print("\n=== Wilson by hand, 18/59 ===")
    k, n = 18, 59
    p = k / n
    print("  p=%.6f  centre=%.6f  margin=%.6f  denom=%.6f -> [%.3f, %.3f]"
          % (p, p + Z * Z / (2 * n),
             Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)),
             1 + Z * Z / n,
             (p + Z * Z / (2 * n) - Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))) / (1 + Z * Z / n) * 100,
             (p + Z * Z / (2 * n) + Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))) / (1 + Z * Z / n) * 100))

    print("\n=== unit1 graded picks, all %d ===" % g1)
    for kk in sorted(k for k in u1 if k in pool):
        print("   %-24s %s  raw=%s" % (kk, pool[kk]["grade"], pool[kk]["raw"]))


if __name__ == "__main__":
    main()
