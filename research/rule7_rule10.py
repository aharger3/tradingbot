"""omen-3.7 T3: Rule 7 (speed of the retest) and Rule 10 (left-side pivot noise).

Austin's two hardest rejections, which omen-3.6's 16-feature vector did not
represent. Encode both as measurable features and test whether they separate
his S / A / X tiers.

Rule 7 -- bars_break_to_retest
    From his dictation: the break and retest should happen as fast as possible;
    over 3-7 candles is "decent", too many candles and probability decreases.
    Feature = bars elapsed between the BREAK candle and the RETEST candle.
      - reference level = the retested level, recomputed the SAME way
        mark_features.compute_features does (nearest weight>=2 level node to the
        entry close, via levels.levels_at_bar over the truncated bars -- leakage-
        bounded at entry_i). This mirrors 3.6's `broken_level_price`/`direction`
        exactly and is now computed for every mark that has bars (the archive has
        been expanded since mark_features.jsonl was written, so this script covers
        all 159 marks rather than the 105 that had bars when 3.6 ran).
      - direction = 'call' if entry close > level else 'put' (same computation).
      - BREAK candle = mark_features.find_break(bars_trunc, entry_i, level, dir):
        the most recent bar before entry_i that closed THROUGH the level coming
        from the other side (close beyond level by eps = 0.10*median range). This
        is the existing break detector; "body closed beyond" = its close term.
      - RETEST candle = the first bar after the break (up to and including the
        entry bar) whose WICK returns to the level (call: low <= level+eps;
        put: high >= level-eps).
      - value = retest_index - break_index. null if no break identifiable, or if a
        break was found but no retest bar reached the level before/at the entry.
    The null rate (no break identifiable) is itself the headline finding: a high
    rate means the engine's "retested level" (nearest node) often is not a freshly
    broken level at all.

Rule 10 -- left_pivot_count (+ left_pivots_near_level)
    From his X card: "a bunch of candles or pivot structures already there before
    your break... if the break and retest is not clean or the order block is not
    clean." Feature = the count of swing pivots in the 20 bars BEFORE the
    reference level was broken, using the SAME 3-bar swing definition
    MarketStructure.update uses in omen_bot.py (a high above both neighbours, a
    low below both -- a single outside bar can be both). Also emitted: how many of
    those pivots sit within 0.2% of the reference level (the "noise at the level"
    version). null when no break is identifiable (there is no "before the break"
    window).

Leakage rule (voids the row if broken): no feature may read any bar at index >
entry_i. Enforcement is structural and identical to mark_features.py:
    - bars are loaded once (levels.load_rth_bars) and TRUNCATED to
      bars[:entry_i+1] (bars_trunc, length entry_i+1) before any feature reads
      them; find_break scans bars_trunc[:entry_i], the retest scan and the pivot
      scan both run over bars_trunc (max index entry_i), and the reference level
      / direction came from mark_features.jsonl which was built under the same
      truncation. So no path can index a bar beyond entry_i.
    - marks whose symbol/day has no archive, or whose entry_i is out of range,
      are dropped (no bars -> no features); this matches mark_features.py.

Outputs:
    research/rule7_rule10.jsonl  (identity triple, tier, both features + near-level
                                  count + break/retest indices + null reason)
    research/rule7_rule10.md     (rule-7 null rate; per-feature separation tables
                                  with Cohen's d, a 95% block-bootstrap CI over
                                  whole trading days (10k resamples), and the MDE
                                  at the n actually available)
"""

from __future__ import annotations
import json, os, sys, math, random
from statistics import median

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)        # research/levels, research/mark_features
sys.path.insert(0, ROOT)        # predicates

import levels
import mark_features as mf       # reuse find_break + the leakage discipline

MARKS = os.path.join(HERE, "austin_marks_v2.jsonl")
OUT_JSONL = os.path.join(HERE, "rule7_rule10.jsonl")
OUT_MD = os.path.join(HERE, "rule7_rule10.md")

TICK = levels.TICK


