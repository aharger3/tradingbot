"""Empirical reclaim-distance d on the 123 fired 84% rows, to test whether the
rr_ok cap is BINDING (truncation at exactly 0.2R) or merely latent. Read-only."""
import json, re, collections, statistics as st
T = json.load(open('research/bt2y_trades.json', encoding='utf-8'))['trades']
r84 = [r for r in T if r['setup'] == 'reentry_84_rule']
print("sample reason:", r84[0]['reason'])
print({k: r84[0][k] for k in ('entry', 'stop', 'target', 'cls', 'dir', 'status')})
ds = []
for r in r84:
    m = re.search(r"\$([0-9]+\.?[0-9]*)", r['reason'] or "")
    if not m or r.get('cls') is None or r.get('target') is None:
        continue
    pe = float(m.group(1))                 # prior (original) entry price
    R = abs(r['target'] - pe) / 2.0        # original R, since target = pe +- 2R
    if R <= 0:
        continue
    d = (r['cls'] - pe) / R if r['dir'] == 'call' else (pe - r['cls']) / R
    ds.append(d)
print("n=%d  min %.4f  median %.4f  max %.4f" % (len(ds), min(ds), st.median(ds), max(ds)))
print("bucketed:", collections.Counter(round(d, 1) for d in ds).most_common())
print("frac d > 0.2000R : %.4f" % (sum(1 for d in ds if d > 0.2 + 1e-9) / len(ds)))
print("frac d in [0.15,0.20] : %.4f" % (sum(1 for d in ds if 0.15 <= d <= 0.2 + 1e-9) / len(ds)))
