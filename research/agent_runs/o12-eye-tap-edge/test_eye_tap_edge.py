"""Tests for eye_tap_edge. Synthetic bars only: no network, no omen_data, no real taps.
Run: python -m pytest research/agent_runs/o12-eye-tap-edge/test_eye_tap_edge.py -q
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eye_tap_edge as E  # noqa: E402


def arrays(n=91):
    nan = np.full(n, np.nan)
    return {k: nan.copy() for k in ("open", "high", "low", "close")}


def bar(A, j, o, h, l, c):
    A["open"][j], A["high"][j], A["low"][j], A["close"][j] = o, h, l, c


def short_setup():
    """Decision bar 10; entry bar 11 opens 100 -> short entry 99.75, stop 101 (dist 1.25), target 97.25."""
    A = arrays()
    for j in range(0, 91):
        bar(A, j, 100.0, 100.4, 99.6, 100.0)
    return A


# ------------------------------------------------------------------ fills
def test_winner_hits_2r_exactly():
    A = short_setup()
    bar(A, 12, 100.0, 100.2, 97.0, 97.5)           # low <= tgt - tick -> target fills
    r = E.score_fill(A, 10, -1, 101.0)
    assert r == pytest.approx((2.5 * 2 - 1.24) / 2.5, abs=1e-9)   # +1.504R after $1.24 RT


def test_stop_loses_with_gap_slippage():
    A = short_setup()
    bar(A, 12, 100.0, 101.5, 99.9, 101.0)           # high >= stop; exit = max(stop, open)+tick = 101.25
    r = E.score_fill(A, 10, -1, 101.0)
    assert r == pytest.approx((-1.5 * 2 - 1.24) / 2.5, abs=1e-9)


def test_same_bar_stop_wins():
    A = short_setup()
    bar(A, 12, 100.0, 101.5, 97.0, 99.0)            # touches both stop and target in one bar
    assert E.score_fill(A, 10, -1, 101.0) < 0


def test_entry_is_bar_after_decision_bar():
    A = short_setup()
    bar(A, 10, 100.0, 101.5, 90.0, 95.0)            # the decision bar itself must be ignored
    bar(A, 11, 100.0, 100.2, 99.0, 99.5)
    bar(A, 12, 100.0, 100.2, 97.0, 97.5)
    assert E.score_fill(A, 10, -1, 101.0) > 1.0


def test_degenerate_stop_and_missing_entry_bar_return_none():
    A = short_setup()
    assert E.score_fill(A, 10, -1, 99.9) is None    # < 2 ticks from entry
    A2 = short_setup()
    A2["open"][11] = np.nan
    assert E.score_fill(A2, 10, -1, 101.0) is None
    assert E.score_fill(short_setup(), 90, -1, 101.0) is None   # no bar 91


def test_cut_changes_exit():
    A = short_setup()
    bar(A, 70, 100.0, 100.2, 97.0, 97.5)            # target only hit at minute 70
    assert E.score_fill(A, 10, -1, 101.0, cut=60) < 0.5     # flat at 10:30 before it
    assert E.score_fill(A, 10, -1, 101.0, cut=90) > 1.0     # 11:00 cutoff sees it


def test_orb1m_is_the_frozen_tracked_copy():
    assert E.ORB1M_PATH.name == "orb1m.py" and E.ORB1M_PATH.exists()
    assert len(E.orb1m_sha256()) == 64
    assert E.load_orb1m().CUTS["11:00"] == E.CUT_PREREG and E.CUT_LOOP == 60


# ------------------------------------------------------------------ parsing / classification
def utc(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_parse_candidate_id():
    assert E.parse_candidate_id("S43-1-20260907") == dict(grade="S", minute=43, seq=1, date="2026-09-07")
    assert E.parse_candidate_id("O11-1-20260917")["minute"] == 11
    assert E.parse_candidate_id("garbage") is None and E.parse_candidate_id("") is None


def tap(cid, label, when, ip="100.64.0.9"):
    return dict(candidate_id=cid, label=label, logged_at=utc(when), source_ip=ip, mode="PAPER")


def test_classification_kinds():
    sent = {"S43-1-20260907": [utc("2026-09-28T14:11:00"), utc("2026-10-02T15:58:00")],
            "S20-1-20150302": [utc("2026-09-29T13:50:00")]}
    taps = [
        tap("O11-1-20260917", "S", "2026-09-27T04:00:08", ip="127.0.0.1"),        # agent curl
        tap("S43-1-20260907", "S", "2026-09-28T14:11:40"),                        # first send, in live-watch window
        tap("S43-1-20260907", "notS", "2026-09-28T14:11:50"),                     # second tap, same card
        tap("S43-1-20260907", "S", "2026-10-02T15:58:30"),                        # card sent a 2nd time
        tap("S20-1-20150302", "notS", "2026-09-29T13:50:20"),                     # old never-seen date
    ]
    k = [t["kind"] for t in E.classify_taps(taps, sent)]
    assert k == ["test", "remembered", "repeat", "repeat", "blind"]


def test_test_tap_does_not_make_next_real_tap_a_repeat():
    sent = {"S43-1-20260907": [utc("2026-09-28T14:11:00")]}
    taps = [tap("S43-1-20260907", "S", "2026-09-27T04:00:08", ip="::1"),
            tap("S43-1-20260907", "S", "2026-09-28T14:11:40")]
    assert [t["kind"] for t in E.classify_taps(taps, sent)] == ["test", "remembered"]


def test_window_a_is_reserved():
    assert E.in_window_a("2019-09-26") and E.in_window_a("2024-09-25")
    assert not E.in_window_a("2019-09-25") and not E.in_window_a("2024-09-26")


def test_read_sent_log_and_taps(tmp_path):
    log = tmp_path / "l.log"
    log.write_text("[2026-09-28T10:11:15-04:00] sent S43-1-20260907 grade=S dir=SHORT\n"
                   "[2026-09-28T10:13:17-04:00] expire S43-1-20260907: no S tap\n", encoding="utf-8")
    sent = E.read_sent_log(log, tmp_path / "missing.log")
    assert list(sent) == ["S43-1-20260907"] and len(sent["S43-1-20260907"]) == 1
    csvp = tmp_path / "labels.csv"
    csvp.write_text("logged_at,candidate_id,label,mode,source_ip\n"
                    "2026-09-27T04:00:08+00:00,O11-1-20260917,S,PAPER,127.0.0.1\n"
                    "2026-09-27T03:00:00+00:00,X1-1-20260101,notS,PAPER,1.2.3.4\n", encoding="utf-8")
    t = E.read_taps(csvp)
    assert [x["label"] for x in t] == ["notS", "S"]            # sorted oldest first, normalised
    assert E.read_taps(tmp_path / "nope.csv") == []


# ------------------------------------------------------------------ statistics
def rows_from(rs, labels, dates=None):
    dates = dates or [str(date(2026, 1, 1) + timedelta(days=i)) for i in range(len(rs))]
    return [dict(R=r, label=l, date=d, week=E.iso_week(utc(d + "T15:00:00"))) for r, l, d in zip(rs, labels, dates)]


def test_perfect_separation_is_significant_and_deterministic():
    rs = [1.5] * 15 + [-1.0] * 15
    labels = ["S"] * 15 + ["notS"] * 15
    a = E.summarize(rows_from(rs, labels), n_perm=2000)
    b = E.summarize(rows_from(rs, labels), n_perm=2000)
    assert a["gap_R"] == pytest.approx(2.5) and a["p_perm_day"] < 0.01
    assert a == b
    assert a["S"]["n"] == 15 and a["S"]["win_pct"] == 100.0 and a["notS"]["win_pct"] == 0.0


def test_noise_is_not_significant():
    rng = np.random.default_rng(3)
    rs = list(rng.choice([-1.0, 2.0], size=60, p=[0.65, 0.35]))
    labels = ["S" if i % 2 else "notS" for i in range(60)]
    assert E.summarize(rows_from(rs, labels), n_perm=2000)["p_perm_day"] > 0.05


def test_missing_group_gives_no_p():
    a = E.summarize(rows_from([1.0, 2.0], ["S", "S"]), n_perm=100)
    assert a["p_perm_day"] is None and a["gap_R"] is None and a["notS"]["n"] == 0
    z = E.summarize([], n_perm=100)
    assert z["n"] == 0 and z["p_perm_day"] is None and z["S"]["mean_R"] is None


def test_permutation_keeps_a_days_trades_together():
    # day D1 has [S, notS]; every other day has one trade. With size-2 blocks only D1 exists in its
    # group, so its label pair can never move to a single-trade day.
    rows = [dict(R=2.0, label="S", date="D1", week="w"), dict(R=-1.0, label="notS", date="D1", week="w")]
    rows += [dict(R=-1.0, label="notS", date=f"D{i}", week="w") for i in range(2, 8)]
    rows += [dict(R=2.0, label="S", date=f"D{i}", week="w") for i in range(8, 13)]
    gap, p = E.day_permutation_p(rows, n_perm=500, seed=1)
    assert gap is not None and 0 < p <= 1


def test_by_week_split():
    r = rows_from([1, -1, 2, -1], ["S", "notS", "S", "notS"],
                  ["2026-09-28", "2026-09-29", "2026-10-05", "2026-10-06"])
    s = E.summarize(r, n_perm=50)
    assert list(s["by_week"]) == ["2026-W40", "2026-W41"]
    assert s["by_week"]["2026-W40"]["S"]["n"] == 1 and s["by_week"]["2026-W41"]["notS"]["mean_R"] == -1


# ------------------------------------------------------------------ end to end (synthetic)
def test_analyse_end_to_end(tmp_path):
    csvp = tmp_path / "labels.csv"
    csvp.write_text(
        "logged_at,candidate_id,label,mode,source_ip\n"
        "2026-09-27T04:00:08+00:00,O11-1-20260917,S,PAPER,127.0.0.1\n"               # agent test
        "2026-09-28T14:11:40+00:00,S43-1-20260907,S,PAPER,100.64.0.9\n"              # real, remembered
        "2026-09-28T14:11:55+00:00,S43-1-20260907,notS,PAPER,100.64.0.9\n"           # repeat on same card
        "2026-09-29T14:00:00+00:00,S20-1-20210303,S,PAPER,100.64.0.9\n"              # window A -> refused
        "2026-09-29T14:05:00+00:00,S20-1-20150302,notS,PAPER,100.64.0.9\n", encoding="utf-8")  # blind
    log = tmp_path / "l.log"
    log.write_text("[2026-09-28T10:11:15-04:00] sent S43-1-20260907 grade=S\n"
                   "[2026-09-29T10:00:00-04:00] sent S20-1-20150302 grade=S\n", encoding="utf-8")
    asked = []

    def bars_for(date):
        asked.append(date)
        A = short_setup()
        bar(A, 12, 100.0, 100.2, 97.0, 97.5)
        return A

    cand = SimpleNamespace(direction="short", stop=101.0, features=dict(minutes_after_open=10))
    res = E.analyse(csvp, [log], bars_for, finder=lambda A, info, inst: cand, n_perm=200)
    assert res["n_rows_in_labels_csv"] == 5 and res["n_test"] == 1 and res["n_real"] == 4
    assert "2021-03-03" not in asked and "2017-09-17" not in asked       # window A never loaded
    st = {(t["candidate_id"], t["label"]): t["status"] for t in res["taps"]}
    assert st[("O11-1-20260917", "S")].startswith("excluded: agent test")
    assert st[("S43-1-20260907", "S")] == "scored"
    assert st[("S43-1-20260907", "notS")].startswith("repeat tap")
    assert st[("S20-1-20210303", "S")].startswith("excluded: reserved window A")
    assert st[("S20-1-20150302", "notS")] == "scored"
    a = res["all_scored"]
    assert a["n"] == 2 and a["S"]["n"] == 1 and a["notS"]["n"] == 1 and a["S"]["mean_R"] == pytest.approx(1.504, abs=1e-3)
    assert res["blind_only"]["n"] == 1 and res["remembered_only"]["n"] == 1
    assert len(res["orb1m_sha256"]) == 64


def test_analyse_with_only_test_taps_reports_n0(tmp_path):
    csvp = tmp_path / "labels.csv"
    csvp.write_text("logged_at,candidate_id,label,mode,source_ip\n"
                    "2026-09-27T04:00:08+00:00,O11-1-20260917,S,PAPER,127.0.0.1\n", encoding="utf-8")
    res = E.analyse(csvp, [], lambda d: pytest.fail("bars must not be loaded"), n_perm=50)
    assert res["n_real"] == 0 and res["all_scored"]["n"] == 0 and res["all_scored"]["p_perm_day"] is None


def test_no_label_file_is_n0(tmp_path):
    res = E.analyse(tmp_path / "none.csv", [], lambda d: None, n_perm=50)
    assert res["n_rows_in_labels_csv"] == 0 and res["all_scored"]["n"] == 0
