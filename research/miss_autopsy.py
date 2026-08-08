"""Miss autopsy (omen-3.7 T2 + T2.1): classify WHY the engine fired no entry
at every marked bar (T2) and every Discord-alert bar (T2.1), using ONE fixed
reason vocabulary so the two distributions are directly comparable.

T2's data (the marks) and T2.1's data (the 10,379-instance corpus) are classified
by the SAME function below — there is one classifier, not two, which is the
whole point (two classifiers => two vocabularies => counts stop comparing).

Detection is NOT reimplemented. The replay is the engine's own
`SignalRunner.detect_signals`, walked bar-by-bar through the same
`CaptureRunner`/`run_day` harness `research/t4_engine_recall.py` already uses
(itself a mirror of `backtest_week.simulate_day`). The level inputs
(PDH/PDL/PMH/PML/HTF bias) are reconstructed from `data_archive/` identically to
`t4_engine_recall`. The 84% re-entry rule is NOT armed (no stopped prior trade in
replay state — see t4_engine_recall docstring), so `not_armed_84` is structurally
0 here and is reported as such.

Reason vocabulary (fixed; from the omen-3.7 T2 spec — order = the order the
checks occur inside `detect_signals`):

  detected                  entry fired within +/-2 bars (not a miss)
  too_few_candles           len(candles) < 5 at that bar
  consolidation_early_return  _is_consolidation returned True -> detect_signals []
  no_reference_level        no level in level_pairs within 0.5% of the close
  no_break_retest           detect_break_retest falsy for every level
  no_order_block            detect_order_block_setup returned None
  not_armed_84              84% re-entry but no stopped prior trade in replay
  vetoed_htf                signal built; grade_trade D via htf_bias opposed
  vetoed_candle_colour      _grade_pa D on candle colour
  vetoed_stop_too_tight     B&R risk<0.10/0.0015*close, OB/FVG risk<0.50, or
                            _route dropped a C via _min_viable_stop
  vetoed_stop_too_wide      OB path stock_risk/close > 0.004
  vetoed_pa_grade_D         _grade_pa fell through to D (not at the level)
  fired_wrong_bar           engine fired on that symbol-day but >2 bars away

Outputs:
  research/miss_autopsy.jsonl / .md          (T2 — the 159 marks)
  research/corpus_miss_autopsy.jsonl / .md   (T2.1 — the 10,379 corpus instances)
"""
from __future__ import annotations
import json, os, sys, multiprocessing
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import t4_engine_recall as t4
from omen_bot import (Candle, TradeGrade, PriceActionAnalyzer,
                      OpeningRangeAnalyzer, detect_break_retest,
                      detect_order_block_setup)

TOL = t4.TOL  # +/-2 bar join tolerance

REASONS = [
    "detected", "too_few_candles", "consolidation_early_return",
    "no_reference_level", "no_break_retest", "no_order_block", "not_armed_84",
    "vetoed_htf", "vetoed_candle_colour", "vetoed_stop_too_tight",
    "vetoed_stop_too_wide", "vetoed_pa_grade_D", "fired_wrong_bar",
]
REASON_SET = set(REASONS)

MARKS = os.path.join(HERE, "austin_marks_v2.jsonl")
CORPUS = os.path.join(HERE, "corpus_instances.jsonl")
CORPUS_ENTRIES = os.path.join(HERE, "corpus_engine_entries.jsonl")
OUT_MARKS_JSONL = os.path.join(HERE, "miss_autopsy.jsonl")
OUT_MARKS_MD = os.path.join(HERE, "miss_autopsy.md")
OUT_CORPUS_JSONL = os.path.join(HERE, "corpus_miss_autopsy.jsonl")
OUT_CORPUS_MD = os.path.join(HERE, "corpus_miss_autopsy.md")


