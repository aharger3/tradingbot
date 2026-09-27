"""Scarface/J-Dub Discord called trades -> outcome on NQ/ES 1-min (honest fills).

Input: a3 pro_calls_raw.csv (option entries parsed from scarface-alerts/jdub-alerts)
       + J-Dub's explicit futures entries (hand-listed below, read from jdub-alerts.json).
Output: <OUT>/pro_calls.csv, <OUT>/pro_calls_summary.txt. Stock-sim a3 R kept as R_stock.
Rig: entry = open of first 1m bar after the message +1 tick; stop = extreme of the 2 closed
bars before entry -1 tick (min 4 ticks risk); 2R limit; stop first if both in one bar;
flat 11:00 (15:55 if entered >=10:59); stop fill -1 tick; commission $4.50 RT.
"""
import csv, glob, json, os, random, re, sys, datetime as dt, collections
from zoneinfo import ZoneInfo
import pandas as pd

ET = ZoneInfo('America/New_York')
TB = r'C:\Users\aharg\Desktop\Projects\tradingbot'
A3 = os.path.join(TB, r'research\agent_runs\v3-a3-pro-calls')
FUT = os.path.join(TB, r'research\agent_runs\t01-orb5\fut')
DISC = os.path.join(TB, 'discord_data')
SPEC = {'NQ': dict(tick=0.25, pv=20.0), 'ES': dict(tick=0.25, pv=50.0)}
ES_SYMS = {'SPY', 'ES', 'MES', 'IWM', 'DIA'}
# J-Dub explicit futures entries (jdub-alerts.json, ET). entry_px/stop_px only where he stated them.
JDUB_FUT = [
    ('2024-04-05 10:27', 'NQ', 'short', 'Short NQ 18210 / Stop above 18233'),
    ('2024-11-25 10:46', 'ES', 'short', 'ES has to stay heavy here (entry implied; partial at LOD 11:11)'),
    ('2025-04-14 11:38', 'ES', 'short', 'In Es Shorts Risking off 540 on Spy'),
    ('2025-05-07 14:37', 'ES', 'long', 'Took some ES off risking off 558.8 (84% re-entry; cut -5 pts)'),
    ('2025-05-15 11:15', 'NQ', 'long', 'Picked up NQ cons looking to buy on dips for a push towards the PDH'),
    ('2026-06-17 14:14', 'ES', 'long', "I'm long ES off Last Fridays highs"),
]

def setup_tag(text):
    t = text.lower()
    if re.search(r'\b84 ?(%|rule|percent)|reclaim', t): return '84-reclaim'
    if re.search(r'order ?block|\bob\b|one candle|\bocr\b|(up|down)[ -]?clos', t): return 'OB'
    if re.search(r'retest|b&r|break and retest', t): return 'retest'
    if re.search(r'\bpd[hl]\b|\bpm ?(high|low|h|l)\b|pre ?market (high|low)|friday', t): return 'PD/PM level'
    if re.search(r'\b(hod|lod)\b', t): return 'HOD/LOD'
    return 'unstated'

def load_fut(root):
    """date -> 1m RTH DataFrame (front contract = most RTH volume that day)."""
    out = {}
    frames = []
    for f in glob.glob(os.path.join(FUT, root + '*.csv')):
        d = pd.read_csv(f)
        if d.empty: continue
        d['c'] = os.path.basename(f)
        frames.append(d)
    d = pd.concat(frames)
    d['t'] = pd.to_datetime(d.ts_ns, utc=True).dt.tz_convert(ET)
    d = d[(d.t.dt.time >= dt.time(9, 30)) & (d.t.dt.time < dt.time(16, 0))]
    d['date'] = d.t.dt.date
    for day, g in d.groupby('date'):
        front = g.groupby('c').volume.sum().idxmax()
        out[day] = g[g.c == front].set_index('t').sort_index()[['open', 'high', 'low', 'close']]
    return out

