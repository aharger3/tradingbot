"""G71/trend, part 3 - on Austin's held-out S days, is the setup with the trend?

The book (research/g71_trend.py) can only answer this for the 25 of his 34 S
cards whose symbol the two-year book trades. This script answers it for all 34
by replaying each day through `research/t4_engine_recall.run_day` - the same
harness the recall gate itself uses - and taking the direction of the signal
nearest the minute he wrote on the card.

It also prints the definition-drift check: the two functions BOTH named
`htf_bias` in this repo disagree, and they feed the same hard veto.

  backtest_week.htf_bias_for:713          SMA20 of HOURLY closes  (~3 sessions)
  research/t4_engine_recall.htf_bias:108  SMA20 of DAILY  closes  (20 sessions)

The money book grades under the first; the recall gate grades under the second.

Usage:
  python research/g71_trend_scards.py [--out research/g71_trend_scards.json]
"""
from __future__ import annotations
import argparse, json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import polygon_feed as pf                                      # noqa: E402
from backtest_week import htf_bias_for                          # noqa: E402
from backtest_12mo import hourly_from_1m                        # noqa: E402
from research.t4_engine_recall import run_day, htf_bias as daily_bias   # noqa: E402
from research import g71_trend_cache as tc                      # noqa: E402
from research.g71_trend import DEFS, label, read_sweep, trend_sides  # noqa: E402

ARCHIVE = os.path.join(ROOT, "data_archive")


def archive_days(sym):
    d = os.path.join(ARCHIVE, sym)
    return sorted(f[:-4] for f in os.listdir(d) if f.endswith(".csv")) \
        if os.path.isdir(d) else []


def hourly_bias(sym, day):
    """backtest_week.htf_bias_for, fed the same hourly series backtest_2y feeds
    it: last close per hour bucket, RTH, over the sessions before `day`."""
    days = [d for d in archive_days(sym) if d < day][-8:]
    hourly = []
    for d in days:
        try:
            bars = pf.rth(pf.fetch_day(sym, d))
        except Exception:
            continue
        if bars:
            hourly.extend(hourly_from_1m(d, bars))
    return htf_bias_for(hourly, day)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "g71_trend_scards.json"))
    a = ap.parse_args()

    S_cards, refused, minute = read_sweep()
    ctx = tc.load()
    rows, tally = [], {k: Counter() for k in ("hourly", "daily") + tuple(DEFS[1:])}
    drift = Counter()

    for k in sorted(S_cards):
        sym, day = k
        et = minute.get(k)
        try:
            entries, sigs, _raw = run_day(sym, day)
        except Exception as e:
            entries, sigs = None, None
            err = "%s: %s" % (type(e).__name__, e)
        else:
            err = None if sigs is not None else "no archived bars"
        pick = None
        if sigs and et:
            m = int(et[:2]) * 60 + int(et[3:])
            pick = min(sigs, key=lambda s: abs(
                int(s["timestamp"][:2]) * 60 + int(s["timestamp"][3:5]) - m))
        hb, db = hourly_bias(sym, day), daily_bias(sym, day)
        drift["%s|%s" % (hb, db)] += 1
        rec = (ctx.get(sym) or {}).get(day)
        row = {"card": "%s_%s" % k, "min": et, "error": err,
               "n_sigs": len(sigs or ()), "n_fired": len(entries or ()),
               "dir": pick["direction"] if pick else None,
               "et": pick["timestamp"][:5] if pick else None,
               "grade": pick["grade"] if pick else None,
               "status": pick["status"] if pick else None,
               "hourly_bias": hb, "daily_bias": db}
        if pick:
            d = pick["direction"]
            row["hourly"] = label({"bullish": "bull", "bearish": "bear",
                                   "neutral": "flat"}.get(hb), d)
            row["daily"] = label({"bullish": "bull", "bearish": "bear",
                                  "neutral": "flat"}.get(db), d)
            tally["hourly"][row["hourly"]] += 1
            tally["daily"][row["daily"]] += 1
            if rec:
                sides = trend_sides({"bias": None, "et": row["et"],
                                     "entry": pick["entry"]}, rec)
                for name in DEFS[1:]:
                    row[name] = label(sides.get(name), d)
                    tally[name][row[name]] += 1
        rows.append(row)
        print("  %-20s %-5s %-4s %-3s %-11s h=%-8s d=%-8s %s"
              % (row["card"], et or "-", row["dir"] or "-", row["grade"] or "-",
                 row["status"] or (err or "-"), row.get("hourly", "-"),
                 row.get("daily", "-"),
                 " ".join("%s=%s" % (n[:6], row.get(n, "-")) for n in DEFS[1:])),
              flush=True)

    print("\nTALLY over the %d S cards with a signal near his minute:"
          % sum(1 for r in rows if r.get("dir")))
    for name, c in tally.items():
        print("  %-12s %s" % (name, dict(c)))
    print("\nDEFINITION DRIFT on the 34 S days  (hourly_bias | daily_bias):")
    for k, v in sorted(drift.items(), key=lambda kv: -kv[1]):
        print("  %-24s %d" % (k, v))
    same = sum(v for k, v in drift.items() if k.split("|")[0] == k.split("|")[1])
    print("  the two shipped `htf_bias` functions agree on %d of %d S days"
          % (same, len(rows)))

    json.dump({"cards": rows, "tally": {k: dict(v) for k, v in tally.items()},
               "drift": dict(drift)},
              open(a.out, "w", encoding="utf-8"), indent=1, default=str)
    print("\nwrote %s" % a.out)


if __name__ == "__main__":
    main()
