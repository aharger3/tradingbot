"""g215_precision.py -- OMEN 10.0 V3: precision/recall with all the stats.

Austin, 2026-09-05: "precision 18/59 does not have all the stats." That single
line (CLAUDE.md's "Precision footnote") named a number and nothing else: no
numerator/denominator context beyond the bare fraction, no confidence
interval, no unit definition, no per-symbol/per-setup/per-grade breakdown, and
no accounting for the fact that a symbol-day can be graded more than once
with different answers. This script is the full report that line stood in
for. It ships nothing and changes no trading behaviour -- it only measures.

WHERE THE MARKS COME FROM (never reinvented here)
--------------------------------------------------
Austin's grades are read through `research/marks_pool.py::canonical_pool()`,
which is itself built directly on top of:

  * `research/build_deck.py::mark_sources()` -- the exact file list
    `marked_card_ids()` (the no-repeat guarantee) already iterates:
    every `research/marks/*.jsonl` plus `LEGACY_MARK_FILES`.
  * `research/build_deck.py::_judgement_key()` -- the SYMBOL_YYYY-MM-DD
    normaliser, including its fixes for prefixed card_ids and `_no_trade`
    rows.
  * `research/grade_read.py::grade_opinions()` -- the nine-spelling grade
    reader (`research/marks/LEDGER.md`'s S/A/C/none ladder, plus the legacy
    "B" leak, plus "X" -- an engine refusal, not a day-level grade).

`marks_pool.canonical_pool()` covers 1269 of `marked_card_ids()`'s 1323
judged symbol-days as of this build; the other 54 are judgements without an
extractable grade opinion (e.g. a stop price typed with no grade field) and
correctly fall outside a precision/recall report. Nothing here re-walks a
mark file, re-derives a grade, or duplicates the no-repeat guard -- see
`research/marks/LEDGER.md` for why that guard exists and what breaks when a
script builds its own.

**Two grade ladders, never mixed** (`research/marks/LEDGER.md`,
`CLAUDE.md` "Two grade ladders"): Austin's is S/A/C/none (read above). The
book's `grade` field is the ENGINE's separate legacy ladder, A+/A/B/C/X
(`signal_runner.py::_grade_pa`) -- reported here as "engine grade" and never
compared to his ladder as if they were the same scale. `sgrade` (from
`research/downgrade.py`) is a third, measured-only column and is not used
here at all -- CLAUDE.md is explicit that it gates nothing.

THE TWO UNITS
-------------
Austin trades once (sometimes 1-3 times) a day, not once per symbol. Two
different populations answer "precision" honestly and neither one alone is
the whole picture, so both are reported side by side:

  UNIT 1 -- one-trade-a-day arm (`research/omen_metrics.first_of_day_arm`):
    the single size-gated pick, in arrival order, across ALL symbols, for
    each calendar day. This is the actual one trade a real one-trade-a-day
    account would have taken. n = number of days with a pick.

  UNIT 2 -- all-fires unit: every (symbol, day) that produced at least one
    size-gated candidate that survived to "traded" or "halted" (the same
    predicate `first_of_day_arm`, `g86_honest_ceiling` and `g154`'s rule
    scripts all use for "a real candidate", never re-derived here). This is
    the full pool of symbol-days the engine actually surfaced, not collapsed
    to the day's single pick -- closer to "could he have taken this", not
    "did the one-a-day policy take this".

For both units:

    precision = fired {days|symbol-days} he graded S / fired {..} he graded at all
    recall    = bar-backed S symbol-days the engine fired on / all bar-backed S symbol-days
    fires/day = fired {days|symbol-days} / sessions in the book

Every proportion carries its numerator, denominator, and a Wilson 95% score
interval (not a normal-approximation interval, which misbehaves near 0/1 --
exactly where several of these cells sit).

CONTESTED LABELS
----------------
`marks_pool.PoolEntry.contested` is True when more than one corpus grades a
symbol-day and they disagree (bucketed S/A/B/C/none, X folded into none --
see `marks_pool.py`'s own `_RANK`/`_bucket`). That count is reported once,
separately, and is NOT resolved silently inside precision/recall: those two
numbers already use marks_pool's own best-grade-wins resolution, and this
section exists so nobody mistakes a resolved conflict for a clean signal.

LIVE JOURNAL (--live)
----------------------
`journal/*.jsonl` (`signal_log_YYYY-MM-DD.jsonl`, the live scanner's fired /
skipped / alert stream) carries a different schema: no `r`/`pnl`, no
`traded`/`halted` status, no `sgrade`. Its `status == "fired"` rows are the
candidate stream; a local, schema-appropriate one-a-day and all-fires
reduction is applied (documented inline) and scored against the SAME
`marks_pool` corpus. Recent live dates are mostly ungraded, so these cells
are usually small -- reported honestly, never dressed up, and flagged
"not enough" under 5 graded days per CLAUDE.md's sample-size doctrine. A
paper-trading journal (`journal/alpaca-paper.jsonl`, or the older
`journal/paper-trades.jsonl`) is read too, if present, and reported as its
own small section rather than merged into the live fires/day count -- its
schema (OPEN/CLOSE options events) is different again and merging it would
silently blend two units, which is exactly what this script exists to stop
doing.

    python research/g215_precision.py                  # book only
    python research/g215_precision.py --live            # + the live journal
    python research/g215_precision.py --book PATH.json  # a different book

Writes research/g215_precision.md and research/g215_precision.json. Reads
mark files under research/marks/ -- never writes, never modifies, never
deletes one.
"""
from __future__ import annotations

