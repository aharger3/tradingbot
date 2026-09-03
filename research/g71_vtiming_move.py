"""ADVERSARIAL VERIFY of G71/timing's look-ahead claim.

Independent of research/g71_timing.py: does NOT use its _MATCH cache, its
_Src params file, or its build(). Bars come straight off data_archive via
polygon_feed; the entry bar is located by the book's own `entry_i`/`et`,
cross-checked against the timestamp.

Q1  entry-bar signed move in R  -> reproduce +0.7974 / 93.4% ?
Q2  same, sliced by setup       -> does the mechanism track the k=-1 lift ?
Q3  a from-scratch arm-T k-surface with a SIMPLE control manager (stop on
    close floored at -1.25R via stop_rule.stop_fill_price, flat 2R target)
    -> does the k=-1 peak survive a manager that shares no code with
    _ladder_bar, and does it equal the bar move ?
Q4  the decisive conditional: on trades whose entry bar moved AGAINST the
    trade, does k=-1 still pay ?
"""
from __future__ import annotations
import json, os, statistics, sys, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import polygon_feed as pf
import stop_rule

BOOK = os.path.join(HERE, "bt2y_trades.json")
book = json.load(open(BOOK, encoding="utf-8"))
rows = [r for r in book["trades"] if r["traded"]]
print("book meta traded=%s signals=%s generated=%s" %
      (book["meta"]["traded"], book["meta"]["signals"], book["meta"]["generated"]))
print("traded rows loaded: %d" % len(rows))

_C = {}
def rth_of(sym, day):
    k = (sym, day)
    if k not in _C:
        try:
            _C[k] = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            _C[k] = []
    return _C[k]

def boot(xs, n=2000, seed=7):
    rnd = random.Random(seed); m = len(xs)
    s = sorted(statistics.fmean(rnd.choices(xs, k=m)) for _ in range(n))
    return s[int(.025*n)], s[int(.975*n)]

# ---------------- Q1/Q2 ----------------
movs, by_setup, ts_bad = [], defaultdict(list), 0
per = {}
for n, r in enumerate(rows):
    rth = rth_of(r["sym"], r["day"])
    i = r["entry_i"]
    if not rth or i < 1 or i >= len(rth):
        continue
    if str(rth[i].timestamp)[:5] != r["et"]:
        ts_bad += 1
        continue
    risk = abs(r["entry"] - r["stop"])
    if risk <= 0:
        continue
    sgn = 1 if r["dir"] == "call" else -1
    m = sgn * (rth[i].close - rth[i-1].close) / risk
    movs.append(m); by_setup[r["setup"]].append(m); per[n] = m

print("\n== Q1 entry-bar signed move in R (independent) ==")
lo, hi = boot(movs)
print("  n=%d  mean %+.4f  median %+.4f  95%% boot [%+.4f, %+.4f]"
      % (len(movs), statistics.fmean(movs), statistics.median(movs), lo, hi))
fav = sum(1 for m in movs if m > 0)
print("  favourable %d/%d = %.1f%%   timestamp mismatches skipped: %d"
      % (fav, len(movs), 100*fav/len(movs), ts_bad))
print("\n== Q2 by setup ==")
for s, v in sorted(by_setup.items(), key=lambda kv: -len(kv[1])):
    print("  %-18s n=%4d  mean move %+.4f R  fav %.1f%%"
          % (s, len(v), statistics.fmean(v), 100*sum(1 for x in v if x > 0)/len(v)))

