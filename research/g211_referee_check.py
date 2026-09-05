"""W9 referee: independent recompute of the g211 eye-test, leakage probe, corrected null."""
import json, random, math
from collections import Counter

idx = json.load(open("research/g210_cards/index.json", encoding="utf-8"))
his = {c["card_id"]: c["his_grade"] for c in idx}
cut = {c["card_id"]: c["cut_bar_time"] for c in idx}
N = len(his); NS = sum(1 for g in his.values() if g == "S")
print(f"cards={N} S={NS} base_rate={NS/N:.3f}")

def load(p):
    rows = json.load(open(p, encoding="utf-8"))
    ids = [r["card_id"] for r in rows]
    print(f"{p}: rows={len(rows)} unique={len(set(ids))} missing={len(set(his)-set(ids))} extra={len(set(ids)-set(his))} grades={dict(Counter(r.get('grade') for r in rows))}")
    return {r["card_id"]: r for r in rows}

models = {"haiku": load("research/g211_reads_haiku.json"), "sonnet": load("research/g211_reads_sonnet.json")}

# --- LEAKAGE: does the cut time (printed in the PNG title) determine his grade?
tp = sum(1 for cid in his if cut[cid] != "10:00:00" and his[cid] == "S")
fp = sum(1 for cid in his if cut[cid] != "10:00:00" and his[cid] != "S")
fn = sum(1 for cid in his if cut[cid] == "10:00:00" and his[cid] == "S")
print(f"\nLEAKAGE cut!=10:00 -> S :  TP={tp} FP={fp} FN={fn}  precision={tp/(tp+fp):.3f} recall={tp/(tp+fn):.3f}")

def binom_p_ge(k, n, p):  # one-sided P(X>=k)
    return sum(math.comb(n, i) * p**i * (1-p)**(n-i) for i in range(k, n+1))

rng = random.Random(20260905)
for name, m in models.items():
    calls = [cid for cid in his if m.get(cid, {}).get("grade") == "S"]
    tp = sum(1 for cid in calls if his[cid] == "S")
    nc = len(calls)
    prec = tp/nc; rec = tp/NS
    f1 = 2*prec*rec/(prec+rec) if prec+rec else 0
    # bootstrap over cards
    ids = list(his); draws = []
    for _ in range(20000):
        s = [ids[rng.randrange(N)] for _ in range(N)]
        a = sum(1 for c in s if m.get(c, {}).get("grade") == "S" and his[c] == "S")
        b = sum(1 for c in s if m.get(c, {}).get("grade") == "S")
        if b: draws.append(a/b)
    draws.sort()
    lo, hi = draws[int(.025*len(draws))], draws[int(.975*len(draws))]
    p_vs_base = binom_p_ge(tp, nc, NS/N)
    # does the model exploit the cut-time channel?
    ex = sum(1 for cid in calls if cut[cid] != "10:00:00")
    print(f"\n{name}: S-calls={nc} TP={tp} precision={prec:.3f} recall={rec:.3f} F1={f1:.3f}")
    print(f"  bootstrap95=[{lo:.3f},{hi:.3f}] (20k)   one-sided binomial vs deck base {NS/N:.3f}: p={p_vs_base:.3f}")
    print(f"  S-calls landing on a leaked (cut!=10:00) card: {ex}/{nc} (perfect exploitation would be {nc}/{nc} and precision 1.000)")

pa, ra = NS/N, 1.0
print(f"\ntrivial 'always S' reader: precision={pa:.3f} recall=1.000 F1={2*pa/(1+pa):.3f}")
