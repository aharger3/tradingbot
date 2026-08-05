#!/usr/bin/env python3
"""H intrabar — can the 1-minute bar resolve what happened? (omen-3.4 / T8)

Pure resimulation over the existing engine trade population
(backtest_charts_12mo.json, 974 records). No new data, no human input.

Question: when a trade's target AND stop both lie inside a single 1-min bar's
high-low range, OHLCV cannot say which was hit first. Count how often that
happens (% of all trades, % of resolved trades) and score the population twice:
  pessimistic (stop hit first -> loss, -1R)  [primary; = engine default]
  optimistic  (target hit first -> win, +R at target)
Report mean realized R under both, and whether any T5/T6/T7 conclusion flips.

Method: the engine's OWN fill model (backtest_week.simulate_day / h5_resim.resim):
scan bars from entry_i+1; on the FIRST bar whose wick reaches stop or target,
the trade resolves. If that resolve bar's range contains BOTH stop and target,
the bar is AMBIGUOUS (OHLCV cannot order the two touches). h5_resim validated
this model reproduces the recorded outcome on 974/974 trades, so the
pessimistic scoring here == the recorded population.
"""
import json, math
from collections import Counter, defaultdict

def load(): return json.load(open('backtest_charts_12mo.json'))

def resim_resolve(candles, entry_i, stop, target, direction):
    """Find the resolving bar (first post-entry bar touching stop or target).
    Returns (resolve_i, stopped, targeted, scratch_i).
    stopped/targeted are evaluated on the resolve bar. If no bar touches either,
    the trade scratches at the last close."""
    long = direction == 'call'
    last_i = len(candles) - 1
    for i in range(entry_i + 1, len(candles)):
        c = candles[i]
        if long:
            stopped = c['l'] <= stop
            targeted = c['h'] >= target
        else:
            stopped = c['h'] >= stop
            targeted = c['l'] <= target
        if stopped or targeted:
            return i, stopped, targeted, None
    return last_i, False, False, last_i  # scratch at last close

def realized_r(entry, stop, exit_price, direction):
    risk = abs(entry - stop)
    if risk == 0: return 0.0
    if direction == 'call':
        return (exit_price - entry) / risk
    return (entry - exit_price) / risk

