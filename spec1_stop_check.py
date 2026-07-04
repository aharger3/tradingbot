"""SPEC1 verification: old stop (entry candle wick) vs new stop (key level).

5 hypothetical scenarios. Asserts new stops are wider (room to breathe) and
the min-stop filter behaves per spec.
"""
from signal_runner import SignalRunner

MAX_LOSS = 1000.0
DELTA = 0.5


def contracts(stock_risk: float) -> int:
    premium_risk = max(stock_risk * DELTA, 0.05)
    return int(MAX_LOSS // (premium_risk * 100))


# (name, entry, key_level_stop, entry_candle_wick)
SCENARIOS = [
    ("META B&R long, tight wick",      611.40, 610.80, 611.34),
    ("TSLA B&R long",                  440.50, 439.60, 440.44),
    ("NVDA One Candle long",           215.30, 214.20, 215.22),
    ("SPY B&R short",                  749.10, 750.20, 749.18),
    ("TSLA 84% reclaim",               441.00, 440.10, 440.94),
]


def main():
    r = SignalRunner(post_to_discord=False, log_signals=False)
    print(f"{'Scenario':32} {'old stop':>9} {'new stop':>9} {'old risk':>9} {'new risk':>9} {'old #':>6} {'new #':>6}")
    for name, entry, key_stop, wick in SCENARIOS:
        old_risk = abs(entry - wick)
        new_risk = abs(entry - key_stop)
        assert new_risk > old_risk, f"{name}: new stop not wider"
        # old wick stop would demand absurd contract counts (instant stop-out territory)
        assert contracts(old_risk) > contracts(new_risk), f"{name}: sizing didn't shrink"
        print(f"{name:32} {wick:9.2f} {key_stop:9.2f} {old_risk:9.2f} {new_risk:9.2f} {contracts(old_risk):6d} {contracts(new_risk):6d}")

    # Min-stop filter per spec: skip only if stock risk <0.5% AND premium risk <$0.20
    assert not r._min_viable_stop(611.40, 611.34, "call")   # $0.06 risk → skip
    assert r._min_viable_stop(611.40, 610.80, "call")       # $0.60 → premium $0.30 → viable
    assert r._min_viable_stop(100.00, 99.40, "call")        # 0.6% → viable
    assert not r._min_viable_stop(100.00, 100.00, "call")   # entry==stop → skip
    print("\nAll SPEC1 checks passed.")


if __name__ == "__main__":
    main()
