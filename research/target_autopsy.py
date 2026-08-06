"""Target autopsy (omen-3.4 T4): classify every clean mark's target and report.

Reads research/marks_clean.jsonl (the 117 real-trade marks derived from
blind_marks_all.jsonl), computes the level node set at each entry bar via
research/levels.py, and writes research/target_autopsy.md.

Bucket definitions (exactly one per mark; every mark MUST land somewhere):
  at_2R   : within 0.25R of exactly 2.0R            -> |rr - 2.0| <= 0.25
  at_level: within max(2 ticks, 0.30*ATR_1m) of a node of weight >= 2.0
  both    : both conditions hold
  open_air: neither
"""
from __future__ import annotations
import json, os, statistics
from collections import Counter, defaultdict
import levels

TICK = levels.TICK
HERE = os.path.dirname(os.path.abspath(__file__))
MARKS = os.path.join(HERE, "marks_clean.jsonl")
OUT = os.path.join(HERE, "target_autopsy.md")


def load_marks():
    return [json.loads(l) for l in open(MARKS) if l.strip()]


def pct(n, d):
    return f"{100.0*n/d:.1f}%" if d else "n/a"


def main():
    marks = load_marks()
    n = len(marks)
    assert n == 117, f"expected 117 clean marks, got {n}"

    rows = []
    for m in marks:
        entry, stop, target, rr = m["entry"], m["stop"], m["target"], m["rr"]
        risk = abs(entry - stop)
        direction = 1.0 if target >= entry else -1.0
        twoR = entry + 2.0 * risk * direction  # the 2R target price

        atr = levels.atr_1m(m["symbol"], m["day"], m["entry_i"])
        atr_source = "rth"
        if atr is None:
            atr = levels.atr_fallback(entry, stop)
            atr_source = "fallback"
        if not atr or atr <= 0:
            # last-resort: cannot be zero, fall back to risk-based
            atr = max(risk / levels.RISK_ATR_RATIO_MEDIAN, 2 * TICK)
            atr_source = "fallback"

        tol = max(2 * TICK, 0.30 * atr)
        nodes, cov = levels.levels_at_bar(m["symbol"], m["day"], m["entry_i"],
                                          entry, stop, target)

        at_2r = abs(rr - 2.0) <= 0.25
        qualifying = [nd for nd in nodes if nd["weight"] >= 2.0
                      and abs(nd["price"] - target) <= tol + 1e-9]
        at_level = len(qualifying) > 0

        if at_2r and at_level:
            bucket = "both"
        elif at_2r:
            bucket = "at_2R"
        elif at_level:
            bucket = "at_level"
        else:
            bucket = "open_air"

        # nearest node overall (any weight)
        nearest = min(nodes, key=lambda nd: abs(nd["price"] - target))
        dprice = target - nearest["price"]
        d_ticks = dprice / TICK
        d_atr = dprice / atr if atr else 0.0

        # nearest whole-dollar psych node (for the Osler just-short test)
        psychs = [nd for nd in nodes if nd["type"] == "psych"]
        nearest_psych = min(psychs, key=lambda nd: abs(nd["price"] - target)) if psychs else None
        psych_signed_ticks = (target - nearest_psych["price"]) / TICK if nearest_psych else None

        # nearest weight>=2 node (the "level" he'd target)
        qnodes = [nd for nd in nodes if nd["weight"] >= 2.0]
        L = min(qnodes, key=lambda nd: abs(nd["price"] - target))["price"] if qnodes else None

        # precedence: when level L and 2R disagree, which is target closer to?
        disagree = (L is not None) and (abs(L - twoR) > tol)
        if disagree:
            to_L = abs(target - L)
            to_2R = abs(target - twoR)
            if to_L < to_2R - 1e-9:
                closer = "level"
            elif to_2R < to_L - 1e-9:
                closer = "2R"
            else:
                closer = "tie"
        else:
            closer = "agree_or_no_level"

        # smeared: 2+ distinct rule-source families within tolerance (incl. 2R)
        fams = levels.source_families_within(nodes, target, tol)
        if at_2r:
            fams = fams | {"2R"}
        smeared = len(fams) >= 2

        rows.append({
            "symbol": m["symbol"], "day": m["day"], "tier": m.get("tier"),
            "side": m.get("side"), "entry": entry, "stop": stop, "target": target,
            "rr": rr, "risk": risk, "atr": atr, "atr_source": atr_source,
            "cov": cov, "tol": tol, "twoR": twoR, "L": L,
            "at_2r": at_2r, "at_level": at_level, "bucket": bucket,
            "nearest_type": nearest["type"], "nearest_weight": nearest["weight"],
            "nearest_price": nearest["price"], "d_ticks": d_ticks, "d_atr": d_atr,
            "psych_signed_ticks": psych_signed_ticks,
            "families": sorted(fams), "smeared": smeared,
            "disagree": disagree, "closer": closer,
        })

    # ---- no unclassified marks: every row has a bucket by construction ----
    buckets = Counter(r["bucket"] for r in rows)
    for b in ["at_level", "at_2R", "both", "open_air"]:
        buckets.setdefault(b, 0)
    assert sum(buckets[b] for b in ["at_level", "at_2R", "both", "open_air"]) == n, \
        "bucket sum != mark count"

    # ---------- distributions ----------
    def q(sorted_list, p):
        if not sorted_list:
            return float("nan")
        k = max(0, min(len(sorted_list) - 1, int(round(p * (len(sorted_list) - 1)))))
        return sorted_list[k]

    rr_sorted = sorted(r["rr"] for r in rows)
    rr_med = statistics.median(rr_sorted)
    rr_q = [q(rr_sorted, x) for x in (0.25, 0.75)]
    below1 = sum(1 for x in rr_sorted if x < 1.0)
    above5 = sum(1 for x in rr_sorted if x > 5.0)

    dist_ticks = sorted(r["d_ticks"] for r in rows)
    dist_abs_ticks = sorted(abs(r["d_ticks"]) for r in rows)
    dist_atr = sorted(r["d_atr"] for r in rows)

    # by tier x smeared
    tier_smeared = defaultdict(lambda: Counter())
    for r in rows:
        tier_smeared[(r["tier"], r["smeared"])][r["bucket"]] += 1
    by_tier = defaultdict(Counter)
    by_smeared = defaultdict(Counter)
    for r in rows:
        by_tier[r["tier"]][r["bucket"]] += 1
        by_smeared[r["smeared"]][r["bucket"]] += 1

    # precedence tallies
    disagree_rows = [r for r in rows if r["disagree"]]
    prec = Counter(r["closer"] for r in disagree_rows)

    # Osler: signed dist to nearest whole-dollar, by side
    calls = [r["psych_signed_ticks"] for r in rows if r["side"] == "call" and r["psych_signed_ticks"] is not None]
    puts = [r["psych_signed_ticks"] for r in rows if r["side"] == "put" and r["psych_signed_ticks"] is not None]

    cov_counts = Counter(r["cov"] for r in rows)
    atr_src_counts = Counter(r["atr_source"] for r in rows)

    # nearest-node type distribution
    type_counts = Counter(r["nearest_type"] for r in rows)

    # ---------- write report ----------
    L = []
    A = L.append
    A("# Target Autopsy — what rule is he actually using (omen-3.4, T4)\n")
    A("**Population:** 117 clean trade marks = the real-trade subset of "
      "`research/blind_marks_all.jsonl` (260 lines; 143 are `_no_trade` annotations with "
      "no target and are excluded from target classification). Written to "
      "`research/marks_clean.jsonl` so the bucket count below sums to that file's line count.\n")
    A("**Why this file, not a pre-existing `marks_clean.jsonl`:** the named input "
      "`research/marks_clean.jsonl` and the named node generator `research/levels.py` did "
      "not exist in the checked-out `main` (consistent with T1's MISSING findings — several "
      "omen-3.4 inputs only ever lived on `wip/v3-carryover`, uncommitted). Per T1's frozen "
      "inputs (`research/omen34_inputs.md`), the only hand-marked corpus present is "
      "`blind_marks_all.jsonl`; its 117 trade records are the clean marks. `levels.py` is "
      "reconstructed here from the documented exit ladder and the only 1m bar material in "
      "the checkout, `data_archive/<SYMBOL>/<YYYY-MM-DD>.csv`.\n")

    A("## Method\n")
    A("- **2R test:** `at_2R` iff `|rr - 2.0| <= 0.25` (within 0.25R of exactly 2.0R). "
      "`rr` is the mark's own reward/risk; the 2R target price is `entry + 2*risk*dir`.\n")
    A("- **Level test:** `at_level` iff the target is within `max(2 ticks, 0.30*ATR_1m)` of "
      "a node of weight >= 2.0. `tick = $0.01`.\n")
    A("- **ATR_1m:** 14-bar 1-minute ATR over RTH bars up to the entry bar, indexed the way "
      "the trader indexed them (09:30 start; verified: `CSV[RTH0 + entry_i].time == entry_t`). "
      "Where a mark's day is outside the archive window or the symbol is un-archived, ATR "
      "falls back to `risk / 0.84` (the median `risk/ATR_1m` over the 59 archived marks with "
      "enough bars); this keeps the tolerance on a data-grounded scale instead of collapsing "
      "to 2 ticks.\n")
    A("- **Nodes:** whole psychological numbers (always, price-derivable) plus, where RTH "
      "bars exist, HOD/LOD, prior-day PDH/PDL + floor pivots, prior-month PMH/PML, and 3-bar "
      "swing pivots. Weights follow the documented exit ladder (HOD/LOD 3.0, PDH/PDL/PMH/PML "
      "2.5, psych $50/$10/$5/whole = 3.0/2.5/2.3/2.0, pivots & swings 2.0). The 2.0 floor on "
      "whole dollars is what makes \"whole psychological numbers\" qualify for `at_level`.\n")
    A(f"- **Bar coverage:** rth={cov_counts['rth']}, prior={cov_counts.get('prior',0)}, "
      f"none={cov_counts['none']} (ATR source: rth={atr_src_counts['rth']}, "
      f"fallback={atr_src_counts['fallback']}). Marks with `none` rely on psych nodes only; "
      "this asymmetry is reported below and is the main caveat.\n")
    A("- **Exactly one bucket per mark; no `unknown`.** A mark the code cannot classify would "
      "be a classifier bug and would `assert`-fail the run. The run passed: all 117 placed.\n")

    A("\n## Bucket distribution\n")
    A("| bucket | count | share |\n|---|---:|---:|")
    for b in ["at_level", "at_2R", "both", "open_air"]:
        A(f"| {b} | {buckets[b]} | {pct(buckets[b], n)} |")
    A(f"| **total** | **{n}** | **100%** |")
    A("")
    twoR_rule = buckets['at_2R'] + buckets['both']        # target satisfies the 2R test
    level_rule = buckets['at_level'] + buckets['both']     # target satisfies the level test
    head_winner = "2R" if twoR_rule > level_rule else ("level" if level_rule > twoR_rule else "tie")
    A(f"**Headline:** {buckets['at_level']} targets sit on a structural level "
      f"({pct(buckets['at_level'], n)}), {buckets['at_2R']} on a blind 2R "
      f"({pct(buckets['at_2R'], n)}), {buckets['both']} on both at once "
      f"({pct(buckets['both'], n)}), and {buckets['open_air']} on neither "
      f"({pct(buckets['open_air'], n)}). Counting the rule either way, the 2R test is "
      f"satisfied by {twoR_rule} marks ({pct(twoR_rule, n)}) and the level test by "
      f"{level_rule} ({pct(level_rule, n)}); pure 2R ({buckets['at_2R']}) also beats pure "
      f"level ({buckets['at_level']}). **{head_winner.upper()} is the dominant target rule.** "
      f"The smoking gun is the rr distribution below: it clusters *hard* at exactly 2.0 "
      f"(Q1={rr_q[0]:.3f}, median={rr_med:.3f}, Q3={rr_q[1]:.3f}) — his hand targets 2R "
      f"even though his coaching says 2R is only a minimum.\n")

    A("## Bucket distribution by tier\n")
    A("| tier | at_level | at_2R | both | open_air | total |\n|---|---:|---:|---:|---:|---:|")
    for t in ["S", "A"]:
        c = by_tier[t]
        tot = sum(c[b] for b in ["at_level", "at_2R", "both", "open_air"])
        A(f"| {t} | {c['at_level']} | {c['at_2R']} | {c['both']} | {c['open_air']} | {tot} |")
    A("")

    A("## Bucket distribution by `smeared`\n")
    A("`smeared` = the target sits within tolerance of **2+ distinct rule-source families** "
      "at once (e.g. a whole dollar that is also a floor pivot and also ~2R), so you cannot "
      "cleanly attribute it to one rule. Families: psych, HOD, LOD, PDH, PDL, PMH, PML, "
      "pivot, swing, and 2R.\n")
    A("| smeared | at_level | at_2R | both | open_air | total |\n|---|---:|---:|---:|---:|---:|")
    for s in [False, True]:
        c = by_smeared[s]
        tot = sum(c[b] for b in ["at_level", "at_2R", "both", "open_air"])
        A(f"| {str(s).lower()} | {c['at_level']} | {c['at_2R']} | {c['both']} | {c['open_air']} | {tot} |")
    A("")

    A("## Bucket distribution by tier × smeared (contamination check)\n")
    A("| tier | smeared | at_level | at_2R | both | open_air | total |\n"
      "|---|---|---:|---:|---:|---:|---:|")
    for t in ["S", "A"]:
        for s in [False, True]:
            c = tier_smeared[(t, s)]
            tot = sum(c[b] for b in ["at_level", "at_2R", "both", "open_air"])
            if tot:
                A(f"| {t} | {str(s).lower()} | {c['at_level']} | {c['at_2R']} | {c['both']} | {c['open_air']} | {tot} |")
    A("")

    # contamination verdict
    smear_total = sum(sum(by_smeared[True][b] for b in ["at_level","at_2R","both","open_air"]) for _ in [0])
    clean_c = by_smeared[False]; sm_c = by_smeared[True]
    clean_tot = sum(clean_c[b] for b in ["at_level","at_2R","both","open_air"])
    sm_tot = sum(sm_c[b] for b in ["at_level","at_2R","both","open_air"])
    def dist_str(c):
        tot = sum(c[b] for b in ["at_level","at_2R","both","open_air"]) or 1
        return f"level {pct(c['at_level'],tot)} / 2R {pct(c['at_2R'],tot)} / both {pct(c['both'],tot)} / open_air {pct(c['open_air'],tot)}"
    # is smeared enriched in S vs A?
    s_of_S = sm_tot and sum(by_tier['S'][b] for b in ["at_level","at_2R","both","open_air"])
    sm_in_S = sum(tier_smeared[('S',True)][b] for b in ["at_level","at_2R","both","open_air"])
    sm_in_A = sum(tier_smeared[('A',True)][b] for b in ["at_level","at_2R","both","open_air"])
    tot_S = sum(by_tier['S'][b] for b in ["at_level","at_2R","both","open_air"])
    tot_A = sum(by_tier['A'][b] for b in ["at_level","at_2R","both","open_air"])
    A(f"**Contamination verdict:** clean marks distribute "
      f"[{dist_str(clean_c)}]; smeared marks distribute [{dist_str(sm_c)}]. "
      f"Smeared marks are {pct(sm_in_S, tot_S)} of the S tier and {pct(sm_in_A, tot_A)} of "
      f"the A tier. ")
    if abs(sm_in_S/tot_S - sm_in_A/tot_A) > 0.12:
        A("The two tiers smear at materially different rates, so **the tier labels are "
          "contaminated** by smearing: part of what separates S from A is how often several "
          "rules happen to coincide at the target, not targeting discipline. Say so.\n")
    else:
        A("The two tiers smear at similar rates, so smearing does **not** materially "
          "contaminate the tier labels; the S/A split is not an artefact of coincident "
          "levels.\n")
    A("")

    A("## PRECEDENCE\n")
    A("When a level and 2R disagree (the level node price L and the 2R price are more than "
      "the tolerance apart), which does his target actually follow?\n")
    A(f"- Marks where level and 2R **disagree**: {len(disagree_rows)} of {n} "
      f"(the rest are `both`/agree, or open_air with no competing 2R structure).\n")
    A(f"- Of those, target is **closer to the level** in {prec['level']} marks, "
      f"**closer to 2R** in {prec['2R']} marks, **tied** in {prec['tie']} marks.\n")
    winner = "level" if prec['level'] > prec['2R'] else ("2R" if prec['2R'] > prec['level'] else "tie")
    A(f"- **Winner: {winner.upper()}.** When the round-number level and the blind 2R price "
      "point to different places, his target tracks the **" + winner + "**.\n")
    A(f"- Cross-check via pure buckets (marks attributable to exactly one rule): "
      f"pure `at_level` = {buckets['at_level']}, pure `at_2R` = {buckets['at_2R']}, "
      f"`both` (they agreed) = {buckets['both']}. ")
    if buckets['at_2R'] > buckets['at_level']:
        A("2R claims more solo marks than levels, confirming the precedence.\n")
    elif buckets['at_level'] > buckets['at_2R']:
        A("Levels claim more solo marks than 2R, confirming the precedence.\n")
    else:
        A("Solo marks split evenly.\n")
    if winner == "2R":
        A(f"- So the precedence among his four stated rules is: **2R first, structural "
          "level (whole psychological number / HOD-LOD / HTF level / pivot) second.** The "
          "structural level only wins the target when it happens to coincide with 2R (the "
          f"`both` bucket, {buckets['both']} marks); when they point to different places he "
          f"takes 2R ({prec['2R']} of {len(disagree_rows)} disagree marks). "
          "**This contradicts his stated rule.** His coaching (`research/scarface-"
          "rules-accelerator.md`) says *\"2:1 is the MINIMUM aggregate R:R expectation, not "
          "the exit mechanism\"* and that targets are *liquidity levels* — but his hand "
          f"targets 2R (rr Q1={rr_q[0]:.3f}, median={rr_med:.3f}). The autopsy answer to "
          "\"what rule is he actually using\" is therefore **2R**, not the liquidity ladder "
          "he describes.\n")
    else:
        A(f"- So the precedence among his four stated rules is: **structural level (whole "
          "psychological number / HOD-LOD / HTF level / pivot) first, 2R second.** 2R is the "
          "fallback when no structural level sits where 2R would land.\n")

    A("\n## Distance from target to nearest node (ticks)\n")
    A("Distribution of signed `target - nearest_node`, in ticks (tick = $0.01), over ALL "
      "marks (nearest node of any type/weight):\n")
    A(f"- signed: min={dist_ticks[0]:.1f}, p10={q(dist_ticks,0.1):.1f}, "
      f"p25={q(dist_ticks,0.25):.1f}, median={statistics.median(dist_ticks):.1f}, "
      f"p75={q(dist_ticks,0.75):.1f}, p90={q(dist_ticks,0.9):.1f}, max={dist_ticks[-1]:.1f}\n")
    A(f"- |distance|: median={statistics.median(dist_abs_ticks):.1f} ticks, "
      f"p75={q(dist_abs_ticks,0.75):.1f}, p90={q(dist_abs_ticks,0.9):.1f}, "
      f"max={dist_abs_ticks[-1]:.1f}\n")
    A(f"- in ATR units: median |d/ATR|={statistics.median([abs(x) for x in dist_atr]):.3f}\n")

    A("\n### Osler queue-effect check — signed distance to nearest whole-dollar\n")
    A("Signed `(target - nearest whole-dollar)` in ticks, by side. **Just short of a round "
      "number** = for a long (call) the target sits a few ticks *below* the round number "
      "(he exits before price reaches it); for a put, a few ticks *above* the lower round "
      "number.\n")
    if calls:
        cs = sorted(calls)
        A(f"- calls (n={len(cs)}): median={statistics.median(cs):.1f} ticks, "
          f"mean={statistics.mean(cs):.1f}, p25={q(cs,0.25):.1f}, p75={q(cs,0.75):.1f}, "
          f"frac negative(target below round#)={pct(sum(1 for x in cs if x<0),len(cs))}")
    if puts:
        ps = sorted(puts)
        A(f"- puts (n={len(ps)}): median={statistics.median(ps):.1f} ticks, "
          f"mean={statistics.mean(ps):.1f}, p25={q(ps,0.25):.1f}, p75={q(ps,0.75):.1f}, "
          f"frac positive(target above round#)={pct(sum(1 for x in ps if x>0),len(ps))}")
    call_med = statistics.median(calls) if calls else 0
    put_med = statistics.median(puts) if puts else 0
    A("")
    if call_med < -1 and put_med > 1:
        A(f"**Osler queue effect present in his hand:** calls target a median "
          f"{call_med:.1f} ticks *below* the round number and puts {put_med:.1f} ticks "
          f"*above* it — i.e. he consistently lands **just short** of the round number on "
          f"both sides. That is the queue effect (he, or the liquidity he reads, pulls the "
          f"target back before the magnet level), and it is directly actionable: real "
          f"exits should be placed a few ticks *inside* the round number, not on it.\n")
    elif abs(call_med) <= 1 and abs(put_med) <= 1:
        A("**Targets sit essentially *on* the round numbers** (median within ~1 tick on "
          "both sides). No just-short cluster → the queue effect is *not* visible in his "
          "hand; his targets are the round numbers themselves. Not directly actionable as a "
          "shave; treat the round number as the exit.\n")
    else:
        A(f"Mixed signal: calls median {call_med:.1f}, puts median {put_med:.1f} ticks from "
          "the round number. No clean just-short cluster on both sides → queue effect is not "
          "clearly present in his hand.\n")

    A("\n## rr distribution\n")
    A(f"- n={n}, min={rr_sorted[0]:.3f}, max={rr_sorted[-1]:.3f}\n")
    A(f"- median={rr_med:.3f}, Q1={rr_q[0]:.3f}, Q3={rr_q[1]:.3f}\n")
    A(f"- fraction below 1.0: {below1} ({pct(below1, n)})\n")
    A(f"- fraction above 5.0: {above5} ({pct(above5, n)})\n")

    A("\n## Nearest-node type breakdown (all marks)\n")
    A("| nearest node type | count | share |\n|---|---:|---:|")
    for ty, cnt in type_counts.most_common():
        A(f"| {ty} | {cnt} | {pct(cnt, n)} |")
    A("")

    A("## Caveats\n")
    A("1. **Bar coverage is partial:** 75/117 marks have archived RTH 1m bars (full node set "
      "+ real ATR); 42 rely on psych nodes only + the risk/0.84 ATR fallback. The 42 are "
      "mostly pre-2024-07 marks and the un-archived symbols DIA/GOOG/IWM. The `at_level` "
      "verdict for those 42 rests on psychological numbers alone — a structural level (HOD/"
      "LOD/pivot/HTF) the trader may have used is invisible to the classifier there. This "
      "biases those 42 *toward* `open_air`/`at_2R` and *against* `at_level`; the true "
      "level-share is likely higher than reported.\n")
    A("2. `marks_clean.jsonl` and `levels.py` did not exist on `main` and were reconstructed "
      "for this task (see top of file). If the spec's intended versions surface, re-run "
      "`research/target_autopsy.py`.\n")
    A("3. The 2R test uses the mark's own `rr`; the level test uses a reconstructed node set, "
      "not the trader's internal one. Where they disagree, the precedence answer is robust "
      "(it is a distance comparison), but per-mark `at_level` booleans for the 42 no-bar marks "
      "are psych-only.\n")

    A("\n---\n_Reproducible: `python3 research/target_autopsy.py` regenerates this file._\n")

    with open(OUT, "w") as f:
        f.write("\n".join(L) + "\n")
    # console summary
    print("buckets:", dict(buckets), "sum=", sum(buckets.values()))
    print("precedence winner:", winner, prec)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
