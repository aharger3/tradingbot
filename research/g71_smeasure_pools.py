"""G7.1 / track `smeasure` (part 2) -- where S-graded days pool, and where the
pools disagree.

Austin, 2026-08-29: "s is not pooling as the same."

Every corpus in research/marks/LEDGER.md is enumerated through the SAME
symbol-day normaliser the no-repeat guarantee uses
(research/build_deck.py::_judgement_key), so this file can never count by hand
and can never drift from the guard. What it adds on top is an S EXTRACTOR,
because the corpora do not agree on which FIELD carries an S:

    austin_tier / tier / austin_grade  == "S"       legacy bar-level corpora
    verdict                            == "s"       austin_verdicts.json
    grade                              == "S"       deck + probe day-cards
    answers.grade / answers.your_grade == ["S"]     probe pages (ladder form)
    answers.s / answers.s_call         == ["s"]     probe pages (yes/no form)

The last row is the trap. research/marks/probe_s_sweep_2026-08-28.jsonl -- the
100 blind cards the whole project's recall number is scored on -- carries
"grade": "none" on ALL 100 rows, including the 34 he called S. Any reader that
looks at `grade` sees zero S days in the governing sample.

Read-only. No mark file is written. No engine file is touched.

Usage:
  python research/g71_smeasure_pools.py [--out research/g71_smeasure_pools.json]
"""
from __future__ import annotations
import argparse, json, os, sys
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import research.build_deck as bd  # noqa: E402  the ONE enumerator

# ---------------------------------------------------------------- S extractor

# Field -> the value that means "Austin called this an S".
_SCALAR_S = {
    "austin_tier": {"s"},
    "tier": {"s"},
    "austin_grade": {"s"},
    "grade": {"s"},
    "verdict": {"s"},
}
# answers.<key> -> values meaning S.  A probe answer is a list.
_ANSWER_S = {
    "grade": {"s"},
    "your_grade": {"s"},
    "s": {"s"},
    "s_call": {"s"},
}


def _opinions(row: dict):
    """Every S/not-S opinion this row carries, as a list of bools."""
    vals = []
    for k, yes in _SCALAR_S.items():
        v = str(row.get(k, "")).strip().lower()
        if v and v not in ("none", "null"):
            vals.append(v in yes)
    ans = row.get("answers")
    if isinstance(ans, dict):
        for k, yes in _ANSWER_S.items():
            a = ans.get(k)
            if a:
                first = str(a[0] if isinstance(a, list) else a).strip().lower()
                if first:
                    vals.append(first in yes)
    return vals


def s_verdict(row: dict):
    """-> True (S), False (judged, not S), or None (no opinion about S)."""
    vals = _opinions(row)
    if not vals:
        # `grade: "none"` / `_no_trade: true` is a judgement -- an explicit
        # refusal to trade the day -- and a refusal is not an S.
        if (str(row.get("grade", "")).strip().lower() in ("none", "null")
                or row.get("_no_trade")):
            return False
        return None
    return any(vals)


def row_conflicts(row: dict) -> bool:
    """True when one row's own fields disagree about S-ness."""
    return len(set(_opinions(row))) > 1


def collect():
    """pools[key][corpus] = Counter({True: n_S_rows, False: n_notS_rows})."""
    pools = defaultdict(lambda: defaultdict(Counter))
    per_source = {}
    row_conf = []
    for path in bd.mark_sources():
        name = os.path.relpath(path, HERE).replace("\\", "/")
        n_j = n_s = 0
        for r in bd._rows(path):
            key = bd._judgement_key(r)
            if not key:
                continue
            n_j += 1
            v = s_verdict(r)
            if v is None:
                continue
            pools[key][name][v] += 1
            n_s += int(v)
            if row_conflicts(r):
                row_conf.append({"corpus": name, "key": key})
        per_source[name] = {"judgement_keys": n_j, "S_rows": n_s}
    return pools, per_source, row_conf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "g71_smeasure_pools.json"))
    a = ap.parse_args()

    guard = bd.marked_card_ids()          # the no-repeat enumerator, verbatim
    pools, per_source, row_conf = collect()

    s_days, not_s_days, both = set(), set(), set()
    for key, by_corpus in pools.items():
        says_s = {c for c, t in by_corpus.items() if t[True]}
        says_no = {c for c, t in by_corpus.items() if t[False]}
        if says_s and says_no:
            both.add(key)
        elif says_s:
            s_days.add(key)
        else:
            not_s_days.add(key)

    # split the conflicts: inside one corpus (bar-level granularity, not a
    # disagreement) vs across corpora (two sittings, two answers).
    within, across = [], []
    for key in sorted(both):
        by_corpus = pools[key]
        says_s = {c for c, t in by_corpus.items() if t[True]}
        says_no = {c for c, t in by_corpus.items() if t[False]}
        rec = {"key": key,
               "S_in": sorted(says_s), "notS_in": sorted(says_no),
               "counts": {c: {"S": t[True], "notS": t[False]}
                          for c, t in sorted(by_corpus.items())}}
        # DAY-LEVEL verdict per corpus: a corpus that marked any bar of the day
        # S votes S, because the recall metric asks "did the engine take an
        # entry that day", not "on that bar". So a corpus appearing in BOTH
        # sets is a bar-level granularity artefact, not a disagreement.
        votes_s = says_s
        votes_no = says_no - says_s
        rec["day_votes_S"] = sorted(votes_s)
        rec["day_votes_notS"] = sorted(votes_no)
        if votes_s and votes_no:
            across.append(rec)
        else:
            within.append(rec)

    multi = {k: v for k, v in pools.items() if len(v) > 1}

    res = {
        "enumerator": "research/build_deck.py::marked_card_ids (verbatim) + g71 S extractor",
        "guard_keys_total": len(guard),
        "keys_with_an_S_opinion": len(pools),
        "S_days_unanimous": len(s_days),
        "S_days_contested": len(both),
        "S_days_any": len(s_days) + len(both),
        "notS_days_unanimous": len(not_s_days),
        "keys_in_more_than_one_corpus": len(multi),
        "contested_across_corpora": len(across),
        "contested_within_one_corpus_only": len(within),
        "rows_self_contradicting": len(row_conf),
        "per_source": per_source,
        "across_corpus_conflicts": across,
        "within_corpus_conflicts": within,
        "S_days_unanimous_list": sorted(s_days),
        "S_days_contested_list": sorted(both),
    }

    print(json.dumps({k: v for k, v in res.items()
                      if not isinstance(v, (list, dict))}, indent=2))
    print("\nper corpus (judgement keys / rows carrying an S):")
    for name, d in per_source.items():
        print("  %-58s %5d %5d" % (name, d["judgement_keys"], d["S_rows"]))
    print("\n%d symbol-days appear in >1 corpus; %d carry an S in one corpus "
          "and a NOT-S in another:" % (len(multi), len(across)))
    for rec in across[:60]:
        print("  %-22s S:%-40s notS:%s" % (
            rec["key"],
            ",".join(os.path.basename(x) for x in rec["day_votes_S"])[:40],
            ",".join(os.path.basename(x) for x in rec["day_votes_notS"])[:70]))
    if len(across) > 60:
        print("  ... %d more" % (len(across) - 60))

    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print("\nwrote " + a.out)


if __name__ == "__main__":
    main()
