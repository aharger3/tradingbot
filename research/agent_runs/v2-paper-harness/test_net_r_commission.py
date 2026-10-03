"""R-LR1: paper_replay's net_R must subtract COMMISSION_RT_USD / risk_usd (it used to copy gross_R).
Plain script, asserts, prints TESTS OK. Run: python research/agent_runs/v2-paper-harness/test_net_r_commission.py
No market data needed. The 105-trade parity run needs the PC (see PR body)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import paper_replay  # noqa: E402


def test_one_r_winner_at_200_risk_nets_09938():
    assert paper_replay.COMMISSION_RT_USD == 1.24
    got = paper_replay.net_R(1.0, 200.0)
    assert abs(got - 0.9938) < 1e-9, got
    print("test_one_r_winner_at_200_risk_nets_09938 OK")


def test_loser_and_2r_target_and_scaling():
    assert abs(paper_replay.net_R(-1.0, 200.0) - (-1.0062)) < 1e-9
    # MNQ 1 contract: stop 2.5 pts -> risk $5.00 -> a 2R target nets 2 - 1.24/5
    risk = 2.5 * paper_replay.MNQ_USD_PT
    assert abs(paper_replay.net_R(2.0, risk) - (2.0 - 1.24 / 5.0)) < 1e-9
    # commission cost shrinks as risk grows, and is always strictly positive
    assert paper_replay.net_R(0.0, 100.0) > paper_replay.net_R(0.0, 50.0)
    assert paper_replay.net_R(0.0, 50.0) < 0.0
    print("test_loser_and_2r_target_and_scaling OK")


def test_matches_orb1m_run_trade_formula():
    # orb1m.run_trade: R = (pnl_pts*usd - comm) / (dist*usd); same thing with gross_R = pnl_pts/dist.
    usd, comm, dist, pnl_pts = 2.0, 1.24, 3.0, 6.0
    ref = (pnl_pts * usd - comm) / (dist * usd)
    assert abs(paper_replay.net_R(pnl_pts / dist, dist * usd) - ref) < 1e-12
    print("test_matches_orb1m_run_trade_formula OK")


if __name__ == "__main__":
    test_one_r_winner_at_200_risk_nets_09938()
    test_loser_and_2r_target_and_scaling()
    test_matches_orb1m_run_trade_formula()
    print("TESTS OK")
