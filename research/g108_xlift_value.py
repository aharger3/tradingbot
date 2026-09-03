"""Price the misfire slices on the SAME rig as g104: first size-gated candidate
of each of the 498 sessions, book fill and the g101 ladder replica."""
import json, os, sys
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import g86_honest_ceiling as g86
import g102_wait_for_the_open as g102

b = json.load(open(os.path.join(HERE, "bt2y_trades_retest_on.json"), encoding="utf-8"))
rows_all = b["trades"]
NS = b["meta"]["sessions"]
byday = g86.candidates(rows_all)
print("sessions", NS, "days with candidates", len(byday))

def build(pred):
    recs = []
    for d in sorted(byday):
        first = next((r for r in byday[d] if g102.sized(r) and pred(r)), None)
        if first is None: continue
        v = g102.replay(first)
        if v is None: continue
        bp, lp, mfe, state, al = v
        recs.append(dict(day=d, et=first["et"], sym=first["sym"],
                         book=bp, ladder=lp, runner=mfe >= 3.0, row=first))
    return recs

def show(label, recs):
    if not recs:
        print("%-38s n=0" % label); return
    bs = g86.stats([dict(day=x["day"], et=x["et"], sym=x["sym"], pnl=x["book"]) for x in recs], NS)
    ls = g86.stats([dict(day=x["day"], et=x["et"], sym=x["sym"], pnl=x["ladder"]) for x in recs], NS)
    run = 100*sum(1 for x in recs if x["runner"])/len(recs)
    print("%-38s n=%3d  book $%-5d ladder $%-5d  win %4.1f%%  green %d/%d  DD $%-7d  runner %4.1f%%"
          % (label, len(recs), bs["per_day"], ls["per_day"], ls["win_pct"],
             ls["months_green"], ls["months"], ls["worst_drawdown"], run))

allr = build(lambda r: True)
show("everything (control)", allr)
show("  of which lifted", [x for x in allr if "x-lift" in x["row"]["reason"]])
show("  of which NOT lifted", [x for x in allr if "x-lift" not in x["row"]["reason"]])
show("X_LIFT off (first non-lifted)", build(lambda r: "x-lift" not in r["reason"]))
show("X_LIFT off + chase veto", build(lambda r: "x-lift" not in r["reason"] and "chase" not in (r.get("tags") or [])))
show("chase veto only (g104 control)", build(lambda r: "chase" not in (r.get("tags") or [])))
