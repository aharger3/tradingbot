"""omen_metrics.py -- the EV/R reporting kernel and the prop-evaluation simulator.

Austin's ruling, 2026-09-03: the bar is PASS ONE PROP EVALUATION within 12
months, not $397/day, not six figures. That makes DRAWDOWN and CONSISTENCY
primary and raw return secondary. THE HEADLINE NUMBER IS EV PER TRADE, IN R:
`win% x avg_win_R - loss% x avg_loss_R`. It is sizing-independent and
comparable across every arm. $/day is demoted to a supporting row and must
never lead. His words: "The daily metric is hard to read over rr and yearly
profit and EV."

Two things live here so fifty agents stop producing fifty dialects of the
same number:

  1. ev_r_scoreboard()          -- one function, one scoreboard, fed a list
                                    of R-multiples OR a list of book rows.
  2. evaluate_prop_challenge()  -- PASS/FAIL a daily equity curve against a
                                    modern prop-firm evaluation (profit
                                    target, trailing drawdown, daily loss
                                    limit, minimum trading days, consistency
                                    rule) and say WHICH rule broke and on
                                    WHICH day -- the failure reason is the
                                    actionable part, not the pass/fail bit.

Both size-gate on signal_runner.min_risk_floor: a row whose |entry - stop|
is narrower than the floor is an arithmetic artifact, not a trade a real
account could hold (an R-multiple with a one-cent denominator). The count
dropped is always returned, never swallowed silently.

    python research/omen_metrics.py     # demo() self-checks + the book table
"""
import importlib
import json
import os
import statistics
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")


# --------------------------------------------------------------------------
# signal_runner.min_risk_floor -- imported live, not re-derived, per CLAUDE.md
# ("Never re-implement a fill locally"). A bug-fix fleet is editing
# signal_runner.py tonight; if the import fails because the file is mid-edit,
# wait once and retry, then fall back to the formula verbatim from
# min_risk_floor's own docstring (max(0.10, 0.0015 x close)) so this module
# never blocks on a concurrent, unrelated edit. The fallback is a values
# passthrough, not a new rule -- see _MIN_RISK_FLOOR_SOURCE below.
# --------------------------------------------------------------------------
def _resolve_min_risk_floor():
    for attempt in range(2):
        try:
            importlib.invalidate_caches()
            from signal_runner import min_risk_floor as _mrf
            return _mrf, "signal_runner.min_risk_floor"
        except Exception:
            if attempt == 0:
                time.sleep(2)
                continue
    return (lambda close, scaled_dollars=None: max(0.10, 0.0015 * close),
            "fallback formula (signal_runner import failed -- mid-edit)")


_MIN_RISK_FLOOR_FN, MIN_RISK_FLOOR_SOURCE = _resolve_min_risk_floor()


def min_risk_floor(close):
    return _MIN_RISK_FLOOR_FN(close)


# ==========================================================================
# 1. THE EV/R REPORTING KERNEL
# ==========================================================================

def _row_is_sizeable(row):
    """True/False if the row carries entry+stop, else None (ungateable)."""
    entry = row.get("entry")
    stop = row.get("stop")
    if entry is None or stop is None:
        return None
    close = row.get("close", entry)  # this book's fill IS the bar close
    risk_per_share = abs(entry - stop)
    return risk_per_share >= min_risk_floor(close)


