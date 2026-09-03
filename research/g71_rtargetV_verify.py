"""ADVERSARIAL VERIFY of track `rtarget`'s central claim.

Re-implements the candidate stream and the causal one-position walk from the
SPEC in g71_firsts_policy.py's docstring -- deliberately WITHOUT importing that
module -- and re-derives P1/P2/P4 mean R per trade, trades per day, R per day,
dollars per day, and the risk-normalised comparison the claim omits.
Read-only on the book. Touches no engine file.
"""
import json, math, statistics, sys
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
book = json.loads((ROOT / "research/bt2y_trades.json").read_text())
meta, trades = book["meta"], book["trades"]
print("book", meta["generated"], "sessions", meta["sessions"],
      "signals", meta["signals"], "traded", meta["traded"])

ekey = lambda r: (r["entry_i"], r["et"], r["sym"])
xkey = lambda r: (r["entry_i"] + r["bars"], r["et"], r["sym"])

counted = [r for r in trades
           if (r["status"] == "fired" and r["traded"]) or r["status"] == "halted"]
by_day = defaultdict(list)
for r in counted:
    by_day[r["day"]].append(r)
for d in by_day:
    by_day[d].sort(key=ekey)
days = sorted(by_day)
print("counted rows", len(counted), "candidate days", len(days),
      "sessions in meta", meta["sessions"])

def walk(cands, stop):
    taken, free = [], None
    wins = losses = scr = 0
    cum = 0.0
    for c in cands:
        if stop(len(taken), wins, losses, scr, cum):
            break
        if free is not None and ekey(c) < free:
            continue
        taken.append(c); free = xkey(c)
        o = c["out"]
        if o == "win": wins += 1
        elif o == "loss": losses += 1
        else: scr += 1
        cum += c["r"]
    return taken

POL = {
    "P1": lambda n, w, l, s, cum: n >= 1,
    "P2": lambda n, w, l, s, cum: w >= 1 or l >= 2,
    "P4": lambda n, w, l, s, cum: cum > 0 or l >= 3,
}

res = {}
for name, stop in POL.items():
    dayr, dayr_cap, rows = [], [], []
    for d in days:
        tk = walk(by_day[d], stop)
        dayr.append(sum(x["r"] for x in tk))
        dayr_cap.append(sum(min(x["r"], 2.0) for x in tk))
        rows.extend(tk)
    outs = Counter(x["out"] for x in rows)
    dec = outs["win"] + outs["loss"]
    wins = [x["r"] for x in rows if x["r"] > 0]
    res[name] = dict(
        n=len(rows), win=round(outs["win"]/dec*100, 2),
        mean_r_trade=round(statistics.mean(x["r"] for x in rows), 4),
        mean_r_day=round(statistics.mean(dayr), 4),
        mean_r_day_cap=round(statistics.mean(dayr_cap), 4),
        sd_day=round(statistics.pstdev(dayr), 4),
        sd_day_cap=round(statistics.pstdev(dayr_cap), 4),
        tpd=round(len(rows)/len(days), 4),
        avg_winner=round(statistics.mean(wins), 4),
        total=round(sum(dayr), 2), total_cap=round(sum(dayr_cap), 2),
        dayr=dayr, dayr_cap=dayr_cap)

print()
hdr = f"{'pol':4} {'n':>5} {'win%':>6} {'R/trade':>8} {'trades/day':>10} {'R/day':>8} {'$ /day':>8} {'sd/day':>7} {'R/day cap2':>10} {'$/day cap':>9}"
print(hdr)
for k in ("P1", "P2", "P4"):
    r = res[k]
    print(f"{k:4} {r['n']:5d} {r['win']:6.2f} {r['mean_r_trade']:+8.4f} "
          f"{r['tpd']:10.4f} {r['mean_r_day']:+8.4f} {r['mean_r_day']*1000:8.0f} "
          f"{r['sd_day']:7.4f} {r['mean_r_day_cap']:+10.4f} {r['mean_r_day_cap']*1000:9.0f}")

print("\n-- identity check: R/trade * trades/day == R/day ?")
for k in ("P1", "P2", "P4"):
    r = res[k]
    print(f"  {k}: {r['mean_r_trade']:+.4f} * {r['tpd']:.4f} = "
          f"{r['mean_r_trade']*r['tpd']:+.4f}  vs R/day {r['mean_r_day']:+.4f}")

print("\n-- the claim's headline pair")
p1, p4 = res["P1"], res["P4"]
print(f"  P1 mean R/trade {p1['mean_r_trade']:+.4f}  P4 {p4['mean_r_trade']:+.4f}")
print(f"  P1 $/day {p1['mean_r_day']*1000:.0f}  P4 {p4['mean_r_day']*1000:.0f}  "
      f"uplift {(p4['mean_r_day']/p1['mean_r_day']-1)*100:.1f}%")

print("\n-- RISK-NORMALISED: the risk unit is a free variable (model docstring).")
print("   P4 deploys %.4f R of risk per day, P1 deploys %.4f. Equalise the risk"
      % (p4['tpd'], p1['tpd']))
print("   deployed per day by sizing P1 up %.3fx:" % (p4['tpd']/p1['tpd']))
scale = p4['tpd']/p1['tpd']
print(f"   P1 at {scale:.3f}R per trade: $/day = {p1['mean_r_day']*scale*1000:.0f}  "
      f"vs P4 $897-scale {p4['mean_r_day']*1000:.0f}  -> "
      f"{'P1 WINS' if p1['mean_r_day']*scale > p4['mean_r_day'] else 'P4 wins'} "
      f"by {abs(p1['mean_r_day']*scale/p4['mean_r_day']-1)*100:.1f}%")

