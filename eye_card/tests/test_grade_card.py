from eye_card.chart import Candidate
from eye_card.grade_card import render_grade_card, s_traits


def _bars():
    # 09:30..09:40, break at 09:36 (close > 100), retest at 09:40 wick to 100.1
    px = [99, 99.5, 99.2, 99.8, 99.6, 99.4, 101.5, 102, 101.8, 101.2, 100.8]
    out = []
    for i, c in enumerate(px):
        o = px[i - 1] if i else 99
        lo = min(o, c) - 0.3
        if i == 10:
            lo = 100.1
        out.append(dict(time=f"09:{30 + i:02d}:00", open=o, high=max(o, c) + 0.3, low=lo, close=c))
    return out


def _cand():
    return Candidate(candidate_id="t", symbol="MNQ", direction="LONG", trigger_time="09:40:00",
                     entry=101.0, stop=99.9, targets=[102.1, 103.2], level=100.0,
                     extra=dict(atr=1.0, retest_bars_after_break=4, gap_in_direction=True))


def test_traits_values():
    t = {k: ok for k, _, ok in s_traits(_cand(), _bars())}
    assert t == {"Early": True, "Fast": True, "Shallow": True, "Held": True,
                 "Trigger": True, "Gap with": True}


def test_traits_missing_inputs_are_unknown():
    c = _cand(); c.extra = {}
    t = {k: ok for k, _, ok in s_traits(c, _bars())}
    assert t["Fast"] is None and t["Shallow"] is None and t["Gap with"] is None


def test_render_png(tmp_path):
    p = render_grade_card(_cand(), _bars(), tmp_path / "c.png")
    assert p.exists() and p.stat().st_size > 5000
