"""G7.2 verification — score the freshly rebuilt two-year book on the six
headline numbers the G7.1 board quotes, so "nothing was quietly fudged" is a
checkable claim and not a promise.

This does NOT re-run the backtest. Run `python backtest_2y.py` first (it writes
research/bt2y_trades.json); this reads that file and prices it.

The arithmetic is IMPORTED from research/g72_suppress_price.py rather than
re-typed, on purpose: win rate, months green, weeks green, drawdown and the
one-trade-a-day candidate stream all have to mean exactly what they meant when
the board was written, or the comparison is theatre. `oneaday_rows` in
particular is g71_board_check.py's candidate stream (fired-and-traded, plus the
rows the account-wide two-loss halt blocked -- under one-a-day that halt cannot
have fired yet).

1R = $1,000 (CLAUDE.md). Writes research/g72_after_headline.json.

Usage:
    python research/g72_after_headline.py
    python research/g72_after_headline.py --book path/to/other_book.json
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from g72_suppress_price import stats, shipped_rows, oneaday_rows, load, RISK  # noqa: E402

# What research/g71_board.md printed, 2026-08-28, off the pre-fix book.
# Row 125 of the board is the all-trades policy; row 126 is first-trade-only.
# The dispatch line quoted to this pass mixes the two, so both are carried here.
BOARD = {
    "shipped":   {"trades": 2437, "win_pct": 49.5, "per_day": 2700,
                  "months_green": 25, "months": 25, "weeks_green": 91, "weeks": 105,
                  "worst_drawdown": 14714, "note": "board table row 'Everything, as shipped today'"},
    "one_a_day": {"trades": 496, "win_pct": 54.9, "per_day": 611,
                  "months_green": 22, "months": 25, "weeks_green": 77, "weeks": 105,
                  "worst_drawdown": 20100, "note": "board table row 'First trade only, then done'"},
}
# The board also quotes a $17,132 worst drawdown for the shipped book in its
# prose (lines 59 / 329 / 339) against $14,714 in its own table -- the prose
# figure is the R31/loss-halt arm. Both are recorded so neither can be quietly
# adopted as "the" number.
BOARD_PROSE_SHIPPED_DRAWDOWN = 17132

FIELDS = ["trades", "win_pct", "per_trade", "per_day", "months_green", "months",
          "weeks_green", "weeks", "green_days_pct", "worst_drawdown", "total_dollars"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--book", default=str(ROOT / "research" / "bt2y_trades.json"))
    ap.add_argument("--out", default=str(ROOT / "research" / "g72_after_headline.json"))
    args = ap.parse_args()

    book = Path(args.book)
    if not book.exists():
        raise SystemExit("no book at %s -- run `python backtest_2y.py` first" % book)

    meta, rows = load(book)
    nd = meta["sessions"]

    out = {
        "book": str(book),
        "meta": {k: meta.get(k) for k in
                 ("generated", "first", "last", "sessions", "signals", "traded",
                  "halted", "loss_halt")},
        "risk_dollars": RISK,
        "board_prose_shipped_drawdown": BOARD_PROSE_SHIPPED_DRAWDOWN,
    }
    for name, sel in (("shipped", shipped_rows), ("one_a_day", oneaday_rows)):
        cur = stats(sel(rows), nd)
        out[name] = {"now": cur, "board": BOARD[name],
                     "delta": {f: round(cur.get(f, 0) - BOARD[name][f], 1)
                               for f in ("trades", "win_pct", "per_day",
                                         "months_green", "weeks_green",
                                         "worst_drawdown")}}

    # Labels landed this pass: every traded row should now carry a setup and a
    # level name. Report the coverage rather than assert it, so a gap shows up
    # as a number instead of a traceback.
    traded = shipped_rows(rows)
    lab = sum(1 for r in traded if r.get("setup_label"))
    lvl = sum(1 for r in traded if r.get("level_name"))
    out["labels"] = {
        "traded_rows": len(traded),
        "with_setup_label": lab,
        "with_level_name": lvl,
        "setup_label_pct": round(lab / len(traded) * 100, 1) if traded else 0.0,
        "level_name_pct": round(lvl / len(traded) * 100, 1) if traded else 0.0,
    }

    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)

    print("book      %s" % meta.get("generated"))
    print("sessions  %s   signals %s   traded %s"
          % (meta.get("sessions"), meta.get("signals"), meta.get("traded")))
    print()
    for name in ("shipped", "one_a_day"):
        cur, bd = out[name]["now"], out[name]["board"]
        print("== %s ==  (%s)" % (name.upper(), bd["note"]))
        print("  %-16s %14s %14s" % ("", "NOW", "G7.1 BOARD"))
        for f in FIELDS:
            b = bd.get(f, "-")
            print("  %-16s %14s %14s" % (f, cur.get(f, "-"), b))
        print()
    print("labels: setup %.1f%%, level %.1f%% of %d traded rows"
          % (out["labels"]["setup_label_pct"], out["labels"]["level_name_pct"],
             out["labels"]["traded_rows"]))
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()
