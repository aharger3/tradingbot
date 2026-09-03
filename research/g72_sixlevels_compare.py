"""G7.2 track `sixlevels` -- score the arm books written by g72_sixlevels_book.py.

Reports, per arm, the four numbers the ticket asks for plus the level mix:

  * dollars per trade, on every trade the book takes (1R = $1,000)
  * dollars per DAY under one-trade-a-day, the policy Austin is actually going
    to run (candidate stream and walk copied from research/g71_board_check.py)
  * months green / weeks green      (definitions from research/g71_firsts_policy.py)
  * worst drawdown, in dollars, on the calendar of all candidate days
  * which level each trade was keyed to, so "did the opening range and the
    pivots actually go away" is checked rather than assumed

Also prints the PAIRED delta against the base arm on trades both arms took
(same symbol, day, entry minute, direction), with a 95% interval, because every
A/B in this project moves less than its own unpaired error bar.

Usage:
    python research/g72_sixlevels_compare.py
    python research/g72_sixlevels_compare.py --out research/g72_sixlevels_compare.json
"""
from __future__ import annotations
import argparse, json, math, os, statistics as st
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ARMS = ["base", "hodlod", "hodfast", "noor", "nopivot", "sixlevels", "sixfast"]
LABEL = {
    "base": "shipped today (OR gates, HOD/LOD off, pivots on)",
    "hodlod": "+ HOD/LOD turned on, F3 staleness gates as shipped",
    "hodfast": "+ HOD/LOD turned on with the F3 staleness gates relaxed",
    "noor": "- opening range out of the gating set",
    "nopivot": "- pivots gate nothing",
    "sixlevels": "HIS SIX (PDH PDL PMH PML HOD LOD), F3 gates as shipped",
    "sixfast": "HIS SIX, F3 staleness gates relaxed (>=20 bars in, extreme >=12 bars old)",
}
R_DOLLARS = 1000.0


def iso_week(day):
    y, w, _ = date.fromisoformat(day).isocalendar()
    return "%04d-W%02d" % (y, w)


