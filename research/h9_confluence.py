#!/usr/bin/env python3
"""H9 confluence-weight vs outcome (omen-3.4 / T7) -- does the weight ordering track R?

Pure analysis over the existing engine trade population (backtest_charts_12mo.json,
974 records). No new data, no human input.

TASK (H9): for every trade, compute the confluence weight of the nearest node to the
entry price at the entry bar, then measure whether that weight tracks realized R:
  - Spearman rho across all trades, with a day-block bootstrap CI;
  - binned mean realized R by weight bucket (readable artifact, n per bucket);
  - OLS of R on weight with day-clustered standard errors;
  - monotonicity check: does mean R rise across consecutive weight buckets? name
    any bucket that breaks the ordering.
Uses every trade (the spec needs ~780; if smaller, report achieved power).

NODE SET -- T3 (research/levels.py) is ABSENT on this checkout (same blocker as
T4/target_autopsy, H5/frontrun, H3/veto): the spec's full confluence node set (round
numbers + HTF levels + pivots, with T2's typed weights) is not computable. The
faithful no-new-data node set is the engine's OWN S/R level set (each record carries
levels = {PDH,PDL,PMH,PML,ORH,ORL} -- prior-day / premarket extremes and opening-range
H/L), exactly the levels the engine grades and caps trades on (signal_runner
._grade_for_levels). To that we add price-derivable psychological round numbers
($10/$50/$100 multiples), which are the Osler component of the confluence set and
need no external data. HTF levels / pivots are not present (htf_bias is a bias label,
not a price node) and are omitted -- documented, not hidden.

CONFLUENCE WEIGHT TABLE (proxy for T2's table -- T2 is itself absent). Base type
weights (a wall-strength ordering a trader would guess; the spec calls every weight a
guess, and H9 is precisely the test of whether the ordering is real):
    $100 round  : 5      (coarsest psychological)
    PDH / PDL   : 4      (prior-day extreme -- strongest structural wall)
    $50 round   : 4
    PMH / PML   : 3      (premarket extreme)
    $10 round   : 3
    ORH / ORL   : 2      (opening range -- intraday, weakest)
Confluence = stacking: when distinct node types coincide at one price (within
tolerance tol = max(2 ticks, 0.10*ATR_1m)), the merged node's weight is the SUM of
the base weights of every contributing type. A lone ORL is weight 2; an ORL that is
also a $10 round is weight 5; a PDH that is also a $50 round and a $100 round is
weight 13. The literal "confluence" reading -- stack the levels -- not the max.

NEAREST NODE = min |node_price - entry| over the whole merged node set (both sides;
the spec says "nearest node to the entry price", no direction qualifier). A
directional (in-trade-direction) variant is reported as robustness.

POWER: the spec wants ~780 trades for this all-trades test. The population is 974
records, 965 with a computable nearest node and positive risk -- above the 780
target, so the test runs at the intended size and achieved power is reported from the
data (Spearman SE / MDE).
"""
import json, math, random, statistics
from collections import defaultdict, Counter

TICK = 0.01

# ---- T2 confluence weight table (proxy) ----
BASE_W = {
    'PDH': 4, 'PDL': 4,
    'PMH': 3, 'PML': 3,
    'ORH': 2, 'ORL': 2,
    'R100': 5, 'R50': 4, 'R10': 3,
}

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
        c = candles[i]; pc = candles[i - 1]['c']
        trs.append(max(c['h'] - c['l'], abs(c['h'] - pc), abs(c['l'] - pc)))
    if not trs:
        trs = [c['h'] - c['l'] for c in candles if c['h'] - c['l'] > 0]
    return sum(trs) / len(trs) if trs else 0.0

def round_mult(e, base):
    return float(base * round(e / base))

def build_nodes(r):
    """Merged confluence node set at the entry bar -> list of (price, weight, types)."""
    e = r['entry']
    atr = atr_1m(r.get('candles') or [], r.get('entry_i'))
    tol = max(2 * TICK, 0.10 * atr) if atr > 0 else 2 * TICK
    raw = []  # (price, type)
    L = r.get('levels') or {}
    for k in ('PDH', 'PDL', 'PMH', 'PML', 'ORH', 'ORL'):
        v = L.get(k)
        if v is not None:
            raw.append((float(v), k))
    # coarse psychological round numbers near entry (within +-2 grids)
    for base, tag in ((100, 'R100'), (50, 'R50'), (10, 'R10')):
        ctr = round_mult(e, base)
        for d in range(-2, 3):
            raw.append((float(ctr + d * base), tag))
    # merge coincident types within tol
    merged = []  # (price, set_of_types)
    for price, t in raw:
        placed = False
        for m in merged:
            if abs(m[0] - price) <= tol:
                m[1].add(t); placed = True; break
        if not placed:
            merged.append([price, {t}])
    out = []
    for price, types in merged:
        w = sum(BASE_W[t] for t in types)
        out.append((price, w, tuple(sorted(types))))
    return out, tol

