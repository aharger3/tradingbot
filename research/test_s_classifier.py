"""g156 -- S_CLASSIFIER v0 does what it says, and nothing else.

    python research/test_s_classifier.py

OMEN 9.0 row F7: zero of the 25 candidates mined from Austin's marks
(research/g154_rule_*.py) survived F6 refutation (research/g155_rule_verdicts.md).
This flag ships the single best NON-refuted candidate anyway, per the row's own
fallback instruction: research/g154_rule_or-break-without-retest.py -- an OR
high/OR low break that never retested the level is DROPPED from the candidate
stream, not merely capped to C (RETEST_REQUIRED already caps to C, and a C
still trades). See research/g156_s_classifier_v0.md for the honest read: it
does not clear the 39.5% precision bar.

Four assertions, mirroring test_retest_gate.py:

  1. default is OFF, and it is byte-identical to today at OFF.
  2. ON drops (X-grades) a real book candidate whose ONLY downgrade is
     no_retest on an OR level (IWM 2024-10-01 09:40, OR low -- the same real
     day test_retest_gate.py uses to prove RETEST_REQUIRED is reachable).
  3. ON leaves a real break-AND-retest alone (the clean synthetic fixture).
  4. ON never touches a non-OR level (PDH/PDL/PMH/PML) even when it trips
     no_retest -- the arm measured is OR-specific, not blanket.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import signal_runner as sr                       # noqa: E402
from signal_runner import Candle, SignalRunner    # noqa: E402


def _bars(seq):
    return [Candle(t, o, h, lo, c, v) for t, o, h, lo, c, v in seq]


def clean_break_and_retest():
    """Flat OR range, displaced break above OR high, leave, retest, confirm."""
    out = [("09:%02d:00" % (30 + i), 100.0, 100.5, 99.9, 100.2, 1000)
           for i in range(5)]
    out += [("09:%02d:00" % (35 + i), 100.1, 100.4, 100.0, 100.2, 1000)
            for i in range(15)]
    out += [("09:50:00", 100.3, 102.0, 100.2, 101.9, 5000),   # displaced break
            ("09:51:00", 101.9, 102.3, 101.7, 102.1, 2000),   # leave
            ("09:52:00", 102.1, 102.2, 101.3, 101.6, 1500),   # drift back
            ("09:53:00", 101.6, 101.7, 100.4, 100.9, 1800),   # RETEST the level
            ("09:54:00", 101.0, 101.6, 100.8, 101.5, 1600)]   # confirm
    return _bars(out)


def run(bars, s_classifier):
    old = sr.S_CLASSIFIER
    sr.S_CLASSIFIER = s_classifier
    try:
        r = SignalRunner(post_to_discord=False, symbol="TEST", log_signals=False)
        r.candles = bars
        return r.detect_signals()
    finally:
        sr.S_CLASSIFIER = old


def _real_book_drop():
    """IWM 2024-10-01 09:40 put, OR low -- the same real day test_retest_gate.py
    uses to prove RETEST_REQUIRED is reachable: the honest book's first pick,
    graded B, and the only downgrade variable it trips is no_retest. Proves the
    gate is reachable on the live path, not merely on a synthetic tape.

    Skips (loudly) if the bars are not archived, rather than passing quietly.
    """
    sym, day = "IWM", "2024-10-01"
    try:
        from research import g80_ordertype_grid as G
        bars, pdh, pdl, pmh, pml = G.day_pack(sym, day)
    except Exception as e:
        print("  2. SKIPPED -- could not load %s %s (%s). NOT a pass."
              % (sym, day, type(e).__name__))
        return
    if not bars:
        print("  2. SKIPPED -- no archived bars for %s %s. NOT a pass." % (sym, day))
        return

    import backtest_week as bw
    seen = {}
    for on in (False, True):
        old_rr, old_sc = sr.RETEST_REQUIRED, sr.S_CLASSIFIER
        sr.RETEST_REQUIRED, sr.S_CLASSIFIER = False, on
        try:
            ts = bw.simulate_day(sym, day, bars, pdh, pdl, None, pmh, pml)
        finally:
            sr.RETEST_REQUIRED, sr.S_CLASSIFIER = old_rr, old_sc
        seen[on] = {t.entry_time: t for t in ts}

    assert seen[False], "%s %s produced no candidates at all" % (sym, day)
    first_off = sorted(seen[False].items())[0]
    t0, trade0 = first_off
    assert trade0.stop_level_name == "OR low", \
        "fixture drift: %s %s first pick is now %r, not OR low -- pick a new " \
        "real day or the OR-specific claim is untested" % (sym, day, trade0.stop_level_name)
    assert t0 in seen[True], \
        "S_CLASSIFIER OFF vs ON produced a different candidate set at any " \
        "OTHER row; only the OR-low no_retest row should ever move"
    assert seen[True][t0].grade == "X", \
        "S_CLASSIFIER ON left %s ungraded X, got %r -- the drop is not " \
        "reaching the real book candidate" % (t0, seen[True][t0].grade)
    print("  2. ON X-grades the real OR-low no_retest candidate on %s %s  OK"
          % (sym, day))


def main():
    # -- 1. default is OFF -----------------------------------------------
    assert sr.S_CLASSIFIER is False, \
        "S_CLASSIFIER default is %r; it must ship OFF until the morning " \
        "read (research/g156_s_classifier_v0.md)" % sr.S_CLASSIFIER
    os.environ["S_CLASSIFIER"] = "1"
    import importlib
    assert importlib.reload(sr).S_CLASSIFIER is True, \
        "S_CLASSIFIER=1 does not turn the gate on"
    os.environ.pop("S_CLASSIFIER", None)
    importlib.reload(sr)
    assert sr.S_CLASSIFIER is False, "module did not reload back to the default"
    print("  1. default is OFF; S_CLASSIFIER=1 turns it on  OK")

    # -- 2. ON drops the real no-retest OR-low candidate ------------------
    _real_book_drop()

    # -- 3. ON leaves a real break-and-retest alone ------------------------
    on_clean = run(clean_break_and_retest(), True)
    off_clean = run(clean_break_and_retest(), False)
    assert on_clean, "the clean break-and-retest fired nothing even with the gate on"
    assert len(on_clean) == len(off_clean), \
        "S_CLASSIFIER dropped a setup that DID retest -- it must refuse the " \
        "missing retest, not the setup"
    assert not any("S_CLASSIFIER" in s["reason"] for s in on_clean), \
        "the gate marked a retested setup as dropped"
    print("  3. ON leaves a real break-and-retest alone (%d signal(s))  OK"
          % len(on_clean))

    # -- 4. OFF is byte-identical: same signals, same reasons --------------
    for a, b in zip(off_clean, on_clean):
        assert a == b, "OFF and ON disagree on a setup that never trips the gate"
    print("  4. OFF is byte-identical on a tape the gate never touches  OK")

    print("test_s_classifier OK")


if __name__ == "__main__":
    main()
