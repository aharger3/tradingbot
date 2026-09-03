"""g85_verify_1.py — independent recompute of the two largest numbers in
research/g85_honest_book.md, written for the adversarial verification pass.

It shares NO code with research/g85_honest_book.py: no import of
g72_suppress_price, no import of book_stamp. The day-selection rule, the
dollar sum, the month tally and the drawdown are re-typed from the report's own
prose so that agreeing is evidence and disagreeing is a refutation.

1R = $1,000. Austin's bar is $397 a day.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RISK = 1000.0
BAR = 397.0


def load(p):
    b = json.load(open(p, encoding="utf-8"))
    return b["meta"], b["trades"]


def key(r):
    return (r["day"], r["et"], r["sym"])


def every_signal(rows):
    return sorted([r for r in rows if r.get("traded")], key=key)


def one_a_day(rows):
    """First candidate of each session. Candidates = fired-and-traded, plus the
    rows the account-wide two-loss halt blocked (under one-a-day the halt has
    not fired yet)."""
    byday = {}
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            byday.setdefault(r["day"], []).append(r)
    return [min(v, key=key) for _, v in sorted(byday.items())]


def measure(rows, n_days, all_days):
    tot = sum(r["pnl"] for r in rows)
    wins = sum(1 for r in rows if r["pnl"] > 0)
    # dollars are re-derived from R so a bad pnl column cannot hide
    tot_from_r = sum(r["r"] * RISK for r in rows)
    bym = {}
    for r in rows:
        bym[r["ym"]] = bym.get(r["ym"], 0.0) + r["pnl"]
    byday = {d: 0.0 for d in all_days}
    for r in rows:
        byday[r["day"]] = byday.get(r["day"], 0.0) + r["pnl"]
    eq = 0.0; peak = 0.0; dd = 0.0
    for d in sorted(byday):
        eq += byday[d]
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return {
        "trades": len(rows),
        "win_pct": round(100.0 * wins / len(rows), 1) if rows else 0.0,
        "mean_r": round(tot / len(rows) / RISK, 4) if rows else 0.0,
        "total_dollars": round(tot, 0),
        "total_dollars_from_r_column": round(tot_from_r, 0),
        "per_day": round(tot / n_days, 0),
        "pct_of_bar": round(100.0 * (tot / n_days) / BAR, 1),
        "short_by": round(BAR - tot / n_days, 0),
        "months_green": sum(1 for v in bym.values() if v > 0),
        "months": len(bym),
        "worst_drawdown": round(dd, 0),
    }


def main():
    books = [("close  (research/bt2y_trades.json)", ROOT / "research/bt2y_trades.json"),
             ("published (preserved, NOT OBTAINABLE)",
              ROOT / "research/bt2y_trades_published_fill.json")]
    out = {}
    for label, p in books:
        if not p.exists():
            print("MISSING %s" % p); continue
        meta, rows = load(p)
        nd = meta["sessions"]
        all_days = sorted({r["day"] for r in rows})
        res = {"sessions": nd, "distinct_days_in_file": len(all_days),
               "declared_fill": meta.get("entry_fill"),
               "declared_traded": meta.get("traded"),
               "every_signal": measure(every_signal(rows), nd, all_days),
               "one_a_day": measure(one_a_day(rows), nd, all_days)}
        out[label] = res
        print("\n=== %s ===" % label)
        print("  sessions %d, file declares fill=%r traded=%s"
              % (nd, meta.get("entry_fill"), meta.get("traded")))
        for pol in ("one_a_day", "every_signal"):
            s = res[pol]
            print("  %-13s %5d tr  %5.1f%% win  %+.4fR  $%s/day  (%.0f%% of $397, short $%s)"
                  " months %d/%d  total $%s  maxDD $%s"
                  % (pol, s["trades"], s["win_pct"], s["mean_r"], f'{s["per_day"]:,.0f}',
                     s["pct_of_bar"], f'{s["short_by"]:,.0f}', s["months_green"],
                     s["months"], f'{s["total_dollars"]:,.0f}',
                     f'{s["worst_drawdown"]:,.0f}'))
            # the r column is stored to 3 decimals, so ~$0.50 of rounding per
            # trade is expected; anything bigger means the two columns disagree
            # about the trade itself
            assert abs(s["total_dollars"] - s["total_dollars_from_r_column"]) \
                < 1.0 * s["trades"], "pnl column disagrees with r column"
    (ROOT / "research/g85_verify_1.json").write_text(json.dumps(out, indent=1))
    print("\nwrote research/g85_verify_1.json")


if __name__ == "__main__":
    sys.exit(main())