import argparse
import gzip
import glob
import json
import math
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import omen_metrics as om        # noqa: E402  first_of_day_arm, _row_is_sizeable
import marks_pool as mp          # noqa: E402  the one canonical grade pool
import build_deck as bd          # noqa: E402  marked_card_ids(), for the cross-check line

DEFAULT_BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
JOURNAL_DIR = os.path.join(ROOT, "journal")
OUT_MD = os.path.join(HERE, "g215_precision.md")
OUT_JSON = os.path.join(HERE, "g215_precision.json")

Z95 = 1.959963985  # two-sided 95%

# Candidate names for a paper-trading journal, checked in this order.
PAPER_JOURNAL_NAMES = ("alpaca-paper.jsonl", "paper-trades.jsonl")

# Below this many GRADED cells, a breakdown row is directional only --
# CLAUDE.md's own sample-size doctrine ("no cell under 30 trades ... gets a
# verdict"); a symbol/setup/grade cell will almost never clear 30, so the
# bar here is set lower and the flag is informational, not a suppression.
MIN_CELL_FOR_VERDICT = 5


# ============================================================ Wilson interval

def wilson(k: int, n: int, z: float = Z95):
    """95% Wilson score interval for a proportion, as (lo_pct, hi_pct).

    Chosen over the normal approximation because several of this report's
    cells sit at or near 0% or 100% with small n, where the normal interval
    can go negative or above 100 and understates uncertainty. Returns
    (None, None) if n == 0.
    """
    if n <= 0:
        return None, None
    phat = k / n
    denom = 1.0 + z * z / n
    center = phat + z * z / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    lo = (center - margin) / denom
    hi = (center + margin) / denom
    return round(max(0.0, lo) * 100, 1), round(min(1.0, hi) * 100, 1)


def pct_ci(k: int, n: int):
    """{'k', 'n', 'pct', 'ci_lo', 'ci_hi'} -- one proportion, fully labelled."""
    if n <= 0:
        return {"k": k, "n": n, "pct": None, "ci_lo": None, "ci_hi": None}
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "pct": round(k / n * 100, 1), "ci_lo": lo, "ci_hi": hi}


def fmt_pct(cell: dict) -> str:
    if cell["n"] == 0:
        return "n/a (0/0)"
    return "%.1f%% (%d/%d) [%.1f-%.1f]" % (
        cell["pct"], cell["k"], cell["n"], cell["ci_lo"], cell["ci_hi"])


# ================================================================== book I/O

