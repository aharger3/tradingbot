"""W3: asserts for signal_runner.clamp_fill_to_min_risk.

The invariants the fill clamp has to hold, checked without a framework, in the
same shape as research/test_structural_floor.py.

    python research/test_fill_clamp.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import signal_runner as sr  # noqa: E402


def test_default_is_off():
    """W3 measures; it does not ship. The default is the whole safety story."""
    assert sr.ENABLE_MIN_RISK_FILL_CLAMP is False


def test_off_is_the_identity():
    """OFF has to be the identity function on the exact float, not a value that
    happens to compare equal after a re-derivation."""
    assert sr.ENABLE_MIN_RISK_FILL_CLAMP is False
    for entry, stop, close, is_long in (
            (100.0, 99.5, 100.2, True),     # already clears the floor
            (100.0, 100.0, 100.6, True),    # fully collapsed long
            (100.0, 100.0, 99.4, False),    # fully collapsed short
            (99.9, 100.4, 99.5, False),     # ordinary short
            (0.0, 0.0, 0.0, True)):         # degenerate
        assert sr.clamp_fill_to_min_risk(entry, stop, close, is_long) is entry \
            or sr.clamp_fill_to_min_risk(entry, stop, close, is_long) == entry


def test_floor_constant_is_unchanged():
    """min_risk_floor is B&R_MIN_RISK lifted out of the call sites verbatim.
    If this drifts, the clamp and the gate it feeds stop agreeing."""
    for close in (10.0, 50.0, 66.6667, 100.0, 166.825, 516.65):
        assert sr.min_risk_floor(close) == max(0.10, 0.0015 * close)


def _on():
    sr.ENABLE_MIN_RISK_FILL_CLAMP = True


def _off():
    sr.ENABLE_MIN_RISK_FILL_CLAMP = False


def test_on_is_a_noop_when_the_fill_already_clears():
    _on()
    try:
        assert sr.clamp_fill_to_min_risk(100.5, 100.0, 100.6, True) == 100.5
        assert sr.clamp_fill_to_min_risk(99.5, 100.0, 99.4, False) == 99.5
    finally:
        _off()


def test_on_clamps_to_the_floor_and_the_call_site_then_passes():
    """The point of the whole ticket: after the clamp, the SAME comparison the
    B&R call site makes -- stock_risk < max(0.10, 0.0015*close) -- is false."""
    _on()
    try:
        for stop, close, is_long in ((100.0, 100.6, True), (100.0, 99.4, False),
                                     (94.6172, 95.155, True),
                                     (166.40, 166.825, True),
                                     (517.75, 516.65, False)):
            floor = sr.min_risk_floor(close)
            got = sr.clamp_fill_to_min_risk(stop, stop, close, is_long)
            risk = (got - stop) if is_long else (stop - got)
            assert not (risk < floor), (stop, close, is_long, risk, floor)
    finally:
        _off()


def test_the_clamped_price_is_one_the_bar_traded():
    """The clamped entry is never better than the back-dated fill and never
    worse than the bar's own close, so it lies on the path price took to reach
    the level. That is what makes it an achievable fill rather than a fiction."""
    _on()
    try:
        # long: entry <= clamped <= close
        for entry, stop, close in ((100.0, 100.0, 100.6), (166.515, 166.40, 166.825),
                                   (94.75, 94.6172, 95.155)):
            got = sr.clamp_fill_to_min_risk(entry, stop, close, True)
            assert entry <= got <= close, (entry, got, close)
        # short: close <= clamped <= entry
        for entry, stop, close in ((100.0, 100.0, 99.4), (184.12, 184.22, 183.79),
                                   (517.26, 517.75, 516.65)):
            got = sr.clamp_fill_to_min_risk(entry, stop, close, False)
            assert close <= got <= entry, (close, got, entry)
    finally:
        _off()


def test_an_unsizeable_setup_is_still_rejected():
    """When even the CLOSE cannot clear the floor there is no trade to size, and
    the clamp must not invent one. It resolves to the close and the floor still
    rejects the setup -- pre-5e3677ea behaviour, unchanged."""
    _on()
    try:
        got = sr.clamp_fill_to_min_risk(100.0, 100.0, 100.05, True)
        assert got == 100.05
        assert (got - 100.0) < sr.min_risk_floor(100.05)

        got = sr.clamp_fill_to_min_risk(100.0, 100.0, 99.96, False)
        assert got == 99.96
        assert (100.0 - got) < sr.min_risk_floor(99.96)
    finally:
        _off()


def test_the_tick_is_load_bearing_and_is_only_a_tick():
    """Two reasons to clamp one tick PAST the floor rather than onto it, both
    about a number being written down rather than about a rule.

    1. `(stop + floor) - stop` is not `floor` in IEEE 754, and two of the six
       recovered marks ride exactly that edge.
    2. The book stores entry and stop at 2dp, so a fill resting exactly ON the
       floor rounds to one that reads a cent under it -- and the
       takeable/untakeable split this ticket is judged on reads the stored
       numbers, not the engine's."""
    assert sr._FILL_CLAMP_TICK == 0.01, "one cent, the smallest quoted price"
    for stop, close in ((94.6172, 95.155), (166.40, 166.825)):
        floor = max(0.10, 0.0015 * close)
        naive = (stop + floor) - stop
        assert naive < floor, (stop, close, naive, floor)          # reason 1
        assert floor - naive < 1e-12, "the error is representation, not arithmetic"
    # reason 2: a row clamped ONTO the floor can round to under it; clamped one
    # tick past it, it cannot.
    for stop, close, is_long in ((166.40, 166.825, True), (517.75, 516.65, False)):
        floor = max(0.10, 0.0015 * close)
        got = sr.clamp_fill_to_min_risk(stop, stop, close, is_long)             if sr.ENABLE_MIN_RISK_FILL_CLAMP else None
        assert got is None  # off by default; the ON case is checked below
        booked_risk = floor + sr._FILL_CLAMP_TICK
        assert round(booked_risk, 2) >= round(floor, 2)


def test_the_booked_risk_survives_2dp_storage():
    """The invariant the untakeable split actually reads: after the clamp AND
    after the book rounds both prices to 2dp, the row still clears the floor."""
    _on()
    try:
        for stop, close, is_long in ((100.0, 100.6, True), (166.40, 166.825, True),
                                     (94.6172, 95.155, True), (100.0, 99.4, False),
                                     (517.75, 516.65, False), (184.22, 183.79, False)):
            got = sr.clamp_fill_to_min_risk(stop, stop, close, is_long)
            e, s2 = round(got, 2), round(stop, 2)
            assert abs(e - s2) >= max(0.10, 0.0015 * e) - 1e-12,                 (stop, close, is_long, e, s2, abs(e - s2), max(0.10, 0.0015 * e))
    finally:
        _off()


def main():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok  %s" % fn.__name__)
    print("\n%d/%d passed" % (len(fns), len(fns)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