def ev_r_scoreboard(trades, risk_dollars=1000.0, sessions=None, size_gate=True):
    """The one scoreboard. `trades` is either a flat list of R-multiples
    (floats/ints, assumed already in chronological order) or a list of book
    rows (dicts) carrying at least 'r' (or 'pnl' to derive r = pnl /
    risk_dollars), optionally 'day' (YYYY-MM-DD, enables months_green and
    expectancy_per_day) and 'entry'/'stop' (enables the size gate).

    Returns a dict:
      ev_r               -- THE headline: win_rate*avg_win_R - loss_rate*avg_loss_R
      n                   -- trades actually scored, after the size gate
      n_input             -- trades handed in, before the gate
      n_dropped_size_gate -- dropped as unsizeable (|entry-stop| < floor); 0 if ungateable
      size_gate_applicable-- whether any row actually carried entry+stop
      win_rate, avg_win_R, avg_loss_R  -- avg_loss_R is a positive magnitude
      profit_factor       -- sum(wins)/sum(|losses|); None if no losses and no wins,
                              inf if losses are zero but wins exist
      total_R
      max_drawdown_R      -- worst peak-to-trough dip in cumulative R, <= 0,
                              over `trades` in the order given (sort first if
                              the order isn't already chronological)
      months_green        -- "g/total" string; None unless every scored row has 'day'
      expectancy_per_day  -- dollars/day at `risk_dollars` per R; None unless
                              every scored row has 'day' (or `sessions` given)
      r_stability         -- mean(R)/stdev(R) per trade, sharpe-like; None if n<2
                              or stdev is 0
      yearly_R            -- total_R scaled to 252 sessions, via `sessions` if
                              given, else distinct days if available, else n
      risk_dollars, sessions_used
    """
    n_input = len(trades)
    plain = []  # (r, day_or_None)
    n_dropped = 0
    gate_applicable = False

    for t in trades:
        if isinstance(t, dict):
            sizeable = _row_is_sizeable(t) if size_gate else None
            if sizeable is not None:
                gate_applicable = True
                if not sizeable:
                    n_dropped += 1
                    continue
            r = t.get("r")
            if r is None:
                pnl = t.get("pnl")
                r = (pnl / risk_dollars) if pnl is not None else None
            if r is None:
                continue
            plain.append((r, t.get("day")))
        else:
            plain.append((float(t), None))

    n = len(plain)
    if n == 0:
        return {
            "ev_r": None, "n": 0, "n_input": n_input,
            "n_dropped_size_gate": n_dropped,
            "size_gate_applicable": gate_applicable,
            "win_rate": None, "avg_win_R": None, "avg_loss_R": None,
            "profit_factor": None, "total_R": 0.0, "max_drawdown_R": 0.0,
            "months_green": None, "expectancy_per_day": None,
            "r_stability": None, "yearly_R": None,
            "risk_dollars": risk_dollars, "sessions_used": sessions,
        }

    rs = [r for r, _ in plain]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    win_rate = len(wins) / n
    loss_rate = len(losses) / n
    avg_win_R = statistics.fmean(wins) if wins else 0.0
    avg_loss_R = statistics.fmean([-x for x in losses]) if losses else 0.0
    ev_r = win_rate * avg_win_R - loss_rate * avg_loss_R
    total_R = sum(rs)

    sum_win = sum(wins)
    sum_loss_abs = sum(-x for x in losses)
    if sum_loss_abs > 0:
        profit_factor = sum_win / sum_loss_abs
    else:
        profit_factor = float("inf") if sum_win > 0 else None

    peak = cum = worst = 0.0
    for r in rs:
        cum += r
        peak = max(peak, cum)
        worst = min(worst, cum - peak)
    max_drawdown_R = worst

    if n >= 2:
        stdev_r = statistics.stdev(rs)
        r_stability = (total_R / n) / stdev_r if stdev_r > 0 else None
    else:
        r_stability = None

    days = [d for _, d in plain]
    have_days = all(d for d in days)
    sessions_used = sessions
    months_green = None
    expectancy_per_day = None
    if have_days:
        by_day = defaultdict(float)
        for r, d in plain:
            by_day[d] += r
        if sessions_used is None:
            sessions_used = len(by_day)
        by_month = defaultdict(float)
        for d, rv in by_day.items():
            by_month[d[:7]] += rv
        months_total = len(by_month)
        months_green_n = sum(1 for v in by_month.values() if v > 0)
        months_green = "%d/%d" % (months_green_n, months_total)
        expectancy_per_day = (total_R * risk_dollars) / sessions_used if sessions_used else None
    elif sessions_used is None:
        sessions_used = n  # fallback assumption: one trade per session

    yearly_R = (total_R / sessions_used * 252) if sessions_used else None

    return {
        "ev_r": round(ev_r, 4),
        "n": n, "n_input": n_input,
        "n_dropped_size_gate": n_dropped,
        "size_gate_applicable": gate_applicable,
        "win_rate": round(win_rate, 4),
        "avg_win_R": round(avg_win_R, 4),
        "avg_loss_R": round(avg_loss_R, 4),
        "profit_factor": round(profit_factor, 4) if isinstance(profit_factor, float) and profit_factor != float("inf") else profit_factor,
        "total_R": round(total_R, 4),
        "max_drawdown_R": round(max_drawdown_R, 4),
        "months_green": months_green,
        "expectancy_per_day": round(expectancy_per_day, 2) if expectancy_per_day is not None else None,
        "r_stability": round(r_stability, 4) if r_stability is not None else None,
        "yearly_R": round(yearly_R, 4) if yearly_R is not None else None,
        "risk_dollars": risk_dollars,
        "sessions_used": sessions_used,
    }


