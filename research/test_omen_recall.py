"""Self-test for research/omen_recall.py.

Builds a throwaway db from two tiny fixture markdown files (never touches the
real .omen_recall.sqlite or any mark corpus) and asserts a keyword search
finds the paragraph it should.

    python research/test_omen_recall.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "research"))

import omen_recall  # noqa: E402

FIXTURE_A = """---
date: 2026-01-01
---

# Fixture spec

## Decided 2026-01-01

- the widget tolerance is **84%**, not 25%, per the fixture ruling
- unrelated bullet about turnips

## Other section

Some unrelated paragraph about nothing in particular.
"""

FIXTURE_B = """# Fixture rulebook

## Stops

> *"the disaster stop sits at the level, not past it."* -- Fixture, 2026-01-02
"""


def main():
    tmpdir = Path(tempfile.mkdtemp(prefix="omen_recall_test_"))
    try:
        doc_a = tmpdir / "fixture-spec.md"
        doc_b = tmpdir / "fixture-rulebook.md"
        doc_a.write_text(FIXTURE_A, encoding="utf-8")
        doc_b.write_text(FIXTURE_B, encoding="utf-8")
        db_path = tmpdir / "test.sqlite"

        omen_recall.build_db(db_path, [doc_a, doc_b], [])

        hits = omen_recall.search(db_path, "84% tolerance", k=8)
        assert hits, "expected at least one hit for '84% tolerance'"
        joined = " ".join(h[0] for h in hits)  # text column
        assert "84%" in joined, f"expected the 84% row in hits, got: {hits}"
        top_source = hits[0][2]
        assert top_source == "fixture-spec.md", (
            f"expected fixture-spec.md to rank first, got {top_source}: {hits}"
        )

        hits2 = omen_recall.search(db_path, "disaster stop", k=8)
        assert hits2, "expected at least one hit for 'disaster stop'"
        assert any("disaster stop" in h[0] for h in hits2), hits2

        print("test_omen_recall: ok (%d + %d hits)" % (len(hits), len(hits2)))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
