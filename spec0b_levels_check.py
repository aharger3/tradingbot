"""SPEC0 gaps verification: true PDH/PDL as B&R levels + HTF bias grade gating."""
import omen_bot
from signal_runner import SignalRunner
from omen_bot import Candle, TradeGrade, PriceActionAnalyzer


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
    # B-04 / ticket 23 (2026-09-05): the opposed-bias veto has no author (rule
    # ballot batch 02 c6: "we dont have any higher timeframe bias yet") but the
    # shipped default is ON -- os.getenv("HTF_BIAS_VETO", "1") -- and has been
    # since P16/W3 (71f39851, 2026-08-27); the docstring correction f959cff5
    # (2026-08-28) already says so ("SHIPPED DEFAULT"). An opposed hour hard-
    # vetoes to D by default; HTF_BIAS_VETO=0 lifts it back to PA-alone
    # grading. This assertion previously asserted the opposite (veto OFF by
    # default) and crashed -- see omen-rulebook.md's dated correction under
    # "Higher-timeframe bias is not a rule, so it is not a veto" for why: an
    # ancestor commit (d0a38dc9, OMEN 8.0 R4) shipped a default-OFF
    # HTF_GRADE_VETO for part of one day, but its omen_bot.py/signal_runner.py
    # hunks are not in this tree (grep -c HTF_GRADE_VETO omen_bot.py == 0) --
    # dropped by the 2026-09-03 history rewrite. test_htf_bias_veto_default.py
    # asserts the same ON default and passes; this file now agrees with it.
    assert g_opp == TradeGrade.D, g_opp            # veto ON by default: opposed hour vetoes to D
    orig_veto = omen_bot.HTF_BIAS_VETO
    omen_bot.HTF_BIAS_VETO = False
    try:
        g_opp_novet = PriceActionAnalyzer.grade_trade(hammer, lookback, 101.0, 97.0, True, htf_bias="bearish")
    finally:
        omen_bot.HTF_BIAS_VETO = orig_veto
    assert g_opp_novet == TradeGrade.A_PLUS, g_opp_novet  # HTF_BIAS_VETO=0 lifts the veto, grades on PA alone
    print(f"HTF gating: aligned {g_up.value} / unknown {g_none.value} / neutral {g_neut.value} / "
          f"opposed (veto on, default) {g_opp.value} / opposed (HTF_BIAS_VETO=0) {g_opp_novet.value}")

    # 4. An opposed-bias signal is still a row in detect_signals()'s output
    # even when it hard-vetoes to D -- the veto downgrades the grade, it does
    # not remove the row (nothing in detect_signals() filters by grade; T10
    # X_LIFT, default "clean", can independently rescue an X-graded row's
    # grade back up, which is a separate, already-shipped mechanism this file
    # does not test).
    sigs = br_signals(make_runner(pdh=101.0, pdl=97.0, bias="bearish"))
    assert any(s["stop_level_name"] == "PDH" for s in sigs), "counter-trend signal unexpectedly absent from detect_signals()"
    print("Counter-trend PDH signal still present in detect_signals() (grade reflects the veto, row is not dropped)")

    print("\nAll SPEC0-gap checks passed.")


if __name__ == "__main__":
    main()
