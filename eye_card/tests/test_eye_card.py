"""Tests for the eye3 phone card: chart render, ntfy message build, label
endpoint. No network calls (ntfy sends are mocked); no live orders anywhere.

Run:  python -m unittest eye_card.tests.test_eye_card  (from repo root)
"""
import csv
import json
import os
import tempfile
import unittest
from pathlib import Path

from eye_card.chart import Candidate, render_candidate_chart
from eye_card.labels import append_label
from unittest import mock

import requests

import eye_card.notify as notify_mod
from eye_card.notify import build_actions, build_message, build_title, send_card
from eye_card.server import app as label_app

FIXTURES = Path(__file__).parent / "fixtures"


def _load_bars(name):
    bars = []
    with open(FIXTURES / name, newline="") as fh:
        for row in csv.DictReader(fh):
            bars.append({
                "time": row["time"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            })
    return bars


def _candidate(**overrides):
    base = dict(
        candidate_id="T20260926-0937",
        symbol="MNQ",
        direction="SHORT",
        trigger_time="09:37:00",
        entry=99.55,
        stop=100.40,
        targets=[98.80, 98.20],
        level=100.00,
        level_label="OR low",
        setup="ORB+OCR",
        reason="ORB break, wick-only retest",
        or_high=101.25,
        or_low=99.75,
    )
    base.update(overrides)
    return Candidate(**base)


class ChartTests(unittest.TestCase):
    def test_renders_png_up_to_trigger_time(self):
        bars = _load_bars("sample_bars.csv")
        cand = _candidate()
        with tempfile.TemporaryDirectory() as td:
            out = render_candidate_chart(cand, bars, Path(td) / "card.png")
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)

    def test_unknown_trigger_time_raises(self):
        bars = _load_bars("sample_bars.csv")
        cand = _candidate(trigger_time="12:00:00")
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                render_candidate_chart(cand, bars, Path(td) / "card.png")

    def test_replay_fixture_renders(self):
        path = FIXTURES / "replay_nq_2025.csv"
        if not path.exists():
            self.skipTest("replay fixture not generated on this machine")
        bars = _load_bars("replay_nq_2025.csv")
        cand = _candidate(
            candidate_id="REPLAY-20251103-0949", symbol="NQ", direction="SHORT",
            trigger_time="09:49:00", entry=26154.00, stop=26172.75,
            targets=[26126.00, 26107.00], level=26155.00, level_label="OR low",
            setup="ORB break + retest", reason="OR low break, retest rejected",
            or_high=26266.00, or_low=26155.00,
        )
        with tempfile.TemporaryDirectory() as td:
            out = render_candidate_chart(cand, bars, Path(td) / "replay.png")
            self.assertTrue(out.exists())


class MessageTests(unittest.TestCase):
    def test_title_has_symbol_and_direction(self):
        cand = _candidate()
        title = build_title(cand)
        self.assertIn("MNQ", title)
        self.assertIn("SHORT", title)

    def test_message_is_paper_labeled(self):
        cand = _candidate()
        msg = build_message(cand)
        self.assertIn("PAPER", msg)
        self.assertIn(cand.candidate_id, msg)
        self.assertIn("Entry", msg)
        self.assertIn("Stop", msg)

    def test_actions_wire_s_and_not_s_to_label_endpoint(self):
        cand = _candidate()
        actions = build_actions(cand, token="tok123")
        self.assertIn("label=S", actions)
        self.assertIn("label=notS", actions)
        self.assertIn("tok123", actions)
        self.assertIn("/label", actions)


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append((url, data, headers, timeout))

        class R:
            ok = True
            status_code = 200

        return R()


class SendCardTests(unittest.TestCase):
    def test_send_card_uses_ntfy_topic_and_paper_tag_no_real_network(self):
        os.environ["NTFY_TOPIC"] = "aharg-ev-eo5zvp"
        cand = _candidate()
        bars = _load_bars("sample_bars.csv")
        with tempfile.TemporaryDirectory() as td:
            png = render_candidate_chart(cand, bars, Path(td) / "card.png")
            sess = FakeSession()
            result = send_card(cand, png, token="tok", session=sess)
        self.assertTrue(result.ok)
        self.assertIn("aharg-ev-eo5zvp", result.url)
        self.assertEqual(len(sess.calls), 1)
        _, _, headers, _ = sess.calls[0]
        self.assertIn("PAPER", headers["Message"])
        self.assertIn("paper", headers["Tags"])
        self.assertNotIn("\n", headers["Message"])  # header-safe: real newlines escaped
        self.assertIn("\\n", headers["Message"])

    def test_test_title_prefix_marks_replay_sends(self):
        os.environ["NTFY_TOPIC"] = "aharg-ev-eo5zvp"
        cand = _candidate()
        bars = _load_bars("sample_bars.csv")
        with tempfile.TemporaryDirectory() as td:
            png = render_candidate_chart(cand, bars, Path(td) / "card.png")
            sess = FakeSession()
            send_card(cand, png, token="tok", session=sess, test_title_prefix="TEST")
        _, _, headers, _ = sess.calls[0]
        self.assertTrue(headers["Title"].startswith("TEST"))


