"""g109 -- what the engine's own S grade is worth as a CLASSIFIER of his S.

OMEN-MASTER-SPEC quoted "35.0% precise, 20.9% recall" with no committed script,
and on a unit (first candidate of the day) that contradicts the rest of the
document (first SIZE-GATED candidate). Both are computed here, on the same pool,
so the number that ships names its unit.

Unit: the judged symbol-day. Positive = Austin graded that symbol-day S.
Prediction = the sgrade the engine stamped on that symbol-day's first candidate.
No bars, no replay -- book stamp plus marks pool only.

    python research/g109_sgrade_precision.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402
import g102_wait_for_the_open as g102             # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_JSON = os.path.join(HERE, "g109_sgrade_precision.json")


def main():
    from research import marks_pool as mp
    pool = mp.canonical_pool()
    s_days = set(mp.s_days(pool))
    judged = set(pool)

    b = json.load(open(BOOK, encoding="utf-8"))
    rows = b["trades"] if isinstance(b, dict) else b
    bysd = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            bysd["%s_%s" % (r["sym"], r["day"])].append(r)
    for v in bysd.values():
        v.sort(key=g86.ekey)

    out = {}
    for unit, pick in (("first candidate", lambda v: v[0]),
                       ("first size-gated candidate",
                        lambda v: next((r for r in v if g102.sized(r)), None))):
        pop = {}
        for k in bysd:
            if k not in judged:
                continue
            r = pick(bysd[k])
            if r is None:
                continue
            pop[k] = r.get("sgrade")
        n = len(pop)
        pos = sum(1 for k in pop if k in s_days)
        print("=== %s ===" % unit)
        print("judged symbol-days with one: %d ; his S: %d ; base rate %.1f%%"
              % (n, pos, 100 * pos / n))
        print("| sgrade | n | precision | recall |")
        print("|---|---:|---:|---:|")
        rec = {"n": n, "s_days": pos, "base_rate": round(100 * pos / n, 1), "grades": {}}
        for g in ("S", "A", "C", "X", None):
            v = [k for k in pop if pop[k] == g]
            if not v:
                continue
            tp = sum(1 for k in v if k in s_days)
            print("| %s | %d | %.1f%% | %.1f%% |"
                  % (g, len(v), 100 * tp / len(v), 100 * tp / pos))
            rec["grades"][str(g)] = {"n": len(v), "tp": tp,
                                     "precision": round(100 * tp / len(v), 1),
                                     "recall": round(100 * tp / pos, 1)}
        print()
        out[unit] = rec

    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    main()
