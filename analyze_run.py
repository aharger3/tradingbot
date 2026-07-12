"""Post-hoc analysis of the 30d backtest: per-stock table, A/A+ focus,
SPY-trend alignment A/B. Run: python analyze_run.py"""
from collections import defaultdict
from datetime import date, timedelta

from backtest_week import htf_bias_for, simulate_day, CORE_SYMBOLS
from backtest_sweep import load_data


def run(days: int = 29):
    ws = (date.today() - timedelta(days=days)).isoformat()
    we = (date.today() - timedelta(days=1)).isoformat()
    data = load_data(days)
    allt, spy_days = [], {}
    for sym, d in data.items():
        prev = None
        for dy in sorted(d["days"]):
            c = d["days"][dy]
            if ws <= dy <= we and len(c) >= 30:
                if sym == "SPY":
                    spy_days[dy] = c
                if prev:
                    pc = d["days"][prev]
                    pdh, pdl = max(x.high for x in pc), min(x.low for x in pc)
                else:
                    pdh = pdl = None
                pmh, pml = d.get("premkt", {}).get(dy, (None, None))
                allt += simulate_day(sym, dy, c, pdh, pdl,
                                     htf_bias_for(d["hourly"], dy), pmh, pml)
            prev = dy
    tr = [t for t in allt if t.counted and t.outcome in ("win", "loss")]

    def stats(ts):
        w = sum(1 for t in ts if t.outcome == "win")
        return len(ts), w, sum(t.pnl for t in ts)

    n, w, p = stats(tr)
    print(f"ALL: {n}tr {w}W {w/max(1,n)*100:.0f}% ${p:+,.0f}")
    for g in ("A+", "A", "B"):
        n, w, p = stats([t for t in tr if t.grade == g])
        print(f"  {g}: {n}tr {w}W {w/max(1,n)*100:.0f}% ${p:+,.0f}")
    aa = [t for t in tr if t.grade in ("A+", "A")]
    n, w, p = stats(aa)
    print(f"A/A+ ONLY: {n}tr ({n/20:.1f}/day) {w/max(1,n)*100:.0f}% ${p:+,.0f}")

    # Two-tier governor sim (Austin 2026-07-07): one TRADE/day across all
    # symbols = first fired B+ chronologically; done after win; 84% re-entry
    # (same symbol) exempt while losses < 2.
    # Matches live _tier (2026-07-07): first A/A+ >= 09:40. First-10-min
    # signals are opening chop (31% win -$3k/30d); first-B+-anytime = -$6k.
    byday = defaultdict(list)
    for t in tr:
        if t.grade in ("A+", "A") and t.entry_time >= "09:40":
            byday[t.day].append(t)
    took = []
    for dy, ts in sorted(byday.items()):
        ts.sort(key=lambda t: t.entry_time)
        losses = 0
        last_sym = None
        for t in ts:
            is84 = t.signal_type == "reentry_84_rule" and t.symbol == last_sym
            if losses >= 2 or (last_sym and not is84):
                continue
            took.append(t)
            last_sym = t.symbol
            if t.outcome == "win":
                break
            losses += 1
    n, w, p = stats(took)
    print(f"GOVERNOR (1 trade/day + 84%): {n}tr ({n/20:.1f}/day) {w/max(1,n)*100:.0f}% ${p:+,.0f}")

    print("\nPER-STOCK (all traded | A/A+ only):")
    bysym = defaultdict(list)
    for t in tr:
        bysym[t.symbol].append(t)
    for sym in sorted(bysym, key=lambda s: -sum(t.pnl for t in bysym[s])):
        n, w, p = stats(bysym[sym])
        na, wa, pa = stats([t for t in bysym[sym] if t.grade in ("A+", "A")])
        tag = "core" if sym in CORE_SYMBOLS else "exp "
        print(f"  {sym:5s} [{tag}] {n:3d}tr {w/max(1,n)*100:3.0f}% ${p:+8,.0f} | A/A+: {na}tr ${pa:+,.0f}")

    # SPY alignment: SPY bias at entry time = above ORH -> bullish, below ORL -> bearish
    print("\nSPY-TREND ALIGNMENT (non-SPY trades):")
    def spy_bias(day, entry_time):
        c = spy_days.get(day)
        if not c:
            return None
        upto = [x for x in c if x.timestamp <= entry_time]
        if len(upto) < 5:
            return None
        orh = max(x.high for x in upto[:5])
        orl = min(x.low for x in upto[:5])
        last = upto[-1].close
        return "bullish" if last > orh else "bearish" if last < orl else "neutral"
    buckets = defaultdict(list)
    for t in tr:
        if t.symbol in ("SPY", "QQQ"):
            continue
        b = spy_bias(t.day, t.entry_time)
        if b is None:
            continue
        aligned = (b == "bullish") == (t.direction == "call") if b != "neutral" else None
        key = "neutral" if aligned is None else ("aligned" if aligned else "counter")
        buckets[key].append(t)
    for k in ("aligned", "neutral", "counter"):
        n, w, p = stats(buckets[k])
        print(f"  {k:8s}: {n}tr {w/max(1,n)*100:3.0f}% ${p:+,.0f}")


if __name__ == "__main__":
    run()