# ==========================================================================
# 2. THE PROP-EVALUATION SIMULATOR
# ==========================================================================

def _normalize_daily(daily_pnls):
    """Accepts a list of (day_label, pnl) tuples, a list of dicts with
    'day'/'pnl'/optional 'intraday_min', or a plain list of pnl floats
    (day_label becomes the 1-based index). Returns a list of
    (day_label, pnl, intraday_min_or_None), chronological order preserved
    as given -- this function does not sort."""
    out = []
    for i, row in enumerate(daily_pnls):
        if isinstance(row, dict):
            out.append((row.get("day", i + 1), float(row.get("pnl", 0.0)),
                        row.get("intraday_min")))
        elif isinstance(row, (tuple, list)) and len(row) >= 2:
            im = row[2] if len(row) > 2 else None
            out.append((row[0], float(row[1]), im))
        else:
            out.append((i + 1, float(row), None))
    return out


def evaluate_prop_challenge(daily_pnls, account_size=50000.0,
                             profit_target_pct=0.08, trailing_dd_pct=0.04,
                             daily_loss_limit_pct=0.02, min_trading_days=5,
                             consistency_pct=0.30, dd_mode="eod"):
    """PASS/FAIL a daily equity curve against a modern prop-firm evaluation.

    `daily_pnls` -- chronological. Each entry is one of:
        (day_label, pnl_dollars)
        (day_label, pnl_dollars, intraday_min_dollars)   -- worst running
            open P&L that day relative to the day's starting balance, <= 0;
            only meaningful with dd_mode="intraday"
        {"day": ..., "pnl": ..., "intraday_min": ...}
        a bare number (day_label becomes its 1-based index)
    A day with pnl == 0 and no intraday activity does not count as a
    trading day and does not move the equity curve.

    Rules, all parameterized because firms differ (defaults per Austin
    2026-09-03):
        profit_target_pct    -- fraction of account_size to reach, e.g. 0.08
        trailing_dd_pct       -- trailing max drawdown off PEAK equity, as a
                                  fraction of account_size (a fixed dollar
                                  trail, the common modern-eval convention --
                                  not a fraction of current balance)
        daily_loss_limit_pct  -- fixed fraction of account_size a single day
                                  may not lose (checked off the day's own
                                  worst realized/intraday P&L)
        min_trading_days      -- minimum days with nonzero activity
        consistency_pct       -- no single day's profit may exceed this
                                  fraction of TOTAL net profit (cumulative
                                  equity) at the moment the target is judged
        dd_mode                -- "eod" (default) checks the trailing
                                  drawdown only against end-of-day equity.
                                  "intraday" ALSO checks it against each
                                  day's worst point (equity + intraday_min)
                                  before that day's P&L is realized -- a
                                  day can breach and fail even if it closes
                                  green. Falls back to EOD-only behavior for
                                  any day missing intraday_min.

    Order of evaluation per day: daily loss limit first (a single day can
    kill the eval outright), then trailing drawdown, then the pass
    conditions (profit target reached AND min_trading_days met AND the
    consistency rule holds). If the curve runs out of days without a clean
    pass, the most specific reason is reported: min_trading_days if too few
    trading days occurred, else consistency if the target was reached but
    never cleanly (no day ever brought the concentration under the cap),
    else profit_target_not_reached.

    Returns a dict: passed (bool), fail_reason (str|None: one of
    "daily_loss_limit", "trailing_drawdown", "min_trading_days",
    "consistency", "profit_target_not_reached", or None on PASS), fail_day,
    final_equity, final_equity_pct, days_traded, max_drawdown_seen_dollars,
    best_day_dollars, best_day_pct_of_profit, params.
    """
    days = _normalize_daily(daily_pnls)
    profit_target = profit_target_pct * account_size
    trailing_dd = trailing_dd_pct * account_size
    daily_loss_limit = daily_loss_limit_pct * account_size
    params = dict(account_size=account_size, profit_target_pct=profit_target_pct,
                  trailing_dd_pct=trailing_dd_pct,
                  daily_loss_limit_pct=daily_loss_limit_pct,
                  min_trading_days=min_trading_days,
                  consistency_pct=consistency_pct, dd_mode=dd_mode)

    equity = 0.0
    peak_equity = 0.0
    worst_dd_seen = 0.0
    days_traded = 0
    day_profits = []
    target_ever_reached = False

    def finalize(passed, fail_reason, fail_day):
        best_day = max(day_profits) if day_profits else 0.0
        best_day_pct = (best_day / equity * 100) if equity > 0 else None
        return {
            "passed": passed, "fail_reason": fail_reason, "fail_day": fail_day,
            "final_equity": round(equity, 2),
            "final_equity_pct": round(equity / account_size * 100, 3),
            "days_traded": days_traded,
            "max_drawdown_seen_dollars": round(worst_dd_seen, 2),
            "max_drawdown_seen_pct": round(worst_dd_seen / account_size * 100, 3),
            "best_day_dollars": round(best_day, 2),
            "best_day_pct_of_profit": round(best_day_pct, 2) if best_day_pct is not None else None,
            "params": params,
        }

    for day_label, pnl, intraday_min in days:
        if pnl == 0 and not intraday_min:
            continue
        days_traded += 1
        day_profits.append(pnl)

        worst_realized = pnl if intraday_min is None else min(pnl, intraday_min)
        if worst_realized <= -daily_loss_limit:
            return finalize(False, "daily_loss_limit", day_label)

        if dd_mode == "intraday" and intraday_min is not None:
            intraday_low = equity + intraday_min
            worst_dd_seen = min(worst_dd_seen, intraday_low - peak_equity)
            if intraday_low < peak_equity - trailing_dd:
                return finalize(False, "trailing_drawdown", day_label)

        equity += pnl
        peak_equity = max(peak_equity, equity)
        worst_dd_seen = min(worst_dd_seen, equity - peak_equity)
        if equity < peak_equity - trailing_dd:
            return finalize(False, "trailing_drawdown", day_label)

        if equity >= profit_target and days_traded >= min_trading_days:
            target_ever_reached = True
            best_day = max(day_profits)
            share = (best_day / equity) if equity > 0 else 1.0
            if share <= consistency_pct:
                return finalize(True, None, None)
            # target hit but concentrated in one day -- not a clean pass yet,
            # keep trading in case a later day dilutes the concentration

    if days_traded < min_trading_days:
        reason = "min_trading_days"
    elif target_ever_reached:
        reason = "consistency"
    else:
        reason = "profit_target_not_reached"
    return finalize(False, reason, days[-1][0] if days else None)


