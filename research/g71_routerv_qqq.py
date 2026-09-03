import os,sys
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
sys.path.insert(0,HERE); sys.path.insert(0,ROOT)
import research.t4_engine_recall as t4, signal_runner as sr
from signal_runner import TradeGrade
ORIG=t4.CaptureRunner._route
def deleg(self,signals,sig):
    b=len(signals); sr.SignalRunner._route(self,signals,sig)
    sig["status"]="fired" if len(signals)>b else "skipped"
    self.captured.append(sig)
t4.CaptureRunner._route=deleg
e,s,raw=t4.run_day("QQQ","2025-09-23")
for r in raw:
    if r["grade"] in ("A+","A","B","C"):
        print(r["bar"],r["timestamp"],r["grade"],r["status"],"entry",r["entry"],"stop",r["stop"],
              "stop_pct=%.4f%%"%(abs(r["entry"]-r["stop"])/abs(r["entry"])*100))
t4.CaptureRunner._route=ORIG
