"""Discord webhook integration for trading signals"""

import os
import json
import time
import requests
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass
from omen_bot import SignalType, Candle
from position_sizer import SizingPlan
from options_sizer import OptionsPlan

# Reliability (2026-07-11): every signal MUST reach Discord or be recoverable.
# Failed posts retry 3x with backoff; on final failure the full payload is
# appended here so nothing is silently lost. URL is NEVER written to disk —
# only a masked endpoint label, so logs stay safe to share.
FAILED_LOG = Path(__file__).parent / "journal" / "failed_webhooks.jsonl"
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = (1.0, 2.0)  # seconds between attempts (2 gaps for 3 attempts)


class DiscordSignalBot:
    """Post trading signals to Discord webhook"""

    def __init__(self, webhook_url: Optional[str] = None):
        # Bot-token mode preferred: Trader bot lacks MANAGE_WEBHOOKS in the
        # trading channel (2026-07-07), so we post via the messages API instead
        # of a webhook. Embed payloads are identical on both endpoints.
        tok, chan = os.getenv("DISCORD_BOT_TOKEN"), os.getenv("DISCORD_CHANNEL_ID")
        self._headers = {}
        self._channel_id = chan
        if webhook_url:
            self.webhook_url = webhook_url
            self._endpoint = "webhook"
        elif tok and chan:
            self.webhook_url = f"https://discord.com/api/v10/channels/{chan}/messages"
            self._headers = {"Authorization": f"Bot {tok}",
                             "User-Agent": "DiscordBot (omen, 1.0)"}
            self._endpoint = "bot_channel"
        else:
            self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
            self._endpoint = "webhook"
        if not self.webhook_url:
            raise ValueError("DISCORD_WEBHOOK_URL not set. Set via env var or __init__ arg.")
        # Per-scan-cycle delivery counters (live_scanner reads + resets)
        self.posted = 0
        self.failed = 0

    def format_signal_message(
        self,
        signal_type: SignalType,
        candle: Candle,
        reason: str,
        plan=None,  # OptionsPlan (preferred) or legacy SizingPlan
        grade: str = "",
        stop_level_name: str = "",
        stop_width_pct: float = 0.0,
    ) -> dict:
        """Format signal as Discord embed. plan may be OptionsPlan or SizingPlan."""
        color_map = {
            SignalType.BREAK_AND_RETEST: 3066993,
            SignalType.ONE_CANDLE_RULE: 15844367,
            SignalType.REENTRY_84_RULE: 9109760,
            SignalType.NONE: 9807270,
        }
        # Grade colors: A+ green, A teal, B blue, C yellow, D red
        grade_colors = {"A+": 3066993, "A": 1752220, "B": 3447003, "C": 15844367, "D": 15158332}
        if grade in grade_colors:
            color_map = {k: grade_colors[grade] for k in color_map}

        if isinstance(plan, OptionsPlan):
            return self._format_options_embed(signal_type, candle, reason, plan, color_map,
                                               grade, stop_level_name, stop_width_pct)
        return self._format_stock_embed(signal_type, candle, reason, plan, color_map,
                                         grade, stop_level_name, stop_width_pct)

    def _format_options_embed(self, signal_type, candle, reason, plan: OptionsPlan,
                               color_map, grade="", stop_level_name="", stop_width_pct=0.0) -> dict:
        arrow = "↑ CALL" if plan.direction == "call" else "↓ PUT"
        dte = plan._dte_label()
        title = f"🚀 {plan.symbol} {dte} ${plan.strike:g} {arrow}"
        fields = [
            {"name": "Setup", "value": signal_type.value.replace("_", " ").title(), "inline": True},
            {"name": "Grade", "value": grade or "N/A", "inline": True},
            {"name": "Time", "value": candle.timestamp, "inline": True},
            {"name": "Expiration", "value": plan.expiration, "inline": True},
            {"name": "Strike", "value": f"${plan.strike:g}", "inline": True},
            {"name": "Contracts", "value": f"{plan.contracts}", "inline": True},
            {"name": "Entry", "value": f"${plan.entry_premium:.2f}", "inline": True},
            {"name": "Stop", "value": f"${plan.stop_premium:.2f}", "inline": True},
            {"name": "Target (2R)", "value": f"${plan.target_premium:.2f}", "inline": True},
        ]
        if stop_width_pct:
            stop_label = f"{stop_level_name or 'N/A'} ({stop_width_pct}%)"
            fields.append({"name": "Stop level", "value": stop_label, "inline": False})
        fields += [
            {"name": "Max Loss / Reward",
             "value": f"-${plan.max_loss:.0f} / +${plan.max_reward:.0f}", "inline": False},
            {"name": "Reason", "value": reason, "inline": False},
            {"name": "Stock ref",
             "value": f"entry ${plan.stock_entry:.2f} | stop ${plan.stock_stop:.2f} | target ${plan.stock_target:.2f}",
             "inline": False},
        ]
        if plan.option_warnings:
            fields.append({"name": "⚠ Warnings", "value": ", ".join(plan.option_warnings), "inline": False})
        return {
            "embeds": [{
                "title": title,
                "color": color_map.get(signal_type, 9807270),
                "fields": fields,
                "footer": {"text": f"Omen Signal Bot · Grade {grade} · {plan.occ_symbol or 'no OCC'}"},
            }]
        }

    def _format_stock_embed(self, signal_type, candle, reason, plan, color_map,
                             grade="", stop_level_name="", stop_width_pct=0.0) -> dict:
        fields = [
            {"name": "Grade", "value": grade or "N/A", "inline": True},
            {"name": "Time", "value": candle.timestamp, "inline": True},
            {"name": "Reason", "value": reason, "inline": False},
        ]
        if plan is not None:
            arrow = "↑ CALLS" if plan.direction == "call" else "↓ PUTS"
            fields.extend([
                {"name": "Direction", "value": arrow, "inline": True},
                {"name": "Entry", "value": f"${plan.stock_entry:.2f}", "inline": True},
                {"name": "Stop", "value": f"${plan.stock_stop:.2f}", "inline": True},
                {"name": "Target (2R)", "value": f"${plan.stock_target:.2f}", "inline": True},
                {"name": "~Contracts", "value": f"{plan.contracts_estimated}", "inline": True},
                {"name": "Max Loss / Reward",
                 "value": f"-${plan.max_loss:.0f} / +${plan.max_reward:.0f}", "inline": False},
            ])
        else:
            fields.append({"name": "Price", "value": f"${candle.close:.2f}", "inline": True})
        fields.append({
            "name": "Candle",
            "value": f"O={candle.open} H={candle.high} L={candle.low} C={candle.close}",
            "inline": False,
        })
        return {
            "embeds": [{
                "title": f"🚀 {signal_type.value.upper().replace('_', ' ')}",
                "color": color_map.get(signal_type, 9807270),
                "fields": fields,
                "footer": {"text": "Omen Signal Bot"},
            }]
        }

    def format_trade_result(self, trade_data: dict) -> dict:
        """Format completed trade as Discord embed"""
        is_win = trade_data.get("is_win", False)
        status = "✅ WIN" if is_win else "❌ LOSS"
        color = 3066993 if is_win else 15158332  # Green if win, Red if loss

        return {
            "embeds": [
                {
                    "title": f"{status} | {trade_data.get('signal_type', 'TRADE')}",
                    "color": color,
                    "fields": [
                        {"name": "Entry", "value": f"{trade_data.get('entry_time')} @ ${trade_data.get('entry_price'):.2f}", "inline": False},
                        {"name": "Exit", "value": f"{trade_data.get('exit_time')} @ ${trade_data.get('exit_price'):.2f}", "inline": False},
                        {"name": "P&L", "value": f"${trade_data.get('profit_loss'):.2f} ({trade_data.get('pnl_pct'):.2f}%)", "inline": False},
                    ],
                    "footer": {"text": "Trade Closed"},
                }
            ]
        }

    def _post_with_retry(self, payload: dict) -> bool:
        """POST payload with 3 attempts + backoff. On final failure append the
        full payload to journal/failed_webhooks.jsonl. Returns True on success.
        Updates self.posted/self.failed counters (reset per scan by live_scanner).
        """
        last_err, last_status = "", None
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                resp = requests.post(self.webhook_url, json=payload,
                                     headers=self._headers, timeout=5)
                last_status = resp.status_code
                if resp.ok:  # 2xx
                    self.posted += 1
                    return True
                last_err = f"HTTP {resp.status_code} {resp.text[:120]}"
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BACKOFF[attempt - 1])
        # Scrub the webhook URL (token lives in the path) from the error string
        # — requests decomposes it into host + path in connection-error text,
        # so replace both the full URL and its path component.
        from urllib.parse import urlparse
        _path = urlparse(self.webhook_url).path
        last_err = last_err.replace(self.webhook_url, "<endpoint>").replace(_path, "<path>")
        self.failed += 1
        self._log_failed(payload, last_status, last_err)
        print(f"Discord post FAILED after {RETRY_ATTEMPTS}x: {last_err}")
        return False

    def _log_failed(self, payload: dict, status: Optional[int], err: str) -> None:
        """Append full payload + failure context to failed_webhooks.jsonl.
        URL is never written — only a masked endpoint label."""
        FAILED_LOG.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "endpoint": self._endpoint,
            "channel_tail": (self._channel_id[-4:] if self._channel_id else None),
            "http_status": status,
            "attempts": RETRY_ATTEMPTS,
            "error": err,
            "payload": payload,
        }
        with open(FAILED_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")

    def post_signal(
        self,
        signal_type: SignalType,
        candle: Candle,
        reason: str,
        plan=None,  # OptionsPlan or SizingPlan
        grade: str = "",
        stop_level_name: str = "",
        stop_width_pct: float = 0.0,
    ) -> bool:
        """Post signal to Discord. Returns True if successful."""
        payload = self.format_signal_message(signal_type, candle, reason, plan,
                                              grade, stop_level_name, stop_width_pct)
        return self._post_with_retry(payload)

    def post_text(self, content: str) -> bool:
        """Plain-content post (futures cards, notices)."""
        return self._post_with_retry({"content": content[:1990]})

    def post_trade_result(self, trade_data: dict) -> bool:
        """Post completed trade to Discord. Returns True if successful."""
        return self._post_with_retry(self.format_trade_result(trade_data))

    def post_test_card(self) -> Tuple[int, bool]:
        """Startup self-test: post one test card, return (http_status, ok).
        Single attempt (no retry) so the real HTTP code is visible. Used by
        `python discord_bot.py --test`."""
        payload = {"embeds": [{
            "title": "🧪 Omen Signal Bot — self-test",
            "color": 9807270,
            "fields": [
                {"name": "Endpoint", "value": self._endpoint, "inline": True},
                {"name": "Status", "value": "delivered OK", "inline": True},
            ],
            "footer": {"text": f"Omen self-test · {__import__('datetime').date.today().isoformat()}"},
        }]}
        try:
            resp = requests.post(self.webhook_url, json=payload,
                                  headers=self._headers, timeout=8)
            return resp.status_code, resp.ok
        except Exception as e:
            print(f"self-test request error: {type(e).__name__}: {e}")
            return 0, False


# Test / self-test
if __name__ == "__main__":
    import sys, argparse
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    # Standalone run: load .env so DISCORD_* / TASTYTRADE_* are visible without
    # the signal_runner .env loader that live_scanner normally does.
    _env = Path(__file__).parent / ".env"
    if _env.exists():
        for _line in _env.read_text().splitlines():
            if _line.strip() and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())
    parser = argparse.ArgumentParser(description="Omen Discord signal bot")
    parser.add_argument("--test", action="store_true",
                        help="Post one test card to the configured channel and print HTTP status.")
    parser.add_argument("--format", action="store_true",
                        help="Print sample embed JSON without posting (offline).")
    args = parser.parse_args()

    if args.test:
        bot = DiscordSignalBot()
        status, ok = bot.post_test_card()
        print(f"HTTP {status} -> {'OK ✓' if ok else 'FAILED ✗'}")
        raise SystemExit(0 if ok else 1)

    if args.format:
        bot = DiscordSignalBot("https://discord.com/api/webhooks/dummy/dummy")
        test_candle = Candle(timestamp="09:35:00", open=102.5, high=103.2,
                              low=102.0, close=103.0, volume=1200)
        print("Signal format:")
        print(json.dumps(bot.format_signal_message(SignalType.BREAK_AND_RETEST, test_candle, "A+ retest entry"), indent=2))
        print("\nTrade result format:")
        print(json.dumps(bot.format_trade_result({
            "entry_time": "09:35:00", "entry_price": 103.0, "exit_time": "09:42:00",
            "exit_price": 105.0, "profit_loss": 2.0, "signal_type": "BREAK_AND_RETEST",
            "is_win": True, "pnl_pct": 1.94}), indent=2))
        raise SystemExit(0)

    parser.print_help()
