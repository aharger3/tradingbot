import json, os, re, glob, subprocess, sys
B = r'C:\Users\aharg\Desktop\Projects\tradingbot'
R = B + r'\research'; A = R + r'\agent_runs'
o = {}
e = json.load(open(A + r'\t04-his-eye-test\eye_test.json'))
o['t04_post_1100'] = json.dumps(e['post_1100'])[:700]
# t01 q
hits = []
for f in glob.glob(A + r'\t01-orb5\*'):
    try: s = open(f, errors='ignore').read()
    except Exception: continue
    for m in re.finditer(r'.{0,60}\b0\.6[24]\d*.{0,40}', s):
        if 'q' in m.group(0).lower(): hits.append(os.path.basename(f) + ': ' + m.group(0).replace('\n', ' '))
o['t01_q_hits'] = hits[:6]
# u03 g88
try:
    g = json.load(open(R + r'\g88_level_limit_retest_on.json'))
    o['g88'] = json.dumps(g)[:900]
except Exception as ex: o['g88'] = str(ex)
# edge slices count
for f in glob.glob(R + r'\edge_slice*') + glob.glob(R + r'\*slices*'):
    o.setdefault('slices_files', []).append(os.path.basename(f))
for f in glob.glob(R + r'\edge_slices*.json'):
    try:
        d = json.load(open(f)); o['slices_' + os.path.basename(f)] = json.dumps({k: (v if not isinstance(v, (list, dict)) else (len(v))) for k, v in d.items()} if isinstance(d, dict) else len(d))[:400]
    except Exception as ex: o['slices_err'] = str(ex)
# live-order scan in PR files
pat = re.compile(r'submit_order|place_order|create_order|orders\.create|/v2/orders|api\.alpaca\.markets(?!/)|live_trading|tradovate.*order', re.I)
scan = {}
for f in [R + r'\futures_signal.py', R + r'\scaling_ladder.py', R + r'\propfirm_gate.py', B + r'\run_daily.ps1', A + r'\omen-scaling-0926\build_nq_br_trades.py',
          B + r'\.claude\worktrees\omen-signal-0926\research\futures_signal.py', B + r'\.claude\worktrees\omen-signal-0926\run_daily.ps1']:
    if os.path.exists(f):
        s = open(f, errors='ignore').read().splitlines()
        scan[f.replace(B, '')] = [f'{i+1}: {l.strip()[:120]}' for i, l in enumerate(s) if pat.search(l)]
o['order_scan'] = scan
# Alpaca endpoint: paper or live (no secrets printed)
envp = B + r'\.env'
if os.path.exists(envp):
    for l in open(envp, errors='ignore'):
        if '=' not in l: continue
        k = l.split('=', 1)[0].strip()
        if 'BASE' in k.upper() or ('URL' in k.upper() and 'ALPACA' in k.upper()):
            v = l.split('=', 1)[1].strip().strip('"')
            o.setdefault('alpaca_url_keys', []).append(k + ' -> ' + ('paper' if 'paper' in v else ('LIVE' if 'alpaca.markets' in v else 'other')))
# run_daily.ps1 lines referencing futures_signal
for f in [B + r'\run_daily.ps1']:
    o['run_daily_futures_lines'] = [l.strip() for l in open(f, errors='ignore') if 'futures_signal' in l]
# tests
def run(cwd, t):
    p = subprocess.run([sys.executable, t], cwd=cwd, capture_output=True, text=True, timeout=900)
    tail = (p.stdout + p.stderr).strip().splitlines()[-3:]
    return dict(rc=p.returncode, tail=tail)
o['tests_main_checkout'] = {t: run(B, 'research\\' + t) for t in ['test_futures_signal.py', 'test_scaling_ladder.py', 'test_propfirm_gate.py', 'test_propfirm_luck_check.py']}
wt = B + r'\.claude\worktrees\omen-signal-0926'
o['tests_pr31_worktree'] = {t: run(wt, 'research\\' + t) for t in ['test_futures_signal.py']}
json.dump(o, open(A + r'\referee\referee_out2.json', 'w'), indent=1)
print(json.dumps(o, indent=1))
