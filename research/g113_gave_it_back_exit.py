"""g113 -- what backtest_week.GAVE_IT_BACK_EXIT is worth.

R2 (Austin, 2026-09-03 ruling): "A trade that ran and came back through its
entry candle is dead. Exit at that close; do not wait for the stop." Implemented
in backtest_week.py as a bar-ordered, causal per-bar check (`_gave_it_back`),
flag-gated GAVE_IT_BACK_EXIT (default OFF, byte-identical when off -- proven
below by book_id), checked in `_ladder_bar` / `_ladder_bar_4` / the binary path
AFTER the disaster stop and the level stop (so a bar that satisfies both goes to
the STOP), and filled through `_stop_fill_px` (`stop_rule.stop_fill_price`) --
never a locally invented price. This is the IN-TRADE exit, distinct from
`omen_bot.detect_break_retest`'s pre-entry gave-it-back veto (research/g107):
that one stops a candidate from being taken at all; this one manages a trade
already open, on every bar of its life, not only the bar after entry.

Same one-trade-a-day unit as g86/g102/g107: the first candidate of the day that
clears `signal_runner.min_risk_floor`, book fill, over all 498 sessions.

Reproduce (both are the exact commands used to build the two books this script
reads, ~5 minutes each on the cached archive):

    RETEST_REQUIRED=1 python backtest_2y.py --out research/bt2y_trades_retest_on.json
    RETEST_REQUIRED=1 GAVE_IT_BACK_EXIT=1 python backtest_2y.py --out <on-book>

    python research/g113_gave_it_back_exit.py <off-book> <on-book>
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86             # noqa: E402
import signal_runner as sr                   # noqa: E402


def sized(r):
    return abs(r["entry"] - r["stop"]) >= sr.min_risk_floor(r["entry"])


def first_of_day(rows):
    """The one-trade-a-day pick: first size-gated candidate of each session,
    same rule g102.sized/g86.candidates uses everywhere else in this repo."""
    byday = g86.candidates(rows)
    picks = {}
    for d, v in byday.items():
        for r in v:
            if sized(r):
                picks[d] = r
                break
    return picks


def report(label, off_path, on_path):
    off_blob = json.load(open(off_path, encoding="utf-8"))
    on_blob = json.load(open(on_path, encoding="utf-8"))
    off_rows, on_rows = off_blob["trades"], on_blob["trades"]
    n_days = off_blob["meta"]["sessions"]
    assert n_days == on_blob["meta"]["sessions"], "session count mismatch"

    # ---- byte-identical-when-off proof --------------------------------
    off_stamp = off_blob["meta"]["stamp"]
    print("=== parity: GAVE_IT_BACK_EXIT off ===")
    print("  off-book id: %s" % off_stamp["book_id"])
    committed = os.path.join(HERE, "bt2y_trades_retest_on.json")
    if os.path.abspath(off_path) != os.path.abspath(committed) and os.path.exists(committed):
        c = json.load(open(committed, encoding="utf-8"))["meta"]["stamp"]
        print("  committed book_id (research/bt2y_trades_retest_on.json): %s" % c["book_id"])
        print("  MATCH -- byte-identical to the shipped book"
              if c["book_id"] == off_stamp["book_id"] else
              "  MISMATCH -- investigate before trusting anything below")
    print()

    # ---- reachability, whole traded book -------------------------------
    on_traded = [r for r in on_rows if r.get("traded")]
    off_traded_n = sum(1 for r in off_rows if r.get("traded"))
    print("=== reachability, ALL traded rows (not the one-a-day unit) ===")
    print("  off book: %d traded rows" % off_traded_n)
    print("  on  book: %d traded rows" % len(on_traded))
    print("  (counts differ because a changed exit can flip R31's two-loss")
    print("   account-wide halt for later signals THAT SAME DAY -- expected,")
    print("   not a bug: the halt is a statement about the day, and the veto")
    print("   changes some days' outcomes.)")
    print()

    # ---- the one-trade-a-day unit ---------------------------------------
    off_first = first_of_day(off_rows)
    on_first = first_of_day(on_rows)
    print("=== one-trade-a-day: first size-gated candidate, %d sessions ===" % n_days)
    print("  off days with a candidate: %d" % len(off_first))
    print("  on  days with a candidate: %d" % len(on_first))

    def stats_of(picks):
        rows = list(picks.values())
        return g86.stats(rows, n_days)

    off_s, on_s = stats_of(off_first), stats_of(on_first)
    print()
    print("  %-28s %6s %8s %8s %10s %10s" %
          ("", "n", "$/day", "win%", "green/mo", "maxDD"))
    print("  %-28s %6d %8d %8.1f %6d/%-3d %10d" %
          ("off (shipped exit, today)", off_s["trades"], off_s["per_day"],
           off_s["win_pct"], off_s["months_green"], off_s["months"],
           off_s["worst_drawdown"]))
    print("  %-28s %6d %8d %8.1f %6d/%-3d %10d" %
          ("on (+ gave-it-back exit)", on_s["trades"], on_s["per_day"],
           on_s["win_pct"], on_s["months_green"], on_s["months"],
           on_s["worst_drawdown"]))
    print()
    print("  delta: $%+d/day, %+.1f win pts, %+d green months, DD %+d"
          % (on_s["per_day"] - off_s["per_day"], on_s["win_pct"] - off_s["win_pct"],
             on_s["months_green"] - off_s["months_green"],
             on_s["worst_drawdown"] - off_s["worst_drawdown"]))

    # ---- how many of the 498 first-of-day picks did the veto touch? ----
    changed, better, worse, ident_changed = 0, 0, 0, 0
    for d in sorted(set(off_first) & set(on_first)):
        o, n = off_first[d], on_first[d]
        key_o = (o["sym"], o["et"], o["entry_i"], o["dir"])
        key_n = (n["sym"], n["et"], n["entry_i"], n["dir"])
        if key_o != key_n:
            # a downstream halt cascade changed which candidate books the
            # day's risk-floor slot -- not a direct fire on this pick
            ident_changed += 1
            continue
        if round(o["pnl"], 2) != round(n["pnl"], 2):
            changed += 1
            if n["pnl"] > o["pnl"]:
                better += 1
            else:
                worse += 1
    print()
    print("  first-of-day candidate SAME identity, pnl differs (the veto")
    print("  fired on this exact trade): %d of %d" % (changed, len(off_first)))
    print("    -> better off %d, worse off %d" % (better, worse))
    print("  first-of-day candidate identity CHANGED (halt cascade, not a")
    print("  direct fire): %d of %d" % (ident_changed, len(off_first)))
    print()
    print("  cf. in-engine funnel, ALL traded signals whole book (not just")
    print("  first-of-day): see GAVE_IT_BACK_FUNNEL printed by the run that")
    print("  built the ON book.")


if __name__ == "__main__":
    off_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "bt2y_trades_retest_on.json")
    on_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "g113_on_full.json")
    report("gave-it-back exit", off_path, on_path)
