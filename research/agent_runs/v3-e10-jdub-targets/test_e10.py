"""Tests for E10. Run: python -m pytest research/agent_runs/v3-e10-jdub-targets/test_e10.py -q
Integration tests need the real-NQ CSVs from the main tradingbot checkout and skip if they are absent."""
import os, sys
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e10
import mnq

HAVE_DATA = os.path.isdir(os.path.join(e10.AR, "t01-orb5", "fut"))


def flat_day(open_=100.0, n=91):
    A = {k: np.full(n, open_) for k in ("open", "high", "low", "close")}
    A.update(date="2025-01-02", pdh=None, pdl=None, pmh=None, pml=None)
    return A


# ------------------------------------------------------------ level rule (synthetic)
def test_nearest_level_long_ignores_levels_behind_fill():
    A = flat_day(); A.update(pdh=110.0, pdl=90.0, pmh=104.0, pml=95.0)
    r, name, px = e10.nearest_level(A, fill=100.0, d=1, dist=2.0)
    assert (name, px) == ("pmh", 104.0) and r == pytest.approx(2.0)


def test_nearest_level_short_uses_lows():
    A = flat_day(); A.update(pdh=110.0, pdl=96.0, pmh=104.0, pml=92.0)
    r, name, px = e10.nearest_level(A, fill=100.0, d=-1, dist=2.0)
    assert (name, px) == ("pdl", 96.0) and r == pytest.approx(2.0)


def test_target_uses_level_when_far_enough_else_flat_2r():
    A = flat_day(); A.update(pmh=103.0)               # 1.5R away with dist 2
    assert e10.target_for(A, 100.0, 1, 2.0, 1.0) == (103.0, "pmh")
    assert e10.target_for(A, 100.0, 1, 2.0, 1.5) == (103.0, "pmh")      # boundary counts
    assert e10.target_for(A, 100.0, 1, 2.0, 2.0) == (104.0, "flat2R")   # too close -> flat 2R
    assert e10.target_for(A, 100.0, 1, 2.0, None) == (104.0, "flat2R")  # baseline


def test_literal_rule_nearest_level_too_close_means_flat_even_if_farther_level_qualifies():
    A = flat_day(); A.update(pmh=101.0, pdh=108.0)    # nearest 0.5R, a second level at 4R
    assert e10.target_for(A, 100.0, 1, 2.0, 1.0) == (104.0, "flat2R")


def test_no_level_ahead_is_flat_2r_and_missing_levels_are_safe():
    A = flat_day(); A.update(pdh=99.0, pmh=None, pdl=None, pml=float("nan"))
    assert e10.nearest_level(A, 100.0, 1, 2.0) is None
    assert e10.target_for(A, 100.0, 1, 2.0, 1.0)[1] == "flat2R"


def test_level_target_can_sit_below_2r_and_exit_at_level():
    A = flat_day()
    A["high"][3] = 103.5; A["low"][3] = 100.0          # bar 3 trades through 103 by >= 1 tick
    R, usd, kind = e10.trade_to_target(A, 2, 1, 2.0, 60, 103.0)   # fill = open[2]+tick = 100.25, stop 98.25
    assert kind == "target"
    assert R > 0


def test_same_bar_stop_wins_when_target_and_stop_touch_together():
    A = flat_day()
    A["high"][3] = 110.0; A["low"][3] = 90.0           # both touched in one bar
    R, usd, kind = e10.trade_to_target(A, 2, 1, 2.0, 60, 103.0)
    assert kind == "stop" and R < 0


def test_trade_to_target_equals_frozen_mnq_trade_for_flat_2r():
    rng = np.random.default_rng(3)
    for _ in range(25):
        A = flat_day()
        walk = 100 + np.cumsum(rng.normal(0, 0.6, 91))
        A["open"] = walk; A["close"] = walk + rng.normal(0, 0.2, 91)
        A["high"] = np.maximum(A["open"], A["close"]) + rng.uniform(0, 0.8, 91)
        A["low"] = np.minimum(A["open"], A["close"]) - rng.uniform(0, 0.8, 91)
        side = int(rng.choice([-1, 1])); dist = float(rng.choice([2.0, 3.5, 5.0]))
        fill = A["open"][10] + e10.TICK * side
        ref = mnq.trade(A, 10, side, dist, e10.CUT, 9, "2R")
        mine = e10.trade_to_target(A, 10, side, dist, e10.CUT, fill + side * 2 * dist)
        assert mine[0] == pytest.approx(ref[0]) and mine[1] == pytest.approx(ref[1])


# ------------------------------------------------------------ statistics
def test_paired_signflip_detects_consistent_improvement_and_ignores_noise():
    p, _ = e10.paired_signflip(np.full(60, 0.2), n_flips=20_000)
    assert p < 0.001
    rng = np.random.default_rng(1)
    noise = rng.normal(0, 1, 80); noise -= noise.mean()   # exactly zero mean
    p, p2 = e10.paired_signflip(noise, n_flips=20_000)
    assert p > 0.3
    p0, _ = e10.paired_signflip(np.zeros(40), n_flips=2_000)
    assert p0 == pytest.approx(1.0)


