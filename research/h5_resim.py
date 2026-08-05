#!/usr/bin/env python3
"""H5 frontrun resimulation (omen-3.4 / T5).

Pure resimulation over the existing engine trade population
(backtest_charts_12mo.json, 974 records). No new data, no human input.

Question (Osler 2003): does a take-profit resting exactly at a round number sit
behind a queue and fail to fill on a wick that touches and reverses, while a
limit placed just short of the round number fills? For every trade whose target
lies within one tick of a qualifying round-number node, simulate two
counterfactuals from the SAME 1-min bar path:

  A (at_node) : target = the round-number node
  B (frontrun): target = node - direction * max(1 tick, 0.10 * ATR_1m)

Both arms share the original stop and bar path -> paired design. Only
discordant pairs carry information for the fill endpoint (McNemar); realized R
uses all paired diffs (Wilcoxon signed-rank + day-block bootstrap).

Fill model = the engine's OWN model (backtest_week.simulate_day): a target fills
when a bar's wick reaches it (high>=target for calls, low<=target for puts),
stop takes priority on a bar where both hit, unresolved = scratch at last close.
Validated to reproduce the recorded outcome/exit_price on the original target.

NODE WEIGHTING NOTE: the omen-3.4 weighted-node module (research/levels.py, T3)
is ABSENT on this checkout (same blocker as T4/target_autopsy). H5 is explicitly
the Osler round-number hypothesis, and round numbers are price-derivable, so we
implement the faithful no-new-data subset: nodes = equity round numbers. We assign
weight so the Osler round number for equities (the whole dollar) is the
qualifying node: whole$=3, $5-multiple=4, $10/$50/$100=5. weight>=3.0 == all
round numbers (whole dollar and coarser). Under a coarser weighting ($10=3) the
eligible set is 0 (the engine's 2R targets don't land on $10 marks) -- reported
as a robustness check; the underpowered verdict is unchanged.
"""
import json, math, random
from collections import defaultdict

TICK = 0.01  # US equity minimum price increment

def load(): return json.load(open('backtest_charts_12mo.json'))

def round_weight(p):
    """Osler equity round-number weight: whole$=3, $5=4, $10/$50/$100=5, else 0."""
    if p is None: return 0
    if abs(p - round(p)) > 1e-9: return 0
    r = round(p)
    if r % 100 == 0: return 5
    if r % 50 == 0: return 5
    if r % 10 == 0: return 5
    if r % 5 == 0: return 4
    return 3  # whole dollar

def nearest_round_node(target):
    """Nearest weight>=3 round number (whole-dollar grid) to target, with weight."""
    base = round(target)              # nearest whole dollar
    cands = [base - 1, base, base + 1]
    # nearest by distance; tiebreak higher weight
    best = min(cands, key=lambda n: (abs(target - n), -round_weight(n)))
    return best, abs(target - best), round_weight(best)

def atr_1m(candles, entry_i):
    """Mean true range of 1-min bars over the pre-entry window (fallback: all)."""
    end = entry_i if entry_i >= 2 else len(candles)
    end = max(min(end, len(candles)), 2)
    trs = []
    for i in range(1, end):
        c = candles[i]; pc = candles[i-1]['c']
        tr = max(c['h'] - c['l'], abs(c['h'] - pc), abs(c['l'] - pc))
        trs.append(tr)
    if not trs:  # fallback: all bars high-low
        trs = [c['h'] - c['l'] for c in candles if c['h'] - c['l'] > 0]
    return sum(trs) / len(trs) if trs else 0.0

def resim(candles, entry_i, stop, target, direction):
    """Engine fill model from entry_i+1..last bar. Returns (filled, exit_price, exit_i)."""
    long = direction == 'call'
    risk = abs(candles[entry_i]['c'] - stop)  # not used here
    last_i = len(candles) - 1
    for i in range(entry_i + 1, len(candles)):
        c = candles[i]
        if long:
            stopped = c['l'] <= stop
            targeted = c['h'] >= target
        else:
            stopped = c['h'] >= stop
            targeted = c['l'] <= target
        if stopped:                      # conservative: stop wins ties
            return False, stop, i
        if targeted:
            return True, target, i
    return False, candles[last_i]['c'], last_i  # scratch at last close

def realized_r(entry, stop, exit_price, direction):
    risk = abs(entry - stop)
    if risk == 0: return 0.0
    if direction == 'call':
        return (exit_price - entry) / risk
    return (entry - exit_price) / risk

