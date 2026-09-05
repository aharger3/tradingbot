"""g202 refuter #2 -- multiplicity / sampling-error attack on P3
(research/g173_shares_personal_refresh.md).

Lens: how many arms were tried, paired bootstrap over sessions, one-day
dominance, H1-to-select vs H1-to-validate.

Same fill as P3: signal bar CLOSE entry, stop_rule.stop_fill_price stops,
size-gated on signal_runner.min_risk_floor, 1R = $1,000, one-trade-a-day unit
research/omen_metrics.first_of_day_arm (via g116 build_arm A_base), book
research/bt2y_trades_retest_on.json. H1 = day < 2025-09-01.

Run: python research/g202_p3_refute2.py
"""
from __future__ import annotations
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from g116_sizing_kelly_options import load_rows, build_arm
from g120_prop_arms import shares_for
from omen_metrics import evaluate_prop_challenge

OUT = os.path.join(HERE, "g202_p3_refute2.json")
SPLIT = "2025-09-01"
SEED = 20260905

TTP_ROWS = [
    ("TTP 25K MAX day",   25000,  1500, 250,  750,  60,  97),
    ("TTP 50K MAX day",   50000,  3000, 500,  1500, 60,  230),
    ("TTP 100K MAX day",  100000, 6000, 1000, 3000, 60,  435),
    ("TTP 200K MAX day",  200000, 12000, 2000, 6000, 60,  1100),
    ("TTP 25K FLEX day",  25000,  1500, 500,  1000, 120, 97),
    ("TTP 50K FLEX day",  50000,  3000, 1000, 2000, 120, 230),
    ("TTP 100K FLEX day", 100000, 6000, 2000, 4000, 120, 435),
    ("TTP 200K FLEX day", 200000, 12000, 4000, 8000, 120, 1100),
]
KW_BASE = dict(consistency_pct=1.0, dd_mode="eod", min_trading_days=0)


def series_for(arm, account, dll_cap_pct=None):
    """dll_cap_pct=None reproduces g173 exactly (no daily-loss-limit share
    cap). dll_cap_pct=<pct> restores g120 arm 2's ADVERSARIAL FIX #2, which
    g173's own report claims is carried over unchanged."""
    out = []
    for r in arm:
        sh = shares_for(r["entry"], r["stop"], account=account,
                        daily_loss_limit_pct=dll_cap_pct)
        risk = sh * abs(r["entry"] - r["stop"])
        out.append(dict(day=r["day"], pnl=r["r"] * risk, risk=risk, r=r["r"]))
    return out


def verdict(series, account, target, dll, mdd):
    kw = dict(profit_target_pct=target / account, daily_loss_limit_pct=dll / account,
              trailing_dd_pct=mdd / account, account_size=account, **KW_BASE)
    res = evaluate_prop_challenge([(s["day"], s["pnl"]) for s in series], **kw)
    return bool(res["passed"]), res["fail_reason"], res["fail_day"]