print("\n-- VOLATILITY-NORMALISED (equal sd of daily $): the honest 'more money' size")
for k in ("P1", "P2", "P4"):
    r = res[k]
    print(f"   {k}: mean/sd per day = {r['mean_r_day']/r['sd_day']:.4f}")
s1, s4 = p1['mean_r_day']/p1['sd_day'], p4['mean_r_day']/p4['sd_day']
print(f"   P4 advantage at EQUAL daily volatility: {(s4/s1-1)*100:+.1f}%  "
      f"(claim advertises +47%)")

print("\n-- MAX-DRAWDOWN-NORMALISED, realised 2y path (equity in R, EOD)")
def maxdd(seq):
    cum = peak = dd = 0.0
    for v in seq:
        cum += v; peak = max(peak, cum); dd = max(dd, peak-cum)
    return dd
for k in ("P1", "P2", "P4"):
    r = res[k]
    dd = maxdd(r['dayr'])
    print(f"   {k}: total {r['total']:+.1f}R  maxDD {dd:.2f}R  "
          f"return/DD {r['total']/dd:.2f}")
d1, d4 = maxdd(p1['dayr']), maxdd(p4['dayr'])
print(f"   P4 advantage at EQUAL max drawdown: "
      f"{((p4['total']/d4)/(p1['total']/d1)-1)*100:+.1f}%")

print("\n-- UNDER THE LIVE EXIT (every winner clipped at 2.0R -- the report's own")
print("   section 2 says this is the exit he owns and the uncapped row 'describes")
print("   a backtest exit he does not own')")
for k in ("P1", "P2", "P4"):
    r = res[k]
    print(f"   {k}: $/day capped {r['mean_r_day_cap']*1000:.0f}  "
          f"(uncapped {r['mean_r_day']*1000:.0f})")
print(f"   P4 vs P1 uplift on the LIVE exit: "
      f"{(p4['mean_r_day_cap']/p1['mean_r_day_cap']-1)*100:+.1f}%")
print(f"   P1 sized to P4's deployed risk, live exit: "
      f"${p1['mean_r_day_cap']*scale*1000:.0f} vs P4 ${p4['mean_r_day_cap']*1000:.0f}")

print("\n-- THE ARITHMETIC IN EVIDENCE OFFERED (report section 3)")
for w, m in ((0.5486, 2.0), (0.55, 2.0), (0.5486, 2.0)):
    pass
w, m = 0.5486, 2.0
T = (m + (1 - w)) / w
print(f"   mean R = wT-(1-w) => T = (2.0 + {1-w:.4f})/{w} = {T:.4f}R")
print(f"   report says 5.455R. (2.0+0.4514)/0.5486 = {2.4514/0.5486:.4f}. "
      f"5.455 = (2.0+1.0)/0.55 = {(2.0+1.0)/0.55:.4f} -- the (1-w) numerator")
print(f"   was replaced by 1.0. Script's own Scenario('gate') computes "
      f"T = (2.0+0.45)/0.55 = {(2.0+0.45)/0.55:.4f}, contradicting its own note "
      f"string 'requires a 5.455R average WINNER'.")
print(f"   measured P1 average winner {p1['avg_winner']:.4f}R -> real gap "
      f"{T-p1['avg_winner']:.4f}R, not the 3.5R the report states.")
print(f"   P1 win rate {p1['win']:.2f}% vs gate 55.0% -> "
      f"{'MEETS' if p1['win']>=55 else 'MISSES'} the win-rate half.")

print("\n-- PAIRED SIGNIFICANCE of the headline gap, over the 496 shared days")
import statistics as st
d = [a-b for a, b in zip(res['P4']['dayr'], res['P1']['dayr'])]
n = len(d); m = st.mean(d); se = st.pstdev(d)/math.sqrt(n)
print(f"   P4-P1 per day: mean {m:+.4f}R  sd {st.pstdev(d):.4f}  se {se:.4f}  "
      f"t={m/se:.2f}  95%CI [{m-1.96*se:+.4f}, {m+1.96*se:+.4f}]R/day")
dc = [a-b for a, b in zip(res['P4']['dayr_cap'], res['P1']['dayr_cap'])]
mc = st.mean(dc); sec = st.pstdev(dc)/math.sqrt(n)
print(f"   LIVE EXIT (2R cap) P4-P1: mean {mc:+.4f}R  se {sec:.4f}  t={mc/sec:.2f}  "
      f"95%CI [{mc-1.96*sec:+.4f}, {mc+1.96*sec:+.4f}]R/day  "
      f"{'SIGNIFICANT' if abs(mc)>1.96*sec else 'INSIDE NOISE'}")
dr = [a*1.7359-b for a, b in zip(res['P1']['dayr'], res['P4']['dayr'])]
mr = st.mean(dr); ser = st.pstdev(dr)/math.sqrt(n)
print(f"   risk-matched P1x1.736 - P4: mean {mr:+.4f}R  se {ser:.4f}  t={mr/ser:.2f}")
print("\n-- book identity: what the report's parametric baseline row assumes vs the")
print("   book it actually loaded")
tr = [r for r in trades if r.get('traded')]
oc = Counter(r['out'] for r in tr)
print(f"   loaded book traded rows: n={len(tr)} win={oc['win']/(oc['win']+oc['loss'])*100:.2f}% "
      f"meanR={st.mean(r['r'] for r in tr):+.4f}")
print("   DIRECTION.md money row it cites: n=2,595 win=43.1% meanR=+0.5481")
