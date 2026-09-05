"""g202 -- REFUTER #2 of P3 (research/g173_shares_personal_refresh.md).

Lens: multiplicity and sampling error. Four attacks:

  A. START-DATE MULTIPLICITY. g173 evaluates each Trade The Pool row from
     exactly ONE start date -- day 0 of the book. n=1 per row. "Never
     passes on any of 8 rows" is then 8 correlated draws of a single
     sample, which is the same class of error that sank P1 ("window =
     min(252, n)" evaluated exactly one window). This re-runs every row
     from EVERY tradable start date, with each plan's own max_days
     evaluation window enforced as a real clock (g173 states it does not
     enforce it), and reports the all-starts pass rate.

  B. A DROPPED SIZING CAP. g173's `pool_series_for_account` calls
     `shares_for(entry, stop, account=account)` WITHOUT
     `daily_loss_limit_pct`, so g120's "ADVERSARIAL FIX #2" -- cap the
     share count so one trade's max loss cannot exceed the firm's own
     daily loss limit -- is silently not applied. The headline fail reason
     on 4 of 8 rows is `daily_loss_limit`. This re-runs every row with the
     cap restored, using each row's OWN stated limit.

  C. PERSONAL ARM SAMPLING ERROR. $3.56/day and $35.56/day are point
     estimates off 495 sessions. Paired bootstrap over sessions (the same
     resampled session set drives both sizings, so they stay paired),
     10,000 draws, plus leave-one-day-out dominance and the H1/H2 split.

  D. IN-SAMPLE HALF. The $35.56/day headline is the full book. H1/H2 are
     reported here as select-vs-validate, not as a footnote.

Fill: unchanged from g173 -- signal bar CLOSE entry, `stop_rule.stop_fill_price`
stops, size-gated on `signal_runner.min_risk_floor`, 1R = $1,000 on the
personal arm, book `research/bt2y_trades_retest_on.json` (RETEST_REQUIRED=1),
one-trade-a-day unit `research/omen_metrics.first_of_day_arm` via
g116 `build_arm(keep=lambda r: True)` (A_base).

Run:  python research/g202_p3_refute2.py
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from omen_metrics import evaluate_prop_challenge
from g116_sizing_kelly_options import load_rows, build_arm, months_between
from g120_prop_arms import shares_for, pass_day_series, personal_arm_result
from g173_shares_personal_refresh import TTP_ROWS, TTP_KW_BASE, H_SPLIT_DAY

OUT_JSON = os.path.join(HERE, "g202_p3_refute2.json")
SEED = 20260905
N_BOOT = 10000


# ---------------------------------------------------------------- sizing
def series_for(arm, account, dll_dollars=None):
    """g173's own series builder. dll_dollars=None reproduces g173 exactly
    (no daily-loss-limit share cap). Passing the row's own limit restores
    g120's ADVERSARIAL FIX #2."""
    out = []
    for r in arm:
        kw = {}
        if dll_dollars is not None:
            kw["daily_loss_limit_pct"] = dll_dollars / account
        sh = shares_for(r["entry"], r["stop"], account=account, **kw)
        risk = sh * abs(r["entry"] - r["stop"])
        out.append(dict(day=r["day"], sym=r["sym"], shares=sh,
                        risk_dollars=risk, pnl=r["r"] * risk, r=r["r"]))
    return out


def eval_row(series, account, target, dll, mdd):
    kw = dict(profit_target_pct=target / account,
              daily_loss_limit_pct=dll / account,
              trailing_dd_pct=mdd / account, **TTP_KW_BASE)
    pd_, pi, res = pass_day_series(series, account_size=account, **kw)
    return bool(res["passed"]), res["fail_reason"], pd_, pi


def cal_days(d0, d1):
    a = date(*map(int, d0.split("-")))
    b = date(*map(int, d1.split("-")))
    return (b - a).days


