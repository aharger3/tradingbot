"""test_loop_gate.py -- O4's gate arithmetic, on synthetic books.

Covers: the no-regression gate's percentage math (a 4.9% $/day fall passes,
5.1% fails, a rise passes, a negative-baseline gate reads "may not get more
than N% worse"), a green-months fall failing on its own, the two halves
being scored independently, the halves boundary itself, and all three
trade-set units. No real book is read here -- backtest_2y.py is never run
by this file (that is what --smoke is for, exercised separately)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import loop_cycle as lc


def mk(trades=40, months=13, months_green=13, per_day=100.0):
    return {"trades": trades, "months": months, "months_green": months_green,
            "per_day": per_day}


class TestGatePercentage(unittest.TestCase):
    def test_4_9_pct_fall_passes(self):
        v = lc.half_verdict(mk(per_day=100.0), mk(per_day=95.1), 5.0)
        self.assertTrue(v["enough"])
        self.assertTrue(v["pass"])

    def test_5_1_pct_fall_fails(self):
        v = lc.half_verdict(mk(per_day=100.0), mk(per_day=94.9), 5.0)
        self.assertTrue(v["enough"])
        self.assertFalse(v["pass"])

    def test_exactly_5_pct_fall_passes(self):
        v = lc.half_verdict(mk(per_day=100.0), mk(per_day=95.0), 5.0)
        self.assertTrue(v["pass"])

    def test_rise_passes(self):
        v = lc.half_verdict(mk(per_day=100.0), mk(per_day=150.0), 5.0)
        self.assertTrue(v["pass"])

    def test_negative_baseline_5_1_pct_worse_fails(self):
        # baseline already losing $100/day; losing $105.10/day is > 5% worse
        v = lc.half_verdict(mk(per_day=-100.0), mk(per_day=-105.1), 5.0)
        self.assertFalse(v["pass"])

    def test_negative_baseline_4_9_pct_worse_passes(self):
        v = lc.half_verdict(mk(per_day=-100.0), mk(per_day=-104.9), 5.0)
        self.assertTrue(v["pass"])

    def test_zero_baseline_any_nonnegative_passes(self):
        v = lc.half_verdict(mk(per_day=0.0), mk(per_day=0.0), 5.0)
        self.assertTrue(v["pass"])


class TestGateGreenMonths(unittest.TestCase):
    def test_green_months_fall_by_one_fails(self):
        v = lc.half_verdict(mk(months_green=13), mk(months_green=12), 5.0)
        self.assertFalse(v["pass"])

    def test_green_months_unchanged_with_good_dollars_passes(self):
        v = lc.half_verdict(mk(months_green=13, per_day=100.0),
                            mk(months_green=13, per_day=100.0), 5.0)
        self.assertTrue(v["pass"])

    def test_green_months_rise_passes(self):
        v = lc.half_verdict(mk(months_green=13), mk(months_green=14), 5.0)
        self.assertTrue(v["pass"])


class TestSampleSizeFloor(unittest.TestCase):
    def test_under_30_trades_is_not_enough(self):
        v = lc.half_verdict(mk(trades=29, months=13), mk(trades=29, months=13), 5.0)
        self.assertFalse(v["enough"])
        self.assertIsNone(v["pass"])

    def test_under_12_months_is_not_enough(self):
        v = lc.half_verdict(mk(trades=40, months=11), mk(trades=40, months=11), 5.0)
        self.assertFalse(v["enough"])
        self.assertIsNone(v["pass"])

    def test_exactly_30_trades_12_months_is_enough(self):
        v = lc.half_verdict(mk(trades=30, months=12), mk(trades=30, months=12), 5.0)
        self.assertTrue(v["enough"])


class TestHalvesIndependent(unittest.TestCase):
    def test_h1_fail_h2_pass_overall_hold(self):
        # loop_cycle's own decision rule: ship only if BOTH halves pass.
        h1 = lc.half_verdict(mk(months_green=13), mk(months_green=12), 5.0)  # fails
        h2 = lc.half_verdict(mk(months_green=13), mk(months_green=13), 5.0)  # passes
        decision = "ship" if (h1["enough"] and h1["pass"] and h2["enough"] and h2["pass"]) else "hold"
        self.assertFalse(h1["pass"])
        self.assertTrue(h2["pass"])
        self.assertEqual(decision, "hold")


class TestHalvesSplit(unittest.TestCase):
    def test_boundary_is_inclusive_to_h2(self):
        rows = [{"day": "2025-08-31"}, {"day": "2025-09-01"}, {"day": "2025-09-02"}]
        h1, h2 = lc.split_halves(rows, "2025-09-01")
        self.assertEqual([r["day"] for r in h1], ["2025-08-31"])
        self.assertEqual([r["day"] for r in h2], ["2025-09-01", "2025-09-02"])

    def test_half_n_days_matches_split(self):
        rows = [{"day": "2025-08-30"}, {"day": "2025-08-31"}, {"day": "2025-09-01"}]
        n1, n2 = lc.half_n_days(rows, "2025-09-01")
        self.assertEqual((n1, n2), (2, 1))


class TestUnits(unittest.TestCase):
    def _rows(self):
        return [
            {"day": "2026-01-02", "et": "09:35", "sym": "AAA", "status": "fired",
             "traded": True, "pnl": 100.0},
            {"day": "2026-01-02", "et": "09:40", "sym": "BBB", "status": "fired",
             "traded": True, "pnl": -50.0},
            {"day": "2026-01-02", "et": "09:50", "sym": "CCC", "status": "fired",
             "traded": True, "pnl": -50.0},
            {"day": "2026-01-02", "et": "10:00", "sym": "DDD", "status": "fired",
             "traded": True, "pnl": 200.0},
            {"day": "2026-01-03", "et": "09:35", "sym": "AAA", "status": "fired",
             "traded": True, "pnl": -10.0},
        ]

    def test_every_signal_takes_all_traded(self):
        out = lc.UNIT_FUNCS["every_signal"](self._rows())
        self.assertEqual(len(out), 5)

    def test_first_of_day_takes_one_per_day(self):
        out = lc.UNIT_FUNCS["first_of_day"](self._rows())
        self.assertEqual(len(out), 2)
        self.assertEqual((out[0]["day"], out[0]["sym"]), ("2026-01-02", "AAA"))
        self.assertEqual((out[1]["day"], out[1]["sym"]), ("2026-01-03", "AAA"))

    def test_up_to_3_stops_after_first_win(self):
        out = lc.UNIT_FUNCS["up_to_3_stop_win_or_2loss"](self._rows())
        day1 = [r for r in out if r["day"] == "2026-01-02"]
        self.assertEqual(len(day1), 1)              # AAA wins first, day stops
        self.assertEqual(day1[0]["sym"], "AAA")

    def test_up_to_3_stops_after_second_loss(self):
        rows = [
            {"day": "2026-02-01", "et": "09:35", "sym": "A", "status": "fired",
             "traded": True, "pnl": -10.0},
            {"day": "2026-02-01", "et": "09:40", "sym": "B", "status": "fired",
             "traded": True, "pnl": -10.0},
            {"day": "2026-02-01", "et": "09:45", "sym": "C", "status": "fired",
             "traded": True, "pnl": 50.0},           # never taken -- 2 losses already stopped the day
        ]
        out = lc.UNIT_FUNCS["up_to_3_stop_win_or_2loss"](rows)
        self.assertEqual([r["sym"] for r in out], ["A", "B"])

    def test_up_to_3_caps_at_three_with_no_win_or_2loss(self):
        rows = [
            {"day": "2026-03-01", "et": "09:35", "sym": "A", "status": "fired",
             "traded": True, "pnl": 0.0},
            {"day": "2026-03-01", "et": "09:40", "sym": "B", "status": "fired",
             "traded": True, "pnl": 0.0},
            {"day": "2026-03-01", "et": "09:45", "sym": "C", "status": "fired",
             "traded": True, "pnl": 0.0},
            {"day": "2026-03-01", "et": "09:50", "sym": "D", "status": "fired",
             "traded": True, "pnl": 500.0},          # 4th signal -- never reached, cap is 3
        ]
        out = lc.UNIT_FUNCS["up_to_3_stop_win_or_2loss"](rows)
        self.assertEqual([r["sym"] for r in out], ["A", "B", "C"])


class TestAvgWinLoss(unittest.TestCase):
    def test_avg_win_loss(self):
        rows = [{"pnl": 100.0}, {"pnl": -50.0}, {"pnl": 200.0}, {"pnl": -30.0}, {"pnl": 0.0}]
        aw, al = lc.avg_win_loss(rows)
        self.assertEqual(aw, 150.0)   # (100+200)/2
        self.assertEqual(al, 40.0)    # abs((-50-30)/2)

    def test_no_wins_or_losses(self):
        aw, al = lc.avg_win_loss([{"pnl": 0.0}])
        self.assertEqual((aw, al), (0.0, 0.0))


class TestTargetMet(unittest.TestCase):
    def test_target_met_when_all_three_hold(self):
        whole = {"per_day": 550.0, "avg_win_over_avg_loss": 2.1, "months": 25, "months_green": 25}
        self.assertTrue(lc.target_met(whole, {"dollars_per_day": 500, "avg_win_over_avg_loss": 2.0}))

    def test_target_missed_on_one_green_month(self):
        whole = {"per_day": 550.0, "avg_win_over_avg_loss": 2.1, "months": 25, "months_green": 24}
        self.assertFalse(lc.target_met(whole, {"dollars_per_day": 500, "avg_win_over_avg_loss": 2.0}))

    def test_target_missed_on_dollars(self):
        whole = {"per_day": 400.0, "avg_win_over_avg_loss": 2.1, "months": 25, "months_green": 25}
        self.assertFalse(lc.target_met(whole, {"dollars_per_day": 500, "avg_win_over_avg_loss": 2.0}))

    def test_no_months_never_met(self):
        whole = {"per_day": 9999.0, "avg_win_over_avg_loss": 9.0, "months": 0, "months_green": 0}
        self.assertFalse(lc.target_met(whole, {"dollars_per_day": 500, "avg_win_over_avg_loss": 2.0}))


if __name__ == "__main__":
    unittest.main()
