"""X13 -- wayfinder probes for the angles nobody in the 12-lane digest is looking at.

Every number in research/x13_new_angles.md comes from here.  No network, no new data:
research/g3_arm_ow1.json (the shipped 2-year book), research/x1_mfe_mae.json (X1's
per-trade MFE/MAE archive) and data_archive/<SYM>/<DAY>.csv (04:00-20:00 1-minute bars,
already on disk -- premarket included).

    python research/x13_new_angles.py            # everything
    python research/x13_new_angles.py selection  # one section

Sections
  selection  the DAY-level selection oracle: one trade per calendar day
  instrument re-score the same 1,017 trades as 0DTE ATM CONTRACTS (Black-Scholes)
  premarket  ex-ante premarket features -- the honest version of X8's look-ahead rangeb
  symbol     is symbol strength persistent?  (split-half + walk-forward)
  durability weekly vs monthly green, against an iid shuffle of the same trades
  arith      what mean R 2.0 actually demands of the average winner
"""
import csv
import json
import math
import os
import random
import statistics as st
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = os.path.join(ROOT, "research", "g3_arm_ow1.json")
MFE = os.path.join(ROOT, "research", "x1_mfe_mae.json")
ARCHIVE = os.path.join(ROOT, "data_archive")
RTH_MIN = 390.0


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def load_book():
    with open(BOOK) as fh:
        return [r for r in json.load(fh)["trades"] if r.get("traded")]


def by_day(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["day"]].append(r)
    return d


def et_min(hhmm):
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m - 570


# ---------------------------------------------------------------- selection
def section_selection(bk):
    bd = by_day(bk)
    days = sorted(bd)
    print("=== SELECTION -- one trade per CALENDAR day (%d days, book %d trades %+.4f R)"
          % (len(days), len(bk), mean(r["r"] for r in bk)))

    def num(x, d=0.0):
        try:
            return float(x)
        except Exception:
            return d

    def pick(key):
        return [sorted(bd[d], key=lambda r: (-key(r), r["et"]))[0] for d in days]

    arms = {
        "ORACLE (best r)": [max(bd[d], key=lambda r: r["r"]) for d in days],
        "first by time": [sorted(bd[d], key=lambda r: r["et"])[0] for d in days],
        "last by time": [sorted(bd[d], key=lambda r: r["et"])[-1] for d in days],
        "highest s": pick(lambda r: num(r.get("s"))),
        "lowest tripped": pick(lambda r: -num(r.get("tripped"))),
        "sgrade S>A>C": pick(lambda r: {"S": 3, "A": 2, "C": 1}.get(r.get("sgrade"), 0)),
        "confluence first": pick(lambda r: 1 if r.get("confluence") == "yes" else 0),
        "clean tag first": pick(lambda r: 1 if "clean" in (r.get("tags") or []) else 0),
        "biggest abs gap": pick(lambda r: abs(num(r.get("gap")))),
        "widest stop pct": pick(lambda r: num(r.get("stop_pct"))),
        "tightest stop pct": pick(lambda r: -num(r.get("stop_pct"))),
        "biggest drange*": pick(lambda r: num(r.get("drange"))),  # * LOOK-AHEAD
    }
    random.seed(7)
    draws = [mean(random.choice(bd[d])["r"] for d in days) for _ in range(2000)]
    out = {k: mean(r["r"] for r in v) for k, v in arms.items()}
    out["random"] = mean(draws)
    for k, v in sorted(out.items(), key=lambda kv: -kv[1]):
        print("   %-18s %+.4f" % (k, v))
    print("   random sd over 2000 draws %.4f   (* drange is full-session = look-ahead)"
          % st.pstdev(draws))

    dead = sum(1 for v in bd.values() if max(r["r"] for r in v) <= 0)
    print("   days where even the best trade is <= 0 : %d of %d (%.1f%%)"
          % (dead, len(days), 100 * dead / len(days)))
    for k in (1, 2, 3):
        tot = [x["r"] for v in bd.values() for x in sorted(v, key=lambda r: -r["r"])[:k]]
        print("   oracle top-%d/day  n=%-4d %+.4f  win %.1f%%"
              % (k, len(tot), mean(tot), 100 * sum(1 for x in tot if x > 0) / len(tot)))
    h = len(days) // 2
    for lbl, dd in (("H1", days[:h]), ("H2", days[h:])):
        print("   %s days=%d oracle %+.4f  first %+.4f  all %+.4f (n=%d)"
              % (lbl, len(dd),
                 mean(max(bd[d], key=lambda r: r["r"])["r"] for d in dd),
                 mean(sorted(bd[d], key=lambda r: r["et"])[0]["r"] for d in dd),
                 mean(r["r"] for d in dd for r in bd[d]),
                 sum(len(bd[d]) for d in dd)))
    bysd = defaultdict(list)
    for r in bk:
        bysd[(r["sym"], r["day"])].append(r)
    print("   symbol-days %d, of which multi-signal %d  -> the competition is CROSS-SYMBOL"
          % (len(bysd), sum(1 for v in bysd.values() if len(v) > 1)))


