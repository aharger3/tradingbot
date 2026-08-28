"""Runner-stop enforcement selftest for research/exit_lab.py (OMEN 6 ticket 02).

The 5.2 scale-out table reported a worst trade of -12.46R on ``30_30_30_10``.
``exit_lab``'s own module docstring states the runner rule as:

    after tranche 1 the stop moves to entry (break-even)

If that stop is actually enforced, the runner leg can never realise worse than
0R, so a laddered policy's floor is tranche 1's weight on a full stop-out.

Since ticket 17 that floor is -1.25R, not -1.0R: Austin's stop rule (ballot q1)
triggers on the candle CLOSE and fills at that close, so a bar that closes far
beyond the stop books more than a clean -1.0R. -1.25R is his stated worst case
and exit_lab clamps there. Anything below it is a bug.

The second half of this file is the other half of ticket 17: a day that wicks
through the stop on every bar and closes above it every time. Austin does not get
stopped out on that day. Under the old wick-based test he booked -1.0R on it.

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
    MAX_LOSS_R,
    hod_only,
    policy_30_30_30_10,
    policy_50_20_20_10,
)

LADDERED = {
    "30_30_30_10": policy_30_30_30_10,
    "50_20_20_10": policy_50_20_20_10,
}

FLOOR = -MAX_LOSS_R
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


def wick_through_stop(side="L"):
    """Every bar spikes through the stop and closes back on the right side.

    This is the shape Austin described five times in one batch of marks: the
    wick takes out the level, the close does not, and the trade is still on. A
    wick-based stop books a loss here; a close-based one books the winner.

    Built per side rather than by mirroring -- the mirror of a rising day is not
    a falling day with the same wick geometry, and getting that wrong silently
    turns the short case into a different test.
    """
    bars = [_bar(100.0, 100.4, 99.6, 100.0) for _ in range(21)]
    for k in range(10):
        if side == "L":
            top = 100.6 + k * 0.5
            # low 98.5 is well through the 99.00 stop; the close never is
            bars.append(_bar(100.2 + k * 0.5, top, 98.5, top - 0.1))
        else:
            bot = 99.4 - k * 0.5
            # high 101.5 is well through the 101.00 stop; the close never is
            bars.append(_bar(99.8 - k * 0.5, 101.5, bot, bot + 0.1))
    last = bars[-1]["c"]
    while len(bars) <= CLOCK_BAR:
        bars.append(_bar(last, last + 0.2, last - 0.2, last))
    return bars



def stop_then_rally(side="L"):
    """The close goes through the stop on the very next bar, then price rips.

    This is the shape `research/h1_2y_nowatch.py` found on PLTR 2026-06-01 and
    45 rows of the 2-year book: the ORIGINAL stop fires before tranche 1
    ever reaches its HOD rung, so the WHOLE position is flat -- there is no
    runner left to move to break-even. `scale_out` was moving one anyway and
    booking the rally that followed, which turned a full stop-out into a
    profit. Third instance of ticket 02's bug class (a stop that is computed
    and then not applied to the tranche it governs).
    """
    bars = [_bar(100.0, 100.4, 99.6, 100.0) for _ in range(21)]
    # 21: closes at 98.50, well below the 99.00 stop -> whole position out
    bars.append(_bar(99.8, 99.9, 98.4, 98.50))
    for k in range(10):                      # 22..31: the rally that must not count
        t = 100.0 + k
        bars.append(_bar(t - 0.5, t + 0.5, t - 0.8, t))
    last = bars[-1]["c"]
    while len(bars) <= CLOCK_BAR:
        bars.append(_bar(last, last + 0.2, last - 0.2, last))
    if side == "S":
        bars = [_bar(200 - b["o"], 200 - b["l"], 200 - b["h"], 200 - b["c"])
                for b in bars]
    return bars



def hod_bar_craters(side="L"):
    """The causal-HOD exit bar itself closes far beyond the stop.

    `causal_hod_exit_bar` returns the first bar after the new session extreme
    that fails to extend it. That bar is where tranche 1 exits -- and its own
    close can be anywhere. Here it closes 4R the wrong way.

    `hod_only` scanned for the stop over `range(entry_i + 1, end)` with
    `end = min(hod_i, n)`, EXCLUSIVE of hod_i, so the stop was not live on the
    one bar the policy actually exits on: the -4R close was booked in full and
    never floored. `scale_out` carried the identical off-by-one and it was
    fixed at `f5ff006a` ("tranche 1: fixed stop until the HOD exit bar,
    INCLUSIVE"); `hod_only` was left behind. Measured on the real book by
    `research/w13_scaling.py --selfcheck`: 5 of 1,017 traded rows, worst
    -1.4013R on MU 2026-06-16.

    Bar 21 prints the new extreme, so hod_bar = 21. Bar 22 fails to extend it,
    so the exit bar is 22 -- and bar 22 closes 4R the wrong way.

    Built per side rather than by mirroring -- the mirror of a rising day is
    not a falling day with the same HOD/LOD geometry, and getting that wrong
    silently turns the short case into a different test. Same reason
    `wick_through_stop` is built this way.
    """
    bars = [_bar(100.0, 100.4, 99.6, 100.0) for _ in range(21)]
    if side == "L":
        bars.append(_bar(100.0, 101.0, 99.8, 100.8))  # 21: new session high
        bars.append(_bar(100.6, 100.5, 95.5, 96.00))  # 22: exit bar, craters
        tail = 96.0
    else:
        bars.append(_bar(100.0, 100.2, 99.0, 99.20))  # 21: new session low
        bars.append(_bar(99.40, 104.5, 99.5, 104.00))  # 22: exit bar, craters
        tail = 104.0
    while len(bars) <= CLOCK_BAR:
        bars.append(_bar(tail, tail + 0.4, tail - 0.4, tail))
    return bars


# `hod_only` is not a laddered policy, so it gets its own list. The floor is
# the same one every other case asserts: nothing books below -1.25R.
HOD_CASES = [
    ("hod_bar_craters long", hod_bar_craters, 20, 100.0, 99.00, "L"),
    ("hod_bar_craters short", hod_bar_craters, 20, 100.0, 101.00, "S"),
]

# Cases where the original stop fires first: the whole position is out, so the
# realised R must be a LOSS. Booking anything above 0 means a stopped-out trade
# kept running.
STOPPED_CASES = [
    ("stop_then_rally long", stop_then_rally, 20, 100.0, 99.00, "L"),
    ("stop_then_rally short", stop_then_rally, 20, 100.0, 101.00, "S"),
]

# Cases that must NOT stop out at all -- the close never goes beyond the stop.
POSITIVE_CASES = [
    ("wick_through_stop long", wick_through_stop, 20, 100.0, 99.00, "L"),
    ("wick_through_stop short", wick_through_stop, 20, 100.0, 101.00, "S"),
]


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

    for name, bars_fn, entry_i, entry, stop, side in STOPPED_CASES:
        bars = bars_fn(side)
        if side == "S":
            entry, stop = 200 - entry, 200 - stop
        for pid, fn in LADDERED.items():
            r = fn(bars, entry_i, entry, stop, side)
            rows.append((name, pid, r))
            if r > -1.0 + EPS:
                failures.append(
                    f"  {name} / {pid}: realised {r:+.4f}R on a trade whose close "
                    f"went through the ORIGINAL stop before any tranche exited -- "
                    f"100% of the position is out at that close, so this must be a "
                    f"full stop-out (<= -1.00R), not a partial one"
                )
            if r < FLOOR - EPS:
                failures.append(
                    f"  {name} / {pid}: realised {r:+.4f}R, floor is {FLOOR:+.2f}R"
                )

    for name, bars_fn, entry_i, entry, stop, side in HOD_CASES:
        bars = bars_fn(side)          # already side-correct, do not mirror
        r = hod_only(bars, entry_i, entry, stop, side)
        rows.append((name, "hod_only", r))
        if r < FLOOR - EPS:
            failures.append(
                f"  {name} / hod_only: realised {r:+.4f}R, floor is {FLOOR:+.2f}R "
                f"(the stop was not live on the HOD exit bar itself)"
            )

    for name, bars_fn, entry_i, entry, stop, side in POSITIVE_CASES:
        bars = bars_fn(side)          # already side-correct, do not mirror
        for pid, fn in LADDERED.items():
            r = fn(bars, entry_i, entry, stop, side)
            rows.append((name, pid, r))
            if r <= 0:
                failures.append(
                    f"  {name} / {pid}: realised {r:+.4f}R on a day whose closes "
                    f"never went beyond the stop -- a wick stopped it out"
                )

    width = max(len(n) for n, _, _ in rows)
    for name, pid, r in rows:
        positive = any(name == pn for pn, _, _, _, _, _ in POSITIVE_CASES)
        bad = (r <= 0) if positive else (r < FLOOR - EPS)
        flag = "  FAIL" if bad else ""
        print(f"{name:<{width}}  {pid:<12} {r:+8.4f}R{flag}")

    if failures:
        print()
        print(f"RUNNER-STOP SELFTEST FAILED: {len(failures)} of {len(rows)} "
              f"laddered results are wrong.")
        print("\n".join(failures))
        sys.exit(1)

    print()
    print(f"runner-stop selftest ok: {len(rows)} laddered results, "
          f"stop-outs floored at {FLOOR:+.2f}R, wick-only days never stopped out")


if __name__ == "__main__":
    main()