class NtfyDownSession:
    """ntfy always times out; the Discord endpoint accepts. Records every call."""
    DISCORD = "https://discord.example/api/webhooks/123/SECRET"

    def __init__(self, discord_ok=True):
        self.ntfy_calls = 0
        self.discord_calls = []
        self.discord_ok = discord_ok

    def post(self, url, data=None, headers=None, timeout=None, files=None):
        if url == self.DISCORD:
            self.discord_calls.append({"data": data, "files": files, "headers": headers})
            ok = self.discord_ok

            class R:
                pass
            R.ok, R.status_code = ok, (200 if ok else 500)
            return R()
        self.ntfy_calls += 1
        raise requests.exceptions.ConnectTimeout("ntfy.sh timed out")


class DiscordFallbackTests(unittest.TestCase):
    def _send(self, sess):
        cand = _candidate()
        bars = _load_bars("sample_bars.csv")
        with tempfile.TemporaryDirectory() as td:
            png = render_candidate_chart(cand, bars, Path(td) / "card.png")
            with mock.patch.object(notify_mod, "_discord_target",
                                   return_value=(sess.DISCORD, {})):
                return send_card(cand, png, token="tok", session=sess, backoff=(0, 0))

    def test_ntfy_connect_timeout_falls_back_to_discord_once(self):
        sess = NtfyDownSession()
        result = self._send(sess)  # must not raise: runner keeps looping
        self.assertEqual(sess.ntfy_calls, 3)
        self.assertEqual(len(sess.discord_calls), 1)
        self.assertTrue(result.ok)
        self.assertEqual(result.channel, "discord")
        call = sess.discord_calls[0]
        content = json.loads(call["data"]["payload_json"])["content"]
        self.assertIn("PAPER", content)
        self.assertIn("label=S&token=tok&channel=discord", content)
        self.assertIn("label=notS&token=tok&channel=discord", content)
        name, png, ctype = call["files"]["file"]
        self.assertEqual(ctype, "image/png")
        self.assertTrue(png.startswith(b"\x89PNG"))
        self.assertNotIn("SECRET", result.url + result.error)

    def test_both_down_returns_not_ok_without_raising(self):
        sess = NtfyDownSession(discord_ok=False)
        result = self._send(sess)
        self.assertFalse(result.ok)
        self.assertEqual(result.channel, "none")
        self.assertEqual(len(sess.discord_calls), 1)

    def test_discord_target_error_is_swallowed_and_scrubbed(self):
        sess = NtfyDownSession()
        cand = _candidate()
        bars = _load_bars("sample_bars.csv")
        with tempfile.TemporaryDirectory() as td:
            png = render_candidate_chart(cand, bars, Path(td) / "card.png")
            with mock.patch.object(notify_mod, "_discord_target",
                                   side_effect=ValueError("DISCORD_WEBHOOK_URL not set")):
                result = send_card(cand, png, token="tok", session=sess, backoff=(0, 0))
        self.assertFalse(result.ok)
        self.assertIn("ValueError", result.error)

    def test_ntfy_ok_never_touches_discord(self):
        cand = _candidate()
        bars = _load_bars("sample_bars.csv")
        with tempfile.TemporaryDirectory() as td:
            png = render_candidate_chart(cand, bars, Path(td) / "card.png")
            sess = FakeSession()
            with mock.patch.object(notify_mod, "_discord_target") as tgt:
                result = send_card(cand, png, token="tok", session=sess)
        tgt.assert_not_called()
        self.assertEqual(result.channel, "ntfy")
        self.assertEqual(len(sess.calls), 1)


class LabelEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = label_app.test_client()
        os.environ["EYE_LABEL_TOKEN"] = "test-token"

    def test_rejects_bad_token(self):
        resp = self.client.post("/label?id=c1&label=S&token=wrong")
        self.assertEqual(resp.status_code, 403)

    def test_logs_s_label_to_csv(self):
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "labels.csv"
            import eye_card.server as server_mod
            server_mod.LABELS_CSV = csv_path
            resp = self.client.post("/label?id=c1&label=S&token=test-token")
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(csv_path.exists())
            with open(csv_path) as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["label"], "S")
            self.assertEqual(rows[0]["mode"], "PAPER")

    def test_discord_channel_logged_to_csv(self):
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "labels.csv"
            import eye_card.server as server_mod
            server_mod.LABELS_CSV = csv_path
            resp = self.client.get("/label?id=c1&label=S&token=test-token&channel=discord")
            self.assertEqual(resp.status_code, 200)
            with open(csv_path) as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(rows[0]["channel"], "discord")
            self.assertEqual(rows[0]["mode"], "PAPER")

    def test_rejects_bad_label_value(self):
        resp = self.client.post("/label?id=c1&label=maybe&token=test-token")
        self.assertEqual(resp.status_code, 400)


class LabelsCsvTests(unittest.TestCase):
    def test_append_label_rejects_unknown_label(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                append_label(Path(td) / "labels.csv", "c1", "maybe")

    def test_legacy_header_migrated_old_rows_marked_ntfy(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "labels.csv"
            p.write_text("logged_at,candidate_id,label,mode,source_ip\n"
                         "2026-09-27T04:00:08+00:00,O11-1,S,PAPER,127.0.0.1\n", encoding="utf-8")
            append_label(p, "c2", "notS", channel="discord")
            with open(p) as fh:
                rows = list(csv.DictReader(fh))
        self.assertEqual([r["channel"] for r in rows], ["ntfy", "discord"])
        self.assertEqual(rows[0]["candidate_id"], "O11-1")


if __name__ == "__main__":
    unittest.main()
