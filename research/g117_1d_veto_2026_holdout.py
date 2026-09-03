"""g117 — the 1D veto on 2026 only, and the pick-then-gate before/after.

omen-8 ticket 12(a) and 12(d). Two questions, one book, nothing refit:

  (a) `first_of_day_arm` used to pick the day's first candidate and let the
      size gate drop it downstream, so a day whose first setup was too tight to
      size vanished from the arm entirely instead of falling through to the
      next tradeable candidate. This prints the arm before and after that fix,
      with and without the 1D veto, so the veto's number can be read on a
      selection rule that does not silently lose days.

  (b) The 1D veto (skip a retest of a prior-day high or low) was found on the
      full two-year book. This scores it on 2026 ALONE -- a period the rule was
      not chosen on. Nothing is fitted here: the veto is one boolean already in
      `research/MORNING_REPORT.md`, applied as-is.

The veto is a MEASUREMENT arm, not the shipped live gate. Austin, 2026-09-03:
"PDH/PDL are good levels in my eyes" -- so `live_scanner.OMEN_LIVE_1D_VETO`
ships OFF and the live 11:00 summary reports both arms every day. This script
is how the two get compared on history.

    python research/g117_1d_veto_2026_holdout.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from omen_metrics import ev_r_scoreboard, first_of_day_arm   # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
# The two of Austin's six levels that are drawn on the daily chart. Single
# owner: backtest_2y.LEVEL_TF (commit 82f5639d). Named here rather than
# imported so this script does not drag the whole offline stack in.
ONE_D = {"PDH", "PDL"}


def _is_1d(row) -> bool:
    """True when this row retested a prior-day high or low.

    Prefers the book's own `level_tf` stamp; falls back to the level's name.
    Reported, never guessed: a row carrying neither is treated as not-1D and
    counted separately below.
    """
    tf = row.get("level_tf")
    if tf is not None:
        return tf == "1D"
    return (row.get("level_name") or row.get("stop_level_name") or "") in ONE_D


def _line(label, rows, sessions):
    sb = ev_r_scoreboard(rows, risk_dollars=1000.0, sessions=sessions)
    print("  %-34s n=%4d  ev_r=%+.4f  total_R=%8.2f  $/day=%6.0f  "
          "win=%5.1f%%  months_green=%-7s maxDD_R=%7.2f"
          % (label, sb["n"], sb["ev_r"], sb["total_R"],
             sb["expectancy_per_day"] or 0.0, 100 * (sb["win_rate"] or 0),
             sb["months_green"] or "-", sb["max_drawdown_R"]))
    return sb


def main() -> int:
    if not os.path.exists(BOOK):
        print("MISSING %s — run backtest_2y.py first." % BOOK)
        return 1

    blob = json.load(open(BOOK, encoding="utf-8"))
    rows, meta = blob["trades"], blob["meta"]
    sessions = meta.get("sessions") or len({r["day"] for r in rows})

    stamped = sum(1 for r in rows if r.get("level_tf") is not None)
    print("book: %s — %d rows, %d sessions, %d rows carry level_tf"
          % (os.path.basename(BOOK), len(rows), sessions, stamped))
    if stamped == 0:
        print("  NOTE: no row carries `level_tf`; the veto is being read off the\n"
              "  level NAME instead. That is the honest read available on this\n"
              "  book, not a silent equivalent — backtest_2y.level_label() is\n"
              "  what stamps the timeframe, and this book predates the stamp.")

    # ---- (a) pick-then-gate, before and after -----------------------------
    print("\n=== (a) pick-then-gate: the selection rule itself ===")
    old = first_of_day_arm(rows, size_gate=False)   # pick, then gate downstream
    new = first_of_day_arm(rows, size_gate=True)    # gate inside selection
    print("  days picked: before=%d  after=%d  (%+d days recovered)"
          % (len(old), len(new), len(new) - len(old)))
    sb_old = _line("before (pick, then gate)", old, sessions)
    sb_new = _line("after  (gate inside pick)", new, sessions)
    print("  days the old rule LOST to the gate: %d" % sb_old["n_dropped_size_gate"])
    print("  delta: ev_r %+.4f -> %+.4f (%+.4f), $/day %+.0f"
          % (sb_old["ev_r"], sb_new["ev_r"], sb_new["ev_r"] - sb_old["ev_r"],
             (sb_new["expectancy_per_day"] or 0) - (sb_old["expectancy_per_day"] or 0)))

    # ---- the 1D veto on the corrected arm ---------------------------------
    print("\n=== the 1D veto, full book, on the corrected arm ===")
    kept = [r for r in new if not _is_1d(r)]
    print("  1D rows in the arm: %d of %d (%.1f%%)"
          % (len(new) - len(kept), len(new),
             100.0 * (len(new) - len(kept)) / max(len(new), 1)))
    _line("no veto", new, sessions)
    _line("1D veto ON", kept, sessions)

    # ---- (d) 2026 only, nothing refit -------------------------------------
    print("\n=== (d) 2026 holdout — the veto scored on a year it was not chosen on ===")
    y26 = [r for r in new if r["day"] >= "2026-01-01"]
    if not y26:
        print("  no 2026 rows in this book.")
        return 0
    sess26 = len({r["day"] for r in rows if r["day"] >= "2026-01-01"})
    k26 = [r for r in y26 if not _is_1d(r)]
    print("  2026 sessions=%d, arm days=%d, 1D rows vetoed=%d"
          % (sess26, len(y26), len(y26) - len(k26)))
    a = _line("2026 no veto", y26, sess26)
    b = _line("2026 1D veto ON", k26, sess26)
    print("\n  2026 delta: ev_r %+.4f, $/day %+.0f, on %d vetoed day(s)."
          % (b["ev_r"] - a["ev_r"],
             (b["expectancy_per_day"] or 0) - (a["expectancy_per_day"] or 0),
             len(y26) - len(k26)))
    print("  A single year of one-trade-a-day is a few hundred rows. This is a\n"
          "  direction check, not a decision: it cannot separate a real effect\n"
          "  from noise at this sample size, and it is not a reason to ship the\n"
          "  veto live on its own.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
