"""G7.2 / buffer_math -- does the 5% position-volume rule bind at $200k?

Trade The Pool: "The volume of any opening trades must not exceed 5% of the
trading volume in the previous one-minute candle for that instrument."
(tradethepool.com/program-terms/, retrieved 2026-08-29)

Shares needed = notional / entry price. Prior-minute volume is read from
data_archive/<SYM>/<DAY>.csv at the bar before entry_i (entry_i is minutes
after 09:30 ET; verified against the row's own `et` field).
"""
import csv, json, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
from g72_buffer_math import load_days, policy_days, P_GREEN3, ekey, walk  # noqa

meta, by_day = load_days()

# rebuild P4 keeping sym/day/entry_i
rows = []
for d in sorted(by_day):
    for x in walk(by_day[d], P_GREEN3):
        rows.append(x)
print("P4 trades:", len(rows))

vol_cache = {}


def prior_vol(sym, day, entry_i):
    key = (sym, day)
    if key not in vol_cache:
        p = ROOT / "data_archive" / sym / (day + ".csv")
        if not p.exists():
            vol_cache[key] = None
        else:
            m = {}
            for r in csv.DictReader(p.open()):
                t = r["Datetime"][11:16]
                m[t] = int(float(r["Volume"]))
            vol_cache[key] = m
    m = vol_cache[key]
    if m is None:
        return None
    mins = 9 * 60 + 30 + entry_i - 1          # the candle BEFORE entry
    return m.get("%02d:%02d" % (mins // 60, mins % 60))


res = defaultdict(lambda: [0, 0])
missing = 0
for x in rows:
    v = prior_vol(x["sym"], x["day"], x["entry_i"])
    if v is None or v == 0:
        missing += 1
        continue
    px = x["entry"]
    for bp in (50000, 100000, 200000, 450000):
        shares = bp / px
        res[bp][1] += 1
        if shares > 0.05 * v:
            res[bp][0] += 1

print("rows with no prior-minute volume:", missing)
print("\n  %-10s %10s %10s %8s" % ("BP", "blocked", "checked", "% blocked"))
out = {}
for bp in (50000, 100000, 200000, 450000):
    b, n = res[bp]
    print("  $%-9s %10d %10d %7.2f%%" % ("{:,}".format(bp), b, n, 100.0 * b / n))
    out[str(bp)] = dict(blocked=b, checked=n, pct=round(100.0 * b / n, 3))

# which symbols hurt at 200k
bysym = defaultdict(lambda: [0, 0])
for x in rows:
    v = prior_vol(x["sym"], x["day"], x["entry_i"])
    if not v:
        continue
    bysym[x["sym"]][1] += 1
    if 200000 / x["entry"] > 0.05 * v:
        bysym[x["sym"]][0] += 1
print("\n  worst symbols at $200k notional:")
for s, (b, n) in sorted(bysym.items(), key=lambda z: -z[1][0] / max(z[1][1], 1))[:10]:
    print("    %-6s %3d/%3d  %5.1f%%" % (s, b, n, 100.0 * b / n))
out["by_symbol_200k"] = {s: dict(blocked=b, n=n) for s, (b, n) in bysym.items()}
(ROOT / "research" / "_g72_volume_check.json").write_text(json.dumps(out, indent=1))
print("\nwrote research/_g72_volume_check.json")

# ---- what the 5% rule costs in DOLLARS: size down to the cap, don't skip ----
print("\n=== income with the 5%% volume cap applied as a SIZE cap ===")
print("  %-10s %12s %12s %10s" % ("BP", "net $/mo free", "net $/mo capped", "haircut"))
inc = {}
for bp in (50000, 100000, 200000):
    risk_cap = bp * 0.005
    free = capped = 0.0
    for x in rows:
        sp = x["stop_pct"] / 100.0
        v = prior_vol(x["sym"], x["day"], x["entry_i"]) or 0
        n_free = min(bp, risk_cap / sp) if sp > 0 else bp
        n_cap = min(n_free, 0.05 * v * x["entry"])
        for n, acc in ((n_free, "f"), (n_cap, "c")):
            shares = n / x["entry"]
            comm = 3.0 * max(0.75, 0.005 * shares / 3.0)
            pnl = x["r"] * n * sp - comm
            if acc == "f":
                free += pnl
            else:
                capped += pnl
    # 861 trades over 496 days -> per month of 21 days
    f_mo = free / 496.0 * 21.0 * 0.70
    c_mo = capped / 496.0 * 21.0 * 0.70
    print("  $%-9s %12s %12s %9.1f%%" % ("{:,}".format(bp),
          "${:,.0f}".format(f_mo), "${:,.0f}".format(c_mo),
          100.0 * (1 - c_mo / f_mo)))
    inc[str(bp)] = dict(free_net_mo=round(f_mo, 2), capped_net_mo=round(c_mo, 2))
out["income_with_volume_cap"] = inc
(ROOT / "research" / "_g72_volume_check.json").write_text(json.dumps(out, indent=1))
