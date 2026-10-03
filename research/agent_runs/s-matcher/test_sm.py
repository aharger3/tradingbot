"""pytest tests for s-matcher: decision-time-only features, honest sim, reserved-window guard, walk-forward split."""
import os, sys
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sm_features as F
import sm_data as D
import sm_fit as FIT


def synth_day(seed=0, base=100.0, n=420, start=240):
    rng = np.random.default_rng(seed)
    d = F.empty_day()
    px = base
    for m in range(start, start + n):
        o = px
        c = o + rng.normal(0, 0.15)
        h = max(o, c) + abs(rng.normal(0, 0.08))
        l = min(o, c) - abs(rng.normal(0, 0.08))
        d["O"][m], d["H"][m], d["L"][m], d["C"][m], d["V"][m] = o, h, l, c, 1000 + rng.integers(0, 500)
        px = c
    return d


def test_features_use_no_future_bars():
    day, prev = synth_day(1), synth_day(2)
    m = 600
    base = F.features_at(day, prev, m, 1, 99.0)
    cut = {k: v.copy() for k, v in day.items()}
    for k in cut:                      # destroy every bar after the signal bar
        cut[k][m + 1:] = np.nan
    again = F.features_at(cut, prev, m, 1, 99.0)
    for k in F.FEATURES:
        a, b = base[k], again[k]
        assert (np.isnan(a) and np.isnan(b)) or a == b, k
    wild = {k: v.copy() for k, v in day.items()}
    for k in "OHLC":                   # and scramble the future instead of deleting it
        wild[k][m + 1:] = wild[k][m + 1:] * 3 + 50
    third = F.features_at(wild, prev, m, 1, 99.0)
    for k in F.FEATURES:
        a, b = base[k], third[k]
        assert (np.isnan(a) and np.isnan(b)) or a == b, k


def test_features_populated_and_mirrored():
    day, prev = synth_day(3), synth_day(4)
    f = F.features_at(day, prev, 600, 1, 99.0)
    assert all(np.isfinite(f[k]) for k in F.FEATURES if k != "bars_since_or_break"), f
    short = F.features_at(day, prev, 600, -1, 101.0)
    assert short["is_long"] == 0.0 and np.isfinite(short["mom5_atr"])


def test_prior_day_only_from_previous_session():
    day, prev = synth_day(5), synth_day(6)
    a = F.features_at(day, prev, 600, 1, 99.0)
    prev2 = {k: v.copy() for k, v in prev.items()}
    prev2["H"][F.RTH0:F.RTH1] += 5.0   # change yesterday's highs
    b = F.features_at(day, prev2, 600, 1, 99.0)
    assert a["room_pd_atr"] != b["room_pd_atr"]
    assert a["mom5_atr"] == b["mom5_atr"]


def _flat(px=100.0):
    d = F.empty_day()
    for m in range(F.RTH0, F.RTH1):
        d["O"][m] = d["H"][m] = d["L"][m] = d["C"][m] = px
        d["V"][m] = 100
    return d


def test_sim_target_stop_time_and_costs():
    d = _flat()
    m = 600
    # long, stop 99, fill 100.01 -> risk 1.01, 2R target 102.03; make bar m+3 trade through it
    d["H"][m + 3] = 102.5
    r, how = F.simulate(d, m, 1, 99.0)
    assert how == "tgt" and abs(r - ((2 * 1.01 - 0.01) / 1.01)) < 1e-9
    d2 = _flat()
    d2["L"][m + 2] = 98.5
    r2, how2 = F.simulate(d2, m, 1, 99.0)
    assert how2 == "stop" and r2 < -1.0
    d3 = _flat()
    r3, how3 = F.simulate(d3, m, 1, 99.0)
    assert how3 == "time" and r3 < 0          # flat tape: only slippage + commission
    # stop and target in the same bar -> stop wins
    d4 = _flat()
    d4["H"][m + 1], d4["L"][m + 1] = 103.0, 98.0
    assert F.simulate(d4, m, 1, 99.0)[1] == "stop"
    # degenerate stop (above fill for a long) is skipped, not traded
    assert F.simulate(_flat(), m, 1, 100.5) is None


def test_reserved_window_never_loaded():
    n = 4
    rows = []
    for dt in ["2024-09-23", "2024-09-24", "2024-09-25", "2024-09-26", "2024-09-27", "2024-09-30"]:
        base = int(pd.Timestamp(dt + " 09:30", tz="America/New_York").tz_convert("UTC").value)
        for k in range(n):
            rows.append(dict(ts_ns=base + k * 60_000_000_000, open=1.0, high=2.0, low=0.5, close=1.5,
                             volume=10, contract="NQZ4"))
    nq = D.build_nq_days(pd.DataFrame(rows))
    assert nq and min(nq) > D.B1_END
    assert "2024-09-26" not in nq        # its prior session (09-25) is inside the reserved window
    assert "2024-09-27" in nq


def test_walk_forward_splits_are_strictly_forward():
    dates = pd.Series(pd.date_range("2024-10-01", periods=200, freq="D").strftime("%Y-%m-%d"))
    folds = FIT.wf_folds(dates, n_folds=4, first=0.4)
    assert len(folds) == 4
    for tr, te in folds:
        assert dates[tr].max() < dates[te].min()
        assert not set(tr) & set(te)


def test_fit_pipeline_recovers_planted_signal():
    rng = np.random.default_rng(0)
    n = 400
    X = pd.DataFrame({"a": rng.normal(size=n), "b": rng.normal(size=n), "c": rng.normal(size=n)})
    y = (X["a"] + 0.3 * rng.normal(size=n) > 0.5).astype(int).to_numpy()
    days = pd.Series(pd.date_range("2024-10-01", periods=n, freq="D").strftime("%Y-%m-%d"))
    auc = FIT.walk_forward_auc(X, y, days, model="l1", n_folds=4, first=0.4)
    assert auc["auc"] > 0.85
    noise = rng.integers(0, 2, n)
    assert FIT.walk_forward_auc(X, noise, days, model="tree", n_folds=4, first=0.4)["auc"] < 0.62
