"""g154 refuter #3 -- reproduce be-stop-after-enough-past-pt1 from its own script,
then stress it: shipped-model baseline, paired significance, fine k grid,
contributor concentration, and the -1R floor after arming.

Imports the claim script itself so every number comes from ITS code, not a
re-implementation. Same fill: book entry (signal-bar close), stop_rule stops,
size-gated first_of_day_arm, 1R = $1000, H1/H2 split 2025-09-01.

    python research/g154_refute3_reproduce.py
"""
from __future__ import annotations
import importlib, json, os, random, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

g154 = importlib.import_module("g154_rule_be-stop-after-enough-past-pt1")
import g86_honest_ceiling as g86
import omen_metrics as om

H = g154.H_SPLIT
FINE_K = [round(0.05 * i, 2) for i in range(1, 41)]   # 0.05 .. 2.00


def half(rows, lo=None, hi=None, n=None):
    sub = [r for r in rows if (lo is None or r["day"] >= lo) and (hi is None or r["day"] < hi)]
    return g86.stats(sub, n)


def main():
    blob = json.load(open(g154.BOOK_PATH, encoding="utf-8"))
    rows = blob["trades"]
    nd = blob["meta"].get("sessions") or len({r["day"] for r in rows})
    nd1 = g154.n_days_in(rows, hi=H); nd2 = g154.n_days_in(rows, lo=H)
    firsts = om.first_of_day_arm(rows, size_gate=True)
    print("picks %d  sessions %d (H1 %d H2 %d)" % (len(firsts), nd, nd1, nd2))

    # --- A. the SHIPPED-model baseline: the book's own recorded r, untouched
    ship = g86.stats([dict(r) for r in firsts], nd)
    ship1 = half(firsts, hi=H, n=nd1); ship2 = half(firsts, lo=H, n=nd2)
    print("\nA. SHIPPED book r (no replay): $%d/day (H1 $%d, H2 $%d) meanR %+.3f win %.1f%% green %d/%d"
          % (ship["per_day"], ship1["per_day"], ship2["per_day"], ship["mean_r"],
             ship["win_pct"], ship["months_green"], ship["months"]))

    # --- replay once, keeping per-pick R for the fine grid
    g154.K_VALUES = tuple(FINE_K)
    base_rows, k_rows, nfb = g154.build_lists(firsts)
    print("   fallback picks: %d" % nfb)
    base = g86.stats(base_rows, nd)
    b1 = half(base_rows, hi=H, n=nd1); b2 = half(base_rows, lo=H, n=nd2)
    print("   SCRIPT no-BE replay baseline: $%d/day (H1 $%d, H2 $%d) meanR %+.3f"
          % (base["per_day"], b1["per_day"], b2["per_day"], base["mean_r"]))
    print("   -> replay baseline is %+.0f%% vs the shipped book on the same picks"
          % (100.0 * (base["per_day"] - ship["per_day"]) / abs(ship["per_day"])))

    # --- B. paired significance for the headline k=0.5
    K0 = 0.5
    br = [r["r"] for r in base_rows]; kr = [r["r"] for r in k_rows[K0]]
    d = [a - b for a, b in zip(kr, br)]
    changed = [i for i, x in enumerate(d) if abs(x) > 1e-9]
    md = statistics.mean(d); sd = statistics.pstdev(d)
    se = sd / (len(d) ** 0.5)
    print("\nB. k=0.50 paired delta over %d picks: %d changed (%.1f%%)"
          % (len(d), len(changed), 100.0 * len(changed) / len(d)))
    print("   mean dR %+.4f  sd %.4f  se %.4f  t %+.2f  -> $%+.1f/day"
          % (md, sd, se, md / se if se else 0.0, md * len(d) * g86.RISK / nd))
    random.seed(0)
    boots = []
    for _ in range(4000):
        s = [d[random.randrange(len(d))] for _ in range(len(d))]
        boots.append(sum(s) * g86.RISK / nd)
    boots.sort()
    print("   bootstrap 95%% CI on $/day delta: [%+.0f, %+.0f]"
          % (boots[100], boots[3899]))

    # contributor concentration
    top = sorted(changed, key=lambda i: -abs(d[i]))[:5]
    tot = sum(d)
    print("   top-5 |dR| picks carry %.0f%% of the total delta:" % (100.0 * sum(d[i] for i in top) / tot))
    for i in top:
        print("     %-6s %s  dR %+.2f  (base %+.2f -> k %+.2f)"
              % (base_rows[i]["sym"], base_rows[i]["day"], d[i], br[i], kr[i]))

    # --- C. fine k grid: is 0.50 a plateau or a spike?
    print("\nC. fine k grid (H1 delta / H2 delta / $per day / survivor)")
    surv = []
    grid = []
    for k in FINE_K:
        f = g86.stats(k_rows[k], nd)
        h1 = half(k_rows[k], hi=H, n=nd1); h2 = half(k_rows[k], lo=H, n=nd2)
        d1 = h1["per_day"] - b1["per_day"]; d2 = h2["per_day"] - b2["per_day"]
        s = d1 > 0 and d2 > 0
        grid.append((k, f["per_day"], d1, d2, s))
        if s:
            surv.append(k)
    for k, pd_, d1, d2, s in grid:
        print("   k=%.2f  $%4d/day  H1 %+5.0f  H2 %+5.0f  %s" % (k, pd_, d1, d2, "SURVIVOR" if s else ""))
    print("   survivors on the fine grid: %d/%d k values -> %s"
          % (len(surv), len(FINE_K), surv))

    # --- D. -1R floor after arming (CLAUDE.md: max loss is -1R hard)
    worse = [i for i, x in enumerate(kr) if x < -1.0 - 1e-9]
    worse_b = [i for i, x in enumerate(br) if x < -1.0 - 1e-9]
    print("\nD. picks booking worse than -1.000R: k=0.50 -> %d, baseline -> %d "
          "(stop_fill_price called with default floor_r=MAX_LOSS_R=1.25; the "
          "disaster-touch cap is disabled once armed)" % (len(worse), len(worse_b)))
    for i in worse[:5]:
        print("     %-6s %s  r %+.3f" % (base_rows[i]["sym"], base_rows[i]["day"], kr[i]))


if __name__ == "__main__":
    main()
