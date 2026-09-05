"""g202 refuter #1 (lookahead / leakage) against P3 =
research/g173_shares_personal_refresh.md.

Lens: any read past the bar the decision is made on, any fill that uses the
signal bar itself, any blacklisted field, and -- the same bug class one step
out -- any position size the account could not actually have carried at the
moment of entry (capital the arm does not have is future information about
the account, and it is exactly what the g120 "ADVERSARIAL FIX #2" existed to
stop).

Attacks:
  A. g173's pool_series_for_account() drops the daily-loss-limit share cap
     that g120's pool_series() passes. Re-run all 8 TTP rows WITH the cap.
  B. the personal $10k arm applies a flat $1,000 risk with NO buying-power
     constraint, while the same script enforces 4:1 buying power for TTP.
     Price the same arm with the $10k account's own 4:1 buying power.
  C. field audit: what the arm actually reads, blacklist check, causality of
     the prefix replay, and the traded/r-is-None survivorship filter.

Fill contract: signal bar CLOSE entry, stop_rule.stop_fill_price stops,
size-gated on signal_runner.min_risk_floor, book
research/bt2y_trades_retest_on.json (RETEST_REQUIRED=1), one-trade-a-day unit
= g116.build_arm(keep=True) (== the A_base / first_of_day arm g173 uses).
H1 = day < 2025-09-01, H2 = day >= 2025-09-01.

Run: python research/g202_p3_refute1.py
"""
from __future__ import annotations
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from g116_sizing_kelly_options import load_rows, build_arm, months_between
from g120_prop_arms import shares_for, pass_day_series, POOL_SHARE_CAP, POOL_BP_MULT
from g173_shares_personal_refresh import (TTP_ROWS, TTP_KW_BASE, H_SPLIT_DAY,
                                          pool_series_for_account)

OUT = os.path.join(HERE, "g202_p3_refute1.json")
PERSONAL_ACCOUNT = 10000.0


def slices_of(arm):
    return {"full": arm,
            "H1": [r for r in arm if r["day"] < H_SPLIT_DAY],
            "H2": [r for r in arm if r["day"] >= H_SPLIT_DAY]}


# ---------------------------------------------------------------- A
def pool_series_capped(arm, account, dll_pct):
    """g120's pool_series(), generalised to any account -- the DLL share cap
    that g173 dropped is passed through."""
    out = []
    for r in arm:
        shares = shares_for(r["entry"], r["stop"], account=account,
                            daily_loss_limit_pct=dll_pct)
        risk = shares * abs(r["entry"] - r["stop"])
        out.append(dict(day=r["day"], sym=r["sym"], shares=shares,
                        risk_dollars=risk, pnl=r["r"] * risk, r=r["r"]))
    return out


def ttp_eval(series, name, account, target, dll, mdd, max_days, fee):
    if not series:
        return dict(name=name, n_trades=0)
    kw = dict(profit_target_pct=target / account,
              daily_loss_limit_pct=dll / account,
              trailing_dd_pct=mdd / account, **TTP_KW_BASE)
    d0, dl = series[0]["day"], series[-1]["day"]
    cum, s = [], 0.0
    for row in series:
        s += row["pnl"]
        cum.append(s)
    pd_, pi, res = pass_day_series(series, account_size=account, **kw)
    passed = bool(res["passed"])
    if passed:
        months = months_between(d0, pd_)
        net = cum[pi - 1] - fee
    else:
        fd = res["fail_day"]
        months = months_between(d0, fd) if fd else months_between(d0, dl)
        net = -fee
    risks = [r["risk_dollars"] for r in series]
    return dict(name=name, account=account, n_trades=len(series),
                dll_dollars=dll,
                risk_max=round(max(risks), 2),
                risk_mean=round(sum(risks) / len(risks), 2),
                n_risk_over_dll=sum(1 for x in risks if x > dll),
                passed=passed, fail_reason=res["fail_reason"],
                fail_day=res.get("fail_day"),
                months_to_event=round(months, 3),
                window_days_used=pi, eval_window_days=max_days,
                net_after_cost=round(net, 2),
                total_if_ungated=round(cum[-1], 2))


