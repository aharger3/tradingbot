import unittest
import numpy as np
import mentor_cells as m


def day(**kw):
    A = {k: np.full(91, 100.0) for k in ("open", "high", "low", "close")}
    A.update(h_open=100.0, h_close=101.0, pdh=120.0, pdl=90.0, date="2025-03-03")
    A.update(kw)
    return A


def orb_long():
    A = day()
    A["high"][:5] = 101.0; A["low"][:5] = 100.0; A["open"][:5] = 100.5; A["close"][:5] = 100.5
    A["open"][5], A["high"][5], A["low"][5], A["close"][5] = 100.9, 103.0, 100.9, 102.9   # break
    A["open"][6], A["high"][6], A["low"][6], A["close"][6] = 102.9, 103.0, 102.0, 102.5
    A["open"][7], A["high"][7], A["low"][7], A["close"][7] = 101.5, 102.1, 101.0, 102.0   # green retest touching 101
    for j in range(8, 91):
        A["open"][j] = 102.0 + (j - 8) * .5
        A["high"][j] = A["open"][j] + .5
        A["low"][j] = A["open"][j] - .1
        A["close"][j] = A["open"][j] + .4
    return A


class T(unittest.TestCase):
    def test_guard(self):
        with self.assertRaises(AssertionError):
            m.guard(["2024-09-25"])
        m.guard(["2024-09-26"])

    def test_bias_long_signal(self):
        self.assertEqual(m.signal_bias_orb5(orb_long()), (8, 1, 100.75))

    def test_bias_blocks_wrong_side(self):
        A = orb_long(); A["h_close"] = 99.0
        self.assertIsNone(m.signal_bias_orb5(A, True))
        self.assertEqual(m.signal_bias_orb5(A, False), (8, 1, 100.75))

    def test_close_through_voids(self):
        A = orb_long(); A["close"][6] = 100.9; A["low"][6] = 100.5
        self.assertNotEqual(m.signal_bias_orb5(A), (8, 1, 100.75))

    def test_trade_hits_2r(self):
        r, u = m.run_trade(orb_long(), 8, 1, 1.5)
        self.assertAlmostEqual(r, 2 - 1.24 / 3.0)

    def test_stop_same_bar_wins(self):
        A = orb_long(); A["low"][8] = 90.0; A["high"][8] = 120.0
        r, u = m.run_trade(A, 8, 1, 1.5)
        self.assertLess(r, -1.0)

    def test_sweep_long_same_bar_reclaim(self):
        A = day(pdl=99.0)
        A["open"][3], A["low"][3], A["close"][3], A["high"][3] = 99.5, 98.5, 99.4, 99.6
        self.assertEqual(m.signal_sweep_reclaim(A), (4, 1, 98.25))

    def test_sweep_needs_reclaim_within_5(self):
        A = day(pdl=99.0)
        A["open"][3], A["low"][3], A["close"][3], A["high"][3] = 98.8, 98.0, 98.5, 98.9
        for j in range(4, 12):
            A["open"][j] = A["close"][j] = 98.6; A["high"][j] = 98.7; A["low"][j] = 98.4
        A["close"][12] = 99.5; A["high"][12] = 99.6
        self.assertIsNone(m.signal_sweep_reclaim(A))

    def test_sweep_short(self):
        A = day(pdh=101.0)
        A["open"][3], A["high"][3], A["close"][3], A["low"][3] = 100.8, 101.5, 100.7, 100.6
        self.assertEqual(m.signal_sweep_reclaim(A), (4, -1, 101.75))

    def test_gap_start_below_no_signal(self):
        self.assertIsNone(m.signal_sweep_reclaim(day(pdl=105.0)))

    def test_evaluate_runs(self):
        res, tr = m.evaluate([orb_long()] + [day(date="2025-03-0%d" % k) for k in range(4, 7)], m.signal_bias_orb5, nshuf=20)
        self.assertEqual(res["n"], 1)


if __name__ == "__main__":
    unittest.main()
