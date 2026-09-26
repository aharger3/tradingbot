"""propfirm_gate.py -- the always-on prop-firm drawdown gate.

Austin, the card (2026-09-26): "Agents hunt a strategy that passes" -- every
candidate strategy the nightly no-regression loop measures must ALSO report
whether it would pass specific prop-firm rules, on paper, before anything is
bought. Known fact (2026-09-05, `research/g174_funding_ladder.py` /
`Projects/open-loops.md::omen-funding-ladder`): 16/16 futures firms tested
failed OMEN's trailing drawdown; Trade The Pool failed too but passed
5.7-32.9% of start dates; Vanquish never passed.

REUSED, NOT REIMPLEMENTED. The PASS/FAIL simulator is
`omen_metrics.evaluate_prop_challenge()` -- the exact function
`research/g172_vanquish_refresh.py` and `research/g174_funding_ladder.py`
already trust for this. This file adds two things that did not exist yet:

  1. FIRM_RULES -- a per-firm data table (account size, profit target,
     trailing drawdown pct + EOD/intraday mode + lock-at-breakeven, daily
     loss limit, consistency rule, minimum trading days) for the firms in
     `Resources/omen-prop-firms-2026-09.md` (Vanquish, Topstep, Apex,
     MyFundedFutures, Alpha Futures, Take Profit Trader), each a $50k
     account so every row is comparable. `dd_lock_at_breakeven` is new --
     `research/g71_propfirm_sim.py`'s FIRMS table carries a `lock` column
     but its own `simulate()` reads and discards it (`_lock` is unused);
     `omen_metrics.evaluate_prop_challenge`'s new `dd_lock_at_breakeven`
     parameter (this PR) is the real implementation.
  2. gate_series() / write_gate_report() -- run EVERY firm over one P&L
     series and report pass/fail, the breach day and rule, max DD used, and
     a start-date sweep (all_starts_pass_rate(), the same "share of start
     dates that pass" statistic `g174_funding_ladder.py::all_starts_pass_rate`
     already established and the 09-05 finding reported for Trade The Pool).

Run: python research/propfirm_gate.py [--book PATH] [--out PATH] [--risk N]
"""
from __future__ import annotations

import gzip
import json
import os
import sys
from datetime import date
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from omen_metrics import evaluate_prop_challenge, first_of_day_arm  # noqa: E402

DEFAULT_BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
DEFAULT_OUT = os.path.join(ROOT, "logs", "propfirm_gate_latest.json")
DEFAULT_RISK_DOLLARS = 1000.0  # CLAUDE.md: 1R = $1,000 unless a row says otherwise


# ==========================================================================
# 1. FIRM RULES -- the six firms in Resources/omen-prop-firms-2026-09.md,
#    each priced at a $50k account so every row is comparable. Every
#    dollar/pct figure below is either lifted from a firm-specific committed
#    row already in this repo (cited) or from the firm's own published rules
#    page fetched 2026-09-26 (cited); anything that could not be verified is
#    flagged in its own "verify" note rather than guessed silently.
# ==========================================================================

