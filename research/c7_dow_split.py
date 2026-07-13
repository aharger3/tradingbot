"""C7 — day-of-week split + Friday deep-dive.

Per-weekday trades / win% / P&L on research/c1_off_charts.json (clean 12mo
baseline, 671 traded / 866 signals). Full-pop AND tier (S>=4+[hammer], max
2/day, stop-when-green — same sim as b4_analyze/c3_tag_split/c6).

Friday deep-dive: is Friday materially worse/better? Within Friday, split by
entry time if sample allows.

Friday-next-week-contracts rule (rulebook hard rule): on Fridays, use next
week's expiry instead of same-day/this-week. options_sizer.py expiry
selection is READ-ONLY here — D1 (SCARFACE_CONTRACT A/B) has NOT run, so this
task DOCUMENTS the encoding only, encodes nothing.

Usage: py -3.13 research/c7_dow_split.py
"""
import json, re
from collections import defaultdict
from datetime import datetime

CHARTS = "research/c1_off_charts.json"
WDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]


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


def weekday(rec):
    """0=Mon..4=Fri from rec['day'] YYYY-MM-DD."""
    return datetime.strptime(rec["day"], "%Y-%m-%d").weekday()


def entry_time(rec):
    """HH:MM string from entry candle."""
    return rec["candles"][rec["entry_i"]]["t"]


def gstats(recs):
    counted = [r for r in recs if not r["alert_only"]]
    w = sum(1 for r in counted if r["outcome"] == "win")
    l = sum(1 for r in counted if r["outcome"] == "loss")
    pnl = sum(r["pnl"] for r in counted)
    wr = w / (w + l) * 100 if (w + l) else 0.0
    return len(counted), w, l, pnl, wr


def tier_sim(recs, min_s=4, max_n=2):
    """S>=4+hammer tier, max 2/day, stop-when-green. Returns (n, wr, pnl, taken)."""
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
            taken_n += 1; n += 1; pnl_day += r["pnl"]; tot += r["pnl"]
            w += r["outcome"] == "win"
            taken.append(r)
    wr = w / n * 100 if n else 0.0
    return n, wr, tot, taken


def row(recs):
    n, w, l, pnl, wr = gstats(recs)
    return n, w, l, wr, pnl


