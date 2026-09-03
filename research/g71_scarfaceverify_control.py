"""Control arm the claim lacks: OMEN's base fire rate on RANDOM in-universe symbol-days,
matched to the Scarface sample's symbol mix and date range. Read-only."""
import json, sys, random, os
from pathlib import Path
from collections import Counter
ROOT = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"research"))
from research.t4_engine_recall import run_day

recs = [json.loads(l) for l in open(ROOT/"research/g71_scarface_candidates.jsonl", encoding='utf-8')]
scar = [r for r in recs if r["source"]=="Scarface" and r["in_backtest_universe"] and r["tier"] in ("T1","T2")]
scar.sort(key=lambda r: r["day"])
target = scar[:200]
scar_days = {(r["symbol"], r["day"]) for r in scar}
allscar_days = {(r["symbol"], r["day"]) for r in recs}   # any channel, any tier
symmix = Counter(r["symbol"] for r in target)
lo, hi = target[0]["day"], target[-1]["day"]

arch = ROOT/"data_archive"
pool = []
for sym, k in symmix.items():
    days = sorted(p.stem for p in (arch/sym).glob("*.csv")) if (arch/sym).is_dir() else []
    days = [d for d in days if lo <= d <= hi and (sym,d) not in allscar_days]
    random.seed((hash(sym) & 0xffff) + 777)
    random.shuffle(days)
    pool += [(sym,d) for d in days[:k]]
print(f"control n={len(pool)} vs target {len(target)}; range {lo}..{hi}")

C = Counter()
for i,(sym,day) in enumerate(pool):
    try: entries, sigs, raw = run_day(sym, day)
    except Exception: C["err"] += 1; continue
    C["n"] += 1
    if entries is None: C["no_archive"] += 1
    if entries: C["fired"] += 1
    if sigs: C["anysig"] += 1
    if i % 50 == 0: print(i, flush=True)
n = C["n"]
print(f"CONTROL: n={n} fired={C['fired']} ({C['fired']/n:.1%}) anysig={C['anysig']} ({C['anysig']/n:.1%}) err={C['err']}")
