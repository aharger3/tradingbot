"""The card: three tap buttons, no grade/score/outcome on it, chart cut at the signal bar, secrets masked."""
import json
import re
from datetime import datetime

import pytest

from stock_cards import cards
from stock_cards.config import ET
from . import fx

C = {"sym": "PLTR", "day": fx.DAY, "sig_t": "10:06", "side": "L", "stop": 152.75, "entry": 154.1, "level": 152.9,
     "level_name": "OR high", "status": "fired", "tags": ["clean", "hammer"], "setup": "break_and_retest",
     "sig_close_ts": "2026-08-04T10:07:00-04:00"}
CFG = {"token": "tok-SECRET-123", "answer_topic": "ans-SECRET-topic", "base_url": "", "topic": "alert-SECRET-topic"}


def payload(cfg=CFG, base_url=""):
    return cards.build_payload(C, "EYE-W9-PLTR-20260804-1006L-ab12", 2, {**cfg, "base_url": base_url},
                               chart_url="https://ntfy.sh/file/x.png")


def test_three_buttons_s_nots_skip():
    acts = payload()["actions"]
    assert [a["label"] for a in acts] == ["S", "Not S", "Skip"]
    assert [json.loads(a["body"])["choice"] for a in acts] == ["S", "notS", "skip"]
    assert all(json.loads(a["body"])["card_id"] == "EYE-W9-PLTR-20260804-1006L-ab12" for a in acts)


def test_relay_route_posts_to_the_answer_topic_not_tailscale():
    acts = payload()["actions"]
    assert all(a["url"] == "https://ntfy.sh/ans-SECRET-topic" for a in acts)
    assert not any("ts.net" in a["url"] for a in acts)


def test_tunnel_route_when_tap_base_url_is_set():
    acts = payload(base_url="https://ask.example.test")["actions"]
    assert all(a["url"] == "https://ask.example.test/tap/tok-SECRET-123" for a in acts)
    assert "token" not in json.loads(acts[0]["body"])


def test_card_text_has_no_grade_score_or_outcome():
    p = payload()
    text = (p["title"] + p["message"]).lower()
    for bad in ("grade", "score", "looks like", "clean", "fired", "hammer", "win", "loss", "result"):
        assert bad not in text, bad
    assert p["title"] == "S or Not S? PLTR Long"
    assert "10:06 ET" in p["message"] and "Tap within 2 min" in p["message"] and "PAPER" in p["message"]
    assert p["topic"] == "alert-SECRET-topic"


def test_card_id_prefix_and_length():
    ids = {cards.eyetap.card_id_for(cards.candidate_id(C), blind=False) for _ in range(20)}
    assert len(ids) > 15                                               # random suffix: a replay never reuses an id
    for i in ids:
        assert i.startswith("EYE-") and re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", i)
    assert cards.candidate_id({**C, "sym": "SPCX"}) == "W9-SPCX-20260804-1006L"


def test_chart_stops_at_the_signal_bar(tmp_path):
    rth = [k for k in fx.bars("PLTR") if "09:30:00" <= k.timestamp < "16:00:00"]
    bars = cards.chart_bars(rth, "10:06")
    assert bars[-1]["time"] == "10:06:00" and len(bars) == 37 and bars[0]["time"] == "09:30:00"
    png = cards.render_card(C, rth, tmp_path)
    assert png.exists() and png.read_bytes()[1:4] == b"PNG"


def test_dry_delivery_masks_every_secret(tmp_path):
    rth = [k for k in fx.bars("PLTR") if "09:30:00" <= k.timestamp < "16:00:00"]
    now = datetime(2026, 8, 4, 10, 7, 8, tzinfo=ET)
    row = cards.deliver(C, rth, 2, now, live=False, out_dir=tmp_path, cfg=CFG)
    blob = json.dumps(row)
    for secret in ("tok-SECRET-123", "ans-SECRET-topic", "alert-SECRET-topic"):
        assert secret not in blob
    assert "<TOKEN>" in blob and "<ANSWER_TOPIC>" in blob and "<ALERT_TOPIC>" in blob
    assert row["mode"] == "dry" and row["sig_close_ts"] == C["sig_close_ts"] and row["card_id"].startswith("EYE-W9-PLTR-")


def test_live_delivery_uploads_chart_then_posts_the_same_payload(tmp_path):
    rth = [k for k in fx.bars("PLTR") if "09:30:00" <= k.timestamp < "16:00:00"]
    calls = []

    class R:
        ok, status_code = True, 200

        def json(self):
            return {"attachment": {"url": "https://ntfy.sh/file/abc.png"}}

    class S:
        def put(self, url, **kw):
            calls.append(("put", url))
            return R()

        def post(self, url, json=None, **kw):
            calls.append(("post", url, json))
            return R()

    row = cards.deliver(C, rth, 2, datetime(2026, 8, 4, 10, 7, 8, tzinfo=ET), live=True, out_dir=tmp_path,
                        session=S(), cfg=CFG)
    assert [c[0] for c in calls] == ["put", "post"] and calls[1][1] == "https://ntfy.sh/"
    sent = calls[1][2]
    assert sent["attach"] == "https://ntfy.sh/file/abc.png" and sent["topic"] == "alert-SECRET-topic"
    assert [a["label"] for a in sent["actions"]] == ["S", "Not S", "Skip"]
    assert row["ok"] is True and row["mode"] == "live" and "would_send" not in row


def test_live_without_secrets_refuses():
    with pytest.raises(cards.eyetap.TapConfigError):
        cards.load_cfg(live=True)
    assert cards.load_cfg(live=False)["token"] == "<TOKEN>"
