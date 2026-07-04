"""SPEC0 gaps verification: true PDH/PDL as B&R levels + HTF bias grade gating."""
from signal_runner import SignalRunner
from vanquish_bot import Candle, TradeGrade, PriceActionAnalyzer


def c(ts, o, h, l, cl):
    return Candle(timestamp=ts, open=o, high=h, low=l, close=cl, volume=1000)


def make_runner(pdh=None, pdl=None, bias=None):
    r = SignalRunner(post_to_discord=False, log_signals=False)
    r.pdh, r.pdl, r.htf_bias = pdh, pdl, bias
    return r


# Session: OR = 100.4-99.6 (first 5 candles), then breakout above PDH 101 and
# hammer retest of it. OR high stays untouched by the retest candle.
CANDLES = [
    c("09:31", 100.0, 100.4, 99.8, 100.2),
    c("09:32", 100.2, 100.3, 99.9, 100.1),
    c("09:33", 100.1, 100.2, 99.6, 100.0),
    c("09:34", 100.0, 100.3, 99.9, 100.2),
    c("09:35", 100.2, 100.4, 100.0, 100.3),
    c("09:36", 100.3, 101.6, 100.3, 101.5),   # displacement through PDH 101
    c("09:37", 101.5, 101.8, 101.4, 101.7),
    c("09:38", 101.6, 101.75, 100.9, 101.7),  # hammer retest of PDH (wick to 100.9)
]


def br_signals(r):
    r.candles = CANDLES
    return [s for s in r.detect_signals() if s["stop_level_name"] in ("PDH", "OR high")]


def main():
    # 1. Without PDH set: no PDH-level signal exists
    sigs = br_signals(make_runner())
    assert not any(s["stop_level_name"] == "PDH" for s in sigs), "PDH signal without levels?"

    # 2. With true PDH 101: B&R long fires at PDH with stop at 101
    sigs = br_signals(make_runner(pdh=101.0, pdl=97.0))
    pdh_sigs = [s for s in sigs if s["stop_level_name"] == "PDH"]
    assert pdh_sigs and pdh_sigs[0]["stop"] == 101.0, f"PDH B&R missing: {sigs}"
    print(f"PDH B&R fires: entry {pdh_sigs[0]['entry']}, stop {pdh_sigs[0]['stop']}, grade {pdh_sigs[0]['grade']}")

    # 3. HTF gating on grade_trade directly
    hammer = CANDLES[-1]
    lookback = CANDLES[-6:-1]
    g_none = PriceActionAnalyzer.grade_trade(hammer, lookback, 101.0, 97.0, True)
    g_up = PriceActionAnalyzer.grade_trade(hammer, lookback, 101.0, 97.0, True, htf_bias="bullish")
    g_neut = PriceActionAnalyzer.grade_trade(hammer, lookback, 101.0, 97.0, True, htf_bias="neutral")
    g_opp = PriceActionAnalyzer.grade_trade(hammer, lookback, 101.0, 97.0, True, htf_bias="bearish")
    assert g_none == g_up == TradeGrade.A_PLUS, (g_none, g_up)
    assert g_neut == TradeGrade.B, g_neut          # A+/A capped at B when HTF neutral
    assert g_opp == TradeGrade.D, g_opp            # counter-trend = skip
    print(f"HTF gating: aligned {g_up.value} / unknown {g_none.value} / neutral {g_neut.value} / opposed {g_opp.value}")

    # 4. Opposed-bias signal gets routed to skip (D) end to end
    sigs = br_signals(make_runner(pdh=101.0, pdl=97.0, bias="bearish"))
    assert not any(s["stop_level_name"] == "PDH" for s in sigs), "counter-trend signal not filtered"
    print("Counter-trend PDH signal filtered end-to-end")

    print("\nAll SPEC0-gap checks passed.")


if __name__ == "__main__":
    main()
