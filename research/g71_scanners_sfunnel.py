"""G7.1 / scanners — where Austin's S rows die. 2-year book, read-only.

`sgrade` is research/downgrade.py's S/A/C on the same row the engine graded
A+/A/B/C/X. This walks the 9,923 sgrade==S rows through the gates in the order
signal_runner._route applies them and reports the first one that killed each.
"""
import json, collections, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.load(open(ROOT / "research" / "bt2y_trades.json", encoding="utf-8"))
rows = d["trades"]
S = [r for r in rows if r["sgrade"] == "S"]
print("sgrade==S rows: %d of %d (%.1f%%)" % (len(S), len(rows), 100.0 * len(S) / len(rows)))

def why(r):
    if r["status"] == "halted":
        return "R31 loss halt (2 consecutive losses, account-wide)"
    if r["grade"] == "X":
        if r["aligned"] == "against":
            return "omen_bot.HTF_BIAS_VETO -> D (hourly bias opposed)"
        return "_grade_pa -> D (candle shape / not at level)"
    if r["status"] == "skipped_tight_stop":
        if "[skip: stop under" in r["reason"]:
            return "MIN_STOP_PCT (stop < 0.08% of price)"
        return "_min_viable_stop on a C"
    if r["grade"] == "C":
        return "grade C = alert only (never traded)"
    return "TRADED"

c = collections.Counter(why(r) for r in S)
for k, v in c.most_common():
    print("  %6d  %5.1f%%  %s" % (v, 100.0 * v / len(S), k))

print("\nsame funnel over ALL %d rows:" % len(rows))
c = collections.Counter(why(r) for r in rows)
for k, v in c.most_common():
    print("  %6d  %5.1f%%  %s" % (v, 100.0 * v / len(rows), k))

# what the S rows that DID trade are worth vs the rest
tr = [r for r in rows if r["traded"]]
for name, sub in (("sgrade S", [r for r in tr if r["sgrade"] == "S"]),
                  ("sgrade A", [r for r in tr if r["sgrade"] == "A"]),
                  ("sgrade C", [r for r in tr if r["sgrade"] == "C"])):
    R = [r["r"] for r in sub]
    print("%-10s n=%4d win%%=%5.1f meanR=%+.4f" %
          (name, len(R), 100.0 * sum(1 for x in R if x > 0) / len(R), statistics.fmean(R)))
