"""g85_honest_book.py — re-measure the two-year book on a fill he can actually pay.

WHAT THIS ANSWERS. Every dollar figure DIRECTION.md and OMEN-7.3.md publish was
priced at `signal_runner.fill_price`'s old clamp — the LEVEL, inside the signal
minute's own range — and the signal does not exist until that minute closes.
Only 105 of 4,508 trades (2.3%) were obtainable at that price
(`research/g80_lookahead_refute.md`). `entry_fill.py` made the signal minute's
CLOSE the shipped default on 2026-08-30. This script re-runs the whole
measurement on the new default and prints the same table for the three arms the
order-type grid could not separate, so the band is visible instead of implied.

It does NOT re-run the backtest. Build the books first, one per fill:

    ENTRY_FILL=close      python backtest_2y.py --out research/bt2y_trades.json
    ENTRY_FILL=published  python backtest_2y.py --out <scratch>/bt2y_published.json
    ENTRY_FILL=chase_once python backtest_2y.py --out <scratch>/bt2y_chase_once.json
    ENTRY_FILL=next_open  python backtest_2y.py --out <scratch>/bt2y_next_open.json

then

    python research/g85_honest_book.py --book close=research/bt2y_trades.json \
        --book published=<scratch>/bt2y_published.json ...

THE ARITHMETIC IS IMPORTED, NOT RE-TYPED. `stats`, `shipped_rows` and
`oneaday_rows` come from research/g72_suppress_price.py, which is what priced the
figures now being replaced — otherwise this would be comparing two definitions
and calling the difference a fill.

Every book is checked against its own stamp before a dollar is read off it
(`research/book_stamp.py`): a book whose metadata does not say which fill priced
it is not quoted here.

1R = $1,000 (CLAUDE.md). Austin's bar is $397 a day, ratified 2026-08-30.
The standing error bar on any A/B in this project is +/-1.5799R, so two arms
inside it are a TIE and no winner may be picked out of them on money.

Writes research/g85_honest_book.json and prints the markdown the report uses.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from g72_suppress_price import stats, shipped_rows, oneaday_rows, load, RISK  # noqa: E402
import book_stamp  # noqa: E402

BAR = 397.0            # Austin's money bar, $/day, ratified 2026-08-30
ERROR_BAR_R = 1.5799   # the standing per-trade error bar (memory: error-bar-exceeds-arms)

LABEL = {
    "published": "published fill — NOT OBTAINABLE (the old default)",
    "close": "close: the signal minute's close (the new default)",
    "chase_once": "chase once: limit at the level one bar, then market",
    "next_open": "next open: market at the next minute's open",
    "limit_level": "limit at the level, resting until 11:00",
}


def boot_per_day(rows, n_days, iters=2000, seed=20260830):
    """95% band on $/day, resampling DAYS (not trades) with replacement.

    Days are the independent unit: two trades on one session share the tape, the
    two-loss halt and the same regime, so resampling trades would understate the
    band. Days with no trade count as $0 and stay in the denominator."""
    if not rows:
        return (0.0, 0.0)
    byday = {}
    for r in rows:
        byday[r["day"]] = byday.get(r["day"], 0.0) + r["pnl"]
    vals = list(byday.values()) + [0.0] * max(0, n_days - len(byday))
    rnd = random.Random(seed)
    n = len(vals)
    means = []
    for _ in range(iters):
        means.append(sum(vals[rnd.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return (round(means[int(0.025 * iters)], 0), round(means[int(0.975 * iters)], 0))


def per_day_series(rows, n_days_index):
    """day -> dollars, zero-filled across every session in the book."""
    out = {d: 0.0 for d in n_days_index}
    for r in rows:
        out[r["day"]] = out.get(r["day"], 0.0) + r["pnl"]
    return out


def paired_diff(a, b, iters=2000, seed=20260830):
    """$/day difference between two fills, resampling the SAME days for both.

    Paired, because both arms price the same sessions: an unpaired comparison
    would carry the market's own variance twice and hide a real difference (or
    invent one). Returns (mean, lo, hi)."""
    days = sorted(set(a) & set(b))
    diffs = [a[d] - b[d] for d in days]
    rnd = random.Random(seed)
    n = len(diffs)
    means = sorted(sum(diffs[rnd.randrange(n)] for _ in range(n)) / n for _ in range(iters))
    return (round(sum(diffs) / n, 0),
            round(means[int(0.025 * iters)], 0), round(means[int(0.975 * iters)], 0))


def arm(path, expect_fill=None):
    """Every figure this report publishes for one fill, off one book."""
    meta, rows = load(Path(path))
    fill = meta.get("entry_fill")
    declared = False
    if fill is None:
        # Only one book on disk predates the stamp: the preserved published-fill
        # book every pre-2026-08-30 figure came from. It is kept BYTE-IDENTICAL
        # rather than re-stamped, so its fill is declared by the caller and said
        # out loud in the output instead of being read off metadata it lacks.
        fill, declared = expect_fill, True
    elif expect_fill and fill != expect_fill:
        raise SystemExit("%s says entry_fill=%r, expected %r" % (path, fill, expect_fill))
    nd = meta["sessions"]
    all_rows, one_rows = shipped_rows(rows), oneaday_rows(rows)
    out = {"book": str(path), "fill": fill,
           "unobtainable": fill == "published",
           "book_id": (meta.get("stamp") or {}).get("book_id"),
           "commit": ((meta.get("stamp") or {}).get("git") or {}).get("commit"),
           "built_at": (meta.get("stamp") or {}).get("built_at", meta.get("generated")),
           "stamped": "stamp" in meta, "fill_declared_by_caller": declared,
           "sessions": nd, "signals": meta["signals"],
           "entry_misses": meta.get("entry_misses"),
           "all": stats(all_rows, nd), "one_a_day": stats(one_rows, nd)}
    days = sorted({r["day"] for r in rows})
    out["series"] = {"all": per_day_series(all_rows, days),
                     "one_a_day": per_day_series(one_rows, days)}
    for k, sel in (("all", all_rows), ("one_a_day", one_rows)):
        lo, hi = boot_per_day(sel, nd)
        out[k]["per_day_lo"], out[k]["per_day_hi"] = lo, hi
        out[k]["vs_bar"] = round(out[k]["per_day"] - BAR, 0)
        out[k]["pct_of_bar"] = round(out[k]["per_day"] / BAR * 100, 0)
        out[k]["risk_to_reach_bar"] = (round(RISK * BAR / out[k]["per_day"], 0)
                                       if out[k]["per_day"] > 0 else None)
    return out


def md_row(name, a, key):
    """One arm's row. EVERY dollar figure states its distance to his $397 bar."""
    s = a[key]
    pd_ = s["per_day"]
    risk = ("$%s" % format(int(s["risk_to_reach_bar"]), ",")) if s["risk_to_reach_bar"] else "never"
    return ("| %s | %s | %s | %.1f%% | %+.3fR | **$%s** | $%s to $%s | %s | %s | %s | %d / %d | %d / %d | $%s |"
            % (name, format(s["trades"], ","), format(s["days_traded"], ","),
               s["win_pct"], s["mean_r"], format(int(pd_), ","),
               format(int(s["per_day_lo"]), ","), format(int(s["per_day_hi"]), ","),
               ("%d%%" % s["pct_of_bar"]) if pd_ > 0 else "0%",
               ("$%s" % format(int(abs(s["vs_bar"])), ",")) if pd_ < BAR else "AT THE BAR",
               risk, s["months_green"], s["months"], s["weeks_green"], s["weeks"],
               format(int(s["worst_drawdown"]), ",")))


