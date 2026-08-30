"""G8.2 — the stop A/B and the profit-leg A/B Austin asked for, over two years.

Austin on the close-only stop rule: it stands *"if you have the metrics."*
Nobody had ever run the plain A/B. This is it.

WHAT IT MEASURES
----------------
Six full replays of the 500-session archive through the shipped engine
(`backtest_2y.py`), one per arm, each priced on identical arithmetic imported
from `research/g72_suppress_price.py` so nothing is re-typed:

STOPS
  shipped        the book as it ships. Close-triggered LEVEL stop, PLUS a
                 resting -1R disaster stop on TOUCH, PLUS the -1.25R floor.
  close_floor    close trigger, fill at that close, floored at -1.25R, and NO
                 disaster stop underneath. This is the rule CLAUDE.md states.
  close_nofloor  the same with the floor removed.
  touch          a resting stop order: fires the moment price TOUCHES the level,
                 fills there (or at the bar's open if the bar gapped through it).
                 No floor.
  touch_floor    the same, floored at -1.25R -- so the floor is doing gap
                 protection and nothing else.

PROFIT LEGS
  shipped        every profit leg fills on an intrabar TOUCH. This is what the
                 code already does at all three of them, and always has.
  target_close   a profit leg needs a candle to CLOSE through it.

THE THING TO KNOW BEFORE READING THE STOP TABLE
-----------------------------------------------
`stop_rule.disaster_stop_price(entry, risk, long, 1.0)` is `entry -/+ 1.0 * risk`,
and `risk` IS `abs(entry - stop)`. So the resting disaster stop sits at exactly
the same price as the level stop, and `backtest_week._ladder_bar` tests it FIRST,
on a touch. The shipped book therefore already exits on an intrabar touch of the
stop on every unscaled leg -- the close-only rule only survives on a runner whose
stop has been raised to break-even. Which is why 0 of 1,828 losses in
`research/bt2y_trades.json` book worse than -1.000R and 1,775 of them book
exactly -1.000R: the -1.25R floor is unreachable code again, for a second and
completely different reason from the one T11 fixed.

Usage:
    python research/g82_stop_ab.py                 # build all six, then price
    python research/g82_stop_ab.py --skip-run      # re-price books on disk
    python research/g82_stop_ab.py --only shipped touch
    python research/g82_stop_ab.py --jobs 3        # parallel replays

1R = $1,000 (CLAUDE.md). Writes research/g82_stop_ab.json and the two tables
that go into research/g82_stop_ab.md.
"""
import argparse, json, os, random, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from g72_suppress_price import (stats, shipped_rows, oneaday_rows, load,  # noqa: E402
                                RISK, iso_week)

# The standing method finding, DIRECTION.md: every A/B this project has ever run
# moves less than this. Two arms inside it are a TIE and must be reported as one.
ERROR_BAR_R = 1.5799

# arm -> (env overrides, one-line English)
ARMS = {
    "shipped":       ({}, "as shipped: close-triggered level stop + resting -1R "
                          "disaster stop on touch + -1.25R floor"),
    "close_floor":   ({"STOP_ARM": "close_floor"},
                      "close only, fill at that close, floored at -1.25R"),
    "close_nofloor": ({"STOP_ARM": "close_nofloor"},
                      "close only, fill at that close, no floor"),
    "touch":         ({"STOP_ARM": "touch"},
                      "resting stop: fires on touch, fills at the stop (bar open on a gap)"),
    "touch_floor":   ({"STOP_ARM": "touch_floor"},
                      "the same, floored at -1.25R (gap protection only)"),
    "target_close":  ({"TARGET_ON_CLOSE": "1"},
                      "shipped stop; profit legs need a candle CLOSE through the target"),
}
STOP_ARMS = ["shipped", "close_floor", "close_nofloor", "touch", "touch_floor"]
TARGET_ARMS = ["shipped", "target_close"]

BOOKS = ROOT / "research" / "_g82_books"


def book_path(arm: str) -> Path:
    return BOOKS / ("g82_%s.json" % arm)


# ------------------------------------------------------------------- building

