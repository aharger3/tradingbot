"""g154 -- F5: "stop-placement-routed" (S-indicator), the routed stop.

Austin's words: "The stop is a choice among structure candidates -- entry-candle
extreme, OCR wick, or the broken level / pivot structure -- picked per trade for
the best tradable risk; where they disagree and risk is tight he takes the wick,
not the level."

`signal_runner.py::placed_stop` already names this exact taxonomy as its
"routed" STOP_PLACEMENT arm (line ~1612): one_candle_rule -> the OCR block's
own wick, break_and_retest -> the broken level. This script recomputes that
SAME routing from `data_archive` for the book's own signal bars, without an
engine re-run:

  * one_candle_rule  -> the OCR (order-block) candle's far wick, found by
    `omen_bot.detect_order_block_setup` on bars[<= entry_i] -- the SAME
    detector call `signal_runner.ocr_far_edge` makes, not a second reading of
    "the OCR candle". No block found (or the candidate wick sits on the wrong
    side of the close) -> falls back to the shipped structural stop, exactly
    as `placed_stop` does.
  * break_and_retest -> `r["level_px"]`, the broken level/pivot itself.
  * reentry_84_rule (the third setup in this book) -> unchanged. `placed_stop`
    itself only routes those two; everything else returns the caller's own
    structural stop, and so does this arm.

RISK AND THE GATE. risk_new = |entry - routed_stop|, re-gated on
`signal_runner.min_risk_floor(entry)` (the book's fill IS the bar close, so
`entry` doubles as `close` the way `omen_metrics._row_is_sizeable` already
reads it). A day whose first candidate's routed stop collapses the risk below
the floor falls through to the next candidate that day, same mechanism
`omen_metrics.first_of_day_arm` already uses for the size gate.

REPLAY. Only the STOP moves; the target is untouched. Because
`DISASTER_STOP_R == 1.0` (CLAUDE.md, R1/R2), the resting disaster order sits
exactly `risk_new` from entry -- i.e. exactly ON the routed stop -- and it
fills on an intrabar TOUCH, tested before the close-only level trigger on
every bar (`stop_rule.disaster_stop_hit` first, `stop_rule.stop_hit_on_close`
+ `stop_rule.stop_fill_price` as the close-only fallback, which cannot
actually fire ahead of the touch on continuous OHLC data -- documented, not
special-cased away, matching `backtest_week._stop_fill_px`'s own comment that
the close branch is a no-op under the original stop). The target is a
resting limit, fills on a touch. Whichever the walk from entry_i+1 to the end
of that RTH session touches first wins; a stop-touch and a target-touch on the
SAME bar resolve to the stop (conservative). A day that touches neither by
session end keeps the book's ORIGINAL exit (fewer than 1% of rows in the
shipped book are these "neither" outcomes; scratch or timeout dispositions
are not being re-derived here). A day whose bars cannot be read from
data_archive (a Polygon gap) also keeps the original row unchanged -- no
fabricated numbers.

`stop_disagree = |routed - r["stop"]| / |entry - r["stop"]|` is reported as a
descriptive distribution (mean/median), split by whether the ORIGINAL risk
was "tight" (<= 2x min_risk_floor(entry)) -- the wick-vs-level tie-break
Austin names -- not gated on.

Unit: research/omen_metrics.first_of_day_arm (one trade a day, arrival
order across ALL symbols, size-gated). Same unit as
research/g86_honest_ceiling.py and research/g91_lane_slice.py.

    python research/g154_rule_stop-placement-routed.py

Writes research/g154_rule_stop-placement-routed.{json,md}.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import polygon_feed as pf                                   # noqa: E402  cache-only bar reads
from omen_bot import detect_order_block_setup                # noqa: E402  the engine's own OCR detector
from signal_runner import min_risk_floor                     # noqa: E402  the one floor
from stop_rule import (disaster_stop_price, disaster_stop_hit,  # noqa: E402
                       stop_hit_on_close, stop_fill_price, DISASTER_STOP_R)
from omen_metrics import _row_is_sizeable                     # noqa: E402
import marks_pool                                              # noqa: E402

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")
SWEEP_PATH = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT_JSON = os.path.join(HERE, "g154_rule_stop-placement-routed.json")
OUT_MD = os.path.join(HERE, "g154_rule_stop-placement-routed.md")

RISK = 1000.0
H_SPLIT = "2025-09-01"
TIGHT_MULT = 2.0   # "risk is tight" descriptive cutoff: <= 2x the floor

_bars_cache = {}


def get_bars(sym, day):
    k = (sym, day)
    if k not in _bars_cache:
        try:
            _bars_cache[k] = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            _bars_cache[k] = []
    return _bars_cache[k]


# --------------------------------------------------------------- routed stop

def ocr_wick(bars, entry_i, is_long):
    """The OCR block's far wick, computed on bars[<= entry_i] only -- the
    identical call `signal_runner.ocr_far_edge` makes. None if no block."""
    if entry_i is None or entry_i < 0 or entry_i >= len(bars):
        return None
    prefix = bars[:entry_i + 1]
    try:
        block, _retest, _note = detect_order_block_setup(
            prefix, "bullish" if is_long else "bearish")
    except Exception:
        return None
    if block is None:
        return None
    return block.low if is_long else block.high


def routed_stop_for(row):
    """(routed_stop, source) for one book row, or (row['stop'], 'unchanged')
    when the setup isn't one of the two `placed_stop` routes, no candidate
    was found, or the candidate sits on the wrong side of the close (mirrors
    `signal_runner.placed_stop`'s own fallback to the structural stop)."""
    setup = row.get("setup")
    entry = row["entry"]
    structural = row["stop"]
    is_long = row["dir"] == "call"

    if setup == "break_and_retest":
        cand = row.get("level_px")
        source = "broken_level"
    elif setup == "one_candle_rule":
        bars = get_bars(row["sym"], row["day"])
        cand = ocr_wick(bars, row.get("entry_i"), is_long)
        source = "ocr_wick"
    else:
        return structural, "unchanged"

    if cand is None:
        return structural, "unchanged (no candidate)"
    # A candidate stop that isn't on the losing side of the close isn't a
    # stop -- it would size a trade at negative risk.
    if (cand >= entry) if is_long else (cand <= entry):
        return structural, "unchanged (wrong side of close)"
    return cand, source


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


# --------------------------------------------------------------- replay

def replay_routed(row, routed_stop):
    """Re-derive pnl/r under `routed_stop`, target unchanged. Walks bars from
    entry_i+1 to the end of the RTH session. Returns a new row (copy) with
    stop/exit/pnl/r updated, or None if bars can't be read (caller keeps the
    original row unchanged in that case)."""
    bars = get_bars(row["sym"], row["day"])
    entry_i = row.get("entry_i")
    if not bars or entry_i is None or entry_i + 1 > len(bars):
        return None
    is_long = row["dir"] == "call"
    entry = row["entry"]
    target = row["target"]
    risk_new = abs(entry - routed_stop)
    if risk_new <= 0:
        return None

    for b in bars[entry_i + 1:]:
        dpx = disaster_stop_price(entry, risk_new, is_long, DISASTER_STOP_R)
        if disaster_stop_hit(b.high, b.low, dpx, is_long):
            exit_px = dpx
            r_mult = (exit_px - entry) / risk_new if is_long else (entry - exit_px) / risk_new
            out = "loss" if r_mult < 0 else ("win" if r_mult > 0 else "scratch")
            new = dict(row)
            new["stop"], new["exit"], new["out"] = routed_stop, round(exit_px, 4), out
            new["pnl"], new["r"] = round(r_mult * RISK, 2), round(r_mult, 4)
            return new
        # Close-only fallback -- documented as a no-op on continuous OHLC data
        # (a close beyond the stop implies the same bar's wick already
        # touched it), kept so the replay names `stop_rule.stop_fill_price`
        # rather than silently assuming the touch check is exhaustive.
        if stop_hit_on_close(b.close, routed_stop, is_long):
            exit_px = stop_fill_price(b.close, entry, risk_new, is_long, DISASTER_STOP_R)
            r_mult = (exit_px - entry) / risk_new if is_long else (entry - exit_px) / risk_new
            new = dict(row)
            new["stop"], new["exit"], new["out"] = routed_stop, round(exit_px, 4), "loss"
            new["pnl"], new["r"] = round(r_mult * RISK, 2), round(r_mult, 4)
            return new
        touched_target = (b.high >= target) if is_long else (b.low <= target)
        if touched_target:
            r_mult = (target - entry) / risk_new if is_long else (entry - target) / risk_new
            new = dict(row)
            new["stop"], new["exit"], new["out"] = routed_stop, round(target, 4), "win"
            new["pnl"], new["r"] = round(r_mult * RISK, 2), round(r_mult, 4)
            return new
    return None  # touched neither by session end -- caller keeps the original row


def build_routed_book(byday):
    """{day: [rows]} with every candidate's stop routed and exit replayed.
    A row that cannot be recomputed (unreadable bars, or neither touched)
    keeps its ORIGINAL entry/stop/exit/pnl -- no fabricated numbers."""
    out = defaultdict(list)
    disagree_all, disagree_tight = [], []
    routed_counts = defaultdict(int)
    for day in sorted(byday):
        for r in byday[day]:
            routed, source = routed_stop_for(r)
            routed_counts[source] += 1
            orig_risk = abs(r["entry"] - r["stop"])
            if orig_risk > 0:
                dis = abs(routed - r["stop"]) / orig_risk
                disagree_all.append(dis)
                if orig_risk <= TIGHT_MULT * min_risk_floor(r["entry"]):
                    disagree_tight.append(dis)
            if source == "unchanged" or source.startswith("unchanged"):
                out[day].append(r)
                continue
            new = replay_routed(r, routed)
            out[day].append(new if new is not None else r)
    return out, routed_counts, disagree_all, disagree_tight


def pick_first_of_day(byday):
    """First-of-day, size-gated on the ROUTED risk (entry/stop already
    reflect the routed stop from build_routed_book). Mirrors
    omen_metrics.first_of_day_arm's pick-then-gate fix: the gate runs INSIDE
    selection so a dropped/unsizeable first candidate falls through to the
    next one on the same day, never skips the day."""
    firsts = []
    for day in sorted(byday):
        v = byday[day]
        pick = next((r for r in v if _row_is_sizeable(r) is not False), None)
        if pick is not None:
            firsts.append(pick)
    return firsts


# --------------------------------------------------------------------- scoring

def iso_week(day):
    y, w, _ = date.fromisoformat(day).isocalendar()
    return "%04d-W%02d" % (y, w)


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
    import grade_read
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


def measure(firsts, n_days_total, s_pairs_100, all_s_pairs, pool):
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
    cand_per_day = round(sum(len(v) for v in byday.values()) / n_days_total, 2)

    s_pairs_100 = load_sweep_s_days()
    pool = marks_pool.canonical_pool()
    all_s_pairs = []
    for k in marks_pool.s_days(pool):
        sym, day = k.split("_", 1)
        all_s_pairs.append((sym, day))

    baseline_firsts = pick_first_of_day(byday)
    baseline = measure(baseline_firsts, n_days_total, s_pairs_100, all_s_pairs, pool)

    routed_byday, routed_counts, disagree_all, disagree_tight = build_routed_book(byday)
    candidate_firsts = pick_first_of_day(routed_byday)
    candidate = measure(candidate_firsts, n_days_total, s_pairs_100, all_s_pairs, pool)

    h1_delta_usd = candidate["H1"]["usd_day"] - baseline["H1"]["usd_day"]
    h2_delta_usd = candidate["H2"]["usd_day"] - baseline["H2"]["usd_day"]
    usd_improves = h1_delta_usd > 0 and h2_delta_usd > 0
    prec_improves = candidate["precision"]["pct"] > baseline["precision"]["pct"]
    recall_ok = candidate["s_recall_100"]["pct"] >= baseline["s_recall_100"]["pct"]
    survivor = bool((usd_improves or prec_improves) and recall_ok)

    def dstats(vals):
        if not vals:
            return {"n": 0, "mean": None, "median": None}
        return {"n": len(vals), "mean": round(statistics.fmean(vals), 4),
                "median": round(statistics.median(vals), 4)}

    out = {
        "row": "F5",
        "slug": "stop-placement-routed",
        "predicate": "one_candle_rule -> OCR block wick (detect_order_block_setup on "
                     "bars[<=entry_i]); break_and_retest -> level_px; else unchanged. "
                     "risk = |entry - routed_stop|, gated on min_risk_floor(entry). "
                     "Exits replayed via stop_rule (disaster touch at DISASTER_STOP_R, "
                     "close fallback via stop_fill_price); target unchanged.",
        "polarity": "S-indicator",
        "n_days_total": n_days_total,
        "candidates_per_day": cand_per_day,
        "routed_source_counts": dict(routed_counts),
        "stop_disagree": {
            "all_candidates": dstats(disagree_all),
            "tight_risk_only": dstats(disagree_tight),
            "tight_definition": "original risk <= %sx min_risk_floor(entry)" % TIGHT_MULT,
        },
        "baseline": baseline,
        "candidate": candidate,
        "h1_delta_usd_day": round(h1_delta_usd, 2),
        "h2_delta_usd_day": round(h2_delta_usd, 2),
        "survivor": survivor,
        "notes": ("survivor = True only if (H1 AND H2 both improve $/day, OR "
                  "precision improves) AND S-recall-100 does not fall below "
                  "baseline. `routed_source_counts` shows how many candidates "
                  "actually got a routed stop vs fell back unchanged (no OCR "
                  "block found / wrong side of close / reentry_84_rule setup) "
                  "-- a rule can be real and still rarely trip on this book."),
    }

    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=2)
    write_md(out)
    print(json.dumps(out, indent=2))
    return out


