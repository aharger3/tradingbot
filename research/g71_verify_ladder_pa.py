"""G7.1 adversarial verify of track `ladder`.

Isolates what `sac_all` actually does. Three extra arms, all runtime-only:

  pa_del    `_grade_pa` DELETED and nothing else -- the shape veto never returns
            D; everything downstream (HTF_BIAS_VETO, _grade_for_levels,
            _calibration_grade, the C tight-stop gate) is untouched.
  htf_off   HTF_BIAS_VETO off only -- the OTHER veto `sac_all` lifts, which is
            not `_grade_pa` at all (omen_bot.grade_trade:243 returns D before
            `_grade_pa` is ever called, on 47.0% of the book).
  sac_all_x sac_all as the ladder track ran it, for a same-process control.

Read-only. Writes research/g71_verify_ladder_pa_<arm>.json.
"""
import os, sys, json, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

ARMS = ("pa_del", "htf_off", "pa_del_htf_off", "sac_all_x")


def apply_arm(arm):
    import omen_bot as ob
    import signal_runner as sr
    if arm == "sac_all_x":
        sr.ENABLE_SAC_LADDER = True
        sr.SAC_LADDER_REGRADE_ALL = True
        sr.X_LIFT = "off"
        return
    if arm in ("pa_del", "pa_del_htf_off"):
        orig = ob.PriceActionAnalyzer._grade_pa

        def nod(candle, lookback, or_high, or_low, is_long):
            g = orig(candle, lookback, or_high, or_low, is_long)
            return ob.TradeGrade.C if g is ob.TradeGrade.D else g
        ob.PriceActionAnalyzer._grade_pa = staticmethod(nod)
    if arm in ("htf_off", "pa_del_htf_off"):
        ob.HTF_BIAS_VETO = False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arm", choices=ARMS)
    a = ap.parse_args()
    apply_arm(a.arm)
    from research import t0_heldout_recall as t0
    res = {"arm": a.arm, "sweep": t0.score_sweep(), "vetoes": t0.score_vetoes()}
    json.dump(res, open(os.path.join(HERE, "g71_verify_ladder_pa_%s.json" % a.arm), "w"), indent=1)
    s, v = res["sweep"], res["vetoes"]
    print("%-15s recall %2d/%2d = %5.1f%%  precision %5.1f%%  fired_on_no %d/%d  "
          "vetoS %d/%d  false-fire %.1f%%"
          % (a.arm, s["fired_on_S"], s["n_S"], s["recall_pct"], s["precision_pct"],
             s["fired_on_no"], s["n_no"], v["fired_on_his_S"], v["his_S"],
             v["false_fire_pct"]))


if __name__ == "__main__":
    main()
