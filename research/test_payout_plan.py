import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from payout_plan import LUCID, TOPSTEP, simulate_payouts, render_md, summarize  # noqa: E402


def test_lucid_cap_binds():
    # 5 x $1,000 days -> $5K profit; 50% = $2.5K > $2K cap -> request $2K, trader $1.8K
    p = simulate_payouts([1000.0] * 5, LUCID)
    assert len(p) == 1 and p[0]["session"] == 5
    assert p[0]["gross"] == 2000.0
    assert p[0]["trader"] == 1800.0
    assert abs(p[0]["net"] - 1260.0) < 1e-9          # 30% tax set-aside


def test_topstep_5k_cap_binds():
    # 5 x $3,000 days -> $15K profit; 50% = $7.5K > $5K cap
    p = simulate_payouts([3000.0] * 5, TOPSTEP, trail=1e9)
    assert p[0]["gross"] == 5000.0
    assert p[0]["trader"] == 4500.0
    # Lucid on the same path is held to its $2K cap
    assert simulate_payouts([3000.0] * 5, LUCID, trail=1e9)[0]["gross"] == 2000.0


def test_zero_profit_path_no_payout():
    for rules in (LUCID, TOPSTEP):
        assert simulate_payouts([0.0] * 120, rules) == []
    s = summarize([[0.0] * 120], LUCID)
    assert s["paid"] == 0 and s["cum1_mean"] == 0


def test_md_has_paper_header():
    s = summarize([[1000.0] * 10], LUCID)
    md = render_md([("B", s)], "B", 1, "j")
    assert "PAPER/SIM" in md.splitlines()[6]
