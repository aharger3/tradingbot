"""G7.2 (suppress) — price the suppression fix over the full two years.

THE BUG (board item #5, research/g71_board.md): backtest_week.simulate_day kept
one `seen` map of "this level just fired, ignore re-fires for 2 bars", and it
wrote that map from EVERY captured signal — including the ones the router had
just REJECTED (D-grade, tight stop, repeat entry, repeat idea, retired level).
A reject therefore silenced the real, tradeable setup one or two bars later on
the same level.

THE FIX: backtest_week.DEDUPE_FIRES_ONLY (default 1). Only a signal whose status
is "fired" may open or extend the window. DEDUPE_FIRES_ONLY=0 restores the old
behaviour, which is how this script builds the BEFORE book.

WHAT IT DOES: runs backtest_2y.py twice — once with the bug, once without —
into a scratch directory, then prices both on identical arithmetic:
dollars per trade, dollars per day under one-trade-a-day, win rate, months
green, weeks green, worst drawdown. Plus a split of the entries the fix ADDS,
so "we just doubled the bad trades" is a checkable claim and not a worry.

Usage:
    python research/g72_suppress_price.py                 # full run, ~10 min
    python research/g72_suppress_price.py --workdir DIR   # keep the two books
    python research/g72_suppress_price.py --skip-run      # re-price existing books

1R = $1,000 (CLAUDE.md). Writes research/g72_suppress_numbers.json.
"""
import argparse, json, os, random, subprocess, sys, tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RISK = 1000.0


# ---------------------------------------------------------------- build books

def build(out_path: Path, fires_only: bool) -> None:
    env = dict(os.environ)
    env["DEDUPE_FIRES_ONLY"] = "1" if fires_only else "0"
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, str(ROOT / "backtest_2y.py"), "--out", str(out_path)]
    print("  $ DEDUPE_FIRES_ONLY=%s python backtest_2y.py --out %s"
          % (env["DEDUPE_FIRES_ONLY"], out_path.name), flush=True)
    p = subprocess.run(cmd, cwd=str(ROOT), env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                       errors="replace")
    tail = [l for l in p.stdout.splitlines() if "apiKey" not in l][-3:]
    for l in tail:
        print("    " + l, flush=True)
    if p.returncode != 0:
        raise SystemExit("backtest_2y failed (exit %d)" % p.returncode)


# ------------------------------------------------------------------ arithmetic

def iso_week(day: str) -> str:
    y, w, _ = date.fromisoformat(day).isocalendar()
    return "%04d-W%02d" % (y, w)


def drawdown(seq) -> float:
    """Worst peak-to-trough of the cumulative dollar curve, in dollars."""
    cum = peak = 0.0
    worst = 0.0
    for pnl in seq:
        cum += pnl
        peak = max(peak, cum)
        worst = max(worst, peak - cum)
    return worst


def stats(rows, n_days: int) -> dict:
    """rows: chronological list of dicts with day/pnl. n_days: sessions in book."""
    if not rows:
        return {}
    pnls = [r["pnl"] for r in rows]
    wins = sum(1 for r in rows if r["pnl"] > 0)
    losses = sum(1 for r in rows if r["pnl"] < 0)
    total = sum(pnls)
    by_m, by_w, by_d = {}, {}, {}
    for r in rows:
        by_m[r["day"][:7]] = by_m.get(r["day"][:7], 0.0) + r["pnl"]
        by_w[iso_week(r["day"])] = by_w.get(iso_week(r["day"]), 0.0) + r["pnl"]
        by_d[r["day"]] = by_d.get(r["day"], 0.0) + r["pnl"]
    return {
        "trades": len(rows),
        "win_pct": round(wins / (wins + losses) * 100, 1) if wins + losses else 0.0,
        "total_dollars": round(total, 0),
        "per_trade": round(total / len(rows), 0),
        "mean_r": round(total / len(rows) / RISK, 4),
        "per_day": round(total / n_days, 0),
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "months": len(by_m),
        "weeks_green": sum(1 for v in by_w.values() if v > 0),
        "weeks": len(by_w),
        "green_days_pct": round(sum(1 for v in by_d.values() if v > 0) / len(by_d) * 100, 1),
        "days_traded": len(by_d),
        "worst_drawdown": round(drawdown(pnls), 0),
    }


