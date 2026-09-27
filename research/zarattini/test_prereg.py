# Locks the OOS pre-registration bar (prereg.json) before Databento data lands.
# (a) prereg.json params must equal robust.py's DEF (the defaults asserted to reproduce zarattini.book).
# (b) gate() must return PASS/FAIL correctly on 3 fixture ledgers.
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import robust as R  # noqa: E402  (defaults asserted at import time to reproduce zarattini.book)

PREREG = json.loads((HERE / "prereg.json").read_text())


def gate(ledger, criteria=None):
    """PASS/FAIL per prereg.json's pass_criteria: R/trade > 0, t >= t_stat_gte, top-5 share < top5_share_lt."""
    criteria = criteria or PREREG["pass_criteria"]
    r = np.asarray(ledger, dtype=float)
    n = len(r)
    r_trade = float(r.mean())
    t = float(r_trade / (r.std(ddof=1) / math.sqrt(n))) if n > 1 else 0.0
    total = r.sum()
    top5 = np.sort(r)[-5:].sum() if n >= 5 else total
    top5_share = float(top5 / total) if total != 0 else math.inf
    ok = (r_trade > criteria["R_per_trade_gt"]) and (t >= criteria["t_stat_gte"]) and (top5_share < criteria["top5_share_lt"])
    return "PASS" if ok else "FAIL"


def test_prereg_params_match_robust_defaults():
    assert PREREG["params"] == R.DEF


def test_prereg_rule_is_nq925():
    assert PREREG["rule"] == "NQ925"


# --- 3 fixture ledgers ---

LEDGER_PASS = [
    0.30, 0.45, 0.50, 0.35, 0.40, 0.42, 0.38, 0.41, 0.39, 0.44,
    0.36, 0.43, 0.37, 0.46, 0.33, 0.48, 0.34, 0.47, 0.32, 0.49,
    0.31, 0.50, 0.40, 0.40, 0.40, 0.40, 0.40, 0.40, 0.40, 0.40,
]  # steady +R, low variance, no fat tail -> PASS

LEDGER_FAIL_FLAT = [
    1, -1, 2, -2, 1.5, -1.5, 0.5, -0.5, 3, -3,
    2, -2, 1, -1, 0.8, -0.8, 1.2, -1.2, 0.3, -0.3,
    2.5, -2.5, 1, -1, 0.6, -0.6, 0.9, -0.9, 1.1, -1.1,
]  # symmetric, R/trade == 0 -> fails R>0 -> FAIL

LEDGER_FAIL_TOPHEAVY = [-0.1] * 25 + [10.0] * 5  # R/trade>0, t ok, but top-5 = 105% of total R -> FAIL


def test_gate_pass():
    assert gate(LEDGER_PASS) == "PASS"


def test_gate_fail_flat_mean():
    assert gate(LEDGER_FAIL_FLAT) == "FAIL"


def test_gate_fail_top5_concentration():
    assert gate(LEDGER_FAIL_TOPHEAVY) == "FAIL"