HEAD = ("| fill | trades | days traded | win | mean R | $ / day | 95% band |"
        " % of $397 | short of $397 by | risk/trade that reaches $397 |"
        " months green | weeks green | worst drawdown |\n"
        "|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|")


# ------------------------------------------------- what the report published

# The figures research/g85_honest_book.md prints, and the book they came off.
# `python research/g85_honest_book.py --check` re-derives every one of them from
# the book on disk and raises BookMismatch naming both numbers if any moved. A
# report that cannot be re-checked is a report nobody can trust twice.
PUBLISHED_BOOK = str(ROOT / "research" / "bt2y_trades.json")
PUBLISHED = {
    "entry_fill": "close", "traded": 4329, "signals": 127188,
    "book_id": "f76361ae47e9a3b2",
    "figures": [
        ("one_a_day", "trades", 500), ("one_a_day", "win_pct", 45.5),
        ("one_a_day", "mean_r", 0.028), ("one_a_day", "per_day", 28),
        ("one_a_day", "months_green", 11), ("one_a_day", "weeks_green", 49),
        ("one_a_day", "worst_drawdown", 25570),
        ("all", "trades", 4329), ("all", "win_pct", 44.3),
        ("all", "mean_r", -0.033), ("all", "per_day", -283),
        ("all", "months_green", 8), ("all", "weeks_green", 35),
        ("all", "worst_drawdown", 194012),
    ],
}


