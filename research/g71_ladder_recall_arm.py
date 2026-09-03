"""G7.1 / track `ladder` -- held-out S recall for each ladder-removal arm.

Scores the SAME two held-out sets `research/t0_heldout_recall.py` scores
(100 blind cards of 2026-08-28; the 40 graded engine vetoes of 2026-08-29)
with the legacy A+/A/B/C/X ladder progressively replaced by Austin's S/A/C
downgrade count. Method rule: held-out recall governs, not mean R.

Arms are identical to research/g71_ladder_bt2y_arm.py so the money and the
recall column describe the same engine.

Usage:  python research/g71_ladder_recall_arm.py <arm>
Marks are read, never written. No shared engine file is edited.
"""
import os, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from research.g71_ladder_bt2y_arm import apply_arm, ARMS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arm", choices=ARMS)
    a = ap.parse_args()
    apply_arm(a.arm)
    from research import t0_heldout_recall as t0
    res = {"arm": a.arm, "sweep": t0.score_sweep(), "vetoes": t0.score_vetoes()}
    out = os.path.join(HERE, "g71_ladder_recall_%s.json" % a.arm)
    json.dump(res, open(out, "w"), indent=1)
    s, v = res["sweep"], res["vetoes"]
    print("%-10s recall %2d/%2d = %5.1f%%   precision %5.1f%%   "
          "vetoes S %d/%d  false-fire %.1f%%"
          % (a.arm, s["fired_on_S"], s["n_S"], s["recall_pct"],
             s["precision_pct"], v["fired_on_his_S"], v["his_S"],
             v["false_fire_pct"]))


if __name__ == "__main__":
    main()
