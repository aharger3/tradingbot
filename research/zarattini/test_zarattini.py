import hashlib
from pathlib import Path
import numpy as np
import zarattini as Z

HERE = Path(__file__).parent


def sess(bars):
    """bars: list of (o, h, l, c) starting 09:30, one per minute."""
    a = np.array(bars, dtype=float)
    return dict(tk="NQZ5", tod=np.arange(570, 570 + len(a)), o=a[:, 0], h=a[:, 1], l=a[:, 2], c=a[:, 3])


# opening 5 bars: 100 -> 110, low 100, high 110 (bullish)
OPEN = [(100, 102, 100, 102), (102, 104, 101, 104), (104, 106, 103, 106), (106, 108, 105, 108), (108, 110, 107, 110)]


def test_bt_unchanged():
    assert hashlib.sha256((HERE / "bt.py").read_bytes()).hexdigest().upper() == \
        "D9DE2165191EB4DEC30FECFF3AB13718075FA6C33C768EDC3940FB95CD22632E"


def test_stop_is_minus_one_R_gross():
    S = sess(OPEN + [(110, 111, 99, 99)])
    t = Z.trade(S, 1, 0, net=False)
    assert t["why"] == "stop" and abs(t["R"] + 1) < 1e-9


def test_slippage_worsens_stop():
    S = sess(OPEN + [(110, 111, 99, 99)])
    g, s = Z.trade(S, 1, 0, net=False)["R"], Z.trade(S, 1, 2, net=False)["R"]
    assert s < g


def test_target_ten_R():
    # entry 110, stop 100, dist 10 -> target 210 (needs trade-through by 1 tick)
    S = sess(OPEN + [(110, 112, 109, 111), (111, 220, 110, 215)])
    t = Z.trade(S, 1, 0, net=False)
    assert t["why"] == "tgt" and abs(t["R"] - 10) < 1e-9


def test_close_exit():
    S = sess(OPEN + [(110, 112, 109, 111), (111, 116, 110, 115)])
    t = Z.trade(S, 1, 0, net=False)
    assert t["why"] == "close" and abs(t["R"] - 0.5) < 1e-9


def test_short_mirror():
    down = [(110, 110, 108, 108), (108, 108, 106, 106), (106, 106, 104, 104), (104, 104, 102, 102), (102, 102, 100, 100)]
    S = sess(down + [(100, 111, 99, 111)])
    t = Z.trade(S, -1, 0, net=False)
    assert t["why"] == "stop" and abs(t["R"] + 1) < 1e-9


def test_breakeven_interp():
    assert Z.breakeven([0, 1, 2], [0.2, 0.1, -0.1]) == 1.5
    assert Z.breakeven([0, 1], [-0.1, -0.2]) is None
