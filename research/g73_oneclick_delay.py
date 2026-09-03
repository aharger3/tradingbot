"""G7.3 / oneclick — what a human's reaction time costs the book.

The question: Austin is busy 09:30-11:00. If the engine finds a setup and he
clicks a prepared order 1, 2, 5 or 15 minutes later, what happens to the money?

METHOD (deliberately minimal, so it cannot invent an edge)

  * The signal, the stop and the target are UNCHANGED. They are what the alert
    carries. A late human uses the same plan.
  * Because the stop and target prices do not move, THE EXIT DOES NOT MOVE
    EITHER -- the trade leaves at the same price on the same bar whether he got
    in at 09:43 or 09:58. So this rig reuses the book's own exit (exit price,
    exit bar) and changes exactly one thing: the fill.
  * R is recomputed off the new fill, because risk per share changed and
    1R = $1,000 is fixed:   long  R = (exit - fill) / (fill - stop)
    That is why every stop-out is still exactly -1.00R at any delay: size
    shrinks to match. Delay does not make a loser lose more. It makes a winner
    win less, and it makes some trades unavailable.

TWO CALIBRATION ROWS, and the gap between them is the whole finding:

    BOOK   fill = the book's own entry price. MUST reproduce the published
           mean R exactly, or this rig is wrong and nothing else may be quoted.
    CLOSE  fill = the CLOSE of the signal bar -- the fastest price any decision
           taken ON that close could ever get.

  BOOK is better than CLOSE, and that gap is not human slowness. It is
  `signal_runner.fill_price`: when the bar closes at its own extreme (or at the
  session extreme, ON WATCH) the entry BOOKS AT THE LEVEL -- a price the bar
  traded earlier in that minute, before the signal existed. Only an order
  already resting at the level gets it. The census below counts how much of the
  book is that kind of fill.

  Then +0m is an instant robot buying at the next bar's open, and +1/+2/+5/+15
  are a human clicking that many minutes later.

  Three ways a delayed click gets nothing, all counted separately:
      MISSED  the trade already exited before he clicked
      DEAD    price is already at/through the stop -- entering is a knife catch
      GONE    price is already at/through the target -- he would be buying his
              own exit

  SIZE CAP sensitivity: a fill landing a hair from the stop implies an enormous
  position. The capped variant refuses to let risk-per-share fall below 25% of
  the plan's (i.e. at most 4x the intended size).

Policies scored, the same two the board quotes:
  shipped    every signal the engine trades
  one-a-day  first candidate of the day -- and under delay, the first candidate
             he can actually GET, which is the honest human model

Usage:  python research/g73_oneclick_delay.py
Writes: research/g73_oneclick_delay.json
"""
import argparse, json, random, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

import polygon_feed as pf                                            # noqa: E402
from g72_suppress_price import load, stats, ekey, RISK               # noqa: E402

DELAYS = [-2, -1, 0, 1, 2, 5, 15]
LABEL = {-2: "BOOK ", -1: "CLOSE"}
SIZE_CAP = 0.25          # risk/share may not fall below 25% of the plan's
BOOT = 4000              # bootstrap resamples for the per-day dollar CI


def mins(hhmm):
    return int(hhmm[:2]) * 60 + int(hhmm[3:5])


# ------------------------------------------------------------ the one measurement

def price_at(row, bars, delay):
    """(tag, fill). tag in {"filled","missed","nobars"}; price checks come after."""
    ei = row["entry_i"]
    if ei >= len(bars):
        return "nobars", 0.0
    xi = min(row["entry_i"] + row["bars"], len(bars) - 1)
    if delay == -2:
        return "filled", row["entry"]
    if delay == -1:
        return "filled", bars[ei].close
    want = mins(bars[ei].timestamp) + 1 + delay      # alert lands at that close
    for i in range(ei, len(bars)):
        if mins(bars[i].timestamp) >= want:
            return ("missed", 0.0) if i > xi else ("filled", bars[i].open)
    return "missed", 0.0


def evaluate(row, bars, delay):
    """(tag, pnl, pnl_capped)."""
    tag, fill = price_at(row, bars, delay)
    if tag != "filled":
        return tag, 0.0, 0.0
    stop, tgt, exitpx, entry = row["stop"], row["target"], row["exit"], row["entry"]
    long = row["side"] == "L" or row["dir"] == "call"
    if long:
        if fill <= stop:
            return "dead", 0.0, 0.0
        if fill >= tgt:
            return "gone", 0.0, 0.0
        rps, plan = fill - stop, entry - stop
        r = (exitpx - fill) / rps
        r_cap = (exitpx - fill) / max(rps, SIZE_CAP * plan) if plan > 0 else r
    else:
        if fill >= stop:
            return "dead", 0.0, 0.0
        if fill <= tgt:
            return "gone", 0.0, 0.0
        rps, plan = stop - fill, stop - entry
        r = (fill - exitpx) / rps
        r_cap = (fill - exitpx) / max(rps, SIZE_CAP * plan) if plan > 0 else r
    return "filled", r * RISK, r_cap * RISK


# ---------------------------------------------------------------------- policies

def shipped_stream(rows):
    out = [r for r in rows if r.get("traded")]
    out.sort(key=ekey)
    return out


def oneaday_candidates(rows):
    """Per day, the candidate stream in time order (g72_suppress_price's set)."""
    byday = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            byday[r["day"]].append(r)
    return {d: sorted(v, key=ekey) for d, v in byday.items()}


