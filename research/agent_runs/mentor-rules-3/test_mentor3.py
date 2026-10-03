import os, tempfile, unittest
import numpy as np
import pandas as pd
import mentor3 as r


def day(price=1000.0, **kw):
    A = {k: np.full(91, price) for k in ("open", "high", "low", "close")}
    A.update(pdh=price + 50, pdl=price - 50, pdc=price, onh=price + 40, onl=price - 40, date="2025-03-03", sym="NQ")
    A.update(kw)
    return A


def setbar(A, j, o, h, l, c):
    A["open"][j], A["high"][j], A["low"][j], A["close"][j] = o, h, l, c


def flat(A, start, px, end=91):
    for j in range(start, end):
        setbar(A, j, px, px + .25, px - .25, px)


class Smt(unittest.TestCase):
    def pairdays(self):
        T, X = day(1000.0), day(5000.0, sym="ES")
        T["x"] = X
        return T, X

    def test_bullish_leader_nq_other_holds(self):
        T, X = self.pairdays()
        setbar(T, 3, 965, 966, 958, 962)            # NQ low 958 < ONL 960: sweep, bar closes under the level, red
        setbar(T, 4, 962, 970, 961, 968)            # reclaim: closes over 960 and green
        # ES never goes under its own ONL (4960): untouched at 5000
        self.assertEqual(r.smt_triggers(T, X, "ON"), [(4, 1)])
        self.assertEqual(r.signal_smt(T, "ON", "candle"), (5, 1, 961 - 0.25))
        self.assertEqual(r.signal_smt(T, "ON", "swing10"), (5, 1, 958 - 0.25))

    def test_bullish_leader_es_trade_nq(self):
        T, X = self.pairdays()
        setbar(X, 2, 4965, 4966, 4958, 4963)        # ES sweeps ONL 4960
        setbar(X, 3, 4963, 4975, 4962, 4972)        # ES reclaims
        sig = r.signal_smt(T, "ON", "candle")       # trades NQ, whose own candle low is 1000
        self.assertEqual(sig, (4, 1, 1000.0 - 0.25))

    def test_sweep_on_the_trigger_bar_itself(self):
        T, X = self.pairdays()
        setbar(T, 6, 962, 972, 958, 970)            # wick sweep, closes back over the level and green
        self.assertEqual(r.smt_triggers(T, X, "ON"), [(6, 1)])

    def test_both_swept_no_signal(self):
        T, X = self.pairdays()
        setbar(T, 3, 965, 966, 958, 962); setbar(T, 4, 962, 970, 961, 968)
        setbar(X, 3, 4965, 4966, 4958, 4962)        # ES also sweeps in the same bar
        self.assertEqual(r.smt_triggers(T, X, "ON"), [])
        self.assertIsNone(r.signal_smt(T, "ON", "candle"))

    def test_other_sweeps_before_trigger_voids(self):
        T, X = self.pairdays()
        setbar(T, 3, 965, 966, 958, 962)
        setbar(X, 4, 4965, 4966, 4958, 4962)        # ES sweeps at bar 4
        setbar(T, 4, 962, 970, 961, 968)            # NQ would reclaim at bar 4, but both swept by then
        self.assertEqual(r.smt_triggers(T, X, "ON"), [])

    def test_reclaim_window_15(self):
        T, X = self.pairdays()
        setbar(T, 2, 965, 966, 958, 962)            # first sweep at bar 2, no reclaim
        for j in range(3, 91):
            setbar(T, j, 955, 956, 954, 955)        # stays under 960, red or flat (close == open is not green)
        setbar(T, 17, 955, 966, 954, 965)           # bar 17 = 2 + 15: allowed
        self.assertEqual(r.smt_triggers(T, X, "ON"), [(17, 1)])
        T2, X2 = self.pairdays()
        setbar(T2, 2, 965, 966, 958, 962)
        for j in range(3, 91):
            setbar(T2, j, 955, 956, 954, 955)
        setbar(T2, 18, 955, 966, 954, 965)          # 16 bars after: too late
        self.assertEqual(r.smt_triggers(T2, X2, "ON"), [])

    def test_bearish_mirror_and_pd(self):
        T, X = self.pairdays()
        setbar(T, 5, 1045, 1052, 1040, 1048)        # NQ high 1052 > PDH 1050, closes under it and red? close 1048 < open 1045? no
        self.assertEqual(r.smt_triggers(T, X, "PD"), [])            # green bar: not a rejection
        setbar(T, 5, 1049, 1052, 1040, 1044)        # red, closes under 1050
        self.assertEqual(r.smt_triggers(T, X, "PD"), [(5, -1)])
        self.assertEqual(r.signal_smt(T, "PD", "candle"), (6, -1, 1052 + 0.25))
        self.assertEqual(r.smt_triggers(T, X, "ON"), [])            # closes at 1044, still over ONH 1040: no reclaim

    def test_conflict_skips_day(self):
        T, X = self.pairdays()
        # one bar that sweeps both the low and the high of NQ's overnight range and closes... cannot be both green and red;
        # build two different sweeping indices: NQ sweeps low and reclaims green, ES sweeps high and reclaims red, same bar
        setbar(T, 4, 962, 970, 958, 968)             # NQ bullish trigger, ES not swept low
        setbar(X, 4, 5045, 5048, 5030, 5035)         # ES high 5048 > ONH 5040: sweep, red, closes under 5040
        trig = r.smt_triggers(T, X, "ON")
        self.assertEqual(trig, [(4, -1), (4, 1)])
        self.assertIsNone(r.signal_smt(T, "ON", "candle"))

    def test_signal_window_and_nan(self):
        T, X = self.pairdays()
        setbar(T, 61, 962, 972, 958, 970)            # signal bar 61 closes after 10:30: out
        self.assertEqual(r.smt_triggers(T, X, "ON"), [])
        T, X = self.pairdays()
        setbar(T, 60, 962, 972, 958, 970)
        self.assertEqual(r.smt_triggers(T, X, "ON"), [(60, 1)])
        T["open"][61] = np.nan
        self.assertEqual(r.smt_triggers(T, X, "ON"), [])