def simulate(bars, t_msg, direction, root):
    """bars: 1m DataFrame for the day. Returns dict or None if not simulable."""
    tk = SPEC[root]['tick']; comm = 4.5 / SPEC[root]['pv']
    start = t_msg.replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    idx = bars.index
    k = idx.searchsorted(start)
    if k < 2 or k >= len(idx) or (idx[k] - start) > dt.timedelta(minutes=5): return None
    s = 1 if direction == 'long' else -1
    e = bars.open.iloc[k] + s * tk
    prev = bars.iloc[k - 2:k]
    stop = (prev.low.min() - tk) if s == 1 else (prev.high.max() + tk)
    if s * (e - stop) < 4 * tk: stop = e - s * 4 * tk
    risk = s * (e - stop); tgt = e + s * 2 * risk
    flat = dt.time(15, 55) if idx[k].time() >= dt.time(10, 59) else dt.time(11, 0)
    exit_px, why = None, 'time'
    for i in range(k, len(idx)):
        b = bars.iloc[i]
        if idx[i].time() >= flat:
            exit_px = b.open; break
        hit_s = (b.low <= stop) if s == 1 else (b.high >= stop)
        hit_t = (b.high >= tgt) if s == 1 else (b.low <= tgt)
        if hit_s: exit_px, why = stop - s * tk, 'stop'; break
        if hit_t: exit_px, why = tgt, 'target'; break
    if exit_px is None: exit_px = bars.close.iloc[-1]
    R = (s * (exit_px - e) - comm) / risk
    # index gate: index already beyond its own 5m OR in call direction at entry
    orb = bars[bars.index.time < dt.time(9, 35)]
    gate = None
    if len(orb) and idx[k - 1].time() >= dt.time(9, 35):
        c = bars.close.iloc[k - 1]
        gate = int(c > orb.high.max()) if s == 1 else int(c < orb.low.min())
    return dict(entry=round(e, 2), stop=round(stop, 2), target=round(tgt, 2), exit=why,
                R=round(R, 3), gate=gate, et=idx[k])

