"""G7.2 / options_props -- what a $10,000 self-funded options account actually supports.

Question: Austin has a $10,000 cash buffer. If he trades the OMEN book as 0DTE
ATM options in his OWN account (no prop firm), how much can he risk per trade
before the CASH DEBIT -- not the risk -- becomes the binding constraint?

Long options cannot be margined: Reg T requires options with 9 months or less to
expiry be paid for in full. So the account's cash balance is a hard ceiling on
the debit, and the debit is ~8x the risk on a 0DTE ATM contract.

This is a sizing calculator on the already-ratified book. It changes no engine
file, touches no mark file, and cannot move recall by construction.

Premiums come from `research/t7_real_contracts.py`'s `Contract` -- prior-session
Parkinson sigma x 1.2, NO same-day range (the un-retracted, ex-ante pricer).

Run:
    python research/g72_options_props_sizing.py
    python research/g72_options_props_sizing.py --selfcheck
"""

from __future__ import annotations

import json
import os
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for p in (_ROOT, _HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import t7_real_contracts as t7                                   # noqa: E402

BOOK = os.path.join(_HERE, "bt2y_trades.json")

# tastytrade options, round trip, per contract:
#   $1.00 open + $0.00 close + $0.10 clearing x2 + $0.02 ORF x2 + $0.00329 TAF sell
# https://assets.contentstack.io/v3/assets/blt7dc2e3d4a7071563/
#        blt2b752fef372188fe/commissions-and-fees  (last updated 2026-07-30)
OPT_ROUND_TURN = 1.00 + 0.00 + 2 * 0.10 + 2 * 0.02 + 0.00329   # $1.24329


def med(v):
    return statistics.median(v) if v else float("nan")


def pct(v, p):
    if not v:
        return float("nan")
    s = sorted(v)
    return s[min(len(s) - 1, int(round(p / 100.0 * (len(s) - 1))))]


def load_rows():
    with open(BOOK, "r", encoding="utf-8") as fh:
        book = json.load(fh)
    out = []
    for r in book["trades"]:
        if not r.get("traded"):
            continue
        c = t7.Contract(r, None)
        if not c.ok or not c.risk or c.risk <= 0 or not c.p0 or c.p0 <= 0:
            continue
        out.append({
            "day": r["day"],
            "sym": r["sym"],
            "r": r["r"],
            "prem_risk": c.risk,      # $/share of premium that equals 1R
            "prem_entry": c.p0,       # $/share paid at entry
            "lev": c.p0 / c.risk,     # debit dollars per risk dollar
        })
    return book["meta"], out


def report():
    meta, rows = load_rows()
    print("=== G7.2 options_props -- $10,000 self-funded 0DTE ATM sizing ===")
    print("book %s -> %s, %d traded rows, %d priced (%.1f%%)"
          % (meta["first"], meta["last"], meta["traded"], len(rows),
             100.0 * len(rows) / meta["traded"]))

    lev = [x["lev"] for x in rows]
    print("\n--- 1. DEBIT PER DOLLAR OF RISK (the whole problem) ---")
    print("  debit/risk ratio   p10 %.1fx  median %.1fx  p90 %.1fx  max %.1fx"
          % (pct(lev, 10), med(lev), pct(lev, 90), max(lev)))
    print("  i.e. to risk $1 on a 0DTE ATM contract he must lay out ~$%.0f of cash"
          % med(lev))

    print("\n--- 2. MAX RISK PER TRADE AT A GIVEN CASH CEILING ---")
    print("  (max risk on THIS row = ceiling / (debit-per-risk); 1 contract granularity ignored)")
    print("  %-14s %10s %10s %10s %10s" % ("cash ceiling", "p10 risk", "median", "p90", "worst row"))
    for cap in (10000, 7500, 5000, 2500, 1000):
        mr = [cap / x["lev"] for x in rows]
        print("  $%-13s $%9.0f $%9.0f $%9.0f $%9.0f"
              % ("{:,}".format(cap), pct(mr, 10), med(mr), pct(mr, 90), min(mr)))

    print("\n--- 3. AT A FIXED RISK, WHAT FRACTION OF THE BOOK IS AFFORDABLE? ---")
    print("  a row is affordable if debit(risk) <= cash ceiling")
    print("  %-10s" % "risk/trade", end="")
    caps = (10000, 7500, 5000, 2500)
    for cap in caps:
        print(" %11s" % ("$" + "{:,}".format(cap)), end="")
    print()
    for risk in (100, 150, 200, 250, 300, 400, 500, 750, 1000):
        print("  $%-9d" % risk, end="")
        for cap in caps:
            ok = sum(1 for x in rows if risk * x["lev"] <= cap)
            print(" %10.1f%%" % (100.0 * ok / len(rows)), end="")
        print()

    print("\n--- 4. CONTRACT GRANULARITY AND FEE DRAG AT SMALL RISK ---")
    print("  1 contract risks prem_risk x 100:")
    one = [x["prem_risk"] * 100.0 for x in rows]
    print("     p10 $%.0f  median $%.0f  p90 $%.0f  max $%.0f"
          % (pct(one, 10), med(one), pct(one, 90), max(one)))
    print("  fee drag (round-trip $%.5f/contract) as %% of risk, integer contracts:"
          % OPT_ROUND_TURN)
    for risk in (100, 250, 500, 1000):
        drags, skipped = [], 0
        for x in rows:
            n = int(risk / (x["prem_risk"] * 100.0))
            if n < 1:
                skipped += 1
                continue
            real_risk = n * x["prem_risk"] * 100.0
            drags.append(OPT_ROUND_TURN * n / real_risk)
        print("     $%-6d fees = %.2f%% of risk (median), %.2f%% (p90); "
              "%d of %d rows (%.1f%%) cannot buy even 1 contract"
              % (risk, 100 * med(drags), 100 * pct(drags, 90),
                 skipped, len(rows), 100.0 * skipped / len(rows)))

    print("\n--- 5. THE JOINT CONSTRAINT: $10,000 ACCOUNT, ONE TRADE A DAY ---")
    print("  integer contracts, debit capped at the ceiling, risk capped at the target")
    for cap, risk in ((10000, 250), (10000, 500), (10000, 1000),
                      (5000, 250), (5000, 500)):
        taken, realised, cut = 0, [], 0
        for x in rows:
            n_risk = int(risk / (x["prem_risk"] * 100.0))
            n_cash = int(cap / (x["prem_entry"] * 100.0))
            n = min(n_risk, n_cash)
            if n < 1:
                continue
            taken += 1
            if n_cash < n_risk:
                cut += 1
            realised.append(n * x["prem_risk"] * 100.0)
        print("  cap $%-6s target risk $%-5d -> %d/%d rows tradable (%.1f%%), "
              "%d (%.1f%%) cash-capped below target; realised risk median $%.0f"
              % ("{:,}".format(cap), risk, taken, len(rows),
                 100.0 * taken / len(rows), cut, 100.0 * cut / len(rows),
                 med(realised)))

    print("\n--- 6. EXPECTED DOLLARS AT THE BOOK'S OWN MEAN R ---")
    mean_r = sum(x["r"] for x in rows) / len(rows)
    print("  mean R over the %d priced rows: %+.4f R" % (len(rows), mean_r))
    print("  one trade a day, ~250 sessions/yr, at the realised risk above:")
    for risk in (100, 250, 500):
        print("     $%-5d/trade -> %+.0f R/yr = $%s/yr gross of fees"
              % (risk, 250 * mean_r,
                 "{:,.0f}".format(250 * mean_r * risk)))


def selfcheck():
    """Assert this module is not imported by any engine or backtest file."""
    targets = ["backtest_2y.py", "backtest_week.py", "signal_runner.py",
               "options_sizer.py", "paper_trader.py"]
    me = "g72_options_props_sizing"
    for t in targets:
        p = os.path.join(_ROOT, t)
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
            assert me not in fh.read(), "%s imports %s" % (t, me)
    # the pricer must be the ex-ante one: no same-day range in the sigma
    import re
    src = open(os.path.join(_HERE, "t7_real_contracts.py"), "r",
               encoding="utf-8", errors="ignore").read()
    bad = re.findall(r'row(?:\[|\.get\()["\']drange["\']', src)
    assert not bad, "same-day drange leaked into the pricing path: %r" % bad
    print("selfcheck OK: no engine imports this; t7 pricer is drange-free")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        report()
