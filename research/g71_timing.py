"""G71/timing — the entry-shift surface: what does the book earn at -2..+2 bars?

Austin, on 7.1: "8 percent of the book was a candle late or early, but it has
the data to figure out itself, thats me saying im going to work smarter, not
harder."

The 8% is `research/t12_earlier-entry-gap.md` section 4: 218 of 2,595 traded rows
(8.4%) had a candidate 1-6 bars EARLIER that graded S on Austin's own ladder.
That number counted CANDIDATES. It never priced them. This track prices them.

WHAT IS MEASURED
----------------
Every traded row of the ratified 2-year book (`research/bt2y_trades.json`,
2,437 rows) is re-managed from a shifted entry bar, k in {-2,-1,0,+1,+2}, through
`backtest_week._ladder_bar` — the shipped management loop, not a copy. Nothing is
re-implemented: the stop trigger, the -1.25R floor, the disaster stop, the
PT1 scale rung and the pessimistic same-bar tie all come from the engine.

The fill at bar i+k is the shipped fill TRANSLATED by the price the tape moved
between the two bars:

    delta_k  = close[i+k] - close[i]
    entry_k  = entry_0 + delta_k

so k=0 is the identity and reproduces the book exactly (that identity is
asserted, not assumed — see `--check`). Two arms, because the stop is the thing
that decides what "the same trade one candle earlier" means:

  ARM T (translate) — stop and target move with the entry. Risk is IDENTICAL to
      the book's, so the R denominator is fixed and the k-surface is pure path:
      "did the tape treat that bar better?" This is the honest statistical arm.

  ARM S (structural stop) — the stop stays where it is, because on a break-and-
      retest the stop IS a level and a level does not move because you were
      early. Risk becomes |entry_k - stop|, target re-derives at 2R. This is the
      arm Austin's sentence actually describes, and it is CONFOUNDED: entering
      earlier on a long shrinks the distance to the stop, which shrinks 1R, which
      inflates R mechanically. Both are reported; neither is quoted alone.

LOOK-AHEAD, STATED LOUDLY
-------------------------
k<0 is an ORACLE. The engine did not have the signal at bar i-1; that is the
whole content of "the engine entered one candle late". A negative-k number is a
CEILING on what better timing could pay, never a backtest of a tradable rule.
k>0 is causal (you can always wait) and is a real, tradable arm.

Usage:
    python research/g71_timing.py            # full surface + slices
    python research/g71_timing.py --check    # k=0 identity only (fast gate)
    python research/g71_timing.py --marks    # his S minutes vs the engine's
"""
from __future__ import annotations

import argparse, json, math, os, random, statistics, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import polygon_feed as pf                                     # noqa: E402
import backtest_week as bw                                    # noqa: E402
import loss_halt                                              # noqa: E402
from backtest_week import SimTrade, RISK_DOLLARS              # noqa: E402
from backtest_12mo import hourly_from_1m, qqq_level_breaks    # noqa: E402
from universe import ALL_SYMS, has_archive                    # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades.json")
SHIFTS = (-2, -1, 0, 1, 2)


# --------------------------------------------------------------------------
# day context — the same inputs backtest_2y.py hands simulate_day.
# Reconstructed rather than read off the JSON because the published book rounds
# entry/stop/target to 2dp, and on a $0.11 risk that is a 4% error in R. The
# k=0 identity below is exact only against the engine's own floats.
# --------------------------------------------------------------------------
def archive_days(sym):
    d = os.path.join(ROOT, "data_archive", sym)
    if not os.path.isdir(d):
        return []
    return sorted(f[:-4] for f in os.listdir(d) if f.endswith(".csv"))


_DAYS: dict[str, list] = {}
_CTX: dict[tuple, object] = {}
_HOURLY: dict[str, list] = {}
_WINDOW_START = [None]
_QQQ = [None]


def window_start():
    """The same 730-day window backtest_2y.py cut."""
    if _WINDOW_START[0] is None:
        from datetime import date, timedelta
        syms = [s for s in ALL_SYMS if has_archive(s, 100)]
        last = max((archive_days(s) or ["1970-01-01"])[-1] for s in syms)
        _WINDOW_START[0] = (date.fromisoformat(last) - timedelta(days=730)).isoformat()
    return _WINDOW_START[0]