def main():
    recs = load_all(CHARTS)
    n, w, l, pnl, wr = gstats(recs)
    n_sig = len(recs)
    print("# C7 — day-of-week split + Friday deep-dive (12mo baseline)")
    print(f"Baseline: {n} traded / {n_sig} signals incl alert-only  "
          f"{w}W {l}L {wr:.1f}%W ${pnl:,.0f}\n")

    traded = [r for r in recs if not r["alert_only"]]

    # --- full-pop per weekday ---
    print("## Full-pop per weekday (traded A+/A/B only)")
    bywd = defaultdict(list)
    for r in traded:
        bywd[weekday(r)].append(r)
    print(f"{'day':4} {'tr':>5} {'W':>4} {'L':>4} {'win%':>6} {'P&L':>10} {'avgPnL':>8}")
    fp_rows = []
    for wd in range(5):
        sub = bywd.get(wd, [])
        n2, w2, l2, wr2, p2 = row(sub)
        avg = p2 / n2 if n2 else 0.0
        fp_rows.append((WDAYS[wd], n2, wr2, p2))
        print(f"{WDAYS[wd]:4} {n2:>5} {w2:>4} {l2:>4} {wr2:>5.1f}% ${p2:>9,.0f} ${avg:>7,.1f}")
    print(f"{'ALL':4} {n:>5} {w:>4} {l:>4} {wr:>5.1f}% ${pnl:>9,.0f}")

    # --- tier per weekday (split of tier-accepted trades) ---
    tn, twr, tpnl, taken = tier_sim(recs)
    print(f"\n## Tier (S>=4+[hammer], max 2/day, stop-green): "
          f"{tn} tr  {twr:.1f}%W  ${tpnl:,.0f}/yr\n")
    print("## Tier per weekday (split of trades the tier accepts)")
    tbywd = defaultdict(list)
    for r in taken:
        tbywd[weekday(r)].append(r)
    print(f"{'day':4} {'tr':>5} {'W':>4} {'L':>4} {'win%':>6} {'P&L':>10} {'%tier':>6}")
    t_rows = []
    for wd in range(5):
        sub = tbywd.get(wd, [])
        n2, w2, l2, wr2, p2 = row(sub)
        share = 100 * n2 / tn if tn else 0.0
        t_rows.append((WDAYS[wd], n2, wr2, p2))
        print(f"{WDAYS[wd]:4} {n2:>5} {w2:>4} {l2:>4} {wr2:>5.1f}% ${p2:>9,.0f} {share:>5.0f}%")

    # --- Friday deep-dive ---
    fri = bywd.get(4, [])
    print(f"\n## Friday deep-dive (full-pop, n={len(fri)})")
    n2, w2, l2, wr2, p2 = row(fri)
    print(f"Friday: {n2} tr {wr2:.1f}%W ${p2:,.0f}  (vs non-Fri "
          f"{n-n2} tr {(w-w2)/((w-w2)+(l-l2))*100 if (w-w2)+(l-l2) else 0:.1f}%W "
          f"${pnl-p2:,.0f})")
    # split by entry time bands
    print("\nFriday by entry-time band:")
    bands = [("pre-10:30", lambda t: t < "10:30"),
             ("10:30-11:30", lambda t: "10:30" <= t < "11:30"),
             ("11:30-13:00", lambda t: "11:30" <= t < "13:00"),
             ("13:00-14:30", lambda t: "13:00" <= t < "14:30"),
             ("14:30+", lambda t: t >= "14:30")]
    print(f"{'band':12} {'tr':>4} {'W':>3} {'L':>3} {'win%':>6} {'P&L':>9}")
    any_split = False
    for label, pred in bands:
        sub = [r for r in fri if pred(entry_time(r))]
        n3, w3, l3, wr3, p3 = row(sub)
        if n3:
            any_split = True
            print(f"{label:12} {n3:>4} {w3:>3} {l3:>3} {wr3:>5.1f}% ${p3:>8,.0f}")
    if not any_split:
        print("  (no Friday trades in these bands)")

    # Friday within tier
    tfri = tbywd.get(4, [])
    if tfri:
        n3, w3, l3, wr3, p3 = row(tfri)
        print(f"\nFriday within tier: {n3} tr {wr3:.1f}%W ${p3:,.0f} "
              f"(vs non-Fri tier {tn-n3} tr "
              f"{(sum(1 for r in taken if weekday(r)!=4 and r['outcome']=='win'))/max(tn-n3,1)*100:.1f}%W)")

    # --- Friday-next-week-contracts rule (DOCUMENT ONLY) ---
    print("\n## Friday-next-week-contracts rule (DOCUMENT ONLY — D1 not run)")
    print("""Rulebook hard rule: on Fridays, trade NEXT WEEK's expiry, not same-day /
this-week. Current expiry selection in options_sizer.py (READ-ONLY):
  - default (SCARFACE_CONTRACT=False): nearest_expiration() — 0DTE if before
    14:30 ET on a weekday, else next weekday. On a Friday <14:30 this returns
    TODAY (same-day 0DTE), the opposite of the rule.
  - SCARFACE_CONTRACT=True (D1, not yet measured): weekly_expiration() =
    nearest Friday; on a Friday it returns TODAY (this week's weekly = today),
    also NOT next-week.
Encoding it would require (do NOT encode now — D1 owns SCARFACE_CONTRACT):
  - In weekly_expiration(), if today.weekday()==4 (Fri), return today + 7d
    (next Friday) instead of today. One-line guard.
  - OR a separate FRIDAY_NEXT_WEEK flag layered on whichever path D1 lands,
    so the rule survives even if D1 keeps SCARFACE_CONTRACT=False (then it
    applies to nearest_expiration: on Friday shift to next weekday's weekly).
  - Live: only matters for symbols without daily expirations; TSLA/NVDA 0DTE
    same-day is the measured baseline. Premium/delta shift unmeasured → D1.""")

    # --- verdict ---
    print("\n## Verdict")
    best = max(fp_rows, key=lambda r: r[3])
    worst = min(fp_rows, key=lambda r: r[3])
    tbest = max(t_rows, key=lambda r: r[3])
    tworst = min(t_rows, key=lambda r: r[3])
    # materiality: Friday vs non-Friday (the rulebook's actual question)
    fri_pnl = fp_rows[4][3]; nonfri_pnl = sum(r[3] for r in fp_rows[:4])
    fri_n = fp_rows[4][1]; nonfri_n = sum(r[1] for r in fp_rows[:4])
    fri_avg = fri_pnl / fri_n if fri_n else 0
    nonfri_avg = nonfri_pnl / nonfri_n if nonfri_n else 0
    print(f"Full-pop best day: {best[0]} {best[1]} tr {best[2]:.1f}%W ${best[3]:,.0f}")
    print(f"Full-pop worst day: {worst[0]} {worst[1]} tr {worst[2]:.1f}%W ${worst[3]:,.0f}")
    print(f"Tier best day: {tbest[0]} {tbest[1]} tr {tbest[2]:.1f}%W ${tbest[3]:,.0f}")
    print(f"Tier worst day: {tworst[0]} {tworst[1]} tr {tworst[2]:.1f}%W ${tworst[3]:,.0f}")
    print(f"Friday avg $/trade ${fri_avg:,.0f} vs non-Fri ${nonfri_avg:,.0f} "
          f"(Δ ${fri_avg-nonfri_avg:+,.0f}/trade)")
    spread = best[3] - worst[3]
    print(f"Full-pop P&L spread best→worst weekday: ${spread:,.0f}")
    # Friday-specific edge (the rulebook question): avg-per-trade gap
    fri_gap = abs(fri_avg - nonfri_avg)
    # tier per-weekday n are 12-22 — overfit-prone (same caveat as C6's n<5 symbols)
    tier_min_n = min(r[1] for r in t_rows)
    print(f"\nFriday rulebook question: Friday is NOT materially worse — "
          f"avg ${fri_avg:,.0f}/trade vs ${nonfri_avg:,.0f} non-Fri "
          f"(Δ ${fri_avg-nonfri_avg:+,.0f}, {fri_gap<15 and 'within noise' or 'material'}). "
          f"Friday next-week-contract rule is a live-sizing/encoding concern for D1, "
          f"NOT a win-rate lever — no edge to flag there.")
    print(f"\nDay-of-week edge: Thu ${best[3]:,.0f} / Tue ${worst[3]:,.0f} spread is large "
          f"(${spread:,.0f}) but tier per-weekday n={tier_min_n}-22 is overfit-prone "
          f"(C6 precedent: n<5 flagged). Skip-Tuesday-at-tier would cut 14 tr −$2k; "
          f"skip-Thursday would forfeit 12 tr +$12k (66.7%W) — NOT a gate to ship blind.")
    print(f"\nC10 flag: WATCH only — no weekday gate to live config from this. If C10 "
          f"wants a weekday rule, walk-forward (F1) MUST validate Thu-good/Tue-bad "
          f"out-of-sample before trust; treat as same overfit risk class as C6's "
          f"per-symbol list.")


if __name__ == "__main__":
    main()