# ==========================================================================
# demo() -- a simulator that passes everything is worthless
# ==========================================================================

def demo():
    ok = True

    def check(name, cond):
        nonlocal ok
        status = "PASS" if cond else "FAIL <<<"
        print("  demo: %-38s %s" % (name, status))
        ok = ok and cond

    print("demo() -- self-check: the simulator must fail a curve that")
    print("breaches each rule in turn, and pass a clean one.\n")

    acct = 50000.0

    # 1. daily loss limit breach: one brutal day, well inside every other rule
    r = evaluate_prop_challenge([("d1", 200), ("d2", -1200), ("d3", 100)],
                                 account_size=acct)
    check("daily_loss_limit breach -> FAIL(daily_loss_limit)",
          not r["passed"] and r["fail_reason"] == "daily_loss_limit" and r["fail_day"] == "d2")

    # 2. trailing drawdown breach: run up (short of the profit target, so it
    # can't auto-pass first), then give it back over SEVERAL days, each one
    # individually under the daily loss limit (-1,000) so daily_loss_limit
    # can't fire first -- only the cumulative trail (4% of 50k = 2,000) can
    curve = ([("d%d" % i, 500) for i in range(1, 6)]        # +2,500 over 5 days
             + [("d6", -700), ("d7", -700), ("d8", -700)])   # -2,100 off peak by d8
    r = evaluate_prop_challenge(curve, account_size=acct)
    check("trailing_drawdown breach -> FAIL(trailing_drawdown)",
          not r["passed"] and r["fail_reason"] == "trailing_drawdown" and r["fail_day"] == "d8")

    # 2b. same shape, intraday mode: the breach happens mid-day on d8 even
    # though the day itself closes flat, so EOD mode would have missed it
    curve_id = ([{"day": "d%d" % i, "pnl": 500} for i in range(1, 6)]
                + [{"day": "d6", "pnl": -700}, {"day": "d7", "pnl": -700}])
    curve_id.append({"day": "d8", "pnl": 0, "intraday_min": -700})
    r_eod = evaluate_prop_challenge(curve_id, account_size=acct, dd_mode="eod")
    r_intra = evaluate_prop_challenge(curve_id, account_size=acct, dd_mode="intraday")
    check("intraday trailing_dd catches a mid-day breach an EOD-only day misses",
          r_intra["fail_reason"] == "trailing_drawdown" and r_eod["fail_reason"] != "trailing_drawdown")

    # 3. minimum trading days: hits the profit target in one day, cleanly
    # distributed, but never trades again
    r = evaluate_prop_challenge([("d1", profit_target := 0.08 * acct)],
                                 account_size=acct, min_trading_days=5)
    check("min_trading_days breach -> FAIL(min_trading_days)",
          not r["passed"] and r["fail_reason"] == "min_trading_days")

    # 4. consistency: target reached almost entirely on one day, and it's
    # never diluted before the curve runs out
    curve = [("d1", 0.08 * acct)] + [("d%d" % i, 5.0) for i in range(2, 7)]
    r = evaluate_prop_challenge(curve, account_size=acct, min_trading_days=5,
                                 consistency_pct=0.30)
    check("consistency breach -> FAIL(consistency)",
          not r["passed"] and r["fail_reason"] == "consistency")

    # 5. a clean pass: target reached on day 6 (>= min_trading_days), no
    # single day dominant, no drawdown breach
    curve = [("d%d" % i, 700) for i in range(1, 7)]  # 4,200 by day 6, target 4,000
    r = evaluate_prop_challenge(curve, account_size=acct, min_trading_days=5,
                                 consistency_pct=0.30)
    check("clean curve -> PASS", r["passed"] and r["fail_reason"] is None)

    # 6. ev_r_scoreboard sanity: known R stream -> known EV/R
    sb = ev_r_scoreboard([1.0, 1.0, -1.0, 1.0, -1.0], size_gate=False)
    # win_rate .6, avg_win 1.0, loss_rate .4, avg_loss 1.0 -> ev_r = .2
    check("ev_r_scoreboard: 3W/2L @ 1R each -> ev_r == 0.2",
          abs(sb["ev_r"] - 0.2) < 1e-9 and sb["n"] == 5 and sb["n_dropped_size_gate"] == 0)

    # 7. size gate actually drops unsizeable rows and counts them
    rows = [
        {"r": 1.0, "day": "2026-01-02", "entry": 100.0, "stop": 99.5},   # rps .5 >= floor .15 -- kept
        {"r": -1.0, "day": "2026-01-03", "entry": 100.0, "stop": 99.999},  # rps .001 < floor -- dropped
    ]
    sb = ev_r_scoreboard(rows)
    check("size gate drops the unsizeable row and reports it",
          sb["n"] == 1 and sb["n_dropped_size_gate"] == 1 and sb["size_gate_applicable"])

    print()
    if not ok:
        raise SystemExit("demo() FAILED -- a check above did not hold")
    print("demo() -- all checks held.\n")


