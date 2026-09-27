"""prop_guard: one fixture per LucidFlex rule + one clean day. PAPER ONLY,
no network (ntfy is a list-append stub).

Run:  pytest research/tests/test_prop_guard.py  (from repo root)
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "research"))

import prop_guard  # noqa: E402

TODAY = "2026-09-07"


@pytest.fixture
def account():
    return prop_guard.load_account("lucidflex_50k_paper", REPO / "config" / "accounts.json")


def row(date, r, usd, ts="09:45", contracts=None):
    out = {"date": date, "ts": f"{date}T{ts}:00-04:00", "confirmed": True, "r": r, "usd": usd}
    if contracts:
        out["contracts"] = contracts
    return out


def test_clean_day(account):
    rows = [row("2026-09-03", 1.9, 80.0)]  # prior winner, nothing today
    v = prop_guard.check(account, TODAY, rows)
    assert v.ok and v.reason.startswith("GUARD OK")


def test_trail_blocks_and_locks_at_plus_100(account):
    # +$2,400 banked (hwm 52,400): the floor locks at 50,100, not 50,400.
    rows = [row("2026-09-01", 2.0, 200.0, contracts=12)]
    assert prop_guard.check(account, TODAY, rows).ok
    rows.append(row("2026-09-02", -3.0, -230.0, contracts=10))  # 52,400 - 2,300 = 50,100
    v = prop_guard.check(account, TODAY, rows)
    assert not v.ok and v.reason.startswith("trail breached") and "$50,100" in v.reason


def test_two_loss_day_stop_suppresses_third_card(account, tmp_path):
    account = {**account, "max_trades_per_day": 5}  # isolate the loss rule (prereg allows 5/day)
    journal = tmp_path / "acks_replay.jsonl"
    sent, lines = [], []
    gate = prop_guard.CardGate(account, TODAY, journal, notify=lines.append)
    for i, ts in enumerate(["09:41", "09:55", "10:10"]):
        footer = gate.allow()
        if footer is None:
            continue
        sent.append((i, footer))
        with open(journal, "a") as fh:  # each sent card gets tapped S and stops out
            fh.write(json.dumps(row(TODAY, -1.0, -20.0, ts=ts)) + "\n")
    assert sent == [(0, "GUARD OK"), (1, "GUARD OK")]
    assert lines == ["GUARD: 2-loss day stop"]


def test_one_trade_per_day(account):
    v = prop_guard.check(account, TODAY, [row(TODAY, 1.0, 40.0)])
    assert not v.ok and v.reason.startswith("trade cap: 1/1")


def test_consistency_cap(account):
    account = {**account, "max_trades_per_day": 5}
    rows = [row(TODAY, 2.0, 130.0)]  # 12 MNQ x $130 = +$1,560 >= 0.5 x $3,000
    v = prop_guard.check(account, TODAY, rows)
    assert not v.ok and v.reason.startswith("consistency")


def test_micro_cap(account):
    account = {**account, "ladder": [[0, 50]]}
    v = prop_guard.check(account, TODAY, [])
    assert not v.ok and v.reason == "micro cap: 50 > 40 micros"