# ------------------------------------------------ A: all start dates
def all_starts(series, account, target, dll, mdd, max_days):
    """Every tradable start date. The plan's max_days is enforced as a real
    calendar-day evaluation clock: a start that has not passed within
    max_days of its first trade is a FAIL (window expired), which is the
    STRICTER reading -- g173 enforces no clock at all."""
    kw = dict(profit_target_pct=target / account,
              daily_loss_limit_pct=dll / account,
              trailing_dd_pct=mdd / account, **TTP_KW_BASE)
    n = len(series)
    passes, fails = 0, {}
    pass_starts = []
    for s in range(n):
        d0 = series[s]["day"]
        # trades inside this start's evaluation window
        win = [row for row in series[s:] if cal_days(d0, row["day"]) <= max_days]
        if not win:
            continue
        outcome, reason = None, None
        for i in range(1, len(win) + 1):
            res = evaluate_prop_challenge(
                [(row["day"], row["pnl"]) for row in win[:i]],
                account_size=account, **kw)
            if res["passed"]:
                outcome = "pass"
                break
            if res["fail_reason"] in ("daily_loss_limit", "trailing_drawdown"):
                outcome, reason = "fail", res["fail_reason"]
                break
        if outcome is None:
            outcome, reason = "fail", "window_expired"
        if outcome == "pass":
            passes += 1
            pass_starts.append(d0)
        else:
            fails[reason] = fails.get(reason, 0) + 1
    tried = passes + sum(fails.values())
    return dict(starts_tried=tried, passes=passes,
                pass_rate_pct=round(100.0 * passes / tried, 2) if tried else None,
                fail_breakdown=fails, first_pass_starts=pass_starts[:8])


# --------------------------------------------- C/D: personal sampling
def personal_boot(arm, risk, n_boot=N_BOOT, seed=SEED):
    rng = random.Random(seed)
    rs = [r["r"] for r in arm]
    n = len(rs)
    per_day = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            s += rs[rng.randrange(n)]
        per_day.append(s * risk / n)
    per_day.sort()
    lo = per_day[int(0.025 * n_boot)]
    hi = per_day[int(0.975 * n_boot)]
    p_le0 = sum(1 for v in per_day if v <= 0) / n_boot
    return dict(point=round(sum(rs) * risk / n, 2),
                ci95=[round(lo, 2), round(hi, 2)],
                p_le_zero=round(p_le0, 4))


def leave_one_day_out(arm, risk):
    tot = sum(r["r"] for r in arm) * risk
    n = len(arm)
    worst = None
    for r in arm:
        without = (tot - r["r"] * risk)
        share = (r["r"] * risk / tot) if tot else None
        if worst is None or (share is not None and share > worst[1]):
            worst = (r, share, without)
    r, share, without = worst
    return dict(top_day=r["day"], top_sym=r["sym"], top_r=round(r["r"], 3),
                top_day_dollars=round(r["r"] * risk, 2),
                pct_of_total=round(100 * share, 2) if share is not None else None,
                total_with=round(tot, 2), total_without=round(without, 2),
                per_day_with=round(tot / n, 2), per_day_without=round(without / (n - 1), 2))


