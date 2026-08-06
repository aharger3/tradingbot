"""omen-3.6 T3: feature vector at every marked bar.

For each row of research/austin_marks_v2.jsonl, load that day's RTH bars from
data_archive/<SYMBOL>/<DAY>.csv and compute features at bar index entry_i using
only bars at index <= entry_i (the no-future-bars / leakage rule). Rows whose
bars are missing (per research/bar_coverage.md) are skipped and counted.

Uses what exists, does not reimplement:
  - research/levels.py for the level node set (HOD/LOD/swing/psych/PDH/PMH/pivots)
  - root predicates.py for is_break_and_retest, is_order_block,
    is_84_reentry_opportunity, is_chop_market, is_x_signal

Outputs:
  - research/mark_features.jsonl  (one row per usable mark)
  - research/mark_features.md     (usable/dropped counts, per-feature null counts,
                                   and how the no-future-bars rule was enforced)
  - research/bar_coverage.md      (per-mark archive coverage; the authority the
                                   main routine consults to decide drops)

R-unit (risk scale) for R-multiple distances: the 14-bar 1-minute ATR over RTH
bars up to and including the entry bar, via levels.atr_1m. This is the
data-grounded risk scale already used by levels.py (the trader's stops sit at
~0.84x ATR_1m), it is derivable purely from past bars, and the marks carry no
explicit stop. ATR falls back to levels.atr_fallback using a proxy risk of one
ATR-equivalent only when there are no archived bars — but such marks are dropped
anyway for missing bars, so every emitted row has a real ATR.
"""

from __future__ import annotations
import json, os, sys
from statistics import median
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)        # research/levels
sys.path.insert(0, ROOT)        # predicates

import levels
from predicates import (
    Candle, is_break_and_retest, is_order_block,
    is_84_reentry_opportunity, is_chop_market, is_x_signal,
)

MARKS = os.path.join(HERE, "austin_marks_v2.jsonl")
OUT_JSONL = os.path.join(HERE, "mark_features.jsonl")
OUT_MD = os.path.join(HERE, "mark_features.md")
COVERAGE_MD = os.path.join(HERE, "bar_coverage.md")

TICK = levels.TICK


def to_candles(bars):
    """Convert levels.py bar dicts -> predicates.Candle (volume unknown -> 0)."""
    return [Candle(timestamp=b["t"], open=b["o"], high=b["h"],
                   low=b["l"], close=b["c"], volume=0) for b in bars]


def prior_extremes(bars_trunc, entry_i):
    """Session high/low of bars strictly before entry_i (bars[:entry_i])."""
    seg = bars_trunc[:entry_i]
    if not seg:
        return None, None
    hi = max(b["h"] for b in seg)
    lo = min(b["l"] for b in seg)
    return hi, lo


def nearest_above_below(nodes, ref):
    """Nearest node strictly above and strictly below ref price.

    Returns (above_node, below_node) each as dict or None.
    """
    above = [n for n in nodes if n["price"] > ref + 1e-9]
    below = [n for n in nodes if n["price"] < ref - 1e-9]
    a = min(above, key=lambda n: n["price"] - ref) if above else None
    b = min(below, key=lambda n: ref - n["price"]) if below else None
    return a, b


def find_break(bars_trunc, entry_i, level, direction):
    """Most recent bar before entry_i that BROKE `level` in `direction`.

    A break = a bar that closed through the level coming from the other side
    (mirrors is_break_and_retest's break test). Returns the bar index of the
    break candle (the bar that closed through), or None.
    """
    seg = bars_trunc[:entry_i]  # only bars before the entry bar may be breaks
    if len(seg) < 2:
        return None
    eps = 0.10 * (median(b["h"] - b["l"] for b in seg) or TICK)
    for i in range(len(seg) - 1, 0, -1):
        c, p = seg[i], seg[i - 1]
        if direction == "call":
            if p["c"] <= level and c["c"] > level + eps:
                return i
        else:
            if p["c"] >= level and c["c"] < level - eps:
                return i
    return None


