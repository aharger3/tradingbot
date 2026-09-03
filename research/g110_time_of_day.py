"""g110 -- time of day, and what else separates a good S trade from the rest.

Austin's R3 ruling (2026-09-03): he did NOT pick a stopping-for-the-day rule.
His words: "We have to measure best s trades based on time which is most
important factor and other ones if you can think of." He told us TIME is the
biggest lever and to go find the rest -- not to assert a policy and back into
a justification for it.

Four questions, one book (`bt2y_trades_retest_on.json`), one gate
(`signal_runner.min_risk_floor`), one fill (the book's own honest close fill --
see MASTER_SPEC.md sec1, this is the pessimistic ruler, not the ladder):

  Q1  Bucket every size-gated candidate by entry minute (5-minute buckets,
      09:30 through 11:00). Per bucket: n, mean R, win rate, share reaching
      2R/3R while still alive (bar-ordered, g97's walk -- no lookahead), and
      $/day if that bucket's first candidate were the ONLY thing traded that
      day (every other day pays $0; MASTER_SPEC.md's one unit).
  Q2  Cross those buckets with HIS labels. Unit matches g109's: the judged
      symbol-day's own first size-gated candidate, bucketed by ITS entry
      minute. Answers "does the window a candidate arrives in predict whether
      he'd call the day S," not "does the calendar day's first trade land in
      a good window" -- those are different questions and g109 already
      answers the second one.
  Q3  Scan every OTHER causal field the book stamps -- excluding anything
      computed from the full session or the full 2-year sample (rangeb, dret,
      spy_trend, vol_regime, drange, gap: see MASTER_SPEC.md sec4, "Nothing
      the engine computes identifies one at entry time"). `bucket` (this
      script's own time slice) is included IN the same scan, not reported
      separately, so time can be ranked against everything else on one table
      instead of asserted to win.
  Q4  Price the day-end policy the time profile implies: first regardless
      (shipped), first at/after the best threshold T, first in the best
      window only (sit out otherwise), and first in the best window falling
      back to first-regardless (never sit out). Same unit throughout: $/day
      over all 498 sessions, book fill.

No lookahead: every field read here is knowable at or before the entry bar's
close, and the bar-ordered walk (g97.walk) only ever looks forward from
entry_i + 1, same convention every other g9x/g10x script uses. This script
APPLIES NOTHING -- no engine file is touched.

    python research/g110_time_of_day.py
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402
import g97_mfe as g97                             # noqa: E402
import g102_wait_for_the_open as g102             # noqa: E402
from research import g80_ordertype_grid as G      # noqa: E402
from research import marks_pool as mp             # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_JSON = os.path.join(HERE, "g110_time_of_day.json")
OUT_MD = os.path.join(HERE, "g110_time_of_day.md")

BUCKET_MIN = 5
SESSION_START_MIN = 9 * 60 + 30    # 09:30
SESSION_END_MIN = 11 * 60          # 11:00 -- signal_runner.SESSION_END
MIN_DAYS = 30                      # a feature-value must cover this many days to be scored

# Full-session or full-2-year-sample derived -- lookahead at the entry bar.
# See MASTER_SPEC.md sec4: rangeb/dret/spy_trend/vol_regime are the named four;
# drange and raw gap are the same class (day's whole range, unbucketed magnitude
# with no fixed causal threshold). gapb IS causal -- backtest_2y.py buckets it
# on a fixed abs() threshold, no sample statistic.
EXCLUDED_LOOKAHEAD = ("rangeb", "dret", "spy_trend", "vol_regime", "drange", "gap")

_PACK = {}


def pack(sym, day):
    k = (sym, day)
    if k not in _PACK:
        _PACK[k] = G.day_pack(sym, day)
    return _PACK[k]


def minute_of(et):
    hh, mm = et.split(":")[:2]
    return int(hh) * 60 + int(mm)


def bucket_label(et):
    m = minute_of(et)
    start = (m // BUCKET_MIN) * BUCKET_MIN
    end = start + BUCKET_MIN - 1
    return "%02d:%02d-%02d:%02d" % (start // 60, start % 60, end // 60, end % 60)


def bucket_start_minute(label):
    hh, mm = label[:5].split(":")
    return int(hh) * 60 + int(mm)


def money(daily, n_days):
    return round(sum(daily.values()) / n_days, 2) if n_days else 0.0


def causal_features(r):
    """Every label the book stamps that is knowable AT the entry bar's close.

    Excludes EXCLUDED_LOOKAHEAD. `bucket` (this script's own 5-minute entry
    window) rides in the SAME list as everything else, on purpose -- Q3 asks
    whether anything beats time, and that question is only honest if time
    competes in the same scan rather than getting a separate victory lap.
    """
    out = [("dow", r.get("dow")), ("gapb", r.get("gapb")), ("stopb", r.get("stopb")),
           ("bias", r.get("bias")), ("aligned", r.get("aligned")), ("side", r.get("side")),
           ("confluence", r.get("confluence")),
           ("tripped", "tripped%s" % r.get("tripped")), ("seq", "seq%s" % r.get("seq")),
           ("level_tf", r.get("level_tf")), ("tier", r.get("tier")), ("pool", r.get("pool")),
           ("cls", r.get("cls")), ("grade", r.get("grade")), ("sgrade", r.get("sgrade")),
           ("bucket", bucket_label(r.get("et")))]
    for t in (r.get("tags") or ()):
        out.append(("tag", t))
    for d in (r.get("downgrades") or ()):
        out.append(("downgrade", d))
    return [(k, v) for k, v in out if v not in (None, "", "None")]


def bucket_order(keys):
    return sorted(keys, key=bucket_start_minute)


def q1_buckets(byday, n_days):
    print("=== Q1: entry-minute buckets, every size-gated candidate ===")
    all_sized = [r for d in sorted(byday) for r in byday[d] if g102.sized(r)]
    print("size-gated candidates: %d across %d sessions\n" % (len(all_sized), n_days))

    by_bucket = defaultdict(list)
    for r in all_sized:
        by_bucket[bucket_label(r["et"])].append(r)

    firsts_sized = {}
    for d in sorted(byday):
        r = next((x for x in byday[d] if g102.sized(x)), None)
        if r is not None:
            firsts_sized[d] = r
    baseline_pday = money({d: r["pnl"] for d, r in firsts_sized.items()}, n_days)

    stats = {}
    print("%-14s %5s %9s %7s %7s %7s %8s %6s" %
          ("bucket", "n", "mean R", "win%", ">=2R", ">=3R", "$/day", "days"))
    for bk in bucket_order(by_bucket):
        rs = by_bucket[bk]
        n = len(rs)
        mean_r = statistics.mean(r["r"] for r in rs)
        wins = sum(1 for r in rs if r["pnl"] > 0)
        losses = sum(1 for r in rs if r["pnl"] < 0)
        win_pct = 100 * wins / (wins + losses) if wins + losses else 0.0

        alive2 = alive3 = measured = 0
        for r in rs:
            bars, *_ = pack(r["sym"], r["day"])
            if not bars:
                continue
            w = g97.walk(r, bars)
            if w is None:
                continue
            mfe, _stopped, _out = w
            measured += 1
            alive2 += mfe >= 2.0
            alive3 += mfe >= 3.0
        p2 = 100 * alive2 / measured if measured else 0.0
        p3 = 100 * alive3 / measured if measured else 0.0

        daily = {}
        for d in sorted(byday):
            r = next((x for x in byday[d] if g102.sized(x) and bucket_label(x["et"]) == bk),
                     None)
            if r is not None:
                daily[d] = r["pnl"]
        pday = money(daily, n_days)

        stats[bk] = {"n": n, "mean_r": round(mean_r, 4), "win_pct": round(win_pct, 1),
                     "pct_2r_alive": round(p2, 1), "pct_3r_alive": round(p3, 1),
                     "mfe_measured": measured, "dollars_per_day": pday,
                     "days_taken": len(daily)}
        print("%-14s %5d %+9.3f %6.1f%% %6.1f%% %6.1f%% %8.0f %6d" %
              (bk, n, mean_r, win_pct, p2, p3, pday, len(daily)))

    print("\nreference: first-of-day, any bucket, all %d sessions: $%.0f/day"
          % (n_days, baseline_pday))
    return stats, baseline_pday, firsts_sized


def q2_his_labels(rows):
    print("\n=== Q2: within each bucket, what share of HIS judged symbol-days "
          "did he call S? ===")
    print("(unit: the judged symbol-day's own first size-gated candidate, "
          "bucketed by ITS entry minute -- g109's unit, sliced finer.)\n")
    pool = mp.canonical_pool()
    s_days = set(mp.s_days(pool))
    judged = set(pool)

    bysd = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            bysd["%s_%s" % (r["sym"], r["day"])].append(r)
    for v in bysd.values():
        v.sort(key=g86.ekey)

    judged_firsts = {}
    for k in bysd:
        if k not in judged:
            continue
        r = next((x for x in bysd[k] if g102.sized(x)), None)
        if r is not None:
            judged_firsts[k] = r

    n_judged = len(judged_firsts)
    n_s = sum(1 for k in judged_firsts if k in s_days)
    print("judged symbol-days with a size-gated first candidate: %d ; his S: %d "
          "(%.1f%% base rate)\n" % (n_judged, n_s, 100 * n_s / n_judged if n_judged else 0))

    by_bucket = defaultdict(list)
    for k, r in judged_firsts.items():
        by_bucket[bucket_label(r["et"])].append(k)

    out = {}
    print("%-14s %5s %8s" % ("bucket", "n", "S-rate"))
    for bk in bucket_order(by_bucket):
        ks = by_bucket[bk]
        s_n = sum(1 for k in ks if k in s_days)
        rate = 100 * s_n / len(ks)
        out[bk] = {"n": len(ks), "s": s_n, "s_rate": round(rate, 1)}
        print("%-14s %5d %7.1f%%" % (bk, len(ks), rate))
    return out, n_judged, n_s


def q3_other_factors(byday, n_days, baseline_pday):
    print("\n=== Q3: does any OTHER causal field separate, beyond time? ===")
    print("(excluded as lookahead: %s)\n" % ", ".join(EXCLUDED_LOOKAHEAD))

    bucket_pnl = defaultdict(dict)
    for d in sorted(byday):
        for r in byday[d]:
            if not g102.sized(r):
                continue
            for kv in causal_features(r):
                bucket_pnl[kv].setdefault(d, r["pnl"])

    scored = []
    for kv, daily in bucket_pnl.items():
        if len(daily) < MIN_DAYS:
            continue
        scored.append((money(daily, len(daily)), money(daily, n_days), len(daily), kv))
    scored.sort(key=lambda s: s[1], reverse=True)

    print("%-28s %10s %10s %6s" % ("feature=value", "$/covered", "$/all-day", "days"))
    for cov, alld, nd, (k, v) in scored[:20]:
        print("%-28s %10.0f %10.0f %6d" % ("%s=%s" % (k, v), cov, alld, nd))
    beats = [s for s in scored if s[1] > baseline_pday]
    print("\n... %d feature-values scored (min %d days each); baseline first-of-day "
          "$%.0f/day" % (len(scored), MIN_DAYS, baseline_pday))
    print("feature-values beating first-of-day on an all-day basis: %d" % len(beats))

    bucket_entries = [s for s in scored if s[3][0] == "bucket"]
    if bucket_entries:
        best_bucket_entry = bucket_entries[0]
        rank = scored.index(best_bucket_entry) + 1
        print("best TIME bucket (%s) ranks #%d of %d scored feature-values by "
              "$/all-day ($%.0f)" % (best_bucket_entry[3][1], rank, len(scored),
                                      best_bucket_entry[1]))
    return scored, beats


def q4_day_end_policy(byday, n_days, bucket_stats, baseline_pday):
    print("\n=== Q4: the day-end / arrival policy the time profile implies ===")
    print("all four price the SAME unit: $/day, all %d sessions, book fill.\n" % n_days)

    elig = [(bk, s) for bk, s in bucket_stats.items() if s["days_taken"] >= MIN_DAYS]
    elig.sort(key=lambda kv: kv[1]["dollars_per_day"], reverse=True)
    best_bucket = elig[0][0] if elig else None

    policies = []

    n_with_candidate = sum(1 for d in byday if any(g102.sized(r) for r in byday[d]))
    policies.append(("A first regardless (shipped)", baseline_pday, n_with_candidate))

    best_T, best_T_pday, best_T_n = None, None, None
    for T in range(SESSION_START_MIN, SESSION_END_MIN, BUCKET_MIN):
        daily = {}
        for d in sorted(byday):
            r = next((x for x in byday[d] if g102.sized(x) and minute_of(x["et"]) >= T),
                     None)
            if r is not None:
                daily[d] = r["pnl"]
        pday = money(daily, n_days)
        if best_T_pday is None or pday > best_T_pday:
            best_T, best_T_pday, best_T_n = T, pday, len(daily)
    policies.append(("B first at/after best T (%02d:%02d)"
                     % (best_T // 60, best_T % 60), best_T_pday, best_T_n))

    if best_bucket:
        daily = {}
        for d in sorted(byday):
            r = next((x for x in byday[d] if g102.sized(x)
                      and bucket_label(x["et"]) == best_bucket), None)
            if r is not None:
                daily[d] = r["pnl"]
        pday = money(daily, n_days)
        policies.append(("C first in best window (%s) only" % best_bucket, pday, len(daily)))

        daily = {}
        for d in sorted(byday):
            cands = [x for x in byday[d] if g102.sized(x)]
            if not cands:
                continue
            pick = next((x for x in cands if bucket_label(x["et"]) == best_bucket), cands[0])
            daily[d] = pick["pnl"]
        pday = money(daily, n_days)
        policies.append(("D best window (%s), else first regardless" % best_bucket,
                         pday, len(daily)))

    out = {}
    for name, pday, nd in policies:
        print("%-46s $%7.0f/day  (%d/%d days traded)" % (name, pday, nd, n_days))
        out[name] = {"dollars_per_day": pday, "days_traded": nd}

    print("\nHonesty note: B is the winner of an unstated 18-slice scan (every 5-minute\n"
          "threshold from 09:30 to 10:55) and C/D pick the winner of the SAME 18-bucket\n"
          "scan Q1 already ran once. Same provenance as the chase veto (MASTER_SPEC.md\n"
          "sec2.3): not a fitted model, but not significance-tested either. Q5 below is\n"
          "the check for whether it survives, not proof that it does.")
    return out, best_bucket, (best_T, best_T_pday)


def q5_half_split(byday, best_bucket, best_T):
    """Does the scan-picked window/threshold survive OUT of the half of the book
    it was picked on? Same convention as research/x8_time_blocks.py's chronological
    split: n < 30 per half is printed but is not evidence."""
    print("\n=== Q5: does the Q4 scan survive a chronological split? ===")
    days = sorted(byday)
    mid = days[len(days) // 2]
    h1 = [d for d in days if d < mid]
    h2 = [d for d in days if d >= mid]
    print("half 1: %s .. %s (%d sessions)  half 2: %s .. %s (%d sessions)\n"
          % (h1[0], h1[-1], len(h1), h2[0], h2[-1], len(h2)))

    def pday_for(pick, half):
        total, nd = 0.0, 0
        for d in half:
            r = pick(d)
            if r is not None:
                total += r["pnl"]
                nd += 1
        return round(total / len(half), 2), nd

    arms = {
        "A first regardless":
            lambda d: next((x for x in byday[d] if g102.sized(x)), None),
        "B first at/after best T (%02d:%02d)" % (best_T[0] // 60, best_T[0] % 60):
            lambda d: next((x for x in byday[d] if g102.sized(x)
                            and minute_of(x["et"]) >= best_T[0]), None),
    }
    if best_bucket:
        arms["C first in best window (%s) only" % best_bucket] = (
            lambda d: next((x for x in byday[d] if g102.sized(x)
                            and bucket_label(x["et"]) == best_bucket), None))

    out = {}
    print("%-42s %14s %14s" % ("policy", "half 1 $/day", "half 2 $/day"))
    for name, pick in arms.items():
        p1, n1 = pday_for(pick, h1)
        p2, n2 = pday_for(pick, h2)
        both_positive = p1 > 0 and p2 > 0
        flag = "  (positive both halves)" if both_positive else ""
        print("%-42s %9.0f (n=%3d) %9.0f (n=%3d)%s" % (name, p1, n1, p2, n2, flag))
        out[name] = {"half1_pday": p1, "half1_days": n1,
                     "half2_pday": p2, "half2_days": n2,
                     "positive_both_halves": both_positive}
    return out


def main():
    b = json.load(open(BOOK, encoding="utf-8"))
    rows = b["trades"] if isinstance(b, dict) else b
    n_days = b["meta"]["sessions"]
    byday = g86.candidates(rows)

    bucket_stats, baseline_pday, _firsts = q1_buckets(byday, n_days)
    labels_by_bucket, n_judged, n_s = q2_his_labels(rows)
    scored, beats = q3_other_factors(byday, n_days, baseline_pday)
    policies, best_bucket, best_T = q4_day_end_policy(byday, n_days, bucket_stats,
                                                       baseline_pday)
    half_split = q5_half_split(byday, best_bucket, best_T)

    out = {
        "n_sessions": n_days,
        "baseline_first_of_day_pday": baseline_pday,
        "buckets": bucket_stats,
        "his_labels_by_bucket": labels_by_bucket,
        "judged_with_candidate": n_judged,
        "judged_s": n_s,
        "top_causal_features": [
            {"feature": "%s=%s" % kv, "per_covered_day": cov, "per_all_day": alld,
             "days": nd} for cov, alld, nd, kv in scored[:20]],
        "features_beating_first_of_day": len(beats),
        "day_end_policies": policies,
        "best_bucket": best_bucket,
        "best_T_minute": best_T[0], "best_T_pday": best_T[1],
        "half_split_check": half_split,
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = ["# g110 -- time of day, and what else separates a good S trade", "",
          "Book `bt2y_trades_retest_on.json`, %d sessions, size-gated on "
          "`signal_runner.min_risk_floor`, book (close) fill." % n_days, "",
          "## Q1 -- entry-minute buckets",
          "", "| bucket | n | mean R | win%% | >=2R alive | >=3R alive | $/day | days |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for bk in bucket_order(bucket_stats):
        s = bucket_stats[bk]
        md.append("| %s | %d | %+.3f | %.1f%% | %.1f%% | %.1f%% | $%.0f | %d |"
                  % (bk, s["n"], s["mean_r"], s["win_pct"], s["pct_2r_alive"],
                     s["pct_3r_alive"], s["dollars_per_day"], s["days_taken"]))
    md += ["", "Reference: first-of-day, any bucket: **$%.0f/day**." % baseline_pday, "",
          "## Q2 -- his S-rate by bucket (judged symbol-days, first size-gated candidate)",
          "", "| bucket | n | S-rate |", "|---|---:|---:|"]
    for bk in bucket_order(labels_by_bucket):
        e = labels_by_bucket[bk]
        md.append("| %s | %d | %.1f%% |" % (bk, e["n"], e["s_rate"]))
    md += ["", "## Q3 -- top causal feature-values by $/all-day", "",
          "| feature=value | $/covered | $/all-day | days |", "|---|---:|---:|---:|"]
    for cov, alld, nd, kv in scored[:20]:
        md.append("| %s=%s | $%.0f | $%.0f | %d |" % (kv[0], kv[1], cov, alld, nd))
    md += ["", "%d of %d scored feature-values beat first-of-day on an all-day basis."
          % (len(beats), len(scored)), "",
          "## Q4 -- day-end policy", "", "| policy | $/day | days traded |",
          "|---|---:|---:|"]
    for name, e in policies.items():
        md.append("| %s | $%.0f | %d/%d |"
                  % (name, e["dollars_per_day"], e["days_traded"], n_days))
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n  -> %s\n  -> %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