def main():
    rows = load_rows()
    arm = build_arm(rows, keep=lambda r: True)
    h1 = [r for r in arm if r["day"] < H_SPLIT_DAY]
    h2 = [r for r in arm if r["day"] >= H_SPLIT_DAY]
    out = {"meta": dict(n_full=len(arm), n_h1=len(h1), n_h2=len(h2),
                        book="bt2y_trades_retest_on.json", seed=SEED, n_boot=N_BOOT,
                        span=[arm[0]["day"], arm[-1]["day"]])}
    print("arm n=%d  %s..%s  H1=%d H2=%d" % (len(arm), arm[0]["day"], arm[-1]["day"],
                                             len(h1), len(h2)))

    # ---- B: reproduce vs cap-restored, full book
    print("\n=== B: g173 sizing (no daily-loss-limit share cap) vs cap restored ===")
    b_rows = []
    for (name, acct, target, dll, mdd, max_days, fee) in TTP_ROWS:
        s_nocap = series_for(arm, acct, dll_dollars=None)
        s_cap = series_for(arm, acct, dll_dollars=dll)
        p0, r0, d0_, i0 = eval_row(s_nocap, acct, target, dll, mdd)
        p1, r1, d1_, i1 = eval_row(s_cap, acct, target, dll, mdd)
        over = sum(1 for x in s_nocap if x["risk_dollars"] > dll)
        b_rows.append(dict(name=name, account=acct, dll=dll,
                           g173_passed=p0, g173_fail_reason=r0,
                           capped_passed=p1, capped_fail_reason=r1,
                           trades_oversized_vs_dll=over, n=len(s_nocap),
                           mean_risk_nocap=round(sum(x["risk_dollars"] for x in s_nocap) / len(s_nocap), 2),
                           mean_risk_cap=round(sum(x["risk_dollars"] for x in s_cap) / len(s_cap), 2)))
        print("  %-17s g173=%-4s(%s)  capped=%-4s(%s)  oversized %d/%d"
              % (name, "PASS" if p0 else "FAIL", r0, "PASS" if p1 else "FAIL", r1,
                 over, len(s_nocap)))
    out["B_sizing_cap"] = b_rows

    # ---- A: all start dates, both sizings
    print("\n=== A: all-start-date sweep (max_days enforced as a real clock) ===")
    a_rows = []
    for (name, acct, target, dll, mdd, max_days, fee) in TTP_ROWS:
        rec = dict(name=name, account=acct, max_days=max_days)
        for tag, dllc in (("g173_sizing", None), ("capped_sizing", dll)):
            s = series_for(arm, acct, dll_dollars=dllc)
            rec[tag] = all_starts(s, acct, target, dll, mdd, max_days)
        a_rows.append(rec)
        print("  %-17s g173 %s/%s (%s%%)   capped %s/%s (%s%%)"
              % (name, rec["g173_sizing"]["passes"], rec["g173_sizing"]["starts_tried"],
                 rec["g173_sizing"]["pass_rate_pct"],
                 rec["capped_sizing"]["passes"], rec["capped_sizing"]["starts_tried"],
                 rec["capped_sizing"]["pass_rate_pct"]))
    out["A_all_starts"] = a_rows

    # ---- C/D: personal arm
    print("\n=== C/D: personal $10k -- bootstrap, dominance, halves ===")
    pers = {}
    for tag, sl in (("full", arm), ("H1", h1), ("H2", h2)):
        d = {}
        for key, risk in (("book_native_1000", 1000.0), ("conservative_1pct", 100.0)):
            d[key] = personal_boot(sl, risk)
            d[key]["n_sessions"] = len(sl)
        d["dominance_1000"] = leave_one_day_out(sl, 1000.0)
        pers[tag] = d
        print("  %-5s $1000/trade %s/day CI95 %s  P(<=0)=%.3f | $100/trade %s/day CI95 %s"
              % (tag, d["book_native_1000"]["point"], d["book_native_1000"]["ci95"],
                 d["book_native_1000"]["p_le_zero"],
                 d["conservative_1pct"]["point"], d["conservative_1pct"]["ci95"]))
        dm = d["dominance_1000"]
        print("        top day %s %s = %s%% of the total; without it %s/day"
              % (dm["top_day"], dm["top_sym"], dm["pct_of_total"], dm["per_day_without"]))
    out["CD_personal"] = pers

    # solvency detail g173's md dropped
    out["personal_solvency_full"] = {k: dict(min_equity_ever=v["min_equity_ever"],
                                             min_equity_pct=v["min_equity_pct_of_account"],
                                             min_equity_day=v["min_equity_day"],
                                             max_dd=v["max_drawdown_dollars"],
                                             wiped=v["wiped"])
                                     for k, v in personal_arm_result(arm).items()}
    print("\n  solvency (full book, g120 fields g173's md omitted):")
    for k, v in out["personal_solvency_full"].items():
        print("    %-18s min equity ever $%.0f (%.1f%% of acct) on %s"
              % (k, v["min_equity_ever"], v["min_equity_pct"], v["min_equity_day"]))

    json.dump(out, open(OUT_JSON, "w"), indent=1)
    print("\nwrote", OUT_JSON)
    return out


if __name__ == "__main__":
    main()
