"""G76 — price every rebuilt book side by side, with error bars.

Reads the books `research/g76_rebuild_book.py` writes and prices each one on
`research/g72_suppress_price.py`'s arithmetic — imported, not re-typed, so
"trades / win rate / dollars a day / months green / weeks green / worst
drawdown" mean exactly what they mean everywhere else in this repo.

Two policies, both reported for every model:
  ALL     every trade the engine takes  (`shipped_rows`)
  1/DAY   the first trade of each day, then done  (`oneaday_rows`)

and for the resting-limit model a third:
  1/DAY-SIGNAL   the FIRST FIRED SIGNAL of the day gets the order, and that is
                 the only order placed. If it never fills there is no trade that
                 day. This is the version a person with a job can actually run:
                 you do not get to watch which of the day's five signals fills.

ERROR BARS. Days are the resampling unit (500 sessions, drawn with replacement,
10,000 times) for dollars-a-day, dollars-a-month, mean R and win rate; months
and weeks are resampled as themselves for months-green / weeks-green; the
drawdown bar resamples days and walks the resampled order. A 95% interval whose
LOWER bound is above zero is a model that clears zero.

Usage:  python research/g76_rebuild_report.py
Writes: research/g76_rebuild_numbers.json
"""
from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from g72_suppress_price import (stats, shipped_rows, oneaday_rows, load,  # noqa: E402
                                iso_week, drawdown, ekey, RISK)

MODELS = [
    ("head", "the book as published (look-ahead fill)"),
    ("close", "A — the signal minute's CLOSE"),
    ("next_open", "B — the NEXT minute's OPEN"),
    ("limit", "C — a resting limit AT the level, filled only on a later trade through it"),
    ("late1", "D — one minute late (open of signal+2)"),
    ("late2", "D — two minutes late (open of signal+3)"),
    ("late5", "five minutes late (open of signal+6)"),
]
N_BOOT = 10000
SEED = 20260829


# ----------------------------------------------------------------- policies

def oneaday_signal_rows(rows):
    """One order a day, placed on the day's FIRST FIRED SIGNAL, then done.

    The candidate stream is the same one `oneaday_rows` uses (fired-and-traded
    plus the rows R31's halt blocked -- under one-a-day the halt cannot have
    fired yet) PLUS the unfilled rows, because an order that never filled is
    still the order you placed and used up your day. Ordered by SIGNAL time,
    not fill time: you cannot know in advance which of the day's orders will be
    touched.
    """
    byday = {}
    for r in rows:
        ordered = ((r["status"] == "fired" and r.get("traded"))
                   or r["status"] == "halted"
                   or (r["status"] == "unfilled" and r.get("sig_status") == "fired"
                       and r.get("grade") != "C"))
        if ordered:
            byday.setdefault(r["day"], []).append(r)
    out = []
    for _d, v in sorted(byday.items()):
        first = sorted(v, key=lambda r: (r.get("sig_et", r["et"]), r["sym"]))[0]
        if first["status"] != "unfilled":
            out.append(first)
    return out


# ----------------------------------------------------------------- bootstrap

def _pct(xs, lo=2.5, hi=97.5):
    xs = sorted(xs)
    n = len(xs)
    return (round(xs[int(lo / 100 * n)], 1), round(xs[min(n - 1, int(hi / 100 * n))], 1))


def bootstrap(rows, n_days: int, n_boot: int = N_BOOT) -> dict:
    """Per-day resampling. Returns 95% intervals for the money numbers."""
    rng = random.Random(SEED)
    byday = {}
    for r in rows:
        byday.setdefault(r["day"], []).append(r)
    days = sorted(byday)
    if not days:
        return {}
    # one entry per SESSION in the book, including the ones with no trade --
    # a day the model never fills on is a real zero, not a missing sample
    pnl_by_day = [sum(x["pnl"] for x in byday[d]) for d in days]
    pnl_by_day += [0.0] * max(0, n_days - len(days))
    per_trade = [x["pnl"] for x in rows]
    wins = [1 if x["pnl"] > 0 else 0 for x in rows if x["pnl"] != 0]

    nd = len(pnl_by_day)
    day_means, dds = [], []
    for _ in range(n_boot):
        s = [pnl_by_day[rng.randrange(nd)] for _ in range(nd)]
        day_means.append(sum(s) / nd)
        dds.append(drawdown(s))
    tr_means, wrs = [], []
    nt = len(per_trade)
    for _ in range(n_boot):
        s = [per_trade[rng.randrange(nt)] for _ in range(nt)]
        tr_means.append(sum(s) / nt)
    nw = len(wins)
    for _ in range(n_boot):
        wrs.append(sum(wins[rng.randrange(nw)] for _ in range(nw)) / nw * 100)

    by_m, by_w = {}, {}
    for r in rows:
        by_m[r["day"][:7]] = by_m.get(r["day"][:7], 0.0) + r["pnl"]
        by_w[iso_week(r["day"])] = by_w.get(iso_week(r["day"]), 0.0) + r["pnl"]
    mv, wv = list(by_m.values()), list(by_w.values())
    mg = [sum(1 for _ in range(len(mv)) if mv[rng.randrange(len(mv))] > 0) / len(mv) * 100
          for _ in range(n_boot)] if mv else []
    wg = [sum(1 for _ in range(len(wv)) if wv[rng.randrange(len(wv))] > 0) / len(wv) * 100
          for _ in range(n_boot)] if wv else []

    months = len(by_m) or 1
    return {
        "per_day_ci": _pct(day_means),
        "per_month_ci": tuple(round(x * nd / months, 0) for x in _pct(day_means)),
        "per_trade_ci": _pct(tr_means),
        "mean_r_ci": tuple(round(x / RISK, 3) for x in _pct(tr_means)),
        "win_pct_ci": _pct(wrs),
        "worst_drawdown_ci": _pct(dds),
        "months_green_pct_ci": _pct(mg) if mg else None,
        "weeks_green_pct_ci": _pct(wg) if wg else None,
        "clears_zero": _pct(day_means)[0] > 0,
    }


