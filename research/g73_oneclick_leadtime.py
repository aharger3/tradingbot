"""G7.3 / oneclick — how much of the book can be ORDERED BEFORE THE BELL.

g73_oneclick_delay.py showed the edge is not lost to reaction time, it is lost
the moment you pay a market price: 83% of traded rows book their entry AT THE
LEVEL (an order already resting there), and that family carries 100% of the
edge. So the design question stops being "how fast can he click" and becomes
"how early can the order be sitting there".

This script asks three things of the same two-year book, and nothing else:

  1. WHICH LEVELS. Split every traded row by whether the level it entered on
     was knowable BEFORE 09:30 (PDH/PDL from yesterday, PMH/PML from the
     premarket session) or only formed intraday (HOD/LOD, opening range,
     pivots, order blocks). A premarket-knowable level can carry a bracket
     order placed at 09:25, before he starts work.
  2. WOULD A RESTING LIMIT AT THE LEVEL HAVE FILLED. The book's fill is
     `min(max(level, bar.low), bar.high)` -- clamped INTO the bar. When the
     clamp bites, the bar never traded at the level and a resting limit there
     would NOT have filled. Counted, with the money attached.
  3. WHEN. Entry-time histogram, so the share needing a live decision inside
     09:30-11:00 is a number rather than a worry.

Reads research/bt2y_trades.json. Writes research/g73_oneclick_leadtime.json.
Usage:  python research/g73_oneclick_leadtime.py
"""
import argparse, json, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

import polygon_feed as pf                                            # noqa: E402
from g72_suppress_price import load, stats, RISK                     # noqa: E402
from g73_oneclick_delay import shipped_stream, oneaday_candidates    # noqa: E402

# Knowable before 09:30. PDH/PDL come off yesterday's session; PMH/PML off the
# 04:00-09:29 premarket bars. HOD/LOD, the opening range and pivots cannot
# exist until the session has run.
PREBELL = {"PDH", "PDL", "PMH", "PML"}


def bucket(row):
    n = (row.get("level_name") or "").strip()
    if n in PREBELL:
        return "pre-bell"
    if n in ("HOD", "LOD"):
        return "intraday: session extreme"
    if n.startswith("not-his: OR"):
        return "intraday: opening range"
    if n.startswith("not-his: pivot"):
        return "intraday: pivot"
    if n:
        return "intraday: " + n.replace("not-his: ", "")
    return "unnamed"


def summarise(rows, nd):
    out = {}
    for r in rows:
        b = bucket(r)
        d = out.setdefault(b, {"trades": 0, "dollars": 0.0})
        d["trades"] += 1
        d["dollars"] += r["pnl"]
    tot = sum(d["dollars"] for d in out.values()) or 1.0
    for b, d in out.items():
        d["mean_r"] = round(d["dollars"] / d["trades"] / RISK, 3)
        d["per_day"] = round(d["dollars"] / nd, 0)
        d["dollars"] = round(d["dollars"], 0)
        d["share_of_dollars_pct"] = round(d["dollars"] / tot * 100, 1)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["dollars"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--book", default=str(ROOT / "research" / "bt2y_trades.json"))
    ap.add_argument("--out", default=str(ROOT / "research" / "g73_oneclick_leadtime.json"))
    args = ap.parse_args()

    meta, rows = load(Path(args.book))
    nd = meta["sessions"]
    ship = shipped_stream(rows)
    oad = [v[0] for _, v in sorted(oneaday_candidates(rows).items())]

    out = {"book": args.book, "sessions": nd,
           "levels_shipped": summarise(ship, nd),
           "levels_one_a_day": summarise(oad, nd)}

    # ---- 2. would a resting limit AT the level have filled?
    groups = defaultdict(list)
    for r in ship:
        groups[(r["sym"], r["day"])].append(r)
    tally = defaultdict(lambda: {"trades": 0, "dollars": 0.0})
    for (sym, day), rs in sorted(groups.items()):
        try:
            bars = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            bars = []
        for r in rs:
            ei = r["entry_i"]
            lp = r.get("level_px")
            if not bars or ei >= len(bars) or lp is None:
                k = "unknown"
            else:
                c = bars[ei]
                # the clamp in signal_runner.fill_price. If the level sits
                # inside the signal bar's range, a resting limit there fills.
                k = ("limit at the level fills" if c.low - 0.005 <= lp <= c.high + 0.005
                     else "level never traded -- resting limit misses")
            tally[k]["trades"] += 1
            tally[k]["dollars"] += r["pnl"]
    for k, d in tally.items():
        d["mean_r"] = round(d["dollars"] / d["trades"] / RISK, 3)
        d["per_day"] = round(d["dollars"] / nd, 0)
        d["dollars"] = round(d["dollars"], 0)
    out["resting_limit_at_level"] = dict(tally)

    # ---- 3. when does he have to act?
    hist = defaultdict(lambda: {"trades": 0, "dollars": 0.0})
    for r in oad:
        k = r["et"][:2] + ":" + ("00" if int(r["et"][3:5]) < 30 else "30")
        hist[k]["trades"] += 1
        hist[k]["dollars"] += r["pnl"]
    for d in hist.values():
        d["dollars"] = round(d["dollars"], 0)
    out["one_a_day_entry_clock"] = dict(sorted(hist.items()))

    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)

    print("== WHICH LEVEL, one-trade-a-day (%d days) ==" % len(oad))
    for b, d in out["levels_one_a_day"].items():
        print("  %-32s %4d trades  meanR %6.3f  $%8s  %5.1f%% of the money"
              % (b, d["trades"], d["mean_r"], d["dollars"], d["share_of_dollars_pct"]))
    print("\n== WHICH LEVEL, every trade (%d) ==" % len(ship))
    for b, d in out["levels_shipped"].items():
        print("  %-32s %4d trades  meanR %6.3f  $%9s  %5.1f%% of the money"
              % (b, d["trades"], d["mean_r"], d["dollars"], d["share_of_dollars_pct"]))
    print("\n== WOULD A RESTING LIMIT AT THE LEVEL HAVE FILLED (every trade) ==")
    for k, d in out["resting_limit_at_level"].items():
        print("  %-44s %4d trades  meanR %6.3f  $%9s"
              % (k, d["trades"], d["mean_r"], d["dollars"]))
    print("\n== WHEN he would have to act, one-trade-a-day ==")
    for k, d in out["one_a_day_entry_clock"].items():
        print("  %s  %3d days  $%s" % (k, d["trades"], d["dollars"]))
    print("\nwrote %s" % args.out)


if __name__ == "__main__":
    main()
