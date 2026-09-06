"""t2_referee.py -- independent re-derivation of T2 (row commit c1261604).

Refutation pass. Nothing here imports g213_instruments; every number is
recomputed from research/tape/instruments_2026-09-05.json.gz and from the
baseline book, with this file's own arithmetic, so a bug in the builder's
aggregation cannot reproduce itself here.

Sections
  A  per-instrument $/day, mean R, win%, green months, recomputed
  B  contract rounding: the realised-R distribution vs 1.0
  C  basis shock: re-price the futures column at +/- ratio shocks
  D  instrument_source labelling and the real-bar share
  E  the futures-vs-shares delta, decomposed
  F  Polygon coverage forensics: how many rows were ever attempted
  G  option commission asymmetry

Run: python research/t2_referee.py            (offline, no network)
     python research/t2_referee.py --refetch  (adds section H: 10 live re-prices)
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BOOK = ROOT / "research" / "tape" / "instruments_2026-09-05.json.gz"
BASELINE = ROOT / "research" / "tape" / "baseline_2026-09-05.json.gz"
CACHE = ROOT / "data_archive" / "options"
BOUNDARY = "2025-09-01"
RISK = 1000.0

FUT_MAP = {"SPY": "MES", "QQQ": "MNQ", "IWM": "M2K"}
FUT_RATIO = {"SPY": 10.0, "QQQ": 41.35, "IWM": 10.0}
FUT_TICK = {"MES": 0.25, "MNQ": 0.25, "M2K": 0.10}
FUT_MULT = {"MES": 5.0, "MNQ": 2.0, "M2K": 5.0}
FUT_COMM_SIDE = 0.62


def load():
    d = json.load(gzip.open(BOOK, "rt", encoding="utf-8"))
    return d["meta"], d["trades"]


def agg(rows, n_days):
    """rows: [(day, pnl)]. Independent of g72_suppress_price."""
    if not rows:
        return None
    pnls = [p for _, p in rows]
    total = sum(pnls)
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    by_m = defaultdict(float)
    for day, p in rows:
        by_m[day[:7]] += p
    return {
        "n": len(rows),
        "total": round(total, 2),
        "per_day": round(total / n_days, 2),
        "mean_r_vs_1000": round(total / len(rows) / RISK, 4),
        "win_pct": round(wins / (wins + losses) * 100, 1) if wins + losses else 0.0,
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "months": len(by_m),
    }


def section_a(trades):
    print("== A. per-instrument, recomputed independently ==")
    days_all = {t["day"] for t in trades}
    days_h1 = {t["day"] for t in trades if t["day"] < BOUNDARY}
    days_h2 = {t["day"] for t in trades if t["day"] >= BOUNDARY}
    print("day counts: all=%d h1=%d h2=%d" % (len(days_all), len(days_h1), len(days_h2)))
    out = {}
    for key in ("shares", "futures", "options"):
        rows = [(t["day"], t[key]["pnl"]) for t in trades if "pnl" in t.get(key, {})]
        h1 = [r for r in rows if r[0] < BOUNDARY]
        h2 = [r for r in rows if r[0] >= BOUNDARY]
        out[key] = {
            "whole": agg(rows, len(days_all)),
            "h1": agg(h1, len(days_h1)),
            "h2": agg(h2, len(days_h2)),
        }
        for lab, sl in (("whole", out[key]["whole"]), ("h1", out[key]["h1"]), ("h2", out[key]["h2"])):
            if sl:
                print("  %-8s %-5s n=%-4d $/day=%8.2f meanR=%7.4f win=%5.1f%% green=%d/%d"
                      % (key, lab, sl["n"], sl["per_day"], sl["mean_r_vs_1000"],
                         sl["win_pct"], sl["months_green"], sl["months"]))
    # matched shares on the futures-eligible rows
    fut_ids = {t["id"] for t in trades if "pnl" in t.get("futures", {})}
    rows = [(t["day"], t["shares"]["pnl"]) for t in trades if t["id"] in fut_ids]
    m = agg(rows, len(days_all))
    print("  %-8s %-5s n=%-4d $/day=%8.2f meanR=%7.4f win=%5.1f%% green=%d/%d"
          % ("sh-match", "whole", m["n"], m["per_day"], m["mean_r_vs_1000"],
             m["win_pct"], m["months_green"], m["months"]))
    # matched shares split by half, for the sample-size rule
    for lab, sl in (("h1", [r for r in rows if r[0] < BOUNDARY]),
                    ("h2", [r for r in rows if r[0] >= BOUNDARY])):
        a = agg(sl, len(days_h1) if lab == "h1" else len(days_h2))
        if a:
            print("  %-8s %-5s n=%-4d $/day=%8.2f green=%d/%d"
                  % ("sh-match", lab, a["n"], a["per_day"], a["months_green"], a["months"]))
    # futures halves trade counts (sample-size rule)
    fr = [(t["day"], t["futures"]["pnl"]) for t in trades if "pnl" in t.get("futures", {})]
    print("  futures h1 n=%d, h2 n=%d  (30-trade floor)"
          % (len([r for r in fr if r[0] < BOUNDARY]), len([r for r in fr if r[0] >= BOUNDARY])))
    return out


def section_b(trades):
    print("\n== B. contract rounding: realised R vs 1.0 ==")
    for key in ("futures", "options"):
        vals = [t[key]["actual_r_dollars"] for t in trades
                if "actual_r_dollars" in t.get(key, {})]
        if not vals:
            continue
        vals_s = sorted(vals)
        n = len(vals_s)
        rr = [v / RISK for v in vals_s]
        def pct(p):
            return rr[min(n - 1, int(p * n))]
        off5 = sum(1 for v in rr if abs(v - 1.0) > 0.05)
        off10 = sum(1 for v in rr if abs(v - 1.0) > 0.10)
        print("  %-8s n=%d  realised R: min=%.4f p05=%.4f p50=%.4f p95=%.4f max=%.4f"
              % (key, n, rr[0], pct(0.05), pct(0.50), pct(0.95), rr[-1]))
        print("           mean=%.4f  |R-1|>5%%: %d (%.1f%%)  |R-1|>10%%: %d (%.1f%%)"
              % (sum(rr) / n, off5, off5 / n * 100, off10, off10 / n * 100))
        c = [t[key]["contracts"] for t in trades if "contracts" in t.get(key, {})]
        c.sort()
        print("           contracts: min=%d p50=%d max=%d ; contracts==1: %d"
              % (c[0], c[len(c) // 2], c[-1], sum(1 for x in c if x == 1)))
        if key == "futures":
            nm = sorted(t["futures"]["notional"] for t in trades
                        if "notional" in t.get("futures", {}))
            dm = sorted(t["futures"]["day_margin"] for t in trades
                        if "day_margin" in t.get("futures", {}))
            print("           notional: p50=$%s max=$%s ; day margin: p50=$%s max=$%s"
                  % (format(nm[len(nm) // 2], ",.0f"), format(nm[-1], ",.0f"),
                     format(dm[len(dm) // 2], ",.0f"), format(dm[-1], ",.0f")))


def base_rows():
    b = json.load(gzip.open(BASELINE, "rt", encoding="utf-8"))
    return {r.get("id") or "": r for r in b["trades"]}, b["trades"]


def section_c(trades):
    """Re-price futures at ratio shocks, using entry/stop from the baseline book."""
    print("\n== C. basis shock on the futures column ==")
    _, brows = base_rows()
    # index the baseline by (sym, day, et, entry, stop) fragments of the id
    byk = {}
    for r in brows:
        byk[(r["sym"], r["day"], r["et"], round(float(r["entry"]), 4))] = r
    days_all = len({t["day"] for t in trades})
    matched = 0
    shocks = [-0.10, -0.05, -0.02, -0.01, 0.0, 0.01, 0.02, 0.05, 0.10]
    results = {}
    for sh in shocks:
        rows = []
        for t in trades:
            if "pnl" not in t.get("futures", {}):
                continue
            k = (t["sym"], t["day"], t["et"], round(float(t["id"].split("|")[3]), 4))
            br = byk.get(k)
            if br is None:
                continue
            sym = t["sym"]
            fut = FUT_MAP[sym]
            ratio = FUT_RATIO[sym] * (1.0 + sh)
            tick, mult = FUT_TICK[fut], FUT_MULT[fut]
            ie = round(round(br["entry"] * ratio / tick) * tick, 4)
            istop = round(round(br["stop"] * ratio / tick) * tick, 4)
            rpts = abs(ie - istop) or tick
            rpc = rpts * mult
            ctr = max(1, round(RISK / rpc))
            ard = ctr * rpc
            pnl = t["r"] * ard - 2 * FUT_COMM_SIDE * ctr
            rows.append((t["day"], pnl))
        if sh == 0.0:
            matched = len(rows)
        a = agg(rows, days_all)
        results[sh] = a
        print("  ratio %+5.1f%%  n=%-4d $/day=%7.2f  meanR=%7.4f  green=%d/%d"
              % (sh * 100, a["n"], a["per_day"], a["mean_r_vs_1000"],
                 a["months_green"], a["months"]))
    print("  rows matched back to the baseline at shock 0: %d" % matched)
    # does the reproduction at shock 0 match the book?
    book_fut = agg([(t["day"], t["futures"]["pnl"]) for t in trades
                    if "pnl" in t.get("futures", {})], days_all)
    print("  book futures whole: $%.2f/day green=%d/%d ; my shock-0 rebuild: $%.2f/day green=%d/%d"
          % (book_fut["per_day"], book_fut["months_green"], book_fut["months"],
             results[0.0]["per_day"], results[0.0]["months_green"], results[0.0]["months"]))
    spread = max(a["per_day"] for a in results.values()) - min(a["per_day"] for a in results.values())
    gm = {a["months_green"] for a in results.values()}
    print("  $/day range across +/-10%% basis: $%.2f ; green-month values seen: %s"
          % (spread, sorted(gm)))
    # additive basis (cost of carry) -- cancels exactly in a difference
    print("  additive basis (futures = index + carry) cancels exactly: entry-stop is a difference")


def section_d(trades):
    print("\n== D. instrument_source labelling and the real-bar share ==")
    src = defaultdict(int)
    missing = 0
    for t in trades:
        o = t.get("options")
        if not o:
            missing += 1
            continue
        s = o.get("instrument_source")
        if s is None:
            missing += 1
        else:
            src[s] += 1
    print("  options rows: %d ; sources: %s ; rows with no instrument_source: %d"
          % (len(trades), dict(src), missing))
    real = src.get("real", 0)
    print("  real share computed from instrument_source: %d/%d = %.2f%%"
          % (real, len(trades), real / len(trades) * 100))
    # fields present on real vs model
    rf = set()
    mf = set()
    for t in trades:
        o = t["options"]
        (rf if o["instrument_source"] == "real" else mf).update(o.keys())
    print("  real-row fields:  %s" % sorted(rf))
    print("  model-row fields: %s" % sorted(mf))
    # futures labelling
    fs = defaultdict(int)
    for t in trades:
        fs[t["futures"].get("instrument", "MISSING")] += 1
    print("  futures instrument field: %s" % dict(fs))


def section_e(trades):
    print("\n== E. futures-vs-shares delta, decomposed ==")
    fut = [t for t in trades if "pnl" in t.get("futures", {})]
    d_total = sum(t["shares"]["pnl"] - t["futures"]["pnl"] for t in fut)
    comm = sum(t["futures"]["commission"] for t in fut)
    sizing = sum(t["r"] * (RISK - t["futures"]["actual_r_dollars"]) for t in fut)
    days_all = len({t["day"] for t in trades})
    print("  n=%d  shares-minus-futures total = $%.2f" % (len(fut), d_total))
    print("    of which commission            = $%.2f" % comm)
    print("    of which integer-sizing residual= $%.2f" % sizing)
    print("    unexplained                    = $%.2f" % (d_total - comm - sizing))
    print("  that delta is $%.2f/day on the %d-day denominator" % (d_total / days_all, days_all))
    # month-by-month: which month flips
    bm_f, bm_s = defaultdict(float), defaultdict(float)
    for t in fut:
        bm_f[t["day"][:7]] += t["futures"]["pnl"]
        bm_s[t["day"][:7]] += t["shares"]["pnl"]
    flips = [(m, bm_s[m], bm_f[m]) for m in bm_s if (bm_s[m] > 0) != (bm_f[m] > 0)]
    print("  months where the sign differs between shares and futures on the same rows: %d" % len(flips))
    for m, s, f in flips:
        print("    %s shares=$%.2f futures=$%.2f (gap $%.2f)" % (m, s, f, s - f))


def section_f(trades):
    print("\n== F. Polygon coverage forensics ==")
    aggs = sorted((CACHE / "aggs").glob("*.json"))
    cats = sorted((CACHE / "catalog").glob("*.json"))
    ok = err = 0
    errs = []
    for f in aggs:
        j = json.loads(f.read_text(encoding="utf-8"))
        if j.get("_status"):
            err += 1
            errs.append((f.name, j["_status"]))
        else:
            ok += 1
    print("  aggs cache files: %d (ok=%d, status-error=%d)" % (len(aggs), ok, err))
    for n, s in errs:
        print("    error: %s -> %s" % (n, s))
    print("  catalog cache files: %d" % len(cats))
    print("  progress checkpoint exists: %s" % (CACHE / "g213_progress.json").exists())
    print("  => rows ever ATTEMPTED against Polygon aggs: %d of %d (%.1f%%)"
          % (len(aggs), len(trades), len(aggs) / len(trades) * 100))
    print("  => rows NEVER attempted: %d (%.1f%%)"
          % (len(trades) - len(aggs), (len(trades) - len(aggs)) / len(trades) * 100))
    # how many rows are outside a rolling 2-year lookback from the build date?
    cutoff = "2024-09-06"   # meta.built_at 2026-09-06 minus 2 years
    old = [t for t in trades if t["day"] < cutoff]
    print("  rows older than a rolling 2y lookback (%s): %d (%.1f%%) -- the report's"
          % (cutoff, len(old), len(old) / len(trades) * 100))
    print("     stated cause (a) can account for at most this many missing rows")
    days = sorted({t["day"] for t in trades})
    print("  book window: %s .. %s" % (days[0], days[-1]))
    # spread of the 20 real rows across the window
    realdays = sorted(t["day"] for t in trades if t["options"]["instrument_source"] == "real")
    print("  real rows span %s .. %s (%d rows) -- consistent with a shuffled prefix, not a date cut"
          % (realdays[0], realdays[-1], len(realdays)))


def section_g(trades):
    print("\n== G. option commission asymmetry ==")
    has_comm = sum(1 for t in trades if "commission" in t["options"])
    print("  option rows carrying a commission field: %d of %d" % (has_comm, len(trades)))
    ctr = sum(t["options"]["contracts"] for t in trades)
    days_all = len({t["day"] for t in trades})
    for rate in (0.65, 1.00):
        cost = ctr * 2 * rate
        print("  at $%.2f/contract/side a round trip on %d contracts costs $%s = $%.2f/day"
              % (rate, ctr, format(cost, ",.0f"), cost / days_all))
    print("  the futures column IS charged $0.62/side; the options column is charged none.")
    # real rows also pay no spread
    real = [t for t in trades if t["options"]["instrument_source"] == "real"]
    print("  real option rows carrying a spread_cost field: %d of %d"
          % (sum(1 for t in real if "spread_cost" in t["options"]), len(real)))


def section_i(trades):
    """What is actually IN the options headline."""
    print("\n== I. the options headline, decomposed ==")
    days = len({t["day"] for t in trades})
    sh = sum(t["shares"]["pnl"] for t in trades)
    op = sum(t["options"]["pnl"] for t in trades)
    spread = sum(t["options"].get("spread_cost", 0.0) for t in trades)
    model = [t for t in trades if t["options"]["instrument_source"] == "model"]
    real = [t for t in trades if t["options"]["instrument_source"] == "real"]
    sizing = sum(t["r"] * (t["options"]["actual_r_dollars"] - RISK) for t in model)
    realgap = sum(t["options"]["pnl"] - (t["r"] * t["options"]["actual_r_dollars"]) for t in real)
    print("  shares total  $%s = $%.2f/day" % (format(sh, ",.0f"), sh / days))
    print("  options total $%s = $%.2f/day" % (format(op, ",.0f"), op / days))
    print("  difference    $%s = $%.2f/day, of which:" % (format(op - sh, ",.0f"), (op - sh) / days))
    print("    the flat $0.05 spread on model rows  $%s = $%.2f/day  (%.0f%% of the gap)"
          % (format(-spread, ",.0f"), -spread / days, spread / abs(op - sh) * 100))
    print("    delta-sizing residual on model rows  $%s = $%.2f/day"
          % (format(sizing, ",.0f"), sizing / days))
    print("    the 20 real bars vs their linear R    $%s = $%.2f/day"
          % (format(realgap, ",.0f"), realgap / days))
    print("  SPREAD SENSITIVITY (model rows only; real rows keep their real prices):")
    mc = sum(t["options"]["contracts"] for t in model)
    for w in (0.00, 0.01, 0.02, 0.05, 0.10, 0.20):
        tot = op + spread - w * 100 * mc
        bym = defaultdict(float)
        for t in trades:
            adj = t["options"]["pnl"]
            if t["options"]["instrument_source"] == "model":
                adj = t["options"]["pnl"] + t["options"]["spread_cost"] - w * 100 * t["options"]["contracts"]
            bym[t["day"][:7]] += adj
        print("    width $%.2f -> $%7.2f/day, green %d/%d" %
              (w, tot / days, sum(1 for v in bym.values() if v > 0), len(bym)))
    print("  model contracts total = %s ; every $0.01 of assumed width = $%.2f/day"
          % (format(mc, ","), 0.01 * 100 * mc / days))
    print("  no Polygon QUOTE data was pulled anywhere in this row: the width is an assumption,")
    print("  and the 20 rows priced from real trades are the only rows exempt from it.")
    # max loss per row
    worst_opt = min(t["options"]["pnl"] / t["options"]["actual_r_dollars"] for t in trades)
    worst_real = min((t["options"]["pnl"] / t["options"]["actual_r_dollars"] for t in real), default=None)
    n_below = sum(1 for t in trades if t["options"]["pnl"] / t["options"]["actual_r_dollars"] < -1.0)
    print("  worst option row = %.3fR (real rows worst %.3fR); rows below -1.000R: %d of %d"
          % (worst_opt, worst_real, n_below, len(trades)))


def section_h(trades, n=10):
    """Live re-price: refetch aggs straight from Polygon, bypassing the cache."""
    print("\n== H. live re-price of real option rows (cache bypassed) ==")
    from research.g73_polygon_fetch import _get
    import datetime as dt
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    real = [t for t in trades if t["options"]["instrument_source"] == "real"]
    real.sort(key=lambda t: t["day"], reverse=True)   # newest first: inside the lookback
    picked = real[:n]
    npass = nfail = nerr = 0
    for t in picked:
        o = t["options"]
        tk, day = o["contract"], t["day"]
        j = _get("/v2/aggs/ticker/%s/range/1/minute/%s/%s" % (tk, day, day),
                 adjusted="true", sort="asc", limit=50000)
        if "_status" in j:
            print("  %-6s %s %s %-28s FETCH ERROR %s" % (t["sym"], day, t["et"], tk, j["_status"]))
            nerr += 1
            continue
        bars = {}
        for b in (j.get("results") or []):
            ts = dt.datetime.fromtimestamp(b["t"] / 1000, tz=dt.timezone.utc).astimezone(ET)
            bars[ts.strftime("%H:%M")] = b["c"]

        def near(hhmm):
            if hhmm in bars:
                return bars[hhmm]
            h, m = int(hhmm[:2]), int(hhmm[3:])
            tot = h * 60 + m
            best, bd = None, 6
            for k, v in bars.items():
                d = abs(int(k[:2]) * 60 + int(k[3:]) - tot)
                if d < bd:
                    bd, best = d, v
            return best
        h, m = int(t["et"][:2]), int(t["et"][3:])
        tot = h * 60 + m + int(t.get("bars", 1) or 1)
        ex = "%02d:%02d" % (tot // 60, tot % 60)
        e2, x2 = near(t["et"]), near(ex)
        okp = (e2 == o["entry_opt"] and x2 == o["exit_opt"])
        pnl2 = None if e2 is None or x2 is None else round((x2 - e2) * 100 * o["contracts"], 2)
        print("  %-6s %s %s %-28s stored %.2f/%.2f pnl %s | fresh %s/%s pnl %s -- %s"
              % (t["sym"], day, t["et"], tk, o["entry_opt"], o["exit_opt"], o["pnl"],
                 e2, x2, pnl2, "PASS" if okp else "MISMATCH"))
        if okp:
            npass += 1
        else:
            nfail += 1
    print("  %d pass, %d mismatch, %d fetch error, of %d" % (npass, nfail, nerr, len(picked)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", action="store_true")
    ap.add_argument("--n", type=int, default=10)
    a = ap.parse_args()
    meta, trades = load()
    print("book=%s rows=%d book_id=%s stamp_commit=%s dirty_py=%s"
          % (BOOK.name, len(trades), meta["book_id"], meta["git"]["commit"][:8],
             meta["git"].get("dirty_py_count")))
    section_a(trades)
    section_b(trades)
    section_c(trades)
    section_d(trades)
    section_e(trades)
    section_f(trades)
    section_g(trades)
    section_i(trades)
    if a.refetch:
        section_h(trades, a.n)


if __name__ == "__main__":
    main()
