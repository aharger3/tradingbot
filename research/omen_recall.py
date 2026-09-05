#!/usr/bin/env python3
"""omen_recall.py -- sqlite FTS5 keyword search over OMEN's own decisions.

Austin, 2026-09-05: "we should probably have an agent or a couple of people
with good memories that remember the good stuff, because i feel like im
alone on an island." This is that memory: a read-only index over the places
his rulings already live, so any agent's first move can be a search instead
of a re-ask.

Shape copied from C:\\Users\\aharg\\Desktop\\Projects\\stage-manager\\memory.py
(sqlite FTS5 over a jsonl log) -- same build_match() OR-of-tokens query, same
bm25() ordering, same "rebuild the whole table" refresh instead of incremental
upsert. That project indexes one jsonl log; this one indexes many markdown
docs plus many mark corpora, so the row-gathering side is bigger, but the
index itself is the same handful of sqlite calls.

Two source kinds, one table:

* **doc rows** -- one row per paragraph/bullet/table-row out of
  omen-rulebook.md, every omen-*-spec.md, this repo's CLAUDE.md and SWARM.md,
  and research/marks/LEDGER.md. Carries (source file, heading path, date if
  the text names one, text).
* **mark rows** -- one row per human-judgement row, across every corpus
  research/build_deck.py's no-repeat guard reads (LEGACY_MARK_FILES +
  research/marks/*.jsonl), but only rows that actually carry comment/note
  text -- a blank note is not memory. Read-only: this file never writes to a
  mark corpus. Carries (source file, card id + grade, date if the card id or
  text names one, comment text).

    python research/omen_recall.py "84% tolerance"   # top 8 hits
    python research/omen_recall.py --rebuild          # force a re-index
    python research/omen_recall.py --stats            # row counts per source

The db (research/.omen_recall.sqlite, gitignored) auto-rebuilds whenever it
is missing or older than any source file it reads.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # research/
ROOT = HERE.parent                               # repo root
VAULT_PROJECTS = Path.home() / "Austin's Vault" / "Projects"
MARKS_DIR = HERE / "marks"
DB_PATH = HERE / ".omen_recall.sqlite"

_DATE_RE = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")
_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")

# Mirrors research/build_deck.py::LEGACY_MARK_FILES (paths relative to
# research/). Not imported directly -- build_deck.py pulls in deck_ui,
# t21_card_filter and research.t4_engine_recall at module load, which is a
# lot of engine machinery for a read-only index to drag in. SWARM.md's rule
# stands either way: a new mark corpus goes into BOTH lists in the same
# commit.
LEGACY_MARK_FILES = [
    "marks/deck_marks_h2_3lane_2026-08-28.jsonl",
    "marks/regrade_confirm_2026-09-03.jsonl",
    "austin_marks_v7.jsonl",
    "blind_marks_all.jsonl",
    "marks_clean.jsonl",
    "mark_batch_02_grades.jsonl",
    "mark_batch_03_regrades.jsonl",
    "mark_batch_04_grades.jsonl",
    "derived_marks_v1.jsonl",
    "derived_marks_v2.jsonl",
    "recovered_reviews.jsonl",
    "austin_verdicts.json",
]

# Austin's grade, wherever it is spelled -- a light-weight subset of
# research/grade_read.py's SCALAR_FIELDS list. Good enough for tagging a row
# in a search index; not a substitute for the canonical reader when a score
# is on the line.
_GRADE_SCALAR_FIELDS = ("austin_tier", "tier", "austin_grade", "grade", "verdict")


def _find_date(*texts):
    for t in texts:
        if t:
            m = _DATE_RE.search(t)
            if m:
                return m.group(1)
    return ""


# ---------------------------------------------------------------- doc rows


def doc_sources_default():
    paths = [
        VAULT_PROJECTS / "omen-rulebook.md",
        ROOT / "CLAUDE.md",
        ROOT / "SWARM.md",
        MARKS_DIR / "LEDGER.md",
    ]
    paths += sorted(VAULT_PROJECTS.glob("omen-*-spec.md"))
    return paths


def _is_table_sep(line):
    core = line.strip().strip("|")
    if not core:
        return False
    return set(core.replace(":", "").replace(" ", "")) == {"-"}


def parse_markdown_rows(text):
    """(heading path, row text) for every paragraph/bullet/table-row.

    Headings build a " > "-joined path. A blank line, a heading, or a table
    row all flush whatever paragraph/quote text has been accumulating -- so
    a bullet list with no blank lines between items (most of this repo's
    markdown) still yields one row per bullet, not one blob.
    """
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                lines = lines[i + 1 :]
                break

    rows = []
    heading_stack = []  # [(level, text), ...]
    buf = []

    def heading_path():
        return " > ".join(h for _, h in heading_stack)

    def flush():
        if buf:
            joined = re.sub(r"\s+", " ", " ".join(buf)).strip()
            if joined:
                rows.append((heading_path(), joined))
            buf.clear()

    for raw in lines:
        line = raw.rstrip("\n")
        if not line.strip():
            flush()
            continue
        m = _HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            heading_stack[:] = [h for h in heading_stack if h[0] < level]
            heading_stack.append((level, m.group(2).strip()))
            continue
        if line.lstrip().startswith("|"):
            flush()
            if _is_table_sep(line):
                continue
            core = line.strip().strip("|")
            cells = [c.strip() for c in core.split("|")]
            joined = " -- ".join(c for c in cells if c)
            if joined:
                rows.append((heading_path(), joined))
            continue
        if _BULLET_RE.match(line):
            flush()
            buf.append(_BULLET_RE.sub("", line, count=1).strip())
            continue
        buf.append(re.sub(r"^>+\s?", "", line).strip())
    flush()
    return rows


# --------------------------------------------------------------- mark rows


def mark_sources_default():
    return sorted(str(p) for p in MARKS_DIR.glob("*.jsonl")) + [
        str(HERE / name) for name in LEGACY_MARK_FILES
    ]


def _mark_rows(path):
    """Yield dict rows from a .jsonl file or a .json list. Read-only."""
    if not os.path.exists(path):
        return
    if path.endswith(".json"):
        try:
            data = json.load(open(path, encoding="utf-8"))
        except ValueError:
            return
        for row in data if isinstance(data, list) else data.values():
            if isinstance(row, dict):
                yield row
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                yield row


def _card_id(row):
    for f in ("card_id", "id"):
        v = row.get(f)
        if isinstance(v, str) and v:
            return v
    symbol = row.get("symbol")
    day = row.get("day") or row.get("date")
    entry_i = row.get("entry_i")
    if symbol and day and entry_i is not None:
        return f"{symbol}_{day}_{entry_i}"
    if symbol and day:
        return f"{symbol}_{day}"
    return ""


def _mark_grade(row):
    for f in _GRADE_SCALAR_FIELDS:
        v = row.get(f)
        if isinstance(v, str) and v.strip():
            return v.strip().upper()
    answers = row.get("answers")
    if isinstance(answers, dict):
        for f in ("your_grade", "grade"):
            v = answers.get(f)
            if isinstance(v, list) and v:
                return str(v[0]).strip().upper()
        for f in ("s", "s_call"):
            v = answers.get(f)
            if isinstance(v, list) and v and str(v[0]).strip().lower() in ("s", "yes"):
                return "S"
    return ""


def _mark_text(row):
    parts = []
    note = row.get("note")
    if isinstance(note, str) and note.strip():
        parts.append(note.strip())
    notes = row.get("notes")
    if isinstance(notes, str) and notes.strip():
        parts.append(notes.strip())
    elif isinstance(notes, dict):
        for v in notes.values():
            if isinstance(v, str) and v.strip():
                parts.append(v.strip())
    return " / ".join(parts)


# -------------------------------------------------------------------- db


def build_db(db_path, doc_paths, mark_paths):
    db_path = Path(db_path)
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute(
        "CREATE VIRTUAL TABLE recall USING fts5("
        "text, heading, source UNINDEXED, date UNINDEXED)"
    )
    for path in doc_paths:
        path = Path(path)
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for heading, row_text in parse_markdown_rows(text):
            date = _find_date(row_text, heading)
            con.execute(
                "INSERT INTO recall (text, heading, source, date) VALUES (?,?,?,?)",
                (row_text, heading, path.name, date),
            )
    for path in mark_paths:
        path = str(path)
        if not os.path.exists(path):
            continue
        source = os.path.basename(path)
        for row in _mark_rows(path):
            row_text = _mark_text(row)
            if not row_text:
                continue
            card_id = _card_id(row)
            grade = _mark_grade(row)
            heading = f"{card_id} [{grade}]" if grade else card_id
            date = _find_date(card_id, row_text)
            con.execute(
                "INSERT INTO recall (text, heading, source, date) VALUES (?,?,?,?)",
                (row_text, heading, source, date),
            )
    con.commit()
    con.close()


def _all_source_paths():
    return [p for p in doc_sources_default() if p.exists()] + [
        Path(p) for p in mark_sources_default() if os.path.exists(p)
    ]


def needs_rebuild(db_path):
    db_path = Path(db_path)
    if not db_path.exists():
        return True
    db_mtime = db_path.stat().st_mtime
    for p in _all_source_paths():
        try:
            if p.stat().st_mtime > db_mtime:
                return True
        except OSError:
            continue
    return False


def build_match(q):
    toks = re.findall(r"\w+", q)
    return " OR ".join(f'"{t}"' for t in toks) if toks else None


def search(db_path, query, k=8):
    match = build_match(query)
    if not match:
        return []
    con = sqlite3.connect(db_path)
    sql = (
        "SELECT text, heading, source, date, bm25(recall) AS score FROM recall "
        "WHERE recall MATCH ? ORDER BY score ASC, (date = '') ASC, date DESC LIMIT ?"
    )
    rows = con.execute(sql, (match, k)).fetchall()
    con.close()
    return rows


def print_stats(db_path):
    con = sqlite3.connect(db_path)
    rows = con.execute(
        "SELECT source, COUNT(*) FROM recall GROUP BY source ORDER BY source"
    ).fetchall()
    con.close()
    total = 0
    for source, n in rows:
        print(f"{n:5d}  {source}")
        total += n
    print(f"{total:5d}  TOTAL")


def _ensure_db(force=False):
    if force or needs_rebuild(DB_PATH):
        build_db(DB_PATH, doc_sources_default(), mark_sources_default())
        return True
    return False


def main():
    # Vault text carries em dashes, curly quotes, minus signs -- Windows'
    # default console codepage (cp1252) chokes on those. Force utf-8 out.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser(prog="omen_recall.py")
    ap.add_argument("query", nargs="?", help="search text, e.g. \"84% tolerance\"")
    ap.add_argument("--rebuild", action="store_true", help="force a full re-index")
    ap.add_argument("--stats", action="store_true", help="row counts per source")
    ap.add_argument("-k", type=int, default=8, help="max hits (default 8)")
    args = ap.parse_args()

    rebuilt = _ensure_db(force=args.rebuild)

    if args.stats:
        print_stats(DB_PATH)
        return
    if args.query:
        for text, heading, source, date, _score in search(DB_PATH, args.query, args.k):
            sentence = text if len(text) <= 220 else text[:217] + "..."
            print(f"{date} | {source}#{heading} | {sentence}")
        return
    if rebuilt:
        print(f"rebuilt {DB_PATH}")
        return
    ap.print_help()


if __name__ == "__main__":
    main()
