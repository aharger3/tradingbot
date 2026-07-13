"""C8 — two-consecutive-losses = quit day: 12mo A/B (SIMULATION, no bot edits).

Rulebook hard rule "2 consecutive losses = quit day" is checked against the
config's current loss-halt. They are the SAME rule (see report), so per the
task we instead run a sensitivity A/B: no-halt / halt-at-1 / halt-at-2.

Halt semantics mirror live (omen_bot.TradingSession): walk each day's trades
in chronological order; consecutive_losses resets to 0 on a win, +1 on a loss;
once it reaches N the session stops taking trades for the rest of that day.

Two populations (both from research/c1_off_charts.json = clean 12mo baseline,
671 traded / 866 signals):
  - full-pop: all A+/A/B (alert_only=False) trades, one shared session across
    symbols per day (matches live scanner: consecutive_losses is portfolio-wide)
  - tier: S>=4 + hammer, max 2/day, stop-when-green (the c3/c6/c7 tier_sim),
    with the halt governor layered on top.

Usage: py -3.13 research/c8_loss_halt.py
"""
import json, re
from collections import defaultdict

CHARTS = "research/c1_off_charts.json"


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


def _t(rec):
    return rec["candles"][rec["entry_i"]]["t"]


def replay_fullpop(recs, halt_n):
    """One shared session per day across all symbols, chronological by entry
    time. halt_n=0 means no halt (take everything). Returns (n, wins, pnl)."""
    byday = defaultdict(list)
    for r in recs:
        if not r["alert_only"]:
            byday[r["day"]].append(r)
    n = w = 0; pnl = 0.0
    for day, rs in byday.items():
        rs.sort(key=_t)
        consec = 0
        for r in rs:
            if halt_n and consec >= halt_n:
                break
            n += 1; pnl += r["pnl"]
            if r["outcome"] == "win":
                w += 1; consec = 0
            else:
                consec += 1
    wr = w / n * 100 if n else 0.0
    return n, w, n - w, pnl, wr


def replay_tier(recs, halt_n, min_s=4, max_n=2):
    """S>=4+hammer tier, max 2/day, stop-when-green, + halt governor.
    halt_n=0 = no halt (current tier baseline). Returns (n, wins, pnl)."""
    recs = [r for r in recs if not r["alert_only"]]
    byday = defaultdict(list)
    for r in recs:
        byday[r["day"]].append(r)
    n = w = 0; pnl = 0.0
    for day, rs in byday.items():
        rs.sort(key=_t)
        taken = pnl_day = 0; consec = 0
        for r in rs:
            if taken >= max_n or pnl_day > 0:
                break
            if halt_n and consec >= halt_n:
                break
            s = s_score(r)
            if s is None or s < min_s or not is_hammer(r):
                continue
            taken += 1; n += 1; pnl_day += r["pnl"]; pnl += r["pnl"]
            if r["outcome"] == "win":
                w += 1; consec = 0
            else:
                consec += 1
    wr = w / n * 100 if n else 0.0
    return n, w, n - w, pnl, wr


def row(label, n, w, l, pnl, wr):
    return (label, n, wr, pnl)


def main():
    recs = load_all(CHARTS)
    # sanity: raw counts
    raw = [r for r in recs if not r["alert_only"]]
    print("# C8 — loss-halt sensitivity (12mo sim, research/c1_off_charts.json)")
    print(f"# Raw baseline: {len(raw)} traded (A+/A/B), "
          f"{len(recs)} signals incl alert-only\n")

    variants = [("no-halt (raw)", 0), ("halt-at-1", 1), ("halt-at-2", 2)]

    print("## Full-pop — loss-halt governor (one shared session/day)")
    print(f"{'variant':18} {'tr/yr':>6} {'win%':>6} {'$/yr':>10}")
    fp_rows = []
    for label, h in variants:
        n, w, l, pnl, wr = replay_fullpop(recs, h)
        fp_rows.append(row(label, n, w, l, pnl, wr))
        print(f"{label:18} {n:>6} {wr:>5.1f}% ${pnl:>9,.0f}")
    print(f"{'(note)':18} halt-at-2 == config consecutive_loss_halt:2 == rulebook hard rule\n")

    print("## Tier (S>=4+[hammer], max 2/day, stop-when-green) + halt governor")
    print(f"{'variant':18} {'tr/yr':>6} {'win%':>6} {'$/yr':>10}")
    t_rows = []
    for label, h in variants:
        n, w, l, pnl, wr = replay_tier(recs, h)
        t_rows.append(row("tier " + label, n, w, l, pnl, wr))
        print(f"{'tier '+label:18} {n:>6} {wr:>5.1f}% ${pnl:>9,.0f}")
    print(f"{'(note)':18} tier max-2/day makes halt-at-2 a no-op (2 losses = cap hit)\n")

    # verdict
    print("## Verdict")
    base_fp = fp_rows[0]
    best_fp = max(fp_rows, key=lambda r: r[3])
    print(f"full-pop best $/yr: {best_fp[0]} {best_fp[1]} tr {best_fp[2]:.1f}%W "
          f"${best_fp[3]:,.0f} (base {base_fp[0]} {base_fp[1]} tr "
          f"{base_fp[2]:.1f}%W ${base_fp[3]:,.0f})")
    base_t = t_rows[0]
    best_t = max(t_rows, key=lambda r: r[3])
    print(f"tier    best $/yr: {best_t[0]} {best_t[1]} tr {best_t[2]:.1f}%W "
          f"${best_t[3]:,.0f} (base {base_t[0]} {base_t[1]} tr "
          f"{base_t[2]:.1f}%W ${base_t[3]:,.0f})")


if __name__ == "__main__":
    main()
