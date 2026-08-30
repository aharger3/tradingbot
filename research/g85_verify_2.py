"""g85_verify_2 -- adversarial recompute of the g85 accuracy claim.

Written from the replay dumps up, NOT by importing g83_recall278's scorer.
The point is to see whether a second, independent count of the same two
arm files lands on the same recall, the same false-fire rate, the same
separation, and the same paired flip counts.
"""
from __future__ import annotations
import json, os, sys, random, math
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)

import marks_pool as mp

H = json.load(open(os.path.join(HERE, "_g85_arms", "arm_honest.json"), encoding="utf-8"))
P = json.load(open(os.path.join(HERE, "_g85_arms", "arm_published.json"), encoding="utf-8"))
assert H["entry_fill"] == "close" and P["entry_fill"] == "published", "arms mislabelled"

pool = mp.canonical_pool()
days = sorted(k for k, e in pool.items() if e.has_bars)
print("bar-backed judged days:", len(days))
print("arm day counts: honest", len(H["days"]), "published", len(P["days"]))
missing_h = [k for k in days if k not in H["days"]]
missing_p = [k for k in days if k not in P["days"]]
print("days missing from a dump:", len(missing_h), len(missing_p))

grade = {k: pool[k].grade for k in days}
from collections import Counter
print("grade mix:", dict(Counter(grade.values())))

S    = [k for k in days if grade[k] == "S"]
NONE = [k for k in days if grade[k] == "none"]
print("S days:", len(S), " refusal days:", len(NONE))

def hit(arm, k):
    d = arm["days"].get(k)
    return bool(d and d["hit"])

def rate(arm, keys):
    n = sum(1 for k in keys if hit(arm, k)); return n, len(keys), 100.0 * n / len(keys)

for name, arm in (("honest", H), ("published", P)):
    rs = rate(arm, S); rn = rate(arm, NONE)
    prec = 100.0 * rs[0] / (rs[0] + rn[0])
    print(f"{name:>10}  recall_S {rs[0]}/{rs[1]} = {rs[2]:.1f}%   "
          f"false_fire {rn[0]}/{rn[1]} = {rn[2]:.1f}%   "
          f"sep {rs[2]-rn[2]:+.1f} pts   precision(S vs none) {prec:.1f}%")

# ---- detection: did the fill change what was DETECTED? -------------------
sig_h = sum(H["days"][k]["n_signals"] for k in days)
sig_p = sum(P["days"][k]["n_signals"] for k in days)
ent_h = sum(H["days"][k]["n_entries"] for k in days)
ent_p = sum(P["days"][k]["n_entries"] for k in days)
same_sig = sum(1 for k in days if H["days"][k]["n_signals"] == P["days"][k]["n_signals"])
same_ent = sum(1 for k in days if H["days"][k]["n_entries"] == P["days"][k]["n_entries"])
print(f"signals {sig_p} -> {sig_h} ({sig_h-sig_p:+d});  entries {ent_p} -> {ent_h} ({ent_h-ent_p:+d})")
print(f"days with identical signal count {same_sig}/{len(days)}; identical entry count {same_ent}/{len(days)}")

# ---- paired flips + exact McNemar ---------------------------------------
def mcnemar(keys):
    b = sum(1 for k in keys if hit(H, k) and not hit(P, k))   # honest only
    c = sum(1 for k in keys if hit(P, k) and not hit(H, k))   # old only
    both = sum(1 for k in keys if hit(H, k) and hit(P, k))
    nei = len(keys) - b - c - both
    n = b + c
    if n == 0: return b, c, both, nei, 1.0
    lo = min(b, c)
    p = 2.0 * sum(math.comb(n, i) for i in range(lo + 1)) / (2 ** n)
    return b, c, both, nei, min(1.0, p)

for label, keys in (("S", S), ("none", NONE)):
    b, c, both, nei, p = mcnemar(keys)
    print(f"paired {label:>5}: n={len(keys)} both={both} honest_only={b} old_only={c} neither={nei} exact_p={p:.3g}")

# ---- paired bootstrap on the separation DELTA ---------------------------
rng = random.Random(20260830)
def sep(arm, sk, nk):
    return 100.0*sum(hit(arm,k) for k in sk)/len(sk) - 100.0*sum(hit(arm,k) for k in nk)/len(nk)
obs = sep(H, S, NONE) - sep(P, S, NONE)
draws = []
for _ in range(20000):
    sk = [S[rng.randrange(len(S))] for _ in range(len(S))]
    nk = [NONE[rng.randrange(len(NONE))] for _ in range(len(NONE))]
    draws.append(sep(H, sk, nk) - sep(P, sk, nk))
draws.sort()
lo, hi = draws[int(0.025*len(draws))], draws[int(0.975*len(draws))-1]
print(f"separation delta (honest - old): {obs:+.2f} pts, 95% [{lo:+.2f}, {hi:+.2f}]  straddles_zero={lo<0<hi}")

# ---- by entry minute, my own bucketing ----------------------------------
def bucket(m):
    if m < 585: return "0930-0945"
    if m < 615: return "0945-1015"
    return "1015-1100"
print("\nby engine fire minute (denominator = all S / all none):")
for name, arm in (("honest", H), ("published", P)):
    for lab, keys in (("S", S), ("none", NONE)):
        cnt = Counter()
        for k in keys:
            bs = {bucket(e["min"]) for e in arm["days"][k]["entries"]}
            for b in bs: cnt[b] += 1
        print(f"  {name:>10} {lab:>5}: " + "  ".join(
            f"{b} {cnt[b]}/{len(keys)} = {100.0*cnt[b]/len(keys):.1f}%"
            for b in ("0930-0945", "0945-1015", "1015-1100")))

# ---- legacy ladder on S hits -------------------------------------------
print("\nlegacy grade mix on entries taken on his S days:")
for name, arm in (("honest", H), ("published", P)):
    c = Counter(e["legacy_grade"] for k in S for e in arm["days"][k]["entries"])
    print("  ", name, dict(sorted(c.items())))
