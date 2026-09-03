"""Adversarial verify probe: does the monkeypatch take, and what grades fire?"""
import os, sys, json
from collections import Counter
HERE=os.path.join(os.path.dirname(os.path.abspath(__file__)))
ROOT=os.path.dirname(HERE)
sys.path.insert(0,HERE); sys.path.insert(0,ROOT)
import research.t4_engine_recall as t4
import signal_runner as sr
from signal_runner import TradeGrade

ORIG=t4.CaptureRunner._route
CALLS={"hand":0,"deleg":0}

def deleg(self, signals, sig):
    CALLS["deleg"]+=1
    before=len(signals)
    sr.SignalRunner._route(self, signals, sig)
    if len(signals)>before: sig["status"]="fired"
    elif sig["grade"]==TradeGrade.D.value: sig["status"]="skipped_d"
    else: sig["status"]="skipped_tight_stop"
    self.captured.append(sig)

def wrapped_orig(self, signals, sig):
    CALLS["hand"]+=1
    return ORIG(self, signals, sig)

pairs=[("QQQ","2025-09-23"),("NVDA","2025-01-23"),("PLTR","2024-03-11"),("AMD","2024-10-24")]
for name,fn in (("hand",wrapped_orig),("deleg",deleg)):
    t4.CaptureRunner._route=fn
    gc=Counter(); fc=Counter()
    for s,d in pairs:
        e,sg,raw=t4.run_day(s,d)
        if e is None: print("noarch",s,d); continue
        for r in raw:
            gc[r["grade"]]+=1
            if r["status"]=="fired": fc[r["grade"]]+=1
        print(name,s,d,"entries",len(e),[x["grade"] for x in e])
    print(name,"all-sig grades",dict(gc),"fired grades",dict(fc))
t4.CaptureRunner._route=ORIG
print("route calls",CALLS)
print("_SKIP_GRADES",sr._SKIP_GRADES,"X_LIFT",sr.X_LIFT,"MIN_STOP_PCT",sr.MIN_STOP_PCT,"NO_REPEAT_ENTRIES",sr.NO_REPEAT_ENTRIES,"AUSTIN_TIER_ENABLED",sr.AUSTIN_TIER_ENABLED)
