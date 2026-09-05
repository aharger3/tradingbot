"""W9 referee (scoring) -- independent recompute of the g211 eye-test.

Does not import g211_eye_test.py. Recomputes precision/recall from the reads JSONs,
re-derives the deck's own S base rate, runs an exact one-sided binomial test and a
label-permutation test against that rate, re-runs the bootstrap at a different seed and
draw count, measures the leak channel (cut time / candle count vs his grade), measures how
much each reader's S-calls track the leak, and measures the test-retest agreement between
the two reader passes committed under the same name (50d3f7d0 vs e326b1cd).

Usage: python research/g211_referee_score.py
"""
import json, random, subprocess
from collections import Counter
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parent
cards = json.load(open(ROOT / "g210_cards" / "index.json", encoding="utf-8"))
his = {c["card_id"]: c["his_grade"] for c in cards}
cut = {c["card_id"]: c["cut_bar_time"] for c in cards}
reads = {m: {r["card_id"]: r for r in json.load(open(ROOT / f"g211_reads_{m}.json", encoding="utf-8"))}
         for m in ("haiku", "sonnet")}

n = len(his)
S = sum(1 for g in his.values() if g == "S")
base = S / n
print(f"deck: n={n}, his S={S}, deck S base rate={base:.3f}")
print("his grade distribution:", Counter(his.values()))


def pr(model):
    tp = sum(1 for c in his if his[c] == "S" and model.get(c, {}).get("grade") == "S")
    fp = sum(1 for c in his if his[c] != "S" and model.get(c, {}).get("grade") == "S")
    fn = sum(1 for c in his if his[c] == "S" and model.get(c, {}).get("grade") != "S")
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return tp, fp, fn, p, r, f1


def binom_ge(k, m, p):
    """P(X >= k) for X~Bin(m,p) -- exact one-sided."""
    return sum(comb(m, i) * p**i * (1 - p)**(m - i) for i in range(k, m + 1))


def boot(model, seed, draws):
    rng = random.Random(seed)
    ids = list(his)
    out = []
    for _ in range(draws):
        s = [ids[rng.randrange(n)] for _ in range(n)]
        tp = fp = 0
        for c in s:
            if model.get(c, {}).get("grade") == "S":
                if his[c] == "S":
                    tp += 1
                else:
                    fp += 1
        if tp + fp:
            out.append(tp / (tp + fp))
    out.sort()
    return out[int(.025 * len(out))], out[min(int(.975 * len(out)), len(out) - 1)]


def perm_p(model, seed=7, draws=20000):
    """Permute his labels; how often does a random labelling give >= this precision?"""
    tp, fp, fn, p, r, f1 = pr(model)
    k = tp + fp
    if k == 0:
        return float("nan")
    rng = random.Random(seed)
    labels = [g == "S" for g in his.values()]
    hit = 0
    for _ in range(draws):
        rng.shuffle(labels)
        perm = dict(zip(his.keys(), labels))
        t = sum(1 for c in his if perm[c] and model.get(c, {}).get("grade") == "S")
        if t / k >= p - 1e-12:
            hit += 1
    return hit / draws


print("\n=== independent precision / recall / F1, S vs not-S ===")
print(f"{'reader':<14}{'S-calls':>8}{'TP':>5}{'FP':>5}{'FN':>5}{'prec':>8}{'rec':>8}{'F1':>8}"
      f"{'p(binom vs 34%)':>18}{'p(permutation)':>16}")
for m in ("haiku", "sonnet"):
    tp, fp, fn, p, r, f1 = pr(reads[m])
    pb = binom_ge(tp, tp + fp, base)
    print(f"{m:<14}{tp+fp:>8}{tp:>5}{fp:>5}{fn:>5}{p:>8.3f}{r:>8.3f}{f1:>8.3f}{pb:>18.3f}{perm_p(reads[m]):>16.3f}")
always = {c: {"grade": "S"} for c in his}
tp, fp, fn, p, r, f1 = pr(always)
print(f"{'always-S':<14}{tp+fp:>8}{tp:>5}{fp:>5}{fn:>5}{p:>8.3f}{r:>8.3f}{f1:>8.3f}")

print("\n=== bootstrap on precision, my seed/draws vs the committed run ===")
for m in ("haiku", "sonnet"):
    print(f"  {m}: seed 11 / 20000 draws -> [{boot(reads[m],11,20000)[0]:.3f}, {boot(reads[m],11,20000)[1]:.3f}]"
          f"   seed 99 / 50000 -> [{boot(reads[m],99,50000)[0]:.3f}, {boot(reads[m],99,50000)[1]:.3f}]")

print("\n=== leak channel: cut time vs his grade ===")
tab = Counter((his[c], "10:00" if cut[c] == "10:00:00" else "not 10:00") for c in his)
for k, v in sorted(tab.items()):
    print("   ", k, v)
lk = {c: {"grade": "S" if cut[c] != "10:00:00" else "none"} for c in his}
tp, fp, fn, p, r, f1 = pr(lk)
print(f'   trivial reader "S iff cut != 10:00": prec={p:.3f} rec={r:.3f} (TP={tp} FP={fp} FN={fn})')

print("\n=== did the readers ride the leak? S-calls on leaked (cut!=10:00) cards ===")
leaked = [c for c in his if cut[c] != "10:00:00"]
for m in ("haiku", "sonnet"):
    sc = [c for c in his if reads[m].get(c, {}).get("grade") == "S"]
    on = sum(1 for c in sc if c in leaked)
    exp = len(sc) * len(leaked) / n
    print(f"   {m}: {on}/{len(sc)} S-calls on leaked cards (chance expectation {exp:.1f})")

print("\n=== test-retest: the two reader passes committed under the same filename ===")
for m in ("haiku", "sonnet"):
    old = {r["card_id"]: r["grade"] for r in json.loads(subprocess.run(
        ["git", "show", f"50d3f7d0:research/g211_reads_{m}.json"],
        capture_output=True, text=True, cwd=ROOT.parent).stdout)}
    new = {c: reads[m][c]["grade"] for c in reads[m]}
    same4 = sum(1 for c in old if new.get(c) == old[c])
    same2 = sum(1 for c in old if (new.get(c) == "S") == (old[c] == "S"))
    oldS = {c: {"grade": old[c]} for c in old}
    _, _, _, po, ro, _ = pr(oldS)
    print(f"   {m}: exact 4-way agreement run1 vs run2 = {same4}/{len(old)}; S/not-S = {same2}/{len(old)}")
    print(f"        run1 precision={po:.3f} recall={ro:.3f}   run2 precision={pr(reads[m])[3]:.3f} recall={pr(reads[m])[4]:.3f}")
