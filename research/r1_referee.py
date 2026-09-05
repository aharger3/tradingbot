"""R1 referee -- independent re-derivation of every number and mechanism the
R1 builder (commit 738e856d) published in research/g210_fill_arms_v2.md.

Nothing here imports g210_fill_arms_v2's or g90_fill_arms's arithmetic. Stats,
fills and the lookahead truncation test are re-implemented from scratch against
the raw archive CSVs and the stamped books in research/tape/.

Subcommands:
  stats      recompute every arm's headline row from its own book
  lookahead  physically truncate each sampled row's day at the signal bar and
             re-derive next_open / limit_level / chase_once / mid_candle
  close      confirm the close arm == the raw tape's own close on 100% of rows
  achr       re-derive the single entry_idx mismatch the builder diagnosed
  scaleplan  probe bw.SCALE_PLAN INSIDE a spawned worker, and in the parent
  losses     the DISASTER_STOP asymmetry: who can book worse than -1R
"""
import os
import sys
import csv
import gzip
import json
import argparse
from collections import defaultdict

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


def load(arm, pool):
    p = os.path.join(TAPE, f"fillarms_{arm}_{pool}.json.gz")
    with gzip.open(p, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


# ------------------------------------------------------------------ 1. stats
def recompute(rows):
    filled = [r for r in rows if not r["unfilled"]]
    n = len(filled)
    rs = [r["r"] for r in filled]
    wins = [r for r in filled if r["r"] > 0]
    losses = [r for r in filled if r["r"] < 0]
    # outcome label is not in the flat book; classify by sign, and separately
    # count exact +2R / exact -1R so the "avg win 2.0 / avg loss -1.0" claim
    # can be checked for being an artefact rather than a measurement.
    exact_win = sum(1 for r in filled if abs(r["r"] - 2.0) < 1e-9)
    exact_loss = sum(1 for r in filled if abs(r["r"] + 1.0) < 1e-9)
    worse_than_1r = sum(1 for r in filled if r["r"] < -1.0 + 1e-9 and abs(r["r"] + 1.0) > 1e-9)
    total_r = sum(rs)
    by_month = defaultdict(float)
    for r in filled:
        by_month[r["day"][:7]] += r["r"]
    total_days = len({r["day"] for r in rows})
    dec = len(wins) + len(losses)
    return dict(
        n=n, unfilled=len(rows) - n,
        wr=round(100.0 * len(wins) / dec, 1) if dec else None,
        mean_r=round(total_r / n, 4) if n else None,
        avg_win=round(sum(x["r"] for x in wins) / len(wins), 4) if wins else None,
        avg_loss=round(sum(x["r"] for x in losses) / len(losses), 4) if losses else None,
        months=len(by_month),
        green=sum(1 for v in by_month.values() if v > 1e-9),
        dollar_day=round(total_r * RISK / total_days, 0) if total_days else None,
        days=total_days, exact_2r=exact_win, exact_m1r=exact_loss,
        worse_than_m1r=worse_than_1r,
        total_pnl=round(sum(r["pnl"] for r in filled), 0),
    )


def cmd_stats(_a):
    for pool in POOLS:
        print(f"\n=== {pool} (referee recomputation, own code) ===")
        print("arm          trades unfil   win%   meanR   avgW   avgL  mo green  $/day   days  =2R  =-1R  <-1R")
        for arm in ARMS:
            meta, rows = load(arm, pool)
            s = recompute(rows)
            print(f"{arm:<12} {s['n']:>6} {s['unfilled']:>5} {str(s['wr']):>6} "
                  f"{s['mean_r']:>+8.4f} {s['avg_win']:>6} {s['avg_loss']:>6} "
                  f"{s['months']:>3} {s['green']:>3}   ${s['dollar_day']:>8,.0f} "
                  f"{s['days']:>5} {s['exact_2r']:>4} {s['exact_m1r']:>5} {s['worse_than_m1r']:>4}")


# --------------------------------------------------------------- 2. lookahead
def raw_rth(sym, day):
    """Rebuild the RTH bar list from the raw CSV, independently of t8_two_year."""
    p = os.path.join(ARCHIVE, sym, f"{day}.csv")
    if not os.path.exists(p):
        return None
    out = []
    with open(p) as f:
        for r in csv.DictReader(f):
            t = r["Datetime"][11:16]
            if t < "09:30" or t >= "16:00":
                continue
            out.append((t + ":00", float(r["Open"]), float(r["High"]),
                        float(r["Low"]), float(r["Close"])))
    return out or None


def resting(bars_after, level):
    """First bar in the (already truncated) forward list whose range strictly
    contains `level` (EXTREME_BUF at each end), within RETEST_WINDOW bars."""
    for j, b in enumerate(bars_after[:RETEST_WINDOW]):
        _, o, h, l, c = b
        buf = EXTREME_BUF * (h - l)
        if l + buf <= level <= h - buf:
            return level, j
    return None, None


def cmd_lookahead(a):
    from signal_runner import CHASE_PCT
    n_each = a.n
    problems = []
    print(f"CHASE_PCT = {CHASE_PCT}")
    for arm in ("next_open", "limit_level", "chase_once", "mid_candle"):
        meta, rows = load(arm, "full29")
        filled = [r for r in rows if not r["unfilled"]]
        step = max(1, len(filled) // n_each)
        sample = filled[::step][:n_each]
        ok = bad = skip = 0
        for r in sample:
            bars = raw_rth(r["sym"], r["day"])
            if not bars:
                skip += 1
                continue
            idx = next((i for i, b in enumerate(bars) if b[0] == r["entry_time"]), None)
            if idx is None:
                skip += 1
                continue
            # PHYSICAL TRUNCATION: everything at or before the signal bar is gone.
            after = bars[idx + 1:]
            sig_bar = bars[idx]          # handed over ONLY as a price reference
            is_long = r["side"] == "call"
            lvl = r["level_price"]
            got = gotj = None
            if arm == "next_open":
                if after:
                    got, gotj = after[0][1], 0
            elif arm == "chase_once":
                if after:
                    _, o, h, l, c = after[0]
                    cand = max(o, c) if is_long else min(o, c)
                    if abs(cand - lvl) / lvl <= CHASE_PCT:
                        got, gotj = cand, 0
            elif arm == "limit_level":
                got, gotj = resting(after, lvl)
            elif arm == "mid_candle":
                mid = (sig_bar[2] + sig_bar[3]) / 2.0
                got, gotj = resting(after, mid)
            if got is None:
                problems.append((arm, r["sym"], r["day"], r["entry_time"],
                                 "referee found NO fill after truncation; book says "
                                 f"{r['entry']}"))
                bad += 1
                continue
            if abs(got - r["entry"]) > 1e-4:   # the book rounds entry to 4dp
                problems.append((arm, r["sym"], r["day"], r["entry_time"],
                                 f"entry {r['entry']} vs truncated re-derivation {got:.4f}"))
                bad += 1
                continue
            fill_ts = after[gotj][0]
            if r["fill_time"] and fill_ts != r["fill_time"]:
                problems.append((arm, r["sym"], r["day"], r["entry_time"],
                                 f"fill bar {r['fill_time']} vs {fill_ts}"))
                bad += 1
                continue
            if fill_ts <= r["entry_time"]:
                problems.append((arm, r["sym"], r["day"], r["entry_time"],
                                 "fill bar at or before the signal bar"))
                bad += 1
                continue
            ok += 1
        print(f"{arm:<12} sampled {len(sample):>3}  match {ok:>3}  mismatch {bad:>3}  skipped {skip}")
    if problems:
        print("\nPROBLEMS:")
        for p in problems[:40]:
            print("  ", p)
    else:
        print("\nno lookahead / re-derivation problems in the sample")
    return 1 if problems else 0


# ------------------------------------------------------------------- 3. close
def cmd_close(_a):
    import entry_fill
    print("entry_fill.ENTRY_FILL =", repr(entry_fill.ENTRY_FILL))
    print("needs_future_bars() =", entry_fill.needs_future_bars())

    class C:
        pass
    c = C()
    c.open, c.high, c.low, c.close = 10.0, 11.0, 9.0, 10.5
    print("entry_fill_price(mode='close') on a synthetic bar (level 9.0, long) =",
          entry_fill.entry_fill_price(9.0, c, True, mode="close"))

    meta, rows = load("close", "full29")
    cache = {}
    bad = []
    for r in rows:
        key = (r["sym"], r["day"])
        if key not in cache:
            bars = raw_rth(*key) or []
            cache[key] = {b[0]: b[4] for b in bars}
        px = cache[key].get(r["entry_time"])
        if px is None or abs(px - r["entry"]) > 1e-4:
            bad.append((r["sym"], r["day"], r["entry_time"], r["entry"], px))
    print(f"close arm: {len(rows)} rows, {len(bad)} not equal to the raw tape's own close")
    for b in bad[:10]:
        print("  ", b)
    # cross-arm identity: as_booked entry must be the level, never the close
    _, ab = load("as_booked", "full29")
    same = sum(1 for x, y in zip(ab, rows) if x["entry"] is not None and abs(x["entry"] - y["entry"]) < 1e-9)
    print(f"as_booked entry == close entry on {same} of {len(rows)} rows "
          f"(should be a small minority -- proves the arms are distinct)")
    return 1 if bad else 0


# -------------------------------------------------------------------- 4. ACHR
def cmd_achr(a):
    sym, day = a.sym, a.day
    os.environ["OMEN_SCALE_PLAN"] = "none"
    import backtest_week as bw
    import signal_runner as sr
    from t8_two_year import day_table, rth_candles, bias_from
    assert bw.SCALE_PLAN is None, bw.SCALE_PLAN

    mailbox = {}
    orig = sr.fill_price

    def wrapped(level, candle, is_long, session_hi=None, session_lo=None):
        res = orig(level, candle, is_long, session_hi=session_hi, session_lo=session_lo)
        mailbox["last"] = (level, candle, is_long)
        return res
    sr.fill_price = wrapped

    class R(bw.BacktestRunner):
        def _route(self, signals, sig):
            super()._route(signals, sig)
            ctx = mailbox.pop("last", None)
            if ctx is not None:
                sig["_level"], sig["_candle_id"] = ctx[0], id(ctx[1])
    seen = []
    oi = R.__init__

    def init(self, s):
        oi(self, s)
        seen.append(self)
    R.__init__ = init
    bw.BacktestRunner = R

    table = day_table(sym)
    days = sorted(table)
    i = days.index(day)
    candles = rth_candles(sym, day)
    prev = days[i - 1] if i else None
    pdh = pdl = pdo = pdc = None
    if prev:
        pdh, pdl, pdo, pdc = table[prev][0], table[prev][1], table[prev][2], table[prev][3]
    pmh, pml = table[day][4], table[day][5]
    bias = bias_from([table[d][3] for d in days[max(0, i - 40):i]])
    idx_by_id = {id(c): j for j, c in enumerate(candles)}
    trades = bw.simulate_day(sym, day, candles, pdh, pdl, bias, pmh, pml, pdo, pdc, None)

    print(f"{sym} {day}: {len(candles)} bars, {len(trades)} trades")
    caps = seen[-1].captured if seen else []
    print(f"captured signals: {len(caps)}")
    pool = defaultdict(list)
    for s in caps:
        k = (s["signal_type"].value, s["direction"], round(float(s["entry"]), 4), s.get("status"))
        pool[k].append(s)
    for k, lst in sorted(pool.items(), key=lambda kv: str(kv[0])):
        if len(lst) > 1 or True:
            print(f"  key={k}  n={len(lst)}  candle_idx={[idx_by_id.get(s.get('_candle_id')) for s in lst]}")
    used = defaultdict(int)
    for t in trades:
        if not t.counted or t.signal_type == "reentry_84_rule":
            continue
        k = (t.signal_type, t.direction, round(float(t.entry), 4), t.status)
        lst = pool.get(k) or []
        n = used[k]
        sig = lst[n] if n < len(lst) else None
        used[k] += 1
        eidx = idx_by_id.get(sig.get("_candle_id")) if sig else None
        flag = "" if eidx == t.entry_idx else "   <<< MISMATCH"
        print(f"  trade {t.signal_type} {t.direction} entry={t.entry} stop={t.stop} "
              f"t.entry_idx={t.entry_idx} matched_sig_idx={eidx} grade={t.grade}{flag}")
    return 0


# --------------------------------------------------------------- 5. scaleplan
def _probe(_x):
    import os as _os
    _os.environ["OMEN_SCALE_PLAN"] = "none"
    import backtest_week as _bw
    return ("worker", _os.getpid(), repr(_bw.SCALE_PLAN), repr(_bw.DISASTER_STOP))


def cmd_scaleplan(_a):
    from multiprocessing import Pool
    with Pool(2) as p:
        for r in p.map(_probe, [0, 1]):
            print(r)
    import importlib
    import backtest_week as bw
    print("parent (env NOT set before import):", repr(bw.SCALE_PLAN))
    for pool in POOLS:
        for arm in ARMS:
            meta, _ = load(arm, pool)
            f = meta["stamp"]["flags"]
            print(f"  stamp {arm:<12} {pool:<7} SCALE_PLAN={f['backtest_week.SCALE_PLAN']!r} "
                  f"commit={meta['stamp']['git']['commit'][:8]} "
                  f"dirty_py={meta['stamp']['git']['dirty_py_count']} "
                  f"dirty_engine={meta['stamp']['git']['dirty_engine_py']}")
    return 0


# ------------------------------------------------------------------ 6. losses
def cmd_losses(_a):
    print("distribution of loss magnitudes per arm (full29), from the books")
    for arm in ARMS:
        _, rows = load(arm, "full29")
        filled = [r for r in rows if not r["unfilled"]]
        losses = [r["r"] for r in filled if r["r"] < 0]
        worse = [x for x in losses if x < -1.0 - 1e-9]
        exact = [x for x in losses if abs(x + 1.0) <= 1e-9]
        better = [x for x in losses if -1.0 + 1e-9 < x < 0]
        print(f"{arm:<12} losses={len(losses):>5}  exactly -1R={len(exact):>5}  "
              f"worse than -1R={len(worse):>4} (worst {min(losses) if losses else 0:.4f})  "
              f"between 0 and -1R={len(better):>4}")
    return 0


# ---------------------------------------------------- 7. exit-model contamination
def cmd_closewalk(a):
    """Is `close` handicapped by an exit model the other five arms never face?

    `close` is read off the real SimTrade, so it is managed by
    backtest_week.simulate_day -- which keeps DISASTER_STOP on (an intrabar -1R
    touch) even under SCALE_PLAN=None. The other five arms are priced by
    g90's own `_walk`: close-through stop, filled AT the stop, plus a 2R target
    on an intrabar touch. Re-price every `close` row with `_walk` -- same entry,
    same stop, same 2R target -- and see how much of the close-vs-next_open gap
    is the FILL and how much is the EXIT."""
    pool = a.pool
    _, rows = load("close", pool)
    cache = {}
    n = flip_w = flip_l = same = skip = 0
    tot_book = tot_walk = 0.0
    for r in rows:
        if r["unfilled"]:
            continue
        key = (r["sym"], r["day"])
        if key not in cache:
            cache[key] = raw_rth(*key) or []
        bars = cache[key]
        idx = next((i for i, b in enumerate(bars) if b[0] == r["entry_time"]), None)
        if idx is None:
            skip += 1
            continue
        is_long = r["side"] == "call"
        entry, stop = r["entry"], r["stop"]
        risk = (entry - stop) if is_long else (stop - entry)
        if risk <= 0:
            skip += 1
            continue
        target = entry + 2 * risk if is_long else entry - 2 * risk
        out = None
        for j in range(idx + 1, len(bars)):
            _, o, h, l, c = bars[j]
            if (c <= stop) if is_long else (c >= stop):
                out = -1.0
                break
            if (h >= target) if is_long else (l <= target):
                out = 2.0
                break
        if out is None:
            lastc = bars[-1][4]
            move = (lastc - entry) if is_long else (entry - lastc)
            out = move / risk
        n += 1
        tot_book += r["r"]
        tot_walk += out
        if abs(out - r["r"]) < 1e-6:
            same += 1
        elif out > r["r"]:
            flip_w += 1
        else:
            flip_l += 1
    days = len({r["day"] for r in rows})
    print(f"pool={pool}  rows repriced={n}  skipped={skip}  identical={same}  "
          f"_walk better={flip_w}  _walk worse={flip_l}")
    print(f"  close as booked (real engine exit): mean R {tot_book/n:+.4f}  "
          f"${tot_book*RISK/days:,.0f}/day")
    print(f"  close repriced with the other arms' _walk exit: mean R "
          f"{tot_walk/n:+.4f}  ${tot_walk*RISK/days:,.0f}/day")
    print(f"  exit-model contamination in the close row: "
          f"{(tot_walk-tot_book)/n:+.4f}R per trade")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats")
    lp = sub.add_parser("lookahead")
    lp.add_argument("--n", type=int, default=30)
    sub.add_parser("close")
    ac = sub.add_parser("achr")
    ac.add_argument("--sym", default="ACHR")
    ac.add_argument("--day", default="2026-04-06")
    sub.add_parser("scaleplan")
    sub.add_parser("losses")
    cw = sub.add_parser("closewalk")
    cw.add_argument("--pool", default="full29")
    a = ap.parse_args()
    fn = {"stats": cmd_stats, "lookahead": cmd_lookahead, "close": cmd_close,
          "achr": cmd_achr, "scaleplan": cmd_scaleplan, "losses": cmd_losses,
          "closewalk": cmd_closewalk}[a.cmd]
    sys.exit(fn(a) or 0)
