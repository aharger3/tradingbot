"""grade_read.py - ONE function that reads Austin's grade, whatever it is spelled.

Austin's grade ladder is **S / A / C / none** (`research/downgrade.py`,
`Projects/omen-rulebook.md`). It is stored under **eight different field names**
across the 19 mark corpora, because every grading page that was ever built
invented its own. Two of those spellings live inside an ``answers`` dict, and a
tool that reads a top-level ``grade`` field cannot see them at all:

    research/marks/probe_s_sweep_2026-08-28.jsonl -- the 100 blind cards the
    whole project's recall number is scored on -- carries "grade": "none" on ALL
    100 rows, INCLUDING the 34 he called S. The real answer is in
    answers.s == ["s"].

That is why 48 of his S days were invisible to every grade-field reader, and why
this repo has published three different S-day counts (154, 207, 288).

**Read the grade through ``read_grade(row)`` and nowhere else.**

    read_grade({"tier": "S"})                            -> "S"
    read_grade({"grade": "none", "answers": {"s": ["s"]}}) -> "S"
    read_grade({"symbol": "AMD", "day": "2025-01-28"})    -> None

Values it returns, and only these:

    "S" / "A" / "C"   Austin's ladder
    "B"               17 rows of austin_tier carry it; kept, never invented
    "X"               NOT a grade. On a mark row it is Austin saying "this
                      should not have fired" -- a refusal aimed at the engine.
    "none"            an explicit refusal to trade the day. A judgement, not a
                      blank (``_no_trade: true`` is the same thing in another
                      dress). An EMPTY grade string on a card he was served
                      counts here too -- one row, SPY 2026-08-03, where he wrote
                      a note and left the grade blank. Counting it as a refusal
                      costs nothing and keeps that card out of a future deck.
    None              the row carries no opinion about the grade at all

**This is Austin's ladder only.** The engine's legacy A+/A/B/C/X ladder
(`signal_runner.py::_grade_pa`) is a different question and must never be read
through this file. Nothing here touches a mark file: readers get fixed, data
never does.

Read-only, no I/O, standard library only, so `research/build_deck.py` -- the
enumerator of record -- can import it without a cycle.
"""
from __future__ import annotations

# ---------------------------------------------------------------- the spellings

#: Top-level fields that carry Austin's grade, and the corpora that use each.
#: Order is precedence order for a row that spells itself twice (see read_grade).
#: Order is build_deck._GRADE_KEYS' original order, unchanged -- three scripts
#: iterate that tuple first-hit-wins and reordering it would move their numbers.
SCALAR_FIELDS = (
    "austin_tier",   # austin_marks_v7, derived_marks_v2, recovered_reviews
    "tier",          # blind_marks_all, marks_clean, mark_batch_03/04, derived_v1
    "austin_grade",  # mark_batch_02_grades
    "grade",         # the deck files and most probe files
    "verdict",       # austin_verdicts.json (lowercase "s")
)

#: ``answers.<key>`` fields, ladder form -- the value is a list, e.g. ["S"].
ANSWER_LADDER_FIELDS = ("your_grade", "grade")

#: ``answers.<key>`` fields, yes/no form -- ["s"] means S, ["no"] means refused.
ANSWER_YESNO_FIELDS = ("s", "s_call")

#: ``answers.<key>`` fields where **only the refusal carries a grade**.
#:
#: The tenth spelling, found 2026-09-02 in the `take_the_trade` section of
#: `research/marks/probe_g84_all_in_one_STANDING154_2026-09-01.jsonl` -- the
#: 147 answers recovered a day earlier, which no reader had ever seen. 22
#: symbol-days he answered were invisible to `marks_pool.canonical_pool()`
#: entirely (the no-repeat guarantee still protected them, so nothing was at
#: risk of being re-served -- but every S/A measurement silently excluded them).
#:
#: `take: no` is unambiguous: he was shown the tape and refused it. That is a
#: `none`, the same judgement `why_not` records.
#:
#: `take: yes` is NOT S and must never be read as one. He answered "yes" and
#: then wrote "9:50 a trade no displacement" (MSFT_2026-07-28), "10:02 A trade
#: because theres major levels it needs to break for good rr" (UBER_2026-08-04),
#: "9:38 a trade but wouldnt been in and out" (AAPL_2024-10-23) -- and elsewhere
#: "9:50 S" (NFLX_2025-08-08), "10:20 S" (COIN_2025-11-21). The section asked
#: *would you trade this*, not *what grade*. Mapping yes -> S would inflate his
#: S count with A trades and corrupt every recall number downstream, which is
#: the exact failure `marks_pool` exists to prevent. So: yes yields NO opinion,
#: and `would_take()` below exposes it for callers that want tradeability
#: rather than grade.
ANSWER_REFUSAL_ONLY_FIELDS = ("take",)