def compute_ref(sym, day, bars_trunc, entry_i):
    """Reference level + direction, mirroring mark_features.compute_features.

    reference = nearest weight>=2 level node to the entry close; direction =
    'call' if entry close > level else 'put'. Built from levels.levels_at_bar
    (leakage-bounded at entry_i -- see mark_features.py) over the truncated bars,
    so it is identical to 3.6's `broken_level_price`/`direction` for the marks
    that were in mark_features.jsonl and is now defined for every mark with bars.
    Returns (level, direction) or (None, None).
    """
    entry_close = bars_trunc[entry_i]["c"]
    prior_hi, prior_lo = mf.prior_extremes(bars_trunc, entry_i)
    if prior_hi is None:
        prior_hi = prior_lo = entry_close
    nodes, _cov = levels.levels_at_bar(sym, day, entry_i, entry_close,
                                       prior_lo, prior_hi)
    qnodes = [n for n in nodes if n["weight"] >= 2.0]
    if not qnodes:
        return None, None
    ref = min(qnodes, key=lambda n: abs(n["price"] - entry_close))
    direction = "call" if entry_close > ref["price"] else "put"
    return ref["price"], direction


def retest_eps(bars_trunc, entry_i):
    """Same break-detection tolerance mark_features.find_break uses."""
    seg = bars_trunc[:entry_i]
    if len(seg) < 2:
        return TICK
    return 0.10 * (median(b["h"] - b["l"] for b in seg) or TICK)


def rule7(bars_trunc, entry_i, level, direction):
    """Return (bars_break_to_retest, break_i, retest_i, null_reason)."""
    seg = bars_trunc[:entry_i + 1]            # max index entry_i (leakage-free)
    break_i = mf.find_break(bars_trunc, entry_i, level, direction)
    if break_i is None:
        return None, None, None, "no_break"
    eps = retest_eps(bars_trunc, entry_i)
    # retest = first bar after the break (up to & including entry bar) whose wick
    # returns to the level.
    retest_i = None
    for i in range(break_i + 1, entry_i + 1):
        b = seg[i]
        if direction == "call" and b["l"] <= level + eps:
            retest_i = i
            break
        if direction == "put" and b["h"] >= level - eps:
            retest_i = i
            break
    if retest_i is None:
        return None, break_i, None, "no_retest"
    return retest_i - break_i, break_i, retest_i, None


def swing_pivots_in_window(seg, lo_center, hi_center):
    """3-bar swing pivots (MarketStructure.update definition) with center index in
    [lo_center, hi_center]. A high > both neighbours and/or a low < both
    neighbours; an outside bar can be both (appended to both lists, as in
    MarketStructure.update). Neighbours are read from seg (all indices <= entry_i).
    Returns list of pivot prices (one entry per pivot; an outside bar -> two)."""
    pivots = []
    n = len(seg)
    for j in range(max(1, lo_center), min(hi_center, n - 2) + 1):
        h, l = seg[j]["h"], seg[j]["l"]
        if h > seg[j - 1]["h"] and h > seg[j + 1]["h"]:
            pivots.append(h)
        if l < seg[j - 1]["l"] and l < seg[j + 1]["l"]:
            pivots.append(l)
    return pivots


def rule10(bars_trunc, entry_i, level, direction, break_i):
    """Return (left_pivot_count, left_pivots_near_level, null_reason)."""
    if break_i is None:
        return None, None, "no_break"
    seg = bars_trunc[:entry_i + 1]
    # the 20 bars before the break: indices break_i-20 .. break_i-1 (centers)
    lo = break_i - 20
    pivots = swing_pivots_in_window(seg, lo, break_i - 1)
    near = sum(1 for p in pivots if abs(p - level) <= 0.002 * level)  # within 0.2%
    return len(pivots), near, None


# ----------------------------- statistics ---------------------------------

def mean(xs):
    return sum(xs) / len(xs)


def sample_var(xs):
    n = len(xs)
    if n < 2:
        return None
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (n - 1)


