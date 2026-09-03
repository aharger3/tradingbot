"""Robustness of the f-sweep to the BOOK. The scaleladder ran on the current
research/bt2y_trades.json (2,437 traded, R31 loss-halt ON). DIRECTION.md quotes
a 2,595-trade post-T0 book. Re-run the f x trail grid with the 857 halted rows
restored (loss-halt OFF, 3,294 traded) and see if the conclusion moves.
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = Path(os.path.dirname(HERE))
for p in (str(ROOT), HERE):
    if p not in sys.path: sys.path.insert(0, p)
import importlib.util
spec = importlib.util.spec_from_file_location("repro", os.path.join(HERE, "g71_scaleladderverify_repro.py"))
# can't import (it calls main()); re-declare by exec of the module minus main()
src = open(os.path.join(HERE, "g71_scaleladderverify_repro.py")).read().replace("\nmain()\n", "\n")
g = {"__name__": "repro", "__file__": os.path.join(HERE, "g71_scaleladderverify_repro.py")}
exec(compile(src, "repro", "exec"), g)
ladder, bars_for = g["ladder"], g["bars_for"]
import p21_target_availability as p21
SIX = g["SIX"]

book = json.load(open(ROOT / "research/bt2y_trades.json"))
rows = [t for t in book["trades"] if t.get("traded") or t.get("status") == "halted"]
print("halt-OFF book: %d rows (traded %d + halted %d)"
      % (len(rows), sum(1 for t in rows if t.get("traded")),
         sum(1 for t in rows if t.get("status") == "halted")))
W = {0.0: (1/3, 1/3, 1/3, 0.0), 0.30: (0.7/3, 0.7/3, 0.7/3, 0.30)}
out = {}; inc = []
for t in rows:
    ei = t.get("entry_i"); bars = bars_for(t["sym"], t["day"])
    if ei is None or not bars or ei >= len(bars) - 1: continue
    long = t["dir"] == "call"
    lv = p21.levels_for_entry(t["sym"], t["day"], ei) or {}
    six = [px for k, px in lv.items() if k in SIX]
    risk = abs(t["entry"] - t["stop"])
    two = t["entry"] + 2*risk if long else t["entry"] - 2*risk
    beyond = [px for px in six if (px > t["entry"] if long else px < t["entry"])]
    t2 = two
    if beyond:
        nr = min(beyond) if long else max(beyond)
        t2 = min(two, nr) if long else max(two, nr)
    inc.append(t["r"])
    for f, ww in W.items():
        for tr in ("be", "1r", "struct"):
            out.setdefault((f, tr), []).append(ladder(bars, ei, t["entry"], t["stop"], long, ww, t2, tr)[0])
print("kept %d ; incumbent book r mean %+.4f" % (len(inc), sum(inc)/len(inc)))
for f in (0.0, 0.30):
    for tr in ("be", "1r", "struct"):
        v = [x for x in out[(f, tr)] if x is not None]
        print("f=%d%% / trail=%-6s n=%d win=%.1f%% mean=%+.4f"
              % (round(f*100), tr, len(v), 100*sum(1 for r in v if r>0)/sum(1 for r in v if r!=0), sum(v)/len(v)))
a = [x for x in out[(0.0,"be")] if x is not None]; b = [x for x in out[(0.30,"be")] if x is not None]
print("\nf 0%% -> 30%% (trail=be) delta = %+.4fR" % (sum(b)/len(b) - sum(a)/len(a)))
