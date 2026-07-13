"""C5 — HTF_BIAS_GATE A/B (SPEC10 daily-trend bias gate): gate OFF vs ON, 12mo.

SIMULATION on the clean 12mo baseline (research/c1_off_charts.json = 671 traded
/ 866 signals, 24 symbols, 2025-07-14..2026-07-10), NOT a re-run — matches the
c3/c8 tier-sim pattern so the baseline is bit-identical to every other C task.

Daily-trend proxy (the shippable gate's exact predicate, signal_runner.
daily_trend_bias): for a signal on day D, take that symbol's COMPLETED daily
closes strictly before D and compare the last close to its SMA20 — bullish if
close > SMA20, bearish if <. No look-ahead (D-1 close is known at D's open),
no DXLink MTF. Daily candles fetched from yfinance (per task).

Gate ON = only trade signals whose direction matches the daily trend
(call<->bullish, put<->bearish). Counter-trend signals are dropped from the
traded population (live flag caps them to C/alert-only — same effect: they
don't trade and free the day's tier slot). Days with no clear trend
(neutral / insufficient buffer / no daily data) pass through ungated.

Usage: py -3.13 research/c5_htf_gate.py
"""
import json, re, sys
from collections import defaultdict, Counter
from datetime import date, timedelta

sys.path.insert(0, ".")
from signal_runner import daily_trend_bias  # the shippable gate predicate

CHARTS = "research/c1_off_charts.json"
SMA = 20


def load_all(path):
    return json.load(open(path))


def s_score(rec):
    m = re.search(r" S(\d+)", rec["reason"])
    return int(m.group(1)) if m else None


def is_hammer(rec):
    c = rec["candles"][rec["entry_i"]]
    body = abs(c["c"] - c["o"]); rng = c["h"] - c["l"]
    if rng == 0:
        return False
    if rec["direction"] == "call":
        return min(c["o"], c["c"]) - c["l"] >= body and c["c"] >= c["l"] + 0.5 * rng
    return c["h"] - max(c["o"], c["c"]) >= body and c["c"] <= c["h"] - 0.5 * rng


def _t(rec):
    return rec["candles"][rec["entry_i"]]["t"]


# --- daily trend proxy from yfinance ------------------------------------------
def fetch_daily(symbols, start, end):
    """{sym: [(date_iso, close), ...] chronological}. One batched yf.download."""
    import yfinance as yf
    df = yf.download(symbols, start=start, end=end, interval="1d",
                     auto_adjust=True, progress=False, group_by="ticker",
                     threads=True)
    out = {}
    for s in symbols:
        try:
            closes = df[s]["Close"].dropna() if len(symbols) > 1 else df["Close"].dropna()
        except (KeyError, TypeError):
            out[s] = []
            continue
        out[s] = [(idx.date().isoformat(), float(v)) for idx, v in closes.items()]
    return out


def bias_map(daily, sym_days):
    """{(sym, day): 'bullish'/'bearish'/'neutral'/None}. Uses only closes
    strictly before `day` (no look-ahead)."""
    bm = {}
    for sym, days in sym_days.items():
        series = daily.get(sym, [])
        for day in days:
            prior = [c for (d, c) in series if d < day]
            bm[(sym, day)] = daily_trend_bias(prior, SMA)
    return bm


def aligned(rec, bm):
    """True if the gate PASSES this signal (trend-aligned, or no clear trend)."""
    b = bm.get((rec["symbol"], rec["day"]))
    if b not in ("bullish", "bearish"):
        return True  # can't gate -> pass through
    want = "call" if b == "bullish" else "put"
    return rec["direction"] == want


# --- populations --------------------------------------------------------------
def gstats(recs):
    counted = [r for r in recs if not r["alert_only"]]
    w = sum(1 for r in counted if r["outcome"] == "win")
    l = sum(1 for r in counted if r["outcome"] == "loss")
    pnl = sum(r["pnl"] for r in counted)
    wr = w / (w + l) * 100 if (w + l) else 0.0
    return len(counted), w, l, pnl, wr


