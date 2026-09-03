"""G7.2 / `onespelling` -- who still reads Austin's grade by hand.

One function reads the grade now (`research/grade_read.py::read_grade`). This
script is the standing check that nobody quietly writes a sixth spelling reader:
it scans every .py in research/ for a literal read of one of the grade fields and
reports the files that do it WITHOUT importing grade_read.

It is a report, not a gate -- most of the hits are finished measurement scripts
whose published numbers must not move. Run it before adding a new S measurement,
and route the new one through grade_read.

Usage:
  python research/g72_onespelling_readers.py
"""
from __future__ import annotations

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import grade_read  # noqa: E402

# A literal read of a grade field off a mark row.
PATTERNS = [
    re.compile(r'\[["\']%s["\']\]' % f) for f in grade_read.SCALAR_FIELDS
] + [
    re.compile(r'\.get\(\s*["\']%s["\']' % f) for f in grade_read.SCALAR_FIELDS
] + [
    re.compile(r'answers["\']?\s*\)?\s*\[["\'](?:%s)["\']\]'
               % "|".join(grade_read.ANSWER_LADDER_FIELDS
                          + grade_read.ANSWER_YESNO_FIELDS)),
    re.compile(r'answers\.get\(\s*["\'](?:%s)["\']'
               % "|".join(grade_read.ANSWER_LADDER_FIELDS
                          + grade_read.ANSWER_YESNO_FIELDS)),
    re.compile(r'_no_trade'),
]

SELF = {"grade_read.py", "g72_onespelling_readers.py", "g72_onespelling_count.py"}

# Only files that actually open a mark corpus can be reading HIS grade. A
# `["grade"]` on an engine signal dict is the legacy A+/A/B/C/X ladder and is a
# different question entirely -- never route that through grade_read.
CORPUS = re.compile(r"mark_sources|marked_card_ids|austin_marks|blind_marks|"
                    r"marks_clean|mark_batch_0|derived_marks|recovered_reviews|"
                    r"austin_verdicts|rule_ballot|marks[/\\]|MARKS_DIR|probe_.*\.jsonl")


def main() -> int:
    routed, hand = [], []
    for path in sorted(glob.glob(os.path.join(HERE, "*.py"))):
        name = os.path.basename(path)
        if name in SELF:
            continue
        try:
            src = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        hits = sum(len(p.findall(src)) for p in PATTERNS)
        if not hits or not CORPUS.search(src):
            continue
        (routed if "grade_read" in src else hand).append((name, hits))

    print("ROUTED through grade_read (%d files):" % len(routed))
    for name, hits in routed:
        print("  %-46s %3d literal field reads left" % (name, hits))
    print("\nSTILL HAND-ROLLED (%d files) -- finished measurements, left alone so "
          "their published numbers do not move:" % len(hand))
    for name, hits in sorted(hand, key=lambda x: -x[1]):
        print("  %-46s %3d" % (name, hits))
    print("\nAny NEW S measurement must import research/grade_read.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
