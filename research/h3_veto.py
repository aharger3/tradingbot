#!/usr/bin/env python3
"""H3 veto analysis (omen-3.4 / T6) -- does a veto in front of a wall pay for itself?

Pure analysis over the existing engine trade population (backtest_charts_12mo.json,
974 records). No new data, no human input.

DEFINITION (veto): at entry, if the nearest node of weight >= 3.0 in the trade's
direction sits closer than 1.0R, the trade is vetoed -- the best realistic outcome
is under +1R against -1R of risk. Partition the whole population into vetoed and
non-vetoed; primary endpoint is mean realized R (Welch t on day-clustered means +
day-block bootstrap CI on the difference). Sweep the threshold at 0.8/1.0/1.2/1.5R.

NODE SET -- T3 (research/levels.py) is ABSENT on this checkout (same blocker as
T4/target_autopsy and H5/frontrun): the spec's "node of weight >= 3.0" is not
computable in its full confluence form (round numbers + HTF levels + pivots,
weighted). The faithful no-new-data node set is therefore the engine's OWN S/R
level set, which is the only significance-filtered "wall" set present in the data:
each record carries levels = {PDH, PDL, PMH, PML, ORH, ORL} (prior-day / prior-
session H/L and opening-range H/L) -- exactly the levels the engine grades and
caps trades on (signal_runner._grade_for_levels: "levels in the trade direction";
reason text "level $X blocks 2R path"). In the absence of T3's weights, the
weight>=3.0 qualifier collapses to "is an engine S/R level"; every engine level is
treated as a qualifying wall. This is the honest proxy, documented not hidden.

Why not round numbers (H5's weight>=3 = whole dollar)? Because for the VETO the
sanity check fails: a whole-dollar node sits ahead of almost every entry within
1R, giving a 53-76% veto rate -- over 40% at every threshold, i.e. "measuring
something other than what it claims" (every dollar is not a wall). The engine S/R
set gives 18-34%, inside the 5-40% band and smoothly degrading -- the signature of
a real effect. A coarse round-number ($10/$50/$100) variant is reported as a
robustness check.
"""
import json, math, random, statistics
from collections import defaultdict, Counter

TICK = 0.01

def load(): return json.load(open('backtest_charts_12mo.json'))

def risk(r): return abs(r['entry'] - r['stop'])

def realized_r(r):
    rk = risk(r)
    if rk <= 0: return 0.0
    if r['direction'] == 'call': return (r['exit_price'] - r['entry']) / rk
    return (r['entry'] - r['exit_price']) / rk

def atr_1m(candles, entry_i):
    """Mean true range of 1-min bars over the pre-entry window (fallback: all)."""
    if not candles: return 0.0
    end = entry_i if (entry_i is not None and entry_i >= 2) else len(candles)
    end = max(min(end, len(candles)), 2)
    trs = []
    for i in range(1, end):
        c = candles[i]; pc = candles[i-1]['c']
        trs.append(max(c['h'] - c['l'], abs(c['h'] - pc), abs(c['l'] - pc)))
    if not trs:
        trs = [c['h'] - c['l'] for c in candles if c['h'] - c['l'] > 0]
    return sum(trs) / len(trs) if trs else 0.0

# ---- node sets ----
def engine_levels(r):
    L = r.get('levels') or {}
    return [float(v) for v in L.values() if v is not None]

def coarse_round_nodes(r):
    """$10/$50/$100 multiples near entry -- round-number robustness variant."""
    e = r['entry']; out = set()
    for base in (10, 50, 100):
        b = base * round(e / base)
        for d in range(-2, 3):
            out.add(float(b + d * base))
    return list(out)

def nearest_in_dir(nodes, entry, direction):
    """Nearest qualifying node strictly in the trade's direction (ahead of entry)."""
    if direction == 'call':
        ahead = [n for n in nodes if n > entry + 1e-9]
    else:
        ahead = [n for n in nodes if n < entry - 1e-9]
    if not ahead: return None
    return min(ahead, key=lambda n: abs(n - entry))

