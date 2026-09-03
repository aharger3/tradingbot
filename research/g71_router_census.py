"""g71 router track: census of EVERY base-_route skip reason over the union of
the regression-gate marks and the two held-out probe sets."""
from __future__ import annotations
import os, sys, json, collections, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import signal_runner as sr, t4_engine_recall as t4
import t0_heldout_recall as t0

REASONS = collections.Counter()
def delegating(self, signals, sig):
    before = len(signals)
    sr.SignalRunner._route(self, signals, sig)
    if len(signals) > before:
        sig["status"] = "fired"
    else:
        sig["status"] = "skipped"
        if sig.get("grade") not in ("X", "D"):
            for m in re.findall(r"\[(skip|retired|capped)[^\]]*\]", sig.get("reason", "")):
                pass
            tags = re.findall(r"\[(?:skip|retired|capped)[^\]]*\]", sig.get("reason", ""))
            REASONS[tags[-1] if tags else "UNTAGGED:" + sig.get("reason", "")[-60:]] += 1
    self.captured.append(sig)

pairs = set()
for m in (json.loads(l) for l in open(t4.MARKS) if l.strip()):
    pairs.add((m["symbol"], m["day"]))
for path in (t0.SWEEP, t0.MASTER):
    for r in t0.rows(path):
        if r.get("symbol") and r.get("date"): pairs.add((r["symbol"], r["date"]))
print("union symbol-days:", len(pairs))
t4.CaptureRunner._route = delegating
ok = 0
for sym, day in sorted(pairs):
    try:
        e, s, r = t4.run_day(sym, day)
        ok += e is not None
    except Exception:
        pass
print("replayed:", ok)
for k, v in REASONS.most_common():
    print("%6d  %s" % (v, k))
