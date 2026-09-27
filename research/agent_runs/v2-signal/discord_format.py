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


# Grade drives color/priority in the example card (message 1550153955668004945,
# #signals 2026-09-17: S = green 3066993), not trade direction.
GRADE_PRIORITY = {"S": "urgent", "A": "high", "C": "default", "X": "low"}
GRADE_TAG = {"S": "green_circle", "A": "large_blue_circle", "C": "yellow_circle", "X": "red_circle"}
TV_SYMBOL = {"MNQ": "CME_MINI:MNQ1!", "MES": "CME_MINI:MES1!"}


def build_card(c: SizedCard) -> dict:
    """Field order = example card: title | Setup/Grade/Time | Expiration(contract)/
    Contracts | Entry/Stop/Target (xR) | Stop level | Max Loss / Reward | Reason |
    (Stock ref slot -> Valid until) | footer. Max Loss / Reward is the POSITION
    total (example: 50 cons -> -$1000 / +$1600), net of round-trip fees."""
    direction = "LONG" if c.side > 0 else "SHORT"
    arrow = "↑" if c.side > 0 else "↓"
    pv = POINT_VALUE.get(c.symbol, 2.0)
    dist = abs(c.entry - c.stop)
    reward_pts = abs(c.target - c.entry)
    r_mult = reward_pts / dist if dist else float("nan")
    r_label = f"{r_mult:g}R" if r_mult == r_mult else "?R"

    def _money(n: int) -> str:
        loss = n * (dist * pv + RT_COMMISSION)
        reward = n * (reward_pts * pv - RT_COMMISSION)
        return f"-${loss:,.0f} / +${reward:,.0f}"

    counts = sorted(set(c.contracts.values()))
    if len(counts) == 1:
        money = f"{_money(counts[0])} ({counts[0]} cons, net {RT_COMMISSION:.2f} RT)"
    else:
        money = " · ".join(f"{k} {_money(v)}" for k, v in c.contracts.items()) + \
            f" (net {RT_COMMISSION:.2f} RT)"

    title = f"\U0001F680 {c.symbol} {arrow} {direction} · {c.setup_grade} · {PAPER_LABEL}"

    contracts_line = f"Contract: {c.contract} | Contracts: " + \
        " · ".join(f"{k} {v}" for k, v in c.contracts.items())
    body_lines = [
        f"Setup: ORB5 break+disp+retest | Grade: {c.setup_grade} | Time: {c.time_et} ET",
        contracts_line,
        f"Entry: {c.entry:,.2f} (next-bar open) | Stop: {c.stop:,.2f} ({dist:.2f} pt) | "
        f"Target ({r_label}): {c.target:,.2f}",
        f"Stop level: {c.stop_level_desc}",
        f"Max Loss / Reward: {money}",
        f"TRADE · {c.reason}",
        f"Valid until: {c.valid_until_et} · Cutoff {c.cutoff_et} flat · 1 trade/day",
        f"Omen Signal Bot · Grade {c.setup_grade} · {PAPER_LABEL} · #{c.signal_id}",
    ]
    body = "\n".join(body_lines)
    tv = TV_SYMBOL.get(c.symbol, f"CME_MINI:{c.symbol}1!")
    return {
        "title": title,
        "body": body,
        "priority": GRADE_PRIORITY.get(c.setup_grade, "default"),
        "tags": ["rocket", GRADE_TAG.get(c.setup_grade, "white_circle")],
        "click": f"https://www.tradingview.com/chart/?symbol={tv}",
    }