# ---- stats: Welch t (manual, t-dist p via regularized incomplete beta) ----
def _betacf(a, b, x):
    MAXIT = 300; EPS = 3e-16; FPMIN = 1e-300
    qab = a + b; qap = a + 1; qam = a - 1
    c = 1.0; d = 1 - qab * x / qap
    if abs(d) < FPMIN: d = FPMIN
    d = 1.0 / d; h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        if abs(d) < FPMIN: d = FPMIN
        c = 1 + aa / c
        if abs(c) < FPMIN: c = FPMIN
        d = 1.0 / d; h *= c * d
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        if abs(d) < FPMIN: d = FPMIN
        c = 1 + aa / c
        if abs(c) < FPMIN: c = FPMIN
        d = 1.0 / d; de = c * d; h *= de
        if abs(de - 1.0) < EPS: break
    return h

def betai(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    bt = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1 - bt * _betacf(b, a, 1 - x) / b

def welch_t(x, y):
    """Two-sample Welch t-test. Returns (t, df, p_two_sided) or (None,None,None)."""
    n1, n2 = len(x), len(y)
    if n1 < 2 or n2 < 2: return None, None, None
    m1 = statistics.mean(x); m2 = statistics.mean(y)
    v1 = statistics.variance(x); v2 = statistics.variance(y)
    se2 = v1 / n1 + v2 / n2
    if se2 <= 0: return None, None, None
    t = (m1 - m2) / math.sqrt(se2)
    df = se2 * se2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1))
    # two-sided p from t dist: p = I_x(df/2, 1/2), x = df/(df+t^2)
    x = df / (df + t * t)
    p = betai(df / 2.0, 0.5, x)
    return t, df, p

def day_block_bootstrap_diff(by_day, trades_by_day, B=20000, seed=20260805):
    """Resample whole days w/ replacement; recompute mean_R(vetoed)-mean_R(nonvetoed)."""
    rng = random.Random(seed)
    days = sorted(by_day.keys())
    diffs = []
    for _ in range(B):
        samp = [rng.choice(days) for _ in range(len(days))]
        vsum = vcnt = nvsum = nvcnt = 0.0
        for d in samp:
            for (isveto, rr) in trades_by_day[d]:
                if isveto: vsum += rr; vcnt += 1
                else: nvsum += rr; nvcnt += 1
        if vcnt == 0 or nvcnt == 0: continue
        diffs.append(vsum / vcnt - nvsum / nvcnt)
    diffs.sort()
    lo = diffs[int(0.025 * len(diffs))]; hi = diffs[int(0.975 * len(diffs))]
    p_neg = sum(1 for d in diffs if d < 0) / len(diffs)
    p_pos = sum(1 for d in diffs if d > 0) / len(diffs)
    return lo, hi, p_neg, p_pos

