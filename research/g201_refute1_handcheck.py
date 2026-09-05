"""g201 refute #1 -- hand-check of the unmanaged-fill-bar leak.

Walks a sample of MID25 fills whose post-fill stop was already touched on the
very bar the limit filled on, prints the raw candle so the claim can be read
off the data, and reports what those rows currently book under g158.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import g80_ordertype_grid as G   # noqa: E402
import backtest_week as bw                     # noqa: E402
from stop_rule import disaster_stop_price      # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades_retest_on.json"
EPS = 1e-9


def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    allrows = book["trades"]
    universe = [r for r in allrows if r.get("traded") or r["status"] == "halted"]
    universe.sort(key=lambda r: (r["day"], r["et"], r["sym"]))

    shown = 0
    n_hit = n_fill = 0
    pnl_hit = 0.0
    wins_hit = 0
    for r in universe:
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        i = r["entry_i"]
        if not bars or i >= len(bars):
            continue
        rng = bars[i].high - bars[i].low
        cut = G.cutoff_idx(bars)
        if rng <= 0 or i + 1 >= min(cut, len(bars) - 1):
            continue
        long = r["dir"] == "call"
        px = r["entry"] - 0.25 * rng if long else r["entry"] + 0.25 * rng
        j, fillpx = G.limit_touch(bars, px, long, i + 1, cut)
        if j is None or j >= len(bars) - 1:
            continue
        res = G.run_trade(r, bars, j, fillpx, pdh, pdl, pmh, pml,
                          move_stop_to_entry_bar=True)
        if res is None:
            continue
        n_fill += 1
        s = res["stop"]
        risk = abs(fillpx - s)
        dz = disaster_stop_price(fillpx, risk, long, bw.DISASTER_R)
        hit = (bars[j].low <= s + EPS) if long else (bars[j].high >= s - EPS)
        if not hit:
            continue
        n_hit += 1
        pnl_hit += res["pnl"]
        if res["pnl"] > 0:
            wins_hit += 1
        if shown < 8:
            c = bars[j]
            print("%-6s %s signal_i=%d fill_i=%d dir=%s | limit %.4f fill %.4f "
                  "stop %.4f disaster %.4f | fill bar O%.4f H%.4f L%.4f C%.4f "
                  "-> g158 books %s $%.0f"
                  % (r["sym"], r["day"], i, j, r["dir"], px, fillpx, s, dz,
                     c.open, c.high, c.low, c.close, res["out"], res["pnl"]))
            shown += 1

    print()
    print("MID25 fills priced: %d" % n_fill)
    print("of those, stop/disaster order touched on the UNMANAGED fill bar: %d (%.1f%%)"
          % (n_hit, n_hit / n_fill * 100))
    print("what g158 currently books for those rows: $%.0f total, %d wins (%.1f%%)"
          % (pnl_hit, wins_hit, wins_hit / n_hit * 100))
    print("shipped rule would book them all at -1R = $%.0f  (delta $%.0f)"
          % (-1000.0 * n_hit, -1000.0 * n_hit - pnl_hit))


if __name__ == "__main__":
    main()