def check():
    book_stamp.assert_book(PUBLISHED_BOOK, entry_fill=PUBLISHED["entry_fill"],
                           traded=PUBLISHED["traded"], signals=PUBLISHED["signals"],
                           book_id_=PUBLISHED["book_id"])
    for policy, field, value in PUBLISHED["figures"]:
        book_stamp.assert_figure(PUBLISHED_BOOK, policy, field, value)
    print("g85_honest_book.md still matches the book on disk — %d figures checked\n  %s"
          % (len(PUBLISHED["figures"]), book_stamp.describe(PUBLISHED_BOOK)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--book", action="append", default=[],
                    metavar="FILL=PATH", help="repeatable, e.g. close=research/bt2y_trades.json")
    ap.add_argument("--check", action="store_true",
                    help="re-derive every figure this report published and fail if one moved")
    ap.add_argument("--out", default=str(ROOT / "research" / "g85_honest_book.json"))
    args = ap.parse_args()
    if args.check:
        return check()
    if not args.book:
        raise SystemExit("give at least one --book FILL=PATH")

    arms = {}
    for spec in args.book:
        fill, _, path = spec.partition("=")
        arms[fill] = arm(path, expect_fill=fill)
        print(book_stamp.describe(path)
              + ("   <- UNSTAMPED, fill declared by the caller" if arms[fill]["fill_declared_by_caller"] else ""))

    order = [f for f in ("close", "chase_once", "next_open", "published") if f in arms]
    lines = []
    for policy, title in (("one_a_day", "One trade a day"), ("all", "Taking every signal")):
        lines += ["", "### %s" % title, "", HEAD]
        for f in order:
            lines.append(md_row(LABEL.get(f, f), arms[f], policy))
    # Paired against the shipped default, day by day. This is the only way to ask
    # "is this arm actually different from close?" without the market's own
    # variance answering for it.
    pair = {}
    for f in order:
        if f == "close" or "close" not in arms:
            continue
        for policy in ("one_a_day", "all"):
            m, lo, hi = paired_diff(arms[f]["series"][policy], arms["close"]["series"][policy])
            pair["%s|%s" % (f, policy)] = {
                "per_day": m, "lo": lo, "hi": hi,
                "verdict": ("TIE — the band straddles zero" if lo <= 0 <= hi
                            else "separates from zero")}
    if pair:
        lines += ["", "### Paired against the shipped `close` fill, day by day", "",
                  "| arm | policy | $ / day vs close | 95% band | verdict |",
                  "|---|---|---:|---|---|"]
        for k, v in pair.items():
            a, _, policy = k.partition("|")
            lines.append("| %s | %s | %+d | $%s to $%s | %s |"
                         % (LABEL.get(a, a), policy.replace("_", " "), v["per_day"],
                            format(int(v["lo"]), ","), format(int(v["hi"]), ","),
                            v["verdict"]))
    md = "\n".join(lines)
    print(md)

    Path(args.out).write_text(json.dumps(
        {"bar_per_day": BAR, "risk_dollars": RISK, "error_bar_r": ERROR_BAR_R,
         "paired_vs_close": pair, "arms": arms, "markdown": md}, indent=1),
        encoding="utf-8")
    print("\nwrote %s" % args.out)


if __name__ == "__main__":
    main()
