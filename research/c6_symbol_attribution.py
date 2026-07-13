"""C6 — per-symbol tier attribution (S>=4+[hammer]).

Takes = trades the tier actually accepts (S>=4 + hammer entry, max 2/day,
stop-when-green), same sim as b4_analyze/c3_tag_split. Aggregates by symbol.

Tables:
  - tier-only per-symbol (sorted by P&L)
  - full-pop per-symbol for context
  - concentration: symbols carrying 80% of tier profit; net-negative in tier
  - proposed tier-specific symbol list (net-positive tier symbols; n<5 flagged
    "insufficient data", NOT dropped) + recomputed tier stats with that list

No config change, no new backtest. Reads research/c1_off_charts.json
(clean 12mo baseline, 671 traded / 9,423 signals incl alert-only).

Usage: py -3.13 research/c6_symbol_attribution.py
"""
import json, re, sys
from collections import defaultdict

CHARTS = "research/c1_off_charts.json"
SMALL_N = 5  # below this = insufficient data


def load_all(path):
    return json.load(open(path))


def s_score(rec):
    m = re.search(r" S(\d+)", rec["reason"])
    return int(m.group(1)) if m else None


def is_hammer(rec):
    c = rec["candles"][rec["entry_i"]]
    body = abs(c["c"] - c["o"]); rng = c["h"] - c["l"]
    if rng == 0:
        return False
    if rec["direction"] == "call":
        return min(c["o"], c["c"]) - c["l"] >= body and c["c"] >= c["l"] + 0.5 * rng
    return c["h"] - max(c["o"], c["c"]) >= body and c["c"] <= c["h"] - 0.5 * rng


def gstats(recs):
    counted = [r for r in recs if not r["alert_only"]]
    w = sum(1 for r in counted if r["outcome"] == "win")
    l = sum(1 for r in counted if r["outcome"] == "loss")
    pnl = sum(r["pnl"] for r in counted)
    wr = w / (w + l) * 100 if (w + l) else 0.0
    return len(counted), w, l, pnl, wr


def tier_sim(recs, min_s=4, max_n=2, allow=None):
    """S>=4+hammer tier, max 2/day, stop-when-green.

    allow = optional set of symbols permitted at the tier gate (proposed-list
    test). None = all symbols. Returns (n, wr, pnl, taken_records)."""
    recs = [r for r in recs if not r["alert_only"]]
    byday = defaultdict(list)
    for r in recs:
        byday[r["day"]].append(r)
    tot = w = n = 0
    taken = []
    for day, rs in byday.items():
        rs.sort(key=lambda r: r["candles"][r["entry_i"]]["t"])
        taken_n = pnl_day = 0
        for r in rs:
            if taken_n >= max_n or pnl_day > 0:
                break
            s = s_score(r)
            if s is None or s < min_s or not is_hammer(r):
                continue
            if allow is not None and r["symbol"] not in allow:
                continue
            taken_n += 1; n += 1; pnl_day += r["pnl"]; tot += r["pnl"]
            w += r["outcome"] == "win"
            taken.append(r)
    wr = w / n * 100 if n else 0.0
    return n, wr, tot, taken


def by_sym(recs):
    out = {}
    for r in recs:
        s = r["symbol"]
        out.setdefault(s, []).append(r)
    return out


def sym_row(sym, recs):
    w = sum(1 for r in recs if r["outcome"] == "win")
    l = sum(1 for r in recs if r["outcome"] == "loss")
    pnl = sum(r["pnl"] for r in recs)
    wr = w / (w + l) * 100 if (w + l) else 0.0
    return (sym, len(recs), w, l, wr, pnl)


def fmt_row(r, flag_small=False):
    sym, n, w, l, wr, pnl = r
    mark = "  *insufficient data*" if (flag_small and n < SMALL_N) else ""
    return f"{sym:6} {n:>5} {w:>4} {l:>4} {wr:>6.1f}% ${pnl:>9,.0f}{mark}"


