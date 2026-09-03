"""G7.1 / track `ladder` -- the 2-year book with the legacy ladder REPLACED by
Austin's S/A/C downgrade count, measured instead of guessed.

Runtime emulation of the removal diff in `research/g71_ladder.md`. No shared
engine file is edited: the arm sets `signal_runner.ENABLE_SAC_LADDER` (the
wiring that already exists) AND regrades an X_LIFT-lifted signal through the
same ladder, which the shipped `_apply_x_lift` does not do -- it writes a bare
`TradeGrade.B`, which is why turning the existing flag on does not actually
kill `B`.

Arms:
  head        shipped defaults (control; == research/bt2y_trades.json)
  sac         ENABLE_SAC_LADDER only (what the repo ships behind the flag)
  sac_xlift   + the lifted signals regraded on the ladder  <- THE DIFF
  sac_all     ladder is the ONLY grader (SAC_LADDER_REGRADE_ALL, X_LIFT off)
              i.e. `_grade_pa` deleted outright

Usage:  python research/g71_ladder_bt2y_arm.py <arm> [--out PATH] [--days 730]
Never writes research/bt2y_trades.json.
"""
import os, sys, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

ARMS = ("head", "sac", "sac_xlift", "sac_all", "noab")


def apply_arm(arm):
    import signal_runner as sr
    if arm == "head":
        return
    sr.ENABLE_SAC_LADDER = True
    if arm == "sac_all":
        sr.SAC_LADDER_REGRADE_ALL = True
        sr.X_LIFT = "off"
        return
    if arm == "noab":
        # The RENAME arm. Under a straight A+->S, A->A, B->A, C->C, X->X rename
        # the two `_grade_for_levels` promotions that move a signal between `A`
        # and `B` collapse into no-ops -- both letters land on his `A`. This arm
        # neutralises exactly those two branches (the `A+` stack is KEPT, it
        # maps to his `S`) so "the A/B lattice selects nothing" stops being an
        # argument and becomes a measurement: if this arm scores what `head`
        # scores, the letters are decoration.
        sr.ENABLE_SAC_LADDER = False
        orig = sr.SignalRunner._grade_for_levels

        def gfl(self, sig, *a, **k):
            before = sig.get("grade")
            r = orig(self, sig, *a, **k)
            if before in ("A", "B") and sig.get("grade") in ("A", "B"):
                sig["grade"] = before      # undo the A<->B move only
            return r
        sr.SignalRunner._grade_for_levels = gfl
        return
    if arm == "sac_xlift":
        orig = sr.SignalRunner._apply_x_lift

        def lifted(self, sig):
            ok = orig(self, sig)
            if ok:
                self._sac_ladder_grade(sig)
            return ok
        sr.SignalRunner._apply_x_lift = lifted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arm", choices=ARMS)
    ap.add_argument("--days", default="730")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or os.path.join("research", "g71_ladder_bt2y_%s.json" % a.arm)
    assert not out.endswith("bt2y_trades.json"), "refusing to clobber the book"
    apply_arm(a.arm)
    import backtest_2y
    sys.argv = ["backtest_2y.py", "--days", str(a.days), "--out", out]
    backtest_2y.main()


if __name__ == "__main__":
    main()