def load(path: Path):
    b = json.load(open(path, encoding="utf-8"))
    return b["meta"], b["trades"]


def ekey(r):
    return (r["day"], r["et"], r["sym"])


def shipped_rows(rows):
    """The book as shipped: every row the engine actually traded, in time order."""
    out = [r for r in rows if r.get("traded")]
    out.sort(key=ekey)
    return out


def oneaday_rows(rows):
    """One trade a day: the FIRST candidate of each day, then done.

    Candidate stream is g71_board_check.py's: fired-and-traded, plus the rows
    R31's account-wide two-loss halt blocked — under one-a-day the halt cannot
    have fired yet, so those days are live again.
    """
    byday = {}
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            byday.setdefault(r["day"], []).append(r)
    return [sorted(v, key=ekey)[0] for _, v in sorted(byday.items())]


def idkey(r):
    """Identity of a trade across the two books."""
    return (r["sym"], r["day"], r["et"], round(r["entry"], 2), round(r["stop"], 2),
            r["dir"], r["setup"])


# ----------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workdir", default=None,
                    help="where the two 60MB books go (default: system temp)")
    ap.add_argument("--skip-run", action="store_true",
                    help="re-price books already in --workdir")
    args = ap.parse_args()

    wd = Path(args.workdir) if args.workdir else Path(tempfile.gettempdir()) / "g72_suppress"
    wd.mkdir(parents=True, exist_ok=True)
    before_p, after_p = wd / "g72_book_before.json", wd / "g72_book_after.json"

    if not args.skip_run:
        print("BEFORE — the bug in place (a reject starts the window):", flush=True)
        build(before_p, fires_only=False)
        print("AFTER — only a fire starts the window:", flush=True)
        build(after_p, fires_only=True)

    mb, rb = load(before_p)
    ma, ra = load(after_p)
    nd_b, nd_a = mb["sessions"], ma["sessions"]

    out = {"before": {"meta": {k: mb[k] for k in
                               ("generated", "first", "last", "sessions", "signals",
                                "traded", "halted", "loss_halt")}},
           "after": {"meta": {k: ma[k] for k in
                              ("generated", "first", "last", "sessions", "signals",
                               "traded", "halted", "loss_halt")}}}

    for name, rows, nd in (("before", rb, nd_b), ("after", ra, nd_a)):
        out[name]["shipped"] = stats(shipped_rows(rows), nd)
        out[name]["one_a_day"] = stats(oneaday_rows(rows), nd)

    # what the fix ADDS, on its own — the "did we just double the bad trades" test
    old_ids = {idkey(r) for r in shipped_rows(rb)}
    new_only = [r for r in shipped_rows(ra) if idkey(r) not in old_ids]
    kept = [r for r in shipped_rows(ra) if idkey(r) in old_ids]
    lost = old_ids - {idkey(r) for r in shipped_rows(ra)}
    out["added_entries"] = stats(new_only, nd_a)
    out["surviving_entries"] = stats(kept, nd_a)
    out["entries_lost"] = len(lost)

    old_ids1 = {idkey(r) for r in oneaday_rows(rb)}
    new1 = [r for r in oneaday_rows(ra) if idkey(r) not in old_ids1]
    out["one_a_day_days_changed"] = len(new1)
    out["one_a_day_added"] = stats(new1, nd_a)

    # The standing method finding in DIRECTION.md: every A/B this project has run
    # moves less than its own error bar. So put one on this one. Paired by DAY --
    # the same 500 sessions, the difference in what the day earned -- resampled
    # 10,000 times. If the interval straddles zero, the per-trade edge did not
    # move and only the COUNT did, which is a different (and checkable) claim.
    out["error_bars"] = {}
    for policy, fn in (("shipped", shipped_rows), ("one_a_day", oneaday_rows)):
        db, da = {}, {}
        for r in fn(rb):
            db[r["day"]] = db.get(r["day"], 0.0) + r["pnl"]
        for r in fn(ra):
            da[r["day"]] = da.get(r["day"], 0.0) + r["pnl"]
        days = sorted(set(db) | set(da))
        diff = [da.get(d, 0.0) - db.get(d, 0.0) for d in days]
        rng = random.Random(20260829)
        n = len(diff)
        means = sorted(sum(rng.choices(diff, k=n)) / n for _ in range(10000))
        lo, hi = means[250], means[9750]
        out["error_bars"][policy] = {
            "days": n,
            "mean_daily_gain": round(sum(diff) / n, 0),
            "ci95_low": round(lo, 0), "ci95_high": round(hi, 0),
            "beats_its_own_error_bar": bool(lo > 0 or hi < 0),
        }

    (ROOT / "research" / "g72_suppress_numbers.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")

    # ---- print
    def row(label, b, a, fmt="%s", key=None):
        print("  %-22s %14s %14s" % (label, fmt % b[key], fmt % a[key]))

    for policy, title in (("shipped", "EVERY TRADE THE ENGINE TAKES"),
                          ("one_a_day", "ONE TRADE A DAY, FIRST SIGNAL")):
        b, a = out["before"][policy], out["after"][policy]
        print("\n== %s ==" % title)
        print("  %-22s %14s %14s" % ("", "BEFORE (bug)", "AFTER (fixed)"))
        for label, key, fmt in (
                ("trades", "trades", "%d"),
                ("win rate %", "win_pct", "%.1f"),
                ("$ per trade", "per_trade", "$%.0f"),
                ("$ per day", "per_day", "$%.0f"),
                ("$ total (2y)", "total_dollars", "$%.0f"),
                ("mean R", "mean_r", "%+0.4f"),
                ("months green", "months_green", "%d"),
                ("weeks green", "weeks_green", "%d"),
                ("green days %", "green_days_pct", "%.1f"),
                ("worst drawdown", "worst_drawdown", "$%.0f")):
            print("  %-22s %14s %14s" % (label, fmt % b[key], fmt % a[key]))
        print("  %-22s %14s %14s" % ("(months / weeks)",
                                     "%d / %d" % (b["months"], b["weeks"]),
                                     "%d / %d" % (a["months"], a["weeks"])))

    ae = out["added_entries"]
    print("\n== THE ENTRIES THE FIX UNLOCKS, ON THEIR OWN ==")
    print("  new entries        : %d" % ae.get("trades", 0))
    print("  win rate           : %.1f%%" % ae.get("win_pct", 0))
    print("  $ per trade        : $%.0f" % ae.get("per_trade", 0))
    print("  mean R             : %+0.4f" % ae.get("mean_r", 0))
    print("  entries lost       : %d" % out["entries_lost"])
    se = out["surviving_entries"]
    print("  old entries kept   : %d at $%.0f each (%.1f%% win)"
          % (se.get("trades", 0), se.get("per_trade", 0), se.get("win_pct", 0)))
    print("\n  one-a-day: %d of %d days now open on a DIFFERENT trade, "
          "worth $%.0f each" % (out["one_a_day_days_changed"],
                                out["after"]["one_a_day"]["trades"],
                                out["one_a_day_added"].get("per_trade", 0)))
    print("\n== IS IT BIGGER THAN ITS OWN ERROR BAR? (paired by day, 10k bootstrap) ==")
    for policy, e in out["error_bars"].items():
        print("  %-10s gain %s a day   95%% CI [%s, %s]   -> %s"
              % (policy,
                 "${:,.0f}".format(e["mean_daily_gain"]),
                 "${:,.0f}".format(e["ci95_low"]),
                 "${:,.0f}".format(e["ci95_high"]),
                 "REAL" if e["beats_its_own_error_bar"] else "inside the noise"))

    print("\nwrote research/g72_suppress_numbers.json")
    print("books: %s" % wd)


if __name__ == "__main__":
    main()
