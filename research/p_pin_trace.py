"""Cycle P (research/tape/cycles.md, 2026-09-13): does the OFF arm reproduce
the 2026-09-05 baseline (book_id 2c39ced2697c26cc) once the window is pinned
--start 2024-09-04 --end 2026-09-04? And if not, what does the pinned window
actually read, honestly, on today's archive?

Every figure below is read off the book named on the command line -- nothing
here is re-typed from a report. Same unit, slice and script path
research/loop_cycle.py already uses for every other row, imported not
retyped.

    python research/p_pin_trace.py PINNED_BOOK.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import book_stamp                                    # noqa: E402
from research.loop_cycle import (                                  # noqa: E402
    apply_universe_filter, compute_all, load_book_any,
)

BASELINE_BOOK_ID = "2c39ced2697c26cc"
LOOP_CFG = json.loads((ROOT / "research" / "tape" / "loop.json").read_text(encoding="utf-8"))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "research/tape/rebuild_pin_check.json"
    meta, rows = load_book_any(path)
    book_id = meta.get("stamp", {}).get("book_id") or book_stamp.book_id(rows)
    print("book: %s" % path)
    print("book_id: %s  (baseline: %s)  match: %s"
          % (book_id, BASELINE_BOOK_ID, book_id == BASELINE_BOOK_ID))
    print("window: %s..%s, %d sessions, %d symbols"
          % (meta.get("first"), meta.get("last"), meta.get("sessions"), len(meta.get("symbols", []))))

    core_rows = apply_universe_filter(rows, LOOP_CFG["universe"])
    figs = compute_all(meta, core_rows, LOOP_CFG["unit"], LOOP_CFG["halves_boundary"])
    for slice_name in ("whole", "h1", "h2"):
        f = figs[slice_name]
        print("%-6s trades=%-4d per_day=%-6s mean_r=%-8s win_pct=%-6s "
              "avg_win=%-6s avg_loss=%-6s months_green=%s/%s"
              % (slice_name, f.get("trades", 0), f.get("per_day"), f.get("mean_r"),
                 f.get("win_pct"), f.get("avg_win"), f.get("avg_loss"),
                 f.get("months_green"), f.get("months")))


if __name__ == "__main__":
    main()
