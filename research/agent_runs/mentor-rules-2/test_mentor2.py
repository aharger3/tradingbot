import unittest
import numpy as np
import mentor2 as m


def day(price=100.0, **kw):
    A = {k: np.full(91, price) for k in ("open", "high", "low", "close")}
    A.update(pdh=price + 20, pdl=price - 20, pdc=price, date="2025-03-03", sym="X", up=True)
    A.update(kw)
    return A


def setbar(A, j, o, h, l, c):
    A["open"][j], A["high"][j], A["low"][j], A["close"][j] = o, h, l, c


def flat_to_end(A, start, px):
    for j in range(start, 91):
        setbar(A, j, px, px + .05, px - .05, px)


class Fills(unittest.TestCase):
    def test_nq_guard(self):
        with self.assertRaises(AssertionError):
            m.guard_nq(["2024-09-25"])
        m.guard_nq(["2024-09-26"])

    def test_timed_exit_stock(self):
        A = day()
        setbar(A, 5, 100, 100.1, 99.95, 100)
        for j in range(6, 91):
            setbar(A, j, 100.5, 101.0, 100.4, 100.9)
        r, u = m.run_trade(A, 5, 1, 0.50, m.SPEC_STK)    # e=100.01, stop 99.51, tgt 101.01 -> needs high >= 101.02
        # high 101.0 never reaches tgt+tick (101.02) -> flat exit at 11:00 open 100.5 - 0.01
        self.assertAlmostEqual(u, (100.5 - 0.01 - 100.01) - 0.01, places=6)

    def test_target_needs_tick_through(self):
        A = day()
        setbar(A, 5, 100, 100.1, 99.95, 100)
        setbar(A, 6, 100.5, 101.02, 100.4, 100.9)
        flat_to_end(A, 7, 100.9)
        r, u = m.run_trade(A, 5, 1, 0.50, m.SPEC_STK)
        self.assertAlmostEqual(u, (101.01 - 100.01) - 0.01, places=6)
        self.assertAlmostEqual(r, u / 0.5, places=6)

    def test_same_bar_stop_wins(self):
        A = day()
        setbar(A, 5, 100, 100.1, 99.95, 100)
        setbar(A, 6, 100.2, 103.0, 99.0, 100.0)
        r, u = m.run_trade(A, 5, 1, 0.50, m.SPEC_STK)
        self.assertLess(u, 0)
        self.assertAlmostEqual(u, (99.51 - 0.01 - 100.01) - 0.01, places=6)

    def test_gap_through_stop_uses_open(self):
        A = day()
        setbar(A, 5, 100, 100.1, 99.95, 100)
        setbar(A, 6, 98.0, 98.5, 97.0, 98.0)
        r, u = m.run_trade(A, 5, 1, 0.50, m.SPEC_STK)
        self.assertAlmostEqual(u, (98.0 - 0.01 - 100.01) - 0.01, places=6)

    def test_short_and_nq_costs(self):
        A = day(20000.0)
        setbar(A, 5, 20000, 20001, 19999, 20000)
        setbar(A, 6, 19990, 19995, 19900, 19910)
        flat_to_end(A, 7, 19910)
        r, u = m.run_trade(A, 5, -1, 20.0, m.SPEC_NQ)   # e=19999.75, tgt=19959.75 reached
        self.assertAlmostEqual(u, (19999.75 - 19959.75) * 2 - 1.24, places=6)
        self.assertAlmostEqual(r, u / 40.0, places=6)


