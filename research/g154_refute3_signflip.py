"""g154 refuter #3 -- sign-flip permutation p-value for the k=0.50 survivor test.

Under the null "the BE rule changes nothing systematic", each pick's delta dR is
equally likely to have carried the opposite sign. Flip signs at random, recompute
the exact criterion the claim uses (H1 $/day delta > 0 AND H2 $/day delta > 0),
and count how often a null arm passes. Same fill/units as g154.
"""
from __future__ import annotations
import importlib, json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
g154 = importlib.import_module("g154_rule_be-stop-after-enough-past-pt1")
import g86_honest_ceiling as g86
import omen_metrics as om

H = g154.H_SPLIT
blob = json.load(open(g154.BOOK_PATH, encoding="utf-8"))
rows = blob["trades"]
nd1 = g154.n_days_in(rows, hi=H); nd2 = g154.n_days_in(rows, lo=H)
firsts = om.first_of_day_arm(rows, size_gate=True)
g154.K_VALUES = (0.5,)
base_rows, k_rows, _ = g154.build_lists(firsts)
d = [k["r"] - b["r"] for b, k in zip(base_rows, k_rows[0.5])]
h1 = [i for i, r in enumerate(base_rows) if r["day"] < H]
h2 = [i for i, r in enumerate(base_rows) if r["day"] >= H]
obs1 = sum(d[i] for i in h1) * g86.RISK / nd1
obs2 = sum(d[i] for i in h2) * g86.RISK / nd2
print("observed H1 %+.1f  H2 %+.1f $/day" % (obs1, obs2))
random.seed(1)
N = 20000
both = one = 0
ge = 0
for _ in range(N):
    s = [x if random.random() < 0.5 else -x for x in d]
    a = sum(s[i] for i in h1); b = sum(s[i] for i in h2)
    if a > 0 and b > 0:
        both += 1
    if a > 0 or b > 0:
        one += 1
    if (a * g86.RISK / nd1) >= obs1 and (b * g86.RISK / nd2) >= obs2:
        ge += 1
print("null pass rate for 'H1>0 AND H2>0': %.3f  (one-sided-either %.3f)" % (both / N, one / N))
print("p(null arm >= BOTH observed halves): %.4f" % (ge / N))