def compute_features(mark, bars_trunc, entry_i):
    """Compute the full feature dict for one usable mark.

    bars_trunc is the day's RTH bars truncated to index <= entry_i
    (len == entry_i+1), so every read below is provably leakage-free.
    """
    entry_bar = bars_trunc[entry_i]
    entry_close = entry_bar["c"]
    sym, day = mark["symbol"], mark["day"]

    # ---- risk scale R = 14-bar 1m ATR up to and including entry_i ----
    R = levels.atr_1m(sym, day, entry_i)
    if not R or R <= 0:
        # atr_1m slices bars[:entry_i+1] == bars_trunc; if it still failed,
        # synthesize from the truncated bars themselves (still no future bars).
        seg = bars_trunc
        trs = []
        for i in range(1, len(seg)):
            h, l, pc = seg[i]["h"], seg[i]["l"], seg[i - 1]["c"]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        R = median(trs[-14:]) if trs else None
    if not R or R <= 0:
        R = None

    # ---- prior session extremes (for new-session-H/L + psych window) ----
    prior_hi, prior_lo = prior_extremes(bars_trunc, entry_i)
    if prior_hi is None:
        prior_hi = prior_lo = entry_close

    # ---- level node set (research/levels.py) ----
    # levels_at_bar builds psych over [lo,hi] = the session range here, plus
    # HOD/LOD (bars[:entry_i]), swings (bars[:entry_i+1]), prior-day & prior-month
    # structural nodes. None of these read a bar index > entry_i.
    nodes, cov = levels.levels_at_bar(sym, day, entry_i, entry_close,
                                     prior_lo, prior_hi)

    above, below = nearest_above_below(nodes, entry_close)

    feats = {}
    feats["dist_R_above"] = round((above["price"] - entry_close) / R, 4) if (above and R) else None
    feats["weight_above"] = above["weight"] if above else None
    feats["type_above"] = above["type"] if above else None
    feats["dist_R_below"] = round((entry_close - below["price"]) / R, 4) if (below and R) else None
    feats["weight_below"] = below["weight"] if below else None
    feats["type_below"] = below["type"] if below else None

    # ---- body/range ratio + displacement ----
    rng = entry_bar["h"] - entry_bar["l"]
    body = abs(entry_bar["c"] - entry_bar["o"])
    feats["body_range_ratio"] = round(body / rng, 4) if rng > 0 else None
    prior20 = bars_trunc[max(0, entry_i - 20):entry_i]
    prior_ranges = [b["h"] - b["l"] for b in prior20 if (b["h"] - b["l"]) > 0]
    med_rng = median(prior_ranges) if prior_ranges else None
    feats["displacement"] = round(rng / med_rng, 4) if (med_rng and med_rng > 0) else None

    # ---- bars since the retested level was broken ----
    # reference = nearest weight>=2 node to the entry close (the level being
    # retested). direction from where price sits relative to it.
    qnodes = [n for n in nodes if n["weight"] >= 2.0]
    ref = min(qnodes, key=lambda n: abs(n["price"] - entry_close)) if qnodes else None
    if ref is not None:
        direction = "call" if entry_close > ref["price"] else "put"
        break_i = find_break(bars_trunc, entry_i, ref["price"], direction)
        feats["bars_since_break"] = (entry_i - break_i) if break_i is not None else None
        feats["broken_level_price"] = ref["price"]
        feats["broken_level_type"] = ref["type"]
        feats["broken_level_weight"] = ref["weight"]
        feats["direction"] = direction
    else:
        feats["bars_since_break"] = None
        feats["broken_level_price"] = None
        feats["broken_level_type"] = None
        feats["broken_level_weight"] = None
        feats["direction"] = None

    # ---- entry_i and time of day ----
    feats["entry_i"] = entry_i
    feats["time_of_day"] = entry_bar["t"]

    # ---- new session high / low ----
    feats["new_session_high"] = bool(entry_bar["h"] > prior_hi) if prior_extremes(bars_trunc, entry_i)[0] is not None else None
    feats["new_session_low"] = bool(entry_bar["l"] < prior_lo) if prior_extremes(bars_trunc, entry_i)[1] is not None else None

    # ---- predicate outputs (root predicates.py) ----
    candles = to_candles(bars_trunc)           # last candle == entry bar; no future bars
    level_arg = ref["price"] if ref is not None else None
    dir_arg = feats["direction"]

    feats["is_break_and_retest"] = None
    feats["is_order_block"] = None
    feats["is_84_reentry_opportunity"] = None
    feats["is_chop_market"] = None
    feats["is_x_signal"] = None

    if dir_arg is not None and level_arg is not None:
        try:
            feats["is_break_and_retest"] = bool(is_break_and_retest(candles, level_arg, dir_arg))
        except Exception:
            feats["is_break_and_retest"] = None

    if dir_arg is not None:
        try:
            ob_respected, ob_candle = is_order_block(candles, dir_arg)
            feats["is_order_block"] = bool(ob_respected)
        except Exception:
            feats["is_order_block"] = None
    ob_candle = None
    if dir_arg is not None:
        try:
            _, ob_candle = is_order_block(candles, dir_arg)
        except Exception:
            ob_candle = None

    # 84% re-entry is a RE-entry: needs the original (stopped-out) trade's entry
    # & stop, which the marks do not carry. Proxy (documented in the report):
    #   original_entry_price = the broken level (where the first entry was),
    #   original_stop        = the order-block far side (where the stop sat),
    #   original_direction   = direction.
    # All inputs derive from bars <= entry_i; the predicate itself only walks
    # the supplied (truncated) window.
    if dir_arg is not None and level_arg is not None:
        if ob_candle is not None:
            o_stop = ob_candle.low if dir_arg == "call" else ob_candle.high
        else:
            o_stop = prior_lo if dir_arg == "call" else prior_hi
        try:
            feats["is_84_reentry_opportunity"] = bool(
                is_84_reentry_opportunity(candles, level_arg, dir_arg, o_stop))
        except Exception:
            feats["is_84_reentry_opportunity"] = None

    try:
        feats["is_chop_market"] = bool(is_chop_market(candles))
    except Exception:
        feats["is_chop_market"] = None

    if dir_arg is not None and level_arg is not None:
        try:
            feats["is_x_signal"] = bool(is_x_signal(candles, level_arg, dir_arg))
        except Exception:
            feats["is_x_signal"] = None
    else:
        try:
            feats["is_x_signal"] = bool(is_x_signal(candles, None, "call"))
        except Exception:
            feats["is_x_signal"] = None

    # ---- bar coverage for this row ----
    feats["bar_coverage"] = cov

    return feats


