"""G71/rule84ocrV: does _has_displacement remove BR+OCR confluence signals?

The claim under test: "it removes exactly the confluence setup Austin calls his
best."  A/B the veto by setting omen_bot.DISPLACEMENT_MULT to 0.0 (always true)
and counting fired signals by (signal_type, br_ocr).  Read-only.
"""
import os, sys
from collections import Counter
from pathlib import Path
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT); os.chdir(ROOT)

import omen_bot, signal_runner as sr
from t3_session_extreme import day_inputs

SYMS = ["AAPL", "AMD", "AMZN", "AVGO", "COIN", "NVDA"]
DAYS = sorted({p.stem for s in SYMS
               for p in Path(f"data/cache/{s}/1min").glob("*.csv")})[-25:]


class Cap(sr.SignalRunner):
    def __init__(self, symbol):
        super().__init__(post_to_discord=False, symbol=symbol, log_signals=False)
        self.fired = []
    def _route(self, signals, sig):
        n = len(signals)
        super()._route(signals, sig)
        if len(signals) > n:
            self.fired.append(dict(sig))


def run(mult):
    omen_bot.DISPLACEMENT_MULT = mult
    c = Counter()
    for sym in SYMS:
        for d in DAYS:
            got = day_inputs(sym, d)
            if got is None:
                continue
            candles, pdh, pdl, pdo, pdc, pmh, pml, bias = got
            r = Cap(sym)
            r.pdh, r.pdl, r.pmh, r.pml = pdh, pdl, pmh, pml
            r.pd_open, r.pd_close, r.htf_bias = pdo, pdc, bias
            for i in range(5, len(candles)):
                r.candles = candles[: i + 1]
                r.detect_signals()
            for s in r.fired:
                st = getattr(s.get("signal_type"), "value", s.get("signal_type"))
                c[(st, bool(s.get("br_ocr")))] += 1
    return c


base = run(1.5)          # shipped
off = run(0.0)           # veto disabled (every leg has "displacement")
omen_bot.DISPLACEMENT_MULT = 1.5

keys = sorted(set(base) | set(off))
print(f"symbols={SYMS} days={DAYS[0]}..{DAYS[-1]} ({len(DAYS)})")
print(f"{'setup':22s} {'brocr':6s} {'shipped':>9s} {'disp OFF':>9s} {'delta':>7s}")
for k in keys:
    print(f"{k[0]:22s} {str(k[1]):6s} {base[k]:9d} {off[k]:9d} {off[k]-base[k]:+7d}")
b_br = sum(v for k, v in base.items() if k[1]); o_br = sum(v for k, v in off.items() if k[1])
print(f"\nTOTAL br_ocr=True   shipped={b_br}  disp OFF={o_br}  delta={o_br-b_br:+d}")
print(f"TOTAL signals       shipped={sum(base.values())}  disp OFF={sum(off.values())}")
