"""SPEC3 verification: market structure, order block = last red before HH,
retest strength classification, structure-intact gate."""
from vanquish_bot import Candle, MarketStructure, check_retest_type, detect_order_block_setup


def c(ts, o, h, l, cl):
    return Candle(timestamp=ts, open=o, high=h, low=l, close=cl, volume=1000)


# Uptrend: swing high at 101 (idx1), red pullback candle (idx3, the order block),
# then leg up making a higher high 102.5 (idx5).
BASE = [
    c("09:31", 100.0, 100.8, 99.8, 100.7),
    c("09:32", 100.7, 101.0, 100.5, 100.9),   # swing high 101.0
    c("09:33", 100.9, 100.95, 100.4, 100.5),
    c("09:34", 100.5, 100.6, 100.2, 100.3),   # LAST red before leg up = ORDER BLOCK (100.2-100.6)
    c("09:35", 100.3, 101.5, 100.3, 101.4),
    c("09:36", 101.4, 102.5, 101.3, 102.3),   # higher high 102.5 → structure break
    c("09:37", 102.3, 102.4, 101.8, 102.0),
]


def main():
    ms = MarketStructure()
    ms.update(BASE)
    assert ms.last_hh is not None and ms.last_hh[0] == 102.5, f"HH wrong: {ms.last_hh}"
    blocks = ms.get_valid_order_blocks(BASE, "bullish")
    assert blocks and blocks[0].timestamp == "09:34", "order block must be LAST red before HH"
    print(f"Order block found: {blocks[0].low}-{blocks[0].high} at {blocks[0].timestamp} (last red before HH 102.5)")

    block = blocks[0]
    # Retest classification
    wick = c("09:38", 100.9, 101.0, 100.5, 100.95)     # wick dips into block, body above
    partial = c("09:38", 100.5, 101.0, 100.4, 100.9)   # body opens inside block
    full = c("09:38", 100.55, 100.6, 100.2, 100.25)    # whole body inside block
    none = c("09:38", 101.0, 101.5, 100.8, 101.4)      # never touches block
    assert check_retest_type(block, wick, "bullish") == "wick_only"
    assert check_retest_type(block, partial, "bullish") == "partial_body"
    assert check_retest_type(block, full, "bullish") == "full_body"
    assert check_retest_type(block, none, "bullish") == "not_retesting"
    print("Retest types: wick_only / partial_body / full_body / not_retesting — all correct")

    # Setup fires on wick retest
    b, retest, note = detect_order_block_setup(BASE[:-1] + [wick], "bullish")
    assert b is not None and retest == "wick_only", note
    print(f"Setup detected: {note}")

    # Structure broken: candle closes below block low → no valid order block
    broken = BASE + [c("09:39", 100.5, 100.5, 99.5, 99.8)]  # close 99.8 < block low 100.2
    b, retest, note = detect_order_block_setup(broken + [wick], "bullish")
    assert b is None, "must not fire after structure break"
    print(f"Structure-broken gate works: {note}")

    print("\nAll SPEC3 checks passed.")


if __name__ == "__main__":
    main()