class Rejection(unittest.TestCase):
    def nq(self, **kw):
        A = day(20000.0, pdh=20050.0, pdl=19950.0, pdc=20000.0)
        A.update(kw)
        return A

    def test_short_poke_and_close_under(self):
        A = self.nq()
        setbar(A, 4, 20040, 20049, 20038, 20045)
        setbar(A, 5, 20046, 20052, 20040, 20041)       # pokes 2 over PDH, closes under, red
        self.assertEqual(m.signal_rejection(A, 4, "candle"), (6, -1, 20052.25))

    def test_needs_prior_close_under(self):
        A = self.nq()
        setbar(A, 4, 20055, 20060, 20053, 20056)       # already above PDH
        setbar(A, 5, 20056, 20058, 20040, 20041)
        self.assertIsNone(m.signal_rejection(A, 4, "candle"))

    def test_needs_red_close(self):
        A = self.nq()
        setbar(A, 4, 20040, 20049, 20038, 20045)
        setbar(A, 5, 20040, 20052, 20039, 20049)       # closes under PDH but green
        self.assertIsNone(m.signal_rejection(A, 4, "candle"))

    def test_tolerance(self):
        A = self.nq()
        setbar(A, 4, 20040, 20049, 20038, 20045)
        setbar(A, 5, 20046, 20047, 20040, 20041)       # high 3 pts under PDH
        self.assertIsNone(m.signal_rejection(A, 1, "candle"))
        self.assertEqual(m.signal_rejection(A, 20, "candle"), (6, -1, 20047.25))   # 20 ticks = 5 pts

    def test_push5_stop(self):
        A = self.nq()
        setbar(A, 3, 20030, 20060, 20030, 20040)       # an earlier higher high inside 5 bars
        setbar(A, 4, 20040, 20049, 20038, 20045)
        setbar(A, 5, 20046, 20052, 20040, 20041)
        self.assertEqual(m.signal_rejection(A, 4, "push5")[2], 20060.25)

    def test_long_at_pdl(self):
        A = self.nq()
        setbar(A, 4, 19960, 19962, 19951, 19955)
        setbar(A, 5, 19954, 19960, 19948, 19958)       # undercut, closes over PDL, green
        self.assertEqual(m.signal_rejection(A, 4, "candle"), (6, 1, 19947.75))

    def test_window_end(self):
        A = self.nq()
        setbar(A, 61, 20046, 20052, 20040, 20041)      # signal bar 61 is too late (entry would be 62)
        self.assertIsNone(m.signal_rejection(A, 4, "candle"))
        A = self.nq()
        setbar(A, 60, 20046, 20052, 20040, 20041)      # last legal bar, entry 61
        self.assertEqual(m.signal_rejection(A, 4, "candle")[0], 61)


class ThreeBar(unittest.TestCase):
    def stk(self):
        return day(100.0, pdh=105.0, pdl=95.0, pdc=100.0)

    def bars5(self, A, b, o, h, l, c):
        """put a 5-min candle into minutes 5b..5b+4: first minute opens at o, last closes at c"""
        for j in range(5 * b, 5 * b + 5):
            setbar(A, j, (o + c) / 2, (o + c) / 2 + .01, (o + c) / 2 - .01, (o + c) / 2)
        A["open"][5 * b] = o; A["close"][5 * b + 4] = c
        A["high"][5 * b + 2] = h; A["low"][5 * b + 3] = l

    def test_bearish_extreme(self):
        A = self.stk()
        self.bars5(A, 2, 104.0, 104.95, 103.9, 104.8)   # lead green, high within tol of PDH (0.25% = 0.2625)
        self.bars5(A, 3, 104.8, 105.0, 104.2, 104.3)    # reaction red
        self.bars5(A, 4, 104.3, 104.4, 103.4, 103.5)    # closes under lead low 103.9
        self.assertEqual(m.signal_three_bar(A, 0.0025, "extreme"), (25, -1, 105.01))

    def test_body_vs_extreme(self):
        A = self.stk()
        self.bars5(A, 2, 104.0, 104.95, 103.9, 104.8)
        self.bars5(A, 3, 104.8, 105.0, 104.2, 104.3)
        self.bars5(A, 4, 104.3, 104.4, 103.95, 103.97)  # under open 104.0 (body) but not under low 103.9
        self.assertIsNone(m.signal_three_bar(A, 0.0025, "extreme"))
        self.assertEqual(m.signal_three_bar(A, 0.0025, "body")[:2], (25, -1))

    def test_not_at_level(self):
        A = self.stk()
        self.bars5(A, 2, 102.0, 102.9, 101.9, 102.8)
        self.bars5(A, 3, 102.8, 102.9, 102.0, 102.1)
        self.bars5(A, 4, 102.1, 102.2, 101.0, 101.1)
        self.assertIsNone(m.signal_three_bar(A, 0.0025, "extreme"))

    def test_bullish_mirror(self):
        A = self.stk()
        self.bars5(A, 1, 96.0, 96.1, 95.05, 95.2)       # lead red, low near PDL 95
        self.bars5(A, 2, 95.2, 95.9, 95.1, 95.8)        # reaction green
        self.bars5(A, 3, 95.8, 96.4, 95.7, 96.3)        # closes over lead high 96.1
        s = m.signal_three_bar(A, 0.0025, "extreme")
        self.assertEqual(s[:2], (20, 1))
        self.assertAlmostEqual(s[2], 95.05 - 0.01)

    def test_last_legal_candle(self):
        A = self.stk()
        self.bars5(A, 9, 104.0, 104.95, 103.9, 104.8)
        self.bars5(A, 10, 104.8, 105.0, 104.2, 104.3)
        self.bars5(A, 11, 104.3, 104.4, 103.4, 103.5)   # confirm candle 11 closes at minute 60 -> entry 60
        self.assertEqual(m.signal_three_bar(A, 0.0025, "extreme")[0], 60)
        B = self.stk()
        self.bars5(B, 10, 104.0, 104.95, 103.9, 104.8)
        self.bars5(B, 11, 104.8, 105.0, 104.2, 104.3)
        self.bars5(B, 12, 104.3, 104.4, 103.4, 103.5)   # too late
        self.assertIsNone(m.signal_three_bar(B, 0.0025, "extreme"))

    def test_agg(self):
        A = self.stk()
        for j in range(5):
            setbar(A, j, 100 + j, 101 + j, 99 + j, 100.5 + j)
        O, H, L, C = m.agg(A, 5)
        self.assertEqual((O[0], H[0], L[0], C[0]), (100, 105, 99, 104.5))


