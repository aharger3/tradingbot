"""BR+OCR confluence SignalType selftest (P3/G8, 2026-08-26).

Austin: "One candle rule should be just as popular as break-and-retest is. And
both trading strategies should have an option where both one candle rule and
break-and-retest occur."

What this pins down:

  1. A synthetic bar series carrying BOTH a break-and-retest and an isolated,
     respected order block gets SignalType.BR_OCR_CONFLUENCE. A series with the
     same break and NO counter-coloured candle does not.
  2. The label is computed by research/downgrade.py::has_confluence and nothing
     else -- one definition of confluence. The test asserts the runner's answer
     equals a direct call, so a second definition cannot quietly appear here.
  3. ROUTING IS UNCHANGED by default: sig["signal_type"] survives the label
     untouched, which is what keeps backtest_week's dedupe idea key -- and
     therefore the 2-year book -- identical. Only CONFLUENCE_SETUP_ROUTES=1
     promotes the label into signal_type.
  4. The label is CAUSAL. signal_runner computes it on bars truncated at the
     signal, backtest_2y.py computes dg.score on the whole day at the same
     index; if those two disagreed the book's `confluence` column and the new
     setup label would be two different measurements.
  5. BR_OCR_CONFLUENCE is in S_ELIGIBLE_SETUPS and RULE84_ARM_ON, because a
     confluence setup is a break-and-retest AND an order block at once and both
     of those are already in each set.

    python research/test_confluence_setup.py
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import signal_runner as sr                                      # noqa: E402
from signal_runner import SignalRunner                          # noqa: E402
from omen_bot import Candle, SignalType                         # noqa: E402
from research import downgrade as dg                            # noqa: E402

FAILURES = []
LEVEL = 100.0


def check(cond, label):
    if cond:
        print("  ok    %s" % label)
    else:
        print("  FAIL  %s" % label)
        FAILURES.append(label)


# --- the fixture ----------------------------------------------------------
# Both series break LEVEL on bar 4 (bar 3 closes 99.80 <= 100.0 < 100.50) and
# trend up after it. They differ in ONE bar: bar 7.
#   confluence: bar 7 closes DOWN (101.10 -> 101.00) with up-closes either side,
#     so it is an isolated order block; its low 100.90 sits below the signal
#     bar's close (usable as a stop) and no later bar closes back through it.
#   plain B&R: bar 7 closes UP like every other bar, so find_ocr finds nothing
#     in its 20-bar lookback and confluence is absent.
_ROWS = [
    #  open,    high,     low,   close
    (99.00,  99.30,  98.90,  99.20),
    (99.20,  99.50,  99.10,  99.40),
    (99.40,  99.70,  99.30,  99.60),
    (99.60,  99.90,  99.50,  99.80),
    (99.80, 100.70,  99.70, 100.50),   # 4 — the break
    (100.50, 100.90, 100.40, 100.80),
    (100.80, 101.20, 100.70, 101.10),
    (101.10, 101.20, 100.90, 101.00),  # 7 — the OCR (down close, isolated)
    (101.00, 101.40, 100.95, 101.30),
    (101.30, 101.60, 101.20, 101.50),
    (101.50, 101.80, 101.40, 101.70),
    (101.70, 102.00, 101.60, 101.90),  # 11 — the signal bar
]
_OCR_BAR = 7
# The plain-B&R twin: same bar 7, closed up instead of down.
_PLAIN_BAR7 = (101.10, 101.20, 100.90, 101.15)


def candles(confluence: bool):
    rows = list(_ROWS)
    if not confluence:
        rows[_OCR_BAR] = _PLAIN_BAR7
    return [Candle(timestamp="09:%02d:00" % (35 + i), open=o, high=h,
                   low=lo, close=c, volume=1000)
            for i, (o, h, lo, c) in enumerate(rows)]


def bars(confluence: bool):
    return [{"o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
            for c in candles(confluence)]


def emit(stype, confluence: bool, routes: bool = False, n: int = None):
    """Push one signal through SignalRunner._emit and hand back the dict."""
    cs = candles(confluence)
    if n is not None:
        cs = cs[:n]
    runner = SignalRunner(webhook_url=None, post_to_discord=False)
    runner.symbol = "TEST"
    runner.candles = cs
    runner._bar_setups = {}
    kept = []
    runner._route = lambda signals, sig: kept.append(sig)
    sig = {"signal_type": stype, "reason": "test signal", "entry": 100.50,
           "stop": LEVEL if stype is SignalType.BREAK_AND_RETEST else LEVEL,
           "direction": "call", "grade": "B", "stop_level_name": "OR high",
           "stop_width_pct": 0.5}
    old_log, old_flag = sr.log_signal, sr.CONFLUENCE_SETUP_ROUTES
    sr.log_signal = lambda *a, **k: None
    sr.CONFLUENCE_SETUP_ROUTES = routes
    try:
        runner._emit([], sig)
    finally:
        sr.log_signal = old_log
        sr.CONFLUENCE_SETUP_ROUTES = old_flag
    return sig


print("\nfixture — downgrade.has_confluence is the only definition")
check(dg.has_confluence(bars(True), 11, LEVEL, True),
      "the BR+OCR series has confluence per downgrade.has_confluence")
check(not dg.has_confluence(bars(False), 11, LEVEL, True),
      "the plain-B&R series does not (no isolated counter-coloured candle)")
check(dg.find_ocr(bars(True), 11, True) == _OCR_BAR,
      "the order block is bar %d" % _OCR_BAR)
check(dg.find_ocr(bars(False), 11, True) is None,
      "the plain-B&R series has no order block in the lookback")

print("\nthe label")
for stype in (SignalType.BREAK_AND_RETEST, SignalType.ONE_CANDLE_RULE):
    got = emit(stype, True)
    check(got["setup_type"] is SignalType.BR_OCR_CONFLUENCE,
          "%s + OCR is labelled BR_OCR_CONFLUENCE" % stype.name)
    check(got.get("br_ocr") is True and "[brocr]" in got["reason"],
          "%s + OCR carries br_ocr and the [brocr] reason tag" % stype.name)
plain = emit(SignalType.BREAK_AND_RETEST, False)
check(plain["setup_type"] is SignalType.BREAK_AND_RETEST,
      "a plain break-and-retest keeps setup_type BREAK_AND_RETEST")
check("br_ocr" not in plain and "[brocr]" not in plain["reason"],
      "a plain break-and-retest carries no confluence tag")
for stype in (SignalType.FAIR_VALUE_GAP, SignalType.FLAG,
              SignalType.REENTRY_84_RULE):
    got = emit(stype, True)
    check(got["setup_type"] is stype,
          "%s is never relabelled — it cannot be half of a confluence" % stype.name)

print("\nrouting is unchanged (CONFLUENCE_SETUP_ROUTES default OFF)")
check(sr.CONFLUENCE_SETUP_ROUTES is False,
      "CONFLUENCE_SETUP_ROUTES defaults OFF")
conf = emit(SignalType.BREAK_AND_RETEST, True, routes=False)
check(conf["signal_type"] is SignalType.BREAK_AND_RETEST,
      "with the flag OFF signal_type — the dedupe/routing key — is untouched")
check("base_signal_type" not in conf,
      "with the flag OFF nothing pretends the type was rewritten")
routed = emit(SignalType.BREAK_AND_RETEST, True, routes=True)
check(routed["signal_type"] is SignalType.BR_OCR_CONFLUENCE,
      "with the flag ON signal_type becomes BR_OCR_CONFLUENCE")
check(routed["base_signal_type"] is SignalType.BREAK_AND_RETEST,
      "with the flag ON the base setup is preserved on base_signal_type")

print("\nthe label is causal — truncated bars give the whole day's answer")
full = bars(True)
for i in range(5, len(full)):
    live = emit(SignalType.BREAK_AND_RETEST, True, n=i + 1)
    offline = dg.score(full, i, LEVEL, True)
    check((live["setup_type"] is SignalType.BR_OCR_CONFLUENCE)
          == bool(offline["confluence"]),
          "bar %d: detection-time label == dg.score on the full day" % i)

print("\nset membership, decided deliberately")
check(SignalType.BR_OCR_CONFLUENCE in sr.S_ELIGIBLE_SETUPS,
      "BR_OCR_CONFLUENCE is S-eligible (both its halves already are)")
check(SignalType.BR_OCR_CONFLUENCE in sr.RULE84_ARM_ON,
      "BR_OCR_CONFLUENCE arms the 84% rule (both its halves already do)")
check(SignalType.BR_OCR_CONFLUENCE not in sr.RETIRED_SETUPS,
      "BR_OCR_CONFLUENCE is not a retired setup")
check(len({s.value for s in SignalType}) == len(list(SignalType)),
      "every SignalType still has a unique value (no accidental aliasing)")

print()
if FAILURES:
    print("CONFLUENCE SETUP SELFTEST FAILED: %d check(s)" % len(FAILURES))
    for f in FAILURES:
        print("  - %s" % f)
    sys.exit(1)
print("confluence setup selftest ok")