# ---------------------------------------------------------------- B
def personal_arm(arm, risk, bp_mult=None, account=PERSONAL_ACCOUNT,
                 share_cap=None):
    """risk = flat dollars at risk per trade. If bp_mult is given, the share
    count is capped at the account's own buying power (and optionally the
    same 1,000-share cap the TTP arm carries), so a trade that would need
    more notional than the account can hold is scaled down, not taken whole."""
    equity, peak, mn = account, account, account
    maxdd, wiped, wipe_day = 0.0, False, None
    n_capped = 0
    tot_notional_needed = 0.0
    for r in arm:
        rps = abs(r["entry"] - r["stop"])
        eff = risk
        if bp_mult and rps > 0:
            want = risk / rps                       # shares needed to risk `risk`
            tot_notional_needed += want * r["entry"]
            allowed = math.floor(bp_mult * account / r["entry"])
            if share_cap:
                allowed = min(allowed, share_cap)
            if allowed < want:
                n_capped += 1
                eff = allowed * rps                 # what the account can carry
        equity += r["r"] * eff
        peak = max(peak, equity)
        maxdd = max(maxdd, peak - equity)
        if equity < mn:
            mn = equity
        if equity <= 0 and not wiped:
            wiped, wipe_day = True, r["day"]
    n = len(arm)
    return dict(n_trades=n, risk_per_trade=risk,
                bp_mult=bp_mult, n_trades_capped_by_bp=n_capped,
                pct_capped=round(100.0 * n_capped / n, 1) if n else None,
                mean_notional_needed=(round(tot_notional_needed / n, 0)
                                      if (n and bp_mult) else None),
                total_dollars=round(equity - account, 2),
                per_day=round((equity - account) / n, 2) if n else None,
                max_dd_dollars=round(maxdd, 2),
                max_dd_pct_acct=round(maxdd / account * 100, 2),
                min_equity=round(mn, 2), wiped=wiped, wipe_day=wipe_day)


