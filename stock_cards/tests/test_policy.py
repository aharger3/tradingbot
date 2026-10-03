"""Which candidates become cards: window, eligibility, cap, spacing, staleness, duplicates, Mon-Thu."""
from datetime import datetime, timedelta

from stock_cards import policy
from stock_cards.config import ET


def cand(sig_t="09:40", status="fired", tags=("clean",), sym="NVDA", day="2026-10-05", side="L"):
    h, m = map(int, sig_t.split(":"))
    close = datetime(2026, 10, 5, h, m, tzinfo=ET) + timedelta(minutes=1)
    return {"sym": sym, "day": day, "sig_t": sig_t, "side": side, "status": status, "tags": list(tags),
            "sig_close_ts": close.isoformat(timespec="seconds"), "key": f"{sym}|{day}|{sig_t}|{side}"}


def now_for(c, secs=8):
    return datetime.fromisoformat(c["sig_close_ts"]) + timedelta(seconds=secs)


def test_send_when_everything_fits():
    c = cand()
    assert policy.decide(c, now_for(c), 0, set()) == "send"


def test_window_edges():
    for t, v in (("09:34", "window"), ("09:35", "send"), ("10:58", "send"), ("10:59", "window"), ("11:00", "window")):
        c = cand(t)
        assert policy.decide(c, now_for(c), 0, set()) == v, t


def test_eligibility_needs_fired_and_clean():
    for kw in ({"status": "skipped_d"}, {"status": "skipped_tight_stop"}, {"tags": ("late",)}, {"tags": ()}):
        c = cand(**kw)
        assert policy.decide(c, now_for(c), 0, set()) == "ineligible", kw


def test_cap_is_six_a_day():
    c = cand()
    assert policy.decide(c, now_for(c), 5, set()) == "send"
    assert policy.decide(c, now_for(c), 6, set()) == "cap"


def test_five_minute_spacing():
    a, b = cand("09:40"), cand("09:44", sym="AMD")
    assert policy.decide(b, now_for(b), 1, set(), prev_cards=[a]) == "gap"
    b = cand("09:45", sym="AMD")
    assert policy.decide(b, now_for(b), 1, set(), prev_cards=[a]) == "send"


def test_same_symbol_and_side_not_again_within_30_minutes():
    a = cand("09:40", sym="NFLX", side="S")
    other = cand("09:50", sym="AMD")
    assert policy.decide(cand("10:01", sym="NFLX", side="S"), now_for(cand("10:01", sym="NFLX", side="S")), 2, set(), prev_cards=[a, other]) == "repeat"
    far = cand("10:11", sym="NFLX", side="S")
    assert policy.decide(far, now_for(far), 2, set(), prev_cards=[a, other]) == "send"
    flip = cand("10:01", sym="NFLX", side="L")
    assert policy.decide(flip, now_for(flip), 2, set(), prev_cards=[a, other]) == "send"


def test_stale_candidate_is_not_sent():
    c = cand()
    assert policy.decide(c, now_for(c, secs=46), 0, set()) == "stale"
    assert policy.decide(c, now_for(c, secs=44), 0, set()) == "send"


def test_duplicate_key():
    c = cand()
    assert policy.decide(c, now_for(c), 0, {c["key"]}) == "dup"


def test_mon_thu_only():
    for day, ok in ((5, True), (6, True), (7, True), (8, True), (9, False), (10, False), (11, False)):
        assert policy.schedule_ok(datetime(2026, 10, day, 9, 40, tzinfo=ET))[0] is ok, day
