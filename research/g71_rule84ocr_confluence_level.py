"""G71/rule84ocr: the BR+OCR confluence label is computed against the STOP, not
the level -- and the level is right there on the signal.

signal_runner.py:2409  `level = sig.get("stop")`      <- _label_confluence
backtest_2y.py:151     `dg.score(dbars, t.entry_idx, t.stop, ...)`  <- the book's
                       `confluence` column and the whole S/A/C grade
Every detection site already emits `sig["level_price"]` (signal_runner.py:2827,
2913, 3010, 3091, 3164, 3251) and SimTrade carries it (backtest_week.py:280,877).

This replays real days and evaluates downgrade.has_confluence BOTH ways on the
same signals. Read-only. Usage: python research/g71_rule84ocr_confluence_level.py
"""
import os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT); os.chdir(ROOT)

import signal_runner as sr
from research import downgrade as dg
from t3_session_extreme import day_inputs
from pathlib import Path

SYMS = ["AAPL", "AMD", "AMZN", "AVGO", "COIN", "NVDA", "TSLA", "MSFT"]
DAYS = sorted({p.stem for s in SYMS
               for p in Path(f"data/cache/{s}/1min").glob("*.csv")})[-30:]


class Cap(sr.SignalRunner):
    def __init__(self, symbol):
        super().__init__(post_to_discord=False, symbol=symbol, log_signals=False)
        self.fired = []

    def _route(self, signals, sig):
        n = len(signals)
        super()._route(signals, sig)
        if len(signals) > n:
            self.fired.append(dict(sig))


x = Counter(); by_setup = Counter(); n = 0
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
            before = len(r.fired)
            r.detect_signals()
            if len(r.fired) == before:
                continue
            bars = [{"o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
                    for c in r.candles]
            j = len(bars) - 1
            for sig in r.fired[before:]:
                st = sig.get("signal_type")
                if st not in sr.CONFLUENCE_BASE_SETUPS:
                    continue
                lvl = sig.get("level_price")
                stp = sig.get("stop")
                if lvl is None or stp is None:
                    continue
                is_long = sig.get("direction") == "call"
                a = dg.has_confluence(bars, j, stp, is_long)   # SHIPPED
                b = dg.has_confluence(bars, j, lvl, is_long)   # the level itself
                x[(a, b)] += 1
                by_setup[(st.value, a, b)] += 1
                n += 1

print(f"n={n} BR/OCR signals over {SYMS} x {len(DAYS)} days ({DAYS[0]}..{DAYS[-1]})")
for k in sorted(x):
    print(f"  has_confluence(stop)={k[0]!s:5s} has_confluence(level_price)={k[1]!s:5s}"
          f"  {x[k]:6d}  {x[k]/max(n,1)*100:5.1f}%")
print(f"  SHIPPED(stop) says yes on {sum(v for k,v in x.items() if k[0])/max(n,1)*100:.1f}%")
print(f"  LEVEL          says yes on {sum(v for k,v in x.items() if k[1])/max(n,1)*100:.1f}%")
agree = x[(True, True)] + x[(False, False)]
print(f"  AGREE {agree/max(n,1)*100:.1f}%  DISAGREE {100-agree/max(n,1)*100:.1f}%")
for k in sorted(by_setup):
    print("   ", k, by_setup[k])
