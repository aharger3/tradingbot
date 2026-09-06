"""R1 referee, THIRD PASS -- independent re-derivation, told to refute.

Imports nothing from `g90_fill_arms.py`, `g210_fill_arms_v2.py`, `r1_repair.py`,
`r1_referee.py` or `r1_referee2.py`. Every bar is read from the raw
`data_archive/<SYM>/<day>.csv` with this file's own RTH filter; every fill,
walk and statistic below is written here from scratch. The only project module
imported is `signal_runner` (for `CHASE_PCT` and `min_risk_floor`), and only in
the two commands that need those constants.

Commands
    stats            re-derive every cell of all 12 stamped books
    lookahead --n N  truncate the day's bars at the signal bar and re-derive
                     the fill for next_open / limit_level / chase_once /
                     mid_candle from the truncated list alone
    closecheck       every row of the close book vs the raw archive close
    scaleplan        prove bw.SCALE_PLAN is None INSIDE a spawned worker
    achr             re-derive the one entry_idx mismatch (ACHR 2026-04-06)
    uniform          price ALL SIX arms under ONE exit model, twice: the
                     close-only stop the five _walk arms get, and the
                     intrabar-touch stop the engine gives `close`
"""
import os
import sys
import csv
import json
import gzip
import argparse
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARCHIVE = os.path.join(ROOT, "data_archive")
TAPE = os.path.join(HERE, "tape")

ARMS = ["as_booked", "limit_level", "next_open", "chase_once", "close", "mid_candle"]
POOLS = ["core11", "full29"]
RISK_DOLLARS = 1000.0
EXTREME_BUF = 0.05
RETEST_WINDOW = 12


# ------------------------------------------------------------------ raw bars
_BARCACHE = {}


def bars(sym, day):
    """RTH 1-minute bars straight out of the archive CSV. Own loader."""
    key = (sym, day)
    if key in _BARCACHE:
        return _BARCACHE[key]
    path = os.path.join(ARCHIVE, sym, "%s.csv" % day)
    out = []
    if os.path.exists(path):
        with open(path) as f:
            for r in csv.DictReader(f):
                ts = r["Datetime"]
                hhmm = ts.split("T", 1)[1][:5] if "T" in ts else ts[11:16]
                if hhmm < "09:30" or hhmm >= "16:00":
                    continue
                out.append({"t": hhmm, "o": float(r["Open"]), "h": float(r["High"]),
                            "l": float(r["Low"]), "c": float(r["Close"])})
    if len(_BARCACHE) > 400:
        _BARCACHE.clear()
    _BARCACHE[key] = out
    return out


def idx_at(bs, hhmm):
    for i, b in enumerate(bs):
        if b["t"] == hhmm:
            return i
    return None


