"""What the touch-fill rule on profit legs is worth, in dollars.

Austin ratified it 2026-08-30: "A profit target is a resting limit order and it
fills the moment price touches it." The code already did that everywhere
(`research/test_scaleout_touch.py` is the guard, `research/g83_scaleout_touch.md`
the finding), so the shipped book does not move. This prices the OTHER arm --
what waiting for a candle close on profit legs would have cost -- so the
ratified rule carries a number instead of a preference.

Two full two-year books, same engine, one env flag apart:

    python backtest_2y.py --days 730 --out <dir>/bt2y_touch.json
    TARGET_ON_CLOSE=1 python backtest_2y.py --days 730 --out <dir>/bt2y_close.json

`TARGET_ON_CLOSE` is `backtest_week`'s profit-leg switch and it governs all three
legs together -- the blind 2R target, the ladder's first scale rung and the
runner target. Nothing about a STOP changes between the arms: the stop trigger,
the resting -1R disaster order and the -1.25R floor are identical in both, which
is the point. Stops are a separate question and are not re-ratified.

The arithmetic is imported from `research/g72_suppress_price.py`, the same
functions the board and `g72_after_headline.py` use, so "dollars a day" means
here exactly what it means there. 1R = $1,000. The bar is $397/day
(=$100,000 / 252 sessions).

Usage:
    python research/g83_scaleout_price.py --touch A.json --close B.json

Writes research/g83_scaleout_price.json.
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from g72_suppress_price import stats, shipped_rows, oneaday_rows, load  # noqa: E402

BAR_PER_DAY = 100_000 / 252          # Austin, 2026-08-30: six figures a year
ROWS = ("trades", "win_pct", "per_trade", "per_day", "months_green", "months",
        "weeks_green", "weeks", "worst_drawdown", "total_dollars")


def score(path: Path) -> dict:
    meta, rows = load(path)
    nd = meta["sessions"]        # both arms replay the same 500 sessions
    return {"sessions": nd,
            "shipped": stats(shipped_rows(rows), nd),
            "one_a_day": stats(oneaday_rows(rows), nd)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--touch", required=True, help="book built with the shipped rule")
    ap.add_argument("--close", required=True, help="book built with TARGET_ON_CLOSE=1")
    ap.add_argument("--out", default=str(ROOT / "research" / "g83_scaleout_price.json"))
    args = ap.parse_args()

    touch, close = score(Path(args.touch)), score(Path(args.close))

    for stream in ("one_a_day", "shipped"):
        t, c = touch[stream], close[stream]
        print(f"\n== {stream.upper()} ==")
        print(f"{'':<18}{'TOUCH (shipped)':>18}{'CLOSE (arm)':>14}{'delta':>12}")
        for k in ROWS:
            a, b = t.get(k), c.get(k)
            if a is None or b is None:
                continue
            d = a - b
            print(f"  {k:<16}{a:>18,.1f}{b:>14,.1f}{d:>+12,.1f}")
        gap_t = t["per_day"] - BAR_PER_DAY
        gap_c = c["per_day"] - BAR_PER_DAY
        print(f"  {'vs $397/day':<16}{gap_t:>+18,.0f}{gap_c:>+14,.0f}"
              f"{gap_t - gap_c:>+12,.0f}")

    out = {"bar_per_day": round(BAR_PER_DAY, 2),
           "touch": touch, "close": close,
           "delta_per_day_one_a_day":
               round(touch["one_a_day"]["per_day"] - close["one_a_day"]["per_day"], 2),
           "delta_per_day_shipped":
               round(touch["shipped"]["per_day"] - close["shipped"]["per_day"], 2)}
    Path(args.out).write_text(json.dumps(out, indent=2))
    print("\nwrote", args.out)


if __name__ == "__main__":
    main()