def load(arm):
    p = os.path.join(HERE, "g72_arm_%s.json" % arm)
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def candidates(rows):
    """What a human could have taken: a fired-and-traded row, plus the rows the
    account-wide loss halt blocked (they carry every measured field).
    research/g71_board_check.py uses exactly this stream."""
    return [r for r in rows
            if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted"]


def ekey(r):
    return (r["day"], r["et"], r["sym"])


def one_a_day(cand):
    byday = defaultdict(list)
    for r in cand:
        byday[r["day"]].append(r)
    return [sorted(byday[d], key=ekey)[0] for d in sorted(byday)]


def curve(rows, all_days):
    day_r = defaultdict(float)
    for r in rows:
        day_r[r["day"]] += r["r"]
    mon, wk = defaultdict(float), defaultdict(float)
    for d, v in day_r.items():
        mon[d[:7]] += v
        wk[iso_week(d)] += v
    cum = peak = dd = 0.0
    for d in all_days:
        cum += day_r.get(d, 0.0)
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    months = sorted({d[:7] for d in all_days})
    weeks = sorted({iso_week(d) for d in all_days})
    return {
        "months_green": sum(1 for m in months if mon.get(m, 0.0) > 0),
        "months_total": len(months),
        "weeks_green": sum(1 for w in weeks if wk.get(w, 0.0) > 0),
        "weeks_total": len(weeks),
        "max_dd_dollars": round(dd * R_DOLLARS),
        "green_days": sum(1 for v in day_r.values() if v > 0),
        "days_traded": len(day_r),
    }


def money(rows):
    n = len(rows)
    if not n:
        return {"n": 0}
    wins = sum(1 for r in rows if r["out"] == "win")
    losses = sum(1 for r in rows if r["out"] == "loss")
    total = sum(r["r"] for r in rows)
    return {
        "n": n,
        "win_pct": round(wins / (wins + losses) * 100, 1) if (wins + losses) else 0.0,
        "per_trade_dollars": round(total / n * R_DOLLARS),
        "total_dollars": round(total * R_DOLLARS),
        "mean_r": round(total / n, 4),
    }


HIS_SIX = {"PDH", "PDL", "PMH", "PML", "HOD", "LOD"}


def bucket(name):
    """Collapse the 160-odd `pivot high @09:37` spellings into one family, and
    say plainly whether the level is one of Austin's six. The `not-his:` prefix
    is stamped on the row by backtest_2y.level_label."""
    n = (name or "(none)").replace("not-his: ", "")
    if n.startswith("pivot "):
        return "pivot structure"
    if n.startswith("OR "):
        return "opening range"
    if n in HIS_SIX:
        return n
    return n


def level_mix(rows):
    c = defaultdict(int)
    for r in rows:
        c[bucket(r.get("level_name") or r.get("level"))] += 1
    return dict(sorted(c.items(), key=lambda kv: -kv[1]))


def paired(a_rows, b_rows):
    """Delta on trades BOTH arms took at the same moment."""
    ai = {(r["sym"], r["day"], r["et"], r["dir"]): r["r"] for r in a_rows}
    bi = {(r["sym"], r["day"], r["et"], r["dir"]): r["r"] for r in b_rows}
    keys = sorted(set(ai) & set(bi))
    d = [bi[k] - ai[k] for k in keys]
    if len(d) < 2:
        return {"shared": len(keys), "mean_delta_r": None, "ci95": None}
    m = st.mean(d)
    se = st.stdev(d) / math.sqrt(len(d))
    return {"shared": len(keys), "moved": sum(1 for x in d if abs(x) > 1e-9),
            "mean_delta_r": round(m, 4), "ci95": round(1.96 * se, 4),
            "mean_delta_dollars": round(m * R_DOLLARS)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "g72_sixlevels_compare.json"))
    a = ap.parse_args()

    books = {arm: load(arm) for arm in ARMS}
    missing = [k for k, v in books.items() if v is None]
    if missing:
        print("MISSING arm books: %s -- run g72_sixlevels_book.py first" % ", ".join(missing))
    have = [k for k in ARMS if books[k]]

    # the calendar every arm is scored on: the union of candidate days, so a day
    # one arm sits out is a flat day, not a missing one
    all_days = set()
    for k in have:
        all_days |= {r["day"] for r in candidates(books[k]["trades"])}
    all_days = sorted(all_days)

    out = {"calendar_days": len(all_days), "arms": {}}
    base_cand = candidates(books["base"]["trades"]) if books.get("base") else []
    base_one = one_a_day(base_cand) if base_cand else []

    for k in have:
        cand = candidates(books[k]["trades"])
        one = one_a_day(cand)
        rec = {
            "label": LABEL[k],
            "meta_signals": books[k]["meta"]["signals"],
            "meta_traded": books[k]["meta"]["traded"],
            "all_trades": dict(money(cand), **curve(cand, all_days)),
            "one_a_day": dict(money(one), **curve(one, all_days)),
            "level_mix_all": level_mix(cand),
            "level_mix_one_a_day": level_mix(one),
        }
        rec["one_a_day"]["per_day_dollars"] = round(
            sum(r["r"] for r in one) / len(all_days) * R_DOLLARS) if all_days else 0
        rec["one_a_day"]["per_month_dollars"] = rec["one_a_day"]["per_day_dollars"] * 21
        if k != "base" and base_cand:
            rec["paired_vs_base_all"] = paired(base_cand, cand)
            rec["paired_vs_base_one_a_day"] = paired(base_one, one)
        out["arms"][k] = rec

    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)

    hdr = ("%-10s %7s %7s %8s %10s %7s %8s %9s" %
           ("arm", "trades", "win%", "$/trade", "total $", "months", "weeks", "worst DD"))
    print("\nALL TRADES\n" + hdr)
    print("-" * len(hdr))
    for k in have:
        m, c = out["arms"][k]["all_trades"], out["arms"][k]["all_trades"]
        print("%-10s %7d %6.1f%% %8s %10s %4d/%-2d %4d/%-3d %9s" %
              (k, m["n"], m["win_pct"], "${:,}".format(m["per_trade_dollars"]),
               "${:,}".format(m["total_dollars"]), c["months_green"], c["months_total"],
               c["weeks_green"], c["weeks_total"], "${:,}".format(c["max_dd_dollars"])))

    hdr2 = ("%-10s %7s %7s %8s %9s %7s %8s %9s" %
            ("arm", "days", "win%", "$/day", "$/month", "months", "weeks", "worst DD"))
    print("\nONE TRADE A DAY\n" + hdr2)
    print("-" * len(hdr2))
    for k in have:
        m = out["arms"][k]["one_a_day"]
        print("%-10s %7d %6.1f%% %8s %9s %4d/%-2d %4d/%-3d %9s" %
              (k, m["n"], m["win_pct"], "${:,}".format(m["per_day_dollars"]),
               "${:,}".format(m["per_month_dollars"]), m["months_green"],
               m["months_total"], m["weeks_green"], m["weeks_total"],
               "${:,}".format(m["max_dd_dollars"])))

    print("\nPAIRED vs base (all trades)")
    for k in have:
        if k == "base":
            continue
        p = out["arms"][k].get("paired_vs_base_all", {})
        print("  %-10s shared=%s moved=%s  dR=%s +/- %s" %
              (k, p.get("shared"), p.get("moved"), p.get("mean_delta_r"), p.get("ci95")))

    print("\nLEVEL MIX (all trades)")
    for k in have:
        mix = out["arms"][k]["level_mix_all"]
        tot = sum(mix.values()) or 1
        top = ", ".join("%s %d (%.0f%%)" % (n, v, 100 * v / tot)
                        for n, v in list(mix.items())[:8])
        print("  %-10s %s" % (k, top))
    print("\nwrote", a.out)


if __name__ == "__main__":
    main()