def test_top5_share_and_summarize_halves():
    R = np.array([5, 4, 3, 2, 1, 1, -1, -1, -2, 0.0])
    net, gross = e10.top5_share(R)
    assert net == pytest.approx(15 / 12) and gross == pytest.approx(15 / 16)
    dates = [f"2025-01-{i:02d}" for i in range(1, 11)]
    s = e10.summarize(R, dates, "2025-01-06")
    assert s["n_h1"] == 5 and s["n_h2"] == 5 and s["h1"] == pytest.approx(3.0) and s["h2"] == pytest.approx(-0.6)
    assert s["win"] == pytest.approx(0.6)


# ------------------------------------------------------------ integration on real NQ (fit window only)
@pytest.fixture(scope="module")
def days():
    if not HAVE_DATA:
        pytest.skip("real NQ csvs not found")
    return e10.load_days()


def test_window_guard_fit_window_only(days):
    assert days[0]["date"] >= e10.FIT_START and days[-1]["date"] <= e10.FIT_END
    assert len(days) > 450


def test_premarket_window_definition_is_04_00_to_09_29(days):
    import pandas as pd, glob
    NY = "America/New_York"
    D = days[100]["date"]
    parts = []
    for f in glob.glob(os.path.join(e10.AR, "t01-orb5", "fut", "NQ*.csv")):
        d = pd.read_csv(f)
        if d.empty: continue
        d["ts"] = pd.to_datetime(d["ts_ns"], unit="ns", utc=True).dt.tz_convert(NY); d["f"] = os.path.basename(f)
        parts.append(d[(d.ts >= pd.Timestamp(D + " 03:00", tz=NY)) & (d.ts < pd.Timestamp(D + " 09:31", tz=NY))])
    x = pd.concat(parts)
    k = x[x.ts >= pd.Timestamp(D + " 09:30", tz=NY)].groupby("f").volume.sum().idxmax()  # contract trading at the open
    x = x[x.f == k]
    pm = x[(x.ts >= pd.Timestamp(D + " 04:00", tz=NY)) & (x.ts < pd.Timestamp(D + " 09:30", tz=NY))]
    assert days[100]["pmh"] == pm.high.max() and days[100]["pml"] == pm.low.min()
    # a bar at 03:xx or 09:30 must not leak in
    assert pm.ts.min() >= pd.Timestamp(D + " 04:00", tz=NY) and pm.ts.max() <= pd.Timestamp(D + " 09:29", tz=NY)


def test_days_match_frozen_loader(days):
    ref = mnq.load_real()
    assert [a["date"] for a in ref] == [a["date"] for a in days]
    for a, b in zip(ref, days):
        assert np.array_equal(a["open"], b["open"], equal_nan=True)
        assert (a["pdh"] is None and b["pdh"] is None) or a["pdh"] == b["pdh"]
        assert (a["pdl"] is None and b["pdl"] is None) or a["pdl"] == b["pdl"]


def test_baseline_reproduces_frozen_mantra_result(days):
    T = e10.frozen_entries(days)
    base = e10.run_variant(days, T, None)
    R = np.array([r["R"] for r in base])
    assert len(R) == 105 and R.mean() == pytest.approx(0.3092672630906555, abs=1e-9)
    ref, _ = mnq.run_cell(days, e10.SETUP, "10:30", "2R", nshuf=0)
    assert np.allclose(R, [t["R"] for t in ref])


def test_levels_are_known_before_entry_bar_and_variants_only_change_level_days(days):
    T = e10.frozen_entries(days)
    assert all(t["i"] >= 6 for t in T)                 # entry at or after 09:36: OR5 done, premarket closed at 09:30
    base = e10.run_variant(days, T, None)
    v = e10.run_variant(days, T, 1.0)
    for b, r in zip(base, v):
        if r["tgt_label"] == "flat2R":
            assert b["R"] == r["R"]


# ------------------------------------------------------------ locked confirm helpers
def test_verdict_requires_every_clause():
    assert e10.verdict(40, 0.06, 0.02, 0.10, 0.004)[0] == "PASS"
    assert e10.verdict(29, 0.06, 0.02, 0.10, 0.004)[0] == "FAIL"      # n
    assert e10.verdict(40, 0.049, 0.02, 0.10, 0.004)[0] == "FAIL"     # margin
    assert e10.verdict(40, 0.06, -0.01, 0.10, 0.004)[0] == "FAIL"     # one half negative
    assert e10.verdict(40, 0.06, 0.02, 0.10, 0.011)[0] == "FAIL"      # p


def test_confirm_machinery_on_fit_window_fails_as_the_fit_numbers_say(days):
    out = e10.confirm(days, n_flips=20_000)           # machinery check only; the fit window confirms nothing
    assert out["n"] == 105 and out["verdict"] == "FAIL" and out["diff"] < 0


def test_thin_session_rule_keeps_fit_window_days(days):
    thin = e10.load_days(min_open_bars=55)
    assert {a["date"] for a in thin} <= {a["date"] for a in days}
    assert len(days) - len(thin) <= 3                 # drops at most a few half-day style sessions
