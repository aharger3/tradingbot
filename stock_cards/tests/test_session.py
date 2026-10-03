"""A whole morning on fixture bars: dry run, live run with a fake ntfy, restart safety, cap, weekday gate."""
import json
from datetime import datetime, timedelta

from stock_cards import ledger, session
from stock_cards.config import ET
from . import fx

CFG = {"token": "tok-SECRET", "answer_topic": "ans-SECRET", "base_url": "", "topic": "alert-SECRET"}


def _scan(tmp_path, live=False, syms=("PLTR", "QQQ"), check_schedule=False, cap=6, session_obj=None):
    full = {s: fx.bars(s) for s in syms}
    ctxs = {s: fx.ctx(s) for s in syms}
    return session.Scan(fx.DAY, list(syms), ctxs, session.ReplayFetcher(full), live=live, data_dir=tmp_path,
                        out_dir=tmp_path / "charts", cfg=CFG, cap=cap, session=session_obj, log=lambda m: None,
                        check_schedule=check_schedule)


def _run(scan):
    sent = []
    for now in session.minute_times(fx.DAY):
        sent += scan.step(now)
    return sent


def test_dry_morning_on_fixture(tmp_path):
    sent = _run(_scan(tmp_path))
    # PLTR: 09:39 x2 (same minute+side: one card, one dup), 09:41 (inside 5 min of 09:39: gap), 10:04 not fired,
    # 10:06 (27 min after the 09:39 card, same symbol and side: repeat), 10:15 tight stop, 10:16 card (37 min after).
    # QQQ (scanned too) has an eligible 09:45.
    assert [(r["sym"], r["sig_t"], r["side"]) for r in sent] == [("PLTR", "09:39", "L"), ("QQQ", "09:45", "L"),
                                                                 ("PLTR", "10:16", "L")]
    assert [r["seq"] for r in sent] == [1, 2, 3] and all(r["mode"] == "dry" for r in sent)
    by = {}
    for c in ledger.candidates(fx.DAY, tmp_path):
        if c["sym"] == "PLTR":
            by.setdefault(c["action"], []).append(c["sig_t"])
    assert by["dry"] == ["09:39", "10:16"]
    assert by["dup"] == ["09:39"] and by["gap"] == ["09:41"] and by["repeat"] == ["10:06"]
    assert sorted(by["ineligible"]) == ["10:04", "10:15"]
    assert (tmp_path / "cards_dry.jsonl").exists() and not (tmp_path / "cards_sent.jsonl").exists()
    for r in sent:                                                       # decision at the bar close; sent seconds later
        lag = datetime.fromisoformat(r["sent_at"]) - datetime.fromisoformat(r["sig_close_ts"])
        assert timedelta(0) <= lag <= timedelta(seconds=45)


def test_restart_never_resends_and_cap_is_restart_safe(tmp_path):
    first = _run(_scan(tmp_path))
    again = _run(_scan(tmp_path))                                        # a second process the same morning
    assert len(first) == 3 and again == []
    assert ledger.n_sent("dry", fx.DAY, tmp_path) == 3


def test_cap_stops_further_cards(tmp_path):
    sent = _run(_scan(tmp_path, cap=2))
    assert len(sent) == 2
    assert "cap" in {c["action"] for c in ledger.candidates(fx.DAY, tmp_path)}


def test_weekday_gate_blocks_friday(tmp_path):
    scan = _scan(tmp_path, check_schedule=True)
    fri = datetime(2026, 10, 2, 9, 40, tzinfo=ET)
    assert scan.step(fri) == [] and ledger.candidates(None, tmp_path) == []


def test_live_morning_posts_and_logs_to_the_live_ledger(tmp_path):
    posts = []

    class R:
        ok, status_code = True, 200

        def json(self):
            return {"attachment": {"url": "https://ntfy.sh/file/a.png"}}

    class S:
        def put(self, url, **kw):
            return R()

        def post(self, url, json=None, **kw):
            posts.append(json)
            return R()

    sent = _run(_scan(tmp_path, live=True, session_obj=S()))
    assert len(sent) == 3 and len(posts) == 3 and all(r["mode"] == "live" for r in sent)
    assert (tmp_path / "cards_sent.jsonl").exists() and not (tmp_path / "cards_dry.jsonl").exists()
    assert {r["card_id"] for r in ledger.cards("live", fx.DAY, tmp_path)} == {
        json.loads(p["actions"][0]["body"])["card_id"] for p in posts}


def test_a_failing_card_does_not_stop_the_morning(tmp_path):
    class Boom:
        def put(self, *a, **k):
            raise RuntimeError("network down")

        def post(self, *a, **k):
            raise RuntimeError("network down")

    scan = _scan(tmp_path, live=True, session_obj=Boom())
    assert _run(scan) == []
    assert any(c["action"].startswith("error:") for c in ledger.candidates(fx.DAY, tmp_path))
    assert ledger.n_sent("live", fx.DAY, tmp_path) == 0


def test_replay_fetcher_hides_the_bar_in_progress():
    f = session.ReplayFetcher({"PLTR": fx.bars("PLTR")})
    now = datetime(2026, 8, 4, 9, 40, 6, tzinfo=ET)
    assert f(now)["PLTR"][-1].timestamp == "09:39:00"
    assert session.minute_times(fx.DAY)[0].strftime("%H:%M:%S") == "09:36:06"
    assert session.minute_times(fx.DAY)[-1].strftime("%H:%M:%S") == "10:59:06"
