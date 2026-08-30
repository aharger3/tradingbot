"""G80 - independent reconciliation of the two-year dollar figures.

WHY THIS EXISTS
---------------
Three different dollars-a-day headlines are in circulation, all describing a file
called research/bt2y_trades.json:

  * research/g71_board.md      "$305 a day one trade a day, $2,700 a day taking
                                everything", on a 2,437-trade book.
  * DIRECTION.md / g72_after   "$721 a day one trade a day", on a 4,508-trade book.
  * research/g76_rebuild_verdict.md
                               "$721 a day is dead; honest fills give $0 to $114
                                a day."

This script does three things, none of which trust any of those reports:

  A. BOOK CENSUS. Enumerates every version of research/bt2y_trades.json that
     exists - the working-tree file and every committed one - and prices each on
     one arithmetic. This settles which published number belongs to which book.

  B. THE PUBLISHED FILL, RECOMPUTED. One trade a day and everything-taken, from
     the working-tree book, with a day-resampled 95% interval.

  C. THE HEAD START, MODEL-FREE. For every traded row, how far in front the trade
     already is at the instant its signal exists - measured off the archived bar
     the trade was opened on. No model, no re-simulation.

  D. THE MATCHED-PAIR TEST. One simple flat-2R simulation, run twice over the
     same archived bars with the same stops and the same rules, differing in one
     thing only: the price paid. Arm 1 pays the book's fill. Arm 2 pays the close
     of the minute the signal fired. Everything else is held identical, so the
     difference IS the fill and nothing else. This is the control-beside-the-
     intricate-rig pattern: it is not the shipped exit machinery (no scale-outs,
     no break-even move), and it is not meant to be. It is meant to be the same
     on both sides.

Conventions (CLAUDE.md): 1R = $1,000. Stops trigger on the candle CLOSE and fill
through stop_rule.stop_fill_price, floored at -1.25R. Wicks stop nothing.
Targets are limit orders and fill on an intrabar touch. The minute the trade is
opened on is not a management minute (the same convention the book itself uses).

Reads only. Touches no mark file, no engine file, nothing under research/marks/.
Bars come from the local data_archive cache; no API call is made and no URL is
printed.

Usage:  python research/g80_dollar_reconcile.py
Writes: research/g80_dollar_reconcile.json
"""
from __future__ import annotations

import json
import random
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import polygon_feed as pf          # noqa: E402  (cache-first; no network if cached)
from stop_rule import stop_hit_on_close, stop_fill_price   # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades.json"
OUT = ROOT / "research" / "g80_dollar_reconcile.json"
RISK = 1000.0
SEED = 20260830
BOOTS = 10000


# --------------------------------------------------------------- arithmetic

def drawdown(seq):
    cum = peak = worst = 0.0
    for p in seq:
        cum += p
        peak = max(peak, cum)
        worst = max(worst, peak - cum)
    return worst


def price(rows, n_days):
    """One arithmetic for every book in this file. rows: dicts with day + pnl."""
    if not rows:
        return {}
    pnls = [r["pnl"] for r in rows]
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    by_m, by_d = {}, {}
    for r in rows:
        by_m[r["day"][:7]] = by_m.get(r["day"][:7], 0.0) + r["pnl"]
        by_d[r["day"]] = by_d.get(r["day"], 0.0) + r["pnl"]
    total = sum(pnls)
    return {
        "trades": len(rows),
        "win_pct": round(wins / (wins + losses) * 100, 1) if wins + losses else 0.0,
        "total_dollars": round(total, 0),
        "per_trade": round(total / len(rows), 0),
        "mean_r": round(total / len(rows) / RISK, 4),
        "per_day": round(total / n_days, 0),
        "per_month": round(total / n_days * 20, 0),
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "months": len(by_m),
        "worst_drawdown": round(drawdown(pnls), 0),
    }


def day_ci(rows, all_days, label=""):
    """95% interval on dollars-a-day, resampling whole SESSIONS with replacement.

    A day with no trade contributes $0 and is in the draw - otherwise the
    interval prices a different question than the headline does.
    """
    by_d = {d: 0.0 for d in all_days}
    for r in rows:
        by_d[r["day"]] = by_d.get(r["day"], 0.0) + r["pnl"]
    v = [by_d[d] for d in sorted(by_d)]
    rng = random.Random(SEED)
    n = len(v)
    means = sorted(sum(rng.choices(v, k=n)) / n for _ in range(BOOTS))
    return {"label": label, "days": n,
            "per_day": round(sum(v) / n, 0),
            "ci95_low": round(means[int(BOOTS * 0.025)], 0),
            "ci95_high": round(means[int(BOOTS * 0.975)], 0),
            "crosses_zero": bool(means[int(BOOTS * 0.025)] <= 0 <= means[int(BOOTS * 0.975)])}