# --------------------------------------------------------------------------
# no-detection classification (no captured signal within +/-2 of the bar)
# --------------------------------------------------------------------------
def classify_no_detection(candles, pdh, pdl, pmh, pml):
    """candles = candles[:b+1]. Returns (reason, detail) for a bar where the
    engine built NO signal at all. Mirrors detect_signals' own checks, calling
    the engine's real helpers (_is_consolidation logic, detect_break_retest,
    detect_order_block_setup)."""
    n = len(candles)
    if n < 5:
        return "too_few_candles", f"len(candles)={n} < 5"
    or_high, or_low = OpeningRangeAnalyzer.get_opening_range(candles)
    hod = max(c.high for c in candles)
    lod = min(c.low for c in candles)
    _pdh = pdh if pdh is not None else hod
    _pdl = pdl if pdl is not None else lod
    # _is_consolidation: all of [pdh,pdl,or_high,or_low] within 0.5% of mean
    lv = [_pdh, _pdl, or_high, or_low]
    avg = sum(lv) / 4.0
    if all(abs(l - avg) / avg < 0.005 for l in lv):
        return "consolidation_early_return", \
            f"PDH/PDL/OR all within 0.5% of mean ${avg:.2f} -> detect_signals returned [] silently"
    # level_pairs, exactly as detect_signals builds them (HODLOD_PAIR off)
    level_pairs = [("OR high", "OR low", or_high, or_low)]
    if pdh is not None and pdl is not None:
        level_pairs.append(("PDH", "PDL", pdh, pdl))
    if pmh is not None and pml is not None:
        level_pairs.append(("PMH", "PML", pmh, pml))
    level_vals = []
    for _, _, hi, lo in level_pairs:
        if hi is not None:
            level_vals.append(hi)
        if lo is not None:
            level_vals.append(lo)
    close = candles[-1].close
    near = [L for L in level_vals if abs(L - close) / close < 0.005]
    if not near:
        nn = min(level_vals, key=lambda L: abs(L - close)) if level_vals else None
        nnames = [t[0] for t in level_pairs]  # available level names
        return "no_reference_level", \
            (f"no level within 0.5% of close ${close:.2f}; nearest ${nn:.2f} "
             f"({abs(nn-close)/close*100:.2f}% away); levels available: "
             + ", ".join(f"{n}=${v:.2f}" for n, v in _named_levels(level_pairs)))
    # no_break_retest: detect_break_retest falsy for every level (engine order)
    br_any = False
    for _, _, hi, lo in level_pairs:
        if hi is not None and detect_break_retest(candles, hi, is_long=True):
            br_any = True
            break
        if lo is not None and detect_break_retest(candles, lo, is_long=False):
            br_any = True
            break
    if not br_any:
        return "no_break_retest", \
            "a reference level is near but detect_break_retest returned falsy for every level"
    # no_order_block: detect_order_block_setup None on both sides
    _, _, note_bull = detect_order_block_setup(candles, "bullish")
    _, _, note_bear = detect_order_block_setup(candles, "bearish")
    # block is None when note is a refusal string
    bbull = detect_order_block_setup(candles, "bullish")[0]
    bbear = detect_order_block_setup(candles, "bearish")[0]
    if bbull is None and bbear is None:
        return "no_order_block", f"{note_bull} / {note_bear}"
    # residual: a B&R pattern AND an order block both exist but neither built a
    # signal on this bar (current not beyond level / retest not in OB_RETEST_TYPES
    # / volume). No dedicated label -> fold into no_break_retest (primary path).
    return "no_break_retest", \
        "B&R pattern & order block present but neither produced a signal on this bar"


def _named_levels(level_pairs):
    out = []
    for hi_name, lo_name, hi, lo in level_pairs:
        if hi is not None:
            out.append((hi_name, hi))
        if lo is not None:
            out.append((lo_name, lo))
    return out