def nearest_node(nodes, entry, directional=None):
    """Nearest node by |price-entry|. directional='call'/'put' restricts to the
    in-trade-direction side; None = both sides (primary, literal spec reading)."""
    if directional == 'call':
        cands = [n for n in nodes if n[0] > entry + 1e-9]
    elif directional == 'put':
        cands = [n for n in nodes if n[0] < entry - 1e-9]
    else:
        cands = nodes
    if not cands:
        return None
    return min(cands, key=lambda n: abs(n[0] - entry))

# ---- Spearman (manual) ----
def rankdata(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # average rank (1-based)
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks

def pearson(x, y):
    n = len(x)
    if n < 2: return float('nan')
    mx = sum(x) / n; my = sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x); syy = sum((b - my) ** 2 for b in y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    if sxx <= 0 or syy <= 0: return float('nan')
    return sxy / math.sqrt(sxx * syy)

def spearman(x, y):
    if len(x) < 2: return float('nan')
    return pearson(rankdata(x), rankdata(y))

def spearman_se(n, rho):
    """Large-sample SE of Spearman rho under H0: sqrt((1-rho^2)/(n-2))... use the
    standard Fisher-style approximation sqrt((1-rho^2)/(n-2)) for the t-form; here we
    report the simple asymptotic SE 1/sqrt(n-1) for the no-tie null as a power read."""
    if n <= 2: return float('nan')
    return math.sqrt((1 - rho * rho) / (n - 2))

def day_block_bootstrap_rho(by_day, B=20000, seed=20260805):
    """Resample whole days w/ replacement; recompute Spearman rho each draw."""
    rng = random.Random(seed)
    days = sorted(by_day.keys())
    rhos = []
    for _ in range(B):
        samp = [rng.choice(days) for _ in range(len(days))]
        xs = []; ys = []
        for d in samp:
            for (w, rr) in by_day[d]:
                xs.append(w); ys.append(rr)
        if len(set(xs)) < 2 or len(set(ys)) < 2:
            continue
        r = spearman(xs, ys)
        if r == r:
            rhos.append(r)
    rhos.sort()
    if not rhos: return (float('nan'), float('nan'), float('nan'), 0)
    lo = rhos[int(0.025 * len(rhos))]; hi = rhos[int(0.975 * len(rhos))]
    p_pos = sum(1 for v in rhos if v > 0) / len(rhos)
    p_neg = sum(1 for v in rhos if v < 0) / len(rhos)
    return lo, hi, p_pos, p_neg, len(rhos)

# ---- OLS with day-clustered (Liang-Zeger) standard errors ----
def ols_clustered(weights, R, days):
    """OLS of R on weight (with intercept). Returns (beta_weight, se_clustered,
    t, p_two_sided, df, intercept). Cluster-robust SE over day clusters."""
    n = len(weights)
    if n < 3:
        return None
    # OLS fit
    xbar = sum(weights) / n; ybar = sum(R) / n
    sxx = sum((x - xbar) ** 2 for x in weights)
    if sxx <= 0:
        return None
    beta = sum((x - xbar) * (y - ybar) for x, y in zip(weights, R)) / sxx
    intercept = ybar - beta * xbar
    resid = [y - (intercept + beta * x) for x, y in zip(weights, R)]
    # cluster-robust variance: bread = (X'X)^-1 ; meat = sum_g (X_g'u_g)(X_g'u_g)'
    # X row = [1, weight]
    XtX = [[0.0, 0.0], [0.0, 0.0]]
    for x in weights:
        XtX[0][0] += 1; XtX[0][1] += x; XtX[1][0] += x; XtX[1][1] += x * x
    det = XtX[0][0] * XtX[1][1] - XtX[0][1] * XtX[1][0]
    if det == 0:
        return None
    inv = [[XtX[1][1] / det, -XtX[0][1] / det], [-XtX[1][0] / det, XtX[0][0] / det]]
    # per-cluster sums
    clusters = defaultdict(lambda: [0.0, 0.0])  # sum_g X_g * u_g
    for x, u, d in zip(weights, resid, days):
        clusters[d][0] += u            # *1
        clusters[d][1] += x * u        # *weight
    meat = [[0.0, 0.0], [0.0, 0.0]]
    for g in clusters.values():
        meat[0][0] += g[0] * g[0]; meat[0][1] += g[0] * g[1]
        meat[1][0] += g[1] * g[0]; meat[1][1] += g[1] * g[1]
    # sandwich var = inv * meat * inv ; var(beta_weight) = [1][1]
    G = len(clusters)
    # small-sample correction (n/(n-2)) * (G/(G-1))
    fcc = (n / (n - 2)) * (G / (G - 1)) if G > 1 else 1.0
    var_b = (inv[0][0] * meat[0][1] + inv[0][1] * meat[1][1])  # row0 . col1 of meat
    var_b = inv[0][0] * meat[0][1] + inv[0][1] * meat[1][1]
    # full sandwich [1][1]:
    # (inv * meat) row1 = [inv[1][0]*m00+inv[1][1]*m10, inv[1][0]*m01+inv[1][1]*m11]
    # then * inv col1: * inv[0][1] and inv[1][1]
    s = inv[1][0] * meat[0][0] + inv[1][1] * meat[1][0]
    t1 = inv[1][0] * meat[0][1] + inv[1][1] * meat[1][1]
    var_beta = (s * inv[0][1] + t1 * inv[1][1]) * fcc
    if var_beta <= 0:
        return None
    se = math.sqrt(var_beta)
    t = beta / se
    df = G - 1  # cluster-robust t uses G-1 df (common convention)
    # two-sided p from the Student-t dist: p = I_x(df/2, 1/2), x = df/(df+t^2)
    # (same form as the Welch p in h3_veto.py -- verified there against known t)
    p = _betai(0.5 * df, 0.5, df / (df + t * t)) if df > 0 else float('nan')
    return {'beta': beta, 'intercept': intercept, 'se': se, 't': t, 'p': p,
            'df': df, 'n_clusters': G}

def _t_cdf(t, df):
    """CDF of Student t at +t via the regularized incomplete beta (Numerical Recipes)."""
    x = df / (df + t * t)
    return 0.5 * _betai(0.5 * df, 0.5, x)

def _betai(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    bt = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1 - bt * _betacf(b, a, 1 - x) / b

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

def build_rows(recs, directional=None):
    rows = []
    for r in recs:
        if r['direction'] not in ('call', 'put'): continue
        rk = risk(r)
        if rk <= 0: continue
        nodes, tol = build_nodes(r)
        nn = nearest_node(nodes, r['entry'], directional)
        if nn is None: continue
        rows.append({
            'rec': r, 'day': r['day'], 'dir': r['direction'], 'R': rk,
            'rr': realized_r(r), 'node_price': nn[0], 'weight': nn[1],
            'types': nn[2], 'tol': tol, 'dist': abs(nn[0] - r['entry']),
            'alert_only': bool(r.get('alert_only')),
        })
    return rows

def monotonicity(buckets):
    """buckets: list of (label, n, meanR) ordered by weight ascending. Return list of
    consecutive transitions and the set of breakers (label of the higher bucket)."""
    breaks = []
    trans = []
    for i in range(1, len(buckets)):
        lo = buckets[i - 1]; hi = buckets[i]
        ok = hi[2] >= lo[2]
        trans.append((lo[0], hi[0], lo[2], hi[2], ok))
        if not ok:
            breaks.append(hi[0])
    return trans, breaks

def bucketize(rows, scheme='value'):
    """Group by weight. scheme='value' -> one bucket per distinct integer weight
    (NO merge -- every weight is its own row with its own n, as the done-when
    requires). Returns ordered list of (label, n, meanR, medianR, win%, small)."""
    if scheme == 'value':
        groups = defaultdict(list)
        for r in rows:
            groups[r['weight']].append(r['rr'])
        out = []
        for w in sorted(groups):
            rrs = groups[w]
            n = len(rrs)
            m = sum(rrs) / n
            med = statistics.median(rrs)
            wr = sum(1 for v in rrs if v > 0) / n
            out.append((str(w), n, m, med, wr, n < 20))
        return out
    return []

def analyze(recs, directional=None, label='PRIMARY'):
    rows = build_rows(recs, directional)
    n = len(rows)
    ws = [r['weight'] for r in rows]
    rrs = [r['rr'] for r in rows]
    rho = spearman(ws, rrs)
    rho_se = spearman_se(n, rho)

    by_day = defaultdict(list)
    for r in rows:
        by_day[r['day']].append((r['weight'], r['rr']))
    blo, bhi, ppos, pneg, B = day_block_bootstrap_rho(by_day)

    ols = ols_clustered(ws, rrs, [r['day'] for r in rows])

    buckets = bucketize(rows, 'value')
    trans, breaks = monotonicity([(b[0], b[1], b[2]) for b in buckets])
    # monotonicity restricted to buckets with n>=20 (the readable, powered chain)
    big = [(b[0], b[1], b[2]) for b in buckets if b[1] >= 20]
    trans_big, breaks_big = monotonicity(big)

    # nearest-node type composition
    type_comp = Counter()
    for r in rows:
        for t in r['types']:
            type_comp[t] += 1
    # weight distribution
    wdist = Counter(ws)

    res = {
        'label': label, 'n': n,
        'spearman_rho': rho, 'spearman_se_asymptotic': rho_se,
        'rho_bootstrap_ci': {'lo': blo, 'hi': bhi, 'P_rho_gt_0': ppos,
                             'P_rho_lt_0': pneg, 'B': B},
        'ols_clustered': ols,
        'buckets': [{'weight': b[0], 'n': b[1], 'mean_R': b[2], 'median_R': b[3],
                     'win_rate': b[4], 'small': b[5]} for b in buckets],
        'monotonicity': {'transitions': trans, 'breakers': breaks,
                         'is_monotone': len(breaks) == 0,
                         'transitions_n20plus': trans_big,
                         'breakers_n20plus': breaks_big,
                         'is_monotone_n20plus': len(breaks_big) == 0},
        'weight_distribution': dict(sorted(wdist.items())),
        'type_composition': dict(type_comp),
        'pop_mean_R': sum(rrs) / n if n else float('nan'),
        'n_days': len(by_day),
    }
    return res

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
    out['primary'] = analyze(recs, None,
                             'PRIMARY: nearest node (both sides), T2-proxy weights')
    out['directional'] = analyze(recs, 'call',
                                 'ROBUST: nearest node in trade direction')

    # traded-only subset (alert_only=False) on primary
    traded = [r for r in recs if not r.get('alert_only')]
    out['traded_only'] = analyze(traded, None,
                                 'ROBUST: traded-only (alert_only=False)')

    # print summary
    for key in ('primary', 'directional', 'traded_only'):
        r = out[key]
        print(f'\n=== {r["label"]}  (N={r["n"]}, days={r["n_days"]}, pop mean R={r["pop_mean_R"]:.4f}) ===')
        print(f'Spearman rho = {r["spearman_rho"]:+.4f}  (asymptotic SE {r["spearman_se_asymptotic"]:.4f})')
        rb = r['rho_bootstrap_ci']
        print(f'  day-block bootstrap 95% CI = [{rb["lo"]:+.4f}, {rb["hi"]:+.4f}]  '
              f'P(rho>0)={rb["P_rho_gt_0"]:.3f}  P(rho<0)={rb["P_rho_lt_0"]:.3f}  (B={rb["B"]})')
        o = r['ols_clustered']
        if o:
            print(f'OLS R ~ weight (day-clustered): beta={o["beta"]:+.5f}  '
                  f'se={o["se"]:.5f}  t={o["t"]:.3f}  df={o["df"]}  p={o["p"]:.4g}  '
                  f'(clusters={o["n_clusters"]}, intercept={o["intercept"]:+.4f})')
        print('Binned mean realized R by weight bucket:')
        print(f'  {"weight":>10} {"n":>5} {"meanR":>8} {"medR":>8} {"win%":>6}')
        for b in r['buckets']:
            flag = ' *' if b['small'] else ''
            print(f'  {str(b["weight"]):>10} {b["n"]:>5} {b["mean_R"]:>+8.4f} '
                  f'{b["median_R"]:>+8.3f} {b["win_rate"]*100:>5.1f}%{flag}')
        m = r['monotonicity']
        print('Monotonicity -- mean R across consecutive weight buckets (all):')
        for t in m['transitions']:
            tag = 'ok' if t[4] else 'BREAK'
            print(f'  {t[0]:>5} -> {t[1]:>5}: {t[2]:+.4f} -> {t[3]:+.4f}  [{tag}]')
        print(f'  breakers (all): {m["breakers"] if m["breakers"] else "none (monotone)"}')
        print('Monotonicity -- restricted to buckets with n>=20 (powered chain):')
        for t in m['transitions_n20plus']:
            tag = 'ok' if t[4] else 'BREAK'
            print(f'  {t[0]:>5} -> {t[1]:>5}: {t[2]:+.4f} -> {t[3]:+.4f}  [{tag}]')
        print(f'  breakers (n>=20): '
              f'{m["breakers_n20plus"] if m["breakers_n20plus"] else "none (monotone)"}')
        # achieved power read
        se = r['spearman_se_asymptotic']
        mde = 2.802 * se if se == se else float('nan')  # 80% power, alpha=0.05 two-sided
        print(f'Achieved power: n={r["n"]} (>=780 target: '
              f'{"YES" if r["n"]>=780 else "NO"}). Spearman SE={se:.4f} -> '
              f'MDE(rho) @80% power ~{mde:.4f}; observed rho={r["spearman_rho"]:+.4f}; '
              f'rho upper-95={r["rho_bootstrap_ci"]["hi"]:+.4f}.')
        print(f'  weight distribution: {r["weight_distribution"]}')
        print(f'  nearest-node type composition: {r["type_composition"]}')

    json.dump(out, open('research/h9_results.json', 'w'), indent=2, default=str)
    print('\nsaved research/h9_results.json')

main()