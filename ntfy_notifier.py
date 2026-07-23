"""ntfy push-notification integration for Omen trading signals.

Companion to discord_bot.py. Discord stays the rich-embed channel; ntfy is the
phone-push channel — one topic, instant alerts on the lock screen even when
Discord isn't open. Both fire independently: a broken Discord webhook never
starves ntfy and vice-versa.

Config (all via env, loaded from .env by signal_runner._load_env_file):
    NTFY_TOPIC    required to enable. The subscribe topic (e.g. "omen-austin").
                  Pick something unguessable — anyone with the topic can read it.
    NTFY_SERVER   optional, default https://ntfy.sh. Self-hosted: https://ntfy.example.com
    NTFY_TOKEN    optional, Bearer token for a protected topic / self-hosted auth.

If NTFY_TOPIC is unset the constructor raises ValueError, and the caller
disables ntfy gracefully (same contract as DiscordSignalBot) — a run with no
ntfy configured is never a crash.

Reliability mirrors discord_bot: 3 attempts with backoff, and on final failure
the full message is appended to journal/failed_ntfy.jsonl so nothing is lost.
The topic/URL are NEVER written to that log — only a masked label.
"""

import os
import json
import time
import requests
from pathlib import Path
from typing import Optional, Tuple

from omen_bot import SignalType, Candle
from options_sizer import OptionsPlan

FAILED_LOG = Path(__file__).parent / "journal" / "failed_ntfy.jsonl"
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = (1.0, 2.0)  # seconds between attempts (2 gaps for 3 attempts)
DEFAULT_SERVER = "https://ntfy.sh"