class PdhRetest(unittest.TestCase):
    def stk(self, **kw):
        A = day(100.0, pdh=101.0, pdl=95.0, pdc=100.5, up=True)
        A.update(kw)
        return A

    def make(self, A):
        for j in range(0, 3):
            setbar(A, j, 100.2, 100.6, 100.1, 100.4)
        setbar(A, 3, 100.4, 101.5, 100.4, 101.4)       # break: first close over 101
        setbar(A, 4, 101.4, 101.6, 101.3, 101.5)
        setbar(A, 5, 101.2, 101.6, 100.9, 101.5)       # retest: low under PDH+tick, green, close over 101
        flat_to_end(A, 6, 101.5)
        return A

    def test_candle_stop(self):
        A = self.make(self.stk())
        self.assertEqual(m.signal_pdh_retest(A, 1, "candle", False), (6, 1, 100.89))

    def test_level_stop(self):
        A = self.make(self.stk())
        self.assertEqual(m.signal_pdh_retest(A, 1, "level", False), (6, 1, 100.99))

    def test_ema_filter(self):
        A = self.make(self.stk(up=False))
        self.assertIsNone(m.signal_pdh_retest(A, 1, "candle", True))
        self.assertIsNotNone(m.signal_pdh_retest(A, 1, "candle", False))

    def test_close_back_under_voids(self):
        A = self.make(self.stk())
        setbar(A, 4, 101.4, 101.5, 100.5, 100.8)       # closes back under PDH: void
        setbar(A, 5, 100.8, 101.0, 100.7, 100.9)
        self.assertIsNone(m.signal_pdh_retest(A, 1, "candle", False))

    def test_retest_must_be_green(self):
        A = self.make(self.stk())
        setbar(A, 5, 101.5, 101.6, 100.9, 101.1)       # red retest candle (close 101.1 < open 101.5)
        flat_to_end(A, 6, 101.2)
        self.assertIsNone(m.signal_pdh_retest(A, 1, "candle", False))

    def test_gap_open_counts_as_break(self):
        A = self.stk(pdc=100.5)
        setbar(A, 0, 102.0, 102.2, 101.8, 102.0)       # opens over PDH 101: break at bar 0
        setbar(A, 1, 102.0, 102.1, 100.95, 101.5)      # pullback to PDH, green? close 101.5 < open 102.0 -> red
        setbar(A, 2, 101.5, 101.9, 100.9, 101.8)       # touches, green, closes over
        flat_to_end(A, 3, 101.8)
        s = m.signal_pdh_retest(A, 1, "candle", False)
        self.assertEqual(s[0], 3)

    def test_5m_timeframe(self):
        A = self.stk()
        for j in range(0, 5):
            setbar(A, j, 100.2, 100.6, 100.1, 100.4)
        for j in range(5, 10):
            setbar(A, j, 101.2, 101.6, 101.1, 101.4)   # 5m candle 1 closes 101.4 over PDH: break
        setbar(A, 10, 101.4, 101.5, 101.3, 101.4)
        for j in range(11, 14):
            setbar(A, j, 101.2, 101.3, 100.9, 101.2)
        setbar(A, 14, 101.2, 101.6, 101.0, 101.5)      # 5m candle 2 (10..14): open 101.4, close 101.5 green, low 100.9
        flat_to_end(A, 15, 101.5)
        self.assertEqual(m.signal_pdh_retest(A, 5, "level", False)[:2], (15, 1))