FIRM_RULES = {
    "Vanquish Trader Advanced Options 50K": dict(
        account_size=50_000.0,
        profit_target_pct=0.10,
        trailing_dd_pct=0.05,
        dd_mode="eod",
        dd_lock_at_breakeven=False,   # not documented; treated as trails forever
        daily_loss_limit_pct=1.0,     # Vanquish publishes no daily loss limit
        min_trading_days=4,
        consistency_pct=0.30,
        max_days=None,                # subscription eval, no day cap
        cost_dollars=499.0,           # monthly subscription (VANQUISH_MONTHLY_FEE)
        source=("research/g172_vanquish_refresh.py::VANQUISH_KW (reused as-is); "
                "https://www.vanquishtrader.com/how-vanquish-trader-evaluations-work-and-how-to-pass-them"),
        verify=None,
    ),
    "Topstep 50K Combine": dict(
        account_size=50_000.0,
        profit_target_pct=0.06,       # $3,000
        trailing_dd_pct=0.04,         # $2,000
        dd_mode="eod",
        dd_lock_at_breakeven=True,    # Topstep: trailing DD stops trailing at breakeven
        daily_loss_limit_pct=0.02,    # $1,000
        min_trading_days=0,           # no published minimum for the Combine
        consistency_pct=1.0,          # no consistency rule at the eval stage
        max_days=120,
        cost_dollars=49.0,
        source=("https://www.topstep.com/topstep-prop, verified 2026-09-05 "
                "(research/g170_futures_firms_2026-09.md); "
                "matches research/g71_propfirm_sim.py FIRMS row"),
        verify=None,
    ),
    "Apex 50K Eval EOD": dict(
        account_size=50_000.0,
        profit_target_pct=0.06,       # $3,000
        trailing_dd_pct=0.05,         # $2,500
        dd_mode="eod",
        dd_lock_at_breakeven=False,   # matches g71's lock=None; NOT independently confirmed
        daily_loss_limit_pct=1.0,     # Apex publishes no daily loss limit
        min_trading_days=0,
        consistency_pct=1.0,
        max_days=120,
        cost_dollars=35.0,
        source="research/g71_propfirm_sim.py FIRMS row (committed 2026-08-23)",
        verify=("apexfunded.com returned 403 Forbidden on both 2026-08-23 and "
                "2026-09-05 (research/g170_futures_firms_2026-09.md) -- these numbers "
                "are NOT independently re-verified against a live official page."),
    ),
    "MyFundedFutures Rapid 50K": dict(
        account_size=50_000.0,
        profit_target_pct=0.06,       # $3,000
        trailing_dd_pct=0.04,         # $2,000
        dd_mode="eod",
        dd_lock_at_breakeven=False,   # matches g71's lock=None; NOT independently confirmed
        daily_loss_limit_pct=1.0,     # MFFU publishes no daily loss limit
        min_trading_days=0,
        consistency_pct=1.0,
        max_days=120,
        cost_dollars=80.0,
        source="research/g71_propfirm_sim.py FIRMS row (committed 2026-08-23)",
        verify=("help.myfundedfutures.com did not resolve on 2026-09-05 "
                "(research/g170_futures_firms_2026-09.md) -- min trading days and "
                "consistency rule were never found on any public page; these numbers "
                "are NOT independently re-verified."),
    ),
    "Alpha Futures 50K Standard": dict(
        account_size=50_000.0,
        profit_target_pct=0.06,       # $3,000
        trailing_dd_pct=0.04,         # $2,000 (4% EOD trailing MLL, all plans)
        dd_mode="eod",
        dd_lock_at_breakeven=False,   # not documented as locking; treated as trails forever
        daily_loss_limit_pct=0.02,    # ~$1,000 Daily Loss Guard, interpolated for 50K
        min_trading_days=0,           # not stated on the fetched page
        consistency_pct=0.50,         # Standard plan: 50% during eval, 40% once qualified
        max_days=None,
        cost_dollars=None,
        source=("https://alpha-futures.com/posts/futures-prop-firm-rules-explained-2026, "
                "fetched 2026-09-26"),
        verify=("the article gives the Daily Loss Guard as '$500 / $1K / $2K by size' "
                "without naming which size gets which figure, and points to "
                "help.alpha-futures.com for exact $50K numbers (not fetched); "
                "$1,000 here is interpolated, not read off a page."),
    ),
    "Take Profit Trader 50K Test": dict(
        account_size=50_000.0,
        profit_target_pct=0.06,       # $3,000
        trailing_dd_pct=0.05,         # $2,500 (official blog's own worked example)
        dd_mode="eod",                # Test/Evaluation + PRO+ are EOD; PRO is intraday
        dd_lock_at_breakeven=True,    # "stops trailing once it reaches your starting balance"
        daily_loss_limit_pct=1.0,     # no daily loss limit on Test/PRO accounts as of Jan 2025
        min_trading_days=5,
        consistency_pct=0.50,         # no single day >= 50% of total net profit
        max_days=None,
        cost_dollars=None,
        source="https://takeprofittrader.com/blog/what-is-a-trailing-drawdown, fetched 2026-09-26",
        verify=("takeprofittrader.com/blog/prop-firm-rules (the firm's own rules index) "
                "returned 403 Forbidden on 2026-09-26. research/g71_propfirm_sim.py's "
                "older 'TPT Test 50K' row carries a $2,000 trailing DD, not $2,500 -- "
                "the two committed sources disagree and neither is the firm's live "
                "pricing page; re-verify before using this row for a real eval purchase."),
    ),
}


