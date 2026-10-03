"""Tests for the E9 forward clock. Offline: real archived 2026-09-25 bars stand in for Yahoo."""
import datetime as dt
import hashlib
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import forward_clock as fc  # noqa: E402

ET = fc.ET


@pytest.fixture(autouse=True)
def _isolated_log(tmp_path, monkeypatch):
    """Tests must never write into the real forward-clock.log."""
    monkeypatch.setattr(fc, "LOG_PATH", tmp_path / "test.log")


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


def test_all_four_frozen_files_pinned_and_backups_match():
    assert fc.assert_pins() == fc.FROZEN_SHA256
    assert len(fc.PINS) == 4
    for path, want in fc.PINS.items():
        assert fc.engine_sha(fc.BACKUP_DIR / path.name) == want, path.name


def test_pin_drift_in_any_file_refuses(tmp_path):
    a, b = tmp_path / "a.py", tmp_path / "b.py"
    a.write_bytes(b"x = 1\r\n")                                   # CRLF on disk
    b.write_bytes(b"y = 2\n")
    pa = hashlib.sha256(b"x = 1\n").hexdigest()                    # LF in the pin: must still match
    pb = hashlib.sha256(b"y = 2\n").hexdigest()
    fc.assert_pins({a: pa, b: pb})
    b.write_bytes(b"y = 3\n")
    with pytest.raises(fc.EngineDriftError) as e:
        fc.assert_pins({a: pa, b: pb})
    assert "b.py" in str(e.value) and "a.py:" not in str(e.value)
    b.unlink()
    with pytest.raises(fc.EngineDriftError):
        fc.assert_pins({a: pa, b: pb})


def test_replay_matches_frozen_engine_on_known_day():
    d = dt.date(2026, 9, 25)           # engine signal: short at minute 57 (checked against Yahoo 10-03)
    orb1m, pr = fc.load_engine()
    row = fc.replay_session(archived_bars(d), d, orb1m, pr, fc.FROZEN_SHA256)
    assert row["signal"] == "Y" and row["side"] == "short" and row["data_ok"] == "OK"
    A = orb1m.day_arrays(archived_bars(d))
    assert orb1m.signal(A, 5, 60, 1.0, "strong")[0] == 57
    assert row["entry_min"] == 570 + 57
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
    assert (n < fc.MIN_BARS) == row["data_ok"].startswith("DEGRADED")


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
    base = dict(data_ok="OK", side="", entry_min="", entry="", exit="", exit_reason="", gross_R="", bars_0930_1030=61,
                engine_sha12="x", source="s", signal_match="", logged_at_utc="t")
    return [dict(base, date="2026-10-05", signal="Y", net_R="1.9", gross_R="2.0"),
            dict(base, date="2026-10-06", signal="N", net_R=""),
            dict(base, date="2026-10-07", signal="Y", net_R="-1.03", gross_R="-1.0")]


def test_weekly_line_numbers():
    line = fc.weekly_line(_rows(), dt.date(2026, 10, 5))
    assert "3/4 sessions" in line and "2 signals" in line and "+0.87R" in line and "data_ok 3/3" in line
    assert "parity" not in line and "signal match 0/0" in line


def test_weekly_line_reports_signal_match():
    rows = _rows()
    rows[0]["signal_match"], rows[1]["signal_match"], rows[2]["signal_match"] = "Y", "Y", "N"
    assert "signal match 2/3 (67%, gate 95%)" in fc.weekly_line(rows, dt.date(2026, 10, 5))


def test_weekly_push_once_per_week_on_thursday(tmp_path):
    sent = []
    st = tmp_path / "state.json"
    thu = dt.datetime(2026, 10, 8, 17, 15, tzinfo=ET)
    tue = dt.datetime(2026, 10, 6, 17, 15, tzinfo=ET)
    # Tuesday: this week not due; previous week (START week) is due as a catch-up and is pushed once
    assert len(fc.maybe_weekly_push(tue, _rows(), False, pusher=lambda t: sent.append(t) or True, state_path=st)) == 1
    assert len(fc.maybe_weekly_push(thu, _rows(), False, pusher=lambda t: sent.append(t) or True, state_path=st)) == 1
    assert fc.maybe_weekly_push(thu, _rows(), False, pusher=lambda t: sent.append(t) or True, state_path=st) == []
    assert len(sent) == 2
    sat = dt.datetime(2026, 10, 10, 12, 0, tzinfo=ET)
    assert fc.maybe_weekly_push(sat, _rows(), False, pusher=lambda t: sent.append(t) or True, state_path=st) == []


