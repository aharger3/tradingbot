"""Is downgrade._break_bar anchoring on the MOST RECENT crossing, and does that
make break_then_rejection / stale_retest unreachable?"""
import json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import polygon_feed as pf
from research import downgrade as dg
sys.path.insert(0, os.path.dirname(HERE))
from g105_fsm_trace import trace

b = json.load(open(os.path.join(HERE, "bt2y_trades_retest_on.json"), encoding="utf-8"))
rows = [r for r in b["trades"] if r["traded"] and r["setup"] == "break_and_retest"]
print("traded B&R rows:", len(rows), "| STALE_BARS =", dg.STALE_BARS, "| REJECT_BARS =", dg.REJECT_BARS)
by = collections.defaultdict(list)
for r in rows: by[(r["sym"], r["day"])].append(r)
C = collections.Counter(); D = collections.Counter()
for k, rr in sorted(by.items()):
    try: rth = pf.rth(pf.fetch_day(*k))
    except Exception: continue
    if not rth: continue
    bars = [dict(o=c.open, h=c.high, l=c.low, c=c.close, v=c.volume) for c in rth]
    for r in rr:
        i = r["entry_i"]
        if i >= len(bars): continue
        lv, is_long = r["level_px"], r["dir"] == "call"
        br = dg._break_bar(bars, i, lv, is_long)
        C["rows"] += 1
        if br is None: C["break_bar=None"] += 1; continue
        C["i-break_bar=%d" % min(i - br, 9)] += 1
        rt = dg._retest_bar(bars, i, lv, is_long, br)
        if rt is None: C["retest=None(no_retest)"] += 1
        else:
            D["retest-break=%d" % min(rt - br, 9)] += 1
            if (rt - br) > dg.STALE_BARS: C["stale_retest TRUE"] += 1
        if dg.break_then_rejection(bars, i, lv, is_long): C["break_then_rejection TRUE"] += 1
        # the geometry break_then_rejection is meant to catch, per the ordered FSM
        t = trace(rth[:i+1], lv, is_long)
        if t.get("pass") and t["wrongside_after_leave"]:
            C["FSM: wrong-side close after the leave bar"] += 1
        if t.get("pass") and t["break_idx"] is not None:
            C["FSM break bars back=%d" % min((t["n"]-1-t["break_idx"]), 11)] += 1
print(json.dumps(dict(C), indent=1, sort_keys=True))
print(json.dumps(dict(D), indent=1, sort_keys=True))
