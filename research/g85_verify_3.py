"""g85_verify_3.py -- an adversarial, from-scratch recomputation of the two
largest numbers on `research/omen-71-verdict.html`.

Imports NOTHING from `research/g72_suppress_price.py`, `research/book_stamp.py`
or `research/g85_honest_book.py`.  It reads the two book JSONs off disk and
re-derives, in plain arithmetic written here:

    * money, one trade a day        $/day, mean R, win %
    * money, every signal           $/day, mean R, win %
    * durability                    months green, both policies
    * trade and signal counts
    * the same six on the frozen published-fill control

and then checks them against the figures the verdict page and
`research/g85_verdict_rebuild.md` publish.

1R = $1,000 (CLAUDE.md).  Sessions divisor comes from the book's own meta.

Run:  python research/g85_verify_3.py
Exit 0 = every published figure reproduced.  Exit 1 = at least one did not.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RISK = 1000.0

HONEST = ROOT / "research" / "bt2y_trades.json"
PUBLISHED = ROOT / "research" / "bt2y_trades_published_fill.json"
PAGE = ROOT / "research" / "omen-71-verdict.html"


def load(p):
    b = json.loads(Path(p).read_text(encoding="utf-8"))
    return b["meta"], b["trades"]


def order(r):
    return (r["day"], r["et"], r["sym"])


def all_signal_rows(rows):
    """Every trade the engine actually took."""
    return sorted((r for r in rows if r.get("traded")), key=order)


def one_a_day_rows(rows):
    """The first tradeable candidate of each session, then done for the day.

    A row the account-wide two-loss halt blocked is a candidate here: under
    one-a-day there is no second loss yet, so the halt could not have fired.
    Written out longhand rather than imported."""
    byday = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            byday[r["day"]].append(r)
    return [min(v, key=order) for _, v in sorted(byday.items())]


def figures(rows, sessions):
    if not rows:
        return {}
    pnl = [r["pnl"] for r in rows]
    wins = sum(1 for x in pnl if x > 0)
    losses = sum(1 for x in pnl if x < 0)
    total = sum(pnl)
    by_month = defaultdict(float)
    for r in rows:
        by_month[r["day"][:7]] += r["pnl"]
    return {
        "trades": len(rows),
        "per_day": total / sessions,
        "mean_r": total / len(rows) / RISK,
        "win_pct": wins / (wins + losses) * 100 if wins + losses else 0.0,
        "months": len(by_month),
        "months_green": sum(1 for v in by_month.values() if v > 0),
        "total": total,
    }


def book(path):
    meta, rows = load(path)
    n = meta["sessions"]
    return {
        "meta": meta,
        "sessions": n,
        "signals": len(rows),
        "one_a_day": figures(one_a_day_rows(rows), n),
        "all": figures(all_signal_rows(rows), n),
    }


# ------------------------------------------------------------------ the claims
# label, actual, published, tolerance
def claims(h, p):
    return [
        ("honest one-a-day $/day", h["one_a_day"]["per_day"], 28, 1.0),
        ("honest one-a-day mean R", h["one_a_day"]["mean_r"], 0.0278, 0.0005),
        ("honest one-a-day win %", h["one_a_day"]["win_pct"], 45.5, 0.1),
        ("honest one-a-day months green", h["one_a_day"]["months_green"], 11, 0),
        ("honest one-a-day months", h["one_a_day"]["months"], 25, 0),
        ("honest all-signals $/day", h["all"]["per_day"], -283, 1.0),
        ("honest all-signals mean R", h["all"]["mean_r"], -0.0327, 0.0005),
        ("honest all-signals win %", h["all"]["win_pct"], 44.3, 0.1),
        ("honest all-signals months green", h["all"]["months_green"], 8, 0),
        ("honest traded count", h["all"]["trades"], 4329, 0),
        ("honest signal count", h["signals"], 127188, 0),
        ("published-fill one-a-day $/day", p["one_a_day"]["per_day"], 721, 1.0),
        ("published-fill all-signals $/day", p["all"]["per_day"], 5268, 1.0),
        ("published-fill one-a-day months green", p["one_a_day"]["months_green"], 25, 0),
        ("published-fill all-signals months green", p["all"]["months_green"], 25, 0),
        ("published-fill traded count", p["all"]["trades"], 4508, 0),
    ]


def check_page(h):
    """The page must actually contain the honest figures, not stale ones."""
    if not PAGE.exists():
        return [("verdict page exists", "MISSING", False)]
    txt = PAGE.read_text(encoding="utf-8", errors="replace")
    out = []
    must = ["4,329", "11 / 25", "74.3", "$397", "NOT OBTAINABLE"]
    for s in must:
        out.append(("page contains %r" % s, s in txt, True))
    forbidden = ["2,437", "fonts.googleapis", "fonts.gstatic", "1,339,000",
                 "76,019"]
    for s in forbidden:
        out.append(("page free of %r" % s, s not in txt, True))
    ext = re.findall(r'(?:href|src)\s*=\s*["\'](https?://[^"\']+)', txt)
    out.append(("page requests no external resource: %s" % (ext or "none"),
                not ext, True))
    return out


def main():
    h, p = book(HONEST), book(PUBLISHED)
    print("BOOKS")
    for name, b in (("honest", h), ("published-fill", p)):
        m = b["meta"]
        print("  %-14s fill=%-9s sessions=%d signals=%d traded=%d built=%s"
              % (name, m.get("entry_fill"), b["sessions"], b["signals"],
                 b["all"]["trades"], m.get("generated")))
    print()

    bad = 0
    print("FIGURES  (mine vs published)")
    for label, got, want, tol in claims(h, p):
        ok = abs(got - want) <= tol
        bad += not ok
        print("  %-42s mine %-12s published %-10s %s"
              % (label, round(got, 4), want, "ok" if ok else "MISMATCH"))
    print()

    print("THE PAGE ITSELF")
    for label, got, want in check_page(h):
        ok = got == want
        bad += not ok
        print("  %-62s %s" % (label, "ok" if ok else "FAIL (%r)" % (got,)))
    print()

    print("DISTANCE TO THE $397/DAY BAR")
    d = h["one_a_day"]["per_day"]
    print("  one trade a day: $%.0f/day = %.1f%% of $397, short by $%.0f"
          % (d, d / 397 * 100, 397 - d))
    print("  every signal:    $%.0f/day, short by $%.0f"
          % (h["all"]["per_day"], 397 - h["all"]["per_day"]))
    print("  green months:    %d/%d one-a-day, %d/%d all signals -- "
          "target is every month"
          % (h["one_a_day"]["months_green"], h["one_a_day"]["months"],
             h["all"]["months_green"], h["all"]["months"]))
    print()
    print("VERDICT:", "all published figures reproduced" if not bad
          else "%d figure(s) did NOT reproduce" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
