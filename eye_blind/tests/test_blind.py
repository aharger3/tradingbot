import importlib
import re

import numpy as np
import pandas as pd
import pytest
from flask import Flask

from eye_blind import app as appmod
from eye_blind import core

TOKEN = "dev-local-only"


def day_arrays(kind="win", shift=0.0):
    """orb1m's own synthetic setup: OR 100-101, break+displacement, wick retest pin at bar 7,
    entry bar 8. kind=win runs to target; lose falls through the stop; flat has no setup."""
    n = 91
    O = np.full(n, 100.5); H = np.full(n, 101.0); L = np.full(n, 100.0); C = np.full(n, 100.5)
    if kind != "flat":
        O[5], H[5], L[5], C[5] = 100.9, 103.0, 100.9, 102.9
        O[6], H[6], L[6], C[6] = 102.9, 103.0, 102.0, 102.5
        O[7], H[7], L[7], C[7] = 102.0, 102.1, 101.0, 102.05
        for j in range(8, n):
            if kind == "win":
                O[j], H[j], L[j], C[j] = (102.0 + (j - 8) * .5, 102.5 + (j - 8) * .5, 101.9 + (j - 8) * .5, 102.4 + (j - 8) * .5)
            else:
                O[j], H[j], L[j], C[j] = (101.8 - (j - 8) * .5, 102.1 - (j - 8) * .5, 101.4 - (j - 8) * .5, 101.6 - (j - 8) * .5)
    return dict(open=O + shift, high=H + shift, low=L + shift, close=C + shift)


def make_bars(kinds, start="2012-01-02"):
    dates = pd.bdate_range(start, periods=len(kinds))
    rows = []
    for d, k in zip(dates, kinds):
        A = day_arrays(k, shift=1800.0)  # NQ-like absolute level
        t0 = pd.Timestamp(d.strftime("%Y-%m-%d") + " 09:30", tz="America/New_York")
        for m in range(91):
            rows.append(dict(ts=t0 + pd.Timedelta(minutes=m), open=A["open"][m], high=A["high"][m],
                             low=A["low"][m], close=A["close"][m]))
    return pd.DataFrame(rows)


KINDS = (["win", "lose", "flat"] * 30)[:90]  # 60 signal sessions


@pytest.fixture
def pool():
    return core.build_pool(make_bars(KINDS), seed=1, salt="t")


def test_loader_keeps_only_signal_sessions_and_flags_ready(pool):
    assert len(pool["sessions"]) == 60 and pool["ready"] is True
    small = core.build_pool(make_bars(["win", "flat", "lose"]), seed=1)
    assert len(small["sessions"]) == 2 and small["ready"] is False
    assert pool["sessions"][pool["order"][0]]["i"] == 8


def test_window_guard_refuses_window_a_and_fit_window():
    for start in ("2019-09-26", "2020-03-02", "2024-10-01", "2010-01-04"):
        with pytest.raises(core.WindowViolation):
            core.build_pool(make_bars(["win"], start=start))
    core.build_pool(make_bars(["win"], start="2020-03-02"), window=None)  # synthetic escape hatch only


def test_csv_loader_ts_ns(tmp_path):
    b = make_bars(["win"])
    d = pd.DataFrame(dict(ts_ns=b["ts"].dt.tz_convert("UTC").astype("int64"),
                          open=b.open, high=b.high, low=b.low, close=b.close, volume=1))
    p = tmp_path / "nq.csv"
    d.to_csv(p, index=False)
    got = core.load_bars_csv(p)
    assert str(got["ts"].iloc[0]) == str(b["ts"].iloc[0])
    assert len(core.build_pool(got, seed=1)["sessions"]) == 1


def test_render_is_blind(pool):
    sid = pool["order"][0]
    s = pool["sessions"][sid]
    svg = core.render_svg(s, pool["cfg"])
    assert svg.count('class="up dec"') + svg.count('class="dn dec"') == 2  # one decision candle (wick+body)
    assert len(re.findall(r'<rect class="(?:up|dn)', svg)) == s["i"]  # bars 0..i-1, none after
    body = svg.replace("http://www.w3.org/2000/svg", "")
    assert not re.search(r"\b(19|20)\d\d\b", body)  # no year
    assert not re.search(r"\b1[89]\d\d\b", body)  # no absolute NQ-like price
    assert s["date"] not in svg and "09:30" in svg and "11:00" not in svg


def test_page_hides_date_future_and_id_is_opaque(pool, tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "POOL", tmp_path / "pool.json")
    monkeypatch.setattr(appmod, "TAPS", tmp_path / "taps.jsonl")
    core.save_pool(pool, appmod.POOL)
    c = appmod.create_app().test_client()
    r = c.get(f"/blind?token={TOKEN}")
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "no-store" in r.headers["Cache-Control"]
    for sess in pool["sessions"].values():
        assert sess["date"] not in html and sess["date"].replace("-", "") not in html
    assert "2012" not in html and "Session 1 of 60" in html
    assert c.get("/blind?token=nope").status_code == 403


