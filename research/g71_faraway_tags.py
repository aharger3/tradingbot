"""G7.1/faraway helper: tally every bracketed reason tag across the 2-year
signal set, so the report can say -- with a number -- how many signals were
refused or degraded by a LEVEL-DISTANCE rule rather than by anything else."""
import json, re, collections, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
BOOK = os.path.join(os.path.dirname(HERE), "research", "bt2y_trades.json")
d = json.load(open(BOOK, encoding="utf-8"))
c = collections.Counter()
for t in d["trades"]:
    for tag in re.findall(r"\[[^\]]+\]", t.get("reason") or ""):
        c[re.sub(r"\$[0-9.]+", "$X", tag)] += 1
print("signals:", len(d["trades"]))
for k, v in c.most_common(40):
    print("%7d  %s" % (v, k))