def tier_sim(recs, bm=None, min_s=4, max_n=2):
    """S>=4+hammer tier, max 2/day, stop-when-green. When bm is given, a signal
    that fights the daily trend is skipped at the gate (frees the slot)."""
    recs = [r for r in recs if not r["alert_only"]]
    byday = defaultdict(list)
    for r in recs:
        byday[r["day"]].append(r)
    tot = w = n = 0
    for day, rs in byday.items():
        rs.sort(key=_t)
        taken = pnl_day = 0
        for r in rs:
            if taken >= max_n or pnl_day > 0:
                break
            s = s_score(r)
            if s is None or s < min_s or not is_hammer(r):
                continue
            if bm is not None and not aligned(r, bm):
                continue
            taken += 1; n += 1; pnl_day += r["pnl"]; tot += r["pnl"]
            w += r["outcome"] == "win"
    wr = w / n * 100 if n else 0.0
    return n, wr, tot


def main():
    recs = load_all(CHARTS)
    syms = sorted(set(r["symbol"] for r in recs))
    days = sorted(set(r["day"] for r in recs))
    sym_days = defaultdict(set)
    for r in recs:
        sym_days[r["symbol"]].add(r["day"])

    # fetch daily with a buffer for the SMA20 warm-up
    start = (date.fromisoformat(days[0]) - timedelta(days=90)).isoformat()
    end = (date.fromisoformat(days[-1]) + timedelta(days=2)).isoformat()
    print(f"# C5 HTF_BIAS_GATE A/B (SMA{SMA} daily trend, yfinance)")
    print(f"# baseline {CHARTS}: {len(recs)} signals, {len(syms)} symbols, "
          f"{days[0]}..{days[-1]}")
    print(f"# fetching daily bars {start}..{end} ...")
    daily = fetch_daily(syms, start, end)
    got = {s: len(v) for s, v in daily.items()}
    missing = [s for s in syms if got[s] == 0]
    print(f"# daily bars per symbol: min {min(got.values())}, "
          f"max {max(got.values())}; missing={missing}")
    if len(missing) > len(syms) // 2:
        print("!! more than half of symbols returned 0 daily bars — "
              "yfinance rate-limited. This is NOT a result. Re-run in 30 min.")
        sys.exit(2)

    bm = bias_map(daily, sym_days)
    bc = Counter(bm.values())
    print(f"# bias distribution over (sym,day): {dict(bc)}\n")

    # full-pop: how many traded signals the gate keeps
    traded = [r for r in recs if not r["alert_only"]]
    kept = [r for r in traded if aligned(r, bm)]
    blocked = len(traded) - len(kept)

    print("## Full population (traded A+/A/B)")
    print(f"{'run':16} {'trades':>6} {'win%':>6} {'P&L':>12}")
    for label, pop in [("OFF (baseline)", traded), ("ON (gate)", kept)]:
        n, w, l, pnl, wr = gstats(pop)
        print(f"{label:16} {n:>6} {wr:>5.1f}% ${pnl:>10,.0f}")
    print(f"# gate blocked {blocked} counter-trend trades "
          f"({blocked / len(traded) * 100:.0f}% of traded)\n")

    print("## S>=4+[hammer] tier (max 2/day, stop-when-green)")
    print(f"{'run':16} {'trades':>6} {'win%':>6} {'$/yr':>12}")
    off = tier_sim(recs, bm=None)
    on = tier_sim(recs, bm=bm)
    for label, (n, wr, pnl) in [("OFF (baseline)", off), ("ON (gate)", on)]:
        print(f"{label:16} {n:>6} {wr:>5.1f}% ${pnl:>10,.0f} (${pnl/12:,.0f}/mo)")

    print("\n## Verdict")
    d_wr = on[1] - off[1]; d_pnl = on[2] - off[2]
    better = d_pnl > 0 and d_wr > 0
    print(f"tier Δ: {on[0]-off[0]:+d} tr, {d_wr:+.1f}ppW, ${d_pnl:+,.0f}/yr")
    print("GATE HELPS tier" if better else
          "GATE DOES NOT HELP tier — keep OFF" if d_pnl <= 0 else
          "mixed (win% down or trades-only)")


if __name__ == "__main__":
    main()
