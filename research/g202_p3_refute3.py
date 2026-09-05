"""g202 P3 refuter #3 -- reproduce g173 byte-for-byte, then null control + adversarial variants.

Lens: reproduce from the named script, test a placebo that should produce zero,
and one adversarial variant.

Fill throughout: signal bar CLOSE entry, stop_rule.stop_fill_price stops,
size-gated on signal_runner.min_risk_floor, book research/bt2y_trades_retest_on.json
(RETEST_REQUIRED=1), one-trade-a-day arm research/omen_metrics.first_of_day_arm via
g116_sizing_kelly_options.build_arm(keep=all). H1/H2 split at 2025-09-01.

    python research/g202_p3_refute3.py
"""
from __future__ import annotations

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from g116_sizing_kelly_options import load_rows, build_arm, months_between
from g120_prop_arms import shares_for, pass_day_series, personal_arm_result
from g173_shares_personal_refresh import TTP_ROWS, TTP_KW_BASE, split_h1_h2

OUT = os.path.join(HERE, "g202_p3_refute3.json")


def series_for(arm, account, dll_cap_pct=None):
    """g173's pool_series_for_account, with an optional daily-loss-limit share
    cap -- the ADVERSARIAL FIX #2 that g120.pool_series applies and g173 does
    NOT, even though g173's own report says the mechanics are unchanged."""
    out = []
    for r in arm:
        shares = shares_for(r["entry"], r["stop"], account=account,
                            daily_loss_limit_pct=dll_cap_pct)
        risk_dollars = shares * abs(r["entry"] - r["stop"])
        out.append(dict(day=r["day"], sym=r["sym"], shares=shares,
                        risk_dollars=risk_dollars, pnl=r["r"] * risk_dollars, r=r["r"]))
    return out


def ttp_verdict(series, account, target, dll, mdd, fee):
    if not series:
        return dict(n=0)
    kw = dict(profit_target_pct=target / account, daily_loss_limit_pct=dll / account,
              trailing_dd_pct=mdd / account, **TTP_KW_BASE)
    cum, s = [], 0.0
    for row in series:
        s += row["pnl"]
        cum.append(s)
    pd_, pi, res = pass_day_series(series, account_size=account, **kw)
    passed = bool(res["passed"])
    d0 = series[0]["day"]
    if passed:
        months, net = months_between(d0, pd_), cum[pi - 1] - fee
    else:
        fd = res["fail_day"]
        months = months_between(d0, fd) if fd else months_between(d0, series[-1]["day"])
        net = -fee
    risks = [r["risk_dollars"] for r in series]
    return dict(n=len(series), passed=passed, fail_reason=res["fail_reason"],
                fail_day=res["fail_day"], months=round(months, 3),
                net_after_cost=round(net, 2),
                risk_mean=round(sum(risks) / len(risks), 2),
                risk_max=round(max(risks), 2),
                risk_over_dll_frac=round(sum(1 for x in risks if x > dll) / len(risks), 4),
                dll=dll)


def sweep(arm, dll_cap_pct=None):
    rows = []
    for name, acct, target, dll, mdd, _days, fee in TTP_ROWS:
        ser = series_for(arm, acct, dll_cap_pct=(dll / acct) if dll_cap_pct == "row" else dll_cap_pct)
        v = ttp_verdict(ser, acct, target, dll, mdd, fee)
        v["name"] = name
        rows.append(v)
        print("  %-18s %-5s %-26s months=%-7s net=%-9s risk_mean=%-9s over_DLL=%.0f%%"
              % (name, "PASS" if v["passed"] else "FAIL", v["fail_reason"] or "-",
                 v["months"], v["net_after_cost"], v["risk_mean"],
                 100 * v["risk_over_dll_frac"]))
    return rows


def personal(arm):
    p = personal_arm_result(arm)
    for k, d in p.items():
        print("  %-18s total=$%-11.0f maxDD=$%-10.0f min_eq=$%-10.0f wiped=%s"
              % (k, d["total_dollars"], d["max_drawdown_dollars"],
                 d["min_equity_ever"], "YES" if d["wiped"] else "no"))
    return p


