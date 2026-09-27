"""Referee: re-derive OMEN-SHIP-PLAN numbers from on-disk outputs + independent NQ B&R rerun via bt.py (unmodified)."""
import json, sys, os, statistics, random, re
B = r'C:\Users\aharg\Desktop\Projects\tradingbot\research'
A = B + r'\agent_runs'
out = {}
# t01
g = json.load(open(A + r'\t01-orb5\grid_fut.json'))
r = g['MNQ|za|S2|10R']; out['t01_MNQ_za_S2_10R'] = {k: r.get(k) for k in ('n','avgR','usd_day','h1R','h2R','p_shuffle','q','bh_q') if k in r}
out['t01_keys'] = [k for k in r if not isinstance(r[k], (dict, list))]
out['t01_MES_retest_S2_2R'] = g['MES|retest|S2|2R']['avgR']; out['t01_MNQ_retest_S2_2R'] = g['MNQ|retest|S2|2R']['avgR']
gt = json.load(open(A + r'\t01-orb5\gate_top3.json'))
out['t01_gate_eval_ready_any'] = 'true' in json.dumps(gt['gate']).lower().replace(' ', '').split('"eval_ready":')[1:] and any(s.startswith('true') for s in json.dumps(gt['gate']).replace(' ', '').split('"eval_ready":')[1:])
# t03
for fn in ('t03_result_ES_NQ.json',):
    d = json.load(open(A + r'\t03-one-candle\\' + fn))
    grid = d['grid']; rows = grid if isinstance(grid, list) else list(grid.values())
    keyR = [k for k in rows[0] if 'net' in k.lower() or k.lower() in ('r', 'avgr', 'meanr')]
    out['t03_row_keys'] = list(rows[0].keys())[:30]
    out['t03_full_best'] = d.get('full_best'); out['t03_h1_selected'] = d.get('h1_selected')
    out['t03_n_rows'] = len(rows)
# t04
e = json.load(open(A + r'\t04-his-eye-test\eye_test.json'))
out['t04_ladder_S'] = [x for x in (e['ladder'] if isinstance(e['ladder'], list) else [e['ladder']])][:1]
out['t04_S_vs_Cnone'] = e['S_vs_Cnone']
out['t04_keys'] = list(e.keys())
# t02 NQ cell independent rerun
sys.path.insert(0, A + r'\t02-break-retest'); os.chdir(A + r'\t02-break-retest')
import bt
S = bt.sessions('NQ'); dates = sorted(S); rows = []
for d in dates:
    for sig in bt.signals(S[d], 'PRE'):
        t = bt.trade(S[d], sig, 'LVL', 3, 'NQ', net=True)
        if t: rows.append((d, t['R'], t['usd'])); break
R = [x[1] for x in rows]; n = len(R)
h1 = [x[1] for x in rows if x[0] < bt.SPLIT]; h2 = [x[1] for x in rows if x[0] >= bt.SPLIT]
rng = random.Random(2026); obs = statistics.mean(R)
p_flip = sum(statistics.mean([v * rng.choice((-1, 1)) for v in R]) >= obs for _ in range(5000)) / 5000
# day-shuffle null: random day-of-entry assignment is not defined for a level rule; instead random-direction null (same entry/exit bars, side flipped) is not available without core edits -> report sign-flip only
out['t02_NQ_rerun'] = dict(n=n, meanR=round(obs, 4), win=round(sum(v > 0 for v in R) / n, 4), h1R=round(statistics.mean(h1), 4), h2R=round(statistics.mean(h2), 4),
                          usd_per_session=round(sum(x[2] for x in rows) / len(dates), 2), trades_per_session=round(n / len(dates), 3),
                          usd_per_trade=round(statistics.mean(x[2] for x in rows), 2), sessions=len(dates), p_signflip_trades=p_flip,
                          yr={y: (sum(1 for x in rows if x[0][:4] == y), round(statistics.mean([x[1] for x in rows if x[0][:4] == y]), 3)) for y in ('2024', '2025', '2026')})
# b02 trades file agreement
tb = json.load(open(B + r'\nq_br_trades.json'))
tr = tb['trades'] if 'trades' in tb else tb.get('rows', [])
out['b02_trades_match'] = len(tr) == n and all(abs(a['r'] - b[1]) < 1e-5 and a['day'] == b[0] for a, b in zip(tr, rows)) if tr else 'no trades key: ' + str(list(tb))
json.dump(out, open(A + r'\referee\referee_out.json', 'w'), indent=1, default=str)
print(json.dumps(out, indent=1, default=str))
