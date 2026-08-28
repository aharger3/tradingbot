"""x14 -- the one number the twelve lanes did not produce: a STACKED arm.

Every lane A/B'd one lever against the shipped book. Not one reported two
levers together, so nothing in the digest says whether the surviving levers
add or overlap. This script stacks the only two that can be stacked from
columns that already ship in research/g3_arm_ow1.json:

  A1        -- x8's recommendation: drop the 10:45-11:00 entry block.
  S3/A1/C0  -- x12's finding 14: risk-weight by Austin's ladder, S 3x / A 1x / C 0x.
                (a sizing arm, so it is read as mean R PER UNIT OF RISK, not per trade)

x1's flat-2.5R arm cannot be stacked here: no per-row flat-target column ships
in research/x1_mfe_mae.json (it carries mfe/mae/oracle, not per-arm outcomes),
which is itself the reason nobody could stack anything.

Reproduces, as a cross-check, x8's A1 (+0.0534R over baseline) and x12's
sizing arm (+1.1693 R/unit) exactly.

    python research/x14_completeness_critic.py
"""
import collections
import json
import pathlib

BOOK = pathlib.Path(__file__).with_name("g3_arm_ow1.json")
WEIGHTS = {"S": 3.0, "A": 1.0, "C": 0.0, "none": 0.0}


def traded(book):
    """The shipped 1,017-row book: fired, and not legacy grade C.

    backtest_week.py:221-223 -- `counted = status == 'fired' and grade != 'C'`.
    """
    return [t for t in book["trades"]
            if t.get("status") == "fired" and t.get("grade") != "C"]


def mean(vals):
    return sum(vals) / len(vals) if vals else float("nan")


def months_green(rows):
    by_month = collections.defaultdict(float)
    for r in rows:
        by_month[r["ym"]] += r["r"]
    return sum(1 for v in by_month.values() if v > 0), len(by_month)


def weighted_mean(rows):
    """Mean R per unit of risk deployed, not per trade -- a sizing arm changes
    the denominator, so a per-trade mean would not be comparable."""
    num = sum(WEIGHTS.get(r.get("sgrade"), 0.0) * r["r"] for r in rows)
    den = sum(WEIGHTS.get(r.get("sgrade"), 0.0) for r in rows)
    return (num / den if den else float("nan")), den


def drop_last_block(rows):
    """x8's A1: the only slice in that study significantly negative in BOTH halves."""
    return [r for r in rows if not ("10:45" <= r["et"] < "11:00")]


def main():
    rows = traded(json.loads(BOOK.read_text()))
    base = mean([r["r"] for r in rows])
    g, n = months_green(rows)
    print(f"BASE             n={len(rows):4d}  mean={base:+.4f} R/trade  months={g}/{n}")

    a1 = drop_last_block(rows)
    g, n = months_green(a1)
    print(f"A1  drop 10:45   n={len(a1):4d}  mean={mean([r['r'] for r in a1]):+.4f} R/trade  "
          f"months={g}/{n}   delta={mean([r['r'] for r in a1]) - base:+.4f}")

    w, units = weighted_mean(rows)
    print(f"S3/A1/C0 sizing  units={units:7.1f}  mean={w:+.4f} R/unit   delta={w - base:+.4f}")

    w2, units2 = weighted_mean(a1)
    print(f"STACK  A1+size   units={units2:7.1f}  mean={w2:+.4f} R/unit   delta={w2 - base:+.4f}")
    print(f"                 additive would be {(mean([r['r'] for r in a1]) - base) + (w - base) + base:+.4f}; "
          f"gap to the 2.0 money gate is {2.0 - w2:+.4f} R")

    s_only = [r for r in rows if r.get("sgrade") == "S"]
    g, n = months_green(s_only)
    print(f"S-only           n={len(s_only):4d}  mean={mean([r['r'] for r in s_only]):+.4f} R/trade  months={g}/{n}")
    print("sgrade mix:", dict(collections.Counter(r.get("sgrade") for r in rows)))


if __name__ == "__main__":
    main()