def main():
    res = {}
    rows = load_rows()
    arm = build_arm(rows, keep=lambda r: True)
    sl = split_h1_h2(arm)
    print("arm n=%d (%s..%s) H1=%d H2=%d"
          % (len(arm), arm[0]["day"], arm[-1]["day"], len(sl["H1"]), len(sl["H2"])))
    res["meta"] = dict(n=len(arm), n_h1=len(sl["H1"]), n_h2=len(sl["H2"]),
                       d0=arm[0]["day"], d1=arm[-1]["day"])

    # ---------------- A. reproduce (g173 as shipped) ----------------
    print("\n=== A. reproduce g173 as shipped (no DLL share cap) ===")
    res["A_reproduce"] = sweep(arm, dll_cap_pct=None)

    # ---------------- B. NULL CONTROL: zero-edge placebo ----------------
    # every trade closes at exactly 0R. Same 495 days, same symbols, same
    # entry/stop prices, same share counts -- only the outcome is neutered.
    # A working rig must report NO daily-loss breach and NO trailing-dd
    # breach; the only honest fail is profit_target_not_reached.
    print("\n=== B. NULL CONTROL: r=0 on every trade (should breach nothing) ===")
    zero = [dict(r0, r=0.0) for r0 in arm]
    res["B_null_zero"] = sweep(zero, dll_cap_pct=None)
    print("  personal:")
    res["B_null_zero_personal"] = personal(zero)

    # ---------------- C. NULL CONTROL 2: coin-flip trader ----------------
    # zero-expectancy trader: r = +1 / -1 at random, same sizing. If the FAIL
    # verdict carries information about OMEN's edge it should differ from A;
    # if it is a property of the position-size model it will be identical.
    print("\n=== C. NULL CONTROL 2: coin-flip trader r=+/-1, 200 seeds ===")
    tally = {}
    for seed in range(200):
        rnd = random.Random(seed)
        flip = [dict(r0, r=(1.0 if rnd.random() < 0.5 else -1.0)) for r0 in arm]
        for name, acct, target, dll, mdd, _d, fee in TTP_ROWS:
            v = ttp_verdict(series_for(flip, acct), acct, target, dll, mdd, fee)
            key = (name, "PASS" if v["passed"] else v["fail_reason"])
            tally[key] = tally.get(key, 0) + 1
    coin = {}
    for name, _a, _t, _dl, _m, _d, _f in TTP_ROWS:
        got = {k[1]: v for k, v in tally.items() if k[0] == name}
        coin[name] = got
        print("  %-18s %s" % (name, got))
    res["C_coinflip_200seeds"] = coin

    # ---------------- D. NULL CONTROL 3: a perfect trader ----------------
    # r=+2.0 every trade (the money gate, never a loser). The rig must be able
    # to emit a PASS at all, or "8 of 8 FAIL" is a stuck needle.
    print("\n=== D. NULL CONTROL 3: perfect trader r=+2.0 (rig must be able to PASS) ===")
    res["D_perfect"] = sweep([dict(r0, r=2.0) for r0 in arm], dll_cap_pct=None)

    # ---------------- E. ADVERSARIAL: reinstate the DLL share cap ----------
    # g120.pool_series caps shares so shares*|entry-stop| <= DLL. g173 dropped
    # that argument. Put it back -- this is the mechanic g173's report claims
    # it already has.
    print("\n=== E. ADVERSARIAL VARIANT: DLL share cap reinstated (g120 fix #2) ===")
    res["E_dll_capped"] = sweep(arm, dll_cap_pct="row")
    for half in ("H1", "H2"):
        print("  -- %s --" % half)
        res["E_dll_capped_" + half] = sweep(sl[half], dll_cap_pct="row")

    # ---------------- F. ADVERSARIAL: personal order-dependence -----------
    print("\n=== F. ADVERSARIAL: personal $10k, trade order shuffled (1000 seeds) ===")
    base = personal_arm_result(arm)
    print("  shipped order:")
    personal(arm)
    wipes = {"book_native_1000": 0, "conservative_1pct": 0}
    dd = {"book_native_1000": [], "conservative_1pct": []}
    for seed in range(1000):
        rnd = random.Random(10000 + seed)
        sh = list(arm)
        rnd.shuffle(sh)
        p = personal_arm_result(sh)
        for k in wipes:
            if p[k]["wiped"]:
                wipes[k] += 1
            dd[k].append(p[k]["max_drawdown_dollars"])
    for k in wipes:
        d = sorted(dd[k])
        print("  %-18s wiped in %d/1000 shuffles | maxDD median=$%.0f p95=$%.0f (shipped $%.0f)"
              % (k, wipes[k], d[500], d[950], base[k]["max_drawdown_dollars"]))
    res["F_shuffle"] = {k: dict(wiped_of_1000=wipes[k],
                                dd_median=round(sorted(dd[k])[500], 2),
                                dd_p95=round(sorted(dd[k])[950], 2),
                                dd_shipped=base[k]["max_drawdown_dollars"]) for k in wipes}

    # ---------------- G. is $1,000/trade executable on $10k? -------------
    # the shipped arm sizes a flat $1,000 forever even after equity falls to
    # $3,820 (full) / -$8,071 (H2). Re-run with the obvious real constraint:
    # you cannot risk more than the equity you have.
    print("\n=== G. ADVERSARIAL: personal $1,000/trade with equity-aware sizing ===")
    g = {}
    for label, a in (("full", arm), ("H1", sl["H1"]), ("H2", sl["H2"])):
        for mode in ("flat_1000_equity_capped", "fixed_10pct_of_equity"):
            eq, peak, mdd_, wiped = 10000.0, 10000.0, 0.0, False
            for r0 in a:
                if eq <= 0:
                    wiped = True
                    break
                risk = min(1000.0, eq) if mode == "flat_1000_equity_capped" else 0.10 * eq
                eq += r0["r"] * risk
                peak = max(peak, eq)
                mdd_ = max(mdd_, peak - eq)
                if eq <= 0:
                    wiped = True
            g["%s/%s" % (label, mode)] = dict(final=round(eq, 2), total=round(eq - 10000.0, 2),
                                              maxDD=round(mdd_, 2), wiped=wiped)
            print("  %-6s %-26s final=$%-11.0f total=$%-11.0f maxDD=$%-10.0f wiped=%s"
                  % (label, mode, eq, eq - 10000.0, mdd_, "YES" if wiped else "no"))
    res["G_equity_aware"] = g

    json.dump(res, open(OUT, "w"), indent=1, default=str)
    print("\nwrote", OUT)


if __name__ == "__main__":
    main()