def main():
    rnd = random.Random(SEED)
    rows = load_rows()
    arm = build_arm(rows, keep=lambda r: True)
    h1 = [r for r in arm if r["day"] < SPLIT]
    h2 = [r for r in arm if r["day"] >= SPLIT]
    out = {"meta": dict(n_full=len(arm), n_h1=len(h1), n_h2=len(h2),
                        d0=arm[0]["day"], dN=arm[-1]["day"], seed=SEED)}

    # ---- A. the fee identity: is "net -$97..-$1,100" a measurement? -------
    g173 = json.load(open(os.path.join(HERE, "g173_shares_personal_refresh.json")))
    fee_identity = all(r["net_dollars_after_cost"] == -r["eval_fee"]
                       for sl in ("full", "H1", "H2") for r in g173["ttp_shares"][sl])
    out["A_fee_identity"] = dict(
        every_reported_net_equals_minus_the_eval_fee=fee_identity,
        fees=[r[6] for r in TTP_ROWS],
        distinct_nets=sorted({r["net_dollars_after_cost"]
                              for sl in ("full", "H1", "H2")
                              for r in g173["ttp_shares"][sl]}))

    # ---- B. the missing daily-loss-limit share cap ------------------------
    B = []
    for name, acct, tgt, dll, mdd, maxd, fee in TTP_ROWS:
        s_g173 = series_for(arm, acct, None)
        s_fix = series_for(arm, acct, dll / acct)
        p0, f0, d0_ = verdict(s_g173, acct, tgt, dll, mdd)
        p1, f1, d1_ = verdict(s_fix, acct, tgt, dll, mdd)
        over = sum(1 for s in s_g173 if s["risk"] > dll)
        B.append(dict(name=name, dll=dll,
                      g173_max_risk=round(max(s["risk"] for s in s_g173), 2),
                      trades_sized_over_the_daily_loss_limit=over,
                      pct_over=round(100.0 * over / len(s_g173), 1),
                      g173_verdict=("PASS" if p0 else "FAIL(%s)" % f0),
                      dll_capped_verdict=("PASS" if p1 else "FAIL(%s)" % f1),
                      dll_capped_fail_day=d1_))
    out["B_dll_share_cap"] = B

    # ---- C. rolling start dates (P3 evaluates exactly ONE start) ----------
    C = []
    for name, acct, tgt, dll, mdd, maxd, fee in TTP_ROWS:
        for tag, cap_pct in (("g173_uncapped", None), ("dll_capped", dll / acct)):
            ser = series_for(arm, acct, cap_pct)
            for enforce in (False, True):
                npass = ntot = 0
                for i in range(len(ser)):
                    sub = ser[i:i + maxd] if enforce else ser[i:]
                    if enforce and len(sub) < maxd:
                        break
                    if not sub:
                        break
                    p, _, _ = verdict(sub, acct, tgt, dll, mdd)
                    ntot += 1
                    npass += int(p)
                C.append(dict(name=name, sizing=tag,
                              window=("plan max_days=%d" % maxd) if enforce else "to book end",
                              starts=ntot, passes=npass,
                              pass_rate_pct=round(100.0 * npass / ntot, 1) if ntot else None))
    out["C_rolling_starts"] = C

    # ---- D. personal $10k: sampling error on $/day ------------------------
    Rs = [r["r"] for r in arm]
    n = len(Rs)
    mean_r = sum(Rs) / n
    sd = math.sqrt(sum((x - mean_r) ** 2 for x in Rs) / (n - 1))
    per_day_1000 = mean_r * 1000.0
    B_ITER = 20000
    boots = []
    for _ in range(B_ITER):
        s = 0.0
        for _ in range(n):
            s += Rs[rnd.randrange(n)]
        boots.append(s / n * 1000.0)
    boots.sort()
    lo, hi = boots[int(0.025 * B_ITER)], boots[int(0.975 * B_ITER)]
    p_le_zero = sum(1 for b in boots if b <= 0) / B_ITER
    order = sorted(range(n), key=lambda i: -Rs[i])
    tot = sum(Rs) * 1000.0
    top1 = Rs[order[0]] * 1000.0
    top5 = sum(Rs[i] for i in order[:5]) * 1000.0
    out["D_personal_sampling"] = dict(
        n_sessions=n, mean_R=round(mean_r, 5), sd_R=round(sd, 4),
        dollars_per_day_at_1000=round(per_day_1000, 2),
        dollars_per_day_at_100=round(per_day_1000 / 10.0, 2),
        se_dollars_per_day=round(sd / math.sqrt(n) * 1000.0, 2),
        boot_ci95=[round(lo, 2), round(hi, 2)],
        boot_p_le_zero=round(p_le_zero, 4),
        total_dollars_at_1000=round(tot, 2),
        best_single_day_dollars=round(top1, 2),
        best_day_pct_of_total=round(100.0 * top1 / tot, 1) if tot else None,
        top5_pct_of_total=round(100.0 * top5 / tot, 1) if tot else None,
        total_without_best_day=round(tot - top1, 2),
        per_day_without_best_day=round((tot - top1) / (n - 1), 2))

    # ---- E. the 216% drawdown is one ordering -----------------------------
    def maxdd(seq, risk=1000.0, acct=10000.0):
        eq = acct
        peak = acct
        mdd_ = 0.0
        for r in seq:
            eq += r * risk
            peak = max(peak, eq)
            mdd_ = max(mdd_, peak - eq)
        return mdd_
    actual = maxdd(Rs)
    shuf = []
    for _ in range(2000):
        c = Rs[:]
        rnd.shuffle(c)
        shuf.append(maxdd(c))
    shuf.sort()
    out["E_drawdown_order"] = dict(
        actual_maxdd=round(actual, 2), actual_pct_of_10k=round(actual / 100.0, 1),
        shuffle_median=round(shuf[1000], 2),
        shuffle_p05=round(shuf[100], 2), shuffle_p95=round(shuf[1900], 2),
        pct_of_shuffles_worse=round(100.0 * sum(1 for x in shuf if x > actual) / len(shuf), 1))

    # ---- F. H1 as replication? -------------------------------------------
    same_start = all(g173["ttp_shares"]["H1"][i]["months_to_event"] ==
                     g173["ttp_shares"]["full"][i]["months_to_event"]
                     for i in range(8))
    out["F_h1_is_a_prefix"] = dict(
        h1_first_day=h1[0]["day"], full_first_day=arm[0]["day"],
        h1_starts_on_the_same_day_as_full=(h1[0]["day"] == arm[0]["day"]),
        h1_and_full_identical_months_to_event_on_all_8_rows=same_start,
        cells_reported=8 * 3 + 2 * 3,
        independent_start_dates_evaluated=1)

    json.dump(out, open(OUT, "w"), indent=1)
    print(json.dumps(out, indent=1))
    print("\nwrote", OUT)
    return out


if __name__ == "__main__":
    main()
