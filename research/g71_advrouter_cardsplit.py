"""G7.1 adversarial-verify of track `router`.

Splits the harness-vs-book gap on a card into its three possible causes:
  (1) different LEVEL/CONTEXT inputs  -> different signals detected
  (2) different GRADING               -> same bar, different grade
  (3) the book's dedupe               -> signal detected+graded the same, dropped

Method: run the recall harness (research/t4_engine_recall.run_day with the
DELEGATING router from g71_router_recall) and, in the same process, run the
book's own path -- backtest_week.simulate_day with the exact level inputs
backtest_2y.py feeds it -- with BacktestRunner instrumented to keep every
captured signal. Then join on (bar, setup, direction).

Nothing shared is edited; the instrumentation is in-process only.
Usage: python research/g71_advrouter_cardsplit.py SYM DAY [SYM DAY ...]
"""
from __future__ import annotations
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)

import polygon_feed as pf
import backtest_week as bw
import research.t4_engine_recall as t4
from research.g71_router_recall import _delegating_route, _ORIGINAL_ROUTE
from backtest_12mo import hourly_from_1m, qqq_level_breaks

INSTANCES = []
_orig_init = bw.BacktestRunner.__init__
def _init(self, symbol):
    _orig_init(self, symbol)
    INSTANCES.append(self)
bw.BacktestRunner.__init__ = _init


def archive_days(sym):
    d = os.path.join(ROOT, "data_archive", sym)
    if not os.path.isdir(d):
        return []
    return sorted(f[:-4] for f in os.listdir(d) if f.endswith(".csv"))


def book_day(sym, day, with_qqq=True):
    """Reproduce backtest_2y.main()'s per-day inputs exactly."""
    days = archive_days(sym)
    i = days.index(day)
    prev = days[i - 1] if i else None
    bars = pf.fetch_day(sym, day); rth = pf.rth(bars)
    if prev:
        pbars = pf.fetch_day(sym, prev); prth = pf.rth(pbars)
        pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
        pdo, pdc = prth[0].open, prth[-1].close
    else:
        pdh = pdl = pdo = pdc = None
    pmh, pml = pf.premarket_hi_lo(bars)
    # backtest_2y builds hourly from EVERY archived day >= start, in order
    hourly = []
    for d in days[:i + 1]:
        try:
            r = pf.rth(pf.fetch_day(d and sym, d))
        except Exception:
            continue
        if len(r) >= 30:
            hourly += hourly_from_1m(d, r)
    bias = bw.htf_bias_for(hourly, day)
    qqq = qqq_level_breaks([day]).get(day) if with_qqq else None
    INSTANCES.clear()
    trades = bw.simulate_day(sym, day, rth, pdh, pdl, bias, pmh, pml, pdo, pdc, qqq=qqq)
    runner = INSTANCES[-1]
    return trades, runner, dict(pdh=pdh, pdl=pdl, pmh=pmh, pml=pml, bias=bias, qqq=bool(qqq))


def harness_day(sym, day):
    t4.CaptureRunner._route = _delegating_route
    ent, sigs, raw = t4.run_day(sym, day)
    t4.CaptureRunner._route = _ORIGINAL_ROUTE
    return ent, raw


def main():
    args = sys.argv[1:]
    pairs = [(args[i], args[i + 1]) for i in range(0, len(args), 2)]
    out = {}
    for sym, day in pairs:
        print("=" * 78)
        print("%s %s" % (sym, day))
        ent, raw = harness_day(sym, day)
        trades, runner, ctx = book_day(sym, day)
        bk_cap = runner.captured
        # harness levels for comparison
        hpdh, hpdl, hpdo, hpdc = t4.prior_day_levels(sym, day)
        hpmh, hpml = t4.premarket_extremes(sym, day)
        hbias = t4.htf_bias(sym, day)
        print(" ctx book : pdh=%s pdl=%s pmh=%s pml=%s bias=%s qqq=%s" % (
            ctx["pdh"], ctx["pdl"], ctx["pmh"], ctx["pml"], ctx["bias"], ctx["qqq"]))
        print(" ctx harn : pdh=%s pdl=%s pmh=%s pml=%s bias=%s qqq=False" % (
            hpdh, hpdl, hpmh, hpml, hbias))
        print(" harness raw=%d  fired_raw=%d  entries(deduped)=%d" % (
            len(raw), sum(1 for r in raw if r["status"] == "fired"), len(ent)))
        print(" book captured=%d  fired=%d  rows_in_book(post-dedupe)=%d" % (
            len(bk_cap), sum(1 for s in bk_cap if s["status"] == "fired"), len(trades)))

        # index book captured by (bar-equivalent timestamp, setup, dir)
        def bk_key(s):
            return (s["timestamp"][11:19], s["signal_type"].value, s["direction"])
        bkmap = {}
        for s in bk_cap:
            bkmap.setdefault(bk_key(s), []).append(s)
        rowkeys = {(t.entry_time[:8], t.signal_type, t.direction) for t in trades}
        print(" -- per-signal join (harness vs book captured) --")
        n_missing, n_gradediff, n_deduped, n_same = 0, 0, 0, 0
        for r in raw:
            k = (r["timestamp"][11:19], r["signal_type"], r["direction"])
            b = bkmap.get(k)
            if not b:
                n_missing += 1
                tag = "NOT-DETECTED-BY-BOOK"
                bg = bs = "-"
            else:
                bg, bs = b[0]["grade"], b[0]["status"]
                if bg != r["grade"]:
                    n_gradediff += 1; tag = "GRADE-DIFF"
                elif k not in rowkeys:
                    n_deduped += 1; tag = "DEDUPED-OUT-OF-BOOK"
                else:
                    n_same += 1; tag = "same"
            print("   %s %-18s %-4s H:grade=%-2s/%-20s  B:grade=%-2s/%-16s  %s" % (
                r["timestamp"][11:16], r["signal_type"], r["direction"],
                r["grade"], r["status"], bg, bs, tag))
        print(" summary: same=%d grade-diff=%d deduped=%d not-detected=%d"
              % (n_same, n_gradediff, n_deduped, n_missing))
        # book-only signals
        hkeys = {(r["timestamp"][11:19], r["signal_type"], r["direction"]) for r in raw}
        extra = [s for s in bk_cap if bk_key(s) not in hkeys]
        print(" book-only signals (harness never saw): %d" % len(extra))
        for s in extra[:20]:
            print("   %s %-18s %-4s grade=%-2s status=%s" % (
                s["timestamp"][11:16], s["signal_type"].value, s["direction"],
                s["grade"], s["status"]))
        out["%s %s" % (sym, day)] = dict(
            harness_raw=len(raw), harness_fired=sum(1 for r in raw if r["status"] == "fired"),
            harness_entries=len(ent), book_captured=len(bk_cap),
            book_fired=sum(1 for s in bk_cap if s["status"] == "fired"),
            book_rows=len(trades), same=n_same, grade_diff=n_gradediff,
            deduped=n_deduped, not_detected=n_missing, book_only=len(extra),
            ctx_book=ctx, ctx_harness=dict(pdh=hpdh, pdl=hpdl, pmh=hpmh, pml=hpml, bias=hbias))
    with open(os.path.join(HERE, "g71_advrouter_cardsplit.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)
    print("\nwrote research/g71_advrouter_cardsplit.json")


if __name__ == "__main__":
    main()
