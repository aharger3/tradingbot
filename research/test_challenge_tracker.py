"""Tests for challenge_tracker.py -- synthetic P&L only, stdlib only.

    python -m pytest research/test_challenge_tracker.py -q
    python research/test_challenge_tracker.py

Five-day fixture (LucidFlex 50K, $2K EOD trail locking at start + $100, u06):
  day  pnl       balance    HWM        floor      locked
  1    +800.50   50,800.50  50,800.50  48,800.50  -
  2  +1,000.25   51,800.75  51,800.75  49,800.75  -
  3    -300.10   51,500.65  51,800.75  49,800.75  -
  4    +450.35   51,951.00  51,951.00  49,951.00  -
  5    +200.00   52,151.00  52,151.00  50,100.00  Y  (52,151 - 2,000 = 50,151 capped at 50,100)
"""
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import challenge_tracker as ct  # noqa: E402

FIXTURE = [("2026-09-14", 800.50), ("2026-09-15", 1000.25), ("2026-09-16", -300.10),
           ("2026-09-17", 450.35), ("2026-09-21", 200.00)]
EXPECT = [  # balance, HWM, floor, locked
    (50800.50, 50800.50, 48800.50, False),
    (51800.75, 51800.75, 49800.75, False),
    (51500.65, 51800.75, 49800.75, False),
    (51951.00, 51951.00, 49951.00, False),
    (52151.00, 52151.00, 50100.00, True),
]


def _tmp(name="challenge.jsonl") -> Path:
    return Path(tempfile.mkdtemp()) / name


def test_five_day_floor_and_lock_to_the_cent():
    p = _tmp()
    for (d, pnl), (bal, hw, fl, lk) in zip(FIXTURE, EXPECT):
        r = ct.record("L1", d, pnl, path=p)
        assert (r["balance"], r["high_water"], r["floor"], r["locked"]) == (bal, hw, fl, lk), r
        assert r["status"] == "active"
    assert r["profit_days_150"] == 4          # -300.10 is the only non-qualifying day
    assert r["to_target"] == 849.00
    assert r["session_n"] == 5 and r["sessions_median"] == 43
    assert r["start_date"] == "2026-09-14"
    assert (r["failed_evals"], r["spent"], r["kill_budget"]) == (0, 146.0, 438.0)
    assert len(ct.load_rows(p)) == 5


def test_floor_never_drops_after_lock():
    p = _tmp()
    for d, pnl in FIXTURE:
        ct.record("L1", d, pnl, path=p)
    r = ct.record("L1", "2026-09-22", -2000.00, path=p)   # 50,151.00 > locked floor 50,100
    assert (r["balance"], r["floor"], r["status"]) == (50151.00, 50100.00, "active")
    r = ct.record("L1", "2026-09-23", -51.00, path=p)     # 50,100.00 touches floor -> fail
    assert r["status"] == "failed" and r["failed_evals"] == 1


def test_breach_uses_prior_floor_and_intraday_min():
    assert ct.step(None, "A", "2026-09-14", -1999.99)["status"] == "active"
    assert ct.step(None, "A", "2026-09-14", -2000.00)["status"] == "failed"
    r = ct.step(None, "A", "2026-09-14", +100.00, min_equity=47999.99)
    assert r["status"] == "failed"


def test_pass_at_target():
    r = ct.step(None, "A", "2026-09-14", 3000.00)
    assert (r["status"], r["to_target"]) == ("passed", 0.0)
    try:
        ct.step(r, "A", "2026-09-15", 10.0)
        assert False, "stepping a passed account must raise"
    except ValueError:
        pass


def test_kill_budget_after_three_fails():
    p = _tmp()
    for a in ("L1", "L2", "L3"):
        ct.record(a, "2026-09-14", -2500.00, path=p)
    rows = ct.load_rows(p)
    assert (rows[-1]["failed_evals"], rows[-1]["spent"]) == (3, 438.0)
    assert "KILL BUDGET HIT" in ct.status_table(p)


def test_ladder():
    assert [ct.contracts_for(x) for x in (0, 999.99, 1000, 1999.99, 2000, 5000)] == [12, 12, 10, 10, 6, 6]


def test_seed_paper_builds_paper_row_and_keeps_real():
    d = Path(tempfile.mkdtemp())
    paper = d / "acks_replay.jsonl"
    paper.write_text("\n".join(json.dumps(r) for r in [
        {"date": "2026-09-14", "confirmed": True, "usd": -48.24, "r": -1.0374},
        {"date": "2026-09-17", "confirmed": True, "usd": 90.00, "r": 1.95},
        {"date": "2026-09-17", "confirmed": False, "reason": "late_tap"},
    ]) + "\n")
    j = d / "challenge.jsonl"
    ct.record("REAL-1", "2026-09-14", 10.0, path=j)
    ct.seed_paper([paper], path=j)
    ct.seed_paper([paper], path=j)                     # idempotent: replaces PAPER rows
    rows = ct.load_rows(j)
    paper_rows = [r for r in rows if r["tag"] == "PAPER"]
    assert [r["date"] for r in paper_rows] == ["2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17"]
    assert [r["pnl"] for r in paper_rows] == [-578.88, 0.0, 0.0, 1080.00]   # 12 MNQ each day
    last = paper_rows[-1]
    assert (last["balance"], last["floor"], last["session_n"]) == (50501.12, 48501.12, 4)
    assert last["account"] == ct.PAPER_ACCOUNT and last["plan"] == "LucidFlex 50K"
    assert sum(1 for r in rows if r["tag"] == "REAL") == 1
    table = ct.status_table(j)
    assert "PAPER" in table and "REAL-1" in table
    assert ct.status_line(j).startswith("Challenge: ")


def test_status_line_never_raises():
    assert ct.status_line(_tmp()) == "Challenge: no rows"
    bad = _tmp()
    bad.write_text("{not json\n")
    assert ct.status_line(bad).startswith("Challenge: n/a")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"{len(fns)} passed")
