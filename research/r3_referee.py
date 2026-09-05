"""R3 referee -- independent re-derivation of two things the R3 row claims:

1. The baseline's day-policy unit (up to 3 fired core-11 signals a day, stop
   after a win or the second loss), $/day, green months, avg win/loss, both
   halves -- re-derived off `research/tape/baseline_2026-09-05.json.gz` and
   its published-fill twin, with no import from `loop_cycle.py` or
   `g72_suppress_price.py`.
2. The causal sentence's substrate/ladder split (step 1 -> step 2 of the
   reconciliation ladder), re-derived off `reconcile_fwd_1_add_C_grades`,
   `r2ref_simd_next_open_blind2r_real_engine` and
   `reconcile_fwd_2_swap_exit_shipped_ladder`, with no import from
   `g211_reconcile_ladder.py` or `r2_referee_pass2.py`.

Run: `python research/r3_referee.py baseline` or
`python research/r3_referee.py ladder` (default: both).
"""
import gzip
import json
import sys
from collections import defaultdict

def load(path):
    with gzip.open(path, "rt") as fh:
        return json.load(fh)

def month_key(day):
    return day[:7]

def day_policy_trades(rows):
    """Up to 3 fired-and-traded (or halted) core signals per day, arrival
    order (et, sym), stop after the first win (pnl>0) or the second loss
    (pnl<0) -- matches loop_cycle.py::up_to_3_rows's definition, reimplemented
    independently (not imported) as a cross-check."""
    by_day = defaultdict(list)
    for r in rows:
        if r.get("tier") != "core":
            continue
        if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
            by_day[r["day"]].append(r)
    out = []
    for day, day_rows in by_day.items():
        day_rows = sorted(day_rows, key=lambda r: (r.get("et") or "", r.get("sym") or ""))
        losses = 0
        taken = []
        for r in day_rows:
            if len(taken) >= 3:
                break
            taken.append(r)
            pnl = r.get("pnl", 0.0)
            if pnl > 0:
                break
            if pnl < 0:
                losses += 1
                if losses >= 2:
                    break
        out.extend(taken)
    return out

def stats(rows, n_days):
    n = len(rows)
    if n == 0 or not n_days:
        return dict(n=0, win_rate=0, mean_r=0, avg_win=0, avg_loss=0,
                     total_pnl=0, per_day=0, green=0, total_months=0)
    wins = [r for r in rows if r.get("pnl", 0) > 0]
    losses = [r for r in rows if r.get("pnl", 0) < 0]
    win_rate = len(wins) / n * 100
    mean_r = sum(r["r"] for r in rows) / n
    avg_win = sum(r["pnl"] for r in wins) / len(wins) if wins else 0
    avg_loss = sum(r["pnl"] for r in losses) / len(losses) if losses else 0
    total_pnl = sum(r["pnl"] for r in rows)
    per_day = total_pnl / n_days
    months = defaultdict(float)
    for r in rows:
        months[month_key(r["day"])] += r.get("pnl", 0)
    green = sum(1 for v in months.values() if v > 0)
    total_months = len(months)
    return dict(n=n, win_rate=win_rate, mean_r=mean_r, avg_win=avg_win,
                avg_loss=avg_loss, total_pnl=total_pnl, per_day=per_day,
                green=green, total_months=total_months)

def halves(rows, split="2025-09-01"):
    h1 = [r for r in rows if r["day"] < split]
    h2 = [r for r in rows if r["day"] >= split]
    return h1, h2

def session_days(all_rows, split=None, side=None):
    """Distinct day values appearing anywhere in the (core-filtered) book,
    used to approximate a half's session count, matching loop_cycle.py's
    documented caveat."""
    days = sorted({r["day"] for r in all_rows if r.get("day")})
    if split is None:
        return len(days)
    if side == "h1":
        return sum(1 for d in days if d < split)
    return sum(1 for d in days if d >= split)

def run_baseline(book_path):
    d = load(book_path)
    rows = d["trades"]
    core_rows = [r for r in rows if r.get("tier") == "core"]
    dp = day_policy_trades(rows)
    n_days_whole = d["meta"].get("sessions") or session_days(core_rows)
    full = stats(dp, n_days_whole)
    h1, h2 = halves(dp)
    n1 = session_days(core_rows, split="2025-09-01", side="h1")
    n2 = session_days(core_rows, split="2025-09-01", side="h2")
    s1 = stats(h1, n1)
    s2 = stats(h2, n2)
    print("book:", book_path, "book meta signals:", d["meta"].get("signals"), "sessions:", d["meta"].get("sessions"))
    print("n_days whole/h1/h2:", n_days_whole, n1, n2)
    print("day-policy full:", full)
    print("day-policy H1:", s1)
    print("day-policy H2:", s2)


