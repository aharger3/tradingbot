"""G7.1 / scanners — per-source economics over the 2-year book.
Which level sources and setup classes produce the traded book, and what each
is worth in R. Read-only."""
import json, collections, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.load(open(ROOT / "research" / "bt2y_trades.json", encoding="utf-8"))
rows = d["trades"]
traded = [r for r in rows if r["traded"]]


def stats(rs):
    if not rs:
        return "n=0"
    R = [r["r"] for r in rs]
    w = sum(1 for x in R if x > 0)
    return "n=%5d  win%%=%5.1f  meanR=%+7.4f  totR=%+9.1f" % (
        len(rs), 100.0 * w / len(rs), statistics.fmean(R), sum(R))


def group(rs, key, title):
    print("\n== %s ==" % title)
    g = collections.defaultdict(list)
    for r in rs:
        g[key(r)].append(r)
    for k in sorted(g, key=lambda k: -len(g[k])):
        print("  %-18s %s" % (k, stats(g[k])))


print("ALL TRADED:", stats(traded))
group(traded, lambda r: r["level"], "traded by level source")
group(traded, lambda r: r["setup"], "traded by setup")
group(traded, lambda r: r["sgrade"], "traded by Austin sgrade")
group(traded, lambda r: r["grade"], "traded by engine grade")

# pivot vs named
piv = [r for r in traded if r["level"].startswith("pivot")]
named = [r for r in traded if not r["level"].startswith("pivot")]
print("\n== pivot vs named (traded) ==")
print("  pivot :", stats(piv))
print("  named :", stats(named))
print("  named-only book total R = %+.1f vs full %+.1f" %
      (sum(r["r"] for r in named), sum(r["r"] for r in traded)))

# detections by level source (all statuses)
print("\n== all 76,019 detections by level source ==")
c = collections.Counter(r["level"] for r in rows)
for k, v in c.most_common():
    print("  %-18s %6d  (%4.1f%%)" % (k, v, 100.0 * v / len(rows)))

# S-grade rows (Austin ladder) by level source, traded and not
print("\n== Austin sgrade==S rows by level source ==")
sg = [r for r in rows if r["sgrade"] == "S"]
c = collections.Counter(r["level"] for r in sg)
for k, v in c.most_common():
    print("  %-18s %6d" % (k, v))
print("  of which traded:", sum(1 for r in sg if r["traded"]))

# monthly durability with pivots removed
print("\n== durability: months green ==")
def months(rs):
    g = collections.defaultdict(float)
    for r in rs:
        g[r["ym"]] += r["r"]
    return sum(1 for v in g.values() if v > 0), len(g)
print("  full book  : %d of %d green" % months(traded))
print("  named only : %d of %d green" % months(named))
print("  pivot only : %d of %d green" % months(piv))

# the 84% re-entry slice
r84 = [r for r in traded if r["setup"] == "reentry_84_rule"]
print("\n== 84%% re-entry (traded) ==", stats(r84))
