"""G7.3 / polygon - re-price the book's trades as REAL option contracts.

Reads the minute bars pulled by `g73_polygon_fetch.py` (real OPRA 1-minute aggregates for
the actual contracts, expired included) and the cached underlying bars in `data_archive/`.
Prints dollars-per-day as options beside dollars-per-day as shares, on the same rows.

Everything here is measured, not modelled, EXCEPT the position size, and the one modelled
input is measured from the same real tape:

  entry premium P0  = REAL close of the contract's `et` minute bar
  exit  premium P1  = REAL close of the contract's `et + bars` minute bar
  delta             = OLS slope of contract close on underlying close over the
                      PRE-ENTRY minutes of the same session (09:30..et). Ex-ante:
                      no bar at or after the entry minute is used.
  contracts         = floor($1,000 / (delta * |entry - stop| * 100)), min 1
                      -- this is `options_sizer.build_options_plan`'s own rule, with the
                      flat DEFAULT_DELTA = 0.5 replaced by the measured slope.

CONVENTION, and it is the trap T2 fell into: 54% of the book's rows are `scaled`, so the
book's own `r` is a 50/50 ladder blend, while a single option exit price is one exit for
the whole position. Comparing those two compares an exit plan, not an instrument. So both
columns here are SINGLE - full size held to `exit` - and the book's own ladder R is
printed beside them for reference only, never differenced against the option column.

  python research/g73_polygon_reprice.py
"""
import csv
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import research.g73_polygon_fetch as F  # noqa: E402
from research.g73_polygon_fetch import (  # noqa: E402
    CACHE, FOCUS, WINDOW_START, sample_rows,
)

# This script is READ-ONLY against the cache: it must never fire an API call, so a
# re-run is free and cannot collide with a fetch already in flight.
_orig_catalog = F.catalog


def _cached_catalog(sym, month):
    f = CACHE / "catalog" / (sym + "_" + month + ".json")
    return json.loads(f.read_text()) if f.exists() else []


F.catalog = _cached_catalog
F._get = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("reprice must not call the API"))
pick_contract = F.pick_contract

RISK_DOLLARS = 1000.0
FEE_PER_CONTRACT_ROUND_TURN = 1.24   # tastytrade schedule, quoted in g71_instrument.md
MIN_PRE_BARS = 8                     # minutes of pre-entry tape needed to fit a delta