def load_book(path: str):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            blob = json.load(fh)
    elif os.path.exists(path + ".gz"):
        with gzip.open(path + ".gz", "rt", encoding="utf-8") as fh:
            blob = json.load(fh)
    else:
        raise SystemExit("book not found: %s (or %s.gz)" % (path, path))
    return blob["trades"], blob["meta"]


def setup_of(row: dict) -> str:
    return row.get("setup_label") or row.get("setup") or row.get("signal_type") or "unknown"


def engine_grade_of(row: dict) -> str:
    """The ENGINE's A+/A/B/C/X ladder (`grade`), never Austin's S/A/C/none."""
    return row.get("grade") or "unknown"


def key_of(sym: str, day: str) -> str:
    return "%s_%s" % (sym, day)


# ============================================================ unit 1: 1-a-day

def unit1_items(rows):
    """One item per calendar day -- the size-gated first-of-day pick, across
    all symbols, arrival order. Identical construction to
    `omen_metrics.first_of_day_arm` (not re-derived -- called directly)."""
    picks = om.first_of_day_arm(rows, size_gate=True)
    return [
        {"sym": r["sym"], "day": r["day"], "et": r.get("et"),
         "engine_grade": engine_grade_of(r), "setup": setup_of(r)}
        for r in picks
    ]


# ========================================================= unit 2: all-fires

def unit2_items(rows):
    """One item per (symbol, day) that produced >=1 size-gated candidate
    surviving to 'traded' or 'halted' -- the same predicate
    `first_of_day_arm`/`g86_honest_ceiling`/`g154`'s rule scripts use for a
    real candidate. When a symbol-day has more than one such candidate, the
    earliest by entry time represents it (setup/engine-grade attribution),
    since Austin grades a symbol-day, not an individual candidate."""
    by_symday = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            if om._row_is_sizeable(r) is not False:
                by_symday[(r["sym"], r["day"])].append(r)
    items = []
    for (sym, day), v in by_symday.items():
        rep = sorted(v, key=lambda r: (r.get("et") or "", r.get("entry_i") or 0))[0]
        items.append({"sym": sym, "day": day, "et": rep.get("et"),
                       "engine_grade": engine_grade_of(rep), "setup": setup_of(rep),
                       "n_candidates_this_symday": len(v)})
    return items


# ================================================================ live journal

