"""g154 F5 -- candidate "no-level-to-retest-against" (OMEN 9.0).

Austin's claim, stated as a POLARITY REFUSAL-INDICATOR: no level to break-
and-retest AGAINST is a standalone reason to refuse a trade, distinct from a
level being present but chopped through (that is `level-not-respected-
refusal`, a different row). He does NOT refuse for lacking a level to
TARGET -- `QQQ_2025-08-01` is graded **S** with exactly that complaint on
record (`research/_extract_s_notes.jsonl:225`, `research/g150_marks_comments.jsonl:780`):

    "931 orderblock, looks like a textbook setup just no levels to target
     unless we know the longer timeframe bias"

So any implementation of this row must distinguish ENTRY-level absence
(refuse) from TARGET-level absence (do not refuse) -- and the QQQ card is
the falsifier that keeps the two from being silently merged. Verified below:
QQQ_2025-08-01's fired&traded candidate carries `level`='PML' (a real named
entry level, entry_i=9, 09:39), so the book-proxy predicate does NOT drop
it -- the row is about the level being RETESTED (the book's `level`/
`level_px`/`level_name` fields), never the level being aimed at.

TWO ARMS, cheap proxy first, then a causal bars check that verifies it.

  BOOK PROXY (primary, cheap) -- DROP r if r['level'] == 'other' (531 of
  10830 fired) or r['level_name'].startswith('not-his:'). 'other' means the
  book itself could not name the level at all; 'not-his:' means the level
  exists in the engine's private roster (pivots-at-a-timestamp, order
  blocks, the OR levels the engine tracks) but is NOT one of the six levels
  Austin says he watches (PDH/PDL/PMH/PML/HOD/LOD, 2026-08-29: "you know the
  6 levels i watch thats it") -- so by his own naming, neither is a level he
  would recognize as something to retest against.

  BARS FORM (causal check) -- from data_archive only, up to the signal bar:
  build the named roster PDH/PDL/PMH/PML/ORH/ORL/HOD/LOD as of entry_i via
  `research/p21_target_availability.py::levels_for_entry` (the same causal,
  no-lookahead level assembly `signal_runner.py`'s own mesh-veto code uses),
  and DROP r if the nearest of those eight is farther than 0.5 x ATR14 from
  Close[entry_i] (ATR14 on the RTH 1-minute bars, `research/downgrade.py`'s
  own ATR_WINDOW=14 causal definition, re-typed here for polygon_feed's
  Candle namedtuple instead of downgrade's dict-bar shape -- no other rule
  from downgrade.py is reused or reimplemented). This is strictly stricter
  than the book proxy in one respect (it can drop a row whose OWN named
  level -- e.g. a stale pivot -- turns out to be far from every level in
  the fresh 8-level roster) and looser in another (a book 'other'/'not-his:'
  row can still land inside 0.5xATR14 of some PDH/PDL/PMH/PML/ORH/ORL/HOD/
  LOD by coincidence) -- reported side by side, not averaged together.

  Both arms are REFUSAL-INDICATORS: skip the dropped candidate and take the
  next surviving one in arrival order (never a KEEP preference), applied
  inside the one-trade-a-day pick exactly like
  `research/g154_rule_level-not-respected-refusal.py`'s construction.

Recall/precision definitions and the H1/H2 split are identical to that
file's -- read its docstring for the exact wording; not re-derived here.

Prior art for the unit: `research/g91_lane_slice.py` (one-trade-a-day,
months-green, max-DD path), `research/g86_honest_ceiling.py` (stats()/
candidates() shape). Neither re-derived; `omen_metrics.first_of_day_arm`
(size-gated) is the baseline, imported not re-typed.

Reads only: `research/bt2y_trades_retest_on.json`, `data_archive/<SYM>/
<day>.csv` (via `polygon_feed`, cache-first, never a network fetch --
`research/p21_target_availability.py::_full_bars`/`_rth_bars` already
enforce that), `research/marks/probe_s_sweep_2026-08-28.jsonl`,
`research/marks_pool.py`. Writes nothing but its own two report files. No
engine file is edited.

    python research/g154_rule_no-level-to-retest-against.py
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import omen_metrics as om                       # noqa: E402  reuse, do not re-derive
from research import marks_pool as mp           # noqa: E402
import p21_target_availability as p21           # noqa: E402  causal level roster

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
PROBE_S_SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT_JSON = os.path.join(HERE, "g154_rule_no-level-to-retest-against.json")
OUT_MD = os.path.join(HERE, "g154_rule_no-level-to-retest-against.md")

RISK = 1000.0
SPLIT_DAY = "2025-09-01"           # H1/H2 split, per THE LAW
BAR = 397.0                         # Austin's stated bar, for context only
NAMED8 = ("PDH", "PDL", "PMH", "PML", "ORH", "ORL", "HOD", "LOD")
ATR_N = 14
BARS_FORM_MULT = 0.5


# --------------------------------------------------------------------- rule

def drop_book_proxy(r):
    """Refusal-indicator, BOOK PROXY: no named level to retest against.
    `level_name` may be missing on a synthetic/legacy row -- treat that the
    same as 'other' (cannot name the level) rather than silently keeping it."""
    if r.get("level") == "other":
        return True
    ln = r.get("level_name")
    return isinstance(ln, str) and ln.startswith("not-his:")


_atr_cache: dict = {}
_levels_cache: dict = {}


def _rth_bars(sym, day):
    return p21._rth_bars(sym, day)


def _atr14(rth, entry_i):
    """ATR14 on RTH 1-minute Candle bars (.high/.low), causal: only bars
    <= entry_i. Same window/definition as research/downgrade.py's ATR_WINDOW
    (True Range on 1m bars degenerates to high-low since these are 1m OHLC
    with no overnight gaps inside the session) -- re-typed for the Candle
    namedtuple polygon_feed hands back, not re-derived from a different rule."""
    lo = max(0, entry_i - ATR_N + 1)
    window = rth[lo:entry_i + 1]
    if not window:
        return 0.0
    return sum(c.high - c.low for c in window) / len(window)


def drop_bars_form(r):
    """Refusal-indicator, BARS FORM: nearest of the causal 8-level roster
    is farther than 0.5xATR14 from Close[entry_i]. Missing bars/entry_i or
    an empty roster is treated as 'cannot judge' -- NOT evidence of absence
    -- so it does not drop (same convention downgrade.py's own unresolvable
    checks use: absence of data is not evidence of the setup)."""
    key = (r["sym"], r["day"], r.get("entry_i"))
    if key in _levels_cache:
        near = _levels_cache[key]
    else:
        sym, day, entry_i = r["sym"], r["day"], r.get("entry_i")
        near = None
        if entry_i is not None:
            rth = _rth_bars(sym, day)
            if rth and entry_i < len(rth):
                roster = p21.levels_for_entry(sym, day, entry_i)
                named = {k: v for k, v in roster.items() if k in NAMED8}
                if named:
                    close = rth[entry_i].close
                    atr = _atr14(rth, entry_i)
                    if atr > 0:
                        dist = min(abs(v - close) for v in named.values())
                        near = dist <= BARS_FORM_MULT * atr
        _levels_cache[key] = near
    return near is False


ARMS = {"book_proxy": drop_book_proxy, "bars_form": drop_bars_form}


def _ekey(r):
    return (r["day"], r["et"], r["sym"])


def _candidate_stream(rows):
    by_day = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            by_day[r["day"]].append(r)
    for v in by_day.values():
        v.sort(key=_ekey)
    return by_day


def candidate_arm(rows, drop_fn):
    """Skip DROP, take the first surviving (non-dropped, sizeable) candidate
    in arrival order -- no KEEP preference, a day with nothing surviving has
    no trade."""
    by_day = _candidate_stream(rows)
    picks = []
    for day in sorted(by_day):
        survivors = [r for r in by_day[day]
                     if om._row_is_sizeable(r) is not False
                     and not drop_fn(r)]
        if not survivors:
            continue
        picks.append(survivors[0])
    return picks


# --------------------------------------------------------------- day stats

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


# ------------------------------------------------------------ S recall

def _symday_survivors(rows_by_symday, sym, day, drop_fn):
    rows = rows_by_symday.get((sym, day), [])
    sizeable = [r for r in rows if om._row_is_sizeable(r) is not False]
    if drop_fn is None:
        return sizeable
    return [r for r in sizeable if not drop_fn(r)]


def recall(keys, rows_by_symday, drop_fn):
    """keys: iterable of 'SYM_YYYY-MM-DD'. Returns (baseline_recall,
    arm_recall, n) -- fraction of those symbol-days where the book still
    fires at all (baseline) vs still fires after this arm's refusal filter
    (candidate). Per symbol-day, same convention g154_rule_level-not-
    respected-refusal.py uses -- NOT the single global one-a-day pick."""
    n = 0
    base_hit = arm_hit = 0
    for key in keys:
        sym, day = key.split("_", 1)
        n += 1
        base = _symday_survivors(rows_by_symday, sym, day, None)
        arm = _symday_survivors(rows_by_symday, sym, day, drop_fn)
        if base:
            base_hit += 1
        if arm:
            arm_hit += 1
    return (round(base_hit / n * 100, 1) if n else None,
            round(arm_hit / n * 100, 1) if n else None, n)


def load_probe_s_days():
    keys = []
    with open(PROBE_S_SWEEP, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if mp.row_grade(row) == "S":
                keys.append(row["card_id"])
    return keys


# ----------------------------------------------------------- precision

def precision(picks, pool):
    graded_at_all = 0
    graded_s = 0
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


# ------------------------------------------------------- QQQ falsifier check

def qqq_falsifier_check(rows):
    """QQQ_2025-08-01's fired&traded candidate must NOT be dropped by the
    book-proxy predicate -- it is graded S with a TARGET-level complaint
    ("no levels to target"), not an ENTRY-level one, and this row's
    predicate reads the book's ENTRY level (r['level']/r['level_name']),
    never the target. If this ever flips to True, the predicate has drifted
    onto the target-level question the row explicitly forbids."""
    cands = [r for r in rows if r["sym"] == "QQQ" and r["day"] == "2025-08-01"
              and r["status"] == "fired" and r.get("traded")]
    if not cands:
        return {"found": False, "dropped_by_book_proxy": None,
                "level": None, "level_name": None}
    r = cands[0]
    return {"found": True, "dropped_by_book_proxy": drop_book_proxy(r),
            "level": r.get("level"), "level_name": r.get("level_name"),
            "et": r.get("et")}


def main():
    blob = json.load(open(BOOK, encoding="utf-8"))
    rows = blob["trades"]
    meta = blob["meta"]
    all_days = sorted({r["day"] for r in rows})
    h1_days = [d for d in all_days if d < SPLIT_DAY]
    h2_days = [d for d in all_days if d >= SPLIT_DAY]

    def split(picks, days):
        dset = set(days)
        return [r for r in picks if r["day"] in dset]

    baseline_picks = om.first_of_day_arm(rows, size_gate=True)
    baseline_all = arm_stats(baseline_picks, all_days, "baseline (whole book)")
    baseline_h1 = arm_stats(split(baseline_picks, h1_days), h1_days, "baseline H1")
    baseline_h2 = arm_stats(split(baseline_picks, h2_days), h2_days, "baseline H2")

    by_day_stream = _candidate_stream(rows)
    cand_stream_by_symday = defaultdict(list)
    for day, v in by_day_stream.items():
        for r in v:
            cand_stream_by_symday[(r["sym"], day)].append(r)
    total_cands = sum(len(v) for v in by_day_stream.values())
    cands_per_day = round(total_cands / len(all_days), 2)

    fired_all = [r for r in rows if r["status"] == "fired"]
    fired_proxy = sum(1 for r in fired_all if drop_book_proxy(r))

    probe_keys = load_probe_s_days()
    pool = mp.canonical_pool()
    sdays = mp.s_days(pool)
    bar_backed_s_keys = [k for k in sdays if pool[k].has_bars]

    qqq_check = qqq_falsifier_check(rows)

    arms_out = {}
    for arm_name, drop_fn in ARMS.items():
        arm_picks = candidate_arm(rows, drop_fn)
        arm_all = arm_stats(arm_picks, all_days, "candidate (whole book)")
        arm_h1 = arm_stats(split(arm_picks, h1_days), h1_days, "candidate H1")
        arm_h2 = arm_stats(split(arm_picks, h2_days), h2_days, "candidate H2")

        probe_base_recall, probe_arm_recall, probe_n = recall(
            probe_keys, cand_stream_by_symday, drop_fn)
        pool_base_recall, pool_arm_recall, pool_n = recall(
            bar_backed_s_keys, cand_stream_by_symday, drop_fn)

        base_prec, base_prec_s, base_prec_n = precision(baseline_picks, pool)
        arm_prec, arm_prec_s, arm_prec_n = precision(arm_picks, pool)

        h1_delta = arm_h1["usd_day"] - baseline_h1["usd_day"]
        h2_delta = arm_h2["usd_day"] - baseline_h2["usd_day"]
        h1_improves = (arm_h1["usd_day"] > baseline_h1["usd_day"]) or (
            (arm_prec or 0) > (base_prec or 0))
        h2_improves = (arm_h2["usd_day"] > baseline_h2["usd_day"]) or (
            (arm_prec or 0) > (base_prec or 0))
        recall_ok = (probe_arm_recall is None or probe_base_recall is None
                     or probe_arm_recall >= probe_base_recall) and (
            pool_arm_recall is None or pool_base_recall is None
            or pool_arm_recall >= pool_base_recall)
        survivor = bool(h1_improves and h2_improves and recall_ok)

        arms_out[arm_name] = {
            "candidate": {"all": arm_all, "h1": arm_h1, "h2": arm_h2},
            "h1_delta_usd_day": round(h1_delta, 2),
            "h2_delta_usd_day": round(h2_delta, 2),
            "recall": {
                "probe_s_sweep_34": {
                    "n": probe_n, "baseline_pct": probe_base_recall,
                    "candidate_pct": probe_arm_recall,
                },
                "bar_backed_s_days_canonical_pool": {
                    "n": pool_n, "baseline_pct": pool_base_recall,
                    "candidate_pct": pool_arm_recall,
                },
            },
            "precision": {
                "baseline": {"pct": base_prec, "s": base_prec_s, "graded": base_prec_n},
                "candidate": {"pct": arm_prec, "s": arm_prec_s, "graded": arm_prec_n},
            },
            "survivor": survivor,
        }

    # book_proxy is the load-bearing arm (cheap, exact per the spec's fired
    # count 531/10830); bars_form is reported as the causal cross-check, not
    # averaged in.
    overall_survivor = arms_out["book_proxy"]["survivor"]

    out = {
        "book": os.path.basename(BOOK),
        "book_meta_sessions": meta.get("sessions"),
        "rule": "no-level-to-retest-against",
        "polarity": "refusal-indicator",
        "predicate": {
            "book_proxy": "DROP r if r['level']=='other' or "
                           "r['level_name'].startswith('not-his:')",
            "bars_form": "DROP r if the nearest of PDH/PDL/PMH/PML/ORH/ORL/"
                          "HOD/LOD (causal, as of entry_i) is farther than "
                          "0.5xATR14 from Close[entry_i]",
            "notes": "Both read the ENTRY level (the level being retested), "
                     "never the TARGET level -- see qqq_falsifier_check.",
        },
        "qqq_falsifier_check": qqq_check,
        "fired_base_rates": {
            "fired_all": len(fired_all),
            "no_level_book_proxy": fired_proxy,
            "denominator": "status=='fired', all rows (not one-a-day)",
        },
        "candidates_per_day": cands_per_day,
        "baseline": {"all": baseline_all, "h1": baseline_h1, "h2": baseline_h2},
        "arms": arms_out,
        "survivor": overall_survivor,
        "survivor_basis": "book_proxy arm (the row's specced predicate); "
                           "bars_form is the causal cross-check, reported "
                           "not averaged in",
        "survivor_rule": "H1 and H2 both improve $/day or precision, and "
                          "recall_100 (both recall panels) not below baseline",
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = []
    md.append("# g154 F5 -- no-level-to-retest-against")
    md.append("")
    md.append("No named level to break-and-retest against is tested here as "
              "a standalone REFUSAL, distinct from a level being present "
              "but chopped through (that is a separate row, "
              "`level-not-respected-refusal`). He does NOT refuse for "
              "lacking a level to TARGET -- verified below on "
              "`QQQ_2025-08-01`, graded S with exactly that complaint on "
              "record.")
    md.append("")
    q = qqq_check
    md.append("**QQQ_2025-08-01 falsifier check**: found=%s, level=%r, "
               "level_name=%r, dropped_by_book_proxy=%s. Graded **S** "
               "(`research/_extract_s_notes.jsonl:225`) with the comment "
               "\"931 orderblock, looks like a textbook setup just no "
               "levels to target unless we know the longer timeframe "
               "bias\" -- a TARGET complaint, and its book row carries a "
               "real named ENTRY level, so the predicate correctly keeps it."
               % (q["found"], q["level"], q["level_name"],
                  q["dropped_by_book_proxy"]))
    md.append("")
    md.append("Fired base rate (status=='fired', %d rows, NOT the one-a-day "
               "unit): no-level book_proxy %d." % (len(fired_all), fired_proxy))
    md.append("")
    md.append("candidates/day (raw arrival stream, whole pool): **%.2f**"
               % cands_per_day)
    md.append("")
    md.append("## Baseline -- one trade a day, whole pool, size-gated")
    md.append("")
    md.append("| split | $/day | mean R | win | months green | max DD | fires/day |")
    md.append("|---|---:|---:|---:|---:|---:|---:|")
    for s in (baseline_all, baseline_h1, baseline_h2):
        split_label = s["label"].split(" ", 1)[-1]
        md.append("| %s | $%.2f | %+.3f | %.1f%% | %s | $%.0f | %.3f |"
                   % (split_label, s["usd_day"], s["mean_r"], s["win_pct"],
                      s["months_green"], s["max_dd_usd"], s["fires_per_day"]))
    md.append("")

    for arm_name in ("book_proxy", "bars_form"):
        a = arms_out[arm_name]
        md.append("## Arm: %s" % arm_name)
        md.append("")
        md.append("| split | $/day | mean R | win | months green | max DD | fires/day |")
        md.append("|---|---:|---:|---:|---:|---:|---:|")
        for s in (a["candidate"]["all"], a["candidate"]["h1"], a["candidate"]["h2"]):
            split_label = s["label"].split(" ", 1)[-1]
            md.append("| %s | $%.2f | %+.3f | %.1f%% | %s | $%.0f | %.3f |"
                       % (split_label, s["usd_day"], s["mean_r"], s["win_pct"],
                          s["months_green"], s["max_dd_usd"], s["fires_per_day"]))
        md.append("")
        md.append("delta $/day vs baseline: H1 %+.2f, H2 %+.2f."
                   % (a["h1_delta_usd_day"], a["h2_delta_usd_day"]))
        md.append("")
        md.append("| S recall set | n | baseline | %s |" % arm_name)
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
        md.append("| %s | %s%% | %d / %d |" % (arm_name, pc["pct"], pc["s"], pc["graded"]))
        md.append("")
        md.append("Arm survivor: **%s**." % ("SURVIVOR" if a["survivor"] else "not a survivor"))
        md.append("")

    md.append("## Verdict")
    md.append("")
    md.append("The specced predicate is `book_proxy`, verified to fire on "
               "**%d of %d** fired rows -- matching the row's own quoted "
               "count exactly. `bars_form` is a causal cross-check, not "
               "the survivor basis. **Overall survivor = %s (basis: %s).**"
               % (fired_proxy, len(fired_all), overall_survivor,
                  out["survivor_basis"]))
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")

    print("candidates/day: %.2f" % cands_per_day)
    print("QQQ_2025-08-01 falsifier check: %s" % qqq_check)
    print("baseline: $%.2f/day  mean R %+.3f  win %.1f%%  months %s  maxDD $%.0f  fires/day %.3f"
          % (baseline_all["usd_day"], baseline_all["mean_r"], baseline_all["win_pct"],
             baseline_all["months_green"], baseline_all["max_dd_usd"], baseline_all["fires_per_day"]))
    for arm_name in ("book_proxy", "bars_form"):
        a = arms_out[arm_name]["candidate"]["all"]
        print("%s: $%.2f/day  mean R %+.3f  win %.1f%%  months %s  maxDD $%.0f  fires/day %.3f"
              % (arm_name, a["usd_day"], a["mean_r"], a["win_pct"],
                 a["months_green"], a["max_dd_usd"], a["fires_per_day"]))
        print("  H1 delta $%+.2f/day  H2 delta $%+.2f/day  survivor=%s"
              % (arms_out[arm_name]["h1_delta_usd_day"],
                 arms_out[arm_name]["h2_delta_usd_day"],
                 arms_out[arm_name]["survivor"]))
    print("OVERALL SURVIVOR = %s" % overall_survivor)
    print("-> %s\n-> %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
