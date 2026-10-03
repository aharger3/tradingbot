"""Tests for the tap-to-answer eye cards (eye_card/tap.py). No network: ntfy is a fake session.

Run:  python -m pytest eye_card/tests/test_tap.py -q   (from repo root)
"""
import csv
import json
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from eye_card import tap, vault
from eye_card.chart import Candidate, _blind_view, render_candidate_chart

ET = ZoneInfo("America/New_York")
TOKEN = "T" * 43
ANSWER_TOPIC = "answer-topic-zzzzzzzzzzzzzzzzzz"
ALERT_TOPIC = "lp-alert-topic-yyyyyyyyyyyyyyyy"
CFG = {"token": TOKEN, "answer_topic": ANSWER_TOPIC, "base_url": "", "topic": ALERT_TOPIC}
SERVER_CARD_RE = re.compile(r"[A-Za-z0-9_.-]{1,40}")   # answer-engine tap/server.py CARD_RE
FIXTURES = Path(__file__).parent / "fixtures"


def cand(**kw):
    base = dict(candidate_id="S43-1-20260907", symbol="MNQ", direction="SHORT", trigger_time="10:11:00",
                entry=29609.75, stop=29617.25, targets=[29594.75, 29579.75], level=29612.5,
                level_label="ORB level", setup="ORB break/retest (S)", reason="S-gate clean",
                or_high=29640.0, or_low=29600.0)
    base.update(kw)
    return Candidate(**base)


def payload(**kw):
    args = dict(topic=ALERT_TOPIC, token=TOKEN, answer_topic=ANSWER_TOPIC)
    args.update(kw)
    return tap.build_tap_payload(cand(), "EYE-S43-1-20260907", **args)


class FakeResp:
    def __init__(self, ok=True, code=200, body=None):
        self.ok, self.status_code, self._body = ok, code, body or {}

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, put_resp=None, post_resp=None):
        self.puts, self.posts = [], []
        self._put, self._post = put_resp, post_resp or FakeResp()

    def put(self, url, **kw):
        self.puts.append((url, kw))
        if isinstance(self._put, Exception):
            raise self._put
        return self._put or FakeResp(body={"attachment": {"url": "https://ntfy.sh/file/abc123.png"}})

    def post(self, url, **kw):
        self.posts.append((url, kw))
        if isinstance(self._post, Exception):
            raise self._post
        return self._post

    def get(self, url, **kw):
        self.gets = getattr(self, "gets", []) + [url]
        if isinstance(self._get, Exception):
            raise self._get
        return self._get

    _get = FakeResp(body={"ok": True, "mode": "PAPER"})


class ButtonTests(unittest.TestCase):
    def test_three_buttons_s_not_s_skip(self):
        acts = payload()["actions"]
        self.assertEqual([a["label"] for a in acts], ["S", "Not S", "Skip"])
        self.assertEqual([json.loads(a["body"])["choice"] for a in acts], ["S", "notS", "skip"])

    def test_relay_buttons_post_card_id_and_token_to_answer_topic(self):
        for a in payload()["actions"]:
            self.assertEqual((a["action"], a["method"], a["clear"]), ("http", "POST", True))
            self.assertEqual(a["url"], f"https://ntfy.sh/{ANSWER_TOPIC}")
            body = json.loads(a["body"])
            self.assertEqual(body["card_id"], "EYE-S43-1-20260907")
            self.assertEqual(body["token"], TOKEN)

    def test_tunnel_buttons_post_to_tap_endpoint_without_token_in_body(self):
        for a in payload(base_url="https://ask.example.com/")["actions"]:
            self.assertEqual(a["url"], f"https://ask.example.com/tap/{TOKEN}")
            self.assertNotIn("token", json.loads(a["body"]))
            self.assertEqual(a["headers"], {"Content-Type": "application/json"})

    def test_no_route_is_an_error(self):
        with self.assertRaises(tap.TapConfigError):
            tap.build_actions("EYE-x", TOKEN)


