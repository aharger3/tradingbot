"""ADVERSARIAL VERIFY of track `smeasure`. Part 1: what grade labels actually
exist per corpus, so the "refused" pool can be audited.

Austin's ladder is S / A / C / none. Only `none` is a refusal. A and C are
DOWNGRADED-but-tradeable days (CLAUDE.md: "A = one downgrade, C = two").
Read-only.
"""
import os, sys, json
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import research.build_deck as bd

SEP = os.sep

for path in bd.mark_sources():
    name = os.path.relpath(path, HERE).replace(SEP, "/")
    c = Counter(); n = 0
    for r in bd._rows(path):
        n += 1
        for k in ("austin_tier", "tier", "austin_grade", "grade", "verdict"):
            v = r.get(k)
            if v not in (None, ""):
                c[k + "=" + str(v).strip().lower()] += 1
        a = r.get("answers")
        if isinstance(a, dict):
            for k in ("grade", "your_grade", "s", "s_call"):
                if a.get(k):
                    val = a[k][0] if isinstance(a[k], list) else a[k]
                    c["ans." + k + "=" + str(val).strip().lower()] += 1
        if r.get("_no_trade"):
            c["_no_trade=true"] += 1
    print("%-52s rows=%4d  %s" % (name, n, dict(c.most_common(14))))
