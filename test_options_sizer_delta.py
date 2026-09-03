"""OMEN 8.0 R6 checks. Plain asserts, no pytest:  python test_options_sizer_delta.py

`options_sizer.DEFAULT_DELTA` sizes every options contract count via
`premium_risk = stock_risk * delta_estimate`. It was 0.5 ("ATM ~= 0.5",
assumed, never measured); the spec says the measured delta is 0.42 and this
repo has no options chain to independently re-derive or refute that number
(see the fix's own comment in options_sizer.py and research/g95_delta_fix.md
for what could not be reconstructed). This file asserts:

  1. The shipped default is 0.42, not 0.5.
  2. `build_options_plan`'s reported `max_loss` and the ACTUAL dollar risk
     realized against the true (0.42) delta converge to the same number when
     delta_estimate == 0.42 -- they are the same formula, not two agreeing
     estimates -- and diverge in the specific, priceable direction (~16% under
     the budget) when delta_estimate is the old 0.5.
  3. The relationship is stock-risk-independent (a ratio, not an absolute):
     realized/reported == true_delta / delta_estimate exactly, mod integer
     contract-count rounding.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import options_sizer as os_
from options_sizer import build_options_plan, DEFAULT_DELTA

FAILS = []


def check(cond, label):
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}")
        FAILS.append(label)


def actual_risk(plan, true_delta):
    """What this plan's stop-out would REALLY cost if the option's actual
    premium move follows `true_delta` rather than whatever delta_estimate the
    plan itself was sized with. Mirrors build_options_plan's own formula
    (premium_risk -> per_contract_risk), applied to the SAME contract count
    the plan already committed to -- contracts don't get re-sized after the
    fact in real life."""
    stock_risk = abs(plan.stock_entry - plan.stock_stop)
    premium_risk = max(round(stock_risk * true_delta, 2), 0.05)
    return round(premium_risk * 100 * plan.contracts, 2)


TRUE_DELTA = 0.42  # the only value this repo has any citation for at all

# 1. shipped default
check(DEFAULT_DELTA == 0.42, "(1) DEFAULT_DELTA is 0.42, not the old 0.5")

# 2 & 3. reported vs actual, at the new default and at the old one
for delta_estimate, label in [(0.42, "new default"), (0.5, "old default")]:
    plan = build_options_plan(
        symbol="TSLA", direction="call",
        stock_entry=440.50, stock_stop=439.80,  # $0.70 stock risk
        max_loss=1000.0, delta_estimate=delta_estimate,
    )
    reported = plan.max_loss
    real = actual_risk(plan, TRUE_DELTA)
    gap_pct = 100.0 * abs(reported - real) / reported if reported else 0.0

    if delta_estimate == TRUE_DELTA:
        check(gap_pct < 2.0,
              f"(2) {label} (delta={delta_estimate}): reported ${reported:.2f} vs "
              f"actual ${real:.2f} -- gap {gap_pct:.2f}% is under 2% (same formula)")
        check(reported == real,
              f"(2b) {label}: reported and actual are EXACTLY equal, not just close "
              f"(${reported:.2f} == ${real:.2f})")
    else:
        expected_ratio = TRUE_DELTA / delta_estimate  # 0.42/0.5 = 0.84
        actual_ratio = real / reported if reported else None
        # cent-level rounding in premium_risk = round(stock_risk * delta, 2)
        # bites harder on a tight $0.70 stop than a wide one -- (4) below
        # shows the ratio is exact once that rounding is negligible; here the
        # tolerance just has to be wide enough to admit that known effect.
        check(actual_ratio is not None and abs(actual_ratio - expected_ratio) < 0.02,
              f"(3) {label} (delta={delta_estimate}): actual/reported ratio "
              f"{actual_ratio:.4f} tracks true_delta/delta_estimate "
              f"{expected_ratio:.4f} (the '$840 on a $1,000 budget' pattern, "
              f"modulo cent-rounding on a tight stop -- see check 4)")
        check(gap_pct > 10.0,
              f"(3b) {label}: at the WRONG delta the gap is large ({gap_pct:.1f}%) -- "
              f"this is what R6 fixed, demonstrated by reproducing it")

# stock-risk independence: same ratio at a totally different stop width
plan2 = build_options_plan(
    symbol="NVDA", direction="put",
    stock_entry=850.00, stock_stop=855.00,  # $5.00 stock risk, 7x wider
    max_loss=1000.0, delta_estimate=0.5,
)
ratio2 = actual_risk(plan2, TRUE_DELTA) / plan2.max_loss if plan2.max_loss else None
check(ratio2 is not None and abs(ratio2 - 0.84) < 0.01,
      f"(4) the 0.84 ratio holds at a 7x wider stop too ({ratio2:.4f}) -- "
      f"it's a delta ratio, not a stock-risk artifact")

print()
if FAILS:
    print(f"{len(FAILS)} FAILED:")
    for f in FAILS:
        print(f"  - {f}")
    sys.exit(1)
print("all checks passed")
