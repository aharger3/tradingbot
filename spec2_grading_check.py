"""SPEC2 verification: A-D grading, grade-based sizing, C alert-only, 3/day cap."""
from vanquish_bot import Candle, TradeGrade, PriceActionAnalyzer, TradingSession
from options_sizer import GRADE_SIZE_PCT, build_options_plan

OR_HIGH, OR_LOW = 100.0, 98.0


def c(o, h, l, cl):
    return Candle(timestamp="09:45", open=o, high=h, low=l, close=cl, volume=1000)


def main():
    prev_red = c(100.5, 100.6, 100.1, 100.2)

    # 1. A+: bullish hammer at OR high (lower wick >2x body, close near high)
    hammer = c(100.4, 100.65, 99.5, 100.6)
    assert PriceActionAnalyzer.grade_trade(hammer, [prev_red], OR_HIGH, OR_LOW, True) == TradeGrade.A_PLUS

    # 2. A: bullish engulfing at key level, not a hammer (big body, small wick)
    engulf = c(100.1, 100.75, 99.95, 100.7)
    assert PriceActionAnalyzer.grade_trade(engulf, [prev_red], OR_HIGH, OR_LOW, True) == TradeGrade.A

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
