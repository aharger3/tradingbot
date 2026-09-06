"""R1 referee -- FOURTH PASS (post pass-3 repair, builder commit 0f6a826a).

A fourth independent implementation.  It imports NOTHING from
`g90_fill_arms.py`, `g210_fill_arms_v2.py`, `r1_repair.py`, `r1_referee.py`,
`r1_referee2.py` or `r1_referee3.py` for any arithmetic: its bar loader,
resting-fill, both exit walks and every statistic are written here from
scratch against the raw `data_archive/*.csv` bars and the stamped books in
`research/tape/`.

The two deliberate exceptions, both of which are TESTS of builder code rather
than borrowings of it, and both isolated inside their own subcommand:
  * `avgwl` imports `g210_fill_arms_v2.avg_win_loss` in order to run the
    repaired function and compare its output against this file's own
    sign-bucketed recompute.
  * `scaleplan` / `achr` import `backtest_week` / `t8_two_year` because the
    question is what those modules do.

Subcommands
  stats       re-derive every published cell from the 12 books
  avgwl       run the REPAIRED avg_win_loss() and check it against my own
  closecheck  close arm entry == that minute's own printed close, raw CSV
  lookahead   physically truncate the day at the signal bar and re-derive
  uniform     all six arms under ONE exit model (A close-only, B intrabar)
  pairci      paired next_open - close CI under each exit model
  scaleplan   SCALE_PLAN inside a real worker process + the parent-stamp fix
  achr        re-derive the one entry_idx mismatch
  stamps      every book's stamp: commit, dirty, flags, window, script
"""
import argparse
import csv
import gzip
import json
import math
import os
import subprocess
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TAPE = os.path.join(HERE, "tape")
ARCH = os.path.join(ROOT, "data_archive")

ARMS = ["as_booked", "limit_level", "next_open", "chase_once", "close", "mid_candle"]
POOLS = ["core11", "full29"]
RISK = 1000.0
RETEST_WINDOW = 12          # bars a resting order stays live
EXTREME_BUF = 0.05          # fraction of the bar's range excluded at each end
RESTING_ARMS = ("as_booked", "limit_level", "mid_candle")


# ----------------------------------------------------------------- bars ---
_bars_cache = {}


def bars(sym, day):
    """The day's 09:30-15:59 bars, in order, straight off the raw CSV."""
    key = (sym, day)
    if key in _bars_cache:
        return _bars_cache[key]
    path = os.path.join(ARCH, sym, f"{day}.csv")
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
    _bars_cache[key] = out
    return out


def idx_of_minute(bs, hhmm):
    for i, b in enumerate(bs):
        if b["t"] == hhmm:
            return i
    return None


# ----------------------------------------------------------------- books --
def load(arm, pool):
    path = os.path.join(TAPE, f"fillarms_{arm}_{pool}.json.gz")
    with gzip.open(path, "rt", encoding="utf-8") as f:
        d = json.load(f)
    return d["meta"], d["trades"]


# ------------------------------------------------------------ statistics --
def book_stats(rows, r_of):
    """r_of(row) -> R multiple or None (unfilled).  Everything from scratch."""
    vals, by_month, days = [], defaultdict(float), set()
    for t in rows:
        days.add(t["day"])
        v = r_of(t)
        if v is None:
            continue
        vals.append(v)
        by_month[t["day"][:7]] += v
    n = len(vals)
    tot = sum(vals)
    wins = [v for v in vals if v > 0]
    losses = [v for v in vals if v <= 0]
    return {
        "n": n, "unfilled": len(rows) - n,
        "mean_r": round(tot / n, 4) if n else None,
        "total_r": round(tot, 2),
        "avg_win": round(sum(wins) / len(wins), 4) if wins else None,
        "avg_loss": round(sum(losses) / len(losses), 4) if losses else None,
        "win_pct": round(100.0 * len(wins) / n, 1) if n else None,
        "months": len(by_month),
        "green": sum(1 for v in by_month.values() if v > 0),
        "days": len(days),
        "dpd": round(tot * RISK / len(days), 2) if days else None,
        "worst": round(min(vals), 4) if vals else None,
        "sub_minus_1r": sum(1 for v in vals if v < -1.0),
    }


