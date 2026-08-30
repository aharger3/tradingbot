"""g85_verify_0.py — an INDEPENDENT recompute of the two headline money numbers
in research/g85_entry_fill.md, written by the verifying agent.

Imports nothing from research/g72_suppress_price.py on purpose: the point is to
re-derive the arithmetic from the books on disk rather than re-run the same
helper and call the agreement a check. 1R = $1,000. Austin's bar is $397/day.

    python research/g85_verify_0.py
"""
import json, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RISK = 1000.0
BAR = 397.0

CLOSE_BOOK = ROOT / "research" / "bt2y_trades.json"
PUB_BOOK = ROOT / "research" / "bt2y_trades_published_fill.json"


def price(rows, sessions):
    """My own arithmetic: dollars/day, win rate, mean R, green months."""
    pnl = [r["pnl"] for r in rows]
    w = sum(1 for p in pnl if p > 0)
    l = sum(1 for p in pnl if p < 0)
    tot = sum(pnl)
    months = {}
    for r in rows:
        months[r["day"][:7]] = months.get(r["day"][:7], 0.0) + r["pnl"]
    cum = peak = worst = 0.0
    for p in pnl:
        cum += p
        peak = max(peak, cum)
        worst = max(worst, peak - cum)
    return {
        "trades": len(rows),
        "win_pct": round(w / (w + l) * 100, 1) if w + l else 0.0,
        "per_trade": round(tot / len(rows), 0),
        "mean_r": round(tot / len(rows) / RISK, 3),
        "per_day": round(tot / sessions, 0),
        "months_green": sum(1 for v in months.values() if v > 0),
        "months": len(months),
        "worst_drawdown": round(worst, 0),
        "pct_of_bar": round(tot / sessions / BAR * 100, 1),
    }


def order(r):
    return (r["day"], r["et"], r["sym"])


def every_trade(rows):
    return sorted([r for r in rows if r.get("traded")], key=order)


def one_a_day(rows):
    """First candidate each day. A halted row is a candidate: under one-a-day
    the account-wide two-loss halt cannot have fired yet."""
    byday = {}
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            byday.setdefault(r["day"], []).append(r)
    return [sorted(v, key=order)[0] for _, v in sorted(byday.items())]


def one_a_day_strict(rows):
    """Sensitivity: first row the engine ACTUALLY traded each day, no halted rows."""
    byday = {}
    for r in rows:
        if r.get("traded"):
            byday.setdefault(r["day"], []).append(r)
    return [sorted(v, key=order)[0] for _, v in sorted(byday.items())]


def report(path, label):
    b = json.load(open(path, encoding="utf-8"))
    meta, rows = b["meta"], b["trades"]
    n = meta["sessions"]
    print("\n%s  (%s)" % (label, Path(path).name))
    print("  entry_fill=%s  sessions=%d  signals=%d  traded=%d"
          % (meta.get("entry_fill", "UNSTAMPED"), n, meta["signals"], meta["traded"]))
    out = {}
    for name, sel in (("every trade", every_trade),
                      ("one a day", one_a_day),
                      ("one a day (traded-only)", one_a_day_strict)):
        s = price(sel(rows), n)
        out[name] = s
        print("  %-24s $%s/day  %s%% of the $397 bar  %s%% win  mean R %s  "
              "%d/%d green months  n=%d  worst DD $%s"
              % (name, f"{s['per_day']:,.0f}", s["pct_of_bar"], s["win_pct"],
                 s["mean_r"], s["months_green"], s["months"], s["trades"],
                 f"{s['worst_drawdown']:,.0f}"))
    return meta, out


def main():
    close_meta, close = report(CLOSE_BOOK, "CLOSE FILL — the shipped default")
    pub = None
    if PUB_BOOK.exists():
        pub_meta, pub = report(PUB_BOOK, "PUBLISHED FILL — the old, unobtainable control")

    # The claims in research/g85_entry_fill.md, checked one at a time.
    claims = [
        ("close/one-a-day $/day", close["one a day"]["per_day"], 28),
        ("close/one-a-day win %", close["one a day"]["win_pct"], 45.5),
        ("close/one-a-day green months", close["one a day"]["months_green"], 11),
        ("close/every-trade $/day", close["every trade"]["per_day"], -283),
        ("close/every-trade per trade", close["every trade"]["per_trade"], -33),
        ("close/every-trade win %", close["every trade"]["win_pct"], 44.3),
        ("close/every-trade green months", close["every trade"]["months_green"], 8),
        ("close/every-trade trades", close["every trade"]["trades"], 4329),
    ]
    if pub:
        claims += [
            ("published/one-a-day $/day", pub["one a day"]["per_day"], 721),
            ("published/one-a-day win %", pub["one a day"]["win_pct"], 66.7),
            ("published/one-a-day green months", pub["one a day"]["months_green"], 25),
            ("published/every-trade $/day", pub["every trade"]["per_day"], 5268),
            ("published/every-trade per trade", pub["every trade"]["per_trade"], 584),
            ("published/every-trade trades", pub["every trade"]["trades"], 4508),
            ("published/every-trade green months", pub["every trade"]["months_green"], 25),
        ]
    bad = 0
    print("\nCLAIM CHECK — research/g85_entry_fill.md")
    for name, got, want in claims:
        ok = abs(float(got) - float(want)) <= 0.51
        bad += not ok
        print("  %-38s %-12s claimed %-10s %s"
              % (name, got, want, "ok" if ok else "MISMATCH"))
    print("\n%d of %d headline figures reproduce" % (len(claims) - bad, len(claims)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
