"""Selection/discipline simulator (Austin 2026-07-10): from ALL detected signals,
trade only the best few per day and END THE DAY WHEN GREEN. Grid-searches the
discipline rules to find the 55%-win config. Uses backtest_charts.json (every
counted+alert signal with reason/[clean]/[late] tags) from the last 12mo run.

$1k risk, 2R: win +$2000, loss -$1000, scratch = recorded pnl.
Run: python rank_sim.py
"""
import itertools
import json
from collections import defaultdict

recs = json.load(open("backtest_charts.json", encoding="utf-8"))
for r in recs:
    r["time"] = r["candles"][r["entry_i"]]["t"] if r["candles"] else "00:00"

by_day = defaultdict(list)
for r in recs:
    by_day[r["day"]].append(r)
for d in by_day:
    by_day[d].sort(key=lambda r: r["time"])

MONTHS = len({d[:7] for d in by_day})


def sim(grades, clean_only, max_n, stop_green, loss_stop):
    wins = losses = 0
    pnl = 0.0
    for d, sigs in by_day.items():
        day_pnl, taken, day_losses = 0.0, 0, 0
        for r in sigs:
            if taken >= max_n or day_losses >= loss_stop:
                break
            if stop_green and taken > 0 and day_pnl > 0:
                break
            if r["grade"] not in grades:
                continue
            if clean_only and "[late]" in r["reason"]:
                continue
            taken += 1
            day_pnl += r["pnl"]
            pnl += r["pnl"]
            if r["outcome"] == "win":
                wins += 1
            elif r["outcome"] == "loss":
                losses += 1
                day_losses += 1
    dec = wins + losses
    wr = wins / dec * 100 if dec else 0
    return wins, losses, wr, pnl


def score(r):
    """Live-executable quality score (2026-07-10 feature split, 12mo B&R):
    clean-A 50%W, wide structural stop 44%W vs tight 32%W, PM levels worst."""
    s = 0
    if "[clean]" in r["reason"]:
        s += 2
    if r["grade"] in ("A+", "A"):
        s += 2
    if abs(r["entry"] - r["stop"]) / r["entry"] >= 0.003:
        s += 2
    if "PMH" not in r["reason"] and "PML" not in r["reason"]:
        s += 1
    return s


def sim_score(min_score, max_n, stop_green):
    wins = losses = 0
    pnl = 0.0
    for d, sigs in by_day.items():
        day_pnl, taken = 0.0, 0
        for r in sigs:
            if taken >= max_n or (stop_green and taken > 0 and day_pnl > 0):
                break
            if r["setup"] != "break_and_retest" or score(r) < min_score:
                continue
            taken += 1
            day_pnl += r["pnl"]
            pnl += r["pnl"]
            wins += r["outcome"] == "win"
            losses += r["outcome"] == "loss"
    dec = wins + losses
    return wins, losses, (wins / dec * 100 if dec else 0), pnl


def main():
    print("Score-threshold mode (B&R only):")
    print("  minScore maxN green |  WR%    W    L    P&L     $/mo")
    for ms in (3, 4, 5, 6):
        for max_n, green in ((1, False), (2, True), (2, False)):
            w, l, wr, pnl = sim_score(ms, max_n, green)
            if w + l < 30:
                continue
            print(f"  {ms:<8} {max_n:<4} {str(green):<5} | {wr:5.1f} {w:4} {l:4} "
                  f"{pnl:9,.0f} {pnl/MONTHS:7,.0f}")
    print()
    rows = []
    for grades, clean, max_n, green, lstop in itertools.product(
            [("A+", "A"), ("A+", "A", "B")], [True, False],
            [1, 2, 3], [True, False], [1, 2, 99]):
        w, l, wr, pnl = sim(grades, clean, max_n, green, lstop)
        if w + l < 60:  # too few trades to trust
            continue
        rows.append((wr, pnl, w, l, grades, clean, max_n, green, lstop))

    print(f"{MONTHS} months of data. All configs with >=60 decided trades:\n")
    print("  WR%    P&L/yr   $/mo    W    L  grades      clean maxN green lossStop")
    for wr, pnl, w, l, g, c, n, gr, ls in sorted(rows, reverse=True)[:15]:
        print(f"{wr:5.1f} {pnl:9,.0f} {pnl/MONTHS:7,.0f} {w:4} {l:4}  "
              f"{'+'.join(g):<11} {str(c):<5} {n:<4} {str(gr):<5} {ls}")
    print("\nTop by P&L:")
    for wr, pnl, w, l, g, c, n, gr, ls in sorted(rows, key=lambda r: -r[1])[:10]:
        print(f"{wr:5.1f} {pnl:9,.0f} {pnl/MONTHS:7,.0f} {w:4} {l:4}  "
              f"{'+'.join(g):<11} {str(c):<5} {n:<4} {str(gr):<5} {ls}")


if __name__ == "__main__":
    main()
