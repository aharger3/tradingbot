"""R1 referee, SECOND PASS (post-repair) -- independent re-derivation.

Refereed: builder commit 3676a230 (the repair of 738e856d), report
research/g210_fill_arms_v2.md, repair script research/r1_repair.py.
Pass-1 referee: research/r1_referee.{md,py}, commit e5a9ed7f.

Nothing here imports g90_fill_arms, g210_fill_arms_v2 or r1_repair. Every
statistic, fill and exit below is re-implemented against the raw
data_archive/*.csv bars and the stamped books in research/tape/.

Modes:
  stats      -- trades/mean R/$/day/green months/avg win/avg loss, all arms
  lookahead  -- physically truncate the day at the signal bar and re-derive
  close      -- close arm vs the raw tape's own printed close, every row
  scaleplan  -- probe SCALE_PLAN inside real spawned worker processes
  closewalk  -- reprice `close` on a close-only stop (no intrabar disaster)
  sized      -- min_risk_floor applied post hoc, all arms both pools
  achr       -- re-derive the one entry_idx mismatch (ACHR 2026-04-06)
"""
import argparse
import csv
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

TAPE = os.path.join(HERE, "tape")
ARCHIVE = os.path.join(ROOT, "data_archive")
ARMS = ["as_booked", "limit_level", "next_open", "chase_once", "close", "mid_candle"]
POOLS = ["core11", "full29"]
RISK = 1000.0
EXTREME_BUF = 0.05
RETEST_WINDOW = 12
CHASE_PCT = 0.005


def load(arm, pool):
    p = os.path.join(TAPE, f"fillarms_{arm}_{pool}.json.gz")
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


_bars = {}


def bars_for(sym, day):
    """RTH 1-minute bars straight off the archive CSV: (hh:mm:ss,o,h,l,c)."""
    k = (sym, day)
    if k in _bars:
        return _bars[k]
    path = os.path.join(ARCHIVE, sym, f"{day}.csv")
    out = []
    if os.path.exists(path):
        with open(path) as f:
            for r in csv.DictReader(f):
                ts = r["Datetime"]
                hhmm = ts.split("T", 1)[1][:5] if "T" in ts else ts[11:16]
                if hhmm < "09:30" or hhmm >= "16:00":
                    continue
                out.append((hhmm + ":00", float(r["Open"]), float(r["High"]),
                            float(r["Low"]), float(r["Close"])))
    _bars[k] = out
    return out


# ---------------------------------------------------------------- stats
def month(day):
    return day[:7]


def stats2(rows):
    filled = [r for r in rows if not r["unfilled"] and r["r"] is not None]
    n = len(filled)
    total_r = sum(r["r"] for r in filled)
    days = len({r["day"] for r in rows})
    by_m = {}
    for r in filled:
        by_m[month(r["day"])] = by_m.get(month(r["day"]), 0.0) + r["r"]
    wins = [r["r"] for r in filled if r["r"] > 0]
    losses = [r["r"] for r in filled if r["r"] < 0]
    zeros = [r["r"] for r in filled if r["r"] == 0]
    worst_row = min(filled, key=lambda r: r["r"]) if filled else None
    return dict(
        n=n, unfilled=len(rows) - n,
        mean_r=total_r / n if n else None,
        dollar_day=total_r * RISK / days if days else None,
        days=days, months=len(by_m),
        green=sum(1 for v in by_m.values() if v > 0),
        avg_win=sum(wins) / len(wins) if wins else None,
        avg_loss=sum(losses) / len(losses) if losses else None,
        n_win=len(wins), n_loss=len(losses), n_zero=len(zeros),
        wr_pertrade=100.0 * len(wins) / n if n else None,
        worst=worst_row["r"] if worst_row else None,
        worst_who=f"{worst_row['sym']} {worst_row['day']}" if worst_row else "",
        below1r=sum(1 for r in filled if r["r"] < -1.0),
        pnl_matches_r=sum(1 for r in filled if abs(r["pnl"] - r["r"] * RISK) > 0.51),
    )


