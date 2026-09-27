"""prop_guard.py -- prop-firm rule compliance guard for the eye loop. PAPER ONLY.

`check(account, today) -> Verdict(ok, reason)` answers one question before a
card goes out: "would taking one more trade today break the firm's rules?"

Rules (LucidFlex 50K, from life-plan u06 / g/sizing-mc, k/mentor-sizing-rules,
OMEN-SHIP-PLAN), evaluated in this order, first failure wins:
  1. trail        EOD $2K trailing drawdown; the floor stops rising once it
                  reaches start + $100. Balance at/below floor -> BLOCK.
  2. loss_stop    2 losing trades today -> BLOCK (mentor day stop).
  3. trade_cap    confirmed trades today >= max_trades_per_day (ship plan: 1).
  4. consistency  eval only: today's profit may not exceed 50% of the profit
                  target. Room = 0.5 x target - banked today; room <= 0 -> BLOCK.
  5. micro_cap    next trade's ladder size (12/10/6 MNQ) > 40 micros -> BLOCK.

Input: journal rows from research/paper_journal/acks_replay.jsonl (eye_paper
schema: date, ts, r, usd per 1 contract) and an account entry from
config/accounts.json. Account dollars = row["usd"] x contracts, where contracts
= row["contracts"] if present else the ladder size at that point.

Lucid rules are aggregator-sourced (u06), not live-checked. Never places orders.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

REPO = Path(__file__).resolve().parents[1]
ACCOUNTS_PATH = REPO / "config" / "accounts.json"


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason: str


def load_account(name: str = "lucidflex_50k_paper", path: Path = ACCOUNTS_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))[name]


def load_rows(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if r.get("confirmed", True) and "r" in r and r.get("date")]


def ladder_size(account: dict, profit: float) -> int:
    size = account["ladder"][0][1]
    for threshold, contracts in account["ladder"]:
        if profit >= threshold:
            size = contracts
    return int(size)


def check(account: dict, today: str, rows: Optional[Iterable[dict]] = None,
          since: Optional[str] = None) -> Verdict:
    """`rows` default = the account's journal file. `since` (ISO ts) drops
    today-dated rows written before it, so a re-run replay of the same date
    starts clean instead of inheriting an earlier run's trades."""
    if rows is None:
        rows = load_rows(REPO / account["journal"])
    rows = [r for r in rows if r["date"] <= today]
    if since:  # compare as datetimes: journal ts is UTC, runner start is ET
        t0 = datetime.fromisoformat(since)
        rows = [r for r in rows if r["date"] < today
                or (r.get("ts") and datetime.fromisoformat(r["ts"]) >= t0)]
    rows.sort(key=lambda r: (r["date"], str(r.get("ts", ""))))

    start = float(account["start_balance"])
    balance, hwm = start, start
    today_pnl, today_trades, today_losses = 0.0, 0, 0
    prev_date = None
    for r in rows:
        if prev_date is not None and r["date"] != prev_date and prev_date < today:
            hwm = max(hwm, balance)  # EOD mark for the finished day
        contracts = int(r.get("contracts") or ladder_size(account, balance - start))
        pnl = float(r.get("usd", 0.0)) * contracts
        balance += pnl
        if r["date"] == today:
            today_pnl += pnl
            today_trades += 1
            today_losses += 1 if float(r["r"]) < 0 else 0
        prev_date = r["date"]
    if prev_date is not None and prev_date < today:
        hwm = max(hwm, balance)

    floor = min(hwm - float(account["eod_trail"]), start + float(account["trail_lock_profit"]))
    if balance <= floor:
        return Verdict(False, f"trail breached: balance ${balance:,.0f} <= floor ${floor:,.0f}")
    if today_losses >= int(account["max_losses_per_day"]):
        return Verdict(False, f"{today_losses}-loss day stop")
    if today_trades >= int(account["max_trades_per_day"]):
        return Verdict(False, f"trade cap: {today_trades}/{account['max_trades_per_day']} confirmed today")
    if account.get("phase") == "eval":
        room = float(account["consistency_cap"]) * float(account["profit_target"]) - today_pnl
        if room <= 0:
            return Verdict(False, f"consistency: today +${today_pnl:,.0f} >= "
                                  f"{account['consistency_cap']:.0%} of ${account['profit_target']:,.0f} target")
    size = ladder_size(account, balance - start)
    if size > int(account["max_micros"]):
        return Verdict(False, f"micro cap: {size} > {account['max_micros']} micros")
    return Verdict(True, f"GUARD OK ({size} MNQ, cushion ${balance - floor:,.0f})")


class CardGate:
    """The one call eye_runner makes before send_card. allow() returns the
    card footer ("GUARD OK") or None when the card must be suppressed; on
    BLOCK it sends one 'GUARD: <reason>' line per distinct reason per run."""

    def __init__(self, account: dict, today: str, journal_path: Path,
                 notify: Callable[[str], object], since: Optional[str] = None):
        self.account, self.today, self.journal_path = account, today, Path(journal_path)
        self.notify, self.since = notify, since
        self._told: set[str] = set()
        self.last: Optional[Verdict] = None

    def allow(self) -> Optional[str]:
        v = self.last = check(self.account, self.today, load_rows(self.journal_path), since=self.since)
        if v.ok:
            return "GUARD OK"
        if v.reason not in self._told:
            self._told.add(v.reason)
            self.notify(f"GUARD: {v.reason}")
        return None
