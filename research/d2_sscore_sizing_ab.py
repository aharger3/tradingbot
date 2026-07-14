"""D2 — S-score-scaled sizing A/B (flat $1k vs S-scaled) over the frozen 12mo baseline.

Flag lives in backtest_week.py (SSCORE_SIZING, env OMEN_SSCORE_SIZING, default OFF):
  S=4 -> 1.0x, S=5 -> 1.25x, S>=6 -> 1.5x on $1k base; S<=4 / unscored -> 1.0x.

Backtest P&L is linear in risk dollars (SimTrade.pnl = R-multiple * risk_dollars),
and sizing changes NO signal detection or outcome and (for tier v2) NO selection
(green-stop off, max-2 is a count) -> both arms trade the identical set, only the
per-trade $ multiplier differs. So the scaled arm = flat_pnl * mult(S) trade-for-trade,
bit-identical to what a real `OMEN_SSCORE_SIZING=1` 12mo rerun would write. Computed
here over the frozen charts json (no network, no rate-limit risk per standing rule).

Populations (both on research/c1_off_charts.json, C10's frozen tier-v2 baseline):
  * full-pop  : all traded (non-alert) signals, 671
  * tier v2   : S>=4, skip-[chase], max 2/day, no-hammer, no stop-green, skip-news
                (C10 recommended config v2)

maxDD = day-level cumulative-equity peak-to-trough, computed per arm.

Usage: py -3.13 research/d2_sscore_sizing_ab.py
"""
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHARTS = ROOT / "research" / "c1_off_charts.json"
NEWS = set(json.loads((ROOT / "news_days.json").read_text())["news_days"])


def s_score(rec):
    m = re.search(r" S(\d+)", rec["reason"])
    return int(m.group(1)) if m else None


def mult(rec):
    """D2 S-score risk multiplier (mirrors backtest_week.sscore_mult)."""
    s = s_score(rec)
    if s is None:
        return 1.0
    if s >= 6:
        return 1.5
    if s == 5:
        return 1.25
    return 1.0


def maxdd(recs, scaled):
    """Day-level cumulative-equity peak-to-trough (<=0)."""
    bd = defaultdict(float)
    for r in recs:
        bd[r["day"]] += r["pnl"] * (mult(r) if scaled else 1.0)
    eq = peak = mdd = 0.0
    for d in sorted(bd):
        eq += bd[d]
        peak = max(peak, eq)
        mdd = min(mdd, eq - peak)
    return mdd


def arm_stats(recs, scaled):
    n = len(recs)
    w = sum(1 for r in recs if r["outcome"] == "win")
    l = sum(1 for r in recs if r["outcome"] == "loss")
    pnl = sum(r["pnl"] * (mult(r) if scaled else 1.0) for r in recs)
    wr = w / (w + l) * 100 if (w + l) else 0.0
    return n, w, l, wr, pnl, maxdd(recs, scaled)


def tier_v2(recs):
    """C10 recommended config v2: S>=4, skip-[chase], max 2/day, skip-news,
    no hammer req, no stop-green. Selection is size-invariant here (green-stop
    off, max_n is a count) so the taken set is identical across arms."""
    byday = defaultdict(list)
    for r in recs:
        byday[r["day"]].append(r)
    taken = []
    for day in sorted(byday):
        if day in NEWS:
            continue
        rs = sorted(byday[day], key=lambda r: r["candles"][r["entry_i"]]["t"])
        n = 0
        for r in rs:
            if n >= 2:
                break
            s = s_score(r)
            if s is None or s < 4:
                continue
            if "[chase]" in r["reason"]:
                continue
            n += 1
            taken.append(r)
    return taken


def row(label, st):
    n, w, l, wr, pnl, mdd = st
    return f"| {label} | {n} | {w} | {l} | {wr:.1f}% | ${pnl:,.0f} | ${mdd:,.0f} |"


def block(title, recs):
    flat = arm_stats(recs, scaled=False)
    scal = arm_stats(recs, scaled=True)
    d_pnl = scal[4] - flat[4]
    d_mdd = scal[5] - flat[5]
    pct = d_pnl / flat[4] * 100 if flat[4] else 0.0
    print(f"\n### {title}  (n={len(recs)})\n")
    print("| arm | n | W | L | win% | P&L | maxDD |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    print(row("A — flat $1k (flag OFF)", flat))
    print(row("B — S-scaled (flag ON)", scal))
    print(f"| **Δ (B − A)** | 0 | 0 | 0 | 0.0pp | **${d_pnl:+,.0f}** ({pct:+.1f}%) | **${d_mdd:+,.0f}** |")
    # $ / MAR-style return-to-pain
    for lbl, st in [("A flat", flat), ("B scaled", scal)]:
        mar = st[4] / abs(st[5]) if st[5] else float("inf")
        print(f"<!-- {lbl}: return/|maxDD| = {mar:.2f} -->")
    return flat, scal


def main():
    recs = [r for r in json.load(open(CHARTS)) if not r["alert_only"]]
    print("# D2 — S-score-scaled sizing A/B (12mo)\n")
    print(f"Baseline: `{CHARTS.name}` — {len(recs)} traded (non-alert). "
          "Multipliers: S=4→1.0x, S=5→1.25x, S≥6→1.5x, S≤4/unscored→1.0x.")

    # S-score coverage
    from collections import Counter
    dist = Counter(s_score(r) for r in recs)
    print("\n**S-score coverage (traded):** "
          + ", ".join(f"S{k}={dist[k]}" for k in sorted(x for x in dist if x is not None))
          + f", unscored={dist[None]}")

    block("Full population", recs)
    tk = tier_v2(recs)
    block("Tier v2 (S≥4, skip-[chase], max 2/day, skip-news)", tk)

    # Per-S-bucket: is the uplift accretive (higher-S = higher win%) or pure leverage?
    def bucket(s):
        if s is None or s < 4:
            return "S≤3/uns"
        return "S=4" if s == 4 else ("S=5" if s == 5 else "S≥6")
    for title, pop in [("Full population", recs), ("Tier v2", tk)]:
        print(f"\n### Per-S-score bucket — {title}\n")
        print("| bucket | mult | n | W | L | win% | flat P&L | scaled P&L |")
        print("|---|---:|---:|---:|---:|---:|---:|---:|")
        by = defaultdict(list)
        for r in pop:
            by[bucket(s_score(r))].append(r)
        for b, m in [("S≤3/uns", 1.0), ("S=4", 1.0), ("S=5", 1.25), ("S≥6", 1.5)]:
            rs = by.get(b, [])
            if not rs:
                continue
            w = sum(1 for r in rs if r["outcome"] == "win")
            l = sum(1 for r in rs if r["outcome"] == "loss")
            fp = sum(r["pnl"] for r in rs)
            sp = fp * m
            wr = w / (w + l) * 100 if (w + l) else 0.0
            print(f"| {b} | {m}x | {len(rs)} | {w} | {l} | {wr:.1f}% | ${fp:,.0f} | ${sp:,.0f} |")

    # scale-eligible share (S>=5) — where the two arms actually diverge
    fe = sum(1 for r in recs if (s_score(r) or 0) >= 5)
    te = sum(1 for r in tk if (s_score(r) or 0) >= 5)
    print(f"\n<!-- scale-eligible (S>=5): full-pop {fe}/{len(recs)}, tier {te}/{len(tk)} -->")


if __name__ == "__main__":
    main()