def cmd_stats(_a):
    print("| pool | arm | trades | unfilled | mean R | $/day | months | green | "
          "avg win | avg loss | per-trade win% | worst R | rows<-1R | pnl!=r*1000 |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for pool in POOLS:
        for arm in ARMS:
            s = stats2(load(arm, pool)["trades"])
            print(f"| {pool} | {arm} | {s['n']} | {s['unfilled']} | {s['mean_r']:+.4f} | "
                  f"${s['dollar_day']:,.0f} | {s['months']} | {s['green']}/{s['months']} | "
                  f"{s['avg_win']:+.4f} | {s['avg_loss']:+.4f} | {s['wr_pertrade']:.1f}% | "
                  f"{s['worst']:+.4f} ({s['worst_who']}) | {s['below1r']} | {s['pnl_matches_r']} |")


# ------------------------------------------------------------ lookahead
def idx_of(bars, ts):
    for i, b in enumerate(bars):
        if b[0] == ts:
            return i
    return None


def resting(bars, level):
    """First bar in `bars` (already truncated) within RETEST_WINDOW whose
    range strictly contains `level` (EXTREME_BUF of the bar's own range
    excluded at each end)."""
    for j, b in enumerate(bars[:RETEST_WINDOW]):
        rng = b[2] - b[3]
        buf = EXTREME_BUF * rng
        if b[3] + buf <= level <= b[2] - buf:
            return level, j, b[0]
    return None, None, None


def cmd_lookahead(a):
    n = a.n
    bad = []
    print(f"| arm | sampled | entry matches | fill bar matches | fill at/<= signal bar |")
    print("|---|---:|---:|---:|---:|")
    for arm in ("next_open", "limit_level", "chase_once", "mid_candle"):
        rows = [r for r in load(arm, "full29")["trades"] if not r["unfilled"]]
        step = max(1, len(rows) // n)
        sample = rows[::step][:n]
        ok_entry = ok_bar = at_or_before = 0
        for r in sample:
            bars = bars_for(r["sym"], r["day"])
            si = idx_of(bars, r["entry_time"])
            if si is None:
                bad.append(f"{arm} {r['sym']} {r['day']}: signal bar {r['entry_time']} not in raw tape")
                continue
            fut = bars[si + 1:]          # PHYSICAL truncation: signal bar and all history gone
            is_long = r["side"] == "call"
            e = ft = None
            if arm == "next_open":
                if fut:
                    e, ft = fut[0][1], fut[0][0]
            elif arm == "chase_once":
                if fut:
                    o, c = fut[0][1], fut[0][4]
                    cand = max(o, c) if is_long else min(o, c)
                    lvl = r["level_price"]
                    if abs(cand - lvl) / lvl <= CHASE_PCT:
                        e, ft = cand, fut[0][0]
            elif arm == "limit_level":
                e, _, ft = resting(fut, r["level_price"])
            elif arm == "mid_candle":
                sb = bars[si]
                mid = (sb[2] + sb[3]) / 2.0
                e, _, ft = resting(fut, mid)
            if e is None:
                bad.append(f"{arm} {r['sym']} {r['day']}: book says filled, truncated re-derivation says no fill")
                continue
            if abs(e - r["entry"]) < 1e-6:
                ok_entry += 1
            else:
                bad.append(f"{arm} {r['sym']} {r['day']}: entry {r['entry']} vs re-derived {e}")
            if ft == r["fill_time"]:
                ok_bar += 1
            else:
                bad.append(f"{arm} {r['sym']} {r['day']}: fill bar {r['fill_time']} vs re-derived {ft}")
            if r["fill_time"] <= r["entry_time"]:
                at_or_before += 1
                bad.append(f"{arm} {r['sym']} {r['day']}: LOOKAHEAD fill_time {r['fill_time']} <= signal {r['entry_time']}")
        print(f"| {arm} | {len(sample)} | {ok_entry} | {ok_bar} | {at_or_before} |")
    print()
    for b in bad:
        print("  FAIL:", b)
    if not bad:
        print("  0 failures.")
    return 1 if bad else 0


# ---------------------------------------------------------------- close
def cmd_close(_a):
    import entry_fill
    print("entry_fill.ENTRY_FILL =", repr(entry_fill.ENTRY_FILL))
    for pool in POOLS:
        rows = load("close", pool)["trades"]
        n = miss = nobar = 0
        examples = []
        for r in rows:
            bars = bars_for(r["sym"], r["day"])
            i = idx_of(bars, r["entry_time"])
            if i is None:
                nobar += 1
                continue
            n += 1
            if abs(bars[i][4] - r["entry"]) > 1e-4:
                miss += 1
                if len(examples) < 5:
                    examples.append(f"{r['sym']} {r['day']} {r['entry_time']}: book {r['entry']} vs tape close {bars[i][4]}")
        print(f"{pool}: {n} rows compared to the raw tape's own close, {miss} mismatches, {nobar} bars missing")
        for e in examples:
            print("   ", e)
    # and the as_booked comparison: are the arms really distinct prices?
    for pool in POOLS:
        cb = load("close", pool)["trades"]
        ab = load("as_booked", pool)["trades"]
        same = sum(1 for a, b in zip(cb, ab)
                   if not b["unfilled"] and abs((a["entry"] or 0) - (b["entry"] or 0)) < 1e-9)
        print(f"{pool}: as_booked entry == close entry on {same} rows")


# ------------------------------------------------------------ scaleplan
def _probe(_i):
    import os as _os
    _os.environ["OMEN_SCALE_PLAN"] = "none"
    import backtest_week as bw
    return (_os.getpid(), repr(bw.SCALE_PLAN), hasattr(bw, "LADDER_MODE"), bw.DISASTER_STOP, bw.DISASTER_R)


def _probe_noenv(_i):
    import os as _os
    _os.environ.pop("OMEN_SCALE_PLAN", None)
    import backtest_week as bw
    return (_os.getpid(), repr(bw.SCALE_PLAN))


def cmd_scaleplan(_a):
    import multiprocessing as mp
    print("start method:", mp.get_start_method())
    os.environ.pop("OMEN_SCALE_PLAN", None)
    with mp.Pool(2) as p:
        print("workers WITH the env set inside the worker (g210's pattern):")
        for row in p.map(_probe, [0, 1]):
            print("   pid=%s SCALE_PLAN=%s hasattr(LADDER_MODE)=%s DISASTER_STOP=%s DISASTER_R=%s" % row)
    with mp.Pool(2) as p:
        print("workers WITHOUT the env (control):")
        for row in p.map(_probe_noenv, [0, 1]):
            print("   pid=%s SCALE_PLAN=%s" % row)


# ------------------------------------------------------------ closewalk
def walk(bars, start, stop, target, is_long):
    """Close-only structural stop + intrabar target, the exit the five
    non-close arms get. Returns (outcome, exit_price)."""
    for j in range(start, len(bars)):
        _, o, h, l, c = bars[j]
        if (c <= stop) if is_long else (c >= stop):
            return "loss", stop
        if (h >= target) if is_long else (l <= target):
            return "win", target
    return "scratch", bars[-1][4]


def cmd_closewalk(a):
    for pool in POOLS:
        rows = load("close", pool)["trades"]
        tot_old = tot_new = 0.0
        flip_b = flip_w = 0
        days = len({r["day"] for r in rows})
        by_m = {}
        n = 0
        for r in rows:
            bars = bars_for(r["sym"], r["day"])
            i = idx_of(bars, r["entry_time"])
            if i is None:
                continue
            n += 1
            is_long = r["side"] == "call"
            e, s = r["entry"], r["stop"]
            risk = (e - s) if is_long else (s - e)
            if risk <= 0:
                new_r = r["r"]
            else:
                t = e + 2 * risk if is_long else e - 2 * risk
                out, px = walk(bars, i + 1, s, t, is_long)
                move = (px - e) if is_long else (e - px)
                new_r = move / risk
            tot_old += r["r"]
            tot_new += new_r
            by_m[month(r["day"])] = by_m.get(month(r["day"]), 0.0) + new_r
            if new_r > r["r"] + 1e-9:
                flip_b += 1
            elif new_r < r["r"] - 1e-9:
                flip_w += 1
        print(f"{pool}: n={n} days={days}")
        print(f"   as booked (simulate_day exit): mean {tot_old/n:+.4f}R  ${tot_old*RISK/days:,.0f}/day")
        print(f"   repriced on the close-only stop: mean {tot_new/n:+.4f}R  ${tot_new*RISK/days:,.0f}/day  "
              f"green {sum(1 for v in by_m.values() if v>0)}/{len(by_m)}")
        print(f"   rows better={flip_b} worse={flip_w}")


# ---------------------------------------------------------------- sized
def min_risk_floor(x):
    return max(0.10, 0.0015 * x)


def cmd_sized(_a):
    print("| pool | arm | trades | mean R | $/day | green/months |")
    print("|---|---|---:|---:|---:|---:|")
    for pool in POOLS:
        for arm in ARMS:
            rows = load(arm, pool)["trades"]
            days = len({r["day"] for r in rows})
            kept = [r for r in rows if not r["unfilled"] and r["r"] is not None
                    and r["entry"] is not None and r["stop"] is not None
                    and abs(r["entry"] - r["stop"]) >= min_risk_floor(r["entry"])]
            if not kept:
                print(f"| {pool} | {arm} | 0 | -- | -- | -- |")
                continue
            tot = sum(r["r"] for r in kept)
            by_m = {}
            for r in kept:
                by_m[month(r["day"])] = by_m.get(month(r["day"]), 0.0) + r["r"]
            print(f"| {pool} | {arm} | {len(kept)} | {tot/len(kept):+.4f} | "
                  f"${tot*RISK/days:,.0f} | {sum(1 for v in by_m.values() if v>0)}/{len(by_m)} |")


# ----------------------------------------------------------------- achr
def cmd_achr(_a):
    os.environ["OMEN_SCALE_PLAN"] = "none"
    import backtest_week as bw
    import signal_runner as sr
    from t8_two_year import day_table, rth_candles, bias_from
    sym, day = "ACHR", "2026-04-06"
    table = day_table(sym)
    days = sorted(table)
    i = days.index(day)
    candles = rth_candles(sym, day)
    prev = days[i - 1]
    pdh, pdl, pdo, pdc = table[prev][0], table[prev][1], table[prev][2], table[prev][3]
    pmh, pml = table[day][4], table[day][5]
    bias = bias_from([table[d][3] for d in days[max(0, i - 40):i]])
    idx_by_id = {id(c): j for j, c in enumerate(candles)}
    mailbox, seen = {}, []
    orig = sr.fill_price

    def wrapped(level, candle, is_long, session_hi=None, session_lo=None):
        res = orig(level, candle, is_long, session_hi=session_hi, session_lo=session_lo)
        mailbox["last"] = (level, candle, is_long)
        return res
    sr.fill_price = wrapped

    class R(bw.BacktestRunner):
        def __init__(self, s):
            super().__init__(s)
            seen.append(self)

        def _route(self, signals, sig):
            super()._route(signals, sig)
            ctx = mailbox.pop("last", None)
            if ctx is not None:
                sig["_level"] = ctx[0]
                sig["_candle_id"] = id(ctx[1])
    bw.BacktestRunner = R
    trades = bw.simulate_day(sym, day, candles, pdh, pdl, bias, pmh, pml, pdo, pdc, None)
    print(f"{sym} {day}: {len(candles)} candles, {len(seen[-1].captured)} captured signals, {len(trades)} trades")
    from collections import defaultdict
    pool = defaultdict(list)
    for sig in seen[-1].captured:
        k = (sig["signal_type"].value, sig["direction"], round(float(sig["entry"]), 4), sig.get("status"))
        pool[k].append(sig)
    for k, v in pool.items():
        if len(v) > 1:
            print("  duplicate key:", k, "-> candle idx",
                  [idx_by_id.get(id(s.get("_candle_id") and None)) for s in v] or None,
                  [idx_by_id.get(s.get("_candle_id")) for s in v])
    for t in trades:
        if not t.counted or t.signal_type == "reentry_84_rule":
            continue
        k = (t.signal_type, t.direction, round(float(t.entry), 4), t.status)
        if len(pool.get(k, [])) > 1:
            print(f"  trade entry_idx={t.entry_idx} entry={t.entry} stop={t.stop} key={k} "
                  f"candidates at idx {[idx_by_id.get(s.get('_candle_id')) for s in pool[k]]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["stats", "lookahead", "close", "scaleplan",
                                    "closewalk", "sized", "achr"])
    ap.add_argument("--n", type=int, default=30)
    a = ap.parse_args()
    return {"stats": cmd_stats, "lookahead": cmd_lookahead, "close": cmd_close,
            "scaleplan": cmd_scaleplan, "closewalk": cmd_closewalk,
            "sized": cmd_sized, "achr": cmd_achr}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
