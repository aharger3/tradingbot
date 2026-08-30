"""Adversarial re-verification of research/g80_tradability.py.

Independent recompute -- reads the book and the cached bars directly with csv,
does NOT import g80_tradability and does NOT reuse its helpers. Checks:

  1. traded-row count and bar-lookup success
  2. untradeable count under the stated proxy
  3. dollars/day all-trades and one-a-day, as-is vs tradeable-only
  4. months green, mean R, win rate
  5. entry_i <-> et alignment (is bars[entry_i] really the entry minute?)
  6. LOOK-AHEAD sensitivity: same filter using only the PRIOR bar's range
     (information a robot actually has before the entry minute completes)
  7. mean R = w*T - (1-w) consistency
  8. error-bar check on every claimed difference

Usage: python research/g80_verify_2.py
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "research" / "bt2y_trades.json"
ARCHIVE = ROOT / "data_archive"

SPREAD_FRAC = 0.10
ONE_CENT = 0.01
MIN_MULT = 2.0
ERROR_BAR_R = 1.5799


def read_rth(sym: str, day: str):
    """Own CSV reader; same RTH window filter as polygon_feed.rth()."""
    p = ARCHIVE / sym / f"{day}.csv"
    if not p.exists():
        return None
    out = []
    with open(p, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # a few cached files use a space separator instead of "T"
            hhmmss = row["Datetime"].replace(" ", "T").split("T")[1][:8]
            if "09:30:00" <= hhmmss < "16:00:00":
                out.append((hhmmss, float(row["High"]), float(row["Low"])))
    return out


def mean(xs):
    return statistics.mean(xs) if xs else 0.0


def stats(rows, label):
    n = len(rows)
    pnl = sum(r["pnl"] for r in rows)
    days = sorted({r["day"] for r in rows})
    # one trade a day: earliest by (et, seq) across all symbols that day
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(r)
    oad = [sorted(v, key=lambda t: (t.get("et", ""), t.get("seq", 0)))[0]
           for v in by_day.values()]
    oad_pnl = sum(r["pnl"] for r in oad)
    months = defaultdict(float)
    for r in rows:
        months[r["ym"]] += r["pnl"]
    w = sum(1 for r in rows if r["out"] == "win")
    l = sum(1 for r in rows if r["out"] == "loss")
    return {
        "label": label, "n": n, "total_pnl": pnl,
        "days": len(days),
        "dpd_all": pnl / len(days) if days else 0.0,
        "oad_n": len(oad), "oad_pnl": oad_pnl,
        "dpd_oad": oad_pnl / len(oad) if oad else 0.0,
        "months_green": sum(1 for v in months.values() if v > 0),
        "months_total": len(months),
        "win_rate": 100.0 * w / (w + l) if (w + l) else 0.0,
        "mean_r": mean([r["r"] for r in rows]),
    }


def pctile(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] if f == c else xs[f] + (xs[c] - xs[f]) * (k - f)


def main():
    book = json.loads(BOOK.read_text())
    traded = [t for t in book["trades"] if t.get("traded")]
    print(f"[1] traded rows                 : {len(traded)}")

    bar_cache = {}
    usable, missing = [], 0
    misaligned = 0
    for t in traded:
        key = (t["sym"], t["day"])
        if key not in bar_cache:
            if len(bar_cache) > 80:
                bar_cache.clear()
            bar_cache[key] = read_rth(*key)
        b = bar_cache[key]
        ei = t.get("entry_i")
        if b is None or ei is None or ei < 0 or ei >= len(b):
            missing += 1
            continue
        ts, hi, lo = b[ei]
        if t.get("et") and ts[:5] != t["et"]:
            misaligned += 1
        spread = max(ONE_CENT, SPREAD_FRAC * (hi - lo))
        stop_dist = abs(t["entry"] - t["stop"])
        # no-look-ahead variant: prior completed bar's range
        if ei >= 1:
            _, phi, plo = b[ei - 1]
            spread_prior = max(ONE_CENT, SPREAD_FRAC * (phi - plo))
        else:
            spread_prior = spread
        usable.append({**t,
                       "stop_cents": stop_dist * 100,
                       "mult": stop_dist / spread,
                       "mult_prior": stop_dist / spread_prior,
                       "untradeable": stop_dist / spread < MIN_MULT,
                       "untradeable_prior": stop_dist / spread_prior < MIN_MULT})

    print(f"[1] bar lookup failed           : {missing}")
    print(f"[5] entry_i/et MISALIGNED rows  : {misaligned} of {len(usable)}")

    unt = [r for r in usable if r["untradeable"]]
    trd = [r for r in usable if not r["untradeable"]]
    print(f"[2] untradeable (stop < 2x)     : {len(unt)} of {len(usable)} "
          f"({100.0*len(unt)/len(usable):.2f}%)")

    a = stats(usable, "as-is")
    b_ = stats(trd, "tradeable-only")
    for s in (a, b_):
        print(f"[3] {s['label']:16s} n={s['n']:5d} $/day(all)=${s['dpd_all']:,.0f} "
              f"$/day(1aday)=${s['dpd_oad']:,.0f} win={s['win_rate']:.1f}% "
              f"meanR={s['mean_r']:+.4f} green={s['months_green']}/{s['months_total']}")

    print(f"[3] $/day all delta             : ${a['dpd_all']-b_['dpd_all']:,.0f}")
    print(f"[3] $/day 1-a-day delta         : ${a['dpd_oad']-b_['dpd_oad']:,.0f}")

    # removed slice
    print(f"[2] removed slice meanR         : {mean([r['r'] for r in unt]):+.4f} "
          f"(n={len(unt)}, pnl=${sum(r['pnl'] for r in unt):,.0f}) "
          f"vs rest {mean([r['r'] for r in trd]):+.4f}")

    sc = [r["stop_cents"] for r in usable]
    print(f"[2] stop cents p10/med/p90      : {pctile(sc,.10):.1f} / "
          f"{pctile(sc,.5):.1f} / {pctile(sc,.90):.1f}")
    u10 = sum(1 for x in sc if x < 10.0)
    print(f"[2] stops under 10c             : {u10} of {len(usable)} "
          f"({100.0*u10/len(usable):.1f}%)")

    # 6. look-ahead sensitivity
    unt_p = [r for r in usable if r["untradeable_prior"]]
    trd_p = [r for r in usable if not r["untradeable_prior"]]
    bp = stats(trd_p, "tradeable(prior-bar)")
    both = sum(1 for r in usable if r["untradeable"] and r["untradeable_prior"])
    print(f"[6] PRIOR-BAR proxy untradeable : {len(unt_p)} of {len(usable)} "
          f"({100.0*len(unt_p)/len(usable):.2f}%); overlap with entry-bar set = {both}")
    print(f"[6] prior-bar tradeable-only    : n={bp['n']} $/day(all)=${bp['dpd_all']:,.0f} "
          f"meanR={bp['mean_r']:+.4f} green={bp['months_green']}/{bp['months_total']}")

    # 7. mean R = w*T - (1-w)  =>  implied average winner size
    for s, rows in ((a, usable), (b_, trd)):
        w = s["win_rate"] / 100.0
        implied_T = (s["mean_r"] + (1 - w)) / w if w else float("nan")
        actual_win_r = mean([r["r"] for r in rows if r["out"] == "win"])
        actual_loss_r = mean([r["r"] for r in rows if r["out"] == "loss"])
        other = [r for r in rows if r["out"] not in ("win", "loss")]
        print(f"[7] {s['label']:16s} w={w:.4f} impliedT={implied_T:+.3f} "
              f"actual meanR(win)={actual_win_r:+.3f} meanR(loss)={actual_loss_r:+.3f} "
              f"non-win/loss rows={len(other)}")

    # 8. error bar
    d = abs(a["mean_r"] - b_["mean_r"])
    print(f"[8] meanR diff {d:.4f}R vs bar {ERROR_BAR_R}R -> "
          f"{'TIE (inside bar)' if d < ERROR_BAR_R else 'OUTSIDE BAR'}")
    dp = abs(a["mean_r"] - bp["mean_r"])
    print(f"[8] meanR diff (prior-bar) {dp:.4f}R -> "
          f"{'TIE (inside bar)' if dp < ERROR_BAR_R else 'OUTSIDE BAR'}")


if __name__ == "__main__":
    main()
