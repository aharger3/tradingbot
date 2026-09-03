"""What a working break_then_rejection is worth: veto the day's first candidate
when a bar CLOSED back through the level between the leave bar and the entry bar,
and take the next size-gated candidate instead. Same rig as g104."""
import json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import g86_honest_ceiling as g86, g102_wait_for_the_open as g102, polygon_feed as pf
sys.path.insert(0, os.path.dirname(HERE))
from g105_fsm_trace import trace

b = json.load(open(os.path.join(HERE, "bt2y_trades_retest_on.json"), encoding="utf-8"))
NS = b["meta"]["sessions"]; byday = g86.candidates(b["trades"])
cache = {}
def gave_it_back(r):
    if r["setup"] != "break_and_retest": return False
    k = (r["sym"], r["day"])
    if k not in cache:
        try: cache[k] = pf.rth(pf.fetch_day(*k))
        except Exception: cache[k] = None
    rth = cache[k]
    if not rth or r["entry_i"] >= len(rth): return False
    t = trace(rth[:r["entry_i"]+1], r["level_px"], r["dir"] == "call")
    return bool(t.get("pass") and t["wrongside_after_leave"])

def build(pred):
    out = []
    for d in sorted(byday):
        first = next((r for r in byday[d] if g102.sized(r) and pred(r)), None)
        if first is None: continue
        v = g102.replay(first)
        if v is None: continue
        bp, lp, mfe, _s, _a = v
        out.append(dict(day=d, et=first["et"], sym=first["sym"], book=bp, ladder=lp, runner=mfe>=3.0))
    return out
def show(lbl, recs):
    bs = g86.stats([dict(day=x["day"],et=x["et"],sym=x["sym"],pnl=x["book"]) for x in recs], NS)
    ls = g86.stats([dict(day=x["day"],et=x["et"],sym=x["sym"],pnl=x["ladder"]) for x in recs], NS)
    print("%-42s n=%3d book $%-5d ladder $%-5d win %4.1f%% green %d/%d DD $%-7d runner %4.1f%%"
          % (lbl, len(recs), bs["per_day"], ls["per_day"], ls["win_pct"], ls["months_green"],
             ls["months"], ls["worst_drawdown"], 100*sum(1 for x in recs if x["runner"])/len(recs)))
show("control (first size-gated)", build(lambda r: True))
show("veto 'broke then gave it back'", build(lambda r: not gave_it_back(r)))
show("  + chase veto", build(lambda r: not gave_it_back(r) and "chase" not in (r.get("tags") or [])))
