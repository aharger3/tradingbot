"""G7.4 / ocrgates -- build ONE two-year book with one arm of the one-candle-rule
gate set changed. Measurement only: every arm is a monkeypatch inside THIS
process, no shipped default is edited and nothing is written back to the engine.

Arms
----
head        today's engine, unchanged (control; must reproduce bt2y_trades.json)
pre_r3r4    the engine as it stood before commit 43b3f59c: the B->C demote on
            every OCR signal AND the flat $0.50 minimum stop. This is the
            "before" of an unlock that has already shipped.
demote_only the B->C demote alone
flat50      the flat $0.50 minimum stop alone, on OCR
relfloor    the RELATIVE minimum break-and-retest already uses
            (signal_runner.min_risk_floor = max($0.10, 0.15% of price)), on OCR
nomax       drop the OCR-only 0.4%-of-price MAXIMUM stop gate
            (signal_runner.py:2904 / :3152)
wideretest  OB_RETEST_TYPES = wick_only + partial_body (the OCR-only
            retest-strength gate, signal_runner.py:51)
xlift_ocr   let T10/T23's X_LIFT reach the one-candle rule -- today
            x_lift_qualifies() returns False for anything that is not a
            break-and-retest (signal_runner.py:~975)
merits      nomax + wideretest + xlift_ocr: every OCR-only gate that
            break-and-retest does not carry, removed at once

Usage:  python research/g74_ocrgates_arm.py --arm nomax --out research/_g74_nomax.json
"""
import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import signal_runner as sr
import backtest_2y as bt2y
from omen_bot import SignalType, TradeGrade

# nohtf     -- exempt the one-candle rule from omen_bot.HTF_BIAS_VETO
#              (omen_bot.py:29 / :242), the hard D handed down before any price
#              action is read. 3,384 of OCR's 5,585 killed signals (60.6%) are
#              HTF-opposed against 50.7% of break-and-retest's. It has no author
#              and Projects/omen-rulebook.md records it DELETED 2026-08-28 while
#              the code still ships it ON.
# allmerits -- nohtf + merits: every gate the one-candle rule carries that
#              break-and-retest does not, plus the unauthored veto. A ceiling,
#              not a proposal.
# best      -- allmerits WITHOUT the X-lift, which the first pass showed to be
#              the one clearly harmful arm (-$506/day, CI -944..-88) and which
#              Austin's own marks already rejected 8 of 9. So: no 0.4% maximum,
#              partial_body retests allowed, no HTF veto on OCR. This is the
#              only combination worth proposing.
ARMS = ("head", "pre_r3r4", "demote_only", "flat50", "relfloor", "nomax",
        "wideretest", "xlift_ocr", "merits", "nohtf", "allmerits", "best")


def _pregate_grade(runner, sig, htf="keep"):
    """The grade the OCR detection site computed BEFORE its 0.4%-of-price
    maximum-stop gate. Recomputed from the signal itself: for a long,
    sig['level_price'] is block.high and sig['stop'] is block.low (and the
    mirror for a short), which are exactly the two arguments the call site
    hands _grade_trade.

    `htf=None` re-asks the same grader with no higher-timeframe vote, which is
    exactly what `grade_trade` does when the veto has nothing to say."""
    cs = runner.candles
    cur = cs[-1]
    lookback = cs[-6:-1] if len(cs) >= 6 else cs[:-1]
    bull = sig["direction"] == "call"
    lvl = sig.get("level_price")
    if lvl is None:
        return sig["grade"]
    hi, lo = (lvl, sig["stop"]) if bull else (sig["stop"], lvl)
    bias = runner.htf_bias if htf == "keep" else htf
    return runner._grade_trade(cur, lookback, hi, lo, is_long=bull,
                               htf_bias=bias).value


