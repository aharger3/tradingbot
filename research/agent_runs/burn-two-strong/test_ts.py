import numpy as np
from ts import n_disp_candles, break_bar


def mk(rows):
    A = {k: np.full(91, np.nan) for k in ("open", "high", "low", "close")}
    for b, (o, h, l, c) in enumerate(rows):
        A["open"][b], A["high"][b], A["low"][b], A["close"][b] = o, h, l, c
    return A


def base():
    # 14 quiet bars (range 1) forming OR ~100..101
    return [(100, 101, 100, 100.5)] * 14


def test_two_strong_long():
    rows = base() + [(100.5, 103, 100.5, 102.8), (102.8, 105, 102.7, 104.9), (104.9, 105.2, 104, 104.2), (104.2, 104.5, 101, 101.2)]
    A = mk(rows)
    assert break_bar(A, 17, 1, 101) == 14
    assert n_disp_candles(A, 1, 14, 17) == 2


def test_weak_body_not_counted():
    rows = base() + [(100.5, 103, 100.5, 101.5), (101.5, 105, 101.4, 104.9), (104.9, 105.2, 104, 104.2), (104.2, 104.5, 101, 101.2)]
    assert n_disp_candles(mk(rows), 1, 14, 17) == 1


def test_short_mirror_and_leg_stops_at_extreme():
    rows = base() + [(100, 100, 97.5, 97.7), (97.7, 97.8, 96, 96.1), (96.1, 99, 96.1, 98.9), (98.9, 99.5, 98.5, 99.4)]
    # bar 16 is a big up (against) bar after the extreme at 15 -> excluded
    assert n_disp_candles(mk(rows), -1, 14, 17) == 2


def test_small_range_not_counted():
    rows = base() + [(100.5, 101.3, 100.5, 101.25), (101.25, 101.9, 101.2, 101.85), (101.8, 101.9, 101.2, 101.3)]
    assert n_disp_candles(mk(rows), 1, 14, 16) == 0
