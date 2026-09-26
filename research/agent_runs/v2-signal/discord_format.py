"""Format an OMEN v2 signal as the s06 Discord-card-style ntfy push.

Field order and skeleton match
life-plan/07-money/omen/v2/s06-discord-notification.md section 3. The card is
UNCONDITIONALLY labeled PAPER / EXPERIMENTAL: per OMEN-SHIP-PLAN-v2.md section 4,
the go/no-go gate has only cleared (a) backtest -- OOS (b), a month of paper (c)
and the bootstrap sanity check (d) have not run yet, so no edge is "proven" and
every message must say so (per the build-ticket instruction).
"""
from __future__ import annotations

from dataclasses import dataclass

PAPER_LABEL = "PAPER / EXPERIMENTAL"

POINT_VALUE = {"MNQ": 2.0, "MES": 5.0}   # $/point, micro contract
RT_COMMISSION = 1.24                       # $ per micro round trip, matches orb1m.py


@dataclass
class SizedCard:
    symbol: str            # e.g. "MNQ"
    contract: str          # e.g. "MNQZ6"
    side: int               # 1 long, -1 short
    setup_grade: str        # "S" (only grade this engine emits -- frozen setup)
    time_et: str             # "09:47:00"
    entry: float
    stop: float
    target: float             # 2R
    contracts: dict          # {"Lucid 50K": 12, "Topstep 50K": 12}
    stop_level_desc: str     # "OR5 high retest wick (0.09%)"
    reason: str               # "[MNQ] ORB5 high 24,809.75 broken 09:41, displacement 1.4 ATR, ..."
    valid_until_et: str        # "09:49 open"
    cutoff_et: str = "10:30"
    signal_id: str = ""


def build_card(c: SizedCard) -> dict:
    direction = "LONG" if c.side > 0 else "SHORT"
    arrow = "↑" if c.side > 0 else "↓"
    pv = POINT_VALUE.get(c.symbol, 2.0)
    dist = abs(c.entry - c.stop)
    max_loss = -(dist * pv + RT_COMMISSION)
    max_reward = abs(c.target - c.entry) * pv - RT_COMMISSION

    title = f"\U0001F680 {c.symbol} {arrow} {direction} · {c.setup_grade} · {PAPER_LABEL}"

    contracts_line = "Contracts: " + " · ".join(f"{k} {v}" for k, v in c.contracts.items())
    body_lines = [
        f"Setup: ORB5 break+disp+retest | Grade: {c.setup_grade} | Time: {c.time_et} ET",
        contracts_line,
        f"Entry: {c.entry:,.2f} (next-bar open) | Stop: {c.stop:,.2f} ({dist:.2f} pt) | "
        f"Target (2R): {c.target:,.2f}",
        f"Stop level: {c.stop_level_desc}",
        f"Max Loss / Reward: -${abs(max_loss):,.0f} / +${max_reward:,.0f} (net {RT_COMMISSION:.2f} RT)",
        f"TRADE · {c.reason}",
        f"Valid until: {c.valid_until_et} · Cutoff {c.cutoff_et} flat · 1 trade/day",
        f"Omen Signal Bot · Grade {c.setup_grade} · {PAPER_LABEL} · #{c.signal_id}",
    ]
    body = "\n".join(body_lines)
    return {
        "title": title,
        "body": body,
        "priority": "high",
        "tags": ["rocket", "green_circle"] if c.side > 0 else ["rocket", "red_circle"],
    }
