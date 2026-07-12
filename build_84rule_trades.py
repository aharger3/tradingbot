"""Extract every reentry_84_rule trade + the original stopped-out break-and-retest
trade that armed it, from backtest_charts_12mo.json -> research/84rule_trades.json.

Mechanical join, NO analysis. The join key (verified unique on the 2026-07-11
12mo run: 89/89 match, 0 ambiguous):
  - same symbol + same day
  - original B&R entry == the "prior entry $X" named in the 84% reason
  - original B&R target == the 84% target (the re-entry inherits the original target)

All originals are outcome=loss (the stop-out that arms the one re-entry). Run
after `python backtest_12mo.py --snapshot` regenerates backtest_charts_12mo.json.

Usage: python build_84rule_trades.py [path/to/backtest_charts_12mo.json]
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "backtest_charts_12mo.json"
OUT = Path(__file__).parent / "research" / "84rule_trades.json"


def _ctx(rec):
    """Context fields for a trade record (drops the heavy candles array)."""
    entry_i = rec.get("entry_i", 0)
    candles = rec.get("candles", [])
    entry_time = candles[entry_i]["t"] if candles and entry_i < len(candles) else None
    return {
        "symbol": rec["symbol"], "day": rec["day"], "setup": rec["setup"],
        "direction": rec["direction"], "grade": rec["grade"],
        "alert_only": rec.get("alert_only", False), "outcome": rec["outcome"],
        "htf_bias": rec.get("htf_bias"),
        "entry": rec["entry"], "stop": rec["stop"], "target": rec["target"],
        "exit_price": rec.get("exit_price"), "pnl": rec.get("pnl"),
        "entry_time": entry_time, "reason": rec.get("reason", ""),
        "levels": rec.get("levels"),
    }


def near(a, b):
    return a is not None and b is not None and abs(a - b) < 0.02


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    r84 = [r for r in data if r.get("setup") == "reentry_84_rule"]
    br = [r for r in data if r.get("setup") == "break_and_retest"]
    by_key = defaultdict(list)
    for b in br:
        by_key[(b["symbol"], b["day"])].append(b)

    out, misses, multi = [], [], 0
    for r in r84:
        m = re.search(r"prior entry \$([0-9.]+)", r.get("reason", ""))
        prior_entry = float(m.group(1)) if m else None
        cand = [c for c in by_key.get((r["symbol"], r["day"]), [])
                if near(c.get("target"), r["target"])
                and near(c.get("entry"), prior_entry)]
        if len(cand) != 1:
            if not cand:
                misses.append({"symbol": r["symbol"], "day": r["day"],
                               "target": r["target"], "prior_entry": prior_entry})
            else:
                multi += 1
            continue
        out.append({"reentry": _ctx(r), "original": _ctx(cand[0])})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"84rule_trades.json -> {OUT}")
    print(f"  extracted: {len(out)} reentry_84_rule trades "
          f"(of {len(r84)} in source)")
    if misses:
        print(f"  WARNING: {len(misses)} reentries with no matching original B&R "
              f"(original may be D-grade / not charted):")
        for m_ in misses[:10]:
            print(f"    {m_}")
    if multi:
        print(f"  WARNING: {multi} reentries had multiple candidate originals (skipped)")
    # mechanical summary only — no edge analysis (spec: no analysis)
    from collections import Counter
    oc = Counter(r["reentry"]["outcome"] for r in out)
    print(f"  reentry outcomes: {dict(oc)}")


if __name__ == "__main__":
    main()