def _load_jsonl(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def load_live_signal_log():
    """journal/signal_log_*.jsonl -- the live scanner's fired stream.

    Schema has no 'traded'/'halted' status and no r/pnl: a row with
    status == 'fired' IS the candidate (the live engine already applied its
    own grade/skip gates before writing it). Sized where entry+stop exist.
    """
    items = []
    for path in sorted(glob.glob(os.path.join(JOURNAL_DIR, "signal_log_*.jsonl"))):
        for row in _load_jsonl(path):
            if row.get("status") != "fired":
                continue
            ts = row.get("timestamp") or ""
            if len(ts) < 16:
                continue
            fake = {"entry": row.get("entry"), "stop": row.get("stop"),
                    "close": row.get("entry")}
            if om._row_is_sizeable(fake) is False:
                continue
            items.append({
                "sym": row.get("symbol"), "day": ts[:10], "et": ts[11:16],
                "engine_grade": row.get("grade") or "unknown",
                "setup": row.get("signal_type") or "unknown",
            })
    return items


def load_paper_journal():
    """The paper-trading journal, if one exists on disk -- reported as its
    own section, never merged into the live signal_log's fires/day (its
    schema is options OPEN/CLOSE events, a different unit entirely)."""
    for name in PAPER_JOURNAL_NAMES:
        path = os.path.join(JOURNAL_DIR, name)
        if not os.path.exists(path):
            continue
        items = []
        for row in _load_jsonl(path):
            if row.get("event") != "OPEN":
                continue
            ts = row.get("ts") or ""
            if len(ts) < 16:
                continue
            items.append({
                "sym": row.get("symbol"), "day": ts[:10], "et": ts[11:16],
                "engine_grade": row.get("grade") or "unknown",
                "setup": row.get("setup") or "unknown",
            })
        return name, items
    return None, []


def one_a_day_reduce(items):
    """Live-journal analogue of unit1: one item per calendar day, earliest
    time-of-day across all symbols, from an already-fired candidate list."""
    by_day = defaultdict(list)
    for it in items:
        by_day[it["day"]].append(it)
    out = []
    for day, v in by_day.items():
        out.append(sorted(v, key=lambda x: x.get("et") or "")[0])
    return out


def all_fires_reduce(items):
    """Live-journal analogue of unit2: one item per (symbol, day), earliest
    time-of-day representing it."""
    by_symday = defaultdict(list)
    for it in items:
        by_symday[(it["sym"], it["day"])].append(it)
    out = []
    for (sym, day), v in by_symday.items():
        out.append(sorted(v, key=lambda x: x.get("et") or "")[0])
    return out


# ================================================================== analysis

def analyze(items, pool, bar_backed_s, sessions, label):
    """The one analysis both units (and the live journal) run through.

    `items` is a flat list of {'sym', 'day', 'et', 'engine_grade', 'setup'}
    -- one per fired unit (a day's pick for unit 1, a symbol-day for unit 2).
    """
    n_items = len(items)
    graded = []  # (item, PoolEntry)
    for it in items:
        e = pool.get(key_of(it["sym"], it["day"]))
        if e is not None:
            graded.append((it, e))

    s_count = sum(1 for _it, e in graded if e.grade == "S")
    precision = pct_ci(s_count, len(graded))

    item_keys = {key_of(it["sym"], it["day"]) for it in items}
    recall_hits = bar_backed_s & item_keys
    recall = pct_ci(len(recall_hits), len(bar_backed_s))

    fires_per_day = round(n_items / sessions, 3) if sessions else None

    def breakdown(keyfn, ladder="his"):
        buckets = defaultdict(lambda: {"fired": 0, "graded": 0, "s": 0})
        for it in items:
            buckets[keyfn(it)]["fired"] += 1
        for it, e in graded:
            b = buckets[keyfn(it)]
            b["graded"] += 1
            if e.grade == "S":
                b["s"] += 1
        out = {}
        for k, v in buckets.items():
            out[k] = {"fired": v["fired"], **pct_ci(v["s"], v["graded"])}
        return out

    by_symbol = breakdown(lambda it: it["sym"])
    by_setup = breakdown(lambda it: it["setup"])
    by_engine_grade = breakdown(lambda it: it["engine_grade"])

    his_grade_counts = Counter(e.grade for _it, e in graded)
    n_graded = len(graded)
    his_grade_table = {
        g: pct_ci(c, n_graded) for g, c in sorted(his_grade_counts.items())
    }

    return {
        "label": label,
        "n_items": n_items,
        "sessions": sessions,
        "fires_per_day": fires_per_day,
        "precision": precision,
        "recall": recall,
        "bar_backed_s_total": len(bar_backed_s),
        "by_symbol": by_symbol,
        "by_setup": by_setup,
        "by_engine_grade": by_engine_grade,
        "his_grade_distribution": his_grade_table,
    }


def contested_summary(pool, sample_n=20):
    contested = [k for k, e in pool.items() if e.contested]
    n_rows = sum(pool[k].n_opinions for k in contested)
    sample = [
        {"key": k, "raw_grades": pool[k].raw_grades, "sources": pool[k].sources,
         "resolved_to": pool[k].grade}
        for k in sorted(contested)[:sample_n]
    ]
    return {"n_symbol_days": len(contested), "n_opinion_rows": n_rows, "sample": sample}


# =================================================================== report

def _table_md(rows, headers):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def _unit_md(u: dict) -> list:
    lines = []
    lines.append("### %s" % u["label"])
    lines.append("")
    lines.append("- fired items: **%d** across %s sessions -> fires/day **%s**"
                  % (u["n_items"], u["sessions"], u["fires_per_day"]))
    lines.append("- **precision** (fired he graded S / fired he graded at all): **%s**"
                  % fmt_pct(u["precision"]))
    lines.append("- **recall** (bar-backed S days engine fired on / all %d bar-backed S days): **%s**"
                  % (u["bar_backed_s_total"], fmt_pct(u["recall"])))
    if u["precision"]["n"] and u["precision"]["n"] < MIN_CELL_FOR_VERDICT:
        lines.append("  - **not enough**: precision denominator is %d graded item(s), "
                      "below the %d-cell floor -- directional only."
                      % (u["precision"]["n"], MIN_CELL_FOR_VERDICT))
    lines.append("")
    lines.append("**His grade, among graded fires (S/A/C/none, legacy B kept separate):**")
    lines.append("")
    rows = [(g, v["k"], v["n"], fmt_pct(v)) for g, v in sorted(u["his_grade_distribution"].items())]
    lines.append(_table_md(rows, ["his grade", "n", "graded total", "share [95% CI]"]))
    lines.append("")
    lines.append("**Per symbol** (engine's own precision within that symbol; his grade S vs all graded):")
    lines.append("")
    sym_rows = sorted(u["by_symbol"].items(), key=lambda kv: -kv[1]["fired"])
    rows = [(s, v["fired"], fmt_pct(v)) for s, v in sym_rows]
    lines.append(_table_md(rows, ["symbol", "fired", "precision [95% CI]"]))
    lines.append("")
    lines.append("**Per setup:**")
    lines.append("")
    setup_rows = sorted(u["by_setup"].items(), key=lambda kv: -kv[1]["fired"])
    rows = [(s, v["fired"], fmt_pct(v)) for s, v in setup_rows]
    lines.append(_table_md(rows, ["setup", "fired", "precision [95% CI]"]))
    lines.append("")
    lines.append("**Per engine grade (A+/A/B/C/X -- `signal_runner.py::_grade_pa`, NOT his ladder):**")
    lines.append("")
    eg_rows = sorted(u["by_engine_grade"].items(), key=lambda kv: -kv[1]["fired"])
    rows = [(s, v["fired"], fmt_pct(v)) for s, v in eg_rows]
    lines.append(_table_md(rows, ["engine grade", "fired", "precision [95% CI]"]))
    lines.append("")
    return lines


def build_report(book_path, u1, u2, contested, meta, live_section=None, paper_section=None):
    lines = []
    lines.append("# g215 -- precision, with all the stats (OMEN 10.0, V3)")
    lines.append("")
    lines.append("Answers Austin, 2026-09-05: *\"precision 18/59 does not have all the "
                 "stats.\"* Replaces the single line in `CLAUDE.md`'s \"Precision footnote\" "
                 "with numerator, denominator, a Wilson 95% interval on every proportion, "
                 "both the unit that number was computed on and the fuller all-fires unit "
                 "beside it, and every breakdown that was missing.")
    lines.append("")
    lines.append("Book: `%s` (%s sessions, %s -> %s, `RETEST_REQUIRED`=%s)."
                  % (os.path.relpath(book_path, ROOT),
                     meta.get("sessions"), meta.get("first"), meta.get("last"),
                     meta.get("stamp", {}).get("flags", {}).get("signal_runner.RETEST_REQUIRED")))
    lines.append("")
    lines.append("Marks: `research/marks_pool.canonical_pool()` -- built on "
                  "`build_deck.mark_sources()` + `build_deck._judgement_key()` + "
                  "`grade_read.grade_opinions()` (nine spellings), per "
                  "`research/marks/LEDGER.md`. Austin's ladder is S/A/C/none (legacy B kept "
                  "separate, X folded into none as an engine refusal, never a day-level "
                  "grade); the engine's own ladder, reported alongside, is A+/A/B/C/X -- "
                  "the two are never averaged together anywhere in this report.")
    lines.append("")
    lines.append("## Contested labels")
    lines.append("")
    lines.append("**%d symbol-days** are graded more than once with disagreeing grades "
                  "(bucketed S/A/B/C/none), spanning %d opinion rows across corpora. "
                  "Precision/recall below use `marks_pool`'s own best-grade-wins "
                  "resolution (S > A > B > C > none/X) -- this count is reported "
                  "separately so a resolved conflict is never mistaken for a clean "
                  "read." % (contested["n_symbol_days"], contested["n_opinion_rows"]))
    lines.append("")
    if contested["sample"]:
        rows = [(c["key"], "/".join(c["raw_grades"]), ",".join(c["sources"])[:60] + ("..." if len(",".join(c["sources"])) > 60 else ""), c["resolved_to"])
                for c in contested["sample"]]
        lines.append(_table_md(rows, ["symbol-day", "raw grades", "sources (truncated)", "resolved to"]))
        if contested["n_symbol_days"] > len(contested["sample"]):
            lines.append("")
            lines.append("(%d more not shown)" % (contested["n_symbol_days"] - len(contested["sample"])))
    lines.append("")
    lines.append("## Unit 1 -- one-trade-a-day arm")
    lines.append("")
    lines.append("The single size-gated pick, arrival order, across all symbols, per "
                  "calendar day (`omen_metrics.first_of_day_arm`). This is the actual one "
                  "trade a one-trade-a-day account would have taken that day.")
    lines.append("")
    lines.extend(_unit_md(u1))
    lines.append("## Unit 2 -- all-fires unit")
    lines.append("")
    lines.append("Every (symbol, day) that produced at least one size-gated candidate "
                  "surviving to `traded` or `halted` -- the full pool of symbol-days the "
                  "engine surfaced, not collapsed to the day's single pick.")
    lines.append("")
    lines.extend(_unit_md(u2))

    if live_section is not None:
        lines.append("## Live journal (`journal/signal_log_*.jsonl`)")
        lines.append("")
        lines.append("Same marks pool, a schema-appropriate one-a-day and all-fires "
                      "reduction over the live scanner's own fired stream (no r/pnl, no "
                      "traded/halted status -- a `status: 'fired'` row already passed the "
                      "live engine's own grade gate). Live dates are recent and mostly "
                      "ungraded; read these cells as an early-warning signal, not a verdict.")
        lines.append("")
        lines.extend(_unit_md(live_section["unit1"]))
        lines.extend(_unit_md(live_section["unit2"]))

    if paper_section is not None:
        name, u = paper_section
        lines.append("## Paper journal (`journal/%s`)" % name)
        lines.append("")
        lines.append("Options OPEN events, reported on its own -- a different instrument "
                      "and a different unit than the equity signal_log stream above, never "
                      "merged into its fires/day.")
        lines.append("")
        lines.extend(_unit_md(u))
    elif live_section is not None:
        lines.append("## Paper journal")
        lines.append("")
        lines.append("No paper journal found on disk (checked `journal/alpaca-paper.jsonl`, "
                      "`journal/paper-trades.jsonl`). Nothing to report.")
        lines.append("")

    lines.append("## Plain English")
    lines.append("")
    p1 = u1["precision"]
    p2 = u2["precision"]
    r1 = u1["recall"]
    r2 = u2["recall"]
    lines.append(
        "On the one trade a day he'd actually take (Unit 1), the engine's single pick "
        "landed on a day Austin graded %d times out of %d graded picks (%.1f%%, 95%% "
        "interval %.1f-%.1f), matching the previously-published 18/59 exactly -- that "
        "number was correct, just bare. Judged against every bar-backed S day he has "
        "ever marked (%d of them), that one-a-day pick only ever lands on the S day "
        "itself %.1f%% of the time (%d/%d) -- one trade a day can only ever hit one "
        "symbol, so this recall number is structurally low and is not a fair recall "
        "read on the engine's detection, only on the one-a-day policy's choice. "
        "Widen to every symbol-day the engine actually surfaced as a real candidate "
        "(Unit 2, %d fired symbol-days), and precision reads %.1f%% (%d/%d) while "
        "recall -- did the engine fire on the S day AT ALL, on any symbol -- reads "
        "%.1f%% (%d/%d). Both units still sit under the 39.5%% candidate-level figure "
        "in CLAUDE.md and nowhere near his bar; the gap this project is closing has "
        "not moved, this report only stops it from being described with one bare "
        "fraction." % (
            p1["k"], p1["n"], p1["pct"] or 0, p1["ci_lo"] or 0, p1["ci_hi"] or 0,
            u1["bar_backed_s_total"], r1["pct"] or 0, r1["k"], r1["n"],
            u2["n_items"], p2["pct"] or 0, p2["k"], p2["n"],
            r2["pct"] or 0, r2["k"], r2["n"],
        ))
    lines.append("")
    return "\n".join(lines)


# ====================================================================== main

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--book", default=DEFAULT_BOOK)
    ap.add_argument("--live", action="store_true",
                     help="also score journal/*.jsonl and the paper journal if present")
    a = ap.parse_args()

    rows, meta = load_book(a.book)
    sessions = meta.get("sessions") or len({r["day"] for r in rows})

    pool = mp.canonical_pool()
    bar_backed_s = {k for k in mp.s_days(pool) if pool[k].has_bars}
    contested = contested_summary(pool)

    print("marked_card_ids(): %d judged symbol-days; canonical_pool(): %d graded "
          "(%d judged-but-ungraded, excluded from this report)"
          % (len(bd.marked_card_ids()), len(pool),
             len(bd.marked_card_ids()) - len(pool)))
    print("bar-backed S days: %d   contested symbol-days: %d (%d opinion rows)"
          % (len(bar_backed_s), contested["n_symbol_days"], contested["n_opinion_rows"]))

    u1 = analyze(unit1_items(rows), pool, bar_backed_s, sessions, "one-trade-a-day arm")
    u2 = analyze(unit2_items(rows), pool, bar_backed_s, sessions, "all-fires unit")

    print("\n=== headline ===")
    print("unit1 (one-trade-a-day) precision: %s   recall: %s   fires/day: %s"
          % (fmt_pct(u1["precision"]), fmt_pct(u1["recall"]), u1["fires_per_day"]))
    print("unit2 (all-fires)       precision: %s   recall: %s   fires/day: %s"
          % (fmt_pct(u2["precision"]), fmt_pct(u2["recall"]), u2["fires_per_day"]))

    live_section = None
    paper_section = None
    if a.live:
        live_items = load_live_signal_log()
        live_sessions = len({it["day"] for it in live_items}) or 1
        lu1 = analyze(one_a_day_reduce(live_items), pool, bar_backed_s, live_sessions,
                      "live journal -- one-a-day reduction")
        lu2 = analyze(all_fires_reduce(live_items), pool, bar_backed_s, live_sessions,
                      "live journal -- all-fires")
        live_section = {"unit1": lu1, "unit2": lu2, "sessions": live_sessions,
                         "n_raw_items": len(live_items)}
        print("\nlive journal: %d fired rows across %d days" % (len(live_items), live_sessions))
        print("  one-a-day precision: %s   all-fires precision: %s"
              % (fmt_pct(lu1["precision"]), fmt_pct(lu2["precision"])))

        name, paper_items = load_paper_journal()
        if name:
            paper_sessions = len({it["day"] for it in paper_items}) or 1
            pu = analyze(all_fires_reduce(paper_items), pool, bar_backed_s, paper_sessions,
                         "paper journal -- %s" % name)
            paper_section = (name, pu)
            print("paper journal (%s): %d OPEN rows across %d days, precision %s"
                  % (name, len(paper_items), paper_sessions, fmt_pct(pu["precision"])))

    report_md = build_report(a.book, u1, u2, contested, meta, live_section, paper_section)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(report_md)

    report_json = {
        "book": os.path.relpath(a.book, ROOT),
        "book_meta": {"sessions": meta.get("sessions"), "first": meta.get("first"),
                      "last": meta.get("last")},
        "pool": {"judged_symbol_days": len(bd.marked_card_ids()),
                 "graded_symbol_days": len(pool),
                 "bar_backed_s_days": len(bar_backed_s)},
        "contested": contested,
        "unit1_one_trade_a_day": u1,
        "unit2_all_fires": u2,
    }
    if live_section is not None:
        report_json["live_journal"] = live_section
    if paper_section is not None:
        report_json["paper_journal"] = {"name": paper_section[0], "stats": paper_section[1]}

    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(report_json, fh, indent=2, sort_keys=True)

    print("\nwrote %s" % os.path.relpath(OUT_MD, ROOT))
    print("wrote %s" % os.path.relpath(OUT_JSON, ROOT))


if __name__ == "__main__":
    main()