# --------------------------------------------------------------- instrument
def _n(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def bs(S, K, T, sig, call=True):
    if T <= 0 or sig <= 0:
        return max(0.0, (S - K) if call else (K - S))
    d1 = (math.log(S / K) + 0.5 * sig * sig * T) / (sig * math.sqrt(T))
    d2 = d1 - sig * math.sqrt(T)
    return S * _n(d1) - K * _n(d2) if call else K * _n(-d2) - S * _n(-d1)


def option_r(r, iv_mult=1.2):
    """R measured on a 0DTE ATM CONTRACT instead of on the underlying.

    Strike = entry (perfectly ATM), expiry = today's close, sigma = the day's
    Parkinson range vol x iv_mult.  1R is defined the way options_sizer defines it:
    the modelled premium loss when the underlying reaches the stop, so a stop-out is
    -1R by construction and every deviation from the underlying's R is convexity or
    theta.  NOTE: drange is a full-session range and therefore LOOK-AHEAD -- adequate
    for sizing the effect, not adequate for a shipped arm.  See the .md.
    """
    S0, d = r["entry"], abs(r["entry"] - r["stop"])
    rng = r.get("drange") or 0.0
    if d <= 0 or rng <= 0:
        return None
    call = r["side"] == "L"
    t0 = et_min(r["et"])
    t1 = min(RTH_MIN, t0 + max(1, r["bars"]))
    T0 = max(RTH_MIN - t0, 1.0) / (RTH_MIN * 252.0)
    T1 = max(RTH_MIN - t1, 0.5) / (RTH_MIN * 252.0)
    sig = (rng / S0) / (2 * math.sqrt(math.log(2))) * math.sqrt(252.0) * iv_mult
    p0 = bs(S0, S0, T0, sig, call)
    pstop = bs(S0 - d if call else S0 + d, S0, T0, sig, call)
    risk = p0 - pstop
    if risk <= 1e-6:
        return None
    return (bs(r["exit"], S0, T1, sig, call) - p0) / risk


def section_instrument(bk):
    print("=== INSTRUMENT -- the same 1,017 trades scored as 0DTE ATM CONTRACTS")
    for iv in (1.0, 1.2, 1.5):
        v = [(option_r(r, iv), r["r"]) for r in bk]
        v = [(a, b) for a, b in v if a is not None]
        o = [a for a, _ in v]
        q = sorted(o)
        print("   IV = %.1fx realised   n=%d  CONTRACT %+.4f (win %.1f%%)  UNDERLYING %+.4f (win %.1f%%)"
              % (iv, len(v), mean(o), 100 * sum(1 for x in o if x > 0) / len(o),
                 mean(b for _, b in v), 100 * sum(1 for _, b in v if b > 0) / len(v)))
        print("        contract R  p10 %.2f  p50 %.2f  p90 %.2f  max %.2f"
              % (q[len(q) // 10], q[len(q) // 2], q[9 * len(q) // 10], q[-1]))
    bd = by_day(bk)
    for r in bk:
        r["_or"] = option_r(r)

    def arm(name, sel, f):
        v = [sel(bd[d])[f] for d in sorted(bd) if sel(bd[d]).get(f) is not None]
        print("   %-30s n=%-4d %+.4f  win %.1f%%"
              % (name, len(v), mean(v), 100 * sum(1 for x in v if x > 0) / len(v)))

    print("   -- stacked with one-trade-per-day selection (IV 1.2x) --")
    arm("day-oracle  [underlying]", lambda v: max(v, key=lambda r: r["r"]), "r")
    arm("day-oracle  [contract]", lambda v: max(v, key=lambda r: r["r"]), "_or")
    arm("first-by-time [underlying]", lambda v: sorted(v, key=lambda r: r["et"])[0], "r")
    arm("first-by-time [contract]", lambda v: sorted(v, key=lambda r: r["et"])[0], "_or")


# ---------------------------------------------------------------- premarket
def premarket(sym, day):
    p = os.path.join(ARCHIVE, sym, day + ".csv")
    if not os.path.exists(p):
        return None
    hi, lo, vol, first, last = -1e9, 1e9, 0.0, None, None
    with open(p, newline="") as fh:
        for row in csv.DictReader(fh):
            if row["Datetime"][11:16] >= "09:30":
                continue
            hi = max(hi, float(row["High"]))
            lo = min(lo, float(row["Low"]))
            vol += float(row["Volume"])
            if first is None:
                first = float(row["Open"])
            last = float(row["Close"])
    if last is None or hi <= -1e8:
        return None
    return dict(pm_hi=hi, pm_lo=lo, pm_vol=vol,
                pm_ret=(last - first) / first if first else 0.0)


def section_premarket(bk):
    rows = []
    for r in bk:
        d = premarket(r["sym"], r["day"])
        if not d:
            continue
        r.update(d)
        rg = r["pm_hi"] - r["pm_lo"]
        r["pmr_pct"] = rg / r["entry"] * 100
        r["pm_ret_abs"] = abs(r["pm_ret"]) * 100
        r["pm_pos"] = ((r["entry"] - r["pm_lo"]) / rg) if rg > 0 else 0.5
        r["out_pm"] = 1 if (r["entry"] > r["pm_hi"] or r["entry"] < r["pm_lo"]) else 0
        rows.append(r)
    print("=== PREMARKET -- ex-ante (known 09:29), %d of %d rows have premarket bars"
          % (len(rows), len(bk)))

    def quart(name, key):
        v = sorted(rows, key=lambda r: r[key])
        q = len(v) // 4
        parts = [v[:q], v[q:2 * q], v[2 * q:3 * q], v[3 * q:]]
        print("   %-14s " % name + " | ".join(
            "Q%d n=%d %+.3f" % (i + 1, len(p), mean(x["r"] for x in p))
            for i, p in enumerate(parts)))

    quart("pm range pct", "pmr_pct")
    quart("pm volume", "pm_vol")
    quart("abs pm return", "pm_ret_abs")
    quart("pos in pm rng", "pm_pos")
    a = [r["r"] for r in rows if r["out_pm"]]
    b = [r["r"] for r in rows if not r["out_pm"]]
    print("   entry OUTSIDE the premarket range n=%d %+.4f | inside n=%d %+.4f"
          % (len(a), mean(a), len(b), mean(b)))
    bd = by_day(rows)
    for nm, key, rev in (("max pm range pct", "pmr_pct", True),
                         ("min pm range pct", "pmr_pct", False),
                         ("max pm volume", "pm_vol", True),
                         ("max abs pm return", "pm_ret_abs", True),
                         ("outside pm range", "out_pm", True)):
        sel = [sorted(v, key=lambda r: ((-r[key]) if rev else r[key], r["et"]))[0]["r"]
               for v in bd.values()]
        print("   1/day by %-18s n=%d %+.4f" % (nm, len(sel), mean(sel)))
    print("   1/day first-by-time             n=%d %+.4f  (oracle %+.4f)"
          % (len(bd), mean(sorted(v, key=lambda r: r["et"])[0]["r"] for v in bd.values()),
             mean(max(v, key=lambda r: r["r"])["r"] for v in bd.values())))


# ------------------------------------------------------------------- symbol
def section_symbol(bk):
    print("=== SYMBOL -- is per-symbol edge persistent?")
    bysym = defaultdict(list)
    for r in sorted(bk, key=lambda r: r["day"]):
        bysym[r["sym"]].append(r)
    pairs = []
    for s, v in bysym.items():
        h = len(v) // 2
        if h >= 10:
            pairs.append((s, mean(x["r"] for x in v[:h]), mean(x["r"] for x in v[h:]), len(v)))
    xs = [a for _, a, _, _ in pairs]
    ys = [b for _, _, b, _ in pairs]
    mx, my = mean(xs), mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
    print("   split-half pearson r = %+.3f over %d symbols with >=20 trades"
          % (num / den, len(pairs)))
    top = {s for s, a, _, _ in sorted(pairs, key=lambda t: -t[1])[:6]}
    h2 = [x["r"] for s, v in bysym.items() if s in top for x in v[len(v) // 2:]]
    allh2 = [x["r"] for _, v in bysym.items() for x in v[len(v) // 2:]]
    print("   top-6 symbols chosen on H1 -> H2 %+.4f (n=%d) vs all H2 %+.4f (n=%d)"
          % (mean(h2), len(h2), mean(allh2), len(allh2)))
    bd = by_day(bk)
    hist = defaultdict(list)
    wf = []
    for d in sorted(bd):
        v = bd[d]
        wf.append(sorted(v, key=lambda r: (-(mean(hist[r["sym"]]) if len(hist[r["sym"]]) >= 5
                                             else -99), r["et"]))[0]["r"])
        for r in v:
            hist[r["sym"]].append(r["r"])
    print("   walk-forward 'best trailing symbol' 1/day  n=%d %+.4f  (first-by-time %+.4f)"
          % (len(wf), mean(wf),
             mean(sorted(bd[d], key=lambda r: r["et"])[0]["r"] for d in sorted(bd))))


# --------------------------------------------------------------- durability
def section_durability(bk):
    import datetime as dt
    print("=== DURABILITY -- observed green streaks vs an iid shuffle of the SAME trades")
    allr = [r["r"] for r in bk]

    def shuffle_red(sizes, seed, n=3000):
        rng = random.Random(seed)
        out = []
        for _ in range(n):
            sh = allr[:]
            rng.shuffle(sh)
            i = c = 0
            for s in sizes:
                if sum(sh[i:i + s]) <= 0:
                    c += 1
                i += s
            out.append(c)
        out.sort()
        return out

    for lbl, key in (("WEEK", lambda r: dt.date(*map(int, r["day"].split("-"))).isocalendar()[:2]),
                     ("MONTH", lambda r: r["ym"])):
        buck = defaultdict(list)
        for r in bk:
            buck[key(r)].append(r["r"])
        tot = {k: sum(v) for k, v in buck.items()}
        red = [k for k, v in tot.items() if v <= 0]
        sizes = [len(v) for v in buck.values()]
        sim = shuffle_red(sizes, 11 if lbl == "WEEK" else 12)
        print("   %-5s %d buckets, observed RED %d (worst %.2fR) | iid shuffle mean %.1f p50 %d p95 %d"
              % (lbl, len(tot), len(red), min(tot.values()), mean(sim),
                 sim[len(sim) // 2], sim[int(0.95 * len(sim))]))


# ------------------------------------------------------------------- arith
def section_arith(bk):
    print("=== ARITHMETIC -- what mean R 2.0 demands")
    w = [r["r"] for r in bk if r["r"] > 0]
    losses = [r["r"] for r in bk if r["r"] <= 0]
    p = len(w) / len(bk)
    need = (2.0 - (1 - p) * mean(losses)) / p
    print("   win %.1f%%  avg win %+.4f  avg loss %+.4f  -> mean R 2.0 needs avg win %+.4f (+%.0f%%)"
          % (100 * p, mean(w), mean(losses), need, 100 * (need / mean(w) - 1)))
    rr = [abs(r["target"] - r["entry"]) / abs(r["entry"] - r["stop"])
          for r in bk if r.get("target") and abs(r["entry"] - r["stop"]) > 1e-9]
    print("   planned R:R on every row: mean %.4f median %.4f min %.3f max %.3f"
          % (mean(rr), st.median(rr), min(rr), max(rr)))
    if os.path.exists(MFE):
        with open(MFE) as fh:
            mfe = [r["mfe"] for r in json.load(fh)["rows"]]
        print("   MFE ladder: " + "  ".join(
            ">=%dR %.1f%%" % (t, 100 * sum(1 for x in mfe if x >= t) / len(mfe))
            for t in (2, 3, 4, 5, 6, 8)))
        print("   mean MFE %.4f  median %.4f  (X1 archive, 1,017 rows)"
              % (mean(mfe), st.median(mfe)))


def section_loop(bk):
    """Can a DAILY loop learn from money?  Two-sample detectability at 95%/80%."""
    print("=== LOOP -- what a self-improving daily loop can and cannot learn from")
    rs = [r["r"] for r in bk]
    sd = st.pstdev(rs)
    bd = by_day(bk)
    per_day = len(bk) / len(bd)
    print("   book sd %.4f R over %d trades, %.2f trades per traded day"
          % (sd, len(rs), per_day))
    for delta in (0.05, 0.10, 0.20):
        n = 2 * (1.96 + 0.84) ** 2 * sd * sd / (delta * delta)
        print("   to detect %+.2f R at 95%%/80%%: n=%.0f trades = %.0f trading days = %.1f years"
              % (delta, n, n / per_day, n / per_day / 252))
    print("   -> money is not a daily signal.  A daily loop must learn from marks or health.")


SECTIONS = {"selection": section_selection, "instrument": section_instrument,
            "premarket": section_premarket, "symbol": section_symbol,
            "durability": section_durability, "arith": section_arith,
            "loop": section_loop}

if __name__ == "__main__":
    book = load_book()
    for name in (sys.argv[1:] or list(SECTIONS)):
        SECTIONS[name](book)
        print()