#: Every field name this module reads, for callers that need the list.
ALL_FIELDS = (SCALAR_FIELDS
              + tuple("answers." + k for k in ANSWER_LADDER_FIELDS)
              + tuple("answers." + k for k in ANSWER_YESNO_FIELDS)
              + ("_no_trade",))

_LADDER = {"s": "S", "a": "A", "b": "B", "c": "C", "x": "X"}
_REFUSAL = {"none", "null", "no", "n", "not_s", "nos", "false", ""}
_YES = {"s", "yes", "y", "true", "1"}


def _scalar(value):
    """One raw field value -> a ladder value, "none", or None (says nothing)."""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in _LADDER:
        return _LADDER[text]
    if text in _REFUSAL:
        return "none"
    return None


def _yesno(value):
    """A yes/no S card -> "S", "none", or None."""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in _YES:
        return "S"
    if text in _REFUSAL:
        return "none"
    return None


def grade_opinions(row):
    """Every grade opinion the row carries, as ``(field, grade)``, in precedence
    order. A row that spells itself twice appears twice -- that is the input to
    the conflict count, so it is deliberately not collapsed here.
    """
    out = []
    if not isinstance(row, dict):
        return out
    answers = row.get("answers")
    if isinstance(answers, dict):
        for key in ANSWER_LADDER_FIELDS:
            g = _scalar(answers.get(key))
            if g is not None:
                out.append(("answers." + key, g))
        for key in ANSWER_YESNO_FIELDS:
            g = _yesno(answers.get(key))
            if g is not None:
                out.append(("answers." + key, g))
        for key in ANSWER_REFUSAL_ONLY_FIELDS:
            # Refusal only. `take: no` is a `none`; `take: yes` says he would
            # trade it, which is NOT a grade -- see ANSWER_REFUSAL_ONLY_FIELDS.
            if _yesno(answers.get(key)) == "none":
                out.append(("answers." + key, "none"))
    for key in SCALAR_FIELDS:
        if key in row:
            g = _scalar(row.get(key))
            if g is not None:
                out.append((key, g))
    if row.get("_no_trade"):
        out.append(("_no_trade", "none"))
    return out


def read_grade(row):
    """**The one grade reader.** Austin's grade for this row, or None.

    An S anywhere in the row wins: the S-sweep rows say ``grade: "none"`` in one
    field and ``answers.s: ["s"]`` in another, and the S is the answer he
    actually gave -- the "none" is the page's untouched default. Otherwise the
    first opinion in ``grade_opinions`` order wins, and "none" only when that is
    all the row says.
    """
    ops = grade_opinions(row)
    if not ops:
        return None
    for _field, g in ops:
        if g == "S":
            return "S"
    for _field, g in ops:
        if g != "none":
            return g
    return "none"


def is_s(row):
    """True when Austin called this row S, under any spelling."""
    return read_grade(row) == "S"


def would_take(row):
    """True/False when he answered *would you trade this*, else None.

    Deliberately separate from `read_grade`. Tradeability is not a grade: of the
    22 symbol-days he answered `take: yes`, several are explicitly A in his own
    note. A caller asking "which days would he have traded" wants this; a caller
    asking "which days are S" must keep using `read_grade`, and the two answers
    are allowed to differ. Conflating them is what this function exists to stop.
    """
    if not isinstance(row, dict):
        return None
    answers = row.get("answers")
    if not isinstance(answers, dict):
        return None
    for key in ANSWER_REFUSAL_ONLY_FIELDS:
        v = answers.get(key)
        if isinstance(v, list) and v:
            text = str(v[0]).strip().lower()
            if text in _YES or text == "yes":
                return True
            if text in _REFUSAL or text == "no":
                return False
    return None


def grade_field(row):
    """Which field the grade came out of -- for the spelling table, not for logic."""
    ops = grade_opinions(row)
    if not ops:
        return None
    for field, g in ops:
        if g == "S":
            return field
    for field, g in ops:
        if g != "none":
            return field
    return ops[0][0]


def conflicting(row):
    """True when one row's own fields disagree about the grade."""
    return len({g for _f, g in grade_opinions(row)}) > 1


def has_judgement(row):
    """True when the row is a judgement of any kind -- graded, refused, or answered.

    This is the no-repeat guarantee's gate and it is deliberately WIDER than
    ``read_grade``: a probe row whose only answer is a stop price is still Austin
    spending his attention on that chart, and a row whose grade field holds a
    bare ``None`` was already counted before this module existed. The pool this
    feeds may only ever grow.
    """
    if not isinstance(row, dict):
        return False
    if read_grade(row) is not None:
        return True
    # Verbatim the pre-2026-08-29 predicate in build_deck._judgement_key, kept so
    # the exclusion pool can never shrink by one row.
    if any(str(row.get(k, "")).strip() for k in SCALAR_FIELDS):
        return True
    answers = row.get("answers")
    if isinstance(answers, dict) and any(answers.values()):
        return True
    return bool(row.get("_no_trade"))