class NtfyNotifier:
    """Push Omen signals + paper-trade fills to an ntfy topic."""

    def __init__(self, topic: Optional[str] = None, server: Optional[str] = None,
                 token: Optional[str] = None):
        self.topic = topic or os.getenv("NTFY_TOPIC")
        if not self.topic:
            raise ValueError("NTFY_TOPIC not set. Set via env var or __init__ arg.")
        self.server = (server or os.getenv("NTFY_SERVER") or DEFAULT_SERVER).rstrip("/")
        self.url = f"{self.server}/{self.topic}"
        token = token or os.getenv("NTFY_TOKEN")
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}
        # Per-scan-cycle delivery counters (live_scanner reads + resets)
        self.posted = 0
        self.failed = 0

    # ---- formatting ----

    def _plan_body(self, plan: OptionsPlan) -> str:
        """One-glance body for a signal push (ntfy renders plain text)."""
        arrow = "CALL" if plan.direction == "call" else "PUT"
        return (
            f"{plan.symbol} ${plan.strike:g} {arrow} {plan._dte_label()}\n"
            f"Entry ${plan.entry_premium:.2f}  Stop ${plan.stop_premium:.2f}  "
            f"Target ${plan.target_premium:.2f}\n"
            f"{plan.contracts}x  -${plan.max_loss:.0f} / +${plan.max_reward:.0f}\n"
            f"Stock: entry ${plan.stock_entry:.2f} | stop ${plan.stock_stop:.2f} "
            f"| target ${plan.stock_target:.2f}"
        )

    # ---- transport ----

    def _post(self, body: str, title: str, tags: str = "",
              priority: str = "default", click: str = "") -> bool:
        """POST one message with 3 attempts + backoff.

        ntfy takes the message as the request body; metadata rides in headers
        (Title/Tags/Priority/Click). On final failure appends to failed_ntfy.jsonl.
        Updates self.posted/self.failed (reset per scan by live_scanner).
        """
        headers = dict(self._headers)
        # ntfy headers must be latin-1 safe; strip anything exotic from the title.
        headers["Title"] = title.encode("ascii", "ignore").decode() or "Omen"
        if tags:
            headers["Tags"] = tags
        if priority:
            headers["Priority"] = priority
        if click:
            headers["Click"] = click

        last_err, last_status = "", None
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                resp = requests.post(self.url, data=body.encode("utf-8"),
                                     headers=headers, timeout=5)
                last_status = resp.status_code
                if resp.ok:  # 2xx
                    self.posted += 1
                    return True
                last_err = f"HTTP {resp.status_code} {resp.text[:120]}"
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BACKOFF[attempt - 1])
        # Never leak the topic/URL into logs — mask both.
        last_err = last_err.replace(self.url, "<endpoint>").replace(self.topic, "<topic>")
        self.failed += 1
        self._log_failed(title, body, last_status, last_err)
        print(f"ntfy post FAILED after {RETRY_ATTEMPTS}x: {last_err}")
        return False

    def _log_failed(self, title: str, body: str, status: Optional[int], err: str) -> None:
        """Append the failed message + context. Topic/URL never written — only
        a masked server label."""
        FAILED_LOG.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "server": self.server,          # host only, no topic
            "http_status": status,
            "attempts": RETRY_ATTEMPTS,
            "error": err,
            "title": title,
            "body": body,
        }
        with open(FAILED_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")

    # ---- public API (parallels DiscordSignalBot) ----

    def post_signal(
        self,
        signal_type: SignalType,
        candle: Candle,
        reason: str,
        plan: Optional[OptionsPlan] = None,
        grade: str = "",
        stop_level_name: str = "",
        stop_width_pct: float = 0.0,
        tier: str = "TRADE",
    ) -> bool:
        """Push a fired signal. TRADE tier is high priority; WATCH is default."""
        setup = signal_type.value.replace("_", " ").title() if hasattr(signal_type, "value") else str(signal_type)
        if isinstance(plan, OptionsPlan):
            arrow = "up" if plan.direction == "call" else "down"
            emoji = "chart_with_upwards_trend" if plan.direction == "call" else "chart_with_downwards_trend"
            title = f"{tier} {plan.symbol} {plan.direction.upper()} · {grade or '?'}"
            body = f"{setup} — {reason}\n\n{self._plan_body(plan)}"
            tags = f"dart,{emoji},{arrow}"
        else:
            title = f"{tier} signal · {grade or '?'}"
            body = f"{setup} — {reason}\n@ {candle.timestamp}  ${candle.close:.2f}"
            tags = "dart"
        priority = "high" if tier == "TRADE" else "default"
        return self._post(body, title=title, tags=tags, priority=priority)

    def post_paper_open(self, pos) -> bool:
        """Push a paper-trade entry (PaperPosition)."""
        arrow = "CALL" if pos.direction == "call" else "PUT"
        title = f"PAPER OPEN {pos.symbol} {arrow} · {pos.grade}"
        body = (
            f"{pos.contracts}x {pos.symbol} ${pos.strike:g} {arrow} @ ${pos.entry_premium:.2f}\n"
            f"Stop ${pos.stop_premium:.2f}  Target ${pos.target_premium:.2f}\n"
            f"Stock: entry ${pos.stock_entry:.2f} | stop ${pos.stock_stop:.2f} "
            f"| target ${pos.stock_target:.2f}"
        )
        return self._post(body, title=title, tags="memo,green_circle", priority="default")

    def post_paper_close(self, ev: dict) -> bool:
        """Push a paper-trade close/scale event (close-event dict from PaperBook.mark)."""
        outcome = ev.get("outcome", "")
        symbol = ev.get("symbol", "?")
        direction = str(ev.get("direction", "")).upper()
        if outcome == "be_scale":
            title = f"PAPER SCALE {symbol} {direction} · breakeven"
            body = (f"Scaled {ev.get('scale_contracts', '?')} at breakeven "
                    f"${ev.get('be_exit', 0):.2f}; {ev.get('runner_contracts', '?')} runner(s) left")
            return self._post(body, title=title, tags="scales", priority="default")
        pnl = ev.get("pnl", 0.0)
        win = outcome == "target" or pnl > 0
        tag = "white_check_mark" if win else "x"
        result = "WIN" if win else "LOSS"
        title = f"PAPER {result} {symbol} {direction} · {outcome.upper()}"
        body = (
            f"P&L ${pnl:.2f}  ({ev.get('contracts', '?')}x)\n"
            f"Entry ${ev.get('entry_premium', 0):.2f} -> exit ${ev.get('exit_premium', 0):.2f}\n"
            f"Grade {ev.get('grade', '?')}  {ev.get('setup', '')}"
        )
        return self._post(body, title=title, tags=tag, priority="high" if not win else "default")

    def post_text(self, content: str, title: str = "Omen", tags: str = "",
                  priority: str = "default") -> bool:
        """Plain notice (startup card, futures card, halt notices)."""
        return self._post(content[:3900], title=title, tags=tags, priority=priority)

    def post_test_card(self) -> Tuple[int, bool]:
        """Startup self-test: single attempt, return (http_status, ok)."""
        headers = dict(self._headers)
        headers.update({"Title": "Omen ntfy self-test", "Tags": "test_tube",
                        "Priority": "default"})
        try:
            resp = requests.post(self.url, data=b"ntfy delivery OK",
                                 headers=headers, timeout=8)
            return resp.status_code, resp.ok
        except Exception as e:
            print(f"self-test request error: {type(e).__name__}: {e}")
            return 0, False


# Test / self-test
if __name__ == "__main__":
    import sys
    import argparse
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _env = Path(__file__).parent / ".env"
    if _env.exists():
        for _line in _env.read_text().splitlines():
            if _line.strip() and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

    parser = argparse.ArgumentParser(description="Omen ntfy notifier")
    parser.add_argument("--test", action="store_true",
                        help="Post one test push to NTFY_TOPIC and print HTTP status.")
    parser.add_argument("--format", action="store_true",
                        help="Print sample push bodies without posting (offline).")
    args = parser.parse_args()

    if args.test:
        n = NtfyNotifier()
        status, ok = n.post_test_card()
        print(f"HTTP {status} -> {'OK' if ok else 'FAILED'}  (topic tail …{n.topic[-4:]})")
        raise SystemExit(0 if ok else 1)

    if args.format:
        # Offline: build a notifier without hitting the network.
        n = NtfyNotifier(topic="demo")
        plan = OptionsPlan(
            symbol="TSLA", direction="call", expiration="2026-06-10", strike=440.0,
            entry_premium=2.00, stop_premium=1.65, target_premium=2.70, contracts=5,
            max_loss=175.0, max_reward=350.0,
            stock_entry=440.0, stock_stop=439.3, stock_target=441.4,
            quote_source="estimated_delta", occ_symbol="TSLA260610C00440000",
        )
        candle = Candle(timestamp="09:35:00", open=440.0, high=441.0, low=439.5, close=440.8, volume=1000)
        print("== signal push ==")
        print("TITLE: TRADE TSLA CALL · A+")
        print(f"BODY:\n{'Break And Retest — retest entry'}\n\n{n._plan_body(plan)}")
        print("\n== paper close (win) ==")
        ev = {"outcome": "target", "symbol": "TSLA", "direction": "call", "pnl": 350.0,
              "contracts": 5, "entry_premium": 2.00, "exit_premium": 2.70,
              "grade": "A+", "setup": "break_and_retest"}
        print(f"TITLE: PAPER WIN TSLA CALL · TARGET\nBODY:\n"
              f"P&L $350.00  (5x)\nEntry $2.00 -> exit $2.70\nGrade A+  break_and_retest")
        raise SystemExit(0)

    parser.print_help()
