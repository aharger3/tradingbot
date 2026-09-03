"""G7.1 / weeks -- ADVERSARIAL verification of the 'every week green is
arithmetically out of reach' claim in research/g71_weeks.md sec.4b.

Re-derives every number from research/_g71_weeks.json + research/bt2y_trades.json
independently, then stress-tests the two assumptions the inversion rests on:
  (i)  P(green week) = Phi(week_sharpe)   [normal approx]
  (ii) corr_drag is a constant 1.244 as n scales 6.1x
Read-only. Writes research/_g71_weeksverify_adv.json.
"""
import json, math, statistics, collections
from pathlib import Path
R = Path(__file__).resolve().parent.parent

def phi(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
def inv_phi(p):
    lo,hi=-10.,10.
    for _ in range(300):
        m=(lo+hi)/2
        if phi(m)<p: lo=m
        else: hi=m
    return (lo+hi)/2

d=json.loads((R/"research/_g71_weeks.json").read_text())
book=json.loads((R/"research/bt2y_trades.json").read_text())
rows=[r for r in book["trades"] if r["status"]=="fired" and r["traded"]]
W=d["meta"]["weeks"]; out={}

# ---- 1. reproduce the requirement table from scratch -----------------------
mu=statistics.fmean(r["r"] for r in rows); sg=statistics.pstdev([r["r"] for r in rows])
def isow(s):
    import datetime; y,w,_=datetime.date.fromisoformat(s).isocalendar(); return "%d-W%02d"%(y,w)
wk=collections.defaultdict(float); wn=collections.Counter()
for r in rows: wk[isow(r["day"])]+=r["r"]; wn[isow(r["day"])]+=1
weeks=sorted(wk); ser=[wk[w] for w in weeks]
mw=statistics.fmean(ser); sdw=statistics.pstdev(ser); tpw=len(rows)/len(weeks)
drag=sdw/(sg*math.sqrt(tpw))
repro={"n_trades":len(rows),"weeks":len(weeks),"mu":round(mu,4),"sigma":round(sg,4),
 "mu_over_sigma":round(mu/sg,4),"tpw":round(tpw,2),"mean_week":round(mw,4),
 "sd_week":round(sdw,4),"week_sharpe":round(mw/sdw,4),"corr_drag":round(drag,3),
 "green_weeks":sum(1 for v in ser if v>0),"green_pct":round(sum(1 for v in ser if v>0)/len(ser)*100,2)}
for want in (.5,.8,.95):
    z=inv_phi(want**(1/len(weeks))); n=(z*drag*sg/mu)**2
    repro["req_%.0f"%(want*100)]={"p_wk":round(want**(1/len(weeks))*100,4),"z":round(z,3),
      "n_need":round(n,1),"x_vol":round(n/tpw,1),"mu_sig_need":round(z*drag/math.sqrt(tpw),4)}
out["independent_repro"]=repro

# ---- 2. is Phi(week_sharpe) calibrated? ------------------------------------
cal=[]
for r in d["policies"]+d["week_policies"]+d["capn_curve"]:
    obs=r["green_week_pct"]/100.
    if 0<obs<1:
        cal.append({"policy":r["policy"],"tpw":r["trades_per_week"],"drag":r["corr_drag"],
          "sharpe":r["week_sharpe"],"model_p":round(phi(r["week_sharpe"])*100,2),
          "obs_p":r["green_week_pct"],"err_pts":round(r["green_week_pct"]-phi(r["week_sharpe"])*100,2),
          "implied_sharpe":round(inv_phi(obs),4),
          "sharpe_ratio_obs_over_model":round(inv_phi(obs)/r["week_sharpe"],3) if r["week_sharpe"]>0 else None})
out["calibration"]=sorted(cal,key=lambda x:-abs(x["err_pts"]))

# ---- 3. drag is not constant: regress drag on tpw --------------------------
pts=[(r["trades_per_week"],r["corr_drag"]) for r in d["policies"]+d["capn_curve"]
     if r["corr_drag"] and "ORACLE" not in r["policy"] and "P5" not in r["policy"]]
xs=[math.log(a) for a,_ in pts]; ys=[b for _,b in pts]
n=len(xs); mx=statistics.fmean(xs); my=statistics.fmean(ys)
sl=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/sum((x-mx)**2 for x in xs); ic=my-sl*mx
out["drag_vs_volume"]={"points":[[round(a,2),b] for a,b in sorted(pts)],
  "fit":"drag = %.4f + %.4f*ln(tpw)"%(ic,sl),"slope":round(sl,4),
  "drag_at_141.5":round(ic+sl*math.log(141.5),3),"drag_at_23.2":round(ic+sl*math.log(23.21),3)}
# re-solve n with drag(n)
z=inv_phi(.5**(1/W)); nn=141.5
for _ in range(200):
    dg=max(.3,ic+sl*math.log(nn)); nn=(z*dg*sg/mu)**2
out["drag_vs_volume"]["n_need_with_drag_of_n"]=round(nn,1)
out["drag_vs_volume"]["x_vol_with_drag_of_n"]=round(nn/tpw,1)

# ---- 4. does sqrt(n) scaling survive empirically on THIS book? -------------
# Aggregate the shipped daily-R series into blocks of k sessions. In the iid
# model a k*5-session block has n = k*tpw trades, so P(block green) should be
# Phi(sqrt(k)*week_sharpe). Test k = 1..6 (6x is exactly the claim's 6.1x).
dayr=collections.defaultdict(float)
for r in rows: dayr[r["day"]]+=r["r"]
days=sorted(dayr); dser=[dayr[x] for x in days]
blocks=[]
for k in (1,2,3,4,5,6,8):
    L=5*k; segs=[sum(dser[i:i+L]) for i in range(0,len(dser)-L+1,L)]
    g=sum(1 for v in segs if v>0)
    blocks.append({"k_weeks":k,"blocks":len(segs),"green":g,
      "obs_p":round(g/len(segs)*100,2),
      "model_p":round(phi(math.sqrt(k)*repro["week_sharpe"])*100,2),
      "err_pts":round(g/len(segs)*100-phi(math.sqrt(k)*repro["week_sharpe"])*100,2),
      "sd_obs":round(statistics.pstdev(segs),3),
      "sd_iid_pred":round(sdw*math.sqrt(k),3)})
out["block_scaling_test"]=blocks

# ---- 5. candidate-rate audit: what does the window actually produce? -------
st=collections.Counter(r["status"] for r in book["trades"])
sess=len({r["day"] for r in book["trades"]})
fired_any=st["fired"]+st["halted"]
out["candidate_rate_audit"]={
 "sessions_in_book":sess,
 "claim_says_candidates_per_day":6.64,
 "counted_stream_(traded+halted)":3294,"counted_per_day":round(3294/496,2),
 "fired_or_halted_signals":fired_any,"fired_any_per_day":round(fired_any/sess,2),
 "fired_any_per_week":round(fired_any/W,2),
 "plus_skipped_tight_stop":st["skipped_tight_stop"],
 "pre_stopfilter_candidates_per_week":round((fired_any+st["skipped_tight_stop"])/W,2),
 "all_signal_rows":len(book["trades"]),"all_rows_per_week":round(len(book["trades"])/W,1),
 "fired_but_not_traded_concurrency_blocked":st["fired"]-2437}

# ---- 6. empirical P(all 105 weeks green) by resampling the real weeks ------
import random
random.seed(7)
emp={}
for r in d["policies"]+d["week_policies"]:
    s=[v for _w,v,_c in r["weekly_series"]]
    hits=sum(1 for _ in range(20000) if all(random.choice(s)>0 for _ in range(W)))
    emp[r["policy"]]={"obs_green_pct":r["green_week_pct"],
      "p_all_105_green_iid_resample":round(hits/20000,5),
      "p_all_105_green_binom":round((r["green_week_pct"]/100)**W,6)}
out["empirical_p_all_green"]=emp
(R/"research/_g71_weeksverify_adv.json").write_text(json.dumps(out,indent=1))
print(json.dumps({k:out[k] for k in ("independent_repro","drag_vs_volume","block_scaling_test","candidate_rate_audit")},indent=1))
print("\nWORST-CALIBRATED ROWS:")
for c in out["calibration"][:8]: print(" ",json.dumps(c))
print("\nP(all 105 green):")
for k,v in list(emp.items()): print("  %-40s obs=%5.1f%% p_all=%s"%(k,v["obs_green_pct"],v["p_all_105_green_iid_resample"]))
