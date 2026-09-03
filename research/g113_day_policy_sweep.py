"""g113_day_policy_sweep.py -- SWEEP: day_policy.

One-and-done variants requested for the 2026-09-03 round, scored on
research/bt2y_trades_retest_on.json (the committed book, 498 sessions,
honest close-fill) via research/omen_metrics.py so every number here is
directly comparable to the other eleven sweeps run tonight.

Headline is EV/R (win% * avg_win_R - loss% * avg_loss_R), size-gated on
signal_runner.min_risk_floor. $/day is a supporting row only.

Arms (7 requested, some expand into sub-variants):
  1. first candidate of the day (shipped)              -- baseline
  2. first candidate after 09:45
  3. first candidate in the best time bucket            -- bucket picked
     by full-book EV/R, in-sample (flagged, not lookahead: the bucket is
     a fixed system constant applied identically to every day)
  4. best-graded of the first N                         -- two sub-forms:
       4a. LITERAL best-of-N (flagged UNSHIPPABLE -- lookahead: deciding
           which of N signals is "best" requires having seen the Nth
           before you can act on the 1st)
       4b. CAUSAL PROXY -- first candidate within the first N that clears
           a grade threshold, else the Nth. This is what "best-graded of
           first N" cashes out to for a real account and IS shippable.
     run for N in {2, 3, 5} x ladder in {sgrade S/A/C, legacy grade A/B}
  5. one trade then stop win-or-lose                    -- identical by
     construction to arm 1 (both cap at exactly one trade/day); reported
     once, flagged as a duplicate rather than re-scored
  6. stop after first win                                -- sequential
     intraday: keep taking candidates until one wins, then done for the
     day (a loss does not end the day)
  7. stop after first loss                                -- sequential
     intraday: keep taking candidates until one loses, then done for the
     day (a win does not end the day)

Candidate universe per day: status=='fired' & traded, OR status=='halted'
(same convention as omen_metrics.first_of_day_arm -- the loss-halt is a
shipped-policy artifact; under any of these alternate day policies that
halt may not have fired the same way, so those rows are live candidates
again). Sorted (day, et, sym) -- arrival order, causal.

    python research/g113_day_policy_sweep.py
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from research.omen_metrics import ev_r_scoreboard, evaluate_prop_challenge, MIN_RISK_FLOOR_SOURCE

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")


def ekey(r):
    return (r["day"], r["et"], r["sym"])


def candidates_by_day(rows):
    by_day = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            by_day[r["day"]].append(r)
    for day in by_day:
        by_day[day].sort(key=ekey)
    return by_day


# ---------------------------------------------------------------------
# arm builders -- each returns a chronologically-sorted list of book rows
# ---------------------------------------------------------------------

def arm_first_of_day(by_day):
    return [v[0] for day, v in sorted(by_day.items())]


def arm_first_after(by_day, cutoff="09:45"):
    out = []
    for day, v in sorted(by_day.items()):
        for r in v:
            if r["et"] >= cutoff:
                out.append(r)
                break
    return out


def bucket_of(et, width_min=15):
    hh, mm = int(et[:2]), int(et[3:5])
    total = hh * 60 + mm
    start = (total // width_min) * width_min
    return "%02d:%02d" % (start // 60, start % 60)


def best_time_bucket(by_day, width_min=15):
    """Full-book EV/R per bucket, over ALL candidates (not just firsts).
    In-sample selection -- flagged in the report, not a per-trade lookahead."""
    all_cand = [r for v in by_day.values() for r in v]
    buckets = defaultdict(list)
    for r in all_cand:
        buckets[bucket_of(r["et"], width_min)].append(r)
    scored = {}
    for b, rows in buckets.items():
        sb = ev_r_scoreboard(rows, size_gate=True)
        if sb["n"] >= 30:  # minimum support to call a bucket "best"
            scored[b] = sb["ev_r"]
    if not scored:
        return None, {}
    best = max(scored, key=scored.get)
    return best, scored


def arm_first_in_bucket(by_day, bucket, width_min=15):
    out = []
    for day, v in sorted(by_day.items()):
        for r in v:
            if bucket_of(r["et"], width_min) == bucket:
                out.append(r)
                break
    return out


GRADE_RANK_LEGACY = {"A+": 0, "A": 1, "B": 2, "C": 3, "X": 4}
GRADE_RANK_S = {"S": 0, "A": 1, "C": 2}


def arm_best_of_n_literal(by_day, n, ladder_field, rank):
    """Non-causal reference: literally the best-graded row among the
    first N candidates of the day. UNSHIPPABLE (see module docstring)."""
    out = []
    for day, v in sorted(by_day.items()):
        window = v[:n]
        if not window:
            continue
        best = min(window, key=lambda r: (rank.get(r.get(ladder_field), 99),
                                           window.index(r)))
        out.append(best)
    return out


def arm_best_of_n_causal(by_day, n, ladder_field, rank, threshold_rank=0):
    """Shippable proxy: first candidate within the first N that meets the
    threshold grade (rank <= threshold_rank), else the Nth (last-seen) of
    the window -- both decisions are knowable at the moment they fire."""
    out = []
    for day, v in sorted(by_day.items()):
        window = v[:n]
        if not window:
            continue
        chosen = None
        for r in window:
            if rank.get(r.get(ladder_field), 99) <= threshold_rank:
                chosen = r
                break
        if chosen is None:
            chosen = window[-1]
        out.append(chosen)
    return out


def arm_stop_after_first_win(by_day):
    out = []
    for day, v in sorted(by_day.items()):
        for r in v:
            out.append(r)
            if r["r"] > 0:
                break
    return out


def arm_stop_after_first_loss(by_day):
    out = []
    for day, v in sorted(by_day.items()):
        for r in v:
            out.append(r)
            if r["r"] < 0:
                break
    return out


# ---------------------------------------------------------------------

RISK_LEVELS = (25, 50, 100, 250, 500, 1000, 2000, 5000)


def risk_sweep(rows, sessions, account_size=50000.0):
    """For one arm's R-stream, scan RISK_LEVELS and report every level's
    PASS/FAIL against the $50k eval (defaults). Below the size floor a
    dollar-per-trade choice is a sizing decision, not a signal quality
    one -- this is orthogonal to the per-share size gate already applied
    in ev_r_scoreboard."""
    from collections import defaultdict
    from research.omen_metrics import min_risk_floor
    by_day_r = defaultdict(float)
    for r in rows:
        if r.get("entry") is not None and r.get("stop") is not None:
            close = r.get("close", r["entry"])
            if abs(r["entry"] - r["stop"]) < min_risk_floor(close):
                continue
        rr = r.get("r")
        if rr is None:
            continue
        by_day_r[r["day"]] += rr
    dr = sorted(by_day_r.items())
    out = []
    for risk in RISK_LEVELS:
        daily = [(d, r * risk) for d, r in dr]
        pe = evaluate_prop_challenge(daily, account_size=account_size)
        out.append({"risk_per_trade": risk, "passed": pe["passed"],
                     "fail_reason": pe["fail_reason"], "fail_day": pe["fail_day"],
                     "final_equity_pct": pe["final_equity_pct"],
                     "max_drawdown_seen_pct": pe["max_drawdown_seen_pct"]})
    return out


def report_arm(name, rows, sessions, account_size=50000.0, risk_per_trade=1000.0,
                unshippable_reason=None, caution=None):
    sb = ev_r_scoreboard(rows, risk_dollars=risk_per_trade, sessions=sessions)
    trades_per_day = sb["n"] / sessions if sessions else None
    result = {
        "arm": name,
        "unshippable_reason": unshippable_reason,
        "caution": caution,
        "ev_r": sb["ev_r"],
        "n": sb["n"],
        "n_dropped_size_gate": sb["n_dropped_size_gate"],
        "trades_per_day": round(trades_per_day, 3) if trades_per_day is not None else None,
        "win_rate": sb["win_rate"],
        "avg_win_R": sb["avg_win_R"],
        "avg_loss_R": sb["avg_loss_R"],
        "profit_factor": sb["profit_factor"],
        "months_green": sb["months_green"],
        "expectancy_per_day": sb["expectancy_per_day"],
        "yearly_R": sb["yearly_R"],
        "max_drawdown_R": sb["max_drawdown_R"],
    }
    if unshippable_reason:
        result["prop_eval"] = None
        return result

    by_day_r = defaultdict(float)
    for r in rows:
        if r.get("entry") is not None and r.get("stop") is not None:
            close = r.get("close", r["entry"])
            from research.omen_metrics import min_risk_floor
            if abs(r["entry"] - r["stop"]) < min_risk_floor(close):
                continue
        rr = r.get("r")
        if rr is None:
            continue
        by_day_r[r["day"]] += rr
    daily = [(d, rr * risk_per_trade) for d, rr in sorted(by_day_r.items())]
    pe = evaluate_prop_challenge(daily, account_size=account_size)
    result["prop_eval"] = {
        "passed": pe["passed"],
        "fail_reason": pe["fail_reason"],
        "fail_day": pe["fail_day"],
        "final_equity_pct": pe["final_equity_pct"],
        "max_drawdown_seen_pct": pe["max_drawdown_seen_pct"],
    }
    result["risk_sweep"] = risk_sweep(rows, sessions, account_size)
    passing = [rs["risk_per_trade"] for rs in result["risk_sweep"] if rs["passed"]]
    result["passes_at_risk_per_trade"] = passing or None
    return result


def fmt_row(res):
    ev = "%+.4f" % res["ev_r"] if res["ev_r"] is not None else "n/a"
    tpd = "%.3f" % res["trades_per_day"] if res["trades_per_day"] is not None else "n/a"
    if res["unshippable_reason"]:
        pe = "UNSHIPPABLE: %s" % res["unshippable_reason"]
    elif res["prop_eval"] is None:
        pe = "-"
    else:
        p = res["prop_eval"]
        pe = "PASS" if p["passed"] else ("FAIL(%s)" % p["fail_reason"])
    cau = ("  [%s]" % res["caution"]) if res.get("caution") else ""
    passes = res.get("passes_at_risk_per_trade")
    pass_str = ("passes@$%s" % ",".join(str(x) for x in passes)) if passes else "passes@none"
    return "  %-42s ev_r=%-9s n=%-5d t/day=%-7s win=%-7s pf=%-7s months=%-7s %s %s%s" % (
        res["arm"][:42], ev, res["n"], tpd,
        ("%.3f" % res["win_rate"]) if res["win_rate"] is not None else "n/a",
        res["profit_factor"] if res["profit_factor"] is not None else "n/a",
        res["months_green"] or "n/a",
        pe, pass_str, cau,
    )


def main():
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    sessions = meta.get("sessions") or len({r["day"] for r in rows})
    by_day = candidates_by_day(rows)

    print("min_risk_floor source: %s" % MIN_RISK_FLOOR_SOURCE)
    print("book: %s -- %d sessions, %d candidate-days, %d total candidates\n"
          % (os.path.basename(BOOK_PATH), sessions, len(by_day),
             sum(len(v) for v in by_day.values())))

    results = []
    n_arms_tested = 0

    # 1. first of day (shipped baseline)
    r = report_arm("1. first candidate of day (shipped)",
                    arm_first_of_day(by_day), sessions)
    results.append(r); n_arms_tested += 1

    # 2. first after 09:45
    r = report_arm("2. first candidate after 09:45",
                    arm_first_after(by_day, "09:45"), sessions)
    results.append(r); n_arms_tested += 1

    # 3. first in best time bucket (in-sample bucket pick, flagged)
    best_bucket, bucket_scores = best_time_bucket(by_day, width_min=15)
    print("time-bucket EV/R (15-min, all candidates, n>=30 only):")
    for b in sorted(bucket_scores):
        mark = "  <== best" if b == best_bucket else ""
        print("    %-8s ev_r=%+.4f%s" % (b, bucket_scores[b], mark))
    print()
    r = report_arm("3. first candidate in best bucket (%s)" % best_bucket,
                    arm_first_in_bucket(by_day, best_bucket, 15), sessions,
                    caution="bucket selected in-sample off this same book; "
                            "needs an out-of-sample check before shipping")
    results.append(r); n_arms_tested += 1

    # 4. best-graded of first N -- literal (unshippable) + causal proxy
    ladders = [("sgrade (S/A/C)", "sgrade", GRADE_RANK_S),
               ("legacy grade (A/B present)", "grade", GRADE_RANK_LEGACY)]
    for n in (2, 3, 5):
        for lname, field, rank in ladders:
            lit = arm_best_of_n_literal(by_day, n, field, rank)
            r = report_arm("4a. LITERAL best-of-%d, %s" % (n, lname), lit, sessions,
                            unshippable_reason=("requires knowing signal %d before acting "
                                                 "on an earlier one in the window -- lookahead"
                                                 % n) if n > 1 else None)
            results.append(r); n_arms_tested += 1

            causal = arm_best_of_n_causal(by_day, n, field, rank, threshold_rank=0)
            r = report_arm("4b. causal proxy best-of-%d, %s" % (n, lname), causal, sessions)
            results.append(r); n_arms_tested += 1

    # 5. one trade then stop win-or-lose -- identical to arm 1 by construction
    one_and_done = arm_first_of_day(by_day)
    r = report_arm("5. one trade then stop win-or-lose", one_and_done, sessions,
                    caution="identical by construction to arm 1 (both cap at exactly "
                            "one trade/day) -- reported, not double-counted")
    results.append(r); n_arms_tested += 1

    # 6. stop after first win
    r = report_arm("6. stop after first win (keep trying through a loss)",
                    arm_stop_after_first_win(by_day), sessions)
    results.append(r); n_arms_tested += 1

    # 7. stop after first loss
    r = report_arm("7. stop after first loss (keep trying through a win)",
                    arm_stop_after_first_loss(by_day), sessions)
    results.append(r); n_arms_tested += 1

    print("=== day_policy sweep -- EV/R headline, %d arms tested ===" % n_arms_tested)
    for res in results:
        print(fmt_row(res))

    print("\nranked by EV/R (shippable arms only, literal best-of-N excluded):")
    shippable = [r for r in results if not r["unshippable_reason"]]
    shippable.sort(key=lambda r: (r["ev_r"] if r["ev_r"] is not None else -99), reverse=True)
    for res in shippable:
        print(fmt_row(res))

    out_path = os.path.join(HERE, "g113_day_policy_sweep_out.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"sessions": sessions, "n_arms_tested": n_arms_tested,
                    "bucket_scores": bucket_scores, "best_bucket": best_bucket,
                    "results": results}, f, indent=2)
    print("\nwrote %s" % out_path)


if __name__ == "__main__":
    main()
