"""G7.1 adversarial verify of the exitfam T8 crash claim.

Runs research/t8_strike_sweep.py unmodified, but with BOOK repointed at the
T0-ratified 2,595-trade book (the one the script itself pins) instead of the
2,437-row working-tree book. No shared file is edited.
"""
import os, runpy, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "research")
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

PINNED = os.path.join(ROOT, ".claude", "worktrees", "wf_a5cd199d-944-2",
                      "research", "bt2y_trades.json")

import importlib
mod = importlib.import_module("t8_strike_sweep")
mod.BOOK = PINNED
mod.__name__ = "__main__"
bk, meta = mod.load_book(PINNED)
mod.check_fingerprint(bk)
mod.section_holdout()
mod.section_sweep(bk)
mod.section_cards(bk)
mod.section_assume(bk)
print("COMPLETED WITHOUT EXCEPTION")
