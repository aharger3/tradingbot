"""Tests for eye_report.py: the DNS-not-ready retry and the 'journaled today' summary.

Run:  python -m pytest eye_card/tests/test_eye_report.py -q   (from repo root)
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

import eye_report
from eye_card import notify


class RetryTests(unittest.TestCase):
    def test_retries_while_dns_is_down_then_succeeds(self):
        calls = []

        def flaky(title, msg):
            calls.append(1)
            if len(calls) < 3:
                raise requests.exceptions.ConnectionError("Failed to resolve 'ntfy.sh'")
            return True, 200

        sleeps = []
        with mock.patch.object(eye_report, "push", flaky):
            self.assertEqual(eye_report.push_retry("t", "m", sleep=sleeps.append), (True, 200))
        self.assertEqual((len(calls), len(sleeps)), (3, 2))

    def test_gives_up_after_the_last_try(self):
        with mock.patch.object(eye_report, "push", side_effect=requests.exceptions.ConnectionError("dns")) as p:
            with self.assertRaises(requests.exceptions.ConnectionError):
                eye_report.push_retry("t", "m", tries=3, sleep=lambda s: None)
        self.assertEqual(p.call_count, 3)

    def test_http_failure_is_not_retried(self):
        with mock.patch.object(eye_report, "push", return_value=(False, 500)) as p:
            self.assertEqual(eye_report.push_retry("t", "m", sleep=lambda s: None), (False, 500))
        self.assertEqual(p.call_count, 1)


class SummaryTests(unittest.TestCase):
    def test_counts_rows_scored_today_whatever_session_they_replayed(self):
        rows = [  # ts is UTC; 03:00Z on 10-06 is still 10-05 in New York
            {"date": "2025-03-11", "r": 2.0, "usd": 80.0, "ts": "2026-10-05T14:00:00+00:00"},
            {"date": "2024-11-20", "r": -1.0, "usd": -40.0, "ts": "2026-10-05T14:05:00+00:00"},
            {"date": "2025-06-02", "r": 1.0, "usd": 40.0, "ts": "2026-10-06T03:00:00+00:00"},
            {"date": "2025-07-01", "r": 2.0, "usd": 80.0, "ts": "2026-10-06T14:00:00+00:00"},   # tomorrow
            {"date": "2025-08-01", "confirmed": False, "ts": "2026-10-05T14:00:00+00:00"},      # no r
        ]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "j.jsonl"
            p.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")
            s = eye_report.logged_day_summary("2026-10-05", p)
        self.assertEqual((s["n"], s["mean_r"], s["hit_rate"], s["usd"]), (3, 0.6667, 0.6667, 80.0))

    def test_missing_journal_is_zero_trades(self):
        s = eye_report.logged_day_summary("2026-10-05", Path("no-such-journal.jsonl"))
        self.assertEqual((s["n"], s["mean_r"]), (0, None))


class LegacyCardTests(unittest.TestCase):
    def test_legacy_button_default_is_not_the_tailscale_ip(self):
        with mock.patch.dict("os.environ", {"EYE_LABEL_BASE_URL": ""}):
            import os
            os.environ.pop("EYE_LABEL_BASE_URL")
            base = notify._label_base_url()
        self.assertEqual(base, "https://omen.austinharger.com")
        self.assertNotIn("100.", base)


if __name__ == "__main__":
    unittest.main()