def clip2r(rows):
    """Every winner clipped at +2.0R — what the live path actually books.

    `options_sizer.DEFAULT_RR = 2.0` is the live path's only exit and
    `paper_trader` closes the WHOLE position there; there is no runner leg live
    (research/g71_rrcap.md). g71_board.md's headline dollar figure is this lens,
    not the book's scale-and-runner exit, and that is half of why it differs
    from the figure g76 attacks.
    """
    out = []
    for r in rows:
        rr = min(r["r"], 2.0)
        out.append(dict(r, r=rr, pnl=rr * RISK))
    return out


def ekey(r):
    return (r["day"], r["et"], r["sym"])


def shipped_rows(rows):
    out = [r for r in rows if r.get("traded")]
    out.sort(key=ekey)
    return out


def oneaday_rows(rows):
    """First candidate of the day, then done.

    Candidate stream is g72_suppress_price.py's, unchanged, so the recompute is
    comparable to the number it is checking: a fired-and-traded row, or a row the
    account-wide two-loss halt blocked (under one-a-day the halt cannot have
    fired yet, so those days are live again).
    """
    byday = {}
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            byday.setdefault(r["day"], []).append(r)
    return [sorted(v, key=ekey)[0] for _, v in sorted(byday.items())]


# ------------------------------------------------------------- A. book census

def census():
    """Every version of research/bt2y_trades.json, priced on one arithmetic."""
    out = []

    def add(source, blob):
        b = json.loads(blob)
        m, rows = b["meta"], b["trades"]
        nd = m["sessions"]
        days = sorted({r["day"] for r in rows})
        out.append({
            "source": source,
            "generated": m["generated"],
            "sessions": nd,
            "signals": m.get("signals"),
            "traded_meta": m.get("traded"),
            "traded_counted": sum(1 for r in rows if r.get("traded")),
            "halted": m.get("halted"),
            "everything": price(shipped_rows(rows), nd),
            "one_a_day": price(oneaday_rows(rows), nd),
            # g71_board.md's headline is the LIVE exit, not the book's: the live
            # path sells the whole position at 2R (options_sizer.DEFAULT_RR),
            # so every winner is clipped there. Same rows, one clip.
            "one_a_day_live_2R_clip": price(clip2r(oneaday_rows(rows)), nd),
            "worst_loss_r": round(min(r["r"] for r in rows if r.get("traded")), 4),
            "losses_past_1R": sum(1 for r in rows if r.get("traded") and r["r"] < -1.0),
            "_days": days,
        })

    print("A. BOOK CENSUS", flush=True)
    print("   working tree ...", flush=True)
    add("working tree (uncommitted)", BOOK.read_text(encoding="utf-8"))

    log = subprocess.run(["git", "log", "--format=%h %ad", "--date=short",
                          "--", "research/bt2y_trades.json"],
                         cwd=str(ROOT), capture_output=True, text=True)
    for line in log.stdout.strip().splitlines():
        sha, dt = line.split()
        subj = subprocess.run(["git", "show", "--no-patch", "--format=%s", sha],
                              cwd=str(ROOT), capture_output=True, text=True).stdout.strip()
        print("   commit %s (%s) ..." % (sha, dt), flush=True)
        blob = subprocess.run(["git", "show", "%s:research/bt2y_trades.json" % sha],
                              cwd=str(ROOT), capture_output=True, text=True).stdout
        add("commit %s  %s  %s" % (sha, dt, subj[:60]), blob)
    return out


# ------------------------------------------------------- bar access (cached)

_cache = {}


def bars(sym, day):
    k = (sym, day)
    if k not in _cache:
        if len(_cache) > 60:
            _cache.clear()
        try:
            _cache[k] = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            _cache[k] = []
    return _cache[k]


# -------------------------------------------- D. one simple sim, two fills

