"""g173 -- shares prop (Trade The Pool) + personal $10k refresh, H1/H2 split.

P3 of the OMEN 9.0 spec. Same one-trade-a-day candidate stream as g120/g116:
`build_arm(rows, keep=lambda r: True)` -- the shipped A_base arm, first
size-gated candidate of the day, `research/bt2y_trades_retest_on.json`
(RETEST_REQUIRED=1, current shipped default).

What's new vs g120_prop_arms.py:
  1. Trade The Pool is repriced (g120 arm 2's `shares_for`/`pool_series` --
     shares = min(1000, floor(account*4/entry_price)), daily-loss-limit also
     caps the share count) across ALL EIGHT of that firm's real account/plan
     rows pulled from `research/g71_propfirm_sim.py::FIRMS` (25K/50K/100K/200K
     x MAX/FLEX day plans), not just one $25,000 pick.
  2. Personal $10k arm at $100 and $1,000 risk/trade (g120 arm 3, unchanged
     mechanics) reported alongside.
  3. Every arm is split H1 (2024-09-03..2025-08-31) / H2 (2025-09-01..
     2026-09-02) as well as reported full-book, per CLAUDE.md's H1/H2 rule.

Caveat carried from g71: each TTP row's own `max_days` (60 for MAX plans, 120
for FLEX) is a real evaluation-window clock this arm does NOT enforce --
`evaluate_prop_challenge` has no day-count cutoff, only PASS/FAIL conditions
on the equity curve. A `months_to_event` that implies more calendar days than
the plan allows is flagged `exceeds_plan_window` rather than silently
reported as a clean pass.

Run:
    python research/g173_shares_personal_refresh.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from g116_sizing_kelly_options import load_rows, build_arm, months_between
from g120_prop_arms import shares_for, pass_day_series, personal_arm_result, POOL_BP_MULT

OUT_JSON = os.path.join(HERE, "g173_shares_personal_refresh.json")
OUT_MD = os.path.join(HERE, "g173_shares_personal_refresh.md")

H_SPLIT_DAY = "2025-09-01"   # CLAUDE.md's H1/H2 split

# name, account, target$, daily_loss_limit$, max_drawdown$, max_days(eval
# window, NOT enforced here -- see module docstring), eval_fee$
# pulled verbatim from research/g71_propfirm_sim.py::FIRMS (TTP rows only)
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
# g120 arm 2's own choice, carried here unchanged: no consistency rule found
# for this firm in prop_firms_stocks.md, so consistency_pct=1.0 disables it;
# dd_mode="eod" trailing off peak equity (see g120_prop_arms.py docstring).
TTP_KW_BASE = dict(consistency_pct=1.0, dd_mode="eod", min_trading_days=0)


def split_h1_h2(arm):
    h1 = [r for r in arm if r["day"] < H_SPLIT_DAY]
    h2 = [r for r in arm if r["day"] >= H_SPLIT_DAY]
    return {"full": arm, "H1": h1, "H2": h2}


def pool_series_for_account(arm, account):
    out = []
    for r in arm:
        shares = shares_for(r["entry"], r["stop"], account=account)
        risk_dollars = shares * abs(r["entry"] - r["stop"])
        pnl = r["r"] * risk_dollars
        out.append(dict(day=r["day"], sym=r["sym"], shares=shares,
                        risk_dollars=risk_dollars, pnl=pnl, r=r["r"]))
    return out


def ttp_row_result(arm, name, account, target, dll, mdd, max_days, fee):
    if not arm:
        return dict(name=name, n_trades=0, note="no trades in this slice")
    series = pool_series_for_account(arm, account)
    kw = dict(profit_target_pct=target / account,
              daily_loss_limit_pct=dll / account,
              trailing_dd_pct=mdd / account, **TTP_KW_BASE)
    d0, d_last = series[0]["day"], series[-1]["day"]
    cum, s = [], 0.0
    for row in series:
        s += row["pnl"]
        cum.append(s)
    total_net_full = cum[-1]

    pd_, pi, res_at_pass = pass_day_series(series, account_size=account, **kw)
    passed = bool(res_at_pass["passed"])
    if passed:
        months = months_between(d0, pd_)
        equity_at_event = cum[pi - 1]
        net_after_cost = equity_at_event - fee
        window_days_used = pi
    else:
        fail_day = res_at_pass["fail_day"]
        months = months_between(d0, fail_day) if fail_day else months_between(d0, d_last)
        equity_at_event = 0.0
        net_after_cost = -fee
        window_days_used = None

    exceeds_window = bool(passed and window_days_used and window_days_used > max_days)
    risks = [row["risk_dollars"] for row in series]
    return dict(
        name=name, account_size=account, target=target, daily_loss_limit=dll,
        max_drawdown=mdd, eval_window_days=max_days, eval_fee=fee, params=kw,
        n_trades=len(series),
        risk_dollars_min=round(min(risks), 2), risk_dollars_mean=round(sum(risks) / len(risks), 2),
        risk_dollars_max=round(max(risks), 2),
        passed=passed, fail_reason=res_at_pass["fail_reason"],
        pass_day=pd_, pass_day_index=pi, window_days_used=window_days_used,
        exceeds_plan_window=exceeds_window,
        months_to_event=round(months, 3),
        total_net_dollars_full_book_if_ungated=round(total_net_full, 2),
        equity_at_pass_or_book_end=round(equity_at_event, 2),
        net_dollars_after_cost=round(net_after_cost, 2),
    )


def main():
    rows = load_rows()
    arm_full = build_arm(rows, keep=lambda r: True)
    slices = split_h1_h2(arm_full)
    print("A_base arm, RETEST_REQUIRED=1 book: full n=%d (%s..%s)  H1 n=%d  H2 n=%d"
          % (len(arm_full), arm_full[0]["day"], arm_full[-1]["day"],
             len(slices["H1"]), len(slices["H2"])))

    out = {"meta": dict(book="bt2y_trades_retest_on.json", split_day=H_SPLIT_DAY,
                        n_full=len(arm_full), n_h1=len(slices["H1"]), n_h2=len(slices["H2"]))}

    print("\n=== Trade The Pool, shares (g120 arm 2 rules), all 8 firm rows ===")
    ttp_out = {}
    for slice_name, sl_arm in slices.items():
        print("-- %s --" % slice_name)
        rows_out = []
        for spec in TTP_ROWS:
            res = ttp_row_result(sl_arm, *spec)
            rows_out.append(res)
            if res.get("n_trades", 0):
                print("     %-16s %-6s months=%s window_used=%s(cap %d) net_after_cost=%.0f"
                      % (res["name"], "PASS" if res["passed"] else "FAIL",
                         res["months_to_event"], res["window_days_used"], res["eval_window_days"],
                         res["net_dollars_after_cost"]))
            else:
                print("     %-16s (no trades in slice)" % res["name"])
        ttp_out[slice_name] = rows_out
    out["ttp_shares"] = ttp_out

    print("\n=== Personal $10k, $100 and $1,000 risk/trade (g120 arm 3) ===")
    personal_out = {}
    for slice_name, sl_arm in slices.items():
        if not sl_arm:
            personal_out[slice_name] = {}
            continue
        pers = personal_arm_result(sl_arm)
        personal_out[slice_name] = pers
        print("-- %s --" % slice_name)
        for key, d in pers.items():
            print("   %-20s risk=$%-6.0f total=$%-10.0f maxDD=$%-8.0f (%.2f%% acct) wiped=%s"
                  % (key, d["risk_per_trade"], d["total_dollars"], d["max_drawdown_dollars"],
                     d["max_drawdown_pct_of_account"], "YES" if d["wiped"] else "no"))
    out["personal"] = personal_out

    json.dump(out, open(OUT_JSON, "w"), indent=1)
    print("\nwrote", OUT_JSON)
    write_md(out)
    print("wrote", OUT_MD)
    return out


def _fmt_money(x):
    return "-" if x is None else ("$%s%.0f" % ("-" if x < 0 else "", abs(x)))


def write_md(out):
    meta = out["meta"]
    lines = []
    lines.append("# g173 -- shares prop (Trade The Pool) + personal $10k refresh\n")
    lines.append("What's different: Trade The Pool is now priced across all 8 real account/plan "
                 "rows (25K/50K/100K/200K x MAX/FLEX day), not one $25,000 pick, and every arm "
                 "carries H1/H2 alongside full-book -- same %d-session A_base candidate stream "
                 "(`research/bt2y_trades_retest_on.json`, RETEST_REQUIRED=1), split at %s "
                 "(H1 n=%d, H2 n=%d).\n"
                 % (meta["n_full"], meta["split_day"], meta["n_h1"], meta["n_h2"]))
    lines.append("Fill: signal bar CLOSE entry, `stop_rule.stop_fill_price` stops, size-gated "
                 "on `signal_runner.min_risk_floor`. Script: `research/g173_shares_personal_refresh.py`. "
                 "TTP shares mechanics (share cap, daily-loss-limit cap) and personal-account "
                 "mechanics are unchanged from `research/g120_prop_arms.py` (arm 2 / arm 3) -- "
                 "this file adds the firm-row sweep and the H1/H2 split.\n")

    lines.append("## Caveat\n")
    lines.append("Each TTP row's `max_days` (60 MAX / 120 FLEX) is a real evaluation-window "
                 "clock this arm does NOT enforce -- `evaluate_prop_challenge` has no day-count "
                 "cutoff. A pass whose `window_days_used` exceeds the plan's window is flagged "
                 "`exceeds_plan_window: true` below rather than silently counted as a clean "
                 "pass.\n")

    lines.append("## Trade The Pool, shares -- all 8 firm rows\n")
    for slice_name in ("full", "H1", "H2"):
        lines.append("### %s\n" % slice_name)
        lines.append("| firm/plan | account | n trades | verdict | months to event | "
                     "window used (cap) | net after cost |")
        lines.append("|---|---:|---:|---|---:|---|---:|")
        for r in out["ttp_shares"][slice_name]:
            if not r.get("n_trades"):
                lines.append("| %s | - | 0 | - | - | - | - |" % r["name"])
                continue
            verdict = "PASS" if r["passed"] else "FAIL (%s)" % r["fail_reason"]
            if r.get("exceeds_plan_window"):
                verdict += " *exceeds plan window*"
            window = ("%s (cap %d)" % (r["window_days_used"], r["eval_window_days"])
                      if r["window_days_used"] else "- (cap %d)" % r["eval_window_days"])
            lines.append("| %s | $%s | %d | %s | %.1f | %s | %s |"
                         % (r["name"], format(r["account_size"], ",.0f"), r["n_trades"], verdict,
                            r["months_to_event"], window, _fmt_money(r["net_dollars_after_cost"])))
        lines.append("")

    lines.append("## Personal $10k -- $100 and $1,000 risk/trade\n")
    for slice_name in ("full", "H1", "H2"):
        pers = out["personal"].get(slice_name) or {}
        lines.append("### %s\n" % slice_name)
        if not pers:
            lines.append("(no trades in this slice)\n")
            continue
        lines.append("| sizing | risk/trade | total $ | max DD $ | max DD % acct | wiped? |")
        lines.append("|---|---:|---:|---:|---:|---|")
        for key, d in pers.items():
            lines.append("| %s | $%.0f | %s | $%.0f | %.2f%% | %s |"
                         % (key, d["risk_per_trade"], _fmt_money(d["total_dollars"]),
                            d["max_drawdown_dollars"], d["max_drawdown_pct_of_account"],
                            "YES" if d["wiped"] else "no"))
        lines.append("")

    open(OUT_MD, "w").write("\n".join(lines))


if __name__ == "__main__":
    main()
