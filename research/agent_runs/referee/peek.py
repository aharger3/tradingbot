import json,glob,os
B=r'C:\Users\aharg\Desktop\Projects\tradingbot\research'
for f in [r'agent_runs\t01-orb5\grid_fut.json', r'agent_runs\t01-orb5\gate_top3.json', r'agent_runs\t04-his-eye-test\eye_test.json']+glob.glob(B+r'\agent_runs\t03-one-candle\*.json'):
    p=f if os.path.isabs(f) else os.path.join(B,f)
    try:
        d=json.load(open(p))
    except Exception as e:
        print(p,'ERR',e); continue
    print('##',p, type(d).__name__, (list(d)[:15] if isinstance(d,dict) else len(d)))
    x = d if isinstance(d,list) else next(iter(d.values()))
    print('  sample', json.dumps(x[0] if isinstance(x,list) else x)[:400])
print(os.path.exists(B+r'\g88_level_limit.py'), glob.glob(B+r'\g88_level_limit*'))
