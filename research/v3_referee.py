"""v3_referee.py -- independent recomputation of row V3's numbers.

Referee for builder commit b5267e46 (V3, research/g215_precision.py).
Default posture is REFUTE: nothing here calls g215_precision.py or
marks_pool.py. It re-reads the mark corpora through the two canonical
readers the row names (build_deck.mark_sources/_rows/_judgement_key and
grade_read.grade_opinions), applies its OWN best-grade-wins resolution, its
OWN first-of-day pick over the book, its OWN bar-backed test, and its OWN
Wilson interval, then compares against the builder's published cells.

Also checks, by sensitivity:
  * what the pick-level precision reads WITHOUT the ninth spelling
    (answers.is_s) that marks_pool adds on top of grade_read;
  * whether unit-1 recall and unit-1 precision share a numerator by
    construction or by coincidence.

    python research/v3_referee.py
"""
from __future__ import annotations

import gzip
import json
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import build_deck as bd        # noqa: E402
import grade_read as gr        # noqa: E402
from signal_runner import min_risk_floor  # noqa: E402

ARCHIVE = os.path.join(ROOT, "data_archive")
BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
Z = 1.959963985

RANK = {"S": 0, "A": 1, "B": 2, "C": 3, "none": 4, "X": 4}
IS_S_YES = {"s", "yes", "y", "true", "1"}
IS_S_NO = {"none", "no", "n", "false", "0"}


def wilson(k, n):
    """Wilson 95% score interval, written from the closed form, not imported."""
    if n <= 0:
        return None, None
    p = k / n
    z2 = Z * Z
    d = 1.0 + z2 / n
    c = p + z2 / (2 * n)
    m = Z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return round(max(0.0, (c - m) / d) * 100, 1), round(min(1.0, (c + m) / d) * 100, 1)


def cell(k, n):
    lo, hi = wilson(k, n)
    return "%.1f%% (%d/%d) [%s-%s]" % ((k / n * 100) if n else 0.0, k, n, lo, hi)


def row_grade(row, with_ninth=True):
    ops = list(gr.grade_opinions(row))
    if with_ninth:
        ans = row.get("answers")
        if isinstance(ans, dict) and "is_s" in ans:
            v = ans["is_s"]
            if isinstance(v, (list, tuple)):
                v = v[0] if v else None
            if v is not None:
                t = str(v).strip().lower()
                if t in IS_S_YES:
                    ops.append(("answers.is_s", "S"))
                elif t in IS_S_NO:
                    ops.append(("answers.is_s", "none"))
    if not ops:
        return None
    for _f, g in ops:
        if g == "S":
            return "S"
    for _f, g in ops:
        if g != "none":
            return g
    return "none"


def build_grades(with_ninth=True, drop_derived=False):
    """{SYMBOL_DATE: (resolved_grade, contested_bool, n_opinion_rows)}.

    `drop_derived` excludes research/derived_marks_v*.jsonl -- CLAUDE.md calls
    those 31 rows "derived, low confidence", and best-grade-wins lets one of
    them override an austin_marks_v7 X. Sensitivity, not a proposal.
    """
    by_key = defaultdict(list)
    for path in bd.mark_sources():
        if drop_derived and "derived_marks_v" in os.path.basename(path):
            continue
        for row in bd._rows(path):
            key = bd._judgement_key(row)
            if not key:
                continue
            g = row_grade(row, with_ninth)
            if g is None:
                continue
            by_key[key].append(g)
    out = {}
    for key, gs in by_key.items():
        buckets = {"none" if g in ("none", "X") else g for g in gs}
        best = min(buckets, key=lambda b: RANK[b])
        out[key] = (best, len(buckets) > 1, len(gs))
    return out