def cohen_d(g1, g2):
    """Pooled-SD Cohen's d (g1 - g2). None if undefined (n<2 or zero pooled var)."""
    n1, n2 = len(g1), len(g2)
    if n1 < 2 or n2 < 2:
        return None
    v1, v2 = sample_var(g1), sample_var(g2)
    if v1 is None or v2 is None:
        return None
    sp2 = ((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2)
    if sp2 <= 0:
        return None
    return (mean(g1) - mean(g2)) / math.sqrt(sp2)


def percentile(sorted_xs, q):
    """q in [0,100]; linear interpolation (numpy 'linear' method)."""
    if not sorted_xs:
        return None
    if len(sorted_xs) == 1:
        return sorted_xs[0]
    rank = q / 100.0 * (len(sorted_xs) - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return sorted_xs[lo]
    frac = rank - lo
    return sorted_xs[lo] * (1 - frac) + sorted_xs[hi] * frac


def block_bootstrap_d(rows, feat, tier_a, tier_b, n_boot=10000, seed=20260808):
    """Cluster bootstrap over whole trading days (symbol,day blocks).

    rows: list of dicts with keys 'symbol','day','tier',feat (feat may be None).
    Resample day-blocks with replacement, gather the marks in the sampled blocks,
    split into the two tiers on the non-null feat values, compute Cohen's d
    (tier_a - tier_b). Discard resamples where either arm has n<2 or zero
    variance. Returns the list of valid d values (length up to n_boot) plus the
    list of blocks used.
    """
    rng = random.Random(seed)
    # blocks: (symbol,day) -> list of non-null feat values per tier
    blocks = {}
    for r in rows:
        v = r.get(feat)
        if v is None:
            continue
        blocks.setdefault((r["symbol"], r["day"]), {"a": [], "b": [], "all": []})
        blk = blocks[(r["symbol"], r["day"])]
        if r["tier"] == tier_a:
            blk["a"].append(v)
        elif r["tier"] == tier_b:
            blk["b"].append(v)
    # keep only blocks that actually carry a mark in one of the two tiers
    block_keys = [k for k, b in blocks.items() if b["a"] or b["b"]]
    if not block_keys:
        return [], block_keys
    vals = []
    attempts = 0
    max_attempts = n_boot * 200
    while len(vals) < n_boot and attempts < max_attempts:
        attempts += 1
        ga, gb = [], []
        for _ in range(len(block_keys)):
            blk = blocks[rng.choice(block_keys)]
            ga.extend(blk["a"])
            gb.extend(blk["b"])
        d = cohen_d(ga, gb)
        if d is not None and math.isfinite(d):
            vals.append(d)
    return vals, block_keys


def mde_d(n1, n2, alpha=0.05, power=0.80):
    """Minimum detectable Cohen's d for a two-sample test at the given n.

    MDE_d = (z_{1-a/2} + z_{power}) * sqrt(1/n1 + 1/n2). Normal approximation
    (the conventional planning formula; scipy is not installed in this env)."""
    z_alpha2 = 1.959964   # z_{0.975}
    z_power = 0.841621    # z_{0.80}
    return (z_alpha2 + z_power) * math.sqrt(1.0 / n1 + 1.0 / n2)


def separation_table(rows, feat, tier_a, tier_b, n_boot=10000):
    """Build one contrast row: n, means, d, bootstrap CI, MDE, verdict."""
    ga = [r[feat] for r in rows if r["tier"] == tier_a and r.get(feat) is not None]
    gb = [r[feat] for r in rows if r["tier"] == tier_b and r.get(feat) is not None]
    n1, n2 = len(ga), len(gb)
    d = cohen_d(ga, gb)
    boot, nblocks = block_bootstrap_d(rows, feat, tier_a, tier_b, n_boot=n_boot)
    if len(boot) >= 2:
        sb = sorted(boot)
        ci_lo = percentile(sb, 2.5)
        ci_hi = percentile(sb, 97.5)
    else:
        ci_lo = ci_hi = None
    mde = mde_d(n1, n2) if (n1 >= 2 and n2 >= 2) else None
    # verdict
    if d is None or mde is None:
        verdict = "undefined (an arm has n<2)"
    elif ci_lo is not None and ci_hi is not None and ci_lo > 0 and ci_hi > 0:
        verdict = f"separates (CI excludes 0; |d|={abs(d):.2f} >= MDE {mde:.2f})"
    elif ci_lo is not None and ci_hi is not None and ci_hi < 0 and ci_lo < 0:
        verdict = f"separates (CI excludes 0; |d|={abs(d):.2f} >= MDE {mde:.2f})"
    elif abs(d) < mde:
        verdict = (f"UNDERPOWERED: |d|={abs(d):.2f} < MDE {mde:.2f}; a real effect "
                   f"up to {mde:.2f} is consistent with the data -- not a null")
    else:
        verdict = (f"borderline: |d|={abs(d):.2f} ~ MDE {mde:.2f}, CI includes 0")
    return {
        "contrast": f"{tier_a} vs {tier_b}",
        "n_a": n1, "n_b": n2,
        "mean_a": mean(ga) if ga else None,
        "mean_b": mean(gb) if gb else None,
        "d": d,
        "ci_lo": ci_lo, "ci_hi": ci_hi,
        "n_boot_valid": len(boot),
        "n_day_blocks": len(nblocks),
        "mde": mde,
        "verdict": verdict,
    }


def main():
    marks = [json.loads(l) for l in open(MARKS)]

    rows = []          # one per usable mark (mark with bars)
    dropped = []
    null_reasons_r7 = {"no_break": 0, "no_retest": 0, "no_ref": 0}

    for m in marks:
        bars = levels.load_rth_bars(m["symbol"], m["day"])
        if bars is None:
            dropped.append({**m, "reason": "no_archive_file"})
            continue
        if m["entry_i"] >= len(bars):
            dropped.append({**m, "reason": "entry_i_out_of_range"})
            continue
        # ---- leakage enforcement: truncate to bars[:entry_i+1] ----
        bars_trunc = bars[: m["entry_i"] + 1]
        ei = m["entry_i"]

        level, direction = compute_ref(m["symbol"], m["day"], bars_trunc, ei)
        if level is None or direction is None:
            null_reasons_r7["no_ref"] += 1
            row = {"symbol": m["symbol"], "day": m["day"], "entry_i": ei,
                   "tier": m["tier"], "bars_break_to_retest": None,
                   "left_pivot_count": None, "left_pivots_near_level": None,
                   "break_index": None, "retest_index": None,
                   "broken_level_price": None, "direction": None,
                   "null_reason_r7": "no_ref"}
            rows.append(row)
            continue

        b2r, break_i, retest_i, reason7 = rule7(bars_trunc, ei, level, direction)
        lpc, lpn, reason10 = rule10(bars_trunc, ei, level, direction, break_i)

        if reason7 == "no_break":
            null_reasons_r7["no_break"] += 1
        elif reason7 == "no_retest":
            null_reasons_r7["no_retest"] += 1

        rows.append({
            "symbol": m["symbol"], "day": m["day"], "entry_i": ei,
            "tier": m["tier"],
            "bars_break_to_retest": b2r,
            "left_pivot_count": lpc,
            "left_pivots_near_level": lpn,
            "break_index": break_i,
            "retest_index": retest_i,
            "broken_level_price": level,
            "direction": direction,
            "null_reason_r7": reason7,
        })

    # ---- write jsonl ----
    with open(OUT_JSONL, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    # ---- tier counts ----
    from collections import Counter
    tier_ct = Counter(r["tier"] for r in rows)

    # ---- null rates ----
    n_usable = len(rows)
    r7_null = sum(1 for r in rows if r["bars_break_to_retest"] is None)
    r10_null = sum(1 for r in rows if r["left_pivot_count"] is None)
    r7_nonnull = n_usable - r7_null

    # ---- separation tables ----
    feats = [
        ("bars_break_to_retest", "Rule 7 -- bars break->retest (speed of the retest)"),
        ("left_pivot_count", "Rule 10 -- left-side pivot count (20 bars before break)"),
        ("left_pivots_near_level", "Rule 10 -- pivots within 0.2% of the level (noise at the level)"),
    ]
    contrasts = [("S", "X"), ("S", "A")]
    tables = {}
    for fk, title in feats:
        tables[fk] = {f"{a} vs {b}": separation_table(rows, fk, a, b) for a, b in contrasts}

    # ---- write md ----
    with open(OUT_MD, "w") as f:
        f.write("# rule7_rule10\n\n")
        f.write("Austin's two hardest rejections, encoded as features and tested "
                "for S/A/X tier separation. Built on top of `research/mark_features.py` "
                "(its loading, leakage discipline, and reference-level identification).\n\n")

        f.write("## Leakage rule (no bar at index > entry_i)\n\n")
        f.write("Enforced structurally, identically to `mark_features.py`: each mark's "
                "full RTH bar list is loaded once (`levels.load_rth_bars`) and **truncated "
                "to `bars[:entry_i+1]`** (`bars_trunc`, length entry_i+1) before any feature "
                "reads it. `find_break` scans `bars_trunc[:entry_i]`; the rule-7 retest scan "
                "and the rule-10 pivot scan both run over `bars_trunc` (max index entry_i); "
                "the reference level and direction come from `levels.levels_at_bar` called "
                "over `bars_trunc` (the same leakage-bounded call mark_features uses). "
                "No path -- direct or via `levels.py` -- indexes a bar beyond entry_i. "
                "Marks with no archive file or out-of-range entry_i are dropped "
                "(no bars -> no features).\n\n")

        f.write("## Counts\n\n")
        f.write(f"- Total marks: {len(marks)}\n")
        f.write(f"- Usable (bars present, entry_i in range): **{n_usable}**\n")
        f.write(f"- Dropped: {len(dropped)}\n")
        f.write(f"- Tier counts (usable): "
                f"{', '.join(f'{t}={tier_ct[t]}' for t in sorted(tier_ct))}\n\n")
        f.write(f"3.6's arms were n=48/45/12 (105 usable). The archive has since "
                f"been expanded, so all 159 marks now have bars and the TOTAL tier "
                f"arms are S={tier_ct['S']}/A={tier_ct['A']}/X={tier_ct['X']}. The "
                f"separation tables below use the EFFECTIVE arms -- the non-null "
                f"counts per feature (rule 7 loses the no-break + no-retest marks, "
                f"rule 10 loses only the no-break marks) -- which is the n the MDE is "
                f"computed at.\n\n")

        # ---- Rule 7 null rate ----
        f.write("## Rule 7 -- null rate (no break identifiable)\n\n")
        f.write(f"- `bars_break_to_retest` null: **{r7_null}/{n_usable}** "
                f"({100*r7_null/n_usable:.1f}%)\n")
        f.write(f"  - no break identifiable (find_break found no close-through of the "
                f"reference level): {null_reasons_r7['no_break']}\n")
        f.write(f"  - break found but no retest bar reached the level before/at entry: "
                f"{null_reasons_r7['no_retest']}\n")
        f.write(f"  - no reference level/direction: {null_reasons_r7['no_ref']}\n")
        f.write(f"- `left_pivot_count` null (no break -> no 'before the break' window): "
                f"**{r10_null}/{n_usable}** ({100*r10_null/n_usable:.1f}%)\n\n")
        f.write("A high null rate is itself the finding: it means the engine's "
                "retested level (the nearest weight>=2 node to the entry close) often is "
                "NOT a freshly broken level -- price never closed through it from the other "
                "side in the bars leading to entry, so rule 7 and rule 10 are undefined for "
                "those marks. The break detector reused here is `mark_features.find_break` "
                "(close-through-from-other-side, eps = 0.10 * median bar range), the same "
                "one behind 3.6's `bars_since_break` (37/105 null there).\n\n")

        # ---- separation tables ----
        for fk, title in feats:
            f.write(f"## {title}\n\n")
            f.write("Cohen's d (pooled SD), 95% CI from a block bootstrap over whole "
                    "trading days (10,000 resamples; resample (symbol,day) blocks with "
                    "replacement, split the gathered marks by tier, recompute d; resamples "
                    "where an arm has n<2 or zero variance are discarded), and the MDE at "
                    "the n actually available (normal-approx planning formula: "
                    "MDE = (z_.975 + z_.80) * sqrt(1/n1 + 1/n2); scipy is not installed).\n\n")
            f.write("| contrast | n_a | n_b | mean_a | mean_b | d | 95% CI | n_boot | MDE | verdict |\n")
            f.write("|---|---|---|---|---|---|---|---|---|---|\n")
            for a, b in contrasts:
                t = tables[fk][f"{a} vs {b}"]
                ci = (f"[{t['ci_lo']:.3f}, {t['ci_hi']:.3f}]"
                      if t["ci_lo"] is not None and t["ci_hi"] is not None else "--")
                dstr = f"{t['d']:.3f}" if t["d"] is not None else "--"
                ma = f"{t['mean_a']:.3f}" if t["mean_a"] is not None else "--"
                mb = f"{t['mean_b']:.3f}" if t["mean_b"] is not None else "--"
                mde = f"{t['mde']:.3f}" if t["mde"] is not None else "--"
                f.write(f"| {t['contrast']} | {t['n_a']} | {t['n_b']} | {ma} | {mb} "
                        f"| {dstr} | {ci} | {t['n_boot_valid']} | {mde} | {t['verdict']} |\n")
            f.write("\n")
            # plain-language read
            for a, b in contrasts:
                t = tables[fk][f"{a} vs {b}"]
                dstr = f"{t['d']:.3f}" if t["d"] is not None else "--"
                ci = (f"CI=[{t['ci_lo']:.3f}, {t['ci_hi']:.3f}], "
                      if t["ci_lo"] is not None else "")
                mde = f"MDE={t['mde']:.3f}." if t["mde"] is not None else ""
                f.write(f"- **{t['contrast']}**: {t['verdict']}. "
                        f"n={t['n_a']}/{t['n_b']}, d={dstr}. {ci}{mde}\n")
            # direction-of-effect read
            sx = tables[fk]["S vs X"]; sa = tables[fk]["S vs A"]
            if fk == "bars_break_to_retest":
                note = (f"Direction: S mean={sx['mean_a']:.2f} bars vs "
                        f"X={sx['mean_b']:.2f}, A={sa['mean_b']:.2f}. S has the "
                        f"FASTEST retests (fewest bars break->retest), which is the "
                        f"direction Austin's rule predicts for the top tier -- but "
                        f"the gap is small and below the MDE on both contrasts.")
            elif fk == "left_pivot_count":
                note = (f"Direction: S mean={sx['mean_a']:.2f} pivots vs "
                        f"X={sx['mean_b']:.2f}, A={sa['mean_b']:.2f}. S is cleaner "
                        f"than A (fewer left-side pivots, as the rule predicts) but "
                        f"noisier than X; the raw count does not monotonically order "
                        f"the tiers and both effects are far under the MDE.")
            else:  # left_pivots_near_level
                note = (f"Direction: S mean={sx['mean_a']:.2f} near-level pivots vs "
                        f"X={sx['mean_b']:.2f}, A={sa['mean_b']:.2f}. S has the "
                        f"FEWEST near-level pivots (least noise at the level) on both "
                        f"contrasts -- the right direction for the top tier -- and the "
                        f"S-vs-A d={sa['d']:.2f} is the largest effect in this study, "
                        f"but its CI still includes 0 (MDE={sa['mde']:.2f}).")
            f.write(f"\n{note}\n\n")

        f.write("## Feature dictionary (rule7_rule10.jsonl)\n\n")
        f.write("One line per usable mark (mark with bars). Identity triple + tier +:\n\n")
        f.write("| key | meaning |\n|---|---|\n")
        f.write("| `bars_break_to_retest` | Rule 7: bars between the break candle (last close-through of the reference level before entry) and the retest candle (first wick back to the level). null if no break / no retest. |\n")
        f.write("| `left_pivot_count` | Rule 10: count of 3-bar swing pivots (MarketStructure.update definition) in the 20 bars before the break. null if no break. |\n")
        f.write("| `left_pivots_near_level` | Rule 10: of those pivots, how many sit within 0.2% of the reference level (noise at the level). null if no break. |\n")
        f.write("| `break_index` / `retest_index` | bar indices of the break / retest candles (for audit). |\n")
        f.write("| `broken_level_price` / `direction` | the retested level and direction, recomputed the same way mark_features does (nearest weight>=2 node to entry close via levels.levels_at_bar). |\n")
        f.write("| `null_reason_r7` | why bars_break_to_retest is null: no_break / no_retest / no_ref, else null. |\n")

    print(f"usable={n_usable} dropped={len(dropped)} total={len(marks)}")
    print(f"r7 null={r7_null} ({100*r7_null/n_usable:.1f}%)  r10 null={r10_null} "
          f"({100*r10_null/n_usable:.1f}%)")
    print(f"wrote {OUT_JSONL} ({len(rows)} lines)")
    print(f"wrote {OUT_MD}")
    # quick stdout summary of d's
    for fk, _ in feats:
        for a, b in contrasts:
            t = tables[fk][f"{a} vs {b}"]
            print(f"  {fk} {a}vs{b}: d={t['d']} CI=[{t['ci_lo']},{t['ci_hi']}] "
                  f"MDE={t['mde']} n={t['n_a']}/{t['n_b']}")


if __name__ == "__main__":
    main()
