"""G7.1/scarface: does OMEN fire on the days a professional actually traded?

Scarface's in-window alert days are a SECOND LABELLER's opinion that a tradeable
setup existed. Austin's S-day recall sample is 34 days; this is ~900. If OMEN is
silent on a Scarface day, that is a recall miss from an independent source.
Read-only. Writes nothing but stdout."""
import json, os, sys
from pathlib import Path
from collections import Counter
ROOT = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"research"))
from research.t4_engine_recall import run_day
import universe as U

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 250
recs = [json.loads(l) for l in open(ROOT/"research/g71_scarface_candidates.jsonl", encoding='utf-8')]
# Scarface only, in the backtest universe, and a real trade signal (T1/T2 = direction known)
cand = [r for r in recs if r["source"] == "Scarface" and r["in_backtest_universe"]
        and r["tier"] in ("T1","T2")]
cand.sort(key=lambda r: r["day"])
cand = cand[:LIMIT]
print(f"Scarface T1+T2 in universe: {len([r for r in recs if r['source']=='Scarface' and r['in_backtest_universe'] and r['tier'] in ('T1','T2')])}; testing {len(cand)}")

C = Counter(); silent = []
for r in cand:
    try:
        entries, _s, _raw = run_day(r["symbol"], r["day"])
    except Exception as e:
        C["error"] += 1; continue
    entries = entries or []
    C["tested"] += 1
    if entries:
        C["fired"] += 1
        dirs = {str(e.get("direction") or e.get("side") or "") for e in entries if isinstance(e, dict)}
        if r["direction"] and any(r["direction"][0].lower() in d.lower()[:1] or
                                  (r["direction"]=="call" and "long" in d.lower()) or
                                  (r["direction"]=="put" and "short" in d.lower()) for d in dirs):
            C["fired_same_dir"] += 1
    else:
        C["silent"] += 1; silent.append(r["card_id"])
n = C["tested"]
print(f"tested={n} errors={C['error']}")
print(f"  OMEN fired at least once : {C['fired']}  ({C['fired']/max(1,n)*100:.1f}%)")
print(f"  OMEN SILENT              : {C['silent']}  ({C['silent']/max(1,n)*100:.1f}%)")
print(f"  fired in Scarface's direction: {C['fired_same_dir']} ({C['fired_same_dir']/max(1,n)*100:.1f}%)")
print("silent sample:", silent[:20])