def r_booked(t):
    return None if t["unfilled"] else t["r"]


def cmd_stats(a):
    print("pool arm | n | unf | meanR | avgW | avgL | win% | mo | green | $/day | days | worst | <-1R")
    for pool in POOLS:
        for arm in ARMS:
            _, rows = load(arm, pool)
            s = book_stats(rows, r_booked)
            print(f"{pool:7s} {arm:12s} | {s['n']:5d} | {s['unfilled']:5d} | "
                  f"{s['mean_r']:+.4f} | {s['avg_win']:+.4f} | {s['avg_loss']:+.4f} | "
                  f"{s['win_pct']:5.1f} | {s['months']:2d} | {s['green']:2d} | "
                  f"${s['dpd']:>9,.0f} | {s['days']:4d} | {s['worst']:+.4f} | {s['sub_minus_1r']:4d}")


# ------------------------------------- the repaired avg_win_loss function --
def cmd_avgwl(a):
    """Run the REPAIRED g210_fill_arms_v2.avg_win_loss on rows rebuilt from the
    committed books, and compare with this file's own sign-bucketed numbers."""
    sys.path.insert(0, HERE)
    sys.path.insert(0, ROOT)
    from g210_fill_arms_v2 import avg_win_loss  # the function under test
    bad = 0
    print("pool arm | builder avgW/avgL | referee avgW/avgL | match")
    for pool in POOLS:
        for arm in ARMS:
            _, rows = load(arm, pool)
            if arm == "close":
                shaped = [{"committed_r": t["r"]} for t in rows]
            else:
                shaped = [{arm: {"filled": not t["unfilled"], "r": t["r"]}} for t in rows]
            baw, bal = avg_win_loss(shaped, arm)
            s = book_stats(rows, r_booked)
            ok = (baw == s["avg_win"]) and (bal == s["avg_loss"])
            bad += 0 if ok else 1
            print(f"{pool:7s} {arm:12s} | {baw:+.4f}/{bal:+.4f} | "
                  f"{s['avg_win']:+.4f}/{s['avg_loss']:+.4f} | {'OK' if ok else 'MISMATCH'}")
    print(f"\n{'PASS' if not bad else 'FAIL'}: {bad} mismatches (0 expected)")
    # And the pre-repair behaviour, to show the repair actually changes something
    print("\npre-repair (bucket by outcome label) is not reconstructible from the")
    print("books (they carry no outcome column); the published tautological")
    print("+2.0000/-1.0000 in the report's two headline tables is the evidence.")


# ------------------------------------------------------------ close arm ----
def cmd_closecheck(a):
    for pool in POOLS:
        _, rows = load("close", pool)
        bad = miss = 0
        for t in rows:
            bs = bars(t["sym"], t["day"])
            i = idx_of_minute(bs, (t["entry_time"] or "")[:5])
            if i is None:
                miss += 1
                continue
            if abs(t["entry"] - bs[i]["c"]) > 1e-4:
                bad += 1
        print(f"{pool}: close arm entry == raw printed close on "
              f"{len(rows) - bad - miss}/{len(rows)} rows; {bad} mismatches, {miss} bars missing")
    # and confirm the shipped default really is 'close'
    sys.path.insert(0, ROOT)
    import entry_fill
    print(f"entry_fill.ENTRY_FILL = {entry_fill.ENTRY_FILL!r}; "
          f"needs_future_bars() = {entry_fill.needs_future_bars()}")
    # and that as_booked is a genuinely different price
    _, cb = load("close", "full29")
    _, ab = load("as_booked", "full29")
    same = sum(1 for x, y in zip(cb, ab)
               if not y["unfilled"] and abs((x["entry"] or 0) - (y["entry"] or 0)) < 1e-9)
    print(f"as_booked entry == close entry on {same} of {len(cb)} full29 rows")


# ------------------------------------------------------------ lookahead ---
def resting_fill(bs, start, price):
    """First bar at or after `start` whose range brackets `price`, buffered off
    both extremes, cancelled after RETEST_WINDOW bars.  My own implementation."""
    for j in range(start, min(len(bs), start + RETEST_WINDOW)):
        b = bs[j]
        buf = EXTREME_BUF * (b["h"] - b["l"])
        if b["l"] + buf <= price <= b["h"] - buf:
            return price, j
    return None, None


