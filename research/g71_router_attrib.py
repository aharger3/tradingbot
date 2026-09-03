"""g71 router track: name the exact rows the base skips and the capture copy fires."""
from __future__ import annotations
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import signal_runner as sr, t4_engine_recall as t4

HITS = []
def delegating_route(self, signals, sig):
    before = len(signals)
    sr.SignalRunner._route(self, signals, sig)
    if len(signals) > before:
        sig["status"] = "fired"
    else:
        sig["status"] = "skipped"
        HITS.append((self.symbol, sig.get("grade"), sig.get("signal_type"),
                     sig.get("direction"), sig.get("entry"), sig.get("stop"),
                     sig.get("reason", "")[-160:]))
    self.captured.append(sig)

t4.CaptureRunner._route = delegating_route
for sym, day in [("SPY", "2025-02-20"), ("SPY", "2026-03-05")]:
    HITS.clear()
    ent, sigs, raw = t4.run_day(sym, day)
    keep = [h for h in HITS if h[1] not in ("X", "D")]
    print("== %s %s : base-skipped non-D rows = %d" % (sym, day, len(keep)))
    for h in keep:
        risk_pct = abs(h[4] - h[5]) / abs(h[4]) * 100 if h[4] else -1
        print("   grade=%s %s %s entry=%.4f stop=%.4f stop%%=%.4f\n     reason=...%s"
              % (h[1], h[2], h[3], h[4], h[5], risk_pct, h[6]))
