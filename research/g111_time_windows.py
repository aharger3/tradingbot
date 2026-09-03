"""g111 -- trading-window sweep, headlined in EV/R (Austin's ruling 2026-09-03).

Assigned slice: "time_windows" of the 2026-09-03 backtest sweep. Named windows:
09:30-10:00, 09:30-10:30, 09:30-11:00 (shipped), 09:45-11:00, 10:00-11:30,
full session -- plus the never-asked question, does this setup family fire
and work AT ALL outside 09:30-11:00.

Read-only over the committed book (research/bt2y_trades_retest_on.json, 498
sessions, honest close fill). Every number routes through
research/omen_metrics.py::ev_r_scoreboard so it is comparable with the other
eleven sweeps running tonight. Nothing here touches signal_runner.py,
backtest_week.py, stop_rule.py or test_runner_stop.py -- all mid-edit per the
fleet notice.

TWO ARMS scored per window, because they answer different questions:
  first  -- one trade a day: the day's FIRST size-gated fired-and-traded (or
            halted) candidate whose entry time falls in the window. This is
            the shippable, one-trade-a-day unit the book's own first_of_day_arm
            uses, just re-picked per window. Headline arm.
  all    -- every size-gated fired-and-traded candidate whose entry time
            falls in the window, no one-a-day restriction. Candidate-quality
            context: is the window itself good, independent of the
            first-trade policy layered on top of it.

THE GAP THIS SCRIPT CANNOT CLOSE: the book was built with
signal_runner.SESSION_END = "11:00:00" (see the book's own meta.stamp.flags).
No candidate in this book has an entry time after 10:59 -- not because the
setup doesn't fire after 11:00, but because detection was never RUN past
11:00. So "10:00-11:30" and "full session" are reported here as exactly what
the static book can show (identical to 10:00-11:00 and 09:30-11:00
respectively) with n_after_1100 = 0 stated explicitly, not silently. The
never-asked question -- does break-and-retest work outside 09:30-11:00 at
all -- is UNANSWERED by this book and requires a fresh detection run with
SESSION_END extended, which is out of scope for a read-only sweep over a
frozen artifact and belongs to whoever owns signal_runner.py next.

    python research/g111_time_windows.py
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from omen_metrics import ev_r_scoreboard, evaluate_prop_challenge  # noqa: E402

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")

WINDOWS = [
    ("09:30-10:00", "09:30", "10:00"),
    ("09:30-10:30", "09:30", "10:30"),
    ("09:30-11:00 (shipped)", "09:30", "11:00"),
    ("09:45-11:00", "09:45", "11:00"),
    ("10:00-11:30", "10:00", "11:30"),
    ("full session (09:30-16:00)", "09:30", "16:00"),
]


def _in_window(et, start, end):
    # et is "HH:MM"; end is exclusive to match the book's own SESSION_END
    # convention (its last observed et is 10:59, SESSION_END is 11:00:00).
    return start <= et < end


def candidates(rows):
    """Size-gated-eligible universe for this sweep: fired-and-traded rows,
    plus loss-halted rows (the halt is an account-wide one-trade-a-day
    artifact of the shipped policy -- under any other window policy those
    days are live again). Identical selection to omen_metrics.first_of_day_arm
    before the one-per-day reduction."""
    out = [r for r in rows if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted"]
    return out


def first_of_day_in_window(cands, start, end):
    by_day = defaultdict(list)
    for r in cands:
        if _in_window(r["et"], start, end):
            by_day[r["day"]].append(r)
    firsts = []
    for day in sorted(by_day):
        v = sorted(by_day[day], key=lambda r: (r["et"], r["sym"]))
        firsts.append(v[0])
    return firsts


def all_in_window(cands, start, end):
    return [r for r in cands if _in_window(r["et"], start, end)]


def fmt_row(label, sb, n_days_total):
    days_hit = sb["sessions_used"] if sb["sessions_used"] else 0
    return "  %-26s n=%-5d dropped=%-4d ev_r=%-8s win=%-7s pf=%-7s dd=%-8s months=%-7s yr_R=%-8s days_traded=%d/%d" % (
        label, sb["n"], sb["n_dropped_size_gate"],
        sb["ev_r"], sb["win_rate"], sb["profit_factor"],
        sb["max_drawdown_R"], sb["months_green"], sb["yearly_R"],
        days_hit, n_days_total,
    )


def main():
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    sessions = meta.get("sessions") or len({r["day"] for r in rows})
    cands = candidates(rows)

    print("g111 -- time-window sweep, EV/R headline")
    print("book: %s -- %d sessions, %d size-gate-eligible candidates (fired-traded + halted)"
          % (os.path.basename(BOOK_PATH), sessions, len(cands)))
    max_et = max(r["et"] for r in cands)
    min_et = min(r["et"] for r in cands)
    print("book entry-time range observed: %s - %s (SESSION_END flag = %s)"
          % (min_et, max_et, meta["stamp"]["flags"].get("signal_runner.SESSION_END")))
    n_arms = 0

    print("\n=== ARM 1: first-of-day-in-window (one trade a day, shippable) ===")
    for label, start, end in WINDOWS:
        n_arms += 1
        firsts = first_of_day_in_window(cands, start, end)
        sb = ev_r_scoreboard(firsts, risk_dollars=1000.0, sessions=sessions)
        print(fmt_row(label, sb, sessions))

    print("\n=== ARM 2: all candidates in window (no one-a-day filter; window quality alone) ===")
    for label, start, end in WINDOWS:
        n_arms += 1
        allc = all_in_window(cands, start, end)
        sb = ev_r_scoreboard(allc, risk_dollars=1000.0, sessions=sessions)
        print(fmt_row(label, sb, sessions))

    print("\n=== the never-asked question: outside 09:30-11:00 ===")
    after_1100 = [r for r in cands if r["et"] >= "11:00"]
    print("  candidates with et >= 11:00 in this book: %d" % len(after_1100))
    print("  -> UNANSWERED, not zero-and-done: this book's signal_runner.SESSION_END")
    print("     was fixed at 11:00:00 at generation time, so detection was simply never")
    print("     RUN past 11:00. '10:00-11:30' and 'full session' above are therefore")
    print("     identical to '10:00-11:00' and '09:30-11:00' respectively -- the extra")
    print("     minutes contributed 0 candidates by construction, not by measurement.")
    print("     Answering this needs a fresh detection pass with SESSION_END extended,")
    print("     which is out of scope for a read-only sweep over a frozen book and")
    print("     touches signal_runner.py, which the fleet is editing tonight.")

    print("\n=== prop-eval PASS/FAIL, shipped window vs the widest fully-tested window ===")
    print("  ($50k eval, defaults, ARM 1 R-stream, risk/trade sweep)")
    for label, start, end in [("09:30-11:00 (shipped)", "09:30", "11:00"),
                               ("09:30-10:30", "09:30", "10:30")]:
        firsts = first_of_day_in_window(cands, start, end)
        sb = ev_r_scoreboard(firsts, risk_dollars=1000.0, sessions=sessions)
        # rebuild a per-day R series in day order for the daily-equity curve
        by_day = defaultdict(float)
        for r in firsts:
            if _row_sizeable_ok(r):
                by_day[r["day"]] += r["r"]
        daily_r = [(d, by_day[d]) for d in sorted(by_day)]
        print("  window: %s (ev_r=%s, n=%d)" % (label, sb["ev_r"], sb["n"]))
        for risk_per_trade in (250, 500, 1000):
            daily = [(d, r * risk_per_trade) for d, r in daily_r]
            res = evaluate_prop_challenge(daily, account_size=50000.0)
            print("    $%-6s %-6s %-22s fail_day=%-12s final%%=%-8s DD%%=%-6s" % (
                risk_per_trade, "PASS" if res["passed"] else "FAIL",
                res["fail_reason"] or "-", res["fail_day"] or "-",
                res["final_equity_pct"], res["max_drawdown_seen_pct"]))

    print("\narms tested this sweep: %d (%d windows x 2 arms)" % (n_arms, len(WINDOWS)))


def _row_sizeable_ok(row):
    from omen_metrics import _row_is_sizeable
    ok = _row_is_sizeable(row)
    return ok is not False


if __name__ == "__main__":
    main()
