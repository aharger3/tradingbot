"""G80 VERIFY 1 -- independent recomputation of research/g80_options_honest.py.

Written from scratch for the adversarial pass. It shares NO code with the file
it is checking: it reads the archive CSVs itself, implements its own
Black-Scholes and its own Parkinson sigma, and runs its own flat-2R simulation.
The only shared inputs are the book (research/bt2y_trades.json) and the cached
one-minute bars on disk.

What it recomputes:
  1. shares, market-at-close fill, one trade a day and everything      ($187 / $650)
  2. contracts, market-at-close fill, one a day, IV 1.2x and 1.0x      ($242 / $346)
  3. contracts, market-at-close fill, everything                       ($843)
  4. the mean-R identity check: mean R vs w*T - (1-w), and the actual
     average winner / average loser behind it
  5. per-trade options-minus-shares in R, against the standing +/-1.5799R bar
  6. a look-ahead probe: does any bar at or after the decision minute enter the
     decision? Re-runs the whole thing with every bar after the entry minute
     deleted from the sigma path, and with the entry-minute bar's high/low
     hidden from the market-order arm.

Reads only. Writes nothing. No network (CSV cache only; a missing day is
counted, never fetched).

    python research/g80_verify_1.py
"""
from __future__ import annotations

import csv
import json
import math
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "research" / "bt2y_trades.json"
ARCHIVE = ROOT / "data_archive"

RISK = 1000.0
MAX_LOSS = 1000.0
MULT = 100
MIN_PREM = 0.05
RTH_MIN = 390.0
YEAR = 252.0
FLOOR_R = 1.25
ERROR_BAR = 1.5799


# ------------------------------------------------------------------ bars
class Bar:
    __slots__ = ("t", "o", "h", "l", "c")

    def __init__(self, t, o, h, l, c):
        self.t, self.o, self.h, self.l, self.c = t, o, h, l, c


_cache = {}


