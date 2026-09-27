import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import tgt


def day(bars):
    """bars: list of (o,h,l,c) from minute 0; rest NaN."""
    A = {k: np.full(91, np.nan) for k in ("open", "high", "low", "close")}
    for m, (o, h, l, c) in enumerate(bars):
        A["open"][m], A["high"][m], A["low"][m], A["close"][m] = o, h, l, c
    return A


def test_target_needs_one_tick_through():
    # long, fill 100.25 (open 100 + 1 tick), dist 1.0 -> 2R tgt 102.25; high exactly 102.25 is NOT a fill
    A = day([(100, 100.5, 99.9, 100.2), (100.2, 102.25, 100.0, 102.0), (102.0, 102.0, 99.0, 99.0)] + [(99.0, 99.0, 99.0, 99.0)] * 70)
    r, _ = tgt.trade_k(A, 0, 1, 1.0, 2.0)
    assert abs(r - (-1.25 - 0.62)) < 1e-9  # exact touch no fill -> stopped next bar
    r15, _ = tgt.trade_k(A, 0, 1, 1.0, 1.5)
    assert abs(r15 - (1.5 - 0.62)) < 1e-9


def test_stop_wins_same_bar():
    A = day([(100, 103, 99.0, 101)] + [(101, 101, 101, 101)] * 70)
    r, _ = tgt.trade_k(A, 0, 1, 1.0, 1.5)
    assert r < -1.0  # stop 99.25 hit, filled 99.0 (min(stop, open)=99.25 -1 tick) + comm


def test_runner_flat_at_cut_open():
    bars = [(100, 100.5, 99.9, 100.2)] + [(100.2 + 0.1 * m, 100.3 + 0.1 * m, 100.1 + 0.1 * m, 100.25 + 0.1 * m) for m in range(1, 91)]
    A = day(bars)
    r, u = tgt.trade_k(A, 0, 1, 1.0, None)
    fill = 100.25; exit_px = A["open"][60] - 0.25
    n = min(50, int(200 // (1.0 * 2 + 1.24)))
    assert abs(u - ((exit_px - fill) * n * 2 - n * 1.24)) < 1e-9


def test_short_mirror_and_mfe():
    A = day([(100, 100.1, 99.5, 99.6), (99.6, 99.7, 97.0, 97.5), (97.5, 101.0, 97.4, 100.9)] + [(100.9,) * 4] * 70)
    # short fill 99.75, dist 1 -> stop 100.75; bar1 low 97.0 -> MFE 2.75R; bar2 stops out
    b, ns = tgt.mfe(A, 0, -1, 1.0)
    assert abs(b - 2.75) < 1e-9 and abs(ns - 2.75) < 1e-9
    r, _ = tgt.trade_k(A, 0, -1, 1.0, 2.5)  # tgt 97.25, low 97.0 <= 97.25-0.25 -> fill at tgt
    assert abs(r - (2.5 - 0.62)) < 1e-9
