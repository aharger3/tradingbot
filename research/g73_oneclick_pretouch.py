"""G7.3 / oneclick — the hole in "just rest the order at the level before the bell".

The book's winning fill is an order already sitting at the level. So the design
says: place the bracket before 09:30 and let it fill while he is at work.

The catch this script measures: a resting order fills on ANY touch of that
level. The engine does not. It waits for a break, a leave, a return and a bar
that CLOSES through -- and only then books the trade. So a pre-placed order is
a DIFFERENT strategy, and the difference is every earlier touch.

For each one-trade-a-day row this counts how many times its own level was
touched between 09:30 and the bar the engine actually fired on. A count of 0
means a resting order would have filled on the same bar the engine did -- the
design holds. A count of 3 means the order would have been long gone, filled on
a touch the engine refused, two touches earlier.

Reads research/bt2y_trades.json. Writes research/g73_oneclick_pretouch.json.
Usage:  python research/g73_oneclick_pretouch.py
"""
import argparse, json, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

import polygon_feed as pf                                            # noqa: E402
from g72_suppress_price import load, RISK                            # noqa: E402
from g73_oneclick_delay import shipped_stream, oneaday_candidates    # noqa: E402
from g73_oneclick_leadtime import bucket                             # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--book", default=str(ROOT / "research" / "bt2y_trades.json"))
    ap.add_argument("--out", default=str(ROOT / "research" / "g73_oneclick_pretouch.json"))
    args = ap.parse_args()

    meta, rows = load(Path(args.book))
    oad = [v[0] for _, v in sorted(oneaday_candidates(rows).items())]

    groups = defaultdict(list)
    for r in oad:
        groups[(r["sym"], r["day"])].append(r)

    hist = defaultdict(lambda: {"days": 0, "dollars": 0.0})
    prebell_hist = defaultdict(lambda: {"days": 0, "dollars": 0.0})
    # How much WARNING the setup gives, in minutes: from the first time price
    # touched the level (the earliest the engine could possibly have said
    # "watch this") to the bar it fired on. This is an UPPER BOUND on the
    # arming window -- the real arm is later, once the break has left the level
    # -- but it bounds how long he has to place an order.
    first_lead, last_lead = [], []
    for (sym, day), rs in sorted(groups.items()):
        try:
            bars = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            bars = []
        for r in rs:
            lp, ei = r.get("level_px"), r["entry_i"]
            if not bars or lp is None or ei >= len(bars):
                k = "unknown"
            else:
                # a touch = the level sits inside that bar's range, on any bar
                # of the session BEFORE the one the engine fired on
                hit = [i for i, c in enumerate(bars[:ei]) if c.low <= lp <= c.high]
                n = len(hit)
                k = str(n) if n <= 4 else "5+"
                if hit:
                    first_lead.append(ei - hit[0])
                    last_lead.append(ei - hit[-1])
            hist[k]["days"] += 1
            hist[k]["dollars"] += r["pnl"]
            if bucket(r) == "pre-bell":
                prebell_hist[k]["days"] += 1
                prebell_hist[k]["dollars"] += r["pnl"]

    def fin(h):
        for d in h.values():
            d["mean_r"] = round(d["dollars"] / d["days"] / RISK, 3)
            d["dollars"] = round(d["dollars"], 0)
        return dict(sorted(h.items()))

    def pct(v, q):
        v = sorted(v)
        return v[min(len(v) - 1, int(q * len(v)))] if v else None

    out = {"book": args.book,
           "warning_minutes_from_first_touch": {
               "n": len(first_lead),
               "p10": pct(first_lead, .10), "median": pct(first_lead, .50),
               "p90": pct(first_lead, .90)},
           "warning_minutes_from_last_touch": {
               "n": len(last_lead),
               "p10": pct(last_lead, .10), "median": pct(last_lead, .50),
               "p90": pct(last_lead, .90)},
           "touches_before_the_signal_all": fin(hist),
           "touches_before_the_signal_prebell_only": fin(prebell_hist)}
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)

    for name, h in (("EVERY one-a-day trade", out["touches_before_the_signal_all"]),
                    ("PRE-BELL levels only", out["touches_before_the_signal_prebell_only"])):
        tot = sum(v["days"] for v in h.values()) or 1
        print("\n== times the level was touched BEFORE the engine fired -- %s ==" % name)
        for k, d in h.items():
            print("  %-8s %4d days (%4.1f%%)  meanR %6.3f  $%s"
                  % (k, d["days"], d["days"] / tot * 100, d["mean_r"], d["dollars"]))
    print("\nwrote %s" % out and args.out)


if __name__ == "__main__":
    main()
