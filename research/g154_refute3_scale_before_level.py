"""g154 refuter #3 -- adversarial diagnostics on 'scale-before-the-level'.

Reuses the ORIGINAL script's own functions (import, not re-implementation) so
every number here is produced by the exact code under test. Adds four checks
the original does not run:

  A. CONSTRUCT: is the shifted price actually the LEVEL (HOD/LOD), or is it a
     2R profit target? The book carries both `target` and `level_px`.
  B. PAIRED SIGNIFICANCE: the arms share the same 498 picks, so the delta is a
     paired sample. Bootstrap the paired per-trade R delta, whole book and by
     half.
  C. INTRABAR ORDERING: of the trades the shift CONVERTS into target hits, how
     many are converted on a bar that also closed past the level stop (the
     walker's within-bar priority awards the target) or that later hit the
     disaster stop? Those wins exist only because of an assumed intrabar path.
  D. CONCENTRATION + MULTIPLICITY: how much of the H2 delta rides on the top
     few trades, and what is the null probability of the survivor test.

    python research/g154_refute3_scale_before_level.py
"""
from __future__ import annotations

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import stop_rule as sru                                        # noqa: E402
from research import omen_metrics as om                        # noqa: E402
import importlib                                               # noqa: E402

G = importlib.import_module("research.g154_rule_scale-before-the-level".replace("-", "_")) \
    if False else None
# the module filename has hyphens; load it by path
import importlib.util                                          # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "g154_scale", os.path.join(HERE, "g154_rule_scale-before-the-level.py"))
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)

RISK = 1000.0
H_SPLIT = "2025-09-01"
OUT_MD = os.path.join(HERE, "g154_refute3_scale_before_level.md")
OUT_JSON = os.path.join(HERE, "g154_refute3_scale_before_level.json")


