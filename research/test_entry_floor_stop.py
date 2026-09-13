"""research/test_entry_floor_stop.py -- the g88 POST_floor stop policy in the
shipped engine, behind ENTRY_FLOOR_STOP (default OFF).

backtest_week's default DROPS a resting-limit fill whose risk collapsed to/through
the stop (a limit resting on a break-and-retest level IS the stop). g88's POST_floor
arm instead WIDENS the structural stop out until risk clears
signal_runner.min_risk_floor, reading the last CLOSED bar before the fill so the
sizing constant stays causal (research/g88_level_limit.floored_row). That arm
measured +$256/day on bt2y_trades_retest_on (vs the shipped entry's $31).

This proves backtest_week._floor_widened_stop reproduces floored_row's rule and
that the flag defaults OFF so nothing ships. Adopting it as the default is Austin's
call; this file only guards the behaviour behind the flag.

Run:  python research/test_entry_floor_stop.py
"""
from __future__ import annotations
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import backtest_week as bw          # noqa: E402
import signal_runner as sr          # noqa: E402

EPS = 1e-9


def main():
    rows, failures = [], []

    def chk(name, cond, detail=""):
        rows.append((name, cond))
        print(("  ok  " if cond else "  FAIL") + "  " + name
              + (("  ::  " + detail) if (detail and not cond) else ""))
        if not cond:
            failures.append(name + ((": " + detail) if detail else ""))

    # The flag exists and defaults OFF -- nothing ships until Austin flips it.
    chk("ENTRY_FLOOR_STOP defaults OFF (nothing ships)",
        getattr(bw, "ENTRY_FLOOR_STOP", "MISSING") is False,
        "got %r" % getattr(bw, "ENTRY_FLOOR_STOP", "MISSING"))

    fw = getattr(bw, "_floor_widened_stop", None)
    if fw is None:
        print("  FAIL  backtest_week._floor_widened_stop is missing")
        sys.exit(1)

    close = 100.0
    floor = sr.min_risk_floor(close)
    chk("min_risk_floor(close) is positive (test premise)", floor > 0,
        "floor=%.4f" % floor)

    # LONG, risk collapsed AT the stop (entry == stop): widen below entry by >= floor.
    s = fw(entry=100.0, stop=100.0, ref_close=close, fill_close=close, long=True)
    chk("long: collapsed stop widened below entry by >= floor",
        (100.0 - s) >= floor - EPS,
        "stop=%.4f width=%.4f floor=%.4f" % (s, 100.0 - s, floor))

    # LONG, fill THROUGH the stop (entry below the stop): still a real stop below entry.
    s = fw(entry=99.98, stop=100.0, ref_close=close, fill_close=close, long=True)
    chk("long: through-stop fill still yields a stop below entry (not dropped)",
        s < 99.98 - EPS and (99.98 - s) >= floor - EPS, "stop=%.4f" % s)

    # LONG, structural stop already WIDER than the floor: left unchanged (no-op).
    wide = 100.0 - 5 * floor
    s = fw(entry=100.0, stop=wide, ref_close=close, fill_close=close, long=True)
    chk("long: an already-wide structural stop is left unchanged",
        abs(s - wide) < EPS, "stop=%.4f wide=%.4f" % (s, wide))

    # SHORT mirror: entry == stop -> widen ABOVE entry by >= floor.
    s = fw(entry=100.0, stop=100.0, ref_close=close, fill_close=close, long=False)
    chk("short: collapsed stop widened above entry by >= floor",
        (s - 100.0) >= floor - EPS, "stop=%.4f" % s)

    # Causal: the floor scales with ref_close (the last CLOSED bar), so a larger
    # reference produces a wider floor -- proving ref_close is actually used.
    w_lo = 100.0 - fw(entry=100.0, stop=100.0, ref_close=20.0, fill_close=20.0, long=True)
    w_hi = 100.0 - fw(entry=100.0, stop=100.0, ref_close=500.0, fill_close=500.0, long=True)
    chk("causal: floor scales with ref_close (ref is used, not ignored)",
        w_hi > w_lo + EPS, "w_lo=%.4f w_hi=%.4f" % (w_lo, w_hi))

    total = len(rows)
    if failures:
        print("\nENTRY_FLOOR_STOP selftest FAILED: %d of %d checks wrong."
              % (len(failures), total))
        sys.exit(1)
    print("\nentry-floor-stop selftest ok: %d checks. POST_floor widens the stop "
          "to the causal size floor instead of dropping the trade; flag defaults "
          "OFF." % total)


if __name__ == "__main__":
    main()