class CardTextTests(unittest.TestCase):
    def test_open_card_names_ticker_and_prices(self):
        title, msg = tap.build_text(cand(), blind=False, seq=2, cap=5, title_prefix="OMEN REPLAY TEST")
        self.assertEqual(title, "OMEN REPLAY TEST - S or Not S? MNQ Short")
        self.assertIn("Entry 29609.75", msg)
        self.assertIn("Card 2/5", msg)

    def test_blind_card_hides_ticker_date_grade_and_prices(self):
        title, msg = tap.build_text(cand(), blind=True, seq=2, cap=5, title_prefix="OMEN REPLAY TEST")
        text = title + "\n" + msg
        for leaked in ("MNQ", "20260907", "2026", "29609", "29617", "29594", "ORB", "(S)", "S43", "Entry"):
            self.assertNotIn(leaked, text)
        self.assertIn("Short", title)
        self.assertIn("10:11 ET", msg)
        self.assertIn("stop 0.03% away", msg)

    def test_lock_screen_length(self):
        for blind in (False, True):
            title, msg = tap.build_text(cand(), blind=blind, seq=5, cap=5)
            self.assertLessEqual(len(msg.splitlines()), 3)
            self.assertLess(len(title), 60)
            self.assertLess(max(len(x) for x in msg.splitlines()), 70)

    def test_long_side_and_degenerate_risk(self):
        t, m = tap.build_text(cand(direction="LONG", stop=29609.75), blind=True, seq=1, cap=5)
        self.assertIn("Long", t)
        self.assertIn("0.00%", m)


class CardIdTests(unittest.TestCase):
    def test_ids_match_server_rules_and_prefix(self):
        for blind in (False, True):
            cid = tap.card_id_for("S43-1-20260907", blind)
            self.assertTrue(cid.startswith(tap.CARD_PREFIX))
            self.assertTrue(SERVER_CARD_RE.fullmatch(cid), cid)

    def test_blind_id_is_opaque_and_unique(self):
        ids = {tap.card_id_for("S43-1-20260907", True) for _ in range(50)}
        self.assertEqual(len(ids), 50)
        for i in ids:
            self.assertNotIn("2026", i)
            self.assertNotIn("S43", i)

    def test_open_id_is_readable_and_unique(self):
        a = tap.card_id_for("S43-1-20260907", False)
        b = tap.card_id_for("S43-1-20260907", False)
        self.assertTrue(re.fullmatch(r"EYE-S43-1-20260907-[0-9a-f]{4}", a), a)
        self.assertNotEqual(a, b)
        self.assertTrue(SERVER_CARD_RE.fullmatch(a))


class PayloadTests(unittest.TestCase):
    def test_goes_to_the_alert_topic_and_is_json(self):
        p = payload()
        self.assertEqual(p["topic"], ALERT_TOPIC)
        self.assertEqual(p["priority"], 4)
        json.dumps(p)

    def test_chart_link_only_when_there_is_one(self):
        self.assertNotIn("attach", payload())
        p = payload(chart_url="https://ntfy.sh/file/abc.png")
        self.assertEqual(p["attach"], "https://ntfy.sh/file/abc.png")
        self.assertEqual(p["filename"], "EYE-S43-1-20260907.png")

    def test_redacted_masks_every_secret(self):
        out = tap.redacted(payload(), TOKEN, ANSWER_TOPIC, ALERT_TOPIC)
        for s in (TOKEN, ANSWER_TOPIC, ALERT_TOPIC):
            self.assertNotIn(s, out)
        for m in ("<TOKEN>", "<ANSWER_TOPIC>", "<ALERT_TOPIC>"):
            self.assertIn(m, out)
        json.loads(out)