def stock_minutes(sym, day):
    p = ROOT / "data_archive" / sym / (day + ".csv")
    if not p.exists():
        return {}
    out = {}
    with open(p, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            hhmm = row["Datetime"][11:16]
            out[hhmm] = float(row["Close"])
    return out


def cached_opt(ticker, day):
    f = CACHE / "aggs" / (ticker.replace(":", "_") + "_" + day + ".json")
    if not f.exists():
        return None
    j = json.loads(f.read_text())
    return None if "_error" in j else j


def bar_near(series, hhmm, span=3):
    """Closest available minute within +/- span. Returns (key, bar) or (None, None)."""
    if hhmm in series:
        return hhmm, series[hhmm]
    h, m = int(hhmm[:2]), int(hhmm[3:5])
    for d in range(1, span + 1):
        for k in (h * 60 + m - d, h * 60 + m + d):
            s = "%02d:%02d" % (k // 60, k % 60)
            if s in series:
                return s, series[s]
    return None, None


def plus_minutes(hhmm, n):
    k = int(hhmm[:2]) * 60 + int(hhmm[3:5]) + n
    return "%02d:%02d" % ((k // 60) % 24, k % 60)


def tape_delta(opt, stk, et):
    """OLS slope of option close on underlying close, PRE-ENTRY minutes only."""
    xs, ys = [], []
    for hhmm, bar in opt.items():
        if "09:30" <= hhmm <= et and hhmm in stk and bar.get("v", 0) > 0:
            xs.append(stk[hhmm])
            ys.append(bar["c"])
    if len(xs) < MIN_PRE_BARS:
        return None
    mx, my = st.mean(xs), st.mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den <= 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    # A put's price falls as the stock rises, so its fitted slope is negative. Delta
    # MAGNITUDE is what sizes the position, so take the absolute value -- and check the
    # sign points the right way, because a put whose price rose with the stock over the
    # pre-entry window is a bad fit, not a bad put.
    return abs(slope), slope


def underlying_single_r(row):
    risk = abs(row["entry"] - row["stop"])
    if risk <= 0:
        return None
    move = (row["exit"] - row["entry"]) if row["dir"] == "call" else (row["entry"] - row["exit"])
    return move / risk


def main():
    rows = sample_rows()
    recs, skipped = [], defaultdict(int)
    for r in rows:
        c = pick_contract(r["sym"], r["day"], r["entry"], r["dir"] == "call")
        if not c:
            skipped["no contract listed"] += 1
            continue
        opt = cached_opt(c["ticker"], r["day"])
        if not opt:
            skipped["no option tape cached"] += 1
            continue
        stk = stock_minutes(r["sym"], r["day"])
        if not stk:
            skipped["no underlying bars"] += 1
            continue
        k0, b0 = bar_near(opt, r["et"])
        k1, b1 = bar_near(opt, plus_minutes(r["et"], int(r["bars"])))
        if b0 is None or b1 is None or b0["c"] <= 0:
            skipped["no bar at entry or exit minute"] += 1
            continue
        fit = tape_delta(opt, stk, r["et"])
        if fit is None:
            skipped["not enough pre-entry option bars"] += 1
            continue
        d, signed = fit
        want_positive = (r["dir"] == "call")
        if (signed > 0) != want_positive:
            skipped["pre-entry fit has the wrong sign"] += 1
            continue
        if not (0.05 <= d <= 1.05):
            skipped["fitted delta out of [0.05, 1.05]"] += 1
            continue
        d = min(d, 1.0)
        prem_risk = d * abs(r["entry"] - r["stop"])
        if prem_risk <= 0:
            skipped["degenerate risk"] += 1
            continue
        n = max(1, int(RISK_DOLLARS / (prem_risk * 100.0)))
        gross = (b1["c"] - b0["c"]) * 100.0 * n
        ur = underlying_single_r(r)
        if ur is None:
            skipped["degenerate risk"] += 1
            continue
        # The clean comparison. The book enters at `entry` (a limit at the level) and
        # exits at `exit`, but the option tape only has minute bars -- so pricing the
        # option at a minute CLOSE while pricing the stock at the book's limit compares
        # two different fills and quietly charges the difference to the option. Price
        # BOTH instruments off the SAME two minutes of the SAME session instead. Nothing
        # modelled on either side; only the contract count is.
        s0, s1 = stk.get(k0), stk.get(k1)
        if s0 is None or s1 is None:
            skipped["no underlying bar at those minutes"] += 1
            continue
        sm = (s1 - s0) if r["dir"] == "call" else (s0 - s1)
        shares_matched = sm / abs(r["entry"] - r["stop"]) * RISK_DOLLARS

        recs.append({
            "shares_matched": shares_matched, "s0": s0, "s1": s1,
            "k0": k0, "k1": k1,
            "sym": r["sym"], "day": r["day"], "et": r["et"], "dir": r["dir"],
            "ticker": c["ticker"], "dte": c["dte"], "strike": c["strike"],
            "p0": b0["c"], "p1": b1["c"], "delta": d, "n": n,
            "opt_gross": gross,
            "opt_fee": gross - n * FEE_PER_CONTRACT_ROUND_TURN,
            "opt_002": gross - n * FEE_PER_CONTRACT_ROUND_TURN - n * 100 * 0.02,
            "opt_005": gross - n * FEE_PER_CONTRACT_ROUND_TURN - n * 100 * 0.05,
            "shares_single": ur * RISK_DOLLARS,
            "book_r": r["r"], "book_pnl": r["pnl"], "scaled": bool(r.get("scaled")),
        })

    if not recs:
        print("no rows priced yet -- run research/g73_polygon_fetch.py first")
        return

    days = len({(x["day"]) for x in recs})
    print("=" * 74)
    print("G7.3  REAL OPTION TAPE vs SHARES  -- %s, %d trades, %d sessions"
          % ("/".join(FOCUS), len(recs), days))
    print("window %s .. %s  (2-year Polygon entitlement floor)" % (WINDOW_START, max(x["day"] for x in recs)))
    print("=" * 74)

    def line(label, vals):
        m = st.mean(vals)
        sd = st.pstdev(vals) if len(vals) > 1 else 0.0
        se = sd / (len(vals) ** 0.5) if vals else 0.0
        win = 100.0 * sum(1 for v in vals if v > 0) / len(vals)
        print("  %-40s $%9.0f  +/-$%-7.0f  win %5.1f%%  total $%s"
              % (label, m, 1.96 * se, win, format(round(sum(vals)), ",")))

    # Representativeness. The option pull is paced at 5 calls/min, so what is priced at
    # any moment is a PREFIX of the sample, not the sample. Print all three populations
    # side by side so nobody reads a partial pull as the answer.
    b = json.loads((ROOT / "research" / "bt2y_trades.json").read_text())
    pop = [r for r in b["trades"] if r.get("traded") and r["sym"] in FOCUS
           and r["day"] >= WINDOW_START]

    def shr(rs):
        v = [underlying_single_r(r) for r in rs]
        v = [x for x in v if x is not None]
        return st.mean(v) * RISK_DOLLARS, 100.0 * sum(1 for x in v if x > 0) / len(v)

    print("\nIS WHAT GOT PRICED REPRESENTATIVE? (shares, single exit)")
    for lab, rs in [("all %d traded rows" % len(pop), pop),
                    ("the %d-row sample" % len(rows), rows)]:
        m, w = shr(rs)
        print("  %-26s $%+7.0f / trade   win %4.1f%%" % (lab, m, w))
    # Same measure as the two rows above (the book's own limit fill), so the three are
    # actually comparable -- this row exists to show the priced subset is not a skewed
    # slice of the sample, and it can only do that if it is the SAME statistic.
    m = st.mean(x["shares_single"] for x in recs)
    w = 100.0 * sum(1 for x in recs if x["shares_single"] > 0) / len(recs)
    print("  %-26s $%+7.0f / trade   win %4.1f%%"
          % ("the %d actually priced" % len(recs), m, w))

    print("\nPER TRADE -- both instruments off the SAME two minute closes.")
    print("This is the apples-to-apples arm and the only one a minute tape can support.")
    line("SHARES   at the minute close", [x["shares_matched"] for x in recs])
    line("OPTIONS real tape, mid, no costs", [x["opt_gross"] for x in recs])
    line("OPTIONS  + tastytrade fees", [x["opt_fee"] for x in recs])
    line("OPTIONS  + fees + $0.02 spread", [x["opt_002"] for x in recs])
    line("OPTIONS  + fees + $0.05 spread", [x["opt_005"] for x in recs])

    print("\n  NOT comparable, for reference only: the book fills the stock at its own")
    print("  limit price, which is inside the bar the order was placed in. The same %d"
          % len(recs))
    print("  rows book $%+.0f / trade that way. A minute bar carries no limit fill, so"
          % st.mean(x["shares_single"] for x in recs))
    print("  differencing the option against THAT would charge the option for a fill")
    print("  advantage the stock arm was simply handed. (x9 measured the same optimism")
    print("  at -0.6653R on the underlying.) The gap here is $%+.0f a trade."
          % (st.mean(x["shares_single"] for x in recs)
             - st.mean(x["shares_matched"] for x in recs)))

    # Paired bootstrap on the difference, because this project's standing method finding
    # is that every A/B it has ever run moves less than its own error bar. Resample the
    # SAME rows, so nothing but the instrument differs.
    import random
    random.seed(20260829)
    print("\nOPTIONS MINUS SHARES, per trade, paired, 10,000 resamples:")
    for lab, key in [("mid, no costs", "opt_gross"), ("+fees", "opt_fee"),
                     ("+fees +$0.02 spread", "opt_002"),
                     ("+fees +$0.05 spread", "opt_005")]:
        diffs = [x[key] - x["shares_matched"] for x in recs]
        obs = st.mean(diffs)
        boot = sorted(st.mean(random.choices(diffs, k=len(diffs))) for _ in range(10000))
        lo, hi = boot[249], boot[9750]
        verdict = "clears its bar" if (lo > 0) == (hi > 0) else "INSIDE THE NOISE"
        print("  %-22s $%+8.0f   95%% CI [$%+.0f, $%+.0f]   %s"
              % (lab, obs, lo, hi, verdict))

    print("\nPER SESSION (dollars a day, these symbols, these rows):")
    for lab, key in [("shares", "shares_matched"), ("options mid", "opt_gross"),
                     ("options +fees", "opt_fee"), ("options +fees+$0.02", "opt_002"),
                     ("options +fees+$0.05", "opt_005")]:
        print("  %-24s $%8.0f / day" % (lab, sum(x[key] for x in recs) / days))

    print("\nWHAT CONTRACT DID IT ACTUALLY BUY:")
    dtes = defaultdict(int)
    for x in recs:
        dtes[x["dte"]] += 1
    for k in sorted(dtes):
        print("  %2d DTE  %4d trades  (%4.1f%%)" % (k, dtes[k], 100.0 * dtes[k] / len(recs)))
    print("  median contracts sized: %d   p90 %d   max %d"
          % (st.median(x["n"] for x in recs),
             sorted(x["n"] for x in recs)[int(0.9 * len(recs)) - 1],
             max(x["n"] for x in recs)))
    print("  median entry premium:   $%.2f  -> median cash debit $%s"
          % (st.median(x["p0"] for x in recs),
             format(round(st.median(x["p0"] * 100 * x["n"] for x in recs)), ",")))
    print("  median measured delta:  %.2f  (repo's shipped constant is 0.50)"
          % st.median(x["delta"] for x in recs))

    print("\nROWS DROPPED (%d of %d attempted):" % (sum(skipped.values()), len(rows)))
    for k, v in sorted(skipped.items(), key=lambda kv: -kv[1]):
        print("  %-34s %d" % (k, v))

    out = ROOT / "research" / "g73_polygon_reprice.json"
    out.write_text(json.dumps(recs, indent=1))
    print("\nrows written to %s" % out)


if __name__ == "__main__":
    main()