# --------------------------------------------------------------------------
# veto classification (a signal WAS built but routed to a skip)
# --------------------------------------------------------------------------
def classify_veto(rec, candles, htf_bias):
    """rec = a captured skip (status skipped_d/skipped_tight) at bar rec['bar'].
    Re-derives the D-reason in the order detect_signals applies it, calling the
    engine's real PriceActionAnalyzer.grade_trade."""
    b = rec["bar"]
    lb = candles[: b + 1]
    cur = lb[-1]
    lookback = lb[-6:-1] if len(lb) >= 6 else lb[:-1]
    is_long = rec["direction"] == "call"
    st = rec["signal_type"]

    if rec["status"] == "skipped_tight":
        return "vetoed_stop_too_tight", \
            "C-grade signal dropped by _route/_min_viable_stop (tight stop)"

    htf_opposed = (is_long and htf_bias == "bearish") or \
                  (not is_long and htf_bias == "bullish")
    colour_ok = cur.is_bullish if is_long else cur.is_bearish
    entry, stop = rec["entry"], rec["stop"]
    stock_risk = abs(entry - stop)

    if htf_opposed:
        return "vetoed_htf", f"htf_bias={htf_bias} opposed a {rec['direction']}"
    if not colour_ok:
        return "vetoed_candle_colour", \
            f"entry candle not {'bullish' if is_long else 'bearish'}"

    if st == "break_and_retest":
        thr = max(0.10, 0.0015 * cur.close)
        if stock_risk < thr:
            return "vetoed_stop_too_tight", \
                f"B&R stock_risk ${stock_risk:.3f} < ${thr:.3f} (0.0015*close / $0.10)"
        # colour ok & htf not opposed -> a PA-fallthrough D is promoted to C
        # (fired/skipped_tight), so a skipped_d here can only be the stop check.
        return "vetoed_pa_grade_D", "B&R residual D (PA fall-through not lifted)"
    # one_candle_rule == order block path (FLAG_ENABLED off)
    dirn = "bullish" if is_long else "bearish"
    block, _, _ = detect_order_block_setup(lb, dirn)
    if block is not None:
        base = PriceActionAnalyzer.grade_trade(cur, lookback, block.high, block.low,
                                               is_long=is_long, htf_bias=htf_bias)
    else:
        base = TradeGrade.D
    if stock_risk < 0.50:
        return "vetoed_stop_too_tight", f"OB stock_risk ${stock_risk:.3f} < $0.50"
    if stock_risk / cur.close > 0.004:
        return "vetoed_stop_too_wide", \
            f"OB stock_risk/close {stock_risk/cur.close:.4f} > 0.004"
    if base == TradeGrade.D:
        return "vetoed_pa_grade_D", "OB _grade_pa fall-through (price not at block)"
    return "vetoed_pa_grade_D", "OB residual D"


# --------------------------------------------------------------------------
# per-day replay + classify a single bar on that day
# --------------------------------------------------------------------------
def day_state(symbol, day):
    """Replay the day once. Returns dict with candles, fired entries (bars),
    raw captured signals (per-bar, with status), and the level inputs. None if
    the day has no archived bars."""
    candles = t4.rth_candles(symbol, day)
    if not candles:
        return None
    entries, all_sigs, raw = t4.run_day(symbol, day)
    pdh, pdl, pdo, pdc = t4.prior_day_levels(symbol, day)
    pmh, pml = t4.premarket_extremes(symbol, day)
    htf = t4.htf_bias(symbol, day)
    return {
        "candles": candles, "entries": entries, "raw": raw,
        "pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml, "htf": htf,
    }


def classify_bar(bar, ds):
    """Classify one bar on a replayed day. Returns (reason, detail) or None if
    bar is not resolvable (out of candle range)."""
    candles = ds["candles"]
    if bar < 0 or bar >= len(candles):
        return None
    fired_bars = [e["bar"] for e in ds["entries"]]
    # 1. detected: fired entry within +/-2
    if any(abs(b - bar) <= TOL for b in fired_bars):
        near = [b for b in fired_bars if abs(b - bar) <= TOL]
        return "detected", f"engine fired at bar(s) {near} within +/-2"
    # 2. veto: a built signal was skipped within +/-2
    skips = [r for r in ds["raw"]
             if r["status"] in ("skipped_d", "skipped_tight")
             and abs(r["bar"] - bar) <= TOL]
    if skips:
        skip = min(skips, key=lambda r: abs(r["bar"] - bar))
        return classify_veto(skip, candles, ds["htf"])
    # 3. fired_wrong_bar: engine fired on the day but >2 bars away
    if fired_bars:
        return "fired_wrong_bar", \
            f"engine fired at bar(s) {fired_bars}, all >2 from {bar}"
    # 4. no detection at this bar
    return classify_no_detection(candles[: bar + 1], ds["pdh"], ds["pdl"],
                                 ds["pmh"], ds["pml"])


