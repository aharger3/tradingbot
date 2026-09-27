import numpy as np
import ocr_pos as op


def mk(bars):
    O, H, L, C = (np.array(x, float) for x in zip(*bars))
    return dict(open=O, high=H, low=L, close=C)


def test_long_block_is_last_down_close_in_leg():
    # 0 break (up), 1 down-close 102-104, 2 up to extreme 106, 3 down-close AFTER extreme (ignored), 4 retest
    A = mk([(100, 103, 100, 103), (104, 104, 102, 102.5), (102.5, 106, 102.5, 105.5), (105.5, 105.6, 104, 104.2), (104, 104.5, 103, 104.4)])
    lo, hi, k, ext = op.find_block(A, 1, 0, 4)
    assert (lo, hi, k, ext) == (102, 104, 1, 2)
    assert op.block_pos(A, 1, 4, lo, hi) == 0.5  # retest low 103 = middle of 102-104


def test_short_is_mirrored_and_normalised():
    A = mk([(100, 100, 97, 97), (96, 98, 96, 97.5), (97.5, 97.5, 94, 94.5), (95, 97, 94.8, 95.5)])
    lo, hi, k, ext = op.find_block(A, -1, 0, 3)
    assert (lo, hi, k, ext) == (96, 98, 1, 2)
    assert op.block_pos(A, -1, 3, lo, hi) == 0.5   # retest high 97 mid-block
    A["high"][3] = 96.0
    assert op.block_pos(A, -1, 3, lo, hi) == 1.0   # touched only the near (shallow) edge = "higher" for a short


def test_no_opposite_close_in_leg():
    A = mk([(100, 103, 100, 103), (103, 105, 103, 105), (105, 105.2, 103.5, 104)])
    lo, hi, k, ext = op.find_block(A, 1, 0, 2)
    assert lo is None and ext == 1
    assert op.block_pos(A, 1, 2, lo, hi) is None


def test_tercile_table_detects_monotone_edge():
    rng = np.random.default_rng(0)
    pos = np.linspace(0, 1, 60)
    R = np.where(pos > 0.66, 2.0, -1.0)
    rows, diff = op.tercile_table(pos, R, pos < 0.5, rng)
    assert [r["n"] for r in rows] == [20, 20, 20]
    assert rows[2]["R"] == 2.0 and diff["p_diff"] < 0.01