def patch(arm):
    if arm not in ARMS:
        raise SystemExit("unknown arm %r; pick one of %s" % (arm, ", ".join(ARMS)))
    if arm == "head":
        return

    if arm in ("wideretest", "merits", "allmerits", "best"):
        sr.OB_RETEST_TYPES = ("wick_only", "partial_body")

    if arm in ("xlift_ocr", "merits", "allmerits"):
        _real_q = sr.x_lift_qualifies

        def q(sig, armname):
            st = sig.get("base_signal_type") or sig.get("signal_type")
            if st is SignalType.ONE_CANDLE_RULE and armname != "off":
                return True          # the stop guard in _apply_x_lift still applies
            return _real_q(sig, armname)
        sr.x_lift_qualifies = q

    grade_arms = {"pre_r3r4", "demote_only", "flat50", "relfloor", "nomax",
                  "merits", "nohtf", "allmerits", "best"}
    if arm not in grade_arms:
        return

    _real_emit = sr.SignalRunner._emit

    def emit(self, signals, sig):
        if sig.get("signal_type") is SignalType.ONE_CANDLE_RULE:
            risk = abs(sig["entry"] - sig["stop"])
            close = self.candles[-1].close
            if arm in ("nomax", "merits", "allmerits"):
                sig["grade"] = _pregate_grade(self, sig)
            if arm == "nohtf":
                # veto lifted, 0.4% maximum-stop gate kept exactly as it ships
                g = _pregate_grade(self, sig, htf=None)
                sig["grade"] = (TradeGrade.X.value if risk / close > 0.004 else g)
            if arm in ("allmerits", "best"):
                sig["grade"] = _pregate_grade(self, sig, htf=None)
            if arm in ("pre_r3r4", "demote_only") and sig["grade"] == "B":
                sig["grade"] = TradeGrade.C.value
            if arm in ("pre_r3r4", "flat50") and risk < 0.50:
                sig["grade"] = TradeGrade.X.value
            if arm == "relfloor" and risk < sr.min_risk_floor(close):
                sig["grade"] = TradeGrade.X.value
        return _real_emit(self, signals, sig)

    sr.SignalRunner._emit = emit


# The 138 MB book is never written. `backtest_2y.main()` builds its rows, applies
# the R31 halt, and then spends most of its wall clock serialising 134,012 rows to
# disk -- which this pass does not need, because the only outputs are the priced
# stats. Wrapping loss_halt.apply_to_book is the last point where the finished
# rows exist, so the rows are stashed there and the write is skipped by raising.
# Nothing in the engine or in backtest_2y is modified.
class _Built(Exception):
    pass


def run_and_price(arm, days):
    import loss_halt
    sys.path.insert(0, str(ROOT / "research"))
    from g72_suppress_price import stats, shipped_rows, oneaday_rows

    stash = {}
    _real_halt = loss_halt.apply_to_book

    def halt(rows, **kw):
        n = _real_halt(rows, **kw)
        stash["rows"], stash["halted"] = rows, n
        raise _Built
    loss_halt.apply_to_book = halt
    bt2y.loss_halt = loss_halt

    sys.argv = ["backtest_2y.py", "--days", str(days), "--out", "unused.json"]
    try:
        bt2y.main()
    except _Built:
        pass
    rows = stash["rows"]
    days_seen = sorted({r["day"] for r in rows})
    nd = len(days_seen)
    ship, oad = shipped_rows(rows), oneaday_rows(rows)
    ocr = [r for r in ship if r["setup"] == "one_candle_rule"]
    br = [r for r in ship if r["setup"] == "break_and_retest"]
    ocr_alone = [r for r in ship if r.get("setup_label") == "one-candle-rule"]

    def by_day(sel):
        d = {}
        for r in sel:
            d[r["day"]] = d.get(r["day"], 0.0) + r["pnl"]
        return d

    return {
        "arm": arm, "signals": len(rows), "sessions": nd, "halted": stash["halted"],
        "shipped": stats(ship, nd), "one_a_day": stats(oad, nd),
        "ocr_slice": stats(ocr, nd), "br_slice": stats(br, nd),
        "ocr_alone_slice": stats(ocr_alone, nd),
        "days": days_seen,
        "oad_by_day": by_day(oad), "ship_by_day": by_day(ship),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arm", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--days", type=int, default=730)
    args = ap.parse_args()
    patch(args.arm)
    res = run_and_price(args.arm, args.days)
    import json
    json.dump(res, open(args.out, "w", encoding="utf-8"))
    s = res["shipped"]
    print("ARM %s: %d signals, %d trades, %.1f%%W, $%s/day, %d/%d months green"
          % (args.arm, res["signals"], s["trades"], s["win_pct"], s["per_day"],
             s["months_green"], s["months"]))


if __name__ == "__main__":
    main()