def build(arm: str) -> None:
    env = dict(os.environ)
    env.update(ARMS[arm][0])
    env["PYTHONIOENCODING"] = "utf-8"
    out = book_path(arm)
    cmd = [sys.executable, str(ROOT / "backtest_2y.py"), "--out",
           str(out.relative_to(ROOT)).replace("\\", "/")]
    print("  [%s] starting %s" % (arm, ARMS[arm][0] or "(defaults)"), flush=True)
    p = subprocess.run(cmd, cwd=str(ROOT), env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, errors="replace")
    # POLYGON_API_KEY is interpolated into request URLs and shows up whole in a
    # traceback (CLAUDE.md, Security). Never let a line carrying it reach stdout.
    tail = [l for l in p.stdout.splitlines() if "apiKey" not in l][-2:]
    for l in tail:
        print("  [%s] %s" % (arm, l), flush=True)
    if p.returncode != 0:
        raise SystemExit("[%s] backtest_2y failed (exit %d)" % (arm, p.returncode))


# ------------------------------------------------------------------- pricing

def avg_loss_r(rows) -> float:
    """The average LOSING trade, in R. The column the floor is supposed to move."""
    losses = [r["pnl"] / RISK for r in rows if r["pnl"] < 0]
    return round(sum(losses) / len(losses), 4) if losses else 0.0


def worst_loss_r(rows) -> float:
    losses = [r["pnl"] / RISK for r in rows if r["pnl"] < 0]
    return round(min(losses), 4) if losses else 0.0


def n_past_floor(rows) -> int:
    """How many trades booked worse than -1.25R -- i.e. how often the floor
    would have had something to clamp if it were not there."""
    return sum(1 for r in rows if r["pnl"] / RISK < -1.2500001)


def price(rows, n_days: int) -> dict:
    all_r, one_r = shipped_rows(rows), oneaday_rows(rows)
    out = {}
    for name, sel in (("all", all_r), ("one_a_day", one_r)):
        s = stats(sel, n_days)
        s["avg_loss_r"] = avg_loss_r(sel)
        s["worst_loss_r"] = worst_loss_r(sel)
        s["n_past_floor"] = n_past_floor(sel)
        out[name] = s
    return out


def paired_day_diff(rows_a, rows_b, sel):
    """Per-SESSION dollar difference between two arms, same 500 sessions."""
    da, db = {}, {}
    for r in sel(rows_a):
        da[r["day"]] = da.get(r["day"], 0.0) + r["pnl"]
    for r in sel(rows_b):
        db[r["day"]] = db.get(r["day"], 0.0) + r["pnl"]
    days = sorted(set(da) | set(db))
    return [db.get(d, 0.0) - da.get(d, 0.0) for d in days]


def bootstrap_ci(diff, n=10000, seed=8202):
    """95% CI on the mean per-session dollar difference, resampled by DAY."""
    if not diff:
        return (0.0, 0.0, 0.0)
    rnd = random.Random(seed)
    k = len(diff)
    means = []
    for _ in range(n):
        means.append(sum(diff[rnd.randrange(k)] for _ in range(k)) / k)
    means.sort()
    return (round(sum(diff) / k, 1), round(means[int(0.025 * n)], 1),
            round(means[int(0.975 * n)], 1))


# -------------------------------------------------------------------- tables

def fmt_money(x):
    return ("-$%s" % format(int(abs(x)), ",")) if x < 0 else ("$%s" % format(int(x), ","))


def table(arms, priced, key="all", one="one_a_day"):
    head = ("| arm | $/day, everything | $/day, one a day | trades | win % | "
            "mean R | avg loss R | months green | weeks green | worst drawdown |")
    sep = "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    lines = [head, sep]
    for a in arms:
        s, o = priced[a][key], priced[a][one]
        lines.append("| %s | %s | %s | %s | %.1f%% | %.4f | %.4f | %d of %d | %d of %d | %s |"
                     % (a, fmt_money(s["per_day"]), fmt_money(o["per_day"]),
                        format(s["trades"], ","), s["win_pct"], s["mean_r"],
                        s["avg_loss_r"], s["months_green"], s["months"],
                        s["weeks_green"], s["weeks"], fmt_money(s["worst_drawdown"])))
    return "\n".join(lines)


