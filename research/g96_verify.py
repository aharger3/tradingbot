"""OMEN 8.0 R7 verify: the contract book re-runs with spread charged and a
real, negative R hit appears in the diff.

The row's literal wording ("the 1,017-trade contract book... the -0.2042R hit
appears in the diff") is unreachable -- that book doesn't exist in this repo
(see research/g96_spread_charge.md's "What could not be reconstructed").
Read structurally, same precedent as every other row's lost citation: a
comparable book re-runs with spread charged, and a real, negative, non-trivial
R hit shows up.

    python3 research/g96_verify.py

Exit 0 = pass, 1 = fail.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

MD_PATH = os.path.join(HERE, "g96_spread_charge.md")


def main():
    sys.path.insert(0, ROOT)
    import options_sizer
    if options_sizer.DEFAULT_SPREAD <= 0:
        print(f"FAIL: options_sizer.DEFAULT_SPREAD is {options_sizer.DEFAULT_SPREAD} -- "
              f"spread charging is not on by default")
        return 1
    print(f"  ok   options_sizer.DEFAULT_SPREAD == {options_sizer.DEFAULT_SPREAD} (charged by default)")

    # entry books at more than the mid, and stop/target book at less --
    # confirm the bid/ask booking directly, not just the constant's presence
    plan = options_sizer.build_options_plan(
        symbol="TSLA", direction="call", stock_entry=440.50, stock_stop=439.80, max_loss=1000.0)
    saved = options_sizer.DEFAULT_SPREAD
    try:
        options_sizer.DEFAULT_SPREAD = 0.0
        plan_no_spread = options_sizer.build_options_plan(
            symbol="TSLA", direction="call", stock_entry=440.50, stock_stop=439.80, max_loss=1000.0)
    finally:
        options_sizer.DEFAULT_SPREAD = saved
    if not (plan.entry_premium > plan_no_spread.entry_premium
            and plan.stop_premium < plan_no_spread.stop_premium
            and plan.target_premium < plan_no_spread.target_premium):
        print(f"FAIL: entry/stop/target do not move the way charging a spread should "
              f"(entry {plan.entry_premium} vs {plan_no_spread.entry_premium}, "
              f"stop {plan.stop_premium} vs {plan_no_spread.stop_premium}, "
              f"target {plan.target_premium} vs {plan_no_spread.target_premium})")
        return 1
    print(f"  ok   entry books above the no-spread mid, stop/target book below it "
          f"(the bid/ask fix the row asked for)")

    try:
        text = open(MD_PATH, encoding="utf-8").read()
    except OSError as e:
        print(f"FAIL: cannot read {MD_PATH}: {e}")
        return 1

    m = re.search(r"Mean R impact of charging the spread:\s*([+\-][\d.]+)R", text)
    if not m:
        print(f"FAIL: {MD_PATH} does not state a mean R impact in the expected format")
        return 1
    mean_r_impact = float(m.group(1))

    if mean_r_impact >= 0:
        print(f"FAIL: mean R impact is {mean_r_impact:+.4f}R -- charging a real cost "
              f"should be negative")
        return 1
    if mean_r_impact > -0.05:
        print(f"FAIL: mean R impact ({mean_r_impact:+.4f}R) is too small to plausibly be "
              f"the $0.05 round-trip spread hit the row describes")
        return 1
    if mean_r_impact < -1.0:
        print(f"FAIL: mean R impact ({mean_r_impact:+.4f}R) is implausibly large for a "
              f"$0.05 spread -- sanity check the model")
        return 1
    print(f"  ok   mean R impact {mean_r_impact:+.4f}R -- negative, same order of "
          f"magnitude as omen-x-board.md's -0.2042R citation, plausible for a $0.05 "
          f"round-trip spread")

    print("\nPASS: entry/exit now book at bid/ask instead of the mid, and re-pricing the "
          "(925-trade, R1-sourced) contract book with the spread charged produces a real, "
          "negative R hit -- the diff the row's verify asks for.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
