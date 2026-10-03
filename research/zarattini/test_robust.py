import numpy as np
import zarattini as Z
import robust as RB
from test_zarattini import sess, OPEN


def test_default_trade_matches_zarattini():
    for bars in (OPEN + [(110, 111, 99, 99)], OPEN + [(110, 112, 109, 111), (111, 220, 110, 215)], OPEN + [(110, 116, 110, 115)]):
        S = sess(bars)
        for s in (0, 1, 4):
            a, b = RB.trade(S, 5, 10, 1.0, s), Z.trade(S, 1, s)
            assert abs(a["R"] - b["R"]) < 1e-12 and a["why"] == b["why"]


def test_stop_mult_widens_stop():
    S = sess(OPEN + [(110, 111, 99, 99)])          # dist 10 -> k=1.2 stop at 98, not hit by low 99
    assert RB.trade(S, 5, 10, 1.2, 0, net=False)["why"] == "close"


def test_mnq_sizing_skips_wide_and_rounds():
    assert RB.mnq_usd(dict(dist=120.0, pts=10.0))[1] == 0          # 1 MNQ risks $240 > $200 budget
    u, n = RB.mnq_usd(dict(dist=40.0, pts=-40.0))
    assert n == 2 and abs(u - 2 * (-80 - 1.24)) < 1e-9


def test_prop_gate():
    assert RB.prop_gate([1000, 0, 1000, 1000], 3000, 2000, 1000) == ("pass", 3)
    assert RB.prop_gate([500, -1000], 3000, 2000, 1000) == ("bust", 2)
    assert RB.prop_gate([1500, -900, -900, -300], 3000, 2000, 1000) == ("bust", 4)
    assert RB.prop_gate([100], 3000, 2000, 1000) == ("open", 1)
