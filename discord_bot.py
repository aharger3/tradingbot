"""Discord webhook integration for trading signals"""

import os
import json
import requests
from typing import Optional
from dataclasses import dataclass
from vanquish_bot import SignalType, Candle
from position_sizer import SizingPlan
from options_sizer import OptionsPlan


class DiscordSignalBot:
    """Post trading signals to Discord webhook"""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        if not self.webhook_url:
            raise ValueError("DISCORD_WEBHOOK_URL not set. Set via env var or __init__ arg.")

    def format_signal_message(
        self,
        signal_type: SignalType,
        candle: Candle,
        reason: str,
        plan=None,  # OptionsPlan (preferred) or legacy SizingPlan
    ) -> dict:
        """Format signal as Discord embed. plan may be OptionsPlan or SizingPlan."""
        color_map = {
            SignalType.BREAK_AND_RETEST: 3066993,
            SignalType.ONE_CANDLE_RULE: 15844367,
            SignalType.REENTRY_84_RULE: 9109760,
            SignalType.NONE: 9807270,
        }

        if isinstance(plan, OptionsPlan):
            return self._format_options_embed(signal_type, candle, reason, plan, color_map)
        return self._format_stock_embed(signal_type, candle, reason, plan, color_map)

    def _format_options_embed(self, signal_type, candle, reason, plan: OptionsPlan, color_map) -> dict:
        arrow = "↑ CALL" if plan.direction == "call" else "↓ PUT"
        dte = plan._dte_label()
        title = f"🚀 {plan.symbol} {dte} ${plan.strike:g} {arrow}"
        fields = [
            {"name": "Setup", "value": signal_type.value.replace("_", " ").title(), "inline": True},
            {"name": "Time", "value": candle.timestamp, "inline": True},
            {"name": "Expiration", "value": plan.expiration, "inline": True},
            {"name": "Strike", "value": f"${plan.strike:g}", "inline": True},
            {"name": "Contracts", "value": f"{plan.contracts}", "inline": True},
            {"name": "Quote", "value": plan.quote_source, "inline": True},
            {"name": "Entry", "value": f"${plan.entry_premium:.2f}", "inline": True},
            {"name": "Stop", "value": f"${plan.stop_premium:.2f}", "inline": True},
            {"name": "Target (2R)", "value": f"${plan.target_premium:.2f}", "inline": True},
            {"name": "Max Loss / Reward",
             "value": f"-${plan.max_loss:.0f} / +${plan.max_reward:.0f}", "inline": False},
            {"name": "Reason", "value": reason, "inline": False},
            {"name": "Stock ref",
             "value": f"entry ${plan.stock_entry:.2f} | stop ${plan.stock_stop:.2f} | target ${plan.stock_target:.2f}",
             "inline": False},
        ]
        return {
            "embeds": [{
                "title": title,
                "color": color_map.get(signal_type, 9807270),
                "fields": fields,
                "footer": {"text": f"Vanquish Signal Bot · {plan.occ_symbol or 'no OCC'}"},
            }]
        }

    def _format_stock_embed(self, signal_type, candle, reason, plan, color_map) -> dict:
        fields = [
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
                "footer": {"text": "Vanquish Signal Bot"},
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

    def post_signal(
        self,
        signal_type: SignalType,
        candle: Candle,
        reason: str,
        plan=None,  # OptionsPlan or SizingPlan
    ) -> bool:
        """Post signal to Discord. Returns True if successful."""
        try:
            payload = self.format_signal_message(signal_type, candle, reason, plan)
            resp = requests.post(self.webhook_url, json=payload, timeout=5)
            return resp.status_code in (200, 204)
        except Exception as e:
            print(f"Discord post failed: {e}")
            return False

    def post_trade_result(self, trade_data: dict) -> bool:
        """Post completed trade to Discord. Returns True if successful."""
        try:
            payload = self.format_trade_result(trade_data)
            resp = requests.post(self.webhook_url, json=payload, timeout=5)
            return resp.status_code in (200, 204)
        except Exception as e:
            print(f"Discord post failed: {e}")
            return False


# Test
if __name__ == "__main__":
    # Test without real webhook (will fail but shows format)
    try:
        bot = DiscordSignalBot("https://discord.com/api/webhooks/dummy/dummy")

        test_candle = Candle(
            timestamp="09:35:00",
            open=102.5,
            high=103.2,
            low=102.0,
            close=103.0,
            volume=1200
        )

        print("Signal format:")
        print(json.dumps(bot.format_signal_message(SignalType.BREAK_AND_RETEST, test_candle, "A+ retest entry"), indent=2))

        print("\nTrade result format:")
        trade_data = {
            "entry_time": "09:35:00",
            "entry_price": 103.0,
            "exit_time": "09:42:00",
            "exit_price": 105.0,
            "profit_loss": 2.0,
            "signal_type": "BREAK_AND_RETEST",
            "is_win": True,
            "pnl_pct": 1.94
        }
        print(json.dumps(bot.format_trade_result(trade_data), indent=2))

    except ValueError as e:
        print(f"Note: {e}")
        print("Set DISCORD_WEBHOOK_URL env var to test posting.")
