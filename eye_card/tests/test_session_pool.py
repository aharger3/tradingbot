"""Tests for the rotating replay-session pool (eye_card/session_pool.py). Pure python, no market data.

Run:  python -m pytest eye_card/tests/test_session_pool.py -q   (from repo root)
"""
import json
import tempfile
import unittest
from pathlib import Path

from eye_card import session_pool as sp


def bars(day_vols, nbars=91):
    """{'date': [...], 'volume': [...]}: nbars one-minute bars per day summing to the day's volume."""
    d, v = [], []
    for day, tot in day_vols.items():
        n = nbars[day] if isinstance(nbars, dict) else nbars
        d += [day] * n
        v += [tot / n] * n
    return {"date": d, "volume": v}


class DateTests(unittest.TestCase):
    def test_dates_from_ids(self):
        self.assertEqual(sp.date_from_id("S43-1-20260907"), "2026-09-07")
        self.assertEqual(sp.date_from_id("EYE-S43-1-20260907-ab12"), "2026-09-07")
        self.assertIsNone(sp.date_from_id("EYE-87d6dfed"))
        self.assertIsNone(sp.date_from_id(""))


class LiquidTests(unittest.TestCase):
    DAYS = {"2025-01-06": 150_000, "2025-01-07": 160_000, "2025-01-08": 140_000, "2025-01-09": 150_000,
            "2025-01-10": 14_000}                                  # the last one is a Labor Day type tape

    def test_thin_day_is_out_normal_days_in(self):
        self.assertEqual(sp.liquid_sessions(bars(self.DAYS), start="2025-01-01", end="2025-12-31"),
                         ["2025-01-06", "2025-01-07", "2025-01-08", "2025-01-09"])

    def test_labor_day_2026_would_not_pass(self):
        days = {f"2026-09-0{i}": 150_000 for i in (1, 2, 3, 4, 8, 9)} | {"2026-09-07": 14_534}
        got = sp.liquid_sessions(bars(days), start="2024-09-27", end="2026-09-25")
        self.assertNotIn("2026-09-07", got)
        self.assertEqual(len(got), 6)

    def test_window_bounds_are_inclusive_and_outside_days_dropped(self):
        days = {"2024-09-26": 150_000, "2024-09-27": 150_000, "2026-09-25": 150_000, "2026-09-28": 150_000}
        self.assertEqual(sp.liquid_sessions(bars(days)), ["2024-09-27", "2026-09-25"])

    def test_short_session_is_out_even_with_volume(self):
        got = sp.liquid_sessions(bars(self.DAYS, nbars={**{d: 91 for d in self.DAYS}, "2025-01-06": 35}),
                                 start="2025-01-01", end="2025-12-31")
        self.assertNotIn("2025-01-06", got)

    def test_empty(self):
        self.assertEqual(sp.liquid_sessions({"date": [], "volume": []}), [])


class UsedTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.d = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def w(self, name, text):
        p = self.d / name
        p.write_text(text, encoding="utf-8")
        return p

    def test_legacy_days_always_used(self):
        self.assertTrue({"2026-09-07", "2026-09-17"} <= sp.used_days())

    def test_ledger_sent_cards_labels_skips_and_journal_count(self):
        ledger = self.w("l.jsonl", "\n".join(json.dumps(r) for r in [
            {"card_id": "EYE-87d6dfed", "candidate_id": "S43-1-20250106"},
            {"card_id": "EYE-S10-1-20250107-ab12", "candidate_id": "S10-1-20250107"}]) + "\nnot json\n")
        labels = self.w("labels.csv", "logged_at,candidate_id,label,mode,source_ip\n"
                                      "t,EYE-87d6dfed,S,PAPER,tunnel\nt,EYE-S10-1-20250108-cd34,notS,PAPER,tunnel\n")
        skips = self.w("skips.csv", "logged_at,candidate_id,label,mode,source_ip\nt,EYE-S9-1-20250109-ee55,skip,PAPER,t\n")
        journal = self.w("j.jsonl", json.dumps({"date": "2025-01-10", "r": 1.0}) + "\n")
        got = sp.used_days(labels_csv=labels, skips_csv=skips, ledger=ledger, journal=journal)
        self.assertTrue({"2025-01-06", "2025-01-07", "2025-01-08", "2025-01-09", "2025-01-10"} <= got)

    def test_index_etf_marks_count_stock_marks_do_not(self):
        marks = self.w("m.json", json.dumps({"days": [{"s": "QQQ", "d": "2025-02-03"}, {"s": "SPY", "d": "2025-02-04"},
                                                      {"s": "NVDA", "d": "2025-02-05"}]}))
        got = sp.used_days(marks_json=marks)
        self.assertIn("2025-02-03", got)
        self.assertIn("2025-02-04", got)
        self.assertNotIn("2025-02-05", got)

    def test_missing_or_broken_files_are_fine(self):
        bad = self.w("bad.json", "{nope")
        got = sp.used_days(labels_csv=self.d / "no.csv", ledger=self.d / "no.jsonl", marks_json=bad)
        self.assertEqual(got, set(sp.LEGACY_USED))


class PickTests(unittest.TestCase):
    POOL = [f"2025-03-{d:02d}" for d in range(3, 29)]

    def test_never_returns_a_used_session_or_a_repeat(self):
        used = {"2025-03-03", "2025-03-04"}
        got = sp.pick_sessions(self.POOL + self.POOL, used, 10)
        self.assertEqual(len(got), 10)
        self.assertEqual(len(set(got)), 10)
        self.assertFalse(set(got) & used)

    def test_rotation_never_repeats_until_the_pool_is_empty(self):
        used, seen = set(), []
        while True:
            batch = sp.pick_sessions(self.POOL, used, 5)
            if not batch:
                break
            self.assertFalse(set(batch) & set(seen))
            seen += batch
            used |= set(batch)
        self.assertEqual(sorted(seen), sorted(self.POOL))

    def test_order_is_deterministic_and_stable_as_sessions_are_used(self):
        first = sp.pick_sessions(self.POOL, set(), 6)
        self.assertEqual(first, sp.pick_sessions(self.POOL, set(), 6))
        self.assertEqual(sp.pick_sessions(self.POOL, set(first[:3]), 3), first[3:6])
        self.assertNotEqual(first, sorted(first))               # shuffled, not calendar order

    def test_usable_filter_skips_sessions_without_a_card(self):
        bad = set(self.POOL[:20])
        got = sp.pick_sessions(self.POOL, set(), 5, usable=lambda d: d not in bad)
        self.assertEqual(len(got), 5)
        self.assertFalse(set(got) & bad)

    def test_short_pool_returns_what_is_left(self):
        self.assertEqual(len(sp.pick_sessions(self.POOL[:3], set(), 5)), 3)


if __name__ == "__main__":
    unittest.main()
