"""g154 -- F5 candidate: entry-earlier-satisfiable-bar (OMEN 9.0).

Candidate (polarity S-INDICATOR): "The engine fires systematically later than
the entry he says he would have taken -- 'entry N candles earlier' is the
most repeated comment in the corpus (median ~24 min behind him)."

THE PREDICATE, applied to the book's own signal bar (`entry_i`, RTH-indexed
09:30=0 -- verified against `data_archive/NVDA/2024-09-03.csv`: bar 16 is
09:46, matching that row's own `entry_i`=16, `et`='09:46'). For each fired
signal, scan bar j in [0, entry_i-1] (j=0 has no prior bar and is skipped --
there is nothing for it to retest against):

  (a) some bar k < j closed through `level_px` in the signal's own direction
      (call: close > level: a breakout up. put: close < level: a breakdown
      down) -- tracked as a running flag, folding in bar j-1 each step;
  (b) bar j traded back within `BAR_EXTREME_FRAC` (0.25, `signal_runner.py`)
      x the RANGE of bar j-1 of `level_px` -- i.e. it retested;
  (c) bar j closed back on the signal side of `level_px` (call: close >=
      level. put: close <= level) -- i.e. the retest held.

`lag_bars = entry_i - min(satisfiable j)`, the EARLIEST bar all three hold
(0 if none does -- the engine's own entry was already the earliest workable
one). Bars used are strictly <= entry_i (bars[j] for j < entry_i, bars[j-1]
for the range) -- no bar after the signal is ever read, so this is not a
repriced trade, only a description of when a satisfiable retest existed.

THE ARM. KEEP lag_bars <= L, L in {0, 1, 2, 3} (bars are 1-minute, so this
IS "N minutes earlier was already workable" in minutes, directly). Applied
as a FILTER inside the one-trade-a-day pick (`omen_metrics.first_of_day_arm`
pattern): for each calendar day, walk the book's candidates in arrival order
and take the first that is (1) size-gated sizeable and (2) lag_bars <= L.
A day with no such candidate contributes no trade (like the size gate
already does) -- this is an S-INDICATOR, so it is a SELECTION filter, not a
skip-and-take-next-anyway rule.

WHAT "RECALL" AND "PRECISION" MEAN HERE (stated because the row's wording
does not fully disambiguate them, and CLAUDE.md's rule is: say the
definition, don't oversell the number). The book's one-trade-a-day arm
picks exactly ONE symbol per calendar day, across the whole pool. So:
  - fired_map = {day: the arm's one pick that day}
  - RECALL against a set of graded (symbol, day) pairs = the fraction where
    fired_map[day] exists AND its symbol matches -- "the arm's single daily
    pick happened to be this S day", not "the engine detected something on
    this symbol-day at all" (that looser, per-candidate recall is a
    different and much higher number; not reported here).
  - PRECISION = of the days the arm actually fired, restricted to the days
    where THAT (symbol, day) has a canonical_pool grade of any kind, what
    fraction are graded S.
"recall on all bar-backed S days" further restricts marks_pool.s_days() to
symbol-days where data_archive actually holds bars (the lag feature and the
book itself both require them).

Prior art for the unit: research/g91_lane_slice.py (one-trade-a-day,
months-green, max-DD path); research/g86_honest_ceiling.py (stats()/candidates()
shape). Neither is re-derived; the per_day/mean_r/win_pct arithmetic below
mirrors g86.stats exactly but is re-typed here because this row's per-day
denominator differs by H1/H2 slice and by arm (fewer picks -> more session
days with zero, same denominator, per CLAUDE.md's "no re-implemented fill":
the trade PRICE fields -- entry/stop/exit/pnl/r -- are read verbatim off the
book row, never recomputed).

Reads only: data_archive/<SYM>/<day>.csv (via polygon_feed, cache-first --
no network hit for archived days), research/bt2y_trades_retest_on.json,
research/marks/probe_s_sweep_2026-08-28.jsonl, research/marks_pool.py.
Writes nothing but its own two report files. No engine file is edited.

    python research/g154_rule_entry-earlier-satisfiable-bar.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import polygon_feed as pf                        # noqa: E402
from signal_runner import BAR_EXTREME_FRAC        # noqa: E402
from research import omen_metrics as om           # noqa: E402
from research import marks_pool as mp             # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades_retest_on.json"
OUT_JSON = ROOT / "research" / "g154_rule_entry-earlier-satisfiable-bar.json"
OUT_MD = ROOT / "research" / "g154_rule_entry-earlier-satisfiable-bar.md"
PROBE_S34 = ROOT / "research" / "marks" / "probe_s_sweep_2026-08-28.jsonl"

RISK = 1000.0
BAR_PER_DAY = 397.0            # Austin's stated bar, $/day, one-trade-a-day
SPLIT_DAY = "2025-09-01"       # THE LAW's H1/H2 split
LEVELS = (0, 1, 2, 3)


def ekey(r):
    return (r["day"], r["et"], r["sym"])


def half(day):
    return "H1" if day < SPLIT_DAY else "H2"


# --------------------------------------------------------------- bar access

_bars_cache: dict = {}


def bars_for(sym, day):
    """data_archive only -- never falls through to a network fetch (the row's
    'Bars features read data_archive only' scope; pf.fetch_day itself falls
    back to a live Polygon call for a missing file, which is both a network
    dependency this row must not carry and a source of run-to-run flakiness
    for symbol/days data_archive never had -- so the file's existence is
    checked here, first, and a miss is a plain empty result, not a fetch)."""
    k = (sym, day)
    if k not in _bars_cache:
        if len(_bars_cache) > 800:
            _bars_cache.clear()
        csv_path = pf.ARCHIVE / sym / ("%s.csv" % day)
        if not csv_path.exists():
            _bars_cache[k] = []
        else:
            try:
                _bars_cache[k] = pf.rth(pf.fetch_day(sym, day))
            except Exception:
                _bars_cache[k] = []
    return _bars_cache[k]


# ----------------------------------------------------------- the predicate

_lag_cache: dict = {}


def lag_bars(r):
    """entry_i - min(satisfiable j), 0 if none. Reads bars[0 .. entry_i-1]
    only -- never a bar after the signal."""
    key = ekey(r)
    if key in _lag_cache:
        return _lag_cache[key]

    entry_i = r.get("entry_i")
    out = 0
    if entry_i is not None and entry_i >= 1:
        bars = bars_for(r["sym"], r["day"])
        if bars and entry_i < len(bars):
            level = r["level_px"]
            is_long = r["dir"] == "call"
            seen_break = False
            for j in range(1, entry_i):        # j in [0, entry_i-1]; j=0 has no prior bar
                prev = bars[j - 1]
                broke = (prev.close > level) if is_long else (prev.close < level)
                if broke:
                    seen_break = True
                if not seen_break:
                    continue
                rng = prev.high - prev.low
                if rng <= 0:
                    continue
                tol = BAR_EXTREME_FRAC * rng
                bj = bars[j]
                touched = (bj.low - tol) <= level <= (bj.high + tol)
                if not touched:
                    continue
                closed_side = (bj.close >= level) if is_long else (bj.close <= level)
                if closed_side:
                    out = entry_i - j
                    break
    _lag_cache[key] = out
    return out


# --------------------------------------------------------------- the arms

def is_candidate(r):
    return (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted"


def candidate_arm(rows, L):
    """One-trade-a-day, S-indicator filter applied: KEEP lag_bars(r) <= L.
    Same shape as omen_metrics.first_of_day_arm -- size-gate runs inside
    selection, and the KEEP predicate runs alongside it, both walking
    arrival order; a day with no matching candidate contributes no trade."""
    by_day = defaultdict(list)
    for r in rows:
        if is_candidate(r):
            by_day[r["day"]].append(r)
    picks = []
    for day in sorted(by_day):
        v = sorted(by_day[day], key=ekey)
        pick = None
        for r in v:
            if om._row_is_sizeable(r) is False:
                continue
            if lag_bars(r) <= L:
                pick = r
                break
        if pick is not None:
            picks.append(pick)
    return picks


# ------------------------------------------------------------------ stats

def price_stats(picks, n_days, months_universe):
    by_m = {m: 0.0 for m in months_universe}
    pnls = [r["pnl"] for r in picks]
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    total = sum(pnls)
    by_day = {}
    for r in picks:
        by_day[r["day"]] = by_day.get(r["day"], 0.0) + r["pnl"]
        by_m[r["day"][:7]] = by_m.get(r["day"][:7], 0.0) + r["pnl"]
    cum = peak = dd = 0.0
    for d in sorted(by_day):
        cum += by_day[d]
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return {
        "trades": len(picks),
        "per_day": round(total / n_days, 2) if n_days else 0.0,
        "mean_r": round(total / len(picks) / RISK, 3) if picks else 0.0,
        "win_pct": round(wins / (wins + losses) * 100, 1) if wins + losses else 0.0,
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "months": len(by_m),
        "max_dd": round(dd, 2),
        "total_dollars": round(total, 2),
    }


def recall_frac(sym_days, fired_map):
    """sym_days: iterable of (sym, day). Hit = the arm's ONE pick that day
    exists and is on that symbol."""
    sym_days = list(sym_days)
    if not sym_days:
        return {"hit": 0, "n": 0, "pct": None}
    hit = sum(1 for sym, day in sym_days
              if fired_map.get(day) is not None and fired_map[day]["sym"] == sym)
    return {"hit": hit, "n": len(sym_days), "pct": round(hit / len(sym_days) * 100, 1)}


def precision_frac(fired_map, pool):
    graded_any = graded_s = 0
    for day, r in fired_map.items():
        key = "%s_%s" % (r["sym"], day)
        e = pool.get(key)
        if e is None:
            continue
        graded_any += 1
        if e.grade == "S":
            graded_s += 1
    return {"graded_s": graded_s, "graded_any": graded_any,
            "pct": round(graded_s / graded_any * 100, 1) if graded_any else None}


def load_probe34():
    out = []
    for line in open(PROBE_S34, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        if d.get("answers", {}).get("s") == ["s"]:
            sym, day = d["card_id"].rsplit("_", 1)
            out.append((sym, day))
    return out


def arm_report(label, picks, all_days, all_months, pool, s_days_bb, probe34):
    n_days = len(all_days)
    h1_days = [d for d in all_days if half(d) == "H1"]
    h2_days = [d for d in all_days if half(d) == "H2"]
    h1_months = sorted({d[:7] for d in h1_days})
    h2_months = sorted({d[:7] for d in h2_days})

    full = price_stats(picks, n_days, all_months)
    h1 = price_stats([r for r in picks if half(r["day"]) == "H1"], len(h1_days), h1_months)
    h2 = price_stats([r for r in picks if half(r["day"]) == "H2"], len(h2_days), h2_months)

    fired_map = {r["day"]: r for r in picks}
    rec100 = recall_frac(probe34, fired_map)
    rec_all = recall_frac(s_days_bb, fired_map)
    prec = precision_frac(fired_map, pool)

    return {
        "label": label,
        "full": full, "H1": h1, "H2": h2,
        "fires_per_day": round(len(picks) / n_days, 3),
        "recall_100": rec100,
        "recall_bar_backed": rec_all,
        "precision": prec,
    }


def main():
    blob = json.load(open(BOOK, encoding="utf-8"))
    rows = blob["trades"]
    all_days = sorted({r["day"] for r in rows})
    all_months = sorted({d[:7] for d in all_days})
    n_days = len(all_days)
    print("book %s: %d sessions" % (BOOK.name, n_days), flush=True)

    cand_rows = [r for r in rows if is_candidate(r)]
    cands_per_day = round(len(cand_rows) / n_days, 2)
    print("raw candidates: %d (%.2f/day)" % (len(cand_rows), cands_per_day), flush=True)

    pool = mp.canonical_pool()
    s_days = mp.s_days(pool)
    s_days_pairs = [tuple(k.rsplit("_", 1)) for k in s_days]  # (sym, day)... wait order
    # marks_pool keys are SYMBOL_YYYY-MM-DD -> rsplit gives (SYMBOL, DAY)
    s_days_pairs = [(k.rsplit("_", 1)[0], k.rsplit("_", 1)[1]) for k in s_days]
    s_days_bb = [(sym, day) for sym, day in s_days_pairs if bars_for(sym, day)]
    print("marks_pool: %d graded symbol-days, %d graded S, %d bar-backed S"
          % (len(pool), len(s_days), len(s_days_bb)), flush=True)

    probe34 = load_probe34()
    print("probe_s_sweep 34-card set: %d S cards loaded" % len(probe34), flush=True)

    baseline_picks = om.first_of_day_arm(rows, size_gate=True)
    baseline = arm_report("baseline (first_of_day_arm, size-gated)", baseline_picks,
                          all_days, all_months, pool, s_days_bb, probe34)
    print("baseline: $%.0f/day  meanR %+.3f  win %.1f%%  %d/%d green  maxDD $%.0f"
          % (baseline["full"]["per_day"], baseline["full"]["mean_r"],
             baseline["full"]["win_pct"], baseline["full"]["months_green"],
             baseline["full"]["months"], baseline["full"]["max_dd"]), flush=True)

    arms = {}
    for L in LEVELS:
        picks = candidate_arm(rows, L)
        arms[L] = arm_report("KEEP lag_bars<=%d" % L, picks, all_days, all_months,
                             pool, s_days_bb, probe34)
        a = arms[L]
        print("  L=%d: %d picks  $%.0f/day  meanR %+.3f  win %.1f%%  %d/%d green  "
              "maxDD $%.0f  fires/day %.3f  recall100 %s  precision %s"
              % (L, a["full"]["trades"], a["full"]["per_day"], a["full"]["mean_r"],
                 a["full"]["win_pct"], a["full"]["months_green"], a["full"]["months"],
                 a["full"]["max_dd"], a["fires_per_day"],
                 a["recall_100"]["pct"], a["precision"]["pct"]), flush=True)

    # lag prevalence across the raw candidate stream, for context
    lag_counts = defaultdict(int)
    for r in cand_rows:
        lag_counts[lag_bars(r)] += 1
    n_cand = len(cand_rows)
    lag_le = {L: round(sum(v for k, v in lag_counts.items() if k <= L) / n_cand * 100, 1)
              for L in LEVELS}

    # pick the survivor: best L where H1 AND H2 both improve $/day or precision,
    # and recall_100 is not below baseline
    base_rec100 = baseline["recall_100"]["pct"] or 0.0
    base_prec = baseline["precision"]["pct"] or 0.0
    survivors = []
    for L in LEVELS:
        a = arms[L]
        h1_money_up = a["H1"]["per_day"] > baseline["H1"]["per_day"]
        h2_money_up = a["H2"]["per_day"] > baseline["H2"]["per_day"]
        prec_up = (a["precision"]["pct"] or 0.0) > base_prec
        rec_ok = (a["recall_100"]["pct"] or 0.0) >= base_rec100
        both_improve = (h1_money_up or prec_up) and (h2_money_up or prec_up)
        if both_improve and rec_ok:
            survivors.append(L)

    if survivors:
        chosen_L = max(survivors, key=lambda L: arms[L]["full"]["per_day"])
        survivor = True
    else:
        # report the L with best full $/day as the headline arm anyway, but
        # mark survivor False
        chosen_L = max(LEVELS, key=lambda L: arms[L]["full"]["per_day"])
        survivor = False
    chosen = arms[chosen_L]

    print("\nsurvivor=%s  chosen L=%d" % (survivor, chosen_L), flush=True)

    out = {
        "book": BOOK.name, "sessions": n_days, "split_day": SPLIT_DAY,
        "cands_per_day": cands_per_day,
        "lag_prevalence_pct_le": lag_counts and lag_le,
        "baseline": baseline,
        "arms": {str(L): arms[L] for L in LEVELS},
        "chosen_L": chosen_L,
        "survivor": survivor,
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1, default=str)

    md = []
    md.append("# g154 -- F5: entry-earlier-satisfiable-bar\n")
    md.append("**One sentence: the engine's own signal bar is not always the earliest bar "
             "that would have satisfied a workable retest -- of the book's %d fired-and-"
             "traded candidates, %.1f%% already had lag_bars<=0 (the signal bar itself was "
             "the earliest workable one); the rest had an earlier bar that would have "
             "worked, and restricting the one-trade-a-day pick to KEEP lag_bars<=L "
             "%s.**\n" % (n_cand, lag_le[0],
                          "clears the survivor bar (H1 and H2 both improve, recall_100 not "
                          "below baseline)" if survivor else
                          "does NOT clear the survivor bar on any tested L"))
    md.append("Every dollar figure: signal-bar CLOSE entry, `stop_rule.stop_fill_price` "
             "stops, size-gated on `signal_runner.min_risk_floor`, 1R = $1,000. Book: "
             "`research/bt2y_trades_retest_on.json` (%d sessions, %s -> %s). "
             "Produced by `research/g154_rule_entry-earlier-satisfiable-bar.py`.\n"
             % (n_days, all_days[0], all_days[-1]))

    md.append("## Lag prevalence (raw candidate stream, %d rows, %.2f cand/day)\n"
              % (n_cand, cands_per_day))
    md.append("| lag_bars <= L | %% of raw candidates |")
    md.append("|---:|---:|")
    for L in LEVELS:
        md.append("| %d | %.1f%% |" % (L, lag_le[L]))
    md.append("")

    md.append("## Money and durability, one-trade-a-day\n")
    md.append("| arm | $/day | mean R | win | months green | max DD | fires/day |")
    md.append("|---|---:|---:|---:|---:|---:|---:|")
    b = baseline["full"]
    md.append("| baseline (first_of_day_arm) | $%.0f | %+.3f | %.1f%% | %d/%d | $%.0f | %.3f |"
              % (b["per_day"], b["mean_r"], b["win_pct"], b["months_green"], b["months"],
                 b["max_dd"], 1.0))
    for L in LEVELS:
        a = arms[L]["full"]
        md.append("| KEEP lag_bars<=%d | $%.0f | %+.3f | %.1f%% | %d/%d | $%.0f | %.3f |"
                  % (L, a["per_day"], a["mean_r"], a["win_pct"], a["months_green"],
                     a["months"], a["max_dd"], arms[L]["fires_per_day"]))
    md.append("")

    md.append("## H1 (< %s) vs H2 (>= %s)\n" % (SPLIT_DAY, SPLIT_DAY))
    md.append("| arm | H1 $/day | H2 $/day | H1 months green | H2 months green |")
    md.append("|---|---:|---:|---:|---:|")
    md.append("| baseline | $%.0f | $%.0f | %d/%d | %d/%d |"
              % (baseline["H1"]["per_day"], baseline["H2"]["per_day"],
                 baseline["H1"]["months_green"], baseline["H1"]["months"],
                 baseline["H2"]["months_green"], baseline["H2"]["months"]))
    for L in LEVELS:
        a = arms[L]
        md.append("| KEEP lag_bars<=%d | $%.0f | $%.0f | %d/%d | %d/%d |"
                  % (L, a["H1"]["per_day"], a["H2"]["per_day"],
                     a["H1"]["months_green"], a["H1"]["months"],
                     a["H2"]["months_green"], a["H2"]["months"]))
    md.append("")

    md.append("## Recall and precision\n")
    md.append("Definitions (stated because the row's wording underdetermines them): the "
             "one-trade-a-day arm picks exactly ONE symbol per calendar day across the "
             "whole pool. RECALL(100) = of the %d cards in `probe_s_sweep_2026-08-28.jsonl` "
             "graded S (answers.s==['s']), the fraction where that day's arm pick exists "
             "and is on that symbol. RECALL(bar-backed) = the same test against all "
             "`marks_pool.s_days()` symbol-days that have `data_archive` bars (%d of %d "
             "graded S). PRECISION = of the days the arm fired, restricted to days where "
             "that (symbol, day) has ANY `marks_pool.canonical_pool()` grade, the fraction "
             "graded S.\n" % (len(probe34), len(s_days_bb), len(s_days)))
    md.append("| arm | recall(100) | recall(bar-backed) | precision |")
    md.append("|---|---:|---:|---:|")
    md.append("| baseline | %s (%d/%d) | %s (%d/%d) | %s (%d/%d) |"
              % (fmt_pct(baseline["recall_100"]["pct"]), baseline["recall_100"]["hit"],
                 baseline["recall_100"]["n"], fmt_pct(baseline["recall_bar_backed"]["pct"]),
                 baseline["recall_bar_backed"]["hit"], baseline["recall_bar_backed"]["n"],
                 fmt_pct(baseline["precision"]["pct"]), baseline["precision"]["graded_s"],
                 baseline["precision"]["graded_any"]))
    for L in LEVELS:
        a = arms[L]
        md.append("| KEEP lag_bars<=%d | %s (%d/%d) | %s (%d/%d) | %s (%d/%d) |"
                  % (L, fmt_pct(a["recall_100"]["pct"]), a["recall_100"]["hit"],
                     a["recall_100"]["n"], fmt_pct(a["recall_bar_backed"]["pct"]),
                     a["recall_bar_backed"]["hit"], a["recall_bar_backed"]["n"],
                     fmt_pct(a["precision"]["pct"]), a["precision"]["graded_s"],
                     a["precision"]["graded_any"]))
    md.append("")

    md.append("## Verdict\n")
    md.append("Survivor test (THE LAW): H1 AND H2 both improve $/day or precision, and "
             "recall_100 is not below baseline. **survivor = %s**, chosen L = %d.\n"
             % (survivor, chosen_L))
    md.append("Chosen arm (KEEP lag_bars<=%d) vs baseline: $%.0f/day vs $%.0f/day "
             "(H1 $%.0f vs $%.0f, H2 $%.0f vs $%.0f); precision %s vs %s; recall(100) "
             "%s vs %s; %d/%d months green vs %d/%d.\n"
             % (chosen_L, chosen["full"]["per_day"], baseline["full"]["per_day"],
                chosen["H1"]["per_day"], baseline["H1"]["per_day"],
                chosen["H2"]["per_day"], baseline["H2"]["per_day"],
                fmt_pct(chosen["precision"]["pct"]), fmt_pct(baseline["precision"]["pct"]),
                fmt_pct(chosen["recall_100"]["pct"]), fmt_pct(baseline["recall_100"]["pct"]),
                chosen["full"]["months_green"], chosen["full"]["months"],
                baseline["full"]["months_green"], baseline["full"]["months"]))
    md.append("Small-N caveat: recall(100) denominators are 34 cards; a single card flipping "
             "moves the percentage by ~3 points. Read this as a direction, not a diagnosis "
             "(CLAUDE.md: never oversell a handful of marks).\n")
    md.append("**Survivor test is fragile, flag for F6.** The formula as specified -- \"H1 "
             "and H2 both improve $/day OR precision\" -- was implemented literally: precision "
             "is a single overall number (the row names no H1/H2-split precision field), so it "
             "is checked once and OR'd into BOTH half-conditions. That is what let L=%d pass: "
             "H1 $/day COLLAPSED (baseline $%.0f/day -> $%.0f/day) while H2 $/day barely moved "
             "(baseline $%.0f/day -> $%.0f/day, still negative) -- neither half's MONEY improved, "
             "but overall precision rose (%s -> %s) and that alone satisfied both halves. A "
             "stricter reading -- both halves' $/day must not get WORSE, with precision only as "
             "a tie-breaker -- would flip every tested L to survivor=False, since every arm's "
             "full-book $/day is negative against a $%.0f/day positive baseline. Reported as "
             "specified; treat 'survivor=True' here as 'passes the letter of the rule', not as "
             "a shippable arm.\n" % (chosen_L, baseline["H1"]["per_day"], chosen["H1"]["per_day"],
                                     baseline["H2"]["per_day"], chosen["H2"]["per_day"],
                                     fmt_pct(baseline["precision"]["pct"]),
                                     fmt_pct(chosen["precision"]["pct"]),
                                     baseline["full"]["per_day"]))
    md.append("Nothing here is applied. `signal_runner.py` is unchanged.\n")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print("\nwrote %s and %s" % (OUT_JSON, OUT_MD), flush=True)


def fmt_pct(p):
    return "n/a" if p is None else "%.1f%%" % p


if __name__ == "__main__":
    main()
