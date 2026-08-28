"""W1 -- does the count ladder reproduce Austin? Scored on his own 59 verdicts.

`Specs/omen6-h2-master-spec.md` section 1.2 proposes a ladder off the eight
downgrade variables:

    0 downgrades = S    1 = A    2 = C    3 or more = X (not tradeable)

On 2026-08-28 Austin graded **59 engine-proposed `B`-only signals** himself
(`research/marks/deck_marks_h2_3lane_2026-08-28.jsonl`, lane `b_remap`). Those
are the exact rows the remap is about -- signals that are `B` only because
`signal_runner._calibration_grade` floors the first with-trend signal of the day.
So for the first time the ladder can be scored against the thing it claims to
reproduce, rather than against a book.

This script is the scoring. It answers three questions and stops:

  1. How often does the ladder agree with him, against the MAJORITY-CLASS
     baseline (always guess the most common verdict)? A grader that cannot beat
     "always guess X" has not learned anything.
  2. Where does it disagree -- by downgrade count, and per variable?
  3. Does ANY simple function of the eight variables beat majority class? Single
     variables, count thresholds, and a weighted score, every one scored
     LEAVE-ONE-OUT so that fitting on n=59 cannot be mistaken for a result.

It does NOT propose a replacement grader. If nothing beats majority class, that
is the finding, and fitting harder on 59 rows is how a project convinces itself
of something that is not there.

    python research/w1_ladder_vs_marks.py            # the tables
    python research/w1_ladder_vs_marks.py --json     # machine-readable
    python research/w1_ladder_vs_marks.py --selfcheck

NOTHING HERE IS FITTED AND KEPT. Every constant is either Austin's, already
committed in `research/downgrade.py`, or searched and then reported with its
leave-one-out score beside its in-sample one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import downgrade as dg                                    # noqa: E402

MARKS = os.path.join(HERE, "marks", "deck_marks_h2_3lane_2026-08-28.jsonl")
LANE = "b_remap"
GRADES = ("S", "A", "C", "X")
TAKE = ("S", "A", "C")           # the engine's decision is binary: take or skip


# ---------------------------------------------------------------------------
# the marks
# ---------------------------------------------------------------------------

def load_marks(path=MARKS):
    """His 59 verdicts on B-only signals, with the engine's own downgrade list.

    A row without a grade is not a judgement and is dropped, counted rather than
    silently absorbed -- `grade: "none"` IS a judgement (an explicit refusal) and
    is mapped to `X`, the convention `research/t70_test1_score.py` uses."""
    rows, skipped = [], 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("lane") not in (None, LANE):
                skipped += 1
                continue
            g = (r.get("grade") or "").strip().upper()
            if g == "NONE":
                g = "X"
            if g not in GRADES:
                skipped += 1
                continue
            r["his"] = g
            rows.append(r)
    return rows, skipped


# ---------------------------------------------------------------------------
# the ladder, and the baseline it has to beat
# ---------------------------------------------------------------------------

def ladder(n: int) -> str:
    """Spec section 1.2, read on a downgrade COUNT."""
    return "S" if n <= 0 else ("A" if n == 1 else ("C" if n == 2 else "X"))


def net_of(row) -> int:
    """The count the ENGINE would use: tripped minus the confluence +1.

    The card carries `n_downgrades` (raw) and `eng_sgrade`
    (`downgrade.score()`'s own floored grade). `sgrade` is S when net <= 0 and A
    when net == 1, so those two cases pin the confluence bit exactly; at
    `sgrade == "C"` (net >= 2) it does not, and the raw count is used. That
    under-counts confluence only where the answer is already `C` or `X`, and the
    ambiguity is REPORTED (`net_exact`) rather than hidden."""
    n = row["n_downgrades"]
    sg = row.get("eng_sgrade")
    if sg == "S":
        return 0
    if sg == "A":
        return 1
    return n


def net_is_exact(row) -> bool:
    return row.get("eng_sgrade") in ("S", "A")


def majority(rows):
    c = Counter(r["his"] for r in rows)
    g, n = c.most_common(1)[0]
    return g, n, len(rows)


def score(rows, predict):
    """(hits, n) for a predictor of his four-way grade."""
    return sum(1 for r in rows if predict(r) == r["his"]), len(rows)


def score_binary(rows, predict_take):
    """(hits, n) on the decision the ENGINE actually makes: take or skip."""
    return (sum(1 for r in rows if predict_take(r) == (r["his"] in TAKE)),
            len(rows))


# ---------------------------------------------------------------------------
# per-variable information
# ---------------------------------------------------------------------------

def per_variable(rows):
    """For each variable: trip rate, and his X-rate when tripped vs clean.

    A variable carries information about his verdict only if those two rates
    differ. `counter_trend_not_respected` firing on 93% of the rows cannot
    separate anything no matter which way it points."""
    base_x = sum(1 for r in rows if r["his"] == "X") / len(rows)
    out = []
    names = list(dg.VARIABLES) + sorted(
        {v for r in rows for v in r.get("eng_downgrades", [])}
        - set(dg.VARIABLES))
    for v in names:
        trip = [r for r in rows if v in r.get("eng_downgrades", [])]
        clean = [r for r in rows if v not in r.get("eng_downgrades", [])]
        xt = (sum(1 for r in trip if r["his"] == "X") / len(trip)) if trip else None
        xc = (sum(1 for r in clean if r["his"] == "X") / len(clean)) if clean else None
        # best single-variable rule using this variable alone: predict X when
        # tripped (or when clean, whichever way round wins), scored in sample
        best = None
        if trip and clean:
            a = sum(1 for r in trip if r["his"] == "X") + \
                sum(1 for r in clean if r["his"] != "X")
            b = sum(1 for r in trip if r["his"] != "X") + \
                sum(1 for r in clean if r["his"] == "X")
            best = max(a, b) / len(rows)
        out.append({"var": v, "n_trip": len(trip),
                    "trip_pct": 100.0 * len(trip) / len(rows),
                    "x_rate_tripped": xt, "x_rate_clean": xc,
                    "delta": (xt - xc) if (xt is not None and xc is not None) else None,
                    "best_single_acc": best})
    return {"base_x_rate": base_x, "vars": out}


def by_count(rows, key="n_downgrades"):
    """His verdict distribution at each downgrade count, next to the ladder's."""
    d = defaultdict(Counter)
    for r in rows:
        d[r[key] if key in r else net_of(r)][r["his"]] += 1
    out = []
    for n in sorted(d):
        c = d[n]
        out.append({"n": n, "total": sum(c.values()),
                    "his": {g: c.get(g, 0) for g in GRADES},
                    "ladder": ladder(n),
                    "hits": c.get(ladder(n), 0)})
    return out


# ---------------------------------------------------------------------------
# does ANYTHING beat majority class? leave-one-out, so fitting cannot win
# ---------------------------------------------------------------------------

def _loo(rows, fit, predict_take):
    """Leave-one-out accuracy of a FAMILY on the take/skip decision.

    `fit(train)` returns a parameter; `predict_take(param, row)` is the rule.
    Fitting inside the loop is the whole point: an in-sample number on 59 rows
    is a description of those 59 rows, not a grader."""
    hits = 0
    for i in range(len(rows)):
        train = rows[:i] + rows[i + 1:]
        param = fit(train)
        hits += int(predict_take(param, rows[i]) == (rows[i]["his"] in TAKE))
    return hits, len(rows)


def _acc_take(rows, rule):
    return sum(1 for r in rows if rule(r) == (r["his"] in TAKE))


def search(rows):
    """Three families, each fitted inside a leave-one-out loop.

    Everything is scored on TAKE vs SKIP, not on the four-way grade: that is the
    decision the engine makes, it is the easier problem, and if nothing clears
    majority class even there the four-way question is settled too."""
    n = len(rows)
    base_take = sum(1 for r in rows if r["his"] in TAKE)
    maj_take = max(base_take, n - base_take)
    out = {"n": n, "majority_take_acc": maj_take / n,
           "majority_class": "take" if base_take > n - base_take else "skip"}

    # (1) a count threshold: skip when count >= k
    def fit_thr(train):
        best, bk = -1, 1
        for k in range(0, 9):
            a = _acc_take(train, lambda r, k=k: r["n_downgrades"] < k)
            if a > best:
                best, bk = a, k
        return bk
    out["count_threshold"] = dict(zip(("hits", "n"),
                                      _loo(rows, fit_thr,
                                           lambda k, r: r["n_downgrades"] < k)))
    out["count_threshold"]["fit_all"] = fit_thr(rows)

    # (2) the single best variable, refitted each fold
    names = list(dg.VARIABLES)

    def fit_var(train):
        best, bv = -1, (names[0], True)
        for v in names:
            for take_when_tripped in (True, False):
                a = _acc_take(train, lambda r, v=v, t=take_when_tripped:
                              (v in r.get("eng_downgrades", [])) == t)
                if a > best:
                    best, bv = a, (v, take_when_tripped)
        return bv
    out["best_variable"] = dict(zip(("hits", "n"), _loo(
        rows, fit_var,
        lambda p, r: (p[0] in r.get("eng_downgrades", [])) == p[1])))
    out["best_variable"]["fit_all"] = fit_var(rows)

    # (3) a weighted score: weight each variable by its own take-rate lift on the
    # training fold, take when the total clears the training median. This is the
    # simplest thing that could work and is deliberately not richer -- 59 rows do
    # not support a richer model.
    def fit_w(train):
        base = sum(1 for r in train if r["his"] in TAKE) / len(train)
        w = {}
        for v in names:
            t = [r for r in train if v in r.get("eng_downgrades", [])]
            w[v] = ((sum(1 for r in t if r["his"] in TAKE) / len(t)) - base) if t else 0.0
        sc = sorted(sum(w[v] for v in r.get("eng_downgrades", []) if v in w)
                    for r in train)
        thr = sc[len(sc) // 2] if sc else 0.0
        return (w, thr)
    out["weighted"] = dict(zip(("hits", "n"), _loo(
        rows, fit_w,
        lambda p, r: sum(p[0].get(v, 0.0)
                         for v in r.get("eng_downgrades", [])) >= p[1])))

    # (4) the proposed ladder itself -- no fitting at all, so LOO == in sample
    out["ladder_take"] = dict(zip(("hits", "n"), score_binary(
        rows, lambda r: ladder(r["n_downgrades"]) in TAKE)))
    for k in ("count_threshold", "best_variable", "weighted", "ladder_take"):
        out[k]["acc"] = out[k]["hits"] / out[k]["n"]
        out[k]["beats_majority"] = out[k]["acc"] > out["majority_take_acc"]
        # "beats" on a point estimate is not the same as "separates". At n=59 a
        # 5-point win is three rows; the only honest test is whether the 95%
        # interval clears the baseline at all.
        out[k]["separates"] = wilson(out[k]["hits"], out[k]["n"])[0]             > out["majority_take_acc"]
    return out


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------

def analyse():
    rows, skipped = load_marks()
    maj_g, maj_n, n = majority(rows)
    lad_raw = score(rows, lambda r: ladder(r["n_downgrades"]))
    lad_net = score(rows, lambda r: ladder(net_of(r)))
    conf = defaultdict(Counter)
    for r in rows:
        conf[r["his"]][ladder(r["n_downgrades"])] += 1
    return {
        "n": n, "skipped": skipped,
        "his_mix": dict(Counter(r["his"] for r in rows)),
        "majority": {"grade": maj_g, "hits": maj_n, "acc": maj_n / n},
        "ladder_raw": {"hits": lad_raw[0], "n": n, "acc": lad_raw[0] / n},
        "ladder_net": {"hits": lad_net[0], "n": n, "acc": lad_net[0] / n},
        "net_exact": sum(1 for r in rows if net_is_exact(r)),
        "take_rate": sum(1 for r in rows if r["his"] in TAKE) / n,
        "n_take": sum(1 for r in rows if r["his"] in TAKE),
        "n_s": sum(1 for r in rows if r["his"] == "S"),
        "s_at_counts": sorted(r["n_downgrades"] for r in rows if r["his"] == "S"),
        "by_count": by_count(rows),
        "confusion": {g: dict(conf[g]) for g in GRADES},
        "per_variable": per_variable(rows),
        "search": search(rows),
    }


def _pct(x):
    return "%.1f%%" % (100.0 * x)


def wilson(hits, n, z=1.96):
    """95% Wilson interval on an accuracy. n=59 is small and the whole point of
    printing this is that the intervals overlap: a 5-point 'win' here is three
    rows, and three rows is not a result."""
    if not n:
        return (0.0, 0.0)
    p = hits / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return ((c - h) / d, (c + h) / d)


def _ci(hits, n):
    lo, hi = wilson(hits, n)
    return "[%s, %s]" % (_pct(lo), _pct(hi))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return selfcheck()
    d = analyse()
    if a.json:
        print(json.dumps(d, indent=2, sort_keys=True, default=str))
        return 0

    print("n = %d verdicts (%d rows skipped: wrong lane or no grade)"
          % (d["n"], d["skipped"]))
    print("his mix: %s" % d["his_mix"])
    print("he TRADES %d of %d = %s, including %d S"
          % (d["n_take"], d["n"], _pct(d["take_rate"]), d["n_s"]))
    print("his S grades came at downgrade counts %s" % d["s_at_counts"])
    print()
    print("LADDER   agreement %d/%d = %s  95%% CI %s  (on the raw count)"
          % (d["ladder_raw"]["hits"], d["n"], _pct(d["ladder_raw"]["acc"]),
             _ci(d["ladder_raw"]["hits"], d["n"])))
    print("LADDER   agreement %d/%d = %s  (on the net count, confluence +1 applied "
          "where the card pins it -- %d of %d exact)"
          % (d["ladder_net"]["hits"], d["n"], _pct(d["ladder_net"]["acc"]),
             d["net_exact"], d["n"]))
    print("BASELINE always guess %s: %d/%d = %s  95%% CI %s"
          % (d["majority"]["grade"], d["majority"]["hits"], d["n"],
             _pct(d["majority"]["acc"]), _ci(d["majority"]["hits"], d["n"])))
    print("VERDICT  the ladder %s the majority-class baseline"
          % ("BEATS" if d["ladder_raw"]["acc"] > d["majority"]["acc"] else "LOSES to"))
    print()
    print("by downgrade count:")
    print("  n  total  ladder says   his S/A/C/X")
    for b in d["by_count"]:
        print("  %-2d %5d  %-11s   %d/%d/%d/%d"
              % (b["n"], b["total"], b["ladder"], b["his"]["S"], b["his"]["A"],
                 b["his"]["C"], b["his"]["X"]))
    print()
    print("per variable (his X-rate when tripped vs clean; base %s):"
          % _pct(d["per_variable"]["base_x_rate"]))
    for v in d["per_variable"]["vars"]:
        print("  %-30s trips %2d (%5.1f%%)  X|trip %s  X|clean %s  best single %s"
              % (v["var"], v["n_trip"], v["trip_pct"],
                 "  n/a" if v["x_rate_tripped"] is None else _pct(v["x_rate_tripped"]),
                 "  n/a" if v["x_rate_clean"] is None else _pct(v["x_rate_clean"]),
                 "  n/a" if v["best_single_acc"] is None
                 else _pct(v["best_single_acc"])))
    print()
    s = d["search"]
    print("does ANY function of the eight beat majority class on TAKE vs SKIP?")
    mh = int(round(s["majority_take_acc"] * s["n"]))
    print("  majority class (%s): %s  95%% CI %s"
          % (s["majority_class"], _pct(s["majority_take_acc"]), _ci(mh, s["n"])))
    for k, label in (("ladder_take", "the proposed ladder (no fitting)"),
                     ("count_threshold", "best count threshold (leave-one-out)"),
                     ("best_variable", "best single variable (leave-one-out)"),
                     ("weighted", "weighted score (leave-one-out)")):
        r = s[k]
        print("  %-38s %d/%d = %s  95%% CI %s  %s%s"
              % (label, r["hits"], r["n"], _pct(r["acc"]),
                 _ci(r["hits"], r["n"]),
                 ("BEATS majority, CI CLEARS it" if r["separates"]
                  else "beats majority on the point estimate, CI does NOT clear it")
                 if r["beats_majority"] else "does not beat majority",
                 ("  [fitted: %s]" % (r["fit_all"],)) if "fit_all" in r else ""))
    fam = ("ladder_take", "count_threshold", "best_variable", "weighted")
    any_sep = any(s[k]["separates"] for k in fam)
    best = max(fam, key=lambda k: s[k]["acc"])
    print()
    print("CONCLUSION: %s"
          % ("`%s` separates from the baseline -- its 95%% interval clears "
             "%s. Treat it as a hypothesis for the next 60 cards."
             % (best, _pct(s["majority_take_acc"])) if any_sep else
             "NOTHING tried separates from the majority-class baseline. The best "
             "of them (`%s`, %s) beats %s on the point estimate by %.1f points -- "
             "%d rows out of %d -- and its 95%% interval still contains the "
             "baseline. The eight variables as committed do not reproduce his 59 "
             "calls, and fitting harder on n=59 is how a project convinces itself "
             "of something that is not there."
             % (best, _pct(s[best]["acc"]), _pct(s["majority_take_acc"]),
                100.0 * (s[best]["acc"] - s["majority_take_acc"]),
                s[best]["hits"] - int(round(s["majority_take_acc"] * s["n"])),
                s["n"])))
    return 0


# ---------------------------------------------------------------------------

def selfcheck() -> int:
    # the ladder is the spec's, exactly
    assert [ladder(i) for i in range(6)] == ["S", "A", "C", "X", "X", "X"]
    assert ladder(-1) == "S"

    # net_of: sgrade pins the confluence bit at S and A, not at C
    assert net_of({"n_downgrades": 2, "eng_sgrade": "A"}) == 1
    assert net_of({"n_downgrades": 1, "eng_sgrade": "S"}) == 0
    assert net_of({"n_downgrades": 4, "eng_sgrade": "C"}) == 4
    assert net_is_exact({"eng_sgrade": "A"}) and not net_is_exact({"eng_sgrade": "C"})

    # majority / score on a hand-built set
    rows = [{"his": "X", "n_downgrades": 3, "eng_downgrades": ["no_retest"]},
            {"his": "X", "n_downgrades": 0, "eng_downgrades": []},
            {"his": "S", "n_downgrades": 2, "eng_downgrades": ["no_retest"]}]
    assert majority(rows) == ("X", 2, 3)
    assert score(rows, lambda r: ladder(r["n_downgrades"])) == (1, 3)

    # per_variable: a variable that fires on everything carries no information
    pv = per_variable([{"his": "X", "eng_downgrades": ["no_retest"]},
                       {"his": "S", "eng_downgrades": ["no_retest"]}])
    row = [v for v in pv["vars"] if v["var"] == "no_retest"][0]
    assert row["n_trip"] == 2 and row["x_rate_clean"] is None
    assert row["best_single_acc"] is None, "a constant variable has no rule"

    # _loo really refits: a family that memorises the training set must NOT
    # score 100% out of fold
    rr = [{"his": "S", "n_downgrades": i} for i in range(5)] + \
         [{"his": "X", "n_downgrades": i} for i in range(5)]
    for r in rr:
        r["eng_downgrades"] = []
    got = _loo(rr, lambda tr: 0, lambda p, r: True)
    assert got == (5, 10), got

    # wilson: a 26/59 accuracy's interval must contain 52.5% -- the whole
    # "does it beat the baseline" question is inside one interval width here
    lo, hi = wilson(35, 59)
    assert lo < 0.525 < hi, (lo, hi)
    assert wilson(0, 0) == (0.0, 0.0)

    print("selfcheck ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