def main():
    recs = load_all(CHARTS)
    n, w, l, pnl, wr = gstats(recs)
    n_sig = len(recs)
    print("# C6 — per-symbol tier attribution (S>=4+[hammer])")
    print(f"Baseline 12mo: {n} traded / {n_sig} signals incl alert-only  "
          f"{w}W {l}L {wr:.1f}%W ${pnl:,.0f}\n")

    # --- tier ---
    tn, twr, tpnl, taken = tier_sim(recs)
    print(f"## Tier (S>=4+[hammer], max 2/day, stop-green): "
          f"{tn} tr  {twr:.1f}%W  ${tpnl:,.0f}/yr (${tpnl/12:,.0f}/mo)\n")

    # --- tier per-symbol ---
    tsym = by_sym(taken)
    trows = [sym_row(s, rs) for s, rs in tsym.items()]
    trows.sort(key=lambda r: r[5], reverse=True)  # by P&L desc
    print("## Tier trades by symbol (sorted by P&L)")
    print(f"{'sym':6} {'tr':>5} {'W':>4} {'L':>4} {'win%':>7} {'P&L':>11}")
    for r in trows:
        print(fmt_row(r, flag_small=True))
    pos = [r for r in trows if r[5] > 0]
    neg = [r for r in trows if r[5] < 0]
    print(f"\ntier symbols: {len(trows)}  net-positive: {len(pos)}  "
          f"net-negative: {len(neg)}  net-zero: {len(trows)-len(pos)-len(neg)}\n")

    # --- full-pop per-symbol context ---
    traded = [r for r in recs if not r["alert_only"]]
    frows = [sym_row(s, rs) for s, rs in by_sym(traded).items()]
    frows.sort(key=lambda r: r[5], reverse=True)
    print("## Full-pop traded by symbol (context, sorted by P&L)")
    print(f"{'sym':6} {'tr':>5} {'W':>4} {'L':>4} {'win%':>7} {'P&L':>11}")
    for r in frows:
        print(fmt_row(r))

    # --- concentration: 80% of tier profit ---
    print("\n## Concentration — symbols carrying 80% of tier profit")
    tot_profit = sum(r[5] for r in pos)
    # walk down pos (already sorted desc by P&L), accumulate
    cum = 0; eighty = []
    for r in pos:
        cum += r[5]
        eighty.append(r)
        if tot_profit > 0 and cum >= 0.8 * tot_profit:
            break
    print(f"net-positive tier P&L total: ${tot_profit:,.0f}")
    print(f"symbols to reach 80% of that: {len(eighty)} / {len(pos)} positive symbols")
    for r in eighty:
        print(f"  {r[0]:6} {r[1]:>3} tr {r[4]:.1f}%W ${r[5]:>9,.0f}")
    print(f"\nnet-negative in tier ({len(neg)} symbols):")
    for r in neg:
        flag = " *insufficient data*" if r[1] < SMALL_N else ""
        print(f"  {r[0]:6} {r[1]:>3} tr {r[4]:.1f}%W ${r[5]:>9,.0f}{flag}")

    # --- proposed tier-specific symbol list ---
    print("\n## Proposed tier-specific symbol list")
    print(f"(net-positive tier symbols; n<{SMALL_N} flagged 'insufficient data', "
          f"NOT dropped on noise per task rules)")
    proposed = [r[0] for r in pos]
    proposed.sort()
    insuf = [r[0] for r in pos if r[1] < SMALL_N]
    print(f"  list ({len(proposed)}): {', '.join(proposed)}")
    if insuf:
        print(f"  insufficient-data flags ({len(insuf)}): {', '.join(insuf)}")

    # --- recompute tier stats with proposed list ---
    pn, pwr, ppnl, _ = tier_sim(recs, allow=set(proposed))
    print(f"\n## Tier stats with proposed symbol list as gate")
    print(f"  trades/yr: {pn}  win%: {pwr:.1f}  $/yr: ${ppnl:,.0f}  "
          f"(${ppnl/12:,.0f}/mo)")
    print(f"  vs current tier: {tn} tr {twr:.1f}%W ${tpnl:,.0f}/yr  "
          f"(Δ {pn-tn:+d} tr, {pwr-twr:+.1f}pp, ${ppnl-tpnl:+,.0f})")

    # --- verdict ---
    print("\n## Verdict")
    print(f"Tier profit concentrated in {len(eighty)} symbol(s) "
          f"({100*len(eighty)/max(len(pos),1):.0f}% of positive symbols carry 80% "
          f"of tier P&L). Net-negative tier symbols: {len(neg)}. "
          f"Restricting the tier gate to the {len(proposed)} net-positive symbols "
          f"moves tier to {pn} tr/yr {pwr:.1f}%W ${ppnl:,.0f}/yr "
          f"(vs {tn} tr {twr:.1f}%W ${tpnl:,.0f}/yr). "
          f"Small-sample symbols (n<{SMALL_N}) marked insufficient-data, not dropped. "
          f"PROPOSAL ONLY — no config change; C10 decides.")


if __name__ == "__main__":
    main()