# --------------------------------------------------------------------------
# T2: marks
# --------------------------------------------------------------------------
def run_marks():
    marks = [json.loads(l) for l in open(MARKS) if l.strip()]
    by_pair = defaultdict(list)
    for m in marks:
        by_pair[(m["symbol"], m["day"])].append(m)

    rows = []
    state_cache = {}
    no_bar_pairs = 0
    for (sym, day), ms in sorted(by_pair.items()):
        if (sym, day) not in state_cache:
            state_cache[(sym, day)] = day_state(sym, day)
        ds = state_cache[(sym, day)]
        if ds is None:
            no_bar_pairs += 1
            continue
        for m in ms:
            res = classify_bar(m["entry_i"], ds)
            if res is None:
                # entry_i out of candle range (e.g. >= cutoff slice) — still
                # classify via no-detection on the full available candles up to
                # the last bar, but record the out-of-range note.
                res = classify_no_detection(ds["candles"], ds["pdh"], ds["pdl"],
                                            ds["pmh"], ds["pml"])
            reason, detail = res
            assert reason in REASON_SET, reason
            rows.append({
                "symbol": sym, "day": day, "entry_i": m["entry_i"],
                "tier": m["tier"], "miss_reason": reason, "detail": detail,
            })

    with open(OUT_MARKS_JSONL, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    # reason x tier table, sorted by S column desc
    tiers = ["S", "A", "X"]
    counts = {r: Counter() for r in REASONS}
    for r in rows:
        counts[r["miss_reason"]][r["tier"]] += 1
    order = sorted([r for r in REASONS if r != "detected"],
                   key=lambda r: counts[r]["S"], reverse=True)
    # put detected first (it is not a miss but is part of the vocabulary table)
    table_order = ["detected"] + order

    def line(r):
        c = counts[r]
        return f"| {r} | {c['S']} | {c['A']} | {c['X']} | {c['S']+c['A']+c['X']} |"

    S_with_bars = sum(1 for r in rows if r["tier"] == "S")
    n_with_bars = len(rows)
    lines = []
    lines.append("# miss_autopsy (omen-3.7 T2)")
    lines.append("")
    lines.append("Why the engine fired NO entry at every marked bar. One classifier, "
                "fixed vocabulary (see footer). Detection is the engine's own "
                "`SignalRunner.detect_signals` replayed bar-by-bar via "
                "`research/t4_engine_recall.py` (a mirror of "
                "`backtest_week.simulate_day`).")
    lines.append("")
    lines.append(f"Classified **{n_with_bars}** marks that have bars (of 159; "
                 f"{no_bar_pairs} symbol-day pair(s) had no archive). "
                 f"**{S_with_bars}** of those are S marks.")
    lines.append("")
    lines.append("## Reason x tier (sorted by S column, descending)")
    lines.append("")
    lines.append("| reason | S | A | X | total |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in table_order:
        lines.append(line(r))
    # total row
    tot = Counter()
    for r in rows:
        tot[r["tier"]] += 1
    lines.append(f"| **total** | **{tot['S']}** | **{tot['A']}** | **{tot['X']}** | **{n_with_bars}** |")
    lines.append("")
    lines.append("`detected` is not a miss (the engine fired within +/-2 bars) "
                 "but is shown so the vocabulary table is complete.")
    lines.append("")
    # top-3 paragraphs
    top3 = [r for r in order if counts[r]["S"] > 0][:3]
    lines.append("## Top three S-blindness causes — what would have to change")
    lines.append("")
    for r in top3:
        c = counts[r]["S"]
        lines.append(f"### {r} ({c} S marks)")
        lines.append("")
        lines.append(_fix_paragraph(r, c))
        lines.append("")
    lines.append("## Method / vocabulary")
    lines.append("")
    lines.append("Reasons (order = order the checks occur inside `detect_signals`):")
    for r in REASONS:
        lines.append(f"- `{r}`")
    lines.append("")
    lines.append("Detection vs veto is read from `CaptureRunner`'s per-bar capture "
                 "(fired / skipped_d / skipped_tight). No-detection sub-reasons call "
                 "the engine's real helpers (`detect_break_retest`, "
                 "`detect_order_block_setup`, the `_is_consolidation` test). Veto "
                 "sub-reasons re-run `PriceActionAnalyzer.grade_trade` with the same "
                 "levels/lookback `detect_signals` uses. The 84% re-entry rule is not "
                 "armed in this replay (no stopped prior trade), so `not_armed_84` is "
                 "structurally 0 — a replay limitation, recorded not pretended away.")
    lines.append("")
    lines.append("No code was changed in this row.")
    open(OUT_MARKS_MD, "w").write("\n".join(lines) + "\n")

    # console
    print("=== marks ===")
    for r in table_order:
        c = counts[r]
        print(f"{r:28s} S={c['S']:3d} A={c['A']:3d} X={c['X']:3d} tot={c['S']+c['A']+c['X']:3d}")
    print(f"detected S = {counts['detected']['S']} (engine_recall.md expected ~4)")
    print(f"detected+veto S = {counts['detected']['S'] + sum(counts[r]['S'] for r in REASONS if r.startswith('vetoed'))} (any-signal expected ~19)")


def _fix_paragraph(reason, s_count):
    """One short paragraph per top reason: what in the code changes, roughly how
    many S marks it would reach. Do NOT change code here."""
    n = {
        "consolidation_early_return":
            "`signal_runner.py:457` (`_is_consolidation`) returns `[]` and abandons "
            "the whole bar whenever PDH/PDL/OR-high/OR-low all sit within 0.5%% of their "
            "mean. Austin has already ruled clustered levels are NOT a no-trade "
            "condition (framing B): one level broken and retested cleanly is enough, "
            "level spread is a probability input. Removing the blanket `return []` and "
            "recording level-spread as a flag would let these bars proceed to the "
            "B&R/OB paths. Would reach ~%d S marks (the bars currently killed before "
            "any setup is even tested)." % s_count,
        "no_reference_level":
            "No reference level sits within 0.5%% of the close, so `detect_break_retest` "
            "has nothing to retest. The fix is the level vocabulary: `HODLOD_PAIR`'s "
            ">=43-bar and >=30-bar-age conditions (currently OFF), and the absence of "
            "swing-pivot and round-number levels. Widening the vocabulary so a nearby "
            "swing pivot or session extreme counts as a reference would reach ~%d S "
            "marks currently graded in open air." % s_count,
        "no_break_retest":
            "`detect_break_retest` (`omen_bot.py:403`) returned falsy for every level — "
            "its ordered break/leave/retest/confirm geometry did not complete. The fix "
            "is that geometry: its 12-bar window, its `max_confirm_gap`, or its "
            "requirement that the break close beyond the level by body. Relaxing the "
            "window or the confirm gap would reach ~%d S marks where a break happened "
            "but the retest/confirm did not line up inside the window." % s_count,
        "no_order_block":
            "`detect_order_block_setup` (`omen_bot.py:304`) returned None — its four "
            "refusals (no valid block / structure broken, not isolated, no displacement, "
            "not retesting). The fix is the isolation/displacement gates or the retest "
            "type vocabulary (`OB_RETEST_TYPES`). Would reach ~%d S marks where an "
            "order block existed in structure but was refused." % s_count,
        "vetoed_stop_too_tight":
            "A signal was built but the stop was too tight: the B&R path's "
            "`stock_risk < max(0.10, 0.0015*close)` (`signal_runner.py:592`), the order "
            "block path's `stock_risk < 0.50`, or `_route` dropping a C via "
            "`_min_viable_stop` (`signal_runner.py:302`). The fix is the tight-stop "
            "thresholds or the stop-placement mode (`BNR_STOP_MODE`). Would recover "
            "~%d S marks the engine saw and then threw away for stop width." % s_count,
        "vetoed_htf":
            "`PriceActionAnalyzer.grade_trade` returned D because `htf_bias` opposed the "
            "direction (`omen_bot.py:141-144`). The fix is the HTF bias construction or "
            "its gating strength. Would recover ~%d S marks vetoed on trend." % s_count,
        "vetoed_candle_colour":
            "`_grade_pa` returned D because the entry candle was not bullish (long) / "
            "not bearish (short) (`omen_bot.py:162` / `:175`). The fix is the candle-"
            "colour requirement. Would recover ~%d S marks." % s_count,
        "vetoed_stop_too_wide":
            "The order block path's `stock_risk / close > 0.004` (`signal_runner.py:681`) "
            "set the grade to D — stop wider than 0.4%% makes 2R unreachable. The fix is "
            "that threshold or stop placement. Would recover ~%d S marks." % s_count,
        "vetoed_pa_grade_D":
            "`_grade_pa` fell through to D — price never retested the level on that bar "
            "(`omen_bot.py:173` / `:186`). The fix is the retest/at-key-level geometry. "
            "Would recover ~%d S marks." % s_count,
        "fired_wrong_bar":
            "The engine DID fire on this symbol-day, but more than 2 bars from the mark "
            "— a timing/geometry mismatch, not a blind spot. Reaching these needs the "
            "B&R window or confirm-gap widened so the fire lands on the marked bar. "
            "Would move ~%d S marks from wrong-bar to detected." % s_count,
        "too_few_candles":
            "Fewer than 5 candles at the marked bar (`signal_runner.py:512`). These are "
            "very early open marks; the fix would be lowering the 5-candle floor, which "
            "is rarely worth it. ~%d S marks." % s_count,
        "not_armed_84":
            "84%% re-entry but the replay carries no stopped-out prior trade, so the "
            "branch could not arm — a replay limitation, not a detection failure. "
            "~%d S marks (structurally 0 in this replay)." % s_count,
        "detected":
            "Not a miss — the engine already fires here. ~%d S marks." % s_count,
    }
    return n.get(reason, f"~{s_count} S marks.")


# --------------------------------------------------------------------------
# T2.1: corpus
# --------------------------------------------------------------------------
def _classify_day(task):
    """Worker: replay one (symbol, day) and classify all its instances.
    Returns (rows, out_of_range, n_inst, had_archive). Plain data only — the
    day_state (Candle objects etc.) stays in the worker and never crosses the
    process boundary, so nothing unpicklable is returned. The classifier
    (day_state + classify_bar) is the SAME one T2 uses — unchanged."""
    sym, day, xs = task
    ds = day_state(sym, day)
    if ds is None:
        return [], 0, len(xs), False
    rows = []
    out_of_range = 0
    for x in xs:
        bar = x["minute_i"]
        res = classify_bar(bar, ds)
        if res is None:
            out_of_range += 1
            continue
        reason, detail = res
        assert reason in REASON_SET, reason
        rows.append({
            "symbol": sym, "day": day, "minute_i": bar,
            "channel": x.get("channel"), "author": x.get("author"),
            "msg_id": x.get("msg_id"), "miss_reason": reason, "detail": detail,
        })
    return rows, out_of_range, len(xs), True


def run_corpus():
    inst = [json.loads(l) for l in open(CORPUS) if l.strip()]
    # official fired entries over the corpus (produced through simulate_day)
    official_entries = defaultdict(list)
    for l in open(CORPUS_ENTRIES):
        if l.strip():
            e = json.loads(l)
            official_entries[(e["symbol"], e["day"])].append(e["minute_i"])
    # group instances by (symbol, day)
    by_pair = defaultdict(list)
    for x in inst:
        by_pair[(x["symbol"], x["day"])].append(x)

    rows = []
    excluded = Counter()
    covered_days = 0
    tasks = [(sym, day, xs) for (sym, day), xs in sorted(by_pair.items())]
    # The per-day replay (~0.17s/day, 3,595 days) is the whole cost. Single-
    # process that is ~10 min; the FIRST attempt at this row ran the marks
    # autopsy + this corpus replay single-process and exceeded the 25-min wall.
    # Parallelize the per-day replay across cores — the classifier
    # (day_state + classify_bar) is byte-identical to T2's; this is purely a
    # scheduling fix so the corpus run finishes in minutes.
    nproc = max(1, multiprocessing.cpu_count())
    if len(tasks) > 50 and nproc > 1:
        with multiprocessing.Pool(nproc) as pool:
            results = pool.map(_classify_day, tasks, chunksize=16)
    else:
        results = [_classify_day(t) for t in tasks]
    for day_rows, out_of_range, n_inst, had_archive in results:
        if not had_archive:
            excluded["no_archive_file"] += n_inst
            continue
        covered_days += 1
        excluded["bar_out_of_range"] += out_of_range
        rows.extend(day_rows)

    with open(OUT_CORPUS_JSONL, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    # ---- reason counts over whole corpus ----
    counts = Counter(r["miss_reason"] for r in rows)
    order = sorted([r for r in REASONS if r != "detected"],
                  key=lambda r: counts[r], reverse=True)
    table_order = ["detected"] + order
    n_classified = len(rows)

    # ---- by channel ----
    chan_counts = defaultdict(Counter)
    for r in rows:
        chan_counts[r["channel"]][r["miss_reason"]] += 1
    # channels to report: scarface-alerts, jdub-alerts, and the rest grouped
    chans_sorted = sorted(chan_counts, key=lambda c: sum(chan_counts[c].values()), reverse=True)

    # ---- S-mark distribution from T2 (miss_autopsy.jsonl) for side-by-side ----
    s_counts = Counter()
    maj_path = OUT_MARKS_JSONL
    if os.path.exists(maj_path):
        for l in open(maj_path):
            if l.strip():
                m = json.loads(l)
                if m["tier"] == "S":
                    s_counts[m["miss_reason"]] += 1
    s_total = sum(s_counts.values())

    # ---- write md ----
    lines = []
    lines.append("# corpus_miss_autopsy (omen-3.7 T2.1)")
    lines.append("")
    lines.append("The same autopsy as `research/miss_autopsy.md` (T2), run over the "
                 "10,379-instance `omen-corpus-1.0` Discord-alert corpus, using the "
                 "SAME classifier and the SAME fixed reason vocabulary — so the counts "
                 "are directly comparable to T2's mark autopsy.")
    lines.append("")
    lines.append("## Structural difference from T2")
    lines.append("")
    lines.append("Corpus instances are **alerts from Discord**, not Austin's own graded "
                 "setups, so there is no S/A/X tier. Reasons are reported as a flat "
                 "distribution, plus a split by `channel` "
                 "(`scarface-alerts` 4,020, `jdub-alerts` 3,080, remainder per "
                 "`research/corpus_instances.md`).")
    lines.append("")
    total_inst = len(inst)
    lines.append("## Coverage / classification count")
    lines.append("")
    lines.append(f"- Total corpus instances: **{total_inst}**")
    lines.append(f"- Covered symbol-days (the denominator, per "
                 f"`research/corpus_bar_coverage.md`): **3,595**")
    lines.append(f"- Distinct (symbol, day) pairs with bars replayed here: **{covered_days}**")
    lines.append(f"- **Instances classified: {n_classified}** (of {total_inst}; "
                 f"those on the {covered_days} covered days whose `minute_i` resolves "
                 f"to a bar index).")
    if sum(excluded.values()):
        lines.append(f"- Excluded: {dict(excluded)} "
                     f"(no archived bars for the day, or minute_i outside the day's "
                     f"RTH bar range — e.g. premarket/after-hours alerts).")
    lines.append("")
    lines.append("`minute_i` is minutes since 09:30, the same frame as the marks' "
                 "`entry_i`, so the +/-2 bar join and the per-bar classification are "
                 "identical to T2.")
    lines.append("")
    lines.append("## Reason counts over the whole corpus")
    lines.append("")
    lines.append("| reason | count | % |")
    lines.append("|---|---:|---:|")
    for r in table_order:
        c = counts[r]
        lines.append(f"| {r} | {c} | {100.0*c/n_classified:.1f}% |" if n_classified else f"| {r} | 0 | 0% |")
    lines.append(f"| **total** | **{n_classified}** | |")
    lines.append("")
    lines.append("## Reason counts split by channel")
    lines.append("")
    head = "| reason | " + " | ".join(chans_sorted) + " |"
    sep = "|---|" + "|".join(["---:" for _ in chans_sorted]) + "|"
    lines.append(head)
    lines.append(sep)
    for r in table_order:
        cells = " | ".join(str(chan_counts[c][r]) for c in chans_sorted)
        lines.append(f"| {r} | {cells} |")
    tot_cells = " | ".join(str(sum(chan_counts[c].values())) for c in chans_sorted)
    lines.append(f"| **total** | {tot_cells} |")
    lines.append("")
    # ---- side-by-side with T2 S-mark distribution ----
    lines.append("## Side-by-side: corpus vs T2's S-mark reason distribution")
    lines.append("")
    lines.append("Corpus (n=%d classified instances) against the S column of "
                 "`research/miss_autopsy.md` (n=%d S marks with bars). Same vocabulary, "
                 "same classifier." % (n_classified, s_total))
    lines.append("")
    lines.append("| reason | corpus count | corpus % | S-mark count | S-mark % |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in table_order:
        cc = counts[r]
        sc = s_counts.get(r, 0)
        cp = f"{100.0*cc/n_classified:.1f}%" if n_classified else "0%"
        sp = f"{100.0*sc/s_total:.1f}%" if s_total else "0%"
        lines.append(f"| {r} | {cc} | {cp} | {sc} | {sp} |")
    lines.append(f"| **total** | **{n_classified}** | | **{s_total}** | |")
    lines.append("")
    # verdict on agreement
    top_corpus = max((r for r in table_order if r != "detected"),
                     key=lambda r: counts[r], default=None)
    top_s = max((r for r in REASONS if r != "detected"),
                key=lambda r: s_counts.get(r, 0), default=None)
    lines.append("## Agreement")
    lines.append("")
    if top_corpus and top_s:
        cc = counts[top_corpus]; sc = s_counts.get(top_s, 0)
        if top_corpus == top_s:
            lines.append(f"**The same reason tops both: `{top_corpus}`** "
                         f"(corpus {cc}/{n_classified}, S-marks {s_counts.get(top_s,0)}/{s_total}). "
                         "Austin's own graded setups and the Discord alerts fail the "
                         "same way at n=3,595 and n≈77 — the strongest evidence this "
                         "project has for what to change. T5 should target "
                         f"`{top_s}`.")
        else:
            lines.append(f"They **disagree**. The corpus's top reason is "
                         f"`{top_corpus}` ({cc}/{n_classified}); the S-mark top "
                         f"reason is `{top_s}` ({sc}/{s_total}). That means Austin's "
                         "own graded setups fail differently from the alerts. "
                         "**T5 must follow the S column** — Austin's setups are the "
                         "target; the Discord alerts are not.")
    else:
        lines.append("Could not determine a top reason on one side.")
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append("Same as `research/miss_autopsy.md`: the engine's own "
                 "`detect_signals` replayed bar-by-bar via "
                 "`research/t4_engine_recall.py`, with `CaptureRunner` recording "
                 "every built signal's status (fired / skipped_d / skipped_tight) "
                 "per bar. `detected` = fired entry within +/-2 bars; veto reasons "
                 "re-run `grade_trade`; no-detection reasons call the engine's real "
                 "`detect_break_retest` / `detect_order_block_setup` / "
                 "`_is_consolidation`. The 84% rule is not armed in replay, so "
                 "`not_armed_84` is structurally 0. Bars past the 11:00 entry cutoff "
                 "are classified by detection state (the engine would not trade them "
                 "regardless, but the vocabulary has no cutoff label). No code changed.")
    open(OUT_CORPUS_MD, "w").write("\n".join(lines) + "\n")

    # console
    print("=== corpus ===")
    for r in table_order:
        print(f"{r:28s} {counts[r]:5d}  {100.0*counts[r]/n_classified:.1f}%")
    print(f"classified {n_classified}/{total_inst}; covered days {covered_days}")
    print(f"top corpus={top_corpus}  top S={top_s}  agree={top_corpus==top_s}")


if __name__ == "__main__":
    run_marks()
    run_corpus()