def cmd_lookahead(a):
    sys.path.insert(0, ROOT)
    import signal_runner
    chase = signal_runner.CHASE_PCT
    print(f"CHASE_PCT = {chase}")
    print("arm | sampled | price re-derived | fill minute re-derived | fill at/<= signal bar")
    total_bad = 0
    for arm in ("next_open", "limit_level", "chase_once", "mid_candle"):
        _, rows = load(arm, "full29")
        filled = [t for t in rows if not t["unfilled"]]
        step = max(1, len(filled) // a.n)
        sample = filled[::step][:a.n]
        okp = okt = viol = 0
        for t in sample:
            bs = bars(t["sym"], t["day"])
            si = idx_of_minute(bs, (t["entry_time"] or "")[:5])
            if si is None:
                total_bad += 1
                continue
            sig_bar = bs[si]
            is_long = t["side"] == "call"
            # PHYSICAL TRUNCATION: everything at or before the signal bar is gone.
            fut = bs[si + 1:]
            price = fidx = None
            if arm == "next_open":
                if fut:
                    price, fidx = fut[0]["o"], 0
            elif arm == "chase_once":
                if fut:
                    cand = max(fut[0]["o"], fut[0]["c"]) if is_long else min(fut[0]["o"], fut[0]["c"])
                    lv = t["level_price"]
                    if abs(cand - lv) / lv <= chase:
                        price, fidx = cand, 0
            elif arm == "limit_level":
                price, fidx = resting_fill(fut, 0, t["level_price"])
            elif arm == "mid_candle":
                mid = (sig_bar["h"] + sig_bar["l"]) / 2.0
                price, fidx = resting_fill(fut, 0, mid)
            if price is None:
                total_bad += 1
                continue
            if abs(round(price, 4) - t["entry"]) < 1e-4:
                okp += 1
            fill_min = fut[fidx]["t"]
            if fill_min == (t["fill_time"] or "")[:5]:
                okt += 1
            if fill_min <= (t["entry_time"] or "")[:5]:
                viol += 1
        print(f"{arm:12s} | {len(sample):7d} | {okp:16d} | {okt:22d} | {viol:21d}")
        total_bad += (len(sample) - okp)
    print(f"\nnon-reproducing rows across all four arms: {total_bad}")


# -------------------------------------------------- one exit model, six arms
def walk(bs, start, stop, target, is_long, touch):
    """touch=False -> stop triggers only on a CLOSE through it (model A).
       touch=True  -> stop is a resting order filled on an intrabar TOUCH
                      (model B, the engine's DISASTER_STOP at 1.0R, which sits
                      exactly on the structural stop).  Stop is checked before
                      the target inside a bar, i.e. pessimistic."""
    for j in range(start, len(bs)):
        b = bs[j]
        if touch:
            hit_stop = (b["l"] <= stop) if is_long else (b["h"] >= stop)
        else:
            hit_stop = (b["c"] <= stop) if is_long else (b["c"] >= stop)
        if hit_stop:
            return "loss", stop
        if (b["h"] >= target) if is_long else (b["l"] <= target):
            return "win", target
    return ("scratch", bs[-1]["c"]) if bs else ("scratch", None)


def reprice(arm, pool, touch):
    """Re-walk every filled row of a book under one exit model, keeping the
    arm's own entry, stop and fill bar exactly as the book records them."""
    _, rows = load(arm, pool)
    out = []
    for t in rows:
        if t["unfilled"]:
            out.append((t, None))
            continue
        bs = bars(t["sym"], t["day"])
        fi = idx_of_minute(bs, (t["fill_time"] or "")[:5])
        if fi is None:
            out.append((t, None))
            continue
        entry, stop = t["entry"], t["stop"]
        is_long = t["side"] == "call"
        risk = (entry - stop) if is_long else (stop - entry)
        if risk <= 0:
            out.append((t, None))
            continue
        target = entry + 2 * risk if is_long else entry - 2 * risk
        exit_px = None
        if arm in RESTING_ARMS:
            fb = bs[fi]
            if (fb["c"] < stop) if is_long else (fb["c"] > stop):
                exit_px = fb["c"]          # the arm's own "scratch" path
        if exit_px is None:
            _, exit_px = walk(bs, fi + 1, stop, target, is_long, touch)
        if exit_px is None:
            out.append((t, None))
            continue
        move = (exit_px - entry) if is_long else (entry - exit_px)
        out.append((t, round(move / risk, 6)))
    return out


def cmd_uniform(a):
    for pool in POOLS:
        for label, touch in (("A close-only stop", False), ("B intrabar touch", True)):
            print(f"\n--- {pool} / model {label} ---")
            print("arm | n | meanR | $/day | green/mo | avgW | avgL")
            for arm in ARMS:
                pr = reprice(arm, pool, touch)
                lut = {id(t): v for t, v in pr}
                rows = [t for t, _ in pr]
                s = book_stats(rows, lambda t: lut[id(t)])
                print(f"{arm:12s} | {s['n']:5d} | {s['mean_r']:+.4f} | "
                      f"${s['dpd']:>9,.0f} | {s['green']:2d}/{s['months']:2d} | "
                      f"{s['avg_win']:+.4f} | {s['avg_loss']:+.4f}")


def cmd_pairci(a):
    for pool in POOLS:
        for label, touch in (("A close-only", False), ("B intrabar touch", True)):
            no = {(t["sym"], t["day"], t["entry_time"]): v
                  for t, v in reprice("next_open", pool, touch) if v is not None}
            cl = {(t["sym"], t["day"], t["entry_time"]): v
                  for t, v in reprice("close", pool, touch) if v is not None}
            diffs = [no[k] - cl[k] for k in no if k in cl]
            n = len(diffs)
            m = sum(diffs) / n
            var = sum((d - m) ** 2 for d in diffs) / (n - 1)
            se = math.sqrt(var / n)
            print(f"{pool} model {label}: n={n} mean(next_open-close)={m:+.4f}R "
                  f"95% CI [{m - 1.96 * se:+.4f}, {m + 1.96 * se:+.4f}]")


# ------------------------------------------------------------- SCALE_PLAN --
_WORKER_SRC = r'''
import os, sys
os.environ["OMEN_SCALE_PLAN"] = "none"
sys.path.insert(0, r"{root}")
import backtest_week as bw
print("WORKER pid", os.getpid(), "SCALE_PLAN", repr(bw.SCALE_PLAN),
      "LADDER_MODE?", hasattr(bw, "LADDER_MODE"),
      "DISASTER_STOP", getattr(bw, "DISASTER_STOP", None),
      "DISASTER_STOP_R", getattr(bw, "DISASTER_STOP_R", None))
'''

_PARENT_SRC = r'''
import os, sys
sys.path.insert(0, r"{root}")
os.environ.pop("OMEN_SCALE_PLAN", None)
os.environ.pop("OMEN_LADDER_MODE", None)
import backtest_week as bw
print("CLEAN PARENT SCALE_PLAN", repr(bw.SCALE_PLAN))
sys.path.insert(0, r"{here}")
import book_stamp
print("STAMP BEFORE FIX", repr(book_stamp.engine_flags().get("backtest_week.SCALE_PLAN")))
bw.SCALE_PLAN = None          # the builder's one-line repair, applied here
print("STAMP AFTER  FIX", repr(book_stamp.engine_flags().get("backtest_week.SCALE_PLAN")))
'''


def _run_py(src):
    p = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True,
                       cwd=ROOT, timeout=300)
    return (p.stdout + p.stderr).strip()


