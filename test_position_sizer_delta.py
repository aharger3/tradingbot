"""B-06 (OMEN 9.0 B3): position_sizer.compute_plan's assumed_delta default must
match options_sizer.DEFAULT_DELTA (the measured 0.42), not a separate,
unmeasured 0.5. Plain asserts, no pytest:  python test_position_sizer_delta.py

Before the fix, the ticket's failing input:
  compute_plan(..., direction='call').contracts_estimated            -> 47
  compute_plan(..., direction='call', assumed_delta=0.42).contracts_estimated -> 56
Both must be 56 after the fix -- compute_plan's default IS 0.42.
"""
import inspect
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import position_sizer as ps
from options_sizer import DEFAULT_DELTA

FAILS = []


def check(name, cond):
    if not cond:
        FAILS.append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}")


# 1. compute_plan's default delta is the shared, measured constant.
_default_delta = inspect.signature(ps.compute_plan).parameters["assumed_delta"].default
check(
    "compute_plan default assumed_delta == options_sizer.DEFAULT_DELTA (0.42)",
    _default_delta == DEFAULT_DELTA,
)

# 2. The ticket's exact failing input: default call now matches the explicit-0.42 call.
default_plan = ps.compute_plan(stock_entry=100.0, stock_stop=99.58, direction="call")
explicit_plan = ps.compute_plan(
    stock_entry=100.0, stock_stop=99.58, direction="call", assumed_delta=0.42
)
check(
    "default-delta contracts_estimated == explicit-0.42 contracts_estimated (56 == 56)",
    default_plan.contracts_estimated == explicit_plan.contracts_estimated == 56,
)

# 3. The stale ATM ~0.5 default no longer applies -- 47 contracts (the pre-fix
# under-sized figure) must NOT be what the default now produces.
check(
    "default no longer reproduces the pre-fix 47-contract (delta=0.5) figure",
    default_plan.contracts_estimated != 47,
)

if FAILS:
    print(f"\n{len(FAILS)} FAILED: {FAILS}")
    sys.exit(1)
print("\nAll checks passed.")
