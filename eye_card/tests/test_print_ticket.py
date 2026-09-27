"""Tests for scripts/print_ticket.py (manual ticket checklist). No network,
no orders. Run:  python -m unittest eye_card.tests.test_print_ticket
"""
import datetime as dt
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts.print_ticket import build_ticket, front_month, main

CARD = Path(__file__).parent / "fixtures" / "replay_card.json"


class PrintTicketTest(unittest.TestCase):
    def setUp(self):
        self.card = json.loads(CARD.read_text())

    def test_replay_card_every_field_populated(self):
        rows = build_ticket(self.card)
        self.assertEqual(len(rows), 12)
        for key, val in rows:
            self.assertTrue(val.strip(), key)
            self.assertNotIn("None", val, key)

    def test_replay_card_values(self):
        d = dict(build_ticket(self.card))
        self.assertIn("MNQZ5", d["1 contract"])
        self.assertTrue(d["2 qty"].startswith("5 MNQ"))  # floor(200/(18.75*2+2.25))
        self.assertIn("MARKET SELL at 09:50", d["3 entry"])
        self.assertIn("STOP SELL @ 26153.75", d["3 entry"])
        self.assertIn("STOP-MARKET BUY @ 26172.75", d["4 stop"])
        self.assertIn("2 @ 26116.5 (2R)", d["5 targets"])
        self.assertIn("3 @ 26097.75 (3R)", d["5 targets"])

    def test_front_month_roll(self):
        self.assertEqual(front_month("MNQ", dt.date(2026, 9, 27)), "MNQZ6")
        self.assertEqual(front_month("MNQ", dt.date(2026, 9, 9)), "MNQU6")
        self.assertEqual(front_month("MNQ", dt.date(2026, 12, 11)), "MNQH7")

    def test_qty_override_and_atr(self):
        self.card.update(qty=1, atr=5)
        d = dict(build_ticket(self.card))
        self.assertTrue(d["2 qty"].startswith("1 MNQ"))
        self.assertNotIn("3R", d["5 targets"])
        self.assertIn("26135.0", d["9 chase guard"])

    def test_bad_stop_side_rejected(self):
        self.card["stop"] = 26140.0
        with self.assertRaises(ValueError):
            build_ticket(self.card)

    def test_cli_prints(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(main([str(CARD)]), 0)
        self.assertEqual(buf.getvalue().count("[ ]"), 12)


if __name__ == "__main__":
    unittest.main()