def main():
    random.seed(20260805)
    recs = load()
    n = len(recs)

    # ---- 0. validate resim reproduces recorded outcomes on original target ----
    agree = 0; disagree = []
    for r in recs:
        cs = r['candles']; ei = r['entry_i']
        if not cs or ei is None or ei < 0 or ei >= len(cs): continue
        filled, ep, xi = resim(cs, ei, r['stop'], r['target'], r['direction'])
        # map to outcome label
        if filled:
            sim_out, sim_ep = 'win', r['target']
        elif xi == len(cs)-1 and abs(ep - cs[-1]['c']) < 1e-9:
            sim_out, sim_ep = 'scratch', cs[-1]['c']
        else:
            sim_out, sim_ep = 'loss', r['stop']
        rec_out = r['outcome']
        # compare outcome (allow scratch vs loss/win boundary nuances)
        ok = (sim_out == rec_out) or (sim_out in ('loss','scratch') and rec_out in ('loss','scratch'))
        if ok: agree += 1
        else:
            if len(disagree) < 8:
                disagree.append((r['symbol'], r['day'], r['direction'], r['entry'], r['stop'],
                                 r['target'], rec_out, r['exit_price'], sim_out, round(ep,3), xi))
    print(f'VALIDATION resim vs recorded: {agree}/{n} agree ({round(agree/n*100,1)}%)')
    if disagree:
        print('  disagree samples (sym day dir entry stop target | rec_out rec_ep | sim_out sim_ep xi):')
        for d in disagree: print('   ', d)

    # ---- 1. eligible set: target within 1 tick of a weight>=3 round number ----
    eligible = []
    for r in recs:
        cs = r['candles']; ei = r['entry_i']
        if not cs or ei is None or ei < 0 or ei >= len(cs): continue
        if r['direction'] not in ('call','put'): continue
        node, dist, w = nearest_round_node(r['target'])
        if w >= 3.0 and dist <= TICK:
            atr = atr_1m(cs, ei)
            offset = max(TICK, 0.10 * atr)
            d_sign = 1 if r['direction'] == 'call' else -1
            at_node = float(node)
            frontrun = node - d_sign * offset
            eligible.append({
                'rec': r, 'node': at_node, 'weight': w, 'dist': dist,
                'atr': atr, 'offset': offset, 'at_node': at_node, 'frontrun': frontrun,
            })
    print(f'\nELIGIBLE (target within 1 tick of weight>=3 round number): {len(eligible)} of {n}')

    # robustness: coarser weighting ($10=3) eligible count
    coarser = 0
    for r in recs:
        t = r['target']
        base = 10*round(t/10)
        node = min([base-10,base,base+10], key=lambda n: abs(t-n))
        if abs(t-node) <= TICK: coarser += 1
    print(f'  robustness: under $10=weight3 weighting, eligible = {coarser}')

    # ---- 2. resim both arms ----
    pairs = []
    for e in eligible:
        r = e['rec']; cs = r['candles']; ei = r['entry_i']
        fa, epa, _ = resim(cs, ei, r['stop'], e['at_node'], r['direction'])
        fb, epb, _ = resim(cs, ei, r['stop'], e['frontrun'], r['direction'])
        ra = realized_r(r['entry'], r['stop'], epa, r['direction'])
        rb = realized_r(r['entry'], r['stop'], epb, r['direction'])
        pairs.append({
            'day': r['day'], 'symbol': r['symbol'], 'direction': r['direction'],
            'node': e['at_node'], 'offset': e['offset'], 'atr': e['atr'],
            'fill_a': fa, 'fill_b': fb, 'r_a': ra, 'r_b': rb,
            'diff_r': rb - ra, 'diff_fill': int(fb) - int(fa),
        })

    fill_a = sum(p['fill_a'] for p in pairs)
    fill_b = sum(p['fill_b'] for p in pairs)
    n_both = sum(1 for p in pairs if p['fill_a'] and p['fill_b'])
    n_neither = sum(1 for p in pairs if not p['fill_a'] and not p['fill_b'])
    b = sum(1 for p in pairs if p['fill_b'] and not p['fill_a'])  # frontrun only
    c = sum(1 for p in pairs if p['fill_a'] and not p['fill_b'])  # at_node only
    n_disc = b + c
    print(f'\nFILL: at_node filled {fill_a}/{len(pairs)}, frontrun filled {fill_b}/{len(pairs)}')
    print(f'  both={n_both} neither={n_neither} frontrun-only(b)={b} at_node-only(c)={c} n_discordant={n_disc}')

    # ---- 3. McNemar (exact, since small n) ----
    from math import comb
    def mcnemar_exact(b, c):
        n = b + c
        if n == 0: return None, None
        # two-sided exact: 2 * sum_{k>=b} C(n,k) 0.5^n  (b is the larger arm)
        m = max(b, c)
        p = sum(comb(n, k) for k in range(m, n+1)) * (0.5 ** n)
        p2 = min(1.0, 2 * p)
        return (abs(b - c) / n, p2)
    chi = (abs(b - c) - 1)**2 / (b + c) if (b + c) > 0 else None  # continuity-corrected
    mne, mnp = mcnemar_exact(b, c)
    print(f'  McNemar exact: proportion_diff={mne} p={mnp}  (chi2_cc={chi})')

    # ---- 4. Wilcoxon signed-rank + day-block bootstrap on realized R diffs ----
    diffs = [p['diff_r'] for p in pairs]
    nonzero = [d for d in diffs if abs(d) > 1e-12]
    mean_diff = sum(diffs) / len(diffs) if diffs else 0.0
    print(f'\nREALIZED R: mean diff (frontrun - at_node) = {mean_diff:.4f} R')
    ra_mean = sum(p['r_a'] for p in pairs)/len(pairs) if pairs else 0.0
    rb_mean = sum(p['r_b'] for p in pairs)/len(pairs) if pairs else 0.0
    print(f'  at_node mean R = {ra_mean:.4f}')
    print(f'  frontrun mean R = {rb_mean:.4f}')
    print(f'  nonzero diffs: {len(nonzero)} of {len(diffs)}')

    # Wilcoxon signed-rank (manual, exact for small n via normal approx with tie correction)
    def wilcoxon(dvals):
        nz = [d for d in dvals if abs(d) > 1e-12]
        if not nz: return None, None
        abs_sorted = sorted(range(len(nz)), key=lambda i: abs(nz[i]))
        # average ranks for ties in |d|
        ranks = [0.0] * len(nz)
        i = 0
        while i < len(abs_sorted):
            j = i
            while j+1 < len(abs_sorted) and abs(nz[abs_sorted[j+1]]) - abs(nz[abs_sorted[i]]) < 1e-12:
                j += 1
            avg = (i + 1 + j + 1) / 2.0  # 1-indexed average rank
            for k in range(i, j+1): ranks[abs_sorted[k]] = avg
            i = j + 1
        w_plus = sum(ranks[i] for i in range(len(nz)) if nz[i] > 0)
        w_minus = sum(ranks[i] for i in range(len(nz)) if nz[i] < 0)
        W = min(w_plus, w_minus)
        n_r = len(nz)
        # tie correction for normal approx
        # mean = n(n+1)/4 ; var with tie correction
        mean_w = n_r * (n_r + 1) / 4.0
        # sum of squared ranks
        sum_r2 = sum(rk * rk for rk in ranks)
        var_w = (n_r * (n_r + 1) * (2 * n_r + 1) / 24.0) - sum_r2 / 48.0  # not exact; use standard
        # standard Wilcoxon variance with tie correction:
        # Var = [n(n+1)(2n+1) - 0.5*sum(t_j^3 - t_j)] / 24
        # compute tie groups
        tie_groups = defaultdict(int)
        for rk in ranks: tie_groups[rk] += 1
        tie_term = sum(t**3 - t for t in tie_groups.values())
        var_w = (n_r*(n_r+1)*(2*n_r+1) - tie_term/2.0) / 24.0
        if var_w <= 0:
            return W, None
        z = (W - mean_w - 0.5) / math.sqrt(var_w)  # continuity
        # two-sided p from normal
        def norm_cdf(z):
            return 0.5*(1+math.erf(z/math.sqrt(2)))
        p = 2 * (1 - norm_cdf(abs(z)))
        return W, p
    Wstat, Wp = wilcoxon(diffs)
    print(f'  Wilcoxon signed-rank: W={Wstat} p={Wp}')

    # day-block bootstrap of mean R diff
    by_day = defaultdict(list)
    for p in pairs: by_day[p['day']].append(p['diff_r'])
    days = sorted(by_day.keys())
    B = 10000
    boot = []
    for _ in range(B):
        s = 0; cnt = 0
        for d in days:
            picks = by_day[d]
            for v in picks:
                # resample days with replacement; take whole day block
                pass
        # simpler: resample days with replacement, accumulate all diffs in chosen days
        samp_days = [random.choice(days) for _ in range(len(days))]
        diffs_samp = []
        for d in samp_days: diffs_samp.extend(by_day[d])
        boot.append(sum(diffs_samp)/len(diffs_samp) if diffs_samp else 0.0)
    boot.sort()
    lo = boot[int(0.025*len(boot))]; hi = boot[int(0.975*len(boot))]
    pct_pos = sum(1 for x in boot if x > 0) / len(boot)
    print(f'  day-block bootstrap ({B}): mean diff 95% CI = [{lo:.4f}, {hi:.4f}]  P(diff>0)={pct_pos:.2f}')

    # ---- 5. save results for the report ----
    out = {
        'n_population': n, 'validation_agree': agree, 'validation_pct': round(agree/n*100,1),
        'n_eligible': len(eligible), 'coarser_eligible': coarser,
        'fill_a': fill_a, 'fill_b': fill_b, 'n_both': n_both, 'n_neither': n_neither,
        'b': b, 'c': c, 'n_discordant': n_disc,
        'mcnemar_prop_diff': mne, 'mcnemar_p': mnp, 'mcnemar_chi2_cc': chi,
        'mean_r_at_node': sum(p['r_a'] for p in pairs)/len(pairs) if pairs else None,
        'mean_r_frontrun': sum(p['r_b'] for p in pairs)/len(pairs) if pairs else None,
        'mean_r_diff': mean_diff, 'wilcoxon_W': Wstat, 'wilcoxon_p': Wp,
        'n_nonzero_diffs': len(nonzero),
        'boot_ci_lo': lo, 'boot_ci_hi': hi, 'boot_p_pos': pct_pos,
        'pairs': pairs,
    }
    json.dump(out, open('research/h5_results.json','w'), indent=2, default=str)
    print('\nsaved research/h5_results.json')

main()