# ------------------------------------------------------------ ladder re-derive

def ladder_stats(trades, label, n_days=499):
    rows = [t for t in trades if t.get("r") is not None]
    n = len(rows)
    wins = [t for t in rows if t["r"] > 0]
    losses = [t for t in rows if t["r"] <= 0]
    win_rate = len(wins) / n * 100
    mean_r = sum(t["r"] for t in rows) / n
    avg_win = sum(t["r"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["r"] for t in losses) / len(losses) if losses else 0
    total_pnl = sum(t.get("pnl", t["r"] * 1000) for t in rows)
    per_day = total_pnl / n_days
    print(f"{label}: n={n} win={win_rate:.1f}% meanR={mean_r:.4f} "
          f"avgwin={avg_win:.4f} avgloss={avg_loss:.4f} per_day={per_day:.2f}")
    return per_day, win_rate, avg_win, avg_loss


def flag_diff(meta_a, meta_b):
    fa = meta_a["stamp"]["flags"]
    fb = meta_b["stamp"]["flags"]
    diffs = {}
    for k in sorted(set(fa) | set(fb)):
        if fa.get(k) != fb.get(k):
            diffs[k] = (fa.get(k), fb.get(k))
    return diffs


def run_ladder():
    d1 = load("research/tape/reconcile_fwd_1_add_C_grades.json.gz")
    dD = load("research/tape/r2ref_simd_next_open_blind2r_real_engine.json.gz")
    d2 = load("research/tape/reconcile_fwd_2_swap_exit_shipped_ladder.json.gz")

    print("--- flag diffs: fwd_1 vs SIM D (should be empty -- same flags, "
          "different simulation code: g90._walk vs backtest_week.simulate_day) ---")
    print(flag_diff(d1["meta"], dD["meta"]) or "(none)")
    print("--- flag diffs: SIM D vs fwd_2 (should be exactly SCALE_PLAN) ---")
    print(flag_diff(dD["meta"], d2["meta"]))

    pd1, w1, aw1, al1 = ladder_stats(d1["trades"], "fwd_1  lab: close-only stop, blind 2R")
    pdD, wD, awD, alD = ladder_stats(dD["trades"], "SIM D  real engine: 1R touch stop, blind 2R")
    pd2, w2, aw2, al2 = ladder_stats(d2["trades"], "fwd_2  real engine: 1R touch stop, shipped ladder")

    substrate = pdD - pd1
    ladder = pd2 - pdD
    total = pd2 - pd1
    print()
    print(f"substrate leg (fwd_1 -> SIM D): {substrate:.2f}/day  "
          f"({substrate/total*100:.1f}% of total)")
    print(f"ladder leg (SIM D -> fwd_2):    {ladder:.2f}/day  "
          f"({ladder/total*100:.1f}% of total)")
    print(f"total delta:                    {total:.2f}/day")
    print(f"win rate: fwd_1 {w1:.1f}% -> SIM D {wD:.1f}% "
          f"(the sentence's '38.8% -> 33.6%')")
    print(f"avg win/loss fwd_1 vs SIM D (should read ~unchanged): "
          f"{aw1:.4f}/{al1:.4f} vs {awD:.4f}/{alD:.4f}")

    print()
    print("Reverse-order note: a true reverse decomposition (apply the "
          "ladder to fwd_1's own substrate, then apply the substrate swap) "
          "needs a 4th simulation -- g90._walk plus the shipped scale-out "
          "ladder -- which does not exist in research/tape/. Not built here "
          "(a new simulation is a second change); flagged as untested, same "
          "as r2_referee_pass2.md's own declared limit on path-dependence.")

    print()
    for label, trades in (("fwd_1", d1["trades"]), ("SIM D", dD["trades"]), ("fwd_2", d2["trades"])):
        rows = [t for t in trades if t.get("r") is not None]
        h1 = [t for t in rows if t["day"] < "2025-09-01"]
        h2 = [t for t in rows if t["day"] >= "2025-09-01"]
        d1n = len({t["day"] for t in h1})
        d2n = len({t["day"] for t in h2})
        pd_h1 = sum(t.get("pnl", t["r"] * 1000) for t in h1) / d1n
        pd_h2 = sum(t.get("pnl", t["r"] * 1000) for t in h2) / d2n
        print(f"{label}: H1 n={len(h1)} days={d1n} per_day={pd_h1:.2f}   "
              f"H2 n={len(h2)} days={d2n} per_day={pd_h2:.2f}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"
    if mode in ("baseline", "both"):
        run_baseline("research/tape/baseline_2026-09-05.json.gz")
        print()
        run_baseline("research/tape/baseline_2026-09-05_published.json.gz")
    if mode in ("ladder", "both"):
        print()
        run_ladder()
