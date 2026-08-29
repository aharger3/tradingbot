"""T3 - the 84% rule rewritten from source vs. the shipped default, on the
2-year book. Same error-bar method research/t0_rebaseline.py uses (1.96x the
standard error of the difference in mean R, treating the two books as
independent samples), applied twice: to the whole traded book, and to the
reentry_84_rule slice on its own.

Reads two backtest_2y.py books:
  BEFORE = shipped default (RULE84_SOURCE unset/0)
  AFTER  = RULE84_SOURCE=1 python backtest_2y.py ...

Usage:
  python research/t3_backtest_compare.py BEFORE.json AFTER.json
"""
from __future__ import annotations
import argparse, json, math, statistics as st


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    return d["meta"], d["trades"]


def traded(rows):
    return [r for r in rows if r["traded"]]


def stats(rows):
    tr = traded(rows)
    rs = [r["r"] for r in tr]
    wins = [r for r in tr if r["out"] == "win"]
    losses = [r for r in tr if r["out"] == "loss"]
    decided = len(wins) + len(losses)
    sd = st.pstdev(rs) if len(rs) > 1 else 0.0
    return {
        "n": len(tr),
        "mean_r": st.fmean(rs) if rs else 0.0,
        "sd_r": sd,
        "se_r": sd / math.sqrt(len(rs)) if rs else 0.0,
        "win_rate": (len(wins) / decided * 100) if decided else 0.0,
    }


def error_bar(before_rows, after_rows):
    B, A = stats(before_rows), stats(after_rows)
    se = math.sqrt(B["se_r"] ** 2 + A["se_r"] ** 2)
    bar = 1.96 * se
    move = A["mean_r"] - B["mean_r"]
    return {"before": B, "after": A, "move": move, "error_bar_95": bar,
            "inside_bar": abs(move) < bar}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    a = ap.parse_args()

    _mb, rb = load(a.before)
    _ma, ra = load(a.after)

    print("=== whole book ===")
    whole = error_bar(rb, ra)
    print(json.dumps(whole, indent=2))

    r84_b = [r for r in rb if r["setup"] == "reentry_84_rule"]
    r84_a = [r for r in ra if r["setup"] == "reentry_84_rule"]
    print("\n=== reentry_84_rule slice only ===")
    slice_ = error_bar(r84_b, r84_a)
    print(json.dumps(slice_, indent=2))

    print("\n=== reentry_84_rule signal counts (all statuses, not just traded) ===")
    print("before:", sum(1 for r in rb if r["setup"] == "reentry_84_rule"))
    print("after: ", sum(1 for r in ra if r["setup"] == "reentry_84_rule"))


if __name__ == "__main__":
    main()