def simulate(entry_px, stop_px, long, b, i):
    """Flat 2R, close-triggered stop, -1.25R floor, target on touch.

    Returns (r, tag) or None if the trade is not takeable at that price
    (the entry is already at or through its own stop).

    Bar i is the minute the signal fired and the trade is opened on; management
    starts at i+1, which is the convention the published book uses for its own
    entries. Unresolved at 15:59 is marked to the last close.
    """
    risk = (entry_px - stop_px) if long else (stop_px - entry_px)
    if risk <= 0.005:
        return None
    target = entry_px + 2.0 * risk if long else entry_px - 2.0 * risk
    for c in b[i + 1:]:
        if stop_hit_on_close(c.close, stop_px, long):
            fill = stop_fill_price(c.close, entry_px, risk, long)
            r = (fill - entry_px) / risk if long else (entry_px - fill) / risk
            return round(r, 4), "stop"
        if (long and c.high >= target) or ((not long) and c.low <= target):
            return 2.0, "target"
    if len(b) <= i + 1:
        return None
    last = b[-1].close
    r = (last - entry_px) / risk if long else (entry_px - last) / risk
    return round(max(r, -1.25), 4), "eod"


def matched_pair(rows):
    """The same simulation over the same bars, twice, differing only in the fill.

    Arm PUBLISHED pays the book's own entry price.
    Arm CLOSE pays the close of the minute the signal fired.
    Both use the book's stop, a 2R target measured from their own entry, and the
    same close-triggered stop with the -1.25R floor.
    """
    tr = shipped_rows(rows)
    tr.sort(key=lambda r: (r["sym"], r["day"]))
    pub, cls = [], []
    missing = notakeable_pub = notakeable_cls = 0
    head_r, head_dollars = [], []
    for r in tr:
        b = bars(r["sym"], r["day"])
        i = r["entry_i"]
        if i >= len(b) - 1:
            missing += 1
            continue
        long = r["dir"] == "call"
        close = b[i].close
        risk = (r["entry"] - r["stop"]) if long else (r["stop"] - r["entry"])
        if risk > 0.005:
            hs = ((close - r["entry"]) if long else (r["entry"] - close)) / risk
            head_r.append(hs)
            head_dollars.append(hs * RISK)

        a = simulate(r["entry"], r["stop"], long, b, i)
        if a is None:
            notakeable_pub += 1
        else:
            pub.append({"day": r["day"], "sym": r["sym"], "et": r["et"],
                        "status": r["status"], "traded": True,
                        "r": a[0], "pnl": a[0] * RISK, "tag": a[1]})
        c = simulate(close, r["stop"], long, b, i)
        if c is None:
            notakeable_cls += 1
        else:
            cls.append({"day": r["day"], "sym": r["sym"], "et": r["et"],
                        "status": r["status"], "traded": True,
                        "r": c[0], "pnl": c[0] * RISK, "tag": c[1]})
    return pub, cls, {
        "rows_attempted": len(tr),
        "bars_missing_or_last_bar": missing,
        "published_fill_not_takeable": notakeable_pub,
        "close_fill_not_takeable": notakeable_cls,
        "head_start_mean_r": round(statistics.fmean(head_r), 4) if head_r else None,
        "head_start_median_r": round(statistics.median(head_r), 4) if head_r else None,
        "head_start_mean_dollars": round(statistics.fmean(head_dollars), 0)
        if head_dollars else None,
        "head_start_pct_positive": round(
            sum(1 for x in head_r if x > 0.005) / len(head_r) * 100, 1) if head_r else None,
        "head_start_pct_over_half_r": round(
            sum(1 for x in head_r if x >= 0.5) / len(head_r) * 100, 1) if head_r else None,
        "head_start_pct_over_1r": round(
            sum(1 for x in head_r if x >= 1.0) / len(head_r) * 100, 1) if head_r else None,
        "n_measured": len(head_r),
    }


def first_per_day(rows):
    byday = {}
    for r in rows:
        byday.setdefault(r["day"], []).append(r)
    return [sorted(v, key=ekey)[0] for _, v in sorted(byday.items())]


# ------------------------------------------------------------------- main

