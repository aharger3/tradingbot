"""G71/sigfire — the stages ABOVE `_route`, which `research/bt2y_trades.json`
cannot see.

`backtest_week.BacktestRunner.captured` is appended inside `_route`, so the
book's "signals" number counts only candidates that already survived
`SignalRunner._emit`'s two pre-route vetoes. This instruments the real top of
the funnel:

  bar scans      -> detect_signals() calls (one per 1-min bar in the window)
  raw candidates -> _emit() calls (a detector's pattern conditions matched)
  routed         -> _route() calls (== a row in the book)
  fired / TRADE  -> as the book reports them

Runs on a deterministic SAMPLE of sessions (default every 12th) so it finishes
in minutes; the per-session ratios are what the funnel needs, and the routed
count is cross-checked against the full book's routed-per-session rate.

Usage: python research/g71_sigfire_upstream.py [--stride 12]
"""
import argparse, sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import polygon_feed as pf
import signal_runner as sr
from backtest_week import simulate_day, htf_bias_for
from backtest_12mo import hourly_from_1m, qqq_level_breaks
from universe import ALL_SYMS, has_archive

CNT = Counter()

_orig_detect = sr.SignalRunner.detect_signals
_orig_emit = sr.SignalRunner._emit
_orig_route = sr.SignalRunner._route


def detect_signals(self):
    CNT["bar_scans"] += 1
    out = _orig_detect(self)
    if out:
        CNT["bars_producing_a_fire"] += 1
    return out


def _emit(self, signals, sig):
    CNT["raw_candidates"] += 1
    st = getattr(sig.get("signal_type"), "value", str(sig.get("signal_type")))
    CNT["cand:" + st] += 1
    before = len(signals)
    n_route = CNT["routed"]
    _orig_emit(self, signals, sig)
    if CNT["routed"] == n_route:          # never reached _route
        if not sr.TRADE_RETIRED_SETUPS and sig.get("signal_type") in sr.RETIRED_SETUPS:
            CNT["veto_retired_setup"] += 1
            CNT["vetoret:" + st] += 1
        else:
            CNT["veto_session_extreme"] += 1
    if len(signals) > before:
        CNT["accepted_by_route"] += 1


def _route(self, signals, sig):
    CNT["routed"] += 1
    _orig_route(self, signals, sig)


sr.SignalRunner.detect_signals = detect_signals
sr.SignalRunner._emit = _emit
sr.SignalRunner._route = _route


def archive_days(sym):
    d = ROOT / "data_archive" / sym
    return sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stride", type=int, default=12)
    ap.add_argument("--days", type=int, default=730)
    args = ap.parse_args()

    syms = [s for s in ALL_SYMS if has_archive(s, 100)]
    last = max((archive_days(s) or ["1970-01-01"])[-1] for s in syms)
    start = (date.fromisoformat(last) - timedelta(days=args.days)).isoformat()
    window = sorted({d for s in syms for d in archive_days(s) if d >= start})
    sample = set(window[::args.stride])
    print("%d symbols; %d sessions in window; sampling %d (stride %d)"
          % (len(syms), len(window), len(sample), args.stride))

    qqq_brk = qqq_level_breaks(sorted(sample))
    n_trades = 0
    symday = 0
    for sym in syms:
        days = [d for d in archive_days(sym) if d in sample]
        if not days:
            continue
        day_bars, hourly = {}, []
        for d in sorted(set(archive_days(sym)) & sample):
            try:
                bars = pf.fetch_day(sym, d)
            except Exception:
                continue
            if not bars:
                continue
            r = pf.rth(bars)
            if len(r) < 30:
                continue
            day_bars[d] = (bars, r)
            hourly += hourly_from_1m(d, r)
        prev = None
        for d in sorted(day_bars):
            bars, rth = day_bars[d]
            if prev:
                _, prth = day_bars[prev]
                pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
                pdo, pdc = prth[0].open, prth[-1].close
            else:
                pdh = pdl = pdo = pdc = None
            pmh, pml = pf.premarket_hi_lo(bars)
            bias = htf_bias_for(hourly, d)
            t = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml, pdo, pdc,
                             qqq=qqq_brk.get(d))
            n_trades += len(t)
            CNT["book_rows"] += len(t)
            CNT["book_fired"] += sum(1 for x in t if x.status == "fired")
            CNT["book_traded"] += sum(1 for x in t if x.counted)
            CNT["book_alert"] += sum(1 for x in t if x.is_alert)
            symday += 1
            prev = d

    print()
    print("=== SAMPLE FUNNEL (%d symbol-days, %d sessions) ===" % (symday, len(sample)))
    order = ["bar_scans", "raw_candidates", "veto_retired_setup",
             "veto_session_extreme", "routed", "accepted_by_route",
             "book_rows", "book_fired", "book_traded", "book_alert"]
    top = CNT["bar_scans"] or 1
    for k in order:
        print("  %-24s %8d   %7.3f%% of bar scans" % (k, CNT[k], 100.0 * CNT[k] / top))
    print()
    print("  raw candidates by setup:")
    for k, v in sorted(CNT.items()):
        if k.startswith("cand:"):
            print("    %-26s %8d" % (k[5:], v))
    print("  vetoed as retired setup:")
    for k, v in sorted(CNT.items()):
        if k.startswith("vetoret:"):
            print("    %-26s %8d" % (k[8:], v))
    print()
    print("  routed per symbol-day        %8.2f" % (CNT["routed"] / max(1, symday)))
    print("  raw candidates per symbol-day%8.2f" % (CNT["raw_candidates"] / max(1, symday)))
    print("  raw -> routed survival       %8.2f%%"
          % (100.0 * CNT["routed"] / max(1, CNT["raw_candidates"])))
    print("  routed -> fired              %8.2f%%"
          % (100.0 * CNT["book_fired"] / max(1, CNT["routed"])))
    print("  routed -> TRADE              %8.2f%%"
          % (100.0 * CNT["book_traded"] / max(1, CNT["routed"])))


if __name__ == "__main__":
    main()