def load_book(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            blob = json.load(fh)
    else:
        with gzip.open(path + ".gz", "rt", encoding="utf-8") as fh:
            blob = json.load(fh)
    return blob["trades"], blob["meta"]


def sizeable(r):
    e, s = r.get("entry"), r.get("stop")
    if e is None or s is None:
        return None
    return abs(e - s) >= min_risk_floor(r.get("close", e))


def main():
    grades = build_grades(True)
    grades_no9 = build_grades(False)
    judged = bd.marked_card_ids()

    bar_s = {k for k, (g, _c, _n) in grades.items()
             if g == "S" and os.path.exists(
                 os.path.join(ARCHIVE, k.split("_", 1)[0], k.split("_", 1)[1] + ".csv"))}
    contested_n = sum(1 for v in grades.values() if v[1])
    contested_rows = sum(v[2] for v in grades.values() if v[1])

    rows, meta = load_book(BOOK)
    sessions = meta.get("sessions") or len({r["day"] for r in rows})

    # unit 1 -- my own first-of-day pick, size gate inside selection
    by_day = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            by_day[r["day"]].append(r)
    picks = []
    for day in sorted(by_day):
        v = sorted(by_day[day], key=lambda r: (r["day"], r["et"], r["sym"]))
        p = next((r for r in v if sizeable(r) is not False), None)
        if p is not None:
            picks.append(p)

    # unit 2 -- my own symbol-day collapse
    symdays = set()
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            if sizeable(r) is not False:
                symdays.add((r["sym"], r["day"]))

    def score(keys, label):
        graded = [k for k in keys if k in grades]
        s = sum(1 for k in graded if grades[k][0] == "S")
        hit = bar_s & set(keys)
        print("%-14s n=%-5d fires/day=%-7.3f precision=%-28s recall=%s"
              % (label, len(keys), len(keys) / sessions, cell(s, len(graded)),
                 cell(len(hit), len(bar_s))))
        return s, len(graded), len(hit)

    k1 = ["%s_%s" % (r["sym"], r["day"]) for r in picks]
    k2 = ["%s_%s" % (sym, day) for sym, day in symdays]

    print("judged symbol-days (marked_card_ids): %d   graded (my resolution): %d"
          % (len(judged), len(grades)))
    print("bar-backed S: %d   contested: %d symbol-days / %d opinion rows"
          % (len(bar_s), contested_n, contested_rows))
    print("book: %s  sessions=%s  %s -> %s"
          % (os.path.basename(BOOK), sessions, meta.get("first"), meta.get("last")))
    print()
    s1, g1, h1 = score(k1, "unit1 pick")
    s2, g2, h2 = score(k2, "unit2 allfires")
    print()
    print("unit1 precision numerator %d vs recall numerator %d -- %s"
          % (s1, h1, "identical" if s1 == h1 else "DIFFER"))

    # sensitivity: drop the ninth spelling
    gr9 = grades_no9
    graded9 = [k for k in k1 if k in gr9]
    s9 = sum(1 for k in graded9 if gr9[k][0] == "S")
    print("unit1 precision WITHOUT the answers.is_s spelling: %s" % cell(s9, len(graded9)))

    # sensitivity: drop the low-confidence derived corpora
    gnd = build_grades(True, drop_derived=True)
    bar_s_nd = {k for k, (g, _c, _n) in gnd.items()
                if g == "S" and os.path.exists(
                    os.path.join(ARCHIVE, k.split("_", 1)[0], k.split("_", 1)[1] + ".csv"))}
    gradednd = [k for k in k1 if k in gnd]
    snd = sum(1 for k in gradednd if gnd[k][0] == "S")
    hitnd = bar_s_nd & set(k1)
    hit2nd = bar_s_nd & set(k2)
    graded2nd = [k for k in k2 if k in gnd]
    s2nd = sum(1 for k in graded2nd if gnd[k][0] == "S")
    print("WITHOUT derived_marks_v*: bar-backed S %d (was %d)" % (len(bar_s_nd), len(bar_s)))
    print("  unit1 precision %s  recall %s" % (cell(snd, len(gradednd)),
                                               cell(len(hitnd), len(bar_s_nd))))
    print("  unit2 precision %s  recall %s" % (cell(s2nd, len(graded2nd)),
                                               cell(len(hit2nd), len(bar_s_nd))))

    # hand-check one Wilson cell
    k, n = s1, g1
    p = k / n
    d = 1 + Z * Z / n
    c = p + Z * Z / (2 * n)
    m = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    print("hand Wilson for %d/%d: p=%.6f centre=%.6f margin=%.6f denom=%.6f -> [%.3f, %.3f]"
          % (k, n, p, c, m, d, (c - m) / d * 100, (c + m) / d * 100))


if __name__ == "__main__":
    main()
