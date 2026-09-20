"""research/test_status_page.py -- the phone status page must actually show
tonight's numbers, not a stale template.

Builds research/build_status.py's page against a small temp fixture (never
the live repo files -- the real research/tape/*.md changes every night, so
pinning assertions to it would make this test flaky) and checks:

  1. the headline's "$/day" text is on the page;
  2. the newest nightly.md row's date is on the page (proves last_night_line
     reads the LAST row, not the header or an earlier one);
  3. adopted_status()'s few accepted shapes of the not-yet-final
     shipped_flags.json (dict-of-bool, dict-of-dict, list-of-dict, missing
     file, non-ship decision) each resolve the way the docstring promises;
  4. build() writes a real file to disk and skips the AI-Outputs copy when
     told to (so the test never touches the real dispatch path).

    python research/test_status_page.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import shutil
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from research import build_status as bs  # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if not cond:
        FAILURES.append(f"{name}: {detail}")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture(tmp: Path) -> dict:
    """A minimal, self-consistent set of input files under tmp, and the
    `sources` dict build_status.render() needs to read them instead of the
    real repo paths."""
    tape = tmp / "tape"
    journal = tmp / "journal"

    _write(tape / "summary_data.json", json.dumps({
        "baseline": {"whole": {"per_day": -52, "green_months": 11, "months": 25}}
    }))

    _write(tape / "cycles.md", "\n".join([
        "# loop cycles",
        "| date | label | flag | decision | $/day a->b | green months a->b | H1 | H2 | trades | off book | on book | script |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
        "| 2026-09-05 | l1 | F1 | hold | -9.0 -> 29.0 | 12 -> 12 | pass | fail | 767 | off | on | s |",
        "<!-- a repair note with a | pipe | in it, must not be parsed as a row -->",
        "| 2026-09-14 | l2 | F2 | hold | -52.0 -> -87.0 | 11 -> 11 | fail | fail | 773 | off | on | s |",
        "| 2026-09-19 | l3 | BNR_DISPLACEMENT_GATE | ship | -52.0 -> -54.0 | 11 -> 11 | pass | pass | 770 | off | on | s |",
    ]))

    newest_date = "2026-09-19"
    _write(tape / "nightly.md", "\n".join([
        "# nightly loop receipts", "",
        "| date | flag | decision | $/day a->b | green a->b | off_book_id -> on_book_id |",
        "|---|---|---|---|---|---|",
        "| 2026-09-17 | - | empty | - | - | - |",
        "| %s | BNR_DISPLACEMENT_GATE | ship | -52.0 -> -54.0 | 11 -> 11 | aaa -> bbb |" % newest_date,
    ]))

    _write(tape / "loop_queue.json", json.dumps([
        {"_example": True, "flag": "EXAMPLE_FLAG", "on": "1", "label": "not real"},
        {"flag": "HTF_BIAS_GATE", "on": "1", "label": "only trade with the daily trend"},
        {"flag": "OCR_STRICT", "on": "1", "label": "the full one-candle-rule clause list"},
    ]))

    _write(tape / "shipped_flags.json", json.dumps({"BNR_DISPLACEMENT_GATE": True}))

    _write(journal / "alpaca-paper.jsonl", "\n".join([
        json.dumps({"event": "entry", "ts": "2026-09-17T10:35:00", "arm": "engine"}),
        json.dumps({"event": "entry", "ts": "09:52:00", "arm": "engine",
                    "candidate_id": "AAPL_2026-09-18_0952"}),
        json.dumps({"event": "dry_fire", "ts": "10:10:00", "arm": "austin",
                    "candidate_id": "AAPL_2026-09-18_1010"}),
        json.dumps({"event": "entry_error", "ts": "2026-09-19T11:07:37"}),
    ]))

    _write(journal / "bar-deck-2026-09-19.log", (
        "=== OMEN bar deck 2026-09-19 === \n"
        "sm deck 2026-09-19: 3 cards, from somewhere\n"
    ))

    sources = {
        "summary_data": tape / "summary_data.json",
        "cycles_md": tape / "cycles.md",
        "nightly_md": tape / "nightly.md",
        "loop_queue": tape / "loop_queue.json",
        "shipped_flags": tape / "shipped_flags.json",
        "alpaca_paper": journal / "alpaca-paper.jsonl",
        "bar_deck_glob": str(journal / "bar-deck-*.log"),
    }
    return {"sources": sources, "newest_date": newest_date}


def test_page_shows_dollar_per_day_and_newest_nightly_date() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="build_status_test_"))
    try:
        fx = _fixture(tmp)
        html = bs.render(fx["sources"])
        check("page has $/day headline", "$/day" in html, html[:200])
        check("page has newest nightly.md date", fx["newest_date"] in html,
              "expected %r in rendered page" % fx["newest_date"])
        check("page has last-night flag+decision", "BNR_DISPLACEMENT_GATE ship" in html, html)
        check("page has adopted yes (shipped_flags.json says True)", "adopted yes" in html, html)
        check("page has queue count and label", "2 left" in html and "HTF_BIAS_GATE" not in html,
              "queue line should show plain-English labels, not flag names: %s" % html)
        check("page has v5 sessions/fills", "2 sessions, 2 fills" in html, html)
        check("page has bar deck count", "3 cards last night" in html, html)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_adopted_status_shapes() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="build_status_adopted_test_"))
    try:
        dict_bool = tmp / "a.json"
        dict_dict = tmp / "b.json"
        list_shape = tmp / "c.json"
        real_shape = tmp / "d.json"
        missing = tmp / "does_not_exist.json"

        _write(dict_bool, json.dumps({"F": True}))
        _write(dict_dict, json.dumps({"F": {"adopted": False}}))
        _write(list_shape, json.dumps([{"flag": "F", "adopted": True}]))
        # research/shipped_flags.py's actual schema: append-only list, key
        # is "adopt" not "adopted", last entry per flag wins.
        _write(real_shape, json.dumps([
            {"flag": "F", "value": "1", "adopt": False},
            {"flag": "F", "value": "1", "adopt": True},
        ]))

        check("dict-of-bool True -> yes", bs.adopted_status("F", "ship", dict_bool) == "yes")
        check("dict-of-dict False -> no", bs.adopted_status("F", "ship", dict_dict) == "no")
        check("list-of-dict (adopted key) True -> yes", bs.adopted_status("F", "ship", list_shape) == "yes")
        check("real shipped_flags.py schema, last entry wins -> yes",
              bs.adopted_status("F", "ship", real_shape) == "yes")
        check("missing file -> unknown", bs.adopted_status("F", "ship", missing) == "unknown")
        check("hold decision -> n/a", bs.adopted_status("F", "hold", dict_bool) == "n/a")
        check("unlisted flag -> unknown", bs.adopted_status("OTHER", "ship", dict_bool) == "unknown")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_build_writes_file_and_skips_dispatch_copy_when_asked() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="build_status_build_test_"))
    try:
        out = tmp / "omen-status.html"
        result = bs.build(out=out, dispatch_copy=None)
        check("build() returns the out path", result == out)
        check("build() wrote a real file", out.exists() and out.stat().st_size > 0)
        check("build() output has $/day", "$/day" in out.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    test_page_shows_dollar_per_day_and_newest_nightly_date()
    test_adopted_status_shapes()
    test_build_writes_file_and_skips_dispatch_copy_when_asked()

    if FAILURES:
        print("STATUS PAGE TEST FAILED: %d check(s)" % len(FAILURES))
        for f in FAILURES:
            print("  " + f)
        sys.exit(1)

    print("status page test ok: page shows $/day and the newest nightly.md date, "
          "adopted_status handles every shipped_flags.json shape it documents, "
          "and build() writes a real file without touching the dispatch copy.")


if __name__ == "__main__":
    main()