def analyze(recs, nodefn, label, thresholds=(0.8, 1.0, 1.2, 1.5)):
    # precompute per-trade invariants
    rows = []
    for r in recs:
        if r['direction'] not in ('call', 'put'): continue
        rk = risk(r)
        if rk <= 0: continue
        nodes = nodefn(r)
        n = nearest_in_dir(nodes, r['entry'], r['direction'])
        dist = abs(n - r['entry']) if n is not None else None
        rows.append({
            'rec': r, 'day': r['day'], 'dir': r['direction'], 'R': rk,
            'rr': realized_r(r), 'node': n, 'dist': dist,
            'atr': atr_1m(r.get('candles') or [], r.get('entry_i')),
            'alert_only': bool(r.get('alert_only')),
        })
    denom = len(rows)
    pop_mean = statistics.mean(r['rr'] for r in rows) if rows else 0.0

    results = {'label': label, 'n_total': denom, 'pop_mean_R': pop_mean, 'sweep': []}
    print(f'\n=== {label}  (N={denom}, pop mean R={pop_mean:.4f}) ===')
    hdr = f'{"T":>4} {"grp":>8} {"n":>5} {"meanR":>7} {"medR":>7} {"win%":>6} {"vetoRate":>8} | {"ATR":>7}'
    print(hdr)
    for T in thresholds:
        for r in rows:
            r['vetoed'] = (r['dist'] is not None) and (r['dist'] < T * r['R'])
        v = [r for r in rows if r['vetoed']]
        nv = [r for r in rows if not r['vetoed']]
        veto_rate = len(v) / denom if denom else 0.0
        def stats(g):
            if not g: return (0, float('nan'), float('nan'), float('nan'))
            meanR = statistics.mean(x['rr'] for x in g)
            medR = statistics.median(x['rr'] for x in g)
            wr = sum(1 for x in g if x['rr'] > 0) / len(g)
            return len(g), meanR, medR, wr
        vn, vm, vmd, vw = stats(v)
        nn, nm, nmd, nw = stats(nv)
        v_atr = statistics.mean(x['atr'] for x in v) if v else float('nan')
        n_atr = statistics.mean(x['atr'] for x in nv) if nv else float('nan')
        diff = vm - nm  # mean realized R: vetoed - non_vetoed
        gain = nm - pop_mean  # population mean lift from removing vetoed

        # day-clustered means for Welch t
        by_day_v = defaultdict(list); by_day_nv = defaultdict(list)
        for r in rows:
            (by_day_v if r['vetoed'] else by_day_nv)[r['day']].append(r['rr'])
        dv = [statistics.mean(vs) for vs in by_day_v.values()]
        dnv = [statistics.mean(vs) for vs in by_day_nv.values()]
        tstat, df, p = welch_t(dv, dnv)

        # day-block bootstrap on the diff
        trades_by_day = defaultdict(list)
        for r in rows:
            trades_by_day[r['day']].append((r['vetoed'], r['rr']))
        blo, bhi, pneg, ppos = day_block_bootstrap_diff(
            {d: trades_by_day[d] for d in trades_by_day}, trades_by_day)

        results['sweep'].append({
            'threshold': T, 'denom': denom,
            'vetoed':   {'n': vn, 'mean_R': vm, 'median_R': vmd, 'win_rate': vw, 'atr': v_atr},
            'nonvetoed':{'n': nn, 'mean_R': nm, 'median_R': nmd, 'win_rate': nw, 'atr': n_atr},
            'veto_rate': veto_rate, 'diff_mean_R': diff, 'pop_gain_R': gain,
            'welch_t_daycluster': {'t': tstat, 'df': df, 'p_two_sided': p,
                                   'n_days_vetoed': len(dv), 'n_days_nonvetoed': len(dnv)},
            'bootstrap_diff': {'ci_lo': blo, 'ci_hi': bhi, 'P_diff_lt_0': pneg, 'P_diff_gt_0': ppos, 'B': 20000},
        })
        print(f'{T:>4} {"vetoed":>8} {vn:>5} {vm:>7.3f} {vmd:>7.3f} {vw*100:>5.1f}% {veto_rate*100:>7.1f}% | {v_atr:>7.3f}')
        print(f'{T:>4} {"nonveto":>8} {nn:>5} {nm:>7.3f} {nmd:>7.3f} {nw*100:>5.1f}% {"":>8} | {n_atr:>7.3f}')
        print(f'      diff(ved-nonv)={diff:+.4f}  pop_gain={gain:+.4f}  Welch t={tstat:.3f} df={df:.1f} p={p:.4g}  bootCI=[{blo:+.4f},{bhi:+.4f}] P(<0)={pneg:.3f}')
    return results

def main():
    recs = load()
    print(f'population N = {len(recs)}')
    # outcome sanity
    b = defaultdict(list)
    for r in recs:
        if r['direction'] in ('call', 'put') and risk(r) > 0:
            b[r['outcome']].append(realized_r(r))
    for k, v in b.items():
        print(f'  {k}: n={len(v)} meanR={statistics.mean(v):.4f}')

    out = {'n_population': len(recs)}
    out['primary'] = analyze(recs, engine_levels, 'PRIMARY: engine S/R levels (PDH/PDL/PMH/PML/ORH/ORL)')
    out['robust_coarse_round'] = analyze(recs, coarse_round_nodes, 'ROBUST: coarse round numbers ($10/$50/$100)')

    # traded-only subset (alert_only=False) on primary node set
    traded = [r for r in recs if not r.get('alert_only')]
    out['traded_only'] = analyze(traded, engine_levels, 'ROBUST: traded-only (alert_only=False), engine S/R levels')

    json.dump(out, open('research/h3_results.json', 'w'), indent=2, default=str)
    print('\nsaved research/h3_results.json')

main()