# ==========================================================================
# 2. per-series evaluation -- every firm, plus the start-date sweep
# ==========================================================================

def _challenge_kwargs(rule: dict) -> dict:
    """The subset of `rule` evaluate_prop_challenge() actually accepts."""
    return {k: rule[k] for k in (
        "account_size", "profit_target_pct", "trailing_dd_pct",
        "daily_loss_limit_pct", "min_trading_days", "consistency_pct",
        "dd_mode", "dd_lock_at_breakeven",
    )}


def evaluate_firm(daily_pnls, rule: dict) -> dict:
    """One firm, one series -> evaluate_prop_challenge()'s own result dict,
    unmodified (pass/fail, fail_reason, fail_day, max_drawdown_seen_dollars,
    ...). Thin wrapper so callers never have to know which of `rule`'s keys
    the simulator accepts."""
    return evaluate_prop_challenge(daily_pnls, **_challenge_kwargs(rule))


def all_starts_pass_rate(daily_pnls, rule: dict) -> tuple[float | None, int]:
    """(pass_pct, n_starts) -- start a fresh eval on EVERY day in the series
    and see whether it passes within the firm's own `max_days` (or over the
    rest of the series if the firm has no day cap). This is
    `g174_funding_ladder.py::all_starts_pass_rate` generalized off the book
    format to a plain (day, pnl) series -- same statistic, same reason
    (g174's own docstring: g171's committed 'rolling-252 pass rate' was a
    `window = min(252, n)` artifact, i.e. exactly one start point restated
    as a percentage; sweeping every start is the honest version, and it is
    what the 09-05 finding reported for Trade The Pool as "passes
    5.7-32.9% of start dates")."""
    n = len(daily_pnls)
    if n == 0:
        return None, 0
    max_days = rule.get("max_days")
    kw = _challenge_kwargs(rule)
    passed = 0
    for s in range(n):
        seg = daily_pnls[s:s + max_days] if max_days else daily_pnls[s:]
        if evaluate_prop_challenge(seg, **kw)["passed"]:
            passed += 1
    return round(100.0 * passed / n, 1), n


def gate_series(daily_pnls, firms: dict | None = None) -> dict:
    """Every firm in `firms` (default FIRM_RULES) against ONE chronological
    daily/per-trade P&L series -- (day_label, pnl_dollars) tuples, or
    anything `omen_metrics.evaluate_prop_challenge` already accepts.
    Returns {firm_name: {...evaluate_prop_challenge()'s own keys...,
    all_starts_pass_pct, all_starts_n, source, verify}}."""
    firms = firms if firms is not None else FIRM_RULES
    out = {}
    for name, rule in firms.items():
        res = evaluate_firm(daily_pnls, rule)
        sweep_pct, sweep_n = all_starts_pass_rate(daily_pnls, rule)
        res["all_starts_pass_pct"] = sweep_pct
        res["all_starts_n"] = sweep_n
        res["source"] = rule.get("source")
        res["verify"] = rule.get("verify")
        out[name] = res
    return out


# ==========================================================================
# 3. loading a book and writing the report
# ==========================================================================