def main(out_dir):
    raw = list(csv.DictReader(open(os.path.join(A3, 'pro_calls_raw.csv'), encoding='utf-8')))
    stockR = {(r['time'], r['instrument']): r['R'] for r in csv.DictReader(open(os.path.join(A3, 'pro_calls_stock.csv'), encoding='utf-8'))}  # a3 stock sim, backed up
    # prior 30 min of same-channel text for setup context
    ctx = {}
    for src in ('scarface', 'jdub'):
        ms = [m for m in json.load(open(os.path.join(DISC, src + '-alerts.json'), encoding='utf-8')) if m.get('content')]
        ctx[src] = sorted(((int(m['id']) >> 22) + 1420070400000, m['content']) for m in ms)
    def context(src, t):
        ms_t = t.timestamp() * 1000
        return ' / '.join(c for ts, c in ctx[src] if ms_t - 1800e3 <= ts <= ms_t + 60e3)
    calls = [dict(mentor=r['source'], time=r['time'], symbol=r['instrument'], direction=r['direction'],
                  swing=int(r['swing']), text=r['text']) for r in raw]
    calls += [dict(mentor='jdub', time=t, symbol=s, direction=d, swing=0, text=x) for t, s, d, x in JDUB_FUT]
    fut = {k: load_fut(k) for k in SPEC}
    rows = []
    for c in calls:
        t = dt.datetime.strptime(c['time'], '%Y-%m-%d %H:%M').replace(tzinfo=ET)
        c['setup'] = setup_tag(c['text'])
        if c['setup'] == 'unstated': c['setup'] = setup_tag(context(c['mentor'], t))
        c['idx'] = 'ES' if c['symbol'].upper() in ES_SYMS else 'NQ'
        c['R_stock'] = stockR.get((c['time'], c['symbol']), '')
        for root in SPEC:
            sim = None if c['swing'] else (simulate(fut[root][t.date()], t, c['direction'], root) if t.date() in fut[root] else None)
            c['R_' + root] = sim['R'] if sim else ''
            if root == c['idx']:
                c.update({k: (sim[k] if sim else '') for k in ('entry', 'stop', 'target', 'exit', 'gate')})
                c['R'] = sim['R'] if sim else ''
                c['win'] = int(sim['R'] > 0) if sim else ''
                c['half'] = ''
        rows.append(c)
    sim = sorted([r for r in rows if r['R'] != ''], key=lambda r: r['time'])
    for i, r in enumerate(sim): r['half'] = 'H1' if i < len(sim) / 2 else 'H2'
    cols = ['mentor', 'time', 'symbol', 'direction', 'setup', 'idx', 'entry', 'stop', 'target', 'exit', 'R', 'win',
            'R_NQ', 'R_ES', 'R_stock', 'gate', 'half', 'swing', 'text']
    with open(os.path.join(out_dir, 'pro_calls.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    L = []
    def line(name, rs):
        if not rs: return
        R = [r['R'] for r in rs]
        L.append(f'{name:32s} n={len(R):3d} win={sum(x > 0 for x in R) / len(R):.0%} avgR={sum(R) / len(R):+.2f}')
    L.append(f'calls={len(rows)} swing={sum(r["swing"] for r in rows)} simulated={len(sim)} '
             f'no-bars={sum(1 for r in rows if not r["swing"] and r["R"] == "")}')
    line('ALL', sim)
    for m in ('scarface', 'jdub'):
        line(m, [r for r in sim if r['mentor'] == m])
        for s in sorted({r['setup'] for r in sim}):
            line(f'  {m} / {s}', [r for r in sim if r['mentor'] == m and r['setup'] == s])
    for h in ('H1', 'H2'): line(h, [r for r in sim if r['half'] == h])
    for g in (1, 0): line(f'index gate={g}', [r for r in sim if r['gate'] == g])
    g1 = [r['R'] for r in sim if r['gate'] == 1]; g0 = [r['R'] for r in sim if r['gate'] == 0]
    if g1 and g0:
        pool = g1 + g0; d0 = sum(g1) / len(g1) - sum(g0) / len(g0); rg = random.Random(3); hit = 0
        for _ in range(2000):
            rg.shuffle(pool); hit += sum(pool[:len(g1)]) / len(g1) - sum(pool[len(g1):]) / len(g0) >= d0
        L.append(f'gate diff {d0:+.2f}R permutation p={(hit + 1) / 2001:.3f}')
    for d in ('long', 'short'): line(d, [r for r in sim if r['direction'] == d])
    both = [r for r in sim if r['R_stock'] != '']
    if both:
        L.append(f'same calls stock-sim avgR={sum(float(r["R_stock"]) for r in both) / len(both):+.2f} vs index {sum(r["R"] for r in both) / len(both):+.2f} (n={len(both)})')
    # shuffle: same day/direction/index, random minute 09:36-10:30, 300x
    rnd = random.Random(7); act = sum(r['R'] for r in sim) / len(sim); ge = 0; means = []
    for _ in range(300):
        acc = []
        for r in sim:
            day = dt.datetime.strptime(r['time'], '%Y-%m-%d %H:%M').replace(tzinfo=ET)
            t = day.replace(hour=9, minute=36) + dt.timedelta(minutes=rnd.randrange(55))
            x = simulate(fut[r['idx']][day.date()], t, r['direction'], r['idx'])
            if x: acc.append(x['R'])
        m = sum(acc) / len(acc); means.append(m); ge += m >= act
    L.append(f'shuffle: random-minute mean={sum(means) / len(means):+.2f} vs actual {act:+.2f}, p={(ge + 1) / 301:.3f}')
    txt = '\n'.join(L); print(txt)
    open(os.path.join(out_dir, 'pro_calls_summary.txt'), 'w').write(txt)

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else A3)