def day_ctx(sym, day):
    """(rth candles, pdh, pdl, pmh, pml, pdo, pdc) — cache-first off data_archive."""
    key = (sym, day)
    if key in _CTX:
        return _CTX[key]
    if sym not in _DAYS:
        _DAYS[sym] = archive_days(sym)
    days = _DAYS[sym]
    try:
        bars = pf.fetch_day(sym, day)
        rth = pf.rth(bars)
    except Exception:
        rth = []
    if len(rth) < 30:
        _CTX[key] = None
        return None
    pmh, pml = pf.premarket_hi_lo(bars)
    pdh = pdl = pdo = pdc = None
    if day in days:
        j = days.index(day)
        # backtest_2y walks only days inside the window, so the FIRST windowed
        # day has no prior day even when the archive holds one. Mirror that.
        if j > 0 and days[j - 1] >= window_start():
            try:
                prth = pf.rth(pf.fetch_day(sym, days[j - 1]))
                if len(prth) >= 30:
                    pdh = max(c.high for c in prth)
                    pdl = min(c.low for c in prth)
                    pdo, pdc = prth[0].open, prth[-1].close
            except Exception:
                pass
    _CTX[key] = (rth, pdh, pdl, pmh, pml, pdo, pdc)
    return _CTX[key]


def hourly_for(sym):
    """The symbol's hourly series, built exactly as backtest_2y.py builds it."""
    if sym in _HOURLY:
        return _HOURLY[sym]
    start = window_start()
    h = []
    for d in [x for x in archive_days(sym) if x >= start]:
        ctx = day_ctx(sym, d)
        if ctx:
            h += hourly_from_1m(d, ctx[0])
    _HOURLY[sym] = h
    return h


def qqq_breaks():
    if _QQQ[0] is None:
        start = window_start()
        syms = [s for s in ALL_SYMS if has_archive(s, 100)]
        window = sorted({d for s in syms for d in archive_days(s) if d >= start})
        _QQQ[0] = qqq_level_breaks(window)
    return _QQQ[0]


_SIMS: dict[tuple, list] = {}


def sim_day(sym, day):
    """The engine's own SimTrade objects for one session — exact floats."""
    key = (sym, day)
    if key in _SIMS:
        return _SIMS[key]
    ctx = day_ctx(sym, day)
    if ctx is None:
        _SIMS[key] = []
        return []
    rth, pdh, pdl, pmh, pml, pdo, pdc = ctx
    bias = bw.htf_bias_for(hourly_for(sym), day)
    _SIMS[key] = bw.simulate_day(sym, day, rth, pdh, pdl, bias, pmh, pml, pdo, pdc,
                                 qqq=qqq_breaks().get(day))
    return _SIMS[key]


class _StubRunner:
    """Everything `_ladder_bar` -> `_arm_84` touches, and nothing else.

    `_arm_84` only writes `runner.session.*` to arm an 84% re-entry. This replay
    never calls `detect_signals`, so the arm is inert by construction — the
    signal population is held FIXED at the book's. That is deliberate: mixing a
    changed entry bar with a changed set of re-entries would make the surface
    unreadable."""

    class _S:
        entry_price = entry_direction = entry_target = entry_stop = None

    def __init__(self, candles, bias=None):
        self.session = _StubRunner._S()
        self.candles = candles
        self.htf_bias = bias


# --------------------------------------------------------------------------
# one shifted trade
# --------------------------------------------------------------------------
_MATCH: dict[int, object] = {}
_BOOK_BY_DAY: dict[tuple, list] = {}


def _key(entry_i, setup, direction, entry, stop, target):
    return (entry_i, setup, direction,
            round(entry, 2), round(stop, 2), round(target, 2))


_CANDS: dict[int, list] = {}
CAND_BACK = 6          # T12 section 4's window: "1-6 bars earlier, his own range"


