"""G7.1 / adversarial verify of track `capture`'s "book-reachable recall 15/34 = 44.1%".

Two independent defects in that number, neither of which is a reproduction failure:

  1. WRONG UNIVERSE CONSTANT. `universe.BACKTEST_SYMBOLS` is `backtest_week.py`'s
     list (backtest_week.py:39-40, the only main-tree importer). The money /
     durability book is `backtest_2y.py`, and it iterates
     `[s for s in ALL_SYMS if has_archive(s, 100)]` (backtest_2y.py:92).
     SPCX and ACHR are in ALL_SYMS and ARE traded in the shipped book.

  2. MIXED DENOMINATOR. 15 is a numerator restricted to the traded universe;
     34 is an unrestricted denominator that still counts S cards on symbols no
     book can ever reach. Recall must restrict both sides or neither.

Reads only. No engine file touched, no mark file written.
Usage:  python research/g71_advcapture_universe_check.py
"""
from __future__ import annotations
import json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)

from universe import BACKTEST_SYMBOLS, ALL_SYMS  # noqa: E402

SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
BOOK = os.path.join(HERE, "bt2y_trades.json")

# hits reproduced from research/g71_capture_heldout_ab.py, arm B (delegating router)
B_HIT_OFF_UNIVERSE = {"ARM": 2, "MSTR": 2, "SMCI": 1, "ACHR": 1, "SPCX": 1}
B_HITS = 22
S_CARDS = 34


def main():
    d = json.load(open(BOOK, encoding="utf-8"))
    meta = d["meta"]
    traded = Counter(t["sym"] for t in d["trades"] if t.get("traded"))
    book_syms = set(traded)
    print("book: %s  sessions=%d  signals=%d  traded=%d"
          % (os.path.basename(BOOK), meta["sessions"], meta["signals"], meta["traded"]))
    print("book universe (meta.symbols) n=%d" % len(meta["symbols"]))
    print("symbols with >=1 traded row n=%d" % len(book_syms))
    print("BACKTEST_SYMBOLS n=%d   ALL_SYMS n=%d" % (len(BACKTEST_SYMBOLS), len(ALL_SYMS)))
    print("in the BOOK but NOT in BACKTEST_SYMBOLS:",
          sorted(book_syms - set(BACKTEST_SYMBOLS)))
    for s in ("SPCX", "ACHR", "ARM", "MSTR", "SMCI"):
        print("  %-5s traded rows in book: %-4d  in BACKTEST_SYMBOLS: %s  in ALL_SYMS: %s"
              % (s, traded.get(s, 0), s in BACKTEST_SYMBOLS, s in ALL_SYMS))

    cards = [json.loads(l) for l in open(SWEEP, encoding="utf-8") if l.strip()]
    s_cards = [r for r in cards if r["answers"].get("s") == ["s"]]
    assert len(s_cards) == S_CARDS, len(s_cards)
    s_by_sym = Counter(r["symbol"] for r in s_cards)
    off_bt = [r for r in s_cards if r["symbol"] not in BACKTEST_SYMBOLS]
    off_book = [r for r in s_cards if r["symbol"] not in book_syms]
    print("\nS cards: %d" % S_CARDS)
    print("  on symbols outside BACKTEST_SYMBOLS: %d %s"
          % (len(off_bt), dict(Counter(r["symbol"] for r in off_bt))))
    print("  on symbols outside the BOOK:         %d %s"
          % (len(off_book), dict(Counter(r["symbol"] for r in off_book))))

    off_hits_bt = sum(B_HIT_OFF_UNIVERSE.values())
    off_hits_book = sum(v for k, v in B_HIT_OFF_UNIVERSE.items() if k not in book_syms)
    print("\n== arm B (delegating router), %d/%d = %.1f%% raw ==" % (B_HITS, S_CARDS, B_HITS/S_CARDS*100))
    print("  CLAIM   : %d/%d = %.1f%%  (numerator cut by BACKTEST_SYMBOLS, denominator not cut)"
          % (B_HITS - off_hits_bt, S_CARDS, (B_HITS-off_hits_bt)/S_CARDS*100))
    print("  cut BOTH by BACKTEST_SYMBOLS: %d/%d = %.1f%%"
          % (B_HITS - off_hits_bt, S_CARDS - len(off_bt),
             (B_HITS-off_hits_bt)/(S_CARDS-len(off_bt))*100))
    print("  cut BOTH by the actual BOOK : %d/%d = %.1f%%   <-- correct book-reachable recall"
          % (B_HITS - off_hits_book, S_CARDS - len(off_book),
             (B_HITS-off_hits_book)/(S_CARDS-len(off_book))*100))
    print("  off-book hits are only: %s"
          % {k: v for k, v in B_HIT_OFF_UNIVERSE.items() if k not in book_syms})


if __name__ == "__main__":
    main()
