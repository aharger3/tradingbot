"""marks_pool.py -- ONE canonical (symbol, date, austin_grade) view, every corpus.

Answers the problem `research/g71_board.md` reported and left unfixed:

    "Your S grade is not stored in one place. Five different fields mean S
     across your 19 mark files, and 48 of your S days are invisible to any
     tool that reads a grade field -- including all 34 S days in the 100-card
     sweep, which are filed as grade:"none" with the real answer somewhere
     else. Three different S-day counts are already published in this repo:
     154, 207, 288."

That board note undercounted its own problem: by the time it was written,
`research/grade_read.py` already knew of EIGHT spellings, not five (see
`research/g72_onespelling.md`). This file adds a NINTH, found tonight
(2026-08-29) in the g71 homework deck's third lane -- see SPELLINGS below --
and is now the single place any future script should read a grade from when
it wants ONE grade per symbol-day rather than grade_read's per-row opinion.

Read-only. No mark file is opened for writing. No corpus is touched. This
module reuses two things that already exist rather than re-walking the
corpora by hand:

  * `research/build_deck.py::mark_sources()` -- every path that carries a
    human judgement (research/marks/*.jsonl + the LEGACY_MARK_FILES list).
  * `research/build_deck.py::_judgement_key()` -- the SYMBOL_YYYY-MM-DD
    normaliser the no-repeat guarantee already depends on, including its
    fixes for prefixed card_ids and _no_trade rows.
  * `research/grade_read.py::grade_opinions()` -- the eight-spelling reader.

What this file adds on top of both: a NINTH spelling (answers.is_s, tonight's
homework file), and a CROSS-CORPUS resolution rule that collapses possibly
several opinions about one symbol-day (one per corpus it appears in) down to
ONE canonical grade -- something neither `build_deck.graded_days()` (returns
a *set* of grades per day) nor `grade_read.read_grade()` (resolves conflicts
*within* a single row, not across rows) does today.

Usage:
    python research/marks_pool.py                 # prints the report figures
    python research/marks_pool.py --out research/marks_pool.json

    import marks_pool
    pool = marks_pool.canonical_pool()             # {SYM_DATE: PoolEntry}
    marks_pool.s_days(pool)                        # -> set of SYM_DATE
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict, namedtuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as bd          # noqa: E402  the one enumerator + key normaliser
import grade_read as gr          # noqa: E402  the eight-spelling reader

ARCHIVE = os.path.join(ROOT, "data_archive")

# --------------------------------------------------------------- the ninth spelling

# grade_read.py's ANSWER_YESNO_FIELDS is ("s", "s_call") -- verified against
# every corpus on disk tonight (grep for '"is_s"' across research/*.jsonl and
# research/marks/*.jsonl): only two files use it, both are tonight's homework
# deck, `research/marks/probe_g71_homework_s3_2026-08-29.jsonl` (25 rows, an
# earlier autosave) and `..._complete.jsonl` (30 rows, the final export -- a
# strict superset of the 25). grade_read.read_grade() returns None for all 30
# rows of the complete file -- confirmed by running it before this module
# existed. Handled HERE, not by editing grade_read.py: that keeps every
# already-published number in this repo byte-identical, at the cost of one
# more place a future spelling could hide. Flagged as a follow-up in the
# report this module prints.
_IS_S_YES = {"yes", "y", "true", "1", "s"}
_IS_S_NO = {"no", "n", "false", "0"}

# Every field name this module has ever seen carry a grade opinion, in the
# order grade_read.py checks them, plus the ninth appended at the end. This
# is the full spelling list the report enumerates -- NOT "five" (the board
# note), NOT "eight" (grade_read.py before tonight): nine.
SPELLINGS = tuple(gr.ALL_FIELDS) + ("answers.is_s",)

# Austin's four-value ladder, plus the two things that are NOT a grade of the
# day: "B" (17 legacy rows, kept, never invented -- grade_read.py's own words)
# and "X" (a refusal AIMED AT THE ENGINE -- "this specific detection was
# wrong" -- not a day-level "I would not trade this", per
# research/marks/LEDGER.md and research/g72_onespelling.md). Precedence is
# "best answer wins", the same rule this codebase already applies to S alone
# (`build_deck.s_days()`'s union rule) carried uniformly down the whole
# ladder. X and none tie at the bottom: neither is a positive grade, and a
# day where every opinion is X-or-none about equally means "no trade here",
# which is exactly what the "none" bucket already means.
_RANK = {"S": 0, "A": 1, "B": 2, "C": 3, "none": 4, "X": 4}


def _is_s_opinion(row):
    """The ninth spelling: answers.is_s -> ('S' | 'none', field) or (None, None)."""
    ans = row.get("answers")
    if not isinstance(ans, dict) or "is_s" not in ans:
        return None
    v = ans["is_s"]
    if isinstance(v, (list, tuple)):
        v = v[0] if v else None
    if v is None:
        return None
    t = str(v).strip().lower()
    if t in _IS_S_YES:
        return ("answers.is_s", "S")
    if t in _IS_S_NO:
        return ("answers.is_s", "none")
    return None


def row_opinions(row):
    """Every grade opinion ONE row carries -- the eight known spellings from
    grade_read.py, plus the ninth. (field, grade) tuples, precedence order."""
    ops = list(gr.grade_opinions(row))
    extra = _is_s_opinion(row)
    if extra is not None:
        ops.append(extra)
    return ops


def row_grade(row):
    """One row's own grade under the same precedence grade_read.read_grade()
    uses (an S anywhere in the row wins; else the first non-'none' opinion;
    else 'none' if the row said anything; else None) -- just fed the extended
    nine-spelling opinion list instead of the eight-spelling one."""
    ops = row_opinions(row)
    if not ops:
        return None
    for _field, g in ops:
        if g == "S":
            return "S"
    for _field, g in ops:
        if g != "none":
            return g
    return "none"


def has_bars(symbol, date):
    return os.path.exists(os.path.join(ARCHIVE, symbol, date + ".csv"))


def _relname(path):
    return os.path.relpath(path, HERE).replace("\\", "/")


PoolEntry = namedtuple("PoolEntry", [
    "symbol", "date", "grade", "raw_grades", "sources", "n_opinions",
    "contested", "has_bars",
])


def _bucket(g):
    """Collapse X into the same reporting bucket as none -- see _RANK above."""
    return "none" if g in ("none", "X") else g


def build_pool():
    """Every judged symbol-day, one entry each, resolved across corpora.

    Returns (pool: {key: PoolEntry}, per_source: {name: {...}}, field_counts:
    Counter(field -> n rows carrying an opinion in that field)).
    """
    by_key = defaultdict(list)   # key -> [(source_name, row_grade)]
    per_source = {}
    field_counts = Counter()
    field_s_counts = Counter()

    for path in bd.mark_sources():
        name = _relname(path)
        n_rows_with_key = 0
        n_rows_with_grade = 0
        for row in bd._rows(path):
            key = bd._judgement_key(row)
            if not key:
                continue
            n_rows_with_key += 1
            for field, g in row_opinions(row):
                field_counts[field] += 1
                if g == "S":
                    field_s_counts[field] += 1
            g = row_grade(row)
            if g is None:
                continue
            n_rows_with_grade += 1
            by_key[key].append((name, g))
        per_source[name] = {
            "rows_with_judgement_key": n_rows_with_key,
            "rows_with_grade": n_rows_with_grade,
        }

    pool = {}
    for key, opinions in by_key.items():
        symbol, date = key.split("_", 1)
        buckets_here = {_bucket(g) for _s, g in opinions}
        best_bucket = min(buckets_here, key=lambda b: _RANK[b])
        # Prefer a literal value over the collapsed bucket when reporting the
        # grade itself: "none" bucket could be all-X, all-"none", or a mix --
        # keep the literal set so nothing is silently folded away.
        raw_here = sorted({g for _s, g in opinions})
        if best_bucket == "none":
            canonical_grade = "none"   # X reported separately, see raw_grades
        else:
            canonical_grade = best_bucket
        pool[key] = PoolEntry(
            symbol=symbol, date=date, grade=canonical_grade,
            raw_grades=raw_here, sources=sorted({s for s, _g in opinions}),
            n_opinions=len(opinions),
            contested=len(buckets_here) > 1,
            has_bars=has_bars(symbol, date),
        )
    return pool, per_source, field_counts, field_s_counts


def canonical_pool():
    """The public entry point: {SYMBOL_YYYY-MM-DD: PoolEntry}."""
    pool, _per_source, _fc, _fsc = build_pool()
    return pool


def s_days(pool=None):
    pool = pool if pool is not None else canonical_pool()
    return {k for k, e in pool.items() if e.grade == "S"}


def grade_counts(pool=None):
    pool = pool if pool is not None else canonical_pool()
    return Counter(e.grade for e in pool.values())


def x_only_days(pool=None):
    """Days bucketed 'none' whose only literal opinions were X (engine
    refusal), never a literal 'none' (day refusal) -- reported so the two
    are not silently merged into one meaning."""
    pool = pool if pool is not None else canonical_pool()
    return {k for k, e in pool.items()
            if e.grade == "none" and set(e.raw_grades) == {"X"}}


# --------------------------------------------------------------------- report

def build_report(pool, per_source, field_counts, field_s_counts):
    counts = grade_counts(pool)
    total = len(pool)
    contested = [k for k, e in pool.items() if e.contested]
    contested_rows = sum(pool[k].n_opinions for k in contested)
    bars_yes = sum(1 for e in pool.values() if e.has_bars)
    x_only = x_only_days(pool)
    literal_none = sum(1 for e in pool.values()
                        if e.grade == "none" and "none" in e.raw_grades)

    return {
        "total_symbol_days": total,
        "grade_counts": {
            "S": counts.get("S", 0),
            "A": counts.get("A", 0),
            "C": counts.get("C", 0),
            "none": counts.get("none", 0),
        },
        "grade_counts_footnote": {
            "B_folded_into": "counted as its own bucket above the C/none ladder, "
                              "never merged into A or C -- %d days" % counts.get("B", 0),
            "B_days": counts.get("B", 0),
            "none_bucket_breakdown": {
                "explicit_none": literal_none,
                "X_only_refusal_aimed_at_engine": len(x_only),
                "note": "both fold into the single 'none' count above; kept "
                        "distinct here so an engine-refusal is never mistaken "
                        "for a day-level 'I would not trade this'.",
            },
        },
        "bars_available": {"yes": bars_yes, "no": total - bars_yes},
        "contested_days": {
            "n_days": len(contested),
            "n_rows_across_those_days": contested_rows,
            "resolution_rule": (
                "best-grade-wins ladder S > A > B > C > none (X ties with "
                "none): the same union rule build_deck.s_days() already uses "
                "for S alone, carried uniformly down the whole ladder. Two "
                "corpora that AGREE are not a conflict, just a dedup at the "
                "symbol-day key -- only disagreement counts as 'contested'."
            ),
            "sample": [
                {"key": k, "raw_grades": pool[k].raw_grades,
                 "sources": pool[k].sources, "resolved_to": pool[k].grade}
                for k in sorted(contested)[:15]
            ],
        },
        "spellings": {
            field: {"rows": field_counts.get(field, 0),
                    "S_rows": field_s_counts.get(field, 0)}
            for field in SPELLINGS
        },
        "per_source": per_source,
    }


# ------------------------------------------------------------------------ CLI

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "marks_pool.json"))
    a = ap.parse_args()

    pool, per_source, field_counts, field_s_counts = build_pool()
    report = build_report(pool, per_source, field_counts, field_s_counts)

    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)

    print("total judged symbol-days: %d" % report["total_symbol_days"])
    print("  S    %d" % report["grade_counts"]["S"])
    print("  A    %d" % report["grade_counts"]["A"])
    print("  C    %d" % report["grade_counts"]["C"])
    print("  none %d  (of which %d explicit refusal, %d X-only engine refusal)"
          % (report["grade_counts"]["none"],
             report["grade_counts_footnote"]["none_bucket_breakdown"]["explicit_none"],
             report["grade_counts_footnote"]["none_bucket_breakdown"]["X_only_refusal_aimed_at_engine"]))
    print("  B    %d  (legacy ladder leak, kept separate)"
          % report["grade_counts_footnote"]["B_days"])
    print("bars available: %d / %d" % (report["bars_available"]["yes"],
                                        report["total_symbol_days"]))
    print("contested days (corpora disagree): %d, spanning %d rows"
          % (report["contested_days"]["n_days"],
             report["contested_days"]["n_rows_across_those_days"]))
    print("wrote %s" % a.out)

    # ---------------------------------------------------------- self-check
    # Pins tonight's counts. If this fails, either a mark file changed (never
    # supposed to happen -- see CLAUDE.md "never lose a mark") or this
    # module's reading rule changed -- in which case update the report this
    # file cites, not just these numbers.
    assert report["total_symbol_days"] == 1178, \
        "total symbol-days moved: %d != 1178" % report["total_symbol_days"]
    assert report["grade_counts"]["S"] == 309, \
        "S count moved: %d != 309" % report["grade_counts"]["S"]
    assert report["grade_counts"]["A"] == 237, \
        "A count moved: %d != 237" % report["grade_counts"]["A"]
    assert report["grade_counts"]["C"] == 58, \
        "C count moved: %d != 58" % report["grade_counts"]["C"]
    assert report["grade_counts"]["none"] == 560, \
        "none count moved: %d != 560" % report["grade_counts"]["none"]
    assert report["bars_available"]["yes"] == 1145, \
        "bars-available count moved: %d != 1145" % report["bars_available"]["yes"]
    print("ok   self-check: all pinned counts match")


if __name__ == "__main__":
    main()