def main():
    recs = load()
    n = len(recs)

    # ---- 0. validate: pessimistic (stop-priority) reproduces recorded outcome ----
    agree = 0
    for r in recs:
        cs = r['candles']; ei = r['entry_i']
        ri, stopped, targeted, scratch_i = resim_resolve(cs, ei, r['stop'], r['target'], r['direction'])
        if targeted and not scratch_i is None and ri == scratch_i:
            # scratch path only triggers when no stop/target touched
            pass
        if scratch_i is not None:
            sim_out = 'scratch'
        elif targeted and not stopped:
            sim_out = 'win'
        elif stopped and not targeted:
            sim_out = 'loss'
        elif stopped and targeted:
            sim_out = 'loss'  # pessimistic: stop wins the tie
        else:
            sim_out = 'scratch'
        rec_out = r['outcome']
        ok = (sim_out == rec_out) or (sim_out in ('loss','scratch') and rec_out in ('loss','scratch'))
        if ok: agree += 1
    print(f'VALIDATION pessimistic resim vs recorded: {agree}/{n} agree ({round(agree/n*100,1)}%)')

    # ---- 1. classify every trade: ambiguous? and score both ways ----
    rows = []
    n_ambig = 0
    n_resolved = 0
    n_scratch = 0
    for r in recs:
        cs = r['candles']; ei = r['entry_i']
        entry, stop, target, direction = r['entry'], r['stop'], r['target'], r['direction']
        ri, stopped, targeted, scratch_i = resim_resolve(cs, ei, stop, target, direction)

        if scratch_i is not None:
            # scratch: neither stop nor target touched -> not ambiguous, same both scorings
            exit_price = cs[scratch_i]['c']
            r_pess = realized_r(entry, stop, exit_price, direction)
            r_opt = r_pess
            kind = 'scratch'
            n_scratch += 1
        else:
            n_resolved += 1
            ambig = stopped and targeted
            if ambig:
                n_ambig += 1
                # pessimistic: stop first -> loss at stop
                r_pess = -1.0
                # optimistic: target first -> win at target
                r_opt = realized_r(entry, stop, target, direction)
                kind = 'ambiguous'
            else:
                # unambiguous resolve: outcome determined, both scorings agree
                exit_price = target if targeted else stop
                r_pess = realized_r(entry, stop, exit_price, direction)
                r_opt = r_pess
                kind = ('win' if targeted else 'loss')
        rows.append({
            'symbol': r['symbol'], 'day': r['day'], 'direction': direction,
            'grade': r['grade'], 'alert_only': r['alert_only'],
            'entry': entry, 'stop': stop, 'target': target,
            'outcome': r['outcome'], 'kind': kind,
            'r_pess': r_pess, 'r_opt': r_opt,
        })

    mean_pess = sum(x['r_pess'] for x in rows) / n
    mean_opt = sum(x['r_opt'] for x in rows) / n
    ambig_rate_all = n_ambig / n * 100
    ambig_rate_resolved = (n_ambig / n_resolved * 100) if n_resolved else float('nan')

    print(f'\nN population: {n}')
    print(f'resolved (win/loss via target or stop): {n_resolved}')
    print(f'scratch: {n_scratch}')
    print(f'ambiguous (both stop+target in resolve bar): {n_ambig}')
    print(f'ambiguous rate, % of ALL trades:      {ambig_rate_all:.2f}%')
    print(f'ambiguous rate, % of RESOLVED trades:  {ambig_rate_resolved:.2f}%')
    print(f'\nmean realized R, PESSIMISTIC (stop-first): {mean_pess:.4f}')
    print(f'mean realized R, OPTIMISTIC  (target-first): {mean_opt:.4f}')
    print(f'delta (opt - pess): {mean_opt - mean_pess:.4f}')

    # cross-check: pessimistic mean R vs recorded exit_price mean R
    rec_mean = sum(realized_r(r['entry'], r['stop'], r['exit_price'], r['direction']) for r in recs) / n
    print(f'(cross-check recorded-exit_price mean R: {rec_mean:.4f}  -- must match pessimistic)')

    # ---- traded-only subset (alert_only=False) ----
    tr = [x for x in rows if not x['alert_only']]
    nt = len(tr)
    tr_ambig = sum(1 for x in tr if x['kind'] == 'ambiguous')
    tr_resolved = sum(1 for x in tr if x['kind'] in ('win','loss','ambiguous'))
    mp_t = sum(x['r_pess'] for x in tr) / nt
    mo_t = sum(x['r_opt'] for x in tr) / nt
    print(f'\nTRADED-ONLY (alert_only=False): N={nt}  resolved={tr_resolved}  ambig={tr_ambig}')
    print(f'  ambig % all: {tr_ambig/nt*100:.2f}%   ambig % resolved: {tr_ambig/tr_resolved*100:.2f}%')
    print(f'  mean R pess: {mp_t:.4f}   mean R opt: {mo_t:.4f}')

    # ---- kind breakdown ----
    kc = Counter(x['kind'] for x in rows)
    print(f'\nkind breakdown (full pop): {dict(kc)}')

    # ---- per-grade ambig (for T5/T6/T7 flip discussion) ----
    print('\nper-grade ambiguous count:')
    by_grade = defaultdict(lambda: [0,0])
    for x in rows:
        by_grade[x['grade']][1] += 1
        if x['kind']=='ambiguous': by_grade[x['grade']][0] += 1
    for g in sorted(by_grade):
        a,tot = by_grade[g]
        print(f'  grade {g}: {a}/{tot} ambiguous ({a/tot*100:.1f}%)')

    # ---- save results ----
    out = {
        'n_population': n, 'n_resolved': n_resolved, 'n_scratch': n_scratch, 'n_ambiguous': n_ambig,
        'ambiguous_rate_pct_all': round(ambig_rate_all, 2),
        'ambiguous_rate_pct_resolved': round(ambig_rate_resolved, 2),
        'mean_realized_R_pessimistic': round(mean_pess, 4),
        'mean_realized_R_optimistic': round(mean_opt, 4),
        'delta_opt_minus_pess': round(mean_opt - mean_pess, 4),
        'recorded_exit_price_mean_R': round(rec_mean, 4),
        'validation_agree': agree, 'validation_pct': round(agree/n*100, 1),
        'traded_only': {
            'n': nt, 'n_resolved': tr_resolved, 'n_ambiguous': tr_ambig,
            'ambiguous_rate_pct_all': round(tr_ambig/nt*100, 2),
            'ambiguous_rate_pct_resolved': round(tr_ambig/tr_resolved*100, 2),
            'mean_R_pessimistic': round(mp_t, 4), 'mean_R_optimistic': round(mo_t, 4),
        },
        'kind_breakdown': dict(kc),
        'per_grade_ambiguous': {g: {'ambig': by_grade[g][0], 'n': by_grade[g][1]} for g in sorted(by_grade)},
    }
    json.dump(out, open('research/h_intrabar_results.json','w'), indent=2)
    # also dump per-trade rows for audit
    json.dump(rows, open('research/h_intrabar_rows.json','w'), indent=2)
    print('\nsaved research/h_intrabar_results.json + h_intrabar_rows.json')

main()
