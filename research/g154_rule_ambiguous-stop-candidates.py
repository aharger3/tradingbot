"""g154 -- F5: "ambiguous-stop-candidates" (refusal-indicator), measured over the honest book.

Austin's words, mined in F1/F4 from his own marks (the corpus itself is
SILENT -- research/g153_corpus_confirm_ambiguous-stop-candidates.md):

  * "AS CANDLE FORMING, see on that candle close you get a bad entry? and its
    hard to enter a stock when there 2 stop loss options ..." (PLTR_2024-10-23)
  * "not respecting level, 2 stop losses to choose from no other" (META_2024-09-30)
  * "mini higher highs so makes the stop muddled" (PLTR_2025-08-06)

The rule (row F5): a stop that is AMBIGUOUS -- two live stop candidates that
do not agree, or a muddled structure with several recent highs/lows -- is a
downgrade in itself, independent of clean entry criteria. Polarity:
refusal-indicator (skip an ambiguous candidate, take the next one that day).

THREE STOP CANDIDATES computed from data_archive at index <= entry_i (no
lookahead -- the signal bar is fully printed by the time this runs):

  1. ocr_wick     -- the extreme of the "OCR candle" -- the order-block
                      candle `omen_bot.detect_order_block_setup` locates from
                      candles[:entry_i+1] (the SAME anatomy the
                      ocr-strict-definition rule and OCR_STRICT already use).
                      For a call (direction="bullish"), the block is the last
                      down candle before the break -- its LOW is the wick that
                      would invalidate the setup. For a put, the block is the
                      last up candle -- its HIGH invalidates. None when no
                      order block resolves standalone from this bar slice.
  2. broken_level -- r['level_px'], the level the setup is built on.
  3. entry_bar    -- the signal bar's OWN adverse extreme: bars[entry_i].low
                      for a call, .high for a put (same convention
                      research/g154_rule_forming-candle-entry-not-extreme.py
                      already uses for "the bar's adverse extreme").

avg_rng = mean(High - Low) over the 10 bars strictly before entry_i (fewer
if entry_i < 10; ambiguity is not computable with 0 prior bars).

AMBIGUOUS when >= 2 of the 3 candidates are:
  (a) on the correct (adverse) side of entry -- a candidate on the wrong
      side is not a real competing stop and is excluded; this operationalizes
      "neither nests inside the other (both on the same side of entry with a
      gap between)" from the row's predicate: a stop that would sit on the
      wrong side of entry can't "nest" with a real one, it just isn't a live
      candidate, and
  (b) pairwise farther apart than 1 x avg_rng -- the "gap between" clause.
A row with < 2 valid same-side candidates, or no computable avg_rng (bars
unreadable / entry_i < 1), is treated as NOT ambiguous (conservative: missing
data never manufactures a flag).

Arm (refusal-indicator, DROP polarity): an ambiguous row is skipped; the
day's first-of-day pick falls through to the next candidate, exactly as
omen_metrics.first_of_day_arm's pick-then-gate fix already does for the size
gate (two owners of one decision was the bug that fix closed -- this rule
reuses the same fall-through, not a second implementation of it).

PRIOR ART, reused not re-derived:
  - research/g86_honest_ceiling.py, research/g91_lane_slice.py -- the
    one-trade-a-day unit.
  - research/omen_metrics.py -- first_of_day_arm, _row_is_sizeable (size gate
    on signal_runner.min_risk_floor).
  - research/g154_rule_forming-candle-entry-not-extreme.py -- the
    bars-feature scoring/recall/precision scaffolding this file copies.
  - research/g154_rule_ocr-strict-definition.py -- the
    detect_order_block_setup call shape (candles[:entry_i+1], direction,
    out=info dict for block_idx/break_idx).
  - omen_bot.py::detect_order_block_setup -- imported, not reimplemented.
  - polygon_feed.py -- fetch_day/rth, cache-only bar reads.
  - research/marks_pool.py -- canonical_pool(), s_days() for recall/precision.

    python research/g154_rule_ambiguous-stop-candidates.py

Writes research/g154_rule_ambiguous-stop-candidates.{json,md}.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import polygon_feed as pf                                   # noqa: E402  cache-only bar reads
from omen_bot import detect_order_block_setup               # noqa: E402  imported, not reimplemented
from omen_metrics import _row_is_sizeable                     # noqa: E402  size gate
import marks_pool                                             # noqa: E402
import grade_read                                              # noqa: E402

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")
SWEEP_PATH = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT_JSON = os.path.join(HERE, "g154_rule_ambiguous-stop-candidates.json")
OUT_MD = os.path.join(HERE, "g154_rule_ambiguous-stop-candidates.md")

RISK = 1000.0
H_SPLIT = "2025-09-01"
PRIOR_BARS = 10
GAP_MULT = 1.0

_bars_cache = {}
_ambig_cache = {}


def get_bars(sym, day):
    k = (sym, day)
    if k not in _bars_cache:
        try:
            _bars_cache[k] = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            _bars_cache[k] = []
    return _bars_cache[k]


def _ocr_wick(candles, direction):
    """The extreme of the order-block ("OCR") candle, or None if no valid
    order block resolves standalone from this bar slice."""
    if len(candles) < 3:
        return None
    info = {}
    try:
        block, retest, _note = detect_order_block_setup(candles, direction, out=info)
    except Exception:
        return None
    if block is None:
        return None
    return block.low if direction == "bullish" else block.high


def is_ambiguous(row):
    """(ambiguous: bool, detail: dict) -- computed once per (sym, day,
    entry_i, dir) and cached, since the same signal bar can recur across
    corpora reads."""
    key = (row["sym"], row["day"], row.get("entry_i"), row["dir"])
    if key in _ambig_cache:
        return _ambig_cache[key]
    result = _compute_ambiguous(row)
    _ambig_cache[key] = result
    return result


def _compute_ambiguous(row):
    i = row.get("entry_i")
    if i is None or i < 1:
        return False, {"reason": "no entry_i / too early for prior bars"}
    bars = get_bars(row["sym"], row["day"])
    if not bars or i >= len(bars):
        return False, {"reason": "bars unreadable"}

    prior = bars[max(0, i - PRIOR_BARS):i]
    if not prior:
        return False, {"reason": "no prior bars for avg_rng"}
    avg_rng = sum(b.high - b.low for b in prior) / len(prior)
    if avg_rng <= 0:
        return False, {"reason": "degenerate avg_rng"}

    candles = bars[: i + 1]
    entry = row["entry"]
    is_call = row["dir"] == "call"
    direction = "bullish" if is_call else "bearish"
    sig_bar = bars[i]

    raw = {
        "ocr_wick": _ocr_wick(candles, direction),
        "broken_level": row.get("level_px"),
        "entry_bar": sig_bar.low if is_call else sig_bar.high,
    }

    # keep only candidates on the correct (adverse) side of entry -- a value
    # on the wrong side is not a live competing stop, it's not comparable.
    valid = {}
    for name, px in raw.items():
        if px is None:
            continue
        on_side = (px < entry) if is_call else (px > entry)
        if on_side:
            valid[name] = px

    if len(valid) < 2:
        return False, {"reason": "fewer than 2 same-side candidates",
                        "raw": raw, "avg_rng": round(avg_rng, 4)}

    names = list(valid)
    gaps = []
    for a in range(len(names)):
        for b in range(a + 1, len(names)):
            gaps.append((abs(valid[names[a]] - valid[names[b]]), names[a], names[b]))
    max_gap, na, nb = max(gaps, key=lambda g: g[0])
    ambiguous = max_gap > GAP_MULT * avg_rng
    return ambiguous, {
        "raw": raw, "valid": valid, "avg_rng": round(avg_rng, 4),
        "max_gap": round(max_gap, 4), "max_gap_pair": (na, nb),
    }


# --------------------------------------------------------------- candidate stream

def ekey(r):
    return (r["day"], r["et"], r["sym"])


def by_day_candidates(rows):
    """Same population as g86_honest_ceiling.candidates / omen_metrics.
    first_of_day_arm: fired-and-traded rows, plus halted rows (one-a-day
    means that halt cannot have fired yet, so the day is live again)."""
    byday = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            byday[r["day"]].append(r)
    for v in byday.values():
        v.sort(key=ekey)
    return byday


def pick_first_of_day(byday, drop_ambiguous):
    """First-of-day, size-gated, optionally skipping ambiguous rows (the
    refusal-indicator polarity: skip and take the next). Mirrors
    omen_metrics.first_of_day_arm's pick-then-gate fix -- the gate runs
    INSIDE selection so a dropped/unsizeable first candidate falls through
    to the next one on the same day, never skips the day."""
    firsts = []
    for day in sorted(byday):
        v = byday[day]
        pick = None
        for r in v:
            if _row_is_sizeable(r) is False:
                continue
            if drop_ambiguous:
                ambig, _detail = is_ambiguous(r)
                if ambig:
                    continue
            pick = r
            break
        if pick is not None:
            firsts.append(pick)
    return firsts


# --------------------------------------------------------------------- scoring

def drawdown(pnls):
    peak = cum = worst = 0.0
    for p in pnls:
        cum += p
        peak = max(peak, cum)
        worst = min(worst, cum - peak)
    return worst


def split_h1_h2(firsts):
    h1 = [r for r in firsts if r["day"] < H_SPLIT]
    h2 = [r for r in firsts if r["day"] >= H_SPLIT]
    return h1, h2


def score(firsts):
    if not firsts:
        return {"n": 0, "usd_day": 0.0, "mean_r": 0.0, "win_pct": 0.0,
                "green_months": 0, "months": 0, "max_dd": 0.0}
    days = sorted({r["day"] for r in firsts})
    n_days = len(days)
    pnls = [r["pnl"] for r in firsts]
    wins = sum(1 for r in firsts if r["pnl"] > 0)
    losses = sum(1 for r in firsts if r["pnl"] < 0)
    by_m = defaultdict(float)
    for r in firsts:
        by_m[r["day"][:7]] += r["pnl"]
    total = sum(pnls)
    return {
        "n": len(firsts),
        "usd_day": round(total / n_days, 2),
        "mean_r": round(total / len(firsts) / RISK, 4),
        "win_pct": round(wins / (wins + losses) * 100, 1) if (wins + losses) else 0.0,
        "green_months": sum(1 for v in by_m.values() if v > 0),
        "months": len(by_m),
        "max_dd": round(drawdown([r["pnl"] for r in sorted(firsts, key=ekey)]), 2),
    }


# --------------------------------------------------------------------- S recall

def load_sweep_s_days():
    """The 34 S symbol-days out of the 100-card probe_s_sweep deck."""
    out = []
    with open(SWEEP_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if grade_read.read_grade(r) is not None and grade_read.is_s(r):
                out.append((r["symbol"], r["date"]))
    return out


def recall(firsts, s_pairs):
    """Fraction of s_pairs for which the arm fired on THAT symbol on THAT
    day (arrival-order, size-gated; a one-trade-a-day arm across ALL symbols
    can only be measured this way -- a day's pick is one symbol, so recall
    asks whether that pick happened to be the S symbol)."""
    if not s_pairs:
        return 0.0, 0, 0
    fired_syms_by_day = defaultdict(set)
    for r in firsts:
        fired_syms_by_day[r["day"]].add(r["sym"])
    hit = sum(1 for sym, day in s_pairs if sym in fired_syms_by_day.get(day, ()))
    return round(hit / len(s_pairs) * 100, 1), hit, len(s_pairs)


def precision(firsts, pool):
    """fired days graded S / fired days graded at all, per canonical_pool()."""
    graded_s = graded_any = 0
    for r in firsts:
        key = "%s_%s" % (r["sym"], r["day"])
        entry = pool.get(key)
        if entry is None:
            continue
        graded_any += 1
        if entry.grade == "S":
            graded_s += 1
    pct = round(graded_s / graded_any * 100, 1) if graded_any else 0.0
    return pct, graded_s, graded_any


def full_arm(firsts, s_pairs_100, all_s_pairs, pool, n_days_total):
    h1, h2 = split_h1_h2(firsts)
    out = {
        "overall": score(firsts), "H1": score(h1), "H2": score(h2),
        "fires_per_day": round(len(firsts) / n_days_total, 3),
    }
    r100, hit100, n100 = recall(firsts, s_pairs_100)
    rall, hitall, nall = recall(firsts, all_s_pairs)
    p, gs, ga = precision(firsts, pool)
    out["s_recall_100"] = {"pct": r100, "hit": hit100, "n": n100}
    out["s_recall_all_bar_backed"] = {"pct": rall, "hit": hitall, "n": nall}
    out["precision"] = {"pct": p, "graded_s": gs, "graded_any": ga}
    return out


# --------------------------------------------------------------------------- main

def main():
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    byday = by_day_candidates(rows)
    n_days_total = meta.get("sessions") or len({r["day"] for r in rows})
    all_cands = [r for v in byday.values() for r in v]
    cand_per_day = round(len(all_cands) / n_days_total, 2)

    s_pairs_100 = load_sweep_s_days()
    pool = marks_pool.canonical_pool()
    all_s_pairs = [tuple(k.split("_", 1)) for k in marks_pool.s_days(pool)]

    # -------- ambiguous rate over ALL candidates (not just first-of-day) --------
    n_ambig = 0
    n_computable = 0
    for r in all_cands:
        ambig, detail = is_ambiguous(r)
        if "reason" not in detail:
            n_computable += 1
        if ambig:
            n_ambig += 1
    ambig_rate_pct = round(n_ambig / len(all_cands) * 100, 2) if all_cands else 0.0

    # ambiguous rate against his S/A/C/none grades, per graded fired-candidate
    grade_counts = defaultdict(lambda: [0, 0])  # grade -> [n, n_ambiguous]
    for r in all_cands:
        key = "%s_%s" % (r["sym"], r["day"])
        entry = pool.get(key)
        g = entry.grade if entry is not None else "ungraded"
        ambig, _d = is_ambiguous(r)
        grade_counts[g][0] += 1
        if ambig:
            grade_counts[g][1] += 1
    ambig_by_grade = {
        g: {"n": n, "n_ambiguous": na,
            "pct": round(na / n * 100, 1) if n else 0.0}
        for g, (n, na) in grade_counts.items()
    }

    # ambiguous rate against realized R
    r_ambig = [r["r"] for r in all_cands if is_ambiguous(r)[0] and r.get("r") is not None]
    r_clean = [r["r"] for r in all_cands if not is_ambiguous(r)[0] and r.get("r") is not None]
    realized_r = {
        "ambiguous": {"n": len(r_ambig),
                      "mean_r": round(sum(r_ambig) / len(r_ambig), 4) if r_ambig else None},
        "clean": {"n": len(r_clean),
                  "mean_r": round(sum(r_clean) / len(r_clean), 4) if r_clean else None},
    }

    baseline_firsts = pick_first_of_day(byday, drop_ambiguous=False)
    baseline = full_arm(baseline_firsts, s_pairs_100, all_s_pairs, pool, n_days_total)

    arm_firsts = pick_first_of_day(byday, drop_ambiguous=True)
    arm = full_arm(arm_firsts, s_pairs_100, all_s_pairs, pool, n_days_total)

    h1_delta_usd = arm["H1"]["usd_day"] - baseline["H1"]["usd_day"]
    h2_delta_usd = arm["H2"]["usd_day"] - baseline["H2"]["usd_day"]
    usd_improves = h1_delta_usd > 0 and h2_delta_usd > 0
    prec_improves = arm["precision"]["pct"] > baseline["precision"]["pct"]
    recall_ok = arm["s_recall_100"]["pct"] >= baseline["s_recall_100"]["pct"]
    survivor = bool((usd_improves or prec_improves) and recall_ok)

    out = {
        "row": "F5",
        "slug": "ambiguous-stop-candidates",
        "predicate": ("3 stop candidates from data_archive at index <= entry_i: "
                      "ocr_wick (order-block candle extreme via "
                      "omen_bot.detect_order_block_setup), broken_level "
                      "(r['level_px']), entry_bar (signal bar's adverse extreme). "
                      "avg_rng = mean(High-Low) over prior 10 bars. AMBIGUOUS when "
                      ">=2 candidates are on the adverse side of entry AND pairwise "
                      "farther apart than 1x avg_rng."),
        "polarity": "refusal-indicator (DROP ambiguous rows, take next candidate)",
        "n_days_total": n_days_total,
        "candidates_per_day": cand_per_day,
        "n_candidates_all": len(all_cands),
        "n_candidates_ambiguity_computable": n_computable,
        "ambiguous_rate_pct_of_all_candidates": ambig_rate_pct,
        "ambiguous_by_his_grade": ambig_by_grade,
        "realized_r_ambiguous_vs_clean": realized_r,
        "baseline": baseline,
        "arm": arm,
        "h1_delta_usd_day": round(h1_delta_usd, 2),
        "h2_delta_usd_day": round(h2_delta_usd, 2),
        "survivor": survivor,
        "notes": (
            "survivor = True only if (H1 AND H2 both improve $/day) OR "
            "precision improves, AND S-recall-100 does not fall below "
            "baseline. 'On the adverse side of entry with a gap between' is "
            "read as: exclude a candidate that sits on the WRONG side of "
            "entry (not a live competing stop) before testing the >1x "
            "avg_rng gap -- this is how 'neither nests inside the other' is "
            "operationalized here, since two same-side points on a line "
            "can't nest, they can only be near or far. Ambiguity is scored "
            "over the FULL candidate population (not just first-of-day "
            "picks) for the rate-vs-his-grades and rate-vs-realized-R "
            "reads; the $/day arm applies the drop only inside first-of-day "
            "selection, per the row's arm instruction."),
    }

    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=2)
    write_md(out)
    print(json.dumps(out, indent=2))
    return out


def _fmt_row(label, d):
    o = d["overall"] if "overall" in d else d
    return ("| %s | %d | $%s | %s | %s%% | %s/%s | $%s |" %
            (label, o["n"], o["usd_day"], o["mean_r"], o["win_pct"],
             o["green_months"], o["months"], o["max_dd"]))


def write_md(out):
    lines = []
    lines.append("# g154 -- F5 ambiguous-stop-candidates\n")
    lines.append("**What is different now:** measured Austin's rule that an "
                 "ambiguous stop (two disagreeing stop candidates, or a "
                 "muddled structure) is a downgrade in itself, as a "
                 "refusal-indicator arm over the one-trade-a-day book.\n")
    lines.append("## Ambiguous rate\n")
    lines.append("%s%% of all %d fired/halted candidates are flagged "
                 "ambiguous (%d had a computable avg_rng)." %
                 (out["ambiguous_rate_pct_of_all_candidates"],
                  out["n_candidates_all"], out["n_candidates_ambiguity_computable"]))
    lines.append("")
    lines.append("### Against his S/A/C/none grades\n")
    lines.append("| grade | n candidates | n ambiguous | pct ambiguous |")
    lines.append("|---|---:|---:|---:|")
    for g, d in sorted(out["ambiguous_by_his_grade"].items(),
                        key=lambda kv: -kv[1]["n"]):
        lines.append("| %s | %d | %d | %s%% |" % (g, d["n"], d["n_ambiguous"], d["pct"]))
    lines.append("")
    lines.append("### Against realized R\n")
    rr = out["realized_r_ambiguous_vs_clean"]
    lines.append("| bucket | n | mean R |")
    lines.append("|---|---:|---:|")
    lines.append("| ambiguous | %d | %s |" % (rr["ambiguous"]["n"], rr["ambiguous"]["mean_r"]))
    lines.append("| clean | %d | %s |\n" % (rr["clean"]["n"], rr["clean"]["mean_r"]))

    b, a = out["baseline"], out["arm"]
    lines.append("## Baseline (no drop) vs arm (drop ambiguous)\n")
    lines.append("| arm | pop | n | $/day | mean R | win | green/mo | max DD |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for label, d in (("baseline", b), ("arm", a)):
        lines.append("| %s | overall | %d | $%s | %s | %s%% | %s/%s | $%s |" %
                      (label, d["overall"]["n"], d["overall"]["usd_day"],
                       d["overall"]["mean_r"], d["overall"]["win_pct"],
                       d["overall"]["green_months"], d["overall"]["months"],
                       d["overall"]["max_dd"]))
        lines.append("| %s | H1 | %d | $%s | %s | %s%% | %s/%s | $%s |" %
                      (label, d["H1"]["n"], d["H1"]["usd_day"], d["H1"]["mean_r"],
                       d["H1"]["win_pct"], d["H1"]["green_months"], d["H1"]["months"],
                       d["H1"]["max_dd"]))
        lines.append("| %s | H2 | %d | $%s | %s | %s%% | %s/%s | $%s |" %
                      (label, d["H2"]["n"], d["H2"]["usd_day"], d["H2"]["mean_r"],
                       d["H2"]["win_pct"], d["H2"]["green_months"], d["H2"]["months"],
                       d["H2"]["max_dd"]))
    lines.append("")
    lines.append("candidates/day: %s -- fires/day baseline: %s -- fires/day arm: %s" %
                 (out["candidates_per_day"], b["fires_per_day"], a["fires_per_day"]))
    lines.append("S recall (100-card, 34 S): baseline %s%% (%d/%d) -- arm %s%% (%d/%d)" %
                 (b["s_recall_100"]["pct"], b["s_recall_100"]["hit"], b["s_recall_100"]["n"],
                  a["s_recall_100"]["pct"], a["s_recall_100"]["hit"], a["s_recall_100"]["n"]))
    lines.append("S recall (all bar-backed): baseline %s%% (%d/%d) -- arm %s%% (%d/%d)" %
                 (b["s_recall_all_bar_backed"]["pct"], b["s_recall_all_bar_backed"]["hit"],
                  b["s_recall_all_bar_backed"]["n"], a["s_recall_all_bar_backed"]["pct"],
                  a["s_recall_all_bar_backed"]["hit"], a["s_recall_all_bar_backed"]["n"]))
    lines.append("precision: baseline %s%% (%d/%d) -- arm %s%% (%d/%d)\n" %
                 (b["precision"]["pct"], b["precision"]["graded_s"], b["precision"]["graded_any"],
                  a["precision"]["pct"], a["precision"]["graded_s"], a["precision"]["graded_any"]))

    lines.append("## Survivor verdict\n")
    lines.append("H1 delta $/day: %s -- H2 delta $/day: %s" %
                 (out["h1_delta_usd_day"], out["h2_delta_usd_day"]))
    lines.append("**survivor = %s**\n" % out["survivor"])
    lines.append(out["notes"])
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