def main():
    out = {}

    out["census"] = census()
    days_all = out["census"][0].pop("_days")
    for c in out["census"][1:]:
        c.pop("_days", None)

    print("\n   %-44s %7s %10s %11s %13s"
          % ("book", "traded", "$/day all", "$/day 1ad", "1ad live-2R"))
    for c in out["census"]:
        print("   %-44s %7d %10s %11s %13s"
              % (c["source"][:44], c["traded_counted"],
                 "$%.0f" % c["everything"]["per_day"],
                 "$%.0f" % c["one_a_day"]["per_day"],
                 "$%.0f" % c["one_a_day_live_2R_clip"]["per_day"]))

    print("\nB. THE PUBLISHED FILL, RECOMPUTED FROM THE WORKING-TREE BOOK",
          flush=True)
    book = json.load(open(BOOK, encoding="utf-8"))
    rows, nd = book["trades"], book["meta"]["sessions"]
    sess = sorted({r["day"] for r in rows})
    pub_all = shipped_rows(rows)
    pub_1ad = oneaday_rows(rows)
    out["published"] = {
        "everything": price(pub_all, nd),
        "one_a_day": price(pub_1ad, nd),
        "everything_ci": day_ci(pub_all, sess, "published, everything"),
        "one_a_day_ci": day_ci(pub_1ad, sess, "published, one a day"),
    }
    for k in ("everything", "one_a_day"):
        s, ci = out["published"][k], out["published"][k + "_ci"]
        print("   %-14s %5d trades  %.1f%% win  $%.0f/day  [%s to %s]  meanR %+.4f"
              % (k, s["trades"], s["win_pct"], s["per_day"],
                 "$%.0f" % ci["ci95_low"], "$%.0f" % ci["ci95_high"], s["mean_r"]))

    print("\nC/D. MATCHED PAIR OVER THE ARCHIVED BARS (this reads ~4.5k cached "
          "day files, ~1-2 min)", flush=True)
    sim_pub, sim_cls, diag = matched_pair(rows)
    out["diagnostics"] = diag
    print("   head start at the instant the signal exists:")
    print("     mean %+.4fR  (%s)   median %+.4fR   over half an R %.1f%%   "
          "over a full R %.1f%%"
          % (diag["head_start_mean_r"], "$%.0f" % diag["head_start_mean_dollars"],
             diag["head_start_median_r"], diag["head_start_pct_over_half_r"],
             diag["head_start_pct_over_1r"]))
    print("   book's own measured edge, everything taken: %+.4fR"
          % out["published"]["everything"]["mean_r"])
    print("   trades not takeable at the close (close already at/through the "
          "stop): %d of %d" % (diag["close_fill_not_takeable"],
                               diag["rows_attempted"]))

    out["matched_pair"] = {}
    for name, sim in (("published_fill", sim_pub), ("entry_minute_close", sim_cls)):
        one = first_per_day(sim)
        out["matched_pair"][name] = {
            "everything": price(sim, nd),
            "one_a_day": price(one, nd),
            "everything_ci": day_ci(sim, sess, name + ", everything"),
            "one_a_day_ci": day_ci(one, sess, name + ", one a day"),
            "exit_mix": {t: sum(1 for r in sim if r["tag"] == t)
                         for t in ("target", "stop", "eod")},
        }
    print("\n   %-22s %7s %7s %11s %24s" %
          ("simple 2R sim", "trades", "win%", "$/day", "95% interval"))
    for name in ("published_fill", "entry_minute_close"):
        for pol in ("everything", "one_a_day"):
            s = out["matched_pair"][name][pol]
            ci = out["matched_pair"][name][pol + "_ci"]
            print("   %-22s %7d %6.1f%% %11s %24s"
                  % ("%s / %s" % (name[:12], pol[:8]), s["trades"], s["win_pct"],
                     "$%.0f" % s["per_day"],
                     "[$%.0f to $%.0f]" % (ci["ci95_low"], ci["ci95_high"])))

    # the paired difference, day by day - the fill's price, with its own bar
    print("\n   the fill, paired by session:", flush=True)
    out["fill_cost"] = {}
    for pol, fn in (("everything", lambda x: x), ("one_a_day", first_per_day)):
        a = {d: 0.0 for d in sess}
        b = {d: 0.0 for d in sess}
        for r in fn(sim_pub):
            a[r["day"]] = a.get(r["day"], 0.0) + r["pnl"]
        for r in fn(sim_cls):
            b[r["day"]] = b.get(r["day"], 0.0) + r["pnl"]
        diffv = [b[d] - a[d] for d in sess]
        rng = random.Random(SEED)
        n = len(diffv)
        means = sorted(sum(rng.choices(diffv, k=n)) / n for _ in range(BOOTS))
        out["fill_cost"][pol] = {
            "mean_daily_change": round(sum(diffv) / n, 0),
            "ci95_low": round(means[int(BOOTS * 0.025)], 0),
            "ci95_high": round(means[int(BOOTS * 0.975)], 0),
        }
        e = out["fill_cost"][pol]
        print("     %-12s paying the close changes the day by %s   "
              "95%% CI [%s, %s]"
              % (pol, "$%.0f" % e["mean_daily_change"],
                 "$%.0f" % e["ci95_low"], "$%.0f" % e["ci95_high"]))

    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\nwrote %s" % OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