class Calendar(unittest.TestCase):
    def test_prev_session(self):
        self.assertEqual(m.PREV_OF["2024-09-26"], "2024-09-25")
        self.assertEqual(m.PREV_OF["2024-11-29"], "2024-11-27")      # Thanksgiving skipped
        self.assertEqual(m.PREV_OF["2025-01-10"], "2025-01-08")      # day of mourning skipped
        self.assertEqual(m.PREV_OF["2025-03-03"], "2025-02-28")      # weekend skipped
        self.assertNotIn("2025-07-04", m.PREV_OF)


class Stats(unittest.TestCase):
    def test_summarize_and_bar(self):
        tr = [dict(date="2025-01-0%d" % (k % 9 + 1), R=0.4 if k % 2 else -0.1, pct=.002, side=1, up=True) for k in range(40)]
        s = m.summarize(tr, "2025-01-05")
        self.assertEqual(s["n"], 40)
        self.assertTrue(m.clears_std(s, 0.01))
        self.assertFalse(m.clears_std(s, 0.2))
        self.assertFalse(m.clears_std(dict(s, n=29), 0.01))
        self.assertFalse(m.clears_std(dict(s, meanR=0.14), 0.01))
        self.assertFalse(m.clears_std(dict(s, h2_meanR=-0.01), 0.01))

    def test_shuffle_maps_to_other_dates(self):
        sess = {"X": {}}
        for k in range(6):
            A = day(100.0, date="2025-03-0%d" % (k + 1))
            setbar(A, 5, 100, 100.1, 99.95, 100)
            for j in range(6, 91):
                setbar(A, j, 100.5, 101.5, 100.4, 101.4)   # winner after bar 5 on every day except day 0
            if k == 0:
                for j in range(6, 91):
                    setbar(A, j, 99.0, 99.2, 98.0, 98.5)    # a loser: only this day loses
            sess["X"][A["date"]] = A
        trades = [dict(sym="X", date="2025-03-01", i=5, side=1, pct=0.005, R=-1.0)]
        out = m.shuffle_means({"v": trades}, sess, m.SPEC_STK, ndraw=50, seed=3)["v"]
        self.assertTrue((out > 0).all())                    # never replayed on its own (losing) date
        # real mean -1R sits far under every shuffle -> p of "real >= shuffles" is the minimum bound... check +1 rule
        self.assertAlmostEqual(m.perm_p(5.0, out), 1 / 51)

    def test_flag_perm_p(self):
        tr = [dict(R=1.0, up=True)] * 20 + [dict(R=-1.0, up=False)] * 20
        d, p = m.flag_perm_p(tr, ndraw=300)
        self.assertAlmostEqual(d, 2.0)
        self.assertLess(p, 0.01)


class NoLookahead(unittest.TestCase):
    """overwrite every bar from the entry minute on with garbage: the signal (entry minute, side, stop) must not move"""

    def walk(self, seed, tick):
        rng = np.random.default_rng(seed)
        A = {k: np.empty(91) for k in ("open", "high", "low", "close")}
        px = 100.0
        for j in range(91):
            o = px; c = o + rng.normal(0, 0.12); h = max(o, c) + abs(rng.normal(0, 0.06)); l = min(o, c) - abs(rng.normal(0, 0.06))
            A["open"][j], A["high"][j], A["low"][j], A["close"][j] = o, h, l, c
            px = c
        A.update(pdh=100.6, pdl=99.3, pdc=100.0, date="2025-03-03", sym="X", up=True)
        return A

    def scramble(self, A, i, seed):
        B = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in A.items()}
        rng = np.random.default_rng(seed)
        n = 91 - i
        for k in ("open", "high", "low", "close"):
            B[k][i:] = 50 + rng.random(n) * 100
        return B

    def check(self, fn):
        hits = 0
        for seed in range(400):
            A = self.walk(seed, .01)
            s = fn(A)
            if not s:
                continue
            hits += 1
            B = self.scramble(A, s[0], seed)
            # the entry bar's own open may be read to confirm it exists; its values are not used by the signal
            B["open"][s[0]] = A["open"][s[0]]
            self.assertEqual(fn(B), s)
        self.assertGreater(hits, 10)

    def test_rejection(self):
        self.check(lambda A: m.signal_rejection(A, 4, "push5"))

    def test_three_bar(self):
        self.check(lambda A: m.signal_three_bar(A, 0.0025, "body"))

    def test_pdh_retest_1m(self):
        self.check(lambda A: m.signal_pdh_retest(A, 1, "candle", False))

    def test_pdh_retest_5m(self):
        self.check(lambda A: m.signal_pdh_retest(A, 5, "level", False))


if __name__ == "__main__":
    unittest.main()
