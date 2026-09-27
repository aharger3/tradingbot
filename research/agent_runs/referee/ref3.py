import json, glob, os, re
B = r'C:\Users\aharg\Desktop\Projects\tradingbot'; A = B + r'\research\agent_runs'
g = json.load(open(A + r'\t01-orb5\grid_fut.json'))
ps = sorted((v['p_shuffle'], k) for k, v in g.items() if 'p_shuffle' in v); m = len(ps)
q = [min(ps[j][0] * m / (j + 1) for j in range(i, m)) for i in range(m)]
print('t01 cells', m, 'best p/q', ps[0], round(q[0], 3), 'za10R rank', [i for i, x in enumerate(ps) if x[1] == 'MNQ|za|S2|10R'], 'q_min', round(min(q), 3))
gg = json.load(open(B + r'\research\g88_level_limit_retest_on.json'))
def find(d, path=''):
    if isinstance(d, dict):
        for k, v in d.items():
            if 'POST' in str(k).upper(): print(path + '/' + k, json.dumps(v)[:500])
            find(v, path + '/' + str(k))
find(gg)
live = []
for f in glob.glob(B + r'\**\*.py', recursive=True):
    if '.claude' in f or 'agent_runs' in f or 'node_modules' in f or '.loop-wt' in f: continue
    try: s = open(f, errors='ignore').read()
    except Exception: continue
    if re.search(r'https://api\.alpaca\.markets', s) or re.search(r'paper\s*=\s*False', s): live.append(os.path.relpath(f, B))
print('live-endpoint refs:', live)
