"""Adversarial re-measure of the `levels` runner-target claim.

Claim: median runner-leg RR 3.275R shipped vs 5.758R on his six; 24.1% of
shipped runner targets sit below 2.0R; median paired lift +1.691R, on the
2,540 traded rows of research/g71_runner_probe.json.
"""
import json, statistics as st
from collections import defaultdict

P = json.load(open("research/g71_runner_probe.json"))
B = json.load(open("research/g71_arm_base.json"))
C = json.load(open("research/bt2y_trades.json"))

print("probe rows            ", len(P))
print("arm_base meta traded  ", B["meta"]["traded"], "signals", B["meta"]["signals"])
print("bt2y   meta traded    ", C["meta"]["traded"], "signals", C["meta"]["signals"])

bt = [r for r in B["trades"] if r["traded"]]
ct = [r for r in C["trades"] if r["traded"]]
print("arm_base traded rows  ", len(bt))
print("bt2y     traded rows  ", len(ct))
rv1 = [round(r["r"], 6) for r in bt]
rv2 = [round(r["r"], 6) for r in ct]
print("R vectors identical   ", rv1 == rv2, "| sum", round(sum(rv1), 3), round(sum(rv2), 3))

KEY = lambda r: (r["sym"], r["day"], r["et"], r["dir"])
pk = defaultdict(list)
for r in P:
    pk[KEY(r)].append(r)
print("probe uniq keys       ", len(pk), "| dup keys", sum(1 for v in pk.values() if len(v) > 1))

# --- join, the way the claim's 2,540 was most likely produced -------------
naive = []          # every probe row whose key is a traded key  (inflates)
onece = []          # one probe row per traded book row          (correct)
miss = 0
for r in bt:
    v = pk.get(KEY(r))
    if not v:
        miss += 1
        continue
    naive += v
    onece.append(v[0])
print("traded rows w/o probe ", miss)
print("naive join rows       ", len(naive))
print("one-per-trade rows    ", len(onece))

def med(xs):
    return round(st.median(xs), 4) if xs else None

def report(tag, rows):
    sh = [r["rr_shipped"] for r in rows if r["rr_shipped"] is not None]
    sx = [r["rr_six"] for r in rows if r["rr_six"] is not None]
    # honest six: 2R fallback when none of his six lies beyond the scale point,
    # which is what the six_target arm actually books.
    sx_fb = [(r["rr_six"] if r["rr_six"] is not None else 2.0) for r in rows
             if r["rr_shipped"] is not None]
    print("\n== %s  n=%d ==" % (tag, len(rows)))
    print("  median rr_shipped        ", med(sh), " mean", round(st.fmean(sh), 4))
    print("  median rr_six (six!=None)", med(sx), " n", len(sx))
    print("  median rr_six w/ 2R fallb", med(sx_fb), " mean", round(st.fmean(sx_fb), 4))
    print("  shipped_is_whole share   ", round(100 * sum(r["shipped_is_whole"] for r in rows) / len(rows), 1), "%")
    print("  six_is_none share        ", round(100 * sum(r["six_is_none"] for r in rows) / len(rows), 1), "%")
    print("  shipped rr < 2.0R        ", round(100 * sum(1 for x in sh if x < 2.0) / len(sh), 1), "%")
    print("  six(fb) rr < 2.0R        ", round(100 * sum(1 for x in sx_fb if x < 2.0) / len(sx_fb), 1), "%")
    pair_c = [r["rr_six"] - r["rr_shipped"] for r in rows
              if r["rr_six"] is not None and r["rr_shipped"] is not None]
    pair_a = [((r["rr_six"] if r["rr_six"] is not None else 2.0) - r["rr_shipped"])
              for r in rows if r["rr_shipped"] is not None]
    print("  paired lift, six!=None   ", med(pair_c), " n", len(pair_c))
    print("  paired lift, ALL (2R fb) ", med(pair_a), " n", len(pair_a),
          " mean", round(st.fmean(pair_a), 4))
    print("  rows where six is WORSE  ", round(100 * sum(1 for x in pair_a if x < 0) / len(pair_a), 1), "%")

report("naive key-join (traded)", naive)
report("one-probe-row-per-trade", onece)
report("ALL probe rows (untraded incl.)", P)

# ---------------------------------------------------------------------------
# Join-variant matrix: no variant reproduces the claim's n=2,540 /
# medSh=3.275 / medSix=5.758 / <2R=24.1% / lift=+1.691.
# ---------------------------------------------------------------------------
def variants():
    K4 = lambda r: (r["sym"], r["day"], r["et"], r["dir"])
    K3 = lambda r: (r["sym"], r["day"], r["et"])
    K5 = lambda r: (r["sym"], r["day"], r["et"], r["dir"], round(r["entry"], 4))
    def line(rows, tag):
        sh = [r["rr_shipped"] for r in rows if r["rr_shipped"] is not None]
        sx = [r["rr_six"] for r in rows if r["rr_six"] is not None]
        pr = [r["rr_six"] - r["rr_shipped"] for r in rows
              if r["rr_six"] is not None and r["rr_shipped"] is not None]
        print("%-34s n=%-5d medSh=%.4f medSix=%.4f <2R=%.1f%% lift=%.4f" % (
            tag, len(rows), st.median(sh), st.median(sx),
            100 * sum(1 for x in sh if x < 2) / len(sh), st.median(pr)))
    print()
    for nm, K in (("K4", K4), ("K3", K3), ("K5", K5)):
        pk2 = defaultdict(list)
        for r in P:
            pk2[K(r)].append(r)
        tk = {K(r) for r in bt}
        line([r for r in P if K(r) in tk], "probe rows w/ traded key " + nm)
        line([pk2[k][0] for k in tk if k in pk2], "first probe per traded key " + nm)
        line([pk2[k][-1] for k in tk if k in pk2], "last probe per traded key " + nm)


variants()