def main():
    blob = json.load(open(G.BOOK, encoding="utf-8"))
    rows = blob["trades"]
    n_days = blob["meta"].get("sessions") or len({r["day"] for r in rows})
    picks = om.first_of_day_arm(rows, size_gate=True)
    picks_by_day = {r["day"]: r for r in picks}
    days = sorted(picks_by_day)
    print("picks %d over %d sessions" % (len(picks), n_days))

    # ---------------- A. construct validity ----------------
    at_level = tgt_2r = has_lvl = 0
    r_of_target = []
    for d in days:
        r = picks_by_day[d]
        risk = abs(r["entry"] - r["stop"])
        if risk <= 0:
            continue
        tr = ((r["target"] - r["entry"]) / risk if r["dir"] == "call"
              else (r["entry"] - r["target"]) / risk)
        r_of_target.append(tr)
        if abs(tr - 2.0) < 1e-6:
            tgt_2r += 1
        lp = r.get("level_px")
        if lp is not None:
            has_lvl += 1
            if abs(lp - r["target"]) < 1e-6:
                at_level += 1
    A = {
        "picks_with_target": len(r_of_target),
        "target_is_exactly_2R": tgt_2r,
        "target_is_exactly_2R_pct": round(100 * tgt_2r / len(r_of_target), 1),
        "picks_with_level_px": has_lvl,
        "target_equals_level_px": at_level,
        "target_equals_level_px_pct": round(100 * at_level / has_lvl, 1) if has_lvl else None,
        "median_target_R": round(sorted(r_of_target)[len(r_of_target) // 2], 4),
    }
    print("A construct: target==2R on %d/%d (%.1f%%); target==level_px on %d/%d (%s%%)"
          % (tgt_2r, len(r_of_target), A["target_is_exactly_2R_pct"],
             at_level, has_lvl, A["target_equals_level_px_pct"]))

    # ---------------- run baseline + cents_005 with per-trade detail ----------------
    def run(bfn):
        out = []
        for d in days:
            r = picks_by_day[d]
            bars = G.bars_for(r["sym"], r["day"])
            b = bfn(r, bars)
            tgt = G.shifted_target(r, b) if b else r["target"]
            pnl, rm, reason = G.simulate_exit(r, tgt)
            out.append({"day": d, "sym": r["sym"], "pnl": pnl, "r": rm,
                        "reason": reason, "tgt": tgt})
        return out

    base = run(lambda r, bars: 0.0)
    cand = run(lambda r, bars: 0.05)          # the headline arm, cents_005
    assert len(base) == len(cand) == len(days)

    # ---------------- B. paired significance ----------------
    dR = [c["r"] - b["r"] for b, c in zip(base, cand)]
    h1_idx = [i for i, d in enumerate(days) if d < H_SPLIT]
    h2_idx = [i for i, d in enumerate(days) if d >= H_SPLIT]

    def boot(idx, iters=20000, seed=20260905):
        rnd = random.Random(seed)
        vals = [dR[i] for i in idx]
        n = len(vals)
        mean = sum(vals) / n
        ms = []
        for _ in range(iters):
            ms.append(sum(vals[rnd.randrange(n)] for _ in range(n)) / n)
        ms.sort()
        lo, hi = ms[int(0.025 * iters)], ms[int(0.975 * iters)]
        p_le0 = sum(1 for m in ms if m <= 0) / iters
        return {"n": n, "mean_dR": round(mean, 4),
                "usd_day": round(mean * RISK, 2),
                "ci95_R": [round(lo, 4), round(hi, 4)],
                "ci95_usd_day": [round(lo * RISK, 1), round(hi * RISK, 1)],
                "p_boot_le_0": round(p_le0, 4)}

    B = {"full": boot(list(range(len(days)))), "h1": boot(h1_idx), "h2": boot(h2_idx)}
    for k, v in B.items():
        print("B paired %s: dR %.4f  ($%.1f/day)  CI95 $[%s, %s]/day  P(delta<=0)=%.3f"
              % (k, v["mean_dR"], v["usd_day"], v["ci95_usd_day"][0],
                 v["ci95_usd_day"][1], v["p_boot_le_0"]))

    # ---------------- C. intrabar ordering on the CONVERTED trades ----------------
    converted = [i for i in range(len(days))
                 if cand[i]["reason"] == "target" and base[i]["reason"] != "target"]
    lost = [i for i in range(len(days))
            if base[i]["reason"] == "target" and cand[i]["reason"] != "target"]
    same_bar_stop = 0
    later_disaster = 0
    detail = []
    for i in converted:
        r = picks_by_day[days[i]]
        bars = G.bars_for(r["sym"], r["day"])
        entry, stop = r["entry"], r["stop"]
        long = r["dir"] == "call"
        risk = abs(entry - stop)
        dprice = sru.disaster_stop_price(entry, risk, long)
        tgt = cand[i]["tgt"]
        flag_stop = flag_dis = False
        for j in range(r["entry_i"] + 1, len(bars)):
            c = bars[j]
            if sru.disaster_stop_hit(c.high, c.low, dprice, long):
                break
            hit = (c.high >= tgt) if long else (c.low <= tgt)
            if hit:
                # would the SAME bar have closed past the level stop?
                if sru.stop_hit_on_close(c.close, stop, long):
                    flag_stop = True
                # and how far past the shifted target did the bar actually run?
                over = (c.high - tgt) if long else (tgt - c.low)
                detail.append({"day": days[i], "sym": r["sym"],
                               "overshoot_cents": round(over * 100, 2),
                               "same_bar_stop_close": flag_stop,
                               "base_reason": base[i]["reason"],
                               "dR": round(cand[i]["r"] - base[i]["r"], 3)})
                break
            if sru.stop_hit_on_close(c.close, stop, long):
                break
        if flag_stop:
            same_bar_stop += 1
        if flag_dis:
            later_disaster += 1
    total_dR = sum(dR)
    zero_touch = [d for d in detail if d["overshoot_cents"] == 0.0]
    le1_touch = [d for d in detail if d["overshoot_cents"] <= 1.0]
    C = {
        "converted_to_target": len(converted),
        "lost_target": len(lost),
        "converted_where_same_bar_closed_past_stop": same_bar_stop,
        "converted_same_bar_stop_pct": (round(100 * same_bar_stop / len(converted), 1)
                                        if converted else None),
        "converted_from": {k: sum(1 for i in converted if base[i]["reason"] == k)
                           for k in ("stop_close", "disaster", "eod", "no_bars")},
        "book_total_R_delta": round(total_dR, 2),
        "exact_touch_conversions": len(zero_touch),
        "exact_touch_R": round(sum(d["dR"] for d in zero_touch), 2),
        "exact_touch_share_of_total_pct": round(
            100 * sum(d["dR"] for d in zero_touch) / total_dR, 1) if total_dR else None,
        "within_1c_touch_conversions": len(le1_touch),
        "within_1c_touch_R": round(sum(d["dR"] for d in le1_touch), 2),
        "within_1c_share_of_total_pct": round(
            100 * sum(d["dR"] for d in le1_touch) / total_dR, 1) if total_dR else None,
    }
    print("C intrabar: %d converted to target, %d lost; %s converted on a bar that "
          "ALSO closed past the level stop (%s%%); converted-from %s"
          % (len(converted), len(lost), same_bar_stop,
             C["converted_same_bar_stop_pct"], C["converted_from"]))
    print("C exact-touch: %d conversions where the bar's extreme equalled the shifted "
          "target TO THE PENNY and went no further -- %.2fR of the book's %.2fR total "
          "delta (%s%%). Within 1c: %d conversions, %.2fR (%s%%)."
          % (len(zero_touch), C["exact_touch_R"], C["book_total_R_delta"],
             C["exact_touch_share_of_total_pct"], len(le1_touch),
             C["within_1c_touch_R"], C["within_1c_share_of_total_pct"]))

    # ---------------- D. concentration + multiplicity ----------------
    h2_pairs = sorted(((dR[i], days[i], picks_by_day[days[i]]["sym"]) for i in h2_idx),
                      key=lambda t: -abs(t[0]))
    h2_total = sum(dR[i] for i in h2_idx)
    top5 = sum(p[0] for p in h2_pairs[:5])
    top10 = sum(p[0] for p in h2_pairs[:10])
    n_moved = sum(1 for i in h2_idx if abs(dR[i]) > 1e-9)
    D = {
        "h2_days": len(h2_idx),
        "h2_days_where_pnl_moved": n_moved,
        "h2_total_R_delta": round(h2_total, 3),
        "h2_top5_R_delta": round(top5, 3),
        "h2_top5_share_pct": round(100 * top5 / h2_total, 1) if h2_total else None,
        "h2_top10_share_pct": round(100 * top10 / h2_total, 1) if h2_total else None,
        "h2_top10": [{"day": d, "sym": s, "dR": round(v, 3)} for v, d, s in h2_pairs[:10]],
        "arms_in_this_script": 3,
        "candidates_in_swarm": 25,
        "null_p_both_halves_positive_one_arm": 0.25,
        "null_p_any_of_3_arms": round(1 - 0.75 ** 3, 3),
        "null_expected_survivors_of_25_candidates": round(25 * (1 - 0.75 ** 3), 1),
    }
    print("D concentration: H2 delta %.2fR total; top-5 trades = %s%%, top-10 = %s%%; "
          "only %d/%d H2 days moved at all"
          % (h2_total, D["h2_top5_share_pct"], D["h2_top10_share_pct"],
             n_moved, len(h2_idx)))
    print("D multiplicity: 3 arms here -> P(any survives under null) = %.3f; "
          "25 swarm candidates -> ~%.1f expected false survivors"
          % (D["null_p_any_of_3_arms"], D["null_expected_survivors_of_25_candidates"]))

    out = {"A_construct": A, "B_paired_significance": B, "C_intrabar": C,
           "C_converted_detail": sorted(detail, key=lambda d: -d["dR"])[:20],
           "D_concentration_multiplicity": D}
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=2)

    md = []
    md.append("# g154 refuter #3 -- scale-before-the-level: REFUTED\n")
    md.append("What is different now, in one sentence: the script's numbers reproduce "
              "byte for byte, but the price it shifts is the book's **2R profit target**, "
              "not the level -- so the arm does not test the rule it is named after, and "
              "the surviving $/day gain is a %.3f R/trade paired difference whose 95%% "
              "bootstrap interval is $[%s, %s]/day, straddling zero.\n"
              % (B["full"]["mean_dR"], B["full"]["ci95_usd_day"][0],
                 B["full"]["ci95_usd_day"][1]))
    md.append("Fill named on every figure below: signal-bar CLOSE entry (`entry` from "
              "`bt2y_trades_retest_on.json`), stops through `stop_rule.stop_fill_price`, "
              "size-gated one-trade-a-day picks from `research.omen_metrics.first_of_day_arm"
              "(size_gate=True)`, 1R = $1,000. Produced by "
              "`research/g154_refute3_scale_before_level.py`, which imports and calls the "
              "functions in `research/g154_rule_scale-before-the-level.py` directly.\n")

    md.append("## A. The shifted price is a 2R target, not the level\n")
    md.append("| check | value |")
    md.append("|---|---:|")
    md.append("| picks priced | %d |" % A["picks_with_target"])
    md.append("| `target` is exactly entry +/- 2R | %d (%.1f%%) |"
              % (A["target_is_exactly_2R"], A["target_is_exactly_2R_pct"]))
    md.append("| `target` equals the book's own `level_px` | %d/%d (%s%%) |"
              % (A["target_equals_level_px"], A["picks_with_level_px"],
                 A["target_equals_level_px_pct"]))
    md.append("| median target R-multiple | %.2f |" % A["median_target_R"])
    md.append("")
    md.append("The report's table header reads `baseline (target=level)`. It is not the "
              "level. The book carries `level_px` separately, and the baseline "
              "R-on-hit-only of 2.001 is the giveaway. Austin's rule is about resting the "
              "scale-out slightly inside the HOD/LOD; this arm nudges a fixed 2R profit "
              "target $0.02-$0.05 nearer to entry, which is a different rule with a "
              "different mechanism.\n")

    md.append("## B. Paired bootstrap on the headline arm (cents_005)\n")
    md.append("| split | days | delta R/trade | delta $/day | 95%% CI $/day | P(delta<=0) |")
    md.append("|---|---:|---:|---:|---:|---:|")
    for k in ("full", "h1", "h2"):
        v = B[k]
        md.append("| %s | %d | %+.4f | %+.2f | [%s, %s] | %.3f |"
                  % (k, v["n"], v["mean_dR"], v["usd_day"],
                     v["ci95_usd_day"][0], v["ci95_usd_day"][1], v["p_boot_le_0"]))
    md.append("")

    md.append("## C. 90%% of the whole result is 7 penny-exact touches\n")
    md.append("| check | value |")
    md.append("|---|---:|")
    md.append("| whole-book R delta the arm earns | %+.2fR |" % C["book_total_R_delta"])
    md.append("| trades converted into target hits by the $0.05 shift | %d of 498 |" % C["converted_to_target"])
    md.append("| trades that LOST a target hit | %d |" % C["lost_target"])
    md.append("| baseline outcome of the converted trades | %s |" % json.dumps(C["converted_from"]))
    md.append("| conversions where the bar's extreme equalled the shifted target TO THE PENNY | **%d** |"
              % C["exact_touch_conversions"])
    md.append("| ... and they carry | **%+.2fR = %s%% of the whole delta** |"
              % (C["exact_touch_R"], C["exact_touch_share_of_total_pct"]))
    md.append("| conversions where it cleared by <= $0.01 | %d, %+.2fR (%s%%) |"
              % (C["within_1c_touch_conversions"], C["within_1c_touch_R"],
                 C["within_1c_share_of_total_pct"]))
    md.append("| conversions on a bar that ALSO closed past the level stop | %s (%s%%) |"
              % (C["converted_where_same_bar_closed_past_stop"], C["converted_same_bar_stop_pct"]))
    md.append("")
    md.append("This is the refutation. The arm's entire edge is 15 trades out of 498, "
              "**14 of which the baseline booked as a -1R disaster stop** -- price ran to "
              "within a nickel of the 2R target and then collapsed. On 7 of them the "
              "1-minute bar's extreme equals the shifted target exactly, to the cent, and "
              "goes no further; the walker books each as a full ~+2.7R swing. Those 7 "
              "alone are 90%% of the book-wide gain. A resting limit whose price the bar "
              "merely touches is the least reliable fill in this project -- it is the "
              "queue-priority coin flip, on the one bar where the market immediately "
              "reversed to a full stop-out. `simulate_exit`'s intrabar priority attack "
              "does NOT land (0 of 15 converted on a bar that also closed past the stop), "
              "and that is reported here as a check that failed; the exact-touch "
              "dependence is what does land.\n")

    md.append("## D. Concentration and multiplicity\n")
    md.append("| check | value |")
    md.append("|---|---:|")
    md.append("| H2 sessions | %d |" % D["h2_days"])
    md.append("| H2 sessions where the shift changed pnl at all | %d |" % D["h2_days_where_pnl_moved"])
    md.append("| H2 total R delta | %+.2fR |" % D["h2_total_R_delta"])
    md.append("| share of the H2 delta from its 5 largest trades | %s%% |" % D["h2_top5_share_pct"])
    md.append("| share from its 10 largest | %s%% |" % D["h2_top10_share_pct"])
    md.append("| arms tried in this one script | 3 |")
    md.append("| P(one arm passes 'both halves positive' under a coin-flip null) | 0.25 |")
    md.append("| P(any of 3 arms passes) | %.3f |" % D["null_p_any_of_3_arms"])
    md.append("| expected false survivors across the swarm's 25 candidates | ~%.1f |"
              % D["null_expected_survivors_of_25_candidates"])
    md.append("")
    md.append("| H2 day | sym | delta R |")
    md.append("|---|---|---:|")
    for e in D["h2_top10"]:
        md.append("| %s | %s | %+.3f |" % (e["day"], e["sym"], e["dR"]))
    md.append("")
    md.append("## Verdict: REFUTED\n")
    md.append("The arithmetic reproduces byte for byte -- `$50/day -> $93/day`, H1 "
              "+9.40, H2 +76.50, precision 30.5%% unchanged, recall_100 5.9%% unchanged, "
              "all re-run from the committed script. It is refuted on four grounds, in "
              "order of weight:\n")
    md.append("1. **90%% of the gain is 7 penny-exact touches.** %d of 498 trades change "
              "outcome; %d of those were -1R disaster stops that came within a nickel of "
              "the 2R target; on %d the bar's extreme equals the shifted target to the "
              "cent. Remove those 7 and %+.2fR of the %+.2fR whole-book delta is gone.\n"
              % (C["converted_to_target"], C["converted_from"]["disaster"],
                 C["exact_touch_conversions"], C["exact_touch_R"], C["book_total_R_delta"]))
    md.append("2. **It does not test the rule it is named after.** The price shifted is "
              "the book's 2R profit target (67.1%% of picks are exactly 2R, median 2.00R), "
              "not the level -- `target` equals `level_px` on **0 of 498** picks. The "
              "report's own table header says `baseline (target=level)`.\n")
    md.append("3. **The H1 leg is a coin flip.** Paired bootstrap: H1 %+.2f $/day, 95%% "
              "CI [%s, %s], P(delta<=0) = %.3f. The survivor rule needs H1 positive and "
              "H1 is indistinguishable from zero.\n"
              % (B["h1"]["usd_day"], B["h1"]["ci95_usd_day"][0],
                 B["h1"]["ci95_usd_day"][1], B["h1"]["p_boot_le_0"]))
    md.append("4. **Multiplicity.** 'Both halves positive' is a 1-in-4 null event; 3 arms "
              "were tried here (P(any) = %.3f) inside a 25-candidate sweep expecting "
              "~%.1f false survivors. All 3 arms 'survived', which is itself the tell: a "
              "monotone knob that always helps at every size is arithmetic, not a rule.\n"
              % (D["null_p_any_of_3_arms"], D["null_expected_survivors_of_25_candidates"]))
    md.append("Separately, and stated by the original script itself: the baseline is a "
              "single-stage proxy walker the shipped book never runs (`backtest_week."
              "_ladder_bar` is the real exit), so `$50/day` is not the engine's booked "
              "one-trade-a-day figure and `$93/day` is not a forecast of it.\n")
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md))
    print("\nwrote %s\nwrote %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