class ScheduleAndCapTests(unittest.TestCase):
    def test_monday_to_thursday_only(self):
        # 2026-10-05 is a Monday
        for day, want in ((5, True), (6, True), (7, True), (8, True), (9, False), (10, False), (11, False)):
            ok, _ = tap.schedule_ok(datetime(2026, 10, day, 10, 0, tzinfo=ET))
            self.assertEqual(ok, want, day)

    def test_weekday_is_judged_in_eastern_time(self):
        thu_late = datetime(2026, 10, 8, 23, 30, tzinfo=ET)          # Friday in UTC
        self.assertTrue(tap.schedule_ok(thu_late.astimezone(ZoneInfo("UTC")))[0])
        fri_early = datetime(2026, 10, 9, 0, 30, tzinfo=ET)          # Thursday in UTC
        self.assertFalse(tap.schedule_ok(fri_early.astimezone(ZoneInfo("UTC")))[0])

    def test_cap_counts_only_today_and_blocks_at_the_limit(self):
        with tempfile.TemporaryDirectory() as td:
            led = Path(td) / "cards.jsonl"
            mon = datetime(2026, 10, 5, 10, 0, tzinfo=ET)
            tap.record_card("EYE-old", "x", datetime(2026, 10, 1, 10, 0, tzinfo=ET), blind=False, seq=1, ledger=led)
            self.assertEqual(tap.cards_sent_on("2026-10-05", led), 0)
            for i in range(tap.MAX_CARDS_PER_DAY - 1):
                tap.record_card(f"EYE-{i}", f"c{i}", mon, blind=False, seq=i + 1, ledger=led)
            self.assertTrue(tap.may_send(mon, led)[0])
            tap.record_card("EYE-last", "c", mon, blind=False, seq=5, ledger=led)
            ok, why = tap.may_send(mon, led)
            self.assertFalse(ok)
            self.assertIn("5/5", why)

    def test_cap_default_is_the_frozen_prereg_limit(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research" / "agent_runs" / "v3-eye4-paper"))
        from prereg_slice_a import PREREG_SLICE_A
        self.assertEqual(tap.MAX_CARDS_PER_DAY, PREREG_SLICE_A.max_trades_per_day)

    def test_friday_blocked_even_with_room(self):
        with tempfile.TemporaryDirectory() as td:
            ok, why = tap.may_send(datetime(2026, 10, 9, 10, 0, tzinfo=ET), Path(td) / "none.jsonl")
            self.assertFalse(ok)
            self.assertIn("Friday", why)

    def test_id_map_roundtrip_and_bad_lines(self):
        with tempfile.TemporaryDirectory() as td:
            led = Path(td) / "cards.jsonl"
            tap.record_card("EYE-a1b2c3d4", "S43-1-20260907", datetime(2026, 10, 5, 10, 0, tzinfo=ET),
                            blind=True, seq=1, ledger=led)
            with open(led, "a") as fh:
                fh.write("not json\n")
            self.assertEqual(tap.load_id_map(led), {"EYE-a1b2c3d4": "S43-1-20260907"})
            self.assertEqual(tap.load_id_map(Path(td) / "missing.jsonl"), {})


class SendTests(unittest.TestCase):
    def test_posts_json_to_ntfy_root_with_chart_link(self):
        s = FakeSession()
        with tempfile.TemporaryDirectory() as td:
            png = Path(td) / "c.png"
            png.write_bytes(b"\x89PNG")
            r = tap.send_tap_card(cand(), png, "EYE-S43-1-20260907", seq=1, session=s, config=CFG,
                                  ntfy_base="https://ntfy.example")
        self.assertTrue(r.ok)
        self.assertEqual(s.puts[0][0].split("/eyechart-")[0], "https://ntfy.example")
        url, kw = s.posts[0]
        self.assertEqual(url, "https://ntfy.example/")
        self.assertEqual(kw["json"]["topic"], ALERT_TOPIC)
        self.assertEqual(kw["json"]["attach"], "https://ntfy.sh/file/abc123.png")
        self.assertEqual(len(kw["json"]["actions"]), 3)

    def test_failed_chart_upload_still_sends_the_card_without_image(self):
        for put in (OSError("down"), FakeResp(ok=False, code=500)):
            s = FakeSession(put_resp=put)
            with tempfile.TemporaryDirectory() as td:
                png = Path(td) / "c.png"
                png.write_bytes(b"\x89PNG")
                r = tap.send_tap_card(cand(), png, "EYE-x", session=s, config=CFG)
            self.assertTrue(r.ok)
            self.assertNotIn("attach", s.posts[0][1]["json"])

    def test_blind_upload_name_is_the_opaque_card_id(self):
        s = FakeSession()
        with tempfile.TemporaryDirectory() as td:
            png = Path(td) / "EYE-a1b2c3d4.png"
            png.write_bytes(b"\x89PNG")
            tap.send_tap_card(cand(), png, "EYE-a1b2c3d4", blind=True, session=s, config=CFG)
        self.assertEqual(s.puts[0][1]["headers"]["Filename"], "EYE-a1b2c3d4.png")

    def test_post_timeout_returns_ambiguous_failure_not_exception(self):
        import requests
        for exc in (requests.ReadTimeout("slow"), requests.ConnectionError("reset")):
            s = FakeSession(post_resp=exc)
            r = tap.send_tap_card(cand(), None, "EYE-x", session=s, config=CFG)
            self.assertFalse(r.ok)
            self.assertIsNone(r.status_code)
            self.assertTrue(r.error.startswith(tap.AMBIGUOUS_ERROR))

    def test_no_chart_means_no_upload(self):
        s = FakeSession()
        tap.send_tap_card(cand(), None, "EYE-x", session=s, config=CFG)
        self.assertEqual(s.puts, [])


class ConfigTests(unittest.TestCase):
    def _env(self, **kw):
        base = {"ANSWER_TAP_TOKEN": TOKEN, "TAP_ANSWER_TOPIC": ANSWER_TOPIC, "NTFY_TOPIC": ALERT_TOPIC,
                "EYE_TAP_BASE_URL": "", "EYE_TAP_RELAY": ""}
        base.update(kw)
        return mock.patch.dict("os.environ", base, clear=False), mock.patch.object(vault, "KEYS_PY", "no-such-file")

    def test_loads_from_env(self):
        a, b = self._env()
        with a, b:
            self.assertEqual(tap.load_config()["topic"], ALERT_TOPIC)

    def test_missing_secret_is_an_error(self):
        a, b = self._env(ANSWER_TAP_TOKEN="")
        with a, b, self.assertRaises(tap.TapConfigError):
            tap.load_config()

    def test_relay_mode_refuses_the_old_guessable_topic(self):
        a, b = self._env(NTFY_TOPIC="aharg-deadlines", EYE_TAP_RELAY="1")
        with a, b, self.assertRaises(tap.TapConfigError):
            tap.load_config()

    def test_default_buttons_go_through_the_cloudflare_tunnel(self):
        a, b = self._env()
        with a, b:
            cfg = tap.load_config()
        self.assertEqual(cfg["base_url"], "https://omen.austinharger.com")
        self.assertEqual(cfg["answer_topic"], "")              # relay is off unless asked for
        acts = tap.build_tap_payload(cand(), "EYE-x", topic=ALERT_TOPIC, token=TOKEN,
                                     answer_topic=cfg["answer_topic"], base_url=cfg["base_url"])["actions"]
        for a_ in acts:
            self.assertEqual(a_["url"], f"https://omen.austinharger.com/tap/{TOKEN}")
            self.assertNotIn("token", json.loads(a_["body"]))

    def test_no_button_url_names_a_tailscale_address(self):
        a, b = self._env()
        with a, b:
            cfg = tap.load_config()
        text = json.dumps(tap.build_tap_payload(cand(), "EYE-x", topic=ALERT_TOPIC, token=TOKEN,
                                                base_url=cfg["base_url"]))
        for bad in ("100.", "ts.net", "tailscale", ":9135"):
            self.assertNotIn(bad, text)

    def test_tunnel_base_can_be_overridden(self):
        a, b = self._env(EYE_TAP_BASE_URL="https://tap.example.com/")
        with a, b:
            self.assertEqual(tap.load_config()["base_url"], "https://tap.example.com")

    def test_relay_flag_switches_back_to_the_answer_topic(self):
        a, b = self._env(EYE_TAP_RELAY="1")
        with a, b:
            cfg = tap.load_config()
        self.assertEqual((cfg["base_url"], cfg["answer_topic"]), ("", ANSWER_TOPIC))


TUNNEL_CFG = {"token": TOKEN, "answer_topic": "", "base_url": "https://omen.austinharger.com",
              "topic": ALERT_TOPIC}


class NetworkWaitTests(unittest.TestCase):
    def test_waits_until_dns_resolves(self):
        calls, sleeps = [], []

        def resolve(host):
            calls.append(host)
            if len(calls) < 3:
                raise OSError("getaddrinfo failed")
            return "1.2.3.4"

        self.assertTrue(tap.wait_for_network(resolve=resolve, sleep=sleeps.append))
        self.assertEqual((calls, len(sleeps)), (["ntfy.sh"] * 3, 2))

    def test_gives_up_and_does_not_sleep_after_the_last_try(self):
        sleeps = []

        def down(host):
            raise OSError("down")

        self.assertFalse(tap.wait_for_network(tries=3, wait_s=5, resolve=down, sleep=sleeps.append))
        self.assertEqual(sleeps, [5, 5])


class TunnelProbeTests(unittest.TestCase):
    def test_probe_hits_healthz_on_the_tunnel_host(self):
        s = FakeSession()
        self.assertTrue(tap.tunnel_up("https://omen.austinharger.com/", session=s))
        self.assertEqual(s.gets, ["https://omen.austinharger.com/healthz"])

    def test_probe_false_on_error_status_bad_json_or_exception(self):
        for resp in (FakeResp(ok=False, code=502), FakeResp(body={"ok": False}), FakeResp(body={}),
                     OSError("dns")):
            s = FakeSession()
            s._get = resp
            self.assertFalse(tap.tunnel_up("https://omen.austinharger.com", session=s))

    def test_card_is_sent_when_the_tunnel_is_up(self):
        s = FakeSession()
        r = tap.send_tap_card(cand(), None, "EYE-x", session=s, config=TUNNEL_CFG)
        self.assertTrue(r.ok)
        self.assertEqual(len(s.posts), 1)
        self.assertTrue(s.posts[0][1]["json"]["actions"][0]["url"].startswith("https://omen.austinharger.com/tap/"))

    def test_no_card_goes_out_when_the_tunnel_is_down(self):
        s = FakeSession()
        s._get = OSError("tunnel down")
        r = tap.send_tap_card(cand(), None, "EYE-x", session=s, config=TUNNEL_CFG)
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "tunnel down")
        self.assertEqual(s.posts, [])
        self.assertEqual(s.puts, [])


