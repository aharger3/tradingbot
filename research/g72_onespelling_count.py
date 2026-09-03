"""G7.2 / `onespelling` -- the one S-day count, the spelling table, and the proof
that the no-repeat guarantee got stronger and not weaker.

Everything here reads through `research/grade_read.py::read_grade` -- the one
grade reader -- and enumerates symbol-days through
`research/build_deck.py::_judgement_key`, the enumerator of record. Nothing is
counted by hand. No mark file is opened for writing.

Three things it prints and writes to research/g72_onespelling_count.json:

  1. the S-day count, the way it splits across the eight spellings, and how many
     days each spelling can see on its own;
  2. a per-corpus table: which file spells the grade which way;
  3. the guard proof -- the PRE-change judgement predicate is reimplemented
     verbatim below and the two exclusion pools are diffed. The new pool must be
     a superset of the old one, and no day may leave it.

Usage:
  python research/g72_onespelling_count.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as bd          # noqa: E402  the enumerator of record
import grade_read                # noqa: E402  the one grade reader

OUT = os.path.join(HERE, "g72_onespelling_count.json")

# ---------------------------------------------------------------- the old reader

_OLD_GRADE_KEYS = ("austin_tier", "tier", "austin_grade", "grade", "verdict")


def _old_is_judgement(row: dict) -> bool:
    """`build_deck._judgement_key`'s gate as it stood before this change, copied
    here so the before/after diff is a real measurement and not an assertion."""
    graded = any(str(row.get(k, "")).strip() for k in _OLD_GRADE_KEYS)
    answers = row.get("answers")
    answered = isinstance(answers, dict) and any(answers.values())
    return bool(graded or answered or row.get("_no_trade"))


def _old_key(row: dict):
    """The pre-change key: the old gate, then _judgement_key's own id logic."""
    if not _old_is_judgement(row):
        return None
    symbol = row.get("symbol")
    day = row.get("date") or row.get("day")
    if not (symbol and day):
        ident = row.get("card_id") or row.get("id") or row.get("card")
        if not ident:
            return None
        m = bd._ID_RE.search(str(ident))
        if not m:
            return None
        symbol, day = m.group(1), m.group(2)
    return "%s_%s" % (symbol, day)


def _old_is_s(row: dict) -> bool:
    """The S test every grade-field reader in this repo used: a scalar field."""
    for k in _OLD_GRADE_KEYS:
        if str(row.get(k, "")).strip().lower() == "s":
            return True
    return False


# ---------------------------------------------------------------- collection

def main() -> int:
    per_corpus = {}
    s_by_field = defaultdict(set)          # field -> {symbol-day}
    field_rows = Counter()                 # field -> rows whose grade came from it
    day_grades = defaultdict(set)          # symbol-day -> {grades}
    day_sources = defaultdict(set)         # symbol-day -> {corpus that says S}
    day_not_s = defaultdict(set)           # symbol-day -> {corpus that says not-S}
    old_scalar_s = set()
    row_conflicts = 0
    old_pool, new_pool = set(), set()

    for path in bd.mark_sources():
        name = os.path.relpath(path, HERE).replace("\\", "/")
        fields = Counter()
        keys = s_keys = 0
        for row in bd._rows(path):
            if _old_key(row):
                old_pool.add(_old_key(row))
            key = bd._judgement_key(row)
            if not key:
                continue
            new_pool.add(key)
            keys += 1
            g = grade_read.read_grade(row)
            if g is None:
                continue
            src = grade_read.grade_field(row)
            fields[src] += 1
            field_rows[src] += 1
            day_grades[key].add(g)
            if grade_read.conflicting(row):
                row_conflicts += 1
            if g == "S":
                s_keys += 1
                s_by_field[src].add(key)
                day_sources[key].add(name)
            else:
                day_not_s[key].add(name)
            if _old_is_s(row):
                old_scalar_s.add(key)
        per_corpus[name] = {
            "judged_symbol_days": keys,
            "S_rows": s_keys,
            "spellings": dict(fields.most_common()),
        }

    s_days = {k for k, gs in day_grades.items() if "S" in gs}
    invisible = s_days - old_scalar_s
    contested = {k for k in s_days if day_not_s.get(k) and day_sources.get(k)
                 and set(day_not_s[k]) - set(day_sources[k])}

    res = {
        "reader": "research/grade_read.py::read_grade",
        "enumerator": "research/build_deck.py::_judgement_key (called, not copied)",
        "judged_symbol_days": len(new_pool),
        "S_days_ONE_TRUE_COUNT": len(s_days),
        "S_days_a_scalar_grade_field_can_see": len(old_scalar_s),
        "S_days_invisible_to_a_grade_field_reader": len(invisible),
        "S_days_contested_across_corpora": len(contested),
        "rows_that_contradict_themselves": row_conflicts,
        "S_days_by_spelling": {f: len(v) for f, v in
                               sorted(s_by_field.items(), key=lambda kv: -len(kv[1]))},
        "rows_by_spelling": dict(field_rows.most_common()),
        "guard_pool_before": len(old_pool),
        "guard_pool_after": len(new_pool),
        "guard_days_lost": sorted(old_pool - new_pool),
        "guard_days_gained": sorted(new_pool - old_pool),
        "per_corpus": per_corpus,
        "S_days": sorted(s_days),
        "S_days_invisible_list": sorted(invisible),
        "S_days_contested_list": sorted(contested),
    }

    print("THE ONE S-DAY COUNT: %d" % len(s_days))
    print("  a scalar grade field alone sees   %d" % len(old_scalar_s))
    print("  invisible without the answers.*   %d" % len(invisible))
    print("  contested (S here, not-S there)   %d" % len(contested))
    print("\nS days each spelling can see on its own:")
    for f, v in sorted(s_by_field.items(), key=lambda kv: -len(kv[1])):
        print("  %-20s %4d" % (f, len(v)))

    print("\nwhich file spells it which way (judged days / S rows / spellings):")
    for name, d in sorted(per_corpus.items()):
        print("  %-52s %4d %4d  %s" % (
            name, d["judged_symbol_days"], d["S_rows"],
            ", ".join("%s=%d" % kv for kv in d["spellings"].items()) or "-"))

    print("\nNO-REPEAT GUARANTEE  before %d  ->  after %d  (lost %d, gained %d)"
          % (len(old_pool), len(new_pool),
             len(old_pool - new_pool), len(new_pool - old_pool)))

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print("wrote " + OUT)

    if old_pool - new_pool:
        print("FAIL the exclusion pool lost days: %s" % sorted(old_pool - new_pool)[:20])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
