"""OMEN 8.0 R7 checks. Plain asserts, no pytest:  python test_options_spread.py

`omen-x-board.md:180-181`: "A $0.05 round-trip option spread costs a further
-0.2042R; entry and exit are both booked at the mid, so spread is currently
charged to nothing." `build_options_plan` now books entry at mid+half-spread
(the ask) and stop/target at mid-half-spread (the bid), so a round trip pays
the full spread once, win or lose. This file isolates the SPREAD effect --
delta is held at the correct 0.42 throughout, so R6's fix isn't what's under
test here (see test_options_sizer_delta.py for that).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import options_sizer as os_
from options_sizer import build_options_plan, DEFAULT_SPREAD, DEFAULT_DELTA, DEFAULT_RR

FAILS = []


def check(cond, label):
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}")
        FAILS.append(label)


check(DEFAULT_SPREAD == 0.05, "(1) DEFAULT_SPREAD is 0.05, matching omen-x-board.md's figure")

# 2. no spread charged vs the shipped default, same trade, same delta
_saved = os_.DEFAULT_SPREAD
try:
    os_.DEFAULT_SPREAD = 0.0
    plan_no_spread = build_options_plan(
        symbol="TSLA", direction="call",
        stock_entry=440.50, stock_stop=439.80,
        max_loss=1000.0, delta_estimate=DEFAULT_DELTA,
    )
finally:
    os_.DEFAULT_SPREAD = _saved

plan_spread = build_options_plan(
    symbol="TSLA", direction="call",
    stock_entry=440.50, stock_stop=439.80,
    max_loss=1000.0, delta_estimate=DEFAULT_DELTA,
)

check(plan_spread.entry_premium > plan_no_spread.entry_premium,
      f"(2) spread charged: entry ${plan_spread.entry_premium:.2f} > "
      f"no-spread entry ${plan_no_spread.entry_premium:.2f} -- pays the ask, not the mid")
check(plan_spread.stop_premium < plan_no_spread.stop_premium,
      f"(2b) spread charged: stop ${plan_spread.stop_premium:.2f} < "
      f"no-spread stop ${plan_no_spread.stop_premium:.2f} -- receives the bid, not the mid")
check(plan_spread.target_premium < plan_no_spread.target_premium,
      f"(2c) spread charged: target ${plan_spread.target_premium:.2f} < "
      f"no-spread target ${plan_no_spread.target_premium:.2f} -- receives the bid, not the mid")

# 3. the round-trip cost hits both the stop AND the target sides -- a full
# spread's worth of premium separates the two plans' entry-to-stop distance
per_contract_gap = round(
    (plan_spread.entry_premium - plan_spread.stop_premium)
    - (plan_no_spread.entry_premium - plan_no_spread.stop_premium), 2)
check(abs(per_contract_gap - DEFAULT_SPREAD) < 0.02,
      f"(3) the spread-charged plan's per-contract risk is ${per_contract_gap:.2f} more "
      f"than the no-spread plan's -- tracks the ${DEFAULT_SPREAD:.2f} round-trip charge "
      f"(mod cent rounding)")

# 4. real bid/ask overrides DEFAULT_SPREAD when a live quote provides one
class _FakeFeed:
    def fetch_option_quote(self, symbol, expiration, strike, direction):
        return {"mid": 3.00, "bid": 2.80, "ask": 3.20, "occ_symbol": "TSLA260101C00440000"}

plan_live = build_options_plan(
    symbol="TSLA", direction="call",
    stock_entry=440.50, stock_stop=439.80,
    max_loss=1000.0, delta_estimate=DEFAULT_DELTA,
    tasty_feed=_FakeFeed(),
)
check(plan_live.quote_source == "tastytrade_dxlink_realtime",
      "(4a) the fake live quote was actually used")
check(plan_live.entry_premium == round(3.00 + 0.20, 2),
      f"(4b) live quote: entry books at mid+half the REAL spread "
      f"(3.00 + 0.20 = {round(3.00+0.20,2)}), not DEFAULT_SPREAD "
      f"(got ${plan_live.entry_premium:.2f})")

# 5. max_reward tracks the real (target - entry) fill prices, not a
# synthetic risk*rr multiple that would ignore the spread entirely (R7 also
# fixed this -- it was decoupled from target_premium before). Not EXACTLY
# equal to (target_premium - entry_premium): those are two independently
# cent-rounded display prices, and max_reward is deliberately computed from
# the pre-rounding model values instead (the same fix that keeps max_loss
# from drifting a cent per contract on a tight stop) -- so this checks
# "close", not "identical".
naive_reward = round((plan_spread.target_premium - plan_spread.entry_premium)
                     * 100 * plan_spread.contracts, 2)
reward_gap = abs(plan_spread.max_reward - naive_reward)
check(reward_gap <= plan_spread.contracts,  # at most ~1 cent/contract of rounding drift
      f"(5) max_reward (${plan_spread.max_reward:.2f}) tracks the naive "
      f"target-minus-entry calc (${naive_reward:.2f}) within cent-rounding "
      f"(${reward_gap:.2f} apart, {plan_spread.contracts} contracts) -- not a "
      f"decoupled risk*rr guess")
check(plan_spread.max_reward < plan_spread.max_loss * DEFAULT_RR,
      f"(5b) the spread pulls max_reward (${plan_spread.max_reward:.2f}) below a clean "
      f"{DEFAULT_RR:.0f}:1 (${plan_spread.max_loss * DEFAULT_RR:.2f}) -- paying it costs "
      f"the reward side too, not just the risk side")

print()
if FAILS:
    print(f"{len(FAILS)} FAILED:")
    for f in FAILS:
        print(f"  - {f}")
    if __name__ == "__main__":  # ponytail: gated so pytest can collect the repo (2026-09-03)
        sys.exit(1)
print("all checks passed")
