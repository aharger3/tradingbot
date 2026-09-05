"""OMEN 9.0 P2: plain asserts for g172_vanquish_refresh.py.

    python research/test_g172_vanquish_refresh.py

Checks the mechanics this row's honesty depends on, not the money verdict
(which is negative and stated as such in the .md):
 1. the S-only candidate stream only ever contains sgrade == 'S' rows.
 2. classifier_on never ADDS a candidate relative to classifier_off, and any
    day where it changes the pick is because the classifier dropped that
    day's original pick (matches the live DROP, not cap, semantics).
 3. spread_r() matches options_sizer's own round-trip formula and is
    strictly non-negative for a real (nonzero) stop distance.
 4. the SPX/XSP arm is a strict subset (by row identity) of the SPY-only S
    rows in the book -- it does not invent candidates.
 5. H1/H2 split partitions the arm with no gaps/overlap, split at
   2025-09-01 per CLAUDE.md.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from g172_vanquish_refresh import (load_rows, build_s_arm, classifier_drop,
                                   spread_r, h1_h2_split, H_SPLIT)
from options_sizer import DEFAULT_DELTA, DEFAULT_SPREAD


def main():
    rows, meta = load_rows()

    arm_off = build_s_arm(rows, classifier_on=False)
    arm_on = build_s_arm(rows, classifier_on=True)

    assert all(r["sgrade"] == "S" for r in arm_off), "classifier-off arm has a non-S row"
    assert all(r["sgrade"] == "S" for r in arm_on), "classifier-on arm has a non-S row"
    print("ok   S-only stream: every row is sgrade=='S' (n=%d off, n=%d on)"
          % (len(arm_off), len(arm_on)))

    assert len(arm_on) <= len(arm_off), "classifier ON produced MORE candidates than OFF"
    by_day_off = {r["day"]: r for r in arm_off}
    by_day_on = {r["day"]: r for r in arm_on}
    for day, r_on in by_day_on.items():
        r_off = by_day_off.get(day)
        assert r_off is not None, "classifier ON invented a day OFF has no candidate for"
        if r_on is not r_off:
            assert classifier_drop(r_off), (
                "pick changed on %s but OFF's own pick was not classifier-droppable" % day)
    print("ok   classifier ON only ever drops/reroutes OFF's pick, never invents one")

    stock_risk = 1.0
    expect = DEFAULT_SPREAD / (stock_risk * DEFAULT_DELTA)
    got = spread_r(dict(entry=100.0, stop=99.0))
    assert abs(got - expect) < 1e-9, "spread_r formula drifted from options_sizer's own constants"
    assert spread_r(dict(entry=100.0, stop=100.0)) == 0.0, "zero stop distance must not divide by zero"
    print("ok   spread_r matches DEFAULT_SPREAD/(stock_risk*DEFAULT_DELTA), n0-stop guarded")

    spx_arm = build_s_arm(rows, classifier_on=False, symbol_filter="SPY")
    spy_s_rows = {id(r) for r in rows if r.get("sgrade") == "S" and r["sym"] == "SPY"}
    assert all(id(r) in spy_s_rows for r in spx_arm), "SPX/XSP arm contains a non-SPY-S row"
    print("ok   SPX/XSP arm (n=%d) is a strict subset of the book's SPY-only S rows" % len(spx_arm))

    h1, h2 = h1_h2_split(arm_off)
    assert len(h1) + len(h2) == len(arm_off), "H1/H2 split lost or duplicated a row"
    assert all(r["day"] < H_SPLIT for r in h1), "H1 leaked a >= split-day row"
    assert all(r["day"] >= H_SPLIT for r in h2), "H2 leaked a < split-day row"
    print("ok   H1/H2 split at %s partitions the arm with no gaps/overlap (H1=%d, H2=%d)"
          % (H_SPLIT, len(h1), len(h2)))

    print("\nPASS: all g172 mechanics checks held.")


if __name__ == "__main__":
    main()
