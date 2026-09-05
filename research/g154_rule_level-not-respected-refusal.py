"""g154 F5 -- candidate "level-not-respected-refusal".

Austin's claim: a level that is NOT being respected -- candles closing
through it or chopping on it instead of reacting off it -- is a reason to
REFUSE the trade outright, not merely a downgrade dimension. This is a pure
REFUSAL-INDICATOR (polarity), no S-indicator/keep half exists in the row spec.

Predicate, exactly as specced, two arms:

  VETO arm   -- DROP r if 'level_not_respected' in r['downgrades']
                (7176 of 10830 fired rows -- a 66% cut, the largest of any
                candidate in this batch. Because the cut is this large,
                candidates/day and S recall decide it, not $/day.)

  SOFTER arm -- DROP r only when 'level_not_respected' in r['downgrades']
                *and* r['confluence'] == 'no' (co-occurrence gate: only
                refuse when nothing else backs the level).

Both measured over the honest, retest-on book
(research/bt2y_trades_retest_on.json), on the one-trade-a-day unit
(research/omen_metrics.first_of_day_arm, size-gated). Neither arm has a KEEP
preference among survivors (no S-indicator half in this row) -- the pick is
simply the first surviving (non-dropped, sizeable) candidate in arrival
order, identical construction to the baseline otherwise.

Recall is scored the way research/g71_router_recall.py scores it: per
SYMBOL-DAY, not the global one-a-day pick -- "did the book still produce a
survivor for THIS symbol on THIS day", using the book's own fired-and-
traded/halted candidate stream for that symbol-day. Precision is scored on
each arm's own one-a-day picks, against research/marks_pool.canonical_pool().

    python research/g154_rule_level-not-respected-refusal.py

Writes research/g154_rule_level-not-respected-refusal.json and .md.
Nothing here is applied; ships nothing.
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

import omen_metrics as om              # noqa: E402  reuse, do not re-derive
from research import marks_pool as mp  # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
PROBE_S_SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT_JSON = os.path.join(HERE, "g154_rule_level-not-respected-refusal.json")
OUT_MD = os.path.join(HERE, "g154_rule_level-not-respected-refusal.md")

RISK = 1000.0
SPLIT_DAY = "2025-09-01"          # H1/H2 split, per row spec
BAR = 397.0                        # Austin's stated bar, for context only


# --------------------------------------------------------------------- rule

def drop_veto(r):
    """Refusal-indicator, VETO arm: level not respected -- drop outright."""
    return "level_not_respected" in r.get("downgrades", [])


def drop_softer(r):
    """Refusal-indicator, SOFTER arm: drop only when level-not-respected
    co-occurs with no other confluence backing the level."""
    return drop_veto(r) and r.get("confluence") == "no"


ARMS = {"veto": drop_veto, "softer": drop_softer}


def _ekey(r):
    return (r["day"], r["et"], r["sym"])


def _candidate_stream(rows):
    """fired&traded or halted, grouped by day, arrival order -- identical
    construction to g86_honest_ceiling.candidates / omen_metrics.first_of_day_arm."""
    by_day = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            by_day[r["day"]].append(r)
    for v in by_day.values():
        v.sort(key=_ekey)
    return by_day


def candidate_arm(rows, drop_fn):
    """The classifier's one-trade-a-day pick: skip DROP, take the first
    surviving (non-dropped, sizeable) candidate in arrival order. No KEEP
    preference exists for this row -- a day where nothing survives has no
    trade."""
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
    fires at all (baseline) vs still fires after the arm's refusal-indicator
    (candidate)."""
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
    fired_lnr = sum(1 for r in fired_all
                     if "level_not_respected" in r.get("downgrades", []))
    fired_lnr_softer = sum(1 for r in fired_all if drop_softer(r))

    probe_keys = load_probe_s_days()
    pool = mp.canonical_pool()
    sdays = mp.s_days(pool)
    bar_backed_s_keys = [k for k in sdays if pool[k].has_bars]

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

    # overall survivor: softer arm is the load-bearing one -- the veto arm's
    # 66% cut is reported for candidates/day and recall, not treated as a
    # money arm on its own (per row: "candidates/day and S recall decide it,
    # not $/day").
    overall_survivor = arms_out["softer"]["survivor"]

    out = {
        "book": os.path.basename(BOOK),
        "book_meta_sessions": meta.get("sessions"),
        "rule": "level-not-respected-refusal",
        "polarity": "refusal-indicator",
        "predicate": {
            "veto": "DROP r if 'level_not_respected' in r['downgrades']",
            "softer": "DROP r if 'level_not_respected' in r['downgrades'] "
                      "and r['confluence'] == 'no'",
            "notes": "No S-indicator/KEEP half exists for this row -- both "
                     "arms are pure refusal filters over the arrival-order "
                     "first-of-day stream.",
        },
        "fired_base_rates": {
            "fired_all": len(fired_all),
            "level_not_respected_veto": fired_lnr,
            "level_not_respected_and_no_confluence_softer": fired_lnr_softer,
            "denominator": "status=='fired', all rows (not one-a-day)",
        },
        "candidates_per_day": cands_per_day,
        "baseline": {"all": baseline_all, "h1": baseline_h1, "h2": baseline_h2},
        "arms": arms_out,
        "survivor": overall_survivor,
        "survivor_basis": "softer arm (co-occurrence gate); veto arm is a "
                           "66% cut and is judged on candidates/day and S "
                           "recall, not survivor status",
        "survivor_rule": "H1 and H2 both improve $/day or precision, and "
                          "recall_100 (both recall panels) not below baseline",
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = []
    md.append("# g154 F5 -- level-not-respected-refusal")
    md.append("")
    md.append("A level not being respected (candles closing through it or "
              "chopping on it instead of reacting off it) is tested here as "
              "a REFUSAL, not a downgrade dimension -- two arms, a hard veto "
              "and a softer co-occurrence gate, on the honest retest-on "
              "book, one-trade-a-day, size-gated.")
    md.append("")
    md.append("Fired base rates (status=='fired', %d rows, NOT the one-a-day "
               "unit): level_not_respected (veto) %d, + no-confluence "
               "(softer) %d." % (len(fired_all), fired_lnr, fired_lnr_softer))
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

    for arm_name in ("veto", "softer"):
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
    md.append("The veto arm cuts **66%%** of fired rows (%d of %d) -- the "
               "largest cut of any F5 candidate. That size means the veto "
               "arm's read comes from candidates/day and S recall, not "
               "$/day: %.2f cand/day, but the recall panels above show how "
               "much of the S-day book it takes with it. **Overall survivor "
               "= %s (basis: %s).**"
               % (fired_lnr, len(fired_all), cands_per_day,
                  overall_survivor, out["survivor_basis"]))
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")

    print("candidates/day: %.2f" % cands_per_day)
    print("baseline: $%.2f/day  mean R %+.3f  win %.1f%%  months %s  maxDD $%.0f  fires/day %.3f"
          % (baseline_all["usd_day"], baseline_all["mean_r"], baseline_all["win_pct"],
             baseline_all["months_green"], baseline_all["max_dd_usd"], baseline_all["fires_per_day"]))
    for arm_name in ("veto", "softer"):
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
