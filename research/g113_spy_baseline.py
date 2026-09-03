"""OMEN 8.1 S4: INCLUDE_SPY_IN_BACKTEST flip -- SPY's contribution to recall,
money and durability, separately from the rest of the book.

Finding worth reading before the numbers: flipping the flag does NOT change
backtest_2y.py's book at all. That script pulls its symbol universe from
`universe.ALL_SYMS` (the newer MAJOR_15/INDEX_POOL/OTHER_POOL pool system,
2026-08-11), and SPY has been in `INDEX_POOL` unconditionally since that pool
system shipped -- `INCLUDE_SPY_IN_BACKTEST` only gates the older
`CORE_SYMBOLS`/`BACKTEST_SYMBOLS` lists, which this script uses solely for a
cosmetic "tier" label (core/experimental/other) on each row. Verified by
running the full 730-day book both ways and diffing: 124,834 signal rows
identical before and after, except the 4,247 SPY rows' `tier` field flips
from "other" to "core". So SPY's actual contribution to this book was never
gated by this flag -- it was always in.

Usage: python research/g113_spy_baseline.py [--book path/to/bt2y_trades.json]
  (defaults to a fresh 730-day run if no book is given -- this takes ~4 min)
"""
from __future__ import annotations
import argparse, json, math, statistics, subprocess, sys, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)


def money_durability(rows, denom_days):
    n = len(rows)
    if n == 0:
        return None
    mean_r = sum(r["r"] for r in rows) / n
    total_pnl = sum(r["pnl"] for r in rows)
    wins = sum(1 for r in rows if r["out"] == "win")
    by_month = defaultdict(float)
    for r in rows:
        by_month[r["ym"]] += r["pnl"]
    months = sorted(by_month)
    green = sum(1 for m in months if by_month[m] > 0)
    return {
        "n": n, "mean_r": mean_r, "win_pct": wins / n * 100,
        "total_pnl": total_pnl, "dollars_per_day": total_pnl / denom_days,
        "months_active": len(months), "months_green": green,
        "by_month": dict(by_month),
    }


def welch_ci(a, b):
    ra, rb = [r["r"] for r in a], [r["r"] for r in b]
    ma, mb = statistics.mean(ra), statistics.mean(rb)
    va = statistics.variance(ra) if len(ra) > 1 else 0.0
    vb = statistics.variance(rb) if len(rb) > 1 else 0.0
    se = math.sqrt(va / len(ra) + vb / len(rb))
    diff = ma - mb
    return diff, diff - 1.96 * se, diff + 1.96 * se


def recall_breakdown(marks):
    import t4_engine_recall as t4
    fired_bars = defaultdict(list)
    for sym, day in sorted({(m["symbol"], m["day"]) for m in marks}):
        ent, _sigs, _raw = t4.run_day(sym, day)
        if ent is None:
            continue
        fired_bars[(sym, day)].extend(e["bar"] for e in ent)

    def score(subset):
        total = len(subset)
        hit = sum(1 for m in subset
                   if any(abs(b - m["entry_i"]) <= t4.TOL
                          for b in fired_bars.get((m["symbol"], m["day"]), [])))
        return {"hit": hit, "total": total,
                "pct": (hit / total * 100) if total else 0.0}

    spy = [m for m in marks if m["symbol"] == "SPY"]
    rest = [m for m in marks if m["symbol"] != "SPY"]
    return {
        "spy_all": score(spy), "rest_all": score(rest),
        "spy_S": score([m for m in spy if m["tier"] == "S"]),
        "rest_S": score([m for m in rest if m["tier"] == "S"]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default=None,
                    help="existing bt2y trades json; omit to run a fresh 730-day book")
    ap.add_argument("--out", default=os.path.join(HERE, "g113_spy_baseline_data.json"))
    a = ap.parse_args()

    if a.book:
        book = json.load(open(a.book))
    else:
        tmp = "/tmp/bt2y_g113.json"
        subprocess.run([sys.executable, os.path.join(ROOT, "backtest_2y.py"),
                        "--days", "730", "--out", tmp], check=True, cwd=ROOT)
        book = json.load(open(tmp))

    trades = book["trades"]
    denom_days = book["meta"]["sessions"]
    traded = [r for r in trades if r["traded"]]
    s_only = [r for r in traded if r.get("sgrade") == "S"]

    result = {"denom_days": denom_days, "commit": book["meta"].get("commit")}
    for scope_name, rows in [("all_traded", traded), ("s_tier_only", s_only)]:
        spy = [r for r in rows if r["sym"] == "SPY"]
        rest = [r for r in rows if r["sym"] != "SPY"]
        diff, lo, hi = welch_ci(spy, rest) if spy and rest else (None, None, None)
        result[scope_name] = {
            "spy": money_durability(spy, denom_days),
            "rest": money_durability(rest, denom_days),
            "whole_book": money_durability(rows, denom_days),
            "mean_r_diff_spy_minus_rest": diff,
            "mean_r_diff_95ci": [lo, hi],
        }

    marks = [json.loads(l) for l in open(os.path.join(HERE, "austin_marks_v2.jsonl")) if l.strip()]
    result["recall"] = recall_breakdown(marks)

    with open(a.out, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(json.dumps({k: v for k, v in result.items() if k != "recall" or True},
                      indent=2, default=str)[:4000])
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
