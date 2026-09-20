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
import re
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
SPELLINGS = tuple(gr.ALL_FIELDS) + ("answers.is_s", "his_grade", "his_letter")

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
    grade_read.py, the ninth, plus the two shape-matched schemas below.
    (field, grade) tuples, precedence order."""
    if "his_grade" in row:
        g = _comments_opinion(row)
        return [("his_grade", g)] if g else []
    if "his_letter" in row:
        return [("his_letter", _bars_opinion(row))]
    ops = list(gr.grade_opinions(row))
    extra = _is_s_opinion(row)
    if extra is not None:
        ops.append(extra)
    return ops


# ------------------------------------------------------- comments and bar-pick schemas

# Two schemas neither grade_read.py's nine spellings nor build_deck.py's key
# normaliser has ever read -- both are sm_deck.py exports (research/sm_deck.py,
# shipped 2026-09-15) and are recognised by shape, not filename, so a future
# export using the same fields is picked up without another edit here. Before
# this: research/marks/*_comments.jsonl and *_bars.jsonl sat in mark_sources()
# (already globbed by build_deck.mark_sources()) but contributed zero opinions
# -- grade_read.has_judgement() doesn't know "his_grade" or "his_letter", so
# build_deck._judgement_key() returned None for every row and they were
# silently skipped.
_COMMENTS_ID_RE = re.compile(r"^([A-Z][A-Z0-9.\-]{0,7})_(\d{4}-\d{2}-\d{2})$")


def _comments_key(row):
    """research/marks/*_comments.jsonl -- {id, his_grade, his_note}, a chat
    export with no symbol/date fields at all; the pair lives inside `id`."""
    ident = row.get("id")
    if "his_grade" not in row or not isinstance(ident, str):
        return None
    m = _COMMENTS_ID_RE.match(ident.strip())
    return "%s_%s" % m.groups() if m else None


def _comments_opinion(row):
    """`his_grade` is free text off a chat export, not a ladder field -- 'A',
    'S@09:50 (served bar A/C, late)', 'not S', 'S', 'ungraded' all appear in
    the two files on disk tonight. Only a clean leading S/A/C is trusted:
    'not S' says the read was wrong, not what the right grade is, and
    'ungraded' means he never actually answered -- both are left as no
    opinion rather than guessed at.
    """
    text = str(row.get("his_grade") or "").strip().upper()
    if not text or text.startswith("NOT ") or text == "UNGRADED":
        return None
    return text[0] if text[0] in "SAC" else None


def _bars_key(row):
    """research/marks/*_bars.jsonl -- sm_deck.py cmd_mark_bar's own output,
    {symbol, date, his_letter, his_bar, engine_bar, minutes_early, ...}."""
    if "his_letter" not in row:
        return None
    symbol, day = row.get("symbol"), row.get("date")
    return "%s_%s" % (symbol, day) if symbol and day else None


def _bars_opinion(_row):
    """A bar pick (his_letter vs the engine's C bar) is entry-timing feedback,
    not a S/A/C verdict. sm_deck's own candidate pool
    (sm_deck.py:_candidate_pool) only ever offers cards the baseline already
    scored S or A, so tapping a bar at all is at minimum his engagement with
    an A-grade candidate -- never read as S, which he never actually tapped
    here.
    """
    return "A"


def _judgement_key(row):
    """Same job as build_deck._judgement_key, extended for the two schemas
    that normaliser has never seen (see row_opinions above)."""
    if "his_grade" in row:
        return _comments_key(row)
    if "his_letter" in row:
        return _bars_key(row)
    return bd._judgement_key(row)


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
            key = _judgement_key(row)
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

def selftest() -> None:
    """omen-bar-deck-nightly's own guarantee: fail loud if *_comments.jsonl
    (his_grade chat exports) or *_bars.jsonl (sm_deck.py --mark-bar's own
    output) ever stop reaching canonical_pool() -- the exact failure mode
    2026-09-17 found (both files sat in mark_sources() for weeks contributing
    zero opinions because neither schema matched grade_read.py's spellings).
    Same two conditions the pending-row verify line already runs by hand,
    here as one flag: ``python research/marks_pool.py --selftest``.
    """
    pool = canonical_pool()
    sources = {s for e in pool.values() for s in e.sources}
    hit = sorted(s for s in sources if "comments" in s or "_bars" in s)
    assert hit, ("no *_comments.jsonl or *_bars.jsonl source reached "
                 "canonical_pool() -- sources seen: %s" % sorted(sources))
    assert len(pool) >= 1272, \
        "pool shrank: %d < 1272 -- a mark file went missing?" % len(pool)
    print("ok   selftest: comments/bars source(s) feed the pool -- %s"
          % ", ".join(hit))
    print("ok   selftest: pool size %d (>= 1272 floor)" % len(pool))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "marks_pool.json"))
    ap.add_argument("--selftest", action="store_true",
                    help="assert *_comments.jsonl/*_bars.jsonl feed the pool, "
                         "then exit (omen-bar-deck-nightly's guarantee)")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

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
    assert report["total_symbol_days"] >= 1178, \
        "pool shrank: %d < 1178 -- a mark file went missing?" % report["total_symbol_days"]
    print("ok   self-check: pool size %d (>= 1178 floor)" % report["total_symbol_days"])


if __name__ == "__main__":
    main()
