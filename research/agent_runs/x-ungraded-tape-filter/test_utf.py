import numpy as np
from utf import pen_ticks, rs_signed, n_ctx


def arr(h, l, o=None, c=None):
    h = np.array(h, float); l = np.array(l, float)
    return dict(high=h, low=l, open=np.array(o if o else h, float), close=np.array(c if c else l, float))


def test_pen_long_and_short():
    A = arr([10, 12, 11, 11], [9, 10, 7.5, 9.75])
    assert pen_ticks(A, 1, 10.0, 0, 3) == 10.0      # low 7.5 -> 2.5 pts = 10 ticks through 10.0
    B = arr([10, 12, 13, 11], [9, 10, 10, 9])
    assert pen_ticks(B, -1, 10.0, 0, 3) == 12.0     # high 13 -> 3 pts = 12 ticks through 10.0


def test_rs_signed():
    nq = dict(open=np.array([100.0]), close=np.array([102.0]))
    es = dict(open=np.array([100.0]), close=np.array([101.0]))
    assert abs(rs_signed(nq, es, 0, 1) - 1.0) < 1e-9
    assert abs(rs_signed(nq, es, 0, -1) + 1.0) < 1e-9
    assert np.isnan(rs_signed(nq, None, 0, 1))


def test_nctx():
    assert n_ctx(True, True, False) == 2 and n_ctx(False, False, True) == 1