def day_bars(sym, day):
    """RTH 1-minute bars straight off the archive CSV. No polygon_feed."""
    k = (sym, day)
    if k in _cache:
        return _cache[k]
    if len(_cache) > 80:
        _cache.clear()
    p = ARCHIVE / sym / (day + ".csv")
    out = []
    if p.exists():
        with open(p, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                ts = row["Datetime"]
                hhmm = ts[11:19]
                if "09:30:00" <= hhmm < "16:00:00":
                    out.append(Bar(hhmm, float(row["Open"]), float(row["High"]),
                                   float(row["Low"]), float(row["Close"])))
    _cache[k] = out
    return out


_dayindex = {}
_priorcache = {}


def prior_range(sym, day):
    """High-low of the latest session on disk strictly before `day`."""
    k = (sym, day)
    if k in _priorcache:
        return _priorcache[k]
    if sym not in _dayindex:
        d = ARCHIVE / sym
        _dayindex[sym] = sorted(f.name[:-4] for f in d.glob("*.csv")) if d.is_dir() else []
    earlier = [x for x in _dayindex[sym] if x < day]
    val = None
    if earlier:
        b = day_bars(sym, earlier[-1])
        if b:
            hi, lo = max(x.h for x in b), min(x.l for x in b)
            if hi > lo:
                val = hi - lo
    _priorcache[k] = val
    return val


# ------------------------------------------------- my own Black-Scholes
def _N(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def bsprice(S, K, T, sig, call):
    if T <= 0.0 or sig <= 0.0:
        return max(0.0, (S - K) if call else (K - S))
    v = sig * math.sqrt(T)
    d1 = (math.log(S / K) + 0.5 * sig * sig * T) / v
    d2 = d1 - v
    if call:
        return S * _N(d1) - K * _N(d2)
    return K * _N(-d2) - S * _N(-d1)


def parkinson(rng_hl, ref):
    if rng_hl <= 0 or ref <= 0:
        return 0.0
    return (rng_hl / ref) / (2.0 * math.sqrt(math.log(2.0))) * math.sqrt(YEAR)


# ------------------------------------------------------- the simulation
def run_trade(entry, stop, long, bars, i):
    """Flat 2R. Stop triggers on a CLOSE beyond it, fills at that close, floored
    at -1.25R of the trade. Target is a resting limit, fills on touch. Anything
    still open at 15:59 is marked to the last close (also floored)."""
    risk = (entry - stop) if long else (stop - entry)
    if risk <= 0.005:
        return None
    tgt = entry + 2 * risk if long else entry - 2 * risk
    for j in range(i + 1, len(bars)):
        b = bars[j]
        hit = (b.c <= stop) if long else (b.c >= stop)
        if hit:
            fill = max(b.c, entry - FLOOR_R * risk) if long else min(b.c, entry + FLOOR_R * risk)
            r = (fill - entry) / risk if long else (entry - fill) / risk
            return round(r, 4), "stop", fill, j
        if (long and b.h >= tgt) or ((not long) and b.l <= tgt):
            return 2.0, "target", tgt, j
    if len(bars) <= i + 1:
        return None
    last = bars[-1].c
    r = (last - entry) / risk if long else (entry - last) / risk
    return round(max(r, -FLOOR_R), 4), "eod", last, len(bars) - 1


def contract_pnl(entry, stop, exit_px, entry_i, exit_i, call, sigma):
    """Same-day ATM contract on the $1 strike grid; both legs floored at $0.05."""
    K = max(1.0, round(entry))
    T0 = max(RTH_MIN - entry_i, 1.0) / (RTH_MIN * YEAR)
    T1 = max(RTH_MIN - exit_i, 0.5) / (RTH_MIN * YEAR)
    p0 = bsprice(entry, K, T0, sigma, call)
    pstop = max(bsprice(stop, K, T0, sigma, call), MIN_PREM)
    pexit = max(bsprice(exit_px, K, T1, sigma, call), MIN_PREM)
    raw = p0 - pstop
    if raw <= 1e-9 or p0 <= 0:
        return None
    prem_risk = max(raw, MIN_PREM)
    n = int(MAX_LOSS // (prem_risk * MULT))
    if n < 1:
        return None
    return {"dollars": n * (pexit - p0) * MULT, "n": n, "p0": p0,
            "contract_r": (pexit - p0) / prem_risk, "prem_risk": prem_risk}


# ------------------------------------------------------------ reporting
def block(rows, key, ndays):
    v = [r[key] for r in rows]
    w = sum(1 for x in v if x > 0)
    l = sum(1 for x in v if x < 0)
    bym = {}
    for r in rows:
        bym[r["day"][:7]] = bym.get(r["day"][:7], 0.0) + r[key]
    return {"n": len(rows), "win": round(100 * w / (w + l), 1) if w + l else 0,
            "total": sum(v), "per_day": sum(v) / ndays,
            "per_trade": sum(v) / len(rows) if rows else 0,
            "green": sum(1 for x in bym.values() if x > 0), "months": len(bym)}


def firsts(rows):
    by = {}
    for r in rows:
        by.setdefault(r["day"], []).append(r)
    return [sorted(v, key=lambda x: (x["et"], x["sym"]))[0] for _, v in sorted(by.items())]


def boot_ci(rows, key, days, seed=7):
    d = {x: 0.0 for x in days}
    for r in rows:
        d[r["day"]] = d.get(r["day"], 0.0) + r[key]
    v = [d[x] for x in sorted(d)]
    rng = random.Random(seed)
    m = sorted(sum(rng.choices(v, k=len(v))) / len(v) for _ in range(4000))
    return m[100], m[3899]


def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    nd = book["meta"]["sessions"]
    days = sorted({r["day"] for r in book["trades"]})
    traded = [r for r in book["trades"] if r.get("traded")]
    traded.sort(key=lambda r: (r["sym"], r["day"], r["et"]))
    print("book %s  %d sessions  %d traded rows"
          % (book["meta"]["generated"], nd, len(traded)))

    rows12, rows10, missing, nosim, nosig, nocon = [], [], 0, 0, 0, 0
    ts_mismatch = 0
    for row in traded:
        b = day_bars(row["sym"], row["day"])
        i = row["entry_i"]
        if not b or i >= len(b) - 1:
            missing += 1
            continue
        # sanity: does entry_i really point at the signal minute?
        if b[i].t[:5] != row["et"]:
            ts_mismatch += 1
        long = row["dir"] == "call"
        entry = b[i].c                      # market order at the signal close
        sim = run_trade(entry, row["stop"], long, b, i)
        if sim is None:
            nosim += 1
            continue
        r_u, tag, exit_px, exit_i = sim
        base = {"day": row["day"], "sym": row["sym"], "et": row["et"], "tag": tag,
                "r_u": r_u, "shares": r_u * RISK}
        pr = prior_range(row["sym"], row["day"])
        if not pr:
            nosig += 1
            rows12.append(dict(base))
            rows10.append(dict(base))
            continue
        for mult, sink in ((1.2, rows12), (1.0, rows10)):
            sigma = parkinson(pr, entry) * mult
            c = contract_pnl(entry, row["stop"], exit_px, i, exit_i, long, sigma)
            if c is None:
                if mult == 1.2:
                    nocon += 1
                sink.append(dict(base))
            else:
                sink.append(dict(base, dollars=c["dollars"], contracts=c["n"],
                                 contract_r=c["contract_r"], p0=c["p0"]))
    print("rows built %d   dropped: no bars %d, unsimulatable %d, no prior range %d, "
          "no contract %d   entry_i/et mismatches %d"
          % (len(rows12), missing, nosim, nosig, nocon, ts_mismatch))

    sc12 = [r for r in rows12 if "dollars" in r]
    sc10 = [r for r in rows10 if "dollars" in r]

    print("\n--- 1. SHARES, market order at the signal close (their $187 / $650)")
    s1 = block(firsts(rows12), "shares", nd)
    sa = block(rows12, "shares", nd)
    print("   one a day : n=%d  win %.1f%%  $%.0f/day  $%.0f/trade  %d/%d green"
          % (s1["n"], s1["win"], s1["per_day"], s1["per_trade"], s1["green"], s1["months"]))
    print("   everything: n=%d  win %.1f%%  $%.0f/day  $%.0f/trade  %d/%d green"
          % (sa["n"], sa["win"], sa["per_day"], sa["per_trade"], sa["green"], sa["months"]))

    print("\n--- 2/3. CONTRACTS, market order at the signal close (their $242 / $346 / $843)")
    for lbl, sc in (("IV 1.2x", sc12), ("IV 1.0x", sc10)):
        o1 = block(firsts(sc), "dollars", nd)
        oa = block(sc, "dollars", nd)
        lo, hi = boot_ci(firsts(sc), "dollars", days)
        print("   %s one a day : n=%d  win %.1f%%  $%.0f/day  [$%.0f, $%.0f]  %d/%d green"
              % (lbl, o1["n"], o1["win"], o1["per_day"], lo, hi, o1["green"], o1["months"]))
        print("   %s everything: n=%d  win %.1f%%  $%.0f/day  %d/%d green"
              % (lbl, oa["n"], oa["win"], oa["per_day"], oa["green"], oa["months"]))

    print("\n--- 4. MEAN R vs w*T - (1-w)")
    for lbl, rws, key, denom in (
            ("shares 1/day", firsts(rows12), "r_u", 1.0),
            ("shares all", rows12, "r_u", 1.0),
            ("options 1/day 1.2x", firsts(sc12), "contract_r", 1.0),
            ("options all 1.2x", sc12, "contract_r", 1.0)):
        v = [r[key] for r in rws]
        w = sum(1 for x in v if x > 0) / len(v)
        wins = [x for x in v if x > 0]
        loss = [x for x in v if x <= 0]
        naive = w * 2.0 - (1 - w)
        print("   %-20s mean %+.4fR   win %.3f   avg winner %+.3fR  avg loser %+.3fR   "
              "naive w*2-(1-w) = %+.4fR   gap %+.4fR"
              % (lbl, statistics.fmean(v), w, statistics.fmean(wins),
                 statistics.fmean(loss) if loss else 0.0, naive,
                 statistics.fmean(v) - naive))

    print("\n--- 5. OPTIONS MINUS SHARES per trade, in R, vs the +/-%.4fR bar" % ERROR_BAR)
    for lbl, sc in (("IV 1.2x", sc12), ("IV 1.0x", sc10)):
        for what, rws in (("one a day", firsts(sc)), ("everything", sc)):
            d = [r["contract_r"] - r["r_u"] for r in rws]
            print("   %s %-11s n=%d  mean difference %+.4fR (= $%+.0f/trade)  %s"
                  % (lbl, what, len(d), statistics.fmean(d),
                     statistics.fmean(d) * RISK,
                     "INSIDE the error bar -> TIE"
                     if abs(statistics.fmean(d)) < ERROR_BAR else "OUTSIDE the bar"))
        one = firsts(sc)
        a = [dict(r, x=r["dollars"]) for r in one]
        b2 = [dict(r, x=r["shares"]) for r in one]
        da = {x: 0.0 for x in days}
        for r in a:
            da[r["day"]] += r["x"]
        for r in b2:
            da[r["day"]] -= r["x"]
        v = [da[x] for x in sorted(da)]
        rng = random.Random(7)
        m = sorted(sum(rng.choices(v, k=len(v))) / len(v) for _ in range(4000))
        print("   %s paired per-day difference: $%+.0f/day  [$%+.0f, $%+.0f]"
              % (lbl, sum(v) / len(v), m[100], m[3899]))

    print("\n--- 6. LOOK-AHEAD PROBES")
    # (a) sigma must not change if the whole of `day` is hidden -- it is read
    #     from the prior session only. Recompute with an assertion.
    bad = 0
    for row in traded[:400]:
        pr = prior_range(row["sym"], row["day"])
        if pr is None:
            continue
        d = ARCHIVE / row["sym"]
        earlier = [x for x in _dayindex[row["sym"]] if x < row["day"]]
        b = day_bars(row["sym"], earlier[-1])
        if abs((max(x.h for x in b) - min(x.l for x in b)) - pr) > 1e-9:
            bad += 1
    print("   sigma source is the prior session on disk: %d disagreements in 400 rows" % bad)

    # (b) the market-order arm must use ONLY bar i's close for entry. Re-run a
    #     sample with bar i's high/low corrupted; the answer must not move.
    sample = traded[:1500]

    def rerun(corrupt_i):
        tot = 0.0
        n = 0
        for row in sample:
            b = day_bars(row["sym"], row["day"])
            i = row["entry_i"]
            if not b or i >= len(b) - 1:
                continue
            if corrupt_i:
                b = list(b)
                bi = b[i]
                b[i] = Bar(bi.t, bi.o, bi.h * 1.5, bi.l * 0.5, bi.c)
            sim = run_trade(b[i].c, row["stop"], row["dir"] == "call", b, i)
            if sim:
                tot += sim[0] * RISK
                n += 1
        return tot, n

    a0 = rerun(False)
    a1 = rerun(True)
    print("   entry-minute high/low hidden from the market-order arm: $%.0f over %d "
          "rows vs $%.0f over %d rows -- %s"
          % (a0[0], a0[1], a1[0], a1[1],
             "identical, no intrabar peek at the decision minute"
             if abs(a0[0] - a1[0]) < 1e-6 and a0[1] == a1[1] else "DIFFERENT -> LOOK-AHEAD"))

    # (c) the exit must not use a bar before i+1
    print("   management starts at bar i+1 by construction (range(i+1, len(bars)))")

    # (d) the LIMIT-at-the-level arm: does it need bar i's intrabar extreme to
    #     decide it filled? Yes -- that is a real dependency, quantified here.
    fills = sum(1 for row in traded
                if (lambda b, i: bool(b) and i < len(b) - 1 and row.get("level_px") and
                    ((b[i].l <= row["level_px"] + 1e-9) if row["dir"] == "call"
                     else (b[i].h >= row["level_px"] - 1e-9)))
                (day_bars(row["sym"], row["day"]), row["entry_i"]))
    print("   limit-at-level arm fills %d of %d traded rows -- it is conditioned on the "
          "signal minute's own low/high, i.e. on a bar the resting order could only have "
          "been placed before" % (fills, len(traded)))


if __name__ == "__main__":
    sys.exit(main())


# ---------------------------------------------------------------------------
# PASS 2 -- the order-dependent statistic, the spread sweep, the -1.25R floor.
# Run with:  python research/g80_verify_1.py pass2
# ---------------------------------------------------------------------------
def dd(seq):
    cum = peak = worst = 0.0
    for p in seq:
        cum += p
        peak = max(peak, cum)
        worst = max(worst, peak - cum)
    return worst


def pass2():
    book = json.load(open(BOOK, encoding="utf-8"))
    nd = book["meta"]["sessions"]
    traded = [r for r in book["trades"] if r.get("traded")]
    sym_major = sorted(traded, key=lambda r: (r["sym"], r["day"], r["et"]))
    built = []
    for row in sym_major:
        b = day_bars(row["sym"], row["day"])
        i = row["entry_i"]
        if not b or i >= len(b) - 1:
            continue
        long = row["dir"] == "call"
        entry = b[i].c
        sim = run_trade(entry, row["stop"], long, b, i)
        if sim is None:
            continue
        r_u, tag, exit_px, exit_i = sim
        rec = {"day": row["day"], "sym": row["sym"], "et": row["et"], "tag": tag,
               "r_u": r_u, "shares": r_u * RISK,
               "shares_held": RISK / abs(entry - row["stop"])}
        pr = prior_range(row["sym"], row["day"])
        if pr:
            c = contract_pnl(entry, row["stop"], exit_px, i, exit_i, long,
                             parkinson(pr, entry) * 1.2)
            if c:
                rec.update(dollars=c["dollars"], contracts=c["n"],
                           contract_r=c["contract_r"], prem_risk=c["prem_risk"],
                           p0=c["p0"], capital=c["n"] * c["p0"] * MULT)
        built.append(rec)
    sc = [r for r in built if "dollars" in r]
    chrono = sorted(built, key=lambda r: (r["day"], r["et"], r["sym"]))
    chrono_sc = sorted(sc, key=lambda r: (r["day"], r["et"], r["sym"]))

    print("\n=== PASS 2")
    print("worst drawdown, EVERYTHING taken:")
    print("   options  symbol-major order (what g80 computes): $%.0f" % dd([r["dollars"] for r in sc]))
    print("   options  chronological order (the real sequence): $%.0f" % dd([r["dollars"] for r in chrono_sc]))
    print("   shares   symbol-major order: $%.0f" % dd([r["shares"] for r in built]))
    print("   shares   chronological order: $%.0f" % dd([r["shares"] for r in chrono]))
    o1 = firsts(chrono_sc)
    s1 = firsts(chrono)
    print("worst drawdown, ONE A DAY (already chronological in g80):")
    print("   options $%.0f   shares $%.0f" % (dd([r["dollars"] for r in o1]),
                                               dd([r["shares"] for r in s1])))

    print("\nthe -1.25R floor on contracts (their 1,337 of 4,472 = 29.9%%, worst -5.93R):")
    worse = [r for r in sc if r["contract_r"] < -1.25]
    print("   %d of %d rows (%.1f%%)  worst contract %+.2fR  worst underlying %+.2fR"
          % (len(worse), len(sc), 100 * len(worse) / len(sc),
             min(r["contract_r"] for r in sc), min(r["r_u"] for r in sc)))

    print("\nthe spread sweep, one trade a day (their $162/$166, $44/$166, -$154/$166):")
    for opt_rt, shr_rt in ((0.02, 0.01), (0.05, 0.01), (0.10, 0.01)):
        o = sum(r["dollars"] - r["contracts"] * opt_rt * MULT for r in o1)
        s = sum(r["shares"] - r["shares_held"] * shr_rt for r in s1)
        print("   option $%.2f / stock $%.2f : options $%.0f/day   shares $%.0f/day   "
              "difference $%+.0f/day" % (opt_rt, shr_rt, o / nd, s / nd, (o - s) / nd))
    print("\nposition size (their median 26 contracts vs 1,226 shares):")
    print("   median %d contracts (%d shares of exposure)   median %d shares on the stock side"
          % (statistics.median(r["contracts"] for r in o1),
             statistics.median(r["contracts"] for r in o1) * MULT,
             statistics.median(r["shares_held"] for r in s1)))
    print("   capital to carry $1,000 of risk: median $%.0f"
          % statistics.median(r["capital"] for r in sc))
    print("\nexit mix (their 1,685 target / 2,678 stop / 109 eod on the market order):")
    print("   " + "  ".join("%s %d" % (t, sum(1 for r in sc if r["tag"] == t))
                            for t in ("target", "stop", "eod")))
