"""Tests for the g-latency fixes: send_card never raises; honest tap entry shifts the fill bar."""
import sys
from pathlib import Path
import numpy as np
import requests

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "research" / "agent_runs" / "v3-eye4-paper"))
sys.path.insert(0, str(REPO))
import eye_paper  # noqa: E402
from eye_card.notify import send_card  # noqa: E402
from eye_card.chart import Candidate  # noqa: E402


class Boom:
    calls = 0
    def post(self, *a, **k):
        Boom.calls += 1
        raise requests.ConnectTimeout("ntfy down")


def test_send_card_survives_outage(tmp_path):
    png = tmp_path / "c.png"; png.write_bytes(b"x")
    c = Candidate(candidate_id="T1", symbol="MNQ", direction="LONG", trigger_time="09:41:00", entry=10.0,
                  stop=9.0, targets=[11.0, 12.0], level=9.5, level_label="ORB", setup="t", reason="")
    r = send_card(c, png, "tok", session=Boom(), backoff_s=0)
    assert r.ok is False and Boom.calls == 3


def _day(n=91, px=100.0):
    O = np.full(n, px); return {"open": O.copy(), "high": O + 1, "low": O - 1, "close": O.copy()}


def _cand(sent):
    return {"id": "X", "symbol": "MNQ", "date": "2026-09-01", "side": 1, "signal_minute": 10, "stop": 95.0,
            "session_extreme": None, "named_levels": {}, "card_sent_ts": sent, "cutoff_minute": 60}


def test_honest_entry_uses_first_open_after_tap():
    A = _day(); A["open"][11] = 100.0; A["open"][12] = 101.0
    cand = _cand("2026-09-01T09:41:00-04:00")
    tap = {"candidate_id": "X", "grade": "S", "tap_ts": "2026-09-01T09:41:25-04:00"}
    old = eye_paper.run_confirmed(cand, tap, day_array=A)
    new = eye_paper.run_confirmed(cand, tap, day_array=A, honest_tap_entry=True)
    assert old["entry"] == 100.25 and new["entry"] == 101.25


def test_honest_entry_skips_if_stopped_while_waiting():
    A = _day(); A["low"][11] = 94.0
    cand = _cand("2026-09-01T09:41:00-04:00")
    tap = {"candidate_id": "X", "grade": "S", "tap_ts": "2026-09-01T09:42:30-04:00"}
    r = eye_paper.run_confirmed(cand, tap, day_array=A, honest_tap_entry=True)
    assert r["confirmed"] is False and r["reason"] == "stopped_before_tap_fill"