class OpeningPrint(unittest.TestCase):
    def test_reject_short(self):
        A = day(1000.0, pdh=1200, pdl=800, onh=1100, onl=900)
        flat(A, 0, 990)
        setbar(A, 0, 1000, 1001, 989, 990)
        setbar(A, 3, 999, 1000.5, 994, 996)          # high reaches OP (1000), prev close 990 < OP, closes 996 red
        self.assertEqual(r.signal_op(A, "reject", "any"), (4, -1, 1001.0 + 0.25))   # swing stop: bar 0 high 1001 is in the last 10 bars

    def test_reject_long_and_first_bar_excluded(self):
        A = day(1000.0, pdh=1200, pdl=800, onh=1100, onl=900)
        flat(A, 0, 1010)
        setbar(A, 0, 1000, 1011, 999, 1010)
        setbar(A, 2, 1005, 1012, 1000.2, 1008)       # low 1000.2 <= OP + tol (1000.05)? no: 1000.2 > 1000.05 -> no touch
        self.assertIsNone(r.signal_op(A, "reject", "any"))
        setbar(A, 2, 1005, 1012, 1000.0, 1008)       # touches OP, prev close 1010 > OP, closes 1008 > OP green? 1008 > 1005 yes
        self.assertEqual(r.signal_op(A, "reject", "any"), (3, 1, 999.0 - 0.25))   # last 10 bars incl bar 0: min low 999

    def test_reject_tolerance_is_pct_of_op(self):
        A = day(1000.0)
        flat(A, 0, 990)
        setbar(A, 0, 1000, 1000.0, 989, 990)
        setbar(A, 3, 998, 999.96, 994, 996)          # tol = 0.05: high 999.96 >= 999.95 -> touches
        self.assertIsNotNone(r.signal_op(A, "reject", "any"))
        B = day(1000.0)
        flat(B, 0, 990)
        setbar(B, 0, 1000, 1000.0, 989, 990)
        setbar(B, 3, 998, 999.90, 994, 996)
        self.assertIsNone(r.signal_op(B, "reject", "any"))

    def test_reclaim_long_needs_dip(self):
        A = day(1000.0)
        flat(A, 0, 1000)
        setbar(A, 0, 1000, 1000.3, 999.8, 1000.1)
        for j in range(1, 5):
            setbar(A, j, 999.0, 999.2, 998.6, 999.0)            # low 998.6: only 1.4 under OP; dip needs 0.5 -> ok
        setbar(A, 5, 999.0, 1001.5, 998.9, 1001.0)              # closes over OP, green, prev close 999 <= OP
        sig = r.signal_op(A, "reclaim", "any")
        self.assertEqual(sig, (6, 1, 998.6 - 0.25))
        B = day(1000.0)
        flat(B, 0, 1000)
        setbar(B, 0, 1000, 1000.3, 999.8, 1000.1)
        for j in range(1, 5):
            setbar(B, j, 999.9, 999.95, 999.7, 999.9)            # dip only 0.3 < 0.5
        setbar(B, 5, 999.9, 1001.5, 999.8, 1001.0)
        self.assertIsNone(r.signal_op(B, "reclaim", "any"))

    def test_reclaim_short_mirror(self):
        A = day(1000.0)
        flat(A, 0, 1000)
        setbar(A, 0, 1000, 1000.2, 999.9, 1000.1)
        for j in range(1, 5):
            setbar(A, j, 1001.0, 1001.4, 1000.8, 1001.0)
        setbar(A, 5, 1001.0, 1001.1, 998.5, 999.0)
        self.assertEqual(r.signal_op(A, "reclaim", "any"), (6, -1, 1001.4 + 0.25))

    def test_near_filter(self):
        A = day(1000.0, pdh=1100, pdl=900, onh=1150, onl=850)          # nearest level 100 away > 1.25
        self.assertFalse(r.near_key_level(A))
        A2 = day(1000.0, pdh=1100, pdl=900, onh=1150, onl=999.0)       # 1.0 away <= 1.25
        self.assertTrue(r.near_key_level(A2))
        flat(A, 0, 990)
        setbar(A, 0, 1000, 1000.0, 989, 990)
        setbar(A, 3, 999, 1000.5, 994, 996)
        self.assertIsNotNone(r.signal_op(A, "reject", "any"))
        self.assertIsNone(r.signal_op(A, "reject", "near"))

    def test_variant_names_and_counts(self):
        self.assertEqual(len(r.n1_variants()), 4)
        self.assertEqual(sorted(r.n2_variants()), ["op_rec_any", "op_rec_near", "op_rej_any", "op_rej_near"])


