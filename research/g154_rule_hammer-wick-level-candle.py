"""g154 F5 -- candidate "hammer-wick-level-candle".

Austin's claim (S-INDICATOR polarity): "A candle with a visible wick reads as
more predictable, better-respected support/resistance in a trending market
than a full solid-body candle -- separate from whether it is tagged OCR."

TWO SEPARATE MEASUREMENTS, reported side by side, exactly as the row asks:

  PROXY arm  -- the book's own 'hammer' tag: KEEP r if 'hammer' in
                r['tags'] (1202 of 10830 status=='fired' rows -- confirmed
                against research/bt2y_trades_retest_on.json before writing
                this file).
  BARS arm   -- a wick ratio computed directly from data_archive on the
                LEVEL-GENERATING CANDLE (the bar that set r['level_px'], not
                the entry/signal bar). For dir=='call' the level is a high
                (resistance) and the candle's LOWER-wick fraction is used;
                for dir=='put' the level is a low (support) and the candle's
                UPPER-wick fraction is used -- exactly the row's formulas:
                    call: wick_ratio = (min(open,close) - low) / (high-low)
                    put:  wick_ratio = (high - max(open,close)) / (high-low)
                Arm: KEEP wick_ratio >= threshold, swept {0.2, 0.3, 0.4}.

If the two arms disagree in direction/magnitude, that means the 'hammer' tag
is not actually measuring the wick-at-the-level claim -- reported explicitly,
not papered over.

FINDING THE LEVEL-GENERATING CANDLE (causal, data_archive only, no network
fetch -- every file access below is gated on the cached CSV already
existing; a cache miss is a plain empty result, never a live Polygon call,
per CLAUDE.md's 403 NOT_AUTHORIZED note). r['level_px'] can be set by a bar
on the SIGNAL DAY itself (OR high/low, order block, pivot, 1m swing/single-
candle/failed-entry -- level_tf starts with '1m' or '5m') or on a PRIOR
trading day (PDH/PDL, level_tf=='1D'). The search:

  1. Same-day, RTH+premarket bars (`polygon_feed.fetch_day`, cache-only) up
     to and including entry_i's timestamp (entry_i indexes the RTH-only
     bars, the same convention every other g154 bars-feature script uses --
     research/g154_rule_scale-before-the-level.py, .../forming-candle-
     entry-not-extreme.py). Scanned in chronological order; FIRST bar whose
     extreme (high for call, low for put) rounds to r['level_px'] (2 dp,
     i.e. to the cent -- verified exact on a spot check: NVDA 2024-09-19
     entry_i=6, level_px=113.02, bar at 09:36 has low=113.0184) wins -- the
     earliest match is taken as the origin, not a later retest that happens
     to touch the same price again.
  2. If nothing matches same-day, walk backward up to 7 CALENDAR days (the
     archive simply has no file for weekends/holidays, so this silently
     skips them) over full-day archived bars (no time cutoff needed -- an
     entirely prior day is entirely in the past already) and take the first
     day with any match, first matching bar within that day. Spot-checked:
     NVDA 2024-09-19 level_px=117.70 (PDH) resolves to a bar at 14:34:00 on
     2024-09-18.
  3. No match within that window: level bar UNAVAILABLE for this row. An
     unavailable row FAILS the bars-arm KEEP predicate (conservative --
     missing data never manufactures a pass) and the count is reported
     separately (coverage), never silently folded into "fails on wick_ratio".

Both arms use the classifier's S-indicator (KEEP) construction: skip a
non-matching candidate, take the next one that day in arrival order (falls
through exactly like `research.omen_metrics.first_of_day_arm`'s
pick-then-gate fix). A day where nothing survives has no trade.

Money read: the honest, retest-on book (research/bt2y_trades_retest_on.json),
one-trade-a-day (research/omen_metrics.first_of_day_arm, size-gated). Recall
scored per-symbol-day (does the book still produce ANY surviving candidate
for that symbol-day, research/g71_router_recall.py's convention) against
both the 34-card probe_s_sweep and all bar-backed S days
(research/marks_pool.s_days). Precision scored on each arm's own one-a-day
picks against research/marks_pool.canonical_pool().

PRIOR ART, reused not re-derived: research/g86_honest_ceiling.py,
research/g91_lane_slice.py (one-trade-a-day unit); research/omen_metrics.py
(first_of_day_arm, _row_is_sizeable); research/marks_pool.py
(canonical_pool, s_days, row_grade); research/build_deck.py (mark-file
reader, for the 34-card probe); research/g154_rule_level-not-respected-
refusal.py (candidate_arm / recall / precision scaffolding, reused with KEEP
polarity instead of DROP); research/g154_rule_scale-before-the-level.py
(bars_for's data_archive-only, cache-first convention); polygon_feed.py
(fetch_day, rth -- the one CSV reader, never reimplemented).

    python research/g154_rule_hammer-wick-level-candle.py

Writes research/g154_rule_hammer-wick-level-candle.json and .md. Nothing
here is applied; ships nothing.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import polygon_feed as pf               # noqa: E402  fetch_day, rth, ARCHIVE
import omen_metrics as om               # noqa: E402  first_of_day_arm, _row_is_sizeable
from research import marks_pool as mp   # noqa: E402
from research import build_deck as bd   # noqa: E402  mark-file reader

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
PROBE_S_SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT_JSON = os.path.join(HERE, "g154_rule_hammer-wick-level-candle.json")
OUT_MD = os.path.join(HERE, "g154_rule_hammer-wick-level-candle.md")

RISK = 1000.0
SPLIT_DAY = "2025-09-01"      # CLAUDE.md-mandated H1/H2 split
BAR = 397.0                    # Austin's stated bar, for context only
THRESHOLDS = [0.2, 0.3, 0.4]
MAX_BACKDAYS = 7


# --------------------------------------------------------------- bar access

_rth_cache: dict = {}
_full_cache: dict = {}


def bars_rth(sym, day):
    """RTH-only 1m bars, cache-only (never a live fetch -- see module
    docstring). entry_i indexes THIS list, the convention every other
    bars-feature g154 script already uses."""
    k = (sym, day)
    if k not in _rth_cache:
        if len(_rth_cache) > 1200:
            _rth_cache.clear()
        csv_path = pf.ARCHIVE / sym / ("%s.csv" % day)
        if not csv_path.exists():
            _rth_cache[k] = []
        else:
            try:
                _rth_cache[k] = pf.rth(pf.fetch_day(sym, day))
            except Exception:
                _rth_cache[k] = []
    return _rth_cache[k]


def bars_full(sym, day):
    """RTH+premarket 1m bars, cache-only. Used to search for a level bar
    that fired before RTH opened (level_tf 'PMH'/'PML'/'1m premarket'), or
    on an entirely prior day."""
    k = (sym, day)
    if k not in _full_cache:
        if len(_full_cache) > 1200:
            _full_cache.clear()
        csv_path = pf.ARCHIVE / sym / ("%s.csv" % day)
        if not csv_path.exists():
            _full_cache[k] = []
        else:
            try:
                _full_cache[k] = pf.fetch_day(sym, day)
            except Exception:
                _full_cache[k] = []
    return _full_cache[k]


# ------------------------------------------------------- level-bar search

_level_bar_cache: dict = {}


def find_level_bar(sym, day, entry_i, level_px, is_long):
    """The causal candle that set r['level_px'] -- see module docstring for
    the search order. Returns a Candle or None."""
    key = (sym, day, entry_i, round(level_px, 2), is_long)
    if key in _level_bar_cache:
        return _level_bar_cache[key]

    result = None
    rth = bars_rth(sym, day)
    if entry_i is not None and rth and entry_i < len(rth):
        cutoff_ts = rth[entry_i].timestamp
        same_day = [c for c in bars_full(sym, day) if c.timestamp <= cutoff_ts]
        result = _scan(same_day, level_px, is_long)

    if result is None:
        d0 = datetime.fromisoformat(day)
        for back in range(1, MAX_BACKDAYS + 1):
            d = (d0 - timedelta(days=back)).strftime("%Y-%m-%d")
            csv_path = pf.ARCHIVE / sym / ("%s.csv" % d)
            if not csv_path.exists():
                continue
            result = _scan(bars_full(sym, d), level_px, is_long)
            if result is not None:
                break

    _level_bar_cache[key] = result
    return result


def _scan(bars, level_px, is_long):
    target = round(level_px, 2)
    for c in bars:
        extreme = c.high if is_long else c.low
        if round(extreme, 2) == target:
            return c
    return None


def wick_ratio(bar, is_long):
    rng = bar.high - bar.low
    if rng <= 0:
        return None
    if is_long:
        return (min(bar.open, bar.close) - bar.low) / rng
    return (bar.high - max(bar.open, bar.close)) / rng


_wick_cache: dict = {}


def row_wick_ratio(r):
    """(wick_ratio or None, level_bar_found: bool)."""
    key = (r["sym"], r["day"], r.get("entry_i"), round(r["level_px"], 2), r["dir"])
    if key in _wick_cache:
        return _wick_cache[key]
    is_long = r["dir"] == "call"
    bar = find_level_bar(r["sym"], r["day"], r.get("entry_i"), r["level_px"], is_long)
    if bar is None:
        out = (None, False)
    else:
        out = (wick_ratio(bar, is_long), True)
    _wick_cache[key] = out
    return out


# --------------------------------------------------------- candidate stream

def _ekey(r):
    return (r["day"], r["et"], r["sym"])


def candidate_stream(rows):
    by_day = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            by_day[r["day"]].append(r)
    for v in by_day.values():
        v.sort(key=_ekey)
    return by_day


def candidate_arm(by_day, keep_fn):
    """S-indicator (KEEP) construction: skip non-matching, take the first
    surviving (sizeable, matching) candidate in arrival order."""
    picks = []
    for day in sorted(by_day):
        survivors = [r for r in by_day[day]
                     if om._row_is_sizeable(r) is not False and keep_fn(r)]
        if not survivors:
            continue
        picks.append(survivors[0])
    return picks


# ------------------------------------------------------------------ stats

def _daily_pnl(picks, all_days):
    d = {day: 0.0 for day in all_days}
    for r in picks:
        d[r["day"]] += r["pnl"]
    return d


def _months_green(daily):
    m = defaultdict(float)
    for day, v in daily.items():
        m[day[:7]] += v
    g = sum(1 for v in m.values() if v > 0)
    return g, len(m)


def _max_dd(daily):
    peak = cum = worst = 0.0
    for day in sorted(daily):
        cum += daily[day]
        peak = max(peak, cum)
        worst = max(worst, peak - cum)
    return worst


def arm_stats(picks, all_days, label):
    daily = _daily_pnl(picks, all_days)
    n_days = len(all_days)
    total = sum(r["pnl"] for r in picks)
    rs = [r["r"] for r in picks]
    wins = sum(1 for v in rs if v > 0)
    losses = sum(1 for v in rs if v < 0)
    g, m = _months_green(daily)
    return {
        "label": label,
        "sessions": n_days,
        "trades": len(picks),
        "fires_per_day": round(len(picks) / n_days, 4) if n_days else 0.0,
        "usd_day": round(total / n_days, 2) if n_days else 0.0,
        "mean_r": round(statistics.fmean(rs), 4) if rs else 0.0,
        "win_pct": round(wins / (wins + losses) * 100, 1) if wins + losses else 0.0,
        "months_green": "%d/%d" % (g, m),
        "months_green_n": g, "months_total": m,
        "max_dd_usd": round(_max_dd(daily), 2),
        "pct_of_bar": round((total / n_days) / BAR * 100, 1) if n_days else None,
    }


def split(picks, days):
    dset = set(days)
    return [r for r in picks if r["day"] in dset]


# ----------------------------------------------------------- S recall / precision

def _symday_survivors(rows_by_symday, sym, day, keep_fn):
    rows = rows_by_symday.get((sym, day), [])
    sizeable = [r for r in rows if om._row_is_sizeable(r) is not False]
    if keep_fn is None:
        return sizeable
    return [r for r in sizeable if keep_fn(r)]


def recall(keys, rows_by_symday, keep_fn):
    n = 0
    base_hit = arm_hit = 0
    for key in keys:
        sym, day = key.split("_", 1)
        n += 1
        base = _symday_survivors(rows_by_symday, sym, day, None)
        arm = _symday_survivors(rows_by_symday, sym, day, keep_fn)
        if base:
            base_hit += 1
        if arm:
            arm_hit += 1
    return (round(base_hit / n * 100, 1) if n else None,
            round(arm_hit / n * 100, 1) if n else None, n)


def load_probe_s_days():
    keys = []
    for row in bd._rows(PROBE_S_SWEEP):
        if mp.row_grade(row) == "S":
            keys.append(row["card_id"])
    return keys


def precision(picks, pool):
    graded_at_all = graded_s = 0
    for r in picks:
        key = "%s_%s" % (r["sym"], r["day"])
        e = pool.get(key)
        if e is None:
            continue
        graded_at_all += 1
        if e.grade == "S":
            graded_s += 1
    return (round(graded_s / graded_at_all * 100, 1) if graded_at_all else None,
            graded_s, graded_at_all)


# ------------------------------------------------------------------- main

def main():
    blob = json.load(open(BOOK, encoding="utf-8"))
    rows = blob["trades"]
    meta = blob["meta"]
    all_days = sorted({r["day"] for r in rows})
    h1_days = [d for d in all_days if d < SPLIT_DAY]
    h2_days = [d for d in all_days if d >= SPLIT_DAY]

    fired_all = [r for r in rows if r["status"] == "fired"]
    fired_hammer = sum(1 for r in fired_all if "hammer" in r.get("tags", []))
    print("book: %s -- %d sessions" % (os.path.basename(BOOK), meta.get("sessions")
                                        or len(all_days)))
    print("fired (status=='fired'): %d, hammer-tagged: %d (spec: 1202/10830)"
          % (len(fired_all), fired_hammer))

    by_day = candidate_stream(rows)
    total_cands = sum(len(v) for v in by_day.values())
    cands_per_day = round(total_cands / len(all_days), 2)
    by_symday = defaultdict(list)
    for day, v in by_day.items():
        for r in v:
            by_symday[(r["sym"], day)].append(r)

    baseline_picks = om.first_of_day_arm(rows, size_gate=True)
    baseline_all = arm_stats(baseline_picks, all_days, "baseline (whole book)")
    baseline_h1 = arm_stats(split(baseline_picks, h1_days), h1_days, "baseline H1")
    baseline_h2 = arm_stats(split(baseline_picks, h2_days), h2_days, "baseline H2")
    fires_per_day_base = round(len(baseline_picks) / len(all_days), 3)
    print("baseline: $%.2f/day, %d trades, fires/day %.3f"
          % (baseline_all["usd_day"], baseline_all["trades"], fires_per_day_base))

    probe_keys = load_probe_s_days()
    pool = mp.canonical_pool()
    sdays = mp.s_days(pool)
    bar_backed_s_keys = [k for k in sdays if pool[k].has_bars]
    base_prec, base_prec_s, base_prec_n = precision(baseline_picks, pool)

    # -------- proxy arm: the 'hammer' tag itself --------
    def keep_proxy(r):
        return "hammer" in r.get("tags", [])

    proxy_picks = candidate_arm(by_day, keep_proxy)

    # -------- bars arm: wick_ratio computed on the level-generating candle,
    # computed once per row in the whole candidate stream (not just picks),
    # so both the money read AND recall/precision see the same feature. --------
    print("\ncomputing wick_ratio for the candidate stream (%d rows, cache-per-symbol-day)..."
          % total_cands)
    n_computed = 0
    n_available = 0
    for v in by_day.values():
        for r in v:
            wr, found = row_wick_ratio(r)
            r["_wick_ratio"] = wr
            r["_wick_found"] = found
            n_computed += 1
            if found:
                n_available += 1
    coverage_pct = round(n_available / n_computed * 100, 1) if n_computed else None
    print("level bar found for %d/%d candidates (%.1f%% coverage)"
          % (n_available, n_computed, coverage_pct or 0.0))

    def make_keep_bars(threshold):
        def keep_bars(r):
            wr = r.get("_wick_ratio")
            return wr is not None and wr >= threshold
        return keep_bars

    def arm_report(label, picks, keep_fn_for_recall):
        a_all = arm_stats(picks, all_days, "%s (whole book)" % label)
        a_h1 = arm_stats(split(picks, h1_days), h1_days, "%s H1" % label)
        a_h2 = arm_stats(split(picks, h2_days), h2_days, "%s H2" % label)
        probe_base_r, probe_arm_r, probe_n = recall(probe_keys, by_symday, keep_fn_for_recall)
        pool_base_r, pool_arm_r, pool_n = recall(bar_backed_s_keys, by_symday, keep_fn_for_recall)
        prec, prec_s, prec_n = precision(picks, pool)
        h1_delta = round(a_h1["usd_day"] - baseline_h1["usd_day"], 2)
        h2_delta = round(a_h2["usd_day"] - baseline_h2["usd_day"], 2)
        h1_improves = (a_h1["usd_day"] > baseline_h1["usd_day"]) or ((prec or 0) > (base_prec or 0))
        h2_improves = (a_h2["usd_day"] > baseline_h2["usd_day"]) or ((prec or 0) > (base_prec or 0))
        recall_ok = ((probe_arm_r is None or probe_base_r is None or probe_arm_r >= probe_base_r)
                     and (pool_arm_r is None or pool_base_r is None or pool_arm_r >= pool_base_r))
        surv = bool(h1_improves and h2_improves and recall_ok)
        return {
            "candidate": {"all": a_all, "h1": a_h1, "h2": a_h2},
            "h1_delta_usd_day": h1_delta, "h2_delta_usd_day": h2_delta,
            "recall": {
                "probe_s_sweep_34": {"n": probe_n, "baseline_pct": probe_base_r,
                                      "candidate_pct": probe_arm_r},
                "bar_backed_s_days_canonical_pool": {"n": pool_n, "baseline_pct": pool_base_r,
                                                      "candidate_pct": pool_arm_r},
            },
            "precision": {
                "baseline": {"pct": base_prec, "s": base_prec_s, "graded": base_prec_n},
                "candidate": {"pct": prec, "s": prec_s, "graded": prec_n},
            },
            "survivor": surv,
        }

    proxy_out = arm_report("proxy (hammer tag)", proxy_picks, keep_proxy)

    bars_arms_out = {}
    for th in THRESHOLDS:
        keep_bars = make_keep_bars(th)
        bars_picks = candidate_arm(by_day, keep_bars)
        bars_arms_out["thr_%.1f" % th] = arm_report(
            "bars (wick_ratio>=%.1f)" % th, bars_picks, keep_bars)

    proxy_vs_bars_agreement = {}
    for th in THRESHOLDS:
        n_both = n_only_proxy = n_only_bars = n_neither = n_no_wick = 0
        for v in by_day.values():
            for r in v:
                p = "hammer" in r.get("tags", [])
                wr = r.get("_wick_ratio")
                if wr is None:
                    n_no_wick += 1
                    continue
                b = wr >= th
                if p and b:
                    n_both += 1
                elif p and not b:
                    n_only_proxy += 1
                elif b and not p:
                    n_only_bars += 1
                else:
                    n_neither += 1
        proxy_vs_bars_agreement["thr_%.1f" % th] = {
            "both": n_both, "only_proxy_hammer_tag": n_only_proxy,
            "only_bars_wick_ratio": n_only_bars, "neither": n_neither,
            "wick_unavailable": n_no_wick,
        }

    any_survivor = proxy_out["survivor"] or any(a["survivor"] for a in bars_arms_out.values())

    out = {
        "book": os.path.basename(BOOK),
        "book_meta_sessions": meta.get("sessions"),
        "rule": "hammer-wick-level-candle",
        "polarity": "S-indicator (keep-only)",
        "predicate": {
            "proxy": "KEEP r if 'hammer' in r['tags']",
            "bars": "KEEP wick_ratio >= threshold, computed on the causal "
                    "level-generating candle (the bar that set r['level_px']); "
                    "call: (min(o,c)-low)/(high-low), put: (high-max(o,c))/(high-low)",
            "thresholds_swept": THRESHOLDS,
        },
        "fired_base_rates": {
            "fired_all": len(fired_all), "hammer_tagged": fired_hammer,
            "denominator": "status=='fired', all rows (not one-a-day)",
        },
        "candidates_per_day": cands_per_day,
        "level_bar_coverage": {
            "n_candidates_in_stream": n_computed, "n_found": n_available,
            "pct": coverage_pct,
        },
        "baseline": {"all": baseline_all, "h1": baseline_h1, "h2": baseline_h2},
        "proxy_arm": proxy_out,
        "bars_arms": bars_arms_out,
        "proxy_vs_bars_agreement": proxy_vs_bars_agreement,
        "survivor": any_survivor,
        "survivor_by_arm": {"proxy": proxy_out["survivor"],
                             **{k: v["survivor"] for k, v in bars_arms_out.items()}},
        "survivor_rule": "H1 and H2 both improve $/day or precision, and "
                          "recall_100 (both recall panels) not below baseline",
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = []
    md.append("# g154 F5 -- hammer-wick-level-candle")
    md.append("")
    md.append("A visible wick on the level-generating candle is tested here two "
               "ways: the book's own 'hammer' tag (proxy) and a wick ratio "
               "computed directly from data_archive on the candle that set "
               "r['level_px'] (bars), reported side by side on the honest "
               "retest-on book, one-trade-a-day, size-gated. "
               + ("At least one arm survived." if any_survivor else "Neither arm survived."))
    md.append("")
    md.append("Fired base rate (status=='fired', %d rows, NOT the one-a-day unit): "
               "hammer-tagged %d (spec: 1202/10830, confirmed)."
               % (len(fired_all), fired_hammer))
    md.append("")
    md.append("candidates/day (raw arrival stream, whole pool): **%.2f**" % cands_per_day)
    md.append("")
    md.append("Level-bar coverage (causal search, data_archive only): found %d/%d "
               "(%.1f%%) of the stream's candidates. A row with no level bar found "
               "FAILS the bars-arm KEEP predicate (conservative)."
               % (n_available, n_computed, coverage_pct or 0.0))
    md.append("")
    md.append("## Baseline -- one trade a day, whole pool, size-gated")
    md.append("")
    md.append("| split | $/day | mean R | win | months green | max DD | fires/day |")
    md.append("|---|---:|---:|---:|---:|---:|---:|")
    for s in (baseline_all, baseline_h1, baseline_h2):
        lbl = s["label"].split(" ", 1)[-1]
        md.append("| %s | $%.2f | %+.3f | %.1f%% | %s | $%.0f | %.3f |"
                   % (lbl, s["usd_day"], s["mean_r"], s["win_pct"], s["months_green"],
                      s["max_dd_usd"], s["fires_per_day"]))
    md.append("")

    def emit_arm_section(title, a):
        md.append("## Arm: %s" % title)
        md.append("")
        md.append("| split | $/day | mean R | win | months green | max DD | fires/day |")
        md.append("|---|---:|---:|---:|---:|---:|---:|")
        for s in (a["candidate"]["all"], a["candidate"]["h1"], a["candidate"]["h2"]):
            lbl = s["label"].split(" ", 1)[-1]
            md.append("| %s | $%.2f | %+.3f | %.1f%% | %s | $%.0f | %.3f |"
                       % (lbl, s["usd_day"], s["mean_r"], s["win_pct"], s["months_green"],
                          s["max_dd_usd"], s["fires_per_day"]))
        md.append("")
        md.append("delta $/day vs baseline: H1 %+.2f, H2 %+.2f."
                   % (a["h1_delta_usd_day"], a["h2_delta_usd_day"]))
        md.append("")
        md.append("| S recall set | n | baseline | candidate |")
        md.append("|---|---:|---:|---:|")
        r1 = a["recall"]["probe_s_sweep_34"]
        r2 = a["recall"]["bar_backed_s_days_canonical_pool"]
        md.append("| probe_s_sweep (34 S cards) | %d | %s%% | %s%% |"
                   % (r1["n"], r1["baseline_pct"], r1["candidate_pct"]))
        md.append("| bar-backed S days (canonical_pool) | %d | %s%% | %s%% |"
                   % (r2["n"], r2["baseline_pct"], r2["candidate_pct"]))
        md.append("")
        pb = a["precision"]["baseline"]
        pc = a["precision"]["candidate"]
        md.append("| precision | pct | S / graded |")
        md.append("|---|---:|---:|")
        md.append("| baseline | %s%% | %d / %d |" % (pb["pct"], pb["s"], pb["graded"]))
        md.append("| candidate | %s%% | %d / %d |" % (pc["pct"], pc["s"], pc["graded"]))
        md.append("")
        md.append("Arm survivor: **%s**." % ("SURVIVOR" if a["survivor"] else "not a survivor"))
        md.append("")

    emit_arm_section("proxy -- 'hammer' tag", proxy_out)
    for th in THRESHOLDS:
        emit_arm_section("bars -- wick_ratio >= %.1f" % th, bars_arms_out["thr_%.1f" % th])

    md.append("## Proxy vs bars agreement")
    md.append("")
    md.append("| threshold | both | only proxy (hammer tag) | only bars (wick_ratio) | "
               "neither | wick unavailable |")
    md.append("|---|---:|---:|---:|---:|---:|")
    for th in THRESHOLDS:
        a = proxy_vs_bars_agreement["thr_%.1f" % th]
        md.append("| %.1f | %d | %d | %d | %d | %d |"
                   % (th, a["both"], a["only_proxy_hammer_tag"], a["only_bars_wick_ratio"],
                      a["neither"], a["wick_unavailable"]))
    md.append("")
    md.append("If 'only proxy' and 'only bars' are both large relative to 'both', the "
               "'hammer' tag is not measuring the same thing as an actual wick ratio "
               "on the level-generating candle -- read alongside whichever arm(s) "
               "above survive, not instead of them.")
    md.append("")
    md.append("## Verdict")
    md.append("")
    md.append("Survivor rule (per row spec): H1 AND H2 both improve $/day or "
               "precision, and recall_100 (both panels) not below baseline.")
    md.append("")
    md.append("| arm | survivor |")
    md.append("|---|---|")
    md.append("| proxy (hammer tag) | %s |" % proxy_out["survivor"])
    for th in THRESHOLDS:
        md.append("| bars (wick_ratio>=%.1f) | %s |" % (th, bars_arms_out["thr_%.1f" % th]["survivor"]))
    md.append("")
    md.append("**any_survivor = %s**" % any_survivor)

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print("\nwrote %s" % OUT_JSON)
    print("wrote %s" % OUT_MD)
    print("\nany_survivor = %s" % any_survivor)


if __name__ == "__main__":
    main()