# ==========================================================================
# main() -- score the book's own first-of-day arm at several risk levels
# ==========================================================================

def first_of_day_arm(rows, size_gate=True):
    """The one-trade-a-day candidate stream, arrival order, across all
    symbols: fired-and-traded rows, plus rows the account-wide loss-halt
    blocked (under a strict one-a-day policy that halt cannot have fired
    yet, so those days are live again). Identical construction to
    research/g86_honest_ceiling.py::candidates + the first-of-day pick.
    Returns one row per day, sorted chronologically.

    THE PICK-THEN-GATE BUG (omen-8 ticket 12a, fixed 2026-09-03). This used to
    return `v[0]` unconditionally and let `ev_r_scoreboard`'s size gate drop it
    downstream. That is not "one trade a day": if the day's FIRST candidate was
    too tight to size, the whole DAY vanished from the arm, rather than the
    trade falling through to the next candidate that could actually be traded.
    A real account does not skip the session because the 09:31 setup had a
    four-cent stop; it takes the next one.

    Two owners of one decision is what made it invisible -- selection here,
    gating there -- so the gate now runs INSIDE selection, through the same
    `_row_is_sizeable` predicate `ev_r_scoreboard` uses. Nothing is
    reimplemented; a row with no entry/stop (predicate returns None) is not
    gateable and is taken, exactly as the scoreboard treats it.

    `size_gate=False` reproduces the old pick-then-gate stream so the
    before/after is measurable from committed code.
    """
    def ekey(r):
        return (r["day"], r["et"], r["sym"])

    by_day = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            by_day[r["day"]].append(r)
    firsts = []
    for day in sorted(by_day):
        v = sorted(by_day[day], key=ekey)
        if not size_gate:
            firsts.append(v[0])
            continue
        pick = next((r for r in v if _row_is_sizeable(r) is not False), None)
        if pick is not None:
            firsts.append(pick)
    return firsts