class Specs(unittest.TestCase):
    def test_es_min_dist_two_ticks(self):
        self.assertEqual(r.min_dist(r.SPEC_ES, 6000.0), 0.5)
        self.assertEqual(r.min_dist(r.SPEC_NQ, 20000.0), 0.5)
        self.assertEqual(r.m.min_dist(r.SPEC_ES, 6000.0), 0.5)          # the patch reaches mentor2's callers
        self.assertAlmostEqual(r.m.min_dist(r.m.SPEC_STK, 100.0), 0.05)  # stocks unchanged

    def test_build_trades_es_skips_tiny_stop(self):
        A = day(6000.0); A["sym"] = "ES"
        flat(A, 0, 6000.0)
        tr, sk = r.m.build_trades([A], lambda a: (5, 1, 5999.75), r.SPEC_ES)   # e=6000.25, dist .5 -> ok (>=2 ticks)
        self.assertEqual((len(tr), sk), (1, 0))
        tr, sk = r.m.build_trades([A], lambda a: (5, 1, 6000.0), r.SPEC_ES)    # dist .25 < .5 -> skipped
        self.assertEqual((len(tr), sk), (0, 1))

    def test_es_dollar_math(self):
        A = day(6000.0); A["sym"] = "ES"
        flat(A, 0, 6000.0)
        for j in range(6, 91):
            setbar(A, j, 6004.0, 6012.0, 6003.0, 6010.0)                 # high 6012 >= tgt + tick
        r_, u = r.m.run_trade(A, 5, 1, 4.0, r.SPEC_ES)                    # e=6000.25 stop 5996.25 tgt 6008.25
        self.assertAlmostEqual(u, (6008.25 - 6000.25) * 5.0 - 1.24, places=6)
        self.assertAlmostEqual(r_, u / (4.0 * 5.0), places=6)


