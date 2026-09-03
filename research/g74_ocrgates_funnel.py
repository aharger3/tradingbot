"""G7.4 / ocrgates -- the one-candle-rule funnel, gate by gate, beside
break-and-retest.

Austin graded 30 engine S calls on 2026-08-29
(research/marks/probe_g71_homework_s3_2026-08-29_complete.jsonl) and said yes to
8 of 10 one-candle-rule cards -- the best of the three setups. The premise of
this script is his: if the eye is good and the trade count is not, the loss is
downstream of detection. So: count every survivor at every gate, for BOTH
setups, off ONE instrumented two-year replay.

Nothing here changes a default. Every counter is a wrapper; the engine runs
exactly as it ships. The replay is `backtest_2y.py` in-process, so the book this
produces is byte-comparable with research/bt2y_trades.json.

Writes research/g74_ocrgates_funnel.json (+ a scratch book that can be deleted).

Usage:  python research/g74_ocrgates_funnel.py [--out ...] [--book ...]
"""
import argparse, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import omen_bot
import signal_runner as sr
import backtest_week as bw
import backtest_2y as bt2y

OCR = Counter()
EMIT = Counter()
ROUTE = Counter()

_NOTE_STAGE = {
    "No valid order block (or structure broken)": "no_order_block",
    "Order block not isolated (consolidation), skipped": "block_not_isolated",
    "No displacement - slow/hesitant break, skipped": "no_displacement",
    "Price not at order block": "not_retesting",
}

_real_ob = sr.detect_order_block_setup


def _ob_wrapper(candles, direction="bullish", out=None):
    """Count the OCR detection ladder exactly as signal_runner's two call sites
    walk it: structure -> isolation -> displacement -> retest present ->
    retest strength -> close through the block -> volume."""
    OCR["calls"] += 1
    block, retest, note = _real_ob(candles, direction, out)
    if block is None:
        OCR[_NOTE_STAGE.get(note, "other:" + str(note))] += 1
        return block, retest, note
    OCR["detected"] += 1
    bull = direction == "bullish"
    if retest not in sr.OB_RETEST_TYPES:
        OCR["retest_strength"] += 1
        OCR["retest_strength:" + str(retest)] += 1
        return block, retest, note
    cur = candles[-1]
    if not ((cur.close > block.high) if bull else (cur.close < block.low)):
        OCR["no_close_through_block"] += 1
        return block, retest, note
    if not sr._volume_ok(candles):
        OCR["volume"] += 1
        return block, retest, note
    OCR["reaches_emit"] += 1
    # the two OCR-only grade gates, measured where the caller applies them
    entry_px = cur.close
    stop_px = block.low if bull else block.high
    risk = abs(entry_px - stop_px)
    OCR["would_fail_max_stop_0.4pct"] += int(risk / cur.close > 0.004)
    OCR["would_fail_flat_50c"] += int(risk < 0.50)
    OCR["would_fail_relative_floor"] += int(risk < sr.min_risk_floor(cur.close))
    return block, retest, note


sr.detect_order_block_setup = _ob_wrapper

_real_emit = sr.SignalRunner._emit
_real_route = bw.BacktestRunner._route


def _emit_wrapper(self, signals, sig):
    EMIT[sig["signal_type"].value] += 1
    return _real_emit(self, signals, sig)


def _route_wrapper(self, signals, sig):
    r = _real_route(self, signals, sig)
    ROUTE[(sig["signal_type"].value, sig["status"], sig["grade"])] += 1
    return r


sr.SignalRunner._emit = _emit_wrapper
bw.BacktestRunner._route = _route_wrapper


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--book", default=str(ROOT / "research" / "_g74_funnel_book.json"))
    ap.add_argument("--out", default=str(ROOT / "research" / "g74_ocrgates_funnel.json"))
    ap.add_argument("--days", type=int, default=730)
    args = ap.parse_args()

    sys.argv = ["backtest_2y.py", "--days", str(args.days), "--out", args.book]
    bt2y.main()

    book = json.load(open(args.book, encoding="utf-8"))
    rows, meta = book["trades"], book["meta"]
    inbook = Counter(r["setup"] for r in rows)
    traded = Counter(r["setup"] for r in rows if r["traded"])
    halted = Counter(r["setup"] for r in rows if r["status"] == "halted")

    out = {
        "meta": meta,
        "ocr_detection": dict(OCR),
        "br_detection": dict(omen_bot.BR_FUNNEL),
        "emitted": dict(EMIT),
        "routed": {"|".join(k): v for k, v in sorted(ROUTE.items())},
        "in_book": dict(inbook),
        "traded": dict(traded),
        "halted": dict(halted),
        "dedupe_killed": {k: EMIT.get(k, 0) - inbook.get(k, 0) for k in EMIT},
    }
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)

    print("\n=== OCR detection ladder ===")
    for k, v in OCR.most_common():
        print("  %-34s %8d" % (k, v))
    print("\n=== B&R detection ladder (omen_bot.BR_FUNNEL) ===")
    for k, v in omen_bot.BR_FUNNEL.items():
        print("  %-34s %8d" % (k, v))
    print("\n=== emitted / in book / traded ===")
    for k in sorted(EMIT):
        print("  %-22s emit %7d  book %7d  dedupe -%6d  traded %6d  halted %5d"
              % (k, EMIT[k], inbook.get(k, 0), EMIT[k] - inbook.get(k, 0),
                 traded.get(k, 0), halted.get(k, 0)))
    print("\n=== routed (setup | status | grade) ===")
    for (setup, status, grade), v in sorted(ROUTE.items()):
        print("  %-22s %-24s %-3s %8d" % (setup, status, grade, v))
    print("\nwrote %s" % args.out)


if __name__ == "__main__":
    main()