def main():
    demo()

    if not os.path.exists(BOOK_PATH):
        print("MISSING %s -- skipping the book table" % BOOK_PATH)
        return

    print("min_risk_floor source: %s\n" % MIN_RISK_FLOOR_SOURCE)

    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    sessions = meta.get("sessions") or len({r["day"] for r in rows})

    firsts = first_of_day_arm(rows)
    print("book: %s -- %d sessions, %d days with a first-of-day trade"
          % (os.path.basename(BOOK_PATH), sessions, len(firsts)))

    sb = ev_r_scoreboard(firsts, risk_dollars=1000.0, sessions=sessions)
    print("\n=== EV/R scoreboard -- first-of-day arm, honest fill ===")
    for k in ("ev_r", "n", "n_input", "n_dropped_size_gate", "win_rate",
              "avg_win_R", "avg_loss_R", "profit_factor", "total_R",
              "max_drawdown_R", "months_green", "expectancy_per_day",
              "r_stability", "yearly_R"):
        print("  %-22s %s" % (k, sb[k]))

    # -- the prop-evaluation table: same R stream, several risk-per-trade
    # dollar levels, against a $50k combine-sized eval at the stated defaults
    print("\n=== prop-evaluation PASS/FAIL -- first-of-day arm, $50k eval, defaults ===")
    print("  %-16s %-6s %-24s %-12s %-10s %-8s" %
          ("risk/trade", "PASS?", "fail_reason", "fail_day", "final%", "DD%"))
    account_size = 50000.0
    for risk_per_trade in (100, 250, 500, 1000, 2000, 5000):
        daily = [(r["day"], r["r"] * risk_per_trade) for r in firsts]
        res = evaluate_prop_challenge(daily, account_size=account_size)
        print("  $%-15s %-6s %-24s %-12s %-10s %-8s" % (
            risk_per_trade,
            "PASS" if res["passed"] else "FAIL",
            res["fail_reason"] or "-",
            res["fail_day"] or "-",
            "%.1f" % res["final_equity_pct"],
            "%.1f" % res["max_drawdown_seen_pct"],
        ))


if __name__ == "__main__":
    main()
