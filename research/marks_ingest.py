"""marks_ingest.py -- one command from a pasted export to a committed mark file.

    python research/marks_ingest.py --probe daily-2026-09-03 export.jsonl
    pbpaste | python research/marks_ingest.py --probe daily-2026-09-03 -
    python research/marks_ingest.py --probe daily-2026-09-03 - --no-commit

Austin does homework on his phone, hits Export -> Copy all, and pastes the JSONL
back. Everything between that paste and a committed file is mechanical, and
every one of those mechanical steps has already been skipped at least once:

* **The .gitignore trap, twice.** `research/*.jsonl` swallowed 5.2's T6 decks and
  needed `git add -f` for two later files, with nothing warning. So this script
  force-adds and then RE-READS `git status --porcelain` to confirm the file is
  actually staged. It does not assume the add worked -- CLAUDE.md's rule is
  "look", and this looks.
* **The no-repeat guard going blind.** A corpus that is not in
  `build_deck.LEGACY_MARK_FILES` is a corpus the deck builder cannot see, and a
  deck he was about to grade held four repeats because of it. The entry is added
  in the same run that writes the file, not in a follow-up nobody does.
* **`LEDGER.md` drifting.** The provenance record is the thing that says which
  corpora count and why. One line, same run.

WHAT IT REFUSES, AND WHY REFUSAL IS THE SAFE DIRECTION. A row without a
`card_id`, or with neither answers nor notes, is not a judgement and is dropped
with a reason printed. A (probe, card_id) already present in `research/marks/`
is a re-paste -- the page's Export hands back the WHOLE standing set every time,
so pasting twice in a day is the normal case, not an error -- and is skipped.
Nothing is ever overwritten: the output file is opened in APPEND mode, and if a
file for this probe and date already exists the new rows go on the end of it.

THE ONE RULE (CLAUDE.md): never lose a mark. This script only ever creates and
appends. It has no delete path, no rewrite path, and no --force.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

MARKS_DIR = os.path.join(HERE, "marks")
LEDGER = os.path.join(MARKS_DIR, "LEDGER.md")
BUILD_DECK = os.path.join(HERE, "build_deck.py")

# A probe name becomes a filename and a LEGACY_MARK_FILES entry, so it is held to
# the characters those can carry. Anything else is a typo or an injection.
_PROBE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


# ---------------------------------------------------------------------------
# read + validate
# ---------------------------------------------------------------------------

def parse(text: str) -> tuple[list, list]:
    """(rows, complaints). A row survives only if it is a JSON object with a
    card_id and at least one non-empty answer or note."""
    rows, bad = [], []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip().rstrip(",")          # a stray trailing comma is a paste artefact
        if not line or line in ("[", "]"):
            continue
        try:
            row = json.loads(line)
        except ValueError as e:
            bad.append("line %d: not JSON (%s)" % (n, e))
            continue
        if not isinstance(row, dict):
            bad.append("line %d: JSON but not an object" % n)
            continue
        if not str(row.get("card_id") or "").strip():
            bad.append("line %d: no card_id" % n)
            continue
        if not (_nonempty(row.get("answers")) or _nonempty(row.get("notes"))):
            bad.append("line %d: %s has neither answers nor notes"
                       % (n, row.get("card_id")))
            continue
        rows.append(row)
    return rows, bad


def _nonempty(v) -> bool:
    if isinstance(v, dict):
        return any(_nonempty(x) for x in v.values())
    if isinstance(v, (list, tuple)):
        return any(_nonempty(x) for x in v)
    return bool(str(v).strip()) if v is not None else False


def n_comments(rows) -> int:
    """Rows carrying prose. Austin, 2026-09-02: "its about the comments." """
    return sum(1 for r in rows if _nonempty(r.get("notes")))


# ---------------------------------------------------------------------------
# duplicate refusal
# ---------------------------------------------------------------------------

def existing_keys() -> set:
    """Every (probe, card_id) already in research/marks/."""
    seen = set()
    for path in sorted(glob.glob(os.path.join(MARKS_DIR, "*.jsonl"))):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("card_id"):
                    seen.add((str(row.get("probe") or ""), str(row["card_id"])))
    return seen


# ---------------------------------------------------------------------------
# write + register
# ---------------------------------------------------------------------------

def out_path(probe: str, day: str) -> str:
    return os.path.join(MARKS_DIR, "%s_%s.jsonl" % (probe, day))


def append_rows(path: str, rows) -> int:
    """APPEND. Never truncates, never rewrites, has no other mode."""
    os.makedirs(MARKS_DIR, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return len(rows)


def register_legacy(name: str) -> bool:
    """Add ``marks/<name>`` to build_deck.LEGACY_MARK_FILES. True if it changed.

    research/marks/*.jsonl is already globbed by `mark_sources()`, so this is
    belt AND braces -- exactly what `regrade_confirm_2026-09-03.jsonl` does, and
    for the stated reason: the guard survives the file later being moved.
    """
    entry = '    "marks/%s",\n' % name
    with open(BUILD_DECK, encoding="utf-8") as fh:
        src = fh.read()
    if entry.strip() in src:
        return False
    i = src.index("LEGACY_MARK_FILES = [")
    j = src.index("\n]", i)
    src = src[:j + 1] + entry + src[j + 1:]
    with open(BUILD_DECK, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src)
    return True


def append_ledger(name: str, probe: str, n: int, comments: int,
                  dupes: int, dropped: int) -> None:
    with open(LEDGER, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(
            "\n## %s — %d rows, human\n\n"
            "Austin's export from the `%s` page, pasted back and ingested by\n"
            "`research/marks_ingest.py` on %s. %d of the %d rows carry a written\n"
            "comment. %d re-pasted rows already present in `research/marks/` were\n"
            "skipped, and %d rows were dropped as non-judgements (no card_id, or\n"
            "neither answers nor notes).\n\n"
            "**Why it counts:** every row is a judgement he made on a chart —\n"
            "a grade, an entry, a stop, or prose about what the engine missed.\n\n"
            "**Provenance:** written append-only, JSON-validated row by row,\n"
            "`git add -f` then `git status` re-read to confirm it staged. Named in\n"
            "`build_deck.py::LEGACY_MARK_FILES` in the same commit.\n"
            % (name, n, probe, _dt.date.today().isoformat(), comments, n,
               dupes, dropped))


# ---------------------------------------------------------------------------
# git
# ---------------------------------------------------------------------------

def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(("git",) + args, cwd=ROOT, capture_output=True,
                          text=True)


def stage_and_commit(path: str, n: int, comments: int, probe: str,
                     touched_legacy: bool) -> bool:
    rel = os.path.relpath(path, ROOT).replace("\\", "/")
    _git("add", "-f", rel)
    # LOOK, do not assume. .gitignore has silently swallowed judgement files
    # twice; a green exit code from `git add` is not evidence it is staged.
    st = _git("status", "--porcelain", "--", rel).stdout
    if not st.strip() or st[0] not in "AM":
        print("REFUSING TO COMMIT: %s is not staged after `git add -f`.\n"
              "  git status said: %r\n"
              "  The rows ARE on disk at %s -- do not delete them."
              % (rel, st, path))
        return False
    _git("add", os.path.relpath(LEDGER, ROOT).replace("\\", "/"))
    if touched_legacy:
        _git("add", "research/build_deck.py")
    msg = ("marks: %d rows from %s (%d with comments)\n\n"
           "Ingested by research/marks_ingest.py: appended to %s, named in\n"
           "build_deck.py::LEGACY_MARK_FILES, one line added to\n"
           "research/marks/LEDGER.md.\n\n"
           "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
           % (n, probe, comments, rel))
    r = _git("commit", "-m", msg)
    if r.returncode != 0:
        print("commit failed:\n%s\n%s" % (r.stdout[-800:], r.stderr[-800:]))
        return False
    print("  committed: %s" % _git("log", "--oneline", "-1").stdout.strip())
    return True


# ---------------------------------------------------------------------------

def ingest(text: str, probe: str, day: str | None = None,
           commit: bool = True) -> int:
    if not _PROBE_RE.match(probe):
        raise SystemExit("bad probe name %r -- letters, digits, . _ - only" % probe)
    day = day or _dt.date.today().isoformat()

    rows, bad = parse(text)
    for b in bad:
        print("  dropped %s" % b)
    if not rows:
        print("nothing to save: no row carried a card_id and an answer or note")
        return 1

    for r in rows:
        r.setdefault("probe", probe)

    have = existing_keys()
    fresh, dupes = [], 0
    for r in rows:
        key = (str(r.get("probe") or ""), str(r["card_id"]))
        if key in have:
            dupes += 1
            continue
        have.add(key)
        fresh.append(r)
    if dupes:
        print("  skipped %d row(s) already in research/marks/ for this probe"
              % dupes)
    if not fresh:
        print("nothing new: every row was already saved")
        return 0

    path = out_path(probe, day)
    existed = os.path.exists(path)
    n = append_rows(path, fresh)
    comments = n_comments(fresh)
    name = os.path.basename(path)
    touched = register_legacy(name)
    if not existed:
        append_ledger(name, probe, n, comments, dupes, len(bad))

    print("%d rows saved to %s, %d comments"
          % (n, os.path.relpath(path, ROOT).replace("\\", "/"), comments))
    if not commit:
        print("  --no-commit: nothing staged")
        return 0
    return 0 if stage_and_commit(path, n, comments, probe, touched) else 1


def main():
    ap = argparse.ArgumentParser(
        description="Save a pasted homework export into research/marks/")
    ap.add_argument("source", help="path to the export, or - for stdin")
    ap.add_argument("--probe", required=True,
                    help="the page it came from, e.g. daily-2026-09-03")
    ap.add_argument("--date", default=None,
                    help="date in the filename (default: today)")
    ap.add_argument("--no-commit", action="store_true",
                    help="write and register, but do not stage or commit")
    a = ap.parse_args()

    text = (sys.stdin.read() if a.source == "-"
            else open(a.source, encoding="utf-8").read())
    sys.exit(ingest(text, a.probe, day=a.date, commit=not a.no_commit))


if __name__ == "__main__":
    main()
