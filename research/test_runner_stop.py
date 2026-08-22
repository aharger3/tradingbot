"""Runner-stop enforcement selftest for research/exit_lab.py (OMEN 6 ticket 02).

The 5.2 scale-out table reported a worst trade of -12.46R on ``30_30_30_10``.
``exit_lab``'s own module docstring states the runner rule as:

    after tranche 1 the stop moves to entry (break-even)

If that stop is actually enforced, the runner leg can never realise worse than
0R, so a laddered policy's floor is tranche 1's -1.0R weight -- i.e. no trade
can book worse than -1.0R overall. Anything below that is the break-even stop
not being applied.

These are synthetic-bar cases, no archive needed. Run:

    python research/test_runner_stop.py
"""

from __future__ import annotations
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from research.exit_lab import (  # noqa: E402
    CLOCK_BAR,
    policy_30_30_30_10,
    policy_50_20_20_10,
)

LADDERED = {
    "30_30_30_10": policy_30_30_30_10,
    "50_20_20_10": policy_50_20_20_10,
}

FLOOR = -1.0
EPS = 1e-9


def _bar(o, h, l, c):
    return {"o": o, "h": h, "l": l, "c": c, "v": 1000}


def wide_atr_collapse(side="L"):
    """New extreme, then one bar craters straight through entry.

    The base is deliberately wide-range so ATR is large (~30). After tranche 1
    exits on the new high, the ATR trail sits ``highest - 1.0*ATR``, which is
    far BELOW the entry price. The break-even stop is meant to sit at entry and
    fire first. If it is not enforced, the runner fills at the ATR trail
    instead -- tens of R below break-even. This is the -12.46R shape.
    """
    bars = []
    for _ in range(20):
        bars.append(_bar(100.0, 120.0, 80.0, 100.0))
    bars.append(_bar(100.0, 100.5, 99.5, 100.0))  # 20: entry bar
    for i in range(3):                            # 21..23: new highs
        t = 121.0 + i
        bars.append(_bar(t - 1, t, t - 2, t - 0.5))
    bars.append(_bar(120.0, 120.5, 40.0, 45.0))   # 24: the crater
    while len(bars) <= CLOCK_BAR:
        bars.append(_bar(45.0, 46.0, 44.0, 45.0))
    if side == "S":
        bars = [_bar(200 - b["o"], 200 - b["l"], 200 - b["h"], 200 - b["c"]) for b in bars]
    return bars


CASES = [
    # name, bars_fn, entry_i, entry, stop, side
    ("wide_atr_collapse long, 1.00 stop", wide_atr_collapse, 20, 100.0, 99.00, "L"),
    ("wide_atr_collapse short, 1.00 stop", wide_atr_collapse, 20, 100.0, 101.00, "S"),
    ("wide_atr_collapse long, hairline stop", wide_atr_collapse, 20, 100.0, 99.90, "L"),
    ("wide_atr_collapse short, hairline stop", wide_atr_collapse, 20, 100.0, 100.10, "S"),
]


def main():
    failures = []
    rows = []
    for name, bars_fn, entry_i, entry, stop, side in CASES:
        bars = bars_fn(side)
        if side == "S":
            entry, stop = 200 - entry, 200 - stop
        for pid, fn in LADDERED.items():
            r = fn(bars, entry_i, entry, stop, side)
            rows.append((name, pid, r))
            if r < FLOOR - EPS:
                failures.append(
                    f"  {name} / {pid}: realised {r:+.4f}R, floor is {FLOOR:+.2f}R "
                    f"(break-even stop on the runner was not enforced)"
                )

    width = max(len(n) for n, _, _ in rows)
    for name, pid, r in rows:
        flag = "  FAIL" if r < FLOOR - EPS else ""
        print(f"{name:<{width}}  {pid:<12} {r:+8.4f}R{flag}")

    if failures:
        print()
        print("RUNNER-STOP SELFTEST FAILED: "
              f"{len(failures)} of {len(rows)} laddered results book worse than "
              f"{FLOOR:+.2f}R.")
        print("\n".join(failures))
        sys.exit(1)

    print()
    print(f"runner-stop selftest ok: all {len(rows)} laddered results >= {FLOOR:+.2f}R")


if __name__ == "__main__":
    main()
