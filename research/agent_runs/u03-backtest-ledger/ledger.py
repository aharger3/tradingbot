"""u03 ledger: uniform re-read of every stamped book under research/ (no engine code changed)."""
import sys, gzip, json, glob, os, random, statistics as st
from collections import defaultdict
ROOT = r"C:\Users\aharg\Desktop\Projects\tradingbot"
sys.path.insert(0, ROOT); os.chdir(ROOT)
from research.loop_cycle import apply_universe_filter, compute_all, load_book_any
CFG = json.load(open("research/tape/loop.json", encoding="utf-8"))
CORE = set(CFG["universe"]["symbols"])
base = json.load(gzip.open("research/tape/baseline_2026-09-13.json.gz"))
ALLDAYS = sorted({t["day"] for t in base["trades"]})

def days_in(a, b):
    return [d for d in ALLDAYS if a <= d <= b]

def stats(rows, a, b, risk_key=True):
    days = days_in(a, b)
    n = len(days) or 1
    daily = defaultdict(float); mon = defaultdict(float); fr = defaultdict(float)
    for t in rows:
        daily[t["day"]] += t["pnl"]; mon[t["day"][:7]] += t["pnl"]
        rk = abs(t.get("entry", 0) - t.get("stop", 0))
        # friction: 1c/share each side slippage on $1000 risk -> 20/rk dollars; cap at 1000
        fr[t["day"]] += min(1000.0, 20.0 / rk) if rk > 0 else 1000.0
    tot = sum(daily.values()); ftot = sum(fr.values())
    mons = sorted({d[:7] for d in days})
    net_mon = defaultdict(float)
    for d, v in daily.items(): net_mon[d[:7]] += v - fr[d]
    half = "2025-09-01"
    h1 = [d for d in days if d < half]; h2 = [d for d in days if d >= half]
    def pd(ds, net=False): return round(sum(daily.get(d, 0) - (fr.get(d, 0) if net else 0) for d in ds) / max(1, len(ds)))
    # day-shuffle / sign-flip: P(random sign daily net PnL >= observed)
    vec = [daily.get(d, 0) - fr.get(d, 0) for d in days]
    obs = sum(vec); rng = random.Random(7); ge = 0
    for _ in range(2000):
        if sum(v if rng.random() < .5 else -v for v in vec) >= obs: ge += 1
    wins = sum(1 for t in rows if t["pnl"] > 0)
    return dict(trades=len(rows), sessions=n, per_day=round(tot / n), net_per_day=round((tot - ftot) / n),
                win=round(100 * wins / max(1, len(rows)), 1), green=f"{sum(1 for m in mons if mon[m] > 0)}/{len(mons)}",
                net_green=f"{sum(1 for m in mons if net_mon[m] > 0)}/{len(mons)}",
                h1=pd(h1), h2=pd(h2), h1n=pd(h1, 1), h2n=pd(h2, 1), p_signflip=round(ge / 2000, 3),
                fric_per_trade=round(ftot / max(1, len(rows))))

out = []
for f in sorted(glob.glob("research/**/*.json.gz", recursive=True)):
    if "agent_runs" in f or "worktrees" in f: continue
    d = json.load(gzip.open(f)); m = d.get("meta", {}); T = d.get("trades", [])
    flags = (m.get("stamp") or {}).get("flags", {})
    row = dict(file=f.replace("\\", "/"), generated=(m.get("generated") or (m.get("stamp") or {}).get("built_at") or "")[:10],
               commit=((m.get("stamp") or {}).get("git") or {}).get("commit", "")[:8],
               fill=m.get("entry_fill") or m.get("fill") or m.get("arm") or "", exit=m.get("exit_plan", ""),
               stop_on_close=flags.get("backtest_week.STOP_ON_CLOSE"), disaster=flags.get("backtest_week.DISASTER_STOP"),
               pool=m.get("pool", ""))
    try:
        if T and "traded" in T[0]:
            # engine book: loop unit (his day policy) on core-11, via repo's own compute_all
            meta, rows = load_book_any(f)
            core = apply_universe_filter(rows, CFG["universe"])
            figs = compute_all(meta, core, CFG["unit"], CFG["halves_boundary"])
            w = figs["whole"]
            row.update(loop_trades=w.get("trades"), loop_per_day=w.get("per_day"), loop_green=f'{w.get("months_green")}/{w.get("months")}',
                       loop_h1=figs["h1"].get("per_day"), loop_h2=figs["h2"].get("per_day"))
            from research.loop_cycle import up_to_3_rows
            sel = [t for t in up_to_3_rows(core)]
            a, b = meta.get("first"), meta.get("last")
            row.update(stats(sel, a, b))
        else:
            rows = [t for t in T if t.get("filled", True) and not t.get("unfilled", False) and "pnl" in t]
            w = m.get("window") or {}
            a = w.get("start") or min(t["day"] for t in rows); b = w.get("end") or max(t["day"] for t in rows)
            row.update(stats(rows, a, b))
    except Exception as e:
        row["err"] = repr(e)[:200]
    out.append(row); print(json.dumps(row), flush=True)
json.dump(out, open("research/agent_runs/u03-backtest-ledger/ledger.json", "w"), indent=1)
