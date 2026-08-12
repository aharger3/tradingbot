"""T8 -- two-year backtest of the omen-5.0 engine, split three ways by pool and
four ways by Austin's own tier scale.

Runs `backtest_week.simulate_day` unchanged, at the committed omen-5.0 defaults
(STOP_ON_CLOSE=1, LADDER_MODE="B", the 09:30-11:00 gate inside detect_signals,
pivot levels on, T11's S quality clauses on). Nothing here tunes anything -- the
only additions are (1) carrying each signal's `austin_tier` through to its trade
and (2) applying `rank_s_plus`'s rule ACROSS the universe per day, which is where
S+ actually lives (the cap is 1-3 a day universe-wide, not per symbol).

Output: research/t8_two_year.md + research/t8_two_year.json
"""
import os, sys, csv, glob, json, argparse
from collections import defaultdict
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE) if os.path.basename(HERE) == "research" else HERE
sys.path.insert(0, ROOT)

from omen_bot import Candle
from universe import MAJOR_15, INDEX_POOL, OTHER_POOL, POOL_OF

ARCHIVE = os.path.join(ROOT, "data_archive")
OUT_MD = os.path.join(ROOT, "research", "t8_two_year.md")
OUT_JSON = os.path.join(ROOT, "research", "t8_two_year.json")

POOLS = [("MAJOR_15", MAJOR_15), ("INDEX_POOL", INDEX_POOL), ("OTHER_POOL", OTHER_POOL)]
TIERS = ["S+", "S", "A", "C"]


def _hhmm(d):
    return d[11:16]


def day_table(symbol):
    out = {}
    for path in sorted(glob.glob(os.path.join(ARCHIVE, symbol, "*.csv"))):
        day = os.path.basename(path)[:-4]
        rth_h = rth_l = rth_o = rth_c = None
        pm_h = pm_l = None
        with open(path) as f:
            for r in csv.DictReader(f):
                t = _hhmm(r["Datetime"])
                h, l, o, cl = float(r["High"]), float(r["Low"]), float(r["Open"]), float(r["Close"])
                if t < "09:30":
                    if "04:00" <= t:
                        pm_h = h if pm_h is None else max(pm_h, h)
                        pm_l = l if pm_l is None else min(pm_l, l)
                    continue
                if t >= "16:00":
                    continue
                if rth_h is None:
                    rth_h, rth_l, rth_o = h, l, o
                else:
                    rth_h, rth_l = max(rth_h, h), min(rth_l, l)
                rth_c = cl
        if rth_h is not None:
            out[day] = (rth_h, rth_l, rth_o, rth_c, pm_h, pm_l)
    return out


def rth_candles(symbol, day):
    path = os.path.join(ARCHIVE, symbol, f"{day}.csv")
    if not os.path.exists(path):
        return None
    bars = []
    with open(path) as f:
        for r in csv.DictReader(f):
            t = _hhmm(r["Datetime"])
            if t < "09:30" or t >= "16:00":
                continue
            bars.append(Candle(timestamp=t + ":00", open=float(r["Open"]),
                               high=float(r["High"]), low=float(r["Low"]),
                               close=float(r["Close"]), volume=int(float(r["Volume"] or 0))))
    return bars or None


def bias_from(closes):
    if len(closes) < 20:
        return None
    sma = sum(closes[-20:]) / 20
    last = closes[-1]
    if last > sma * 1.001:
        return "bullish"
    if last < sma * 0.999:
        return "bearish"
    return "neutral"


