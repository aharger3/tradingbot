import os, sys
import numpy as np
import pytest
sys.path.insert(0, os.path.dirname(__file__))
import e7_close_stop as e7

T = e7.TICK


def mk(bars, n=91):
    A = {k: np.full(n, np.nan) for k in ("open", "high", "low", "close")}
    for j, (o, h, l, c) in enumerate(bars):
        A["open"][j], A["high"][j], A["low"][j], A["close"][j] = o, h, l, c
    return A


# long: entry bar 0, open 100 -> fill 100.25, dist 4 -> stop 96.25, target 108.25, disaster (1.25R) 95.25
def test_wick_stop_fires_on_touch():
    A = mk([(100, 101, 100, 100.5), (100.5, 101, 96, 100), (100, 101, 99, 100)])
    px, why = e7.simulate(A, 1, 0, 4.0, "wick", cut=3)
    assert why == "stop" and px == 96.25 - T


def test_close_stop_survives_wick_that_closes_back():
    A = mk([(100, 101, 100, 100.5), (100.5, 101, 96, 100), (100, 101, 99, 100)])
    px, why = e7.simulate(A, 1, 0, 4.0, "close", 1.25, cut=3)
    assert why == "flat"  # low 96 pierced the stop (above the 95.25 disaster line) but the bar closed back inside


def test_close_stop_exits_at_close_minus_tick():
    A = mk([(100, 101, 100, 100.5), (100.5, 101, 95.5, 96.0), (96, 97, 95, 96)])
    px, why = e7.simulate(A, 1, 0, 4.0, "close", 1.25, cut=3)
    assert why == "close_stop" and px == 96.0 - T


def test_close_next_mode_uses_next_open():
    A = mk([(100, 101, 100, 100.5), (100.5, 101, 95.5, 96.0), (94, 97, 93, 96)])
    px, why = e7.simulate(A, 1, 0, 4.0, "close_next", 1.25, cut=3)
    assert why == "close_stop" and px == 94 - T


def test_wide_is_plain_hard_stop_at_cap():
    A = mk([(100, 101, 100, 100.5), (100.5, 101, 95.5, 99), (99, 100, 90, 99)])
    px, why = e7.simulate(A, 1, 0, 4.0, "wide", 1.25, cut=4)
    assert why == "stop" and px == 95.25 - T and e7.simulate(A, 1, 0, 4.0, "wide", 1.0, cut=4)[0] == 96.25 - T


def test_disaster_stop_on_touch_beyond_cap():
    A = mk([(100, 101, 100, 100.5), (100.5, 101, 90, 99)])
    px, why = e7.simulate(A, 1, 0, 4.0, "close", 1.25, cut=3)
    assert why == "disaster" and px == 95.25 - T


def test_gap_through_disaster_fills_at_open():
    A = mk([(100, 101, 100, 100.5), (90, 91, 89, 90)])
    px, why = e7.simulate(A, 1, 0, 4.0, "close", 1.25, cut=3)
    assert why == "disaster" and px == 90 - T


def test_cap_one_equals_wick_everywhere():
    rng = np.random.default_rng(1)
    for _ in range(300):
        c = 100 + np.cumsum(rng.normal(0, 1.2, 30))
        o = np.r_[100, c[:-1]]
        h = np.maximum(o, c) + rng.random(30)
        l = np.minimum(o, c) - rng.random(30)
        A = mk(list(zip(o, h, l, c)))
        for side in (1, -1):
            a = e7.simulate(A, side, 0, 3.0, "wick", cut=25)
            b = e7.simulate(A, side, 0, 3.0, "close", 1.0, cut=25)
            assert a[0] == pytest.approx(b[0])


def test_same_bar_stop_wins_over_target():
    A = mk([(100, 101, 100, 100.5), (100.5, 109, 96, 96.0)])  # closes past stop and touches target
    assert e7.simulate(A, 1, 0, 4.0, "close", 1.25, cut=3)[1] == "close_stop"
    assert e7.simulate(A, 1, 0, 4.0, "wick", cut=3)[1] == "stop"


def test_short_mirror():
    A = mk([(100, 100, 99, 99.5), (99.5, 104.5, 99, 104.0)])  # short fill 99.75, stop 103.75
    px, why = e7.simulate(A, -1, 0, 4.0, "close", 1.25, cut=3)
    assert why == "close_stop" and px == 104.0 + T


def test_paired_perm_basics():
    assert e7.paired_perm(np.zeros(20)) == 1.0
    assert e7.paired_perm(np.full(30, 0.3)) < 0.001
    assert e7.paired_perm(np.r_[np.full(15, 0.3), np.full(15, -0.3)]) > 0.4


def test_top5_share():
    assert e7.top5_share(np.array([5, 1, 1, 1, 1, 1, -4.0])) == pytest.approx(9 / 6)
    assert e7.top5_share(np.array([-1.0, -2.0])) is None


@pytest.mark.skipif(not os.path.exists(os.path.join(e7.AR, "t01-orb5", "fut")), reason="needs local NQ data")
def test_wick_baseline_reproduces_frozen_mantra():
    days = e7.load_fit()
    assert days[0]["date"] >= "2024-09-26"  # window A is never loaded
    ent = e7.find_entries(days)
    assert len(ent) == 105
    R = []
    for e in ent:
        A = days[e["k"]]
        px, _ = e7.simulate(A, e["side"], e["i"], e["dist"], "wick")
        fill = A["open"][e["i"]] + T * e["side"]
        stop = fill - e["side"] * e["dist"]
        assert px == e7.orb1m.sim(A, e["side"], e["i"], stop, fill + e["side"] * 2 * e["dist"], e7.CUT)
        r = e7.to_R(A, e["side"], e["i"], e["dist"], px)
        assert r == pytest.approx(e7.mnq.trade(A, e["i"], e["side"], e["dist"], e7.CUT, e["j"], "2R")[0])
        R.append(r)
    assert np.mean(R) == pytest.approx(0.3092672630906555, abs=1e-9)
