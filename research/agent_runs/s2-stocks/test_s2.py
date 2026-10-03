import os, copy
import numpy as np
import pytest
import s2_lib as L

M0 = 600  # signal bar 10:00 -> slot 30; entry bar slot 31


def flat_day(price=100.0, n=390):
    return dict(O=np.full(n, price), H=np.full(n, price + 0.05), L=np.full(n, price - 0.05), C=np.full(n, price))


def test_fill_is_next_bar_open_plus_tick_not_signal_bar():
    d = flat_day(); d["O"][31] = 100.20; d["C"][30] = 99.0       # signal-bar close is far from the next open
    r, how = L.sim(d, M0, 1, stop=99.0)
    fill = 100.21; risk = fill - 99.0
    assert how == "flat"
    assert r == pytest.approx(((100.0 - fill) - (2 * L.COMM + L.TICK)) / risk, abs=1e-9)


def test_signal_bar_and_earlier_bars_do_not_matter():
    d = flat_day(); d["O"][31] = 100.0
    a = L.sim(d, M0, 1, 99.0)
    d2 = copy.deepcopy(d); d2["H"][:31] = 500; d2["L"][:31] = 1; d2["C"][:31] = 7
    assert L.sim(d2, M0, 1, 99.0) == a


def test_stop_wins_same_bar_as_target():
    d = flat_day(); d["O"][31] = 100.0
    d["H"][32] = 110.0; d["L"][32] = 98.5           # one bar touches both stop (99) and 2R target
    r, how = L.sim(d, M0, 1, 99.0)
    assert how == "stop" and r < -1.0               # costs push it below -1R


def test_gap_through_stop_fills_at_open():
    d = flat_day(); d["O"][31] = 100.0
    d["O"][33] = 97.0; d["H"][33] = 97.2; d["L"][33] = 96.5
    r, how = L.sim(d, M0, 1, 99.0)
    fill = 100.01; risk = fill - 99.0
    assert how == "stop"
    assert r == pytest.approx(((97.0 - fill) - (2 * L.COMM + L.TICK)) / risk, abs=1e-9)
    assert r < -2.0


def test_target_needs_one_tick_through():
    d = flat_day(); d["O"][31] = 100.0
    fill = 100.01; risk = fill - 99.0; tgt = fill + 2 * risk
    d["H"][32] = tgt + 0.005                          # touches but not through by a tick
    assert L.sim(d, M0, 1, 99.0)[1] == "flat"
    d["H"][32] = tgt + L.TICK
    r, how = L.sim(d, M0, 1, 99.0)
    assert how == "tgt" and r == pytest.approx((2 * risk - 2 * L.COMM) / risk, abs=1e-9)


def test_short_side_mirror():
    d = flat_day(); d["O"][31] = 100.0
    d["H"][32] = 101.5                                # stop at 101 hit
    r, how = L.sim(d, M0, -1, 101.0)
    assert how == "stop" and r < -1.0
    d = flat_day(); d["O"][31] = 100.0
    fill = 99.99; risk = 101.0 - fill; tgt = fill - 2 * risk
    d["L"][35] = tgt - L.TICK
    assert L.sim(d, M0, -1, 101.0)[1] == "tgt"


def test_flat_at_11_open_and_later_bars_ignored():
    d = flat_day(); d["O"][31] = 100.0; d["O"][90] = 100.5   # 11:00 bar
    d["L"][90:] = 1.0; d["H"][90:] = 999.0                    # nothing at/after 11:00 may trigger stop/target
    r, how = L.sim(d, M0, 1, 99.0)
    fill = 100.01; risk = fill - 99.0
    assert how == "flat" and r == pytest.approx(((100.5 - fill) - (2 * L.COMM + L.TICK)) / risk, abs=1e-9)


def test_next_open_through_stop_is_minus_one_and_tiny_risk_is_skipped():
    d = flat_day(); d["O"][31] = 98.0
    assert L.sim(d, M0, 1, 99.0) == (-1.0, "stop_thru_fill")
    d = flat_day(); d["O"][31] = 100.0
    assert L.sim(d, M0, 1, 99.999) is None


def test_no_entry_bar_or_late_signal_returns_none():
    d = flat_day(); d["O"][31] = np.nan
    assert L.sim(d, M0, 1, 99.0) is None
    assert L.sim(flat_day(), 659, 1, 99.0) is None           # signal 10:59 -> entry bar would be the 11:00 flat bar


@pytest.mark.skipif(not os.path.exists(L.S_TRADES), reason="needs tradingbot data")
def test_reproduces_s_dataset_R2_eng_on_his_marks():
    rows = L.run_sim(L.load_s_rows())
    diffs = [abs(x["r"] - float(x["R2_eng"])) for x in rows if x["r"] is not None and x["R2_eng"] not in ("", None)]
    assert len(diffs) > 200 and max(diffs) < 0.01


@pytest.mark.skipif(not os.path.exists(L.S_TRADES), reason="needs tradingbot data")
def test_fit_window_and_no_reserved_dates():
    rows = L.load_s_rows()
    assert rows and all(L.FIT0 <= x["day"] <= L.FIT1 for x in rows)
    assert min(x["day"] for x in rows) > "2024-09-25"


# ---------------------------------------------------------------- s2_run helpers
import s2_run as R


def _c(sym, day, m, r, lab="unmarked", side=1):
    return dict(sym=sym, day=day, m=m, r=r, lab=lab, side=side)


def test_marked_filter_drops_marked_and_near_s_rows():
    cands = [_c("A", "d1", 600, 1.0), _c("A", "d1", 601, 2.0), _c("A", "d1", 601, 3.0, side=-1),
             _c("A", "d2", 600, 4.0, lab="S"), _c("A", "d3", 600, None), _c("A", "d4", 600, 5.0, lab="unmarked_judged")]
    s_rows = [dict(sym="A", day="d1", m=600, side=1)]
    kept = {(x["day"], x["r"]) for x in R.marked_filter(cands, s_rows)}
    assert kept == {("d1", 3.0), ("d4", 5.0)}        # same-side rows within 3 min of his row dropped, opposite side kept


def test_day_perm_is_calibrated_under_no_effect_and_detects_a_planted_one():
    rng = np.random.default_rng(1)
    days = ["d%03d" % i for i in range(120)]
    pool = [_c("A", d, 600 + int(rng.integers(-3, 4)), float(rng.normal(-0.2, 1.0))) for d in days for _ in range(2)]
    idx, _ = R.build_index(pool)
    slots_null = [dict(sym="A", day=d, m=600) for d in days[:40]]
    perm, fills = R.day_perm(slots_null, idx, days, n=400)
    pm = float(np.mean([x['r'] for x in pool]))
    assert fills.mean() > 0.9 and abs(np.nanmean(perm) - pm) < 0.08
    assert (perm >= pm).mean() == pytest.approx(0.5, abs=0.2)        # no effect: observed sits mid-distribution
    assert (perm >= 1.0).mean() < 0.01                                               # a +1.2R mean is far out in the tail
