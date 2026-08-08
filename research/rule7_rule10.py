"""omen-3.7 T3: Rule 7 & Rule 10 features at every marked bar.

Austin's two hardest rejections, encoded as measurable features to test whether
they separate his tiers (S vs X, S vs A) — since nothing in 3.6's 16-feature
vector did.

Rule 7 — speed of the retest (dictation): "ideally the break and retest happens
as soon as possible ... if it takes too many candles probability decreases."
  Feature `bars_break_to_retest`: bars elapsed between the break candle and the
  retest candle. The break candle is the most recent bar before entry_i whose
  body closed beyond the reference level (identified with the same transition
  test `mark_features.find_break` uses — a bar whose close crossed the level from
  the opposite side; the wording "body closed beyond the level" describes that
  break candle). The retest candle is the first bar strictly after the break
  (and at or before entry_i) whose wick returns to the level (low <= level for a
  call, high >= level for a put). `null` where no break is identifiable — and
  that null rate is itself a finding.

Rule 10 — left-side pivot noise (X card): "a bunch of candles or pivot
structures already there before your break ... if the break and retest is not
clean or the order block is not clean."
  Feature `left_pivot_count`: count of 3-bar swing pivots in the 20 bars before
  the reference level was broken, using omen_bot.py MarketStructure.update's
  definition (a high above both neighbours, a low below both).
  Feature `left_pivot_at_level`: how many of those pivots sit within 0.2% of the
  reference level itself — the "noise at the level" version.

Reuses research/mark_features.py loading + leakage discipline and
research/levels.py for the level node set. Leakage rule: no feature reads any
bar at index > entry_i — enforced by truncation to bars[:entry_i+1] (path 1) and
levels.py's internal entry_i-bounded slices (path 2), exactly as in 3.6.

Outputs:
  research/rule7_rule10.jsonl  (identity triple, tier, both features)
  research/rule7_rule10.md    (null rate for rule 7; d, bootstrap CI, MDE per
                               feature per contrast; underpowered verdicts)

Statistics are pure-Python (no numpy/scipy in this environment):
  - Cohen's d with pooled SD.
  - 95% CI from a block bootstrap over whole trading days, 10000 resamples.
  - MDE at the n actually available (alpha=0.05 two-sided, power=0.80).
"""

from __future__ import annotations
import json, os, sys, math, random
from statistics import mean
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)        # research/levels, research/mark_features
sys.path.insert(0, ROOT)        # (predicates, not used here but kept for parity)

import levels
import mark_features as mf          # find_break, prior_extremes (3.6 discipline)

MARKS = os.path.join(HERE, "austin_marks_v2.jsonl")
OUT_JSONL = os.path.join(HERE, "rule7_rule10.jsonl")
OUT_MD = os.path.join(HERE, "rule7_rule10.md")

# z critical values for MDE (alpha=0.05 two-sided, power=0.80)
Z_975 = 1.959964
Z_80 = 0.841621
BOOTSTRAP_N = 10000
SEED = 20260808
CONTRASTS = [("S", "X"), ("S", "A")]


# --------------------------------------------------------------------------- #
# feature computation
# --------------------------------------------------------------------------- #
def find_retest(bars_trunc, break_i, entry_i, level, direction):
    """First bar strictly after the break (and <= entry_i) whose wick returns to
    the level. For a call the wick returns from above (low <= level); for a put
    from below (high >= level). Returns the bar index or None."""
    for j in range(break_i + 1, entry_i + 1):
        b = bars_trunc[j]
        if direction == "call":
            if b["l"] <= level:
                return j
        else:
            if b["h"] >= level:
                return j
    return None


