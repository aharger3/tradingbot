"""g71 levels ADVERSARIAL VERIFY: how load-bearing is the whole-dollar runner
target in backtest_week.simulate_day (lines 850-859)?

For every TRADED row of the 2-year replay, recompute the runner-target candidate
set and record which candidate won min()/max(). No engine file is edited.
Usage: python research/g71_levels_verify_wholedollar.py [--days 730] [--syms N]
"""
import argparse, json, math, sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import polygon_feed as pf
from backtest_week import simulate_day, htf_bias_for, SCALE_PLAN
from backtest_12mo import hourly_from_1m
from universe import ALL_SYMS, has_archive

ROOT = Path(__file__).resolve().parent.parent


def archive_days(sym):
    d = ROOT / "data_archive" / sym
    return sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--syms", type=int, default=0)
    a = ap.parse_args()
    cutoff = (date.today() - timedelta(days=a.days)).isoformat()

    syms = [s for s in ALL_SYMS if has_archive(s)]
    if a.syms:
        syms = syms[:a.syms]
    print(f"SCALE_PLAN={SCALE_PLAN!r}  syms={len(syms)}", flush=True)

    win = Counter()          # which candidate set the runner target
    n_traded = n_scaleplan = 0
    dist = []                # runner_tgt - scale_level, in dollars
    r_by_src = {"whole": [], "pdh_pmh": []}

    for si, sym in enumerate(syms):
        days = [d for d in archive_days(sym) if d >= cutoff]
        day_bars, hourly = {}, []
        for d in days:
            try:
                bars = pf.fetch_day(sym, d)
            except Exception:
                continue
            if not bars:
                continue
            r = pf.rth(bars)
            if len(r) < 30:
                continue
            day_bars[d] = (bars, r)
            hourly += hourly_from_1m(d, r)

        prev = None
        for d in sorted(day_bars):
            bars, rth = day_bars[d]
            if prev:
                _, prth = day_bars[prev]
                pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
                pdo, pdc = prth[0].open, prth[-1].close
            else:
                pdh = pdl = pdo = pdc = None
            pmh, pml = pf.premarket_hi_lo(bars)
            bias = htf_bias_for(hourly, d)
            trades = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml, pdo, pdc)
            prev = d
            for t in trades:
                if not t.counted:
                    continue
                n_traded += 1
                sl, rt = t.scale_level, t.runner_target
                if not sl or not rt:
                    continue
                n_scaleplan += 1
                if t.direction == "call":
                    whole = math.floor(sl) + 1.0
                    named = [x for x in (pdh, pmh) if x is not None and x > sl]
                else:
                    whole = math.ceil(sl) - 1.0
                    named = [x for x in (pdl, pml) if x is not None and x < sl]
                src = "whole" if abs(rt - whole) < 1e-9 else "pdh_pmh"
                if src == "pdh_pmh" and not named:
                    src = "other"
                win[src] += 1
                dist.append(abs(rt - sl))
                if src in r_by_src:
                    r_by_src[src].append(t.pnl / 1000.0)
        print(f"  [{si+1}/{len(syms)}] {sym} traded={n_traded}", flush=True)

    print("\n=== RESULT ===")
    print(f"traded rows            : {n_traded}")
    print(f"rows with a scale plan : {n_scaleplan}")
    for k, v in win.most_common():
        print(f"  runner target set by {k:9s}: {v}  ({100*v/max(1,n_scaleplan):.1f}%)")
    if dist:
        dist.sort()
        print(f"|runner_tgt - scale_level| median ${dist[len(dist)//2]:.3f}  "
              f"p90 ${dist[int(.9*len(dist))]:.3f}  max ${dist[-1]:.3f}")
    for k, v in r_by_src.items():
        if v:
            print(f"  mean R when target from {k:9s}: {sum(v)/len(v):+.4f}  n={len(v)}")
    json.dump({"n_traded": n_traded, "n_scaleplan": n_scaleplan,
               "win": dict(win)}, open(ROOT / "research/_g71_wholedollar.json", "w"), indent=1)


if __name__ == "__main__":
    main()