def test_missed_week_is_pushed_on_next_run_any_weekday(tmp_path):
    sent = []
    st = tmp_path / "state.json"
    st.write_text('{"pushed_weeks": ["2026-09-28"]}')           # START week already sent
    mon = dt.datetime(2026, 10, 12, 17, 15, tzinfo=ET)          # Thu+Fri of the 10-05 week were both missed
    out = fc.maybe_weekly_push(mon, _rows(), False, pusher=lambda t: sent.append(t) or True, state_path=st)
    assert len(out) == 1 and "wk41" in sent[0]                  # previous ISO week (10-05..10-11) is ISO week 41
    assert fc.maybe_weekly_push(mon, _rows(), False, pusher=lambda t: sent.append(t) or True, state_path=st) == []
    assert len(sent) == 1


def test_no_catch_up_for_weeks_before_start(tmp_path):
    thu = dt.datetime(2026, 10, 1, 17, 15, tzinfo=ET)           # Thursday of the START week; previous week is pre-start
    sent = []
    fc.maybe_weekly_push(thu, _rows(), False, pusher=lambda t: sent.append(t) or True, state_path=tmp_path / "s.json")
    assert len(sent) == 1 and "wk40" in sent[0]


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
    row.update(date="2026-10-01", signal="N", data_ok="OK")
    fc.append_row(row, p)
    assert [r["date"] for r in fc.read_rows(p)] == ["2026-10-01"]


def test_migrate_v1_csv_renames_parity(tmp_path):
    p = tmp_path / "f.csv"
    p.write_text("date,signal,side,entry,exit,exit_reason,gross_R,net_R,parity,bars_0930_1030,engine_sha12,source,logged_at_utc\n"
                 "2026-10-01,N,,,,,,,OK,61,bafd7ce4e4f6,yahoo NQ=F 1m,2026-10-03T10:01:50+00:00\n", encoding="utf-8")
    assert fc.migrate_csv(p) is True
    assert p.read_text(encoding="utf-8").splitlines()[0].split(",") == fc.COLS
    r = fc.read_rows(p)[0]
    assert r["data_ok"] == "OK" and r["bars_0930_1030"] == "61" and r["signal_match"] == "" and r["entry_min"] == ""
    assert fc.migrate_csv(p) is False


def test_match_flag_rules():
    y = dict(signal="Y", side="short", entry_min=627)
    n = dict(signal="N", side="", entry_min="")
    assert fc.match_flag(y, dict(signal="Y", side="short", entry_min=627)) == "Y"
    assert fc.match_flag(n, dict(signal="N", side="", entry_min="")) == "Y"
    assert fc.match_flag(y, dict(signal="Y", side="long", entry_min=627)) == "N"
    assert fc.match_flag(y, dict(signal="Y", side="short", entry_min=628)) == "N"
    assert fc.match_flag(y, dict(signal="N", side="", entry_min="")) == "N"
    assert fc.match_flag(n, dict(signal="Y", side="short", entry_min=627)) == "N"
    assert fc.match_flag(y, None) == ""


def test_signal_match_backfill_from_archive_on_known_day():
    d = dt.date(2026, 9, 25)
    orb1m, pr = fc.load_engine()
    arch = archived_bars(d)
    full = fc.load_archive_bars()                                          # what the real loader returns (has a date column)
    full = full[full["date"] == d]
    logged = fc.replay_session(arch, d, orb1m, pr, fc.FROZEN_SHA256)      # stand-in for the Yahoo replay of the same day
    other = dict(logged, date="2026-12-31", signal_match="")              # a date the archive does not cover
    done = dict(logged, date="2026-09-24", signal_match="Y")
    rows = [dict(logged, signal_match=""), other, done]
    n = fc.fill_signal_match(rows, orb1m, pr, fc.FROZEN_SHA256, archive_loader=lambda: full)
    assert n == 1 and rows[0]["signal_match"] == "Y" and rows[1]["signal_match"] == "" and rows[2]["signal_match"] == "Y"
    bad = dict(logged, side="long", signal_match="")
    assert fc.fill_signal_match([bad], orb1m, pr, fc.FROZEN_SHA256, archive_loader=lambda: full) == 1
    assert bad["signal_match"] == "N"


def test_archive_unreadable_never_raises():
    def boom():
        raise FileNotFoundError("x")
    orb1m, pr = fc.load_engine()
    assert fc.fill_signal_match([dict(_rows()[0])], orb1m, pr, fc.FROZEN_SHA256, archive_loader=boom) == 0


def test_band_text_only_after_goal_sessions():
    assert fc.band_text(_rows()) == ""
    rows = [dict(_rows()[0], date=f"2026-11-{i:02d}", signal="Y", net_R="0.1") for i in range(1, 18)]
    t = fc.band_text(rows)
    assert "INSIDE" in t and f"{fc.BAND_LO:+.2f}" in t
    rows[0]["net_R"] = "50"
    assert "OUTSIDE" in fc.band_text(rows)