# ---------------- Q3 simple control manager ----------------
# entry at bar j close-translated price; stop/target translated with it (arm T).
# Manage bar by bar from j+1: stop triggers on CLOSE beyond stop, fill at that
# close, floored at -1.25R (stop_rule.stop_fill_price). Target on touch of high/
# low. EOD -> mark to last close. No scale rung, no BE: a control, not a clone.
def run(r, rth, k):
    i0 = r["entry_i"]; j = i0 + k
    if j < 5 or j >= len(rth) - 1 or i0 >= len(rth):
        return None
    long = r["dir"] == "call"
    d = rth[j].close - rth[i0].close
    e, s, t = r["entry"] + d, r["stop"] + d, r["target"] + d
    risk = abs(e - s)
    if risk <= 0:
        return None
    for c in rth[j+1:]:
        hit_stop = (c.close <= s) if long else (c.close >= s)
        hit_tgt = (c.high >= t) if long else (c.low <= t)
        if hit_stop and hit_tgt:          # pessimistic tie -> stop
            hit_tgt = False
        if hit_stop:
            fill = stop_rule.stop_fill_price(e, s, c.close, long)
            return (fill - e)/risk if long else (e - fill)/risk
        if hit_tgt:
            return (t - e)/risk if long else (e - t)/risk
    c = rth[-1]
    return (c.close - e)/risk if long else (e - c.close)/risk

SHIFTS = (-2, -1, 0, 1, 2)
res = {k: {} for k in SHIFTS}
for n, r in enumerate(rows):
    rth = rth_of(r["sym"], r["day"])
    if not rth or n not in per:
        continue
    vals = {k: run(r, rth, k) for k in SHIFTS}
    if any(v is None for v in vals.values()):
        continue
    for k in SHIFTS:
        res[k][n] = vals[k]
common = sorted(set.intersection(*[set(res[k]) for k in SHIFTS]))
print("\n== Q3 independent control-manager arm-T surface, n=%d ==" % len(common))
base = [res[0][n] for n in common]
print("  k    meanR     WR%%      delta vs k=0    95%% boot on delta")
for k in SHIFTS:
    v = [res[k][n] for n in common]
    dl = [res[k][n] - res[0][n] for n in common]
    lo, hi = boot(dl) if k else (0.0, 0.0)
    print("  %+d  %+.4f  %5.2f    %+.4f        [%+.4f, %+.4f]"
          % (k, statistics.fmean(v), 100*sum(1 for x in v if x > 0)/len(v),
             statistics.fmean(dl), lo, hi))

# ---------------- Q4 the decisive conditional ----------------
print("\n== Q4 k=-1 delta conditioned on the entry bar's own move ==")
d1 = {n: res[-1][n] - res[0][n] for n in common}
mv = {n: per[n] for n in common}
res_r = [d1[n] - mv[n] for n in common]
lo, hi = boot(res_r)
print("  mean(delta_-1) %+.4f   mean(move) %+.4f   residual %+.4f  95%% [%+.4f,%+.4f]"
      % (statistics.fmean([d1[n] for n in common]),
         statistics.fmean([mv[n] for n in common]),
         statistics.fmean(res_r), lo, hi))
for lab, sel in (("move > 0", lambda n: mv[n] > 0), ("move <= 0", lambda n: mv[n] <= 0)):
    g = [n for n in common if sel(n)]
    if not g:
        continue
    dd = [d1[n] for n in g]; l2, h2 = boot(dd)
    print("  %-10s n=%4d  mean move %+.4f  k=-1 delta %+.4f  95%% [%+.4f,%+.4f]"
          % (lab, len(g), statistics.fmean([mv[n] for n in g]),
             statistics.fmean(dd), l2, h2))
# per-setup delta vs move
print("\n  per setup: k=-1 delta vs entry-bar move")
bs = defaultdict(list)
for n in common:
    bs[rows[n]["setup"]].append((d1[n], mv[n]))
for s, v in sorted(bs.items(), key=lambda kv: -len(kv[1])):
    print("    %-18s n=%4d  delta %+.4f  move %+.4f  resid %+.4f"
          % (s, len(v), statistics.fmean(a for a, _ in v),
             statistics.fmean(b for _, b in v),
             statistics.fmean(a-b for a, b in v)))
try:
    cor = statistics.correlation([d1[n] for n in common], [mv[n] for n in common])
    print("\n  pearson r(delta_-1, move) = %.4f" % cor)
except Exception as e:
    print("  corr failed", e)