def count_left_pivots(bars_trunc, break_i, ref_price):
    """3-bar swing pivots (omen_bot.py MarketStructure.update definition) whose
    centre lies in the 20 bars before the break (indices [break_i-20, break_i-1]).

    A centre at index p needs neighbours p-1 and p+1 to exist; computing pivots
    over the whole truncated list then filtering by centre index keeps the
    3-bar definition applied consistently. `at_level` counts those within 0.2%
    of the reference level. Returns (count, at_level)."""
    if break_i is None or break_i < 1:
        return None, None
    lo_win = max(1, break_i - 20)
    hi_win = break_i - 1            # centres strictly before the break candle
    pivot_prices = []               # one entry per pivot (a bar can be both H&L)
    seen_idx = set()
    for p in range(1, len(bars_trunc) - 1):
        h, l = bars_trunc[p]["h"], bars_trunc[p]["l"]
        is_high = h > bars_trunc[p - 1]["h"] and h > bars_trunc[p + 1]["h"]
        is_low = l < bars_trunc[p - 1]["l"] and l < bars_trunc[p + 1]["l"]
        if not (is_high or is_low):
            continue
        if not (lo_win <= p <= hi_win):
            continue
        # count each pivot type; a bar that is both H and L contributes two
        if is_high:
            pivot_prices.append(h)
        if is_low:
            pivot_prices.append(l)
        seen_idx.add(p)
    count = len(pivot_prices)
    at_level = sum(1 for pr in pivot_prices
                   if abs(pr - ref_price) <= 0.002 * ref_price) if ref_price else 0
    return count, at_level


def reference_level(bars_trunc, entry_i, mark):
    """Nearest weight>=2 level node to the entry close, with direction — exactly
    the reference-level selection mark_features.compute_features uses (3.6)."""
    entry_close = bars_trunc[entry_i]["c"]
    prior_hi, prior_lo = mf.prior_extremes(bars_trunc, entry_i)
    if prior_hi is None:
        prior_hi = prior_lo = entry_close
    nodes, _cov = levels.levels_at_bar(mark["symbol"], mark["day"], entry_i,
                                       entry_close, prior_lo, prior_hi)
    qnodes = [n for n in nodes if n["weight"] >= 2.0]
    if not qnodes:
        return None, None
    ref = min(qnodes, key=lambda n: abs(n["price"] - entry_close))
    direction = "call" if entry_close > ref["price"] else "put"
    return ref["price"], direction


def compute_rule7_rule10(mark, bars_trunc, entry_i):
    """Returns (feats, break_found, retest_found).

    break_found/retest_found are not written to the jsonl; they let the report
    split the two distinct rule-7 null reasons (no break vs break-but-no-retest).
    """
    ref_price, direction = reference_level(bars_trunc, entry_i, mark)
    feats = {
        "bars_break_to_retest": None,
        "left_pivot_count": None,
        "left_pivot_at_level": None,
    }
    if ref_price is None or direction is None:
        return feats, False, False
    break_i = mf.find_break(bars_trunc, entry_i, ref_price, direction)
    if break_i is None:
        # no break identifiable -> rule 7 null (the documented null case).
        # rule 10 is tied to "before the level was broken", so it is null too.
        return feats, False, False
    retest_i = find_retest(bars_trunc, break_i, entry_i, ref_price, direction)
    feats["bars_break_to_retest"] = (retest_i - break_i) if retest_i is not None else None
    cnt, at_lvl = count_left_pivots(bars_trunc, break_i, ref_price)
    feats["left_pivot_count"] = cnt
    feats["left_pivot_at_level"] = at_lvl
    return feats, True, retest_i is not None


