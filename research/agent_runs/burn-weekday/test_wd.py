import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wd


def test_ism_rule_skips_holidays():
    assert "2024-09-03" in wd.CAL["ISM_M"]  # Sep 2 2024 = Labor Day
    assert "2025-01-02" in wd.CAL["ISM_M"]  # Jan 1 holiday
    assert "2025-01-06" in wd.CAL["ISM_S"]  # 3rd business day
    assert len(wd.CAL["ISM_M"]) == 25


def test_umich_prelim_is_friday():
    import pandas as pd
    assert all(pd.Timestamp(d).dayofweek == 4 for d in wd.UM_PRELIM)


def test_perm_p_detects_and_ignores():
    dates = [f"2025-01-{d:02d}" for d in range(1, 31)] * 2
    flag = lambda D: int(D[-2:]) % 2 == 0
    y_sig = np.array([5.0 if flag(d) else 0.0 for d in dates]) + np.random.default_rng(0).normal(0, 0.1, len(dates))
    d, p = wd.perm_p(dates, y_sig, flag)
    assert d > 4 and p < 0.01
    y_null = np.random.default_rng(1).normal(0, 1, len(dates))
    _, p0 = wd.perm_p(dates, y_null, flag)
    assert p0 > 0.05