def run_symbol(args):
    """One symbol, full range. Returns (symbol, rows, days_run)."""
    symbol, start_day, end_day = args
    import backtest_week as bw

    # the committed omen-5.0 defaults, restated so a stray env var can't move them
    bw.STOP_ON_CLOSE, bw.LADDER_MODE = True, "B"

    # carry austin_tier from the sig dict onto the trade: BacktestRunner keeps
    # every sig it routed in .captured, so register each runner as it is built
    # and join afterwards on the fields both objects share.
    seen_runners = []
    orig_init = bw.BacktestRunner.__init__

    def init(self, sym):
        orig_init(self, sym)
        seen_runners.append(self)
    bw.BacktestRunner.__init__ = init

    table = day_table(symbol)
    days = sorted(table)
    rows, days_run = [], 0
    for i, day in enumerate(days):
        if day < start_day or day > end_day:
            continue
        candles = rth_candles(symbol, day)
        if not candles or len(candles) < 60:
            continue
        prev = days[i - 1] if i else None
        pdh = pdl = pdo = pdc = None
        if prev:
            pdh, pdl, pdo, pdc = table[prev][0], table[prev][1], table[prev][2], table[prev][3]
        pmh, pml = table[day][4], table[day][5]
        bias = bias_from([table[d][3] for d in days[max(0, i - 40):i]])

        del seen_runners[:]
        trades = bw.simulate_day(symbol, day, candles, pdh, pdl, bias, pmh, pml, pdo, pdc, None)
        days_run += 1

        # join trade -> sig on (setup, direction, entry, status); first unused wins
        pool = defaultdict(list)
        if seen_runners:
            for sig in seen_runners[-1].captured:
                k = (sig["signal_type"].value, sig["direction"], round(float(sig["entry"]), 4),
                     sig.get("status"))
                pool[k].append(sig)
        used = defaultdict(int)
        for t in trades:
            k = (t.signal_type, t.direction, round(float(t.entry), 4), t.status)
            tier = None
            lst = pool.get(k) or []
            n = used[k]
            if n < len(lst):
                tier = lst[n].get("austin_tier")
                used[k] += 1
            rows.append({"symbol": t.symbol, "day": t.day, "time": t.entry_time,
                         "setup": t.signal_type, "dir": t.direction,
                         "grade": t.grade, "tier": tier, "status": t.status,
                         "outcome": t.outcome, "counted": t.counted, "pnl": t.pnl,
                         "r": round(t.pnl / 1000.0, 4)})

    bw.BacktestRunner.__init__ = orig_init
    return symbol, rows, days_run


def mark_s_plus(rows, cap=3):
    """S+ is a universe-wide daily rank, not a per-symbol one: the earliest `cap`
    S signals of the day are S+, ties broken by engine grade, and nothing is
    dropped -- the rest stay S. Mirrors signal_runner.rank_s_plus."""
    order = {"A+": 0, "A": 1, "B": 2, "C": 3}
    by_day = defaultdict(list)
    for r in rows:
        if r["tier"] == "S":
            by_day[r["day"]].append(r)
    for day, sigs in by_day.items():
        sigs.sort(key=lambda r: (r["time"], order.get(r["grade"], 9)))
        for r in sigs[:cap]:
            r["tier"] = "S+"


def stats(rows):
    n = len(rows)
    if not n:
        return dict(n=0, w=0, l=0, scratch=0, wr=None, pnl=0.0, avg=None)
    w = sum(1 for r in rows if r["outcome"] == "win")
    l = sum(1 for r in rows if r["outcome"] == "loss")
    sc = sum(1 for r in rows if r["outcome"] == "scratch")
    pnl = sum(r["pnl"] for r in rows)
    dec = w + l
    return dict(n=n, w=w, l=l, scratch=sc,
                wr=(100.0 * w / dec) if dec else None,
                pnl=round(pnl, 2), avg=round(pnl / n, 2))


def row(label, s):
    wr = f"{s['wr']:.1f}%" if s["wr"] is not None else "--"
    avg = f"${s['avg']:,.0f}" if s["avg"] is not None else "--"
    return (f"| {label} | {s['n']} | {s['w']} | {s['l']} | {s['scratch']} | "
            f"{wr} | ${s['pnl']:,.0f} | {avg} |")