# ----------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skip-run", action="store_true")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--out", default=str(ROOT / "research" / "g82_stop_ab.json"))
    args = ap.parse_args()

    wanted = args.only or list(ARMS)
    BOOKS.mkdir(parents=True, exist_ok=True)

    if not args.skip_run:
        todo = [a for a in wanted if a in ARMS]
        print("building %d arms, %d at a time" % (len(todo), args.jobs), flush=True)
        with ThreadPoolExecutor(max_workers=args.jobs) as ex:
            list(ex.map(build, todo))

    priced, metas, books = {}, {}, {}
    for a in list(ARMS):
        p = book_path(a)
        if not p.exists():
            print("  (no book for %s -- skipped)" % a)
            continue
        m, rows = load(p)
        metas[a], books[a] = m, rows
        priced[a] = price(rows, m["sessions"])
        priced[a]["meta"] = {k: m.get(k) for k in
                             ("generated", "sessions", "signals", "traded", "halted")}

    have_stop = [a for a in STOP_ARMS if a in priced]
    have_tgt = [a for a in TARGET_ARMS if a in priced]

    out = {"risk_dollars": RISK, "error_bar_r": ERROR_BAR_R,
           "arms": {a: {"env": ARMS[a][0], "what": ARMS[a][1]} for a in priced},
           "priced": priced, "error_bars": {}}

    # Every comparison is against the shipped book, paired by session, both
    # policies. The standing finding is that these intervals straddle zero; it
    # is reported either way, never assumed.
    if "shipped" in books:
        for a in priced:
            if a == "shipped":
                continue
            e = {}
            for pol, sel in (("all", shipped_rows), ("one_a_day", oneaday_rows)):
                d = paired_day_diff(books["shipped"], books[a], sel)
                mean, lo, hi = bootstrap_ci(d)
                e[pol] = {"mean_dollars_per_session": mean, "ci_lo": lo, "ci_hi": hi,
                          "mean_r_per_session": round(mean / RISK, 4),
                          "straddles_zero": bool(lo <= 0 <= hi),
                          "inside_error_bar": bool(abs(mean / RISK) < ERROR_BAR_R)}
            out["error_bars"][a] = e

    print()
    print("STOPS - 1R = $1,000, %s sessions" % metas.get("shipped", {}).get("sessions", "?"))
    print(table(have_stop, priced))
    print()
    print("PROFIT LEGS - 1R = $1,000")
    print(table(have_tgt, priced))
    print()
    print("floor check - trades booking worse than -1.25R (all-trades policy):")
    for a in have_stop:
        print("  %-14s %5d of %s   worst %.4fR"
              % (a, priced[a]["all"]["n_past_floor"],
                 format(priced[a]["all"]["trades"], ","),
                 priced[a]["all"]["worst_loss_r"]))
    print()
    print("paired per-session difference vs shipped (95%% CI, 10k resamples), "
          "error bar +/-%.4fR:" % ERROR_BAR_R)
    for a, e in out["error_bars"].items():
        x = e["all"]
        print("  %-14s %+8s  CI [%s, %s]  %s"
              % (a, fmt_money(x["mean_dollars_per_session"]),
                 fmt_money(x["ci_lo"]), fmt_money(x["ci_hi"]),
                 "TIE" if x["straddles_zero"] else "moves"))
    # Where the dollars come from. A book can earn more two ways -- better
    # trades, or more of them -- and DIRECTION.md's standing warning is that
    # this project keeps reading the second as the first. Split it.
    print()
    print("per-trade edge vs shipped, against the standing +/-%.4fR bar:" % ERROR_BAR_R)
    if "shipped" in priced:
        base = priced["shipped"]["all"]
        for a in have_stop + [x for x in have_tgt if x != "shipped"]:
            if a == "shipped":
                continue
            cur = priced[a]["all"]
            d_r = cur["mean_r"] - base["mean_r"]
            d_n = cur["trades"] - base["trades"]
            from_count = d_n * base["per_trade"] / metas[a]["sessions"]
            from_quality = base["trades"] * (cur["per_trade"] - base["per_trade"])                 / metas[a]["sessions"]
            cross = d_n * (cur["per_trade"] - base["per_trade"]) / metas[a]["sessions"]
            out.setdefault("decomposition", {})[a] = {
                "delta_mean_r_per_trade": round(d_r, 4),
                "beats_error_bar": bool(abs(d_r) >= ERROR_BAR_R),
                "delta_trades": d_n,
                "dollars_per_session_from_count": round(from_count, 1),
                "dollars_per_session_from_quality": round(from_quality, 1),
                "dollars_per_session_cross_term": round(cross, 1)}
            print("  %-14s %+8.4fR/trade  %-4s  |  %+d trades -> %s/session, "
                  "quality -> %s/session"
                  % (a, d_r, "beats" if abs(d_r) >= ERROR_BAR_R else "TIE",
                     d_n, fmt_money(from_count), fmt_money(from_quality)))
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)

    md = ROOT / "research" / "_g82_tables.md"
    blocks = ["### stops", table(have_stop, priced),
              "### profit legs", table(have_tgt, priced)]
    md.write_text(("%s%s" % (chr(10), chr(10))).join(blocks) + chr(10),
                  encoding="utf-8")
    print()
    print("wrote %s and %s" % (args.out, md))


if __name__ == "__main__":
    main()