def earlier_candidates(sym, day, src):
    """Every signal the engine ALREADY had 1-6 bars before the entry it took.

    This is `research/t12_earlier-entry-gap.md` section 4's population, rebuilt
    on the current book. Same symbol, same day, same direction, any grade, any
    status — including the `X`/`skipped_d` rows, which is the whole point: the
    engine emitted them and threw them away. Each carries its OWN entry, stop and
    target, so swapping to one is not a price translation, it is taking a
    different trade the engine really produced."""
    from research import downgrade as dg
    ctx = day_ctx(sym, day)
    if ctx is None:
        return []
    rth = ctx[0]
    dbars = [{"o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
             for c in rth]
    bias = bw.htf_bias_for(hourly_for(sym), day)
    out = []
    for t in sim_day(sym, day):
        if t.direction != src.direction or t is src:
            continue
        off = t.entry_idx - src.entry_idx
        if not (-CAND_BACK <= off <= -1):
            continue
        rec = dg.score(dbars, t.entry_idx, t.stop, t.direction == "call", bias)
        out.append({"off": off, "entry_idx": t.entry_idx, "entry": t.entry,
                    "stop": t.stop, "target": t.target, "grade": t.grade,
                    "status": t.status, "setup": t.signal_type,
                    "sgrade": (rec or {}).get("grade", "n/a"),
                    "symbol": sym, "day": day, "direction": t.direction,
                    "signal_type": t.signal_type, "reason": t.reason})
    return sorted(out, key=lambda x: -x["off"])       # nearest first


def build_match_index(rows):
    """Bind every book row to the engine SimTrade that produced it.

    Rounding-safe and COLLISION-safe: three INTC rows share (bar 32, B&R, call)
    on 2025-08-22 — different broken levels, so different stops. Matching on the
    bar alone silently handed all three the same trade. The key carries the
    rounded entry/stop/target the book published, and each SimTrade is consumed
    once, so a row either binds to its own trade or is dropped and counted."""
    for n, r in enumerate(rows):
        _BOOK_BY_DAY.setdefault((r["sym"], r["day"]), []).append(n)
    unbound = 0
    for (sym, day), idxs in _BOOK_BY_DAY.items():
        pool = defaultdict(list)
        for t in sim_day(sym, day):
            if not t.counted:
                continue
            pool[_key(t.entry_idx, t.signal_type, t.direction,
                      t.entry, t.stop, t.target)].append(t)
        for n in idxs:
            r = rows[n]
            k = _key(r["entry_i"], r["setup"], r["dir"],
                     r["entry"], r["stop"], r["target"])
            if pool.get(k):
                _MATCH[n] = pool[k].pop(0)
                _CANDS[n] = earlier_candidates(sym, day, _MATCH[n])
            else:
                unbound += 1
    return unbound


def match(n):
    return _MATCH.get(n)


PARAMS = os.path.join(HERE, "g71_timing_params.json")


class _Src:
    """The eight engine floats a shifted clone needs, without the SimTrade."""
    __slots__ = ("symbol", "day", "signal_type", "direction", "grade", "status",
                 "reason", "entry_idx", "entry", "stop", "target")

    def __init__(self, d):
        for k in self.__slots__:
            setattr(self, k, d[k])


def load_or_build_index(rows):
    """Bind rows to engine trades, caching the exact floats so a re-run is fast.

    Rebuilding the index costs a full detect_signals replay of 2,154 sessions
    plus every symbol's hourly series. The cache holds ONLY engine output that
    the published book already contains at 2dp, so it is regenerable — delete it
    and the next run rebuilds it."""
    if os.path.exists(PARAMS):
        cached = json.load(open(PARAMS, encoding="utf-8"))
        if cached.get("n_rows") == len(rows) and cached.get("v") == 2:
            for k, v in cached["bound"].items():
                _MATCH[int(k)] = _Src(v)
            for k, v in cached["cands"].items():
                _CANDS[int(k)] = v
            return cached["unbound"]
    unbound = build_match_index(rows)
    json.dump({"v": 2, "n_rows": len(rows), "unbound": unbound,
               "bound": {str(n): {s: getattr(t, s) for s in _Src.__slots__}
                         for n, t in _MATCH.items()},
               "cands": {str(n): c for n, c in _CANDS.items() if c}},
              open(PARAMS, "w"), separators=(",", ":"))
    return unbound


def build(src, rth, pdh, pdl, pmh, pml, k, arm):
    """A SimTrade cloned off `src` but entered at bar entry_idx + k, or None."""
    i0 = src.entry_idx
    i = i0 + k
    if i < 5 or i >= len(rth) - 1 or i0 >= len(rth):
        return None
    long = src.direction == "call"
    d = rth[i].close - rth[i0].close
    entry = src.entry + d
    if arm == "T":
        stop, target = src.stop + d, src.target + d
    else:                                   # arm S — the level does not move
        stop = src.stop
        risk = (entry - stop) if long else (stop - entry)
        if risk <= 1e-9:                    # entry through its own stop
            return None
        target = entry + 2 * risk if long else entry - 2 * risk
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    row = {"sym": src.symbol, "day": src.day, "setup": src.signal_type,
           "dir": src.direction, "grade": src.grade, "status": src.status,
           "reason": src.reason}
    # F1 ladder inputs, recomputed CAUSALLY at the shifted bar (no look-ahead
    # inside the trade): scale rung = session extreme as-of the entry bar,
    # runner target = first key level beyond it. Same expressions as
    # backtest_week.simulate_day.
    if long:
        scale = max(c.high for c in rth[: i + 1])
        cands = [x for x in (pdh, pmh) if x is not None and x > scale]
        cands.append(math.floor(scale) + 1.0)
        rtgt = min(cands)
    else:
        scale = min(c.low for c in rth[: i + 1])
        cands = [x for x in (pdl, pml) if x is not None and x < scale]
        cands.append(math.ceil(scale) - 1.0)
        rtgt = max(cands)
    return SimTrade(symbol=row["sym"], day=row["day"], signal_type=row["setup"],
                    direction=row["dir"], grade=row["grade"], status=row["status"],
                    entry_time=rth[i].timestamp[:8], entry=entry, stop=stop,
                    target=target, reason=row["reason"], entry_idx=i,
                    exit_idx=len(rth) - 1, scale_level=scale, runner_target=rtgt)


def manage(t, rth, runner):
    """Walk the shipped per-bar management from entry_idx+1 to the close."""
    open_trades = [t]
    for i in range(t.entry_idx + 1, len(rth)):
        if not open_trades:
            break
        bw._ladder_bar(t, rth[i], i, open_trades, runner)
    if open_trades:                          # EOD scratch, exactly as simulate_day
        t.outcome, t.exit_price = "scratch", rth[-1].close
    return t


def run_row(n, row, k, arm):
    ctx = day_ctx(row["sym"], row["day"])
    if ctx is None:
        return None
    rth, pdh, pdl, pmh, pml = ctx[0], ctx[1], ctx[2], ctx[3], ctx[4]
    src = match(n)
    if src is None:
        return None
    t = build(src, rth, pdh, pdl, pmh, pml, k, arm)
    if t is None:
        return None
    manage(t, rth, _StubRunner(rth))
    from signal_runner import min_risk_floor
    return {"r": t.pnl / RISK_DOLLARS, "out": t.outcome,
            "bars": max(0, t.exit_idx - t.entry_idx), "entry_i": t.entry_idx,
            "risk": abs(t.entry - t.stop), "entry": t.entry, "stop": t.stop,
            # B&R_MIN_RISK: a shifted entry that lands too close to a structural
            # stop is a trade the engine would have refused as skipped_tight_stop.
            # Counted, not silently kept.
            "thin": abs(t.entry - t.stop) < min_risk_floor(t.entry)}


# --------------------------------------------------------------------------
# stats
# --------------------------------------------------------------------------
def boot_ci(xs, reps=4000, seed=71):
    if len(xs) < 3:
        return (float("nan"), float("nan"))
    rnd = random.Random(seed)
    n, ms = len(xs), []
    for _ in range(reps):
        ms.append(statistics.fmean(rnd.choices(xs, k=n)))
    ms.sort()
    return (ms[int(0.025 * reps)], ms[int(0.975 * reps)])


def summarise(rs):
    if not rs:
        return dict(n=0, mean=float("nan"), wr=float("nan"), tot=0.0)
    return dict(n=len(rs), mean=statistics.fmean(rs),
                wr=sum(1 for r in rs if r > 0) / len(rs), tot=sum(rs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--marks", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "g71_timing.json"))
    args = ap.parse_args()

    if args.marks:
        return marks_crosscheck()

    book = json.load(open(BOOK, encoding="utf-8"))
    rows = [r for r in book["trades"] if r["status"] == "fired" and r["traded"]]
    print("book: %d traded rows, mean R %+.4f, WR %.2f%%"
          % (len(rows), statistics.fmean(r["r"] for r in rows),
             100 * sum(1 for r in rows if r["out"] == "win") / len(rows)))

    unbound = load_or_build_index(rows)
    print("match index: %d bound, %d unbound" % (len(_MATCH), unbound))

    # ---- k=0 identity ----------------------------------------------------
    bad, ok, miss = [], 0, 0
    for n, row in enumerate(rows):
        got = run_row(n, row, 0, "T")
        if got is None:
            miss += 1
            continue
        if abs(got["r"] - row["r"]) <= 0.0015 and got["out"] == row["out"]:
            ok += 1
        else:
            bad.append((row["sym"], row["day"], row["entry_i"], row["r"],
                        round(got["r"], 3), row["out"], got["out"]))
    print("k=0 identity: %d/%d exact, %d mismatched, %d unbuildable"
          % (ok, len(rows), len(bad), miss))
    for b in bad[:15]:
        print("   MISMATCH", b)
    if args.check:
        return 0 if not bad else 1

    # ---- the surface -----------------------------------------------------
    res = {}          # (k, arm) -> {row_key: rec}
    for arm in ("T", "S"):
        for k in SHIFTS:
            res[(k, arm)] = {}
            for n, row in enumerate(rows):
                got = run_row(n, row, k, arm)
                if got is not None:
                    res[(k, arm)][n] = got
            print("  ran k=%+d arm %s: %d rows" % (k, arm, len(res[(k, arm)])), flush=True)

    # Support is PER ARM. Arm S drops any row whose shifted entry lands on the
    # wrong side of its own stop, which is 811 rows at k=-1 -- restricting arm T
    # to arm S's survivors would silently re-select the population arm T is
    # supposed to measure. Each arm is reported on the rows IT can build at every
    # k, and the arm-S support is stated so it can be discounted.
    support = {}
    for arm in ("T", "S"):
        s = set(range(len(rows)))
        for k in SHIFTS:
            s &= set(res[(k, arm)])
        support[arm] = sorted(s)
        print("support arm %s: %d of %d rows" % (arm, len(support[arm]), len(rows)))
    common = support["T"]

    out = {"n_support": {a: len(support[a]) for a in support},
           "surface": {}, "slices": {}}

    print("\n== R SURFACE (each arm on its own support) ==")
    print("%-4s %-4s %6s %8s %8s %10s %12s %24s" %
          ("arm", "k", "n", "meanR", "WR%", "totR", "delta k=0", "95% boot CI on delta"))
    for arm in ("T", "S"):
        idx = support[arm]
        base_a = [res[(0, arm)][n]["r"] for n in idx]
        for k in SHIFTS:
            rs = [res[(k, arm)][n]["r"] for n in idx]
            s = summarise(rs)
            d = [rs[j] - base_a[j] for j in range(len(rs))]
            md = statistics.fmean(d)
            lo, hi = boot_ci(d)
            print("%-4s %+4d %6d %8.4f %8.2f %10.1f %12s %24s"
                  % (arm, k, len(idx), s["mean"], 100 * s["wr"], s["tot"],
                     "%+.4f" % md, "[%+.4f, %+.4f]" % (lo, hi)))
            out["surface"]["%s%+d" % (arm, k)] = dict(
                s, dmean=md, ci_lo=lo, ci_hi=hi,
                thin=sum(1 for n in idx if res[(k, arm)][n]["thin"]))
    print("\nrows whose shifted risk falls under B&R_MIN_RISK "
          "(engine would have called them skipped_tight_stop):")
    for arm in ("T", "S"):
        print("  arm %s: " % arm + "  ".join(
            "k=%+d %d" % (k, out["surface"]["%s%+d" % (arm, k)]["thin"]) for k in SHIFTS))

    # ---- slices (arm T — fixed denominator) ------------------------------
    def slice_table(name, keyfn, minn=25):
        print("\n== %s (arm T, delta mean R vs k=0) ==" % name)
        hdr = "%-22s %6s" % ("bucket", "n") + "".join("%9s" % ("k=%+d" % k) for k in SHIFTS)
        print(hdr)
        buckets = defaultdict(list)
        for n in common:
            buckets[keyfn(rows[n])].append(n)
        tab = {}
        for b in sorted(buckets, key=lambda x: (-len(buckets[x]), str(x))):
            idx = buckets[b]
            if len(idx) < minn:
                continue
            b0 = statistics.fmean(res[(0, "T")][n]["r"] for n in idx)
            cells = []
            for k in SHIFTS:
                cells.append(statistics.fmean(res[(k, "T")][n]["r"] for n in idx) - b0)
            print("%-22s %6d" % (str(b)[:22], len(idx)) + "".join("%+9.4f" % c for c in cells))
            tab[str(b)] = {"n": len(idx), **{"k%+d" % k: c for k, c in zip(SHIFTS, cells)}}
        out["slices"][name] = tab

    slice_table("setup", lambda r: r["setup"])
    slice_table("side", lambda r: "long" if r["side"] == "L" else "short")
    slice_table("time-of-day (slot)", lambda r: r["slot"])
    slice_table("entry bar bucket", lambda r: ("bar 5-14" if r["entry_i"] < 15 else
                                               "bar 15-29" if r["entry_i"] < 30 else
                                               "bar 30-44" if r["entry_i"] < 45 else
                                               "bar 45-59" if r["entry_i"] < 60 else
                                               "bar 60+"))
    slice_table("symbol", lambda r: r["sym"], minn=40)
    slice_table("austin ladder (sgrade)", lambda r: r["sgrade"])
    slice_table("legacy grade", lambda r: r["grade"])
    slice_table("year-month", lambda r: r["ym"], minn=1)

    # ---- book level: re-apply R31 on each arm ----------------------------
    print("\n== BOOK LEVEL — R31 loss halt re-applied per k (arm T) ==")
    print("%-5s %8s %8s %10s %8s" % ("k", "traded", "meanR", "totR", "WR%"))
    for k in SHIFTS:
        brows = []
        for n in common:
            g = res[(k, "T")][n]
            r0 = rows[n]
            brows.append({"day": r0["day"], "sym": r0["sym"], "status": "fired",
                          "traded": True, "entry_i": g["entry_i"], "et": r0["et"],
                          "bars": g["bars"], "out": g["out"], "r": g["r"],
                          "reason": ""})
        loss_halt.apply_to_book(brows)
        kept = [b["r"] for b in brows if b["traded"]]
        print("%-5s %8d %8.4f %10.1f %8.2f"
              % ("%+d" % k, len(kept), statistics.fmean(kept), sum(kept),
                 100 * sum(1 for b in brows if b["traded"] and b["out"] == "win") / len(kept)))
        out.setdefault("halted_book", {})["k%+d" % k] = {
            "traded": len(kept), "mean": statistics.fmean(kept), "tot": sum(kept)}

    # ---- durability: months green, per k ---------------------------------
    print("\n== DURABILITY — months green (arm T) ==")
    months = sorted({rows[n]["ym"] for n in common})
    for k in SHIFTS:
        by = defaultdict(list)
        for n in common:
            by[rows[n]["ym"]].append(res[(k, "T")][n]["r"])
        green = sum(1 for m in months if sum(by[m]) > 0)
        print("  k=%+d: %d/%d months green" % (k, green, len(months)))
        out.setdefault("durability", {})["k%+d" % k] = [green, len(months)]

    # ---- IS k=-1 AN EDGE OR IS IT BAR i ITSELF? --------------------------
    # Every slice above is positive at k=-1 — every symbol, every setup, both
    # sides, every month. A real timing edge concentrates somewhere. A uniform
    # one is a mechanism, and there is only one candidate mechanism: bar i is
    # SELECTED to be the confirmation bar. Entering at bar i-1 books bar i's own
    # move as post-entry profit. Measure that move directly, in R.
    print("\n== THE LOOK-AHEAD, MEASURED — bar i's own move in R ==")
    movs = []
    for n in common:
        src, r0 = _MATCH[n], rows[n]
        rth = day_ctx(r0["sym"], r0["day"])[0]
        i = src.entry_idx
        sgn = 1 if src.direction == "call" else -1
        risk = abs(src.entry - src.stop)
        if risk > 0 and i >= 1:
            movs.append(sgn * (rth[i].close - rth[i - 1].close) / risk)
    lo, hi = boot_ci(movs)
    print("  signed move of the ENTRY bar, close[i]-close[i-1], in R:")
    print("    n=%d  mean %+.4f R  median %+.4f R  95%% boot [%+.4f, %+.4f]"
          % (len(movs), statistics.fmean(movs), statistics.median(movs), lo, hi))
    print("    favourable on %d of %d (%.1f%%)"
          % (sum(1 for m in movs if m > 0), len(movs),
             100 * sum(1 for m in movs if m > 0) / len(movs)))
    print("  k=-1's measured gain was %+.4f R. If those two agree, the surface's"
          % out["surface"]["T-1"]["dmean"])
    print("  peak is bar i's own confirmation move, not a better entry.")
    out["entry_bar_move_r"] = {"mean": statistics.fmean(movs),
                               "median": statistics.median(movs),
                               "ci": [lo, hi]}

    # And the shape of the k=-1 gain: is most of the book better, or a tail?
    d1 = [res[(-1, "T")][n]["r"] - res[(0, "T")][n]["r"] for n in common]
    print("\n  k=-1 vs k=0, per trade: better %d / same %d / worse %d  "
          "(median delta %+.4f R)"
          % (sum(1 for x in d1 if x > 1e-9), sum(1 for x in d1 if abs(x) <= 1e-9),
             sum(1 for x in d1 if x < -1e-9), statistics.median(d1)))

    # ---- per-trade argmax: is the best k trade-specific or systematic? ----
    print("\n== ARGMAX k per trade (arm T) ==")
    arg = Counter()
    for n in common:
        rs = {k: res[(k, "T")][n]["r"] for k in SHIFTS}
        arg[max(rs, key=lambda k: (rs[k], -abs(k)))] += 1
    for k in SHIFTS:
        print("  k=%+d best on %5d / %d (%.1f%%)"
              % (k, arg[k], len(common), 100 * arg[k] / len(common)))
    out["argmax"] = {"k%+d" % k: arg[k] for k in SHIFTS}
    orc = statistics.fmean(max(res[(k, "T")][n]["r"] for k in SHIFTS) for n in common)
    print("  perfect-hindsight oracle over k: mean R %+.4f (vs %+.4f at k=0)"
          % (orc, statistics.fmean(res[(0, "T")][n]["r"] for n in common)))
    out["oracle_mean"] = orc

    # ---- THE 8%: swap to the earlier candidate the engine already had -----
    # T12 section 4 counted these and never priced them. This prices them by
    # MANAGING the earlier signal's own entry/stop/target — not by translating a
    # price — so the swapped trade is a trade the engine really produced.
    print("\n== T12 SECTION 4, RE-PRICED — swap to an earlier candidate ==")
    # THE FILTER THAT MAKES THIS READABLE. A candidate whose entry sits inside
    # B&R_MIN_RISK of its own stop is one the engine refuses as
    # `skipped_tight_stop`, and its R denominator is a rounding error: the first
    # cut of this table, with those rows in, read +8.04 mean R at a 47.5% win
    # rate, which is arithmetic on a $0.01 risk, not an edge. Only candidates the
    # engine would have been ALLOWED to take are priced.
    from signal_runner import min_risk_floor
    dropped = Counter()
    for n in list(_CANDS):
        keep = []
        for c in _CANDS[n]:
            if c["status"] == "skipped_tight_stop":
                dropped["skipped_tight_stop"] += 1
            elif abs(c["entry"] - c["stop"]) < min_risk_floor(c["entry"]):
                dropped["under B&R_MIN_RISK"] += 1
            else:
                keep.append(c)
        _CANDS[n] = keep
    print("candidates dropped as untakeable: %s" % dict(dropped))
    have = [n for n in common if _CANDS.get(n)]
    print("traded rows with a TAKEABLE candidate 1-%d bars earlier, same "
          "direction: %d of %d (%.1f%%)" % (CAND_BACK, len(have), len(common),
                                            100 * len(have) / len(common)))
    for pick_name, pick in (
        ("NEAREST earlier candidate", lambda cs: cs[0]),
        ("best AUSTIN-ladder candidate (S>A>C)",
         lambda cs: min(cs, key=lambda c: ({"S": 0, "A": 1, "C": 2}.get(c["sgrade"], 3),
                                           -c["off"]))),
        ("S-on-his-ladder candidates only",
         lambda cs: next((c for c in cs if c["sgrade"] == "S"), None)),
        ("nearest, and only 1-2 bars back (his 'one candle')",
         lambda cs: next((c for c in cs if c["off"] >= -2), None)),
        ("1-2 bars back AND S on his ladder — the tradable arm",
         lambda cs: next((c for c in cs if c["off"] >= -2 and c["sgrade"] == "S"), None)),
    ):
        took, swap, offs, sg = [], [], [], Counter()
        rk_t, rk_s = [], []
        for n in have:
            c = pick(_CANDS[n])
            if c is None:
                continue
            ctx = day_ctx(rows[n]["sym"], rows[n]["day"])
            t = build(_Src(c), ctx[0], ctx[1], ctx[2], ctx[3], ctx[4], 0, "T")
            if t is None:
                continue
            manage(t, ctx[0], _StubRunner(ctx[0]))
            took.append(res[(0, "T")][n]["r"])
            swap.append(t.pnl / RISK_DOLLARS)
            offs.append(c["off"])
            sg[c["sgrade"]] += 1
            rk_t.append(res[(0, "T")][n]["risk"])
            rk_s.append(abs(t.entry - t.stop))
        if not swap:
            continue
        d = [swap[j] - took[j] for j in range(len(swap))]
        lo, hi = boot_ci(d)
        print("\n  %s — n=%d, median offset %+0.1f bars, sgrade mix %s"
              % (pick_name, len(swap), statistics.median(offs), dict(sg)))
        print("    engine took : mean R %+.4f, WR %.1f%%, total %+.1fR"
              % (statistics.fmean(took), 100 * sum(1 for r in took if r > 0) / len(took),
                 sum(took)))
        print("    swapped     : mean R %+.4f, WR %.1f%%, total %+.1fR"
              % (statistics.fmean(swap), 100 * sum(1 for r in swap if r > 0) / len(swap),
                 sum(swap)))
        print("    delta       : %+.4f R/trade, 95%% boot [%+.4f, %+.4f]  total %+.1fR"
              % (statistics.fmean(d), lo, hi, sum(d)))
        # 1R is the denominator. If the swapped trade risks half as much, its R is
        # twice as big for the same dollar move — print both medians so the reader
        # can see whether the delta is edge or arithmetic.
        print("    median 1R   : taken $%.3f -> swapped $%.3f  (ratio %.2fx)"
              % (statistics.median(rk_t), statistics.median(rk_s),
                 statistics.median(rk_s) / statistics.median(rk_t)))
        out.setdefault("swap", {})[pick_name] = {
            "n": len(swap), "took": statistics.fmean(took),
            "swap": statistics.fmean(swap), "delta": statistics.fmean(d),
            "ci": [lo, hi], "total_delta": sum(d)}

    json.dump(out, open(args.out, "w"), indent=1, default=float)
    print("\nwrote %s" % args.out)
    return 0


# --------------------------------------------------------------------------
# his minutes vs the engine's — T1 re-run on the ratified engine
# --------------------------------------------------------------------------
def marks_crosscheck():
    """T1's question, on today's engine, with and without its matching window.

    `research/marks/probe_s_sweep_2026-08-28.jsonl` is the held-out blind pass;
    34 cards came back S and 34 carry a typed minute. Marks are READ ONLY."""
    from research.t4_engine_recall import run_day

    path = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
    cards = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        ans = (o.get("answers") or {}).get("s") or []
        mn = (o.get("notes") or {}).get("min")
        if "s" in [a.lower() for a in ans] and mn:
            cards.append((o["symbol"], o["date"], mn.strip()))
    print("S cards with a typed minute: %d" % len(cards))

    def to_bar(hhmm):
        h, m = hhmm.replace(".", ":").split(":")[:2]
        return (int(h) - 9) * 60 + int(m) - 30

    rows = []
    for sym, day, mn in cards:
        try:
            his = to_bar(mn)
        except Exception:
            continue
        entries, all_sigs, _ = run_day(sym, day)
        if entries is None:
            rows.append((sym, day, his, None, None, "NO BARS"))
            continue
        fired = sorted(e["bar"] for e in entries)
        seen = sorted(s["bar"] for s in all_sigs)
        nf = min(fired, key=lambda b: abs(b - his)) if fired else None
        ns = min(seen, key=lambda b: abs(b - his)) if seen else None
        rows.append((sym, day, his, nf, ns,
                     "FIRED" if nf is not None and abs(nf - his) <= 2 else
                     "DETECTED" if ns is not None and abs(ns - his) <= 2 else
                     "ELSEWHERE" if seen else "SILENT"))

    print("\n%-6s %-11s %5s %8s %8s %6s %6s  %s"
          % ("sym", "day", "his", "fired", "seen", "dF", "dS", "verdict"))
    for sym, day, his, nf, ns, v in sorted(rows, key=lambda x: x[5]):
        print("%-6s %-11s %5d %8s %8s %6s %6s  %s"
              % (sym, day, his, nf, ns,
                 "%+d" % (nf - his) if nf is not None else "-",
                 "%+d" % (ns - his) if ns is not None else "-", v))

    for label, pick, win in (("nearest FIRED, +/-2 window", 3, 2),
                             ("nearest FIRED, no window", 3, 10 ** 9),
                             ("nearest SIGNAL, +/-2 window", 4, 2),
                             ("nearest SIGNAL, +/-6 window", 4, 6),
                             ("nearest SIGNAL, no window", 4, 10 ** 9)):
        ds = [r[pick] - r[2] for r in rows if r[pick] is not None
              and abs(r[pick] - r[2]) <= win]
        if not ds:
            continue
        late = sum(1 for d in ds if d > 0)
        early = sum(1 for d in ds if d < 0)
        nt = late + early
        p = (sum(math.comb(nt, j) for j in range(min(late, early) + 1))
             / 2 ** nt * 2) if nt else float("nan")
        print("\n%-28s n=%2d  median %+0.1f  mean %+0.2f  late %d / exact %d / early %d"
              "  (sign test on %d non-ties, p=%.4f)"
              % (label, len(ds), statistics.median(ds), statistics.fmean(ds),
                 late, len(ds) - late - early, early, nt, min(p, 1.0)))

    # The mechanism, on the days the engine BOTH saw his setup and traded it:
    # how many bars after the earliest thing it emitted near his minute does the
    # entry it actually TOOK land?
    gaps = [r[3] - r[4] for r in rows
            if r[3] is not None and r[4] is not None and abs(r[4] - r[2]) <= 2
            and abs(r[3] - r[2]) <= 2]
    if gaps:
        print("\nfired bar minus nearest-detected bar, on the %d days the engine "
              "both SAW and TRADED his setup:\n  %s\n  median %+0.1f, mean %+0.2f, "
              "positive on %d of %d"
              % (len(gaps), " ".join("%+d" % g for g in gaps),
                 statistics.median(gaps), statistics.fmean(gaps),
                 sum(1 for g in gaps if g > 0), len(gaps)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
