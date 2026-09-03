"""G7.2 track `sixlevels` -- run the two-year book on AUSTIN'S SIX LEVELS.

Austin settled the set on 2026-08-29 (Projects/omen-rulebook.md, "The six
levels, named at last"):

    PDH  PDL   prior regular session high / low
    PMH  PML   PREMARKET high / low (04:00-09:30 the same morning)
    HOD  LOD   the session's own high / low

    > "you know the 6 levels i watch thats it."
    > "only the 6 levels, but you can still visualize those pivots."

The shipped engine gates on a DIFFERENT set: it ships the 5-minute opening
range (ORH/ORL) as a first-class break-and-retest level, keeps HOD/LOD switched
off (`signal_runner.HODLOD_PAIR = False`), and adds ~13 T10 swing-pivot levels
per symbol-day (`PIVOT_LEVELS` default ON).

Three changes, measured one at a time and together:

    hodlod    HODLOD_PAIR = True          (his HOD/LOD, currently off)
    noor      OR high / OR low out of the GATING set (still computed, still
              in `_active_levels` for chop grading and dedupe, still drawable)
    nopivot   PIVOT_LEVELS = 0            (pivots gate nothing; still
              computable and drawable -- nothing in the deck/chart builders
              reads this flag)
    sixlevels all three at once = Austin's roster

HOW THE OR CHANGE IS MADE WITHOUT EDITING signal_runner.py
----------------------------------------------------------
`level_pairs` is a local inside `SignalRunner.detect_signals`, so there is no
attribute to monkey-patch. This rig reads the real `signal_runner.py` off disk,
applies ONE asserted textual substitution to that one line, and execs the
result into `sys.modules["signal_runner"]` before `backtest_week` imports it.
No shipped file is written. The substitution asserts it matched exactly once,
so it fails loudly if the line ever moves.

`_active_levels` is deliberately left ALONE. Removing the opening range from
the gating set is items 2/3 of the ticket; removing it from chop grading and
from the 0.1% dedupe would be a second, unasked change and would confound the
read.

The runner TARGET is NOT touched here. It lives in `backtest_week.py:848-859`
and is owned by another item on the board (the "runner can never aim more than
$1 past the session high" fix). The deliberate fallback decision this ticket
asks for is stated in research/g72_sixlevels_report.md.

Usage:
    python research/g72_sixlevels_book.py --arm base --out research/g72_arm_base.json
    python research/g72_sixlevels_book.py --arm sixlevels --out research/g72_arm_sixlevels.json
"""
from __future__ import annotations
import argparse, os, sys, types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

ap = argparse.ArgumentParser()
ap.add_argument("--arm", required=True,
                choices=["base", "hodlod", "noor", "nopivot", "sixlevels", "sixfast", "hodfast"])
ap.add_argument("--out", required=True)
ap.add_argument("--days", type=int, default=730)
ARGS = ap.parse_args()

WANT_HODLOD = ARGS.arm in ("hodlod", "sixlevels", "sixfast", "hodfast")
WANT_NOOR = ARGS.arm in ("noor", "sixlevels", "sixfast")
WANT_NOPIVOT = ARGS.arm in ("nopivot", "sixlevels", "sixfast")
# `sixfast` = his roster with F3's two staleness gates relaxed. F3 required the
# session extreme to be >=30 BARS old and the day to be >=43 bars in, so HOD/LOD
# could not exist before 10:13 and the extreme had to have been set before
# ~09:42 -- gates chosen in July to stop the pair duplicating the OPENING RANGE
# (signal_runner.py:1155-1162 comment). The opening range is out of the gating
# set in this arm, so the reason for those two gates is gone. The 12-bar
# exclusion stays: a high can only be broken and retested if it was set before
# the FSM window, so the level has to be at least that stale by construction.
WANT_HODFAST = ARGS.arm in ("sixfast", "hodfast")

# PIVOT_LEVELS is read at signal_runner import time -- set it BEFORE the import.
if WANT_NOPIVOT:
    os.environ["PIVOT_LEVELS"] = "0"

