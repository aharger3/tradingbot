"""Selftest for research/sizing.py -- no archive dependency, synthetic R-multiples only.

Checks the guarantees sizing.py's docstrings claim rather than any particular
number: shares is an exact passthrough, futures never risks more than the
R_DOLLARS budget once contracts round down, a stop too wide for one contract
fails loud instead of silently sizing to zero, and -1.25R (the settled floor
from exit_lab.py's MAX_LOSS_R) lands on exactly -$1,250 on shares -- the one
place in this file where a specific dollar figure is allowed to be asserted,
because R_DOLLARS and MAX_LOSS_R are both fixed constants, not measurements.

Run:

    python research/test_sizing.py
"""

from __future__ import annotations
import math
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from research.sizing import (  # noqa: E402
    FUTURES_PRESETS,
    R_DOLLARS,
    dollars,
    dollars_futures,
    dollars_options,
    dollars_shares,
    summarise,
)

EPS = 1e-9


def main():
    failures = []
    checks = []  # (label, ok)

    def check(label, ok):
        checks.append((label, ok))
        if not ok:
            failures.append(label)

    # --- shares: exact passthrough, including the loss-distribution-must-
    # pass-through requirement (a mixed, non-uniform run of R's, not all -1) ---
    sample_rs = [2.4, -1.25, 0.0, 3.9, -0.6, 1.0, -1.25, -0.15, 5.2]
    for r in sample_rs:
        got = dollars_shares(r)
        check(f"shares passthrough r={r:+.2f} -> ${got:+.2f}", math.isclose(got, r * R_DOLLARS))

    # settled floor: -1.25R must map to exactly -$1,250 on shares
    got = dollars(-1.25, "shares")["pnl"]
    check(f"shares -1.25R -> {got:+.2f} (want -1250.00)", math.isclose(got, -1250.0))

    # --- futures: realised risk after integer rounding never exceeds R_DOLLARS,
    # for both presets, across a spread of stop widths (not just an exact fit) ---
    for contract in FUTURES_PRESETS:
        for stop_ticks in [1, 3, 4, 7, 10, 17, 33, 50, 80, 120]:
            row = dollars_futures(1.0, stop_ticks=stop_ticks, contract=contract)
            realised = row["realised_risk_dollars"]
            check(
                f"futures {contract} stop={stop_ticks}t: realised ${realised:.2f} "
                f"<= ${R_DOLLARS:.2f} budget, contracts={row['contracts']}",
                realised <= R_DOLLARS + EPS and row["contracts"] >= 1,
            )
            # rounding error must be non-negative (undershoot only, never a
            # phantom risk boost) and internally consistent with realised risk
            expect_err = (R_DOLLARS - realised) / R_DOLLARS
            check(
                f"futures {contract} stop={stop_ticks}t: rounding_error_r consistent",
                row["rounding_error_r"] >= -EPS
                and math.isclose(row["rounding_error_r"], expect_err, abs_tol=EPS),
            )

    # a 1R-exact stop (chosen to divide evenly) should round-trip with zero error
    exact_ticks = R_DOLLARS / FUTURES_PRESETS["MNQ"]["tick_value"]  # 2000 ticks, 1 contract
    row = dollars_futures(1.0, stop_ticks=exact_ticks, contract="MNQ")
    check(
        f"futures MNQ exact-fit stop: contracts={row['contracts']}, "
        f"error={row['rounding_error_r']:.6f}",
        row["contracts"] == 1 and math.isclose(row["rounding_error_r"], 0.0, abs_tol=EPS),
    )

    # a stop wide enough that one contract alone blows the budget must fail
    # loud, not size to 0 contracts and report a silent $0
    huge_stop = (R_DOLLARS / FUTURES_PRESETS["MES"]["tick_value"]) + 1  # just over budget
    raised = False
    try:
        dollars_futures(1.0, stop_ticks=huge_stop, contract="MES")
    except ValueError:
        raised = True
    check(f"futures MES stop wider than budget raises instead of contracts=0", raised)

    # contracts must never be negative for any legal (positive) stop width
    for stop_ticks in [1, 2, 5, 25, 100, 1000]:
        try:
            row = dollars_futures(1.0, stop_ticks=stop_ticks, contract="MES")
        except ValueError:
            continue  # correctly refused -- not a negative-contracts case
        check(
            f"futures MES stop={stop_ticks}t: contracts={row['contracts']} >= 1",
            row["contracts"] >= 1,
        )

    # negative/zero stop distance is not a valid input, regardless of budget
    for bad_stop in [0, -5]:
        raised = False
        try:
            dollars_futures(1.0, stop_ticks=bad_stop, contract="MNQ")
        except ValueError:
            raised = True
        check(f"futures stop_ticks={bad_stop} raises", raised)

    # --- options: explicit approximation, always low-confidence, delta-scaled ---
    for delta in [0.3, 0.5, 0.8]:
        for r in [2.0, -1.25]:
            row = dollars_options(r, delta=delta)
            check(
                f"options delta={delta} r={r:+.2f}: pnl={row['pnl']:+.2f}, "
                f"confidence={row['confidence']!r}",
                math.isclose(row["pnl"], r * R_DOLLARS * delta)
                and row["confidence"] == "low",
            )
    for bad_delta in [0.0, 1.5, -0.2]:
        raised = False
        try:
            dollars_options(1.0, delta=bad_delta)
        except ValueError:
            raised = True
        check(f"options delta={bad_delta} out of (0,1] raises", raised)

    # --- summarise: matches manual total/mean/worst, futures carries the
    # mean-abs rounding error, options carries confidence ---
    rs = [2.0, -1.25, 0.5, -0.9, 3.1, -1.25, 0.0]

    s_shares = summarise(rs, "shares")
    manual_pnls = [dollars_shares(r) for r in rs]
    check(
        "summarise shares matches manual total/mean/worst",
        math.isclose(s_shares["total_dollars"], sum(manual_pnls))
        and math.isclose(s_shares["mean_dollars"], sum(manual_pnls) / len(manual_pnls))
        and math.isclose(s_shares["worst_dollars"], min(manual_pnls)),
    )

    s_fut = summarise(rs, "futures", stop_ticks=17, contract="MNQ")
    check(
        "summarise futures carries mean_abs_rounding_error_r",
        "mean_abs_rounding_error_r" in s_fut and s_fut["mean_abs_rounding_error_r"] >= 0,
    )

    s_opt = summarise(rs, "options", delta=0.5)
    check("summarise options carries confidence=low", s_opt.get("confidence") == "low")

    unknown_raised = False
    try:
        dollars(1.0, "crypto")
    except ValueError:
        unknown_raised = True
    check("unknown venue raises", unknown_raised)

    width = max(len(label) for label, _ in checks)
    for label, ok in checks:
        flag = "" if ok else "  FAIL"
        print(f"{label:<{width}}{flag}")

    if failures:
        print()
        print(f"SIZING SELFTEST FAILED: {len(failures)} of {len(checks)} checks failed.")
        sys.exit(1)

    print()
    print(f"sizing selftest ok: {len(checks)} checks passed "
          f"(shares exact, futures never over-risks R_DOLLARS, "
          f"options tagged low-confidence, -1.25R -> -$1,250)")


if __name__ == "__main__":
    main()