def _load_book(path) -> tuple[list, dict]:
    """(rows, meta) from a plain .json book or a .json.gz one -- same
    fallback g172_vanquish_refresh.py::load_rows() and
    g174_funding_ladder.py::load_rows() already use, generalized to accept
    a path that already ends in .gz (as loop_cycle.py's own
    book_<flag>_on.json.gz paths do) as well as a plain .json path whose
    .gz twin is what actually exists on disk."""
    path = str(path)
    if path.endswith(".gz"):
        candidates = [path]
    else:
        candidates = [path, path + ".gz"]
    for c in candidates:
        if not os.path.exists(c):
            continue
        if c.endswith(".gz"):
            book = json.loads(gzip.open(c, "rt", encoding="utf-8").read())
        else:
            book = json.load(open(c, encoding="utf-8"))
        return book["trades"], book["meta"]
    raise FileNotFoundError("%s not found (also tried: %s)" % (path, candidates))


def write_gate_report(book_path=None, out_path=None, risk_dollars=DEFAULT_RISK_DOLLARS,
                      firms: dict | None = None) -> dict:
    """The nightly-loop entry point (called from research/nightly_loop.py's
    run_propfirm_gate()). Loads `book_path` (default the committed
    bt2y_trades_retest_on book), builds the one-trade-a-day arm with
    `omen_metrics.first_of_day_arm` (imported, not reimplemented), gates
    every firm in `firms` (default FIRM_RULES) against it at `risk_dollars`
    per R, and writes the report to `out_path`
    (default logs/propfirm_gate_latest.json at the repo root).

    If `book_path` needs live market data this Mac does not have (a fresh
    backtest book only the Windows box can build), pass the path to
    whichever book WAS built tonight -- see nightly_loop.py's own
    run_propfirm_gate() for how it locates that path. This function itself
    never fetches data; it only ever reads a book file already on disk."""
    book_path = book_path or DEFAULT_BOOK
    rows, meta = _load_book(book_path)
    arm = first_of_day_arm(rows)
    daily = [(r["day"], r["r"] * risk_dollars) for r in arm]

    results = gate_series(daily, firms)
    n_pass = sum(1 for v in results.values() if v["passed"])
    n_firms = len(results)

    try:
        book_display = str(Path(book_path).resolve().relative_to(Path(ROOT).resolve()))
    except ValueError:
        book_display = str(book_path)   # outside the repo -- show the real path

    report = {
        "generated": date.today().isoformat(),
        "book": book_display,
        "book_sessions": meta.get("sessions"),
        "risk_dollars": risk_dollars,
        "n_days": len(daily),
        "n_firms": n_firms,
        "n_passing": n_pass,
        "headline": ("%d/%d firms would pass this book on paper (risk $%.0f/trade, "
                    "%d trading days, first-of-day arm)"
                    % (n_pass, n_firms, risk_dollars, len(daily))),
        "firms": results,
    }

    out_path = Path(out_path or DEFAULT_OUT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    report["out_path"] = str(out_path)
    return report


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--book", default=DEFAULT_BOOK)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--risk", type=float, default=DEFAULT_RISK_DOLLARS)
    args = ap.parse_args()

    report = write_gate_report(args.book, args.out, args.risk)
    print(report["headline"])
    print("-" * len(report["headline"]))
    h = "%-38s %-6s %-20s %-12s %10s %10s" % (
        "firm", "PASS?", "fail_reason", "fail_day", "maxDD%", "all-starts%")
    print(h)
    for name, r in report["firms"].items():
        print("%-38s %-6s %-20s %-12s %10s %10s" % (
            name, "PASS" if r["passed"] else "FAIL", r["fail_reason"] or "-",
            r["fail_day"] or "-", "%.1f" % r["max_drawdown_seen_pct"],
            "%.1f" % r["all_starts_pass_pct"] if r["all_starts_pass_pct"] is not None else "-"))
    print("\nwrote", report["out_path"])


if __name__ == "__main__":
    main()