def load(arm, pool):
    p = os.path.join(TAPE, "fillarms_%s_%s.json.gz" % (arm, pool))
    with gzip.open(p, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


# ------------------------------------------------------------------ 1. stats
def cmd_stats(a):
    print("book                              rows traded unfil   meanR   "
          "avgW    avgL   win%%(wl) win%%(all)  mo grn   $/day")
    for pool in POOLS:
        for arm in ARMS:
            meta, rows = load(arm, pool)
            traded = [r for r in rows if not r["unfilled"]]
            n = len(traded)
            rs = [r["r"] for r in traded]
            total_r = sum(rs)
            mean_r = total_r / n if n else 0.0
            wins = [x for x in rs if x > 0]
            losses = [x for x in rs if x < 0]
            # "wl" definition: exactly +2R win / exactly -1R loss (what _walk
            # returns), scratches dropped -- the report's denominator.
            w_exact = [x for x in rs if abs(x - 2.0) < 1e-9]
            l_exact = [x for x in rs if abs(x + 1.0) < 1e-9]
            by_month = defaultdict(float)
            for r in traded:
                by_month[r["day"][:7]] += r["r"]
            months = len(by_month)
            green = sum(1 for v in by_month.values() if v > 0)
            days = len({r["day"] for r in rows})
            dpd = total_r * RISK_DOLLARS / days if days else 0.0
            wr_wl = (100.0 * len(w_exact) / (len(w_exact) + len(l_exact))
                     if (w_exact or l_exact) else float("nan"))
            wr_all = 100.0 * len(wins) / n if n else float("nan")
            print("%-32s %5d %6d %5d %+8.4f %+7.4f %+7.4f  %6.1f  %7.1f  %2d %3d %8.0f"
                  % ("%s/%s" % (arm, pool), len(rows), n, len(rows) - n, mean_r,
                     sum(wins) / len(wins) if wins else 0.0,
                     sum(losses) / len(losses) if losses else 0.0,
                     wr_wl, wr_all, months, green, dpd))
    print("\nunit: every traded signal (fired, legacy grade != C, reentry_84_rule "
          "excluded). exit: as booked in each book. fill: the arm named. "
          "script: research/r1_referee3.py stats")


# -------------------------------------------------------------- 2. lookahead
def _resting(bs, start, price):
    hi = min(len(bs), start + RETEST_WINDOW)
    for j in range(start, hi):
        b = bs[j]
        rng = b["h"] - b["l"]
        buf = EXTREME_BUF * rng
        if b["l"] + buf <= price <= b["h"] - buf:
            return price, j
    return None, None


def cmd_lookahead(a):
    from signal_runner import CHASE_PCT
    bad = 0
    for arm in ("next_open", "limit_level", "chase_once", "mid_candle"):
        meta, rows = load(arm, "full29")
        filled = [r for r in rows if not r["unfilled"]]
        step = max(1, len(filled) // a.n)
        sample = filled[::step][:a.n]
        ok = mism = early = missing = 0
        first_bad = []
        for r in sample:
            bs = bars(r["sym"], r["day"])
            si = idx_at(bs, r["entry_time"][:5])
            if si is None:
                missing += 1
                continue
            # PHYSICAL TRUNCATION: everything at or before the signal bar is
            # deleted before the fill is re-derived. `mid_candle`'s price
            # reference (the completed signal bar's own high/low) is captured
            # first and passed in as a scalar -- the bar list the fill scan
            # sees starts strictly after the signal bar.
            sig_hi, sig_lo = bs[si]["h"], bs[si]["l"]
            fwd = bs[si + 1:]
            ent = ftime = None
            if arm == "next_open":
                if fwd:
                    ent, ftime = fwd[0]["o"], fwd[0]["t"]
            elif arm == "chase_once":
                if fwd:
                    is_long = r["side"] == "call"
                    cand = max(fwd[0]["o"], fwd[0]["c"]) if is_long else min(fwd[0]["o"], fwd[0]["c"])
                    if abs(cand - r["level_price"]) / r["level_price"] <= CHASE_PCT:
                        ent, ftime = cand, fwd[0]["t"]
            elif arm == "limit_level":
                p, j = _resting(fwd, 0, r["level_price"])
                if p is not None:
                    ent, ftime = p, fwd[j]["t"]
            else:  # mid_candle
                mid = (sig_hi + sig_lo) / 2.0
                p, j = _resting(fwd, 0, mid)
                if p is not None:
                    ent, ftime = p, fwd[j]["t"]
            if ent is None:
                mism += 1
                first_bad.append((r["sym"], r["day"], r["entry_time"], "no fill on truncated list"))
                continue
            if ftime <= r["entry_time"][:5]:
                early += 1
            if abs(ent - r["entry"]) > 6e-5 or ftime != r["fill_time"][:5]:
                mism += 1
                if len(first_bad) < 5:
                    first_bad.append((r["sym"], r["day"], r["entry_time"],
                                      "book %.4f@%s vs truncated %.4f@%s"
                                      % (r["entry"], r["fill_time"][:5], ent, ftime)))
            else:
                ok += 1
        bad += mism + early
        print("%-12s sampled %2d  match %2d  mismatch %2d  fill-bar<=signal-bar %d  bar-missing %d"
              % (arm, len(sample), ok, mism, early, missing))
        for b in first_bad[:5]:
            print("     ", b)
    print("\nVERDICT: %s" % ("no lookahead found" if bad == 0 else "PROBLEM (%d)" % bad))
    return bad


# ------------------------------------------------------------- 3. closecheck
def cmd_closecheck(a):
    import entry_fill
    print("entry_fill.ENTRY_FILL=%r  needs_future_bars=%r"
          % (entry_fill.ENTRY_FILL, entry_fill.needs_future_bars()))
    meta, rows = load("close", "full29")
    n = bad = nobar = 0
    ex = []
    for r in rows:
        bs = bars(r["sym"], r["day"])
        i = idx_at(bs, r["entry_time"][:5])
        if i is None:
            nobar += 1
            continue
        n += 1
        if abs(bs[i]["c"] - r["entry"]) > 1e-4:
            bad += 1
            if len(ex) < 5:
                ex.append((r["sym"], r["day"], r["entry_time"], r["entry"], bs[i]["c"]))
    print("close book: %d rows, %d checked against the raw archive close, %d mismatches, %d bars missing"
          % (len(rows), n, bad, nobar))
    for e in ex:
        print("   ", e)
    # and prove close != as_booked, i.e. the arms are distinct prices
    _, ab = load("as_booked", "full29")
    key = {(r["sym"], r["day"], r["entry_time"]): r["entry"] for r in ab}
    same = sum(1 for r in rows
               if key.get((r["sym"], r["day"], r["entry_time"])) is not None
               and abs(key[(r["sym"], r["day"], r["entry_time"])] - r["entry"]) < 1e-9)
    print("rows where as_booked entry == close entry: %d" % same)
    return bad


# --------------------------------------------------------------- 4. scaleplan
def _worker_probe(_):
    os.environ["OMEN_SCALE_PLAN"] = "none"
    import backtest_week as bw
    return (os.getpid(), repr(bw.SCALE_PLAN), bw.DISASTER_STOP, bw.DISASTER_R,
            hasattr(bw, "LADDER_MODE"))


def _worker_probe_noenv(_):
    import backtest_week as bw
    return (os.getpid(), repr(bw.SCALE_PLAN))


def cmd_scaleplan(a):
    import multiprocessing as mp
    print("start method:", mp.get_start_method())
    with mp.Pool(2) as p:
        for row in p.map(_worker_probe, [0, 1]):
            print("  worker(env set) pid=%s SCALE_PLAN=%s DISASTER_STOP=%s DISASTER_R=%s "
                  "hasattr(bw,'LADDER_MODE')=%s" % row)
    with mp.Pool(2) as p:
        for row in p.map(_worker_probe_noenv, [0, 1]):
            print("  worker(no env)  pid=%s SCALE_PLAN=%s" % row)
    import backtest_week as bw
    print("  parent (no env) SCALE_PLAN=%r" % bw.SCALE_PLAN)


# -------------------------------------------------------------------- 5. achr
def cmd_achr(a):
    os.environ["OMEN_SCALE_PLAN"] = "none"
    sys.path.insert(0, ROOT)
    sys.path.insert(0, HERE)
    from t8_two_year import day_table, rth_candles, bias_from
    import backtest_week as bw
    import signal_runner as sr
    assert bw.SCALE_PLAN is None, bw.SCALE_PLAN

    sym, day = "ACHR", "2026-04-06"
    mailbox = {}
    orig = sr.fill_price

    def wrapped(level, candle, is_long, session_hi=None, session_lo=None):
        res = orig(level, candle, is_long, session_hi=session_hi, session_lo=session_lo)
        mailbox["last"] = (level, candle, is_long)
        return res
    sr.fill_price = wrapped

    seen = []

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
    ob = bw.BacktestRunner
    bw.BacktestRunner = R
    table = day_table(sym)
    days = sorted(table)
    i = days.index(day)
    candles = rth_candles(sym, day)
    prev = days[i - 1]
    pdh, pdl, pdo, pdc = table[prev][0], table[prev][1], table[prev][2], table[prev][3]
    pmh, pml = table[day][4], table[day][5]
    bias = bias_from([table[d][3] for d in days[max(0, i - 40):i]])
    idx_by_id = {id(c): j for j, c in enumerate(candles)}
    trades = bw.simulate_day(sym, day, candles, pdh, pdl, bias, pmh, pml, pdo, pdc, None)
    bw.BacktestRunner = ob
    sr.fill_price = orig

    caps = seen[-1].captured
    print("%s %s: %d bars, %d captured signals, %d trades" % (sym, day, len(candles), len(caps), len(trades)))
    pool = defaultdict(list)
    for s in caps:
        k = (s["signal_type"].value, s["direction"], round(float(s["entry"]), 4), s.get("status"))
        pool[k].append(s)
    for k, v in sorted(pool.items(), key=lambda kv: str(kv[0])):
        if len(v) > 1:
            print("  COLLIDING KEY %s -> %d signals at candle idx %s"
                  % (str(k), len(v), [idx_by_id.get(id(s["_candle_id"])) if False else
                                      idx_by_id.get(s["_candle_id"]) for s in v]))
    used = defaultdict(int)
    for t in trades:
        if not t.counted or t.signal_type == "reentry_84_rule":
            continue
        k = (t.signal_type, t.direction, round(float(t.entry), 4), t.status)
        lst = pool.get(k) or []
        n = used[k]
        if n >= len(lst):
            continue
        s = lst[n]
        used[k] += 1
        ei = idx_by_id.get(s.get("_candle_id"))
        if ei != t.entry_idx:
            print("  MISMATCH: %s %s entry=%.4f stop=%.4f  trade.entry_idx=%s  paired-signal idx=%s"
                  % (t.signal_type, t.direction, t.entry, t.stop, t.entry_idx, ei))


# ----------------------------------------------------------------- 6. uniform
def _walk_close_stop(bs, start, stop, target, is_long):
    """Stop triggers only on a candle CLOSE through the level, fills AT the
    level. Target on an intrabar touch. (What the five _walk arms get.)"""
    for j in range(start, len(bs)):
        b = bs[j]
        if (b["c"] <= stop) if is_long else (b["c"] >= stop):
            return "loss", stop
        if (b["h"] >= target) if is_long else (b["l"] <= target):
            return "win", target
    return "scratch", bs[-1]["c"] if bs else stop


def _walk_touch_stop(bs, start, stop, target, is_long):
    """Stop is a RESTING order at the level, filled on an intrabar TOUCH --
    the engine's DISASTER_STOP at 1R, which for these trades sits exactly on
    the structural stop. Stop checked before target within a bar."""
    for j in range(start, len(bs)):
        b = bs[j]
        if (b["l"] <= stop) if is_long else (b["h"] >= stop):
            return "loss", stop
        if (b["h"] >= target) if is_long else (b["l"] <= target):
            return "win", target
    return "scratch", bs[-1]["c"] if bs else stop


SCRATCH_ARMS = ("as_booked", "limit_level", "mid_candle")


def _reprice(arm, pool, walker):
    meta, rows = load(arm, pool)
    days = len({r["day"] for r in rows})
    total_r = 0.0
    n = 0
    by_month = defaultdict(float)
    skipped = 0
    for r in rows:
        if r["unfilled"]:
            continue
        bs = bars(r["sym"], r["day"])
        fi = idx_at(bs, (r["fill_time"] or r["entry_time"])[:5])
        if fi is None:
            skipped += 1
            continue
        is_long = r["side"] == "call"
        entry, stop = r["entry"], r["stop"]
        risk = (entry - stop) if is_long else (stop - entry)
        if risk <= 0:
            skipped += 1
            continue
        target = entry + 2 * risk if is_long else entry - 2 * risk
        fb = bs[fi]
        outcome = px = None
        if arm in SCRATCH_ARMS:
            if (fb["c"] < stop) if is_long else (fb["c"] > stop):
                outcome, px = "scratch", fb["c"]
        if outcome is None:
            outcome, px = walker(bs, fi + 1, stop, target, is_long)
        move = (px - entry) if is_long else (entry - px)
        rr = move / risk
        total_r += rr
        n += 1
        by_month[r["day"][:7]] += rr
    return dict(n=n, mean_r=total_r / n if n else 0.0,
                dpd=total_r * RISK_DOLLARS / days if days else 0.0,
                months=len(by_month),
                green=sum(1 for v in by_month.values() if v > 0),
                skipped=skipped)


def _per_row_r(arm, pool, walker):
    """{(sym,day,entry_time): R} for one arm under one exit model."""
    meta, rows = load(arm, pool)
    out = {}
    for r in rows:
        if r["unfilled"]:
            continue
        bs = bars(r["sym"], r["day"])
        fi = idx_at(bs, (r["fill_time"] or r["entry_time"])[:5])
        if fi is None:
            continue
        is_long = r["side"] == "call"
        entry, stop = r["entry"], r["stop"]
        risk = (entry - stop) if is_long else (stop - entry)
        if risk <= 0:
            continue
        target = entry + 2 * risk if is_long else entry - 2 * risk
        fb = bs[fi]
        outcome = px = None
        if arm in SCRATCH_ARMS:
            if (fb["c"] < stop) if is_long else (fb["c"] > stop):
                outcome, px = "scratch", fb["c"]
        if outcome is None:
            outcome, px = walker(bs, fi + 1, stop, target, is_long)
        move = (px - entry) if is_long else (entry - px)
        out[(r["sym"], r["day"], r["entry_time"])] = move / risk
    return out


def cmd_pairci(a):
    """Paired 95% CI on next_open - close, held to ONE exit model."""
    for pool in ([a.pool] if a.pool else POOLS):
        for label, walker in (("A close-only stop", _walk_close_stop),
                              ("B intrabar-touch stop", _walk_touch_stop)):
            x = _per_row_r("next_open", pool, walker)
            y = _per_row_r("close", pool, walker)
            keys = [k for k in x if k in y]
            d = [x[k] - y[k] for k in keys]
            n = len(d)
            m = sum(d) / n
            var = sum((v - m) ** 2 for v in d) / (n - 1)
            se = (var / n) ** 0.5
            print("%s / %-24s paired n=%d  mean(next_open-close)=%+.4fR  "
                  "95%% CI [%+.4f, %+.4f]  %s"
                  % (pool, label, n, m, m - 1.96 * se, m + 1.96 * se,
                     "SEPARATED" if (m - 1.96 * se) * (m + 1.96 * se) > 0 else "OVERLAPS ZERO"))


def cmd_uniform(a):
    for pool in ([a.pool] if a.pool else POOLS):
        for label, walker in (("A: close-only stop (what the five _walk arms get)", _walk_close_stop),
                              ("B: intrabar-touch stop (what the engine gives `close`)", _walk_touch_stop)):
            print("\n== %s -- %s" % (pool, label))
            print("arm            trades    meanR    $/day  green   skipped")
            res = {}
            for arm in ARMS:
                s = _reprice(arm, pool, walker)
                res[arm] = s
                print("%-12s %7d %+8.4f %8.0f  %2d/%2d %7d"
                      % (arm, s["n"], s["mean_r"], s["dpd"], s["green"], s["months"], s["skipped"]))
            order = sorted(res, key=lambda k: -res[k]["mean_r"])
            print("ranking by mean R: " + " > ".join(order))
    print("\nunit: every traded signal. exit: ONE model per block, named above. "
          "fill: the arm named. script: research/r1_referee3.py uniform")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats")
    p = sub.add_parser("lookahead")
    p.add_argument("--n", type=int, default=30)
    sub.add_parser("closecheck")
    sub.add_parser("scaleplan")
    sub.add_parser("achr")
    p = sub.add_parser("uniform")
    p.add_argument("--pool", default=None)
    p = sub.add_parser("pairci")
    p.add_argument("--pool", default=None)
    a = ap.parse_args()
    sys.path.insert(0, ROOT)
    sys.path.insert(0, HERE)
    return {"stats": cmd_stats, "lookahead": cmd_lookahead, "closecheck": cmd_closecheck,
            "scaleplan": cmd_scaleplan, "achr": cmd_achr, "uniform": cmd_uniform,
            "pairci": cmd_pairci}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(0 if not main() else 1)