# --------------------------------------------------------------------------- #
# statistics (pure python)
# --------------------------------------------------------------------------- #
def cohen_d(a, b):
    """Cohen's d = (mean_a - mean_b) / pooled SD. None if either arm < 2 or no variance."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None
    ma, mb = mean(a), mean(b)
    va = sum((x - ma) ** 2 for x in a) / (na - 1)
    vb = sum((x - mb) ** 2 for x in b) / (nb - 1)
    sp = math.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    if sp == 0:
        return 0.0 if ma == mb else None
    return (ma - mb) / sp


def pooled_sd(a, b):
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None
    ma, mb = mean(a), mean(b)
    va = sum((x - ma) ** 2 for x in a) / (na - 1)
    vb = sum((x - mb) ** 2 for x in b) / (nb - 1)
    return math.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))


def block_bootstrap_d_ci(days_blocks, arm1_tier, arm2_tier, n_boot=BOOTSTRAP_N, seed=SEED):
    """95% CI for Cohen's d via block bootstrap over whole trading days.

    days_blocks: dict day_key -> {tier -> [values]}. Each resample draws
    len(days) days with replacement, pools the values per arm, recomputes d.
    Returns (lo, hi, n_valid_resamples) or None if the contrast has no valid d."""
    day_keys = list(days_blocks.keys())
    n_days = len(day_keys)
    rng = random.Random(seed)
    ds = []
    for _ in range(n_boot):
        a_vals, b_vals = [], []
        for _d in range(n_days):
            dk = day_keys[rng.randrange(n_days)]
            block = days_blocks[dk]
            a_vals.extend(block.get(arm1_tier, []))
            b_vals.extend(block.get(arm2_tier, []))
        d = cohen_d(a_vals, b_vals)
        if d is not None:
            ds.append(d)
    if len(ds) < 2:
        return None
    ds.sort()
    lo = ds[int(0.025 * len(ds))]
    hi = ds[int(0.975 * len(ds)) - 1]
    return lo, hi, len(ds)


def mde(n1, n2, sp, alpha=0.05, power=0.80):
    """Minimum detectable mean difference (native units) and as a Cohen's d
    threshold, for two independent samples at the given n and observed pooled SD.
    Two-sided alpha, specified power. Returns (mde_native, mde_d)."""
    if n1 < 2 or n2 < 2 or not sp or sp <= 0:
        return None, None
    z = Z_975 + Z_80
    mde_native = z * sp * math.sqrt(1.0 / n1 + 1.0 / n2)
    mde_d = z * math.sqrt(1.0 / n1 + 1.0 / n2)
    return mde_native, mde_d


def quantile(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    return s[min(len(s) - 1, max(0, int(q * (len(s) - 1))))]


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    marks = [json.loads(l) for l in open(MARKS)]
    usable = []
    dropped = []
    # rule-7 null-reason split: no break vs break-but-no-retest
    n_no_break = 0
    n_break_no_retest = 0
    break_found_tiers = Counter()

    for m in marks:
        bars = levels.load_rth_bars(m["symbol"], m["day"])
        if bars is None:
            dropped.append({**m, "reason": "no_archive_file"})
            continue
        if m["entry_i"] >= len(bars):
            dropped.append({**m, "reason": "entry_i_out_of_range",
                            "n_rth": len(bars)})
            continue
        bars_trunc = bars[: m["entry_i"] + 1]      # leakage enforcement: truncate
        feats, break_found, retest_found = compute_rule7_rule10(
            m, bars_trunc, m["entry_i"])
        row = {"symbol": m["symbol"], "day": m["day"],
               "entry_i": m["entry_i"], "tier": m["tier"]}
        row.update(feats)
        usable.append(row)
        if not break_found:
            n_no_break += 1
        elif not retest_found:
            n_break_no_retest += 1
        if break_found:
            break_found_tiers[m["tier"]] += 1

    with open(OUT_JSONL, "w") as f:
        for r in usable:
            f.write(json.dumps(r) + "\n")

    # ---- null rates ----
    def null_rate(key, tier=None):
        sub = [r for r in usable if (tier is None or r["tier"] == tier)]
        nn = [r for r in sub if r[key] is not None]
        return len(nn), len(sub)

    r7_nn_total, r7_total = null_rate("bars_break_to_retest")
    r10_nn_total, r10_total = null_rate("left_pivot_count")

    # ---- separation analysis ----
    contrasts = CONTRASTS
    features = ["bars_break_to_retest", "left_pivot_count",
                "left_pivot_at_level"]

    report = {}

    # group non-null feature values by (day -> tier -> values) for bootstrap
    def day_blocks(feat):
        blk = defaultdict(lambda: defaultdict(list))
        for r in usable:
            v = r[feat]
            if v is None:
                continue
            blk[(r["symbol"], r["day"])][r["tier"]].append(v)
        return blk

    for feat in features:
        report[feat] = {}
        blocks = day_blocks(feat)
        for a1, a2 in contrasts:
            vals1 = [r[feat] for r in usable
                     if r["tier"] == a1 and r[feat] is not None]
            vals2 = [r[feat] for r in usable
                     if r["tier"] == a2 and r[feat] is not None]
            n1, n2 = len(vals1), len(vals2)
            d = cohen_d(vals1, vals2)
            sp = pooled_sd(vals1, vals2)
            ci = block_bootstrap_d_ci(blocks, a1, a2)
            mde_native, mde_d = mde(n1, n2, sp)
            # pooled-days count for the contrast
            pdays = sum(1 for dk, cc in blocks.items()
                        if cc.get(a1) or cc.get(a2))
            report[feat][f"{a1}-vs-{a2}"] = {
                "n1": n1, "n2": n2, "n_total": n1 + n2,
                "pooled_days": pdays,
                "mean1": mean(vals1) if vals1 else None,
                "mean2": mean(vals2) if vals2 else None,
                "cohen_d": d,
                "pooled_sd": sp,
                "ci_lo": ci[0] if ci else None,
                "ci_hi": ci[1] if ci else None,
                "ci_valid_resamples": ci[2] if ci else None,
                "mde_native": mde_native,
                "mde_d": mde_d,
            }

    # ---- write markdown ----
    write_report(usable, dropped, marks, r7_nn_total, r7_total,
                 r10_nn_total, r10_total, report,
                 n_no_break, n_break_no_retest, break_found_tiers)

    print(f"usable={len(usable)} dropped={len(dropped)} total={len(marks)}")
    print(f"r7 null rate: {r7_total - r7_nn_total}/{r7_total}")
    print(f"wrote {OUT_JSONL} ({len(usable)} lines)")
    print(f"wrote {OUT_MD}")


def write_report(usable, dropped, marks, r7_nn, r7_total, r10_nn, r10_total,
                 report, n_no_break, n_break_no_retest, break_found_tiers):
    with open(OUT_MD, "w") as f:
        f.write("# rule7_rule10 — Rule 7 & Rule 10 separation\n\n")
        f.write("Austin's two hardest rejections, encoded as features and tested "
                "for tier separation. Reuses `research/mark_features.py`'s "
                "loading + leakage discipline and `research/levels.py`'s level "
                "node set.\n\n")

        f.write("## Counts\n\n")
        f.write(f"- Usable marks: **{len(usable)}**\n")
        f.write(f"- Dropped: **{len(dropped)}** (no archived bars / entry_i out "
                f"of range). NB: the data archive has been filled in since 3.6 "
                f"ran (3.6 dropped 54/159 for missing bars; all 159 now have "
                f"RTH bars), so the arms here are larger than 3.6's "
                f"n=48/45/12 — but the feature nulls below shrink the "
                f"effective arms back down.\n")
        f.write(f"- Total marks: {len(marks)}\n")
        tier_counts = Counter(r["tier"] for r in usable)
        f.write(f"- Tier arms (usable): "
                f"S={tier_counts.get('S',0)} A={tier_counts.get('A',0)} "
                f"X={tier_counts.get('X',0)}\n\n")

        f.write("## Leakage rule — how it was enforced\n\n")
        f.write(
            "No feature reads any bar at index > entry_i. Enforcement is "
            "structural, by construction, not by after-the-fact assertion:\n\n"
            "1. **Truncation (path 1):** for each mark the day's RTH bars are "
            "loaded once via `levels.load_rth_bars` and **truncated to "
            "`bars[:entry_i+1]`** (`bars_trunc`, length entry_i+1). Every "
            "feature here is handed `bars_trunc`:\n"
            "- `mark_features.find_break` (the break candle) scans "
            "`bars[:entry_i]` — strictly before the entry bar.\n"
            "- `find_retest` scans indices in `(break_i, entry_i]` — the entry "
            "bar is the highest index it can read, never beyond.\n"
            "- `count_left_pivots` scans the whole `bars_trunc` for 3-bar "
            "centres, then keeps only centres with index `<= break_i-1 < "
            "entry_i`; every neighbour it touches is within `bars_trunc` "
            "(max index entry_i).\n\n"
            "2. **`research/levels.py` (path 2):** `levels_at_bar` takes "
            "symbol/day/entry_i and reloads the file internally, then slices "
            "itself at entry_i (`hod_lod_nodes` uses `bars[:entry_i]`, "
            "`swing_pivots` uses `bars[:entry_i+1]` whose last centre is "
            "entry_i-1, prior-day/month nodes read earlier calendar days "
            "only). It never receives the untruncated list from this script.\n\n"
            "The reference level itself is the nearest weight>=2 node to the "
            "entry close (the same selection `mark_features.compute_features` "
            "uses in 3.6); `direction` is `call` if entry close > that level "
            "else `put`. The break candle uses `find_break`'s transition test "
            "(a bar whose close crossed the reference level from the opposite "
            "side) — that is the bar whose *body closed beyond the reference "
            "level*; the wording of the row describes this break candle, and "
            "the transition framing is what distinguishes the break candle "
            "from the subsequent bars that also sit beyond the level.\n\n")

        f.write("## Rule 7 — speed of the retest\n\n")
        f.write("`bars_break_to_retest` = bars from the break candle to the "
                "first retest candle (the first bar after the break whose wick "
                "returns to the level, at or before the entry bar). Smaller = "
                "faster retest = what Austin wants.\n\n")
        f.write(f"**Null rate (no break identifiable): "
                f"{n_no_break}/{r7_total} = "
                f"{n_no_break/r7_total:.1%}** of marks with bars have no break "
                f"candle and emit null. A high null rate is itself the finding: "
                f"the retest-speed feature is undefined at its first step for "
                f"{n_no_break} of {r7_total} marks — the engine's retested "
                f"level was never provably *broken* by a closing body in the "
                f"bars leading to entry, so 'speed of retest' has no start "
                f"point.\n\n")
        f.write(f"A further **{n_break_no_retest}** marks have a break candle "
                f"but no retest candle (no bar at or before entry whose wick "
                f"returns to the level) — these are also null for "
                f"`bars_break_to_retest` (the elapsed-bars value needs both "
                f"endpoints). The total rule-7 null count is "
                f"{n_no_break + n_break_no_retest}/{r7_total} = "
                f"{(n_no_break + n_break_no_retest)/r7_total:.1%}; the headline "
                f"rate above isolates the no-break case the row names.\n\n")
        # per-tier null rate for rule 7
        f.write("Per-tier non-null counts (rule 7):\n\n")
        f.write("| tier | non-null | total | null rate |\n|---|---|---|---|\n")
        for t in ["S", "A", "X"]:
            nn, tot = 0, 0
            for r in usable:
                if r["tier"] == t:
                    tot += 1
                    if r["bars_break_to_retest"] is not None:
                        nn += 1
            f.write(f"| {t} | {nn} | {tot} | {tot - nn}/{tot} |\n")
        f.write("\nRule 10 (`left_pivot_count`) is null only on the no-break "
                "case (it is undefined whenever there is no break candle, since "
                "it counts pivots *before the level was broken*); the "
                "break-but-no-retest marks still carry a `left_pivot_count`. "
                f"Its null rate is {r10_total - r10_nn}/{r10_total} = "
                f"{(r10_total - r10_nn)/r10_total:.1%}, equal to the no-break "
                f"rate.\n\n")

        f.write("## Separation tables\n\n")
        f.write("For each feature and each contrast (S-vs-X, S-vs-A): Cohen's d "
                "(S minus the other tier; positive = S larger), a 95% CI from a "
                "block bootstrap over whole trading days with 10,000 resamples, "
                "and the minimum detectable effect at the n actually available "
                "(alpha=0.05 two-sided, power=0.80). MDE_d is the Cohen's-d "
                "threshold; an observed |d| below it is underpowered, not a "
                "null.\n\n")

        for feat in list(report.keys()):
            f.write(f"### `{feat}`\n\n")
            f.write("| contrast | n(S) | n(other) | pooled days | mean(S) | "
                    "mean(other) | Cohen's d | 95% bootstrap CI | MDE (native) "
                    "| MDE_d | verdict |\n")
            f.write("|---|---|---|---|---|---|---|---|---|---|---|\n")
            for a1, a2 in CONTRASTS:
                r = report[feat][f"{a1}-vs-{a2}"]
                d = r["cohen_d"]
                ci_str = (f"[{r['ci_lo']:.3f}, {r['ci_hi']:.3f}]"
                          if r["ci_lo"] is not None else "—")
                mde_nat = (f"{r['mde_native']:.3f}"
                           if r["mde_native"] is not None else "—")
                mde_d = f"{r['mde_d']:.3f}" if r["mde_d"] is not None else "—"
                # verdict: detected if CI excludes 0; else underpowered if
                # |d| < MDE_d (or arms tiny), else null-but-powered.
                if d is None or r["ci_lo"] is None or r["mde_d"] is None:
                    verdict = "too few points"
                elif r["ci_lo"] > 0 or r["ci_hi"] < 0:
                    verdict = "**detected**"
                elif abs(d) < r["mde_d"]:
                    verdict = "underpowered"
                else:
                    verdict = "null (powered)"
                dd = f"{d:.3f}" if d is not None else "—"
                m1 = (f"{r['mean1']:.2f}" if r["mean1"] is not None else "—")
                m2 = (f"{r['mean2']:.2f}" if r["mean2"] is not None else "—")
                f.write(f"| {a1}-vs-{a2} | {r['n1']} | {r['n2']} | "
                        f"{r['pooled_days']} | {m1} | {m2} | {dd} | {ci_str} | "
                        f"{mde_nat} | {mde_d} | {verdict} |\n")
            f.write("\n")

        f.write("## Reading the result\n\n")
        f.write(
            "3.6's arms were n=48/45/12 and detected nothing at 45pp. These "
            "features shed more marks to nulls (no break identifiable), so the "
            "separation arms are smaller still — especially S-vs-X, where the X "
            "arm shrinks to single digits. Where the verdict is "
            "**underpowered**, the observed d is below the Cohen's-d threshold "
            "the experiment could have reliably detected at this n; the honest "
            "report is the MDE, not a claim of no effect. A **detected** verdict "
            "means the bootstrap CI excludes zero.\n\n")

        f.write("## Statistics note\n\n")
        f.write("No numpy/scipy in this environment. Cohen's d uses the pooled-SD "
                "formula; the 95% CI is a block bootstrap over whole trading "
                "days (resampling days with replacement, 10,000 iterations, "
                "seed " + str(SEED) + ") so that same-day marks are not treated "
                "as independent. MDE = (z_0.975 + z_0.80) * s_pooled * "
                "sqrt(1/n1 + 1/n2) in native units, and the same expression "
                "without s_pooled gives the Cohen's-d threshold MDE_d.\n")


if __name__ == "__main__":
    main()
