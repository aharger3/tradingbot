import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import dollar_ledger as DL  # noqa: E402

FIX = json.loads((HERE / "fixtures" / "zarattini_nq925_book.json").read_text())


def test_u07_contracts():
    assert DL.contracts(30.0) == 3          # 200 / (60 + 2.25) = 3.2
    assert DL.contracts(15.0) == 6          # u07 table: 15 pt MNQ -> 6
    assert DL.contracts(50.0) == 1
    assert DL.contracts(99.0) == 0          # 1 lot risks $200.25 > $200
    assert DL.contracts(0.25) == 50         # capped


def test_skip_and_log_wide_stop():
    L = DL.ledger([dict(id="w", date="2026-09-17", stop_pt=120.0, pts=10.0)])
    assert L["trades"] == 0 and L["skipped"][0]["id"] == "w" and "242.25" in L["skipped"][0]["reason"]


def test_cum_and_max_drawdown():
    t = [dict(date=f"d{i}", stop_pt=40.0, pts=p) for i, p in enumerate((20.0, -40.0, -40.0, 60.0))]
    L = DL.ledger(t, rt_comm=1.0)           # n = floor(200 / 82.25) = 2
    assert [r["usd"] for r in L["rows"]] == [78.0, -162.0, -162.0, 238.0]
    assert L["usd_total"] == -8.0 and L["max_dd_usd"] == -324.0


def test_reproduces_zarattini_robust_mnq_book():
    """robust.json 'NQ925 s1 c1x': 222 trades, 39 skipped wide, $35.1/day over 495 sessions,
    $78.2/trade, median 1 MNQ; worst EOD DD -$2,891 (prop section). Sizing there uses bt.COMM
    ($1.24) as the cost term, so size_cost=1.24 here."""
    e = FIX["expect"]
    trades = [dict(date=d, stop_pt=dist, pts=pts) for d, dist, pts in FIX["trades"]]
    L = DL.ledger(trades, sessions=FIX["sessions"], budget=e["budget"], size_cost=e["cost"],
                  rt_comm=e["cost"], max_n=e["max_n"])
    assert (L["trades"], len(L["skipped"])) == (e["trades"], e["skipped_wide"])
    assert L["usd_day"] == e["usd_day"] and L["usd_trade"] == e["usd_trade"]
    assert L["med_contracts"] == e["med_contracts"]
    assert round(L["max_dd_usd"]) == e["worst_eod_dd"]


def test_journal_row_roundtrip(tmp_path):
    # the committed replay row (acks_replay.jsonl): MNQ short, 23.25 pt stop, 1-lot usd -48.24
    row = {"id": "O11-1-20260917", "symbol": "MNQ", "date": "2026-09-17", "side": -1, "confirmed": True,
           "entry": 29619.25, "stop": 29642.5, "r": -1.0374, "usd": -48.24}
    es = dict(row, id="es", symbol="MES")
    p = tmp_path / "acks.jsonl"
    p.write_text(json.dumps(row) + "\n" + json.dumps(es) + "\n")
    trades, bad = DL.journal_trades(p)
    assert [b["id"] for b in bad] == ["es"]
    L = DL.ledger(trades)
    assert L["rows"][0]["n"] == 4 and L["usd_total"] == -192.96   # floor(200 / 48.75) = 4 x -48.24