SR_PATH = os.path.join(ROOT, "signal_runner.py")
OR_LINE = '        level_pairs = [("OR high", "OR low", or_high, or_low)]'
OR_REPLACEMENT = (
    '        level_pairs = []  # G72 sixlevels: the opening range is NOT one of\n'
    '        # Austin\'s six ("you know the 6 levels i watch thats it",\n'
    '        # 2026-08-29). or_high/or_low are still computed above and still\n'
    '        # sit in _active_levels -- they gate nothing.'
)

DUP_LINE = ("            dup = lambda v: any(abs(v - l) / l < 0.001 "
            "for l in self._active_levels)")
DUP_REPLACEMENT = """\
            # G72 sixlevels: dedupe HOD/LOD against the OTHER FOUR levels
            # Austin watches, not against the opening range. Left as shipped,
            # a session high that was set in the first five minutes is thrown
            # away as "the OR high again" -- and that is exactly the HOD he
            # says he watches. The F3 qualifying rule already forces the
            # extreme to be >=30 bars old, so this case is the common one.
            _six4 = [l for l in (self.pdh, self.pdl, self.pmh, self.pml) if l]
            dup = lambda v: any(abs(v - l) / l < 0.001 for l in _six4)"""

AGE_LINE = "        if HODLOD_PAIR and len(self.candles) >= 43:"
AGE_REPLACEMENT = "        if HODLOD_PAIR and len(self.candles) >= 20:"
OLD_LINE = ("            hod_lv = hi_val if hi_age >= 30 and not dup(hi_val) else None\n"
            "            lod_lv = lo_val if lo_age >= 30 and not dup(lo_val) else None")
OLD_REPLACEMENT = (
    "            hod_lv = hi_val if hi_age >= 12 and not dup(hi_val) else None\n"
    "            lod_lv = lo_val if lo_age >= 12 and not dup(lo_val) else None")

src = open(SR_PATH, encoding="utf-8").read()
if WANT_HODFAST:
    for old, new in ((AGE_LINE, AGE_REPLACEMENT), (OLD_LINE, OLD_REPLACEMENT)):
        assert src.count(old) == 1, "F3 staleness gate moved: %r" % old[:60]
        src = src.replace(old, new)
if WANT_NOOR:
    n = src.count(OR_LINE)
    assert n == 1, (
        "expected exactly 1 copy of the OR level_pairs line in signal_runner.py, "
        "found %d -- the line moved, fix this rig before trusting any number" % n)
    src = src.replace(OR_LINE, OR_REPLACEMENT)
    assert src.count(DUP_LINE) == 1, "HOD/LOD dedupe line moved"
    src = src.replace(DUP_LINE, DUP_REPLACEMENT)

mod = types.ModuleType("signal_runner")
mod.__file__ = SR_PATH
sys.modules["signal_runner"] = mod
exec(compile(src, SR_PATH, "exec"), mod.__dict__)

if WANT_HODLOD:
    # F3's HOD/LOD break-and-retest pair. Turned off 2026-07-11 on a 12-month
    # standalone A/B; Austin has since named HOD and LOD as two of his six, and
    # the mentor corpus names HOD on 413 symbol-days the engine has no level
    # for (research/corpus_sf/level_grading.md).
    mod.HODLOD_PAIR = True

assert mod.PIVOT_LEVELS == (not WANT_NOPIVOT), "PIVOT_LEVELS did not take"
assert mod.HODLOD_PAIR == WANT_HODLOD, "HODLOD_PAIR did not take"

import backtest_2y as b2  # noqa: E402

print("arm=%s  HODLOD_PAIR=%s  OR_gating=%s  PIVOT_LEVELS=%s"
      % (ARGS.arm, mod.HODLOD_PAIR, not WANT_NOOR, mod.PIVOT_LEVELS))

sys.argv = ["backtest_2y.py", "--days", str(ARGS.days), "--out", ARGS.out]
b2.main()
