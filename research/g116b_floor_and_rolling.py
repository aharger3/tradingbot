"""g116b -- the three things g116 leaves open, and they are the ones that decide it.

  5. FINE risk grid + ROLLING-START prop eval (the honest form of "pass one
     evaluation within 12 months" -- an eval starts on an arbitrary day).
  6. THE OPTIONS FLOOR, per trade, not at the median: how often ONE contract
     already risks more than 0.25% / 1% of a $1,000 account, and the smallest
     account on which the passing risk level is buyable at all.
  7. THE $1,000 ACCOUNT, simulated: one contract a trade, real premium cost
     from the tape ratio, loss capped at premium, equity compounding.

Reuses g116's arms verbatim.
"""
from __future__ import annotations
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from g116_sizing_kelly_options import (ARMS, build_arm, load_rows, load_tape,
                                       prop_row, months_between, DELTA, MULT)
from omen_metrics import ev_r_scoreboard, evaluate_prop_challenge

ACCOUNT = 50000.0


def main():
    rows = load_rows()
    tape = load_tape()
    med_pct = statistics.median(t["prem"] / t["px"] for t in tape)
    arms = {k: build_arm(rows, keep) for k, (d, keep) in ARMS.items()}
    out = {"median_prem_pct_of_spot": med_pct}

    # ---- 5a. fine risk grid --------------------------------------------
    print("=== 5a. FINE RISK GRID, $50k eval (where exactly does it break?) ===")
    grid = [0.0010, 0.0015, 0.0020, 0.0025, 0.0030, 0.0035, 0.0040, 0.0045,
            0.0050, 0.0060, 0.0075, 0.0100]
    out["fine_grid"] = {}
    for k, a in arms.items():
        line = []
        for rp in grid:
            r = prop_row(a, rp * ACCOUNT)
            line.append("%.2f%%:%s" % (rp * 100, "PASS" if r["passed"]
                                       else r["fail_reason"][:4].upper()))
            out["fine_grid"].setdefault(k, []).append(
                dict(risk_pct=rp, passed=r["passed"], rule=r["fail_reason"]))
        print("  %-14s %s" % (k, "  ".join(line)))

    # ---- 5b. rolling-start ---------------------------------------------
    print("\n=== 5b. ROLLING-START EVAL: from every possible start day, does the")
    print("        account pass within 252 trading days (12 months)? ===")
    print("  %-14s %8s %8s %8s %8s %10s"
          % ("arm", "risk%", "starts", "pass%", "y1 pass%", "y2 pass%"))
    out["rolling"] = {}
    for k, a in arms.items():
        for rp in (0.0025, 0.0035, 0.0050):
            npass = ny1 = ny2 = n1 = n2 = 0
            starts = 0
            for i in range(len(a)):
                win = a[i:i + 252]
                if len(win) < 60:
                    break
                starts += 1
                p = prop_row(win, rp * ACCOUNT)["passed"]
                npass += p
                if win[0]["day"] < "2025-09-01":
                    n1 += 1
                    ny1 += p
                else:
                    n2 += 1
                    ny2 += p
            print("  %-14s %7.2f%% %8d %7.1f%% %7s %9s"
                  % (k, rp * 100, starts, 100 * npass / starts,
                     ("%.1f%%" % (100 * ny1 / n1)) if n1 else "-",
                     ("%.1f%%" % (100 * ny2 / n2)) if n2 else "-"))
            out["rolling"].setdefault(k, []).append(
                dict(risk_pct=rp, starts=starts, pass_pct=100 * npass / starts,
                     y1_pass_pct=(100 * ny1 / n1) if n1 else None,
                     y2_pass_pct=(100 * ny2 / n2) if n2 else None))

    # ---- 6. the options floor, per trade -------------------------------
    print("\n=== 6. THE OPTIONS FLOOR, PER TRADE (one contract is the whole grid) ===")
    print("  premium_risk = |entry-stop| x delta 0.5;  1-contract risk = that x 100")
    print("  %-14s %9s %9s %9s %9s %9s %9s"
          % ("arm", "p10 $", "med $", "p90 $", "<=$2.50", "<=$10", "min acct"))
    out["floor"] = {}
    for k, a in arms.items():
        risks = sorted(abs(r["entry"] - r["stop"]) * DELTA * MULT for r in a)
        n = len(risks)
        p10, med, p90 = risks[int(.1 * n)], statistics.median(risks), risks[int(.9 * n)]
        le250 = sum(1 for x in risks if x <= 2.50)      # 0.25% of $1,000
        le10 = sum(1 for x in risks if x <= 10.0)       # 1% of $1,000
        min_acct = med / 0.0025                         # account where 1ct == 0.25%
        print("  %-14s %9.2f %9.2f %9.2f %8.1f%% %8.1f%% %9.0f"
              % (k, p10, med, p90, 100 * le250 / n, 100 * le10 / n, min_acct))
        out["floor"][k] = dict(p10=p10, median=med, p90=p90,
                               pct_le_2_50=100 * le250 / n, pct_le_10=100 * le10 / n,
                               min_account_for_0_25pct=min_acct)

    # ---- 7. the $1,000 account, simulated ------------------------------
    print("\n=== 7. THE $1,000 ACCOUNT, SIMULATED: 1 contract a trade ===")
    print("  cost = entry x %.4f x 100 (tape median).  loss capped at premium paid."
          % med_pct)
    print("  %-14s %8s %8s %10s %10s %10s %8s %8s"
          % ("arm", "taken", "skipped", "final $", "peak $", "trough $",
             "maxDD%", "ruin"))
    out["thousand_sim"] = {}
    for k, a in arms.items():
        eq = 1000.0
        peak = eq
        trough = eq
        maxdd = 0.0
        taken = skipped = 0
        ruin = False
        for r in a:
            cost = r["entry"] * med_pct * MULT
            prisk = abs(r["entry"] - r["stop"]) * DELTA * MULT
            if cost > eq:
                skipped += 1
                continue
            taken += 1
            pnl = r["r"] * prisk
            pnl = max(pnl, -cost)          # cannot lose more than the premium
            eq += pnl
            peak = max(peak, eq)
            trough = min(trough, eq)
            maxdd = max(maxdd, (peak - eq) / peak)
            if eq <= 0:
                ruin = True
                break
        print("  %-14s %8d %8d %10.0f %10.0f %10.0f %7.1f%% %8s"
              % (k, taken, skipped, eq, peak, trough, maxdd * 100,
                 "YES" if ruin else "no"))
        out["thousand_sim"][k] = dict(taken=taken, skipped=skipped, final=eq,
                                      peak=peak, trough=trough,
                                      max_dd_pct=maxdd * 100, ruin=ruin)

    # ---- 7b. same sim, but is it a prop-eval-shaped account? -----------
    print("\n  same $1,000 account, expressed as risk-per-trade in %% of account:")
    print("  %-14s %10s %10s %10s"
          % ("arm", "med risk%", "p90 risk%", "worst risk%"))
    for k, a in arms.items():
        pr = sorted(abs(r["entry"] - r["stop"]) * DELTA * MULT / 1000 * 100 for r in a)
        print("  %-14s %9.1f%% %9.1f%% %9.1f%%"
              % (k, statistics.median(pr), pr[int(.9 * len(pr))], pr[-1]))
        out["thousand_sim"][k]["risk_pct_median"] = statistics.median(pr)
        out["thousand_sim"][k]["risk_pct_p90"] = pr[int(.9 * len(pr))]
        out["thousand_sim"][k]["risk_pct_worst"] = pr[-1]

    json.dump(out, open(os.path.join(HERE, "g116b_floor_and_rolling.json"), "w"),
              indent=1)
    print("\nwrote research/g116b_floor_and_rolling.json")


if __name__ == "__main__":
    main()
