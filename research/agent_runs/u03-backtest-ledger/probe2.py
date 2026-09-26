import gzip,json,os,glob
os.chdir(r"C:\Users\aharg\Desktop\Projects\tradingbot\research")
for f in ["tape/fillarms_next_open_core11.json.gz","tape/reconcile_fwd_8_universe_29_to_11.json.gz","tape/g88_post_floor_trades.json.gz","tape/r2ref_simd_next_open_blind2r_real_engine.json.gz","bt2y_trades.json.gz"]:
    d=json.load(gzip.open(f)); print("==",f,type(d).__name__)
    if isinstance(d,dict):
        for k,v in d.items():
            print(" ",k,type(v).__name__, json.dumps(v)[:600] if not isinstance(v,list) else len(v))
        t=d.get("trades") or []
    else: t=d
    if t: print("  T0",json.dumps(t[0])[:700])
for r in [r"C:\Users\aharg\Desktop\Projects\TradingBot v2.1-hardening", r"C:\Users\aharg\Desktop\Projects\futuresbot"]:
    print("#####",r)
    for root,ds,fs in os.walk(r):
        ds[:]=[x for x in ds if x not in (".git","node_modules","venv",".venv","__pycache__","site-packages")]
        for x in fs:
            p=os.path.join(root,x)
            print(os.path.relpath(p,r), os.path.getsize(p))
