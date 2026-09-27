"""Tests for the trade journal table + weekly review. No network, no orders.

Run:  python -m unittest trade_journal.tests.test_journal  (from repo root)
"""
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from trade_journal.journal import connect, ingest_acks, iso_week, record, rows_for_week
from trade_journal.review import build_report, perm_p_diff, signflip_p, write_review


def _png(path: Path, shade: int = 0):
    """Tiny valid 1x1 PNG so screenshot archiving has something real to copy."""
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = zlib.compress(bytes([0, shade, shade, shade]))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", raw) + chunk(b"IEND", b""))
    return path


def _paper(confirmed, r=None, reason="confirmed", lat=5.0):
    row = {"confirmed": confirmed, "reason": reason, "tap_latency_s": lat, "management": "flat_2r"}
    if confirmed:
        row.update(entry=100.0, stop=98.0, r=r, usd=r * 4.0)
    return row


class JournalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "paper_journal"
        self.db = self.dir / "journal.db"
        self.con = connect(self.db)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _rec(self, cid, grade, paper, shadow=None, minute=11, png=True, date="2026-09-17"):
        shot = _png(Path(self.tmp.name) / f"{cid}.png") if png else None
        return record(self.con, cid=cid, mode="REPLAY", session_date=date, instrument="MNQ",
                      direction="short", setup="orb-retest", engine_grade="S", austin_grade=grade,
                      paper_row=paper, shadow_r=shadow, minutes_after_open=minute,
                      screenshot_png=shot, journal_dir=self.dir)

    def test_record_taken_archives_png_and_tags(self):
        row = self._rec("S11-1-20260917", "S", _paper(True, r=2.0), shadow=-5.0)
        self.assertEqual(row["taken"], 1)
        self.assertEqual(row["shadow_r"], 2.0)          # taken => shadow is the real R
        self.assertEqual(row["signal_time"], "09:41")
        self.assertEqual(row["iso_week"], "2026-W38")
        tags = json.loads(row["tags"])
        for t in ("S", "eng:S", "setup:orb-retest", "inst:MNQ", "dir:short", "time:0930-0945"):
            self.assertIn(t, tags)
        shot = self.dir / row["screenshot"]
        self.assertTrue(shot.exists())
        self.assertEqual(len(row["screenshot_sha256"]), 64)

    def test_passed_card_has_no_r_but_keeps_shadow(self):
        row = self._rec("O20-1-20260917", "not_s", _paper(False, reason="grade_not_s"), shadow=-1.04, minute=20)
        self.assertEqual(row["taken"], 0)
        self.assertIsNone(row["r"])
        self.assertEqual(row["shadow_r"], -1.04)
        self.assertNotIn("S", json.loads(row["tags"]))

    def test_upsert_is_idempotent(self):
        self._rec("S11-1-20260917", "S", _paper(True, r=2.0))
        self._rec("S11-1-20260917", "S", _paper(True, r=-1.0))
        rows = rows_for_week(self.con, "2026-W38")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["r"], -1.0)

    def test_rejects_bad_grade(self):
        with self.assertRaises(ValueError):
            self._rec("X", "maybe", _paper(False))

    def test_ingest_acks_backfill(self):
        charts = Path(self.tmp.name) / "charts"
        charts.mkdir()
        _png(charts / "O11-1-20260917.png")
        acks = Path(self.tmp.name) / "acks.jsonl"
        acks.write_text(json.dumps({"id": "O11-1-20260917", "symbol": "MNQ", "date": "2026-09-17", "side": -1,
                                    "confirmed": True, "reason": "confirmed", "tap_latency_s": 2.8,
                                    "management": "flat_2r", "entry": 29619.25, "stop": 29642.5,
                                    "r": -1.0374, "usd": -48.24}) + "\n")
        self.assertEqual(ingest_acks(self.con, acks, charts, journal_dir=self.dir), 1)
        (r,) = rows_for_week(self.con, iso_week("2026-09-17"))
        self.assertEqual((r["engine_grade"], r["direction"], r["r"], r["risk_pts"]), ("one-off", "short", -1.0374, 23.25))
        self.assertIsNotNone(r["screenshot"])

    def test_weekly_review_report(self):
        self._rec("S11-1-20260917", "S", _paper(True, r=2.0))
        self._rec("S14-1-20260916", "S", _paper(True, r=-1.0), date="2026-09-16")
        self._rec("O20-1-20260917", "not_s", _paper(False, reason="grade_not_s"), shadow=-1.0, minute=20)
        self._rec("T40-1-20260917", "none", _paper(False, reason="no_tap", lat=None), shadow=None, minute=40, png=False)
        path = write_review("2026-W38", "REPLAY", self.db)
        md = path.read_text(encoding="utf-8")
        self.assertIn("| 2 | 4 | 2 | +1.00 | +0.50 | 50% | +4.00 | 1 |", md)   # scoreboard
        self.assertIn("eye **+1.50R**", md)
        self.assertIn("permutation p", md)
        self.assertIn("[png](../shots/2026-W38/REPLAY_S11-1-20260917.png)", md)
        self.assertIn("1 card(s) have no archived screenshot", md)
        self.assertIn("n=2 < 20", md)

    def test_empty_week(self):
        md = build_report([], "2026-W01", None, Path("x.md"), Path("."))
        self.assertIn("No cards journaled", md)


class StatsTest(unittest.TestCase):
    def test_perm_p_extremes(self):
        self.assertLess(perm_p_diff([2.0] * 10, [-1.0] * 10), 0.01)
        self.assertGreater(perm_p_diff([-1.0] * 10, [2.0] * 10), 0.99)

    def test_signflip(self):
        self.assertLess(signflip_p([1.0] * 12), 0.01)
        self.assertGreater(signflip_p([-1.0] * 12), 0.99)


if __name__ == "__main__":
    unittest.main()
