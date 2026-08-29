"""T2 -- the one-candle-rule DETECTOR, measured against Austin's own sentence.

Austin, probe_master_2026-08-29, fact_ocr_demote note:

    "s trades are all about being early and the most important thing is that
     clear break retest with displacement that happens quick and strong PA entry"

He graded 20 killed one-candle-rule setups in the same session and returned
17 "not this setup at all", 3 "real but not tradeable", ZERO real. So the
imbalance the OCR demote was blamed for is a DETECTION problem: R3 lifted the
demote (rightly, "Ther is no B") and that alone promotes garbage. This script
measures what belongs behind it.

Stage 1  extract, for every one_candle_rule detection in the book, the features
         his sentence names -- clear break, retest, displacement, quick, strong
         PA entry -- by replaying the exact bar prefix the engine saw.
Stage 2  reachability funnel: how many of the current detections satisfy each
         clause and the composite. (Method rule 3: under 1% or over 85% and the
         finding is about the gate, not the threshold.)
Stage 3  validation on his 20 refusals -- a good definition rejects most of them.
Stage 4  a "quick" sweep, because his sentence carries no number for it.

Nothing here writes a mark file. Usage:

    python research/t2_ocr_detector.py --stage1     # features -> _t2_ocr_features.json
    python research/t2_ocr_detector.py --report     # stages 2-4 from that file
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("POLYGON_API_KEY", "unset")

import polygon_feed as pf                                     # noqa: E402
from omen_bot import (Candle, MarketStructure, check_retest_type,   # noqa: E402
                      DISPLACEMENT_MULT, _is_isolated, ocr_quality,
                      OCR_QUICK_BLOCK_TO_BREAK as QUICK_BLOCK_TO_BREAK,
                      OCR_QUICK_BREAK_TO_ENTRY as QUICK_BREAK_TO_ENTRY)
from signal_runner import OB_RETEST_TYPES, STRONG_PA_MULT      # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades.json"
MARKS = ROOT / "research" / "marks" / "probe_master_2026-08-29.jsonl"
FEATS = ROOT / "research" / "_t2_ocr_features.json"

# ---------------------------------------------------------------------------
# The four clauses of his sentence, as predicates.
#
# Every threshold below is either (a) already in the engine, named, with its own
# provenance, or (b) swept in stage 4 because his sentence carries no number.
#
#   "clear break"      -> price LEFT the block after the break. This is exactly
#                         the LEAVE step detect_break_retest already enforces
#                         ("price actually left, didn't chop on it"); the OCR
#                         path never had it. No new constant.
#   "retest"           -> OB_RETEST_TYPES, already ("wick_only",). No change.
#   "with displacement"-> _has_displacement, already DISPLACEMENT_MULT=1.5x the
#                         avg prior body. Reported as a continuous ratio here so
#                         the multiple can be swept rather than asserted.
#   "happens quick"    -> bars(block -> break) + bars(break -> entry). No number
#                         exists in his sentence, so stage 4 sweeps it.
#   "strong PA entry"  -> STRONG_PA_MULT, the codebase's OWN definition of strong
#                         price action (signal_runner, the 84% rule reclaim gate:
#                         body >= 1.5x the avg body of the prior 10 candles),
#                         applied to the OCR entry candle in the trade direction.
#                         Reused, not invented.
#   "being early"      -> reported (minute of the session, and how far the entry
#                         close sits beyond the retested level) but NOT part of
#                         the composite: chase is already its own downgrade
#                         variable under R22 and double-counting it would make
#                         this measurement about the grader again.
# ---------------------------------------------------------------------------

def _avg_body(candles, upto_idx, n=10):
    prior = candles[max(0, upto_idx - n):upto_idx]
    if not prior:
        return 0.0
    return sum(c.body_size for c in prior) / len(prior)


def ocr_features(candles, i, direction):
    """Recompute the OCR anatomy the engine saw at bar `i`.

    Mirrors omen_bot.detect_order_block_setup exactly (same MarketStructure,
    same block/break index derivation), then adds the measurements his sentence
    asks for. Returns None when the detector would not have fired here.
    """
    prefix = candles[:i + 1]
    st = MarketStructure()
    st.update(prefix)
    blocks = st.get_valid_order_blocks(prefix, direction)
    if not blocks:
        return None
    block = blocks[0]
    anchor = st.last_hh if direction == "bullish" else st.last_ll
    if anchor is None:
        return None
    break_idx = anchor[2]
    try:
        block_idx = next(
            j for j in range(break_idx - 1, -1, -1)
            if (prefix[j].is_bearish if direction == "bullish" else prefix[j].is_bullish))
    except StopIteration:
        return None
    if not _is_isolated(prefix, block_idx):
        return None
    retest = check_retest_type(block, prefix[-1], direction)

    bull = direction == "bullish"
    b_hi, b_lo = block.high, block.low

    # displacement, as a continuous ratio (the gate is >= DISPLACEMENT_MULT)
    avg_prior = _avg_body(prefix, block_idx, 10)
    leg = prefix[block_idx + 1:break_idx + 1]
    bodies = [c.body_size for c in leg if (c.is_bullish if bull else c.is_bearish)]
    disp_ratio = (max(bodies) / avg_prior) if (bodies and avg_prior > 0) else float("inf")

    # "clear break": after the break bar, did price actually LEAVE the block?
    after = prefix[break_idx:i]           # break bar through the bar before entry
    if bull:
        left = any(c.low > b_hi for c in after)
        max_clear = max((c.low - b_hi for c in after), default=0.0)
    else:
        left = any(c.high < b_lo for c in after)
        max_clear = max((b_lo - c.high for c in after), default=0.0)

    # "clear break", "quick", "strong PA entry" all come from omen_bot.ocr_quality
    # -- the SAME function the engine gates on under OCR_STRICT, so the number
    # below and the shipped detector can never drift apart.
    q = ocr_quality(prefix, block, block_idx, break_idx, direction)
    cur = prefix[-1]
    entry_body_ratio = q["_body_ratio"]
    rng = cur.high - cur.low
    close_pos = ((cur.close - cur.low) / rng) if rng > 0 else 0.5

    lvl = b_hi if bull else b_lo
    beyond = (cur.close - lvl) if bull else (lvl - cur.close)

    return {
        "block_idx": block_idx,
        "break_idx": break_idx,
        "entry_idx": i,
        "block_to_break": break_idx - block_idx,
        "break_to_entry": i - break_idx,
        "retest": retest,
        "disp_ratio": None if disp_ratio == float("inf") else round(disp_ratio, 4),
        "left_level": q["clear_break"],
        "max_clear_pct": round(max_clear / cur.close * 100, 4) if cur.close else 0.0,
        "entry_body_ratio": None if entry_body_ratio == float("inf") else round(entry_body_ratio, 4),
        "entry_close_pos": round(close_pos, 4),
        "entry_dir_ok": q["_dir_ok"],
        "strong_pa": q["strong_pa"],
        "quick_engine": q["quick"],
        "beyond_level_pct": round(beyond / cur.close * 100, 4) if cur.close else 0.0,
        "et": cur.timestamp[:5],
    }


# ---------------------------------------------------------------------------
# stage 1
# ---------------------------------------------------------------------------

def stage1(limit=None):
    book = json.loads(BOOK.read_text())
    rows = [r for r in book["trades"] if r["setup"] == "one_candle_rule"]
    if limit:
        rows = rows[:limit]
    print("%d one_candle_rule detections in %s" % (len(rows), BOOK.name))

    by_day = defaultdict(list)
    for r in rows:
        by_day[(r["sym"], r["day"])].append(r)

    out, misses, n = [], 0, 0
    for (sym, day), rs in sorted(by_day.items()):
        try:
            rth = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            misses += len(rs)
            continue
        if len(rth) < 30:
            misses += len(rs)
            continue
        for r in rs:
            i = r["entry_i"]
            if i is None or i >= len(rth):
                misses += 1
                continue
            f = ocr_features(rth, i, "bullish" if r["dir"] == "call" else "bearish")
            if f is None:
                misses += 1
                continue
            if f["et"] != r["et"]:
                misses += 1
                continue
            f.update({"sym": sym, "day": day, "dir": r["dir"], "grade": r["grade"],
                      "status": r["status"], "traded": r["traded"], "r": r["r"],
                      "out": r["out"], "sgrade": r.get("sgrade"),
                      "stop_pct": r.get("stop_pct")})
            out.append(f)
        n += 1
        if n % 200 == 0:
            print("  %d sessions, %d rows" % (n, len(out)), flush=True)

    FEATS.write_text(json.dumps({"n_detections": len(rows), "n_replayed": len(out),
                                 "n_unreplayable": misses, "rows": out}))
    print("wrote %s: %d of %d detections replayed (%d unreplayable)"
          % (FEATS.name, len(out), len(rows), misses))


# ---------------------------------------------------------------------------
# the composite
# ---------------------------------------------------------------------------

def clauses(f, qb=QUICK_BLOCK_TO_BREAK, qe=QUICK_BREAK_TO_ENTRY,
            disp=DISPLACEMENT_MULT, pa=STRONG_PA_MULT):
    d = f["disp_ratio"]
    br = f["entry_body_ratio"]
    return {
        "clear_break": f["left_level"],
        "retest": f["retest"] in OB_RETEST_TYPES,
        "displacement": (d is None) or (d >= disp),
        "quick": f["block_to_break"] <= qb and f["break_to_entry"] <= qe,
        "strong_pa": f["entry_dir_ok"] and ((br is None) or (br >= pa)),
    }


def passes(f, **kw):
    return all(clauses(f, **kw).values())


def _stats(rows):
    tr = [r for r in rows if r["traded"]]
    rs = [r["r"] for r in tr]
    if not rs:
        return {"n": len(rows), "traded": 0, "mean_r": None, "win_rate": None}
    wins = sum(1 for x in rs if x > 0)
    return {"n": len(rows), "traded": len(rs),
            "mean_r": round(statistics.fmean(rs), 4),
            "win_rate": round(wins / len(rs) * 100, 2),
            "total_r": round(sum(rs), 2),
            "sd": round(statistics.pstdev(rs), 4) if len(rs) > 1 else 0.0,
            "err95": round(1.96 * statistics.pstdev(rs) / len(rs) ** 0.5, 4) if len(rs) > 1 else None}


def refusal_ids():
    """His 20 rare-lane verdicts: card_id -> (verdict, et).

    The ET matters: a symbol-day can carry several OCR detections and he graded
    exactly one of them (the chart card was drawn on that minute). Keying on
    sym+day alone silently scores a different detection than the one he refused.
    """
    out = {}
    for line in MARKS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("lane") == "rare":
            out[r["card_id"]] = (r["answers"]["real"][0], r["et"])
    return out


def report():
    data = json.loads(FEATS.read_text())
    rows = data["rows"]
    print("=" * 72)
    print("T2 -- OCR detector vs Austin's sentence")
    print("=" * 72)
    print("detections in book : %d" % data["n_detections"])
    print("replayed           : %d" % data["n_replayed"])
    print("unreplayable       : %d" % data["n_unreplayable"])
    print()

    # --- stage 2: reachability funnel ------------------------------------
    print("-- stage 2: per-clause pass rate over %d replayed detections" % len(rows))
    names = ["clear_break", "retest", "displacement", "quick", "strong_pa"]
    cl = [clauses(f) for f in rows]
    for k in names:
        n = sum(1 for c in cl if c[k])
        print("  %-14s %6d  %5.1f%%" % (k, n, n / len(rows) * 100))
    comp = [f for f, c in zip(rows, cl) if all(c.values())]
    print("  %-14s %6d  %5.1f%%   <- composite" % ("ALL", len(comp), len(comp) / len(rows) * 100))
    print()

    # cumulative funnel, in the order his sentence says them
    print("-- cumulative funnel (his order)")
    keep = rows
    for k in ["clear_break", "retest", "displacement", "quick", "strong_pa"]:
        keep = [f for f in keep if clauses(f)[k]]
        print("  after %-14s %6d  %5.1f%%" % (k, len(keep), len(keep) / len(rows) * 100))
    print()

    print("-- book effect on the OCR slice")
    print("  all detections   : %s" % _stats(rows))
    print("  passing composite: %s" % _stats(comp))
    sfail = _stats([f for f, c in zip(rows, cl) if not all(c.values())])
    spass = _stats(comp)
    print("  failing composite: %s" % sfail)
    if spass["traded"] > 1 and sfail["traded"] > 1:
        d = spass["mean_r"] - sfail["mean_r"]
        se = (spass["sd"] ** 2 / spass["traded"] + sfail["sd"] ** 2 / sfail["traded"]) ** 0.5
        print("  pass - fail: %+.4f R   95%% bar +/-%.4f R   -> %s"
              % (d, 1.96 * se,
                 "outside the bar" if abs(d) > 1.96 * se else "INSIDE the bar (null)"))
    print()

    # --- stage 3: his 20 refusals ----------------------------------------
    print("-- stage 3: validation on his 20 refusals (0 of 20 are real)")
    ref = refusal_ids()
    # keyed on sym_day_ET -- the exact detection his chart card was drawn on
    by_key = {"%s_%s_%s" % (f["sym"], f["day"], f["et"]): f for f in rows}
    by_id = {}
    for cid, (verdict, et) in ref.items():
        f = by_key.get("%s_%s" % (cid, et))
        if f is not None:
            by_id[cid] = f
    survives = miss = 0
    for cid, (verdict, et) in ref.items():
        f = by_id.get(cid)
        if f is None:
            print("  %-22s %-5s %s  NOT REPLAYED" % (cid, verdict, et))
            miss += 1
            continue
        c = clauses(f)
        ok = all(c.values())
        fails = [k for k in names if not c[k]]
        print("  %-22s %-5s %s  %s   %s%s"
              % (cid, verdict, et, "SURVIVES" if ok else "rejected",
                 ",".join(fails) or "-",
                 "   [TRADED in the shipped book]" if f["traded"] else ""))
        survives += 1 if ok else 0
    n_rep = len(ref) - miss
    print("  rejected %d of %d replayed refusals (%d survive, %d not replayable)"
          % (n_rep - survives, n_rep, survives, miss))
    print("  of his 20, still TRADED in the shipped (OCR_STRICT off) book: %d"
          % sum(1 for cid in by_id if by_id[cid]["traded"]))
    print()

    # --- stage 4: the quick sweep ----------------------------------------
    print("-- stage 4: 'quick' has no number in his sentence -- sweep it")
    print("  qb  qe    pass    pass%   refusals_kept   traded  mean_r  win%")
    for qb in (3, 4, 6, 8, 12, 999):
        for qe in (3, 5, 10, 20, 999):
            p = [f for f in rows if passes(f, qb=qb, qe=qe)]
            kept = sum(1 for cid in ref if cid in by_id and passes(by_id[cid], qb=qb, qe=qe))
            s = _stats(p)
            print("  %-3s %-4s %6d  %5.1f%%   %2d of %2d        %5s  %6s  %5s"
                  % (qb, qe, len(p), len(p) / len(rows) * 100, kept,
                     sum(1 for cid in ref if cid in by_id),
                     s["traded"], s["mean_r"], s["win_rate"]))
    print()

    print("-- displacement multiple sweep (gate is %.1fx today)" % DISPLACEMENT_MULT)
    for d in (1.5, 2.0, 2.5, 3.0, 4.0):
        p = [f for f in rows if passes(f, disp=d)]
        kept = sum(1 for cid in ref if cid in by_id and passes(by_id[cid], disp=d))
        s = _stats(p)
        print("  %.1fx  %6d  %5.1f%%   refusals kept %2d   traded %s  mean_r %s  win %s"
              % (d, len(p), len(p) / len(rows) * 100, kept, s["traded"],
                 s["mean_r"], s["win_rate"]))
    print()

    print("-- strong-PA is the binding clause: break it into its two parts")
    n = len(rows)
    dir_ok = [f for f in rows if f["entry_dir_ok"]]
    print("  entry candle in the trade's direction : %d  %5.1f%%" % (len(dir_ok), len(dir_ok) / n * 100))
    br = [f["entry_body_ratio"] for f in rows if f["entry_body_ratio"] is not None]
    br.sort()
    print("  entry body / prior-10 avg body, deciles: %s"
          % [round(br[int(len(br) * q / 10)], 2) for q in range(1, 10)])
    print("  strong-PA multiple sweep (engine's own constant is %.1fx):" % STRONG_PA_MULT)
    print("   mult    pass    pass%   refusals_kept   traded  mean_r  win%")
    for m in (0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0):
        p = [f for f in rows if passes(f, pa=m)]
        kept = sum(1 for cid in ref if cid in by_id and passes(by_id[cid], pa=m))
        s = _stats(p)
        print("  %5.2f  %6d  %5.1f%%   %2d of %2d        %5s  %6s  %5s"
              % (m, len(p), len(p) / n * 100, kept,
                 sum(1 for cid in ref if cid in by_id), s["traded"], s["mean_r"], s["win_rate"]))
    print()

    print("-- 'being early' (reported, not gated)")
    et = Counter(f["et"][:2] for f in rows)
    print("  detections by hour: %s" % dict(sorted(et.items())))
    print("  median beyond-level %% : %.4f" % statistics.median(f["beyond_level_pct"] for f in rows))
    print("  median block->break bars: %d ; median break->entry bars: %d"
          % (statistics.median(f["block_to_break"] for f in rows),
             statistics.median(f["break_to_entry"] for f in rows)))


# ---------------------------------------------------------------------------
# stage 5 -- the whole book, OCR_STRICT off vs on
# ---------------------------------------------------------------------------

def _book(path):
    return json.loads(Path(path).read_text())


def _book_stats(b):
    tr = [r for r in b["trades"] if r["traded"]]
    rs = [r["r"] for r in tr]
    by_m = defaultdict(float)
    for r in tr:
        by_m[r["ym"]] += r["r"]
    wins = [x for x in rs if x > 0]
    losses = [x for x in rs if x < 0]
    gp, gl = sum(wins), -sum(losses)
    eq, peak, dd = 0.0, 0.0, 0.0
    for r in sorted(tr, key=lambda x: (x["day"], x["et"])):
        eq += r["r"]
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    setups = Counter(r["setup"] for r in b["trades"])
    tsetups = Counter(r["setup"] for r in tr)
    return {
        "signals": len(b["trades"]),
        "traded": len(rs),
        "mean_r": round(statistics.fmean(rs), 4),
        "sd": round(statistics.pstdev(rs), 4),
        "err95": round(1.96 * statistics.pstdev(rs) / len(rs) ** 0.5, 4),
        "win_rate": round(len(wins) / len(rs) * 100, 2),
        "total_r": round(sum(rs), 2),
        "pf": round(gp / gl, 4) if gl else None,
        "max_dd_r": round(dd, 2),
        "months_green": "%d/%d" % (sum(1 for v in by_m.values() if v > 0), len(by_m)),
        "worst_month": round(min(by_m.values()), 2),
        "detections": dict(setups),
        "traded_by_setup": dict(tsetups),
    }


def compare(before_path, after_path):
    a, b = _book(before_path), _book(after_path)
    sa, sb = _book_stats(a), _book_stats(b)
    print("=" * 72)
    print("T2 stage 5 -- the whole book, OCR_STRICT off vs on")
    print("  OFF: %s" % before_path)
    print("  ON : %s" % after_path)
    print("=" * 72)
    keys = ["signals", "traded", "mean_r", "win_rate", "total_r", "pf",
            "max_dd_r", "months_green", "worst_month"]
    print("%-16s %14s %14s" % ("figure", "OFF", "ON"))
    for k in keys:
        print("%-16s %14s %14s" % (k, sa[k], sb[k]))
    print()
    for k in ("detections", "traded_by_setup"):
        print("%s:" % k)
        for s in sorted(set(sa[k]) | set(sb[k])):
            print("  %-18s %8s -> %8s" % (s, sa[k].get(s, 0), sb[k].get(s, 0)))
    print()
    d = sb["mean_r"] - sa["mean_r"]
    se = (sa["sd"] ** 2 / sa["traded"] + sb["sd"] ** 2 / sb["traded"]) ** 0.5
    bar95 = 1.96 * se
    print("mean R move: %+.4f R   95%% bar on the move: +/-%.4f R   -> %s"
          % (d, bar95, "OUTSIDE the bar" if abs(d) > bar95 else "INSIDE the bar (NULL RESULT)"))
    return sa, sb, d, bar95


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stage1", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--compare", nargs=2, metavar=("OFF_BOOK", "ON_BOOK"))
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if a.stage1:
        stage1(a.limit)
    if a.compare:
        compare(*a.compare)
    if a.report or not (a.stage1 or a.compare):
        report()
