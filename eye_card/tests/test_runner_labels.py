"""Runner test: a labels.csv row from an earlier day must not answer today's tap card.

Needs the local-only data modules (omen_data, orb1m); skipped where they are not importable.
"""
import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

try:
    import eye_runner
except ImportError:  # data modules not on this checkout
    eye_runner = None


class FakeSend:
    ok = True
    status_code = 200


def _run(tmp: Path, labels: Path):
    sent = []
    journal = tmp / "journal.jsonl"

    def fake_send(c, png, card_id, **kw):
        sent.append(card_id)
        return FakeSend()

    with mock.patch.object(eye_runner.eyetap, "send_tap_card", fake_send), \
         mock.patch.object(eye_runner.eyetap, "record_card"), \
         mock.patch.object(eye_runner.eyetap, "load_config", return_value={}), \
         mock.patch.object(eye_runner.eyetap, "wait_for_network", return_value=True), \
         mock.patch.object(eye_runner.eyetap, "cards_sent_on", return_value=0), \
         mock.patch.object(eye_runner, "render_candidate_chart"), \
         mock.patch.object(eye_runner, "CHART_DIR", tmp / "charts"):
        eye_runner.main(["--date", "2026-09-07", "--title-prefix", "T", "--ignore-schedule",
                         "--speed", "100000", "--confirm-window-s", "1", "--max-cards-per-day", "1",
                         "--labels-csv", str(labels), "--journal-path", str(journal)])
    return sent, journal


@unittest.skipIf(eye_runner is None, "eye_runner data modules unavailable")
class StaleLabelTests(unittest.TestCase):
    def test_yesterdays_label_does_not_confirm_todays_card(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            labels = tmp / "labels.csv"
            sent, _ = _run(tmp, labels)                 # pass 1: learn what the card id looks like
            self.assertTrue(sent)
            stale_id = sent[0].rsplit("-", 1)[0]         # the old id format: EYE-<candidate id>
            with open(labels, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["candidate_id", "label", "logged_at", "source_ip"])
                w.writerow([stale_id, "S", "2026-09-06T10:00:00-04:00", ""])
            sent2, journal = _run(tmp, labels)           # pass 2: same candidate, stale S row on disk
            self.assertTrue(sent2)
            self.assertNotEqual(sent[0], sent2[0])       # fresh id per card
            self.assertFalse(journal.exists() and journal.read_text().strip(),
                             "stale S row confirmed a new card")


def _pool_run(tmp: Path, ledger: Path, cards: int, error: str = ""):
    """One pool-mode run (no --date). Returns [(card_id, candidate_id), ...] actually 'sent'."""
    sent = []
    real_record = eye_runner.eyetap.record_card

    class Res:
        ok = not error
        status_code = 200
        pass

    Res.error = error

    def fake_send(c, png, card_id, **kw):
        sent.append((card_id, c.candidate_id))
        return Res()

    with mock.patch.object(eye_runner.eyetap, "send_tap_card", fake_send),          mock.patch.object(eye_runner.eyetap, "LEDGER", ledger),          mock.patch.object(eye_runner.eyetap, "record_card",
                           side_effect=lambda *a, **k: real_record(*a, ledger=ledger, **k)),          mock.patch.object(eye_runner.eyetap, "load_config", return_value={}), \
         mock.patch.object(eye_runner.eyetap, "wait_for_network", return_value=True),          mock.patch.object(eye_runner.eyetap, "cards_sent_on", return_value=0),          mock.patch.object(eye_runner, "render_candidate_chart"),          mock.patch.object(eye_runner, "CHART_DIR", tmp / "charts"):
        eye_runner.main(["--title-prefix", "T", "--ignore-schedule", "--speed", "100000", "--card-gap-s", "0",
                         "--confirm-window-s", "1", "--max-cards-per-day", str(cards), "--blind",
                         "--labels-csv", str(tmp / "labels.csv"), "--journal-path", str(tmp / "j.jsonl"),
                         "--marks-json", str(tmp / "no-marks.json")])
    return sent


@unittest.skipIf(eye_runner is None, "eye_runner data modules unavailable")
class PoolModeTests(unittest.TestCase):
    def test_every_card_is_a_new_liquid_session_and_runs_never_repeat(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            ledger = tmp / "cards_sent.jsonl"
            run1 = _pool_run(tmp, ledger, 3)
            run2 = _pool_run(tmp, ledger, 3)
            dates = [eye_runner.session_pool.date_from_id(cid) for _, cid in run1 + run2]
            self.assertEqual(len(run1), 3)
            self.assertEqual(len(run2), 3)
            self.assertEqual(len(set(dates)), 6, dates)                 # one session per card, no repeat
            self.assertFalse(set(dates) & set(eye_runner.session_pool.LEGACY_USED))
            for dt in dates:
                self.assertTrue("2024-09-27" <= dt <= "2026-09-25", dt)

    def test_a_down_tunnel_stops_the_run_and_uses_up_no_session(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            ledger = tmp / "cards_sent.jsonl"
            run = _pool_run(tmp, ledger, 3, error="tunnel down")
            self.assertEqual(len(run), 1)                                # tried once, then stopped
            self.assertFalse(ledger.exists())                            # nothing recorded as seen
            again = _pool_run(tmp, ledger, 3)
            self.assertEqual(again[0][1], run[0][1])                     # the same session is still next


if __name__ == "__main__":
    unittest.main()