class Loader(unittest.TestCase):
    """a tiny synthetic NQ file: sessions Thu 09-26 (no prior: dropped), Fri 09-27, Mon 09-30"""

    def make(self, d):
        rows = []
        tz = "America/New_York"

        def add(ts, o, h, l, c, v=10):
            rows.append((pd.Timestamp(ts, tz=tz).value, o, h, l, c, v))
        add("2024-09-24 10:00", 1, 99999, 0.5, 1)                        # reserved: must never be read
        add("2024-09-25 20:00", 1, 88888, 0.5, 1)                        # reserved evening: never read
        for D in ("2024-09-26", "2024-09-27", "2024-09-30"):
            for mi in range(570, 960):
                ts = pd.Timestamp(D, tz=tz) + pd.Timedelta(minutes=mi)
                p = 100.0 + (mi - 570) * 0.01 + (50.0 if D == "2024-09-27" else 0.0)   # Friday RTH far above every overnight bar
                rows.append((ts.value, p, p + 0.5, p - 0.5, p + 0.1, 5))
        add("2024-09-26 18:00", 100, 110, 95, 100)                       # evening of 09-26 -> overnight of 09-27
        add("2024-09-27 03:00", 100, 111, 94, 100)                       # overnight of 09-27
        add("2024-09-27 09:29", 100, 105, 99, 100)
        add("2024-09-29 20:00", 100, 120, 90, 100)                       # Sunday evening -> overnight of Mon 09-30
        add("2024-09-30 04:00", 100, 118, 91, 100)
        for i in range(40):                                              # enough overnight bars for the >= 30 rule
            add(f"2024-09-26 19:{i:02d}", 100, 101, 99, 100)
            add(f"2024-09-29 21:{i:02d}", 100, 101, 99, 100)
        pd.DataFrame(rows, columns=["ts_ns", "open", "high", "low", "close", "volume"]).sort_values("ts_ns").to_csv(
            os.path.join(d, "NQZ4_2024.csv"), index=False)

    def test_load(self):
        with tempfile.TemporaryDirectory() as d:
            self.make(d)
            days = r.load_fut("NQ", fut=d)
            self.assertEqual([a["date"] for a in days], ["2024-09-27", "2024-09-30"])
            a, b = days
            self.assertTrue(all(x["date"] > "2024-09-25" for x in days))
            # prior-session RTH levels are the previous session's RTH extremes
            self.assertAlmostEqual(a["pdh"], 100.0 + 389 * 0.01 + 0.5, places=6)
            self.assertAlmostEqual(a["pdl"], 99.5, places=6)
            # overnight 09-27 = 09-26 16:00 .. 09-27 09:29 : max high 111, min low 94 (Thursday RTH tops out under 105)
            self.assertEqual((a["onh"], a["onl"]), (111.0, 94.0))
            # Monday: Friday 16:00 .. Monday 09:29 incl. Sunday evening: 120 / 90 (Friday RTH, up to ~154, must not leak in)
            self.assertEqual((b["onh"], b["onl"]), (120.0, 90.0))
            self.assertEqual(a["open"][0], 150.0)

    def test_align_requires_all_levels(self):
        with tempfile.TemporaryDirectory() as d:
            self.make(d)
            nq = r.load_fut("NQ", fut=d)
        es = [dict(a) for a in nq]
        es[1]["onh"] = np.nan
        n, e = r.align(nq, es)
        self.assertEqual(sorted(n), ["2024-09-27"])
        self.assertEqual(sorted(e), ["2024-09-27"])
        paired = r.pair(n, e)
        self.assertIs(paired[0]["x"], e["2024-09-27"])


if __name__ == "__main__":
    unittest.main()