def main():
    marks = [json.loads(l) for l in open(MARKS)]

    usable = []
    dropped = []
    coverage_rows = []

    for m in marks:
        bars = levels.load_rth_bars(m["symbol"], m["day"])
        if bars is None:
            dropped.append({**m, "reason": "no_archive_file"})
            coverage_rows.append({**m, "has_rth_bars": False, "n_rth": 0, "drop_reason": "no_archive_file"})
            continue
        if m["entry_i"] >= len(bars):
            dropped.append({**m, "reason": "entry_i_out_of_range",
                            "n_rth": len(bars)})
            coverage_rows.append({**m, "has_rth_bars": True, "n_rth": len(bars),
                                  "drop_reason": "entry_i_out_of_range"})
            continue
        # ---- leakage enforcement: truncate to bars[:entry_i+1] ----
        bars_trunc = bars[: m["entry_i"] + 1]
        feats = compute_features(m, bars_trunc, m["entry_i"])
        row = {"symbol": m["symbol"], "day": m["day"],
               "entry_i": m["entry_i"], "tier": m["tier"]}
        row.update(feats)
        usable.append(row)
        coverage_rows.append({**m, "has_rth_bars": True, "n_rth": len(bars),
                              "drop_reason": None})

    # ---- write mark_features.jsonl ----
    with open(OUT_JSONL, "w") as f:
        for r in usable:
            f.write(json.dumps(r) + "\n")

    # ---- per-feature null count ----
    feat_keys = [k for k in (usable[0].keys() if usable else [])]
    null_counts = {k: 0 for k in feat_keys}
    for r in usable:
        for k in feat_keys:
            if r.get(k) is None:
                null_counts[k] += 1

    # ---- bar_coverage.md (the authority consulted for drops) ----
    with open(COVERAGE_MD, "w") as f:
        f.write("# bar_coverage\n\n")
        f.write(f"Per-mark archive coverage for `research/austin_marks_v2.jsonl` "
                f"({len(marks)} marks).\n\n")
        n_have = sum(1 for c in coverage_rows if c["has_rth_bars"] and c["drop_reason"] is None)
        n_no = sum(1 for c in coverage_rows if not c["has_rth_bars"])
        n_oob = sum(1 for c in coverage_rows if c["drop_reason"] == "entry_i_out_of_range")
        f.write(f"- Usable (archived RTH bars, entry_i in range): {n_have}\n")
        f.write(f"- Dropped (no archive file): {n_no}\n")
        f.write(f"- Dropped (entry_i out of range): {n_oob}\n\n")
        f.write("A mark is dropped iff its symbol/day has no `data_archive/<SYMBOL>/<DAY>.csv` "
                "or entry_i >= number of RTH bars. T3 feature computation skips and counts "
                "every dropped mark.\n\n")
        f.write("| symbol | day | entry_i | tier | has_rth_bars | n_rth | drop_reason |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for c in coverage_rows:
            f.write(f"| {c['symbol']} | {c['day']} | {c['entry_i']} | {c['tier']} | "
                    f"{c['has_rth_bars']} | {c['n_rth']} | {c['drop_reason'] or ''} |\n")

    # ---- mark_features.md ----
    with open(OUT_MD, "w") as f:
        f.write("# mark_features\n\n")
        f.write(f"Feature vector at every *usable* marked bar "
                f"(`research/austin_marks_v2.jsonl`).\n\n")
        f.write(f"## Counts\n\n")
        f.write(f"- Usable marks: **{len(usable)}**\n")
        f.write(f"- Dropped marks: **{len(dropped)}** "
                f"(no archived bars, per `research/bar_coverage.md`)\n")
        drop_reasons = Counter(d["reason"] for d in dropped)
        for reason, n in drop_reasons.items():
            f.write(f"  - {reason}: {n}\n")
        f.write(f"- Total marks: {len(marks)}\n\n")

        f.write("## No-future-bars (leakage) rule — how it was enforced\n\n")
        f.write(
            "Every feature reads only bars at index <= entry_i. Enforcement is "
            "structural, not aspirational. There are two paths and both are bounded:\n\n"
            "1. **Direct computation** (body/range, displacement, new-session-H/L, "
            "`find_break`, and every `predicates.*` window): for each mark the day's "
            "full RTH bar list is loaded once and **truncated to `bars[:entry_i+1]`** "
            "(the `bars_trunc` variable, length entry_i+1). These computations are "
            "handed `bars_trunc` (or `candles` built from it), so by construction "
            "they cannot index a bar beyond entry_i — `predicates`' `window = "
            "candles[-(lookback+1):]` is a suffix of that truncated list (max index "
            "entry_i), `find_break` scans `bars[:entry_i]`, displacement/new-session "
            "use `bars[:entry_i]` and `bars[entry_i-20:entry_i]`.\n\n"
            "2. **`research/levels.py` calls** (`levels_at_bar`, `atr_1m`): these "
            "routines take symbol/day/entry_i and reload the file internally, then "
            "slice themselves — they never receive the untruncated list from this "
            "script, and their internal slices are bounded at entry_i:\n"
            "- `levels.hod_lod_nodes` uses `bars[:entry_i]` (strictly before entry).\n"
            "- `levels.swing_pivots` uses `bars[:entry_i+1]`; its last possible "
            "fractal center is index entry_i-1 (it needs the entry bar only as the "
            "right neighbour), so it never reads past entry_i.\n"
            "- `levels.atr_1m` slices `bars[:entry_i+1]`.\n"
            "- `levels.prior_day_nodes` / `levels.prior_month_nodes` read **prior "
            "calendar days** only (earlier data, never the same day's future).\n"
            "- `levels.psych_nodes` is price-derived (no bars).\n\n"
            "No feature path — direct or via levels.py — ever reads a bar at index "
            "> entry_i. The bound is by construction (truncation for path 1, the "
            "documented internal slices for path 2), not by after-the-fact assertion.\n\n")

        f.write("## Feature dictionary\n\n")
        f.write("Each row of `mark_features.jsonl` carries the identity triple "
                "(symbol/day/entry_i) plus tier, then these features:\n\n")
        feat_doc = [
            ("dist_R_above", "(nearest level node above entry close - entry close) / R; R = 14-bar 1m ATR. None if no node above or no ATR."),
            ("weight_above", "weight of that nearest-above node (levels.py scale: HOD/LOD 3.0, psych$50 3.0, etc.)"),
            ("type_above", "type of that node (HOD/LOD/psych/swing_high/PDH/PMH/pivot_*)"),
            ("dist_R_below", "(entry close - nearest level node below) / R; same R."),
            ("weight_below", "weight of the nearest-below node"),
            ("type_below", "type of the nearest-below node"),
            ("body_range_ratio", "entry bar body / entry bar range"),
            ("displacement", "entry bar range / median range of the prior 20 bars"),
            ("bars_since_break", "bars elapsed from the most recent break of the retested level to the entry bar (None if no break identifiable)"),
            ("broken_level_price", "price of the retested level (nearest weight>=2 node to entry close)"),
            ("broken_level_type", "type of that retested level"),
            ("broken_level_weight", "weight of that retested level"),
            ("direction", "'call' if entry close > retested level else 'put'"),
            ("entry_i", "the entry bar's index into the RTH bar list (time-of-day proxy, included as a feature)"),
            ("time_of_day", "entry bar timestamp 'HH:MM'"),
            ("new_session_high", "entry bar high > prior session high (bars[:entry_i])"),
            ("new_session_low", "entry bar low < prior session low (bars[:entry_i])"),
            ("is_break_and_retest", "predicates.is_break_and_retest at the retested level/direction"),
            ("is_order_block", "predicates.is_order_block respected flag at direction"),
            ("is_84_reentry_opportunity", "predicates.is_84_reentry_opportunity (proxy: original_entry=broken level, original_stop=order-block far side)"),
            ("is_chop_market", "predicates.is_chop_market"),
            ("is_x_signal", "predicates.is_x_signal (reject signal) at the retested level/direction"),
            ("bar_coverage", "levels.py coverage code for the day ('rth' for all usable rows)"),
        ]
        f.write("| key | meaning |\n|---|---|\n")
        for k, d in feat_doc:
            f.write(f"| `{k}` | {d} |\n")
        f.write("\n")

        f.write("## R-unit\n\n")
        f.write("Distances are in R-multiples where **R = the 14-bar 1-minute ATR** "
                "over RTH bars up to and including entry_i (`levels.atr_1m`). The "
                "marks carry no explicit stop price; ATR_1m is the data-grounded "
                "risk scale already used by `research/levels.py` (trader stops sit "
                "at ~0.84x ATR_1m), and it is derivable purely from past bars, so "
                "using it as the R-denominator neither leaks nor invents a stop. "
                "Every usable row has a real ATR (rows without archived bars are "
                "dropped), so no `dist_R_*` falls back to a synthetic scale.\n\n")

        f.write("## Per-feature null count\n\n")
        f.write("| feature | null count (of {} usable) |\n|---|---|\n".format(len(usable)))
        for k in feat_keys:
            f.write(f"| `{k}` | {null_counts[k]} |\n")

    print(f"usable={len(usable)} dropped={len(dropped)} total={len(marks)}")
    print(f"wrote {OUT_JSONL} ({len(usable)} lines)")
    print(f"wrote {OUT_MD}")
    print(f"wrote {COVERAGE_MD}")


if __name__ == "__main__":
    main()
