"""Tests for E6 (run: python -m pytest -q test_e6.py  or  python test_e6.py). Synthetic cases need no data; the real
data cases (baseline reproduction, loader equality, window guard, arm-bar parity) skip if the bars are not on disk."""
import os, sys
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e6
from e6 import TICK

N = 91


def day(bars, date="2025-01-02"):
    """bars: {minute: (o,h,l,c)}. Default filler: flat chop inside the opening range, never touching anything."""
    A = {k: np.full(N, 100.5) for k in ("open", "high", "low", "close")}
    A["high"][:] = 100.9
    A["low"][:] = 100.1
    for m, (o, h, l, c) in bars.items():
        A["open"][m], A["high"][m], A["low"][m], A["close"][m] = o, h, l, c
    A["date"] = date
    return A


def mirror(A, c=200.0):
    B = {"date": A["date"]}
    B["open"], B["close"] = c - A["open"], c - A["close"]
    B["high"], B["low"] = c - A["low"], c - A["high"]
    return B


OR = {i: (100.5, 101.0, 100.0, 100.5) for i in range(5)}


def long_case(retest, after, extra=None):
    """OR 100-101, bar5 break+displacement, bar6 drift (no touch), bar7 retest, bars 8.. = after."""
    bars = dict(OR)
    bars[5] = (100.9, 103.0, 100.9, 102.9)
    bars[6] = (102.9, 103.0, 102.0, 102.5)
    bars[7] = retest
    for k, v in after.items():
        bars[k] = v
    if extra:
        bars.update(extra)
    return day(bars)


def test_m1_touch_bar_entry_and_target():
    # touch bar 7 is an up bar that wicks to 101.0 then rallies to 102.4 -> stop-market at 101.5 fills in-bar
    A = long_case((102.0, 102.4, 101.0, 102.3), {8: (102.3, 102.6, 102.2, 102.5), 9: (102.5, 104.5, 102.4, 104.4)})
    t, nref = e6.e6_day(A, 0.25, False, strict=False)
    assert t["how"] == "touchbar" and t["k"] == 7 and t["side"] == 1
    assert t["e"] == 101.75 and t["stop"] == 100.75 and t["dist"] == 1.0
    assert t["x"] == 103.75                      # 2R target = 101.75 + 2.0
    assert t["R"] == pytest.approx(2.0 - 1.24 / 2.0)
    assert nref == 0


def test_m1_down_bar_touch_reach_is_close_not_high():
    # down bar (c < o): path O,H,L,C -> after the touch low the price only gets back to the close (101.2 < 101.5)
    A = long_case((102.0, 102.2, 101.0, 101.2), {8: (101.2, 101.3, 101.0, 101.1), 9: (101.1, 101.3, 101.0, 101.2)})
    t, _ = e6.e6_day(A, 0.25, False, strict=False)
    assert t is None or t["k"] != 7             # no touch-bar fill; with no later cross there is no trade at all
    assert t is None


def test_resting_order_fills_later_bar():
    A = long_case((102.0, 102.2, 101.0, 101.2), {8: (101.2, 101.6, 101.0, 101.5), 9: (101.5, 104.0, 101.4, 103.9)})
    t, _ = e6.e6_day(A, 0.25, False)
    assert t["how"] == "rest" and t["k"] == 8
    assert t["e"] == 101.75 and t["dist"] == 1.0 and t["x"] == 103.75


def test_same_bar_stop_wins():
    # bar 8 touches both the trigger (101.5) and the stop (100.75): stop wins, loss with 1 tick through
    A = long_case((102.0, 102.2, 101.0, 101.2), {8: (101.2, 101.6, 100.5, 101.4)})
    t, _ = e6.e6_day(A, 0.25, False)
    assert t["how"] == "stopwins" and t["k"] == 8
    assert t["x"] == 100.5                       # min(S=100.75, open=101.2) - tick
    assert t["R"] == pytest.approx((100.5 - 101.75) / 1.0 - 1.24 / 2.0)


def test_stop_only_cancels_and_rearms():
    # bar 8 breaks the retest low without reaching the trigger -> old order cancelled, re-armed on bar 8 low (100.25); bar 9 fills
    A = long_case((102.0, 102.2, 101.0, 101.2),
                  {8: (101.2, 101.3, 100.5, 101.1), 9: (101.1, 102.3, 100.9, 102.2), 10: (102.2, 105.0, 102.0, 104.9)})
    t, _ = e6.e6_day(A, 0.25, False)
    assert t is not None and t["k"] == 9 and t["stop"] == 100.25 and t["how"] == "rest"


