"""g201 refuter #2 -- multiplicity and sampling-error attack on F9 (g158 mid-candle).

Lens: how many arms were tried, paired bootstrap over sessions, one-day
dominance, H1-used-to-select vs validate.

Re-runs g158's own loop (same book, same helpers, same size gate, same
one-trade-a-day unit) but keeps the PER-DAY picked row for every arm so the
comparison can be paired by session instead of read off two unpaired totals.
Adds one arm g158 does not have: MATCHED25 / MATCHED50 -- the MID arm
restricted to the SAME candidate CLOSE picked that day, which separates
"better entry price" from "the arm silently re-picked which trade the day
takes".

    python research/g201_refute2.py
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import g80_ordertype_grid as G   # noqa: E402
import signal_runner as sr                     # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades_retest_on.json"
OUT_JSON = ROOT / "research" / "g201_refute2.json"
RISK = 1000.0
SPLIT_DAY = "2025-09-01"
FRACS = (0.25, 0.50, 0.75)
ARM = {0.25: "MID25", 0.50: "MID50", 0.75: "MID75"}
SEED = 20260905
NBOOT = 20000


def half(d):
    return "H1" if d < SPLIT_DAY else "H2"


def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    meta, allrows = book["meta"], book["trades"]
    all_days = sorted({r["day"] for r in allrows})
    n_days = meta["sessions"]

    universe = {i: r for i, r in enumerate(allrows)
                if r.get("traded") or r["status"] == "halted"}
    keys = sorted(universe, key=lambda i: (allrows[i]["day"], allrows[i]["et"],
                                           allrows[i]["sym"], i))
    cand_by_day = defaultdict(list)
    for k in keys:
        cand_by_day[allrows[k]["day"]].append(k)
    for d in cand_by_day:
        cand_by_day[d].sort(key=lambda i: (allrows[i]["et"], allrows[i]["sym"], i))
    print("book %s: %d sessions, %d candidates" % (BOOK.name, n_days, len(keys)),
          flush=True)

    priced = {f: {} for f in FRACS}
    for n, k in enumerate(keys):
        if n and n % 2000 == 0:
            print("   %d / %d" % (n, len(keys)), flush=True)
        r = universe[k]
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        i = r["entry_i"]
        if not bars or i >= len(bars):
            continue
        rng = bars[i].high - bars[i].low
        cutoff = G.cutoff_idx(bars)
        if rng <= 0 or i + 1 >= min(cutoff, len(bars) - 1):
            continue
        long = r["dir"] == "call"
        ec = r["entry"]
        for f in FRACS:
            px = ec - f * rng if long else ec + f * rng
            j, fillpx = G.limit_touch(bars, px, long, i + 1, cutoff)
            if j is None or j >= len(bars) - 1:
                continue
            res = G.run_trade(r, bars, j, fillpx, pdh, pdl, pmh, pml,
                              move_stop_to_entry_bar=True)
            if res is not None:
                priced[f][k] = res

    def sizeable(res):
        if "sizeable" in res:
            return res["sizeable"]
        return (abs(res["entry"] - res["stop"]) >=
                sr.min_risk_floor(res.get("close", res["entry"])))

    def pick_by_day(rows_by_key):
        out = {}
        for d in sorted(cand_by_day):
            for k in cand_by_day[d]:
                res = rows_by_key.get(k)
                if res is None:
                    continue
                if sizeable(res):
                    out[d] = (k, res)
                    break
        return out

    close_rows = {k: universe[k] for k in keys}
    pick = {"CLOSE": pick_by_day(close_rows)}
    for f in FRACS:
        pick[ARM[f]] = pick_by_day(priced[f])

    for f, nm in ((0.25, "MATCHED25"), (0.50, "MATCHED50")):
        m = {}
        for d, kv in pick["CLOSE"].items():
            res = priced[f].get(kv[0])
            if res is not None and sizeable(res):
                m[d] = (kv[0], res)
        pick[nm] = m

    daily = {name: {d: v[1]["pnl"] for d, v in p.items()}
             for name, p in pick.items()}

    repick = Counter()
    for d, kv in pick["MID25"].items():
        if d in pick["CLOSE"]:
            repick["same" if pick["CLOSE"][d][0] == kv[0] else "different"] += 1
    print("MID25 day-pick vs CLOSE day-pick:", dict(repick), flush=True)

    rng_ = random.Random(SEED)

    def summary(name, days=None):
        dd = daily[name]
        ds = [d for d in all_days if (days is None or days(d))]
        tot = sum(dd.get(d, 0.0) for d in ds)
        return {"days_traded": sum(1 for d in ds if d in dd),
                "total": round(tot, 0),
                "per_day": round(tot / len(ds), 1),
                "n_sessions": len(ds)}

    def paired_boot(a, b, days=None):
        ds = [d for d in all_days if (days is None or days(d))]
        diffs = [daily[a].get(d, 0.0) - daily[b].get(d, 0.0) for d in ds]
        n = len(diffs)
        obs = sum(diffs) / n
        reps = []
        for _ in range(NBOOT):
            s = 0.0
            for _ in range(n):
                s += diffs[rng_.randrange(n)]
            reps.append(s / n)
        reps.sort()
        return {"obs_per_day": round(obs, 1),
                "ci_lo": round(reps[int(0.025 * NBOOT)], 1),
                "ci_hi": round(reps[int(0.975 * NBOOT)], 1),
                "boot_frac_le_zero": round(
                    sum(1 for x in reps if x <= 0) / NBOOT, 4),
                "n_sessions": n}

    def dominance(a, b, days=None):
        ds = [d for d in all_days if (days is None or days(d))]
        diffs = sorted(((daily[a].get(d, 0.0) - daily[b].get(d, 0.0), d)
                        for d in ds), reverse=True)
        tot = sum(x for x, _ in diffs)
        top, run = [], 0.0
        for x, d in diffs[:10]:
            run += x
            top.append({"day": d, "diff": round(x, 0),
                        "share_of_total_gap": round(x / tot * 100, 1) if tot else None,
                        "cum_share": round(run / tot * 100, 1) if tot else None})
        best_d = diffs[0][1] if diffs else None
        rest = [x for x, d in diffs if d != best_d]
        return {"total_gap": round(tot, 0), "top10": top,
                "per_day_ex_best": round(sum(rest) / len(ds), 1) if ds else None,
                "n_positive_days": sum(1 for x, _ in diffs if x > 0),
                "n_negative_days": sum(1 for x, _ in diffs if x < 0),
                "n_zero_days": sum(1 for x, _ in diffs if x == 0)}

    res = {"book": BOOK.name, "sessions": n_days, "seed": SEED, "nboot": NBOOT,
           "repick": dict(repick), "summaries": {}, "paired": {}, "dominance": {}}

    names = ("CLOSE", "MID25", "MID50", "MID75", "MATCHED25", "MATCHED50")
    for name in names:
        res["summaries"][name] = {
            "ALL": summary(name),
            "H1": summary(name, lambda d: half(d) == "H1"),
            "H2": summary(name, lambda d: half(d) == "H2")}
        s = res["summaries"][name]
        print("  %-10s ALL $%7.1f/day (%d/%d days)  H1 $%7.1f  H2 $%7.1f"
              % (name, s["ALL"]["per_day"], s["ALL"]["days_traded"],
                 s["ALL"]["n_sessions"], s["H1"]["per_day"], s["H2"]["per_day"]),
              flush=True)

    for a in ("MID25", "MID50", "MID75", "MATCHED25", "MATCHED50"):
        res["paired"][a] = {
            "ALL": paired_boot(a, "CLOSE"),
            "H1": paired_boot(a, "CLOSE", lambda d: half(d) == "H1"),
            "H2": paired_boot(a, "CLOSE", lambda d: half(d) == "H2")}
        res["dominance"][a] = {
            "ALL": dominance(a, "CLOSE"),
            "H2": dominance(a, "CLOSE", lambda d: half(d) == "H2")}
        p = res["paired"][a]["ALL"]
        print("  paired %-10s vs CLOSE  ALL %+.1f/day  95pct CI [%+.1f, %+.1f]  "
              "P(diff<=0)=%.3f" % (a, p["obs_per_day"], p["ci_lo"], p["ci_hi"],
                                   p["boot_frac_le_zero"]), flush=True)

    h1_rank = sorted(("MID25", "MID50", "MID75"),
                     key=lambda a: -res["summaries"][a]["H1"]["per_day"])
    res["oos"] = {
        "best_on_H1": h1_rank[0],
        "H1_ranking": [(a, res["summaries"][a]["H1"]["per_day"]) for a in h1_rank],
        "its_H2_per_day": res["summaries"][h1_rank[0]]["H2"]["per_day"],
        "its_H2_paired_vs_close": res["paired"][h1_rank[0]]["H2"],
        "best_on_combined": max(("MID25", "MID50", "MID75"),
                                key=lambda a: res["summaries"][a]["ALL"]["per_day"]),
    }
    print("OOS: best on H1 =", res["oos"]["best_on_H1"],
          "-> its H2 $%.1f/day" % res["oos"]["its_H2_per_day"],
          "| best on combined =", res["oos"]["best_on_combined"], flush=True)

    ds = all_days
    D = {a: [daily[a].get(d, 0.0) - daily["CLOSE"].get(d, 0.0) for d in ds]
         for a in ("MID25", "MID50", "MID75")}
    obs_max = max(sum(D[a]) / len(ds) for a in D)
    nmax, reps_max = 0, []
    for _ in range(NBOOT):
        flips = [1.0 if rng_.random() < 0.5 else -1.0 for _ in ds]
        m = max(sum(v * f for v, f in zip(D[a], flips)) / len(ds) for a in D)
        reps_max.append(m)
        if m >= obs_max:
            nmax += 1
    reps_max.sort()
    res["maxof3_signflip"] = {
        "obs_max_per_day": round(obs_max, 1),
        "null_p_max_ge_obs": round(nmax / NBOOT, 4),
        "null_95th_pct_of_max": round(reps_max[int(0.95 * NBOOT)], 1),
        "null_median_of_max": round(reps_max[NBOOT // 2], 1),
    }
    print("max-of-3 sign-flip null: obs %+.1f/day, p=%.4f, null 95th %+.1f"
          % (obs_max, nmax / NBOOT, reps_max[int(0.95 * NBOOT)]), flush=True)

    diag = {}
    cr = [v[1] for v in pick["CLOSE"].values()]

    def mrisk(rows):
        xs = [abs(r["entry"] - r["stop"]) for r in rows]
        return round(sum(xs) / len(xs), 4) if xs else None

    for a in ("MID25", "MID50", "MID75"):
        rr = [v[1] for v in pick[a].values()]
        diag[a] = {"mean_risk_per_share": mrisk(rr),
                   "close_mean_risk_per_share": mrisk(cr),
                   "win_pct": round(sum(1 for r in rr if r["pnl"] > 0) /
                                    max(1, sum(1 for r in rr if r["pnl"] != 0)) * 100, 1)}
    res["risk_diag"] = diag
    print("risk diag:", json.dumps(diag), flush=True)

    res["daily_pnl"] = {n: {d: round(v, 2) for d, v in daily[n].items()}
                        for n in daily}
    json.dump(res, open(OUT_JSON, "w", encoding="utf-8"), indent=1)
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    main()
