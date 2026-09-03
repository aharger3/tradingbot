"""G7.1 adversarial verify of the scarface recall claim. Read-only; writes one JSON."""
import json, sys
from pathlib import Path
from collections import Counter
ROOT = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"research"))
from research.t4_engine_recall import run_day

recs = [json.loads(l) for l in open(ROOT/"research/g71_scarface_candidates.jsonl", encoding='utf-8')]
cand = [r for r in recs if r["source"] == "Scarface" and r["in_backtest_universe"]
        and r["tier"] in ("T1","T2")]
cand.sort(key=lambda r: r["day"])
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 365
cand = cand[:LIMIT]
out = []
for i, r in enumerate(cand):
    try:
        entries, allsigs, raw = run_day(r["symbol"], r["day"])
    except Exception as e:
        out.append(dict(card_id=r["card_id"], tier=r["tier"], dir=r["direction"],
                        day=r["day"], err=repr(e)[:120])); continue
    out.append(dict(card_id=r["card_id"], symbol=r["symbol"], day=r["day"],
                    tier=r["tier"], dir=r["direction"],
                    no_archive=(entries is None),
                    n_fired=len(entries or []), n_sig=len(allsigs or []),
                    n_raw=len(raw or []),
                    fired_dirs=sorted({e["direction"] for e in (entries or [])}),
                    sig_dirs=sorted({s["direction"] for s in (allsigs or [])}),
                    grades=sorted({e["grade"] for e in (entries or [])})))
    if i % 25 == 0: print(i, flush=True)
json.dump(out, open(ROOT/"research/_g71_scarfaceverify_recall.json","w"), indent=0)
print("done", len(out))
