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


if __name__ == "__main__":
    unittest.main()