def test_close_through_voids_pending():
    A = long_case((102.0, 102.2, 101.0, 101.2),
                  {8: (101.2, 101.3, 100.8, 100.9), 9: (100.9, 101.9, 100.9, 101.8)})   # bar 8 closes through 101 -> void
    t, _ = e6.e6_day(A, 0.25, False)
    assert t is None


def test_onwatch_refuses_close_at_day_high():
    # retest bar rallies to a new high; the bar after opens above the trigger and closes on the day high
    A = long_case((101.1, 103.5, 101.0, 103.5), {8: (103.5, 103.6, 103.55, 103.6)})
    off, n0 = e6.e6_day(A, 0.25, False)
    on, n1 = e6.e6_day(A, 0.25, True)
    assert off is not None and off["k"] == 8 and off["how"] == "rest" and n0 == 0
    assert on is None and n1 >= 1


def test_onwatch_allows_close_far_from_extreme():
    A = long_case((102.0, 102.4, 101.0, 102.3), {8: (102.3, 102.6, 102.2, 102.5), 9: (102.5, 104.8, 102.4, 104.7)})
    on, n1 = e6.e6_day(A, 0.25, True)
    assert on is not None and n1 == 0           # close 102.5 is 0.5 under the 103.0 day high; U = 0.25 x 1.4 = 0.35


def test_onwatch_entry_bar_fills_then_closes_at_day_high_is_never_dropped():
    # amendment_2: ON WATCH is decided at the ARMING close. Retest bar 7 closes 102.3, far enough under the 103.0 day high
    # (U = 0.25 x 1.0 = 0.25) so the order is armed; bar 8 fills intrabar (T=101.85) and then CLOSES AT THE DAY HIGH 104.0.
    # That close was unknowable at fill time: the trade must be booked exactly as with ON WATCH off, never silently dropped.
    A = long_case((102.0, 102.4, 101.0, 102.3), {8: (102.3, 104.0, 102.2, 104.0), 9: (104.0, 104.1, 103.9, 104.0)})
    off, n0 = e6.e6_day(A, 0.25, False)
    on, n1 = e6.e6_day(A, 0.25, True)
    assert off is not None and off["k"] == 8 and off["how"] == "rest" and off["e"] == 102.55
    assert A["close"][8] >= np.nanmax(A["high"][:9])                      # entry bar really closes at the day high
    assert on is not None, "entry-bar close at the day high silently dropped the trade (post-fill look-ahead)"
    assert n1 == 0 and on == off


def test_onwatch_decision_is_made_at_arming_and_ignores_later_bars():
    # retest closes AT the day high -> refused at bar 7 whatever bar 8 does; retest far from the high -> armed whatever bar 8 does
    for entry in [(103.5, 103.6, 103.55, 103.6), (103.5, 105.0, 101.2, 103.0), (103.5, 103.6, 100.0, 100.2)]:
        _, nr = e6.e6_day(long_case((101.1, 103.5, 101.0, 103.5), {8: entry}), 0.25, True)
        assert nr == 1
        _, na = e6.e6_day(long_case((102.0, 102.4, 101.0, 102.3), {8: (102.3, entry[1] + 1, entry[2], entry[3])}), 0.25, True)
        assert na == 0
    tr = []
    t, nr = e6.e6_day(long_case((101.1, 103.5, 101.0, 103.5), {8: (103.5, 103.6, 103.55, 103.6)}), 0.25, True, trace=tr)
    assert t is None and nr == 1 and tr and tr[0][0] == 7                  # refusal at the retest (arming) bar, not bar 8


def test_strict_never_fills_inside_the_retest_bar():
    A = long_case((102.0, 102.4, 101.0, 102.3), {8: (102.3, 102.5, 102.25, 102.4), 9: (102.4, 105.0, 102.3, 104.9)})
    t, _ = e6.e6_day(A, 0.25, False)
    assert t["k"] == 8 and t["how"] == "rest" and t["e"] == 102.55      # opened above T=101.5 -> open + 1 tick
    m1, _ = e6.e6_day(A, 0.25, False, strict=False)
    assert m1["k"] == 7 and m1["e"] == 101.75                           # the optimistic M1 path, for contrast


def test_strict_trigger_uses_retest_candle_range():
    # retest bar range 3.0 -> U = 0.25 x 3.0 = 0.75 -> T = 101.75; bar 8 high 101.7 misses, bar 9 high 101.8 fills at T
    A = long_case((102.0, 104.0, 101.0, 101.2), {8: (101.2, 101.7, 101.0, 101.3), 9: (101.3, 101.8, 101.1, 101.5)})
    t, _ = e6.e6_day(A, 0.25, False)
    assert t["k"] == 9 and t["e"] == 102.0 and t["stop"] == 100.75


