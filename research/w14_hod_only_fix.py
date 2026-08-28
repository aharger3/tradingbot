"""w14_hod_only_fix.py -- re-measure hod_only after the MAX_LOSS_R floor fix.

`research/exit_lab.py::hod_only` scanned for the stop over
`range(entry_i + 1, min(hod_i, n))` -- EXCLUSIVE of the HOD exit bar -- so a
HOD bar whose own close sat far beyond the stop was booked in full and never
floored at `MAX_LOSS_R`. `scale_out` carried the identical off-by-one and was
fixed at `f5ff006a`; `hod_only` was left behind and found by
`research/w13_scaling.py --selfcheck` (5 of 1,017 rows, worst -1.4013R).

This re-runs the policy on the same 1,017 traded rows both ways, so the
correction to `research/w2_time_ladder.md` §4 and `research/w13_scaling.md` §2
is a measured delta rather than an assertion. Read-only: no default changed,
no bar fetched -- `research/r9_simple_book.py`'s Bars cache is archive-only.

    python research/w14_hod_only_fix.py
"""
from __future__ import annotations
import json, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import exit_lab as xl                       # noqa: E402
from research.r9_simple_book import Bars                  # noqa: E402

ARM = os.path.join(HERE, "g3_arm_ow1.json")


def old_hod_only(bars, entry_i, entry, stop, side):
    """hod_only exactly as it stood before the fix -- the EXCLUSIVE range."""
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    hod_i = xl.causal_hod_exit_bar(bars, entry_i, side)
    if hod_i is None:
        return 0.0
    end = min(hod_i, n)                       # <-- the bug: excludes hod_i
    for i in range(entry_i + 1, end):
        if xl._stop_hit_first(bars, i, entry, stop, side):
            return xl.realised_r(entry, stop,
                                 xl._stop_fill(bars, i, entry, stop, side, risk), side)
    return xl.realised_r(entry, stop, bars[hod_i]["c"], side)


def run(clock):
    keep, xl.CLOCK_BAR = xl.CLOCK_BAR, clock
    try:
        cache = Bars()
        rows = [r for r in json.load(open(ARM, encoding="utf-8"))["trades"]
                if r["traded"]]
        old, new = [], []
        breaches = []
        for r in rows:
            got = cache.get(r["sym"], r["day"])
            if got is None:
                continue
            _rth, dicts, _idx, _hi, _lo = got
            side = r.get("side") or ("L" if r["dir"] == "call" else "S")
            a = (dicts, r["entry_i"], float(r["entry"]), float(r["stop"]), side)
            o, nw = old_hod_only(*a), xl.hod_only(*a)
            old.append(o); new.append(nw)
            if o < -xl.MAX_LOSS_R - 1e-9:
                breaches.append((r["sym"], r["day"], o, nw))
        return old, new, breaches
    finally:
        xl.CLOCK_BAR = keep


def main():
    print("clock | n | hod_only BEFORE | hod_only AFTER | delta | rows below floor")
    for label, clock in (("11:00", 90), ("16:00", 10 ** 6)):
        old, new, br = run(clock)
        print("%-5s | %d | %+.4f | %+.4f | %+.4f | %d"
              % (label, len(old), statistics.fmean(old), statistics.fmean(new),
                 statistics.fmean(new) - statistics.fmean(old), len(br)))
        for sym, day, o, nw in sorted(br, key=lambda x: x[2]):
            print("    %-6s %s  %+.4f -> %+.4f" % (sym, day, o, nw))
        assert all(v >= -xl.MAX_LOSS_R - 1e-9 for v in new), "still below floor"
    assert xl.CLOCK_BAR == 90, "CLOCK_BAR not restored"
    print("selfcheck ok: no row books below -%.2fR after the fix" % xl.MAX_LOSS_R)


if __name__ == "__main__":
    main()
