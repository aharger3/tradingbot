"""SUPERSEDED 2026-08-29 by research/g72_recall278_paired.py (key recall278).

This file re-did the power maths at n = 34 S cards, on a recall constant of
23/34 that came from a hand-rolled copy of the engine's router. Both inputs have
moved: the router now delegates to the shipped engine (22/34 on the same cards)
and the sample is all 278 bar-backed S days, not 34 (163/278 = 58.6%). The
corrected power table lives in research/g72_recall278_paired.json::power.

Kept, unedited below, so g71_ssverify.md still resolves. Do not re-run it to
produce a published number.
"""
"""G7.1 adversarial verify (samplesize): re-do the power maths on the CURRENT
held-out recall (23/34 = 0.676, research/g71_ssverify_recall.json) instead of the
stale 18/34 = 0.529 hardcoded at g71_samplesize_power.py:188,215, and on the
MEASURED A/B discordance instead of the assumed psi=0.30."""
import math, json, itertools
from scipy.stats import binom, norm
za = norm.ppf(0.975)

def pow1(n, p0, p1):
    cs = [i for i in range(n+1) if binom.cdf(i, n, p0) <= 0.025]
    return binom.cdf(max(cs), n, p1) if cs else 0.0

def wilson(k, n):
    ph=k/n; d=1+za*za/n; c=(ph+za*za/(2*n))/d
    h=za*math.sqrt(ph*(1-ph)/n+za*za/(4*n*n))/d
    return round(c-h,3), round(c+h,3)

def n2(p1,p2,power=0.8):
    zb=norm.ppf(power); pb=(p1+p2)/2
    return math.ceil((za*math.sqrt(2*pb*(1-pb))+zb*math.sqrt(p1*(1-p1)+p2*(1-p2)))**2/(p1-p2)**2)

def pw2(n,p1,p2):
    pb=(p1+p2)/2
    return 1-norm.cdf((za*math.sqrt(2*pb*(1-pb)/n)-abs(p1-p2))/math.sqrt((p1*(1-p1)+p2*(1-p2))/n))

def nmc(psi,d,power=0.8):
    return math.ceil((za*math.sqrt(psi)+norm.ppf(power)*math.sqrt(psi-d*d))**2/d**2) if psi>abs(d) else None

def pwm(n,psi,d):
    return norm.cdf((math.sqrt(n)*d-za*math.sqrt(psi))/math.sqrt(psi-d*d)) if psi>abs(d) else 0.0

out={}
for lbl,k in (("STALE_18_34",18),("CURRENT_23_34",23)):
    p=k/34
    out[lbl]={"recall":round(p,4),"wilson95":wilson(k,34),
        "p_vs_0.90":2*binom.cdf(k,34,0.90),
        "power_reject_0.90_at_n34":round(pow1(34,0.90,p),4),
        "n_S_80pct_power_vs_gate":next(N for N in range(2,900) if pow1(N,0.90,p)>=0.80),
        "n_S_per_arm_10pt_unpaired_80":n2(p,p+0.10),
        "power_10pt_unpaired_n34":round(pw2(34,p,p+0.10),3),
        "power_10pt_unpaired_n25":round(pw2(25,p,p+0.10),3)}
# measured discordance on the 34 S cards, every like-for-like G7.1 A/B arm pair
import os
HERE=os.path.dirname(os.path.abspath(__file__))
arms={}
for f in os.listdir(HERE):
    if f.endswith(".json") and "recall" in f and f.startswith(("g71_recall","g71_scanners_recall","g71_ladder_recall")):
        try: d=json.load(open(os.path.join(HERE,f)))
        except Exception: continue
        s=d.get("sweep") or {}
        if s.get("n_S")==34: arms[f]=set(s.get("missed_S",[]))
psis=[]
for a,b in itertools.combinations(sorted(arms),2):
    psis.append((round(len(arms[a]^arms[b])/34,3),a,b))
vals=sorted(p for p,_,_ in psis)
med=vals[len(vals)//2]
out["measured_discordance"]={"n_arm_pairs":len(psis),"min":vals[0],"median":med,"max":vals[-1],
    "pairs":sorted(psis,reverse=True)[:5]}
out["paired_at_measured_psi"]={
    ("psi_%.3f"%psi):{"n_S_for_80pct_10pt":nmc(psi,0.10),
                      "power_10pt_at_n34":round(pwm(34,psi,0.10),3),
                      "power_10pt_at_n25":round(pwm(25,psi,0.10),3)}
    for psi in (0.088,0.147,0.176,0.30)}
# Austin's "25 CARDS" (not 25 S) at both base rates
out["austin_25_cards"]={
    "n_S_at_corpus_rate_0.2533":round(25*0.2533,1),
    "n_S_at_sweep_rate_0.34":round(25*0.34,1),
    "paired_power_10pt_psi0.30_n_S_6":round(pwm(6,0.30,0.10),3),
    "paired_power_10pt_psi0.30_n_S_9":round(pwm(9,0.30,0.10),3),
    "claim_says_86pct_invisible_which_is_n_S_25":round(1-pwm(25,0.30,0.10),3)}
print(json.dumps(out,indent=2))
json.dump(out,open(os.path.join(HERE,"g71_ssverify_power.json"),"w"),indent=2)
