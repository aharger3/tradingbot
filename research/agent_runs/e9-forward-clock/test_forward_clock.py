"""Tests for the E9 forward clock. Offline: real archived 2026-09-25 bars stand in for Yahoo."""
import datetime as dt
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import forward_clock as fc  # noqa: E402

ET = fc.ET


def archived_bars(day):
    orb1m, _ = fc.load_engine()
    from omen_data import load_fut
    m = load_fut("MNQ", "09:30", "11:01")
    return m[m["date"] == day][["ts", "open", "high", "low", "close"]].reset_index(drop=True)


def test_engine_hash_is_frozen_value():
    assert fc.assert_frozen() == fc.FROZEN_SHA256


def test_drift_refuses(tmp_path):
    p = tmp_path / "orb1m.py"
    p.write_bytes(b"changed")
    with pytest.raises(fc.EngineDriftError):
        fc.assert_frozen(p)


def test_replay_matches_frozen_engine_on_known_day():
    d = dt.date(2026, 9, 25)           # engine signal: short at minute 57 (checked against Yahoo 10-03)
    orb1m, pr = fc.load_engine()
    row = fc.replay_session(archived_bars(d), d, orb1m, pr, fc.FROZEN_SHA256)
    assert row["signal"] == "Y" and row["side"] == "short" and row["parity"] == "OK"
    A = orb1m.day_arrays(archived_bars(d))
    assert orb1m.signal(A, 5, 60, 1.0, "strong")[0] == 57
    assert float(row["net_R"]) < float(row["gross_R"])        # commission is charged


def test_holiday_or_thin_session_is_not_a_row():
    d = dt.date(2026, 9, 25)
    orb1m, pr = fc.load_engine()
    thin = archived_bars(d).iloc[:10]
    assert fc.replay_session(thin, d, orb1m, pr, fc.FROZEN_SHA256) is None


def test_degraded_when_bars_missing():
    d = dt.date(2026, 9, 25)
    orb1m, pr = fc.load_engine()
    b = archived_bars(d)
    keep = b[~((b["ts"].dt.minute % 5 == 3) & (b["ts"].dt.hour == 10))]    # drop a few minutes after the OR
    row = fc.replay_session(keep, d, orb1m, pr, fc.FROZEN_SHA256)
    n = row["bars_0930_1030"]
    assert (n < fc.MIN_BARS) == row["parity"].startswith("DEGRADED")


def test_due_dates_mon_thu_only_and_after_window():
    logged = {"2026-10-01"}
    now = dt.datetime(2026, 10, 6, 17, 15, tzinfo=ET)          # Tuesday evening
    due = fc.due_dates(now, logged)
    assert due == [dt.date(2026, 10, 5), dt.date(2026, 10, 6)]  # no Fri/Sat/Sun, Thursday already logged
    early = dt.datetime(2026, 10, 6, 9, 0, tzinfo=ET)
    assert fc.due_dates(early, logged) == [dt.date(2026, 10, 5)]  # Tuesday's window not finished


def test_start_date_floor():
    now = dt.datetime(2026, 10, 1, 17, 15, tzinfo=ET)
    assert fc.due_dates(now, set()) == [dt.date(2026, 10, 1)]


def _rows():
    base = dict(parity="OK", side="", entry="", exit="", exit_reason="", gross_R="", bars_0930_1030=61,
                engine_sha12="x", source="s", logged_at_utc="t")
    return [dict(base, date="2026-10-05", signal="Y", net_R="1.9", gross_R="2.0"),
            dict(base, date="2026-10-06", signal="N", net_R=""),
            dict(base, date="2026-10-07", signal="Y", net_R="-1.03", gross_R="-1.0")]


def test_weekly_line_numbers():
    line = fc.weekly_line(_rows(), dt.date(2026, 10, 5))
    assert "3/4 sessions" in line and "2 signals" in line and "+0.87R" in line and "parity 3/3" in line


def test_weekly_push_once_per_week_on_thursday(tmp_path):
    sent = []
    st = tmp_path / "state.json"
    thu = dt.datetime(2026, 10, 8, 17, 15, tzinfo=ET)
    tue = dt.datetime(2026, 10, 6, 17, 15, tzinfo=ET)
    assert fc.maybe_weekly_push(tue, _rows(), False, pusher=sent.append, state_path=st) is None
    assert fc.maybe_weekly_push(thu, _rows(), False, pusher=lambda t: sent.append(t) or True, state_path=st)
    assert fc.maybe_weekly_push(thu, _rows(), False, pusher=lambda t: sent.append(t) or True, state_path=st) is None
    assert len(sent) == 1
    sat = dt.datetime(2026, 10, 10, 12, 0, tzinfo=ET)
    assert fc.maybe_weekly_push(sat, _rows(), False, pusher=sent.append, state_path=tmp_path / "other.json") is None


def test_failed_push_retries(tmp_path):
    st = tmp_path / "state.json"
    thu = dt.datetime(2026, 10, 8, 17, 15, tzinfo=ET)
    fc.maybe_weekly_push(thu, _rows(), False, pusher=lambda t: False, state_path=st)
    assert not st.exists()
    fc.maybe_weekly_push(thu, _rows(), False, pusher=lambda t: True, state_path=st)
    assert st.exists()


def test_csv_roundtrip_and_no_duplicates(tmp_path):
    p = tmp_path / "f.csv"
    row = {c: "" for c in fc.COLS}
    row.update(date="2026-10-01", signal="N", parity="OK")
    fc.append_row(row, p)
    assert [r["date"] for r in fc.read_rows(p)] == ["2026-10-01"]