def paired_vs(rows_a, rows_b, n_days: int, n_boot: int = N_BOOT) -> dict:
    """Model A minus model B, day by day, resampled. Same 500 sessions."""
    rng = random.Random(SEED + 1)
    da, db = {}, {}
    for r in rows_a:
        da[r["day"]] = da.get(r["day"], 0.0) + r["pnl"]
    for r in rows_b:
        db[r["day"]] = db.get(r["day"], 0.0) + r["pnl"]
    days = sorted(set(da) | set(db))
    diff = [da.get(d, 0.0) - db.get(d, 0.0) for d in days]
    diff += [0.0] * max(0, n_days - len(diff))
    n = len(diff)
    means = [sum(diff[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot)]
    obs = sum(diff) / n
    return {"per_day_delta": round(obs, 1), "ci": _pct(means)}


# --------------------------------------------------------------------- main

def price(path: Path) -> dict:
    meta, rows = load(path)
    nd = meta["sessions"]
    out = {"meta": {k: meta.get(k) for k in
                    ("generated", "model", "first", "last", "sessions", "signals",
                     "traded", "halted", "unfilled", "loss_halt", "fill_bar_live",
                     "status_hist")},
           "rows": rows, "n_days": nd}
    for name, fn in (("all", shipped_rows), ("one_a_day", oneaday_rows),
                     ("one_a_day_signal", oneaday_signal_rows)):
        sel = fn(rows)
        s = stats(sel, nd)
        s["per_month"] = round(s["total_dollars"] / max(1, s["months"]), 0) if s else 0
        s.update(bootstrap(sel, nd))
        out[name] = s
        out[name + "_rows"] = sel
    # fill statistics -- only meaningful for the resting-limit model
    ordered = [r for r in rows if (r.get("sig_status") == "fired"
                                   and r.get("grade") != "C")]
    unf = [r for r in ordered if r["status"] == "unfilled"]
    out["fills"] = {
        "orders_placed": len(ordered),
        "never_filled": len(unf),
        "never_filled_pct": round(len(unf) / len(ordered) * 100, 1) if ordered else 0.0,
        "median_lag_min": (statistics.median([r["lag"] for r in ordered
                                              if r["status"] != "unfilled"])
                           if len(ordered) > len(unf) else None),
    }
    return out


def main():
    books = {}
    for m, _d in MODELS:
        p = ROOT / "research" / ("g76_book_%s.json" % m)
        if p.exists():
            print("pricing %s ..." % p.name, flush=True)
            books[m] = price(p)
        else:
            print("MISSING %s" % p.name, flush=True)
    live = ROOT / "research" / "g76_book_limit_live.json"
    if live.exists():
        print("pricing %s ..." % live.name, flush=True)
        books["limit_live"] = price(live)

    if "head" not in books:
        raise SystemExit("need the head book to compare against")

    out = {"models": {}, "descriptions": dict(MODELS)}
    for m, b in books.items():
        rec = {k: b[k] for k in ("meta", "all", "one_a_day", "one_a_day_signal", "fills")}
        rec["n_days"] = b["n_days"]
        if m != "head":
            for pol in ("all", "one_a_day"):
                rec[pol]["vs_head"] = paired_vs(b[pol + "_rows"],
                                                books["head"][pol + "_rows"],
                                                b["n_days"])
        out["models"][m] = rec

    (ROOT / "research" / "g76_rebuild_numbers.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")

    # ------------------------------------------------------------- printout
    def line(m, pol):
        s = out["models"][m][pol]
        if not s:
            return
        print("  %-10s %-16s n=%-5d win %4.1f%%  $/day %6s [%6s..%6s]  "
              "$/mo %8s  meanR %+.3f [%+.3f..%+.3f]  months %d/%d  weeks %d/%d  DD $%s"
              % (m, pol, s["trades"], s["win_pct"],
                 format(int(s["per_day"]), ","),
                 format(int(s["per_day_ci"][0]), ","), format(int(s["per_day_ci"][1]), ","),
                 format(int(s["per_month"]), ","),
                 s["mean_r"], s["mean_r_ci"][0], s["mean_r_ci"][1],
                 s["months_green"], s["months"], s["weeks_green"], s["weeks"],
                 format(int(s["worst_drawdown"]), ",")))

    for pol in ("all", "one_a_day", "one_a_day_signal"):
        print("\n===== %s =====" % pol.upper())
        for m in books:
            line(m, pol)
    print("\nfills:")
    for m, b in out["models"].items():
        f = b["fills"]
        print("  %-11s orders %5d  never filled %5d (%4.1f%%)  median lag %s min"
              % (m, f["orders_placed"], f["never_filled"], f["never_filled_pct"],
                 f["median_lag_min"]))
    print("\nwrote research/g76_rebuild_numbers.json")


if __name__ == "__main__":
    main()
