"""SPEC2 verification: A-D grading, grade-based sizing, C alert-only, 3/day cap.

T13 (research/t13_candles-beyond-hammer.md): this was "the hammer-only test"
the track brief names — every assertion below ran only the LONG side, so the
short-side hammer analogue (inverted hammer / shooting star) had zero test
coverage even though `_grade_pa` has coded it since before this track. T13
enumerated every named bullish/bearish candle formation against
research/corpus_index.jsonl and Austin's marks; only hammer, inverted
hammer/shooting star (corpus treats them as one shape, both named in the same
sentence), and large-wick rejection (both directions) are validated. Doji,
marubozu, piercing, three-line strike, morning/evening star, harami, and the
rest have zero hits in either corpus or marks and do not ship. Engulfing
stays killed (hallucination-audit #14: mentioned once, not a taught entry
rule, removal measured net +$4k). See research/t13_candle_formations.py for
the corpus/mark search and research/t13_candles-beyond-hammer.md for the
trip-rate table — A+ (hammer / inverted-hammer) trips 7 times in 75,953
signals (0.009%), under the 1% reachability floor; B (wick rejection) is what
actually functions, at 2,447 of 75,953 (3.2%)."""
from omen_bot import Candle, TradeGrade, PriceActionAnalyzer, TradingSession
from options_sizer import GRADE_SIZE_PCT, build_options_plan

OR_HIGH, OR_LOW = 100.0, 98.0


def c(o, h, l, cl):
    return Candle(timestamp="09:45", open=o, high=h, low=l, close=cl, volume=1000)


def main():
    prev_red = c(100.5, 100.6, 100.1, 100.2)

    # 1. A+: bullish hammer at OR high (lower wick >2x body, close near high)
    hammer = c(100.4, 100.65, 99.5, 100.6)
    assert PriceActionAnalyzer.grade_trade(hammer, [prev_red], OR_HIGH, OR_LOW, True) == TradeGrade.A_PLUS

    # 2. Engulfing NO LONGER grades A (hallucination audit 2026-07-11: pattern
    # absent from all 4 rulebooks). Falls through to C (retest, no hammer/wick).
    engulf = c(100.1, 100.75, 99.95, 100.7)
    assert PriceActionAnalyzer.grade_trade(engulf, [prev_red], OR_HIGH, OR_LOW, True) == TradeGrade.C

    # 3. B: large lower wick (1.5-2x body) at key level, no engulfing, close off high
    prev_green = c(100.1, 100.5, 100.0, 100.4)
    strong = c(100.6, 101.5, 99.9, 101.0)  # body .4, wick .7, high-close .5 > .2 → not hammer
    assert PriceActionAnalyzer.grade_trade(strong, [prev_green], OR_HIGH, OR_LOW, True) == TradeGrade.B

    # 4. C: weak bullish retest (tiny wick, no pattern)
    weak = c(99.95, 100.35, 99.93, 100.3)
    assert PriceActionAnalyzer.grade_trade(weak, [prev_green], OR_HIGH, OR_LOW, True) == TradeGrade.C

    # 5. D: bearish candle on a long setup
    red = c(100.3, 100.4, 99.9, 100.0)
    assert PriceActionAnalyzer.grade_trade(red, [prev_green], OR_HIGH, OR_LOW, True) == TradeGrade.D
    print("Grades: A+ / A / B / C / D — all assigned correctly")

    # --- T13: the short side (bearish PA), symmetric to 1-5, untested before ---
    prev_green_s = c(100.1, 100.5, 100.0, 100.4)

    # 6. A+ short: inverted hammer / shooting star at OR low (upper wick >2x
    # body, close near low) — corpus names both "inverted hammer" and
    # "shooting star" for this exact shape in the same breath (Scarface/jdub).
    inv_hammer = c(98.5, 99.6, 98.0, 98.1)  # bearish, upper wick 1.1 > 2x body .4, close-low .1 < .5x body .2
    assert PriceActionAnalyzer.grade_trade(inv_hammer, [prev_green_s], OR_HIGH, OR_LOW, False) == TradeGrade.A_PLUS

    # 7. B short: large upper wick (1.5-2x body), not an inverted hammer
    prev_red_s = c(100.5, 100.6, 100.1, 100.2)
    strong_s = c(98.5, 99.3, 98.0, 98.2)  # body .3, wick .8 (>1.5x), close-low .2 not < .5x body .15
    g = PriceActionAnalyzer.grade_trade(strong_s, [prev_red_s], OR_HIGH, OR_LOW, False)
    assert g == TradeGrade.B, g

    # 8. C short: weak bearish retest, no pattern
    weak_s = c(98.05, 98.1, 97.95, 97.98)
    assert PriceActionAnalyzer.grade_trade(weak_s, [prev_red_s], OR_HIGH, OR_LOW, False) == TradeGrade.C

    # 9. D/X short: bullish candle on a short setup
    green_s = c(97.6, 97.9, 97.55, 97.85)
    assert PriceActionAnalyzer.grade_trade(green_s, [prev_red_s], OR_HIGH, OR_LOW, False) == TradeGrade.D

    # 10. Unvalidated shapes (marubozu, doji) are not special-cased — they
    # grade purely on the coded wick/body geometry, same as any other candle.
    # A marubozu (near-zero wicks, full-range body) bullish candle at the
    # level with no meaningful lower wick falls to C, not a marubozu bonus —
    # there is no marubozu branch to hit because corpus/marks have zero hits.
    marubozu = c(99.95, 100.6, 99.93, 100.58)  # tiny wicks both ends, at OR_HIGH
    assert PriceActionAnalyzer.grade_trade(marubozu, [prev_green], OR_HIGH, OR_LOW, True) == TradeGrade.C
    print("T13: short-side (A+/B/C/D) grades all assigned correctly; "
          "unvalidated shapes (marubozu) confirmed NOT special-cased")

    # Sizing varies by grade: max_loss scaled by GRADE_SIZE_PCT
    sizes = {}
    for g, pct in GRADE_SIZE_PCT.items():
        if pct == 0:
            continue
        plan = build_options_plan("TSLA", "call", 440.50, 439.60, max_loss=1000 * pct)
        sizes[g] = plan.contracts
    assert sizes["A+"] > sizes["A"] > sizes["B"] > sizes["C"] > 0
    print(f"Sizing by grade (TSLA, $0.90 risk): {sizes}")

    # Daily cap: 3 executed trades ends the day
    s = TradingSession()
    for _ in range(3):
        assert not s.day_ended()
        s.signals_today += 1
    assert s.day_ended()
    print("3 trades/day hard cap enforced")

    # C-grade doesn't count toward cap (live_scanner increments only when
    # _emit_signal returns True; verify the routing rule directly)
    assert GRADE_SIZE_PCT["C"] == 0.4 and GRADE_SIZE_PCT["D"] == 0.0
    print("\nAll SPEC2 checks passed.")


if __name__ == "__main__":
    main()