def _fmt_row(label, d):
    o = d["overall"]
    return ("| %s | %d | $%s | %s | %s%% | %s/%s | $%s |" %
            (label, o["n"], o["usd_day"], o["mean_r"], o["win_pct"],
             o["green_months"], o["months"], o["max_dd"]))


def write_md(out):
    lines = []
    lines.append("# g154 -- F5 stop-placement-routed\n")
    lines.append("**What is different now:** recomputed the stop per Austin's "
                 "structure taxonomy (OCR wick for one_candle_rule, broken level "
                 "for break_and_retest) from data_archive, size-gated the "
                 "result, and replayed exits against the one-trade-a-day book.\n")
    for label, d in (("baseline (shipped entry_bar stop)", out["baseline"]),
                     ("candidate (routed stop)", out["candidate"])):
        lines.append("## %s\n" % label)
        lines.append("| pop | n | $/day | mean R | win | green/mo | max DD |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        lines.append(_fmt_row("overall", d))
        lines.append(_fmt_row("H1", {"overall": d["H1"]}))
        lines.append(_fmt_row("H2", {"overall": d["H2"]}))
        lines.append("")
        lines.append("candidates/day: %s -- fires/day: %s" %
                      (out["candidates_per_day"], d["fires_per_day"]))
        lines.append("S recall (100-card deck, 34 S): %s%% (%d/%d)" %
                      (d["s_recall_100"]["pct"], d["s_recall_100"]["hit"],
                       d["s_recall_100"]["n"]))
        lines.append("S recall (all bar-backed S days): %s%% (%d/%d)" %
                      (d["s_recall_all_bar_backed"]["pct"],
                       d["s_recall_all_bar_backed"]["hit"],
                       d["s_recall_all_bar_backed"]["n"]))
        lines.append("precision (fired-day graded S / fired-day graded any): "
                     "%s%% (%d/%d)\n" % (d["precision"]["pct"],
                                        d["precision"]["graded_s"],
                                        d["precision"]["graded_any"]))

    lines.append("## Routed-source counts (all candidates, not just first-of-day)\n")
    for k, v in out["routed_source_counts"].items():
        lines.append("- %s: %d" % (k, v))
    lines.append("")

    lines.append("## stop_disagree = |routed - shipped_stop| / |entry - shipped_stop|\n")
    a, t = out["stop_disagree"]["all_candidates"], out["stop_disagree"]["tight_risk_only"]
    lines.append("all candidates: n=%s mean=%s median=%s" % (a["n"], a["mean"], a["median"]))
    lines.append("tight-risk only (%s): n=%s mean=%s median=%s\n" %
                  (out["stop_disagree"]["tight_definition"], t["n"], t["mean"], t["median"]))

    lines.append("## Survivor verdict\n")
    lines.append("H1 delta $/day: %s -- H2 delta $/day: %s" %
                  (out["h1_delta_usd_day"], out["h2_delta_usd_day"]))
    lines.append("**survivor = %s**\n" % out["survivor"])
    lines.append(out["notes"])
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