class BlindChartTests(unittest.TestCase):
    def _bars(self):
        with open(FIXTURES / "sample_bars.csv", newline="") as fh:
            return [{"time": r["time"], **{k: float(r[k]) for k in ("open", "high", "low", "close")}}
                    for r in csv.DictReader(fh)]

    def test_blind_view_is_percent_from_open_and_leaves_input_alone(self):
        bars = self._bars()
        c = cand(entry=bars[0]["open"] * 1.01, stop=bars[0]["open"], targets=[bars[0]["open"] * 1.02],
                 level=bars[0]["open"], or_high=None, or_low=None)
        before = bars[0]["open"]
        vc, vb = _blind_view(c, bars)
        self.assertAlmostEqual(vb[0]["open"], 0.0)
        self.assertAlmostEqual(vc.entry, 1.0, places=6)
        self.assertAlmostEqual(vc.targets[0], 2.0, places=6)
        self.assertEqual(bars[0]["open"], before)
        self.assertEqual(c.entry, before * 1.01)

    def test_blind_render_writes_a_png(self):
        bars = self._bars()
        c = cand(trigger_time=bars[-1]["time"], entry=bars[-1]["close"], stop=bars[-1]["close"] + 1,
                 targets=[bars[-1]["close"] - 1], level=bars[-1]["close"], or_high=None, or_low=None)
        with tempfile.TemporaryDirectory() as td:
            out = render_candidate_chart(c, bars, Path(td) / "b.png", blind=True)
            self.assertGreater(out.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
