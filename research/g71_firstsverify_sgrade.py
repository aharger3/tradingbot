"""G7.1 adversarial verify of the `firsts` sgrade-S claim.

Re-derives sgrade S vs non-S on research/bt2y_trades.json with (a) the prior
agent's own row filter, (b) the traded-only book, (c) a day-clustered bootstrap
SE, (d) a setup/slot-mix decomposition. Writes nothing.
"""
import json, random, statistics as st
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
book = json.loads((ROOT / "research/bt2y_trades.json").read_text(encoding="utf-8"))
T = book["trades"]
print("meta:", {k: book["meta"][k] for k in ("signals", "traded", "halted", "loss_halt", "sessions")})

sets = {
    "prior-agent counted (fired+traded OR halted)":
        [r for r in T if (r["status"] == "fired" and r["traded"]) or r["status"] == "halted"],
    "traded only (the money book)":
        [r for r in T if r["status"] == "fired" and r["traded"]],
    "halted only (never traded)":
        [r for r in T if r["status"] == "halted"],
}

def naive(rows):
    s = [r["r"] for r in rows if r["sgrade"] == "S"]
    n = [r["r"] for r in rows if r["sgrade"] != "S"]
    d = st.fmean(s) - st.fmean(n)
    se = (st.pvariance(s)/len(s) + st.pvariance(n)/len(n)) ** 0.5
    return len(s), len(n), st.fmean(s), st.fmean(n), d, se

def clustered(rows, key, B=4000, seed=7):
    """Cluster bootstrap: resample whole clusters, recompute S - nonS."""
    rnd = random.Random(seed)
    cl = defaultdict(list)
    for r in rows:
        cl[key(r)].append(r)
    ks = list(cl)
    out = []
    for _ in range(B):
        samp = [x for k in (rnd.choice(ks) for _ in ks) for x in cl[k]]
        s = [r["r"] for r in samp if r["sgrade"] == "S"]
        n = [r["r"] for r in samp if r["sgrade"] != "S"]
        if s and n:
            out.append(st.fmean(s) - st.fmean(n))
    out.sort()
    return st.fmean(out), st.pstdev(out), out[int(.025*len(out))], out[int(.975*len(out))]

for label, rows in sets.items():
    ns, nn, ms, mn, d, se = naive(rows)
    print("\n== %s  N=%d" % (label, len(rows)))
    print("   S n=%d %+0.4fR | non-S n=%d %+0.4fR | diff %+0.4f  naive-se %0.4f  t %+0.2f"
          % (ns, ms, nn, mn, d, se, d/se))
    for ck, cn in (("day", lambda r: r["day"]), ("sym", lambda r: r["sym"]),
                   ("sym-day", lambda r: (r["sym"], r["day"]))):
        m, s, lo, hi = clustered(rows, cn)
        print("   cluster-by-%-8s boot-mean %+0.4f  se %0.4f  95%% [%+0.4f, %+0.4f]  %s"
              % (ck, m, s, lo, hi, "SIG" if (lo > 0) == (hi > 0) else "NOT SIG"))

rows = sets["prior-agent counted (fired+traded OR halted)"]
print("\n-- sgrade x setup mix (prior-agent counted) --")
tot = Counter(r["setup"] for r in rows)
for g in ("S", "A", "C"):
    c = Counter(r["setup"] for r in rows if r["sgrade"] == g)
    print("  %s: %s" % (g, {k: "%d (%.0f%%)" % (v, 100*v/sum(c.values())) for k, v in c.most_common()}))
print("  ALL:", dict(tot))

print("\n-- S vs non-S WITHIN each setup (controls the mix) --")
for su in tot:
    sub = [r for r in rows if r["setup"] == su]
    s = [r["r"] for r in sub if r["sgrade"] == "S"]
    n = [r["r"] for r in sub if r["sgrade"] != "S"]
    if len(s) < 15 or len(n) < 15:
        print("  %-22s n_S=%d n_nonS=%d  (too thin)" % (su, len(s), len(n))); continue
    d = st.fmean(s) - st.fmean(n)
    se = (st.pvariance(s)/len(s) + st.pvariance(n)/len(n)) ** 0.5
    print("  %-22s S n=%3d %+0.4f | nonS n=%4d %+0.4f | diff %+0.4f se %0.4f t %+0.2f"
          % (su, len(s), st.fmean(s), len(n), st.fmean(n), d, se, d/se))

print("\n-- outcome mix: is the effect payoff size or truncation? --")
for g in ("S", "A", "C"):
    v = [r for r in rows if r["sgrade"] == g]
    oc = Counter(r["out"] for r in v)
    w = [r["r"] for r in v if r["out"] == "win"]
    l = [r["r"] for r in v if r["out"] == "loss"]
    print("  %s n=%4d  out=%s  meanWin %+0.3f  meanLoss %+0.3f  maxR %+0.2f  top5 %s"
          % (g, len(v), dict(oc), st.fmean(w), st.fmean(l),
             max(r["r"] for r in v),
             [round(x, 2) for x in sorted((r["r"] for r in v), reverse=True)[:5]]))

print("\n-- trim the top 1% of winners in each arm (fat-tail sensitivity) --")
def trimmed(rows, frac=0.01):
    s = sorted(r["r"] for r in rows if r["sgrade"] == "S")
    n = sorted(r["r"] for r in rows if r["sgrade"] != "S")
    ks, kn = int(len(s)*frac), int(len(n)*frac)
    s2, n2 = s[:len(s)-ks], n[:len(n)-kn]
    return st.fmean(s2) - st.fmean(n2), ks, kn
for f in (0.005, 0.01, 0.02, 0.05):
    d, ks, kn = trimmed(rows, f)
    print("  trim %.1f%% top: diff %+0.4f  (dropped %d S, %d non-S)" % (f*100, d, ks, kn))

# ---- alternate S proxies available in the same book -------------------------
print("\n== alternate S proxies (same rows, prior-agent counted set) ==")
rows = sets["prior-agent counted (fired+traded OR halted)"]
def arm(pred, label):
    a = [r["r"] for r in rows if pred(r)]
    b = [r["r"] for r in rows if not pred(r)]
    d = st.fmean(a) - st.fmean(b)
    se = (st.pvariance(a)/len(a) + st.pvariance(b)/len(b)) ** 0.5
    m, s, lo, hi = clustered(rows, lambda r: r["day"]) if False else (0,0,0,0)
    print("  %-34s in n=%4d %+0.4f | out n=%4d %+0.4f | diff %+0.4f se %0.4f t %+0.2f"
          % (label, len(a), st.fmean(a), len(b), st.fmean(b), d, se, d/se))

arm(lambda r: r["sgrade"] == "S", "sgrade S (9-var, chase ON)")
# 8-variable ladder: drop R22 chase, which only landed 2026-08-29
def net8(r):
    t = [x for x in r["downgrades"] if x != "chase"]
    return len(t) - (1 if r["confluence"] == "yes" else 0)
arm(lambda r: net8(r) <= 0, "sgrade S (8-var, chase OFF)")
arm(lambda r: len(r["downgrades"]) == 0, "zero downgrades tripped (raw)")
arm(lambda r: "no_displacement" not in r["downgrades"], "displacement present (S_GATE stand-in)")
arm(lambda r: r["confluence"] == "yes", "confluence +1")
print("\n  8-var vs 9-var S membership: %s" % Counter(
    (r["sgrade"] == "S", net8(r) <= 0) for r in rows))