HEAD = "| | trades | W | L | scratch | win rate | P&L | avg/trade |\n|---|---|---|---|---|---|---|---|"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2024-08-12")
    ap.add_argument("--end", default="2026-08-11")
    ap.add_argument("--procs", type=int, default=6)
    ap.add_argument("--pools", default="", help="comma-separated pool names to restrict to")
    ap.add_argument("--rows-out", default="", help="dump every trade row to this JSON path")
    ap.add_argument("--md-out", default="", help="override the report path")
    a = ap.parse_args()

    global POOLS, OUT_MD, OUT_JSON
    if a.pools:
        want = {x.strip() for x in a.pools.split(",")}
        POOLS = [(n, p) for n, p in POOLS if n in want]
    if a.md_out:
        OUT_MD = a.md_out
        OUT_JSON = os.path.splitext(a.md_out)[0] + ".json"

    syms = [s for _, p in POOLS for s in p if os.path.isdir(os.path.join(ARCHIVE, s))]
    missing = [s for _, p in POOLS for s in p if not os.path.isdir(os.path.join(ARCHIVE, s))]
    print(f"symbols: {len(syms)}  missing archive: {missing or 'none'}", flush=True)

    args = [(s, a.start, a.end) for s in syms]
    rows, per_sym_days = [], {}
    with Pool(a.procs) as pool:
        for sym, r, d in pool.imap_unordered(run_symbol, args):
            rows.extend(r)
            per_sym_days[sym] = d
            print(f"  {sym}: {len(r)} trades over {d} days", flush=True)

    mark_s_plus(rows)

    traded = [r for r in rows if r["counted"]]          # fired, engine grade != C
    alerts = [r for r in rows if r["status"] == "fired" and r["grade"] == "C"]
    fired = traded + alerts

    days = sorted({r["day"] for r in rows})
    out = {"start": a.start, "end": a.end, "symbols": len(syms),
           "trading_days": len(days), "first_day": days[0] if days else None,
           "last_day": days[-1] if days else None,
           "fired": len(fired), "counted": len(traded), "alerts_C": len(alerts)}

    L = []
    L.append("# T8 -- two-year backtest of the omen-5.0 engine, by pool and by tier\n")
    L.append(f"`backtest_week.simulate_day` at the committed omen-5.0 defaults "
             f"(`STOP_ON_CLOSE=1`, `LADDER_MODE=B`, the 09:30-11:00 gate inside "
             f"`detect_signals`, pivot levels on, T11's S clauses on), replayed over "
             f"**{a.start} to {a.end}** ({len(days)} trading days) across "
             f"**{len(syms)} symbols** in the three tracked pools. $1,000 risk per "
             f"trade. Win rate counts decided trades only (scratches excluded from "
             f"the denominator, kept in P&L).\n")
    if missing:
        L.append(f"**No archive, excluded:** {', '.join(missing)}\n")

    L.append("## Whole run\n")
    L.append(HEAD)
    L.append(row("all fired", stats(fired)))
    L.append(row("traded (engine A+/A/B)", stats(traded)))
    L.append(row("C alerts (not traded)", stats(alerts)))
    L.append("")

    L.append("## By pool\n")
    L.append(HEAD)
    for name, syms_p in POOLS:
        sset = set(syms_p)
        L.append(row(f"**{name}**", stats([r for r in traded if r["symbol"] in sset])))
    L.append("")

    L.append("## By tier (Austin's scale)\n")
    L.append(HEAD)
    for t in TIERS:
        L.append(row(f"**{t}**", stats([r for r in fired if r["tier"] == t])))
    untiered = [r for r in fired if r["tier"] not in TIERS]
    if untiered:
        L.append(row("no tier", stats(untiered)))
    L.append("")

    L.append("## Pool x tier\n")
    L.append("| pool | tier | trades | W | L | scratch | win rate | P&L | avg/trade |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for name, syms_p in POOLS:
        sset = set(syms_p)
        for t in TIERS:
            sub = [r for r in fired if r["symbol"] in sset and r["tier"] == t]
            if not sub:
                continue
            s = stats(sub)
            wr = f"{s['wr']:.1f}%" if s["wr"] is not None else "--"
            avg = f"${s['avg']:,.0f}" if s["avg"] is not None else "--"
            L.append(f"| {name} | {t} | {s['n']} | {s['w']} | {s['l']} | {s['scratch']} | "
                     f"{wr} | ${s['pnl']:,.0f} | {avg} |")
    L.append("")

    L.append("## By setup\n")
    L.append(HEAD)
    for st in sorted({r["setup"] for r in fired}):
        L.append(row(st, stats([r for r in fired if r["setup"] == st])))
    L.append("")

    L.append("## Rates\n")
    nd = len(days) or 1
    for t in TIERS:
        c = sum(1 for r in fired if r["tier"] == t)
        L.append(f"- **{t}**: {c} over {nd} trading days = **{c/nd:.2f}/day** universe-wide")
    L.append("")

    out["by_pool"] = {n: stats([r for r in traded if r["symbol"] in set(p)]) for n, p in POOLS}
    out["by_tier"] = {t: stats([r for r in fired if r["tier"] == t]) for t in TIERS}
    out["by_setup"] = {st: stats([r for r in fired if r["setup"] == st])
                       for st in sorted({r["setup"] for r in fired})}
    out["per_day"] = {t: round(sum(1 for r in fired if r["tier"] == t) / nd, 3) for t in TIERS}

    if a.rows_out:
        with open(a.rows_out, "w") as f:
            json.dump(rows, f)
        print(f"wrote {a.rows_out} ({len(rows)} rows)")

    with open(OUT_MD, "w") as f:
        f.write("\n".join(L))
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=2)
    print("\n".join(L))
    print(f"\nwrote {OUT_MD}")


if __name__ == "__main__":
    main()
