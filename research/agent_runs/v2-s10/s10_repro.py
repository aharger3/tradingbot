"""v2-s10: reproduce g88 POST_floor exactly, then honest-fill arms. Measurement only."""
import os, sys, json, random
from collections import defaultdict, Counter
from pathlib import Path
ROOT = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research"))
os.chdir(ROOT)
from research import g80_ordertype_grid as G
import signal_runner as sr
import importlib.util
spec = importlib.util.spec_from_file_location("g88", ROOT/"research"/"g88_level_limit.py")
g88 = importlib.util.module_from_spec(spec); spec.loader.exec_module(g88)
OUT = ROOT/"research"/"agent_runs"/"v2-s10"
BOOK = ROOT/"research"/"bt2y_trades_retest_on.json"
TICK = 0.01; COMM = 0.005   # $/share per side
def tt_touch(bars, lvl, long, j0, j1):
    for j in range(max(j0,0), min(j1,len(bars))):
        c = bars[j]
        if long and c.low < lvl - TICK/2: return j, min(lvl, c.open)
        if (not long) and c.high > lvl + TICK/2: return j, max(lvl, c.open)
    return None, None
book = json.load(open(BOOK, encoding="utf-8"))
meta, allrows = book["meta"], book["trades"]
n_days = meta["sessions"]; all_days = sorted({r["day"] for r in allrows})
universe = {i:r for i,r in enumerate(allrows) if (r.get("traded") or r["status"]=="halted")}
keys = sorted(universe, key=lambda i:(allrows[i]["day"],allrows[i]["et"],allrows[i]["sym"],i))
ARMS = ["POST_floor", "POST_tradethru", "POST_nextopen"]
priced = {a:{} for a in ARMS}; nof = {a:Counter() for a in ARMS}
for n,k in enumerate(keys):
    r = universe[k]
    bars,pdh,pdl,pmh,pml = G.day_pack(r["sym"], r["day"])
    if not bars or r["entry_i"] >= len(bars): continue
    long = r["dir"]=="call"; cut = G.cutoff_idx(bars)
    if r["entry_i"]+1 >= min(cut, len(bars)-1): continue
    ent = {}
    j,px = G.limit_touch(bars, r["level_px"], long, r["entry_i"]+1, cut)
    ent["POST_floor"] = (j,px) if (j is not None and j < len(bars)-1) else (None,None)
    j2,px2 = tt_touch(bars, r["level_px"], long, r["entry_i"]+1, cut)
    ent["POST_tradethru"] = (j2,px2) if (j2 is not None and j2 < len(bars)-1) else (None,None)
    # next-open: touch bar j confirms the retest, market in at bars[j+1].open (live all of j+1 -> fill_i=j)
    if j is not None and j+1 < min(cut, len(bars)-1):
        ent["POST_nextopen"] = (j, bars[j+1].open)
    else: ent["POST_nextopen"] = (None,None)
    for a in ARMS:
        fi,p = ent[a]
        if fi is None: nof[a]["nofill"] += 1; continue
        if a=="POST_nextopen":
            # stop must still be beyond entry; if open already through structural stop, skip (no trade)
            if (long and p <= r["stop"]) or ((not long) and p >= r["stop"]): nof[a]["opened_thru_stop"]+=1; continue
            fr = g88.floored_row(r, p, bars, fi+1, long)
        else:
            fr = g88.floored_row(r, p, bars, fi, long)
        res = G.run_trade(fr, bars, fi, p, pdh,pdl,pmh,pml, move_stop_to_entry_bar=False)
        if res is None: nof[a]["risk_collapsed"]+=1; continue
        priced[a][k] = res
cand = defaultdict(list)
for k in keys:
    r = allrows[k]
    if (r["status"]=="fired" and r.get("traded")) or r["status"]=="halted": cand[r["day"]].append(k)
for d in cand: cand[d].sort(key=lambda i:(allrows[i]["et"],allrows[i]["sym"],i))
def stats(rows, pnlkey):
    byd = {d:0.0 for d in all_days}
    for x in rows: byd[x["day"]] += x[pnlkey]
    v = [byd[d] for d in all_days]; tot = sum(v)
    h1 = [byd[d] for d in all_days if d < "2025-09-01"]; h2 = [byd[d] for d in all_days if d >= "2025-09-01"]
    bym = defaultdict(float)
    for d in all_days: bym[d[:7]] += byd[d]
    rng = random.Random(7); obs = tot; ge = 0
    for _ in range(2000):
        s = sum(x if rng.random()<.5 else -x for x in v)
        ge += s >= obs
    wins = sum(1 for x in rows if x[pnlkey] > 0)
    return {"trades":len(rows),"per_day":round(tot/n_days,1),"win%":round(100*wins/max(1,len(rows)),1),
            "meanR":round(tot/max(1,len(rows))/1000,3),"green":"%d/%d"%(sum(1 for m in bym.values() if m>0),len(bym)),
            "H1":round(sum(h1)/max(1,len(h1)),1),"H2":round(sum(h2)/max(1,len(h2)),1),"p_signflip":round(ge/2000,3)}
out = {"book":BOOK.name,"sessions":n_days,"candidates":len(keys),"arms":{}}
for a in ARMS:
    one = []
    for d in sorted(cand):
        for k in cand[d]:
            res = priced[a].get(k)
            if res is not None and res["sizeable"]:
                res = dict(res); sh = 1000.0/res["risk"]
                res["cost"] = sh*(2*TICK + 2*COMM); res["net"] = res["pnl"] - res["cost"]
                one.append(res); break
    g = stats(one, "pnl"); nt = stats(one, "net")
    out["arms"][a] = {"gross":g, "net":nt, "median_cost":round(sorted(x["cost"] for x in one)[len(one)//2],1) if one else 0,
                      "nofill":dict(nof[a])}
    print(a, "GROSS", g, "\n   NET", nt, "medcost", out["arms"][a]["median_cost"], dict(nof[a]), flush=True)
json.dump(out, open(OUT/"s10_repro.json","w"), indent=1)