@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("onw", [False, True])
@pytest.mark.parametrize("case", range(5))
def test_short_mirrors_long(case, onw, strict):
    cases = [
        long_case((102.0, 102.4, 101.0, 102.3), {9: (102.5, 104.5, 102.4, 104.4)}),
        long_case((102.0, 102.2, 101.0, 101.2), {8: (101.2, 101.6, 101.0, 101.5), 9: (101.5, 104.0, 101.4, 103.9)}),
        long_case((102.0, 102.2, 101.0, 101.2), {8: (101.2, 101.6, 100.5, 101.4)}),
        long_case((101.1, 103.5, 101.0, 103.5), {8: (103.5, 103.6, 103.0, 103.2)}),
        long_case((102.0, 102.2, 101.0, 101.2), {8: (101.2, 101.3, 100.5, 101.1), 9: (101.1, 102.3, 100.9, 102.2),
                                                  10: (102.2, 105.0, 102.0, 104.9)}),
    ]
    A = cases[case]
    tl, nl = e6.e6_day(A, 0.25, onw, strict=strict)
    ts, ns = e6.e6_day(mirror(A), 0.25, onw, strict=strict)
    assert nl == ns
    if tl is None:
        assert ts is None
    else:
        assert ts["side"] == -1 and ts["how"] == tl["how"] and ts["k"] == tl["k"]
        assert ts["R"] == pytest.approx(tl["R"])


def test_r_formula_matches_frozen_trade():
    import mnq
    A = long_case((102.0, 102.2, 101.0, 102.1), {8: (102.1, 102.3, 102.0, 102.2), 9: (102.2, 105.0, 102.1, 104.9)})
    s = mnq.signal(A, e6.CUT, 1.0, "strong", TICK, 99)
    assert s is not None
    i, side, stop, j = s
    e = A["open"][i] + TICK * side
    dist = (e - stop) * side
    r, _ = mnq.trade(A, i, side, dist, e6.CUT, j, "2R")
    x = e6.mnq.sim(A, side, i, stop, e + side * 2 * dist, e6.CUT)
    assert e6.r_of(e, x, side, dist) == pytest.approx(r)


def test_signflip_p():
    rng = np.random.default_rng(0)
    assert e6.signflip_p(np.zeros(50), nperm=2000) == 1.0
    big = rng.normal(0.5, 1.0, 120)
    assert e6.signflip_p(big, nperm=4000) < 0.01
    sym = rng.normal(0.0, 1.0, 120)
    assert e6.signflip_p(sym, nperm=4000) > 0.02
    assert e6.signflip_p(-np.abs(big), nperm=4000) > 0.95


def test_grid_is_declared_six():
    assert len(e6.GRID) == 6 and e6.TOLS == (0.15, 0.25, 0.35)


# ---- real data (skipped if the bars are not on disk)
@pytest.fixture(scope="module")
def days():
    if not os.path.isdir(e6.AR + r"\t01-orb5\fut"):
        pytest.skip("futures bars not on disk")
    return e6.load_fit_days()


def test_window_guard(days):
    assert days[0]["date"] >= e6.FIT_START and days[-1]["date"] <= e6.FIT_END
    assert all("2024-09-26" <= A["date"] <= "2026-09-25" for A in days)
    assert len(days) > 400


def test_loader_matches_frozen_loader(days):
    import mnq
    ref = {A["date"]: A for A in mnq.load_real() if e6.FIT_START <= A["date"] <= e6.FIT_END}
    assert set(ref) == {A["date"] for A in days}
    for A in days:
        for k in ("open", "high", "low", "close"):
            np.testing.assert_array_equal(A[k], ref[A["date"]][k])


def test_baseline_reproduces_frozen_105(days):
    B0 = [t for t in (e6.baseline_day(A) for A in days) if t]
    R = np.array([t["R"] for t in B0])
    assert len(B0) == 105
    assert R.mean() == pytest.approx(0.309, abs=0.002)


def test_first_arm_bar_matches_frozen_touch_bar(days):
    bad = 0
    n = 0
    for A in days:
        s = e6.mnq.signal(A, e6.CUT, e6.DK, "any", TICK, 99)
        tr = []
        e6.e6_day(A, 0.25, False, trace=tr)
        if s is None:
            continue
        n += 1
        if not tr or tr[0][0] != s[3] or tr[0][1] != s[1]:
            bad += 1
    assert n > 100 and bad <= 2, (bad, n)


if __name__ == "__main__":
    sys.exit(pytest.main(["-q", __file__]))