def cmd_scaleplan(a):
    import multiprocessing as mp
    print("start method:", mp.get_start_method(allow_none=True) or mp.get_start_method())
    print(_run_py(_WORKER_SRC.format(root=ROOT)))
    print(_run_py(_PARENT_SRC.format(root=ROOT, here=HERE)))
    # what g90's close column really was: the flag with no env override
    print("\nstamps written by the 12 committed books:")
    seen = defaultdict(list)
    for pool in POOLS:
        for arm in ARMS:
            meta, _ = load(arm, pool)
            st = meta["stamp"]
            fl = st.get("flags") or {}
            git = st.get("git") or {}
            sp = fl.get("backtest_week.SCALE_PLAN", fl.get("SCALE_PLAN"))
            seen[(git.get("commit"), sp)].append(f"{arm}/{pool}")
    for k, v in seen.items():
        print(f"  commit={k[0]} SCALE_PLAN={k[1]!r}  <- {len(v)} books: {', '.join(v)}")


# ------------------------------------------------------------------ ACHR ---
def cmd_achr(a):
    sys.path.insert(0, ROOT)
    sys.path.insert(0, HERE)
    os.environ["OMEN_SCALE_PLAN"] = "none"
    import backtest_week as bw
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
    # capture which candle each signal was priced off, the same way the
    # harness does -- so the mismatched index can be named, not just counted
    import signal_runner as sr
    mailbox = {}
    orig_fp = sr.fill_price

    def wrapped(level, candle, is_long, session_hi=None, session_lo=None):
        res = orig_fp(level, candle, is_long, session_hi=session_hi, session_lo=session_lo)
        mailbox["last"] = candle
        return res
    sr.fill_price = wrapped

    class R(bw.BacktestRunner):
        def _route(self, signals, sig):
            super()._route(signals, sig)
            c = mailbox.pop("last", None)
            if c is not None:
                sig["_cid"] = id(c)

    seen = []
    orig = R.__init__

    def init(self, s):
        orig(self, s)
        seen.append(self)
    R.__init__ = init
    orig_runner = bw.BacktestRunner
    bw.BacktestRunner = R
    trades = bw.simulate_day(sym, day, candles, pdh, pdl, bias, pmh, pml, pdo, pdc, None)
    bw.BacktestRunner = orig_runner
    sr.fill_price = orig_fp
    idx_by_id = {id(c): j for j, c in enumerate(candles)}
    cap = seen[-1].captured if seen else []
    print(f"{sym} {day}: {len(candles)} bars, {len(cap)} captured signals, {len(trades)} trades")
    keys = defaultdict(list)
    for s in cap:
        keys[(s["signal_type"].value, s["direction"], round(float(s["entry"]), 4),
              s.get("status"))].append(s)
    for k, v in keys.items():
        if len(v) > 1:
            at = [idx_by_id.get(s.get("_cid")) for s in v]
            print(f"  COLLIDING KEY {k}: {len(v)} signals at candles {at}")
    for t in trades:
        if not t.counted or t.signal_type == "reentry_84_rule":
            continue
        k = (t.signal_type, t.direction, round(float(t.entry), 4), t.status)
        if len(keys.get(k, [])) > 1:
            print(f"  trade entry={t.entry} entry_idx={t.entry_idx} key={k} "
                  f"-> {len(keys[k])} candidate signals")