def main():
    book = json.load(open(os.path.join(HERE, "bt2y_trades_retest_on.json")))
    traded = [r for r in book["trades"] if r.get("traded")]
    dropped_r_none = sum(1 for r in traded if r.get("r") is None)

    rows = load_rows()
    arm = build_arm(rows, keep=lambda r: True)
    sl = slices_of(arm)
    out = {"meta": dict(n_full=len(arm), n_h1=len(sl["H1"]), n_h2=len(sl["H2"]),
                        first=arm[0]["day"], last=arm[-1]["day"],
                        traded_rows=len(traded), traded_rows_r_none=dropped_r_none)}
    print("arm: full=%d H1=%d H2=%d  (%s..%s)"
          % (len(arm), len(sl["H1"]), len(sl["H2"]), arm[0]["day"], arm[-1]["day"]))

    # ---- C: field / lookahead audit -------------------------------------
    consumed = sorted({"day", "et", "sym", "entry", "stop", "r", "traded"})
    blacklist = ["spy_trend", "vol_regime", "out", "exit", "pnl", "cls", "status", "scaled"]
    out["audit"] = dict(fields_consumed_by_arm=consumed,
                        blacklisted_fields_consumed=[f for f in blacklist if f in consumed],
                        traded_rows_with_r_none=dropped_r_none)
    print("audit: consumed=%s\n       blacklisted-consumed=%s  traded rows dropped for r=None: %d"
          % (consumed, out["audit"]["blacklisted_fields_consumed"], dropped_r_none))

    # ---- A: DLL share cap restored --------------------------------------
    print("\n=== A: TTP with the daily-loss-limit share cap RESTORED (g120 behaviour) ===")
    a = {}
    for sname, sarm in sl.items():
        rowsout = []
        for (name, acct, tgt, dll, mdd, mdays, fee) in TTP_ROWS:
            asis = ttp_eval(pool_series_for_account(sarm, acct), name, acct,
                            tgt, dll, mdd, mdays, fee)
            fixed = ttp_eval(pool_series_capped(sarm, acct, dll / acct), name, acct,
                             tgt, dll, mdd, mdays, fee)
            rowsout.append(dict(row=name, as_published=asis, with_dll_cap=fixed))
            if sname == "full":
                print("  %-17s published: %-24s %5.1fmo riskmax=$%-9.0f over-DLL=%3d | "
                      "capped: %-24s %5.1fmo riskmax=$%.0f"
                      % (name,
                         ("PASS" if asis["passed"] else "FAIL(%s)" % asis["fail_reason"]),
                         asis["months_to_event"], asis["risk_max"], asis["n_risk_over_dll"],
                         ("PASS" if fixed["passed"] else "FAIL(%s)" % fixed["fail_reason"]),
                         fixed["months_to_event"], fixed["risk_max"]))
        a[sname] = rowsout
    out["A_ttp_dll_cap"] = a

    # ---- B: personal arm, buying power ----------------------------------
    print("\n=== B: personal $10k -- flat risk vs the account's own 4:1 buying power ===")
    b = {}
    for sname, sarm in sl.items():
        d = {}
        for key, risk in (("book_native_1000", 1000.0), ("conservative_1pct", 100.0)):
            d[key + "__as_published"] = personal_arm(sarm, risk)
            d[key + "__bp_4x"] = personal_arm(sarm, risk, bp_mult=4.0)
            d[key + "__bp_4x_sharecap"] = personal_arm(sarm, risk, bp_mult=4.0,
                                                       share_cap=POOL_SHARE_CAP)
        b[sname] = d
        if sname == "full":
            for k, v in d.items():
                print("  %-36s $/day=%-9s total=$%-10s capped=%s%% maxDD=$%-9s minEq=$%s"
                      % (k, v["per_day"], v["total_dollars"], v["pct_capped"],
                         v["max_dd_dollars"], v["min_equity"]))
    out["B_personal_buying_power"] = b

    # ---- D: the personal arm keeps trading past its own wipe -------------
    # g120 fixed exactly this for the prop arms ("a FAILed eval stops trading
    # the day it breaches, so nothing past that day is real") and did NOT fix
    # it for the personal arm. Report how much of each slice's P&L is booked
    # after equity first hits <= 0.
    print("\n=== D: personal arm P&L booked AFTER the account is already wiped ===")
    d = {}
    for sname, sarm in sl.items():
        eq, wipe_i, peak = PERSONAL_ACCOUNT, None, PERSONAL_ACCOUNT
        for i, r in enumerate(sarm):
            eq += r["r"] * 1000.0
            peak = max(peak, eq)
            if eq <= 0 and wipe_i is None:
                wipe_i = i
        if wipe_i is None:
            d[sname] = dict(wiped=False, peak_equity=round(peak, 2))
            print("  %-5s not wiped; peak equity $%.0f, DD as %%-of-peak = %.1f%%"
                  % (sname, peak,
                     100.0 * b[sname]["book_native_1000__as_published"]["max_dd_dollars"] / peak))
            continue
        pre = sum(r["r"] for r in sarm[:wipe_i + 1]) * 1000.0
        post = sum(r["r"] for r in sarm[wipe_i + 1:]) * 1000.0
        d[sname] = dict(wiped=True, wipe_day=sarm[wipe_i]["day"],
                        trades_before_wipe=wipe_i + 1,
                        trades_after_wipe=len(sarm) - wipe_i - 1,
                        pnl_to_wipe=round(pre, 2), pnl_after_wipe=round(post, 2),
                        peak_equity=round(peak, 2))
        print("  %-5s WIPED %s after %d trades; %d trades (%d%%) and $%.0f of P&L are booked "
              "on a dead account" % (sname, sarm[wipe_i]["day"], wipe_i + 1,
                                     len(sarm) - wipe_i - 1,
                                     100 * (len(sarm) - wipe_i - 1) // len(sarm), post))
    out["D_personal_post_wipe"] = d

    json.dump(out, open(OUT, "w"), indent=1)
    print("\nwrote", OUT)
    return out


if __name__ == "__main__":
    main()
