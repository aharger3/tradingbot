"""The detector on fixture bars: it must reproduce the S2 tape, bar by bar, with no look at later bars."""
import copy
import random

from stock_cards import context, detect
from stock_cards.policy import in_window
from . import fx


def _qqq(upto_hhmm=None):
    q = fx.bars("QQQ")
    if upto_hhmm:
        q = fx.upto(q, upto_hhmm)
    pmh, pml, _ = detect.split_session(q)
    return context.qqq_breaks(q, fx.ctx("QQQ"), pmh, pml)


def _sig(c):
    return (c["sig_t"], c["side"], c["stop"], c["status"])


def _exp():
    return {(e["et"], "L" if e["dir"] == "call" else "S", round(e["stop"], 2), e["status"]) for e in fx.expected()}


def test_full_day_reproduces_tape():
    got = {_sig(c) for c in detect.detect_all("PLTR", fx.DAY, fx.bars("PLTR"), fx.ctx("PLTR"), _qqq())}
    assert got == _exp() and len(got) == 7


def test_candidate_fields():
    c = detect.detect_all("PLTR", fx.DAY, fx.bars("PLTR"), fx.ctx("PLTR"), _qqq())[0]
    assert c["sym"] == "PLTR" and c["side"] in ("L", "S") and c["sig_close_ts"].endswith("-04:00")
    assert c["key"] == f"PLTR|{fx.DAY}|{c['sig_t']}|{c['side']}"
    assert "clean" in c["tags"]


def test_bar_by_bar_equals_full_day():
    """Decision-bar scan (what the live feed does) finds exactly the tape's candidates, each at its own bar."""
    full, found = fx.bars("PLTR"), {}
    for h in range(9, 11):
        for m in range(0, 60):
            hhmm = f"{h:02d}:{m:02d}"
            if not ("09:36" <= hhmm <= "10:59"):
                continue
            c_now = fx.upto(full, hhmm)                       # bar hhmm-1 is the newest closed bar
            for c in detect.detect_at("PLTR", fx.DAY, c_now, fx.ctx("PLTR"), _qqq(hhmm)):
                found[c["key"], c["stop"]] = c
    assert {_sig(c) for c in found.values()} == _exp()


def test_later_bars_cannot_change_a_candidate():
    """Replace every bar after 10:07 with noise: candidates with a signal bar before 10:07 do not move."""
    full = fx.bars("PLTR")
    base = {_sig(c) for c in detect.detect_all("PLTR", fx.DAY, fx.upto(full, "10:07"), fx.ctx("PLTR"), _qqq("10:07"))}
    rng = random.Random(7)
    noisy = copy.deepcopy(full)
    for k in noisy:
        if k.timestamp >= "10:07:00":
            k.open, k.high, k.low, k.close = (rng.uniform(100, 200) for _ in range(4))
    got = {_sig(c) for c in detect.detect_all("PLTR", fx.DAY, [k for k in noisy if k.timestamp < "10:07:00"] , fx.ctx("PLTR"), _qqq("10:07"))}
    assert got == base
    assert all(s[0] < "10:07" for s in base) and len(base) == 5


def test_detect_at_only_returns_the_newest_bar():
    full = fx.bars("PLTR")
    out = detect.detect_at("PLTR", fx.DAY, fx.upto(full, "09:40"), fx.ctx("PLTR"), _qqq("09:40"))
    assert {c["sig_t"] for c in out} == {"09:39"} and len(out) == 2        # two candidates share the 09:39 bar
    assert detect.detect_at("PLTR", fx.DAY, [], fx.ctx("PLTR"), None) == []


def test_window_helper():
    assert in_window("09:35") and in_window("10:58") and not in_window("09:34") and not in_window("10:59")