def boot_per_day(taken, n_days, seed=7):
    """95% CI on dollars-per-session, resampling SESSIONS (not trades)."""
    if not taken:
        return [0.0, 0.0]
    byday = defaultdict(float)
    for t in taken:
        byday[t["day"]] += t["pnl"]
    vals = list(byday.values()) + [0.0] * max(0, n_days - len(byday))
    rng = random.Random(seed)
    n = len(vals)
    outs = sorted(sum(vals[rng.randrange(n)] for _ in range(n)) / n
                  for _ in range(BOOT))
    return [round(outs[int(.025 * BOOT)], 0), round(outs[int(.975 * BOOT)], 0)]


def score(taken, n_days, capped=False):
    return stats([{"day": t["day"], "pnl": (t["cap"] if capped else t["pnl"])}
                  for t in taken], n_days)


# --------------------------------------------------------------------------- main

def annotate(all_rows):
    """ONE pass over the archive: stamp every row with its fill mode and, for
    every delay, (tag, pnl, capped pnl). Grouped by (symbol, day) so each CSV is
    read exactly once."""
    groups = defaultdict(list)
    for r in all_rows:
        groups[(r["sym"], r["day"])].append(r)
    done = 0
    for (sym, day), rs in sorted(groups.items()):
        try:
            bars = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            bars = []
        for r in rs:
            ei = r["entry_i"]
            r["_mode"] = ("unknown" if not bars or ei >= len(bars) else
                          ("close" if abs(r["entry"] - bars[ei].close) <= 0.011
                           else "level"))
            r["_d"] = {d: (("nobars", 0.0, 0.0) if not bars else evaluate(r, bars, d))
                       for d in DELAYS}
        done += 1
        if done % 2500 == 0:
            print("  ...%d/%d symbol-days" % (done, len(groups)), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--book", default=str(ROOT / "research" / "bt2y_trades.json"))
    ap.add_argument("--out", default=str(ROOT / "research" / "g73_oneclick_delay.json"))
    args = ap.parse_args()

    meta, rows = load(Path(args.book))
    nd = meta["sessions"]
    ship = shipped_stream(rows)
    cands = oneaday_candidates(rows)

    need = {id(r): r for r in ship}
    for v in cands.values():
        for r in v:
            need[id(r)] = r
    print("annotating %d rows over the archive..." % len(need), flush=True)
    annotate(list(need.values()))

    census, census_r = defaultdict(int), defaultdict(float)
    for r in ship:
        census[r["_mode"]] += 1
        census_r[r["_mode"]] += r["r"]

    out = {"book": args.book, "generated": meta.get("generated"), "sessions": nd,
           "risk_dollars": RISK, "size_cap_frac": SIZE_CAP,
           "book_headline": {
               "shipped": stats(ship, nd),
               "one_a_day": stats([v[0] for _, v in sorted(cands.items())], nd)},
           "fill_mode_census": {k: {"rows": v, "mean_r": round(census_r[k] / v, 4)}
                                for k, v in census.items()},
           "shipped": {}, "one_a_day": {}, "by_fill_mode": {}}

    for d in DELAYS:
        taken, tally = [], defaultdict(int)
        for r in ship:
            tag, pnl, cap = r["_d"][d]
            tally[tag] += 1
            if tag == "filled":
                taken.append({"day": r["day"], "pnl": pnl, "cap": cap})
        s = score(taken, nd)
        s["capped"] = score(taken, nd, capped=True)
        s["per_day_ci95"] = boot_per_day(taken, nd)
        s["outcomes"] = dict(tally)
        s["offered"] = len(ship)
        out["shipped"][str(d)] = s

        taken2, tally2, blank = [], defaultdict(int), 0
        for day, cs in sorted(cands.items()):
            got = None
            for i, r in enumerate(cs):
                tag, pnl, cap = r["_d"][d]
                tally2[tag] += 1
                if tag == "filled":
                    got = {"day": day, "pnl": pnl, "cap": cap, "nth": i + 1}
                    break
            if got:
                taken2.append(got)
            else:
                blank += 1
        s2 = score(taken2, nd)
        s2["capped"] = score(taken2, nd, capped=True)
        s2["per_day_ci95"] = boot_per_day(taken2, nd)
        s2["outcomes"] = dict(tally2)
        s2["days_with_a_candidate"] = len(cands)
        s2["days_he_got_nothing"] = blank
        s2["not_the_first_candidate"] = sum(1 for t in taken2 if t["nth"] > 1)
        out["one_a_day"][str(d)] = s2

        fam = {}
        for mode in ("close", "level"):
            sub = [r for r in ship if r["_mode"] == mode]
            tk = [{"day": r["day"], "pnl": p, "cap": c}
                  for r in sub for (t, p, c) in [r["_d"][d]] if t == "filled"]
            fam[mode] = score(tk, nd)
            fam[mode]["offered"] = len(sub)
        out["by_fill_mode"][str(d)] = fam

        print("%s shipped: %4d filled  meanR %7.3f  $%7s/day [%s..%s]  |  "
              "one-a-day: %3d days  meanR %7.3f  $%6s/day [%s..%s]  |  "
              "close-fill meanR %6.3f   level-fill meanR %6.3f"
              % (LABEL.get(d, "+%2dm " % d), s.get("trades", 0), s.get("mean_r", 0),
                 s.get("per_day", 0), s["per_day_ci95"][0], s["per_day_ci95"][1],
                 s2.get("trades", 0), s2.get("mean_r", 0), s2.get("per_day", 0),
                 s2["per_day_ci95"][0], s2["per_day_ci95"][1],
                 fam["close"].get("mean_r", 0), fam["level"].get("mean_r", 0)),
              flush=True)

    print("\nfill-mode census (traded rows): %s"
          % {k: (v["rows"], v["mean_r"]) for k, v in out["fill_mode_census"].items()})
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()
