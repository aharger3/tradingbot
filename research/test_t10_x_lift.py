"""T10 -- what the X_LIFT flag must never stop doing.

Four things are pinned here, each one a way this lever has already been got
wrong somewhere in this repo:

  1. DEFAULT OFF AND INERT. `X_LIFT` unset means the predicate refuses every
     signal, so the shipped book is byte-identical. Ratified items ship ON;
     this is not one of them -- it is a measured arm.
  2. THE LADDER IS NESTED. disp subset pa subset clean subset br subset all.
     If a later edit breaks the nesting, the report's ladder stops being a
     ladder and its precision column stops meaning anything.
  3. THE ONE-CANDLE-RULE POOL IS NEVER LIFTED BY THE LADDER. Austin's verdict on
     that pool was 17 "not this setup at all" + 3 "weak" out of 20, and 8 of the
     9 OCR cards in the veto lane came back "no". Only the `all` control, which
     exists to be beaten, may touch it.
  4. THE FIT SCORER AND THE ENGINE AGREE. `research/t10_x_lift_fitted.predicate`
     scores book rows; `signal_runner.x_lift_qualifies` gates live signals. They
     are two spellings of one condition, and a drift between them would make the
     fitted numbers describe a rule the engine does not run.

Run:  python research/test_t10_x_lift.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import signal_runner as sr                                   # noqa: E402
from omen_bot import SignalType                              # noqa: E402
from research.t10_x_lift_fitted import ARMS, BOOK, predicate  # noqa: E402

FAILS = []


def check(ok, msg):
    print(("  ok   " if ok else "  FAIL ") + msg)
    if not ok:
        FAILS.append(msg)


def sig(setup, *tags):
    return {"signal_type": setup,
            "reason": "x " + " ".join("[%s]" % t for t in tags) + " S4"}


BR = SignalType.BREAK_AND_RETEST
OCR = SignalType.ONE_CANDLE_RULE

# The full tag space the B&R emission site can produce, as it produces it:
# exactly one of [clean]/[late], optional [hammer], exactly one of [disp]/[nodisp].
SPACE = [(retest, ham, dsp)
         for retest in ("clean", "late")
         for ham in ((), ("hammer",))
         for dsp in ("disp", "nodisp")]


def main():
    print("1. default off and inert")
    check(sr.X_LIFT == os.getenv("X_LIFT", "off").strip().lower(),
          "X_LIFT reads its env var")
    check(os.getenv("X_LIFT") is not None or sr.X_LIFT == "off",
          "unset X_LIFT means 'off'")
    for setup, *tags in [(BR, "clean", "hammer", "disp"), (OCR,)]:
        check(sr.x_lift_qualifies(sig(setup, *tags), "off") is False,
              "arm 'off' lifts nothing (%s)" % setup.value)
    check(sr.x_lift_qualifies(sig(BR, "clean"), "nonsense") is False,
          "an unknown arm name lifts nothing rather than everything")

    print("2. the ladder is nested: disp <= pa <= clean <= br <= all")
    order = ("disp", "pa", "clean", "br", "all")
    for retest, ham, dsp in SPACE:
        tags = (retest,) + ham + (dsp,)
        vals = [sr.x_lift_qualifies(sig(BR, *tags), a) for a in order]
        check(all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1)),
              "nested on B&R [%s]" % ",".join(tags))
    # and the ladder actually separates: each rung must be strictly narrower
    # than the one above it somewhere in the tag space, or it is not a rung.
    counts = {a: sum(1 for r, h, d in SPACE
                     if sr.x_lift_qualifies(sig(BR, *((r,) + h + (d,))), a))
              for a in order}
    check(counts["disp"] < counts["pa"] < counts["clean"] < counts["br"],
          "every rung is strictly narrower than the next: %s" % counts)

    print("3. the ladder never lifts the one-candle-rule pool")
    for arm in ("br", "clean", "pa", "disp"):
        check(sr.x_lift_qualifies(sig(OCR, "brocr"), arm) is False,
              "arm '%s' refuses one_candle_rule" % arm)
    check(sr.x_lift_qualifies(sig(OCR, "brocr"), "all") is True,
          "the 'all' control does lift it -- that is what it is for")

    print("4. the fit scorer and the engine are one condition")
    book = json.load(open(BOOK, encoding="utf-8"))["trades"]
    bad = 0
    for r in book:
        try:
            st = SignalType(r["setup"])
        except ValueError:
            continue
        s = {"signal_type": st, "reason": r["reason"]}
        for arm in ARMS:
            if predicate(arm)(r) != sr.x_lift_qualifies(s, arm):
                bad += 1
    check(bad == 0,
          "0 mismatches over %d book rows x %d arms (got %d)"
          % (len(book), len(ARMS), bad))

    print("5. the stop guard is wired into _route, not optional")
    src = open(os.path.join(ROOT, "signal_runner.py"), encoding="utf-8").read()
    i = src.find("x_lift_qualifies(sig, X_LIFT)")
    check(i > 0, "_route calls x_lift_qualifies")
    window = src[i:i + 400]
    check("_min_viable_stop" in window,
          "the lift is conjoined with _min_viable_stop -- a lift may not smuggle "
          "a 2-cent stop into the book")

    print("6. every _route that scores held-out recall calls the lift")
    t4 = open(os.path.join(HERE, "t4_engine_recall.py"), encoding="utf-8").read()
    j = t4.find("def _route(self, signals, sig):")
    check(j > 0, "t4_engine_recall.CaptureRunner defines its own _route")
    check("_apply_x_lift" in t4[j:j + 900],
          "CaptureRunner._route calls _apply_x_lift -- this replay does not "
          "delegate to super, and it is the rig regression_gate, t70_test1_score "
          "and t0_heldout_recall all score on")
    bw = open(os.path.join(ROOT, "backtest_week.py"), encoding="utf-8").read()
    k = bw.find("def _route(self, signals: List[dict], sig: dict) -> None:")
    check(k > 0 and "super()._route" in bw[k:k + 900],
          "BacktestRunner._route delegates to super, so it inherits the lift")

    print()
    if FAILS:
        print("FAILED %d checks" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("all green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