# ----------------------------------------------------------------- stamps --
def cmd_stamps(a):
    for pool in POOLS:
        for arm in ARMS:
            meta, rows = load(arm, pool)
            st = meta["stamp"]
            fl = st.get("flags") or {}
            git = st.get("git") or {}
            print(f"{arm:12s}/{pool:7s} built={st.get('built_at')} "
                  f"commit={git.get('commit')} dirty_engine={git.get('dirty_engine_py')} "
                  f"dirty_n={git.get('dirty_py_count')} "
                  f"SCALE_PLAN={fl.get('backtest_week.SCALE_PLAN', fl.get('SCALE_PLAN'))!r} "
                  f"flags={len(fl)} window={meta['window']['start']}..{meta['window']['end']} "
                  f"script={meta['script']} rows={len(rows)}")


CMDS = {"stats": cmd_stats, "avgwl": cmd_avgwl, "closecheck": cmd_closecheck,
        "lookahead": cmd_lookahead, "uniform": cmd_uniform, "pairci": cmd_pairci,
        "scaleplan": cmd_scaleplan, "achr": cmd_achr, "stamps": cmd_stamps}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=sorted(CMDS))
    ap.add_argument("--n", type=int, default=30)
    a = ap.parse_args()
    CMDS[a.cmd](a)
