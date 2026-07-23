"""Tests for the ntfy alert channel + paper-trade flow (stdlib unittest only).

Run:  python3 test_notifications.py        # or:  python3 -m unittest test_notifications

No network: requests.post is mocked everywhere. Covers what the live path can't
verify from the sandbox (proxy blocks ntfy.sh): message formatting, retry +
failed-log masking, the ntfy-on / Discord-off wiring, paper P&L incl. the
slippage knob, and the full signal->paper->ntfy chain.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ntfy_notifier
import paper_trader
from ntfy_notifier import NtfyNotifier
from options_sizer import OptionsPlan
from omen_bot import SignalType, Candle
from paper_trader import PaperBook


def _ok_response():
    r = mock.Mock()
    r.status_code = 200
    r.ok = True
    r.text = ""
    return r


def _fail_response(code=500, text="boom"):
    r = mock.Mock()
    r.status_code = code
    r.ok = False
    r.text = text
    return r


CALL_PLAN = OptionsPlan(
    symbol="TSLA", direction="call", expiration="2026-06-10", strike=440.0,
    entry_premium=2.00, stop_premium=1.65, target_premium=2.70, contracts=5,
    max_loss=175.0, max_reward=350.0,
    stock_entry=440.0, stock_stop=439.3, stock_target=441.4,
    quote_source="estimated_delta", occ_symbol="TSLA260610C00440000",
)


class TestNtfyConfig(unittest.TestCase):
    def test_defaults_to_aharg_ops(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NTFY_TOPIC", None)
            n = NtfyNotifier()
            self.assertEqual(n.topic, "aharg-ops")
            self.assertEqual(n.url, "https://ntfy.sh/aharg-ops")

    def test_env_topic_overrides_default(self):
        with mock.patch.dict(os.environ, {"NTFY_TOPIC": "custom-x"}):
            self.assertEqual(NtfyNotifier().topic, "custom-x")

    def test_token_sets_bearer_header(self):
        with mock.patch.dict(os.environ, {"NTFY_TOKEN": "tk_abc"}):
            self.assertEqual(NtfyNotifier()._headers.get("Authorization"),
                             "Bearer tk_abc")


class TestNtfyTransport(unittest.TestCase):
    def setUp(self):
        self.n = NtfyNotifier(topic="t-test")

    def test_post_success_increments_posted(self):
        with mock.patch.object(ntfy_notifier.requests, "post",
                               return_value=_ok_response()) as p:
            ok = self.n.post_text("hello", title="Hi", tags="rocket", priority="high")
        self.assertTrue(ok)
        self.assertEqual((self.n.posted, self.n.failed), (1, 0))
        # metadata rode in headers, body is the message
        _, kwargs = p.call_args
        self.assertEqual(kwargs["headers"]["Title"], "Hi")
        self.assertEqual(kwargs["headers"]["Priority"], "high")
        self.assertEqual(kwargs["data"], b"hello")

    def test_non_ascii_title_is_stripped_for_header(self):
        # ntfy headers must be latin-1/ascii safe; emoji in title must not crash.
        with mock.patch.object(ntfy_notifier.requests, "post",
                               return_value=_ok_response()) as p:
            self.n.post_text("body", title="Omen 🚀 armed")
        _, kwargs = p.call_args
        self.assertEqual(kwargs["headers"]["Title"], "Omen  armed")

    def test_retry_then_log_masks_topic(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "failed_ntfy.jsonl"
            with mock.patch.object(ntfy_notifier, "FAILED_LOG", log), \
                 mock.patch.object(ntfy_notifier, "RETRY_BACKOFF", (0.0, 0.0)), \
                 mock.patch.object(ntfy_notifier.requests, "post",
                                   side_effect=RuntimeError("net down for t-test")):
                ok = self.n.post_text("body", title="T")
            self.assertFalse(ok)
            self.assertEqual(self.n.failed, 1)
            written = log.read_text()
            self.assertNotIn("t-test", written)   # topic never leaks
            rec = json.loads(written.splitlines()[-1])
            self.assertEqual(rec["attempts"], ntfy_notifier.RETRY_ATTEMPTS)
            self.assertEqual(rec["server"], "https://ntfy.sh")

    def test_retries_three_times_on_failure(self):
        with mock.patch.object(ntfy_notifier, "RETRY_BACKOFF", (0.0, 0.0)), \
             mock.patch.object(ntfy_notifier, "FAILED_LOG",
                               Path(tempfile.mkdtemp()) / "f.jsonl"), \
             mock.patch.object(ntfy_notifier.requests, "post",
                               return_value=_fail_response()) as p:
            self.n.post_text("body", title="T")
        self.assertEqual(p.call_count, ntfy_notifier.RETRY_ATTEMPTS)


class TestNtfyFormatting(unittest.TestCase):
    def setUp(self):
        self.n = NtfyNotifier(topic="t-test")

    def test_signal_push_trade_is_high_priority(self):
        with mock.patch.object(ntfy_notifier.requests, "post",
                               return_value=_ok_response()) as p:
            candle = Candle(timestamp="09:35:00", open=440.0, high=441.0,
                            low=439.5, close=440.8, volume=1000)
            self.n.post_signal(SignalType.BREAK_AND_RETEST, candle, "retest",
                               CALL_PLAN, grade="A+", tier="TRADE")
        _, kwargs = p.call_args
        self.assertEqual(kwargs["headers"]["Priority"], "high")
        self.assertIn("TSLA", kwargs["headers"]["Title"])
        self.assertIn("$440", kwargs["data"].decode())

    def test_watch_push_is_default_priority(self):
        with mock.patch.object(ntfy_notifier.requests, "post",
                               return_value=_ok_response()) as p:
            candle = Candle(timestamp="09:35:00", open=1, high=2, low=0.5, close=1.5, volume=1)
            self.n.post_signal(SignalType.BREAK_AND_RETEST, candle, "watch",
                               CALL_PLAN, grade="C", tier="WATCH")
        _, kwargs = p.call_args
        self.assertEqual(kwargs["headers"]["Priority"], "default")

    def test_paper_close_win_vs_loss(self):
        with mock.patch.object(ntfy_notifier.requests, "post",
                               return_value=_ok_response()) as p:
            self.n.post_paper_close({"outcome": "target", "symbol": "TSLA",
                                     "direction": "call", "pnl": 350.0, "contracts": 5,
                                     "entry_premium": 2.0, "exit_premium": 2.7,
                                     "grade": "A+", "setup": "break_and_retest"})
            win_title = p.call_args.kwargs["headers"]["Title"]
            self.n.post_paper_close({"outcome": "stop", "symbol": "AMD",
                                     "direction": "put", "pnl": -728.0, "contracts": 8,
                                     "entry_premium": 2.57, "exit_premium": 1.66,
                                     "grade": "A", "setup": "break_and_retest"})
            loss = p.call_args.kwargs
        self.assertIn("WIN", win_title)
        self.assertIn("LOSS", loss["headers"]["Title"])
        self.assertEqual(loss["headers"]["Priority"], "high")  # losses ping loud


class TestSignalRunnerWiring(unittest.TestCase):
    def test_ntfy_on_discord_off(self):
        from signal_runner import SignalRunner
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NTFY_TOPIC", None)
            r = SignalRunner(post_to_discord=False)
        self.assertTrue(r.post_to_ntfy)
        self.assertIsNotNone(r.ntfy)
        self.assertEqual(r.ntfy.topic, "aharg-ops")
        self.assertFalse(r.post_to_discord)
        self.assertIsNone(r.discord)

    def test_no_ntfy_flag_disables(self):
        from signal_runner import SignalRunner
        r = SignalRunner(post_to_discord=False, post_to_ntfy=False)
        self.assertFalse(r.post_to_ntfy)
        self.assertIsNone(r.ntfy)


class TestPaperFlowAndSlippage(unittest.TestCase):
    def _fresh_book(self):
        return PaperBook(ledger_path=Path(tempfile.mkdtemp()) / "pt.jsonl")

    def test_open_then_stop_out_pnl(self):
        book = self._fresh_book()
        put = OptionsPlan(
            symbol="NVDA", direction="put", expiration="2026-06-10", strike=850.0,
            entry_premium=3.00, stop_premium=2.50, target_premium=4.00, contracts=4,
            max_loss=200.0, max_reward=400.0,
            stock_entry=850.0, stock_stop=852.5, stock_target=845.0,
            quote_source="estimated_delta", occ_symbol="NVDA260610P00850000")
        book.open_from_plan(put, ts="10:00:00")
        closed = book.mark("NVDA", high=853.0, low=849.0, ts="10:05:00")
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0]["outcome"], "stop")
        self.assertEqual(closed[0]["pnl"], round((2.50 - 3.00) * 100 * 4, 2))

    def test_target_hit_pnl(self):
        book = self._fresh_book()
        book.open_from_plan(CALL_PLAN, ts="09:35:00")
        closed = book.mark("TSLA", high=441.5, low=440.5, ts="09:41:00")
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0]["outcome"], "target")
        self.assertEqual(closed[0]["pnl"], round((2.70 - 2.00) * 100 * 5, 2))

    def test_slippage_widens_loss_and_shrinks_gain(self):
        # 2% per side: exit*(0.98), entry*(1.02)
        with mock.patch.object(paper_trader, "PAPER_SLIPPAGE_PCT", 0.02):
            book = self._fresh_book()
            book.open_from_plan(CALL_PLAN, ts="09:35:00")
            closed = book.mark("TSLA", high=441.5, low=440.5, ts="09:41:00")
            gain = closed[0]["pnl"]
            exp = round((2.70 * 0.98 - 2.00 * 1.02) * 100 * 5, 2)
        self.assertEqual(gain, exp)
        # slipped gain must be strictly less than the frictionless gain
        self.assertLess(gain, round((2.70 - 2.00) * 100 * 5, 2))

    def test_slippage_default_off_is_exact(self):
        self.assertEqual(paper_trader.PAPER_SLIPPAGE_PCT, 0.0)
        book = self._fresh_book()
        book.open_from_plan(CALL_PLAN, ts="09:35:00")
        closed = book.mark("TSLA", high=441.5, low=440.5, ts="09:41:00")
        self.assertEqual(closed[0]["pnl"], round((2.70 - 2.00) * 100 * 5, 2))


class TestSignalToNtfyIntegration(unittest.TestCase):
    """End-to-end: a paper open->close cycle drives real ntfy pushes (captured)."""

    def test_full_chain_pushes(self):
        posts = []

        def _capture(url, data=None, headers=None, timeout=None):
            posts.append({"url": url, "title": headers.get("Title"),
                          "priority": headers.get("Priority"), "body": data.decode()})
            return _ok_response()

        n = NtfyNotifier(topic="aharg-ops")
        book = PaperBook(ledger_path=Path(tempfile.mkdtemp()) / "pt.jsonl")
        with mock.patch.object(ntfy_notifier.requests, "post", side_effect=_capture):
            pos = book.open_from_plan(CALL_PLAN, ts="09:35:00", grade="A+",
                                      setup="break_and_retest")
            n.post_paper_open(pos)
            for ev in book.mark("TSLA", high=441.5, low=440.5, ts="09:41:00"):
                n.post_paper_close(ev)

        self.assertEqual(len(posts), 2)
        self.assertTrue(all(p["url"] == "https://ntfy.sh/aharg-ops" for p in posts))
        self.assertIn("PAPER OPEN", posts[0]["title"])
        self.assertIn("PAPER WIN", posts[1]["title"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
