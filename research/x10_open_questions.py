#!/usr/bin/env python
"""X10 -- reproduce every number published in research/x10_open_questions.md.

The X10 lane is a sweep, not a rig: most of its output is provenance (which file
answers which question). Four things in the report are MEASURED, and this script
is the thing that measured them. Run it from the repo root:

    python research/x10_open_questions.py
    python research/x10_open_questions.py --selfcheck

M1  the in-sample recall gate is RED at HEAD, and by how many marks
M2  the forward-clock freeze manifest has drifted -- which files, and the book size
M3  SPY's claim on the held-out gate (the number that reframes R4/Q12)
M4  SPY's claim on the whole judged corpus

Nothing here changes a default, writes a mark file, or re-freezes anything.
"""

from __future__ import annotations

import argparse
import collections
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

HELD_OUT = os.path.join(HERE, "marks", "probe_omen_test1_2026-08-27.jsonl")
FROZEN = os.path.join(HERE, "omen6_frozen.json")

# Every corpus CLAUDE.md names as holding a human judgement.
MARK_GLOBS = [
    "austin_marks_v7.jsonl",
    "blind_marks_all.jsonl",
    "recovered_reviews.jsonl",
    "marks_clean.jsonl",
    "marks/*.jsonl",
    "mark_batch_0*.jsonl",
    "derived_marks_v*.jsonl",
]


def _rows(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def _grade(row):
    g = row.get("grade")
    if g is None:
        g = (row.get("answers") or {}).get("grade")
    return str(g or "").strip().upper()


def _symday(row):
    sym = row.get("sym") or row.get("symbol") or ""
    day = row.get("d") or row.get("date") or row.get("day") or ""
    return (str(sym).strip().upper(), str(day)[:10]) if sym and day else None


# ---------------------------------------------------------------- M1


def m1_recall_gate():
    """Run research/regression_gate.py and count the dropped s_grade marks."""
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "regression_gate.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "") + (proc.returncode and (proc.stderr or "") or "")
    dropped = re.findall(r"DROPPED s_grade:\s*(\S+)", out)
    verdict = "RED" if re.search(r"^FAIL", out, re.M) else "GREEN"
    return {
        "verdict": verdict,
        "dropped_s_grade": sorted(dropped),
        "n_dropped": len(dropped),
        "exit_code": proc.returncode,
    }


# ---------------------------------------------------------------- M2


def m2_freeze_drift():
    """Which frozen files have moved since the manifest was stamped."""
    if not os.path.exists(FROZEN):
        return {"error": "no manifest at %s" % FROZEN}
    man = json.load(open(FROZEN, encoding="utf-8"))
    hashes = man.get("hashes") or man.get("files") or {}
    moved, held = [], []
    for rel, want in sorted(hashes.items()):
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            moved.append(rel)
            continue
        got = hashlib.sha256(open(path, "rb").read()).hexdigest()
        (held if got.startswith(str(want)[:16]) else moved).append(rel)

    book = os.path.join(HERE, "omen6_forward_book.jsonl")
    booked = sum(1 for _ in _rows(book)) if os.path.exists(book) else 0
    return {
        "frozen_at": man.get("frozen_at"),
        "commit": str(man.get("commit"))[:8],
        "moved": moved,
        "unchanged": held,
        "trades_booked": booked,
    }


# ---------------------------------------------------------------- M3


def m3_spy_heldout():
    """SPY's claim on the 100 held-out cards -- cards, and S days."""
    rows = list(_rows(HELD_OUT))
    grades = collections.Counter(_grade(r) for r in rows)
    syms = collections.Counter((r.get("sym") or r.get("symbol") or "").upper() for r in rows)
    spy_s = sum(
        1
        for r in rows
        if (r.get("sym") or r.get("symbol") or "").upper() == "SPY" and _grade(r) == "S"
    )
    return {
        "n_cards": len(rows),
        "grades": dict(grades),
        "n_symbols": len(syms),
        "spy_cards": syms.get("SPY", 0),
        "spy_s_days": spy_s,
        "s_days_total": grades.get("S", 0),
    }


# ---------------------------------------------------------------- M4


def m4_spy_corpus():
    """SPY's share of every distinct judged symbol-day across all mark corpora.

    Caveat carried into the report: grade lives under different keys across the
    corpora, so the S count here is a FLOOR, not the canonical 154.
    """
    seen, per_sym, s_days = set(), collections.Counter(), set()
    files = []
    for pat in MARK_GLOBS:
        files.extend(sorted(glob.glob(os.path.join(HERE, pat))))
    for path in files:
        for row in _rows(path):
            key = _symday(row)
            if not key:
                continue
            if key not in seen:
                per_sym[key[0]] += 1
            seen.add(key)
            if _grade(row) == "S":
                s_days.add(key)
    return {
        "files_read": len(files),
        "distinct_symbol_days": len(seen),
        "spy_symbol_days": per_sym.get("SPY", 0),
        "top_symbols": per_sym.most_common(6),
        "s_days_floor": len(s_days),
        "spy_s_days_floor": sum(1 for k in s_days if k[0] == "SPY"),
    }


# ---------------------------------------------------------------- run


def selfcheck():
    """Assert the shapes the report depends on, without asserting the values."""
    assert os.path.exists(HELD_OUT), "held-out card file missing"
    h = m3_spy_heldout()
    assert h["n_cards"] == 100, "held-out set is not 100 cards: %r" % h["n_cards"]
    assert h["s_days_total"] == 15, "held-out S count moved: %r" % h["s_days_total"]
    assert h["spy_cards"] >= 0 and h["spy_s_days"] <= h["spy_cards"]
    c = m4_spy_corpus()
    assert c["files_read"] > 0, "no mark corpora found"
    assert c["distinct_symbol_days"] > 500, "mark corpus looks truncated"
    f = m2_freeze_drift()
    assert "error" not in f, f.get("error")
    print("x10 selfcheck OK -- %d held-out cards, %d judged symbol-days, %d mark files"
          % (h["n_cards"], c["distinct_symbol_days"], c["files_read"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--skip-gate", action="store_true",
                    help="skip M1 (regression_gate.py takes a few minutes)")
    args = ap.parse_args()

    if args.selfcheck:
        selfcheck()
        return

    out = {}
    if not args.skip_gate:
        out["M1_recall_gate"] = m1_recall_gate()
    out["M2_freeze_drift"] = m2_freeze_drift()
    out["M3_spy_heldout"] = m3_spy_heldout()
    out["M4_spy_corpus"] = m4_spy_corpus()
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