def test_tap_flow_order_dupes_token(pool, tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "POOL", tmp_path / "pool.json")
    monkeypatch.setattr(appmod, "TAPS", tmp_path / "taps.jsonl")
    core.save_pool(pool, appmod.POOL)
    c = appmod.create_app().test_client()
    first, second = pool["order"][:2]
    assert c.post("/blind/tap", data=dict(token="x", id=first, label="S")).status_code == 403
    assert c.post("/blind/tap", data=dict(token=TOKEN, id=second, label="S")).status_code == 409  # no skipping
    assert c.post("/blind/tap", data=dict(token=TOKEN, id=first, label="maybe")).status_code == 400
    assert c.post("/blind/tap", data=dict(token=TOKEN, id="zzz", label="S")).status_code == 404
    assert c.post("/blind/tap", data=dict(token=TOKEN, id=first, label="S")).status_code == 303
    assert c.post("/blind/tap", data=dict(token=TOKEN, id=first, label="notS")).status_code == 409  # no re-tap
    taps = core.read_taps(appmod.TAPS)
    assert [t["label"] for t in taps] == ["S"] and "date" not in taps[0]
    assert "Session 2 of 60" in c.get(f"/blind?token={TOKEN}").get_data(as_text=True)


def test_scorer_uses_frozen_fills(pool):
    o = core.load_orb1m()
    win = next(s for s in pool["sessions"].values() if s["A"]["open"][20] > s["A"]["open"][8] + 3)
    lose = next(s for s in pool["sessions"].values() if s["A"]["open"][20] < s["A"]["open"][8] - 3)
    assert abs(core.trade_r(win, pool["cfg"]) - (2 - 1.24 / (1.5 * 2.0))) < 1e-9  # orb1m's own test number
    assert core.trade_r(lose, pool["cfg"]) < -1.0  # stop gap + costs, same-bar stop wins
    assert o.TICK == 0.25 and len(core.orb1m_sha256()) == 64


def taps_for(pool, s_when_win=1.0, n=None):
    """Tap S on winners (prob s_when_win) -> separates S from Not-S by construction."""
    out = []
    for k, sid in enumerate(pool["order"][:n]):
        win = core.trade_r(pool["sessions"][sid], pool["cfg"]) > 0
        out.append(dict(session_id=sid, label="S" if win and s_when_win else "notS"))
    return out


def test_verdicts(pool):
    perfect = core.score(pool, taps_for(pool), n_shuffles=2000)
    assert perfect["S"]["n"] >= 30 and perfect["verdict"] == "PASS" and perfect["p_perm"] < .05
    assert perfect["S"]["mean_R"] > 1.5 and perfect["S"]["win_pct"] == 100.0
    # anti-skilled: S on losers -> FAIL
    anti = [dict(t, label="notS" if t["label"] == "S" else "S") for t in taps_for(pool)]
    assert core.score(pool, anti, n_shuffles=2000)["verdict"] == "FAIL"
    # coin-flip-like: alternate labels regardless of outcome -> FAIL (n_S >= 30, no edge)
    alt = [dict(session_id=sid, label="S" if k % 2 else "notS") for k, sid in enumerate(pool["order"])]
    r = core.score(pool, alt, n_shuffles=2000)
    assert r["S"]["n"] == 30 and r["verdict"] == "FAIL"
    # 60 sessions tapped but < 30 S taps -> INCONCLUSIVE; fewer sessions -> IN_PROGRESS
    few = [dict(session_id=sid, label="S" if k < 10 else "notS") for k, sid in enumerate(pool["order"])]
    assert core.score(pool, few, n_shuffles=200)["verdict"] == "INCONCLUSIVE"
    assert core.score(pool, few[:20], n_shuffles=200)["verdict"] == "IN_PROGRESS"
    assert core.score(pool, [], n_shuffles=10)["verdict"] == "IN_PROGRESS"


def test_blueprint_is_opt_in_on_live_label_server(monkeypatch):
    monkeypatch.delenv("EYE_BLIND", raising=False)
    import eye_card.server as live
    importlib.reload(live)
    assert not any(r.rule.startswith("/blind") for r in live.app.url_map.iter_rules())
    assert any(r.rule == "/label" for r in live.app.url_map.iter_rules())
    monkeypatch.setenv("EYE_BLIND", "1")
    importlib.reload(live)
    assert any(r.rule == "/blind" for r in live.app.url_map.iter_rules())
    assert any(r.rule == "/label" for r in live.app.url_map.iter_rules())
    monkeypatch.delenv("EYE_BLIND")
    importlib.reload(live)
